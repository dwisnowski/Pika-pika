# Raspberry Pi OS Lite 32-bit Setup Guide

## Installation Instructions

### 1. Download and Install Raspberry Pi OS Lite (32-bit)

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/) for your operating system
2. Insert your microSD card into your computer
3. Launch Raspberry Pi Imager
4. Click **"Choose OS"**
5. Select **Raspberry Pi OS (other)** → **Raspberry Pi OS Lite (32-bit)**
6. Click **"Choose Storage"** and select your microSD card
7. Click **"Write"** to flash the OS to your card
8. Once complete, safely eject the microSD card

### 2. Initial Boot

1. Insert the microSD card into your Raspberry Pi
2. Connect power, keyboard, and monitor
3. Complete the initial setup wizard (set username, password, WiFi, etc.)

## Bootstrap Commands for Development Setup

Run the following commands in order to set up your Raspberry Pi for development:

### Update System Packages
```bash
sudo apt update && sudo apt upgrade -y
```

### Configure Raspberry Pi Connect
```bash
rpi-connect signin
rpi-connect shell on
```

### Install Git
```bash
sudo apt install git -y
```

### Clone Project Repository
```bash
git clone https://github.com/dwisnowski/Pika-pika.git
```

### Navigate to Project and Run Setup
```bash
cd Pika-pika
make setup
```

## Notes

- Make sure you have a stable internet connection during the setup process
- The `make setup` command assumes there's a Makefile in the Pika-pika repository with a setup target
- If you encounter any permission issues, you may need to use `sudo` for certain commands

## Troubleshooting

If you experience issues with `rpi-connect`, ensure you're running the latest version of Raspberry Pi OS and that the service is properly installed:

```bash
sudo apt install rpi-connect
```