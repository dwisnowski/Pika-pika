"""Property-based test for circular buffer behavior.

**Feature: datalogger-multiprocessing, Property 3: Circular Buffer Behavior**
**Validates: Requirements 2.4**

Property: For any shared memory buffer at capacity, writing new samples should 
overwrite the oldest samples while maintaining the total buffer size.
"""

import sys
import os
import time
import logging
from typing import List, Tuple
from hypothesis import given, strategies as st, settings

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pika.shared_memory import SharedSampleBuffer

# Suppress logging during tests to reduce noise
logging.getLogger('pika.shared_memory').setLevel(logging.WARNING)


@given(
    buffer_size=st.integers(min_value=3, max_value=20),
    num_samples=st.integers(min_value=1, max_value=50),
    sample_values=st.lists(
        st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=50
    )
)
@settings(max_examples=100, deadline=5000)
def test_circular_buffer_property(buffer_size: int, num_samples: int, sample_values: List[float]):
    """Property test: Circular buffer maintains size and overwrites oldest samples.
    
    This test validates that regardless of buffer size and number of samples written,
    the circular buffer always:
    1. Maintains the specified maximum size
    2. Contains the most recently written samples when at capacity
    3. Overwrites the oldest samples when new samples are added at capacity
    """
    
    # Limit sample values to match num_samples
    sample_values = sample_values[:num_samples]
    if len(sample_values) < num_samples:
        sample_values.extend([0.0] * (num_samples - len(sample_values)))
    
    buffer = None
    try:
        # Create buffer with specified size
        buffer = SharedSampleBuffer(size=buffer_size)
        
        # Write samples with incrementing timestamps
        base_time = time.time()
        written_samples = []
        
        for i in range(num_samples):
            timestamp = base_time + i * 0.01  # 10ms intervals
            value = sample_values[i]
            written_samples.append((timestamp, value))
            buffer.write_sample(timestamp, value)
        
        # Get buffer info
        info = buffer.get_buffer_info()
        
        # Property 1: Buffer count should never exceed buffer size
        assert info['count'] <= buffer_size, \
            f"Buffer count {info['count']} exceeds size {buffer_size}"
        
        # Property 2: Buffer should contain exactly min(num_samples, buffer_size) samples
        expected_count = min(num_samples, buffer_size)
        assert info['count'] == expected_count, \
            f"Expected count {expected_count}, got {info['count']}"
        
        # Property 3: When buffer is at capacity, it should contain the most recent samples
        if num_samples > buffer_size:
            # Buffer should be at capacity and contain the last buffer_size samples
            all_samples = buffer.read_all()
            assert len(all_samples) == buffer_size, \
                f"Expected {buffer_size} samples, got {len(all_samples)}"
            
            # Should contain the most recent samples (last buffer_size written)
            expected_samples = written_samples[-buffer_size:]
            
            # Verify samples are the most recent ones (allowing for small timestamp differences)
            for i, (actual_ts, actual_val) in enumerate(all_samples):
                expected_ts, expected_val = expected_samples[i]
                
                assert abs(actual_ts - expected_ts) < 1e-6, \
                    f"Timestamp mismatch at index {i}: expected {expected_ts}, got {actual_ts}"
                assert abs(actual_val - expected_val) < 1e-10, \
                    f"Value mismatch at index {i}: expected {expected_val}, got {actual_val}"
        
        else:
            # Buffer not at capacity, should contain all written samples
            all_samples = buffer.read_all()
            assert len(all_samples) == num_samples, \
                f"Expected {num_samples} samples, got {len(all_samples)}"
            
            # Should contain all written samples in order
            for i, (actual_ts, actual_val) in enumerate(all_samples):
                expected_ts, expected_val = written_samples[i]
                
                assert abs(actual_ts - expected_ts) < 1e-6, \
                    f"Timestamp mismatch at index {i}: expected {expected_ts}, got {actual_ts}"
                assert abs(actual_val - expected_val) < 1e-10, \
                    f"Value mismatch at index {i}: expected {expected_val}, got {actual_val}"
        
        # Property 4: Head position should wrap around correctly
        expected_head = num_samples % buffer_size
        assert info['head'] == expected_head, \
            f"Head position should be {expected_head}, got {info['head']}"
        
        # Property 5: Latest sample should be the last one written
        latest = buffer.get_latest_sample()
        if num_samples > 0:
            assert latest is not None, "Latest sample should not be None when samples exist"
            last_written = written_samples[-1]
            assert abs(latest[0] - last_written[0]) < 1e-6, \
                f"Latest timestamp mismatch: expected {last_written[0]}, got {latest[0]}"
            assert abs(latest[1] - last_written[1]) < 1e-10, \
                f"Latest value mismatch: expected {last_written[1]}, got {latest[1]}"
        
    finally:
        if buffer:
            buffer.cleanup()


