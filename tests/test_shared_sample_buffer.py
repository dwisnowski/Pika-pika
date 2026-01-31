"""Tests for SharedSampleBuffer circular buffer implementation."""

import pytest
import time
import struct
from multiprocessing import Process, Queue
from pika.shared_memory import SharedSampleBuffer, SamplePoint


def writer_process_func(buffer_name, queue):
    """Writer process function for testing concurrent operations."""
    try:
        # Attach to existing shared memory
        from multiprocessing import shared_memory
        from pika.shared_memory import SamplePoint
        import time
        
        shm = shared_memory.SharedMemory(name=buffer_name)
        
        # Write samples
        for i in range(10):
            timestamp = time.time() + i * 0.01
            value = float(i)
            
            # Manually write to shared memory (simplified for test)
            sample = SamplePoint(timestamp, value)
            sample_bytes = sample.to_bytes()
            offset = (i % 10) * 16  # Circular write
            shm.buf[offset:offset+16] = sample_bytes
            
            time.sleep(0.001)  # Small delay
        
        queue.put("writer_done")
        shm.close()
        
    except Exception as e:
        queue.put(f"writer_error: {e}")


class TestSamplePoint:
    """Test the SamplePoint data structure."""
    
    def test_sample_point_creation(self):
        """Test creating a sample point."""
        timestamp = time.time()
        value = 3.14159
        
        sample = SamplePoint(timestamp, value)
        assert sample.timestamp == timestamp
        assert sample.value == value
    
    def test_sample_point_serialization(self):
        """Test converting sample point to/from bytes."""
        timestamp = 1234567890.123456
        value = -2.71828
        
        sample = SamplePoint(timestamp, value)
        sample_bytes = sample.to_bytes()
        
        # Should be exactly 16 bytes
        assert len(sample_bytes) == 16
        
        # Should round-trip correctly
        restored_sample = SamplePoint.from_bytes(sample_bytes)
        assert abs(restored_sample.timestamp - timestamp) < 1e-10
        assert abs(restored_sample.value - value) < 1e-10


class TestSharedSampleBuffer:
    """Test the SharedSampleBuffer circular buffer."""
    
    def test_buffer_initialization(self):
        """Test buffer initialization."""
        buffer = SharedSampleBuffer(size=100)
        
        assert buffer.size == 100
        assert buffer.buffer_size == 100 * 16  # 16 bytes per sample
        
        info = buffer.get_buffer_info()
        assert info['size'] == 100
        assert info['count'] == 0
        assert info['head'] == 0
        assert info['utilization'] == 0.0
        
        buffer.cleanup()
    
    def test_single_sample_write_read(self):
        """Test writing and reading a single sample."""
        buffer = SharedSampleBuffer(size=10)
        
        timestamp = time.time()
        value = 1.23
        
        # Write sample
        buffer.write_sample(timestamp, value)
        
        # Check buffer info
        info = buffer.get_buffer_info()
        assert info['count'] == 1
        assert info['head'] == 1
        
        # Read latest sample
        latest = buffer.get_latest_sample()
        assert latest is not None
        assert abs(latest[0] - timestamp) < 1e-10
        assert abs(latest[1] - value) < 1e-10
        
        # Read recent samples
        recent = buffer.read_recent(1.0)  # 1 second
        assert len(recent) == 1
        assert abs(recent[0][0] - timestamp) < 1e-10
        assert abs(recent[0][1] - value) < 1e-10
        
        buffer.cleanup()
    
    def test_multiple_samples_write_read(self):
        """Test writing and reading multiple samples."""
        buffer = SharedSampleBuffer(size=10)
        
        # Write 5 samples
        samples = []
        for i in range(5):
            timestamp = time.time() + i * 0.01
            value = float(i)
            samples.append((timestamp, value))
            buffer.write_sample(timestamp, value)
        
        # Check buffer info
        info = buffer.get_buffer_info()
        assert info['count'] == 5
        assert info['head'] == 5
        
        # Read all samples
        all_samples = buffer.read_all()
        assert len(all_samples) == 5
        
        # Verify samples are in chronological order
        for i, (ts, val) in enumerate(all_samples):
            assert abs(ts - samples[i][0]) < 1e-10
            assert abs(val - samples[i][1]) < 1e-10
        
        buffer.cleanup()
    
    def test_circular_buffer_overflow(self):
        """Test circular buffer behavior when exceeding capacity."""
        buffer = SharedSampleBuffer(size=3)  # Small buffer for testing
        
        # Write 5 samples (more than capacity)
        samples = []
        for i in range(5):
            timestamp = time.time() + i * 0.01
            value = float(i)
            samples.append((timestamp, value))
            buffer.write_sample(timestamp, value)
        
        # Buffer should contain only the last 3 samples
        info = buffer.get_buffer_info()
        assert info['count'] == 3  # Saturated at buffer size
        assert info['head'] == 2   # Wrapped around (5 % 3 = 2)
        
        # Read all samples - should get the last 3
        all_samples = buffer.read_all()
        assert len(all_samples) == 3
        
        # Should contain samples 2, 3, 4 (the last 3 written)
        expected_samples = samples[2:5]  # samples 2, 3, 4
        for i, (ts, val) in enumerate(all_samples):
            assert abs(ts - expected_samples[i][0]) < 1e-10
            assert abs(val - expected_samples[i][1]) < 1e-10
        
        buffer.cleanup()
    
    def test_read_recent_with_time_limit(self):
        """Test reading recent samples with time constraints."""
        buffer = SharedSampleBuffer(size=100)
        
        # Write samples with specific timing
        base_time = time.time()
        for i in range(10):
            timestamp = base_time + i * 0.01  # 10ms intervals
            value = float(i)
            buffer.write_sample(timestamp, value)
        
        # Read last 0.05 seconds (should get ~5 samples at 100Hz)
        recent = buffer.read_recent(0.05)
        
        # Should get the last 5 samples (at 100Hz, 0.05s = 5 samples)
        assert len(recent) == 5
        
        # Verify we got the most recent samples
        for i, (ts, val) in enumerate(recent):
            expected_val = float(5 + i)  # samples 5, 6, 7, 8, 9
            assert abs(val - expected_val) < 1e-10
        
        buffer.cleanup()
    
    def test_empty_buffer_reads(self):
        """Test reading from empty buffer."""
        buffer = SharedSampleBuffer(size=10)
        
        # All read operations should handle empty buffer gracefully
        assert buffer.get_latest_sample() is None
        assert buffer.read_recent(1.0) == []
        assert buffer.read_all() == []
        
        info = buffer.get_buffer_info()
        assert info['count'] == 0
        assert info['utilization'] == 0.0
        
        buffer.cleanup()
    
    def test_concurrent_write_read(self):
        """Test concurrent write and read operations."""
        buffer = SharedSampleBuffer(size=10)
        queue = Queue()
        
        # Start writer process
        writer = Process(target=writer_process_func, args=(buffer.shm.name, queue))
        writer.start()
        
        # Read while writer is working
        time.sleep(0.005)  # Let writer get started
        
        # This tests that reads don't block writes
        for _ in range(5):
            buffer.read_recent(0.1)
            time.sleep(0.001)
        
        # Wait for writer to complete
        writer.join(timeout=2.0)
        result = queue.get() if not queue.empty() else "timeout"
        
        assert result == "writer_done", f"Writer process failed: {result}"
        
        buffer.cleanup()


if __name__ == "__main__":
    pytest.main([__file__])