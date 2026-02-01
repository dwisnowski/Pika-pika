"""Process supervisor and management system for multiprocessing architecture.

This module provides process lifecycle management, health monitoring, and graceful
shutdown coordination for the datalogger multiprocessing system with comprehensive
error handling and crash detection.
"""

import os
import signal
import time
import logging
import psutil
from multiprocessing import Process, Event, Value
from typing import Dict, Optional, Callable, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from .error_handling import ErrorHandler, ProcessCrashDetector, ErrorSeverity, ErrorCategory
from .performance_optimizer import PerformanceOptimizer, ProcessPriority, CPUCore

logger = logging.getLogger(__name__)


class ProcessState(Enum):
    """Process state enumeration."""
    NOT_STARTED = "not_started"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    RESTARTING = "restarting"


@dataclass
class ProcessInfo:
    """Information about a managed process."""
    name: str
    process: Optional[Process]
    target: Callable
    args: Tuple
    kwargs: Dict[str, Any]
    state: ProcessState
    start_time: Optional[float]
    restart_count: int
    last_heartbeat: float
    cpu_affinity: Optional[int]
    max_restarts: int
    restart_delay: float


class ProcessSupervisor:
    """
    Process supervisor for managing multiprocessing architecture.
    
    Provides process lifecycle management (start, stop, restart), health monitoring
    with heartbeat checks, graceful shutdown coordination, and CPU core affinity
    assignment for optimal performance on the Raspberry Pi 2's quad-core CPU.
    """
    
    def __init__(self, heartbeat_interval: float = 5.0, restart_delay: float = 2.0,
                 error_handler: Optional[ErrorHandler] = None,
                 performance_optimizer: Optional[PerformanceOptimizer] = None):
        """
        Initialize process supervisor.
        
        Args:
            heartbeat_interval: Interval in seconds between heartbeat checks
            restart_delay: Delay in seconds before restarting failed processes
            error_handler: ErrorHandler instance for comprehensive error handling
            performance_optimizer: PerformanceOptimizer for resource management
        """
        self.processes: Dict[str, ProcessInfo] = {}
        self.shutdown_event = Event()
        self.heartbeat_interval = heartbeat_interval
        self.restart_delay = restart_delay
        self.supervisor_running = Value('i', 0)  # 0 = stopped, 1 = running
        self.shared_memory_resources = []  # Track shared memory resources for cleanup
        self._shutdown_in_progress = False
        
        # Error handling integration
        self.error_handler = error_handler
        self.crash_detector: Optional[ProcessCrashDetector] = None
        
        if self.error_handler:
            self.crash_detector = ProcessCrashDetector(
                error_handler=self.error_handler,
                check_interval=heartbeat_interval,
                heartbeat_timeout=heartbeat_interval * 3
            )
        
        # Performance optimization integration
        self.performance_optimizer = performance_optimizer
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        logger.info("ProcessSupervisor initialized with enhanced error handling and performance optimization")
    
    def register_shared_memory(self, resource) -> None:
        """
        Register a shared memory resource for cleanup during shutdown.
        
        Args:
            resource: Shared memory resource with a cleanup() method
        """
        if hasattr(resource, 'cleanup'):
            self.shared_memory_resources.append(resource)
            logger.info(f"Registered shared memory resource: {type(resource).__name__}")
        else:
            logger.warning(f"Resource {type(resource).__name__} does not have cleanup() method")
    
    def _cleanup_shared_memory(self) -> None:
        """Clean up all registered shared memory resources."""
        logger.info("Cleaning up shared memory resources")
        
        for resource in self.shared_memory_resources:
            try:
                resource.cleanup()
                logger.info(f"Cleaned up {type(resource).__name__}")
            except Exception as e:
                logger.error(f"Failed to cleanup {type(resource).__name__}: {e}")
        
        self.shared_memory_resources.clear()
        logger.info("Shared memory cleanup completed")
    
    def register_process(self, name: str, target: Callable, args: Tuple = (), 
                        kwargs: Optional[Dict[str, Any]] = None, cpu_affinity: Optional[int] = None,
                        max_restarts: int = 3, restart_delay: Optional[float] = None) -> None:
        """
        Register a process for supervision.
        
        Args:
            name: Unique process name
            target: Target function to run in the process
            args: Arguments to pass to target function
            kwargs: Keyword arguments to pass to target function
            cpu_affinity: CPU core to bind process to (0-3 for Raspberry Pi 2)
            max_restarts: Maximum number of restart attempts
            restart_delay: Delay before restart (uses supervisor default if None)
        """
        if kwargs is None:
            kwargs = {}
        
        if name in self.processes:
            raise ValueError(f"Process '{name}' is already registered")
        
        process_info = ProcessInfo(
            name=name,
            process=None,
            target=target,
            args=args,
            kwargs=kwargs,
            state=ProcessState.NOT_STARTED,
            start_time=None,
            restart_count=0,
            last_heartbeat=0.0,
            cpu_affinity=cpu_affinity,
            max_restarts=max_restarts,
            restart_delay=restart_delay or self.restart_delay
        )
        
        self.processes[name] = process_info
        logger.info(f"Registered process '{name}' with target {target.__name__}")
    
    def start_process(self, name: str) -> bool:
        """
        Start a registered process with enhanced error handling.
        
        Args:
            name: Name of process to start
            
        Returns:
            True if process started successfully, False otherwise
        """
        if name not in self.processes:
            error_msg = f"Process '{name}' not registered"
            logger.error(error_msg)
            if self.error_handler:
                self.error_handler.handle_error(
                    ValueError(error_msg), "supervisor", 
                    ErrorSeverity.MEDIUM, ErrorCategory.PROCESS
                )
            return False
        
        process_info = self.processes[name]
        
        if process_info.state in [ProcessState.RUNNING, ProcessState.STARTING]:
            logger.warning(f"Process '{name}' is already running or starting")
            return True
        
        try:
            logger.info(f"Starting process '{name}'")
            process_info.state = ProcessState.STARTING
            
            # Create new process
            process = Process(
                target=process_info.target,
                args=process_info.args,
                kwargs=process_info.kwargs,
                name=name
            )
            
            # Start the process
            process.start()
            
            # Set CPU affinity if specified
            if process_info.cpu_affinity is not None:
                try:
                    proc = psutil.Process(process.pid)
                    # Check if CPU affinity is supported on this platform
                    if hasattr(proc, 'cpu_affinity') and callable(getattr(proc, 'cpu_affinity', None)):
                        proc.cpu_affinity([process_info.cpu_affinity])
                        logger.info(f"Set CPU affinity for '{name}' to core {process_info.cpu_affinity}")
                    else:
                        logger.warning(f"CPU affinity not supported on this platform for '{name}'")
                except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError, OSError) as e:
                    logger.warning(f"Failed to set CPU affinity for '{name}': {e}")
                    if self.error_handler:
                        self.error_handler.handle_error(
                            e, name, ErrorSeverity.LOW, ErrorCategory.RESOURCE,
                            context={'cpu_affinity': process_info.cpu_affinity}
                        )
            
            # Update process info
            process_info.process = process
            process_info.state = ProcessState.RUNNING
            process_info.start_time = time.time()
            process_info.last_heartbeat = time.time()
            
            # Register with crash detector
            if self.crash_detector:
                self.crash_detector.register_process(
                    name, process, 
                    recovery_handler=lambda n, i: self.restart_process(n)
                )
            
            # Register with performance optimizer
            if self.performance_optimizer:
                # Determine priority and CPU core based on process name
                priority_map = {
                    'datalogger': ProcessPriority.REALTIME,
                    'event_logger': ProcessPriority.HIGH,
                    'fastapi': ProcessPriority.NORMAL,
                    'websocket': ProcessPriority.NORMAL
                }
                
                cpu_core_map = {
                    'datalogger': CPUCore.CORE_0,
                    'event_logger': CPUCore.CORE_1,
                    'fastapi': CPUCore.CORE_2,
                    'websocket': CPUCore.CORE_3
                }
                
                priority = priority_map.get(name, ProcessPriority.NORMAL)
                cpu_core = cpu_core_map.get(name)
                
                self.performance_optimizer.register_process(
                    name, process, priority=priority, cpu_core=cpu_core
                )
                
                # Apply optimizations immediately
                self.performance_optimizer.optimize_process(name)
            
            logger.info(f"Process '{name}' started successfully (PID: {process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start process '{name}': {e}")
            process_info.state = ProcessState.FAILED
            
            if self.error_handler:
                self.error_handler.handle_error(
                    e, name, ErrorSeverity.HIGH, ErrorCategory.PROCESS,
                    context={'action': 'start_process'}
                )
            
            return False
    
    def stop_process(self, name: str, timeout: float = 10.0) -> bool:
        """
        Stop a running process gracefully.
        
        Args:
            name: Name of process to stop
            timeout: Maximum time to wait for graceful shutdown
            
        Returns:
            True if process stopped successfully, False otherwise
        """
        if name not in self.processes:
            logger.error(f"Process '{name}' not registered")
            return False
        
        process_info = self.processes[name]
        
        if process_info.state not in [ProcessState.RUNNING, ProcessState.STARTING]:
            logger.info(f"Process '{name}' is not running")
            return True
        
        if process_info.process is None:
            logger.warning(f"Process '{name}' has no process object")
            process_info.state = ProcessState.STOPPED
            return True
        
        try:
            logger.info(f"Stopping process '{name}' (PID: {process_info.process.pid})")
            process_info.state = ProcessState.STOPPING
            
            # Try graceful shutdown first
            if process_info.process.is_alive():
                process_info.process.terminate()
                
                # Wait for graceful shutdown
                process_info.process.join(timeout=timeout)
                
                # Force kill if still alive
                if process_info.process.is_alive():
                    logger.warning(f"Process '{name}' did not terminate gracefully, killing")
                    process_info.process.kill()
                    process_info.process.join(timeout=2.0)
            
            process_info.state = ProcessState.STOPPED
            process_info.process = None
            process_info.start_time = None
            
            logger.info(f"Process '{name}' stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop process '{name}': {e}")
            process_info.state = ProcessState.FAILED
            return False
    
    def restart_process(self, name: str) -> bool:
        """
        Restart a process.
        
        Args:
            name: Name of process to restart
            
        Returns:
            True if process restarted successfully, False otherwise
        """
        if name not in self.processes:
            logger.error(f"Process '{name}' not registered")
            return False
        
        process_info = self.processes[name]
        
        if process_info.restart_count >= process_info.max_restarts:
            logger.error(f"Process '{name}' has exceeded maximum restart attempts ({process_info.max_restarts})")
            process_info.state = ProcessState.FAILED
            return False
        
        logger.info(f"Restarting process '{name}' (attempt {process_info.restart_count + 1})")
        process_info.state = ProcessState.RESTARTING
        process_info.restart_count += 1
        
        # Stop the process if it's running
        self.stop_process(name)
        
        # Wait before restarting
        time.sleep(process_info.restart_delay)
        
        # Start the process
        return self.start_process(name)
    
    def start_all(self) -> bool:
        """
        Start all registered processes in dependency order.
        
        Returns:
            True if all processes started successfully, False otherwise
        """
        logger.info("Starting all registered processes")
        
        # Define startup order based on dependencies
        # Datalogger -> Event Logger -> FastAPI -> WebSocket
        startup_order = [
            'datalogger',
            'event_logger', 
            'fastapi',
            'websocket'
        ]
        
        success = True
        
        for process_name in startup_order:
            if process_name in self.processes:
                if not self.start_process(process_name):
                    logger.error(f"Failed to start {process_name}, aborting startup")
                    success = False
                    break
                
                # Small delay between process starts
                time.sleep(0.5)
        
        # Start any remaining processes not in the startup order
        for process_name in self.processes:
            if process_name not in startup_order:
                if not self.start_process(process_name):
                    logger.warning(f"Failed to start additional process {process_name}")
                    success = False
        
        if success:
            logger.info("All processes started successfully")
        else:
            logger.error("Some processes failed to start")
        
        return success
    
    def stop_all(self, timeout: float = 10.0) -> bool:
        """
        Stop all processes in reverse dependency order.
        
        Args:
            timeout: Maximum time to wait for each process to stop
            
        Returns:
            True if all processes stopped successfully, False otherwise
        """
        logger.info("Stopping all processes")
        
        # Define shutdown order (reverse of startup)
        shutdown_order = [
            'websocket',
            'fastapi',
            'event_logger',
            'datalogger'
        ]
        
        success = True
        
        # Stop processes in shutdown order
        for process_name in shutdown_order:
            if process_name in self.processes:
                if not self.stop_process(process_name, timeout):
                    logger.error(f"Failed to stop {process_name}")
                    success = False
        
        # Stop any remaining processes
        for process_name in self.processes:
            if process_name not in shutdown_order:
                if not self.stop_process(process_name, timeout):
                    logger.warning(f"Failed to stop additional process {process_name}")
                    success = False
        
        if success:
            logger.info("All processes stopped successfully")
        else:
            logger.error("Some processes failed to stop cleanly")
        
        return success
    
    def monitor_health(self) -> None:
        """
        Monitor process health and restart failed processes with enhanced error handling.
        
        This method runs continuously and should be called in a separate thread
        or as part of the main supervision loop.
        """
        logger.info("Starting enhanced health monitoring")
        self.supervisor_running.value = 1
        
        # Start crash detector if available
        if self.crash_detector:
            self.crash_detector.start_monitoring()
        
        # Start performance monitoring if available
        if self.performance_optimizer:
            self.performance_optimizer.start_monitoring()
        
        try:
            while not self.shutdown_event.is_set():
                current_time = time.time()
                
                for name, process_info in self.processes.items():
                    try:
                        if process_info.state == ProcessState.RUNNING:
                            if process_info.process is None:
                                error_msg = f"Process '{name}' is marked as running but has no process object"
                                logger.error(error_msg)
                                process_info.state = ProcessState.FAILED
                                
                                if self.error_handler:
                                    self.error_handler.handle_error(
                                        RuntimeError(error_msg), name,
                                        ErrorSeverity.HIGH, ErrorCategory.PROCESS
                                    )
                                continue
                            
                            # Check if process is still alive
                            if not process_info.process.is_alive():
                                error_msg = f"Process '{name}' has died unexpectedly"
                                logger.error(error_msg)
                                process_info.state = ProcessState.FAILED
                                
                                if self.error_handler:
                                    self.error_handler.handle_error(
                                        RuntimeError(error_msg), name,
                                        ErrorSeverity.CRITICAL, ErrorCategory.PROCESS,
                                        context={
                                            'pid': process_info.process.pid,
                                            'exit_code': process_info.process.exitcode
                                        }
                                    )
                                
                                # Attempt restart if within limits
                                if process_info.restart_count < process_info.max_restarts:
                                    logger.info(f"Attempting to restart failed process '{name}'")
                                    self.restart_process(name)
                                else:
                                    logger.error(f"Process '{name}' has exceeded restart limit, marking as failed")
                            
                            # Check heartbeat (if implemented by processes)
                            heartbeat_age = current_time - process_info.last_heartbeat
                            if heartbeat_age > self.heartbeat_interval * 3:  # 3x interval = timeout
                                logger.warning(f"Process '{name}' heartbeat timeout ({heartbeat_age:.1f}s)")
                                
                                if self.error_handler:
                                    self.error_handler.handle_error(
                                        TimeoutError(f"Heartbeat timeout for process '{name}'"),
                                        name, ErrorSeverity.MEDIUM, ErrorCategory.PROCESS,
                                        context={'heartbeat_age': heartbeat_age}
                                    )
                                
                                # Update crash detector heartbeat
                                if self.crash_detector:
                                    self.crash_detector.update_heartbeat(name)
                    
                    except Exception as e:
                        logger.error(f"Error monitoring process '{name}': {e}")
                        if self.error_handler:
                            self.error_handler.handle_error(
                                e, "supervisor", ErrorSeverity.MEDIUM, ErrorCategory.PROCESS,
                                context={'monitored_process': name}
                            )
                
                # Sleep before next health check
                time.sleep(self.heartbeat_interval)
                
        except Exception as e:
            logger.error(f"Health monitoring error: {e}")
            if self.error_handler:
                self.error_handler.handle_error(
                    e, "supervisor", ErrorSeverity.HIGH, ErrorCategory.PROCESS
                )
        finally:
            # Stop crash detector
            if self.crash_detector:
                self.crash_detector.stop_monitoring()
            
            # Stop performance monitoring
            if self.performance_optimizer:
                self.performance_optimizer.stop_monitoring()
            
            self.supervisor_running.value = 0
            logger.info("Enhanced health monitoring stopped")
    
    def get_process_status(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get status information for a process.
        
        Args:
            name: Name of process
            
        Returns:
            Dictionary with process status information, or None if not found
        """
        if name not in self.processes:
            return None
        
        process_info = self.processes[name]
        
        status = {
            'name': process_info.name,
            'state': process_info.state.value,
            'restart_count': process_info.restart_count,
            'max_restarts': process_info.max_restarts,
            'cpu_affinity': process_info.cpu_affinity,
            'start_time': process_info.start_time,
            'uptime': time.time() - process_info.start_time if process_info.start_time else None,
            'pid': process_info.process.pid if process_info.process else None,
            'is_alive': process_info.process.is_alive() if process_info.process else False
        }
        
        # Add resource usage if process is running
        if process_info.process and process_info.process.is_alive():
            try:
                proc = psutil.Process(process_info.process.pid)
                status.update({
                    'cpu_percent': proc.cpu_percent(),
                    'memory_mb': proc.memory_info().rss / 1024 / 1024,
                    'memory_percent': proc.memory_percent()
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return status
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status information for all processes.
        
        Returns:
            Dictionary mapping process names to their status information
        """
        return {name: self.get_process_status(name) for name in self.processes}
    
    def graceful_shutdown(self, timeout: float = 30.0) -> None:
        """
        Coordinate graceful shutdown sequence.
        
        Args:
            timeout: Maximum time to wait for all processes to stop
        """
        if self._shutdown_in_progress:
            logger.warning("Shutdown already in progress, ignoring duplicate request")
            return
        
        self._shutdown_in_progress = True
        logger.info("Initiating graceful shutdown")
        
        try:
            # Signal shutdown to all processes
            self.shutdown_event.set()
            
            # Stop health monitoring
            if self.supervisor_running.value:
                logger.info("Stopping health monitoring")
                # Health monitoring will stop on next iteration
            
            # Stop all processes
            self.stop_all(timeout=timeout / len(self.processes) if self.processes else timeout)
            
            # Clean up shared memory resources
            self._cleanup_shared_memory()
            
            logger.info("Graceful shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
        finally:
            self._shutdown_in_progress = False
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        if self._shutdown_in_progress:
            logger.warning("Shutdown already in progress, ignoring signal")
            return
            
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name}, initiating graceful shutdown")
        self.graceful_shutdown()
    
    def update_heartbeat(self, process_name: str) -> None:
        """
        Update heartbeat timestamp for a process.
        
        This method can be called by processes to indicate they are alive.
        
        Args:
            process_name: Name of the process updating its heartbeat
        """
        if process_name in self.processes:
            self.processes[process_name].last_heartbeat = time.time()
    
    def is_running(self) -> bool:
        """
        Check if the supervisor is running.
        
        Returns:
            True if supervisor is actively monitoring processes
        """
        return bool(self.supervisor_running.value)
    
    def cleanup(self) -> None:
        """Clean up supervisor resources."""
        logger.info("Cleaning up ProcessSupervisor")
        
        # Ensure all processes are stopped
        if any(info.state == ProcessState.RUNNING for info in self.processes.values()):
            self.graceful_shutdown()
        
        # Clean up shared memory resources
        self._cleanup_shared_memory()
        
        # Clear process registry
        self.processes.clear()
        
        logger.info("ProcessSupervisor cleanup completed")