@given(
    buffer_size=st.integers(min_value=5, max_value=15),
    initial_samples=st.integers(min_value=1, max_value=10),
    additional_samples=st.integers(min_value=1, max_value=20)
)
@settings(max_examples=50, deadline=3000)
def test_circular_buffer_overwrite_property(buffer_size: int, initial_samples: int, additional_samples: int):
    """Property test: Circular buffer correctly overwrites oldest samples.
    
    This test validates that when a buffer reaches capacity and additional samples
    are written, the oldest samples are correctly overwritten and the buffer
    maintains its circular behavior.
    """
    
    buffer = None
    try:
        buffer = SharedSampleBuffer(size=buffer_size)
        base_time = time.time()
        
        # Phase 1: Write initial samples (may or may not fill buffer)
        initial_written = []
        for i in range(initial_samples):
            timestamp = base_time + i * 0.01
            value = float(i)
            initial_written.append((timestamp, value))
            buffer.write_sample(timestamp, value)
        
        # Phase 2: Write additional samples (will cause overwrites if buffer was full)
        additional_written = []
        for i in range(additional_samples):
            timestamp = base_time + (initial_samples + i) * 0.01
            value = float(initial_samples + i)
            additional_written.append((timestamp, value))
            buffer.write_sample(timestamp, value)
        
        # Analyze final state
        all_written = initial_written + additional_written
        total_samples = initial_samples + additional_samples
        
        info = buffer.get_buffer_info()
        all_samples = buffer.read_all()
        
        # Property 1: Buffer should never exceed its size
        assert info['count'] <= buffer_size
        assert len(all_samples) <= buffer_size
        
        # Property 2: Buffer should contain the most recent samples
        expected_count = min(total_samples, buffer_size)
        assert info['count'] == expected_count
        assert len(all_samples) == expected_count
        
        # Property 3: Samples should be the most recent ones written
        if total_samples > buffer_size:
            # Buffer at capacity - should contain last buffer_size samples
            expected_samples = all_written[-buffer_size:]
        else:
            # Buffer not at capacity - should contain all samples
            expected_samples = all_written
        
        # Verify the samples match expectations
        for i, (actual_ts, actual_val) in enumerate(all_samples):
            expected_ts, expected_val = expected_samples[i]
            
            assert abs(actual_ts - expected_ts) < 1e-6, \
                f"Sample {i}: timestamp mismatch"
            assert abs(actual_val - expected_val) < 1e-10, \
                f"Sample {i}: value mismatch"
        
        # Property 4: Head position should be correct
        expected_head = total_samples % buffer_size
        assert info['head'] == expected_head
        
    finally:
        if buffer:
            buffer.cleanup()


def test_circular_buffer_edge_cases():
    """Test edge cases for circular buffer behavior."""
    
    # Test with buffer size 1
    buffer = SharedSampleBuffer(size=1)
    try:
        # Write multiple samples to size-1 buffer
        for i in range(5):
            buffer.write_sample(time.time() + i, float(i))
        
        info = buffer.get_buffer_info()
        assert info['count'] == 1
        assert info['head'] == 0  # 5 % 1 = 0
        
        # Should contain only the last sample
        latest = buffer.get_latest_sample()
        assert latest is not None
        assert latest[1] == 4.0  # Last value written
        
    finally:
        buffer.cleanup()
    
    # Test with empty buffer
    buffer = SharedSampleBuffer(size=10)
    try:
        info = buffer.get_buffer_info()
        assert info['count'] == 0
        assert info['head'] == 0
        assert buffer.get_latest_sample() is None
        assert buffer.read_all() == []
        
    finally:
        buffer.cleanup()


def main():
    """Run all property tests for circular buffer behavior."""
    
    print("Property-Based Test: Circular Buffer Behavior")
    print("=" * 60)
    print("**Feature: datalogger-multiprocessing, Property 3: Circular Buffer Behavior**")
    print("**Validates: Requirements 2.4**")
    print()
    print("Testing property: For any shared memory buffer at capacity,")
    print("writing new samples should overwrite the oldest samples")
    print("while maintaining the total buffer size.")
    print()
    
    try:
        # Run edge case tests first
        print("Running edge case tests...")
        test_circular_buffer_edge_cases()
        print("✅ Edge case tests passed")
        
        # Run property-based tests
        print("\nRunning property-based tests...")
        print("Testing circular buffer property...")
        test_circular_buffer_property()
        print("✅ Circular buffer property tests passed")
        
        print("\nTesting overwrite behavior property...")
        test_circular_buffer_overwrite_property()
        print("✅ Overwrite behavior property tests passed")
        
        print()
        print("=" * 60)
        print("🎉 ALL PROPERTY TESTS PASSED")
        print("Circular buffer behavior is correctly implemented.")
        return 0
        
    except Exception as e:
        print(f"💥 Property test execution failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())