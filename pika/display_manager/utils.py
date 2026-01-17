"""Utility functions and helpers for display management.

This module provides common utility functions used across the display package,
including font management, text positioning, and platform detection.
"""

import platform
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from .config import Fonts


def get_font_with_cache(font_cache: dict, font_name: str, size: int) -> ImageFont.ImageFont:
    """Get font with caching and fallback logic.
    
    Args:
        font_cache: Dictionary to cache loaded fonts
        font_name: Name of the font file to load
        size: Font size in points
        
    Returns:
        ImageFont instance (cached or newly loaded)
    """
    cache_key = f"{font_name}_{size}"
    if cache_key not in font_cache:
        try:
            font_cache[cache_key] = ImageFont.truetype(font_name, size)
        except (OSError, IOError):
            try:
                font_cache[cache_key] = ImageFont.truetype(Fonts.FALLBACK_MONO, size)
            except (OSError, IOError):
                font_cache[cache_key] = ImageFont.load_default()
    return font_cache[cache_key]


def center_text_x(text: str, font: ImageFont.ImageFont, display_width: int) -> int:
    """Calculate centered x position for text.
    
    Args:
        text: Text to center
        font: Font to use for text measurement
        display_width: Width of the display area
        
    Returns:
        X coordinate for centered text
    """
    bbox = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    return (display_width - text_width) // 2


def is_raspberry_pi() -> bool:
    """Check if running on Raspberry Pi (Linux).
    
    Returns:
        True if running on Linux (assumed Raspberry Pi), False otherwise
    """
    return platform.system() == "Linux"


def format_voltage(voltage: Optional[float]) -> str:
    """Format voltage value for display.
    
    Args:
        voltage: Voltage value in volts, or None if unavailable
        
    Returns:
        Formatted voltage string
    """
    if voltage is None or (isinstance(voltage, float) and (voltage != voltage)):
        return "--.- V"
    return f"{voltage:.1f} V"


def format_anomaly_status(count: int) -> tuple[str, tuple]:
    """Format anomaly status text and color.
    
    Args:
        count: Number of anomalies detected
        
    Returns:
        Tuple of (status_text, color_tuple)
    """
    if count > 0:
        return f"{count} anomalies", (255, 107, 107)  # Red
    return "No anomalies", (0, 255, 0)  # Green
