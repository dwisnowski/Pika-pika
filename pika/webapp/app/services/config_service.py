import yaml
import os
from pathlib import Path

class ConfigService:
    """
    Centralized configuration service for the webapp.
    Loads sensor configuration from the shared config file at pika/config/sensor.yaml
    """
    
    def __init__(self):
        self.config = None
        self.load_config()
    
    def load_config(self):
        """Load the centralized pika configuration"""
        # Find the config file relative to this service
        # Path: pika/webapp/app/services/config_service.py
        # Config: pika/pika.yaml
        service_dir = Path(__file__).parent
        webapp_dir = service_dir.parent.parent
        pika_dir = webapp_dir.parent
        config_path = pika_dir / "pika.yaml"
        
        try:
            if config_path.exists():
                with open(config_path, 'r') as f:
                    self.config = yaml.safe_load(f)
                print(f"[ConfigService] Loaded config from {config_path}")
            else:
                print(f"[ConfigService] Config file not found at {config_path}, using defaults")
                self.config = self._get_defaults()
        except Exception as e:
            print(f"[ConfigService] Error loading config: {e}, using defaults")
            self.config = self._get_defaults()
    
    def _get_defaults(self):
        """Return default configuration"""
        return {
            'sensor': {
                'adc_vref': 4.95,
                'adc_bits': 16,
                'transformer_ratio': 120.0,
                'target_mains_vrms': 120.0,
                'active_channels': 1
            },
            'detection': {
                'ac_freq_hz': 60,
                'rms_window_cycles': 30,
                'learn_cycles': 1000
            },
            'anomalies': {
                'sag': {
                    'threshold_pct': -10,
                    'min_duration_ms': 8
                },
                'swell': {
                    'threshold_pct': 10,
                    'min_duration_ms': 8
                },
                'spike': {
                    'threshold_pct': 20,
                    'max_duration_ms': 100
                }
            },
            'logging': {
                'level': 'info'
            }
        }
    
    def get_adc_vref(self) -> float:
        """Get ADC reference voltage"""
        return self.config.get('sensor', {}).get('adc_vref', 4.95)
    
    def get_adc_bits(self) -> int:
        """Get ADC bit depth"""
        return self.config.get('sensor', {}).get('adc_bits', 16)
    
    def get_transformer_ratio(self) -> float:
        """Get transformer ratio (fallback value)"""
        return self.config.get('sensor', {}).get('transformer_ratio', 120.0)
    
    def get_target_mains_vrms(self) -> float:
        """Get target mains voltage"""
        return self.config.get('sensor', {}).get('target_mains_vrms', 120.0)
    
    def get_ac_freq_hz(self) -> int:
        """Get AC frequency"""
        return self.config.get('detection', {}).get('ac_freq_hz', 60)
    
    def get_sag_threshold_pct(self) -> int:
        """Get SAG threshold percentage"""
        return self.config.get('anomalies', {}).get('sag', {}).get('threshold_pct', -10)
    
    def get_swell_threshold_pct(self) -> int:
        """Get SWELL threshold percentage"""
        return self.config.get('anomalies', {}).get('swell', {}).get('threshold_pct', 10)
    
    def get_calibration_scale(self) -> float:
        """Get the calibration scale factor for converting ADC to volts"""
        adc_vref = self.get_adc_vref()
        adc_bits = self.get_adc_bits()
        transformer_ratio = self.get_transformer_ratio()
        
        full_scale = float(1 << (adc_bits - 1))  # 2^(bits-1)
        return (adc_vref / full_scale) * transformer_ratio

    def get_log_level(self) -> str:
        """Get logging level from config"""
        return self.config.get('logging', {}).get('level', 'info')

    def get_history_max_points(self) -> int:
        """Get maximum number of decimated points to load for trend chart"""
        return self.config.get('webapp', {}).get('history_max_points', 6000)

    def get_nominal_rate_hz(self) -> int:
        """Get ADC nominal sample rate from shared config."""
        return int(self.config.get('sampling', {}).get('nominal_rate_hz', 10000))

# Global instance
config_service = ConfigService()
