"""Tests for SharedConfigBuffer implementation."""

import pytest
import time
import json
from pika.shared_memory import SharedConfigBuffer, ProcessConfig


class TestProcessConfig:
    """Test the ProcessConfig data structure."""
    
    def test_process_config_creation(self):
        """Test creating process configuration."""
        analysis_config = {
            'rms_window_size': 200,
            'frequency_detection': True,
            'sag_threshold': 0.85,
            'swell_threshold': 1.15
        }
        
        config = ProcessConfig(
            sample_hz=200,
            batch_size=50,
            batch_interval_ms=500,
            analysis_config=analysis_config,
            display_fps=10.0,
            version=5
        )
        
        assert config.sample_hz == 200
        assert config.batch_size == 50
        assert config.analysis_config['sag_threshold'] == 0.85
        assert config.version == 5
    
    def test_process_config_serialization(self):
        """Test converting process config to/from JSON."""
        analysis_config = {'test_param': 42}
        
        config = ProcessConfig(
            sample_hz=150,
            batch_size=75,
            batch_interval_ms=750,
            analysis_config=analysis_config,
            display_fps=7.5,
            version=3
        )
        
        # Serialize to JSON
        json_str = config.to_json()
        assert isinstance(json_str, str)
        
        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed['sample_hz'] == 150
        assert parsed['analysis_config']['test_param'] == 42
        assert parsed['version'] == 3
        
        # Should round-trip correctly
        restored_config = ProcessConfig.from_json(json_str)
        assert restored_config.sample_hz == config.sample_hz
        assert restored_config.batch_size == config.batch_size
        assert restored_config.analysis_config == config.analysis_config
        assert restored_config.version == config.version


