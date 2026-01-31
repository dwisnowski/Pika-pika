"""
Event Logger Process for multiprocessing datalogger architecture.

This process is responsible for:
- Reading samples from shared memory buffer
- Performing real-time stream analysis (RMS, frequency, sags/swells)
- Writing analysis metrics to SharedAnalysisBuffer
- Managing highlights file for anomaly detection and event logging
- Monitoring configuration changes and applying updates dynamically
"""

import os
import time
import json
import logging
import threading
from multiprocessing import Process
from typing import Dict, List, Optional, Any, Tuple
from collections import deque

from .shared_memory import SharedSampleBuffer, SharedAnalysisBuffer, SharedConfigBuffer
from .analysis import StreamAnalyzer

logger = logging.getLogger(__name__)


class EventLoggerProcess(Process):
    """
    Dedicated process for event detection and analysis.
    
    This process runs independently from the datalogger and FastAPI processes,
    continuously analyzing samples from shared memory and detecting anomalies.
    """
    
    def __init__(self, 
                 sample_buffer_name: str,
                 analysis_buffer_name: str,
                 config_buffer_name: str,
                 data_dir: str = 'data',
                 analysis_interval: float = 0.1,  # 10Hz analysis updates
                 highlights_scan_interval: int = 60):  # 1 minute highlights scan
        """
        Initialize Event Logger Process.
        
        Args:
            sample_buffer_name: Name of shared sample buffer
            analysis_buffer_name: Name of shared analysis buffer
            config_buffer_name: Name of shared config buffer
            data_dir: Directory for data files (highlights.json)
            analysis_interval: Interval between analysis updates (seconds)
            highlights_scan_interval: Interval between highlights scans (seconds)
        """
        super().__init__(name="EventLoggerProcess")
        
        self.sample_buffer_name = sample_buffer_name
        self.analysis_buffer_name = analysis_buffer_name
        self.config_buffer_name = config_buffer_name
        self.data_dir = data_dir
        self.analysis_interval = analysis_interval
        self.highlights_scan_interval = highlights_scan_interval
        
        # Process control
        self._stop_event = threading.Event()
        self._analysis_thread = None
        self._highlights_thread = None
        
        # Shared memory buffers (initialized in run())
        self.sample_buffer = None
        self.analysis_buffer = None
        self.config_buffer = None
        
        # Analysis components
        self.stream_analyzer = None
        self.last_config_version = 0
        
        # Highlights management
        self._highlights_buffer = deque(maxlen=100000)  # Buffer for streaming analysis
        self._highlights_lock = threading.Lock()
        self._current_highlights = []
        
        # Performance tracking
        self._last_analysis_time = 0.0
        self._analysis_count = 0
        self._last_sample_timestamp = 0.0
        
        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)
    
    def run(self):
        """Main process entry point."""
        try:
            logger.info("EventLoggerProcess starting...")
            
            # Initialize shared memory connections
            self._initialize_shared_memory()
            
            # Initialize stream analyzer with current configuration
            self._initialize_analyzer()
            
            # Load existing highlights for continuity
            self._current_highlights = self.load_existing_highlights()
            
            # Start analysis and highlights threads
            self._start_threads()
            
            # Main process loop - monitor for shutdown
            while not self._stop_event.is_set():
                time.sleep(0.1)
                
        except Exception as e:
            logger.error(f"EventLoggerProcess error: {e}", exc_info=True)
        finally:
            self._cleanup()
            logger.info("EventLoggerProcess stopped")
    
    def stop(self):
        """Stop the event logger process gracefully."""
        logger.info("EventLoggerProcess stopping...")
        self._stop_event.set()
    
    def _initialize_shared_memory(self):
        """Initialize connections to shared memory buffers."""
        try:
            # Connect to existing shared memory buffers
            self.sample_buffer = SharedSampleBuffer(
                create=False, 
                name=self.sample_buffer_name
            )
            
            self.analysis_buffer = SharedAnalysisBuffer(
                create=False,
                name=self.analysis_buffer_name
            )
            
            self.config_buffer = SharedConfigBuffer(
                create=False,
                name=self.config_buffer_name
            )
            
            logger.info("Connected to shared memory buffers")
            
        except Exception as e:
            logger.error(f"Failed to initialize shared memory: {e}")
            raise
    
    def _initialize_analyzer(self):
        """Initialize stream analyzer with current configuration."""
        try:
            # Get current configuration
            config, version = self.config_buffer.get_config()
            analysis_config = config.get('analysis_config', {})
            
            # Create stream analyzer
            self.stream_analyzer = StreamAnalyzer(analysis_config)
            self.last_config_version = version
            
            logger.info(f"Initialized StreamAnalyzer with config version {version}")
            
        except Exception as e:
            logger.error(f"Failed to initialize analyzer: {e}")
            # Use default configuration
            self.stream_analyzer = StreamAnalyzer({})
            self.last_config_version = 0
    
    def _start_threads(self):
        """Start analysis and highlights processing threads."""
        # Start analysis thread
        self._analysis_thread = threading.Thread(
            target=self._analysis_loop,
            name="AnalysisThread",
            daemon=True
        )
        self._analysis_thread.start()
        
        # Start highlights thread
        self._highlights_thread = threading.Thread(
            target=self._highlights_loop,
            name="HighlightsThread", 
            daemon=True
        )
        self._highlights_thread.start()
        
        logger.info("Started analysis and highlights threads")
    
    def _analysis_loop(self):
        """Main analysis loop - processes samples and updates metrics."""
        logger.info("Analysis loop started")
        
        last_processed_timestamp = 0.0
        
        while not self._stop_event.is_set():
            try:
                # Check for configuration changes
                self._check_config_updates()
                
                # Get recent samples from shared memory
                samples = self.sample_buffer.read_recent(seconds=1.0)  # Last 1 second
                
                if not samples:
                    time.sleep(self.analysis_interval)
                    continue
                
                # Filter out already processed samples
                new_samples = [
                    (ts, val) for ts, val in samples 
                    if ts > last_processed_timestamp
                ]
                
                if not new_samples:
                    time.sleep(self.analysis_interval)
                    continue
                
                # Process new samples through stream analyzer
                current_metrics = None
                for timestamp, value in new_samples:
                    metrics = self.stream_analyzer.process_sample(timestamp, value)
                    current_metrics = metrics
                    
                    # Add to highlights buffer for anomaly detection
                    with self._highlights_lock:
                        self._highlights_buffer.append((timestamp, value))
                    
                    last_processed_timestamp = timestamp
                
                # Update shared analysis buffer with latest metrics
                if current_metrics:
                    self._update_analysis_buffer(current_metrics)
                
                # Update performance tracking
                self._analysis_count += len(new_samples)
                self._last_analysis_time = time.time()
                self._last_sample_timestamp = last_processed_timestamp
                
                # Sleep until next analysis interval
                time.sleep(self.analysis_interval)
                
            except Exception as e:
                logger.error(f"Analysis loop error: {e}", exc_info=True)
                time.sleep(self.analysis_interval)
    
    def _highlights_loop(self):
        """Highlights detection loop - scans for anomalies and updates highlights file."""
        logger.info("Highlights loop started")
        
        while not self._stop_event.is_set():
            try:
                # Get samples for highlights analysis
                samples_to_analyze = []
                with self._highlights_lock:
                    # Get samples from last 10 minutes for analysis
                    cutoff_time = time.time() - 600  # 10 minutes
                    
                    # Remove old samples
                    while (self._highlights_buffer and 
                           self._highlights_buffer[0][0] < cutoff_time):
                        self._highlights_buffer.popleft()
                    
                    # Copy samples for analysis
                    samples_to_analyze = list(self._highlights_buffer)
                
                # Detect highlights/anomalies
                if samples_to_analyze:
                    highlights = self._detect_highlights(samples_to_analyze)
                    self._current_highlights = highlights
                    
                    # Write highlights to file
                    self._write_highlights_file(highlights)
                
                # Sleep until next scan
                for _ in range(self.highlights_scan_interval):
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Highlights loop error: {e}", exc_info=True)
                time.sleep(self.highlights_scan_interval)
    
    def _check_config_updates(self):
        """
        Check for configuration updates and apply them dynamically.
        
        This method monitors the SharedConfigBuffer for version changes
        and applies configuration updates without requiring process restart.
        Supports updating analysis parameters, thresholds, and detection settings.
        """
        try:
            current_version = self.config_buffer.get_version()
            
            if current_version > self.last_config_version:
                # Configuration has changed, update analyzer
                config, version = self.config_buffer.get_config()
                analysis_config = config.get('analysis_config', {})
                
                # Log the configuration change
                logger.info(f"Configuration updated from version {self.last_config_version} to {version}")
                logger.debug(f"New analysis config: {analysis_config}")
                
                # Update stream analyzer configuration
                old_config = getattr(self.stream_analyzer, 'config', {})
                self.stream_analyzer.update_config(analysis_config)
                
                # Log specific changes for debugging
                self._log_config_changes(old_config, analysis_config)
                
                # Update analysis interval if specified
                new_interval = analysis_config.get('analysis_interval', self.analysis_interval)
                if new_interval != self.analysis_interval:
                    self.analysis_interval = new_interval
                    logger.info(f"Updated analysis interval to {new_interval}s")
                
                # Update highlights scan interval if specified
                new_scan_interval = analysis_config.get('highlights_scan_interval', self.highlights_scan_interval)
                if new_scan_interval != self.highlights_scan_interval:
                    self.highlights_scan_interval = new_scan_interval
                    logger.info(f"Updated highlights scan interval to {new_scan_interval}s")
                
                self.last_config_version = version
                
        except Exception as e:
            logger.error(f"Error checking config updates: {e}")
    
    def _log_config_changes(self, old_config: Dict[str, Any], new_config: Dict[str, Any]):
        """Log specific configuration changes for debugging."""
        try:
            # Check for key parameter changes
            key_params = [
                'enable_rms', 'enable_freq', 'enable_sags_swells',
                'nominal_voltage', 'sag_threshold', 'swell_threshold',
                'dc_offset', 'rms_window_size', 'frequency_detection'
            ]
            
            changes = []
            for param in key_params:
                old_val = old_config.get(param)
                new_val = new_config.get(param)
                if old_val != new_val:
                    changes.append(f"{param}: {old_val} -> {new_val}")
            
            if changes:
                logger.info(f"Configuration changes: {', '.join(changes)}")
            else:
                logger.debug("Configuration updated but no key parameter changes detected")
                
        except Exception as e:
            logger.debug(f"Error logging config changes: {e}")
    
    def get_current_config(self) -> Dict[str, Any]:
        """
        Get current configuration for monitoring/debugging.
        
        Returns:
            Dictionary containing current configuration and version
        """
        try:
            config, version = self.config_buffer.get_config()
            return {
                'config': config,
                'version': version,
                'last_known_version': self.last_config_version,
                'analysis_interval': self.analysis_interval,
                'highlights_scan_interval': self.highlights_scan_interval,
                'analyzer_config': getattr(self.stream_analyzer, 'config', {})
            }
        except Exception as e:
            logger.error(f"Error getting current config: {e}")
            return {
                'error': str(e),
                'last_known_version': self.last_config_version
            }
    
    def _update_analysis_buffer(self, metrics: Dict[str, Any]):
        """Update shared analysis buffer with current metrics."""
        try:
            # Extract metrics from analyzer output
            rms = metrics.get('rms', 0.0)
            frequency = metrics.get('freq', 60.0)
            
            # Handle sags/swells events
            events = []
            status = metrics.get('status', 'normal')
            if status != 'normal':
                events.append({
                    'type': status,
                    'timestamp': time.time(),
                    'rms': rms
                })
            
            # Update shared memory buffer
            self.analysis_buffer.update_metrics(rms, frequency, events)
            
        except Exception as e:
            logger.error(f"Error updating analysis buffer: {e}")
    
    def _detect_highlights(self, samples: List[tuple]) -> List[Dict]:
        """
        Detect anomalies/highlights in sample data.
        
        This implements the same logic as the original HighlightsManager
        but adapted for the multiprocessing architecture. Maintains exact
        compatibility with existing highlights.json format.
        """
        if len(samples) < 50:  # Minimum points for analysis
            return []
        
        try:
            # Calculate global statistics (same as original HighlightsManager)
            values = [val for (_, val) in samples]
            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            std = variance ** 0.5
            threshold = max(0.06, 3.0 * std)
            
            # Detect anomalous regions
            highlights = []
            current_event = None
            
            for timestamp, value in samples:
                if abs(value - mean) > threshold:
                    if current_event is None:
                        # Start new event
                        current_event = {
                            "start": timestamp,
                            "end": timestamp,
                            "peak_ts": timestamp,
                            "peak_val": value,
                            "count": 1
                        }
                    else:
                        # Continue current event
                        current_event["end"] = timestamp
                        current_event["count"] += 1
                        if abs(value - mean) > abs(current_event["peak_val"] - mean):
                            current_event["peak_val"] = value
                            current_event["peak_ts"] = timestamp
                else:
                    if current_event is not None:
                        # End current event
                        highlights.append(current_event)
                        current_event = None
            
            # Don't forget the last event if it was ongoing
            if current_event is not None:
                highlights.append(current_event)
            
            # Convert to API format (exact same format as original)
            formatted_highlights = []
            for event in highlights:
                duration = event['end'] - event['start']
                score = event['count'] * abs(event['peak_val'] - mean)
                
                # Determine anomaly type based on peak value relative to mean
                anomaly_type = 'spike' if event['peak_val'] > mean else 'drop'
                
                formatted_highlights.append({
                    'start_ts': event['start'],
                    'end_ts': event['end'],
                    'peak_ts': event['peak_ts'],
                    'peak_value': event['peak_val'],
                    'duration': duration,
                    'score': score,
                    'type': anomaly_type  # Add type field for compatibility
                })
            
            return formatted_highlights
            
        except Exception as e:
            logger.error(f"Error detecting highlights: {e}")
            return []
    
    def _write_highlights_file(self, highlights: List[Dict]):
        """
        Write highlights to JSON file.
        
        Maintains exact compatibility with existing highlights.json format
        used by the API endpoints and WebSocket handlers.
        """
        try:
            highlights_file = os.path.join(self.data_dir, 'highlights.json')
            
            # Ensure highlights are sorted by start timestamp for consistency
            sorted_highlights = sorted(highlights, key=lambda x: x.get('start_ts', 0))
            
            # Write with proper formatting for readability
            with open(highlights_file, 'w') as f:
                json.dump(sorted_highlights, f, indent=2)
                
            logger.debug(f"Wrote {len(sorted_highlights)} highlights to {highlights_file}")
                
        except Exception as e:
            logger.error(f"Error writing highlights file: {e}")
    
    def load_existing_highlights(self) -> List[Dict]:
        """
        Load existing highlights from file on startup.
        
        This ensures continuity when the process restarts and preserves
        any existing anomaly data.
        """
        try:
            highlights_file = os.path.join(self.data_dir, 'highlights.json')
            if os.path.exists(highlights_file):
                with open(highlights_file, 'r') as f:
                    highlights = json.load(f)
                    logger.info(f"Loaded {len(highlights)} existing highlights from file")
                    return highlights
        except Exception as e:
            logger.error(f"Error loading existing highlights: {e}")
        
        return []
    
    def update_analysis_config(self, new_config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Update analysis configuration programmatically with validation.
        
        This method allows external processes to update the analysis configuration
        through the shared config buffer. The changes will be picked up by the
        configuration monitoring loop.
        
        Args:
            new_config: Dictionary containing new analysis configuration parameters
            
        Returns:
            Tuple of (success, list_of_errors)
        """
        try:
            # Validate configuration first
            is_valid, errors = self.validate_config_parameters(new_config)
            if not is_valid:
                logger.warning(f"Configuration validation failed: {errors}")
                return False, errors
            
            # Get current configuration
            current_config, _ = self.config_buffer.get_config()
            
            # Update analysis_config section
            updated_analysis_config = current_config.get('analysis_config', {})
            updated_analysis_config.update(new_config)
            current_config['analysis_config'] = updated_analysis_config
            
            # Write back to shared buffer
            new_version = self.config_buffer.update_config(current_config)
            
            logger.info(f"Updated analysis configuration, new version: {new_version}")
            logger.debug(f"Updated parameters: {new_config}")
            
            return True, []
            
        except Exception as e:
            error_msg = f"Error updating analysis config: {e}"
            logger.error(error_msg)
            return False, [error_msg]
    
    def get_supported_config_parameters(self) -> Dict[str, Any]:
        """
        Get list of supported configuration parameters with descriptions.
        
        Returns:
            Dictionary describing supported configuration parameters
        """
        return {
            'analysis_parameters': {
                'enable_rms': {
                    'type': 'boolean',
                    'default': True,
                    'description': 'Enable RMS voltage calculation'
                },
                'enable_freq': {
                    'type': 'boolean', 
                    'default': True,
                    'description': 'Enable frequency detection via zero-crossing'
                },
                'enable_sags_swells': {
                    'type': 'boolean',
                    'default': True,
                    'description': 'Enable sag/swell detection'
                },
                'nominal_voltage': {
                    'type': 'float',
                    'default': 120.0,
                    'description': 'Nominal voltage for sag/swell detection'
                },
                'sag_threshold': {
                    'type': 'float',
                    'default': 108.0,  # 90% of 120V
                    'description': 'Voltage threshold for sag detection'
                },
                'swell_threshold': {
                    'type': 'float',
                    'default': 132.0,  # 110% of 120V
                    'description': 'Voltage threshold for swell detection'
                },
                'dc_offset': {
                    'type': 'float',
                    'default': 1.65,
                    'description': 'DC offset for zero-crossing detection'
                },
                'rms_window_size': {
                    'type': 'integer',
                    'default': 100,
                    'description': 'Number of samples for RMS calculation window'
                }
            },
            'process_parameters': {
                'analysis_interval': {
                    'type': 'float',
                    'default': 0.1,
                    'description': 'Interval between analysis updates (seconds)'
                },
                'highlights_scan_interval': {
                    'type': 'integer',
                    'default': 60,
                    'description': 'Interval between highlights scans (seconds)'
                }
            }
        }
    
    def get_current_highlights(self) -> List[Dict]:
        """Get current highlights (for debugging/monitoring)."""
        return list(self._current_highlights)
    
    def validate_config_parameters(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate configuration parameters before applying them.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        try:
            # Validate boolean parameters
            bool_params = ['enable_rms', 'enable_freq', 'enable_sags_swells']
            for param in bool_params:
                if param in config and not isinstance(config[param], bool):
                    errors.append(f"{param} must be a boolean")
            
            # Validate numeric parameters
            numeric_params = {
                'nominal_voltage': (50.0, 500.0),  # Reasonable voltage range
                'sag_threshold': (10.0, 400.0),
                'swell_threshold': (50.0, 500.0),
                'dc_offset': (0.0, 5.0),  # ADC range
                'analysis_interval': (0.01, 10.0),  # 10ms to 10s
                'highlights_scan_interval': (10, 3600)  # 10s to 1 hour
            }
            
            for param, (min_val, max_val) in numeric_params.items():
                if param in config:
                    val = config[param]
                    if not isinstance(val, (int, float)):
                        errors.append(f"{param} must be a number")
                    elif not (min_val <= val <= max_val):
                        errors.append(f"{param} must be between {min_val} and {max_val}")
            
            # Validate integer parameters
            int_params = ['rms_window_size', 'highlights_scan_interval']
            for param in int_params:
                if param in config:
                    val = config[param]
                    if not isinstance(val, int) or val <= 0:
                        errors.append(f"{param} must be a positive integer")
            
            # Validate logical relationships
            if 'sag_threshold' in config and 'swell_threshold' in config:
                if config['sag_threshold'] >= config['swell_threshold']:
                    errors.append("sag_threshold must be less than swell_threshold")
            
            # Check for unknown parameters
            supported_params = {
                'enable_rms', 'enable_freq', 'enable_sags_swells',
                'nominal_voltage', 'sag_threshold', 'swell_threshold',
                'dc_offset', 'rms_window_size', 'analysis_interval',
                'highlights_scan_interval'
            }
            
            unknown_params = set(config.keys()) - supported_params
            if unknown_params:
                errors.append(f"Unknown parameters: {', '.join(unknown_params)}")
            
        except Exception as e:
            errors.append(f"Validation error: {e}")
        
        return len(errors) == 0, errors
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for monitoring."""
        return {
            'analysis_count': self._analysis_count,
            'last_analysis_time': self._last_analysis_time,
            'last_sample_timestamp': self._last_sample_timestamp,
            'highlights_buffer_size': len(self._highlights_buffer),
            'current_highlights_count': len(self._current_highlights),
            'config_version': self.last_config_version
        }
    
    def _cleanup(self):
        """Clean up resources on shutdown."""
        try:
            # Stop threads
            self._stop_event.set()
            
            if self._analysis_thread and self._analysis_thread.is_alive():
                self._analysis_thread.join(timeout=2.0)
            
            if self._highlights_thread and self._highlights_thread.is_alive():
                self._highlights_thread.join(timeout=2.0)
            
            # Close shared memory connections (don't unlink - other processes need them)
            if self.sample_buffer:
                self.sample_buffer.shm.close()
            
            if self.analysis_buffer:
                self.analysis_buffer.shm.close()
                
            if self.config_buffer:
                self.config_buffer.shm.close()
            
            logger.info("EventLoggerProcess cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")