"""Display manager package for Waveshare/ST7789 240x320 SPI displays.

This package provides a clean, modular display management system with the following components:
- DisplayManager: Main class for managing display lifecycle
- DisplayRenderer: Handles all drawing and rendering operations
- DisplayConfig: Configuration constants and settings
- DisplaySingleton: Global instance management
- DisplayUtils: Utility functions and helpers

The display renders QR codes, voltage readings, anomaly status, and time information
in a clean, organized interface suitable for Raspberry Pi LCD displays.
"""

from .manager import DisplayManager
from .singleton import start_display, stop_display
from .config import Colors, Layout, Fonts

__all__ = [
    'DisplayManager',
    'start_display', 
    'stop_display',
    'Colors',
    'Layout', 
    'Fonts'
]
