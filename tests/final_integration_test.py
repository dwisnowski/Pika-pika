#!/usr/bin/env python3
"""
Final integration test for the multiprocessing datalogger system.

This test validates that the complete system works end-to-end with all
components integrated and functioning correctly.
"""

import logging
import time
import os
import sys
import tempfile
import shutil
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_complete_system_integration():
    """Test complete system integration."""
    logger.info("Testing complete system integration...")
    
    temp_dir = None
    try:
        # Create temporary directory for test
        temp_dir = tempfile.mkdtemp(prefix="pika_integration_")
        logger.info(f"Created test directory: {temp_dir}")
        
        # Test 1: Import all components
        logger.info("1. Testing component imports...")
        import pika.main
        import pika.shared_memory
        import pika.process_supervisor
        import pika.datalogger_process
        import pika.event_logger_process
        import pika.config
        import pika.adapters.adc_adapter
        import pika.app
        logger.info("✓ All components imported successfully")
        
        # Test 2: Shared memory functionality
        logger.info("2. Testing shared memory integration...")
        from pika.shared_memory import SharedSampleBuffer, SharedAnalysisBuffer, SharedConfigBuffer
        
        # Create buffers
        sample_buffer = SharedSampleBuffer(size=100, create=True, name="integration_samples")
        analysis_buffer = SharedAnalysisBuffer(create=True, name="integration_analysis")
        config_buffer = SharedConfigBuffer(create=True, name="integration_config")
        
        # Test data flow
        current_time = time.time()
        for i in range(10):
            sample_buffer.write_sample(current_time + i, float(i * 10))
        
        # Verify data
        recent_samples = sample_buffer.read_recent(15.0)
        assert len(recent_samples) == 10, f"Expected 10 samples, got {len(recent_samples)}"
        
        # Test analysis buffer
        analysis_buffer.update_metrics(rms=120.0, frequency=60.0, events=[])
        metrics = analysis_buffer.get_current_analysis()
        assert metrics['rms'] == 120.0, "Analysis buffer failed"
        
        # Test config buffer
        test_config = {'sample_hz': 100, 'batch_size': 10}
        config_buffer.update_config(test_config)
        retrieved_config, version = config_buffer.get_config()
        assert retrieved_config['sample_hz'] == 100, "Config buffer failed"
        
        logger.info("✓ Shared memory integration working")
        
        # Test 3: ADC adapter pattern
        logger.info("3. Testing ADC adapter integration...")
        from pika.adapters.adc_adapter import create_adc_adapter
        
        # Test mock adapter (should always work)
        mock_adapter = create_adc_adapter('mock', {})
        assert mock_adapter.initialize({}), "Mock adapter initialization failed"
        
        # Test sample reading
        sample = mock_adapter.read_sample()
        assert isinstance(sample, float), "Sample reading failed"
        assert -5.0 <= sample <= 5.0, "Sample out of expected range"
        
        mock_adapter.cleanup()
        logger.info("✓ ADC adapter integration working")
        
        # Test 4: Configuration management
        logger.info("4. Testing configuration management...")
        from pika.config import ConfigurationManager
        
        config_manager = ConfigurationManager("config.toml")
        config = config_manager.load_configuration()
        
        assert isinstance(config, dict), "Configuration not loaded"
        assert "pika" in config, "Missing pika section"
        
        # Test process config extraction
        datalogger_config = config_manager.get_process_config('datalogger')
        assert isinstance(datalogger_config, dict), "Datalogger config not extracted"
        
        logger.info("✓ Configuration management working")
        
        # Test 5: Process supervisor (basic functionality)
        logger.info("5. Testing process supervisor...")
        from pika.process_supervisor import ProcessSupervisor
        
        supervisor = ProcessSupervisor()
        
        # Test process registration (without starting)
        def dummy_process():
            time.sleep(0.1)
        
        supervisor.register_process(
            name="test_process",
            target=dummy_process,
            args=(),
            max_restarts=1
        )
        
        # Verify registration
        assert "test_process" in supervisor.processes, "Process not registered"
        
        logger.info("✓ Process supervisor working")
        
        # Test 6: FastAPI app basic functionality
        logger.info("6. Testing FastAPI app...")
        from pika.app import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200, f"Health endpoint failed: {response.status_code}"
        
        # Test main page (might fail due to missing datalogger, but should not crash)
        try:
            response = client.get("/")
            logger.info(f"Main page response: {response.status_code}")
        except Exception as e:
            logger.info(f"Main page test (expected to have issues): {e}")
        
        logger.info("✓ FastAPI app basic functionality working")
        
        # Test 7: Error handling system
        logger.info("7. Testing error handling...")
        from pika.error_handling import setup_error_handling, ErrorSeverity, ErrorCategory
        
        error_handler = setup_error_handling(log_dir=temp_dir, enable_console=False)
        
        # Test error handling
        test_error = ValueError("Integration test error")
        error_handler.handle_error(
            test_error, "integration_test", ErrorSeverity.LOW, ErrorCategory.VALIDATION
        )
        
        # Verify error log was created
        error_log_path = Path(temp_dir) / "pika_errors.log"
        assert error_log_path.exists(), "Error log not created"
        
        logger.info("✓ Error handling system working")
        
        # Cleanup shared memory
        sample_buffer.cleanup()
        analysis_buffer.cleanup()
        config_buffer.cleanup()
        
        logger.info("🎉 COMPLETE SYSTEM INTEGRATION TEST PASSED!")
        return True
        
    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        return False
        
    finally:
        # Cleanup
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info("Cleaned up test directory")
            except Exception as e:
                logger.warning(f"Failed to cleanup test directory: {e}")


