# System Architecture

## Overview

This document will describe the detailed system architecture for the BeagleBone Black data acquisition system.

## Components

### PRU Firmware

The PRU (Programmable Real-time Unit) firmware provides deterministic, cycle-accurate data acquisition from an AD7606 ADC on the BeagleBone Black. The PRU is a 200 MHz deterministic processor on the AM335x SoC that operates independently of the Linux kernel, providing guaranteed hard real-time performance.

#### Overview

**Key Capabilities:**
- **Cycle-accurate timing**: Sample intervals precise to ±1 cycle (5 ns @ 200 MHz)
- **Deterministic execution**: No OS interference, guaranteed timing
- **Zero-copy data transfer**: Direct memory access to shared memory
- **Parallel ADC interface**: 16-bit parallel data bus with hardware control signals
- **Ring buffer streaming**: Continuous data acquisition without loss

**Performance Specifications:**
- PRU clock: 200 MHz (5 ns per cycle)
- Timing accuracy: ±5 ns per sample
- Maximum sample rate: 100 kHz (limited by ADC conversion time)
- Jitter: <10 ns (deterministic)
- Data throughput: Up to 1.6 MB/s (100 kHz × 8 channels × 2 bytes)

#### Architecture

The firmware consists of several key components:

**1. Shared Memory Interface**
- Contract between PRU and Linux userspace
- Configuration: Sample rate, channel mask, block size
- Status: Current block index, error flags, sample count
- Ring buffer: Multiple blocks with descriptors and data
- Magic number validation for initialization safety

**2. Timing System**
- Cycle counter access via PRU CTRL registers
- Cycle-accurate busy-wait implementation
- 32-bit counter wrap-around handling
- No division or floating-point operations
- All timing functions are inline for zero overhead

**3. ADC Parallel Interface**
- Direct control of CONVST (convert start) signal
- BUSY signal monitoring for conversion completion
- 16-bit parallel data bus reading (D0-D15)
- Timeout detection for hardware failures
- Meets AD7606 timing requirements (>25 ns CONVST pulse)

**4. Main Sampling Loop**
- Initialization with fail-fast validation
- Cycle-accurate sample scheduling
- ADC trigger and data acquisition
- Ring buffer management with automatic wrapping
- Atomic block completion signaling
- Comprehensive error detection and reporting

**5. Bring-up Test Firmware**
- Minimal firmware for hardware validation
- Simple GPIO toggle at 1 kHz
- No shared memory dependencies
- Verifies PRU clock, pin configuration, and basic operation

#### Data Flow

```
Linux Userspace
    ↓ (mmap, write config)
Shared Memory
    ↑ (direct access, read config)
PRU Firmware
    ↓ (R30 outputs: CONVST)
    ↑ (R31 inputs: BUSY, D0-D15)
AD7606 ADC
```

**Sampling Sequence:**
1. PRU reads configuration from shared memory (sample rate, channels)
2. PRU waits for precise sample time using cycle counter
3. PRU asserts CONVST signal to trigger ADC conversion
4. PRU monitors BUSY signal until conversion completes (~4 µs)
5. PRU reads 16-bit parallel data for each enabled channel
6. PRU writes samples directly to ring buffer in shared memory
7. PRU updates block index when block is complete
8. Linux userspace reads completed blocks asynchronously

#### Ring Buffer Design

The ring buffer enables continuous streaming without data loss:

- **Structure**: Fixed number of blocks (typically 4)
- **Block size**: Configurable samples per block (typically 256)
- **Data layout**: Interleaved by channel within each block
- **Descriptors**: Each block has timestamp, sample count, flags
- **Wrapping**: Automatic wrap-around when reaching last block
- **Synchronization**: Atomic write_block_idx updates

**Memory Layout:**
```
[Header: magic, version, config, status]
[Block 0: descriptor + data]
[Block 1: descriptor + data]
[Block 2: descriptor + data]
[Block 3: descriptor + data]
```

#### Error Handling

The firmware uses fail-fast error handling with comprehensive detection:

