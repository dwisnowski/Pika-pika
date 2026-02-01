#!/usr/bin/env python3
"""
Core Infrastructure Verification Script

This script systematically verifies that all core infrastructure components
are working correctly before proceeding with the multiprocessing implementation.

Components verified:
1. Shared memory structures (SharedSampleBuffer, SharedAnalysisBuffer, SharedConfigBuffer)
2. Process supervisor (ProcessSupervisor)
3. ADC adapter pattern (ADS1115Adapter, MockADCAdapter)
"""

import sys
import os
import time
import threading
import logging
from typing import Dict, List, Any

# Add the parent directory to Python path to import pika modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pika.shared_memory import SharedSampleBuffer, SharedAnalysisBuffer, SharedConfigBuffer
from pika.process_supervisor import ProcessSupervisor, ProcessState
from pika.adapters import create_adc_adapter, MockADCAdapter, ADS1115Adapter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _test_process_function():
    """Test process function that can be pickled."""
    time.sleep(0.2)


def _quick_process_function():
    """Quick test process function that can be pickled."""
    time.sleep(0.1)


class InfrastructureVerifier:
    """Comprehensive verification of core infrastructure components."""
    
    def __init__(self):
        self.results = {}
        self.cleanup_tasks = []
    
    def verify_shared_memory_structures(self) -> bool:
        """Verify all shared memory structures work correctly."""
        logger.info("🔍 Verifying shared memory structures...")
        
        try:
            # Test SharedSampleBuffer
            sample_buffer_ok = self._verify_sample_buffer()
            
            # Test SharedAnalysisBuffer
            analysis_buffer_ok = self._verify_analysis_buffer()
            
            # Test SharedConfigBuffer
            config_buffer_ok = self._verify_config_buffer()
            
            success = sample_buffer_ok and analysis_buffer_ok and config_buffer_ok
            self.results['shared_memory'] = {
                'success': success,
                'sample_buffer': sample_buffer_ok,
                'analysis_buffer': analysis_buffer_ok,
                'config_buffer': config_buffer_ok
            }
            
            if success:
                logger.info("✅ Shared memory structures verification PASSED")
            else:
                logger.error("❌ Shared memory structures verification FAILED")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Shared memory verification failed with exception: {e}")
            self.results['shared_memory'] = {'success': False, 'error': str(e)}
            return False
    
    def _verify_sample_buffer(self) -> bool:
        """Verify SharedSampleBuffer functionality."""
        logger.info("  Testing SharedSampleBuffer...")
        
        buffer = None
        try:
            # Create buffer
            buffer = SharedSampleBuffer(size=10)
            self.cleanup_tasks.append(lambda: buffer.cleanup())
            
            # Test basic write/read
            base_time = time.time()
            for i in range(5):
                buffer.write_sample(base_time + i * 0.01, float(i))
            
            # Verify data
            samples = buffer.read_all()
            if len(samples) != 5:
                logger.error(f"    Expected 5 samples, got {len(samples)}")
                return False
            
            # Test circular behavior (write more than buffer size)
            for i in range(15):  # Write 15 more samples (total 20, buffer size 10)
                buffer.write_sample(base_time + (5 + i) * 0.01, float(5 + i))
            
            samples = buffer.read_all()
            if len(samples) != 10:  # Should be capped at buffer size
                logger.error(f"    Expected 10 samples after overflow, got {len(samples)}")
                return False
            
            # Should contain the last 10 samples (10-19)
            expected_values = list(range(10, 20))
            actual_values = [int(sample[1]) for sample in samples]
            if actual_values != expected_values:
                logger.error(f"    Expected values {expected_values}, got {actual_values}")
                return False
            
            # Test buffer info
            info = buffer.get_buffer_info()
            if info['count'] != 10 or info['size'] != 10:
                logger.error(f"    Buffer info incorrect: {info}")
                return False
            
            logger.info("    ✅ SharedSampleBuffer tests passed")
            return True
            
        except Exception as e:
            logger.error(f"    ❌ SharedSampleBuffer test failed: {e}")
            return False
    
    def _verify_analysis_buffer(self) -> bool:
        """Verify SharedAnalysisBuffer functionality."""
        logger.info("  Testing SharedAnalysisBuffer...")
        
        buffer = None
        try:
            # Create buffer
            buffer = SharedAnalysisBuffer(size=1024)
            self.cleanup_tasks.append(lambda: buffer.cleanup())
            
            # Test metrics update
            test_events = [{'type': 'sag', 'value': 0.8, 'duration': 0.1}]
            buffer.update_metrics(rms=120.5, frequency=59.8, events=test_events)
            
            # Verify data retrieval
            analysis = buffer.get_current_analysis()
            if analysis['rms'] != 120.5:
                logger.error(f"    Expected RMS 120.5, got {analysis['rms']}")
                return False
            
            if analysis['frequency'] != 59.8:
                logger.error(f"    Expected frequency 59.8, got {analysis['frequency']}")
                return False
            
            if len(analysis['sags_swells']) != 1:
                logger.error(f"    Expected 1 event, got {len(analysis['sags_swells'])}")
                return False
            
            # Test freshness
            if not buffer.is_data_fresh():
                logger.error("    Data should be fresh after recent update")
                return False
            
            # Test buffer info
            info = buffer.get_buffer_info()
            if info['size'] != 1024:
                logger.error(f"    Buffer size incorrect: {info}")
                return False
            
            logger.info("    ✅ SharedAnalysisBuffer tests passed")
            return True
            
        except Exception as e:
            logger.error(f"    ❌ SharedAnalysisBuffer test failed: {e}")
            return False
    
    def _verify_config_buffer(self) -> bool:
        """Verify SharedConfigBuffer functionality."""
        logger.info("  Testing SharedConfigBuffer...")
        
        buffer = None
        try:
            # Create buffer
            buffer = SharedConfigBuffer(size=2048)
            self.cleanup_tasks.append(lambda: buffer.cleanup())
            
            # Test initial config
            config, version = buffer.get_config()
            if version != 0:
                logger.error(f"    Expected initial version 0, got {version}")
                return False
            
            # Test config update
            new_config = {
                'sample_hz': 200,
                'batch_size': 150,
                'analysis_config': {'test': 'value'}
            }
            new_version = buffer.update_config(new_config)
            if new_version != 1:
                logger.error(f"    Expected version 1 after update, got {new_version}")
                return False
            
            # Verify updated config
            config, version = buffer.get_config()
            if config['sample_hz'] != 200:
                logger.error(f"    Expected sample_hz 200, got {config['sample_hz']}")
                return False
            
            if version != 1:
                logger.error(f"    Expected version 1, got {version}")
                return False
            
            # Test change detection
            if not buffer.has_changed(0):
                logger.error("    Should detect change from version 0")
                return False
            
            if buffer.has_changed(1):
                logger.error("    Should not detect change from current version")
                return False
            
            logger.info("    ✅ SharedConfigBuffer tests passed")
            return True
            
        except Exception as e:
            logger.error(f"    ❌ SharedConfigBuffer test failed: {e}")
            return False
    
    def verify_process_supervisor(self) -> bool:
        """Verify ProcessSupervisor functionality."""
        logger.info("🔍 Verifying process supervisor...")
        
        supervisor = None
        try:
            supervisor = ProcessSupervisor(heartbeat_interval=0.1, restart_delay=0.1)
            self.cleanup_tasks.append(lambda: supervisor.cleanup())
            
            # Test process registration with a module-level function
            supervisor.register_process(
                name="test_process",
                target=_test_process_function,
                max_restarts=1
            )
            
            # Test process start
            if not supervisor.start_process("test_process"):
                logger.error("    Failed to start test process")
                return False
            
            # Verify process is running
            status = supervisor.get_process_status("test_process")
            if status['state'] != ProcessState.RUNNING.value:
                logger.error(f"    Expected RUNNING state, got {status['state']}")
                return False
            
            # Wait for process to complete
            time.sleep(0.3)
            
            # Test process stop
            if not supervisor.stop_process("test_process", timeout=1.0):
                logger.error("    Failed to stop test process")
                return False
            
            # Test multiple processes
            supervisor.register_process("quick1", _quick_process_function)
            supervisor.register_process("quick2", _quick_process_function)
            
            if not supervisor.start_process("quick1"):
                logger.error("    Failed to start quick1")
                return False
            
            if not supervisor.start_process("quick2"):
                logger.error("    Failed to start quick2")
                return False
            
            # Test status retrieval
            all_status = supervisor.get_all_status()
            if len(all_status) != 3:  # test_process, quick1, quick2
                logger.error(f"    Expected 3 processes in status, got {len(all_status)}")
                return False
            
            # Test graceful shutdown
            supervisor.graceful_shutdown(timeout=2.0)
            
            self.results['process_supervisor'] = {'success': True}
            logger.info("✅ Process supervisor verification PASSED")
            return True
            
        except Exception as e:
            logger.error(f"❌ Process supervisor verification failed: {e}")
            self.results['process_supervisor'] = {'success': False, 'error': str(e)}
            return False
    
    def verify_adc_adapters(self) -> bool:
        """Verify ADC adapter pattern with both real and mock hardware."""
        logger.info("🔍 Verifying ADC adapter pattern...")
        
        try:
            # Test MockADC adapter (should always work)
            mock_ok = self._verify_mock_adc()
            
            # Test ADS1115 adapter (will fall back to MockADC without hardware)
            hardware_ok = self._verify_hardware_adc()
            
            success = mock_ok and hardware_ok
            self.results['adc_adapters'] = {
                'success': success,
                'mock_adapter': mock_ok,
                'hardware_adapter': hardware_ok
            }
            
            if success:
                logger.info("✅ ADC adapter verification PASSED")
            else:
                logger.error("❌ ADC adapter verification FAILED")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ ADC adapter verification failed: {e}")
            self.results['adc_adapters'] = {'success': False, 'error': str(e)}
            return False
    
    def _verify_mock_adc(self) -> bool:
        """Verify MockADC adapter functionality."""
        logger.info("  Testing MockADC adapter...")
        
        adapter = None
        try:
            # Test different signal types
            configs = [
                {'signal_type': 'dc', 'dc_offset': 5.0},
                {'signal_type': 'sine', 'frequency': 60.0, 'amplitude': 1.0},
                {'signal_type': 'ac', 'frequency': 50.0},
                {}  # Default config
            ]
            
            for i, config in enumerate(configs):
                adapter = create_adc_adapter('mock', config)
                self.cleanup_tasks.append(lambda a=adapter: a.cleanup())
                
                # Verify it's MockADC
                if not isinstance(adapter, MockADCAdapter):
                    logger.error(f"    Config {i}: Expected MockADCAdapter, got {type(adapter)}")
                    return False
                
                if adapter.is_hardware:
                    logger.error(f"    Config {i}: MockADC should report is_hardware=False")
                    return False
                
                # Test sample reading
                sample = adapter.read_sample()
                if not isinstance(sample, (int, float)):
                    logger.error(f"    Config {i}: Invalid sample type {type(sample)}")
                    return False
                
                # Test sample rate setting
                if not adapter.set_sample_rate(100):
                    logger.error(f"    Config {i}: Failed to set sample rate")
                    return False
                
                adapter.cleanup()
            
            logger.info("    ✅ MockADC adapter tests passed")
            return True
            
        except Exception as e:
            logger.error(f"    ❌ MockADC adapter test failed: {e}")
            return False
    
    def _verify_hardware_adc(self) -> bool:
        """Verify ADS1115 adapter (with fallback to MockADC)."""
        logger.info("  Testing ADS1115 adapter (with fallback)...")
        
        adapter = None
        try:
            # Try to create ADS1115 adapter (will fall back to MockADC without hardware)
            config = {'address': 0x48, 'channel': 0, 'sample_rate': 100}
            adapter = create_adc_adapter('ads1115', config)
            self.cleanup_tasks.append(lambda: adapter.cleanup())
            
            # Should have fallen back to MockADC (no hardware available)
            if isinstance(adapter, MockADCAdapter):
                logger.info("    ✅ Hardware fallback to MockADC working correctly")
                
                # Verify fallback adapter works
                if adapter.is_hardware:
                    logger.error("    Fallback adapter should report is_hardware=False")
                    return False
                
                sample = adapter.read_sample()
                if not isinstance(sample, (int, float)):
                    logger.error(f"    Fallback adapter invalid sample type: {type(sample)}")
                    return False
                
            elif isinstance(adapter, ADS1115Adapter):
                logger.info("    ✅ Real ADS1115 hardware detected and working")
                
                # Verify hardware adapter works
                if not adapter.is_hardware:
                    logger.error("    Hardware adapter should report is_hardware=True")
                    return False
                
                sample = adapter.read_sample()
                if not isinstance(sample, (int, float)):
                    logger.error(f"    Hardware adapter invalid sample type: {type(sample)}")
                    return False
            
            else:
                logger.error(f"    Unexpected adapter type: {type(adapter)}")
                return False
            
            # Test sample rate setting
            if not adapter.set_sample_rate(200):
                logger.error("    Failed to set sample rate on adapter")
                return False
            
            adapter.cleanup()
            
            logger.info("    ✅ ADS1115 adapter tests passed")
            return True
            
        except Exception as e:
            logger.error(f"    ❌ ADS1115 adapter test failed: {e}")
            return False
    
    def run_property_tests(self) -> bool:
        """Run existing property-based tests to verify correctness properties."""
        logger.info("🔍 Running property-based tests...")
        
        try:
            # Import and run existing property tests
            test_results = {}
            
            # Test circular buffer property
            logger.info("  Running circular buffer property test...")
            result = os.system("uv run python tests/test_circular_buffer_property.py > /dev/null 2>&1")
            test_results['circular_buffer'] = result == 0
            
            # Test non-blocking memory property
            logger.info("  Running non-blocking memory property test...")
            result = os.system("uv run python tests/test_nonblocking_memory_property.py > /dev/null 2>&1")
            test_results['nonblocking_memory'] = result == 0
            
            # Test process supervision property
            logger.info("  Running process supervision property test...")
            result = os.system("uv run python tests/test_process_supervision_property.py > /dev/null 2>&1")
            test_results['process_supervision'] = result == 0
            
            # Test ADC fallback property
            logger.info("  Running ADC fallback property test...")
            result = os.system("uv run python tests/test_adc_property_fallback.py > /dev/null 2>&1")
            test_results['adc_fallback'] = result == 0
            
            success = all(test_results.values())
            self.results['property_tests'] = {
                'success': success,
                'individual_results': test_results
            }
            
            if success:
                logger.info("✅ Property-based tests PASSED")
            else:
                failed_tests = [name for name, passed in test_results.items() if not passed]
                logger.error(f"❌ Property-based tests FAILED: {failed_tests}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Property test execution failed: {e}")
            self.results['property_tests'] = {'success': False, 'error': str(e)}
            return False
    
    def cleanup(self):
        """Clean up all resources created during verification."""
        logger.info("🧹 Cleaning up verification resources...")
        
        for cleanup_task in self.cleanup_tasks:
            try:
                cleanup_task()
            except Exception as e:
                logger.warning(f"Cleanup task failed: {e}")
        
        self.cleanup_tasks.clear()
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive verification report."""
        
        total_tests = 0
        passed_tests = 0
        
        report = {
            'timestamp': time.time(),
            'overall_success': True,
            'components': {},
            'summary': {}
        }
        
        for component, result in self.results.items():
            report['components'][component] = result
            
            if isinstance(result, dict) and 'success' in result:
                total_tests += 1
                if result['success']:
                    passed_tests += 1
                else:
                    report['overall_success'] = False
        
        report['summary'] = {
            'total_components': total_tests,
            'passed_components': passed_tests,
            'failed_components': total_tests - passed_tests,
            'success_rate': passed_tests / total_tests if total_tests > 0 else 0.0
        }
        
        return report


def main():
    """Main verification function."""
    
    print("=" * 80)
    print("🔧 CORE INFRASTRUCTURE VERIFICATION")
    print("=" * 80)
    print()
    print("This script verifies that all core infrastructure components")
    print("are working correctly before proceeding with multiprocessing implementation.")
    print()
    
    verifier = InfrastructureVerifier()
    
    try:
        # Run all verification tests
        shared_memory_ok = verifier.verify_shared_memory_structures()
        process_supervisor_ok = verifier.verify_process_supervisor()
        adc_adapters_ok = verifier.verify_adc_adapters()
        property_tests_ok = verifier.run_property_tests()
        
        # Generate report
        report = verifier.generate_report()
        
        print()
        print("=" * 80)
        print("📊 VERIFICATION REPORT")
        print("=" * 80)
        
        print(f"Overall Success: {'✅ PASS' if report['overall_success'] else '❌ FAIL'}")
        print(f"Components Tested: {report['summary']['total_components']}")
        print(f"Components Passed: {report['summary']['passed_components']}")
        print(f"Components Failed: {report['summary']['failed_components']}")
        print(f"Success Rate: {report['summary']['success_rate']:.1%}")
        
        print()
        print("Component Details:")
        for component, result in report['components'].items():
            status = "✅ PASS" if result.get('success', False) else "❌ FAIL"
            print(f"  {component}: {status}")
            
            if not result.get('success', False) and 'error' in result:
                print(f"    Error: {result['error']}")
        
        print()
        print("=" * 80)
        
        if report['overall_success']:
            print("🎉 ALL CORE INFRASTRUCTURE COMPONENTS VERIFIED SUCCESSFULLY!")
            print("✅ Ready to proceed with multiprocessing implementation.")
            return 0
        else:
            print("💥 CORE INFRASTRUCTURE VERIFICATION FAILED!")
            print("❌ Fix the failing components before proceeding.")
            return 1
    
    except KeyboardInterrupt:
        print("\n⚠️  Verification interrupted by user")
        return 1
    
    except Exception as e:
        print(f"\n💥 Verification failed with unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        verifier.cleanup()


if __name__ == "__main__":
    sys.exit(main())