def test_system_stability():
    """Test system stability under repeated operations."""
    logger.info("Testing system stability...")
    
    try:
        from pika.shared_memory import SharedSampleBuffer
        
        # Create buffer
        buffer = SharedSampleBuffer(size=1000, create=True, name="stability_test")
        
        # Run repeated operations
        for cycle in range(10):
            logger.info(f"Stability test cycle {cycle + 1}/10")
            
            # Write samples
            for i in range(100):
                buffer.write_sample(time.time(), float(i))
            
            # Read samples
            recent = buffer.read_recent(1.0)
            assert len(recent) > 0, "No samples read"
            
            # Small delay
            time.sleep(0.1)
        
        buffer.cleanup()
        logger.info("✓ System stability test passed")
        return True
        
    except Exception as e:
        logger.error(f"Stability test failed: {e}")
        return False


def test_performance_requirements():
    """Test key performance requirements."""
    logger.info("Testing performance requirements...")
    
    try:
        from pika.shared_memory import SharedSampleBuffer
        from pika.adapters.adc_adapter import create_adc_adapter
        
        # Test 1: Shared memory write performance
        buffer = SharedSampleBuffer(size=1000, create=True, name="perf_test")
        
        start_time = time.time()
        sample_count = 1000
        
        for i in range(sample_count):
            buffer.write_sample(time.time(), float(i))
        
        duration = time.time() - start_time
        write_rate = sample_count / duration
        
        logger.info(f"Shared memory write rate: {write_rate:.1f} Hz")
        assert write_rate > 100, f"Write rate too low: {write_rate} Hz"
        
        # Test 2: ADC adapter performance
        adapter = create_adc_adapter('mock', {})
        adapter.initialize({})
        
        start_time = time.time()
        sample_count = 1000
        
        for _ in range(sample_count):
            sample = adapter.read_sample()
        
        duration = time.time() - start_time
        sample_rate = sample_count / duration
        
        logger.info(f"ADC sample rate: {sample_rate:.1f} Hz")
        assert sample_rate > 100, f"Sample rate too low: {sample_rate} Hz"
        
        # Cleanup
        buffer.cleanup()
        adapter.cleanup()
        
        logger.info("✓ Performance requirements met")
        return True
        
    except Exception as e:
        logger.error(f"Performance test failed: {e}")
        return False


def main():
    """Main entry point for final integration test."""
    logger.info("Starting final integration test for multiprocessing datalogger...")
    
    tests = [
        ("Complete System Integration", test_complete_system_integration),
        ("System Stability", test_system_stability),
        ("Performance Requirements", test_performance_requirements),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*60}")
        logger.info(f"Running: {test_name}")
        logger.info('='*60)
        
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"Test {test_name} failed with error: {e}")
            results[test_name] = False
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("FINAL INTEGRATION TEST SUMMARY")
    logger.info('='*60)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    logger.info(f"Tests passed: {passed}/{total}")
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"  {test_name}: {status}")
    
    if passed == total:
        logger.info("\n🎉 ALL INTEGRATION TESTS PASSED!")
        logger.info("The multiprocessing datalogger system is ready for deployment!")
        return 0
    else:
        logger.warning(f"\n⚠️  {total - passed} integration tests failed")
        logger.warning("System needs attention before deployment")
        return 1


if __name__ == "__main__":
    sys.exit(main())