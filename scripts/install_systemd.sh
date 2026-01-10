#!/usr/bin/env bash
set -euo pipefail

# Install and enable a systemd service to run the Pika-pika app on boot.
# Must be run with sudo (or will invoke sudo where needed).

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_NAME="pika-pika.service"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"

RUN_USER="${SUDO_USER:-$(whoami)}"
RUN_GROUP="$(id -gn "$RUN_USER")"
VENV="$REPO_DIR/.venv"
UVICORN="$VENV/bin/uvicorn"

if [ ! -x "$UVICORN" ]; then
  echo "[pika-pika] Error: uvicorn not found at $UVICORN. Ensure you've run 'make install' or 'bash scripts/setup_pi.sh' first."
  exit 1
fi

echo "[pika-pika] Installing systemd service ($SERVICE_PATH) to run as user $RUN_USER"

sudo tee "$SERVICE_PATH" > /dev/null <<EOF
[Unit]
Description=Pika-pika voltage logger web app
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
User=$RUN_USER
Group=$RUN_GROUP
WorkingDirectory=$REPO_DIR
ExecStart=$UVICORN pika.app:app --host 0.0.0.0 --port 8000 --workers 1
Restart=always
RestartSec=5
WatchdogSec=30
Environment=PIKA_DATA_DIR=$REPO_DIR/data
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"

echo "[pika-pika] Service installed and started. Check status with: sudo systemctl status $SERVICE_NAME"
