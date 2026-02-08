"""
Threading-based worker functions for single-processor execution.

This module provides thread-compatible versions of the datalogger, event logger,
and web server components that can run in the same process using shared objects
instead of shared memory.
"""

import time
import logging
import threading
import queue
from typing import Dict, Any, Optional
from dataclasses import dataclass
import uvicorn

from .config import ConfigurationManager
from .error_handling import ErrorHandler, ErrorSeverity, ErrorCategory

logger = logging.getLogger(__name__)


@dataclass
class SharedData:
    """
    Shared data structure for thread communication.
    
    This replaces shared memory buffers when running in threading mode,
    using thread-safe data structures for communication between threads.
    """
    # Sample data queue (replaces SharedSampleBuffer)
    sample_queue: queue.Queue = None
    
    # Analysis data (replaces SharedAnalysisBuffer)
    analysis_data: Dict[str, Any] = None
    analysis_lock: threading.Lock = None
    
    # Configuration data (replaces SharedConfigBuffer)
    config_data: Dict[str, Any] = None
    config_lock: threading.Lock = None
    
    # Shutdown event for coordinated shutdown
    shutdown_event: threading.Event = None
    
    def __post_init__(self):
        if self.sample_queue is None:
            self.sample_queue = queue.Queue(maxsize=6000)  # ~60 seconds at 100Hz
        
        if self.analysis_data is None:
            self.analysis_data = {}
        
        if self.analysis_lock is None:
            self.analysis_lock = threading.Lock()
        
        if self.config_data is None:
            self.config_data = {}
        
        if self.config_lock is None:
            self.config_lock = threading.Lock()
        
        if self.shutdown_event is None:
            self.shutdown_event = threading.Event()


class ThreadingDatalogger:
    """
    Threading-based datalogger that produces sample data.
    
    This is the threading equivalent of the multiprocessing datalogger,
    using queues instead of shared memory for data exchange.
    """
    
    def __init__(self, shared_data: SharedData, config: Dict[str, Any]):
        """
        Initialize threading datalogger.
        
        Args:
            shared_data: Shared data structure for thread communication
            config: Configuration dictionary
        """
        self.shared_data = shared_data
        self.config = config
        self.running = False
        
        # Initialize ADC adapter
        self.adc_adapter = None
        self._initialize_adc()
        
        logger.info("ThreadingDatalogger initialized")
    
    def _initialize_adc(self):
        """Initialize ADC adapter with fallback."""
        try:
            # Try to import and initialize ADS1115 adapter
            from .adapters import create_adc_adapter
            
            adc_config = self.config.get('adc_config', {})
            adc_type = self.config.get('adc_type', 'mock')
            
            self.adc_adapter = create_adc_adapter(adc_type, adc_config)
            logger.info(f"Using {type(self.adc_adapter).__name__} ADC adapter")
            
        except Exception as e:
            logger.error(f"Failed to initialize ADC adapter: {e}")
            # This should not happen due to fallback in create_adc_adapter,
            # but provide additional safety
            from .adapters import MockADCAdapter
            self.adc_adapter = MockADCAdapter()
            self.adc_adapter.initialize(self.config.get('adc_config', {}))
            logger.warning("Using MockADC as final fallback")
    
    def run(self):
        """Main datalogger loop."""
        logger.info("Starting threading datalogger")
        self.running = True
        
        sample_hz = self.config.get('sample_hz', 100)
        sample_interval = 1.0 / sample_hz
        
        batch_size = self.config.get('batch_size', 100)
        batch_interval_ms = self.config.get('batch_interval_ms', 1000)
        
        samples_collected = 0
        batch_start_time = time.time()
        
        try:
            while self.running and not self.shared_data.shutdown_event.is_set():
                start_time = time.time()
                
                try:
                    # Read sample from ADC
                    sample_value = self.adc_adapter.read_sample()
                    timestamp = time.time()
                    
                    # Create sample data
                    sample_data = {
                        'timestamp': timestamp,
                        'value': sample_value,
                        'sequence': samples_collected
                    }
                    
                    # Add to queue (non-blocking with timeout)
                    try:
                        self.shared_data.sample_queue.put(sample_data, timeout=0.1)
                    except queue.Full:
                        logger.warning("Sample queue is full, dropping sample")
                    
                    samples_collected += 1
                    
                    # Check if we should write batch to disk
                    elapsed_ms = (time.time() - batch_start_time) * 1000
                    if (samples_collected >= batch_size or 
                        elapsed_ms >= batch_interval_ms):
                        
                        # Reset batch counters
                        samples_collected = 0
                        batch_start_time = time.time()
                        
                        # Note: In threading mode, file I/O could be handled here
                        # or delegated to another thread to avoid blocking
                    
                    # Maintain sample rate
                    elapsed = time.time() - start_time
                    sleep_time = sample_interval - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    
                except Exception as e:
                    logger.error(f"Error in datalogger loop: {e}")
                    time.sleep(0.1)  # Brief pause on error
        
        except Exception as e:
            logger.error(f"Fatal error in threading datalogger: {e}")
        finally:
            self.running = False
            logger.info("Threading datalogger stopped")


