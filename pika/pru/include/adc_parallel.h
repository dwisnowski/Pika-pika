#ifndef ADC_PARALLEL_H
#define ADC_PARALLEL_H

#include "pru_config.h"
#include <stdint.h>

/**
 * ADC Parallel Interface
 *
 * Low-level hardware interface to AD7606 using PRU GPIO registers.
 * All functions are inline for zero overhead in the hot loop.
 */

// PRU register access (Matches pru_bringup.c)
#include <pru_cfg.h>

volatile register uint32_t __R30; // Output register
volatile register uint32_t __R31; // Input register

#define PRU0_R30 __R30 // Output register
#define PRU0_R31 __R31 // Input register

/**
 * Assert CONVST signal (start conversion)
 */
static inline void adc_assert_convst(void) { PRU0_R30 |= (1 << PIN_CONVST); }

/**
 * Deassert CONVST signal
 */
static inline void adc_deassert_convst(void) { PRU0_R30 &= ~(1 << PIN_CONVST); }

/**
 * Read BUSY signal state
 * Returns: 1 if busy, 0 if ready
 */
static inline uint32_t adc_read_busy(void) {
  if (PRU0_R31 & (1 << PIN_BUSY)) {
    return 1;
  }
  return 0;
}

/**
 * Read 16-bit parallel data (DB0 on P8.16 = R31.14)
 */
static inline uint16_t adc_read_channel(uint8_t channel) {
  // Read 16 bits starting at PIN_DATA_BASE (14)
  return (uint16_t)((PRU0_R31 >> PIN_DATA_BASE) & 0xFFFF);
}

/**
 * Trigger conversion and wait for completion
 *
 * Sequence:
 * 1. Assert CONVST pulse (minimum 250ns per AD7606 datasheet)
 * 2. Wait for BUSY to go high (conversion started)
 * 3. Wait for BUSY to go low (conversion complete)
 *
 * Returns: 0 on success, -1 on timeout
 * Requirements: 4.1, 4.2, 4.3, 4.7
 */
static inline int adc_trigger_and_wait(void) {
  // Assert CONVST pulse
  adc_assert_convst();
  __delay_cycles(CONVST_PULSE_CYCLES);
  adc_deassert_convst();

  // TEMPORARY: Bypass BUSY wait for testing without ADC hardware
  // Simulate AD7606 conversion time (~3us = 600 cycles @ 200MHz)
  __delay_cycles(600);

  // TODO: Re-enable this once ADC is properly connected:
  /*
  // Wait for BUSY to go high (conversion started)
  uint32_t timeout = BUSY_TIMEOUT_CYCLES;
  while (!adc_read_busy() && timeout > 0) {
    timeout--;
  }
  if (timeout == 0)
    return -1; // Timeout error

  // Wait for BUSY to go low (conversion complete)
  timeout = BUSY_TIMEOUT_CYCLES;
  while (adc_read_busy() && timeout > 0) {
    timeout--;
  }
  if (timeout == 0)
    return -1; // Timeout error
  */

  return 0; // Success
}

#endif // ADC_PARALLEL_H
