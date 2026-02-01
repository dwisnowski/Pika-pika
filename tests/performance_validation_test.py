#!/usr/bin/env python3
"""
Performance validation test for the multiprocessing datalogger architecture.

This test validates system performance under load conditions to ensure
the multiprocessing architecture meets performance requirements.
"""

import time
import logging
import threading
import statistics
from typing import List, Dict, Any
import psutil
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PerformanceValidator:
    """Performance validation test suite."""
    
    def __init__(self):
        """Initialize performance validator."""
        self.results: Dict[str, Any] = {}
    
    def test_shared_memory_performance(self) -> Dict[str, Any]:
        """Test shared memory buffer performance under load."""
        try:
            logger.info("Testing shared memory performance...")
            
            from pika.shared_memory import SharedSampleBuffer
            
            # Create buffer
            buffer = SharedSampleBuffer(size=6000, create=True, name="perf_test")
            
            # Test write performance
            start_time = time.time()
            sample_count = 1000
            
            for i in range(sample_count):
                timestamp = time.time()
                value = float(i % 100)
                buffer.write_sample(timestamp, value)
            
            write_duration = time.time() - start_time
            write_rate = sample_count / write_duration
            
            # Test read performance
            start_time = time.time()
            read_count = 100
            
            for _ in range(read_count):
                recent = buffer.read_recent(1.0)
            
            read_duration = time.time() - start_time
            read_rate = read_count / read_duration
            
            # Test concurrent access
            write_times = []
            read_times = []
            
            def writer():
                for i in range(100):
                    start = time.time()
                    buffer.write_sample(time.time(), float(i))
                    write_times.append(time.time() - start)
            
            def reader():
                for _ in range(100):
                    start = time.time()
                    buffer.read_recent(0.5)
                    read_times.append(time.time() - start)
            
            # Run concurrent threads
            write_thread = threading.Thread(target=writer)
            read_thread = threading.Thread(target=reader)
            
            start_time = time.time()
            write_thread.start()
            read_thread.start()
            
            write_thread.join()
            read_thread.join()
            
            concurrent_duration = time.time() - start_time
            
            # Calculate statistics
            avg_write_time = statistics.mean(write_times) * 1000  # ms
            avg_read_time = statistics.mean(read_times) * 1000   # ms
            max_write_time = max(write_times) * 1000             # ms
            max_read_time = max(read_times) * 1000               # ms
            
            buffer.cleanup()
            
            results = {
                'write_rate_hz': write_rate,
                'read_rate_hz': read_rate,
                'avg_write_time_ms': avg_write_time,
                'avg_read_time_ms': avg_read_time,
                'max_write_time_ms': max_write_time,
                'max_read_time_ms': max_read_time,
                'concurrent_duration_s': concurrent_duration,
                'meets_1ms_requirement': max_write_time < 1.0,
                'meets_100hz_requirement': write_rate > 100
            }
            
            logger.info(f"Write rate: {write_rate:.1f} Hz")
            logger.info(f"Read rate: {read_rate:.1f} Hz")
            logger.info(f"Avg write time: {avg_write_time:.3f} ms")
            logger.info(f"Max write time: {max_write_time:.3f} ms")
            logger.info(f"Meets 1ms requirement: {results['meets_1ms_requirement']}")
            logger.info(f"Meets 100Hz requirement: {results['meets_100hz_requirement']}")
            
            return results
            
        except Exception as e:
            logger.error(f"Shared memory performance test failed: {e}")
            return {'error': str(e)}
    
    def test_adc_adapter_performance(self) -> Dict[str, Any]:
        """Test ADC adapter performance."""
        try:
            logger.info("Testing ADC adapter performance...")
            
            from pika.adapters.adc_adapter import create_adc_adapter
            
            # Test mock adapter performance
            adapter = create_adc_adapter('mock', {})
            adapter.initialize({})
            
            # Measure sample reading performance
            sample_count = 1000
            start_time = time.time()
            
            samples = []
            for _ in range(sample_count):
                sample = adapter.read_sample()
                samples.append(sample)
            
            duration = time.time() - start_time
            sample_rate = sample_count / duration
            
            # Measure timing consistency
            timing_samples = []
            for _ in range(100):
                start = time.time()
                adapter.read_sample()
                timing_samples.append(time.time() - start)
            
            avg_sample_time = statistics.mean(timing_samples) * 1000  # ms
            max_sample_time = max(timing_samples) * 1000             # ms
            std_sample_time = statistics.stdev(timing_samples) * 1000 # ms
            
            adapter.cleanup()
            
            results = {
                'sample_rate_hz': sample_rate,
                'avg_sample_time_ms': avg_sample_time,
                'max_sample_time_ms': max_sample_time,
                'std_sample_time_ms': std_sample_time,
                'meets_100hz_requirement': sample_rate > 100,
                'low_jitter': std_sample_time < 0.1
            }
            
            logger.info(f"ADC sample rate: {sample_rate:.1f} Hz")
            logger.info(f"Avg sample time: {avg_sample_time:.3f} ms")
            logger.info(f"Timing jitter (std): {std_sample_time:.3f} ms")
            logger.info(f"Meets 100Hz requirement: {results['meets_100hz_requirement']}")
            logger.info(f"Low jitter: {results['low_jitter']}")
            
            return results
            
        except Exception as e:
            logger.error(f"ADC adapter performance test failed: {e}")
            return {'error': str(e)}
    
    def test_system_resource_usage(self) -> Dict[str, Any]:
        """Test system resource usage."""
        try:
            logger.info("Testing system resource usage...")
            
            # Get current process info
            process = psutil.Process(os.getpid())
            
            # Measure baseline resource usage
            baseline_cpu = process.cpu_percent(interval=1.0)
            baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Create some load with shared memory operations
            from pika.shared_memory import SharedSampleBuffer, SharedAnalysisBuffer
            
            buffers = []
            for i in range(3):
                buffer = SharedSampleBuffer(size=1000, create=True, name=f"load_test_{i}")
                buffers.append(buffer)
                
                # Generate some load
                for j in range(100):
                    buffer.write_sample(time.time(), float(j))
            
            # Measure resource usage under load
            load_cpu = process.cpu_percent(interval=1.0)
            load_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Get system-wide resource info
            system_cpu = psutil.cpu_percent(interval=1.0)
            system_memory = psutil.virtual_memory()
            
            # Cleanup
            for buffer in buffers:
                buffer.cleanup()
            
            results = {
                'baseline_cpu_percent': baseline_cpu,
                'baseline_memory_mb': baseline_memory,
                'load_cpu_percent': load_cpu,
                'load_memory_mb': load_memory,
                'system_cpu_percent': system_cpu,
                'system_memory_percent': system_memory.percent,
                'system_memory_available_gb': system_memory.available / 1024 / 1024 / 1024,
                'meets_memory_requirement': load_memory < (system_memory.total / 1024 / 1024 * 0.5),  # < 50% of total
                'cpu_cores': psutil.cpu_count()
            }
            
            logger.info(f"CPU usage: {load_cpu:.1f}% (baseline: {baseline_cpu:.1f}%)")
            logger.info(f"Memory usage: {load_memory:.1f} MB (baseline: {baseline_memory:.1f} MB)")
            logger.info(f"System CPU: {system_cpu:.1f}%")
            logger.info(f"System memory: {system_memory.percent:.1f}%")
            logger.info(f"Available memory: {results['system_memory_available_gb']:.1f} GB")
            logger.info(f"CPU cores: {results['cpu_cores']}")
            logger.info(f"Meets memory requirement: {results['meets_memory_requirement']}")
            
            return results
            
        except Exception as e:
            logger.error(f"System resource usage test failed: {e}")
            return {'error': str(e)}
    
    def test_configuration_performance(self) -> Dict[str, Any]:
        """Test configuration management performance."""
        try:
            logger.info("Testing configuration performance...")
            
            from pika.shared_memory import SharedConfigBuffer
            
            # Create config buffer
            config_buffer = SharedConfigBuffer(create=True, name="config_perf_test")
            
            # Test configuration update performance
            test_configs = []
            for i in range(100):
                config = {
                    'sample_hz': 100 + i,
                    'batch_size': 10 + i,
                    'analysis_config': {
                        'threshold': 0.1 + i * 0.01,
                        'window_size': 100 + i
                    }
                }
                test_configs.append(config)
            
            # Measure update performance
            start_time = time.time()
            for config in test_configs:
                config_buffer.update_config(config)
            
            update_duration = time.time() - start_time
            update_rate = len(test_configs) / update_duration
            
            # Measure read performance
            start_time = time.time()
            for _ in range(100):
                config, version = config_buffer.get_config()
            
            read_duration = time.time() - start_time
            read_rate = 100 / read_duration
            
            config_buffer.cleanup()
            
            results = {
                'config_update_rate_hz': update_rate,
                'config_read_rate_hz': read_rate,
                'update_duration_s': update_duration,
                'read_duration_s': read_duration,
                'fast_updates': update_rate > 10,
                'fast_reads': read_rate > 100
            }
            
            logger.info(f"Config update rate: {update_rate:.1f} Hz")
            logger.info(f"Config read rate: {read_rate:.1f} Hz")
            logger.info(f"Fast updates: {results['fast_updates']}")
            logger.info(f"Fast reads: {results['fast_reads']}")
            
            return results
            
        except Exception as e:
            logger.error(f"Configuration performance test failed: {e}")
            return {'error': str(e)}
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all performance validation tests."""
        logger.info("Starting performance validation tests...")
        
        tests = [
            ("shared_memory", self.test_shared_memory_performance),
            ("adc_adapter", self.test_adc_adapter_performance),
            ("system_resources", self.test_system_resource_usage),
            ("configuration", self.test_configuration_performance),
        ]
        
        results = {}
        
        for test_name, test_method in tests:
            logger.info(f"\n--- {test_name.upper()} Performance Test ---")
            try:
                results[test_name] = test_method()
            except Exception as e:
                logger.error(f"Performance test {test_name} failed: {e}")
                results[test_name] = {'error': str(e)}
        
        return results
    
    def print_summary(self, results: Dict[str, Any]) -> None:
        """Print performance test summary."""
        logger.info("\n" + "="*60)
        logger.info("PERFORMANCE VALIDATION SUMMARY")
        logger.info("="*60)
        
        # Check key performance indicators
        performance_checks = []
        
        # Shared memory performance
        if 'shared_memory' in results and 'error' not in results['shared_memory']:
            sm = results['shared_memory']
            performance_checks.append(("Write latency < 1ms", sm.get('meets_1ms_requirement', False)))
            performance_checks.append(("Write rate > 100Hz", sm.get('meets_100hz_requirement', False)))
        
        # ADC adapter performance
        if 'adc_adapter' in results and 'error' not in results['adc_adapter']:
            adc = results['adc_adapter']
            performance_checks.append(("ADC rate > 100Hz", adc.get('meets_100hz_requirement', False)))
            performance_checks.append(("Low timing jitter", adc.get('low_jitter', False)))
        
        # System resources
        if 'system_resources' in results and 'error' not in results['system_resources']:
            sys_res = results['system_resources']
            performance_checks.append(("Memory usage < 50%", sys_res.get('meets_memory_requirement', False)))
        
        # Configuration performance
        if 'configuration' in results and 'error' not in results['configuration']:
            config = results['configuration']
            performance_checks.append(("Fast config updates", config.get('fast_updates', False)))
            performance_checks.append(("Fast config reads", config.get('fast_reads', False)))
        
        # Print results
        passed_checks = sum(1 for _, passed in performance_checks if passed)
        total_checks = len(performance_checks)
        
        logger.info(f"Performance checks: {passed_checks}/{total_checks} passed")
        
        for check_name, passed in performance_checks:
            status = "✓ PASS" if passed else "✗ FAIL"
            logger.info(f"  {check_name}: {status}")
        
        if passed_checks == total_checks:
            logger.info("🚀 ALL PERFORMANCE REQUIREMENTS MET!")
        else:
            logger.warning(f"⚠️  {total_checks - passed_checks} performance requirements not met")
        
        logger.info("="*60)


def main():
    """Main entry point for performance validation."""
    validator = PerformanceValidator()
    
    try:
        # Run all performance tests
        results = validator.run_all_tests()
        
        # Print summary
        validator.print_summary(results)
        
        # Return appropriate exit code
        has_errors = any('error' in result for result in results.values() if isinstance(result, dict))
        return 1 if has_errors else 0
        
    except KeyboardInterrupt:
        logger.info("Performance validation interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Performance validation failed: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())