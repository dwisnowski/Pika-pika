#!/usr/bin/env bash
set -euo pipefail

echo "[pika-pika] Updating apt and installing system packages (requires sudo)..."
sudo apt update
sudo apt install -y python3 python3-venv python3-pip build-essential git i2c-tools python3-dev

# Create a virtualenv if needed
if [ ! -d ".venv" ]; then
  echo "[pika-pika] Creating virtualenv (.venv)"
  python3 -m venv .venv
fi

echo "[pika-pika] Activating venv and installing Python dependencies..."
# shellcheck disable=SC1091
. .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install . || { echo "[pika-pika] pip install failed"; exit 1; }

# Try installing optional hardware deps, but don't fail if not present
echo "[pika-pika] Installing optional hardware extras (ADS1115). This may fail on non-Pi or missing wheels; it's optional." 
pip install .[hardware] || echo "[pika-pika] Optional hardware extras could not be installed (continue)"

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
