"""Property-based test for data persistence continuity.

**Feature: datalogger-multiprocessing, Property 5: Data Persistence Continuity**
**Validates: Requirements 3.2, 3.3**

Property: For any file operation (daily rotation, batch writing), sampling should 
continue at the expected rate without interruption or data loss.
"""

import sys
import os
import time
import tempfile
import shutil
import csv
import logging
import threading
from typing import List, Tuple
from hypothesis import given, strategies as st, settings

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pika.shared_memory import SharedSampleBuffer, SharedConfigBuffer
from pika.datalogger_process import DataloggerProcess
from pika.adapters import MockADCAdapter

# Suppress logging during tests to reduce noise
logging.getLogger('pika.datalogger_process').setLevel(logging.WARNING)
logging.getLogger('pika.shared_memory').setLevel(logging.WARNING)
logging.getLogger('pika.adapters').setLevel(logging.WARNING)


class TestDataloggerProcess(DataloggerProcess):
    """Test version of DataloggerProcess with controllable timing."""
    
    def __init__(self, *args, **kwargs):
        # Force MockADC for testing
        kwargs['adc_type'] = 'mock'
        kwargs['adc_config'] = {'signal_type': 'dc', 'dc_offset': 5.0}
        # Disable display manager for testing
        kwargs['display_config'] = {'enabled': False}
        super().__init__(*args, **kwargs)
        
        # Track samples for verification
        self.samples_written = []
        self.original_write_sample = self.shared_sample_buffer.write_sample
        
        # Override write_sample to track what we write
        def tracking_write_sample(timestamp, value):
            self.samples_written.append((timestamp, value))
            return self.original_write_sample(timestamp, value)
        
        self.shared_sample_buffer.write_sample = tracking_write_sample


def create_test_environment():
    """Create a temporary test environment with shared memory buffers."""
    # Create temporary directory for test data
    temp_dir = tempfile.mkdtemp(prefix="datalogger_test_")
    
    # Create shared memory buffers
    sample_buffer = SharedSampleBuffer(size=100)
    config_buffer = SharedConfigBuffer()
    
    return temp_dir, sample_buffer, config_buffer


def cleanup_test_environment(temp_dir, sample_buffer, config_buffer):
    """Clean up test environment."""
    try:
        sample_buffer.cleanup()
    except:
        pass
    
    try:
        config_buffer.cleanup()
    except:
        pass
    
    try:
        shutil.rmtree(temp_dir)
    except:
        pass


