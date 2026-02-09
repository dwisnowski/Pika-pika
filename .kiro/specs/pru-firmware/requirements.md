# Requirements Document: PRU Firmware

## Introduction

This document specifies the requirements for PRU (Programmable Real-time Unit) firmware that performs deterministic data acquisition from an AD7606 ADC on the BeagleBone Black. The PRU provides hard real-time sampling capabilities with cycle-accurate timing, communicating with Linux userspace through a shared memory interface.

## Glossary

- **PRU**: Programmable Real-time Unit - a deterministic 32-bit RISC processor on the AM335x SoC
- **AD7606**: 16-bit, 8-channel simultaneous sampling ADC with parallel interface
- **Shared_Memory**: Memory region accessible by both PRU and Linux userspace for configuration and data transfer
- **Ring_Buffer**: Circular buffer structure for continuous data streaming
- **Block**: Fixed-size unit of ADC samples (e.g., 256 samples per channel)
- **CONVST**: Convert Start signal - triggers ADC conversion
- **BUSY**: ADC status signal indicating conversion in progress
- **Cycle_Counter**: PRU hardware counter for precise timing measurements
- **Magic_Number**: Fixed value used to verify shared memory initialization
- **Device_Tree_Overlay**: Configuration file that defines hardware pin assignments
- **Hot_Loop**: Performance-critical code path executed repeatedly during sampling

## Requirements

### Requirement 1: Shared Memory Interface

**User Story:** As a Linux userspace application, I want to communicate with the PRU through shared memory, so that I can configure sampling parameters and receive ADC data efficiently.

#### Acceptance Criteria

1. THE Shared_Memory SHALL contain a Magic_Number field at offset 0 for initialization verification
2. THE Shared_Memory SHALL contain a version field for compatibility checking
3. THE Shared_Memory SHALL contain configuration fields including sample_period_cycles, channel_mask, and block_size
4. THE Shared_Memory SHALL contain a Ring_Buffer with block descriptors
5. THE Shared_Memory SHALL contain volatile status fields including write_block_idx and error_flags
6. WHEN Linux writes configuration fields, THE PRU SHALL read them before starting sampling
7. WHEN the PRU completes a block, THE PRU SHALL update write_block_idx atomically

### Requirement 2: PRU Configuration Constants

**User Story:** As a firmware developer, I want well-defined configuration constants, so that timing and hardware parameters are clearly documented and maintainable.

#### Acceptance Criteria

1. THE PRU_Config SHALL define the PRU clock frequency constant (200 MHz)
2. THE PRU_Config SHALL define minimum and maximum sample period limits in cycles
3. THE PRU_Config SHALL define the number of ADC channels (8)
4. THE PRU_Config SHALL define error flag bit definitions
5. THE PRU_Config SHALL define block size constraints (power of 2, reasonable limits)

### Requirement 3: Cycle-Accurate Timing

**User Story:** As a data acquisition system, I want deterministic timing with cycle-level accuracy, so that samples are acquired at precise intervals.

#### Acceptance Criteria

1. THE Timing_System SHALL provide a function to read the current cycle counter value
2. THE Timing_System SHALL provide a function to wait for a specified number of cycles
3. WHEN waiting for N cycles, THE Timing_System SHALL busy-wait using cycle counter comparison
4. THE Timing_System SHALL NOT use floating-point arithmetic in timing calculations
5. THE Timing_System SHALL NOT use division operations in the Hot_Loop

### Requirement 4: AD7606 Parallel Interface Control

**User Story:** As PRU firmware, I want to control the AD7606 through its parallel interface, so that I can trigger conversions and read sample data.

#### Acceptance Criteria

1. THE ADC_Interface SHALL provide a function to assert the CONVST signal
2. THE ADC_Interface SHALL provide a function to deassert the CONVST signal
3. THE ADC_Interface SHALL provide a function to read the BUSY signal state
4. THE ADC_Interface SHALL provide a function to read 16-bit parallel data from a specified channel
5. WHEN reading parallel data, THE ADC_Interface SHALL use PRU R31 register for input
6. WHEN controlling CONVST, THE ADC_Interface SHALL use PRU R30 register for output
7. THE ADC_Interface SHALL implement all interface functions as inline functions for performance

