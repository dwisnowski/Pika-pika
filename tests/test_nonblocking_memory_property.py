"""Property-based test for non-blocking memory access.

**Feature: datalogger-multiprocessing, Property 4: Non-blocking Memory Access**
**Validates: Requirements 2.2**

Property: For any concurrent read and write operations on shared memory, 
read operations should not block write operations or affect their timing consistency.
"""

import sys
import os
import time
import threading
import logging
import statistics

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pika.shared_memory import SharedSampleBuffer, SharedAnalysisBuffer, SharedConfigBuffer

# Suppress logging during tests to reduce noise
logging.getLogger('pika.shared_memory').setLevel(logging.WARNING)


def test_sample_buffer_nonblocking():
    """Test non-blocking access for SharedSampleBuffer."""
    
    buffer = SharedSampleBuffer(size=100)
    
    try:
        # Measure write timing without concurrent reads (baseline)
        baseline_times = []
        base_time = time.time()
        
        for i in range(20):
            start_time = time.perf_counter()
            buffer.write_sample(base_time + i * 0.01, float(i))
            end_time = time.perf_counter()
            baseline_times.append(end_time - start_time)
            time.sleep(0.001)
        
        # Measure write timing with concurrent reads
        concurrent_times = []
        reader_done = threading.Event()
        
        def concurrent_reader():
            for _ in range(30):
                if reader_done.is_set():
                    break
                buffer.read_recent(0.05)
                time.sleep(0.0005)
        
        # Start reader thread
        reader_thread = threading.Thread(target=concurrent_reader)
        reader_thread.start()
        
        # Perform writes while reader is active
        for i in range(20):
            start_time = time.perf_counter()
            buffer.write_sample(base_time + (20 + i) * 0.01, float(i + 100))
            end_time = time.perf_counter()
            concurrent_times.append(end_time - start_time)
            time.sleep(0.001)
        
        reader_done.set()
        reader_thread.join(timeout=2.0)
        
        # Compare timing
        baseline_avg = statistics.mean(baseline_times)
        concurrent_avg = statistics.mean(concurrent_times)
        
        # Property 1: Concurrent writes should not be excessively slower
        assert concurrent_avg <= baseline_avg * 5.0, \
            f"Concurrent writes too slow: {concurrent_avg:.6f}s vs baseline {baseline_avg:.6f}s"
        
        # Property 2: All operations should be reasonably fast
        assert baseline_avg < 0.01, f"Baseline writes too slow: {baseline_avg:.6f}s"
        assert concurrent_avg < 0.05, f"Concurrent writes too slow: {concurrent_avg:.6f}s"
        
        # Property 3: No operation should take excessively long
        assert max(baseline_times + concurrent_times) < 0.1, \
            f"Some operations too slow: max={max(baseline_times + concurrent_times):.6f}s"
        
    finally:
        buffer.cleanup()


def test_analysis_buffer_nonblocking():
    """Test non-blocking access for SharedAnalysisBuffer."""
    
    buffer = SharedAnalysisBuffer(size=1024)
    
    try:
        # Measure write timing without concurrent reads
        write_times_solo = []
        for i in range(15):
            start_time = time.perf_counter()
            buffer.update_metrics(
                rms=100.0 + i,
                frequency=60.0 + i * 0.1,
                events=[{'type': 'test', 'value': i}]
            )
            end_time = time.perf_counter()
            write_times_solo.append(end_time - start_time)
            time.sleep(0.002)
        
        # Measure write timing with concurrent reads
        write_times_concurrent = []
        reader_done = threading.Event()
        
        def concurrent_reader():
            for _ in range(20):
                if reader_done.is_set():
                    break
                buffer.get_current_analysis()
                time.sleep(0.001)
        
        # Start reader thread
        reader_thread = threading.Thread(target=concurrent_reader)
        reader_thread.start()
        
        # Perform writes while reader is active
        for i in range(15):
            start_time = time.perf_counter()
            buffer.update_metrics(
                rms=200.0 + i,
                frequency=59.0 + i * 0.1,
                events=[{'type': 'concurrent', 'value': i}]
            )
            end_time = time.perf_counter()
            write_times_concurrent.append(end_time - start_time)
            time.sleep(0.002)
        
        reader_done.set()
        reader_thread.join(timeout=2.0)
        
        # Compare timing
        solo_avg = statistics.mean(write_times_solo)
        concurrent_avg = statistics.mean(write_times_concurrent)
        
        # Concurrent writes should not be excessively slower
        assert concurrent_avg <= solo_avg * 5.0, \
            f"Concurrent writes too slow: {concurrent_avg:.6f}s vs solo {solo_avg:.6f}s"
        
        # Both should be reasonably fast
        assert solo_avg < 0.01, f"Solo writes too slow: {solo_avg:.6f}s"
        assert concurrent_avg < 0.05, f"Concurrent writes too slow: {concurrent_avg:.6f}s"
        
    finally:
        buffer.cleanup()


