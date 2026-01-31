"""ADS1115 ADC adapter implementation using existing datalogger ADC code."""

import logging
from typing import Dict
from .adc_adapter import ADCAdapter

logger = logging.getLogger(__name__)


class ADS1115Adapter(ADCAdapter):
    """ADS1115 ADC adapter implementation.
    
    This adapter wraps the existing ADS1115 hardware interface from the datalogger
    to provide a consistent interface for the multiprocessing architecture.
    """
    
    def __init__(self):
        self._ads = None
        self._chan = None
        self._initialized = False
        self._current_rate = None
    
    def initialize(self, config: Dict) -> bool:
        """Initialize the ADS1115 ADC hardware.
        
        Args:
            config: Configuration dictionary with keys:
                - address: I2C address (default: 0x48)
                - channel: ADC channel (default: 0)
                - sample_rate: Target sample rate in Hz (default: 100)
                
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Import hardware libraries
            import board
            import busio
            import adafruit_ads1x15.ads1115 as ADS
            from adafruit_ads1x15.analog_in import AnalogIn
            from adafruit_ads1x15 import ads1x15
            
            # Extract configuration parameters
            address = config.get('address', 0x48)
            channel = config.get('channel', 0)
            sample_rate = config.get('sample_rate', 100)
            
            logger.info(f"Initializing ADS1115 ADC at address 0x{address:02X}, channel {channel}, target rate: {sample_rate}Hz")
            
            # Initialize I2C and ADS1115
            i2c = busio.I2C(board.SCL, board.SDA)
            self._ads = ADS.ADS1115(i2c, address=address)
            
            # Set initial sample rate
            if not self.set_sample_rate(sample_rate):
                logger.warning("Failed to set initial sample rate, using default")
            
            # Initialize analog input channel
            self._chan = AnalogIn(self._ads, getattr(ads1x15.Pin, f"A{channel}"))
            
            self._initialized = True
            logger.info("ADS1115 ADC initialized successfully")
            return True
            
        except ImportError as e:
            logger.error(f"ADS1115 hardware libraries not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize ADS1115 ADC: {e}")
            return False
    
    def read_sample(self) -> float:
        """Read a single voltage sample from the ADS1115.
        
        Returns:
            Voltage reading as float, or NaN if read fails
        """
        if not self._initialized or not self._chan:
            logger.warning("ADS1115 not initialized, returning NaN")
            return float('nan')
        
        try:
            return self._chan.voltage
        except Exception as e:
            logger.debug(f"ADS1115 read failed: {e}")
            return float('nan')
    
    def set_sample_rate(self, rate_hz: int) -> bool:
        """Configure the ADS1115 sample rate.
        
        The ADS1115 supports specific data rates. This method selects the smallest
        valid rate that is >= the target rate.
        
        Args:
            rate_hz: Target sample rate in Hz
            
        Returns:
            True if rate was set successfully, False otherwise
        """
        if not self._initialized or not self._ads:
            logger.warning("ADS1115 not initialized, cannot set sample rate")
            return False
        
        try:
            # ADS1115 supported data rates
            supported_rates = [8, 16, 32, 64, 128, 250, 475, 860]
            
            # Find the smallest rate >= target rate
            selected_rate = 860  # Default to maximum
            for rate in supported_rates:
                if rate >= rate_hz:
                    selected_rate = rate
                    break
            
            self._ads.data_rate = selected_rate
            self._current_rate = selected_rate
            
            logger.info(f"ADS1115 data rate configured to {selected_rate} SPS (requested: {rate_hz})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set ADS1115 sample rate: {e}")
            return False
    
    def cleanup(self) -> None:
        """Clean up ADS1115 resources."""
        if self._initialized:
            try:
                # The Adafruit library doesn't require explicit cleanup,
                # but we can reset our state
                self._ads = None
                self._chan = None
                self._initialized = False
                logger.info("ADS1115 adapter cleaned up")
            except Exception as e:
                logger.error(f"Error during ADS1115 cleanup: {e}")
    
    @property
    def is_hardware(self) -> bool:
        """Return True since this is a hardware ADC."""
        return True
    
    @property
    def current_rate(self) -> int:
        """Get the currently configured sample rate."""
        return self._current_rate