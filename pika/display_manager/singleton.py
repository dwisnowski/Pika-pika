"""Singleton pattern implementation for display manager.

This module provides a singleton pattern for managing the global display
manager instance, ensuring only one display manager runs at a time.
"""

from typing import Optional

from .config import DisplaySettings
from .manager import DisplayManager


class DisplayManagerSingleton:
    """Singleton pattern for managing the global display manager instance."""
    
    def __init__(self):
        """Initialize the singleton."""
        self._instance: Optional[DisplayManager] = None
    
    def start_display(
        self,
        logger_obj,
        url: Optional[str] = None,
        auto_ip: bool = True,
        port: int = DisplaySettings.DEFAULT_PORT,
        fps: float = DisplaySettings.DEFAULT_FPS,
        data_dir: str = DisplaySettings.DEFAULT_DATA_DIR,
        lcd_config: Optional[dict] = None
    ) -> DisplayManager:
        """Start the display manager if not already running.
        
        Args:
            logger_obj: Datalogger instance for voltage data
            url: URL to display in QR code
            auto_ip: Whether to auto-detect local IP for URL
            port: Port for auto-generated URL
            fps: Display refresh rate
            data_dir: Directory for data files
            lcd_config: Dictionary of LCD pin settings
            
        Returns:
            DisplayManager instance
        """
        if self._instance is None:
            self._instance = DisplayManager(
                logger_obj, url=url, auto_ip=auto_ip,
                port=port, fps=fps, data_dir=data_dir,
                lcd_config=lcd_config
            )
            self._instance.start()
        return self._instance
    
    def stop_display(self) -> None:
        """Stop the display manager and clean up."""
        if self._instance:
            self._instance.stop()
            self._instance = None
    
    @property
    def instance(self) -> Optional[DisplayManager]:
        """Get the current display manager instance.
        
        Returns:
            Current DisplayManager instance, or None if not running
        """
        return self._instance


# Global singleton instance
_display_singleton = DisplayManagerSingleton()


# Public API functions for backward compatibility
def start_display(
    logger_obj,
    url: Optional[str] = None,
    auto_ip: bool = True,
    port: int = DisplaySettings.DEFAULT_PORT,
    fps: float = DisplaySettings.DEFAULT_FPS,
    data_dir: str = DisplaySettings.DEFAULT_DATA_DIR,
    lcd_config: Optional[dict] = None
) -> DisplayManager:
    """Start the display manager singleton.
    
    Args:
        logger_obj: Datalogger instance for voltage data
        url: URL to display in QR code
        auto_ip: Whether to auto-detect local IP for URL
        port: Port for auto-generated URL
        fps: Display refresh rate
        data_dir: Directory for data files
        lcd_config: Dictionary of LCD pin settings
        
    Returns:
        DisplayManager instance
    """
    return _display_singleton.start_display(
        logger_obj, url=url, auto_ip=auto_ip,
        port=port, fps=fps, data_dir=data_dir,
        lcd_config=lcd_config
    )


def stop_display() -> None:
    """Stop the display manager singleton."""
    _display_singleton.stop_display()
