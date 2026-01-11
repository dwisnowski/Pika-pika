#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Pika-pika Raspberry Pi Setup Script
# ============================================================================
#
# This script performs a complete setup of the Pika-pika application on a
# Raspberry Pi. It ensures all required system packages, tools, and Python
# dependencies are installed and configured.
#
# What this script does:
#
# 1. SYSTEM PACKAGES (installed via apt):
#    - python3, python3-venv: Python runtime and virtual environment support
#    - build-essential: C/C++ build tools (required for compiling Python packages)
#    - git: Version control system
#    - i2c-tools: Tools for I2C bus communication (required for ADS1115 ADC)
#    - python3-dev: Python development headers
#    - curl: Used to download and install uv
#    - libjpeg-dev: JPEG image format support (required for Pillow)
#    - zlib1g-dev: PNG compression support (required for Pillow)
#    - libfreetype6-dev: Font rendering support (required for Pillow)
#    - liblcms2-dev: Color management support (required for Pillow)
#
# 2. PACKAGE MANAGER:
#    - Installs uv (fast Python package installer) if not present
#    - Configures uv to be available in PATH
#
# 3. PYTHON ENVIRONMENT:
#    - Creates a Python virtual environment (.venv) automatically if needed (via uv)
#    - Syncs and installs the Pika-pika package and all required dependencies using uv
#    - Attempts to install optional hardware dependencies (ADS1115 library) using uv
#
# 4. PROJECT SETUP:
#    - Creates a data/ directory for logging voltage data
#    - Sets appropriate permissions (775) on the data directory
#
# 5. OPTIONAL SERVICES (interactive prompts):
#    - Offers to install a systemd service for autostart on boot
#    - Offers to configure system NTP to use pool.ntp.org for accurate timestamps
#
# Requirements:
#    - Must be run on Raspberry Pi OS (or compatible Debian-based system)
#    - Requires sudo privileges for system package installation
#    - Requires internet connection for package downloads
#
# Usage:
#    bash scripts/setup_pi.sh
#    or
#    make setup
#
# After running this script:
#    1. Enable I2C interface: sudo raspi-config -> Interfacing Options -> I2C
#    2. Reboot the system
#    3. Start the application: make run
#
# ============================================================================

echo "[pika-pika] Updating apt and installing system packages (requires sudo)..."
sudo apt update
sudo apt install -y python3 python3-venv build-essential git i2c-tools python3-dev curl libjpeg-dev zlib1g-dev libfreetype6-dev liblcms2-dev

# Install uv if not already present and set up uv command
if ! command -v uv &> /dev/null; then
  echo "[pika-pika] Installing uv (fast Python package installer)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # Ensure uv is in PATH for this script session
  export PATH="$HOME/.cargo/bin:$PATH"
fi

# Define uv function if still not found (fallback to direct path)
if ! command -v uv &> /dev/null; then
  if [ -f "$HOME/.cargo/bin/uv" ]; then
    uv() {
      "$HOME/.cargo/bin/uv" "$@"
    }
  else
    echo "[pika-pika] Error: uv is not available. Please install manually: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
  fi
fi

# Install packages from appropriate source based on platform
if [ -f "/proc/device-tree/model" ] && grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
  echo "[pika-pika] Detected Raspberry Pi, installing packages from piwheels..."
  echo "[pika-pika] Installing Pillow, uvloop, and watchfiles from piwheels..."
  uv pip install pillow uvloop watchfiles --index-url https://www.piwheels.org/simple || { echo "[pika-pika] Package installation from piwheels failed"; exit 1; }
else
  echo "[pika-pika] Installing packages from PyPI..."
  uv pip install pillow uvloop watchfiles || { echo "[pika-pika] Package installation from PyPI failed"; exit 1; }
fi

# Sync dependencies and install package (uv will create venv if needed)
echo "[pika-pika] Syncing dependencies and installing package using uv..."
uv sync || { echo "[pika-pika] uv sync failed"; exit 1; }

# Try installing optional hardware and display deps, but don't fail if not present
echo "[pika-pika] Installing optional hardware extras (ADS1115). This may fail on non-Pi or missing wheels; it's optional."
uv sync --extra hardware || echo "[pika-pika] Optional hardware extras could not be installed (continue)"

echo "[pika-pika] Installing optional display extras (spidev, RPi.GPIO). This may fail on non-Pi; it's optional."
uv sync --extra display || echo "[pika-pika] Optional display extras could not be installed (continue)"

mkdir -p data
chmod 775 data || true

cat <<'EOF'

[pika-pika] Setup complete.
- Enable I2C: run `sudo raspi-config` -> Interfacing Options -> I2C, then reboot.
- Start the server: `.venv/bin/uvicorn pika.app:app --host 0.0.0.0 --port 8000` or run `make run`.

EOF

# Offer to install a systemd service so the app starts on boot
if [ -t 0 ]; then
  read -r -p "[pika-pika] Install systemd service to autostart app on boot? [Y/n] " RESP || true
  case "$RESP" in
    [nN]|[nN][oO]) echo "[pika-pika] Skipping systemd install";;
    *) echo "[pika-pika] Installing systemd service (requires sudo)"; sudo bash scripts/install_systemd.sh ;;
  esac
else
  echo "[pika-pika] Non-interactive shell. To enable autostart run: sudo bash scripts/install_systemd.sh"
fi

# Offer to configure system NTP (systemd-timesyncd) to use pool.ntp.org
if [ -t 0 ]; then
  read -r -p "[pika-pika] Configure system NTP to use pool.ntp.org and enable time sync? [Y/n] " RESP2 || true
  case "$RESP2" in
    [nN]|[nN][oO]) echo "[pika-pika] Skipping NTP configuration";;
    *) echo "[pika-pika] Configuring systemd-timesyncd to use pool.ntp.org (requires sudo)";
       sudo sed -i.bak -E "s/^#?NTP=.*/NTP=pool.ntp.org/" /etc/systemd/timesyncd.conf || true;
       sudo systemctl restart systemd-timesyncd.service || true;
       sudo timedatectl set-ntp true || true;
       sudo timedatectl status || true
    ;;
  esac
else
  echo "[pika-pika] Non-interactive shell. To configure NTP run: sudo sed -i.bak -E 's/^#?NTP=.*/NTP=pool.ntp.org/' /etc/systemd/timesyncd.conf && sudo systemctl restart systemd-timesyncd && sudo timedatectl set-ntp true"
fi
