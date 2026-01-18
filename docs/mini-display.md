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
uv sync --extra rpi
```
Or via the setup script (recommended as it installs system libraries like `libopenblas-dev`):
```bash
bash scripts/setup_pi.sh
```

## Usage

Run the display script:
```bash
# Auto-detect IP and display QR
uv run python -m pika.mini_display --auto-ip --port 8000

# Specify a URL manually
uv run python -m pika.mini_display --url http://192.168.1.50:8000
```

### Integration
The main application starts the display automatically if the hardware is detected and dependencies are installed.

## Configuration & Customization

You can customize the project settings and GPIO pins by editing `config.toml` in the project root.

### Pin Definitions
The `[pins]` section allows you to customize the hardware setup:

```toml
[pins]
# ADC Settings (ADS1115)
adc_address = 0x48
adc_channel = 0

# LCD Settings (ST7789)
lcd_port = 0
lcd_device = 0
lcd_cs = 8
lcd_dc = 25
lcd_rst = 27
lcd_bl = 24
```

## Technical Details
The script tries several driver names (`LCD_2inch`, `st7789`, `LCD`). If no hardware is found, it fallbacks to saving `qr_lcd.png` in the repository root for debugging.

### Troubleshooting "libopenblas.so.0" or NumPy errors
If you see an error about `libopenblas.so.0` or `numpy` failing to import, it means some system libraries are missing. Run:
```bash
sudo apt-get install -y libopenblas-dev
```
Then try running the command again.
