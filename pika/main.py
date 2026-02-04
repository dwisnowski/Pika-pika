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
from .thread_supervisor import ThreadSupervisor
from .datalogger_process import run_datalogger_process
from .event_logger_process import EventLoggerProcess
from .threading_workers import (
    SharedData, run_threading_datalogger, run_threading_event_logger, 
    run_threading_web_server
)
from .config import ConfigurationManager, ConfigurationError
from .error_handling import setup_error_handling, ErrorHandler, ErrorSeverity, ErrorCategory
from .performance_optimizer import PerformanceOptimizer, create_optimized_process_config

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Reduced from INFO to WARNING to reduce spam
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_event_logger_process(sample_buffer_name: str, analysis_buffer_name: str, 
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


def run_fastapi_process(port: int) -> None:
    """Entry point for FastAPI process."""
    try:
        # Set up logging for the process
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - FastAPI - %(levelname)s - %(message)s'
        )
        
        # Import and run FastAPI app
        # The FastAPI app will load its own configuration from config.toml
        # and use the shared memory names from there
        import uvicorn
        
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


class MultiprocessingApplication:
    """
    Main application that coordinates execution in either multiprocessing or threading mode.
    
    This class initializes shared resources, starts all components in the correct 
    dependency order, and implements supervision for both multiprocessing and 
    threading execution modes.
    """
    
    def __init__(self, config_path: str = "config.toml"):
        """
        Initialize the application.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.config_manager = ConfigurationManager(config_path)
        
        # Execution mode (determined from config)
        self.execution_mode: str = "multiprocessing"
        
        # Supervisors (only one will be used based on mode)
        self.process_supervisor: Optional[ProcessSupervisor] = None
        self.thread_supervisor: Optional[ThreadSupervisor] = None
        
        # Error handling system
        self.error_handler: Optional[ErrorHandler] = None
        
        # Performance optimization system
        self.performance_optimizer: Optional[PerformanceOptimizer] = None
        
        # Shared resources (multiprocessing mode)
        self.shared_sample_buffer: Optional[SharedSampleBuffer] = None
        self.shared_analysis_buffer: Optional[SharedAnalysisBuffer] = None
        self.shared_config_buffer: Optional[SharedConfigBuffer] = None
        
        # Shared data (threading mode)
        self.shared_data: Optional[SharedData] = None
        
        # Application state
        self.running = False
        self.shutdown_event = Event()
        
        # Setup error handling first
        self._setup_error_handling()
        
        # Setup performance optimization
        self._setup_performance_optimization()
        
        # Load and validate configuration
        self._load_and_validate_configuration()
        
        # Determine execution mode
        self.execution_mode = self.config.get("execution", {}).get("mode", "multiprocessing")
        
        logger.info(f"Application initialized in {self.execution_mode} mode")
    
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
    
    def initialize_shared_resources(self) -> None:
        """
        Initialize shared resources for inter-component communication.
        
        Creates either shared memory buffers (multiprocessing) or shared data 
        structures (threading) based on the execution mode.
        """
        try:
            logger.info(f"Initializing shared resources for {self.execution_mode} mode")
            
            if self.execution_mode == "multiprocessing":
                self._initialize_shared_memory()
            else:  # threading mode
                self._initialize_shared_data()
            
            logger.info("Shared resources initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize shared resources: {e}")
            if self.error_handler:
                self.error_handler.handle_error(
                    e, "main", ErrorSeverity.CRITICAL, ErrorCategory.SHARED_MEMORY
                )
            raise
    
    def _initialize_shared_memory(self) -> None:
        """Initialize shared memory structures for multiprocessing mode."""
        # Get shared memory names from configuration
        mp_config = self.config.get("multiprocessing", {})
        shared_memory_names = mp_config.get('shared_memory_names', {})
        sample_buffer_name = shared_memory_names.get('sample_buffer', 'pika_samples')
        analysis_buffer_name = shared_memory_names.get('analysis_buffer', 'pika_analysis')
        config_buffer_name = shared_memory_names.get('config_buffer', 'pika_config')
        
        # Create shared sample buffer (60 seconds at configured sample rate)
        sample_hz = self.config["pika"]["sample_hz"]
        buffer_size = sample_hz * 60  # 60 seconds of data
        
        self.shared_sample_buffer = SharedSampleBuffer(
            size=buffer_size,
            create=True,
            name=sample_buffer_name
        )
        logger.info(f"Created shared sample buffer: {buffer_size} samples")
        
        # Create shared analysis buffer
        self.shared_analysis_buffer = SharedAnalysisBuffer(
            create=True,
            name=analysis_buffer_name
        )
        logger.info("Created shared analysis buffer")
        
        # Create shared configuration buffer and initialize with current config
        self.shared_config_buffer = SharedConfigBuffer(
            create=True,
            name=config_buffer_name
        )
        
        # Initialize configuration buffer with loaded configuration
        config_data = self.config_manager.get_shared_config_data()
        self.shared_config_buffer.update_config(config_data)
        logger.info("Created and initialized shared configuration buffer")
    
    def _initialize_shared_data(self) -> None:
        """Initialize shared data structures for threading mode."""
        from .threading_workers import SharedData
        
        self.shared_data = SharedData()
        
        # Initialize configuration data
        config_data = self.config_manager.get_shared_config_data()
        with self.shared_data.config_lock:
            self.shared_data.config_data.update(config_data)
        
        logger.info("Created shared data structures for threading mode")
    
    def start_components(self) -> None:
        """
        Start all components in correct dependency order.
        
        The startup order ensures that dependencies are available before
        dependent components start. Uses either multiprocessing or threading
        based on the execution mode.
        """
        try:
            logger.info(f"Starting components in {self.execution_mode} mode")
            
            if self.execution_mode == "multiprocessing":
                self._start_processes()
            else:  # threading mode
                self._start_threads()
            
            logger.info("All components started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start components: {e}")
            raise
    
    def _start_processes(self) -> None:
        """Start components in multiprocessing mode."""
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
            target=run_event_logger_process,
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
            target=run_fastapi_process,
            args=(fastapi_config['port'],),
            cpu_affinity=2,  # Core 3
            max_restarts=3  # Fewer restarts for web server
        )
        
        # Start all processes
        success = self.process_supervisor.start_all()
        
        if not success:
            raise RuntimeError("Failed to start all processes")
    
    def _start_threads(self) -> None:
        """Start components in threading mode."""
        # Initialize thread supervisor
        threading_config = self.config.get("threading", {})
        self.thread_supervisor = ThreadSupervisor(
            heartbeat_interval=threading_config.get("heartbeat_interval", 2.0),
            restart_delay=threading_config.get("restart_delay", 1.0),
            error_handler=self.error_handler
        )
        
        # Register shared data for cleanup
        self.thread_supervisor.register_shared_resource(self.shared_data)
        
        # Register datalogger thread
        datalogger_config = self.config_manager.get_process_config('datalogger')
        self.thread_supervisor.register_thread(
            name='datalogger',
            target=run_threading_datalogger,
            args=(self.shared_data, datalogger_config),
            max_restarts=threading_config.get("max_restarts", 3)
        )
        
        # Register event logger thread
        event_logger_config = self.config_manager.get_process_config('event_logger')
        self.thread_supervisor.register_thread(
            name='event_logger',
            target=run_threading_event_logger,
            args=(self.shared_data, event_logger_config),
            max_restarts=threading_config.get("max_restarts", 3)
        )
        
        # Register web server thread
        fastapi_config = self.config_manager.get_process_config('fastapi')
        self.thread_supervisor.register_thread(
            name='fastapi',
            target=run_threading_web_server,
            args=(self.shared_data, fastapi_config),
            max_restarts=2  # Fewer restarts for web server
        )
        
        # Start all threads
        success = self.thread_supervisor.start_all()
        
        if not success:
            raise RuntimeError("Failed to start all threads")
        
        # Start health monitoring
        self.thread_supervisor.start_monitoring()
    
    def run_supervision_loop(self) -> None:
        """
        Implement supervision loop.
        
        This method runs the main supervision loop that monitors component health,
        handles restarts, and coordinates graceful shutdown for both execution modes.
        """
        try:
            logger.info(f"Starting supervision loop in {self.execution_mode} mode")
            self.running = True
            
            if self.execution_mode == "multiprocessing":
                self._run_process_supervision()
            else:  # threading mode
                self._run_thread_supervision()
            
            logger.info("Supervision loop ended")
            
        except Exception as e:
            logger.error(f"Supervision loop error: {e}")
        finally:
            self.running = False
    
    def _run_process_supervision(self) -> None:
        """Run supervision loop for multiprocessing mode."""
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
                    self._log_component_status(status)
                
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
    
    def _run_thread_supervision(self) -> None:
        """Run supervision loop for threading mode."""
        # Main supervision loop (monitoring is handled by ThreadSupervisor)
        while self.running and not self.shutdown_event.is_set():
            try:
                # Check thread status
                status = self.thread_supervisor.get_all_status()
                
                # Log status periodically (every 30 seconds)
                if int(time.time()) % 30 == 0:
                    self._log_component_status(status)
                
                # Check for failed threads that need attention
                for name, info in status.items():
                    if info['state'] == 'failed' and info['restart_count'] >= info['max_restarts']:
                        logger.error(f"Thread {name} has failed permanently after {info['restart_count']} restarts")
                
                # Sleep before next check
                time.sleep(1.0)
                
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
                break
            except Exception as e:
                logger.error(f"Error in supervision loop: {e}")
                time.sleep(5.0)  # Back off on errors
    
    def _log_component_status(self, status: Dict[str, Dict[str, Any]]) -> None:
        """Log component status information."""
        try:
            running_count = sum(1 for info in status.values() if info.get('is_alive', False))
            total_count = len(status)
            
            logger.info(f"Component status: {running_count}/{total_count} running")
            
            for name, info in status.items():
                if info.get('is_alive', False):
                    uptime = info.get('uptime', 0)
                    cpu_percent = info.get('cpu_percent', 0)
                    memory_mb = info.get('memory_mb', 0)
                    logger.debug(f"  {name}: UP (uptime: {uptime:.1f}s, CPU: {cpu_percent:.1f}%, RAM: {memory_mb:.1f}MB)")
                else:
                    logger.warning(f"  {name}: DOWN (state: {info.get('state', 'unknown')}, restarts: {info.get('restart_count', 0)})")
                    
        except Exception as e:
            logger.debug(f"Error logging component status: {e}")
    
    def shutdown(self) -> None:
        """
        Graceful shutdown of the entire application.
        
        Coordinates shutdown sequence across all components and cleans up
        shared resources for both execution modes.
        """
        if not self.running:
            logger.info("Application already shut down")
            return
        
        logger.info("Initiating graceful shutdown")
        self.running = False
        self.shutdown_event.set()
        
        try:
            if self.execution_mode == "multiprocessing":
                self._shutdown_processes()
            else:  # threading mode
                self._shutdown_threads()
            
            logger.info("Graceful shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def _shutdown_processes(self) -> None:
        """Shutdown processes and clean up shared memory."""
        # Stop process supervisor (this will stop all processes)
        if self.process_supervisor:
            mp_config = self.config.get("multiprocessing", {})
            timeout = mp_config.get("shutdown_timeout", 30.0)
            self.process_supervisor.graceful_shutdown(timeout=timeout)
        
        # Clean up shared memory resources (supervisor should handle this)
        # But provide backup cleanup
        for resource in [self.shared_sample_buffer, self.shared_analysis_buffer, self.shared_config_buffer]:
            if resource:
                try:
                    resource.cleanup()
                except Exception as e:
                    logger.debug(f"Error cleaning up shared memory: {e}")
    
    def _shutdown_threads(self) -> None:
        """Shutdown threads and clean up shared data."""
        # Signal shutdown to shared data
        if self.shared_data:
            self.shared_data.shutdown_event.set()
        
        # Stop thread supervisor (this will stop all threads)
        if self.thread_supervisor:
            threading_config = self.config.get("threading", {})
            timeout = threading_config.get("shutdown_timeout", 15.0)
            self.thread_supervisor.graceful_shutdown(timeout=timeout)
    
    def start(self) -> None:
        """
        Start the complete application.
        
        This is the main entry point that initializes everything and starts
        the supervision loop in either multiprocessing or threading mode.
        """
        try:
            logger.info(f"Starting datalogger application in {self.execution_mode} mode")
            
            # Initialize shared resources
            self.initialize_shared_resources()
            
            # Start all components
            self.start_components()
            
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
            'execution_mode': self.execution_mode,
            'config_path': self.config_path
        }
        
        if self.execution_mode == "multiprocessing":
            status['shared_memory_initialized'] = all([
                self.shared_sample_buffer is not None,
                self.shared_analysis_buffer is not None,
                self.shared_config_buffer is not None
            ])
            
            if self.process_supervisor:
                status['components'] = self.process_supervisor.get_all_status()
                status['supervisor_running'] = self.process_supervisor.is_running()
            
            # Add shared memory status
            if self.shared_sample_buffer:
                status['sample_buffer'] = self.shared_sample_buffer.get_buffer_info()
            
            if self.shared_analysis_buffer:
                status['analysis_buffer'] = self.shared_analysis_buffer.get_buffer_info()
            
            if self.shared_config_buffer:
                status['config_buffer'] = self.shared_config_buffer.get_buffer_info()
        
        else:  # threading mode
            status['shared_data_initialized'] = self.shared_data is not None
            
            if self.thread_supervisor:
                status['components'] = self.thread_supervisor.get_all_status()
                status['supervisor_running'] = self.thread_supervisor.is_running()
            
            # Add shared data status
            if self.shared_data:
                status['sample_queue_size'] = self.shared_data.sample_queue.qsize()
                with self.shared_data.analysis_lock:
                    status['analysis_data_keys'] = list(self.shared_data.analysis_data.keys())
                with self.shared_data.config_lock:
                    status['config_data_keys'] = list(self.shared_data.config_data.keys())
        
        # Add configuration status
        status['config'] = {
            'path': self.config_path,
            'loaded': bool(self.config),
            'validation_errors': self.config_manager.get_validation_errors() if hasattr(self, 'config_manager') else []
        }
        
        return status


def main(config_path: str = "config.toml") -> None:
    """
    Main entry point for the datalogger application.
    
    Args:
        config_path: Path to configuration file
    """
    # Set up signal handlers for graceful shutdown
    app = None
    shutdown_requested = False
    
    def signal_handler(signum, frame):
        nonlocal shutdown_requested
        if shutdown_requested:
            print("\n💥 Force shutdown requested!")
            os._exit(1)  # Force exit if already shutting down
        
        shutdown_requested = True
        print(f"\n🛑 Shutdown signal received (signal {signum})")
        if app:
            print("   Initiating graceful shutdown...")
            app.shutdown()
        else:
            print("   Application not started yet, exiting...")
            sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        print("🚀 Starting Pika-pika datalogger system...")
        print("   Press Ctrl+C to stop gracefully")
        print("   Press Ctrl+C twice to force stop")
        print()
        
        # Create and start application
        app = MultiprocessingApplication(config_path)
        print(f"   Execution mode: {app.execution_mode}")
        print()
        app.start()
        
    except KeyboardInterrupt:
        if not shutdown_requested:
            print("\n🛑 Keyboard interrupt received")
            if app:
                app.shutdown()
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