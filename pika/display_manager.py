"""Display manager for Waveshare/ST7789 240x320 SPI displays.

- Renders the QR code (URL) when started.
- Runs a simple, original "electric mascot" animation (non-copyrighted) at a low framerate.
- Overlays the current voltage reading from the datalogger.

This module attempts to use the same display drivers as `pika/display_qr.py` and falls back to saving PNGs for testing.
"""
from __future__ import annotations

import os
import platform
import threading
import time
import logging
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps
import qrcode

from .display_qr import make_qr_image, show_on_waveshare, get_local_ip, DISPLAY_W, DISPLAY_H

logger = logging.getLogger(__name__)

class DisplayManager:
    def __init__(self, logger_obj, url: Optional[str] = None, auto_ip: bool = True, port: int = 8000, fps: float = 5.0, data_dir: str = "data"):
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
        # try to pick a small font; fallback to default if not available
        try:
            self.font = ImageFont.truetype("DejaVuSans-Bold.ttf", 14)
        except Exception:
            self.font = ImageFont.load_default()

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

    def _get_current_voltage(self) -> Optional[float]:
        try:
            data = self.logger.get_recent(seconds=2.0)
            if data:
                return float(data[-1][1])
        except Exception:
            logger.exception("Error reading current voltage from datalogger")
        return None

    def _draw_frame(self) -> Image.Image:
        # Build a display frame matching the demo page LCD preview layout
        im = Image.new("RGB", (DISPLAY_W, DISPLAY_H), color=(0, 0, 0))  # Black background
        draw = ImageDraw.Draw(im)

        # Try to use monospace font, fallback to default
        try:
            font = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 10)
        except Exception:
            try:
                font = ImageFont.truetype("Courier New", 10)
            except Exception:
                font = ImageFont.load_default()

        # QR code at top right
        if self.url:
            qr = qrcode.QRCode(border=1, box_size=3)
            qr.add_data(self.url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="white", back_color="black").convert("RGB")
            qr_size = 60  # Small QR for LCD
            qr_img = ImageOps.contain(qr_img, (qr_size, qr_size))
            qx = DISPLAY_W - qr_size - 8  # Top right
            qy = 8
            im.paste(qr_img, (qx, qy))

        # Title at top
        title = "PIKA-PIKA MONITOR"
        draw.text((8, 8), title, fill=(0, 255, 0), font=font)

        # Voltage display in center
        voltage = self._get_current_voltage()
        if voltage is None or (isinstance(voltage, float) and (voltage != voltage)):
            vtext = "--.- V"
        else:
            vtext = f"{voltage:.1f} V"

        # Use larger font for voltage
        try:
            large_font = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 14)
        except Exception:
            try:
                large_font = ImageFont.truetype("Courier New", 14)
            except Exception:
                large_font = ImageFont.load_default()

        vbbox = draw.textbbox((0, 0), vtext, font=large_font)
        vwidth = vbbox[2] - vbbox[0]
        vx = (DISPLAY_W - vwidth) // 2  # Center horizontally
        vy = DISPLAY_H // 2 - 20  # Center vertically, slightly up
        draw.text((vx, vy), vtext, fill=(0, 255, 0), font=large_font)

        # Anomaly status below voltage
        anom_count = self._get_recent_anomaly_count(hours=1)  # Check past hour
        if anom_count > 0:
            anom_text = f"{anom_count} anomalies"
            anom_color = (255, 107, 107)  # Red tint for anomalies
        else:
            anom_text = "No anomalies"
            anom_color = (0, 255, 0)  # Green for no anomalies

        abbox = draw.textbbox((0, 0), anom_text, font=font)
        awidth = abbox[2] - abbox[0]
        ax = (DISPLAY_W - awidth) // 2  # Center horizontally
        ay = vy + 24  # Below voltage
        draw.text((ax, ay), anom_text, fill=anom_color, font=font)

        # Time at bottom center
        ts = time.strftime("%H:%M:%S")
        ts_bbox = draw.textbbox((0, 0), ts, font=font)
        ts_width = ts_bbox[2] - ts_bbox[0]
        tx = (DISPLAY_W - ts_width) // 2  # Center horizontally
        ty = DISPLAY_H - 24  # Near bottom
        draw.text((tx, ty), ts, fill=(0, 255, 0), font=font)

        # Mascot tagline at very bottom
        mascot = "⚡ Electric Mascot ⚡"
        mbbox = draw.textbbox((0, 0), mascot, font=font)
        mwidth = mbbox[2] - mbbox[0]
        mx = (DISPLAY_W - mwidth) // 2  # Center horizontally
        my = DISPLAY_H - 12  # Very bottom
        draw.text((mx, my), mascot, fill=(0, 255, 0), font=font)

        return im

    def _get_recent_anomaly_count(self, hours: float = 3.0) -> int:
        """Count highlights in `data/highlights.json` whose end or peak is within the past `hours` hours."""
        try:
            path = os.path.join(self.data_dir, 'highlights.json')
            if not os.path.exists(path):
                return 0
            import json
            with open(path, 'r') as f:
                data = json.load(f)
            now = time.time()
            cutoff = now - (float(hours) * 3600.0)
            count = 0
            for h in data:
                end_ts = h.get('end_ts') or 0
                peak_ts = h.get('peak_ts') or 0
                if end_ts >= cutoff or peak_ts >= cutoff:
                    count += 1
            return count
        except Exception:
            logger.exception("Failed to read highlights.json for anomaly count")
            return 0

    def _run(self):
        # Skip LCD operations entirely if not on Linux (Raspberry Pi)
        is_linux = platform.system() == "Linux"
        if not is_linux:
            logger.info("DisplayManager: skipping LCD operations (not on Linux/Raspberry Pi)")
            return

        # Render initial QR immediately
        try:
            frame = self._draw_frame()
            ok = show_on_waveshare(frame)
            if not ok:
                frame.save("lcd_latest.png")
        except Exception:
            logger.exception("Initial display render failed")

        while not self._stop.is_set():
            start = time.time()
            try:
                self.frame_idx += 1
                frame = self._draw_frame()
                ok = show_on_waveshare(frame)
                if not ok:
                    frame.save("lcd_latest.png")
            except Exception:
                logger.exception("Error updating display frame")
            elapsed = time.time() - start
            sleep_for = self.interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)


# Simple helper for external use
_mgr: Optional[DisplayManager] = None

def start_display(logger_obj, url: Optional[str] = None, auto_ip: bool = True, port: int = 8000, fps: float = 5.0, data_dir: str = 'data'):
    global _mgr
    if _mgr is None:
        _mgr = DisplayManager(logger_obj, url=url, auto_ip=auto_ip, port=port, fps=fps, data_dir=data_dir)
        _mgr.start()
    return _mgr


def stop_display():
    global _mgr
    if _mgr:
        _mgr.stop()
        _mgr = None
