"""
Performance optimization and resource management for multiprocessing datalogger.

This module provides performance optimization features including process priorities,
CPU core affinity management, memory usage monitoring, and resource optimization
for the Raspberry Pi 2's quad-core architecture.
"""

import os
import time
import logging
import psutil
import threading
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
from multiprocessing import Process

logger = logging.getLogger(__name__)


class ProcessPriority(Enum):
    """Process priority levels for scheduling optimization."""
    REALTIME = "realtime"      # Highest priority (datalogger)
    HIGH = "high"              # High priority (event logger)
    NORMAL = "normal"          # Normal priority (FastAPI)
    LOW = "low"                # Low priority (background tasks)


class CPUCore(Enum):
    """CPU core assignments for Raspberry Pi 2 quad-core optimization."""
    CORE_0 = 0  # Datalogger (real-time sampling)
    CORE_1 = 1  # Event Logger (analysis)
    CORE_2 = 2  # FastAPI (web server)
    CORE_3 = 3  # WebSocket/Background tasks


@dataclass
class ResourceLimits:
    """Resource limits for process monitoring."""
    max_memory_mb: float = 100.0      # Maximum memory usage in MB
    max_cpu_percent: float = 80.0     # Maximum CPU usage percentage
    max_open_files: int = 100         # Maximum open file descriptors
    memory_warning_threshold: float = 0.8  # Warning at 80% of max memory


@dataclass
class PerformanceMetrics:
    """Performance metrics for a process."""
    process_name: str
    pid: int
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    cpu_affinity: List[int]
    priority: int
    open_files: int
    threads: int
    uptime: float
    io_read_bytes: int
    io_write_bytes: int
    timestamp: float


