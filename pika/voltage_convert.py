"""Voltage conversion utilities for ZMPT101B sensor.

Converts ADC readings to AC line voltage based on calibration constants.
"""

from typing import Optional
import math


class VoltageConverter:
    """Convert ADC voltage readings to AC line voltage."""
    
    # Default calibration constants
    DEFAULT_ADC_OFFSET = 1.65  # DC offset (half of 3.3V)
    DEFAULT_ADC_VPP_TO_AC_RMS = 85.0  # Conversion factor: 1V ADC Vpp ≈ 85V AC RMS
    
    # Brownout thresholds (ANSI C84.1 for 120V nominal)
    THRESHOLDS = {
        'dropout': 80,
        'severe_brownout': 95,
        'brownout': 108,
        'undervoltage_warning': 114,
        'normal_min': 114,
        'normal_max': 126,
        'overvoltage_warning': 126,
        'severe_overvoltage': 132
    }
    
    def __init__(self, config: Optional[dict] = None):
        """Initialize with optional config.
        
        Args:
            config: Dictionary with voltage calibration settings
        """
        self.config = config or {}
        self.adc_offset = self.config.get('adc_offset', self.DEFAULT_ADC_OFFSET)
        self.adc_vpp_to_ac_rms = self.config.get('adc_vpp_to_ac_rms', self.DEFAULT_ADC_VPP_TO_AC_RMS)
        
        # Load thresholds from config or use defaults
        self.thresholds = dict(self.THRESHOLDS)
        for key in self.THRESHOLDS:
            if key in self.config:
                self.thresholds[key] = self.config[key]
    
    def adc_to_ac_instantaneous(self, adc_voltage: float) -> float:
        """Convert instantaneous ADC voltage to AC voltage.
        
        The ADC reads the ZMPT101B output centered around adc_offset.
        This returns the instantaneous AC voltage (can be negative).
        
        Args:
            adc_voltage: Raw ADC voltage reading
            
        Returns:
            Instantaneous AC voltage
        """
        # Remove DC offset to get AC component
        ac_component = adc_voltage - self.adc_offset
        
        # Scale by calibration factor
        # If 1V peak ADC = 170V peak AC (120V RMS), then factor = 170
        ac_peak_factor = self.adc_vpp_to_ac_rms * math.sqrt(2)
        
        return ac_component * ac_peak_factor
    
    def adc_vpp_to_ac_rms(self, adc_vpp: float) -> float:
        """Convert ADC peak-to-peak voltage to AC RMS voltage.
        
        Args:
            adc_vpp: Peak-to-peak voltage measured on ADC
            
        Returns:
            AC RMS voltage
        """
        return adc_vpp * self.adc_vpp_to_ac_rms
    
    def adc_rms_to_ac_rms(self, adc_rms: float) -> float:
        """Convert ADC RMS voltage (around offset) to AC RMS voltage.
        
        For a sine wave centered on DC offset, the ADC RMS of the AC component
        equals the peak / sqrt(2).
        
        Args:
            adc_rms: RMS of ADC voltage readings
            
        Returns:
            AC RMS voltage
        """
        # The adc_rms is the RMS of the full signal including DC offset
        # For pure AC: Vrms_ac = Vpeak / sqrt(2) = Vpp / (2 * sqrt(2))
        # Since we're given ADC RMS (which for AC around offset ≈ Vpp/2/sqrt(2))
        # We multiply by the scaling factor
        
        # More simply: if sensor output is linear,
        # AC_RMS = ADC_ac_rms * scale_factor
        # where ADC_ac_rms ≈ (adc_rms - offset²)^0.5 for mixed signal
        # but if we measure RMS after removing DC offset, it's direct
        
        return adc_rms * self.adc_vpp_to_ac_rms * math.sqrt(2)
    
    def classify_voltage(self, ac_rms: float) -> str:
        """Classify AC voltage status based on thresholds.
        
        Args:
            ac_rms: AC RMS voltage
            
        Returns:
            Status string: 'dropout', 'severe_brownout', 'brownout', 
                          'undervoltage', 'normal', 'overvoltage', 'severe_overvoltage'
        """
        if ac_rms < self.thresholds['dropout']:
            return 'dropout'
        elif ac_rms < self.thresholds['severe_brownout']:
            return 'severe_brownout'
        elif ac_rms < self.thresholds['brownout']:
            return 'brownout'
        elif ac_rms < self.thresholds['undervoltage_warning']:
            return 'undervoltage'
        elif ac_rms > self.thresholds['severe_overvoltage']:
            return 'severe_overvoltage'
        elif ac_rms > self.thresholds['overvoltage_warning']:
            return 'overvoltage'
        else:
            return 'normal'
    
    def get_severity_level(self, status: str) -> int:
        """Get numeric severity level for a status.
        
        Args:
            status: Voltage status string
            
        Returns:
            Severity level (0=normal, 1=warning, 2=moderate, 3=severe, 4=critical)
        """
        severity_map = {
            'normal': 0,
            'undervoltage': 1,
            'overvoltage': 1,
            'brownout': 2,
            'severe_brownout': 3,
            'severe_overvoltage': 3,
            'dropout': 4
        }
        return severity_map.get(status, 0)


# Singleton instance with default config
_converter: Optional[VoltageConverter] = None


def get_converter(config: Optional[dict] = None) -> VoltageConverter:
    """Get or create the voltage converter singleton.
    
    Args:
        config: Optional config dict to update settings
        
    Returns:
        VoltageConverter instance
    """
    global _converter
    if _converter is None or config is not None:
        _converter = VoltageConverter(config)
    return _converter


def adc_to_ac_rms(adc_vpp: float, config: Optional[dict] = None) -> float:
    """Helper function to convert ADC Vpp to AC RMS.
    
    Args:
        adc_vpp: Peak-to-peak ADC voltage
        config: Optional calibration config
        
    Returns:
        AC RMS voltage
    """
    return get_converter(config).adc_vpp_to_ac_rms(adc_vpp)


def classify_voltage(ac_rms: float, config: Optional[dict] = None) -> str:
    """Helper function to classify voltage status.
    
    Args:
        ac_rms: AC RMS voltage
        config: Optional threshold config
        
    Returns:
        Status string
    """
    return get_converter(config).classify_voltage(ac_rms)
