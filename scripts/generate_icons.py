#!/usr/bin/env python3
"""Generate favicon and icon assets from `pika/static/Pika-pika.png`.

Outputs (to `pika/static/`):
- favicon.ico (contains 16x16 and 32x32)
- favicon-16x16.png
- favicon-32x32.png
- apple-touch-icon.png (180x180)
- Pika-pika.webp (compressed WebP)
- Pika-pika-optimized.png (optimized PNG)

Usage:
    python scripts/generate_icons.py

Requires: Pillow (already in project dependencies)
"""
from PIL import Image
from pathlib import Path
import sys

SRC = Path('pika/static/Pika-pika.png')
OUT_DIR = Path('pika/static')

if not SRC.exists():
    print(f"Source image not found: {SRC}. Make sure you have placed your PNG at that path.")
    sys.exit(2)

OUT_DIR.mkdir(parents=True, exist_ok=True)

with Image.open(SRC) as im:
    im = im.convert('RGBA')
    # 16x16
    im16 = im.copy()
    im16.thumbnail((16,16), Image.LANCZOS)
    im16.save(OUT_DIR / 'favicon-16x16.png', optimize=True)

    # 32x32
    im32 = im.copy()
    im32.thumbnail((32,32), Image.LANCZOS)
    im32.save(OUT_DIR / 'favicon-32x32.png', optimize=True)

    # apple touch 180x180
    im180 = im.copy()
    im180.thumbnail((180,180), Image.LANCZOS)
    im180.save(OUT_DIR / 'apple-touch-icon.png', optimize=True)

    # optimized PNG
    im_opt = im.copy()
    im_opt.save(OUT_DIR / 'Pika-pika-optimized.png', optimize=True)

    # WebP
    try:
        im_webp = im.copy()
        im_webp.save(OUT_DIR / 'Pika-pika.webp', format='WEBP', quality=85, method=6)
    except Exception as e:
        print('Warning: could not write WebP:', e)

    # ICO (multiple sizes)
    try:
        sizes = [(16,16),(32,32)]
        im_icon = im.copy()
        im_icon.save(OUT_DIR / 'favicon.ico', sizes=sizes)
    except Exception as e:
        print('Warning: could not write ICO:', e)

print('Generated icons in', OUT_DIR)