### Requirement 5: Main Sampling Loop

**User Story:** As PRU firmware, I want to continuously sample ADC channels at precise intervals, so that I can provide deterministic data acquisition.

#### Acceptance Criteria

1. WHEN starting, THE PRU SHALL read configuration from Shared_Memory
2. WHEN starting, THE PRU SHALL verify the Magic_Number matches the expected value
3. WHEN sampling, THE PRU SHALL assert CONVST to trigger ADC conversion
4. WHEN sampling, THE PRU SHALL wait for BUSY signal to deassert before reading data
5. WHEN sampling, THE PRU SHALL read only channels enabled in channel_mask
6. WHEN sampling, THE PRU SHALL write samples to the current Ring_Buffer block
7. WHEN a block is full, THE PRU SHALL increment write_block_idx atomically
8. WHEN a block is full, THE PRU SHALL move to the next Ring_Buffer block
9. WHEN the Ring_Buffer wraps, THE PRU SHALL continue from block 0
10. THE PRU SHALL maintain cycle-accurate timing between samples using sample_period_cycles
11. THE PRU SHALL NOT use printf, malloc, or division in the Hot_Loop

### Requirement 6: Error Handling

**User Story:** As a data acquisition system, I want the PRU to detect and report errors, so that the Linux application can respond appropriately.

#### Acceptance Criteria

1. WHEN the Magic_Number is invalid, THE PRU SHALL set an error flag and halt
2. WHEN the BUSY signal times out, THE PRU SHALL set an error flag in Shared_Memory
3. WHEN an invalid configuration is detected, THE PRU SHALL set an error flag and halt
4. THE PRU SHALL write error_flags to Shared_Memory before halting

### Requirement 7: Bring-up Test Firmware

**User Story:** As a hardware developer, I want minimal test firmware for hardware validation, so that I can verify PRU operation and pin connectivity before running complex sampling code.

#### Acceptance Criteria

1. THE Bringup_Firmware SHALL toggle GPIO pins at a known frequency
2. THE Bringup_Firmware SHALL NOT depend on Shared_Memory initialization
3. THE Bringup_Firmware SHALL use simple cycle-based delays
4. THE Bringup_Firmware SHALL be buildable as a separate firmware binary

### Requirement 8: Device Tree Configuration

**User Story:** As a system integrator, I want a device tree overlay that configures PRU pins, so that the hardware interface is properly initialized at boot.

#### Acceptance Criteria

1. THE Device_Tree_Overlay SHALL disable HDMI to free pins for PRU use
2. THE Device_Tree_Overlay SHALL configure PRU0 R30 pins as outputs
3. THE Device_Tree_Overlay SHALL configure PRU0 R31 pins as inputs
4. THE Device_Tree_Overlay SHALL document the mapping between PRU pins and AD7606 signals
5. THE Device_Tree_Overlay SHALL include pin assignments for CONVST, BUSY, and 16 data lines

### Requirement 9: Build System

**User Story:** As a developer, I want a Makefile that builds and deploys PRU firmware, so that I can easily compile and load firmware onto the PRU.

#### Acceptance Criteria

1. THE Makefile SHALL provide a 'build' target that compiles the main sampling firmware
2. THE Makefile SHALL provide a 'bringup' target that compiles the test firmware
3. THE Makefile SHALL provide a 'load' target that loads firmware to PRU0
4. THE Makefile SHALL provide a 'clean' target that removes build artifacts
5. THE Makefile SHALL output firmware binaries to the firmware/ directory
6. THE Makefile SHALL use the TI PRU compiler toolchain

### Requirement 10: Timing Validation

**User Story:** As a system validator, I want to verify timing accuracy with external tools, so that I can confirm the PRU meets deterministic sampling requirements.

#### Acceptance Criteria

1. THE PRU SHALL generate signals observable on logic analyzer for timing verification
2. WHEN sampling at configured rate, THE PRU SHALL maintain timing accuracy within ±1 cycle
3. THE PRU SHALL provide CONVST signal timing suitable for logic analyzer measurement
