# PRU Firmware Build System

## Overview

This document describes the build system for the PRU firmware that performs deterministic data acquisition from an AD7606 ADC on the BeagleBone Black.

**Requirements Implemented:** 9.1, 9.2, 9.3, 9.4, 9.5, 9.6

## Prerequisites

### Required Tools

1. **TI PRU C Compiler (clpru)**
   - Part of the TI PRU Code Generation Tools
   - Typically installed at `/usr/share/ti/cgt-pru`

2. **PRU Software Support Package**
   - Contains headers and libraries for PRU development
   - Typically installed at `/usr/lib/ti/pru-software-support-package`

3. **Device Tree Compiler (dtc)**
   - For compiling device tree overlays
   - Usually available via package manager: `apt-get install device-tree-compiler`

### Installation on BeagleBone Black

```bash
# Install PRU development tools
sudo apt-get update
sudo apt-get install ti-pru-cgt-installer
sudo apt-get install am335x-pru-package

# Install device tree compiler
sudo apt-get install device-tree-compiler
```

## Build Targets

### Main Targets

| Target | Description | Requirement |
|--------|-------------|-------------|
| `build` | Compile main sampling firmware to `firmware/ad7606_sampler.out` | 9.1 |
| `bringup` | Compile bringup test firmware to `firmware/bringup_test.out` | 9.2 |
| `load` | Load main firmware to PRU0 using remoteproc | 9.3 |
| `load-bringup` | Load bringup firmware to PRU0 using remoteproc | 9.3 |
| `clean` | Remove all build artifacts | 9.4 |
| `overlay` | Compile device tree overlay | - |
| `install-overlay` | Install device tree overlay to `/lib/firmware` | - |
| `stop` | Stop PRU0 | - |
| `help` | Display help message | - |

### Usage Examples

```bash
# Build main sampling firmware
make build

# Build bringup test firmware
make bringup

# Build both firmwares
make build bringup

# Load main firmware to PRU0
make load

# Load bringup firmware for hardware testing
make load-bringup

# Stop PRU0
make stop

# Clean all build artifacts
make clean

# Compile and install device tree overlay
make overlay
make install-overlay
```

## Directory Structure

```
pika/pru/
├── Makefile                    # Build system
├── include/                    # Header files
│   ├── shm_layout.h           # Shared memory interface
│   ├── pru_config.h           # Configuration constants
│   ├── timing.h               # Timing primitives
│   └── adc_parallel.h         # ADC interface
├── src/                        # Source files
│   ├── pru_main.c             # Main sampling firmware
│   ├── pru_bringup.c          # Bringup test firmware
│   ├── timing.c               # Timing implementation
│   └── adc_parallel.c         # ADC interface implementation
├── firmware/                   # Output directory (Requirement 9.5)
│   ├── ad7606_sampler.out     # Main firmware binary
│   └── bringup_test.out       # Bringup firmware binary
├── build/                      # Intermediate build files
│   ├── *.obj                  # Object files
│   ├── *.pp                   # Preprocessed files
│   └── *.asm                  # Assembly files
└── BB-PRU0-AD7606.dts         # Device tree overlay source
```

## Compiler Configuration

### Compiler Flags (Requirement 9.6)

The build system uses the following compiler flags:

- `-v3` - Target PRU version 3 (AM335x)
- `-O2` - Optimization level 2 for performance
- `--endian=little` - Little-endian byte order
- `--hardware_mac=on` - Enable hardware multiply-accumulate
- `--display_error_number` - Show error numbers for debugging
- No floating-point support (PRU has no FPU)

### Include Paths

The compiler searches for headers in:
- `include/` - Project headers
- `$(PRU_CGT)/include` - PRU compiler headers
- `$(PRU_SSP)/include` - PRU support package headers
- `$(PRU_SSP)/include/am335x` - AM335x-specific headers

## Customization

### Custom Tool Paths

If your PRU tools are installed in non-standard locations, you can override the paths:

```bash
# Build with custom PRU Software Support Package path
make PRU_SSP=/path/to/pru-ssp build

# Build with custom PRU Code Generation Tools path
make PRU_CGT=/path/to/cgt-pru build

# Build with both custom paths
make PRU_SSP=/path/to/pru-ssp PRU_CGT=/path/to/cgt-pru build
```

### Environment Variables

You can also set these as environment variables:

