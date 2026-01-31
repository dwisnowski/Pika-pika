"""Tests for SharedAnalysisBuffer implementation."""

import pytest
import time
import json
from pika.shared_memory import SharedAnalysisBuffer, AnalysisMetrics


class TestAnalysisMetrics:
    """Test the AnalysisMetrics data structure."""
    
    def test_analysis_metrics_creation(self):
        """Test creating analysis metrics."""
        events = [
            {'type': 'sag', 'start': 1234567890.1, 'end': 1234567890.2, 'magnitude': 0.8},
            {'type': 'swell', 'start': 1234567891.1, 'end': 1234567891.3, 'magnitude': 1.2}
        ]
        
        metrics = AnalysisMetrics(
            rms=120.5,
            frequency=59.98,
            sags_swells=events,
            last_updated=time.time()
        )
        
        assert metrics.rms == 120.5
        assert metrics.frequency == 59.98
        assert len(metrics.sags_swells) == 2
        assert metrics.sags_swells[0]['type'] == 'sag'
    
    def test_analysis_metrics_serialization(self):
        """Test converting analysis metrics to/from JSON."""
        events = [{'type': 'sag', 'magnitude': 0.9}]
        timestamp = time.time()
        
        metrics = AnalysisMetrics(
            rms=115.2,
            frequency=60.01,
            sags_swells=events,
            last_updated=timestamp
        )
        
        # Serialize to JSON
        json_str = metrics.to_json()
        assert isinstance(json_str, str)
        
        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed['rms'] == 115.2
        assert parsed['frequency'] == 60.01
        assert len(parsed['sags_swells']) == 1
        
        # Should round-trip correctly
        restored_metrics = AnalysisMetrics.from_json(json_str)
        assert restored_metrics.rms == metrics.rms
        assert restored_metrics.frequency == metrics.frequency
        assert restored_metrics.sags_swells == metrics.sags_swells
        assert abs(restored_metrics.last_updated - metrics.last_updated) < 1e-10


