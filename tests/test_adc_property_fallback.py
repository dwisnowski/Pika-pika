"""Property-based test for ADC adapter hardware fallback behavior.

**Feature: datalogger-multiprocessing, Property 11: Hardware Fallback Behavior**
**Validates: Requirements 6.5**

Property: For any hardware initialization failure, the system should gracefully 
fall back to simulation mode without crashing.
"""

import sys
import os
import logging
from typing import Dict, Any

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pika.adapters import create_adc_adapter, MockADCAdapter

# Suppress logging during tests to reduce noise
logging.getLogger('pika.adapters').setLevel(logging.WARNING)


def test_hardware_fallback_property():
    """Property test: Hardware initialization failures should gracefully fall back to simulation.
    
    This test validates that regardless of the configuration parameters provided,
    when hardware initialization fails, the system always falls back to MockADC
    without crashing and provides a functional ADC interface.
    """
    
    # Test configurations that would cause hardware initialization to fail
    # (since we don't have actual hardware available)
    test_configs = [
        # Standard configuration
        {'address': 0x48, 'channel': 0, 'sample_rate': 100},
        
        # Different I2C addresses
        {'address': 0x49, 'channel': 0, 'sample_rate': 100},
        {'address': 0x4A, 'channel': 1, 'sample_rate': 200},
        {'address': 0x4B, 'channel': 2, 'sample_rate': 50},
        
        # Different channels
        {'address': 0x48, 'channel': 1, 'sample_rate': 100},
        {'address': 0x48, 'channel': 2, 'sample_rate': 100},
        {'address': 0x48, 'channel': 3, 'sample_rate': 100},
        
        # Different sample rates
        {'address': 0x48, 'channel': 0, 'sample_rate': 8},
        {'address': 0x48, 'channel': 0, 'sample_rate': 16},
        {'address': 0x48, 'channel': 0, 'sample_rate': 32},
        {'address': 0x48, 'channel': 0, 'sample_rate': 64},
        {'address': 0x48, 'channel': 0, 'sample_rate': 128},
        {'address': 0x48, 'channel': 0, 'sample_rate': 250},
        {'address': 0x48, 'channel': 0, 'sample_rate': 475},
        {'address': 0x48, 'channel': 0, 'sample_rate': 860},
        
        # Edge cases
        {'address': 0x48, 'channel': 0, 'sample_rate': 1},
        {'address': 0x48, 'channel': 0, 'sample_rate': 1000},
        
        # Minimal configuration
        {},
        
        # Configuration with extra parameters
        {
            'address': 0x48, 
            'channel': 0, 
            'sample_rate': 100,
            'extra_param': 'ignored',
            'another_param': 42
        },
    ]
    
    results = []
    
    for i, config in enumerate(test_configs):
        try:
            # Attempt to create ADS1115 adapter (will fail without hardware)
            adapter = create_adc_adapter('ads1115', config)
            
            # Verify fallback behavior
            result = validate_fallback_adapter(adapter, config, i)
            results.append(result)
            
            # Clean up
            adapter.cleanup()
            
        except Exception as e:
            # Any exception during fallback violates the property
            results.append({
                'config_index': i,
                'config': config,
                'success': False,
                'error': f"Exception during fallback: {e}",
                'adapter_type': None
            })
    
    # Analyze results
    failures = [r for r in results if not r['success']]
    
    if failures:
        print("❌ Property 11 FAILED: Hardware Fallback Behavior")
        print(f"Failed {len(failures)}/{len(results)} test cases:")
        for failure in failures:
            print(f"  Config {failure['config_index']}: {failure['error']}")
            print(f"    Config: {failure['config']}")
        return False
    else:
        print("✅ Property 11 PASSED: Hardware Fallback Behavior")
        print(f"Validated across {len(results)} different configurations")
        return True


def validate_fallback_adapter(adapter: Any, config: Dict, config_index: int) -> Dict:
    """Validate that the fallback adapter meets all requirements."""
    
    try:
        # 1. Must be MockADCAdapter (fallback from hardware failure)
        if not isinstance(adapter, MockADCAdapter):
            return {
                'config_index': config_index,
                'config': config,
                'success': False,
                'error': f"Expected MockADCAdapter fallback, got {type(adapter)}",
                'adapter_type': type(adapter).__name__
            }
        
        # 2. Must report as non-hardware (simulation mode)
        if adapter.is_hardware:
            return {
                'config_index': config_index,
                'config': config,
                'success': False,
                'error': "Fallback adapter should report is_hardware=False",
                'adapter_type': type(adapter).__name__
            }
        
        # 3. Must provide functional ADC interface
        sample = adapter.read_sample()
        if not isinstance(sample, (int, float)):
            return {
                'config_index': config_index,
                'config': config,
                'success': False,
                'error': f"Invalid sample type: {type(sample)}",
                'adapter_type': type(adapter).__name__
            }
        
        # 4. Must handle sample rate changes
        if not adapter.set_sample_rate(100):
            return {
                'config_index': config_index,
                'config': config,
                'success': False,
                'error': "Fallback adapter should support sample rate changes",
                'adapter_type': type(adapter).__name__
            }
        
        # 5. Must handle cleanup without errors
        # (We'll test this in the main function)
        
        return {
            'config_index': config_index,
            'config': config,
            'success': True,
            'error': None,
            'adapter_type': type(adapter).__name__
        }
        
    except Exception as e:
        return {
            'config_index': config_index,
            'config': config,
            'success': False,
            'error': f"Exception during validation: {e}",
            'adapter_type': type(adapter).__name__ if adapter else None
        }


def test_mock_adapter_direct():
    """Test that MockADC adapter works correctly when requested directly."""
    
    configs = [
        {'signal_type': 'dc', 'dc_offset': 5.0},
        {'signal_type': 'sine', 'frequency': 60.0, 'amplitude': 1.0},
        {'signal_type': 'ac', 'frequency': 50.0},
        {'signal_type': 'noise', 'amplitude': 0.5},
        {}  # Default configuration
    ]
    
    for config in configs:
        try:
            adapter = create_adc_adapter('mock', config)
            
            # Verify it's MockADC
            assert isinstance(adapter, MockADCAdapter)
            assert not adapter.is_hardware
            
            # Test functionality
            sample = adapter.read_sample()
            assert isinstance(sample, (int, float))
            
            # Test sample rate setting
            assert adapter.set_sample_rate(200)
            
            # Cleanup
            adapter.cleanup()
            
        except Exception as e:
            print(f"❌ MockADC direct test failed with config {config}: {e}")
            return False
    
    print("✅ MockADC direct creation tests passed")
    return True


def main():
    """Run all property tests for ADC adapter fallback behavior."""
    
    print("Property-Based Test: ADC Adapter Hardware Fallback")
    print("=" * 60)
    print("**Feature: datalogger-multiprocessing, Property 11: Hardware Fallback Behavior**")
    print("**Validates: Requirements 6.5**")
    print()
    print("Testing property: For any hardware initialization failure,")
    print("the system should gracefully fall back to simulation mode without crashing.")
    print()
    
    try:
        # Test the main property
        property_passed = test_hardware_fallback_property()
        
        print()
        
        # Test direct MockADC functionality
        mock_passed = test_mock_adapter_direct()
        
        print()
        print("=" * 60)
        
        if property_passed and mock_passed:
            print("🎉 ALL PROPERTY TESTS PASSED")
            print("Hardware fallback behavior is correctly implemented.")
            return 0
        else:
            print("💥 PROPERTY TESTS FAILED")
            print("Hardware fallback behavior needs fixes.")
            return 1
            
    except Exception as e:
        print(f"💥 Property test execution failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())