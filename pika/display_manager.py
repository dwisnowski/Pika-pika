"""Display manager for Waveshare/ST7789 240x320 SPI displays.

- Renders the QR code (URL) when started.
- Runs a simple, original "electric mascot" animation (non-copyrighted) at a low framerate.
- Overlays the current voltage reading from the datalogger.

This module attempts to use the same display drivers as `pika/display_qr.py` and falls back to saving PNGs for testing.
"""
from __future__ import annotations

import json
import os
import platform
import threading
import time
import logging
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps
import qrcode

from .display_qr import make_qr_image, show_on_waveshare, get_local_ip, DISPLAY_W, DISPLAY_H

logger = logging.getLogger(__name__)

# Color constants
class Colors:
    BLACK = (0, 0, 0)
    GREEN = (0, 255, 0)
    RED = (255, 107, 107)
    WHITE = (255, 255, 255)

# Display layout constants
class Layout:
    MARGIN = 8
    QR_SIZE = 60
    TITLE_Y = 8
    VOLTAGE_Y_OFFSET = -20
    ANOMALY_Y_OFFSET = 24
    TIME_Y_OFFSET = 24
    MASCOT_Y_OFFSET = 12
    SMALL_FONT_SIZE = 10
    LARGE_FONT_SIZE = 14

# Font configuration
class Fonts:
    PREFERRED_MONO = "DejaVuSansMono-Bold.ttf"
    FALLBACK_MONO = "Courier New"
    PREFERRED_BOLD = "DejaVuSans-Bold.ttf"