class ThreadingEventLogger:
    """
    Threading-based event logger that processes samples and generates analysis.
    
    This consumes samples from the datalogger and produces analysis data,
    equivalent to the multiprocessing event logger.
    """
    
    def __init__(self, shared_data: SharedData, config: Dict[str, Any]):
        """
        Initialize threading event logger.
        
        Args:
            shared_data: Shared data structure for thread communication
            config: Configuration dictionary
        """
        self.shared_data = shared_data
        self.config = config
        self.running = False
        
        # Analysis configuration
        self.analysis_config = config.get('analysis_config', {})
        
        logger.info("ThreadingEventLogger initialized")
    
    def run(self):
        """Main event logger loop."""
        logger.info("Starting threading event logger")
        self.running = True
        
        sample_buffer = []
        last_analysis_time = time.time()
        analysis_interval = 1.0  # Analyze every second
        
        try:
            while self.running and not self.shared_data.shutdown_event.is_set():
                try:
                    # Get samples from queue
                    try:
                        sample_data = self.shared_data.sample_queue.get(timeout=1.0)
                        sample_buffer.append(sample_data)
                        
                        # Limit buffer size
                        if len(sample_buffer) > 1000:
                            sample_buffer = sample_buffer[-1000:]
                        
                    except queue.Empty:
                        # No samples available, continue
                        pass
                    
                    # Perform analysis periodically
                    if time.time() - last_analysis_time >= analysis_interval:
                        if sample_buffer:
                            analysis_result = self._perform_analysis(sample_buffer)
                            
                            # Update shared analysis data
                            with self.shared_data.analysis_lock:
                                self.shared_data.analysis_data.update(analysis_result)
                            
                            last_analysis_time = time.time()
                    
                    # Brief sleep to prevent busy waiting
                    time.sleep(0.01)
                    
                except Exception as e:
                    logger.error(f"Error in event logger loop: {e}")
                    time.sleep(0.1)
        
        except Exception as e:
            logger.error(f"Fatal error in threading event logger: {e}")
        finally:
            self.running = False
            logger.info("Threading event logger stopped")
    
    def _perform_analysis(self, samples: list) -> Dict[str, Any]:
        """
        Perform analysis on sample data.
        
        Args:
            samples: List of sample data dictionaries
            
        Returns:
            Dictionary containing analysis results
        """
        if not samples:
            return {}
        
        try:
            # Extract values and timestamps
            values = [s['value'] for s in samples]
            timestamps = [s['timestamp'] for s in samples]
            
            # Basic statistics
            analysis = {
                'timestamp': time.time(),
                'sample_count': len(samples),
                'min_value': min(values),
                'max_value': max(values),
                'avg_value': sum(values) / len(values),
                'latest_value': values[-1] if values else 0,
                'sample_rate': len(samples) / (timestamps[-1] - timestamps[0]) if len(timestamps) > 1 else 0
            }
            
            # RMS calculation if enabled
            if self.analysis_config.get('enable_rms', True):
                rms_value = (sum(v**2 for v in values) / len(values)) ** 0.5
                analysis['rms'] = rms_value
            
            # Frequency analysis if enabled
            if self.analysis_config.get('enable_freq', True):
                # Simple zero-crossing frequency estimation
                zero_crossings = 0
                dc_offset = self.analysis_config.get('dc_offset', 1.65)
                
                for i in range(1, len(values)):
                    if ((values[i-1] - dc_offset) * (values[i] - dc_offset)) < 0:
                        zero_crossings += 1
                
                if len(timestamps) > 1:
                    duration = timestamps[-1] - timestamps[0]
                    frequency = (zero_crossings / 2) / duration  # Half crossings per second
                    analysis['frequency'] = frequency
            
            # Sag/swell detection if enabled
            if self.analysis_config.get('enable_sags_swells', True):
                nominal_voltage = self.analysis_config.get('nominal_voltage', 120.0)
                sag_threshold = self.analysis_config.get('sag_threshold', 108.0)
                swell_threshold = self.analysis_config.get('swell_threshold', 132.0)
                
                # Convert ADC values to voltage (simplified)
                # This would need proper calibration in a real system
                voltage_values = [v * (nominal_voltage / 3.3) for v in values]
                
                sags = sum(1 for v in voltage_values if v < sag_threshold)
                swells = sum(1 for v in voltage_values if v > swell_threshold)
                
                analysis['sags_detected'] = sags
                analysis['swells_detected'] = swells
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error performing analysis: {e}")
            return {'error': str(e)}


