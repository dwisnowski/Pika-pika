# Pika-pika

[![MkDocs Deploy](https://github.com/dwisnowski/Pika-pika/actions/workflows/mkdocs-deploy.yml/badge.svg)](https://github.com/dwisnowski/Pika-pika/actions/workflows/mkdocs-deploy.yml)
[![GitHub Pages](https://img.shields.io/website?down_color=red&down_message=down&up_color=blue&up_message=up&url=https://dwisnowski.github.io/Pika-pika/)](https://dwisnowski.github.io/Pika-pika/)

![Pika-pika logo](pika/static/Pika-pika.png)

A **Python-based** Raspberry Pi voltage logger and live web viewer.

## Overview

Pika-pika allows you to sample voltage at 100 Hz, log data to disk, and view live results via a web interface—all running on a Raspberry Pi 2 or newer.

## Architecture

Pika-pika uses a multiprocessing architecture that distributes work across CPU cores for optimal performance:

1. **Sampling Process** - Core 1: Reads SPI data from ADC, processes voltage measurements
2. **Event Logger Process** - Core 2: Writes CSV files when significant events occur  
3. **FastAPI Process** - Core 3: Serves the web interface and REST APIs
4. **WebSocket Process** - Core 4: Streams live data to connected clients

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Core 1     │  │   Core 2     │  │   Core 3     │  │   Core 4     │
│              │  │              │  │              │  │              │
│  Sampling    │  │  Event       │  │  FastAPI     │  │  WebSocket   │
│  Process     │  │  Logger      │  │  Server      │  │  Handler     │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │                 │
       └─────────────────┴─────────────────┴─────────────────┘
                            │
                    ┌───────┴────────┐
                    │ Shared Memory  │
                    │ (multiprocessing)│
                    └────────────────┘
```

All processes communicate through shared memory buffers, ensuring efficient data flow without blocking operations. This design allows the system to maintain consistent sampling while simultaneously serving web requests and logging data.

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
