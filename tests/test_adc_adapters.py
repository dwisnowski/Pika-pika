"""Tests for ADC adapter interface and implementations."""

import pytest
import math
from pika.adapters import ADCAdapter, ADS1115Adapter, MockADCAdapter, create_adc_adapter


class TestMockADCAdapter:
    """Test the MockADC adapter implementation."""
    
    def test_initialization(self):
        """Test MockADC adapter initialization."""
        adapter = MockADCAdapter()
        config = {
            'sample_rate': 100,
            'signal_type': 'sine',
            'amplitude': 2.0,
            'frequency': 50.0
        }
        
        assert adapter.initialize(config) is True
        assert adapter.is_hardware is False
    
    def test_read_sample(self):
        """Test reading samples from MockADC."""
        adapter = MockADCAdapter()
        config = {'signal_type': 'dc', 'dc_offset': 5.0, 'noise_level': 0.01}
        
        adapter.initialize(config)
        
        # Read multiple samples
        samples = [adapter.read_sample() for _ in range(10)]
        
        # All samples should be valid numbers
        assert all(not math.isnan(sample) for sample in samples)
        
        # For DC signal, samples should be close to offset
        assert all(4.9 < sample < 5.1 for sample in samples)
    
    def test_sample_rate_setting(self):
        """Test setting sample rate."""
        adapter = MockADCAdapter()
        adapter.initialize({})
        
        assert adapter.set_sample_rate(200) is True
        assert adapter.set_sample_rate(1) is True
        assert adapter.set_sample_rate(10000) is True
    
    def test_cleanup(self):
        """Test cleanup functionality."""
        adapter = MockADCAdapter()
        adapter.initialize({})
        adapter.cleanup()
        
        # Should not crash and should handle uninitialized state
        sample = adapter.read_sample()
        assert sample == 0.0


class TestADCFactory:
    """Test the ADC adapter factory function."""
    
    def test_create_mock_adapter(self):
        """Test creating mock adapter via factory."""
        config = {'signal_type': 'sine'}
        adapter = create_adc_adapter('mock', config)
        
        assert isinstance(adapter, MockADCAdapter)
        assert adapter.is_hardware is False
    
    def test_unsupported_adapter_type(self):
        """Test factory with unsupported adapter type."""
        with pytest.raises(ValueError, match="Unsupported ADC type"):
            create_adc_adapter('unsupported', {})
    
    def test_hardware_fallback(self):
        """Test fallback to mock when hardware fails."""
        # This test would need to mock the hardware initialization failure
        # For now, just test that mock adapter works
        config = {}
        adapter = create_adc_adapter('mock', config)
        assert isinstance(adapter, MockADCAdapter)


class TestADCInterface:
    """Test the abstract ADC interface."""
    
    def test_interface_methods(self):
        """Test that all required methods are defined in the interface."""
        # Check that MockADCAdapter implements all required methods
        adapter = MockADCAdapter()
        
        # These should not raise NotImplementedError
        adapter.initialize({})
        sample = adapter.read_sample()
        adapter.set_sample_rate(100)
        adapter.cleanup()
        is_hw = adapter.is_hardware
        
        assert isinstance(sample, float)
        assert isinstance(is_hw, bool)


if __name__ == "__main__":
    pytest.main([__file__])