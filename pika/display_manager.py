"""Display manager for Waveshare/ST7789 240x320 SPI displays.

- Renders the QR code (URL) when started.
- Runs a simple, original "electric mascot" animation (non-copyrighted) at a low framerate.
- Overlays the current voltage reading from the datalogger.

This module attempts to use the same display drivers as `pika/display_qr.py` and falls back to saving PNGs for testing.
"""
from __future__ import annotations

import threading
import time
import logging
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps
import qrcode

from .display_qr import make_qr_image, show_on_waveshare, get_local_ip, DISPLAY_W, DISPLAY_H

logger = logging.getLogger(__name__)

class DisplayManager:
    def __init__(self, logger_obj, url: Optional[str] = None, auto_ip: bool = True, port: int = 8000, fps: float = 5.0):
        self.logger = logger_obj
        self.auto_ip = auto_ip
        self.port = port
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
        # Build a display frame with QR (if available), mascot animation, and current voltage
        im = Image.new("RGB", (DISPLAY_W, DISPLAY_H), color=(255, 255, 255))
        draw = ImageDraw.Draw(im)

        # QR: generate a small QR (square), place near top center
        if self.url:
            qr = qrcode.QRCode(border=1, box_size=4)
            qr.add_data(self.url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            qr_size = min(140, DISPLAY_W - 16)
            qr_img = ImageOps.contain(qr_img, (qr_size, qr_size))
            qx = (DISPLAY_W - qr_img.width) // 2
            qy = 8
            im.paste(qr_img, (qx, qy))
            # small label under QR
            draw.text((8, qy + qr_img.height + 6), self.url, fill=(0,0,0), font=self.font)

        # Mascot animation area: simple original "electric mascot"
        # Draw a circular yellow mascot with ears and a flashing tail. Use frame_idx to animate.
        cx = DISPLAY_W // 2
        cy = int(DISPLAY_H * 0.65)
        r = 40
        # base body
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 210, 30), outline=(150, 100, 0))
        # eyes
        draw.ellipse((cx - 18, cy - 8, cx - 12, cy - 2), fill=(0,0,0))
        draw.ellipse((cx + 12, cy - 8, cx + 18, cy - 2), fill=(0,0,0))
        # cheeks (small circles)
        draw.ellipse((cx - 30, cy + 6, cx - 22, cy + 14), fill=(240,100,120))
        draw.ellipse((cx + 22, cy + 6, cx + 30, cy + 14), fill=(240,100,120))
        # ears (animated slight tilt)
        tilt = (self.frame_idx % 10) - 5
        draw.polygon([(cx - 20, cy - 38), (cx - 20 - 12 - tilt, cy - 78 - tilt), (cx - 4, cy - 38)], fill=(255,210,30), outline=(150,100,0))
        draw.polygon([(cx + 20, cy - 38), (cx + 20 + 12 + tilt, cy - 78 + tilt), (cx + 4, cy - 38)], fill=(255,210,30), outline=(150,100,0))
        # tail (lightning) — flash on alternating frames
        tail_color = (255, 230, 60) if (self.frame_idx // 3) % 2 == 0 else (220, 220, 40)
        tail = [(cx + r - 4, cy + 10), (cx + r + 18, cy - 6), (cx + r - 6, cy - 2), (cx + r + 8, cy - 28), (cx + r - 10, cy - 18)]
        draw.polygon(tail, fill=tail_color, outline=(150,100,0))

        # Voltage readout at bottom
        voltage = self._get_current_voltage()
        if voltage is None or (isinstance(voltage, float) and (voltage != voltage)):
            vtext = "Voltage: -- V"
        else:
            vtext = f"Voltage: {voltage:.3f} V"
        tw, th = draw.textsize(vtext, font=self.font)
        draw.rectangle((8, DISPLAY_H - 28, 8 + tw + 12, DISPLAY_H - 6), fill=(240,240,240))
        draw.text((14, DISPLAY_H - 24), vtext, fill=(0,0,0), font=self.font)

        # small timestamp
        ts = time.strftime("%H:%M:%S")
        draw.text((DISPLAY_W - 8 - draw.textsize(ts, font=self.font)[0], DISPLAY_H - 24), ts, fill=(80,80,80), font=self.font)

        return im

    def _run(self):
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

def start_display(logger_obj, url: Optional[str] = None, auto_ip: bool = True, port: int = 8000, fps: float = 5.0):
    global _mgr
    if _mgr is None:
        _mgr = DisplayManager(logger_obj, url=url, auto_ip=auto_ip, port=port, fps=fps)
        _mgr.start()
    return _mgr


def stop_display():
    global _mgr
    if _mgr:
        _mgr.stop()
        _mgr = None
