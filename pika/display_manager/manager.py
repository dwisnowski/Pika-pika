"""Main display manager class.

This module contains the core DisplayManager class that orchestrates
display rendering, data retrieval, and display lifecycle management.
"""

import logging
import threading
import time
from typing import Optional

from ..display_qr import show_on_waveshare
from .config import DisplaySettings
from .data_source import AnomalyDataSource, NetworkDataSource, VoltageDataSource
from .renderer import DisplayRenderer
from .utils import is_raspberry_pi

logger = logging.getLogger(__name__)


class DisplayManager:
    """Main display manager for SPI LCD displays.
    
    Manages the display lifecycle, rendering loop, and coordinates between
    data sources and the display renderer.
    """
    
    def __init__(
        self,
        logger_obj,
        url: Optional[str] = None,
        auto_ip: bool = True,
        port: int = DisplaySettings.DEFAULT_PORT,
        fps: float = DisplaySettings.DEFAULT_FPS,
        data_dir: str = DisplaySettings.DEFAULT_DATA_DIR
    ):
        """Initialize display manager.
        
        Args:
            logger_obj: Datalogger instance for voltage data
            url: URL to display in QR code
            auto_ip: Whether to auto-detect local IP for URL
            port: Port for auto-generated URL
            fps: Display refresh rate
            data_dir: Directory for data files
        """
        self.logger = logger_obj
        self.auto_ip = auto_ip
        self.port = port
        self.data_dir = data_dir
        self.url = url
        self.fps = fps
        self.interval = 1.0 / float(self.fps)
        self.frame_idx = 0
        
        # Threading control
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        
        # Font cache for performance
        self._font_cache = {}
        
        # Initialize components
        self._renderer = DisplayRenderer(self._font_cache)
        self._voltage_source = VoltageDataSource(logger_obj)
        self._anomaly_source = AnomalyDataSource(data_dir)
        self._network_source = NetworkDataSource()
    
    def start(self) -> None:
        """Start the display manager and rendering thread."""
        if self._thread and self._thread.is_alive():
            logger.debug("DisplayManager already running")
            return
        
        # Auto-detect URL if needed
        if not self.url and self.auto_ip:
            ip = self._network_source.get_local_ip()
            if ip:
                self.url = f"http://{ip}:{self.port}"
            else:
                logger.warning(
                    "DisplayManager: could not auto-detect local IP; "
                    "QR will not be rendered until URL provided"
                )
        
        # Start rendering thread
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("DisplayManager started (fps=%.1f). URL=%s", self.fps, self.url)
    
    def stop(self) -> None:
        """Stop the display manager and clean up resources."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=DisplaySettings.THREAD_JOIN_TIMEOUT)
        logger.info("DisplayManager stopped")
    
    def _render_frame(self) -> None:
        """Render and display a single frame."""
        try:
            # Get current data
            voltage = self._voltage_source.get_current_voltage()
            anomaly_count = self._anomaly_source.get_recent_anomaly_count(hours=1)
            
            # Render frame
            frame = self._renderer.render_complete_frame(
                url=self.url,
                voltage=voltage,
                anomaly_count=anomaly_count
            )
            
            # Display frame
            if not show_on_waveshare(frame):
                frame.save(DisplaySettings.FALLBACK_IMAGE_NAME)
                
        except Exception as e:
            logger.error("Failed to render display frame: %s", e)
    
    def _run(self) -> None:
        """Main display loop running in separate thread."""
        if not is_raspberry_pi():
            logger.info("DisplayManager: skipping LCD operations (not on Linux/Raspberry Pi)")
            return
        
        # Render initial frame immediately
        self._render_frame()
        
        # Main display loop
        while not self._stop.is_set():
            start_time = time.time()
            
            self.frame_idx += 1
            self._render_frame()
            
            elapsed = time.time() - start_time
            sleep_duration = max(0, self.interval - elapsed)
            if sleep_duration > 0:
                time.sleep(sleep_duration)
