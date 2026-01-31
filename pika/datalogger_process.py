"""
DataloggerProcess - Dedicated process for high-frequency ADC sampling and data persistence.

This module implements the DataloggerProcess class that runs in a separate process
and handles ADC sampling, shared memory buffer writing, CSV file persistence,
and display manager integration.
"""

import os
import time
import csv
import math
import logging
import threading
from typing import Optional, Dict, Any, List, Callable
from multiprocessing import Event

from .shared_memory import SharedSampleBuffer, SharedConfigBuffer
from .adapters import create_adc_adapter, ADCAdapter
from .display_manager import DisplayManager

logger = logging.getLogger(__name__)


class DataloggerProcess:
    """
    Dedicated process for high-frequency ADC sampling and data persistence.
    
    This class moves the existing sampling logic to a separate process while
    integrating the ADC adapter pattern and shared memory buffer writing.
    It preserves the existing CSV batch writing mechanism for data persistence.
    """
    
    def __init__(
        self,
        shared_sample_buffer: SharedSampleBuffer,
        shared_config_buffer: SharedConfigBuffer,
        data_dir: str = "data",
        filename_prefix: str = "log",
        retention_days: int = 5,
        adc_type: str = "ads1115",
        adc_config: Optional[Dict[str, Any]] = None,
        display_config: Optional[Dict[str, Any]] = None,
        stop_event: Optional[Event] = None
    ):
        """
        Initialize the DataloggerProcess.
        
        Args:
            shared_sample_buffer: Shared memory buffer for sample data
            shared_config_buffer: Shared memory buffer for configuration
            data_dir: Directory for CSV data files
            filename_prefix: Prefix for CSV filenames
            retention_days: Number of days to retain old log files
            adc_type: Type of ADC adapter ('ads1115', 'mock')
            adc_config: Configuration for ADC adapter
            display_config: Configuration for display manager
            stop_event: Event to signal process shutdown
        """
        self.shared_sample_buffer = shared_sample_buffer
        self.shared_config_buffer = shared_config_buffer
        self.data_dir = data_dir
        self.filename_prefix = filename_prefix
        self.retention_days = retention_days
        self.adc_type = adc_type
        self.adc_config = adc_config or {}
        self.display_config = display_config or {}
        self.stop_event = stop_event or Event()
        
        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Initialize ADC adapter
        self.adc_adapter: Optional[ADCAdapter] = None
        self._initialize_adc()
        
        # Sampling configuration
        self.sample_hz = 100
        self.interval = 1.0 / self.sample_hz
        self._last_config_version = -1
        
        # Batch writing configuration
        self.batch_size = 100
        self.batch_interval_ms = 1000
        self._batch_buffer: List[tuple] = []
        self._last_flush_time = time.time()
        
        # File management
        self._current_date: Optional[str] = None
        self._file: Optional[Any] = None
        
        # Display manager integration
        self.display_manager: Optional[DisplayManager] = None
        self._initialize_display_manager()
        
        # Threading
        self._sampling_thread: Optional[threading.Thread] = None
        self._config_thread: Optional[threading.Thread] = None
        self._running = False
        
        logger.info("DataloggerProcess initialized")
    
    def restore_data_from_disk(self, seconds: float = 30.0, max_lines: int = 10000) -> None:
        """
        Restore recent data from disk to shared memory buffer on startup.
        
        This method loads the last 30 seconds of data from CSV files into the
        shared memory buffer to maintain continuity across process restarts.
        
        Args:
            seconds: Number of seconds of recent data to restore
            max_lines: Maximum number of lines to read from files
        """
        logger.info(f"Restoring last {seconds} seconds of data from disk")
        
        try:
            # Determine which files to check (today and yesterday)
            now = time.time()
            cutoff_time = now - seconds
            
            today_path = self._log_filename_for_date(time.localtime(now))
            yesterday_path = self._log_filename_for_date(time.localtime(now - 86400))
            
            # List of files to check (most recent first)
            file_paths = []
            if os.path.exists(today_path):
                file_paths.append(today_path)
            if os.path.exists(yesterday_path):
                file_paths.append(yesterday_path)
            if os.path.exists(yesterday_path + '.gz'):
                file_paths.append(yesterday_path + '.gz')
            
            if not file_paths:
                logger.info("No existing log files found for data restoration")
                return
            
            # Collect samples from files
            samples = []
            lines_read = 0
            
            for file_path in file_paths:
                if lines_read >= max_lines:
                    break
                
                try:
                    logger.debug(f"Reading samples from {file_path}")
                    
                    if file_path.endswith('.gz'):
                        import gzip
                        file_opener = gzip.open
                        mode = 'rt'
                    else:
                        file_opener = open
                        mode = 'r'
                    
                    with file_opener(file_path, mode) as f:
                        reader = csv.reader(f)
                        
                        # Skip header
                        try:
                            next(reader)
                        except StopIteration:
                            continue
                        
                        # Read samples
                        file_samples = []
                        for row in reader:
                            if lines_read >= max_lines:
                                break
                            
                            if len(row) >= 2:
                                try:
                                    timestamp = float(row[0])
                                    value = float(row[1])
                                    
                                    # Only include samples within the time window
                                    if timestamp >= cutoff_time:
                                        file_samples.append((timestamp, value))
                                    
                                    lines_read += 1
                                    
                                except (ValueError, IndexError):
                                    continue
                        
                        # Add samples from this file (they should be in chronological order)
                        samples.extend(file_samples)
                        logger.debug(f"Read {len(file_samples)} samples from {file_path}")
                
                except Exception as e:
                    logger.warning(f"Failed to read samples from {file_path}: {e}")
                    continue
            
            # Sort samples by timestamp to ensure chronological order
            samples.sort(key=lambda x: x[0])
            
            # Filter to only include samples within the time window
            recent_samples = [(ts, val) for ts, val in samples if ts >= cutoff_time]
            
            # Write samples to shared memory buffer
            restored_count = 0
            for timestamp, value in recent_samples:
                try:
                    self.shared_sample_buffer.write_sample(timestamp, value)
                    restored_count += 1
                except Exception as e:
                    logger.warning(f"Failed to write restored sample to shared memory: {e}")
            
            logger.info(f"Restored {restored_count} samples to shared memory buffer")
            
            # Log buffer status
            buffer_info = self.shared_sample_buffer.get_buffer_info()
            logger.info(f"Shared memory buffer status: {buffer_info['count']}/{buffer_info['size']} samples")
            
        except Exception as e:
            logger.error(f"Error during data restoration: {e}")
            # Don't raise - data restoration failure shouldn't prevent startup
    
    def _initialize_adc(self) -> None:
        """Initialize the ADC adapter with fallback handling."""
        try:
            # Set default configuration
            default_config = {
                'address': 0x48,
                'channel': 0,
                'sample_rate': getattr(self, 'sample_hz', 100)  # Use default if not set yet
            }
            default_config.update(self.adc_config)
            
            self.adc_adapter = create_adc_adapter(self.adc_type, default_config)
            logger.info(f"ADC adapter initialized: {type(self.adc_adapter).__name__}")
            
        except Exception as e:
            logger.error(f"Failed to initialize ADC adapter: {e}")
            # This should not happen due to fallback in create_adc_adapter,
            # but provide additional safety
            from .adapters import MockADCAdapter
            self.adc_adapter = MockADCAdapter()
            self.adc_adapter.initialize(self.adc_config)
            logger.warning("Using MockADC as final fallback")
    
    def _initialize_display_manager(self) -> None:
        """Initialize the display manager if configured."""
        if not self.display_config.get('enabled', False):
            logger.info("Display manager disabled in configuration")
            return
        
        try:
            # The display manager expects a logger object with certain methods
            # We provide self as the logger object since we implement the required interface
            
            self.display_manager = DisplayManager(
                logger_obj=self,  # Pass self as the logger object
                url=self.display_config.get('url'),
                auto_ip=self.display_config.get('auto_ip', True),
                port=self.display_config.get('port', 8000),
                fps=self.display_config.get('display_fps', 5.0),
                data_dir=self.data_dir,
                lcd_config=self.display_config.get('lcd_config')
            )
            logger.info("Display manager initialized and integrated with datalogger process")
            
        except Exception as e:
            logger.error(f"Failed to initialize display manager: {e}")
            self.display_manager = None
    
    def get_current_analysis(self) -> Dict[str, Any]:
        """
        Get current analysis metrics for display manager compatibility.
        
        In the multiprocessing architecture, analysis will be handled
        by the Event Logger Process. For now, this returns basic metrics
        that can be computed from recent samples.
        """
        try:
            # Get recent samples for basic analysis
            recent_samples = self.shared_sample_buffer.read_recent(1.0)  # Last 1 second
            
            if not recent_samples:
                return {
                    'rms': 0.0,
                    'frequency': 60.0,
                    'sags_swells': []
                }
            
            # Calculate basic RMS from recent samples
            values = [sample[1] for sample in recent_samples if not math.isnan(sample[1])]
            if values:
                # Simple RMS calculation
                rms = math.sqrt(sum(v * v for v in values) / len(values))
            else:
                rms = 0.0
            
            return {
                'rms': rms,
                'frequency': 60.0,  # Default frequency
                'sags_swells': []
            }
            
        except Exception as e:
            logger.debug(f"Error calculating analysis metrics: {e}")
            return {
                'rms': 0.0,
                'frequency': 60.0,
                'sags_swells': []
            }
    
    def get_recent(self, seconds: float = 5.0) -> List[tuple]:
        """
        Get recent samples from shared memory buffer.
        
        Args:
            seconds: Number of seconds of recent data to retrieve
            
        Returns:
            List of (timestamp, value) tuples
        """
        return self.shared_sample_buffer.read_recent(seconds)
    
    def get_latest_voltage(self) -> float:
        """
        Get the most recent voltage reading for display manager.
        
        Returns:
            Latest voltage value or 0.0 if no data available
        """
        try:
            latest_sample = self.shared_sample_buffer.get_latest_sample()
            if latest_sample and not math.isnan(latest_sample[1]):
                return latest_sample[1]
            return 0.0
        except Exception:
            return 0.0
    
    def _log_filename_for_date(self, date_struct) -> str:
        """Generate log filename for a given date."""
        date_str = time.strftime("%Y-%m-%d", date_struct)
        return os.path.join(self.data_dir, f"{self.filename_prefix}_{date_str}.csv")
    
    def _open_log_file_for_today(self) -> None:
        """Open or create today's log file with proper CSV header."""
        now = time.localtime()
        date_str = time.strftime("%Y-%m-%d", now)
        
        if self._current_date != date_str:
            # Close previous file and flush remaining batch
            if self._file:
                try:
                    self._flush_batch()
                    self._file.close()
                except Exception as e:
                    logger.error(f"Error closing previous log file: {e}")
            
            # Open new file for today
            self._current_date = date_str
            filename = self._log_filename_for_date(now)
            is_new = not os.path.exists(filename)
            
            try:
                self._file = open(filename, "a", newline='')
                if is_new:
                    writer = csv.writer(self._file)
                    writer.writerow(["timestamp", "value"])
                    self._file.flush()
                logger.info(f"Opened log file: {filename}")
            except Exception as e:
                logger.error(f"Failed to open log file {filename}: {e}")
                self._file = None
            
            # Clean up old log files
            self._cleanup_old_logs()
    
    def _cleanup_old_logs(self) -> None:
        """Remove log files older than retention_days."""
        try:
            now = time.time()
            retention_sec = self.retention_days * 86400
            
            for filename in os.listdir(self.data_dir):
                if filename.startswith(self.filename_prefix) and filename.endswith(".csv"):
                    filepath = os.path.join(self.data_dir, filename)
                    try:
                        if os.stat(filepath).st_mtime < now - retention_sec:
                            os.remove(filepath)
                            logger.info(f"Deleted old log file: {filename}")
                    except Exception as e:
                        logger.warning(f"Failed to delete old log file {filename}: {e}")
                        
        except Exception as e:
            logger.error(f"Error during log cleanup: {e}")
    
    def _flush_batch(self) -> None:
        """Flush the current batch buffer to disk."""
        if not self._batch_buffer or not self._file:
            return
        
        try:
            writer = csv.writer(self._file)
            # Write all samples in the batch with full precision
            writer.writerows([
                (f"{timestamp:.6f}", f"{value:.6f}")
                for timestamp, value in self._batch_buffer
            ])
            
            # Flush to disk
            self._file.flush()
            try:
                os.fsync(self._file.fileno())
            except Exception:
                pass  # fsync may not be available on all systems
            
            # Clear batch and update flush time
            sample_count = len(self._batch_buffer)
            self._batch_buffer.clear()
            self._last_flush_time = time.time()
            
            logger.debug(f"Flushed {sample_count} samples to disk")
            
        except Exception as e:
            logger.error(f"Failed to flush batch to disk: {e}")
    
    def _update_configuration(self) -> None:
        """Check for configuration updates and apply them."""
        try:
            config, version = self.shared_config_buffer.get_config()
            
            if version > self._last_config_version:
                logger.info(f"Applying configuration update (version {version})")
                
                # Update sample rate
                new_sample_hz = config.get('sample_hz', self.sample_hz)
                if new_sample_hz != self.sample_hz:
                    self.sample_hz = max(1, min(860, int(new_sample_hz)))
                    self.interval = 1.0 / self.sample_hz
                    
                    # Update ADC sample rate if supported
                    if hasattr(self.adc_adapter, 'set_sample_rate'):
                        try:
                            self.adc_adapter.set_sample_rate(self.sample_hz)
                        except Exception as e:
                            logger.warning(f"Failed to update ADC sample rate: {e}")
                    
                    logger.info(f"Sample rate updated to {self.sample_hz} Hz")
                
                # Update batch configuration
                self.batch_size = config.get('batch_size', self.batch_size)
                self.batch_interval_ms = config.get('batch_interval_ms', self.batch_interval_ms)
                
                # Update display FPS if display manager is active
                if self.display_manager:
                    display_fps = config.get('display_fps', 5.0)
                    if hasattr(self.display_manager, 'fps') and display_fps != self.display_manager.fps:
                        self.display_manager.fps = display_fps
                        self.display_manager.interval = 1.0 / display_fps
                        logger.info(f"Display FPS updated to {display_fps}")
                
                self._last_config_version = version
                
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
    
    def _config_monitor_loop(self) -> None:
        """Monitor configuration changes in a separate thread."""
        logger.info("Configuration monitor started")
        
        while self._running and not self.stop_event.is_set():
            try:
                self._update_configuration()
                time.sleep(1.0)  # Check for config updates every second
            except Exception as e:
                logger.error(f"Error in configuration monitor: {e}")
                time.sleep(5.0)  # Back off on errors
        
        logger.info("Configuration monitor stopped")
    
    def _sampling_loop(self) -> None:
        """Main sampling loop running at the configured sample rate."""
        logger.info(f"Sampling loop started at {self.sample_hz} Hz")
        
        next_sample = time.perf_counter()
        
        while self._running and not self.stop_event.is_set():
            try:
                # Ensure we have today's log file open
                self._open_log_file_for_today()
                
                # Take sample
                timestamp = time.time()
                try:
                    value = float(self.adc_adapter.read_sample())
                except Exception as e:
                    logger.debug(f"ADC read failed: {e}")
                    value = float('nan')
                
                # Write to shared memory buffer
                try:
                    self.shared_sample_buffer.write_sample(timestamp, value)
                except Exception as e:
                    logger.error(f"Failed to write sample to shared memory: {e}")
                
                # Add to batch buffer for CSV writing
                self._batch_buffer.append((timestamp, value))
                
                # Check if we need to flush the batch
                current_time = time.time()
                batch_age_ms = (current_time - self._last_flush_time) * 1000
                
                if (len(self._batch_buffer) >= self.batch_size or 
                    batch_age_ms >= self.batch_interval_ms):
                    self._flush_batch()
                
                # Sleep until next scheduled sample
                next_sample += self.interval
                sleep_duration = next_sample - time.perf_counter()
                
                if sleep_duration > 0:
                    time.sleep(sleep_duration)
                else:
                    # We're behind schedule, skip sleep to catch up
                    next_sample = time.perf_counter()
                    
            except Exception as e:
                logger.error(f"Error in sampling loop: {e}")
                time.sleep(0.1)  # Brief pause before retrying
        
        # Flush any remaining samples on shutdown
        try:
            self._flush_batch()
        except Exception as e:
            logger.error(f"Error flushing final batch: {e}")
        
        logger.info("Sampling loop stopped")
    
    def start(self) -> None:
        """Start the datalogger process."""
        if self._running:
            logger.warning("DataloggerProcess already running")
            return
        
        logger.info("Starting DataloggerProcess")
        self._running = True
        
        # Restore recent data from disk to maintain continuity
        try:
            self.restore_data_from_disk(seconds=30.0)
        except Exception as e:
            logger.error(f"Data restoration failed: {e}")
            # Continue startup even if restoration fails
        
        # Start configuration monitor thread
        self._config_thread = threading.Thread(
            target=self._config_monitor_loop,
            name="DataloggerConfig",
            daemon=True
        )
        self._config_thread.start()
        
        # Start sampling thread
        self._sampling_thread = threading.Thread(
            target=self._sampling_loop,
            name="DataloggerSampling",
            daemon=True
        )
        self._sampling_thread.start()
        
        # Start display manager if configured
        if self.display_manager:
            try:
                self.display_manager.start()
                logger.info("Display manager started")
            except Exception as e:
                logger.error(f"Failed to start display manager: {e}")
        
        logger.info("DataloggerProcess started successfully")
    
    def stop(self) -> None:
        """Stop the datalogger process and clean up resources."""
        if not self._running:
            return
        
        logger.info("Stopping DataloggerProcess")
        self._running = False
        
        # Signal stop to all components
        self.stop_event.set()
        
        # Stop display manager
        if self.display_manager:
            try:
                self.display_manager.stop()
                logger.info("Display manager stopped")
            except Exception as e:
                logger.error(f"Error stopping display manager: {e}")
        
        # Wait for threads to finish
        if self._sampling_thread and self._sampling_thread.is_alive():
            self._sampling_thread.join(timeout=5.0)
        
        if self._config_thread and self._config_thread.is_alive():
            self._config_thread.join(timeout=2.0)
        
        # Close log file
        if self._file:
            try:
                self._flush_batch()
                self._file.close()
                self._file = None
            except Exception as e:
                logger.error(f"Error closing log file: {e}")
        
        # Clean up ADC adapter
        if self.adc_adapter:
            try:
                self.adc_adapter.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up ADC adapter: {e}")
        
        logger.info("DataloggerProcess stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status information for monitoring."""
        status = {
            'running': self._running,
            'sample_hz': self.sample_hz,
            'batch_size': self.batch_size,
            'batch_buffer_size': len(self._batch_buffer),
            'adc_type': type(self.adc_adapter).__name__ if self.adc_adapter else None,
            'current_date': self._current_date,
            'file_open': self._file is not None,
            'display_manager_active': self.display_manager is not None,
            'config_version': self._last_config_version
        }
        
        # Add shared memory buffer status
        try:
            buffer_info = self.shared_sample_buffer.get_buffer_info()
            status['shared_buffer'] = {
                'count': buffer_info['count'],
                'size': buffer_info['size'],
                'utilization': buffer_info['utilization']
            }
        except Exception:
            status['shared_buffer'] = {'error': 'Unable to get buffer info'}
        
        # Add display manager status if active
        if self.display_manager:
            status['display_manager'] = {
                'fps': getattr(self.display_manager, 'fps', 'unknown'),
                'url': getattr(self.display_manager, 'url', 'unknown')
            }
        
        return status


def run_datalogger_process(
    shared_sample_buffer: SharedSampleBuffer,
    shared_config_buffer: SharedConfigBuffer,
    **kwargs
) -> None:
    """
    Entry point function for running the datalogger in a separate process.
    
    This function is designed to be used as the target for multiprocessing.Process.
    
    Args:
        shared_sample_buffer: Shared memory buffer for sample data
        shared_config_buffer: Shared memory buffer for configuration
        **kwargs: Additional configuration parameters for DataloggerProcess
    """
    # Set up logging for the process
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Starting datalogger process")
    
    # Create stop event for graceful shutdown
    stop_event = Event()
    
    try:
        # Create and start datalogger process
        datalogger = DataloggerProcess(
            shared_sample_buffer=shared_sample_buffer,
            shared_config_buffer=shared_config_buffer,
            stop_event=stop_event,
            **kwargs
        )
        
        datalogger.start()
        
        # Keep the process running until stop is signaled
        while not stop_event.is_set():
            time.sleep(1.0)
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Error in datalogger process: {e}")
        raise
    finally:
        # Clean up
        if 'datalogger' in locals():
            datalogger.stop()
        logger.info("Datalogger process finished")