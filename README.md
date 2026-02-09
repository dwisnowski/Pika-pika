# Pika - BeagleBone Black Data Acquisition System

High-performance data acquisition system for BeagleBone Black using PRU firmware to interface with an AD7606 8-channel ADC.

## Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd Pika-pika

# Build PRU firmware
cd pika
make pru

# Run tests
make test-pru

# See getting started guide for hardware setup
cat docs/getting-started.md
```

## Project Structure

- `pika/` - Main project code
  - `pru/` - PRU firmware for real-time ADC sampling
  - `datalogger/` - Data logging application (planned)
  - `webapp/` - Web interface (planned)
  - `overlays/` - Device tree overlays
- `docs/` - Documentation
- `bbb-plan/` - Development planning documents

## Documentation

- [Getting Started](docs/getting-started.md) - Hardware setup and deployment guide
- [Architecture](docs/architecture.md) - System design and data flow
- [Memory Map](docs/memory-map.md) - PRU shared memory layout
- [PRU README](pika/pru/README.md) - PRU firmware details

## Current Status

✅ PRU firmware implementation complete with comprehensive test suite
🚧 Data logger - planned
🚧 Web application - planned

## License

[License information to be added]
