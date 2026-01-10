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
