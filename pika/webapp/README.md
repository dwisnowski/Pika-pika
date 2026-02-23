# Pika Web Application

A modern, Material Design 3 dashboard for the Pika Power Monitor.

## Installation on BeagleBone Black

Since the BBB uses an ARMv7 architecture, follow these steps to install `uv` and set up the environment:

### 1. Install `uv`
Run the standalone installer script:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Update Path
Reload your shell or source your profile:
```bash
source $HOME/.cargo/env
```
*(Verify with `uv --version`)*

### 3. Setup Project
Navigate to the webapp directory and sync dependencies:
```bash
cd pika/pika/webapp
uv sync
```

## Running the Application

Use the provided Makefile:
```bash
make run
```
Or run directly:
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Architecture

```text
[PRU 180kHz] -> [SHM] -> [PYTHON SERVICE] -> [WEBSOCKET] -> [BROWSER CANVAS]
                                   |
[DISK LOGS] ----> [PARSERS] ----> [REST API] -------------> [CHART.JS]
```
