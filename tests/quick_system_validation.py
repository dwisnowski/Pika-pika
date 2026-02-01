#!/usr/bin/env python3
"""
Quick system validation for the multiprocessing datalogger architecture.
"""

import logging
import time
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_imports():
    """Test critical component imports."""
    try:
        logger.info("Testing imports...")
        
        # Core components
        import pika.main
        import pika.shared_memory
        import pika.process_supervisor
        import pika.datalogger_process
        import pika.event_logger_process
        import pika.config
        import pika.error_handling
        import pika.performance_optimizer
        
        # Adapters
        import pika.adapters.adc_adapter
        import pika.adapters.mock_adc_adapter
        import pika.adapters.ads1115_adapter
        
        # FastAPI app
        import pika.app
        
        logger.info("✓ All imports successful")
        return True
        
    except Exception as e:
        logger.error(f"✗ Import failed: {e}")
        return False


def test_shared_memory():
    """Test shared memory functionality."""
    try:
        logger.info("Testing shared memory...")
        
        from pika.shared_memory import SharedSampleBuffer, SharedAnalysisBuffer, SharedConfigBuffer
        
        # Test sample buffer
        sample_buffer = SharedSampleBuffer(size=100, create=True, name="test_samples")
        
        # Write test samples
        for i in range(5):
            sample_buffer.write_sample(time.time() + i, float(i))
        
        # Read samples
        recent = sample_buffer.read_recent(10.0)
        assert len(recent) == 5, f"Expected 5 samples, got {len(recent)}"
        
        # Test analysis buffer
        analysis_buffer = SharedAnalysisBuffer(create=True, name="test_analysis")
        
        # Use correct method signature
        analysis_buffer.update_metrics(
            rms=120.5,
            frequency=60.0,
            events=[]
        )
        
        metrics = analysis_buffer.get_current_analysis()
        assert metrics['rms'] == 120.5, "Analysis buffer failed"
        
        # Test config buffer
        config_buffer = SharedConfigBuffer(create=True, name="test_config")
        
        test_config = {'sample_hz': 100, 'batch_size': 10}
        config_buffer.update_config(test_config)
        
        retrieved_config, version = config_buffer.get_config()
        assert retrieved_config['sample_hz'] == 100, "Config buffer failed"
        
        # Cleanup
        sample_buffer.cleanup()
        analysis_buffer.cleanup()
        config_buffer.cleanup()
        
        logger.info("✓ Shared memory test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Shared memory test failed: {e}")
        return False


def test_adc_adapters():
    """Test ADC adapter pattern."""
    try:
        logger.info("Testing ADC adapters...")
        
        from pika.adapters.adc_adapter import create_adc_adapter
        
        # Test mock adapter
        mock_adapter = create_adc_adapter('mock', {})
        assert mock_adapter.initialize({}), "Mock adapter init failed"
        
        sample = mock_adapter.read_sample()
        assert isinstance(sample, float), "Sample reading failed"
        
        mock_adapter.cleanup()
        
        # Test hardware fallback
        ads_adapter = create_adc_adapter('ads1115', {})
        logger.info("ADS1115 adapter created (or fell back to mock)")
        
        logger.info("✓ ADC adapter test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ ADC adapter test failed: {e}")
        return False


def test_configuration():
    """Test configuration management."""
    try:
        logger.info("Testing configuration...")
        
        from pika.config import ConfigurationManager
        
        config_manager = ConfigurationManager("config.toml")
        config = config_manager.load_configuration()
        
        assert isinstance(config, dict), "Config not loaded"
        assert "pika" in config, "Missing pika section"
        
        logger.info("✓ Configuration test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Configuration test failed: {e}")
        return False


def test_fastapi_app():
    """Test FastAPI app basic functionality."""
    try:
        logger.info("Testing FastAPI app...")
        
        from pika.app import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200, f"Health endpoint failed: {response.status_code}"
        
        # Test main page
        response = client.get("/")
        assert response.status_code == 200, f"Main page failed: {response.status_code}"
        
        logger.info("✓ FastAPI app test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ FastAPI app test failed: {e}")
        return False


def main():
    """Run quick system validation."""
    logger.info("Starting quick system validation...")
    
    tests = [
        ("Imports", test_imports),
        ("Shared Memory", test_shared_memory),
        ("ADC Adapters", test_adc_adapters),
        ("Configuration", test_configuration),
        ("FastAPI App", test_fastapi_app),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n--- {test_name} Test ---")
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"✗ {test_name} test error: {e}")
            results[test_name] = False
    
    # Summary
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    logger.info(f"\n{'='*50}")
    logger.info(f"VALIDATION SUMMARY: {passed}/{total} tests passed")
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"  {test_name}: {status}")
    
    if passed == total:
        logger.info("🎉 ALL TESTS PASSED - System ready!")
        return 0
    else:
        logger.warning(f"⚠️  {total - passed} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())