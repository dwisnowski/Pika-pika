"""Hardware adapter interfaces for the datalogger multiprocessing architecture."""

from .adc_adapter import ADCAdapter, create_adc_adapter
from .ads1115_adapter import ADS1115Adapter
from .mock_adc_adapter import MockADCAdapter

__all__ = [
    'ADCAdapter',
    'ADS1115Adapter', 
    'MockADCAdapter',
    'create_adc_adapter'
]