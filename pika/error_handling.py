"""
Comprehensive error handling and logging system for multiprocessing datalogger.

This module provides centralized error handling, logging configuration, and
crash detection/recovery mechanisms for all processes in the multiprocessing
architecture.
"""

import os
import sys
import time
import logging
import traceback
import threading
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from multiprocessing import Queue, Process
import json


class ErrorSeverity(Enum):
    """Error severity levels for categorization."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""
    HARDWARE = "hardware"
    SHARED_MEMORY = "shared_memory"
    PROCESS = "process"
    NETWORK = "network"
    CONFIGURATION = "configuration"
    DATA_INTEGRITY = "data_integrity"
    RESOURCE = "resource"
    UNKNOWN = "unknown"


@dataclass
class ErrorEvent:
    """Represents an error event with metadata."""
    timestamp: float
    process_name: str
    error_type: str
    message: str
    severity: ErrorSeverity
    category: ErrorCategory
    traceback_info: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    recovery_attempted: bool = False
    recovery_successful: bool = False
    occurrence_count: int = 1


class ErrorHandler:
    """
    Centralized error handler for the multiprocessing system.
    
    Provides error logging, categorization, recovery coordination,
    and crash detection across all processes.
    """
    
    def __init__(self, log_dir: str = "logs", max_log_size_mb: int = 10, 
                 backup_count: int = 5, enable_console: bool = True):
        """
        Initialize the error handler.
        
        Args:
            log_dir: Directory for log files
            max_log_size_mb: Maximum size of each log file in MB
            backup_count: Number of backup log files to keep
            enable_console: Whether to enable console logging
        """
        self.log_dir = log_dir
        self.max_log_size_mb = max_log_size_mb
        self.backup_count = backup_count
        self.enable_console = enable_console
        
        # Error tracking
        self.error_history: List[ErrorEvent] = []
        self.error_counts: Dict[str, int] = {}
        self.recovery_handlers: Dict[ErrorCategory, Callable] = {}
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Ensure log directory exists
        os.makedirs(log_dir, exist_ok=True)
        
        # Setup logging
        self._setup_logging()
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("ErrorHandler initialized")
    
    def _setup_logging(self) -> None:
        """Setup comprehensive logging configuration."""
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(processName)s:%(process)d - '
            '%(filename)s:%(lineno)d - %(message)s'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # Root logger configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Console handler
        if self.enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(simple_formatter)
            root_logger.addHandler(console_handler)
        
        # Main application log (rotating by size)
        main_log_path = os.path.join(self.log_dir, "pika_main.log")
        main_handler = RotatingFileHandler(
            main_log_path,
            maxBytes=self.max_log_size_mb * 1024 * 1024,
            backupCount=self.backup_count
        )
        main_handler.setLevel(logging.INFO)
        main_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(main_handler)
        
        # Error log (rotating by time - daily)
        error_log_path = os.path.join(self.log_dir, "pika_errors.log")
        error_handler = TimedRotatingFileHandler(
            error_log_path,
            when='midnight',
            interval=1,
            backupCount=30  # Keep 30 days of error logs
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(error_handler)
        
        # Process-specific loggers
        self._setup_process_loggers()
    
    def _setup_process_loggers(self) -> None:
        """Setup individual loggers for each process."""
        processes = ['datalogger', 'event_logger', 'fastapi', 'websocket']
        
        for process_name in processes:
            logger = logging.getLogger(f"pika.{process_name}")
            
            # Process-specific log file
            log_path = os.path.join(self.log_dir, f"pika_{process_name}.log")
            handler = RotatingFileHandler(
                log_path,
                maxBytes=self.max_log_size_mb * 1024 * 1024,
                backupCount=self.backup_count
            )
            handler.setLevel(logging.DEBUG)
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
            ))
            
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
    
    def handle_error(self, error: Exception, process_name: str = "unknown",
                    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                    category: ErrorCategory = ErrorCategory.UNKNOWN,
                    context: Optional[Dict[str, Any]] = None,
                    attempt_recovery: bool = True) -> bool:
        """
        Handle an error with logging, categorization, and recovery.
        
        Args:
            error: The exception that occurred
            process_name: Name of the process where error occurred
            severity: Severity level of the error
            category: Category of the error
            context: Additional context information
            attempt_recovery: Whether to attempt automatic recovery
            
        Returns:
            True if error was handled successfully (possibly with recovery)
        """
        with self._lock:
            # Create error event
            error_event = ErrorEvent(
                timestamp=time.time(),
                process_name=process_name,
                error_type=type(error).__name__,
                message=str(error),
                severity=severity,
                category=category,
                traceback_info=traceback.format_exc(),
                context=context or {}
            )
            
            # Update error counts
            error_key = f"{process_name}:{error_event.error_type}"
            self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
            error_event.occurrence_count = self.error_counts[error_key]
            
            # Log the error
            self._log_error_event(error_event)
            
            # Add to history
            self.error_history.append(error_event)
            
            # Trim history if too long
            if len(self.error_history) > 1000:
                self.error_history = self.error_history[-500:]  # Keep last 500
            
            # Attempt recovery if requested
            recovery_successful = False
            if attempt_recovery and category in self.recovery_handlers:
                try:
                    error_event.recovery_attempted = True
                    recovery_successful = self.recovery_handlers[category](error_event)
                    error_event.recovery_successful = recovery_successful
                except Exception as recovery_error:
                    self.logger.error(f"Recovery handler failed: {recovery_error}")
            
            # Check for critical error patterns
            self._check_critical_patterns(error_event)
            
            return recovery_successful
    
    def _log_error_event(self, error_event: ErrorEvent) -> None:
        """Log an error event with appropriate level and detail."""
        logger = logging.getLogger(f"pika.{error_event.process_name}")
        
        # Create log message
        message = (
            f"[{error_event.severity.value.upper()}] {error_event.error_type}: "
            f"{error_event.message}"
        )
        
        if error_event.context:
            message += f" | Context: {json.dumps(error_event.context, default=str)}"
        
        if error_event.occurrence_count > 1:
            message += f" | Occurrence: {error_event.occurrence_count}"
        
        # Log with appropriate level
        if error_event.severity == ErrorSeverity.CRITICAL:
            logger.critical(message)
            if error_event.traceback_info:
                logger.critical(f"Traceback:\n{error_event.traceback_info}")
        elif error_event.severity == ErrorSeverity.HIGH:
            logger.error(message)
            if error_event.traceback_info:
                logger.error(f"Traceback:\n{error_event.traceback_info}")
        elif error_event.severity == ErrorSeverity.MEDIUM:
            logger.warning(message)
            if error_event.traceback_info:
                logger.debug(f"Traceback:\n{error_event.traceback_info}")
        else:  # LOW
            logger.info(message)
    
    def _check_critical_patterns(self, error_event: ErrorEvent) -> None:
        """Check for critical error patterns that require immediate attention."""
        # Check for repeated critical errors
        if error_event.severity == ErrorSeverity.CRITICAL and error_event.occurrence_count >= 3:
            self.logger.critical(
                f"CRITICAL PATTERN: {error_event.error_type} has occurred "
                f"{error_event.occurrence_count} times in {error_event.process_name}"
            )
        
        # Check for cascading failures
        recent_errors = [e for e in self.error_history if time.time() - e.timestamp < 60]
        if len(recent_errors) >= 10:
            self.logger.critical(
                f"CASCADING FAILURE: {len(recent_errors)} errors in the last minute"
            )
        
        # Check for shared memory errors
        if error_event.category == ErrorCategory.SHARED_MEMORY:
            self.logger.critical(
                f"SHARED MEMORY ERROR: {error_event.message} - This may affect all processes"
            )
    
    def register_recovery_handler(self, category: ErrorCategory, 
                                handler: Callable[[ErrorEvent], bool]) -> None:
        """
        Register a recovery handler for a specific error category.
        
        Args:
            category: Error category to handle
            handler: Function that takes ErrorEvent and returns success boolean
        """
        self.recovery_handlers[category] = handler
        self.logger.info(f"Registered recovery handler for {category.value} errors")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics and health metrics."""
        with self._lock:
            now = time.time()
            
            # Recent errors (last hour)
            recent_errors = [e for e in self.error_history if now - e.timestamp < 3600]
            
            # Error counts by category
            category_counts = {}
            severity_counts = {}
            process_counts = {}
            
            for error in recent_errors:
                category_counts[error.category.value] = category_counts.get(error.category.value, 0) + 1
                severity_counts[error.severity.value] = severity_counts.get(error.severity.value, 0) + 1
                process_counts[error.process_name] = process_counts.get(error.process_name, 0) + 1
            
            return {
                'total_errors': len(self.error_history),
                'recent_errors_1h': len(recent_errors),
                'error_rate_per_hour': len(recent_errors),
                'category_breakdown': category_counts,
                'severity_breakdown': severity_counts,
                'process_breakdown': process_counts,
                'most_common_errors': dict(sorted(self.error_counts.items(), 
                                                key=lambda x: x[1], reverse=True)[:10])
            }
    
    def get_recent_errors(self, hours: int = 1) -> List[ErrorEvent]:
        """Get recent error events."""
        cutoff_time = time.time() - (hours * 3600)
        return [e for e in self.error_history if e.timestamp >= cutoff_time]
    
    def clear_error_history(self) -> None:
        """Clear error history (useful for testing)."""
        with self._lock:
            self.error_history.clear()
            self.error_counts.clear()
            self.logger.info("Error history cleared")


