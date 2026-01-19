"""Render a QR code for a URL and show it on a Waveshare 2" (240x320) SPI LCD.

This script uses PIL + qrcode to generate an image sized for the display. It attempts to use
common Waveshare / ST7789 Python drivers when available, and falls back to writing a PNG to
`qr_lcd.png` when running on a non-Pi or without drivers installed.

Reference (Waveshare): https://www.waveshare.com/wiki/2inch_LCD_Module?amazon#python_2

Usage examples:
  # show QR of the running UI origin
  python -m pika.mini_display --url http://192.168.1.50:8000

  # auto-detect the current device LAN IP and use port 8000
  python -m pika.mini_display --auto-ip --port 8000

Note: This script is optional; add the `display` extra (spidev, RPi.GPIO) if you plan to run on Pi.
"""
from __future__ import annotations

import argparse
import socket
import sys
from typing import Optional

from PIL import Image
import os
import logging

from .qr_generator import make_qr_image

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


def show_on_waveshare(img: Image.Image, lcd_config: Optional[dict] = None) -> bool:
    """Attempt several Waveshare/ST7789 display drivers. Returns True if successful."""
    tried = []

    # 1) Try Adafruit RGB Display (CircuitPython/Blinka) - Preferred
    try:
        import board
        import digitalio
        from adafruit_rgb_display import st7789 as st_ada

        def get_pin(num, default_name):
            pin_name = f"D{num}"
            if hasattr(board, pin_name):
                return getattr(board, pin_name)
            if hasattr(board, default_name):
                return getattr(board, default_name)
            return None

        if lcd_config:
            cs_pin = digitalio.DigitalInOut(get_pin(lcd_config.get("lcd_cs", 8), "CE0"))
            dc_pin = digitalio.DigitalInOut(get_pin(lcd_config.get("lcd_dc", 25), "D25"))
            reset_pin = digitalio.DigitalInOut(get_pin(lcd_config.get("lcd_rst", 27), "D27"))
            bl_pin_num = lcd_config.get("lcd_bl", 24)
            if bl_pin_num:
                try:
                    bl_pin = digitalio.DigitalInOut(get_pin(bl_pin_num, "D24"))
                    bl_pin.switch_to_output()
                    bl_pin.value = True
                except Exception:
                    pass
        else:
            cs_pin = digitalio.DigitalInOut(board.CE0)
            dc_pin = digitalio.DigitalInOut(board.D25)
            reset_pin = digitalio.DigitalInOut(board.D24)

        spi = board.SPI()
        # Create display. 2.0" ST7789 is typically 240x320.
        # adafruit_rgb_display handles the rotation and dimensions.
        disp = st_ada.ST7789(
            spi,
            rotation=90,
            cs=cs_pin,
            dc=dc_pin,
            rst=reset_pin,
            baudrate=24000000,
        )

        # The adafruit_rgb_display library expects images to match the display size.
        # Ensure the image matches the current display dimensions (after rotation)
        if disp.rotation % 180 == 90:
            target_width = disp.height
            target_height = disp.width
        else:
            target_width = disp.width
            target_height = disp.height
            
        if img.width != target_width or img.height != target_height:
            img = img.resize((target_width, target_height), Image.Resampling.BICUBIC)
            
        disp.image(img)
        return True
    except Exception as e:
        tried.append(f"adafruit_rgb_display: {e}")

    # # 2) Try Waveshare LCD example module name 'LCD_2inch' (Waveshare sample naming)
    # try:
    #     import LCD_2inch as lcd

    #     logger.info("Using LCD_2inch driver from Waveshare examples")
    #     lcd.Init()
    #     # Some drivers expect 24-bit or mirrored images; try ShowImage or ShowPic-like API
    #     try:
    #         lcd.ShowImage(img)
    #     except AttributeError:
    #         # Some examples require a raw image buffer
    #         if hasattr(lcd, 'LCD_ShowImage'):
    #             lcd.LCD_ShowImage(img)
    #         else:
    #             # fallback to rotating and showing via generic method
    #             lcd.Init()
    #             lcd.ShowImage(img.rotate(0))
    #     return True
    # except Exception as e:
    #     tried.append(f"LCD_2inch: {e}")

    # # 3) Try st7789 library (common for 240x320 SPI LCDs)
    # try:
    #     import st7789 as st

    #     logger.info("Using st7789 driver")
    #     if lcd_config:
    #         disp = st.ST7789(
    #             port=lcd_config.get("lcd_port", 0),
    #             cs=lcd_config.get("lcd_cs", 8),
    #             dc=lcd_config.get("lcd_dc", 25),
    #             backlight=lcd_config.get("lcd_bl", 24),
    #             rst=lcd_config.get("lcd_rst", 27)
    #         )
    #     else:
    #         disp = st.ST7789()
    #     # The st7789 library commonly offers a display(image) method
    #     try:
    #         disp.display(img)
    #     except Exception:
    #         # try a different method name
    #         if hasattr(disp, 'displayimage'):
    #             disp.displayimage(img)
    #         else:
    #             raise
    #     return True
    # except Exception as e:
    #     tried.append(f"st7789: {e}")

    # # 4) Try PIL-based Waveshare wrapper naming variations (older samples)
    # try:
    #     import LCD as lcdmod
    #     logger.info("Using LCD driver (generic) from Waveshare samples")
    #     try:
    #         lcdmod.Init()
    #         lcdmod.ShowImage(img)
    #         return True
    #     except Exception as e:
    #         tried.append(f"LCD generic show failed: {e}")
    # except Exception as e:
    #     tried.append(f"LCD generic import: {e}")

    full_error_msg = "; ".join(tried)
    if "libopenblas" in full_error_msg or "libatlas" in full_error_msg:
        if not getattr(show_on_waveshare, "_logged_sys_err", False):
            logger.error("Display driver failed due to missing system libraries (libopenblas/libatlas).")
            logger.error("Please run: sudo apt-get install -y libopenblas-dev")
            show_on_waveshare._logged_sys_err = True
    elif "[Errno 2]" in full_error_msg or "No such file or directory" in full_error_msg:
        if not getattr(show_on_waveshare, "_logged_spi_err", False):
            logger.error("Display driver failed: SPI interface not found.")
            logger.error("Please enable SPI: sudo raspi-config nonint do_spi 0")
            show_on_waveshare._logged_spi_err = True
    
    logger.warning("No supported display driver found. Tried: %s", full_error_msg)
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
    img = make_qr_image(url, DISPLAY_W, DISPLAY_H)

    # Try to load config for pins
    lcd_config = None
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        config_path = os.path.join(os.path.dirname(__file__), "..", "config.toml")
        if os.path.exists(config_path):
            with open(config_path, "rb") as f:
                full_config = tomllib.load(f)
                lcd_config = full_config.get("pins")
    except Exception:
        pass

    ok = show_on_waveshare(img, lcd_config=lcd_config)
    if not ok:
        out_path = args.save
        img.save(out_path)
        logger.info("Saved fallback PNG to %s. Use this file to test or display manually.", out_path)
        print(f"Saved fallback QR image: {out_path}")


if __name__ == "__main__":
    main()
