"""Mock ADC adapter implementation for simulation and testing."""

import logging
import math
import random
import time
from typing import Dict
from .adc_adapter import ADCAdapter

logger = logging.getLogger(__name__)


class MockADCAdapter(ADCAdapter):
    """Mock ADC adapter for simulation mode.
    
    This adapter generates simulated voltage readings for testing and development
    when hardware is not available. It can simulate various signal patterns
    including AC waveforms, noise, and anomalies.
    """
    
    def __init__(self):
        self._initialized = False
        self._sample_rate = 100
        self._start_time = None
        self._signal_type = 'ac'  # 'ac', 'dc', 'noise', 'sine'
        self._amplitude = 1.0
        self._frequency = 60.0  # Hz for AC simulation
        self._dc_offset = 1.5
        self._noise_level = 0.02
    
    def initialize(self, config: Dict) -> bool:
        """Initialize the mock ADC with simulation parameters.
        
        Args:
            config: Configuration dictionary with optional keys:
                - sample_rate: Simulated sample rate (default: 100)
                - signal_type: Type of signal ('ac', 'dc', 'noise', 'sine')
                - amplitude: Signal amplitude (default: 1.0)
                - frequency: AC frequency in Hz (default: 60.0)
                - dc_offset: DC offset for signals (default: 1.5)
                - noise_level: Noise amplitude (default: 0.02)
                
        Returns:
            Always True for mock adapter
        """
        try:
            self._sample_rate = config.get('sample_rate', 100)
            self._signal_type = config.get('signal_type', 'ac')
            self._amplitude = config.get('amplitude', 1.0)
            self._frequency = config.get('frequency', 60.0)
            self._dc_offset = config.get('dc_offset', 1.5)
            self._noise_level = config.get('noise_level', 0.02)
            
            self._start_time = time.time()
            self._initialized = True
            
            logger.info(f"MockADC initialized - signal: {self._signal_type}, "
                       f"rate: {self._sample_rate}Hz, freq: {self._frequency}Hz")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize MockADC: {e}")
            return False
    
    def read_sample(self) -> float:
        """Generate a simulated voltage sample.
        
        Returns:
            Simulated voltage reading based on configured signal type
        """
        if not self._initialized:
            logger.warning("MockADC not initialized, returning 0.0")
            return 0.0
        
        try:
            current_time = time.time() - self._start_time
            
            if self._signal_type == 'dc':
                # Simple DC signal with noise
                value = self._dc_offset + random.uniform(-self._noise_level, self._noise_level)
                
            elif self._signal_type == 'sine':
                # Pure sine wave with noise
                value = (self._dc_offset + 
                        self._amplitude * math.sin(2.0 * math.pi * self._frequency * current_time) +
                        random.uniform(-self._noise_level, self._noise_level))
                
            elif self._signal_type == 'noise':
                # Random noise around DC offset
                value = self._dc_offset + random.uniform(-self._amplitude, self._amplitude)
                
            else:  # 'ac' or default
                # Simulated AC power signal with harmonics and noise
                fundamental = self._amplitude * math.sin(2.0 * math.pi * self._frequency * current_time)
                # Add some 3rd harmonic for realism
                harmonic = 0.1 * self._amplitude * math.sin(2.0 * math.pi * 3 * self._frequency * current_time)
                noise = random.uniform(-self._noise_level, self._noise_level)
                value = self._dc_offset + fundamental + harmonic + noise
            
            return float(value)
            
        except Exception as e:
            logger.debug(f"MockADC read error: {e}")
            return float('nan')
    
    def set_sample_rate(self, rate_hz: int) -> bool:
        """Set the simulated sample rate.
        
        Args:
            rate_hz: Target sample rate in Hz
            
        Returns:
            Always True for mock adapter
        """
        try:
            old_rate = self._sample_rate
            self._sample_rate = max(1, min(10000, int(rate_hz)))  # Clamp to reasonable range
            
            logger.info(f"MockADC sample rate changed from {old_rate}Hz to {self._sample_rate}Hz")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set MockADC sample rate: {e}")
            return False
    
    def cleanup(self) -> None:
        """Clean up mock ADC resources."""
        if self._initialized:
            self._initialized = False
            self._start_time = None
            logger.info("MockADC adapter cleaned up")
    
    @property
    def is_hardware(self) -> bool:
        """Return False since this is a simulation."""
        return False
    
    def set_signal_type(self, signal_type: str) -> bool:
        """Change the signal type during runtime.
        
        Args:
            signal_type: New signal type ('ac', 'dc', 'noise', 'sine')
            
        Returns:
            True if signal type was valid and set
        """
        valid_types = ['ac', 'dc', 'noise', 'sine']
        if signal_type in valid_types:
            self._signal_type = signal_type
            logger.info(f"MockADC signal type changed to: {signal_type}")
            return True
        else:
            logger.warning(f"Invalid signal type: {signal_type}. Valid types: {valid_types}")
            return False
    
    def inject_anomaly(self, anomaly_type: str, duration: float = 1.0) -> None:
        """Inject a simulated anomaly for testing event detection.
        
        Args:
            anomaly_type: Type of anomaly ('sag', 'swell', 'outage')
            duration: Duration of anomaly in seconds
        """
        # This could be implemented to temporarily modify the signal
        # for testing anomaly detection algorithms
        logger.info(f"MockADC anomaly injection: {anomaly_type} for {duration}s (not implemented)")
        pass