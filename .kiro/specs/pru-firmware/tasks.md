# Implementation Plan: PRU Firmware

## Overview

This plan implements deterministic PRU firmware for BeagleBone Black data acquisition from an AD7606 ADC. The implementation follows a bottom-up approach: starting with foundational components (shared memory layout, timing primitives), building up to hardware interfaces, then integrating into the main sampling loop. Testing is integrated throughout to catch errors early.

All files are located in the `pika/pru/` directory structure.

## Tasks

- [x] 1. Set up project structure and shared memory interface
  - Create directory structure: pika/pru/include/, pika/pru/src/, pika/pru/firmware/
  - Create pika/pru/include/shm_layout.h with shared memory structure definitions
  - Define pru_shared_memory_t with magic, version, configuration, and status fields
  - Define block_descriptor_t structure
  - Define constants: SHM_MAGIC, SHM_VERSION, error flags
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 1.1 Write unit tests for shared memory layout
  - Test magic number at offset 0
  - Test field accessibility and sizes
  - Test structure alignment
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2. Implement PRU configuration constants
  - Create pika/pru/include/pru_config.h
  - Define PRU_CLOCK_HZ (200 MHz) and timing constants
  - Define MIN/MAX_SAMPLE_PERIOD_CYCLES
  - Define AD7606 timing constants (CONVST_PULSE_CYCLES, BUSY_TIMEOUT_CYCLES)
  - Define pin assignments (PIN_CONVST, PIN_BUSY, PIN_DATA_BASE)
  - Define channel and block size constants
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 2.1 Write unit tests for configuration constants
  - Verify all constants are defined with correct values
  - Test timing constant calculations
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 3. Implement timing system
  - Create pika/pru/src/timing.c and pika/pru/include/timing.h
  - Implement get_cycle_count() using inline assembly to read CTRL.CYCLE register
  - Implement wait_cycles() with busy-wait and wrap-around handling
  - Implement elapsed_cycles() with wrap-around handling
  - Implement is_valid_sample_period() validation function
  - Mark all functions as static inline for zero overhead
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 3.1 Write unit tests for timing functions
  - Test get_cycle_count() returns incrementing values
  - Test elapsed_cycles() with normal and wrap-around cases
  - Test is_valid_sample_period() with valid and invalid inputs
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 3.2 Write property test for cycle-accurate timing
  - **Property 1: Cycle-accurate wait timing**
  - **Validates: Requirements 3.2**
  - Generate random cycle counts (100-10000 range)
  - Verify wait_cycles(N) takes N ± 1 cycles
  - Run 100 iterations minimum

- [x] 4. Implement ADC parallel interface
  - Create pika/pru/src/adc_parallel.c and pika/pru/include/adc_parallel.h
  - Define PRU0_R30 and PRU0_R31 register pointers
  - Implement adc_assert_convst() using R30 bit manipulation
  - Implement adc_deassert_convst() using R30 bit manipulation
  - Implement adc_read_busy() using R31 bit read
  - Implement adc_read_channel() using R31 parallel data read
  - Implement adc_trigger_and_wait() with BUSY timeout handling
  - Mark all functions as static inline
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [x] 4.1 Write unit tests for ADC interface
  - Test CONVST assert/deassert with mocked R30
  - Test BUSY read with mocked R31
  - Test channel read with mocked R31
  - Test trigger_and_wait timeout handling
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 4.2 Write property test for sampling sequence
  - **Property 4: Sampling sequence correctness**
  - **Validates: Requirements 5.3, 5.4, 5.5, 5.6**
  - Generate random channel masks
  - Verify CONVST assertion, BUSY wait, channel filtering, and data storage
  - Run 100 iterations minimum

- [x] 5. Checkpoint - Ensure foundational components are complete
  - Verify all timing and ADC interface functions compile
  - Ensure all tests pass, ask the user if questions arise

- [x] 6. Implement main sampling loop initialization
  - Create pika/pru/src/pru_main.c
  - Implement main() entry point
  - Map shared memory to PRU address space
  - Verify magic number and set ERROR_INVALID_MAGIC on failure
  - Read configuration fields (sample_period, channel_mask, block_size, num_blocks)
  - Validate configuration and set ERROR_INVALID_CONFIG on failure
  - Count enabled channels from channel_mask
  - Calculate block data size and total size
  - Initialize sampling state variables (current_block, sample_in_block, next_sample_time)
  - _Requirements: 5.1, 5.2, 6.1, 6.3_

- [x] 6.1 Write property test for magic number validation
  - **Property 3: Magic number validation**
  - **Validates: Requirements 5.2, 6.1**
  - Generate random invalid magic numbers
  - Verify PRU sets ERROR_INVALID_MAGIC and halts
  - Run 100 iterations minimum

- [x] 6.2 Write unit tests for configuration validation
  - Test valid configuration acceptance
  - Test invalid sample period rejection
  - Test zero channel mask rejection
  - Test invalid block size rejection
  - _Requirements: 5.1, 6.3_

- [x] 7. Implement main sampling loop body
  - Implement while(1) sampling loop in pika/pru/src/pru_main.c
  - Calculate wait time until next_sample_time with drift compensation
  - Call adc_trigger_and_wait() and handle timeout errors
  - Calculate pointers to current block descriptor and data buffer
  - Read enabled channels using channel_mask and store to ring buffer
  - Increment sample_in_block and sample_count
  - Check for block completion and finalize descriptor
  - Update write_block_idx atomically on block completion
  - Wrap to block 0 when reaching num_blocks
  - Schedule next sample by incrementing next_sample_time
  - _Requirements: 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 1.7_

