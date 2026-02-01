"""
Main application entry point for multiprocessing datalogger architecture.

This module provides the main entry point that initializes shared memory structures,
starts all processes in correct dependency order, and implements the process
supervision loop for the multiprocessing datalogger system.
"""

import os
import sys
import time
import logging
import signal
import threading
from typing import Dict, Any, Optional
from multiprocessing import Event

from .shared_memory import SharedSampleBuffer, SharedAnalysisBuffer, SharedConfigBuffer
from .process_supervisor import ProcessSupervisor
from .datalogger_process import run_datalogger_process
from .event_logger_process import EventLoggerProcess
from .config import ConfigurationManager, ConfigurationError
from .error_handling import setup_error_handling, ErrorHandler, ErrorSeverity, ErrorCategory
from .performance_optimizer import PerformanceOptimizer, create_optimized_process_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MultiprocessingApplication:
    """
    Main multiprocessing application that coordinates all processes.
    
    This class initializes shared memory structures, starts all processes
    in the correct dependency order, and implements process supervision
    for the datalogger multiprocessing architecture.
    """
    
    def __init__(self, config_path: str = "config.toml"):
        """
        Initialize the multiprocessing application.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.config_manager = ConfigurationManager(config_path)
        self.process_supervisor: Optional[ProcessSupervisor] = None
        
        # Error handling system
        self.error_handler: Optional[ErrorHandler] = None
        
        # Performance optimization system
        self.performance_optimizer: Optional[PerformanceOptimizer] = None
        
        # Shared memory resources
        self.shared_sample_buffer: Optional[SharedSampleBuffer] = None
        self.shared_analysis_buffer: Optional[SharedAnalysisBuffer] = None
        self.shared_config_buffer: Optional[SharedConfigBuffer] = None
        
        # Application state
        self.running = False
        self.shutdown_event = Event()
        
        # Setup error handling first
        self._setup_error_handling()
        
        # Setup performance optimization
        self._setup_performance_optimization()
        
        # Load and validate configuration
        self._load_and_validate_configuration()
        
        logger.info("MultiprocessingApplication initialized with comprehensive error handling")
    
    def _setup_error_handling(self) -> None:
        """Setup comprehensive error handling system."""
        try:
            # Create logs directory
            log_dir = "logs"
            os.makedirs(log_dir, exist_ok=True)
            
            # Setup error handler
            self.error_handler = setup_error_handling(
                log_dir=log_dir,
                enable_console=True
            )
            
            logger.info("Error handling system initialized")
            
        except Exception as e:
            logger.error(f"Failed to setup error handling: {e}")
            # Continue without error handler - basic logging will still work
            self.error_handler = None
    
    def _setup_performance_optimization(self) -> None:
        """Setup performance optimization system."""
        try:
            # Create performance optimizer
            self.performance_optimizer = PerformanceOptimizer(
                enable_monitoring=True,
                monitoring_interval=10.0
            )
            
            logger.info("Performance optimization system initialized")
            
        except Exception as e:
            logger.error(f"Failed to setup performance optimization: {e}")
            if self.error_handler:
                self.error_handler.handle_error(
                    e, "main", ErrorSeverity.MEDIUM, ErrorCategory.RESOURCE
                )
            # Continue without performance optimizer - basic functionality will still work
            self.performance_optimizer = None
    
    def _load_and_validate_configuration(self) -> None:
        """Load and validate configuration using ConfigurationManager."""
        try:
            self.config = self.config_manager.load_configuration()
            logger.info("Configuration loaded and validated successfully")
            
            # Log any validation warnings
            validation_errors = self.config_manager.get_validation_errors()
            if validation_errors:
                for error in validation_errors:
                    logger.warning(f"Configuration warning: {error}")
            
        except ConfigurationError as e:
            logger.error(f"Configuration error: {e}")
            if self.error_handler:
                self.error_handler.handle_error(
                    e, "main", ErrorSeverity.CRITICAL, ErrorCategory.CONFIGURATION
                )
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading configuration: {e}")
            if self.error_handler:
                self.error_handler.handle_error(
                    e, "main", ErrorSeverity.CRITICAL, ErrorCategory.CONFIGURATION
                )
            raise ConfigurationError(f"Configuration loading failed: {e}")
    
    def initialize_shared_memory(self) -> None:
        """
        Initialize shared memory structures for inter-process communication.
        
        Creates the shared memory buffers that will be used by all processes
        for efficient data exchange without serialization overhead.
        """
        try:
            logger.info("Initializing shared memory structures")
            
            # Create shared sample buffer (60 seconds at configured sample rate)
            sample_hz = self.config["pika"]["sample_hz"]
            buffer_size = sample_hz * 60  # 60 seconds of data
            
            self.shared_sample_buffer = SharedSampleBuffer(
                size=buffer_size,
                create=True,
                name="pika_samples"
            )
            logger.info(f"Created shared sample buffer: {buffer_size} samples")
            
            # Create shared analysis buffer
            self.shared_analysis_buffer = SharedAnalysisBuffer(
                create=True,
                name="pika_analysis"
            )
            logger.info("Created shared analysis buffer")
            
            # Create shared configuration buffer and initialize with current config
            self.shared_config_buffer = SharedConfigBuffer(
                create=True,
                name="pika_config"
            )
            
            # Initialize configuration buffer with loaded configuration
            config_data = self.config_manager.get_shared_config_data()
            self.shared_config_buffer.update_config(config_data)
            logger.info("Created and initialized shared configuration buffer")
            
            logger.info("Shared memory initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize shared memory: {e}")
            if self.error_handler:
                self.error_handler.handle_error(
                    e, "main", ErrorSeverity.CRITICAL, ErrorCategory.SHARED_MEMORY
                )
            raise
    
    def start_processes(self) -> None:
        """
        Start all processes in correct dependency order.
        
        The startup order ensures that dependencies are available before
        dependent processes start:
        1. Datalogger Process (provides sample data)
        2. Event Logger Process (consumes sample data, provides analysis)
        3. FastAPI Process (consumes both sample and analysis data)
        """
        try:
            logger.info("Starting processes in dependency order")
            
            # Initialize process supervisor with configuration, error handling, and performance optimization
            mp_config = self.config.get("multiprocessing", {})
            self.process_supervisor = ProcessSupervisor(
                heartbeat_interval=mp_config.get("heartbeat_interval", 5.0),
                restart_delay=mp_config.get("restart_delay", 2.0),
                error_handler=self.error_handler,
                performance_optimizer=self.performance_optimizer
            )
            
            # Register shared memory resources for cleanup
            self.process_supervisor.register_shared_memory(self.shared_sample_buffer)
            self.process_supervisor.register_shared_memory(self.shared_analysis_buffer)
            self.process_supervisor.register_shared_memory(self.shared_config_buffer)
            
            # Register datalogger process (Core 1)
            datalogger_config = self.config_manager.get_process_config('datalogger')
            datalogger_config['adc_type'] = 'ads1115'  # Default to ADS1115, will fallback to mock if needed
            
            mp_config = self.config.get("multiprocessing", {})
            self.process_supervisor.register_process(
                name='datalogger',
                target=run_datalogger_process,
                args=(self.shared_sample_buffer, self.shared_config_buffer),
                kwargs=datalogger_config,
                cpu_affinity=0,  # Core 1 (0-indexed)
                max_restarts=mp_config.get("max_restarts", 5)
            )
            
            # Register event logger process (Core 2)
            event_logger_config = self.config_manager.get_process_config('event_logger')
            self.process_supervisor.register_process(
                name='event_logger',
                target=self._run_event_logger_process,
                args=(
                    self.shared_sample_buffer.shm.name,
                    self.shared_analysis_buffer.shm.name,
                    self.shared_config_buffer.shm.name,
                    event_logger_config['data_dir']
                ),
                cpu_affinity=1,  # Core 2
                max_restarts=mp_config.get("max_restarts", 5)
            )
            
            # Register FastAPI process (Core 3)
            fastapi_config = self.config_manager.get_process_config('fastapi')
            self.process_supervisor.register_process(
                name='fastapi',
                target=self._run_fastapi_process,
                args=(
                    self.shared_sample_buffer.shm.name,
                    self.shared_analysis_buffer.shm.name,
                    self.shared_config_buffer.shm.name,
                    fastapi_config['port']
                ),
                cpu_affinity=2,  # Core 3
                max_restarts=3  # Fewer restarts for web server
            )
            
            # Start all processes
            success = self.process_supervisor.start_all()
            
            if not success:
                raise RuntimeError("Failed to start all processes")
            
            logger.info("All processes started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start processes: {e}")
            raise
    
    def _run_event_logger_process(self, sample_buffer_name: str, analysis_buffer_name: str, 
                                 config_buffer_name: str, data_dir: str) -> None:
        """Entry point for event logger process."""
        try:
            # Set up logging for the process
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - EventLogger - %(levelname)s - %(message)s'
            )
            
            # Create and run event logger
            event_logger = EventLoggerProcess(
                sample_buffer_name=sample_buffer_name,
                analysis_buffer_name=analysis_buffer_name,
                config_buffer_name=config_buffer_name,
                data_dir=data_dir
            )
            
            event_logger.run()
            
        except Exception as e:
            logger.error(f"Event logger process error: {e}")
            raise
    
    def _run_fastapi_process(self, sample_buffer_name: str, analysis_buffer_name: str,
                           config_buffer_name: str, port: int) -> None:
        """Entry point for FastAPI process."""
        try:
            # Set up logging for the process
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - FastAPI - %(levelname)s - %(message)s'
            )
            
            # Import and run FastAPI app
            # Note: This would need to be updated to use shared memory names
            # For now, we'll use uvicorn to run the existing app
            import uvicorn
            
            # Set environment variables for shared memory names
            os.environ['PIKA_SAMPLE_BUFFER_NAME'] = sample_buffer_name
            os.environ['PIKA_ANALYSIS_BUFFER_NAME'] = analysis_buffer_name
            os.environ['PIKA_CONFIG_BUFFER_NAME'] = config_buffer_name
            os.environ['PIKA_MULTIPROCESSING_MODE'] = 'true'
            
            uvicorn.run(
                "pika.app:app",
                host="0.0.0.0",
                port=port,
                log_level="info",
                access_log=False  # Reduce log noise
            )
            
        except Exception as e:
            logger.error(f"FastAPI process error: {e}")
            raise
    
    def run_supervision_loop(self) -> None:
        """
        Implement process supervision loop.
        
        This method runs the main supervision loop that monitors process health,
        handles restarts, and coordinates graceful shutdown.
        """
        try:
            logger.info("Starting process supervision loop")
            self.running = True
            
            # Start health monitoring in a separate thread
            health_thread = threading.Thread(
                target=self.process_supervisor.monitor_health,
                name="HealthMonitor",
                daemon=True
            )
            health_thread.start()
            
            # Main supervision loop
            while self.running and not self.shutdown_event.is_set():
                try:
                    # Check process status
                    status = self.process_supervisor.get_all_status()
                    
                    # Log status periodically (every 30 seconds)
                    if int(time.time()) % 30 == 0:
                        self._log_process_status(status)
                    
                    # Check for failed processes that need attention
                    for name, info in status.items():
                        if info['state'] == 'failed' and info['restart_count'] >= info['max_restarts']:
                            logger.error(f"Process {name} has failed permanently after {info['restart_count']} restarts")
                            # Could implement notification or emergency shutdown here
                    
                    # Sleep before next check
                    time.sleep(1.0)
                    
                except KeyboardInterrupt:
                    logger.info("Received keyboard interrupt")
                    break
                except Exception as e:
                    logger.error(f"Error in supervision loop: {e}")
                    time.sleep(5.0)  # Back off on errors
            
            logger.info("Process supervision loop ended")
            
        except Exception as e:
            logger.error(f"Supervision loop error: {e}")
        finally:
            self.running = False
    
    def _log_process_status(self, status: Dict[str, Dict[str, Any]]) -> None:
        """Log process status information."""
        try:
            running_count = sum(1 for info in status.values() if info['is_alive'])
            total_count = len(status)
            
            logger.info(f"Process status: {running_count}/{total_count} running")
            
            for name, info in status.items():
                if info['is_alive']:
                    uptime = info.get('uptime', 0)
                    cpu_percent = info.get('cpu_percent', 0)
                    memory_mb = info.get('memory_mb', 0)
                    logger.debug(f"  {name}: UP (uptime: {uptime:.1f}s, CPU: {cpu_percent:.1f}%, RAM: {memory_mb:.1f}MB)")
                else:
                    logger.warning(f"  {name}: DOWN (state: {info['state']}, restarts: {info['restart_count']})")
                    
        except Exception as e:
            logger.debug(f"Error logging process status: {e}")
    
    def shutdown(self) -> None:
        """
        Graceful shutdown of the entire application.
        
        Coordinates shutdown sequence across all processes and cleans up
        shared memory resources.
        """
        if not self.running:
            logger.info("Application already shut down")
            return
        
        logger.info("Initiating graceful shutdown")
        self.running = False
        self.shutdown_event.set()
        
        try:
            # Stop process supervisor (this will stop all processes)
            if self.process_supervisor:
                self.process_supervisor.graceful_shutdown(timeout=30.0)
            
            # Clean up shared memory resources (supervisor should handle this)
            # But provide backup cleanup
            for resource in [self.shared_sample_buffer, self.shared_analysis_buffer, self.shared_config_buffer]:
                if resource:
                    try:
                        resource.cleanup()
                    except Exception as e:
                        logger.debug(f"Error cleaning up shared memory: {e}")
            
            logger.info("Graceful shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def start(self) -> None:
        """
        Start the complete multiprocessing application.
        
        This is the main entry point that initializes everything and starts
        the supervision loop.
        """
        try:
            logger.info("Starting multiprocessing datalogger application")
            
            # Initialize shared memory
            self.initialize_shared_memory()
            
            # Start all processes
            self.start_processes()
            
            # Run supervision loop
            self.run_supervision_loop()
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down")
        except Exception as e:
            logger.error(f"Application error: {e}")
            raise
        finally:
            self.shutdown()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current application status for monitoring."""
        status = {
            'running': self.running,
            'config_path': self.config_path,
            'shared_memory_initialized': all([
                self.shared_sample_buffer is not None,
                self.shared_analysis_buffer is not None,
                self.shared_config_buffer is not None
            ])
        }
        
        if self.process_supervisor:
            status['processes'] = self.process_supervisor.get_all_status()
            status['supervisor_running'] = self.process_supervisor.is_running()
        
        # Add configuration status
        status['config'] = {
            'path': self.config_path,
            'loaded': bool(self.config),
            'validation_errors': self.config_manager.get_validation_errors() if hasattr(self, 'config_manager') else []
        }
        
        # Add shared memory status
        if self.shared_sample_buffer:
            status['sample_buffer'] = self.shared_sample_buffer.get_buffer_info()
        
        if self.shared_analysis_buffer:
            status['analysis_buffer'] = self.shared_analysis_buffer.get_buffer_info()
        
        if self.shared_config_buffer:
            status['config_buffer'] = self.shared_config_buffer.get_buffer_info()
        
        return status


def main(config_path: str = "config.toml") -> None:
    """
    Main entry point for the multiprocessing datalogger application.
    
    Args:
        config_path: Path to configuration file
    """
    # Set up signal handlers for graceful shutdown
    app = None
    
    def signal_handler(signum, frame):
        if app:
            logger.info(f"Received signal {signum}, shutting down")
            app.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Create and start application
        app = MultiprocessingApplication(config_path)
        app.start()
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Multiprocessing Datalogger Application")
    parser.add_argument(
        "--config",
        default="config.toml",
        help="Path to configuration file (default: config.toml)"
    )
    
    args = parser.parse_args()
    main(args.config)