class PerformanceOptimizer:
    """
    Performance optimizer for the multiprocessing datalogger system.
    
    Manages process priorities, CPU core affinity, memory usage monitoring,
    and resource optimization to ensure optimal performance on the Raspberry Pi 2.
    """
    
    def __init__(self, enable_monitoring: bool = True, 
                 monitoring_interval: float = 10.0):
        """
        Initialize performance optimizer.
        
        Args:
            enable_monitoring: Whether to enable continuous performance monitoring
            monitoring_interval: Interval between performance measurements (seconds)
        """
        self.enable_monitoring = enable_monitoring
        self.monitoring_interval = monitoring_interval
        
        # Process tracking
        self.managed_processes: Dict[str, Dict[str, Any]] = {}
        self.performance_history: List[PerformanceMetrics] = []
        self.resource_limits: Dict[str, ResourceLimits] = {}
        
        # Monitoring control
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # System information
        self.system_info = self._get_system_info()
        
        logger.info(f"PerformanceOptimizer initialized - System: {self.system_info}")
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information for optimization decisions."""
        try:
            return {
                'cpu_count': psutil.cpu_count(logical=True),
                'cpu_count_physical': psutil.cpu_count(logical=False),
                'memory_total_gb': psutil.virtual_memory().total / (1024**3),
                'platform': os.uname().sysname,
                'architecture': os.uname().machine,
                'is_raspberry_pi': self._is_raspberry_pi()
            }
        except Exception as e:
            logger.warning(f"Failed to get system info: {e}")
            return {
                'cpu_count': 4,
                'cpu_count_physical': 4,
                'memory_total_gb': 1.0,
                'platform': 'Unknown',
                'architecture': 'Unknown',
                'is_raspberry_pi': False
            }
    
    def _is_raspberry_pi(self) -> bool:
        """Detect if running on Raspberry Pi."""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
                return 'Raspberry Pi' in cpuinfo or 'BCM' in cpuinfo
        except:
            return False
    
    def register_process(self, name: str, process: Process, 
                        priority: ProcessPriority = ProcessPriority.NORMAL,
                        cpu_core: Optional[CPUCore] = None,
                        resource_limits: Optional[ResourceLimits] = None) -> None:
        """
        Register a process for performance optimization.
        
        Args:
            name: Process name
            process: Process object
            priority: Process priority level
            cpu_core: Preferred CPU core assignment
            resource_limits: Resource limits for the process
        """
        self.managed_processes[name] = {
            'process': process,
            'priority': priority,
            'cpu_core': cpu_core,
            'registered_time': time.time()
        }
        
        if resource_limits:
            self.resource_limits[name] = resource_limits
        else:
            # Set default resource limits based on process type
            self.resource_limits[name] = self._get_default_resource_limits(name, priority)
        
        logger.info(f"Registered process '{name}' for performance optimization")
        
        # Apply optimizations immediately if process is running
        if process.is_alive():
            self.optimize_process(name)
    
    def _get_default_resource_limits(self, process_name: str, 
                                   priority: ProcessPriority) -> ResourceLimits:
        """Get default resource limits based on process type and priority."""
        if priority == ProcessPriority.REALTIME:
            # Datalogger - needs more resources for real-time sampling
            return ResourceLimits(
                max_memory_mb=200.0,
                max_cpu_percent=90.0,
                max_open_files=50
            )
        elif priority == ProcessPriority.HIGH:
            # Event logger - moderate resources for analysis
            return ResourceLimits(
                max_memory_mb=150.0,
                max_cpu_percent=70.0,
                max_open_files=30
            )
        elif priority == ProcessPriority.NORMAL:
            # FastAPI - standard web server resources
            return ResourceLimits(
                max_memory_mb=100.0,
                max_cpu_percent=60.0,
                max_open_files=100
            )
        else:  # LOW
            # Background tasks - minimal resources
            return ResourceLimits(
                max_memory_mb=50.0,
                max_cpu_percent=30.0,
                max_open_files=20
            )
    
    def optimize_process(self, process_name: str) -> bool:
        """
        Apply performance optimizations to a registered process.
        
        Args:
            process_name: Name of the process to optimize
            
        Returns:
            True if optimizations were applied successfully
        """
        if process_name not in self.managed_processes:
            logger.error(f"Process '{process_name}' not registered")
            return False
        
        process_info = self.managed_processes[process_name]
        process = process_info['process']
        
        if not process.is_alive():
            logger.warning(f"Process '{process_name}' is not running")
            return False
        
        try:
            psutil_process = psutil.Process(process.pid)
            
            # Set CPU affinity
            if process_info['cpu_core'] is not None:
                self._set_cpu_affinity(psutil_process, process_info['cpu_core'], process_name)
            
            # Set process priority
            self._set_process_priority(psutil_process, process_info['priority'], process_name)
            
            # Set I/O priority (if supported)
            self._set_io_priority(psutil_process, process_info['priority'], process_name)
            
            logger.info(f"Applied performance optimizations to '{process_name}'")
            return True
            
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.error(f"Failed to optimize process '{process_name}': {e}")
            return False
    
    def _set_cpu_affinity(self, psutil_process: psutil.Process, 
                         cpu_core: CPUCore, process_name: str) -> None:
        """Set CPU affinity for a process."""
        try:
            # Validate core exists
            available_cores = list(range(self.system_info['cpu_count']))
            if cpu_core.value not in available_cores:
                logger.warning(f"CPU core {cpu_core.value} not available, using core 0")
                core_list = [0]
            else:
                core_list = [cpu_core.value]
            
            # Check if CPU affinity is supported on this platform
            if hasattr(psutil_process, 'cpu_affinity') and callable(getattr(psutil_process, 'cpu_affinity', None)):
                psutil_process.cpu_affinity(core_list)
                logger.info(f"Set CPU affinity for '{process_name}' to core {core_list}")
            else:
                logger.warning(f"CPU affinity not supported on this platform for '{process_name}'")
            
        except (psutil.AccessDenied, OSError, AttributeError) as e:
            logger.warning(f"Failed to set CPU affinity for '{process_name}': {e}")
    
    def _set_process_priority(self, psutil_process: psutil.Process, 
                            priority: ProcessPriority, process_name: str) -> None:
        """Set process scheduling priority."""
        try:
            if priority == ProcessPriority.REALTIME:
                # Highest priority for real-time processes
                if hasattr(psutil, 'REALTIME_PRIORITY_CLASS'):
                    psutil_process.nice(psutil.REALTIME_PRIORITY_CLASS)
                else:
                    psutil_process.nice(-10)  # High priority on Unix
            elif priority == ProcessPriority.HIGH:
                psutil_process.nice(-5)
            elif priority == ProcessPriority.NORMAL:
                psutil_process.nice(0)
            else:  # LOW
                psutil_process.nice(10)
            
            logger.info(f"Set priority for '{process_name}' to {priority.value}")
            
        except (psutil.AccessDenied, OSError) as e:
            logger.warning(f"Failed to set priority for '{process_name}': {e}")
    
    def _set_io_priority(self, psutil_process: psutil.Process, 
                        priority: ProcessPriority, process_name: str) -> None:
        """Set I/O priority for a process (Linux only)."""
        try:
            if hasattr(psutil_process, 'ionice'):
                if priority == ProcessPriority.REALTIME:
                    psutil_process.ionice(psutil.IOPRIO_CLASS_RT, value=1)
                elif priority == ProcessPriority.HIGH:
                    psutil_process.ionice(psutil.IOPRIO_CLASS_BE, value=2)
                elif priority == ProcessPriority.NORMAL:
                    psutil_process.ionice(psutil.IOPRIO_CLASS_BE, value=4)
                else:  # LOW
                    psutil_process.ionice(psutil.IOPRIO_CLASS_IDLE)
                
                logger.info(f"Set I/O priority for '{process_name}' to {priority.value}")
            
        except (psutil.AccessDenied, OSError, AttributeError) as e:
            logger.debug(f"I/O priority not supported or failed for '{process_name}': {e}")
    
    def get_process_metrics(self, process_name: str) -> Optional[PerformanceMetrics]:
        """
        Get current performance metrics for a process.
        
        Args:
            process_name: Name of the process
            
        Returns:
            PerformanceMetrics object or None if process not found
        """
        if process_name not in self.managed_processes:
            return None
        
        process_info = self.managed_processes[process_name]
        process = process_info['process']
        
        if not process.is_alive():
            return None
        
        try:
            psutil_process = psutil.Process(process.pid)
            
            # Get memory info
            memory_info = psutil_process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            
            # Get CPU info
            cpu_percent = psutil_process.cpu_percent()
            
            # Get I/O info
            try:
                io_counters = psutil_process.io_counters()
                io_read_bytes = io_counters.read_bytes
                io_write_bytes = io_counters.write_bytes
            except (psutil.AccessDenied, AttributeError):
                io_read_bytes = 0
                io_write_bytes = 0
            
            # Calculate uptime
            create_time = psutil_process.create_time()
            uptime = time.time() - create_time
            
            return PerformanceMetrics(
                process_name=process_name,
                pid=process.pid,
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                memory_percent=psutil_process.memory_percent(),
                cpu_affinity=psutil_process.cpu_affinity(),
                priority=psutil_process.nice(),
                open_files=len(psutil_process.open_files()),
                threads=psutil_process.num_threads(),
                uptime=uptime,
                io_read_bytes=io_read_bytes,
                io_write_bytes=io_write_bytes,
                timestamp=time.time()
            )
            
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.debug(f"Failed to get metrics for '{process_name}': {e}")
            return None
    
    def check_resource_limits(self, process_name: str) -> Dict[str, Any]:
        """
        Check if a process is within its resource limits.
        
        Args:
            process_name: Name of the process to check
            
        Returns:
            Dictionary with limit check results
        """
        metrics = self.get_process_metrics(process_name)
        if not metrics:
            return {'error': 'Process not found or not running'}
        
        limits = self.resource_limits.get(process_name)
        if not limits:
            return {'error': 'No resource limits defined'}
        
        results = {
            'within_limits': True,
            'warnings': [],
            'violations': []
        }
        
        # Check memory limit
        if metrics.memory_mb > limits.max_memory_mb:
            results['within_limits'] = False
            results['violations'].append(
                f"Memory usage ({metrics.memory_mb:.1f}MB) exceeds limit ({limits.max_memory_mb}MB)"
            )
        elif metrics.memory_mb > limits.max_memory_mb * limits.memory_warning_threshold:
            results['warnings'].append(
                f"Memory usage ({metrics.memory_mb:.1f}MB) approaching limit ({limits.max_memory_mb}MB)"
            )
        
        # Check CPU limit
        if metrics.cpu_percent > limits.max_cpu_percent:
            results['within_limits'] = False
            results['violations'].append(
                f"CPU usage ({metrics.cpu_percent:.1f}%) exceeds limit ({limits.max_cpu_percent}%)"
            )
        
        # Check open files limit
        if metrics.open_files > limits.max_open_files:
            results['within_limits'] = False
            results['violations'].append(
                f"Open files ({metrics.open_files}) exceeds limit ({limits.max_open_files})"
            )
        
        return results
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get overall system performance metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            
            # Network metrics (if available)
            try:
                network = psutil.net_io_counters()
                network_stats = {
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv
                }
            except:
                network_stats = {}
            
            return {
                'timestamp': time.time(),
                'cpu': {
                    'percent_total': cpu_percent,
                    'percent_per_core': cpu_per_core,
                    'count': self.system_info['cpu_count']
                },
                'memory': {
                    'total_gb': memory.total / (1024**3),
                    'available_gb': memory.available / (1024**3),
                    'used_gb': memory.used / (1024**3),
                    'percent': memory.percent
                },
                'disk': {
                    'total_gb': disk.total / (1024**3),
                    'used_gb': disk.used / (1024**3),
                    'free_gb': disk.free / (1024**3),
                    'percent': (disk.used / disk.total) * 100
                },
                'network': network_stats,
                'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
            }
            
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return {'error': str(e)}
    
    def start_monitoring(self) -> None:
        """Start continuous performance monitoring."""
        if self.monitoring_active:
            logger.warning("Performance monitoring already active")
            return
        
        if not self.enable_monitoring:
            logger.info("Performance monitoring disabled")
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            name="PerformanceMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        logger.info("Performance monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop continuous performance monitoring."""
        if not self.monitoring_active:
            return
        
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        logger.info("Performance monitoring stopped")
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                # Collect metrics for all managed processes
                for process_name in self.managed_processes:
                    metrics = self.get_process_metrics(process_name)
                    if metrics:
                        self.performance_history.append(metrics)
                        
                        # Check resource limits
                        limit_check = self.check_resource_limits(process_name)
                        
                        # Log warnings and violations
                        for warning in limit_check.get('warnings', []):
                            logger.warning(f"Resource warning for '{process_name}': {warning}")
                        
                        for violation in limit_check.get('violations', []):
                            logger.error(f"Resource violation for '{process_name}': {violation}")
                
                # Trim history if too long
                if len(self.performance_history) > 1000:
                    self.performance_history = self.performance_history[-500:]
                
                # Log system metrics periodically
                if int(time.time()) % 60 == 0:  # Every minute
                    system_metrics = self.get_system_metrics()
                    logger.info(f"System metrics: CPU {system_metrics['cpu']['percent_total']:.1f}%, "
                              f"Memory {system_metrics['memory']['percent']:.1f}%")
                
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")
                time.sleep(self.monitoring_interval)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all managed processes."""
        summary = {
            'timestamp': time.time(),
            'system_info': self.system_info,
            'processes': {},
            'system_metrics': self.get_system_metrics()
        }
        
        for process_name in self.managed_processes:
            metrics = self.get_process_metrics(process_name)
            if metrics:
                limit_check = self.check_resource_limits(process_name)
                
                summary['processes'][process_name] = {
                    'metrics': {
                        'cpu_percent': metrics.cpu_percent,
                        'memory_mb': metrics.memory_mb,
                        'memory_percent': metrics.memory_percent,
                        'cpu_affinity': metrics.cpu_affinity,
                        'priority': metrics.priority,
                        'uptime': metrics.uptime,
                        'threads': metrics.threads
                    },
                    'resource_status': limit_check,
                    'optimizations_applied': {
                        'cpu_core': self.managed_processes[process_name]['cpu_core'].value 
                                   if self.managed_processes[process_name]['cpu_core'] else None,
                        'priority': self.managed_processes[process_name]['priority'].value
                    }
                }
        
        return summary
    
    def optimize_all_processes(self) -> Dict[str, bool]:
        """Apply optimizations to all registered processes."""
        results = {}
        
        for process_name in self.managed_processes:
            results[process_name] = self.optimize_process(process_name)
        
        logger.info(f"Applied optimizations to {sum(results.values())}/{len(results)} processes")
        return results
    
    def cleanup(self) -> None:
        """Clean up performance optimizer resources."""
        logger.info("Cleaning up PerformanceOptimizer")
        
        # Stop monitoring
        self.stop_monitoring()
        
        # Clear data structures
        self.managed_processes.clear()
        self.performance_history.clear()
        self.resource_limits.clear()
        
        logger.info("PerformanceOptimizer cleanup completed")


def create_optimized_process_config() -> Dict[str, Dict[str, Any]]:
    """
    Create optimized process configuration for the multiprocessing datalogger.
    
    Returns:
        Dictionary mapping process names to their optimization settings
    """
    return {
        'datalogger': {
            'priority': ProcessPriority.REALTIME,
            'cpu_core': CPUCore.CORE_0,
            'resource_limits': ResourceLimits(
                max_memory_mb=200.0,
                max_cpu_percent=90.0,
                max_open_files=50
            )
        },
        'event_logger': {
            'priority': ProcessPriority.HIGH,
            'cpu_core': CPUCore.CORE_1,
            'resource_limits': ResourceLimits(
                max_memory_mb=150.0,
                max_cpu_percent=70.0,
                max_open_files=30
            )
        },
        'fastapi': {
            'priority': ProcessPriority.NORMAL,
            'cpu_core': CPUCore.CORE_2,
            'resource_limits': ResourceLimits(
                max_memory_mb=100.0,
                max_cpu_percent=60.0,
                max_open_files=100
            )
        },
        'websocket': {
            'priority': ProcessPriority.NORMAL,
            'cpu_core': CPUCore.CORE_3,
            'resource_limits': ResourceLimits(
                max_memory_mb=80.0,
                max_cpu_percent=50.0,
                max_open_files=50
            )
        }
    }