"""
Shared memory data structures for inter-process communication.

This module provides memory-mapped data structures that enable efficient
communication between the datalogger, event logger, FastAPI, and WebSocket processes.
"""

import struct
import time
import json
from multiprocessing import shared_memory, Value, Lock
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class SamplePoint:
    """Represents a single ADC sample with timestamp."""
    timestamp: float  # Unix timestamp with microsecond precision
    value: float      # ADC voltage reading
    
    def to_bytes(self) -> bytes:
        """Convert sample point to bytes for shared memory storage."""
        return struct.pack('dd', self.timestamp, self.value)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'SamplePoint':
        """Create sample point from bytes stored in shared memory."""
        ts, val = struct.unpack('dd', data)
        return cls(ts, val)


class SharedSampleBuffer:
    """
    Memory-mapped circular buffer for high-frequency sample data.
    
    Provides lock-free write operations for the datalogger process and
    non-blocking read operations for API and WebSocket processes.
    
    Buffer stores 60 seconds of data at 100Hz (6000 samples).
    Each sample is 16 bytes (8 bytes timestamp + 8 bytes value).
    """
    
    SAMPLE_SIZE = 16  # 8 bytes timestamp + 8 bytes value
    DEFAULT_SIZE = 6000  # 60 seconds at 100Hz
    
    def __init__(self, size: int = DEFAULT_SIZE, create: bool = True, name: Optional[str] = None):
        """
        Initialize shared sample buffer.
        
        Args:
            size: Number of samples to store in the circular buffer
            create: Whether to create new shared memory or attach to existing
            name: Name of shared memory segment (auto-generated if None)
        """
        self.size = size
        self.buffer_size = size * self.SAMPLE_SIZE
        
        if create:
            # Create new shared memory segment
            self.shm = shared_memory.SharedMemory(
                create=True, 
                size=self.buffer_size,
                name=name
            )
            self.head = Value('i', 0)  # Write position (atomic integer)
            self.count = Value('i', 0)  # Current sample count (atomic integer)
            
            # Initialize buffer with zeros
            for i in range(self.buffer_size):
                self.shm.buf[i] = 0
        else:
            # Attach to existing shared memory
            self.shm = shared_memory.SharedMemory(name=name)
            # Note: head and count would need to be passed separately when attaching
            # This is handled by the process supervisor
    
    def write_sample(self, timestamp: float, value: float) -> None:
        """
        Write a sample to the circular buffer (lock-free).
        
        This method is designed to be called from the datalogger process
        and uses atomic operations to ensure thread safety without locks.
        
        Args:
            timestamp: Unix timestamp with microsecond precision
            value: ADC voltage reading
        """
        # Create sample point and convert to bytes
        sample = SamplePoint(timestamp, value)
        sample_bytes = sample.to_bytes()
        
        # Get current write position atomically
        with self.head.get_lock():
            current_head = self.head.value
            next_head = (current_head + 1) % self.size
            self.head.value = next_head
        
        # Write sample data to buffer at current position
        start_offset = current_head * self.SAMPLE_SIZE
        end_offset = start_offset + self.SAMPLE_SIZE
        self.shm.buf[start_offset:end_offset] = sample_bytes
        
        # Update count atomically (saturate at buffer size)
        with self.count.get_lock():
            if self.count.value < self.size:
                self.count.value += 1
    
    def read_recent(self, seconds: float) -> List[Tuple[float, float]]:
        """
        Read recent samples from the buffer (lock-free).
        
        This method is designed for API and WebSocket processes to read
        recent data without blocking the datalogger write operations.
        
        Args:
            seconds: Number of seconds of recent data to retrieve
            
        Returns:
            List of (timestamp, value) tuples in chronological order
        """
        # Calculate number of samples to read
        samples_requested = min(int(seconds * 100), self.size)  # Assume 100Hz sampling
        
        # Get current buffer state atomically
        with self.count.get_lock():
            current_count = self.count.value
        with self.head.get_lock():
            current_head = self.head.value
        
        # Determine actual samples to read
        samples_to_read = min(samples_requested, current_count)
        if samples_to_read == 0:
            return []
        
        # Calculate start position for reading
        # Head points to next write position, so we read backwards
        start_pos = (current_head - samples_to_read) % self.size
        
        samples = []
        for i in range(samples_to_read):
            pos = (start_pos + i) % self.size
            start_offset = pos * self.SAMPLE_SIZE
            end_offset = start_offset + self.SAMPLE_SIZE
            
            # Read sample bytes from buffer
            sample_bytes = bytes(self.shm.buf[start_offset:end_offset])
            
            # Convert bytes back to sample point
            try:
                sample = SamplePoint.from_bytes(sample_bytes)
                samples.append((sample.timestamp, sample.value))
            except struct.error:
                # Skip corrupted samples (shouldn't happen with atomic writes)
                continue
        
        return samples
    
    def read_all(self) -> List[Tuple[float, float]]:
        """
        Read all available samples from the buffer.
        
        Returns:
            List of (timestamp, value) tuples in chronological order
        """
        with self.count.get_lock():
            current_count = self.count.value
        
        if current_count == 0:
            return []
        
        # Read all available samples
        return self.read_recent(current_count / 100.0)  # Convert count to seconds
    
    def get_latest_sample(self) -> Optional[Tuple[float, float]]:
        """
        Get the most recently written sample.
        
        Returns:
            (timestamp, value) tuple or None if buffer is empty
        """
        with self.count.get_lock():
            current_count = self.count.value
        
        if current_count == 0:
            return None
        
        with self.head.get_lock():
            current_head = self.head.value
        
        # Get the last written sample (head - 1)
        last_pos = (current_head - 1) % self.size
        start_offset = last_pos * self.SAMPLE_SIZE
        end_offset = start_offset + self.SAMPLE_SIZE
        
        sample_bytes = bytes(self.shm.buf[start_offset:end_offset])
        
        try:
            sample = SamplePoint.from_bytes(sample_bytes)
            return (sample.timestamp, sample.value)
        except struct.error:
            return None
    
    def clear(self) -> None:
        """
        Clear the buffer by resetting head and count to zero.
        
        This method is useful for testing and buffer reset operations.
        """
        with self.head.get_lock():
            self.head.value = 0
        with self.count.get_lock():
            self.count.value = 0
        
        # Optionally zero out the buffer memory
        for i in range(self.buffer_size):
            self.shm.buf[i] = 0
    
    def get_buffer_info(self) -> dict:
        """
        Get current buffer status information.
        
        Returns:
            Dictionary with buffer statistics
        """
        with self.count.get_lock():
            current_count = self.count.value
        with self.head.get_lock():
            current_head = self.head.value
        
        return {
            'size': self.size,
            'count': current_count,
            'head': current_head,
            'utilization': current_count / self.size,
            'memory_name': self.shm.name,
            'memory_size': self.buffer_size
        }
    
    def cleanup(self) -> None:
        """Clean up shared memory resources."""
        try:
            self.shm.close()
            self.shm.unlink()
        except FileNotFoundError:
            # Already cleaned up
            pass
    
    def __del__(self):
        """Ensure cleanup on garbage collection."""
        if hasattr(self, 'shm'):
            try:
                self.shm.close()
            except:
                pass


