"""
Property-based test for API backward compatibility.

**Feature: datalogger-multiprocessing, Property 10: API Backward Compatibility**
**Validates: Requirements 9.1, 9.2, 9.3, 9.4**

This test validates that the multiprocessing FastAPI implementation maintains
backward compatibility with existing API endpoints and response formats.
"""

import json
import os
import tempfile
import time
from typing import Dict, Any, List, Tuple
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, strategies as st, settings, assume

from pika.app import app
from pika.shared_memory import SharedSampleBuffer, SharedAnalysisBuffer, SharedConfigBuffer


class TestAPIBackwardCompatibility:
    """Property-based tests for API backward compatibility."""
    
    def setup_method(self):
        """Set up test environment with shared memory buffers."""
        # Create temporary directory for test data
        self.temp_dir = tempfile.mkdtemp()
        
        # Create shared memory buffers for testing
        self.sample_buffer = SharedSampleBuffer(size=1000, create=True)
        self.analysis_buffer = SharedAnalysisBuffer(create=True)
        self.config_buffer = SharedConfigBuffer(create=True)
        
        # Mock the app's shared memory buffers
        app.shared_sample_buffer = self.sample_buffer
        app.shared_analysis_buffer = self.analysis_buffer
        app.shared_config_buffer = self.config_buffer
        
        # Create test client
        self.client = TestClient(app)
    
    def teardown_method(self):
        """Clean up test resources."""
        # Clean up shared memory
        if hasattr(self, 'sample_buffer'):
            self.sample_buffer.cleanup()
        if hasattr(self, 'analysis_buffer'):
            self.analysis_buffer.cleanup()
        if hasattr(self, 'config_buffer'):
            self.config_buffer.cleanup()
        
        # Clean up temp directory
        import shutil
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @given(
        seconds=st.floats(min_value=0.1, max_value=60.0),
        sample_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_api_recent_response_format_property(self, seconds: float, sample_count: int):
        """
        Property: For any valid seconds parameter, /api/recent returns data in the expected format.
        
        The response must be a JSON object with a 'data' key containing an array of 
        [timestamp, value] pairs, maintaining backward compatibility.
        """
        # Populate sample buffer with test data
        current_time = time.time()
        for i in range(sample_count):
            timestamp = current_time - (sample_count - i) * 0.01  # 10ms intervals
            value = 120.0 + (i % 10) * 0.1  # Varying voltage values
            self.sample_buffer.write_sample(timestamp, value)
        
        # Make API request
        response = self.client.get(f"/api/recent?seconds={seconds}")
        
        # Validate response structure
        assert response.status_code == 200
        data = response.json()
        
        # Property: Response must have 'data' key
        assert "data" in data
        assert isinstance(data["data"], list)
        
        # Property: Each data point must be a [timestamp, value] pair
        for point in data["data"]:
            assert isinstance(point, list)
            assert len(point) == 2
            assert isinstance(point[0], (int, float))  # timestamp
            assert isinstance(point[1], (int, float))  # value
            
        # Property: Data points should be in chronological order
        timestamps = [point[0] for point in data["data"]]
        assert timestamps == sorted(timestamps)
    
    @given(
        sample_hz=st.integers(min_value=1, max_value=860)
    )
    @settings(max_examples=30)
    def test_config_sample_rate_api_property(self, sample_hz: int):
        """
        Property: For any valid sample rate, the configuration API maintains backward compatibility.
        
        The PUT /api/config/sample-rate endpoint must accept the same format and return
        the same response structure as the original implementation.
        """
        # Test PUT request format
        request_data = {"sample_hz": sample_hz}
        response = self.client.put("/api/config/sample-rate", json=request_data)
        
        # Property: Response must be successful for valid sample rates
        assert response.status_code == 200
        data = response.json()
        
        # Property: Response must contain expected fields
        assert "success" in data
        assert isinstance(data["success"], bool)
        
        if data["success"]:
            assert "sample_hz" in data
            assert data["sample_hz"] == sample_hz
            # New multiprocessing version may include version field
            if "version" in data:
                assert isinstance(data["version"], int)
        
        # Test GET request to verify configuration was updated
        get_response = self.client.get("/api/config")
        assert get_response.status_code == 200
        config_data = get_response.json()
        
        # Property: GET response must contain expected configuration fields
        required_fields = ["sample_hz", "data_dir", "port", "display_fps", "display_auto_ip"]
        for field in required_fields:
            assert field in config_data
    
    @given(
        analysis_config=st.dictionaries(
            keys=st.sampled_from(["rms_window_size", "frequency_detection", "sag_threshold", "swell_threshold"]),
            values=st.one_of(
                st.integers(min_value=1, max_value=1000),
                st.booleans(),
                st.floats(min_value=0.1, max_value=2.0)
            ),
            min_size=1,
            max_size=4
        )
    )
    @settings(max_examples=30)
    def test_analysis_config_api_property(self, analysis_config: Dict[str, Any]):
        """
        Property: For any valid analysis configuration, the API maintains backward compatibility.
        
        The analysis configuration endpoints must accept and return data in the same format.
        """
        # Test PUT request
        response = self.client.put("/api/config/analysis", json=analysis_config)
        
        # Property: Response must be successful
        assert response.status_code == 200
        data = response.json()
        
        # Property: Response must contain expected fields
        assert "success" in data
        assert isinstance(data["success"], bool)
        
        if data["success"]:
            assert "config" in data
            # The returned config should match what we sent
            for key, value in analysis_config.items():
                if key in data["config"]:
                    assert data["config"][key] == value
        
        # Test GET request to verify configuration
        get_response = self.client.get("/api/config/analysis")
        assert get_response.status_code == 200
        
        # Property: GET response should be a dictionary
        get_data = get_response.json()
        assert isinstance(get_data, dict)
    
    def test_api_highlights_response_format_property(self):
        """
        Property: /api/highlights returns data in the expected format.
        
        The response must be a JSON object with a 'highlights' key containing an array
        of highlight objects, maintaining backward compatibility.
        """
        # Test without any highlights data
        response = self.client.get("/api/highlights")
        
        # Property: Response must be successful
        assert response.status_code == 200
        data = response.json()
        
        # Property: Response must have 'highlights' key
        assert "highlights" in data
        assert isinstance(data["highlights"], list)
        
        # Test with time range parameters
        start_time = time.time() - 3600  # 1 hour ago
        end_time = time.time()
        
        response = self.client.get(f"/api/highlights?start={start_time}&end={end_time}")
        assert response.status_code == 200
        data = response.json()
        
        # Property: Response format should be consistent with time range
        assert "highlights" in data
        assert isinstance(data["highlights"], list)
    
    @given(
        start_time=st.floats(min_value=1600000000, max_value=2000000000),  # Valid timestamp range
        duration=st.floats(min_value=60, max_value=86400),  # 1 minute to 1 day
        max_points=st.integers(min_value=100, max_value=5000)
    )
    @settings(max_examples=20)
    def test_api_range_response_format_property(self, start_time: float, duration: float, max_points: int):
        """
        Property: For any valid time range, /api/range returns data in the expected format.
        
        The response must be a JSON object with a 'data' key containing an array of
        [timestamp, value] pairs, maintaining backward compatibility with CSV file reading.
        """
        end_time = start_time + duration
        
        # Make API request
        response = self.client.get(f"/api/range?start={start_time}&end={end_time}&max_points={max_points}")
        
        # Property: Response must be successful
        assert response.status_code == 200
        data = response.json()
        
        # Property: Response must have 'data' key
        assert "data" in data
        assert isinstance(data["data"], list)
        
        # Property: Each data point must be a [timestamp, value] pair
        for point in data["data"]:
            assert isinstance(point, list)
            assert len(point) == 2
            assert isinstance(point[0], (int, float))  # timestamp
            assert isinstance(point[1], (int, float))  # value
            
            # Property: Timestamps should be within requested range
            assert start_time <= point[0] <= end_time
        
        # Property: Number of points should not exceed max_points
        assert len(data["data"]) <= max_points
        
        # Property: Data points should be in chronological order
        timestamps = [point[0] for point in data["data"]]
        assert timestamps == sorted(timestamps)
    
    def test_demo_mode_compatibility_property(self):
        """
        Property: Demo mode APIs maintain backward compatibility.
        
        All API endpoints should work correctly when demo=true parameter is used.
        """
        # Test recent API with demo mode
        response = self.client.get("/api/recent?demo=true&seconds=5.0")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)
        
        # Test highlights API with demo mode
        response = self.client.get("/api/highlights?demo=true")
        assert response.status_code == 200
        data = response.json()
        assert "highlights" in data
        assert isinstance(data["highlights"], list)
        
        # Test range API with demo mode
        start_time = time.time() - 3600
        end_time = time.time()
        response = self.client.get(f"/api/range?demo=true&start={start_time}&end={end_time}")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)
    
    def test_error_handling_compatibility_property(self):
        """
        Property: Error handling maintains backward compatibility.
        
        Invalid requests should return appropriate HTTP status codes and error formats.
        """
        # Test invalid sample rate
        response = self.client.put("/api/config/sample-rate", json={"sample_hz": 9999})
        assert response.status_code == 400  # Bad Request
        
        # Test invalid range parameters (FastAPI returns 422 for invalid query params)
        response = self.client.get("/api/range?start=invalid&end=invalid")
        assert response.status_code == 422  # Unprocessable Entity for invalid parameters
        
        # Test missing parameters
        response = self.client.put("/api/config/sample-rate", json={})
        # Should handle missing sample_hz gracefully
        assert response.status_code in [200, 400, 422]  # Either handle gracefully or return error