# PRU Datalogger Hardware & Debugging Notes

This document captures the specific hardware configuration, quirks, and workarounds required to run the `ad7606_sampler` firmware on the BeagleBone Black.

## Hardware Configuration (Verified Working)

### AD7606 Pin Settings
*   **RST (Reset)**: **GND** (Active High Reset). Connecting to 3.3V holds the chip in reset and fails operation.
*   **STBY (Standby)**: **3.3V** (Active Low Standby).
*   **RANGE**: **GND** (+/- 5V input range) or **3.3V** (+/- 10V input range).
*   **CONVST A / B**: Tied together and connected to **P9.27**.
*   **BUSY**: Connected to **P8.15**. (Note: Signal is unreliable on current hardware, see workaround).
*   **OS0/OS1/OS2**: Tied to **GND** (No oversampling).

### PRU Pin Mapping
| Signal | BBB Pin | PRU Register | Direction |
| :--- | :--- | :--- | :--- |
| CONVST | P9.27 | R30.5 | Output |
| BUSY | P8.15 | R31.15 | Input |
| DATA[0-7] | P8.16... | R31[14-...] | Input |

## Software Workarounds

### 1. BUSY Signal Bypass (Fixed Delay)
The hardware BUSY signal (P8.15) was found to be unresponsive (always low) during debugging. 
To resolve this, the firmware uses a **deterministic fixed delay** instead of polling the BUSY pin.

*   **File**: `pru/include/adc_parallel.h`
*   **Logic**: `adc_trigger_and_wait()` asserts CONVST, then waits **5µs** (1000 cycles).
*   **Rationale**: The AD7606 conversion time is fixed at ~4µs (datasheet). A 5µs wait guarantees data is ready without relying on the physical BUSY handshake.
*   **Result**: 100% reliable sampling at high speeds.

### 2. PRU Stack Overflow Prevention
The PRU has limited local memory (8KB for stack + data).
*   **Issue**: Allocating `uint16_t local_buffer[32][8]` (512 bytes) on the stack caused silent stack overflows and PRU crashes.
*   **Fix**: The buffer is declared `static` in `pru_main.c` to place it in the `.bss` (data) segment instead of the stack.
*   **Rule**: Never allocate large arrays on the stack in PRU firmware.

## Debugging History

*   **Symptoms**: PRU halting immediately, PRU resetting repeatedly, random data.
*   **Root Causes Found**:
    1.  **RST Pin**: Initially connected to 3.3V (holding reset). Moved to GND.
    2.  **Stack Overflow**: `local_buffer` too large for stack. Moved to static.
    3.  **Compiler Syntax**: TI `clpru` requires specific register access syntax.
    4.  **Hardware Failure**: BUSY pin not toggling. Bypassed with fixed delay.
