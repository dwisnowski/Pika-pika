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
                    'min_duration_ms': 9
                },
                'swell': {
                    'threshold_pct': 10,
                    'min_duration_ms': 9
                },
                'spike': {
                    'threshold_pct': 20,
                    'max_duration_ms': 100
                }
            },
            'review': {
                'interruption_pct': 10,
                'deep_sag_pct': 70,
                'damaging_swell_pct': 120,
                'sustained_duration_ms': 60000,
                'range_b_low_pct': -13.3,
                'range_b_high_pct': 5.8,
            },
            'debounce': {
                'sag_cooldown_ms': 1000,
                'swell_cooldown_ms': 1000,
                'spike_cooldown_ms': 1000,
            },
            'logging': {
                'level': 'info'
            },
            'webapp': {
                'history_window_minutes': 60,
                'history_display_points': 800,
                'history_max_points': 20000,
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

    def get_sag_min_duration_ms(self) -> int:
        return int(self.config.get('anomalies', {}).get('sag', {}).get('min_duration_ms', 9))

    def get_swell_min_duration_ms(self) -> int:
        return int(self.config.get('anomalies', {}).get('swell', {}).get('min_duration_ms', 9))

    def get_sag_cooldown_ms(self) -> int:
        return int(self.config.get('debounce', {}).get('sag_cooldown_ms', 1000))

    def get_swell_cooldown_ms(self) -> int:
        return int(self.config.get('debounce', {}).get('swell_cooldown_ms', 1000))

    def get_anomalies_config(self) -> dict:
        """User-editable log thresholds (not professional-review policy)."""
        return {
            "sag_threshold_pct": self.get_sag_threshold_pct(),
            "swell_threshold_pct": self.get_swell_threshold_pct(),
            "sag_min_duration_ms": self.get_sag_min_duration_ms(),
            "swell_min_duration_ms": self.get_swell_min_duration_ms(),
            "target_mains_vrms": self.get_target_mains_vrms(),
            "sag_cooldown_ms": self.get_sag_cooldown_ms(),
            "swell_cooldown_ms": self.get_swell_cooldown_ms(),
        }

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
        """Fallback source-interval cap if history_window_minutes is unset."""
        return int(self.config.get('webapp', {}).get('history_max_points', 20000))

    def get_history_window_minutes(self) -> int:
        """Lookback window shown on the trend pane (1–720)."""
        web = self.config.get('webapp', {}) or {}
        if web.get('history_window_minutes') is not None:
            return max(1, min(720, int(web['history_window_minutes'])))
        # Derive from the older point cap at the nominal 5 Hz IEC rate.
        return max(1, min(720, round(self.get_history_max_points() / 5.0 / 60.0)))

    def get_history_display_points(self) -> int:
        """Max points sent to the trend chart (100–2000)."""
        return max(100, min(2000, int(
            (self.config.get('webapp', {}) or {}).get('history_display_points', 800)
        )))

    def get_nominal_rate_hz(self) -> int:
        """Get ADC nominal sample rate from shared config."""
        return int(self.config.get('sampling', {}).get('nominal_rate_hz', 10000))

# Global instance
config_service = ConfigService()
