# Pika-pika

[![MkDocs Deploy](https://github.com/dwisnowski/Pika-pika/actions/workflows/mkdocs-deploy.yml/badge.svg)](https://github.com/dwisnowski/Pika-pika/actions/workflows/mkdocs-deploy.yml)
[![GitHub Pages](https://img.shields.io/website?down_color=red&down_message=down&up_color=blue&up_message=up&url=https://dwisnowski.github.io/Pika-pika/)](https://dwisnowski.github.io/Pika-pika/)

![Pika-pika logo](pika/static/Pika-pika.png)  
A **Python-based** Raspberry Pi voltage logger and live web viewer.

## Project overview

This project is a lightweight, Python-based voltage logger that runs on a **Raspberry Pi 2** and can do all of the following at the same time:

- ✔ Sample voltage at **100 Hz**
- ✔ Log data to disk
- ✔ Run a Python-based web server
- ✔ View results live on your phone on the same Wi‑Fi network

## Features

- Real-time sampling and logging
- Simple web UI for live monitoring
- Minimal resource requirements — Raspberry Pi 2 is sufficient

## Hardware

Required hardware:

- **Raspberry Pi 2**
- **ADS1115 ADC**
- **ZMPT101B AC voltage sensor**
- **5 V power supply**
- **microSD card**
- **Jumper wires**
- **Safe enclosure + fuse**

### Wiring

See the wiring diagram: `docs/wiring.svg` (illustrative). **Do not connect mains directly** — use proper isolation, a fuse, and follow local regulations. ZMPT101B outputs typically need biasing/conditioning before feeding an ADC.


## Raspberry Pi Pre-requistites:
Model: Raspberry pi 2b+ 
OS: Pi OS 32bit Lite
Hostname: pika-pika
Username: pika
Password: pikachu


## Getting started

1. Flash a microSD card with Raspberry Pi OS (with Python 3).
2. Connect the ADS1115 (I2C) and ZMPT101B sensor to the Pi following `docs/wiring.svg`.
3. Install Python dependencies and install the package:

```bash
uv pip install .
```

4. Run the app (this starts sampling at 100 Hz and serves the web UI):

```bash
# Run with uvicorn (ASGI server)
uvicorn pika.app:app --host 0.0.0.0 --port 8000
# or use the Makefile (recommended):
make venv
make install
make run
```

5. Quick setup on Raspberry Pi

- Interactive script (recommended):

```bash
# Run the helper script which installs system packages, creates a venv, and installs Python deps
bash scripts/setup_pi.sh
```

- Or use `make setup` to call the same script:

```bash
make setup
```

### Autostart (systemd)

You can enable the app to start automatically on boot via the included installer script.

```bash
# Install and enable the systemd service (requires sudo)
sudo bash scripts/install_systemd.sh
```

### Icons & social preview

Documentation site

This project uses **MkDocs** for documentation. The docs are built and published to GitHub Pages when you push to `main` (the workflow builds the site and publishes the `site/` output to the `gh-pages` branch). To preview locally run:

```bash
make docs-serve
```


A project PNG (`pika/static/Pika-pika.png`) is used as the site logo and social preview image. To generate favicons and optimized assets from that PNG run:

```bash
# generate favicons, webp, and optimized PNG
make icons
# or
python scripts/generate_icons.py
```

This creates `pika/static/favicon.ico`, `favicon-32x32.png`, `favicon-16x16.png`, `apple-touch-icon.png`, `Pika-pika.webp`, and `Pika-pika-optimized.png` which are linked in the site head for better browser and social previews.
# Check status and logs
sudo systemctl status pika-pika
sudo journalctl -u pika-pika -f
```

The systemd service is configured with `Type=notify` and `WatchdogSec=30`. The app uses `sdnotify` if available to:

- send `READY=1` when startup is complete, and
- periodically send `WATCHDOG=1` while the datalogger is producing fresh samples.

If the datalogger stops producing samples (for example, hardware failure or process hangs), the watchdog helper will stop pinging systemd and systemd will restart the service automatically.

If you want to modify runtime options (port, venv path, user), edit `/etc/systemd/system/pika-pika.service`, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl restart pika-pika
```

(When you run `bash scripts/setup_pi.sh` interactively it will offer to install this systemd service for you and to configure system NTP for accurate timestamps.)

6. Open `http://<pi-ip>:8000/` on a phone or other device on the same network to view live data.

Demo preview: If you don’t have the hardware connected (or you want to try the UI), open `http://<pi-ip>:8000/demo` to view a mocked data demo page that simulates voltage readings and highlights for easy exploration without hardware.

> **Note:** FastAPI + Uvicorn is lightweight and should run fine on a Raspberry Pi 2 for this workload (100 Hz sampling + light web UI). If you plan heavy workloads or more concurrent users, consider tuning worker settings or using a lightweight process supervisor.

---

## Displaying the QR on a Waveshare 2" (240x320) SPI LCD

If you have a Waveshare 2" LCD attached to the Pi (SPI), you can render the QR code directly to the screen with the included helper script `pika/display_qr.py`.

- Install optional display/system packages (on the Pi):

```bash
# using the helper script (preferred)
bash scripts/setup_pi.sh
# or install the display optional deps directly:
uv pip install .[display]
```

- Generate and show the QR code (auto-detect local IP):

```bash
# auto-detect local IP and display QR linking to http://<ip>:8000
python -m pika.display_qr --auto-ip --port 8000
```

- Or pass a URL directly:

```bash
python -m pika.display_qr --url http://192.168.1.50:8000
```

Notes
- The script tries several common Waveshare/ST7789 driver names (`LCD_2inch`, `st7789`, `LCD` from Waveshare Python examples). If no supported driver is found it will save `qr_lcd.png` in the repo root as a fallback.
- The app will now render the QR on the attached display when the FastAPI app starts and continuously runs a small original "electric mascot" animation that also overlays the current voltage reading (updated from the datalogger) and the number of detected anomalies in the past 3 hours.
- See Waveshare's docs for driver installation and wiring: https://www.waveshare.com/wiki/2inch_LCD_Module?amazon#python_2

---

If you'd like, I can add a systemd service file, logging rotation, or a sample wiring photo you can include in this repo.

---

Contributions and issues are welcome — see `CONTRIBUTING.md` (when added).
