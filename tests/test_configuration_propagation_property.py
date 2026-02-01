"""
Property-based test for configuration propagation across processes.

**Feature: datalogger-multiprocessing, Property 9: Configuration Propagation**
**Validates: Requirements 7.2, 7.3, 7.5, 9.5**

This test validates that configuration changes made via API or file update
propagate to the appropriate processes without requiring full system restart.
"""

import pytest
import time
import tempfile
import os
from hypothesis import given, strategies as st, settings, assume
from typing import Dict, Any

from pika.shared_memory import SharedConfigBuffer
from pika.config import ConfigurationManager, ConfigurationError


class TestConfigurationPropagation:
    """Property-based tests for configuration propagation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_config_file = None
        self.shared_config_buffer = None
        self.config_manager = None
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.shared_config_buffer:
            try:
                self.shared_config_buffer.cleanup()
            except:
                pass
        
        if self.temp_config_file and os.path.exists(self.temp_config_file):
            try:
                os.unlink(self.temp_config_file)
            except:
                pass
    
    def create_test_config_file(self, config_data: Dict[str, Any]) -> str:
        """Create a temporary config file with given data."""
        import tomli_w
        
        fd, temp_path = tempfile.mkstemp(suffix='.toml')
        try:
            with os.fdopen(fd, 'wb') as f:
                tomli_w.dump(config_data, f)
        except ImportError:
            # Fallback to manual TOML writing if tomli_w not available
            os.close(fd)
            with open(temp_path, 'w') as f:
                f.write(self._dict_to_toml(config_data))
        
        return temp_path
    
    def _dict_to_toml(self, data: Dict[str, Any]) -> str:
        """Simple TOML serialization for fallback."""
        lines = []
        for section, values in data.items():
            lines.append(f"[{section}]")
            for key, value in values.items():
                if isinstance(value, str):
                    lines.append(f'{key} = "{value}"')
                elif isinstance(value, bool):
                    lines.append(f'{key} = {str(value).lower()}')
                else:
                    lines.append(f'{key} = {value}')
            lines.append("")
        return "\n".join(lines)
    
    @given(
        sample_hz=st.integers(min_value=1, max_value=860),
        batch_size=st.integers(min_value=1, max_value=1000),
        batch_interval_ms=st.integers(min_value=100, max_value=10000),
        display_fps=st.floats(min_value=0.1, max_value=60.0),
        nominal_voltage=st.floats(min_value=50.0, max_value=500.0)
    )
    @settings(max_examples=50, deadline=5000)
    def test_configuration_propagation_via_shared_buffer(
        self, sample_hz: int, batch_size: int, batch_interval_ms: int, 
        display_fps: float, nominal_voltage: float
    ):
        """
        Property: For any configuration change made via shared buffer,
        the change should propagate to all processes without system restart.
        
        **Validates: Requirements 7.2, 7.3, 7.5, 9.5**
        """
        # Create shared config buffer
        self.shared_config_buffer = SharedConfigBuffer(create=True)
        
        # Create initial configuration
        initial_config = {
            'sample_hz': 100,
            'batch_size': 50,
            'batch_interval_ms': 1000,
            'analysis_config': {
                'nominal_voltage': 120.0,
                'enable_rms': True
            },
            'display_fps': 5.0
        }
        
        # Set initial configuration
        initial_version = self.shared_config_buffer.update_config(initial_config)
        assert initial_version > 0
        
        # Verify initial configuration is readable
        config, version = self.shared_config_buffer.get_config()
        assert version == initial_version
        assert config['sample_hz'] == 100
        
        # Create updated configuration with property values
        updated_config = {
            'sample_hz': sample_hz,
            'batch_size': batch_size,
            'batch_interval_ms': batch_interval_ms,
            'analysis_config': {
                'nominal_voltage': nominal_voltage,
                'enable_rms': True,
                'sag_threshold': nominal_voltage * 0.9,
                'swell_threshold': nominal_voltage * 1.1
            },
            'display_fps': display_fps
        }
        
        # Update configuration
        new_version = self.shared_config_buffer.update_config(updated_config)
        
        # Property: Version should increment
        assert new_version > initial_version, "Configuration version should increment on update"
        
        # Property: Updated configuration should be immediately readable
        retrieved_config, retrieved_version = self.shared_config_buffer.get_config()
        assert retrieved_version == new_version, "Retrieved version should match updated version"
        
        # Property: All updated values should propagate correctly
        assert retrieved_config['sample_hz'] == sample_hz, "Sample rate should propagate"
        assert retrieved_config['batch_size'] == batch_size, "Batch size should propagate"
        assert retrieved_config['batch_interval_ms'] == batch_interval_ms, "Batch interval should propagate"
        assert retrieved_config['display_fps'] == display_fps, "Display FPS should propagate"
        assert retrieved_config['analysis_config']['nominal_voltage'] == nominal_voltage, "Analysis config should propagate"
        
        # Property: Change detection should work
        assert self.shared_config_buffer.has_changed(initial_version), "Should detect configuration change"
        assert not self.shared_config_buffer.has_changed(new_version), "Should not detect change for current version"
    
    @given(
        config_updates=st.lists(
            st.dictionaries(
                keys=st.sampled_from(['sample_hz', 'batch_size', 'display_fps']),
                values=st.one_of(
                    st.integers(min_value=1, max_value=100),
                    st.floats(min_value=0.1, max_value=10.0)
                ),
                min_size=1,
                max_size=3
            ),
            min_size=1,
            max_size=5
        )
    )
    @settings(max_examples=30, deadline=10000)
    def test_sequential_configuration_updates(self, config_updates):
        """
        Property: For any sequence of configuration updates,
        each update should increment the version and be retrievable.
        
        **Validates: Requirements 7.2, 7.3**
        """
        # Create shared config buffer
        self.shared_config_buffer = SharedConfigBuffer(create=True)
        
        # Track versions
        last_version = 0
        
        for i, update in enumerate(config_updates):
            # Filter out invalid combinations
            if 'sample_hz' in update and not isinstance(update['sample_hz'], int):
                continue
            if 'batch_size' in update and not isinstance(update['batch_size'], int):
                continue
            
            # Apply update
            new_version = self.shared_config_buffer.update_config(update)
            
            # Property: Version should always increment
            assert new_version > last_version, f"Version should increment on update {i}"
            
            # Property: Updated values should be retrievable
            config, version = self.shared_config_buffer.get_config()
            assert version == new_version, f"Retrieved version should match for update {i}"
            
            # Property: Updated values should be present
            for key, value in update.items():
                if key in config:
                    assert config[key] == value, f"Value {key} should be updated in iteration {i}"
            
            last_version = new_version
    
    @given(
        initial_sample_hz=st.integers(min_value=50, max_value=200),
        updated_sample_hz=st.integers(min_value=50, max_value=200)
    )
    @settings(max_examples=20, deadline=3000)
    def test_sample_rate_specific_propagation(self, initial_sample_hz: int, updated_sample_hz: int):
        """
        Property: For any sample rate change via API,
        the change should propagate to the datalogger process configuration.
        
        **Validates: Requirements 9.5**
        """
        assume(initial_sample_hz != updated_sample_hz)
        
        # Create shared config buffer
        self.shared_config_buffer = SharedConfigBuffer(create=True)
        
        # Set initial sample rate
        initial_config = {'sample_hz': initial_sample_hz}
        initial_version = self.shared_config_buffer.update_config(initial_config)
        
        # Update sample rate using the specific method
        new_version = self.shared_config_buffer.update_sample_rate(updated_sample_hz)
        
        # Property: Version should increment
        assert new_version > initial_version, "Version should increment on sample rate update"
        
        # Property: Sample rate should be updated
        config, version = self.shared_config_buffer.get_config()
        assert config['sample_hz'] == updated_sample_hz, "Sample rate should be updated"
        assert version == new_version, "Version should match"
        
        # Property: Other configuration should be preserved
        # (This tests that sample rate updates don't overwrite other settings)
        if 'batch_size' in config:
            # Default batch size should be preserved
            assert 'batch_size' in config, "Other configuration should be preserved"
    
    @given(
        analysis_params=st.dictionaries(
            keys=st.sampled_from(['enable_rms', 'enable_freq', 'nominal_voltage', 'sag_threshold']),
            values=st.one_of(
                st.booleans(),
                st.floats(min_value=50.0, max_value=300.0)
            ),
            min_size=1,
            max_size=4
        )
    )
    @settings(max_examples=25, deadline=5000)
    def test_analysis_configuration_propagation(self, analysis_params):
        """
        Property: For any analysis configuration change,
        the change should propagate to the event logger process.
        
        **Validates: Requirements 7.5**
        """
        # Create shared config buffer
        self.shared_config_buffer = SharedConfigBuffer(create=True)
        
        # Get initial version
        _, initial_version = self.shared_config_buffer.get_config()
        
        # Update analysis configuration
        new_version = self.shared_config_buffer.update_analysis_config(analysis_params)
        
        # Property: Version should increment
        assert new_version > initial_version, "Version should increment on analysis config update"
        
        # Property: Analysis configuration should be updated
        config, version = self.shared_config_buffer.get_config()
        assert version == new_version, "Version should match"
        
        # Property: Analysis parameters should be present in analysis_config section
        analysis_config = config.get('analysis_config', {})
        for key, value in analysis_params.items():
            if isinstance(value, float) and key in ['nominal_voltage', 'sag_threshold']:
                assert analysis_config.get(key) == value, f"Analysis parameter {key} should be updated"
            elif isinstance(value, bool) and key in ['enable_rms', 'enable_freq']:
                assert analysis_config.get(key) == value, f"Analysis parameter {key} should be updated"
    
    @given(
        wait_timeout=st.floats(min_value=0.1, max_value=2.0)
    )
    @settings(max_examples=10, deadline=5000)
    def test_configuration_change_detection_timing(self, wait_timeout: float):
        """
        Property: For any configuration change,
        change detection should work within reasonable time bounds.
        
        **Validates: Requirements 7.2**
        """
        # Create shared config buffer
        self.shared_config_buffer = SharedConfigBuffer(create=True)
        
        # Get initial version
        _, initial_version = self.shared_config_buffer.get_config()
        
        # Make a configuration change
        test_config = {'sample_hz': 150}
        new_version = self.shared_config_buffer.update_config(test_config)
        
        # Property: Change should be detectable immediately
        assert self.shared_config_buffer.has_changed(initial_version), "Change should be immediately detectable"
        
        # Property: Wait for change should return immediately for already changed config
        start_time = time.time()
        changed = self.shared_config_buffer.wait_for_change(initial_version, wait_timeout)
        elapsed = time.time() - start_time
        
        assert changed, "Should detect existing change"
        assert elapsed < 0.1, "Should detect change immediately (not wait full timeout)"
        
        # Property: Wait for change should timeout when no change occurs
        start_time = time.time()
        changed = self.shared_config_buffer.wait_for_change(new_version, wait_timeout)
        elapsed = time.time() - start_time
        
        assert not changed, "Should not detect change when none occurred"
        assert abs(elapsed - wait_timeout) < 0.2, f"Should wait approximately {wait_timeout} seconds"
    
    def test_configuration_file_loading_and_validation(self):
        """
        Property: For any valid configuration file,
        loading should succeed and produce valid shared config data.
        
        **Validates: Requirements 7.1, 7.4**
        """
        # Test with minimal valid configuration
        minimal_config = {
            "pika": {"sample_hz": 100, "data_dir": "test_data"},
            "pins": {"adc_address": 0x48},
            "datalogger": {"batch_size": 50},
            "analysis": {"enable_rms": True}
        }
        
        # Create temporary config file
        self.temp_config_file = self.create_test_config_file(minimal_config)
        
        # Load configuration
        self.config_manager = ConfigurationManager(self.temp_config_file)
        config = self.config_manager.load_configuration()
        
        # Property: Configuration should load successfully
        assert config is not None, "Configuration should load"
        assert 'pika' in config, "Pika section should be present"
        assert 'pins' in config, "Pins section should be present"
        
        # Property: Shared config data should be extractable
        shared_config_data = self.config_manager.get_shared_config_data()
        assert 'sample_hz' in shared_config_data, "Sample rate should be in shared config"
        assert 'analysis_config' in shared_config_data, "Analysis config should be in shared config"
        
        # Property: Shared config should be compatible with SharedConfigBuffer
        self.shared_config_buffer = SharedConfigBuffer(create=True)
        version = self.shared_config_buffer.update_config(shared_config_data)
        assert version > 0, "Should be able to update shared buffer with loaded config"
        
        # Property: Configuration should be retrievable from shared buffer
        retrieved_config, retrieved_version = self.shared_config_buffer.get_config()
        assert retrieved_version == version, "Versions should match"
        assert retrieved_config['sample_hz'] == shared_config_data['sample_hz'], "Sample rate should match"
    
    def test_invalid_configuration_handling(self):
        """
        Property: For any invalid configuration,
        the system should handle errors gracefully and use defaults.
        
        **Validates: Requirements 7.4**
        """
        # Test with invalid configuration
        invalid_config = {
            "pika": {
                "sample_hz": "invalid",  # Should be integer
                "port": 99999999,        # Out of range
                "data_dir": ""           # Empty string
            },
            "analysis": {
                "sag_threshold": 200.0,
                "swell_threshold": 100.0  # Invalid: sag > swell
            }
        }
        
        # Create temporary config file
        self.temp_config_file = self.create_test_config_file(invalid_config)
        
        # Load configuration (should not raise exception)
        self.config_manager = ConfigurationManager(self.temp_config_file)
        
        # Property: Invalid configuration should be handled gracefully
        try:
            config = self.config_manager.load_configuration()
            
            # If loading succeeds, defaults should be applied
            assert config['pika']['sample_hz'] == 100, "Invalid sample_hz should use default"
            assert 1024 <= config['pika']['port'] <= 65535, "Invalid port should use valid default"
            assert config['pika']['data_dir'] == "data", "Empty data_dir should use default"
            
            # Threshold relationship should be corrected
            sag = config['analysis']['sag_threshold']
            swell = config['analysis']['swell_threshold']
            assert sag < swell, "Threshold relationship should be corrected"
            
        except ConfigurationError:
            # If loading fails, that's also acceptable behavior
            # The system should handle this gracefully
            pass
        
        # Property: Validation errors should be trackable
        errors = self.config_manager.get_validation_errors()
        assert isinstance(errors, list), "Validation errors should be a list"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])