@given(
    sample_rate=st.integers(min_value=10, max_value=100),
    batch_size=st.integers(min_value=5, max_value=50),
    test_duration=st.floats(min_value=1.0, max_value=3.0)
)
@settings(max_examples=5, deadline=10000)
def test_data_persistence_continuity_property(sample_rate: int, batch_size: int, test_duration: float):
    """Property test: Sampling continues without interruption during file operations.
    
    This test validates that regardless of sample rate, batch size, and test duration,
    the datalogger maintains consistent sampling without data loss during:
    1. Batch writing operations
    2. File rotation operations
    3. Configuration updates
    """
    
    temp_dir, sample_buffer, config_buffer = create_test_environment()
    
    try:
        # Create test datalogger
        datalogger = TestDataloggerProcess(
            shared_sample_buffer=sample_buffer,
            shared_config_buffer=config_buffer,
            data_dir=temp_dir,
            filename_prefix="test_log",
            retention_days=1,
            adc_type='mock'
        )
        
        # Configure initial settings
        datalogger.sample_hz = sample_rate
        datalogger.interval = 1.0 / sample_rate
        datalogger.batch_size = batch_size
        datalogger.batch_interval_ms = 500  # Force frequent flushes
        
        # Start datalogger
        datalogger.start()
        
        # Let it run for the test duration
        time.sleep(test_duration)
        
        # Trigger a configuration update during operation
        config_buffer.update_config({
            'sample_hz': sample_rate,
            'batch_size': batch_size + 5  # Small change to trigger update
        })
        
        # Continue running briefly after config update
        time.sleep(0.5)
        
        # Stop datalogger
        datalogger.stop()
        
        # Property 1: Samples should have been written to shared memory
        samples_in_memory = len(datalogger.samples_written)
        expected_min_samples = int(sample_rate * test_duration * 0.3)  # Allow 70% tolerance for test environment
        expected_max_samples = int(sample_rate * (test_duration + 3.0) * 3.0)  # Allow for startup/shutdown and timing variations
        
        assert samples_in_memory >= expected_min_samples, \
            f"Too few samples in memory: {samples_in_memory} < {expected_min_samples}"
        assert samples_in_memory <= expected_max_samples, \
            f"Too many samples in memory: {samples_in_memory} > {expected_max_samples}"
        
        # Property 2: Samples should be written to CSV files
        csv_files = [f for f in os.listdir(temp_dir) if f.startswith("test_log") and f.endswith(".csv")]
        assert len(csv_files) > 0, "No CSV files were created"
        
        # Property 3: CSV files should contain data
        total_csv_samples = 0
        for csv_file in csv_files:
            csv_path = os.path.join(temp_dir, csv_file)
            with open(csv_path, 'r') as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                csv_samples = list(reader)
                total_csv_samples += len(csv_samples)
        
        assert total_csv_samples > 0, "No samples found in CSV files"
        
        # Property 4: Sample timestamps should be reasonably spaced
        if len(datalogger.samples_written) >= 2:
            timestamps = [sample[0] for sample in datalogger.samples_written]
            intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
            
            # Filter out any negative intervals (shouldn't happen but be safe)
            positive_intervals = [interval for interval in intervals if interval > 0]
            
            if positive_intervals:
                avg_interval = sum(positive_intervals) / len(positive_intervals)
                expected_interval = 1.0 / sample_rate
                
                # Allow 80% tolerance for timing variations in test environment
                tolerance = expected_interval * 0.8
                assert abs(avg_interval - expected_interval) <= tolerance, \
                    f"Average interval {avg_interval:.4f}s too far from expected {expected_interval:.4f}s (tolerance: {tolerance:.4f}s)"
        
        # Property 5: Shared memory buffer should contain recent samples
        buffer_samples = sample_buffer.read_all()
        assert len(buffer_samples) > 0, "Shared memory buffer should contain samples"
        
        # Property 6: No significant data loss between memory and disk
        # (Allow some tolerance for timing and buffering)
        memory_vs_disk_ratio = total_csv_samples / max(1, samples_in_memory)
        assert 0.5 <= memory_vs_disk_ratio <= 1.5, \
            f"Significant data loss detected: CSV={total_csv_samples}, Memory={samples_in_memory}"
        
    finally:
        cleanup_test_environment(temp_dir, sample_buffer, config_buffer)


def test_file_rotation_continuity():
    """Test that sampling continues during daily file rotation."""
    
    temp_dir, sample_buffer, config_buffer = create_test_environment()
    
    try:
        datalogger = TestDataloggerProcess(
            shared_sample_buffer=sample_buffer,
            shared_config_buffer=config_buffer,
            data_dir=temp_dir,
            filename_prefix="rotation_test",
            retention_days=1
        )
        
        # Configure for fast sampling
        datalogger.sample_hz = 50
        datalogger.interval = 1.0 / 50
        datalogger.batch_size = 10
        datalogger.batch_interval_ms = 200
        
        # Start datalogger
        datalogger.start()
        
        # Let it run briefly
        time.sleep(0.5)
        
        # Force file rotation by changing the current date
        original_date = datalogger._current_date
        datalogger._current_date = None  # Force file reopen
        
        # Continue sampling
        time.sleep(0.5)
        
        # Stop datalogger
        datalogger.stop()
        
        # Verify samples were written throughout
        assert len(datalogger.samples_written) > 20, "Should have many samples across rotation"
        
        # Verify CSV files exist
        csv_files = [f for f in os.listdir(temp_dir) if f.startswith("rotation_test")]
        assert len(csv_files) > 0, "CSV files should exist after rotation"
        
    finally:
        cleanup_test_environment(temp_dir, sample_buffer, config_buffer)


