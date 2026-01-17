"""Render a QR code for a URL and show it on a Waveshare 2" (240x320) SPI LCD.

This script uses PIL + qrcode to generate an image sized for the display. It attempts to use
common Waveshare / ST7789 Python drivers when available, and falls back to writing a PNG to
`qr_lcd.png` when running on a non-Pi or without drivers installed.

Reference (Waveshare): https://www.waveshare.com/wiki/2inch_LCD_Module?amazon#python_2

Usage examples:
  # show QR of the running UI origin
  python -m pika.display_qr --url http://192.168.1.50:8000

  # auto-detect the current device LAN IP and use port 8000
  python -m pika.display_qr --auto-ip --port 8000

Note: This script is optional; add the `display` extra (spidev, RPi.GPIO) if you plan to run on Pi.
"""
from __future__ import annotations

import argparse
import socket
import sys
from typing import Optional

from PIL import Image, ImageOps
import qrcode
import os
import logging

from .qr_generator import QRCodeGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DISPLAY_W = 240
DISPLAY_H = 320


def get_local_ip() -> Optional[str]:
    # Connect to a public IP to determine the outbound interface IP (no data sent)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def show_on_waveshare(img: Image.Image) -> bool:
    """Attempt several Waveshare/ST7789 display drivers. Returns True if successful."""
    # Try common Waveshare python example modules
    tried = []
    # 1) Try Waveshare LCD example module name 'LCD_2inch' (Waveshare sample naming)
    try:
        import LCD_2inch as lcd

        logger.info("Using LCD_2inch driver from Waveshare examples")
        lcd.Init()
        # Some drivers expect 24-bit or mirrored images; try ShowImage or ShowPic-like API
        try:
            lcd.ShowImage(img)
        except AttributeError:
            # Some examples require a raw image buffer
            if hasattr(lcd, 'LCD_ShowImage'):
                lcd.LCD_ShowImage(img)
            else:
                # fallback to rotating and showing via generic method
                lcd.Init()
                lcd.ShowImage(img.rotate(0))
        return True
    except Exception as e:
        tried.append(f"LCD_2inch: {e}")

    # 2) Try st7789 library (common for 240x320 SPI LCDs)
    try:
        import st7789 as st

        logger.info("Using st7789 driver")
        disp = st.ST7789()
        # The st7789 library commonly offers a display(image) method
        try:
            disp.display(img)
        except Exception:
            # try a different method name
            if hasattr(disp, 'displayimage'):
                disp.displayimage(img)
            else:
                raise
        return True
    except Exception as e:
        tried.append(f"st7789: {e}")

    # 3) Try PIL-based Waveshare wrapper naming variations (older samples)
    try:
        import LCD as lcdmod
        logger.info("Using LCD driver (generic) from Waveshare samples")
        try:
            lcdmod.Init()
            lcdmod.ShowImage(img)
            return True
        except Exception as e:
            tried.append(f"LCD generic show failed: {e}")
    except Exception as e:
        tried.append(f"LCD generic import: {e}")

    logger.warning("No supported display driver found. Tried: %s", "; ".join(tried))
    return False


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--url", help="URL to encode as QR (default: auto based on --auto-ip and --port)")
    p.add_argument("--auto-ip", action="store_true", help="Auto-detect local LAN IP and use it as the host")
    p.add_argument("--port", type=int, default=8000, help="Port used when --auto-ip is set (default: 8000)")
    p.add_argument("--save", default="qr_lcd.png", help="Save fallback PNG path when display driver not available")
    args = p.parse_args(argv)

    if args.url:
        url = args.url
    elif args.auto_ip:
        ip = get_local_ip()
        if not ip:
            logger.error("Unable to auto-detect local IP address")
            sys.exit(2)
        url = f"http://{ip}:{args.port}"
    else:
        p.print_help()
        sys.exit(2)

    logger.info("Rendering QR for %s", url)
    qr_generator = QRCodeGenerator()
    img = qr_generator.make_qr_image(url, DISPLAY_W, DISPLAY_H)

    ok = show_on_waveshare(img)
    if not ok:
        out_path = args.save
        img.save(out_path)
        logger.info("Saved fallback PNG to %s. Use this file to test or display manually.", out_path)
        print(f"Saved fallback QR image: {out_path}")


if __name__ == "__main__":
    main()