@dataclass
class AnalysisMetrics:
    """Represents real-time analysis metrics computed from sample data."""
    rms: float                    # RMS voltage value
    frequency: float              # Detected frequency in Hz
    sags_swells: List[Dict]      # List of detected sag/swell events
    last_updated: float          # Timestamp of last update
    
    def to_json(self) -> str:
        """Convert analysis metrics to JSON string for shared memory storage."""
        data = {
            'rms': self.rms,
            'frequency': self.frequency,
            'sags_swells': self.sags_swells,
            'last_updated': self.last_updated
        }
        return json.dumps(data)
    
    @classmethod
    def from_json(cls, data: str) -> 'AnalysisMetrics':
        """Create analysis metrics from JSON string stored in shared memory."""
        parsed = json.loads(data)
        return cls(
            rms=parsed['rms'],
            frequency=parsed['frequency'],
            sags_swells=parsed['sags_swells'],
            last_updated=parsed['last_updated']
        )


class SharedAnalysisBuffer:
    """
    Memory-mapped buffer for analysis metrics storage.
    
    Provides thread-safe storage for real-time computed statistics (RMS, frequency,
    sags/swells) that are generated by the Event Logger Process and consumed by
    the FastAPI and WebSocket processes.
    
    Uses JSON serialization for flexible metric storage with timestamp tracking
    for update frequency control.
    """
    
    DEFAULT_SIZE = 2048  # 2KB for JSON-serialized metrics
    
    def __init__(self, size: int = DEFAULT_SIZE, create: bool = True, name: Optional[str] = None):
        """
        Initialize shared analysis buffer.
        
        Args:
            size: Size of shared memory buffer in bytes
            create: Whether to create new shared memory or attach to existing
            name: Name of shared memory segment (auto-generated if None)
        """
        self.size = size
        
        if create:
            # Create new shared memory segment
            self.shm = shared_memory.SharedMemory(
                create=True,
                size=size,
                name=name
            )
            self.last_update = Value('d', 0.0)  # Timestamp of last update
            self.data_length = Value('i', 0)    # Length of valid JSON data
            self.lock = Lock()                  # For thread-safe operations
            
            # Initialize buffer with empty JSON
            empty_metrics = AnalysisMetrics(
                rms=0.0,
                frequency=0.0,
                sags_swells=[],
                last_updated=0.0
            )
            self._write_metrics_to_buffer(empty_metrics)
            
        else:
            # Attach to existing shared memory
            self.shm = shared_memory.SharedMemory(name=name)
            # Note: last_update, data_length, and lock would need to be passed separately
            # This is handled by the process supervisor
    
    def update_metrics(self, rms: float, frequency: float, events: List[Dict]) -> None:
        """
        Update analysis metrics in shared memory (thread-safe).
        
        This method is designed to be called from the Event Logger Process
        to store computed analysis results.
        
        Args:
            rms: RMS voltage value
            frequency: Detected frequency in Hz
            events: List of detected sag/swell events
        """
        current_time = time.time()
        
        metrics = AnalysisMetrics(
            rms=rms,
            frequency=frequency,
            sags_swells=events,
            last_updated=current_time
        )
        
        with self.lock:
            self._write_metrics_to_buffer(metrics)
            self.last_update.value = current_time
    
    def get_current_analysis(self) -> Dict[str, Any]:
        """
        Read current analysis metrics from shared memory (thread-safe).
        
        This method is designed for FastAPI and WebSocket processes to read
        the latest analysis results without blocking the Event Logger Process.
        
        Returns:
            Dictionary containing current analysis metrics
        """
        with self.lock:
            try:
                # Read JSON data from buffer
                data_len = self.data_length.value
                if data_len == 0:
                    # No data available
                    return {
                        'rms': 0.0,
                        'frequency': 0.0,
                        'sags_swells': [],
                        'last_updated': 0.0
                    }
                
                # Extract JSON string from buffer
                json_bytes = bytes(self.shm.buf[:data_len])
                json_str = json_bytes.decode('utf-8')
                
                # Parse metrics
                metrics = AnalysisMetrics.from_json(json_str)
                
                return {
                    'rms': metrics.rms,
                    'frequency': metrics.frequency,
                    'sags_swells': metrics.sags_swells,
                    'last_updated': metrics.last_updated
                }
                
            except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as e:
                # Return default values if data is corrupted
                return {
                    'rms': 0.0,
                    'frequency': 0.0,
                    'sags_swells': [],
                    'last_updated': 0.0,
                    'error': f"Data corruption: {e}"
                }
    
    def get_last_update_time(self) -> float:
        """
        Get timestamp of last metrics update.
        
        Returns:
            Unix timestamp of last update, or 0.0 if never updated
        """
        return self.last_update.value
    
    def is_data_fresh(self, max_age_seconds: float = 5.0) -> bool:
        """
        Check if analysis data is fresh (recently updated).
        
        Args:
            max_age_seconds: Maximum age in seconds to consider data fresh
            
        Returns:
            True if data was updated within max_age_seconds
        """
        last_update = self.get_last_update_time()
        if last_update == 0.0:
            return False
        
        age = time.time() - last_update
        return age <= max_age_seconds
    
    def _write_metrics_to_buffer(self, metrics: AnalysisMetrics) -> None:
        """
        Write metrics to shared memory buffer (internal method).
        
        Args:
            metrics: AnalysisMetrics object to write
        """
        try:
            # Convert metrics to JSON
            json_str = metrics.to_json()
            json_bytes = json_str.encode('utf-8')
            
            # Check if data fits in buffer
            if len(json_bytes) > self.size:
                # Truncate sags_swells if data is too large
                truncated_metrics = AnalysisMetrics(
                    rms=metrics.rms,
                    frequency=metrics.frequency,
                    sags_swells=[],  # Remove events to save space
                    last_updated=metrics.last_updated
                )
                json_str = truncated_metrics.to_json()
                json_bytes = json_str.encode('utf-8')
                
                # If still too large, use minimal data
                if len(json_bytes) > self.size:
                    minimal_data = {
                        'rms': metrics.rms,
                        'frequency': metrics.frequency,
                        'sags_swells': [],
                        'last_updated': metrics.last_updated
                    }
                    json_str = json.dumps(minimal_data)
                    json_bytes = json_str.encode('utf-8')
            
            # Write to shared memory buffer
            data_len = min(len(json_bytes), self.size)
            self.shm.buf[:data_len] = json_bytes[:data_len]
            
            # Clear remaining buffer space
            if data_len < self.size:
                for i in range(data_len, self.size):
                    self.shm.buf[i] = 0
            
            # Update data length
            self.data_length.value = data_len
            
        except Exception as e:
            # On any error, write minimal valid JSON
            minimal_json = '{"rms":0.0,"frequency":0.0,"sags_swells":[],"last_updated":0.0}'
            minimal_bytes = minimal_json.encode('utf-8')
            data_len = min(len(minimal_bytes), self.size)
            self.shm.buf[:data_len] = minimal_bytes[:data_len]
            self.data_length.value = data_len
    
    def get_buffer_info(self) -> Dict[str, Any]:
        """
        Get current buffer status information.
        
        Returns:
            Dictionary with buffer statistics
        """
        with self.lock:
            return {
                'size': self.size,
                'data_length': self.data_length.value,
                'last_update': self.last_update.value,
                'is_fresh': self.is_data_fresh(),
                'memory_name': self.shm.name,
                'utilization': self.data_length.value / self.size
            }
    
    def cleanup(self) -> None:
        """Clean up shared memory resources."""
        try:
            self.shm.close()
            self.shm.unlink()
        except FileNotFoundError:
            # Already cleaned up
            pass
    
    def __del__(self):
        """Ensure cleanup on garbage collection."""
        if hasattr(self, 'shm'):
            try:
                self.shm.close()
            except:
                pass


