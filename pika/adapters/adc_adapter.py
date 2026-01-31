"""Abstract ADC adapter base class and factory function for hardware abstraction."""

from abc import ABC, abstractmethod
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ADCAdapter(ABC):
    """Abstract base class for ADC hardware adapters.
    
    This interface enables hardware abstraction for different ADC implementations,
    supporting future migration from ADS1115 to AD7606 or other ADC hardware.
    """
    
    @abstractmethod
    def initialize(self, config: Dict) -> bool:
        """Initialize the ADC hardware with given configuration.
        
        Args:
            config: Dictionary containing ADC configuration parameters
            
        Returns:
            True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    def read_sample(self) -> float:
        """Read a single voltage sample from the ADC.
        
        Returns:
            Voltage reading as float, or NaN if read fails
        """
        pass
    
    @abstractmethod
    def set_sample_rate(self, rate_hz: int) -> bool:
        """Configure the ADC sample rate.
        
        Args:
            rate_hz: Target sample rate in Hz
            
        Returns:
            True if rate was set successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Clean up ADC resources and close connections."""
        pass
    
    @property
    @abstractmethod
    def is_hardware(self) -> bool:
        """Return True if this is a hardware ADC, False for simulation."""
        pass


def create_adc_adapter(adc_type: str, config: Dict) -> ADCAdapter:
    """Factory function to create appropriate ADC adapter based on configuration.
    
    Args:
        adc_type: Type of ADC adapter ('ads1115', 'ad7606', 'mock')
        config: Configuration dictionary for the adapter
        
    Returns:
        Initialized ADC adapter instance
        
    Raises:
        ValueError: If adc_type is not supported
        RuntimeError: If adapter initialization fails
    """
    from .ads1115_adapter import ADS1115Adapter
    from .mock_adc_adapter import MockADCAdapter
    
    adapters = {
        'ads1115': ADS1115Adapter,
        'mock': MockADCAdapter,
        # Future adapters can be added here
        # 'ad7606': AD7606Adapter,
    }
    
    if adc_type not in adapters:
        raise ValueError(f"Unsupported ADC type: {adc_type}. Supported types: {list(adapters.keys())}")
    
    adapter_class = adapters[adc_type]
    adapter = adapter_class()
    
    if not adapter.initialize(config):
        logger.error(f"Failed to initialize {adc_type} adapter")
        # Fall back to MockADC if hardware initialization fails
        if adc_type != 'mock':
            logger.warning("Falling back to MockADC due to hardware initialization failure")
            mock_adapter = MockADCAdapter()
            if mock_adapter.initialize(config):
                return mock_adapter
        raise RuntimeError(f"Failed to initialize {adc_type} adapter and fallback failed")
    
    logger.info(f"Successfully initialized {adc_type} adapter")
    return adapter