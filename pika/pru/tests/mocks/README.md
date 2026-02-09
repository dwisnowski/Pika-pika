# PRU Hardware Mocks

This directory contains mock implementations of PRU hardware components for host-based testing.

## Overview

The PRU firmware relies on hardware-specific features that are not available on standard x86/ARM Linux systems:
- **R30/R31 Registers**: Special PRU GPIO registers for direct pin control
- **Cycle Counter**: Hardware counter running at 200 MHz for precise timing

These mocks allow unit tests and property-based tests to run on the host system without requiring actual PRU hardware.

## Components

### pru_registers.c/h
Mock implementations of PRU R30 (output) and R31 (input) registers.

**Features:**
- Simulates 32-bit GPIO registers
- Provides functions to set/clear individual bits
- Allows tests to verify output pin states
- Allows tests to simulate input pin changes

**Usage Example:**
```c
#include "mocks/pru_registers.h"

// Reset registers before test
mock_pru_registers_reset();

// Simulate BUSY pin going high
mock_pru_r31_set_bit(PIN_BUSY);

// Check if CONVST output is set
if (mock_pru_r30_is_bit_set(PIN_CONVST)) {
    // CONVST was asserted
}
```

### cycle_counter.c/h
Mock implementation of the PRU cycle counter.

**Features:**
- Simulates 32-bit counter with wrap-around
- Manual advancement for deterministic testing
- Auto-advance mode for simulating time passage
- Supports testing wrap-around edge cases

**Usage Example:**
```c
#include "mocks/cycle_counter.h"

// Reset counter before test
mock_cycle_counter_reset();

// Set counter to specific value (e.g., near wrap-around)
mock_cycle_counter_set(0xFFFFFFF0);

// Advance counter by N cycles
mock_cycle_counter_advance(100);

// Enable auto-advance (counter increments on each read)
mock_cycle_counter_enable_auto_advance(1);
```

## Building

Build the mock library:
```bash
cd pika/pru/tests/mocks
make
```

This creates `libpru_mocks.a` which can be linked with test executables.

## Integration with Tests

Tests can include the mock headers and link against the mock library:

```makefile
CFLAGS = -I../../tests/mocks
LDFLAGS = -L../../tests/mocks -lpru_mocks

test_example: test_example.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)
```

## Design Notes

- Mocks are designed to be simple and transparent
- No complex simulation - just enough to verify firmware logic
- Tests should reset mocks at the beginning of each test case
- Mocks do not simulate timing delays (tests control time explicitly)
- Thread-safe operation is not required (tests are single-threaded)

## Limitations

These mocks do not simulate:
- Actual timing delays (tests advance time manually)
- Hardware timing constraints (e.g., setup/hold times)
- Electrical characteristics (voltage levels, drive strength)
- Concurrent PRU execution (tests are sequential)

For hardware validation, use actual PRU hardware with logic analyzer verification.
