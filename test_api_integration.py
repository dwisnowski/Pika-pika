#!/usr/bin/env python3
"""
API Integration Test

Test that the FastAPI endpoints work correctly with shared memory data.
This is a focused test for the API portion of checkpoint 9.
"""

import sys
import os
import time
import requests
import threading
from multiprocessing import Process

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pika.shared_memory import SharedSampleBuffer, SharedAnalysisBuffer, SharedConfigBuffer
from pika.datalogger_process import DataloggerProcess

def start_fastapi_server(port=8002):
    """Start FastAPI server for testing."""
    import uvicorn
    from pika.app import app
    
    # Initialize shared memory with test data
    sample_buffer = SharedSampleBuffer(size=100, create=True)
    analysis_buffer = SharedAnalysisBuffer(create=True)
    config_buffer = SharedConfigBuffer(create=True)
    
    # Add some test data
    base_time = time.time()
    for i in range(50):
        sample_buffer.write_sample(base_time + i * 0.01, float(i % 10))
    
    analysis_buffer.update_metrics(rms=120.5, frequency=59.8, events=[])
    config_buffer.update_config({'sample_hz': 100, 'batch_size': 50})
    
    # Update app with shared memory
    app.shared_sample_buffer = sample_buffer
    app.shared_analysis_buffer = analysis_buffer
    app.shared_config_buffer = config_buffer
    
    # Update connection manager
    from pika.app import manager
    manager.sample_buffer = sample_buffer
    manager.analysis_buffer = analysis_buffer
    
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")

def test_api_endpoints():
    """Test API endpoints."""
    base_url = "http://localhost:8002"
    
    # Wait for server to start
    time.sleep(2.0)
    
    try:
        # Test health endpoint
        response = requests.get(f"{base_url}/health", timeout=5)
        print(f"Health endpoint: {response.status_code}")
        
        # Test recent data endpoint
        response = requests.get(f"{base_url}/api/recent", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"Recent data: {len(data)} samples")
        else:
            print(f"Recent data failed: {response.status_code}")
        
        # Test config endpoint
        response = requests.get(f"{base_url}/api/config", timeout=5)
        if response.status_code == 200:
            config = response.json()
            print(f"Config: sample_hz={config.get('sample_hz')}")
        else:
            print(f"Config failed: {response.status_code}")
        
        print("✅ API tests completed")
        
    except Exception as e:
        print(f"❌ API test failed: {e}")

def main():
    """Run API integration test."""
    print("🔍 Testing API integration with shared memory...")
    
    # Start FastAPI server in background
    server_process = Process(target=start_fastapi_server, daemon=True)
    server_process.start()
    
    try:
        # Run API tests
        test_api_endpoints()
        
    finally:
        server_process.terminate()
        server_process.join(timeout=2.0)

if __name__ == "__main__":
    main()