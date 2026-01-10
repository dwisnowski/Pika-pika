# Pika-pika

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

## Getting started

1. Flash a microSD card with Raspberry Pi OS (with Python 3).
2. Connect the ADS1115 (I2C) and ZMPT101B sensor to the Pi following `docs/wiring.svg`.
3. Install Python dependencies and install the package:

```bash
pip install .
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

6. Open `http://<pi-ip>:8000/` on a phone or other device on the same network to view live data.

> **Note:** FastAPI + Uvicorn is lightweight and should run fine on a Raspberry Pi 2 for this workload (100 Hz sampling + light web UI). If you plan heavy workloads or more concurrent users, consider tuning worker settings or using a lightweight process supervisor.

---

If you'd like, I can add a systemd service file, logging rotation, or a sample wiring photo you can include in this repo.

---

Contributions and issues are welcome — see `CONTRIBUTING.md` (when added).