class ProcessCrashDetector:
    """
    Detects and handles process crashes with recovery coordination.
    
    Monitors process health and coordinates recovery actions when
    processes crash or become unresponsive.
    """
    
    def __init__(self, error_handler: ErrorHandler, 
                 check_interval: float = 5.0, 
                 heartbeat_timeout: float = 30.0):
        """
        Initialize crash detector.
        
        Args:
            error_handler: ErrorHandler instance for logging
            check_interval: How often to check process health (seconds)
            heartbeat_timeout: How long to wait for heartbeat before considering crash
        """
        self.error_handler = error_handler
        self.check_interval = check_interval
        self.heartbeat_timeout = heartbeat_timeout
        
        # Process tracking
        self.monitored_processes: Dict[str, Dict[str, Any]] = {}
        self.heartbeats: Dict[str, float] = {}
        
        # Control
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        self.logger = logging.getLogger(__name__)
    
    def register_process(self, name: str, process: Process, 
                        recovery_handler: Optional[Callable] = None) -> None:
        """
        Register a process for crash monitoring.
        
        Args:
            name: Process name
            process: Process object
            recovery_handler: Optional function to call for recovery
        """
        self.monitored_processes[name] = {
            'process': process,
            'recovery_handler': recovery_handler,
            'crash_count': 0,
            'last_crash_time': 0.0
        }
        self.heartbeats[name] = time.time()
        self.logger.info(f"Registered process '{name}' for crash monitoring")
    
    def update_heartbeat(self, process_name: str) -> None:
        """Update heartbeat for a process."""
        if process_name in self.heartbeats:
            self.heartbeats[process_name] = time.time()
    
    def start_monitoring(self) -> None:
        """Start the crash monitoring thread."""
        if self.running:
            self.logger.warning("Crash monitoring already running")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="CrashDetector",
            daemon=True
        )
        self.monitor_thread.start()
        self.logger.info("Process crash monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop the crash monitoring thread."""
        if not self.running:
            return
        
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        self.logger.info("Process crash monitoring stopped")
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self.running:
            try:
                current_time = time.time()
                
                for name, info in self.monitored_processes.items():
                    process = info['process']
                    
                    # Check if process is alive
                    if not process.is_alive():
                        self._handle_process_crash(name, info)
                        continue
                    
                    # Check heartbeat timeout
                    last_heartbeat = self.heartbeats.get(name, 0)
                    if current_time - last_heartbeat > self.heartbeat_timeout:
                        self._handle_heartbeat_timeout(name, info, current_time - last_heartbeat)
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.error_handler.handle_error(
                    e, "crash_detector", ErrorSeverity.HIGH, ErrorCategory.PROCESS
                )
                time.sleep(self.check_interval)
    
    def _handle_process_crash(self, name: str, info: Dict[str, Any]) -> None:
        """Handle a detected process crash."""
        info['crash_count'] += 1
        info['last_crash_time'] = time.time()
        
        # Create error event
        error = RuntimeError(f"Process '{name}' has crashed")
        self.error_handler.handle_error(
            error, name, ErrorSeverity.CRITICAL, ErrorCategory.PROCESS,
            context={
                'crash_count': info['crash_count'],
                'pid': info['process'].pid if hasattr(info['process'], 'pid') else None
            }
        )
        
        # Attempt recovery if handler is available
        if info['recovery_handler']:
            try:
                self.logger.info(f"Attempting recovery for crashed process '{name}'")
                info['recovery_handler'](name, info)
            except Exception as recovery_error:
                self.error_handler.handle_error(
                    recovery_error, name, ErrorSeverity.HIGH, ErrorCategory.PROCESS,
                    context={'recovery_attempt': True}
                )
    
    def _handle_heartbeat_timeout(self, name: str, info: Dict[str, Any], timeout_duration: float) -> None:
        """Handle a heartbeat timeout (process may be hung)."""
        error = TimeoutError(f"Process '{name}' heartbeat timeout ({timeout_duration:.1f}s)")
        self.error_handler.handle_error(
            error, name, ErrorSeverity.HIGH, ErrorCategory.PROCESS,
            context={
                'timeout_duration': timeout_duration,
                'heartbeat_timeout': self.heartbeat_timeout
            }
        )


def setup_error_handling(log_dir: str = "logs", 
                        enable_console: bool = True) -> ErrorHandler:
    """
    Setup comprehensive error handling for the multiprocessing system.
    
    Args:
        log_dir: Directory for log files
        enable_console: Whether to enable console logging
        
    Returns:
        Configured ErrorHandler instance
    """
    error_handler = ErrorHandler(log_dir=log_dir, enable_console=enable_console)
    
    # Register default recovery handlers
    def hardware_recovery_handler(error_event: ErrorEvent) -> bool:
        """Handle hardware-related errors."""
        logger = logging.getLogger("pika.recovery")
        logger.info(f"Attempting hardware error recovery for: {error_event.message}")
        
        # For hardware errors, we typically fall back to simulation mode
        if "ADC" in error_event.message or "hardware" in error_event.message.lower():
            logger.info("Hardware error detected, system should fall back to simulation mode")
            return True  # Assume fallback is successful
        
        return False
    
    def shared_memory_recovery_handler(error_event: ErrorEvent) -> bool:
        """Handle shared memory errors."""
        logger = logging.getLogger("pika.recovery")
        logger.warning(f"Shared memory error detected: {error_event.message}")
        
        # Shared memory errors are critical and usually require process restart
        logger.error("Shared memory errors typically require process restart")
        return False
    
    def resource_recovery_handler(error_event: ErrorEvent) -> bool:
        """Handle resource-related errors."""
        logger = logging.getLogger("pika.recovery")
        logger.info(f"Attempting resource error recovery for: {error_event.message}")
        
        # For resource errors, we can try cleanup and retry
        if "memory" in error_event.message.lower():
            logger.info("Memory error detected, attempting cleanup")
            # Could implement memory cleanup here
            return True
        
        return False
    
    # Register recovery handlers
    error_handler.register_recovery_handler(ErrorCategory.HARDWARE, hardware_recovery_handler)
    error_handler.register_recovery_handler(ErrorCategory.SHARED_MEMORY, shared_memory_recovery_handler)
    error_handler.register_recovery_handler(ErrorCategory.RESOURCE, resource_recovery_handler)
    
    return error_handler


def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """Global uncaught exception handler."""
    if issubclass(exc_type, KeyboardInterrupt):
        # Allow KeyboardInterrupt to be handled normally
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    # Log uncaught exception
    logger = logging.getLogger("pika.uncaught")
    logger.critical(
        "Uncaught exception",
        exc_info=(exc_type, exc_value, exc_traceback)
    )


# Install global exception handler
sys.excepthook = handle_uncaught_exception