def test_config_buffer_nonblocking():
    """Test non-blocking access for SharedConfigBuffer."""
    
    buffer = SharedConfigBuffer(size=2048)
    
    try:
        # Test concurrent config updates and reads
        update_times = []
        reader_done = threading.Event()
        read_results = []
        
        def concurrent_reader():
            read_times = []
            for i in range(10):
                if reader_done.is_set():
                    break
                start_time = time.perf_counter()
                config, version = buffer.get_config()
                end_time = time.perf_counter()
                read_times.append(end_time - start_time)
                time.sleep(0.003)
            
            if read_times:
                read_results.append({
                    'avg_time': statistics.mean(read_times),
                    'max_time': max(read_times),
                    'count': len(read_times)
                })
        
        # Start reader thread
        reader_thread = threading.Thread(target=concurrent_reader)
        reader_thread.start()
        
        # Perform config updates while reader is active
        for i in range(8):
            start_time = time.perf_counter()
            buffer.update_config({
                'sample_hz': 100 + i * 10,
                'batch_size': 50 + i * 5
            })
            end_time = time.perf_counter()
            update_times.append(end_time - start_time)
            time.sleep(0.004)
        
        reader_done.set()
        reader_thread.join(timeout=2.0)
        
        # Validate timing
        avg_update_time = statistics.mean(update_times)
        
        # Operations should be reasonably fast
        assert avg_update_time < 0.05, f"Config updates too slow: {avg_update_time:.6f}s"
        assert max(update_times) < 0.1, f"Slowest update: {max(update_times):.6f}s"
        
        if read_results:
            avg_read_time = read_results[0]['avg_time']
            assert avg_read_time < 0.05, f"Config reads too slow: {avg_read_time:.6f}s"
        
    finally:
        buffer.cleanup()


def main():
    """Run all property tests for non-blocking memory access."""
    
    print("Property-Based Test: Non-blocking Memory Access")
    print("=" * 60)
    print("**Feature: datalogger-multiprocessing, Property 4: Non-blocking Memory Access**")
    print("**Validates: Requirements 2.2**")
    print()
    print("Testing property: For any concurrent read and write operations")
    print("on shared memory, read operations should not block write operations")
    print("or affect their timing consistency.")
    print()
    
    try:
        # Test SharedSampleBuffer non-blocking access
        print("Testing SharedSampleBuffer non-blocking access...")
        test_sample_buffer_nonblocking()
        print("✅ SharedSampleBuffer non-blocking tests passed")
        
        print("\nTesting SharedAnalysisBuffer non-blocking access...")
        test_analysis_buffer_nonblocking()
        print("✅ SharedAnalysisBuffer non-blocking tests passed")
        
        print("\nTesting SharedConfigBuffer non-blocking access...")
        test_config_buffer_nonblocking()
        print("✅ SharedConfigBuffer non-blocking tests passed")
        
        print()
        print("=" * 60)
        print("🎉 ALL PROPERTY TESTS PASSED")
        print("Non-blocking memory access is correctly implemented.")
        return 0
        
    except Exception as e:
        print(f"💥 Property test execution failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())