class DisplayManager:
    def __init__(
        self,
        logger_obj,
        url: Optional[str] = None,
        auto_ip: bool = True,
        port: int = 8000,
        fps: float = 5.0,
        data_dir: str = "data"
    ):
        self.logger = logger_obj
        self.auto_ip = auto_ip
        self.port = port
        self.data_dir = data_dir
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.fps = fps
        self.interval = 1.0 / float(self.fps)
        self.url = url
        self.frame_idx = 0
        self._font_cache = {}

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        if not self.url and self.auto_ip:
            ip = get_local_ip()
            if ip:
                self.url = f"http://{ip}:{self.port}"
            else:
                logger.warning("DisplayManager: could not auto-detect local IP; QR will not be rendered until URL provided")
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("DisplayManager started (fps=%.1f). URL=%s", self.fps, self.url)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        logger.info("DisplayManager stopped")

    def _get_font(self, font_name: str, size: int) -> ImageFont.ImageFont:
        """Get font with caching and fallback logic."""
        cache_key = f"{font_name}_{size}"
        if cache_key not in self._font_cache:
            try:
                self._font_cache[cache_key] = ImageFont.truetype(font_name, size)
            except (OSError, IOError):
                try:
                    self._font_cache[cache_key] = ImageFont.truetype(Fonts.FALLBACK_MONO, size)
                except (OSError, IOError):
                    self._font_cache[cache_key] = ImageFont.load_default()
        return self._font_cache[cache_key]

    def _center_text_x(self, text: str, font: ImageFont.ImageFont) -> int:
        """Calculate centered x position for text."""
        bbox = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        return (DISPLAY_W - text_width) // 2

    def _get_current_voltage(self) -> Optional[float]:
        try:
            data = self.logger.get_recent(seconds=2.0)
            if data:
                return float(data[-1][1])
        except Exception:
            logger.exception("Error reading current voltage from datalogger")
        return None

    def _draw_qr_code(self, draw: ImageDraw.ImageDraw) -> None:
        """Draw QR code in top-right corner if URL is available."""
        if not self.url:
            return
            
        qr = qrcode.QRCode(border=1, box_size=3)
        qr.add_data(self.url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color=Colors.WHITE, back_color=Colors.BLACK).convert("RGB")
        qr_img = ImageOps.contain(qr_img, (Layout.QR_SIZE, Layout.QR_SIZE))
        
        qx = DISPLAY_W - Layout.QR_SIZE - Layout.MARGIN
        qy = Layout.MARGIN
        draw._image.paste(qr_img, (qx, qy))

    def _draw_title(self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> None:
        """Draw title at top of display."""
        title = "PIKA-PIKA MONITOR"
        draw.text((Layout.MARGIN, Layout.TITLE_Y), title, fill=Colors.GREEN, font=font)

    def _draw_voltage(self, draw: ImageDraw.ImageDraw, large_font: ImageFont.ImageFont) -> int:
        """Draw voltage reading in center. Returns y position for next element."""
        voltage = self._get_current_voltage()
        if voltage is None or (isinstance(voltage, float) and (voltage != voltage)):
            vtext = "--.- V"
        else:
            vtext = f"{voltage:.1f} V"

        vx = self._center_text_x(vtext, large_font)
        vy = DISPLAY_H // 2 + Layout.VOLTAGE_Y_OFFSET
        draw.text((vx, vy), vtext, fill=Colors.GREEN, font=large_font)
        return vy

    def _draw_anomaly_status(self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont, y_position: int) -> None:
        """Draw anomaly status below voltage reading."""
        anom_count = self._get_recent_anomaly_count(hours=1)
        if anom_count > 0:
            anom_text = f"{anom_count} anomalies"
            anom_color = Colors.RED
        else:
            anom_text = "No anomalies"
            anom_color = Colors.GREEN

        ax = self._center_text_x(anom_text, font)
        ay = y_position + Layout.ANOMALY_Y_OFFSET
        draw.text((ax, ay), anom_text, fill=anom_color, font=font)

    def _draw_time(self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> None:
        """Draw current time at bottom."""
        ts = time.strftime("%H:%M:%S")
        tx = self._center_text_x(ts, font)
        ty = DISPLAY_H - Layout.TIME_Y_OFFSET
        draw.text((tx, ty), ts, fill=Colors.GREEN, font=font)

    def _draw_mascot(self, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> None:
        """Draw mascot tagline at very bottom."""
        mascot = "⚡ Electric Mascot ⚡"
        mx = self._center_text_x(mascot, font)
        my = DISPLAY_H - Layout.MASCOT_Y_OFFSET
        draw.text((mx, my), mascot, fill=Colors.GREEN, font=font)

    def _draw_frame(self) -> Image.Image:
        """Draw complete display frame with all UI elements."""
        image = Image.new("RGB", (DISPLAY_W, DISPLAY_H), color=Colors.BLACK)
        draw = ImageDraw.Draw(image)
        
        # Store reference for positioning calculations
        draw._image = image
        
        font = self._get_font(Fonts.PREFERRED_MONO, Layout.SMALL_FONT_SIZE)
        large_font = self._get_font(Fonts.PREFERRED_MONO, Layout.LARGE_FONT_SIZE)
        
        self._draw_qr_code(draw)
        self._draw_title(draw, font)
        voltage_y = self._draw_voltage(draw, large_font)
        self._draw_anomaly_status(draw, font, voltage_y)
        self._draw_time(draw, font)
        self._draw_mascot(draw, font)
        
        return image

    def _get_recent_anomaly_count(self, hours: float = 3.0) -> int:
        """Count highlights in `data/highlights.json` whose end or peak is within the past `hours` hours."""
        highlights_path = os.path.join(self.data_dir, 'highlights.json')
        if not os.path.exists(highlights_path):
            return 0
            
        try:
            with open(highlights_path, 'r') as f:
                highlights_data = json.load(f)
            
            cutoff_time = time.time() - (hours * 3600.0)
            return sum(
                1 for highlight in highlights_data
                if (highlight.get('end_ts', 0) >= cutoff_time or 
                    highlight.get('peak_ts', 0) >= cutoff_time)
            )
        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.warning("Failed to read highlights.json for anomaly count: %s", e)
            return 0

    def _is_raspberry_pi(self) -> bool:
        """Check if running on Raspberry Pi (Linux)."""
        return platform.system() == "Linux"

    def _render_frame(self) -> None:
        """Render and display a single frame."""
        try:
            frame = self._draw_frame()
            if not show_on_waveshare(frame):
                frame.save("lcd_latest.png")
        except Exception as e:
            logger.error("Failed to render display frame: %s", e)

    def _run(self) -> None:
        """Main display loop running in separate thread."""
        if not self._is_raspberry_pi():
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


class DisplayManagerSingleton:
    """Singleton pattern for managing the global display manager instance."""
    
    def __init__(self):
        self._instance: Optional[DisplayManager] = None
    
    def start_display(
        self,
        logger_obj,
        url: Optional[str] = None,
        auto_ip: bool = True,
        port: int = 8000,
        fps: float = 5.0,
        data_dir: str = 'data'
    ) -> DisplayManager:
        """Start the display manager if not already running."""
        if self._instance is None:
            self._instance = DisplayManager(
                logger_obj, url=url, auto_ip=auto_ip, 
                port=port, fps=fps, data_dir=data_dir
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
        """Get the current display manager instance."""
        return self._instance

# Global singleton instance
_display_singleton = DisplayManagerSingleton()

# Public API functions for backward compatibility
def start_display(
    logger_obj,
    url: Optional[str] = None,
    auto_ip: bool = True,
    port: int = 8000,
    fps: float = 5.0,
    data_dir: str = 'data'
) -> DisplayManager:
    """Start the display manager singleton."""
    return _display_singleton.start_display(
        logger_obj, url=url, auto_ip=auto_ip, 
        port=port, fps=fps, data_dir=data_dir
    )

def stop_display() -> None:
    """Stop the display manager singleton."""
    _display_singleton.stop_display()
