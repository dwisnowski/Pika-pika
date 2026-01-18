# Raspberry Pi Setup Guide

This guide covers everything from flashing the OS to running Pika-pika as a system service.

## Prerequisites

- **Raspberry Pi**: Raspberry Pi 2B+ or later (tested on Pi 2B).
- **OS**: Raspberry Pi OS Lite (32-bit) is recommended for performance.
- **Hardware**: ADS1115 ADC and ZMPT101B voltage sensor.

## 1. OS Installation

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Insert your microSD card.
3. Launch Imager and click **Choose OS**.
4. Select **Raspberry Pi OS (other)** → **Raspberry Pi OS Lite (32-bit)**.
5. Click **Choose Storage** and select your microSD card.
6. (Optional) Use the settings icon to pre-configure WiFi, SSH, and hostname (`pika-pika`).
7. Click **Write**.

## 2. Project Setup

Once your Pi is booted and you have SSH access:

### Update and Install Git
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install git -y
```

### Clone and Setup
```bash
git clone https://github.com/dwisnowski/Pika-pika.git
cd Pika-pika
bash scripts/setup_pi.sh
```
The `setup_pi.sh` script will:
- Install system dependencies.
- Create a virtual environment.
- Install Python packages.
- Ask to enable I2C.
- Offer to install the systemd service.

## 3. Running the App

### Manual Run
```bash
make run
```

### Development Mode
```bash
make dev
```

## 4. System Integration

### Systemd Service
If you didn't install it during `setup_pi.sh`, you can do so manually:
```bash
sudo bash scripts/install_systemd.sh
```

### Monitoring Logs
```bash
sudo systemctl status pika-pika
sudo journalctl -u pika-pika -f
```

### Watchdog
The application includes a systemd watchdog helper. If the datalogger stops sampling, systemd will automatically restart the service.

## 5. Hardware Configuration

### Enable I2C & SPI
If not already enabled:
```bash
# Enable I2C
sudo raspi-config nonint do_i2c 0
# Enable SPI
sudo raspi-config nonint do_spi 0
```
Then reboot your system.

### Wiring
Refer to the [Wiring Guide](wiring-steps.md) for detailed schematics.
