# Pika - Data Acquisition System

High-performance data acquisition for BeagleBone Black using PRU firmware to interface with an AD7606 8-channel ADC.

## Features

- **PRU-based ADC Interface**: Deterministic sampling with microsecond-level timing precision
- **Shared Memory Communication**: Efficient data transfer between PRU and Linux userspace
- **Modular Design**: Separate firmware, data processing, and presentation layers
- **Device Tree Integration**: Flexible hardware configuration via overlays

## Directory Structure

```
pika/
├── Makefile                # Top-level build orchestrator
├── pru/                    # PRU firmware (✅ complete)
│   ├── src/                # PRU C source code
│   ├── include/            # Header files
│   ├── tests/              # Unit and property tests
│   └── firmware/           # Compiled binaries
├── datalogger/             # Data logger (🚧 planned)
├── webapp/                 # Web application (🚧 planned)
└── overlays/               # Device tree overlays
    └── ad7606-pru0.dts     # PRU0 pin configuration
```

## Quick Start

```bash
# Build PRU firmware
make pru

# Run tests
make test-pru

# Load to BeagleBone Black
make pru-load

# See all targets
make help
```

For detailed setup instructions, see [Getting Started Guide](../docs/getting-started.md).

## Build Targets

Common targets:
- `make pru` - Build PRU firmware
- `make pru-bringup` - Build bringup test firmware
- `make test-pru` - Run all PRU tests
- `make pru-load` - Load firmware to BBB
- `make pru-overlay` - Build and install device tree overlay
- `make help` - Show all available targets

## Documentation

- [Getting Started](../docs/getting-started.md) - Hardware setup and deployment
- [Architecture](../docs/architecture.md) - System design
- [Memory Map](../docs/memory-map.md) - PRU shared memory layout
- [PRU Firmware](pru/README.md) - PRU implementation details

## Current Status

✅ **PRU Firmware** - Complete with comprehensive test suite
- AD7606 parallel interface implementation
- Deterministic timing control
- Circular buffer management
- Unit and property-based tests

🚧 **Data Logger** - Planned
- Memory-mapped access to PRU buffers
- Data processing pipeline
- Time-series storage

🚧 **Web Application** - Planned
- Real-time monitoring
- Historical data visualization
- System control interface