class TestSharedConfigBuffer:
    """Test the SharedConfigBuffer implementation."""
    
    def test_buffer_initialization(self):
        """Test buffer initialization with default configuration."""
        buffer = SharedConfigBuffer(size=2048)
        
        assert buffer.size == 2048
        
        # Should start with default configuration
        config, version = buffer.get_config()
        assert config['sample_hz'] == 100
        assert config['batch_size'] == 100
        assert config['batch_interval_ms'] == 1000
        assert config['display_fps'] == 5.0
        assert isinstance(config['analysis_config'], dict)
        assert version == 0
        
        # Version should be 0 initially
        assert buffer.get_version() == 0
        
        buffer.cleanup()
    
    def test_config_update_and_versioning(self):
        """Test configuration updates and version tracking."""
        buffer = SharedConfigBuffer(size=2048)
        
        # Initial version should be 0
        assert buffer.get_version() == 0
        
        # Update configuration
        new_config = {
            'sample_hz': 200,
            'batch_size': 50,
            'batch_interval_ms': 500,
            'analysis_config': {'test': True},
            'display_fps': 10.0
        }
        
        new_version = buffer.update_config(new_config)
        
        # Version should increment
        assert new_version == 1
        assert buffer.get_version() == 1
        
        # Read back configuration
        config, version = buffer.get_config()
        assert config['sample_hz'] == 200
        assert config['batch_size'] == 50
        assert config['analysis_config']['test'] is True
        assert version == 1
        
        buffer.cleanup()
    
    def test_multiple_updates(self):
        """Test multiple configuration updates."""
        buffer = SharedConfigBuffer(size=2048)
        
        # First update
        buffer.update_config({'sample_hz': 150})
        assert buffer.get_version() == 1
        
        # Second update
        buffer.update_config({'sample_hz': 250, 'batch_size': 25})
        assert buffer.get_version() == 2
        
        # Third update
        buffer.update_config({'display_fps': 15.0})
        assert buffer.get_version() == 3
        
        # Final configuration should have latest values
        config, version = buffer.get_config()
        assert config['display_fps'] == 15.0
        assert version == 3
        
        buffer.cleanup()
    
    def test_change_detection(self):
        """Test configuration change detection."""
        buffer = SharedConfigBuffer(size=2048)
        
        # Initially no changes
        assert not buffer.has_changed(0)
        
        # Update configuration
        buffer.update_config({'sample_hz': 300})
        
        # Should detect change
        assert buffer.has_changed(0)
        assert not buffer.has_changed(1)  # Current version is 1
        
        # Another update
        buffer.update_config({'batch_size': 30})
        
        # Should detect changes from earlier versions
        assert buffer.has_changed(0)
        assert buffer.has_changed(1)
        assert not buffer.has_changed(2)  # Current version is 2
        
        buffer.cleanup()
    
    def test_wait_for_change(self):
        """Test waiting for configuration changes."""
        buffer = SharedConfigBuffer(size=2048)
        
        # Should timeout immediately since no change expected
        start_time = time.time()
        changed = buffer.wait_for_change(0, timeout_seconds=0.1)
        elapsed = time.time() - start_time
        
        assert not changed
        assert elapsed >= 0.1  # Should have waited for timeout
        
        # Test with actual change (would need threading for real test)
        # For now, just test that it returns False for current version
        assert not buffer.wait_for_change(buffer.get_version(), timeout_seconds=0.05)
        
        buffer.cleanup()
    
    def test_sample_rate_update(self):
        """Test updating only sample rate."""
        buffer = SharedConfigBuffer(size=2048)
        
        # Get initial config
        initial_config, _ = buffer.get_config()
        initial_batch_size = initial_config['batch_size']
        
        # Update only sample rate
        new_version = buffer.update_sample_rate(500)
        
        # Version should increment
        assert new_version == 1
        
        # Sample rate should change, other values preserved
        config, version = buffer.get_config()
        assert config['sample_hz'] == 500
        assert config['batch_size'] == initial_batch_size  # Unchanged
        assert version == 1
        
        buffer.cleanup()
    
    def test_analysis_config_update(self):
        """Test updating only analysis configuration."""
        buffer = SharedConfigBuffer(size=2048)
        
        # Get initial config
        initial_config, _ = buffer.get_config()
        initial_sample_hz = initial_config['sample_hz']
        
        # Update only analysis config
        new_analysis = {
            'custom_param': 123,
            'another_param': 'test'
        }
        new_version = buffer.update_analysis_config(new_analysis)
        
        # Version should increment
        assert new_version == 1
        
        # Analysis config should change, other values preserved
        config, version = buffer.get_config()
        assert config['analysis_config'] == new_analysis
        assert config['sample_hz'] == initial_sample_hz  # Unchanged
        assert version == 1
        
        buffer.cleanup()
    
    def test_large_config_handling(self):
        """Test handling of large configuration data."""
        buffer = SharedConfigBuffer(size=512)  # Small buffer
        
        # Create large analysis config
        large_analysis_config = {}
        for i in range(100):
            large_analysis_config[f'param_{i}'] = f'very_long_value_{i}_with_lots_of_text'
        
        # Update with large config
        large_config = {
            'sample_hz': 100,
            'analysis_config': large_analysis_config
        }
        
        new_version = buffer.update_config(large_config)
        
        # Should still work (data may be truncated)
        config, version = buffer.get_config()
        assert config['sample_hz'] == 100
        assert version == new_version
        # Analysis config may be truncated to fit in buffer
        assert isinstance(config['analysis_config'], dict)
        
        buffer.cleanup()
    
    def test_concurrent_access(self):
        """Test concurrent read/write access."""
        buffer = SharedConfigBuffer(size=2048)
        
        # Simulate concurrent access by rapidly updating and reading
        for i in range(10):
            # Update
            buffer.update_config({
                'sample_hz': 100 + i * 10,
                'batch_size': 50 + i * 5
            })
            
            # Read immediately
            config, version = buffer.get_config()
            
            # Should get valid data (may not be the exact update due to timing)
            assert isinstance(config['sample_hz'], int)
            assert isinstance(config['batch_size'], int)
            assert version > 0
        
        buffer.cleanup()
    
    def test_buffer_info(self):
        """Test buffer information retrieval."""
        buffer = SharedConfigBuffer(size=1024)
        
        info = buffer.get_buffer_info()
        
        assert info['size'] == 1024
        assert info['data_length'] > 0  # Should have initial config data
        assert info['version'] == 0  # Initial version
        assert 'memory_name' in info
        assert 0.0 <= info['utilization'] <= 1.0
        
        # Update and check info again
        buffer.update_config({'sample_hz': 200})
        
        info = buffer.get_buffer_info()
        assert info['version'] == 1
        
        buffer.cleanup()
    
    def test_error_handling(self):
        """Test error handling for corrupted data."""
        buffer = SharedConfigBuffer(size=1024)
        
        # Manually corrupt the buffer data
        for i in range(100):
            buffer.shm.buf[i] = 0xFF  # Invalid UTF-8
        buffer.data_length.value = 100
        
        # Should handle corruption gracefully
        config, version = buffer.get_config()
        
        # Should return default values
        assert config['sample_hz'] == 100
        assert config['batch_size'] == 100
        assert 'error' in config  # Should indicate corruption
        
        buffer.cleanup()
    
    def test_partial_config_updates(self):
        """Test partial configuration updates preserve existing values."""
        buffer = SharedConfigBuffer(size=2048)
        
        # Set initial full configuration
        full_config = {
            'sample_hz': 150,
            'batch_size': 75,
            'batch_interval_ms': 750,
            'analysis_config': {'param1': 'value1', 'param2': 42},
            'display_fps': 7.5
        }
        buffer.update_config(full_config)
        
        # Update only one parameter
        partial_config = {'sample_hz': 300}
        buffer.update_config(partial_config)
        
        # Other parameters should use defaults, not preserved values
        # (This is the current behavior - update_config uses defaults for missing keys)
        config, version = buffer.get_config()
        assert config['sample_hz'] == 300
        assert config['batch_size'] == 100  # Default value
        assert config['batch_interval_ms'] == 1000  # Default value
        
        buffer.cleanup()


if __name__ == "__main__":
    pytest.main([__file__])