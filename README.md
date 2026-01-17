# Pika-pika

[![MkDocs Deploy](https://github.com/dwisnowski/Pika-pika/actions/workflows/mkdocs-deploy.yml/badge.svg)](https://github.com/dwisnowski/Pika-pika/actions/workflows/mkdocs-deploy.yml)
[![GitHub Pages](https://img.shields.io/website?down_color=red&down_message=down&up_color=blue&up_message=up&url=https://dwisnowski.github.io/Pika-pika/)](https://dwisnowski.github.io/Pika-pika/)

![Pika-pika logo](pika/static/Pika-pika.png)

A **Python-based** Raspberry Pi voltage logger and live web viewer.

## Overview

Pika-pika allows you to sample voltage at 100 Hz, log data to disk, and view live results via a web interface—all running on a Raspberry Pi 2 or newer.

## Full Documentation

For detailed setup, hardware wiring, and contribution guides, visit our documentation site:

👉 **[https://dwisnowski.github.io/Pika-pika/](https://dwisnowski.github.io/Pika-pika/)**

## Quick Start (Hardware required)

```bash
git clone https://github.com/dwisnowski/Pika-pika.git
cd Pika-pika
bash scripts/setup_pi.sh  # Follow the interactive setup
```

## Quick Start (Demo mode - No hardware)

```bash
make sync
make dev
# Open http://localhost:8000/demo
```

## Contributing

Contributions are welcome! Please see the [Contributing Guide](https://dwisnowski.github.io/Pika-pika/contributing/) for more details.
