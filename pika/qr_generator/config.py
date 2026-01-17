"""Configuration constants for QR code generation."""

from typing import Tuple

# Default QR code settings
class QRDefaults:
    """Default values for QR code generation."""
    BORDER = 2
    BOX_SIZE = 8
    MARGIN = 24
    TEXT_OFFSET_Y = -12

# Color constants
class QRColors:
    """Standard color definitions for QR codes."""
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)

# Common display sizes
class DisplaySizes:
    """Standard display dimensions."""
    WIDESCREEN = (240, 320)  # Common LCD displays
    SQUARE = (240, 240)      # Square displays
    LARGE = (320, 240)       # Larger displays
