# Mini-Display & QR Code

Pika-pika supports displaying a QR code and live status on a Waveshare 2" (240x320) SPI LCD.

## Features

- **Live QR Link**: Shows a QR code that links directly to the Pi's web interface.
- **Mascot Animation**: A small original "electric mascot" animation.
- **Real-time Stats**: Overlays current voltage and anomaly counts (last 3 hours).
- **Auto-IP Detection**: Automatically detects the local IP for the QR code.

## Hardware Support

Designed for the **Waveshare 2" LCD Module**. It uses the ST7789 driver.

## Setup

### Optional Dependencies
Install the display-specific dependencies:
```bash
uv sync --extra display
```
Or via the setup script:
```bash
bash scripts/setup_pi.sh
```

## Usage

Run the display script:
```bash
# Auto-detect IP and display QR
python -m pika.mini_display --auto-ip --port 8000

# Specify a URL manually
python -m pika.mini_display --url http://192.168.1.50:8000
```

### Integration
The main application starts the display automatically if the hardware is detected and dependencies are installed.

## Technical Details
The script tries several driver names (`LCD_2inch`, `st7789`, `LCD`). If no hardware is found, it fallbacks to saving `qr_lcd.png` in the repository root for debugging.
