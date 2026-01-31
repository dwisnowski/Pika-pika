#!/usr/bin/env python3
"""
Multiprocessing Integration Test Script

This script implements task 9 from the datalogger-multiprocessing spec:
- Verify all processes start and communicate correctly
- Test WebSocket streaming with shared memory data
- Verify API endpoints return correct data
- Test graceful shutdown sequence

This is a comprehensive integration test that validates the entire
multiprocessing architecture works as designed.
"""

import sys
import os
import time
import json
import asyncio
import threading
import requests
import websockets
import logging
from typing import Dict, List, Any, Optional
from multiprocessing import Process, Event
from contextlib import asynccontextmanager

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pika.shared_memory import SharedSampleBuffer, SharedAnalysisBuffer, SharedConfigBuffer
from pika.process_supervisor import ProcessSupervisor
from pika.datalogger_process import run_datalogger_process
from pika.event_logger_process import EventLoggerProcess
from pika.adapters import create_adc_adapter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MultiprocessingIntegrationTester:
    """Comprehensive integration tester for the multiprocessing architecture."""
    
    def __init__(self, test_port: int = 8001):
        self.test_port = test_port
        self.base_url = f"http://localhost:{test_port}"
        self.websocket_url = f"ws://localhost:{test_port}/ws"
        
        # Shared memory resources
        self.shared_sample_buffer: Optional[SharedSampleBuffer] = None
        self.shared_analysis_buffer: Optional[SharedAnalysisBuffer] = None
        self.shared_config_buffer: Optional[SharedConfigBuffer] = None
        
        # Process management
        self.supervisor: Optional[ProcessSupervisor] = None
        self.fastapi_process: Optional[Process] = None
        self.datalogger_process: Optional[Process] = None
        self.event_logger_process: Optional[EventLoggerProcess] = None
        
        # Test results
        self.test_results = {}
        self.cleanup_tasks = []
        
        # Test data directory
        self.test_data_dir = "test_data"
        os.makedirs(self.test_data_dir, exist_ok=True)
    
    def setup_shared_memory(self) -> bool:
        """Initialize shared memory structures."""
        logger.info("🔧 Setting up shared memory structures...")
        
        try:
            # Create shared memory buffers
            self.shared_sample_buffer = SharedSampleBuffer(size=1000, create=True)
            self.shared_analysis_buffer = SharedAnalysisBuffer(create=True)
            self.shared_config_buffer = SharedConfigBuffer(create=True)
            
            # Register for cleanup
            self.cleanup_tasks.extend([
                lambda: self.shared_sample_buffer.cleanup(),
                lambda: self.shared_analysis_buffer.cleanup(),
                lambda: self.shared_config_buffer.cleanup()
            ])
            
            # Initialize config buffer with test configuration
            test_config = {
                'sample_hz': 50,  # Lower rate for testing
                'batch_size': 10,
                'batch_interval_ms': 500,
                'analysis_config': {
                    'enable_rms': True,
                    'enable_freq': True,
                    'enable_sags_swells': True,
                    'nominal_voltage': 120.0,
                    'sag_threshold': 108.0,
                    'swell_threshold': 132.0
                },
                'display_fps': 2.0
            }
            self.shared_config_buffer.update_config(test_config)
            
            logger.info("✅ Shared memory structures initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to setup shared memory: {e}")
            return False
    
    def start_datalogger_process(self) -> bool:
        """Start the datalogger process."""
        logger.info("🚀 Starting datalogger process...")
        
        try:
            # Create datalogger process
            self.datalogger_process = Process(
                target=run_datalogger_process,
                args=(self.shared_sample_buffer, self.shared_config_buffer),
                kwargs={
                    'data_dir': self.test_data_dir,
                    'adc_type': 'mock',  # Use mock ADC for testing
                    'adc_config': {'signal_type': 'sine', 'frequency': 60.0, 'amplitude': 1.0},
                    'display_config': {'enabled': False}  # Disable display for testing
                },
                name="TestDatalogger"
            )
            
            self.datalogger_process.start()
            self.cleanup_tasks.append(lambda: self._stop_process(self.datalogger_process, "datalogger"))
            
            # Wait for process to initialize
            time.sleep(2.0)
            
            # Verify process is running
            if not self.datalogger_process.is_alive():
                logger.error("❌ Datalogger process failed to start")
                return False
            
            # Verify data is being written to shared memory
            time.sleep(1.0)  # Allow time for samples
            samples = self.shared_sample_buffer.read_recent(1.0)
            if len(samples) < 10:  # Should have at least 10 samples at 50Hz
                logger.error(f"❌ Expected at least 10 samples, got {len(samples)}")
                return False
            
            logger.info(f"✅ Datalogger process started, {len(samples)} samples in buffer")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start datalogger process: {e}")
            return False
    
    def start_event_logger_process(self) -> bool:
        """Start the event logger process."""
        logger.info("🚀 Starting event logger process...")
        
        try:
            # Create event logger process
            self.event_logger_process = EventLoggerProcess(
                sample_buffer_name=self.shared_sample_buffer.shm.name,
                analysis_buffer_name=self.shared_analysis_buffer.shm.name,
                config_buffer_name=self.shared_config_buffer.shm.name,
                data_dir=self.test_data_dir,
                analysis_interval=0.2,  # 5Hz for testing
                highlights_scan_interval=5  # 5 seconds for testing
            )
            
            self.event_logger_process.start()
            self.cleanup_tasks.append(lambda: self._stop_process(self.event_logger_process, "event_logger"))
            
            # Wait for process to initialize
            time.sleep(2.0)
            
            # Verify process is running
            if not self.event_logger_process.is_alive():
                logger.error("❌ Event logger process failed to start")
                return False
            
            # Verify analysis data is being written
            time.sleep(1.0)  # Allow time for analysis
            analysis = self.shared_analysis_buffer.get_current_analysis()
            if analysis.get('last_updated', 0) == 0:
                logger.error("❌ No analysis data found in shared buffer")
                return False
            
            logger.info(f"✅ Event logger process started, RMS: {analysis.get('rms', 0):.2f}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start event logger process: {e}")
            return False
    
    def start_fastapi_process(self) -> bool:
        """Start the FastAPI process."""
        logger.info("🚀 Starting FastAPI process...")
        
        try:
            # Create a custom FastAPI startup script for testing
            fastapi_script = f"""
import sys
import os
sys.path.insert(0, '{os.getcwd()}')

import uvicorn
from pika.app import app, initialize_shared_memory

# Initialize shared memory with existing buffers
from pika.shared_memory import SharedSampleBuffer, SharedAnalysisBuffer, SharedConfigBuffer

# Attach to existing shared memory
app.shared_sample_buffer = SharedSampleBuffer(create=False, name='{self.shared_sample_buffer.shm.name}')
app.shared_analysis_buffer = SharedAnalysisBuffer(create=False, name='{self.shared_analysis_buffer.shm.name}')
app.shared_config_buffer = SharedConfigBuffer(create=False, name='{self.shared_config_buffer.shm.name}')

# Update connection manager with shared memory buffers
from pika.app import manager
manager.sample_buffer = app.shared_sample_buffer
manager.analysis_buffer = app.shared_analysis_buffer

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port={self.test_port}, log_level="warning")
"""
            
            # Write the script to a temporary file
            script_path = os.path.join(self.test_data_dir, "test_fastapi.py")
            with open(script_path, 'w') as f:
                f.write(fastapi_script)
            
            # Start FastAPI process
            self.fastapi_process = Process(
                target=os.system,
                args=(f"cd {os.getcwd()} && uv run python {script_path}",),
                name="TestFastAPI"
            )
            
            self.fastapi_process.start()
            self.cleanup_tasks.append(lambda: self._stop_process(self.fastapi_process, "fastapi"))
            
            # Wait for FastAPI to start
            time.sleep(3.0)
            
            # Verify FastAPI is responding
            max_retries = 10
            for i in range(max_retries):
                try:
                    response = requests.get(f"{self.base_url}/health", timeout=2)
                    if response.status_code == 200:
                        logger.info("✅ FastAPI process started and responding")
                        return True
                except requests.exceptions.RequestException:
                    if i < max_retries - 1:
                        time.sleep(1.0)
                        continue
            
            logger.error("❌ FastAPI process failed to respond")
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to start FastAPI process: {e}")
            return False
    
    def test_process_communication(self) -> bool:
        """Test that all processes are communicating correctly via shared memory."""
        logger.info("🔍 Testing process communication...")
        
        try:
            # Wait for data to accumulate
            time.sleep(2.0)
            
            # Test 1: Verify datalogger is writing samples
            samples = self.shared_sample_buffer.read_recent(2.0)
            if len(samples) < 50:  # Should have ~100 samples at 50Hz over 2 seconds
                logger.error(f"❌ Insufficient samples from datalogger: {len(samples)}")
                return False
            
            # Test 2: Verify event logger is processing samples and writing analysis
            analysis = self.shared_analysis_buffer.get_current_analysis()
            if not self.shared_analysis_buffer.is_data_fresh(max_age_seconds=3.0):
                logger.error("❌ Analysis data is not fresh")
                return False
            
            if analysis.get('rms', 0) <= 0:
                logger.error(f"❌ Invalid RMS value: {analysis.get('rms')}")
                return False
            
            # Test 3: Verify configuration propagation
            original_config, original_version = self.shared_config_buffer.get_config()
            
            # Update sample rate
            new_config = original_config.copy()
            new_config['sample_hz'] = 75
            new_version = self.shared_config_buffer.update_config(new_config)
            
            # Wait for processes to pick up the change
            time.sleep(2.0)
            
            # Verify version was updated
            if new_version <= original_version:
                logger.error(f"❌ Config version not updated: {new_version} <= {original_version}")
                return False
            
            logger.info("✅ Process communication tests passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Process communication test failed: {e}")
            return False
    
    def test_api_endpoints(self) -> bool:
        """Test that API endpoints return correct data from shared memory."""
        logger.info("🔍 Testing API endpoints...")
        
        try:
            # Test /api/recent endpoint
            response = requests.get(f"{self.base_url}/api/recent", timeout=5)
            if response.status_code != 200:
                logger.error(f"❌ /api/recent returned status {response.status_code}")
                return False
            
            recent_data = response.json()
            if not isinstance(recent_data, list) or len(recent_data) == 0:
                logger.error(f"❌ /api/recent returned invalid data: {type(recent_data)}")
                return False
            
            # Verify data format
            sample = recent_data[0]
            if not isinstance(sample, list) or len(sample) != 2:
                logger.error(f"❌ Invalid sample format: {sample}")
                return False
            
            # Test /api/config endpoint
            response = requests.get(f"{self.base_url}/api/config", timeout=5)
            if response.status_code != 200:
                logger.error(f"❌ /api/config returned status {response.status_code}")
                return False
            
            config_data = response.json()
            if not isinstance(config_data, dict):
                logger.error(f"❌ /api/config returned invalid data: {type(config_data)}")
                return False
            
            # Test configuration update via API
            update_data = {"sample_hz": 60}
            response = requests.post(f"{self.base_url}/api/config", json=update_data, timeout=5)
            if response.status_code != 200:
                logger.error(f"❌ POST /api/config returned status {response.status_code}")
                return False
            
            # Verify the update was applied
            time.sleep(1.0)
            config, _ = self.shared_config_buffer.get_config()
            if config.get('sample_hz') != 60:
                logger.error(f"❌ Config update not applied: {config.get('sample_hz')}")
                return False
            
            # Test /api/highlights endpoint (should exist even if empty)
            response = requests.get(f"{self.base_url}/api/highlights", timeout=5)
            if response.status_code != 200:
                logger.error(f"❌ /api/highlights returned status {response.status_code}")
                return False
            
            highlights_data = response.json()
            if not isinstance(highlights_data, list):
                logger.error(f"❌ /api/highlights returned invalid data: {type(highlights_data)}")
                return False
            
            logger.info("✅ API endpoint tests passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ API endpoint test failed: {e}")
            return False
    
    async def test_websocket_streaming(self) -> bool:
        """Test WebSocket streaming with shared memory data."""
        logger.info("🔍 Testing WebSocket streaming...")
        
        try:
            messages_received = []
            test_duration = 5.0  # Test for 5 seconds
            
            async with websockets.connect(self.websocket_url) as websocket:
                logger.info("Connected to WebSocket")
                
                # Collect messages for the test duration
                start_time = time.time()
                while time.time() - start_time < test_duration:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)
                        messages_received.append(data)
                        
                        if len(messages_received) >= 10:  # Got enough messages
                            break
                            
                    except asyncio.TimeoutError:
                        continue
            
            if len(messages_received) == 0:
                logger.error("❌ No WebSocket messages received")
                return False
            
            # Verify message format
            sample_message = messages_received[0]
            required_fields = ['samples', 'analysis']
            for field in required_fields:
                if field not in sample_message:
                    logger.error(f"❌ Missing field '{field}' in WebSocket message")
                    return False
            
            # Verify samples data
            samples = sample_message['samples']
            if not isinstance(samples, list) or len(samples) == 0:
                logger.error(f"❌ Invalid samples data in WebSocket: {type(samples)}")
                return False
            
            # Verify analysis data
            analysis = sample_message['analysis']
            if not isinstance(analysis, dict):
                logger.error(f"❌ Invalid analysis data in WebSocket: {type(analysis)}")
                return False
            
            # Check that we're getting regular updates
            if len(messages_received) < 3:
                logger.error(f"❌ Too few WebSocket messages: {len(messages_received)}")
                return False
            
            logger.info(f"✅ WebSocket streaming tests passed ({len(messages_received)} messages)")
            return True
            
        except Exception as e:
            logger.error(f"❌ WebSocket streaming test failed: {e}")
            return False
    
    def test_graceful_shutdown(self) -> bool:
        """Test graceful shutdown sequence."""
        logger.info("🔍 Testing graceful shutdown sequence...")
        
        try:
            # Record initial process states
            initial_states = {
                'datalogger': self.datalogger_process.is_alive() if self.datalogger_process else False,
                'event_logger': self.event_logger_process.is_alive() if self.event_logger_process else False,
                'fastapi': self.fastapi_process.is_alive() if self.fastapi_process else False
            }
            
            logger.info(f"Initial process states: {initial_states}")
            
            # Test individual process shutdown
            if self.event_logger_process and self.event_logger_process.is_alive():
                logger.info("Stopping event logger process...")
                self.event_logger_process.stop()
                self.event_logger_process.join(timeout=5.0)
                
                if self.event_logger_process.is_alive():
                    logger.error("❌ Event logger process did not stop gracefully")
                    return False
                logger.info("✅ Event logger stopped gracefully")
            
            if self.datalogger_process and self.datalogger_process.is_alive():
                logger.info("Stopping datalogger process...")
                self.datalogger_process.terminate()
                self.datalogger_process.join(timeout=5.0)
                
                if self.datalogger_process.is_alive():
                    logger.error("❌ Datalogger process did not stop gracefully")
                    return False
                logger.info("✅ Datalogger stopped gracefully")
            
            if self.fastapi_process and self.fastapi_process.is_alive():
                logger.info("Stopping FastAPI process...")
                self.fastapi_process.terminate()
                self.fastapi_process.join(timeout=5.0)
                
                if self.fastapi_process.is_alive():
                    logger.error("❌ FastAPI process did not stop gracefully")
                    return False
                logger.info("✅ FastAPI stopped gracefully")
            
            # Verify shared memory is still accessible after process shutdown
            try:
                buffer_info = self.shared_sample_buffer.get_buffer_info()
                logger.info(f"Shared memory still accessible: {buffer_info['count']} samples")
            except Exception as e:
                logger.error(f"❌ Shared memory corrupted after shutdown: {e}")
                return False
            
            logger.info("✅ Graceful shutdown tests passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Graceful shutdown test failed: {e}")
            return False
    
    def _stop_process(self, process: Process, name: str) -> None:
        """Helper to stop a process gracefully."""
        if process and process.is_alive():
            logger.info(f"Stopping {name} process...")
            try:
                if hasattr(process, 'stop'):
                    process.stop()
                else:
                    process.terminate()
                process.join(timeout=3.0)
                
                if process.is_alive():
                    logger.warning(f"{name} process did not stop gracefully, killing...")
                    process.kill()
                    process.join(timeout=1.0)
                    
            except Exception as e:
                logger.error(f"Error stopping {name} process: {e}")
    
    def cleanup(self) -> None:
        """Clean up all test resources."""
        logger.info("🧹 Cleaning up test resources...")
        
        # Run cleanup tasks in reverse order
        for cleanup_task in reversed(self.cleanup_tasks):
            try:
                cleanup_task()
            except Exception as e:
                logger.warning(f"Cleanup task failed: {e}")
        
        self.cleanup_tasks.clear()
        
        # Clean up test data directory
        try:
            import shutil
            if os.path.exists(self.test_data_dir):
                shutil.rmtree(self.test_data_dir)
        except Exception as e:
            logger.warning(f"Failed to clean up test data directory: {e}")
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all integration tests and return results."""
        logger.info("🚀 Starting multiprocessing integration tests...")
        
        test_results = {
            'setup_shared_memory': False,
            'start_datalogger': False,
            'start_event_logger': False,
            'start_fastapi': False,
            'process_communication': False,
            'api_endpoints': False,
            'websocket_streaming': False,
            'graceful_shutdown': False,
            'overall_success': False
        }
        
        try:
            # Test 1: Setup shared memory
            test_results['setup_shared_memory'] = self.setup_shared_memory()
            if not test_results['setup_shared_memory']:
                return test_results
            
            # Test 2: Start datalogger process
            test_results['start_datalogger'] = self.start_datalogger_process()
            if not test_results['start_datalogger']:
                return test_results
            
            # Test 3: Start event logger process
            test_results['start_event_logger'] = self.start_event_logger_process()
            if not test_results['start_event_logger']:
                return test_results
            
            # Test 4: Start FastAPI process
            test_results['start_fastapi'] = self.start_fastapi_process()
            if not test_results['start_fastapi']:
                return test_results
            
            # Test 5: Process communication
            test_results['process_communication'] = self.test_process_communication()
            
            # Test 6: API endpoints
            test_results['api_endpoints'] = self.test_api_endpoints()
            
            # Test 7: WebSocket streaming
            try:
                test_results['websocket_streaming'] = asyncio.run(self.test_websocket_streaming())
            except Exception as e:
                logger.error(f"WebSocket test failed: {e}")
                test_results['websocket_streaming'] = False
            
            # Test 8: Graceful shutdown
            test_results['graceful_shutdown'] = self.test_graceful_shutdown()
            
            # Overall success
            test_results['overall_success'] = all([
                test_results['setup_shared_memory'],
                test_results['start_datalogger'],
                test_results['start_event_logger'],
                test_results['start_fastapi'],
                test_results['process_communication'],
                test_results['api_endpoints'],
                test_results['websocket_streaming'],
                test_results['graceful_shutdown']
            ])
            
            return test_results
            
        except Exception as e:
            logger.error(f"Integration test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            return test_results
        
        finally:
            self.cleanup()


def main():
    """Main test function."""
    
    print("=" * 80)
    print("🔧 MULTIPROCESSING INTEGRATION TEST")
    print("=" * 80)
    print()
    print("This script implements task 9 from the datalogger-multiprocessing spec:")
    print("- Verify all processes start and communicate correctly")
    print("- Test WebSocket streaming with shared memory data")
    print("- Verify API endpoints return correct data")
    print("- Test graceful shutdown sequence")
    print()
    
    tester = MultiprocessingIntegrationTester()
    
    try:
        # Run all tests
        results = tester.run_all_tests()
        
        print()
        print("=" * 80)
        print("📊 INTEGRATION TEST RESULTS")
        print("=" * 80)
        
        print(f"Overall Success: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}")
        print()
        
        print("Individual Test Results:")
        test_descriptions = {
            'setup_shared_memory': 'Shared Memory Setup',
            'start_datalogger': 'Datalogger Process Start',
            'start_event_logger': 'Event Logger Process Start',
            'start_fastapi': 'FastAPI Process Start',
            'process_communication': 'Process Communication',
            'api_endpoints': 'API Endpoints',
            'websocket_streaming': 'WebSocket Streaming',
            'graceful_shutdown': 'Graceful Shutdown'
        }
        
        for test_key, description in test_descriptions.items():
            status = "✅ PASS" if results.get(test_key, False) else "❌ FAIL"
            print(f"  {description}: {status}")
        
        print()
        print("=" * 80)
        
        if results['overall_success']:
            print("🎉 ALL MULTIPROCESSING INTEGRATION TESTS PASSED!")
            print("✅ The multiprocessing architecture is working correctly.")
            print("✅ All processes start and communicate properly.")
            print("✅ WebSocket streaming works with shared memory data.")
            print("✅ API endpoints return correct data from shared memory.")
            print("✅ Graceful shutdown sequence works as designed.")
            return 0
        else:
            print("💥 MULTIPROCESSING INTEGRATION TESTS FAILED!")
            print("❌ Fix the failing components before proceeding.")
            
            # Provide specific guidance based on failures
            if not results.get('setup_shared_memory'):
                print("   → Check shared memory implementation")
            if not results.get('start_datalogger'):
                print("   → Check datalogger process implementation")
            if not results.get('start_event_logger'):
                print("   → Check event logger process implementation")
            if not results.get('start_fastapi'):
                print("   → Check FastAPI integration with shared memory")
            if not results.get('process_communication'):
                print("   → Check inter-process communication via shared memory")
            if not results.get('api_endpoints'):
                print("   → Check API endpoint implementation")
            if not results.get('websocket_streaming'):
                print("   → Check WebSocket integration with shared memory")
            if not results.get('graceful_shutdown'):
                print("   → Check process shutdown handling")
            
            return 1
    
    except KeyboardInterrupt:
        print("\n⚠️  Integration test interrupted by user")
        return 1
    
    except Exception as e:
        print(f"\n💥 Integration test failed with unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        tester.cleanup()


if __name__ == "__main__":
    sys.exit(main())