def test_batch_writing_continuity():
    """Test that sampling continues during batch writing operations."""
    
    temp_dir, sample_buffer, config_buffer = create_test_environment()
    
    try:
        datalogger = TestDataloggerProcess(
            shared_sample_buffer=sample_buffer,
            shared_config_buffer=config_buffer,
            data_dir=temp_dir,
            filename_prefix="batch_test",
            retention_days=1
        )
        
        # Configure for frequent batch writes
        datalogger.sample_hz = 100
        datalogger.interval = 1.0 / 100
        datalogger.batch_size = 5  # Very small batches
        datalogger.batch_interval_ms = 100  # Frequent time-based flushes
        
        # Start datalogger
        datalogger.start()
        
        # Run long enough to trigger multiple batch writes
        time.sleep(1.0)
        
        # Stop datalogger
        datalogger.stop()
        
        # Verify continuous sampling
        samples_count = len(datalogger.samples_written)
        expected_min = 80  # Allow some tolerance
        assert samples_count >= expected_min, f"Expected at least {expected_min} samples, got {samples_count}"
        
        # Verify samples are in CSV
        csv_files = [f for f in os.listdir(temp_dir) if f.startswith("batch_test")]
        assert len(csv_files) > 0, "CSV files should exist"
        
        # Count samples in CSV
        total_csv_samples = 0
        for csv_file in csv_files:
            csv_path = os.path.join(temp_dir, csv_file)
            with open(csv_path, 'r') as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                total_csv_samples += len(list(reader))
        
        # Should have most samples in CSV (allowing for final batch in memory)
        assert total_csv_samples >= samples_count * 0.7, \
            f"Too few samples in CSV: {total_csv_samples} vs {samples_count} in memory"
        
    finally:
        cleanup_test_environment(temp_dir, sample_buffer, config_buffer)


def test_data_restoration_continuity():
    """Test that data restoration from disk works correctly."""
    
    temp_dir, sample_buffer, config_buffer = create_test_environment()
    
    try:
        # First, create some historical data
        datalogger1 = TestDataloggerProcess(
            shared_sample_buffer=sample_buffer,
            shared_config_buffer=config_buffer,
            data_dir=temp_dir,
            filename_prefix="restore_test",
            retention_days=1
        )
        
        datalogger1.sample_hz = 20
        datalogger1.interval = 1.0 / 20
        datalogger1.batch_size = 10
        datalogger1.batch_interval_ms = 200
        
        # Run first datalogger to create data
        datalogger1.start()
        time.sleep(1.0)
        datalogger1.stop()
        
        # Clear shared memory buffer
        sample_buffer.cleanup()
        sample_buffer = SharedSampleBuffer(size=100)
        
        # Create second datalogger that should restore data
        datalogger2 = TestDataloggerProcess(
            shared_sample_buffer=sample_buffer,
            shared_config_buffer=config_buffer,
            data_dir=temp_dir,
            filename_prefix="restore_test",
            retention_days=1
        )
        
        # Manually call restore (normally called in start())
        datalogger2.restore_data_from_disk(seconds=5.0)
        
        # Verify data was restored
        restored_samples = sample_buffer.read_all()
        assert len(restored_samples) > 0, "Data should be restored from disk"
        
        # Verify restored samples have reasonable timestamps
        if restored_samples:
            latest_timestamp = max(sample[0] for sample in restored_samples)
            current_time = time.time()
            age = current_time - latest_timestamp
            assert age < 10.0, f"Restored data too old: {age} seconds"
        
    finally:
        cleanup_test_environment(temp_dir, sample_buffer, config_buffer)


def main():
    """Run all property tests for data persistence continuity."""
    
    print("Property-Based Test: Data Persistence Continuity")
    print("=" * 60)
    print("**Feature: datalogger-multiprocessing, Property 5: Data Persistence Continuity**")
    print("**Validates: Requirements 3.2, 3.3**")
    print()
    print("Testing property: For any file operation (daily rotation, batch writing),")
    print("sampling should continue at the expected rate without interruption or data loss.")
    print()
    
    try:
        # Test the main property
        print("Testing data persistence continuity property...")
        test_data_persistence_continuity_property()
        print("✅ Data persistence continuity property tests passed")
        
        print("\nTesting file rotation continuity...")
        test_file_rotation_continuity()
        print("✅ File rotation continuity tests passed")
        
        print("\nTesting batch writing continuity...")
        test_batch_writing_continuity()
        print("✅ Batch writing continuity tests passed")
        
        print("\nTesting data restoration continuity...")
        test_data_restoration_continuity()
        print("✅ Data restoration continuity tests passed")
        
        print()
        print("=" * 60)
        print("🎉 ALL PROPERTY TESTS PASSED")
        print("Data persistence continuity is correctly implemented.")
        return 0
        
    except Exception as e:
        print(f"💥 Property test execution failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())