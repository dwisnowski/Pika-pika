"""Configuration constants for display manager.

This module contains all configuration values including colors, layout parameters,
and font settings used throughout the display system.
"""

# Color constants
class Colors:
    """RGB color values used in the display."""
    BLACK = (0, 0, 0)
    GREEN = (0, 255, 0)
    RED = (255, 107, 107)
    WHITE = (255, 255, 255)


class Layout:
    """Layout and positioning constants for display elements."""
    MARGIN = 8
    QR_SIZE = 60
    TITLE_Y = 8
    VOLTAGE_Y_OFFSET = -20
    ANOMALY_Y_OFFSET = 24
    TIME_Y_OFFSET = 24
    MASCOT_Y_OFFSET = 12
    SMALL_FONT_SIZE = 10
    LARGE_FONT_SIZE = 14


class Fonts:
    """Font configuration and fallback preferences."""
    PREFERRED_MONO = "DejaVuSansMono-Bold.ttf"
    FALLBACK_MONO = "Courier New"
    PREFERRED_BOLD = "DejaVuSans-Bold.ttf"


class DisplaySettings:
    """Default settings for display manager."""
    DEFAULT_FPS = 5.0
    DEFAULT_PORT = 8000
    DEFAULT_DATA_DIR = "data"
    THREAD_JOIN_TIMEOUT = 1.0
    VOLTAGE_QUERY_SECONDS = 2.0
    FALLBACK_IMAGE_NAME = "lcd_latest.png"
