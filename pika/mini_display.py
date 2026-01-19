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
import logging
import os
from typing import Optional, Dict, Any

from PIL import Image

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

from .qr_generator import make_qr_image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DISPLAY_W = 320
DISPLAY_H = 240

# Global Caches
_DISPLAY_OBJ = None
_CONFIG_CACHE: Optional[Dict[str, Any]] = None
_QR_CACHE: Dict[str, Image.Image] = {}

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

def _load_config() -> Dict[str, Any]:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    
    config = {
        "pins": {},
        "display": {
            "rotation": 270,
            "refresh_rate": 30,
            "qr_size": 60
        }
    }
    
    if tomllib:
        try:
            config_path = os.path.join(os.path.dirname(__file__), "..", "config.toml")
            if os.path.exists(config_path):
                with open(config_path, "rb") as f:
                    loaded = tomllib.load(f)
                    if "pins" in loaded:
                        config["pins"].update(loaded["pins"])
                    if "display" in loaded:
                        config["display"].update(loaded["display"])
        except Exception as e:
            logger.warning("Failed to load config.toml: %s", e)
            
    _CONFIG_CACHE = config
    return config

def _get_display_obj(lcd_config_override: Optional[dict] = None):
    global _DISPLAY_OBJ
    if _DISPLAY_OBJ is not None:
        return _DISPLAY_OBJ

    # Merge configs
    full_config = _load_config()
    pins = full_config["pins"].copy()
    if lcd_config_override:
        pins.update(lcd_config_override)
    
    disp_cfg = full_config["display"]

    # 1) Try Adafruit RGB Display (CircuitPython/Blinka) - Preferred
    import board
    import digitalio
    from adafruit_rgb_display import st7789 as st_ada
    
    logger.info("Initializing Adafruit RGB Display (ST7789)")
    
    def get_pin(num, default_name):
        pin_name = f"D{num}"
        if hasattr(board, pin_name):
            return getattr(board, pin_name)
        if hasattr(board, default_name):
            return getattr(board, default_name)
        return None

    cs_pin = digitalio.DigitalInOut(get_pin(pins.get("lcd_cs", 8), "CE0"))
    dc_pin = digitalio.DigitalInOut(get_pin(pins.get("lcd_dc", 25), "D25"))
    reset_pin = digitalio.DigitalInOut(get_pin(pins.get("lcd_rst", 27), "D27"))
    bl_pin_num = pins.get("lcd_bl", 24)
    if bl_pin_num:
        try:
            bl_pin = digitalio.DigitalInOut(get_pin(bl_pin_num, "D24"))
            bl_pin.switch_to_output()
            bl_pin.value = True
        except Exception:
            pass

    spi = board.SPI()
    
    # Configure settings
    rotation = disp_cfg.get("rotation", 270)
    refresh_rate = disp_cfg.get("refresh_rate", 30)
    
    # Calculate Baudrate
    # Approx bits/sec = W * H * 16 * Hz
    # 240 * 320 * 16 * 30 ~= 37 Mbps
    # Add overhead
    baudrate = int(DISPLAY_W * DISPLAY_H * 16 * refresh_rate * 1.1)
    
    logger.info("Display Config: Rotation=%d, Refresh=%dHz, Baudrate=%d", rotation, refresh_rate, baudrate)
    
    _DISPLAY_OBJ = st_ada.ST7789(
        spi,
        rotation=rotation,
        cs=cs_pin,
        dc=dc_pin,
        rst=reset_pin,
        baudrate=baudrate,
    )
    return _DISPLAY_OBJ

def show_on_waveshare(img: Image.Image, lcd_config: Optional[dict] = None) -> bool:
    """Attempt several Waveshare/ST7789 display drivers. Returns True if successful."""
    tried = []

    try:
        disp = _get_display_obj(lcd_config)

        # The adafruit_rgb_display library expects images to match the display size.
        # Ensure the image matches the current display dimensions (after rotation)
        if disp.rotation % 180 == 90:
            target_width = disp.height
            target_height = disp.width
        else:
            target_width = disp.width
            target_height = disp.height
            
        # Resize or Center logic
        if img.width != target_width or img.height != target_height:
            if img.width <= target_width and img.height <= target_height:
                # Center the image on a black background
                new_img = Image.new("RGB", (target_width, target_height), (0, 0, 0))
                x = (target_width - img.width) // 2
                y = (target_height - img.height) // 2
                new_img.paste(img, (x, y))
                img = new_img
            else:
                img = img.resize((target_width, target_height), Image.Resampling.BICUBIC)
            
        disp.image(img)
        return True
    except Exception as e:
        tried.append(f"adafruit_rgb_display: {e}")

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

def get_cached_qr_image(url: str, size: int) -> Image.Image:
    """Generate and cache a QR code image."""
    key = f"{url}_{size}"
    if key in _QR_CACHE:
        return _QR_CACHE[key]
    
    img = make_qr_image(url, size, size)
    _QR_CACHE[key] = img
    return img

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
    
    # Load config to get QR size preference
    config = _load_config()
    qr_size = config["display"]["qr_size"]
    
    # Use cached QR generator (creates a small QR image of qr_size x qr_size)
    img = get_cached_qr_image(url, qr_size)

    # Try to load config for pins (passed to show_on_waveshare)
    lcd_config = config.get("pins")

    ok = show_on_waveshare(img, lcd_config=lcd_config)
    if not ok:
        out_path = args.save
        # For saving to disk, we might want the centered version or the small one?
        # User probably wants to see what would be displayed.
        # But 'img' here is small (60x60).
        # We should probably save it as small? Or let the user decide.
        # The existing code saved 'img'.
        img.save(out_path)
        logger.info("Saved fallback PNG to %s. Use this file to test or display manually.", out_path)
        print(f"Saved fallback QR image: {out_path} (Size: {img.size})")

if __name__ == "__main__":
    main()
