#!/usr/bin/env python3
"""
Test script to verify WebSocket handler integration with shared memory.
"""

import asyncio
import time
from pika.shared_memory import SharedSampleBuffer, SharedAnalysisBuffer
from pika.websocket.live_manager import ConnectionManager


async def test_websocket_shared_memory():
    """Test WebSocket manager with shared memory buffers."""
    print("Testing WebSocket handler with shared memory integration...")
    
    # Create shared memory buffers
    sample_buffer = SharedSampleBuffer(size=100, create=True)
    analysis_buffer = SharedAnalysisBuffer(create=True)
    
    # Create connection manager with shared memory
    manager = ConnectionManager(sample_buffer=sample_buffer, analysis_buffer=analysis_buffer)
    
    try:
        # Test 1: Add some sample data to shared memory
        print("\n1. Testing sample data writing...")
        current_time = time.time()
        for i in range(10):
            timestamp = current_time + i * 0.01  # 100Hz simulation
            value = 1.5 + 0.5 * (i % 3)  # Simple test pattern
            sample_buffer.write_sample(timestamp, value)
        
        # Test 2: Check if manager can read recent data
        print("2. Testing recent data retrieval...")
        recent_data = manager.get_recent_data(1.0)  # Last 1 second
        print(f"   Retrieved {len(recent_data)} samples")
        if recent_data:
            print(f"   Latest sample: {recent_data[-1]}")
        
        # Test 3: Add analysis data
        print("3. Testing analysis data...")
        analysis_buffer.update_metrics(
            rms=1.7,
            frequency=60.1,
            events=[{'type': 'sag', 'start': current_time, 'duration': 0.1}]
        )
        
        # Test 4: Check analysis retrieval
        analysis_data = manager.get_current_analysis()
        print(f"   Analysis RMS: {analysis_data.get('rms', 'N/A')}")
        print(f"   Analysis Frequency: {analysis_data.get('frequency', 'N/A')}")
        
        # Test 5: Check connection status
        print("4. Testing connection status...")
        status = manager.get_connection_status()
        print(f"   Datalogger available: {status.get('datalogger_available', False)}")
        print(f"   Mode: {status.get('mode', 'unknown')}")
        
        # Test 6: Test graceful degradation (no shared memory)
        print("5. Testing graceful degradation...")
        degraded_manager = ConnectionManager()  # No shared memory buffers
        degraded_status = degraded_manager.get_connection_status()
        print(f"   Degraded mode: {degraded_status.get('mode', 'unknown')}")
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise
    finally:
        # Cleanup
        try:
            sample_buffer.cleanup()
            analysis_buffer.cleanup()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(test_websocket_shared_memory())