- [x] 7.1 Write property test for block completion signaling
  - **Property 2: Block completion signaling**
  - **Validates: Requirements 1.7, 5.7**
  - Generate random block sequences
  - Verify write_block_idx is updated atomically after each block
  - Run 100 iterations minimum

- [x] 7.2 Write property test for ring buffer wrapping
  - **Property 5: Ring buffer wrapping**
  - **Validates: Requirements 5.8, 5.9**
  - Generate random block counts (2-16 range)
  - Verify wrapping from block (N-1) to block 0
  - Verify no data corruption during wrapping
  - Run 100 iterations minimum

- [x] 7.3 Write property test for sample timing accuracy
  - **Property 6: Sample timing accuracy**
  - **Validates: Requirements 5.10, 10.2**
  - Generate random sample periods (MIN to MAX range)
  - Verify interval between samples is period ± 1 cycle
  - Run 100 iterations minimum

- [x] 7.4 Write property test for channel mask filtering
  - **Property 8: Channel mask filtering**
  - **Validates: Requirements 5.5**
  - Generate random channel masks (1-255 range)
  - Verify number of samples equals number of bits set
  - Verify only enabled channels are read
  - Run 100 iterations minimum

- [x] 8. Implement error handling
  - Add error flag setting before all __halt() calls in pika/pru/src/pru_main.c
  - Ensure ERROR_INVALID_MAGIC is set for magic number mismatch
  - Ensure ERROR_BUSY_TIMEOUT is set for ADC timeout
  - Ensure ERROR_INVALID_CONFIG is set for configuration errors
  - Write error_flags to shared memory before halting
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 8.1 Write property test for error handling completeness
  - **Property 7: Error handling completeness**
  - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**
  - Generate random error conditions
  - Verify appropriate error flag is set before halt
  - Verify error_flags is written to shared memory
  - Run 100 iterations minimum

- [x] 9. Checkpoint - Ensure main firmware is complete
  - Verify pru_main.c compiles without errors
  - Ensure all tests pass, ask the user if questions arise

- [x] 10. Implement bring-up test firmware
  - Create pika/pru/src/pru_bringup.c
  - Implement main() that toggles CONVST pin at 1 kHz (200000 cycles)
  - Use simple wait_cycles() for delays
  - No shared memory dependencies
  - _Requirements: 7.1, 7.2, 7.3_

- [x] 10.1 Write unit test for bringup firmware
  - Verify GPIO toggle at known frequency
  - Test with mocked R30 register
  - _Requirements: 7.1_

- [x] 11. Create device tree overlay
  - Create pika/pru/BB-PRU0-AD7606.dts
  - Add fragment to disable HDMI (lcdc)
  - Add fragment for PRU pin multiplexing
  - Configure P9.31 as PRU0 R30.0 output (CONVST)
  - Configure P9.29 as PRU0 R31.0 input (BUSY)
  - Configure P9.27, P9.25, etc. as PRU0 R31.1-16 inputs (D0-D15)
  - Document pin-to-signal mapping in comments
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 11.1 Write unit test for device tree overlay
  - Verify HDMI is disabled
  - Verify all required pins are configured
  - Verify pin modes (input/output) are correct
  - _Requirements: 8.1, 8.2, 8.3, 8.5_

- [x] 12. Create build system
  - Create pika/pru/Makefile
  - Add 'build' target that compiles pru_main.c to firmware/ad7606_sampler.out
  - Add 'bringup' target that compiles pru_bringup.c to firmware/bringup_test.out
  - Add 'load' target that loads firmware to PRU0 using remoteproc
  - Add 'clean' target that removes build artifacts
  - Use TI PRU compiler toolchain (clpru)
  - Set appropriate compiler flags (-O2, no floating point)
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

- [x] 12.1 Write unit tests for build system
  - Test 'build' target produces ad7606_sampler.out
  - Test 'bringup' target produces bringup_test.out
  - Test 'clean' target removes artifacts
  - Test firmware outputs are in firmware/ directory
  - _Requirements: 9.1, 9.2, 9.4, 9.5_

- [x] 13. Create test infrastructure
  - Create pika/pru/tests/mocks/pru_registers.c for mocking R30/R31
  - Create pika/pru/tests/mocks/cycle_counter.c for mocking cycle counter
  - Create pika/pru/tests/unit/ directory with test harness
  - Create pika/pru/tests/property/ directory with theft integration
  - Add test Makefile targets: test, test-unit, test-property
  - _Requirements: Testing Strategy_

- [x] 14. Final integration and validation
  - Build both firmware binaries (make build && make bringup)
  - Verify firmware files are created in firmware/ directory
  - Run all unit tests (make test-unit)
  - Run all property tests (make test-property)
  - Document hardware validation procedure in README
  - _Requirements: 10.1, 10.2, 10.3_

- [x] 15. Final checkpoint - Complete implementation
  - Ensure all tests pass
  - Verify firmware builds successfully
  - Ask the user if questions arise or if ready for hardware testing

## Notes

- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties with 100+ iterations
- Unit tests validate specific examples, edge cases, and build system
- Hardware validation with logic analyzer is performed after software implementation
- The implementation follows a bottom-up approach: primitives → interfaces → main loop
- All tests are required for comprehensive validation from the start
