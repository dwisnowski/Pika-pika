#!/usr/bin/env python3
"""
Simple Multiprocessing Test

A simplified version of the integration test to verify basic functionality
without complex dependencies like WebSocket and HTTP servers.
"""

import sys
import os
import time
import logging
from multiprocessing import Process

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pika.shared_memory import SharedSampleBuffer, SharedAnalysisBuffer, SharedConfigBuffer
from pika.process_supervisor import ProcessSupervisor
from pika.adapters import create_adc_adapter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_shared_memory():
    """Test basic shared memory functionality."""
    logger.info("🔍 Testing shared memory...")
    
    try:
        # Test SharedSampleBuffer
        sample_buffer = SharedSampleBuffer(size=100, create=True)
        
        # Write some test data
        base_time = time.time()
        for i in range(10):
            sample_buffer.write_sample(base_time + i * 0.01, float(i))
        
        # Read data back
        samples = sample_buffer.read_all()
        if len(samples) != 10:
            logger.error(f"❌ Expected 10 samples, got {len(samples)}")
            return False
        
        # Test SharedAnalysisBuffer
        analysis_buffer = SharedAnalysisBuffer(create=True)
        analysis_buffer.update_metrics(rms=120.0, frequency=60.0, events=[])
        
        analysis = analysis_buffer.get_current_analysis()
        if analysis['rms'] != 120.0:
            logger.error(f"❌ Expected RMS 120.0, got {analysis['rms']}")
            return False
        
        # Test SharedConfigBuffer
        config_buffer = SharedConfigBuffer(create=True)
        test_config = {'sample_hz': 100, 'batch_size': 50}
        version = config_buffer.update_config(test_config)
        
        config, read_version = config_buffer.get_config()
        if config['sample_hz'] != 100 or read_version != version:
            logger.error(f"❌ Config test failed: {config}, version {read_version}")
            return False
        
        # Cleanup
        sample_buffer.cleanup()
        analysis_buffer.cleanup()
        config_buffer.cleanup()
        
        logger.info("✅ Shared memory tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Shared memory test failed: {e}")
        return False


def test_adc_adapters():
    """Test ADC adapter functionality."""
    logger.info("🔍 Testing ADC adapters...")
    
    try:
        # Test MockADC
        mock_adapter = create_adc_adapter('mock', {'signal_type': 'sine'})
        
        if not mock_adapter:
            logger.error("❌ Failed to create mock adapter")
            return False
        
        # Test sample reading
        sample = mock_adapter.read_sample()
        if not isinstance(sample, (int, float)):
            logger.error(f"❌ Invalid sample type: {type(sample)}")
            return False
        
        # Test sample rate setting
        if not mock_adapter.set_sample_rate(100):
            logger.error("❌ Failed to set sample rate")
            return False
        
        mock_adapter.cleanup()
        
        logger.info("✅ ADC adapter tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ ADC adapter test failed: {e}")
        return False


def simple_datalogger_process(shared_sample_buffer, shared_config_buffer, duration=5):
    """Simple datalogger process for testing."""
    try:
        # Create mock ADC
        adc = create_adc_adapter('mock', {'signal_type': 'sine', 'frequency': 60.0})
        
        # Sample for specified duration
        start_time = time.time()
        sample_count = 0
        
        while time.time() - start_time < duration:
            timestamp = time.time()
            value = adc.read_sample()
            
            # Write to shared memory
            shared_sample_buffer.write_sample(timestamp, value)
            sample_count += 1
            
            time.sleep(0.01)  # 100Hz sampling
        
        logger.info(f"Datalogger process completed: {sample_count} samples")
        adc.cleanup()
        
    except Exception as e:
        logger.error(f"Datalogger process error: {e}")


def test_basic_multiprocessing():
    """Test basic multiprocessing with shared memory."""
    logger.info("🔍 Testing basic multiprocessing...")
    
    try:
        # Create shared memory
        sample_buffer = SharedSampleBuffer(size=1000, create=True)
        config_buffer = SharedConfigBuffer(create=True)
        
        # Initialize config
        config_buffer.update_config({'sample_hz': 100, 'batch_size': 10})
        
        # Start datalogger process
        datalogger_proc = Process(
            target=simple_datalogger_process,
            args=(sample_buffer, config_buffer, 3),  # Run for 3 seconds
            name="TestDatalogger"
        )
        
        datalogger_proc.start()
        
        # Monitor the process
        time.sleep(1.0)  # Let it start
        
        if not datalogger_proc.is_alive():
            logger.error("❌ Datalogger process died")
            return False
        
        # Check if data is being written
        samples = sample_buffer.read_recent(1.0)
        if len(samples) < 50:  # Should have ~100 samples at 100Hz
            logger.error(f"❌ Insufficient samples: {len(samples)}")
            return False
        
        # Wait for process to complete
        datalogger_proc.join(timeout=5.0)
        
        if datalogger_proc.is_alive():
            logger.error("❌ Datalogger process did not complete")
            datalogger_proc.terminate()
            return False
        
        # Check final sample count
        final_samples = sample_buffer.read_all()
        logger.info(f"Final sample count: {len(final_samples)}")
        
        if len(final_samples) < 200:  # Should have ~300 samples over 3 seconds
            logger.error(f"❌ Too few final samples: {len(final_samples)}")
            return False
        
        # Cleanup
        sample_buffer.cleanup()
        config_buffer.cleanup()
        
        logger.info("✅ Basic multiprocessing tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Basic multiprocessing test failed: {e}")
        return False


def test_process_supervisor():
    """Test process supervisor functionality."""
    logger.info("🔍 Testing process supervisor...")
    
    try:
        supervisor = ProcessSupervisor(heartbeat_interval=0.1)
        
        # Define a simple test function
        def test_process_func():
            time.sleep(0.5)
        
        # Register and start a process
        supervisor.register_process("test_proc", test_process_func)
        
        if not supervisor.start_process("test_proc"):
            logger.error("❌ Failed to start test process")
            return False
        
        # Check status
        status = supervisor.get_process_status("test_proc")
        if not status or status['state'] != 'running':
            logger.error(f"❌ Process not running: {status}")
            return False
        
        # Wait for completion
        time.sleep(1.0)
        
        # Stop the process
        if not supervisor.stop_process("test_proc"):
            logger.error("❌ Failed to stop test process")
            return False
        
        supervisor.cleanup()
        
        logger.info("✅ Process supervisor tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Process supervisor test failed: {e}")
        return False


def main():
    """Run all simple tests."""
    print("=" * 60)
    print("🔧 SIMPLE MULTIPROCESSING TEST")
    print("=" * 60)
    print()
    
    tests = [
        ("Shared Memory", test_shared_memory),
        ("ADC Adapters", test_adc_adapters),
        ("Process Supervisor", test_process_supervisor),
        ("Basic Multiprocessing", test_basic_multiprocessing),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"Running {test_name} test...")
        results[test_name] = test_func()
        print()
    
    print("=" * 60)
    print("📊 TEST RESULTS")
    print("=" * 60)
    
    passed = 0
    total = len(tests)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print()
    print(f"Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("💥 SOME TESTS FAILED!")
        return 1


if __name__ == "__main__":
    sys.exit(main())