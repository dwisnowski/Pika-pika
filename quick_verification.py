#!/usr/bin/env python3
"""
Quick Core Infrastructure Verification

This script performs a quick verification of core infrastructure components
without running the full property-based tests.
"""

import sys
import os
import time
import logging

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pika.shared_memory import SharedSampleBuffer, SharedAnalysisBuffer, SharedConfigBuffer
from pika.process_supervisor import ProcessSupervisor
from pika.adapters import create_adc_adapter, MockADCAdapter

# Configure logging
logging.basicConfig(level=logging.WARNING)  # Reduce noise


def simple_task():
    """Simple task function that can be pickled."""
    time.sleep(0.1)


def test_shared_memory():
    """Quick test of shared memory structures."""
    print("🔍 Testing shared memory structures...")
    
    # Test SharedSampleBuffer
    buffer = SharedSampleBuffer(size=5)
    try:
        # Write some samples
        base_time = time.time()
        for i in range(3):
            buffer.write_sample(base_time + i * 0.01, float(i))
        
        # Read them back
        samples = buffer.read_all()
        assert len(samples) == 3, f"Expected 3 samples, got {len(samples)}"
        assert samples[0][1] == 0.0, "First sample value incorrect"
        assert samples[2][1] == 2.0, "Last sample value incorrect"
        
        print("  ✅ SharedSampleBuffer working")
    finally:
        buffer.cleanup()
    
    # Test SharedAnalysisBuffer
    analysis_buffer = SharedAnalysisBuffer()
    try:
        analysis_buffer.update_metrics(120.0, 60.0, [])
        metrics = analysis_buffer.get_current_analysis()
        assert metrics['rms'] == 120.0, "RMS value incorrect"
        assert metrics['frequency'] == 60.0, "Frequency value incorrect"
        
        print("  ✅ SharedAnalysisBuffer working")
    finally:
        analysis_buffer.cleanup()
    
    # Test SharedConfigBuffer
    config_buffer = SharedConfigBuffer()
    try:
        config, version = config_buffer.get_config()
        assert version == 0, "Initial version should be 0"
        
        new_version = config_buffer.update_config({'sample_hz': 200})
        assert new_version == 1, "Version should increment"
        
        config, version = config_buffer.get_config()
        assert config['sample_hz'] == 200, "Config update failed"
        assert version == 1, "Version should be 1"
        
        print("  ✅ SharedConfigBuffer working")
    finally:
        config_buffer.cleanup()
    
    print("✅ Shared memory structures verified")


def test_process_supervisor():
    """Quick test of process supervisor."""
    print("🔍 Testing process supervisor...")
    
    supervisor = ProcessSupervisor()
    try:
        # Register and start a simple process
        supervisor.register_process("test", simple_task)
        
        success = supervisor.start_process("test")
        assert success, "Failed to start process"
        
        # Wait a bit
        time.sleep(0.2)
        
        # Check status
        status = supervisor.get_process_status("test")
        assert status is not None, "Failed to get process status"
        
        print("  ✅ Process supervisor working")
    finally:
        supervisor.cleanup()
    
    print("✅ Process supervisor verified")


def test_adc_adapters():
    """Quick test of ADC adapters."""
    print("🔍 Testing ADC adapters...")
    
    # Test MockADC
    mock_adapter = create_adc_adapter('mock', {})
    try:
        assert isinstance(mock_adapter, MockADCAdapter), "Should be MockADC"
        assert not mock_adapter.is_hardware, "MockADC should not be hardware"
        
        sample = mock_adapter.read_sample()
        assert isinstance(sample, (int, float)), "Sample should be numeric"
        
        success = mock_adapter.set_sample_rate(100)
        assert success, "Should be able to set sample rate"
        
        print("  ✅ MockADC adapter working")
    finally:
        mock_adapter.cleanup()
    
    # Test ADS1115 (will fall back to MockADC)
    hardware_adapter = create_adc_adapter('ads1115', {'address': 0x48})
    try:
        # Should have fallen back to MockADC
        assert isinstance(hardware_adapter, MockADCAdapter), "Should fall back to MockADC"
        
        sample = hardware_adapter.read_sample()
        assert isinstance(sample, (int, float)), "Sample should be numeric"
        
        print("  ✅ Hardware fallback working")
    finally:
        hardware_adapter.cleanup()
    
    print("✅ ADC adapters verified")


def main():
    """Run quick verification."""
    print("=" * 60)
    print("🔧 QUICK CORE INFRASTRUCTURE VERIFICATION")
    print("=" * 60)
    print()
    
    try:
        test_shared_memory()
        print()
        
        test_process_supervisor()
        print()
        
        test_adc_adapters()
        print()
        
        print("=" * 60)
        print("🎉 ALL CORE INFRASTRUCTURE VERIFIED!")
        print("✅ Ready to proceed with multiprocessing implementation")
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())