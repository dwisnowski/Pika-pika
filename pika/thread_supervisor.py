"""
Thread-based supervisor for single-processor execution.

This module provides a threading-based alternative to the multiprocessing
supervisor, allowing all components to run in threads within a single process.
This is useful for single-core systems or when shared memory overhead is a concern.
"""

import time
import logging
import threading
import queue
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import psutil
import os

from .error_handling import ErrorHandler, ErrorSeverity, ErrorCategory

logger = logging.getLogger(__name__)


@dataclass
class ThreadInfo:
    """Information about a managed thread."""
    name: str
    target: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    thread: Optional[threading.Thread] = None
    start_time: Optional[float] = None
    restart_count: int = 0
    max_restarts: int = 3
    last_heartbeat: Optional[float] = None
    state: str = "stopped"  # stopped, starting, running, failed, stopping
    exception: Optional[Exception] = None


class ThreadSupervisor:
    """
    Thread-based supervisor for managing application components in a single process.
    
    This supervisor manages threads instead of processes, providing similar
    functionality to ProcessSupervisor but with lower overhead and shared memory.
    """
    
    def __init__(self, 
                 heartbeat_interval: float = 2.0,
                 restart_delay: float = 1.0,
                 error_handler: Optional[ErrorHandler] = None):
        """
        Initialize thread supervisor.
        
        Args:
            heartbeat_interval: Interval between health checks in seconds
            restart_delay: Delay before restarting failed threads in seconds
            error_handler: Optional error handler for logging errors
        """
        self.heartbeat_interval = heartbeat_interval
        self.restart_delay = restart_delay
        self.error_handler = error_handler
        
        # Thread management
        self.threads: Dict[str, ThreadInfo] = {}
        self.running = False
        self.shutdown_event = threading.Event()
        
        # Communication queues for thread coordination
        self.command_queue = queue.Queue()
        self.heartbeat_queue = queue.Queue()
        
        # Monitoring thread
        self.monitor_thread: Optional[threading.Thread] = None
        
        # Shared resources (for cleanup)
        self.shared_resources: List[Any] = []
        
        logger.info("ThreadSupervisor initialized")
    
    def register_thread(self, 
                       name: str, 
                       target: Callable,
                       args: tuple = (),
                       kwargs: dict = None,
                       max_restarts: int = 3) -> None:
        """
        Register a thread for supervision.
        
        Args:
            name: Unique name for the thread
            target: Function to run in the thread
            args: Arguments to pass to the target function
            kwargs: Keyword arguments to pass to the target function
            max_restarts: Maximum number of restart attempts
        """
        if kwargs is None:
            kwargs = {}
        
        if name in self.threads:
            logger.warning(f"Thread {name} already registered, updating configuration")
        
        self.threads[name] = ThreadInfo(
            name=name,
            target=target,
            args=args,
            kwargs=kwargs,
            max_restarts=max_restarts
        )
        
        logger.info(f"Registered thread: {name}")
    
    def start_thread(self, name: str) -> bool:
        """
        Start a specific thread.
        
        Args:
            name: Name of the thread to start
            
        Returns:
            True if thread started successfully, False otherwise
        """
        if name not in self.threads:
            logger.error(f"Thread {name} not registered")
            return False
        
        thread_info = self.threads[name]
        
        if thread_info.thread and thread_info.thread.is_alive():
            logger.warning(f"Thread {name} is already running")
            return True
        
        try:
            logger.info(f"Starting thread: {name}")
            thread_info.state = "starting"
            
            # Create wrapper function that handles exceptions
            def thread_wrapper():
                try:
                    thread_info.state = "running"
                    thread_info.start_time = time.time()
                    thread_info.last_heartbeat = time.time()
                    
                    # Run the target function
                    thread_info.target(*thread_info.args, **thread_info.kwargs)
                    
                except Exception as e:
                    thread_info.exception = e
                    thread_info.state = "failed"
                    logger.error(f"Thread {name} failed: {e}")
                    
                    if self.error_handler:
                        self.error_handler.handle_error(
                            e, f"thread_{name}", ErrorSeverity.HIGH, ErrorCategory.THREAD
                        )
                finally:
                    if thread_info.state == "running":
                        thread_info.state = "stopped"
            
            # Create and start the thread
            thread_info.thread = threading.Thread(
                target=thread_wrapper,
                name=f"pika_{name}",
                daemon=False
            )
            thread_info.thread.start()
            
            # Wait a moment to see if it starts successfully
            time.sleep(0.1)
            
            if thread_info.thread.is_alive():
                logger.info(f"Thread {name} started successfully")
                return True
            else:
                logger.error(f"Thread {name} failed to start")
                thread_info.state = "failed"
                return False
                
        except Exception as e:
            logger.error(f"Failed to start thread {name}: {e}")
            thread_info.state = "failed"
            thread_info.exception = e
            
            if self.error_handler:
                self.error_handler.handle_error(
                    e, f"thread_supervisor", ErrorSeverity.HIGH, ErrorCategory.THREAD
                )
            
            return False
    
    def stop_thread(self, name: str, timeout: float = 10.0) -> bool:
        """
        Stop a specific thread.
        
        Args:
            name: Name of the thread to stop
            timeout: Maximum time to wait for graceful shutdown
            
        Returns:
            True if thread stopped successfully, False otherwise
        """
        if name not in self.threads:
            logger.error(f"Thread {name} not registered")
            return False
        
        thread_info = self.threads[name]
        
        if not thread_info.thread or not thread_info.thread.is_alive():
            logger.info(f"Thread {name} is not running")
            thread_info.state = "stopped"
            return True
        
        try:
            logger.info(f"Stopping thread: {name}")
            thread_info.state = "stopping"
            
            # For threads, we rely on the shutdown_event and cooperative shutdown
            # Most thread functions should check self.shutdown_event.is_set()
            
            # Wait for thread to finish
            thread_info.thread.join(timeout=timeout)
            
            if thread_info.thread.is_alive():
                logger.warning(f"Thread {name} did not stop gracefully within {timeout}s")
                # Note: Python threads cannot be forcefully killed
                # The thread will continue running until it checks shutdown_event
                return False
            else:
                logger.info(f"Thread {name} stopped successfully")
                thread_info.state = "stopped"
                return True
                
        except Exception as e:
            logger.error(f"Error stopping thread {name}: {e}")
            if self.error_handler:
                self.error_handler.handle_error(
                    e, f"thread_supervisor", ErrorSeverity.MEDIUM, ErrorCategory.THREAD
                )
            return False
    
    def start_all(self) -> bool:
        """
        Start all registered threads.
        
        Returns:
            True if all threads started successfully, False otherwise
        """
        logger.info("Starting all threads")
        success = True
        
        for name in self.threads:
            if not self.start_thread(name):
                success = False
        
        if success:
            logger.info("All threads started successfully")
        else:
            logger.error("Some threads failed to start")
        
        return success
    
    def stop_all(self, timeout: float = 15.0) -> bool:
        """
        Stop all threads.
        
        Args:
            timeout: Maximum time to wait for all threads to stop
            
        Returns:
            True if all threads stopped successfully, False otherwise
        """
        logger.info("Stopping all threads")
        
        # Signal shutdown to all threads
        self.shutdown_event.set()
        
        success = True
        for name in self.threads:
            if not self.stop_thread(name, timeout / len(self.threads)):
                success = False
        
        if success:
            logger.info("All threads stopped successfully")
        else:
            logger.warning("Some threads did not stop gracefully")
        
        return success
    
    def restart_thread(self, name: str) -> bool:
        """
        Restart a specific thread.
        
        Args:
            name: Name of the thread to restart
            
        Returns:
            True if thread restarted successfully, False otherwise
        """
        if name not in self.threads:
            logger.error(f"Thread {name} not registered")
            return False
        
        thread_info = self.threads[name]
        
        # Check restart limits
        if thread_info.restart_count >= thread_info.max_restarts:
            logger.error(f"Thread {name} has reached maximum restart limit ({thread_info.max_restarts})")
            return False
        
        logger.info(f"Restarting thread: {name} (attempt {thread_info.restart_count + 1})")
        
        # Stop the thread first
        self.stop_thread(name, timeout=5.0)
        
        # Wait before restarting
        time.sleep(self.restart_delay)
        
        # Increment restart count
        thread_info.restart_count += 1
        thread_info.exception = None
        
        # Start the thread
        return self.start_thread(name)
    
    def monitor_health(self) -> None:
        """
        Monitor thread health and restart failed threads.
        This runs in a separate monitoring thread.
        """
        logger.info("Starting thread health monitoring")
        
        while self.running and not self.shutdown_event.is_set():
            try:
                for name, thread_info in self.threads.items():
                    # Check if thread is alive
                    if thread_info.thread and not thread_info.thread.is_alive():
                        if thread_info.state == "running":
                            logger.warning(f"Thread {name} died unexpectedly")
                            thread_info.state = "failed"
                            
                            # Attempt restart if within limits
                            if thread_info.restart_count < thread_info.max_restarts:
                                logger.info(f"Attempting to restart thread {name}")
                                self.restart_thread(name)
                            else:
                                logger.error(f"Thread {name} has failed permanently")
                    
                    # Update heartbeat (for threads that are cooperative)
                    if thread_info.state == "running":
                        thread_info.last_heartbeat = time.time()
                
                # Sleep before next check
                time.sleep(self.heartbeat_interval)
                
            except Exception as e:
                logger.error(f"Error in health monitoring: {e}")
                if self.error_handler:
                    self.error_handler.handle_error(
                        e, "thread_supervisor", ErrorSeverity.MEDIUM, ErrorCategory.THREAD
                    )
                time.sleep(self.heartbeat_interval)
        
        logger.info("Thread health monitoring stopped")
    
    def get_thread_status(self, name: str) -> Dict[str, Any]:
        """
        Get status information for a specific thread.
        
        Args:
            name: Name of the thread
            
        Returns:
            Dictionary containing thread status information
        """
        if name not in self.threads:
            return {"error": f"Thread {name} not registered"}
        
        thread_info = self.threads[name]
        
        status = {
            "name": name,
            "state": thread_info.state,
            "is_alive": thread_info.thread.is_alive() if thread_info.thread else False,
            "restart_count": thread_info.restart_count,
            "max_restarts": thread_info.max_restarts,
            "start_time": thread_info.start_time,
            "uptime": time.time() - thread_info.start_time if thread_info.start_time else 0,
            "last_heartbeat": thread_info.last_heartbeat,
            "exception": str(thread_info.exception) if thread_info.exception else None
        }
        
        return status
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status information for all threads.
        
        Returns:
            Dictionary mapping thread names to their status information
        """
        return {name: self.get_thread_status(name) for name in self.threads}
    
    def is_running(self) -> bool:
        """Check if the supervisor is running."""
        return self.running
    
    def start_monitoring(self) -> None:
        """Start the health monitoring system."""
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.warning("Health monitoring is already running")
            return
        
        self.running = True
        self.shutdown_event.clear()
        
        self.monitor_thread = threading.Thread(
            target=self.monitor_health,
            name="ThreadHealthMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        
        logger.info("Thread health monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop the health monitoring system."""
        self.running = False
        self.shutdown_event.set()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        
        logger.info("Thread health monitoring stopped")
    
    def graceful_shutdown(self, timeout: float = 15.0) -> None:
        """
        Perform graceful shutdown of all threads and cleanup resources.
        
        Args:
            timeout: Maximum time to wait for shutdown
        """
        logger.info("Starting graceful shutdown of thread supervisor")
        
        try:
            # Stop health monitoring
            self.stop_monitoring()
            
            # Stop all threads
            self.stop_all(timeout=timeout)
            
            # Cleanup shared resources
            self.cleanup_shared_resources()
            
            logger.info("Thread supervisor shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
            if self.error_handler:
                self.error_handler.handle_error(
                    e, "thread_supervisor", ErrorSeverity.HIGH, ErrorCategory.THREAD
                )
    
    def register_shared_resource(self, resource: Any) -> None:
        """
        Register a shared resource for cleanup during shutdown.
        
        Args:
            resource: Resource object that has a cleanup() method
        """
        self.shared_resources.append(resource)
        logger.debug(f"Registered shared resource: {type(resource).__name__}")
    
    def cleanup_shared_resources(self) -> None:
        """Clean up all registered shared resources."""
        logger.info("Cleaning up shared resources")
        
        for resource in self.shared_resources:
            try:
                if hasattr(resource, 'cleanup'):
                    resource.cleanup()
                    logger.debug(f"Cleaned up resource: {type(resource).__name__}")
            except Exception as e:
                logger.error(f"Error cleaning up resource {type(resource).__name__}: {e}")
        
        self.shared_resources.clear()
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information for monitoring."""
        try:
            process = psutil.Process()
            
            return {
                "pid": os.getpid(),
                "cpu_percent": process.cpu_percent(),
                "memory_mb": process.memory_info().rss / 1024 / 1024,
                "thread_count": process.num_threads(),
                "open_files": len(process.open_files()),
                "connections": len(process.connections()),
                "create_time": process.create_time()
            }
        except Exception as e:
            logger.debug(f"Error getting system info: {e}")
            return {"error": str(e)}