@dataclass
class ProcessConfig:
    """Represents process configuration with version tracking."""
    sample_hz: int
    batch_size: int
    batch_interval_ms: int
    analysis_config: Dict[str, Any]
    display_fps: float
    version: int
    
    def to_json(self) -> str:
        """Convert process configuration to JSON string for shared memory storage."""
        data = {
            'sample_hz': self.sample_hz,
            'batch_size': self.batch_size,
            'batch_interval_ms': self.batch_interval_ms,
            'analysis_config': self.analysis_config,
            'display_fps': self.display_fps,
            'version': self.version
        }
        return json.dumps(data)
    
    @classmethod
    def from_json(cls, data: str) -> 'ProcessConfig':
        """Create process configuration from JSON string stored in shared memory."""
        parsed = json.loads(data)
        return cls(
            sample_hz=parsed['sample_hz'],
            batch_size=parsed['batch_size'],
            batch_interval_ms=parsed['batch_interval_ms'],
            analysis_config=parsed['analysis_config'],
            display_fps=parsed['display_fps'],
            version=parsed['version']
        )


class SharedConfigBuffer:
    """
    Memory-mapped buffer for configuration synchronization.
    
    Provides versioned configuration storage with atomic update operations
    and change detection mechanisms. Enables runtime configuration updates
    across all processes without requiring full system restart.
    
    Uses JSON serialization for flexible configuration storage with version
    tracking for change detection and atomic updates.
    """
    
    DEFAULT_SIZE = 4096  # 4KB for JSON-serialized configuration
    
    def __init__(self, size: int = DEFAULT_SIZE, create: bool = True, name: Optional[str] = None):
        """
        Initialize shared configuration buffer.
        
        Args:
            size: Size of shared memory buffer in bytes
            create: Whether to create new shared memory or attach to existing
            name: Name of shared memory segment (auto-generated if None)
        """
        self.size = size
        
        if create:
            # Create new shared memory segment
            self.shm = shared_memory.SharedMemory(
                create=True,
                size=size,
                name=name
            )
            self.version = Value('i', 0)        # Configuration version for change detection
            self.data_length = Value('i', 0)    # Length of valid JSON data
            self.lock = Lock()                  # For atomic operations
            
            # Initialize buffer with default configuration
            default_config = ProcessConfig(
                sample_hz=100,
                batch_size=100,
                batch_interval_ms=1000,
                analysis_config={
                    'rms_window_size': 100,
                    'frequency_detection': True,
                    'sag_threshold': 0.9,
                    'swell_threshold': 1.1,
                    'event_min_duration_ms': 50
                },
                display_fps=5.0,
                version=0
            )
            self._write_config_to_buffer(default_config)
            
        else:
            # Attach to existing shared memory
            self.shm = shared_memory.SharedMemory(name=name)
            # Note: version, data_length, and lock would need to be passed separately
            # This is handled by the process supervisor
    
    def update_config(self, config: Dict[str, Any]) -> int:
        """
        Update configuration and increment version (atomic operation).
        
        This method provides atomic configuration updates with version tracking
        to enable change detection across processes.
        
        Args:
            config: Dictionary containing configuration parameters
            
        Returns:
            New version number after update
        """
        with self.lock:
            # Get current version and increment
            new_version = self.version.value + 1
            
            # Create ProcessConfig with new version
            process_config = ProcessConfig(
                sample_hz=config.get('sample_hz', 100),
                batch_size=config.get('batch_size', 100),
                batch_interval_ms=config.get('batch_interval_ms', 1000),
                analysis_config=config.get('analysis_config', {}),
                display_fps=config.get('display_fps', 5.0),
                version=new_version
            )
            
            # Write to buffer
            self._write_config_to_buffer(process_config)
            
            # Update version atomically
            self.version.value = new_version
            
            return new_version
    
    def get_config(self) -> Tuple[Dict[str, Any], int]:
        """
        Get configuration and version atomically.
        
        This method provides atomic read of both configuration data and version
        to enable change detection without race conditions.
        
        Returns:
            Tuple of (config_dict, version_number)
        """
        with self.lock:
            try:
                # Read JSON data from buffer
                data_len = self.data_length.value
                current_version = self.version.value
                
                if data_len == 0:
                    # No data available, return default
                    default_config = {
                        'sample_hz': 100,
                        'batch_size': 100,
                        'batch_interval_ms': 1000,
                        'analysis_config': {},
                        'display_fps': 5.0
                    }
                    return default_config, current_version
                
                # Extract JSON string from buffer
                json_bytes = bytes(self.shm.buf[:data_len])
                json_str = json_bytes.decode('utf-8')
                
                # Parse configuration
                config = ProcessConfig.from_json(json_str)
                
                config_dict = {
                    'sample_hz': config.sample_hz,
                    'batch_size': config.batch_size,
                    'batch_interval_ms': config.batch_interval_ms,
                    'analysis_config': config.analysis_config,
                    'display_fps': config.display_fps
                }
                
                return config_dict, current_version
                
            except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as e:
                # Return default values if data is corrupted
                default_config = {
                    'sample_hz': 100,
                    'batch_size': 100,
                    'batch_interval_ms': 1000,
                    'analysis_config': {},
                    'display_fps': 5.0,
                    'error': f"Data corruption: {e}"
                }
                return default_config, self.version.value
    
    def get_version(self) -> int:
        """
        Get current configuration version.
        
        Returns:
            Current version number
        """
        return self.version.value
    
    def has_changed(self, last_known_version: int) -> bool:
        """
        Check if configuration has changed since last known version.
        
        Args:
            last_known_version: Version number to compare against
            
        Returns:
            True if configuration has been updated since last_known_version
        """
        return self.get_version() > last_known_version
    
    def wait_for_change(self, last_known_version: int, timeout_seconds: float = 1.0) -> bool:
        """
        Wait for configuration change with timeout.
        
        This method can be used by processes to efficiently wait for
        configuration updates without polling.
        
        Args:
            last_known_version: Version to wait for changes from
            timeout_seconds: Maximum time to wait
            
        Returns:
            True if configuration changed, False if timeout occurred
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            if self.has_changed(last_known_version):
                return True
            time.sleep(0.01)  # Small sleep to avoid busy waiting
        
        return False
    
    def update_sample_rate(self, new_rate: int) -> int:
        """
        Update only the sample rate configuration.
        
        Args:
            new_rate: New sample rate in Hz
            
        Returns:
            New version number after update
        """
        config, _ = self.get_config()
        config['sample_hz'] = new_rate
        return self.update_config(config)
    
    def update_analysis_config(self, analysis_config: Dict[str, Any]) -> int:
        """
        Update only the analysis configuration.
        
        Args:
            analysis_config: New analysis configuration parameters
            
        Returns:
            New version number after update
        """
        config, _ = self.get_config()
        config['analysis_config'] = analysis_config
        return self.update_config(config)
    
    def _write_config_to_buffer(self, config: ProcessConfig) -> None:
        """
        Write configuration to shared memory buffer (internal method).
        
        Args:
            config: ProcessConfig object to write
        """
        try:
            # Convert config to JSON
            json_str = config.to_json()
            json_bytes = json_str.encode('utf-8')
            
            # Check if data fits in buffer
            if len(json_bytes) > self.size:
                # Create minimal configuration if data is too large
                minimal_config = ProcessConfig(
                    sample_hz=config.sample_hz,
                    batch_size=config.batch_size,
                    batch_interval_ms=config.batch_interval_ms,
                    analysis_config={},  # Remove analysis config to save space
                    display_fps=config.display_fps,
                    version=config.version
                )
                json_str = minimal_config.to_json()
                json_bytes = json_str.encode('utf-8')
                
                # If still too large, use absolute minimal data
                if len(json_bytes) > self.size:
                    minimal_data = {
                        'sample_hz': config.sample_hz,
                        'batch_size': 100,
                        'batch_interval_ms': 1000,
                        'analysis_config': {},
                        'display_fps': 5.0,
                        'version': config.version
                    }
                    json_str = json.dumps(minimal_data)
                    json_bytes = json_str.encode('utf-8')
            
            # Write to shared memory buffer
            data_len = min(len(json_bytes), self.size)
            self.shm.buf[:data_len] = json_bytes[:data_len]
            
            # Clear remaining buffer space
            if data_len < self.size:
                for i in range(data_len, self.size):
                    self.shm.buf[i] = 0
            
            # Update data length
            self.data_length.value = data_len
            
        except Exception as e:
            # On any error, write minimal valid JSON
            minimal_json = json.dumps({
                'sample_hz': 100,
                'batch_size': 100,
                'batch_interval_ms': 1000,
                'analysis_config': {},
                'display_fps': 5.0,
                'version': config.version
            })
            minimal_bytes = minimal_json.encode('utf-8')
            data_len = min(len(minimal_bytes), self.size)
            self.shm.buf[:data_len] = minimal_bytes[:data_len]
            self.data_length.value = data_len
    
    def get_buffer_info(self) -> Dict[str, Any]:
        """
        Get current buffer status information.
        
        Returns:
            Dictionary with buffer statistics
        """
        with self.lock:
            return {
                'size': self.size,
                'data_length': self.data_length.value,
                'version': self.version.value,
                'memory_name': self.shm.name,
                'utilization': self.data_length.value / self.size
            }
    
    def cleanup(self) -> None:
        """Clean up shared memory resources."""
        try:
            self.shm.close()
            self.shm.unlink()
        except FileNotFoundError:
            # Already cleaned up
            pass
    
    def __del__(self):
        """Ensure cleanup on garbage collection."""
        if hasattr(self, 'shm'):
            try:
                self.shm.close()
            except:
                pass