```bash
export PRU_SSP=/path/to/pru-ssp
export PRU_CGT=/path/to/cgt-pru
make build
```

## Loading Firmware

### Using remoteproc (Requirement 9.3)

The build system uses the Linux remoteproc framework to load firmware:

1. **Stop PRU0:**
   ```bash
   sudo sh -c "echo 'stop' > /sys/class/remoteproc/remoteproc1/state"
   ```

2. **Copy firmware:**
   ```bash
   sudo cp firmware/ad7606_sampler.out /lib/firmware/am335x-pru0-fw
   ```

3. **Start PRU0:**
   ```bash
   sudo sh -c "echo 'start' > /sys/class/remoteproc/remoteproc1/state"
   ```

The `make load` target automates these steps.

### Verifying PRU Status

```bash
# Check PRU0 state
cat /sys/class/remoteproc/remoteproc1/state

# Check loaded firmware
cat /sys/class/remoteproc/remoteproc1/firmware

# View PRU kernel messages
dmesg | grep pru
```

## Troubleshooting

### PRU remoteproc not found

**Error:** `Error: PRU remoteproc not found. Is PRU enabled in device tree?`

**Solution:** Ensure the PRU device tree overlay is loaded:
```bash
# Check if PRU is enabled
ls /sys/class/remoteproc/

# Load PRU device tree overlay
sudo sh -c "echo 'BB-PRU0-AD7606' > /sys/devices/platform/bone_capemgr/slots"
```

### Compiler not found

**Error:** `clpru: command not found`

**Solution:** Install the TI PRU Code Generation Tools:
```bash
sudo apt-get install ti-pru-cgt-installer
```

### Missing headers

**Error:** `fatal error: pru_cfg.h: No such file or directory`

**Solution:** Install the PRU Software Support Package:
```bash
sudo apt-get install am335x-pru-package
```

### Permission denied when loading firmware

**Error:** `Permission denied` when running `make load`

**Solution:** The load target requires sudo access. Ensure you have sudo privileges or run:
```bash
sudo make load
```

## Build Artifacts (Requirement 9.4)

The `make clean` target removes:
- `build/` directory and all intermediate files (*.obj, *.pp, *.asm)
- `firmware/*.out` firmware binaries
- `*.dtbo` compiled device tree overlays

## Testing the Build System

### 1. Build Test

```bash
# Clean and rebuild
make clean
make build bringup

# Verify outputs exist
ls -lh firmware/
# Should show:
#   ad7606_sampler.out
#   bringup_test.out
```

### 2. Bringup Test

```bash
# Load bringup firmware
make load-bringup

# Verify PRU is running
cat /sys/class/remoteproc/remoteproc1/state
# Should show: running

# Use logic analyzer or oscilloscope to verify:
# - 1 kHz square wave on CONVST pin (P9.31)
# - Confirms PRU clock, pin configuration, and basic operation
```

### 3. Main Firmware Test

```bash
# Load main firmware
make load

# Verify PRU is running
cat /sys/class/remoteproc/remoteproc1/state
# Should show: running

# Check shared memory for data (requires userspace application)
```

## Integration with Testing

The build system integrates with the test infrastructure:

```bash
# Build firmware for testing
make build

# Run unit tests (when test infrastructure is complete)
make test-unit

# Run property-based tests (when test infrastructure is complete)
make test-property

# Run all tests
make test
```

## References

- **TI PRU C Compiler User's Guide:** Documentation for clpru compiler
- **AM335x PRU-ICSS Reference Guide:** Hardware reference for PRU subsystem
- **PRU Software Support Package:** Examples and libraries for PRU development
- **Linux remoteproc Documentation:** Kernel framework for loading PRU firmware

## Summary

This build system provides:
- ✅ **Requirement 9.1:** `build` target compiles main sampling firmware
- ✅ **Requirement 9.2:** `bringup` target compiles test firmware
- ✅ **Requirement 9.3:** `load` target loads firmware to PRU0 via remoteproc
- ✅ **Requirement 9.4:** `clean` target removes build artifacts
- ✅ **Requirement 9.5:** Firmware outputs to `firmware/` directory
- ✅ **Requirement 9.6:** Uses TI PRU compiler toolchain (clpru) with appropriate flags (-O2, no floating point)

The build system is ready for use on the BeagleBone Black with the TI PRU development tools installed.