**Error Types:**
- **Invalid Magic**: Shared memory not properly initialized
- **BUSY Timeout**: ADC hardware failure or timing issue
- **Invalid Config**: Sample rate out of range or bad parameters
- **Buffer Overrun**: Linux not consuming data fast enough (future)

**Error Response:**
- Set appropriate error flag in shared memory
- Halt PRU execution immediately
- Linux must reset and restart PRU to recover

This approach ensures corrupted state never propagates and gives userspace full control over recovery.

#### Hardware Validation

The firmware includes a comprehensive 7-phase validation procedure:

1. **Device Tree Configuration**: Pin multiplexing setup
2. **Bringup Test**: Verify PRU operation without ADC (1 kHz square wave)
3. **ADC Interface Validation**: Verify timing with logic analyzer
4. **Data Acquisition Validation**: Verify correct data transfer
5. **Timing Accuracy Validation**: Long-term precision testing
6. **Stress Testing**: High sample rates, extended operation
7. **Error Condition Testing**: Verify error detection works

#### Testing

**Unit Tests** (361 assertions):
- Shared memory layout and structure alignment
- Configuration constants and calculations
- Timing functions with wrap-around handling
- ADC interface control signals
- Configuration validation logic
- Bringup firmware behavior
- Device tree overlay structure

**Property-Based Tests** (8 properties, 462 iterations):
1. Cycle-accurate wait timing
2. Block completion signaling
3. Magic number validation
4. Sampling sequence correctness
5. Ring buffer wrapping
6. Sample timing accuracy
7. Error handling completeness
8. Channel mask filtering

All tests pass with >90% line coverage and >85% branch coverage.

#### Build System

The firmware uses TI PRU Code Generation Tools (clpru compiler):

**Build Targets:**
- `make build` - Compile main sampling firmware
- `make bringup` - Compile bringup test firmware
- `make load` - Load firmware to PRU0 via remoteproc
- `make test` - Run all unit and property tests
- `make clean` - Remove build artifacts

**Requirements:**
- TI PRU C Compiler (clpru)
- PRU Software Support Package
- Device Tree Compiler (dtc)
- BeagleBone Black with PRU remoteproc driver

#### Pin Mapping

**Control Signals:**
- CONVST (P9.31): PRU0 R30.0 output - Triggers ADC conversion
- BUSY (P9.29): PRU0 R31.0 input - Indicates conversion in progress

**16-bit Parallel Data Bus:**
- D0-D15: PRU0 R31.1-16 inputs - ADC data lines
- Mapped to various P8 and P9 header pins

The device tree overlay configures all pin multiplexing and disables HDMI to free up required pins.

#### Documentation

Detailed documentation available in `docs/pru/`:
- [Build System](pru/build-system.md) - Compilation and deployment
- [Device Tree Overlay](pru/device-tree-overlay.md) - Pin configuration
- [Test Infrastructure](pru/test-infrastructure.md) - Testing approach
- [Bringup Implementation](pru/bringup-implementation.md) - Hardware validation
- [Final Checkpoint](pru/final-checkpoint.md) - Implementation status

See also: `pika/pru/README.md` for complete hardware validation procedures.

### Data Logger
- TODO: Document Linux userspace application architecture
- TODO: Describe data logging mechanisms
- TODO: Document anomaly detection algorithms

### Web Application
- TODO: Document FastAPI web application architecture
- TODO: Describe visualization components
- TODO: Document API endpoints

## Communication Mechanisms

### PRU to Linux Communication
- TODO: Document shared memory interface
- TODO: Describe interrupt mechanisms
- TODO: Document data transfer protocols

### Data Flow
- TODO: Document data flow from ADC through PRU to Linux
- TODO: Describe data processing pipeline
- TODO: Document storage and visualization flow

## Hardware Configuration

- TODO: Document BeagleBone Black pin assignments
- TODO: Describe AD7606 connections
- TODO: Document device tree overlay configuration

## Future Considerations

- TODO: Document scalability considerations
- TODO: Describe performance optimization strategies
- TODO: Document testing and validation approaches