class ThreadingWebServer:
    """
    Threading-based web server that serves the FastAPI application.
    
    This runs the web server in a thread, accessing shared data directly
    instead of through shared memory.
    """
    
    def __init__(self, shared_data: SharedData, config: Dict[str, Any]):
        """
        Initialize threading web server.
        
        Args:
            shared_data: Shared data structure for thread communication
            config: Configuration dictionary
        """
        self.shared_data = shared_data
        self.config = config
        self.running = False
        
        # Store reference to shared data in a way the FastAPI app can access it
        # This is a bit of a hack, but necessary for threading mode
        import pika.app
        pika.app._threading_shared_data = shared_data
        
        logger.info("ThreadingWebServer initialized")
    
    def run(self):
        """Run the web server."""
        logger.info("Starting threading web server")
        self.running = True
        
        try:
            port = self.config.get('port', 8000)
            
            # Configure uvicorn to run in the current thread
            config = uvicorn.Config(
                "pika.app:app",
                host="0.0.0.0",
                port=port,
                log_level="info",
                access_log=False,
                loop="asyncio"
            )
            
            server = uvicorn.Server(config)
            
            # Run the server (this will block until shutdown)
            server.run()
            
        except Exception as e:
            logger.error(f"Error in threading web server: {e}")
        finally:
            self.running = False
            logger.info("Threading web server stopped")


def run_threading_datalogger(shared_data: SharedData, config: Dict[str, Any]) -> None:
    """
    Entry point for threading datalogger.
    
    Args:
        shared_data: Shared data structure
        config: Configuration dictionary
    """
    try:
        datalogger = ThreadingDatalogger(shared_data, config)
        datalogger.run()
    except Exception as e:
        logger.error(f"Threading datalogger error: {e}")
        raise


def run_threading_event_logger(shared_data: SharedData, config: Dict[str, Any]) -> None:
    """
    Entry point for threading event logger.
    
    Args:
        shared_data: Shared data structure
        config: Configuration dictionary
    """
    try:
        event_logger = ThreadingEventLogger(shared_data, config)
        event_logger.run()
    except Exception as e:
        logger.error(f"Threading event logger error: {e}")
        raise


def run_threading_web_server(shared_data: SharedData, config: Dict[str, Any]) -> None:
    """
    Entry point for threading web server.
    
    Args:
        shared_data: Shared data structure
        config: Configuration dictionary
    """
    try:
        web_server = ThreadingWebServer(shared_data, config)
        web_server.run()
    except Exception as e:
        logger.error(f"Threading web server error: {e}")
        raise