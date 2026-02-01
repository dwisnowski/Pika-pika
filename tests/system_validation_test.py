#!/usr/bin/env python3
"""
System validation test for the multiprocessing datalogger architecture.

This script performs comprehensive validation of the complete system including:
- Component imports and initialization
- Shared memory functionality
- Process supervision capabilities
- Configuration management
- Hardware adapter pattern
- API compatibility
"""

import os
import sys
import time
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SystemValidationTest:
    """Comprehensive system validation test suite."""
    
    def __init__(self):
        """Initialize validation test."""
        self.test_results: Dict[str, bool] = {}
        self.test_errors: Dict[str, str] = {}
        self.temp_dir = None
        
    def setup_test_environment(self) -> bool:
        """Setup temporary test environment."""
        try:
            self.temp_dir = tempfile.mkdtemp(prefix="pika_validation_")
            logger.info(f"Created test environment: {self.temp_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to setup test environment: {e}")
            return False
    
    def cleanup_test_environment(self) -> None:
        """Cleanup test environment."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logger.info("Cleaned up test environment")
            except Exception as e:
                logger.warning(f"Failed to cleanup test environment: {e}")
    
    def test_component_imports(self) -> bool:
        """Test that all core components can be imported."""
        try:
            logger.info("Testing component imports...")
            
            # Test core module imports
            import pika.main
            import pika.shared_memory
            import pika.process_supervisor
            import pika.datalogger_process
            import pika.event_logger_process
            import pika.config
            import pika.error_handling
            import pika.performance_optimizer
            
            # Test adapter imports
            import pika.adapters.adc_adapter
            import pika.adapters.ads1115_adapter
            import pika.adapters.mock_adc_adapter
            
            # Test FastAPI app import
            import pika.app
            
            logger.info("✓ All component imports successful")
            return True
            
        except Exception as e:
            logger.error(f"✗ Component import failed: {e}")
            return False
    
    def test_shared_memory_functionality(self) -> bool:
        """Test shared memory buffer functionality."""
        try:
            logger.info("Testing shared memory functionality...")
            
            from pika.shared_memory import SharedSampleBuffer, SharedAnalysisBuffer, SharedConfigBuffer
            
            # Test sample buffer
            sample_buffer = SharedSampleBuffer(size=100, create=True, name="test_samples")
            
            # Write some test samples
            import time
            for i in range(10):
                sample_buffer.write_sample(time.time() + i, float(i))
            
            # Read recent samples
            recent = sample_buffer.read_recent(5.0)
            assert len(recent) == 10, f"Expected 10 samples, got {len(recent)}"
            
            # Test analysis buffer
            analysis_buffer = SharedAnalysisBuffer(create=True, name="test_analysis")
            
            test_metrics = {
                'rms': 120.5,
                'frequency': 60.0,
                'sags_swells': [],
                'last_updated': time.time()
            }
            
            analysis_buffer.update_metrics(test_metrics)
            retrieved_metrics = analysis_buffer.get_current_analysis()
            assert retrieved_metrics['rms'] == 120.5, "Analysis buffer data mismatch"
            
            # Test config buffer
            config_buffer = SharedConfigBuffer(create=True, name="test_config")
            
            test_config = {
                'sample_hz': 100,
                'batch_size': 10,
                'analysis_config': {'threshold': 0.1}
            }
            
            config_buffer.update_config(test_config)
            retrieved_config, version = config_buffer.get_config()
            assert retrieved_config['sample_hz'] == 100, "Config buffer data mismatch"
            
            # Cleanup
            sample_buffer.cleanup()
            analysis_buffer.cleanup()
            config_buffer.cleanup()
            
            logger.info("✓ Shared memory functionality test passed")
            return True
            
        except Exception as e:
            logger.error(f"✗ Shared memory functionality test failed: {e}")
            return False
    
    def test_adc_adapter_pattern(self) -> bool:
        """Test ADC adapter pattern functionality."""
        try:
            logger.info("Testing ADC adapter pattern...")
            
            from pika.adapters.adc_adapter import create_adc_adapter
            from pika.adapters.mock_adc_adapter import MockADCAdapter
            
            # Test mock adapter creation
            mock_adapter = create_adc_adapter('mock', {})
            assert isinstance(mock_adapter, MockADCAdapter), "Mock adapter creation failed"
            
            # Test adapter initialization
            assert mock_adapter.initialize({}), "Mock adapter initialization failed"
            
            # Test sample reading
            sample = mock_adapter.read_sample()
            assert isinstance(sample, float), "Sample reading failed"
            assert -5.0 <= sample <= 5.0, "Sample out of expected range"
            
            # Test sample rate setting
            assert mock_adapter.set_sample_rate(100), "Sample rate setting failed"
            
            # Test cleanup
            mock_adapter.cleanup()
            
            # Test hardware fallback
            try:
                # This should fallback to mock if ADS1115 hardware not available
                ads_adapter = create_adc_adapter('ads1115', {})
                logger.info("ADS1115 adapter created (or fell back to mock)")
            except Exception as e:
                logger.info(f"ADS1115 fallback behavior: {e}")
            
            logger.info("✓ ADC adapter pattern test passed")
            return True
            
        except Exception as e:
            logger.error(f"✗ ADC adapter pattern test failed: {e}")
            return False
    
    def test_process_supervisor(self) -> bool:
        """Test process supervisor functionality."""
        try:
            logger.info("Testing process supervisor...")
            
            from pika.process_supervisor import ProcessSupervisor
            
            # Create supervisor
            supervisor = ProcessSupervisor()
            
            # Test process registration
            def dummy_process():
                time.sleep(0.1)
                return True
            
            supervisor.register_process(
                name="test_process",
                target=dummy_process,
                args=(),
                max_restarts=1
            )
            
            # Test process start
            assert supervisor.start_process("test_process"), "Process start failed"
            
            # Wait for process to complete
            time.sleep(0.2)
            
            # Test status retrieval
            status = supervisor.get_all_status()
            assert "test_process" in status, "Process status not found"
            
            # Test graceful shutdown
            supervisor.graceful_shutdown(timeout=1.0)
            
            logger.info("✓ Process supervisor test passed")
            return True
            
        except Exception as e:
            logger.error(f"✗ Process supervisor test failed: {e}")
            return False
    
    def test_configuration_management(self) -> bool:
        """Test configuration management functionality."""
        try:
            logger.info("Testing configuration management...")
            
            from pika.config import ConfigurationManager
            
            # Test with default config file
            config_manager = ConfigurationManager("config.toml")
            
            # Test configuration loading
            config = config_manager.load_configuration()
            assert isinstance(config, dict), "Configuration not loaded as dict"
            assert "pika" in config, "Missing pika section in config"
            
            # Test process config extraction
            datalogger_config = config_manager.get_process_config('datalogger')
            assert isinstance(datalogger_config, dict), "Datalogger config not extracted"
            
            # Test shared config data
            shared_config = config_manager.get_shared_config_data()
            assert isinstance(shared_config, dict), "Shared config data not extracted"
            
            logger.info("✓ Configuration management test passed")
            return True
            
        except Exception as e:
            logger.error(f"✗ Configuration management test failed: {e}")
            return False
    
    def test_error_handling_system(self) -> bool:
        """Test error handling system functionality."""
        try:
            logger.info("Testing error handling system...")
            
            from pika.error_handling import setup_error_handling, ErrorSeverity, ErrorCategory
            
            # Setup error handler
            error_handler = setup_error_handling(
                log_dir=self.temp_dir,
                enable_console=False
            )
            
            # Test error handling
            test_error = ValueError("Test error")
            error_handler.handle_error(
                test_error, "test_component", ErrorSeverity.LOW, ErrorCategory.VALIDATION
            )
            
            # Check that error was logged
            error_log_path = Path(self.temp_dir) / "pika_errors.log"
            assert error_log_path.exists(), "Error log file not created"
            
            logger.info("✓ Error handling system test passed")
            return True
            
        except Exception as e:
            logger.error(f"✗ Error handling system test failed: {e}")
            return False
    
    def test_performance_optimization(self) -> bool:
        """Test performance optimization functionality."""
        try:
            logger.info("Testing performance optimization...")
            
            from pika.performance_optimizer import PerformanceOptimizer
            
            # Create performance optimizer
            optimizer = PerformanceOptimizer(
                enable_monitoring=False,  # Disable monitoring for test
                monitoring_interval=1.0
            )
            
            # Test CPU affinity setting (may not work on all systems)
            try:
                optimizer.set_process_affinity(os.getpid(), 0)
                logger.info("CPU affinity setting successful")
            except Exception as e:
                logger.info(f"CPU affinity not supported: {e}")
            
            # Test memory optimization
            optimizer.optimize_memory_usage()
            
            logger.info("✓ Performance optimization test passed")
            return True
            
        except Exception as e:
            logger.error(f"✗ Performance optimization test failed: {e}")
            return False
    
    def test_api_compatibility(self) -> bool:
        """Test API compatibility and FastAPI app."""
        try:
            logger.info("Testing API compatibility...")
            
            from pika.app import app
            from fastapi.testclient import TestClient
            
            # Create test client
            client = TestClient(app)
            
            # Test health endpoint
            response = client.get("/health")
            assert response.status_code == 200, f"Health endpoint failed: {response.status_code}"
            
            # Test main page
            response = client.get("/")
            assert response.status_code == 200, f"Main page failed: {response.status_code}"
            
            logger.info("✓ API compatibility test passed")
            return True
            
        except Exception as e:
            logger.error(f"✗ API compatibility test failed: {e}")
            return False
    
    def run_all_tests(self) -> Dict[str, bool]:
        """Run all validation tests."""
        logger.info("Starting comprehensive system validation")
        
        # Setup test environment
        if not self.setup_test_environment():
            return {"setup": False}
        
        try:
            # Define test methods
            tests = [
                ("component_imports", self.test_component_imports),
                ("shared_memory", self.test_shared_memory_functionality),
                ("adc_adapters", self.test_adc_adapter_pattern),
                ("process_supervisor", self.test_process_supervisor),
                ("configuration", self.test_configuration_management),
                ("error_handling", self.test_error_handling_system),
                ("performance_optimization", self.test_performance_optimization),
                ("api_compatibility", self.test_api_compatibility),
            ]
            
            # Run each test
            for test_name, test_method in tests:
                try:
                    logger.info(f"\n--- Running {test_name} test ---")
                    result = test_method()
                    self.test_results[test_name] = result
                    
                    if result:
                        logger.info(f"✓ {test_name} test PASSED")
                    else:
                        logger.error(f"✗ {test_name} test FAILED")
                        
                except Exception as e:
                    logger.error(f"✗ {test_name} test ERROR: {e}")
                    self.test_results[test_name] = False
                    self.test_errors[test_name] = str(e)
            
            return self.test_results
            
        finally:
            self.cleanup_test_environment()
    
    def print_summary(self) -> None:
        """Print test results summary."""
        logger.info("\n" + "="*60)
        logger.info("SYSTEM VALIDATION SUMMARY")
        logger.info("="*60)
        
        passed = sum(1 for result in self.test_results.values() if result)
        total = len(self.test_results)
        
        logger.info(f"Tests passed: {passed}/{total}")
        
        if passed == total:
            logger.info("🎉 ALL TESTS PASSED - System validation successful!")
        else:
            logger.warning(f"⚠️  {total - passed} tests failed - System needs attention")
        
        logger.info("\nDetailed Results:")
        for test_name, result in self.test_results.items():
            status = "✓ PASS" if result else "✗ FAIL"
            logger.info(f"  {test_name}: {status}")
            
            if not result and test_name in self.test_errors:
                logger.info(f"    Error: {self.test_errors[test_name]}")
        
        logger.info("="*60)


def main():
    """Main entry point for system validation."""
    validator = SystemValidationTest()
    
    try:
        # Run all validation tests
        results = validator.run_all_tests()
        
        # Print summary
        validator.print_summary()
        
        # Exit with appropriate code
        all_passed = all(results.values())
        sys.exit(0 if all_passed else 1)
        
    except KeyboardInterrupt:
        logger.info("Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Validation failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()