"""
Configuration loading and validation for the multiprocessing datalogger.

This module provides centralized configuration management with validation
and default value handling for all processes in the multiprocessing architecture.
"""

import os
import logging
from typing import Dict, Any, List, Tuple, Optional

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback for older versions

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""
    pass


class ConfigurationManager:
    """
    Centralized configuration manager for the multiprocessing datalogger.
    
    Handles loading, validation, and default value management for all
    configuration parameters used across the different processes.
    """
    
    def __init__(self, config_path: str = "config.toml"):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to TOML configuration file
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self._validation_errors: List[str] = []
        
    def load_configuration(self) -> Dict[str, Any]:
        """
        Load configuration from TOML file with validation.
        
        Returns:
            Dictionary containing validated configuration
            
        Raises:
            ConfigurationError: If configuration validation fails
        """
        try:
            # Load configuration from file
            if os.path.exists(self.config_path):
                with open(self.config_path, "rb") as f:
                    self.config = tomllib.load(f)
                logger.info(f"Configuration loaded from {self.config_path}")
            else:
                logger.warning(f"Configuration file {self.config_path} not found, using defaults")
                self.config = {}
            
            # Apply defaults and validate
            self.config = self._apply_defaults(self.config)
            self._validate_configuration()
            
            if self._validation_errors:
                error_msg = f"Configuration validation failed: {'; '.join(self._validation_errors)}"
                logger.error(error_msg)
                raise ConfigurationError(error_msg)
            
            logger.info("Configuration validation completed successfully")
            return self.config
            
        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            logger.error(f"Failed to load configuration: {e}")
            raise ConfigurationError(f"Configuration loading failed: {e}")
    
    def _apply_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply default values for missing configuration sections."""
        defaults = self._get_default_configuration()
        
        # Merge defaults with loaded configuration
        merged_config = {}
        for section, default_values in defaults.items():
            if section in config:
                # Merge section-specific values
                merged_section = default_values.copy()
                merged_section.update(config[section])
                merged_config[section] = merged_section
            else:
                # Use entire default section
                merged_config[section] = default_values.copy()
                logger.info(f"Using default configuration for section: {section}")
        
        return merged_config
    
    def _get_default_configuration(self) -> Dict[str, Any]:
        """Get default configuration values."""
        return {
            "pika": {
                "sample_hz": 100,
                "data_dir": "data",
                "port": 8000,
                "display_fps": 5.0,
                "display_auto_ip": True
            },
            "pins": {
                "adc_address": 0x48,
                "adc_channel": 0,
                "lcd_port": 0,
                "lcd_device": 0,
                "lcd_cs": 8,
                "lcd_dc": 25,
                "lcd_rst": 27,
                "lcd_bl": 24
            },
            "datalogger": {
                "batch_size": 100,
                "batch_interval_ms": 1000,
                "retention_days": 5,
                "filename_prefix": "log"
            },
            "analysis": {
                "enable_rms": True,
                "enable_freq": True,
                "enable_sags_swells": True,
                "nominal_voltage": 120.0,
                "sag_threshold": 108.0,  # 90% of nominal
                "swell_threshold": 132.0,  # 110% of nominal
                "dc_offset": 1.65,
                "rms_window_size": 100,
                "frequency_detection": True,
                "event_min_duration_ms": 50
            },
            "display": {
                "rotation": 270,
                "refresh_rate": 30,
                "qr_size": 60
            },
            "multiprocessing": {
                "heartbeat_interval": 5.0,
                "restart_delay": 2.0,
                "max_restarts": 5,
                "shutdown_timeout": 30.0
            },
            "systemd": {
                "enable_watchdog": True,
                "stale_threshold": 3.0
            }
        }
    
    def _validate_configuration(self) -> None:
        """Validate configuration parameters."""
        self._validation_errors = []
        
        try:
            # Validate required sections
            required_sections = ["pika", "pins", "datalogger", "analysis"]
            for section in required_sections:
                if section not in self.config:
                    self._validation_errors.append(f"Missing required section: {section}")
            
            # Validate pika section
            if "pika" in self.config:
                self._validate_pika_section(self.config["pika"])
            
            # Validate pins section
            if "pins" in self.config:
                self._validate_pins_section(self.config["pins"])
            
            # Validate datalogger section
            if "datalogger" in self.config:
                self._validate_datalogger_section(self.config["datalogger"])
            
            # Validate analysis section
            if "analysis" in self.config:
                self._validate_analysis_section(self.config["analysis"])
            
            # Validate display section
            if "display" in self.config:
                self._validate_display_section(self.config["display"])
            
            # Validate multiprocessing section
            if "multiprocessing" in self.config:
                self._validate_multiprocessing_section(self.config["multiprocessing"])
            
        except Exception as e:
            self._validation_errors.append(f"Validation error: {e}")
    
    def _validate_pika_section(self, pika_config: Dict[str, Any]) -> None:
        """Validate pika configuration section."""
        # Sample rate validation
        sample_hz = pika_config.get("sample_hz", 100)
        if not isinstance(sample_hz, int) or not (1 <= sample_hz <= 860):
            self._validation_errors.append(f"sample_hz must be integer between 1-860, got: {sample_hz}")
            pika_config["sample_hz"] = 100
        
        # Data directory validation
        data_dir = pika_config.get("data_dir", "data")
        if not isinstance(data_dir, str) or not data_dir.strip():
            self._validation_errors.append(f"data_dir must be non-empty string, got: {data_dir}")
            pika_config["data_dir"] = "data"
        else:
            # Ensure data directory exists
            try:
                os.makedirs(data_dir, exist_ok=True)
            except Exception as e:
                self._validation_errors.append(f"Cannot create data directory {data_dir}: {e}")
        
        # Port validation
        port = pika_config.get("port", 8000)
        if not isinstance(port, int) or not (1024 <= port <= 65535):
            self._validation_errors.append(f"port must be integer between 1024-65535, got: {port}")
            pika_config["port"] = 8000
        
        # Display FPS validation
        display_fps = pika_config.get("display_fps", 5.0)
        if not isinstance(display_fps, (int, float)) or not (0.1 <= display_fps <= 60.0):
            self._validation_errors.append(f"display_fps must be number between 0.1-60.0, got: {display_fps}")
            pika_config["display_fps"] = 5.0
        
        # Display auto IP validation
        display_auto_ip = pika_config.get("display_auto_ip", True)
        if not isinstance(display_auto_ip, bool):
            self._validation_errors.append(f"display_auto_ip must be boolean, got: {display_auto_ip}")
            pika_config["display_auto_ip"] = True
    
    def _validate_pins_section(self, pins_config: Dict[str, Any]) -> None:
        """Validate pins configuration section."""
        # ADC address validation (I2C address)
        adc_address = pins_config.get("adc_address", 0x48)
        if not isinstance(adc_address, int) or not (0x08 <= adc_address <= 0x77):
            self._validation_errors.append(f"adc_address must be valid I2C address (0x08-0x77), got: {hex(adc_address) if isinstance(adc_address, int) else adc_address}")
            pins_config["adc_address"] = 0x48
        
        # ADC channel validation
        adc_channel = pins_config.get("adc_channel", 0)
        if not isinstance(adc_channel, int) or not (0 <= adc_channel <= 3):
            self._validation_errors.append(f"adc_channel must be integer 0-3, got: {adc_channel}")
            pins_config["adc_channel"] = 0
        
        # LCD pin validations (GPIO pin numbers)
        lcd_pins = ["lcd_cs", "lcd_dc", "lcd_rst", "lcd_bl"]
        for pin_name in lcd_pins:
            pin_value = pins_config.get(pin_name, 0)
            if not isinstance(pin_value, int) or not (0 <= pin_value <= 40):
                self._validation_errors.append(f"{pin_name} must be valid GPIO pin (0-40), got: {pin_value}")
                pins_config[pin_name] = {"lcd_cs": 8, "lcd_dc": 25, "lcd_rst": 27, "lcd_bl": 24}[pin_name]
        
        # SPI port and device validation
        lcd_port = pins_config.get("lcd_port", 0)
        if not isinstance(lcd_port, int) or not (0 <= lcd_port <= 1):
            self._validation_errors.append(f"lcd_port must be 0 or 1, got: {lcd_port}")
            pins_config["lcd_port"] = 0
        
        lcd_device = pins_config.get("lcd_device", 0)
        if not isinstance(lcd_device, int) or not (0 <= lcd_device <= 1):
            self._validation_errors.append(f"lcd_device must be 0 or 1, got: {lcd_device}")
            pins_config["lcd_device"] = 0
    
    def _validate_datalogger_section(self, datalogger_config: Dict[str, Any]) -> None:
        """Validate datalogger configuration section."""
        # Batch size validation
        batch_size = datalogger_config.get("batch_size", 100)
        if not isinstance(batch_size, int) or not (1 <= batch_size <= 10000):
            self._validation_errors.append(f"batch_size must be integer between 1-10000, got: {batch_size}")
            datalogger_config["batch_size"] = 100
        
        # Batch interval validation
        batch_interval_ms = datalogger_config.get("batch_interval_ms", 1000)
        if not isinstance(batch_interval_ms, int) or not (100 <= batch_interval_ms <= 60000):
            self._validation_errors.append(f"batch_interval_ms must be integer between 100-60000, got: {batch_interval_ms}")
            datalogger_config["batch_interval_ms"] = 1000
        
        # Retention days validation
        retention_days = datalogger_config.get("retention_days", 5)
        if not isinstance(retention_days, int) or not (1 <= retention_days <= 365):
            self._validation_errors.append(f"retention_days must be integer between 1-365, got: {retention_days}")
            datalogger_config["retention_days"] = 5
        
        # Filename prefix validation
        filename_prefix = datalogger_config.get("filename_prefix", "log")
        if not isinstance(filename_prefix, str) or not filename_prefix.strip():
            self._validation_errors.append(f"filename_prefix must be non-empty string, got: {filename_prefix}")
            datalogger_config["filename_prefix"] = "log"
    
    def _validate_analysis_section(self, analysis_config: Dict[str, Any]) -> None:
        """Validate analysis configuration section."""
        # Boolean parameter validation
        bool_params = ["enable_rms", "enable_freq", "enable_sags_swells", "frequency_detection"]
        for param in bool_params:
            value = analysis_config.get(param, True)
            if not isinstance(value, bool):
                self._validation_errors.append(f"{param} must be boolean, got: {value}")
                analysis_config[param] = True
        
        # Voltage parameter validation
        nominal_voltage = analysis_config.get("nominal_voltage", 120.0)
        if not isinstance(nominal_voltage, (int, float)) or not (50.0 <= nominal_voltage <= 500.0):
            self._validation_errors.append(f"nominal_voltage must be number between 50.0-500.0, got: {nominal_voltage}")
            analysis_config["nominal_voltage"] = 120.0
        
        sag_threshold = analysis_config.get("sag_threshold", 108.0)
        if not isinstance(sag_threshold, (int, float)) or not (10.0 <= sag_threshold <= 400.0):
            self._validation_errors.append(f"sag_threshold must be number between 10.0-400.0, got: {sag_threshold}")
            analysis_config["sag_threshold"] = nominal_voltage * 0.9
        
        swell_threshold = analysis_config.get("swell_threshold", 132.0)
        if not isinstance(swell_threshold, (int, float)) or not (50.0 <= swell_threshold <= 500.0):
            self._validation_errors.append(f"swell_threshold must be number between 50.0-500.0, got: {swell_threshold}")
            analysis_config["swell_threshold"] = nominal_voltage * 1.1
        
        # Validate threshold relationship
        if sag_threshold >= swell_threshold:
            self._validation_errors.append(f"sag_threshold ({sag_threshold}) must be less than swell_threshold ({swell_threshold})")
            analysis_config["sag_threshold"] = nominal_voltage * 0.9
            analysis_config["swell_threshold"] = nominal_voltage * 1.1
        
        # DC offset validation
        dc_offset = analysis_config.get("dc_offset", 1.65)
        if not isinstance(dc_offset, (int, float)) or not (0.0 <= dc_offset <= 5.0):
            self._validation_errors.append(f"dc_offset must be number between 0.0-5.0, got: {dc_offset}")
            analysis_config["dc_offset"] = 1.65
        
        # RMS window size validation
        rms_window_size = analysis_config.get("rms_window_size", 100)
        if not isinstance(rms_window_size, int) or not (10 <= rms_window_size <= 1000):
            self._validation_errors.append(f"rms_window_size must be integer between 10-1000, got: {rms_window_size}")
            analysis_config["rms_window_size"] = 100
        
        # Event minimum duration validation
        event_min_duration_ms = analysis_config.get("event_min_duration_ms", 50)
        if not isinstance(event_min_duration_ms, int) or not (1 <= event_min_duration_ms <= 10000):
            self._validation_errors.append(f"event_min_duration_ms must be integer between 1-10000, got: {event_min_duration_ms}")
            analysis_config["event_min_duration_ms"] = 50
    
    def _validate_display_section(self, display_config: Dict[str, Any]) -> None:
        """Validate display configuration section."""
        # Rotation validation
        rotation = display_config.get("rotation", 270)
        if rotation not in [0, 90, 180, 270]:
            self._validation_errors.append(f"rotation must be 0, 90, 180, or 270, got: {rotation}")
            display_config["rotation"] = 270
        
        # Refresh rate validation
        refresh_rate = display_config.get("refresh_rate", 30)
        if not isinstance(refresh_rate, int) or not (1 <= refresh_rate <= 60):
            self._validation_errors.append(f"refresh_rate must be integer between 1-60, got: {refresh_rate}")
            display_config["refresh_rate"] = 30
        
        # QR size validation
        qr_size = display_config.get("qr_size", 60)
        if not isinstance(qr_size, int) or not (20 <= qr_size <= 200):
            self._validation_errors.append(f"qr_size must be integer between 20-200, got: {qr_size}")
            display_config["qr_size"] = 60
    
    def _validate_multiprocessing_section(self, mp_config: Dict[str, Any]) -> None:
        """Validate multiprocessing configuration section."""
        # Heartbeat interval validation
        heartbeat_interval = mp_config.get("heartbeat_interval", 5.0)
        if not isinstance(heartbeat_interval, (int, float)) or not (1.0 <= heartbeat_interval <= 60.0):
            self._validation_errors.append(f"heartbeat_interval must be number between 1.0-60.0, got: {heartbeat_interval}")
            mp_config["heartbeat_interval"] = 5.0
        
        # Restart delay validation
        restart_delay = mp_config.get("restart_delay", 2.0)
        if not isinstance(restart_delay, (int, float)) or not (0.1 <= restart_delay <= 30.0):
            self._validation_errors.append(f"restart_delay must be number between 0.1-30.0, got: {restart_delay}")
            mp_config["restart_delay"] = 2.0
        
        # Max restarts validation
        max_restarts = mp_config.get("max_restarts", 5)
        if not isinstance(max_restarts, int) or not (0 <= max_restarts <= 20):
            self._validation_errors.append(f"max_restarts must be integer between 0-20, got: {max_restarts}")
            mp_config["max_restarts"] = 5
        
        # Shutdown timeout validation
        shutdown_timeout = mp_config.get("shutdown_timeout", 30.0)
        if not isinstance(shutdown_timeout, (int, float)) or not (5.0 <= shutdown_timeout <= 300.0):
            self._validation_errors.append(f"shutdown_timeout must be number between 5.0-300.0, got: {shutdown_timeout}")
            mp_config["shutdown_timeout"] = 30.0
    
    def get_process_config(self, process_name: str) -> Dict[str, Any]:
        """
        Get configuration specific to a process.
        
        Args:
            process_name: Name of the process ('datalogger', 'event_logger', 'fastapi')
            
        Returns:
            Dictionary containing process-specific configuration
        """
        if not self.config:
            raise ConfigurationError("Configuration not loaded")
        
        base_config = {
            'sample_hz': self.config["pika"]["sample_hz"],
            'data_dir': self.config["pika"]["data_dir"],
            'display_fps': self.config["pika"]["display_fps"]
        }
        
        if process_name == 'datalogger':
            return {
                'data_dir': base_config['data_dir'],
                'batch_size': self.config["datalogger"]["batch_size"],
                'batch_interval_ms': self.config["datalogger"]["batch_interval_ms"],
                'retention_days': self.config["datalogger"]["retention_days"],
                'filename_prefix': self.config["datalogger"]["filename_prefix"],
                'adc_config': {
                    'address': self.config["pins"]["adc_address"],
                    'channel': self.config["pins"]["adc_channel"]
                },
                'display_config': {
                    'enabled': True,
                    'auto_ip': self.config["pika"]["display_auto_ip"],
                    'port': self.config["pika"]["port"],
                    'lcd_config': self.config["pins"]
                }
            }
        
        elif process_name == 'event_logger':
            return {
                **base_config,
                'analysis_config': self.config["analysis"]
            }
        
        elif process_name == 'fastapi':
            return {
                **base_config,
                'port': self.config["pika"]["port"],
                'display_auto_ip': self.config["pika"]["display_auto_ip"]
            }
        
        else:
            return base_config
    
    def get_shared_config_data(self) -> Dict[str, Any]:
        """
        Get configuration data for SharedConfigBuffer initialization.
        
        Returns:
            Dictionary containing configuration for shared memory
        """
        if not self.config:
            raise ConfigurationError("Configuration not loaded")
        
        return {
            'sample_hz': self.config["pika"]["sample_hz"],
            'batch_size': self.config["datalogger"]["batch_size"],
            'batch_interval_ms': self.config["datalogger"]["batch_interval_ms"],
            'analysis_config': self.config["analysis"],
            'display_fps': self.config["pika"]["display_fps"]
        }
    
    def get_validation_errors(self) -> List[str]:
        """Get list of validation errors from last validation."""
        return self._validation_errors.copy()
    
    def save_configuration(self, output_path: Optional[str] = None) -> None:
        """
        Save current configuration to TOML file.
        
        Args:
            output_path: Path to save configuration (uses original path if None)
        """
        if not self.config:
            raise ConfigurationError("No configuration to save")
        
        output_path = output_path or self.config_path
        
        try:
            import tomli_w  # For writing TOML files
            
            with open(output_path, "wb") as f:
                tomli_w.dump(self.config, f)
            
            logger.info(f"Configuration saved to {output_path}")
            
        except ImportError:
            logger.error("tomli_w not available for saving TOML files")
            raise ConfigurationError("Cannot save TOML files without tomli_w package")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise ConfigurationError(f"Configuration save failed: {e}")


def load_and_validate_config(config_path: str = "config.toml") -> Dict[str, Any]:
    """
    Convenience function to load and validate configuration.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Validated configuration dictionary
        
    Raises:
        ConfigurationError: If configuration loading or validation fails
    """
    manager = ConfigurationManager(config_path)
    return manager.load_configuration()


def get_default_config() -> Dict[str, Any]:
    """
    Get default configuration without loading from file.
    
    Returns:
        Default configuration dictionary
    """
    manager = ConfigurationManager()
    return manager._get_default_configuration()