class TestSharedAnalysisBuffer:
    """Test the SharedAnalysisBuffer implementation."""
    
    def test_buffer_initialization(self):
        """Test buffer initialization."""
        buffer = SharedAnalysisBuffer(size=1024)
        
        assert buffer.size == 1024
        
        # Should start with default empty metrics
        analysis = buffer.get_current_analysis()
        assert analysis['rms'] == 0.0
        assert analysis['frequency'] == 0.0
        assert analysis['sags_swells'] == []
        assert analysis['last_updated'] == 0.0
        
        # Should not be fresh initially
        assert not buffer.is_data_fresh()
        assert buffer.get_last_update_time() == 0.0
        
        buffer.cleanup()
    
    def test_update_and_read_metrics(self):
        """Test updating and reading analysis metrics."""
        buffer = SharedAnalysisBuffer(size=1024)
        
        # Update with test metrics
        events = [
            {'type': 'sag', 'start': time.time(), 'magnitude': 0.85}
        ]
        
        buffer.update_metrics(
            rms=118.5,
            frequency=59.95,
            events=events
        )
        
        # Read back the metrics
        analysis = buffer.get_current_analysis()
        
        assert abs(analysis['rms'] - 118.5) < 1e-10
        assert abs(analysis['frequency'] - 59.95) < 1e-10
        assert len(analysis['sags_swells']) == 1
        assert analysis['sags_swells'][0]['type'] == 'sag'
        assert analysis['last_updated'] > 0
        
        # Should be fresh now
        assert buffer.is_data_fresh()
        assert buffer.get_last_update_time() > 0
        
        buffer.cleanup()
    
    def test_multiple_updates(self):
        """Test multiple metric updates."""
        buffer = SharedAnalysisBuffer(size=1024)
        
        # First update
        buffer.update_metrics(rms=110.0, frequency=60.0, events=[])
        first_update_time = buffer.get_last_update_time()
        
        time.sleep(0.01)  # Small delay
        
        # Second update
        events = [{'type': 'swell', 'magnitude': 1.1}]
        buffer.update_metrics(rms=125.0, frequency=60.1, events=events)
        second_update_time = buffer.get_last_update_time()
        
        # Should have the latest values
        analysis = buffer.get_current_analysis()
        assert analysis['rms'] == 125.0
        assert analysis['frequency'] == 60.1
        assert len(analysis['sags_swells']) == 1
        
        # Update time should have changed
        assert second_update_time > first_update_time
        
        buffer.cleanup()
    
    def test_data_freshness(self):
        """Test data freshness checking."""
        buffer = SharedAnalysisBuffer(size=1024)
        
        # Initially not fresh
        assert not buffer.is_data_fresh(max_age_seconds=1.0)
        
        # Update metrics
        buffer.update_metrics(rms=120.0, frequency=60.0, events=[])
        
        # Should be fresh immediately
        assert buffer.is_data_fresh(max_age_seconds=1.0)
        assert buffer.is_data_fresh(max_age_seconds=0.1)
        
        # Wait and check staleness
        time.sleep(0.05)
        assert buffer.is_data_fresh(max_age_seconds=0.1)  # Still fresh
        assert not buffer.is_data_fresh(max_age_seconds=0.01)  # Now stale
        
        buffer.cleanup()
    
    def test_large_data_handling(self):
        """Test handling of large data that exceeds buffer size."""
        buffer = SharedAnalysisBuffer(size=256)  # Small buffer
        
        # Create large events list
        large_events = []
        for i in range(100):  # Many events
            large_events.append({
                'type': 'sag',
                'start': time.time() + i,
                'end': time.time() + i + 0.1,
                'magnitude': 0.8 + i * 0.001,
                'description': f'Large event description {i} with lots of text to make it big'
            })
        
        # Update with large data
        buffer.update_metrics(
            rms=120.0,
            frequency=60.0,
            events=large_events
        )
        
        # Should still work (data may be truncated)
        analysis = buffer.get_current_analysis()
        assert analysis['rms'] == 120.0
        assert analysis['frequency'] == 60.0
        # Events may be truncated to fit in buffer
        assert isinstance(analysis['sags_swells'], list)
        
        buffer.cleanup()
    
    def test_concurrent_access(self):
        """Test concurrent read/write access."""
        buffer = SharedAnalysisBuffer(size=1024)
        
        # Simulate concurrent access by rapidly updating and reading
        for i in range(10):
            # Update
            buffer.update_metrics(
                rms=100.0 + i,
                frequency=60.0 + i * 0.1,
                events=[{'type': 'test', 'value': i}]
            )
            
            # Read immediately
            analysis = buffer.get_current_analysis()
            
            # Should get valid data (may not be the exact update due to timing)
            assert isinstance(analysis['rms'], (int, float))
            assert isinstance(analysis['frequency'], (int, float))
            assert isinstance(analysis['sags_swells'], list)
        
        buffer.cleanup()
    
    def test_buffer_info(self):
        """Test buffer information retrieval."""
        buffer = SharedAnalysisBuffer(size=512)
        
        info = buffer.get_buffer_info()
        
        assert info['size'] == 512
        assert info['data_length'] > 0  # Should have initial empty data
        assert info['last_update'] == 0.0  # No updates yet
        assert not info['is_fresh']
        assert 'memory_name' in info
        assert 0.0 <= info['utilization'] <= 1.0
        
        # Update and check info again
        buffer.update_metrics(rms=115.0, frequency=59.9, events=[])
        
        info = buffer.get_buffer_info()
        assert info['last_update'] > 0.0
        assert info['is_fresh']
        
        buffer.cleanup()
    
    def test_error_handling(self):
        """Test error handling for corrupted data."""
        buffer = SharedAnalysisBuffer(size=1024)
        
        # Manually corrupt the buffer data
        for i in range(100):
            buffer.shm.buf[i] = 0xFF  # Invalid UTF-8
        buffer.data_length.value = 100
        
        # Should handle corruption gracefully
        analysis = buffer.get_current_analysis()
        
        # Should return default values
        assert analysis['rms'] == 0.0
        assert analysis['frequency'] == 0.0
        assert analysis['sags_swells'] == []
        assert 'error' in analysis  # Should indicate corruption
        
        buffer.cleanup()


if __name__ == "__main__":
    pytest.main([__file__])