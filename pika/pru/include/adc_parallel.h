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
 * Pulse RESET signal
 */
static inline void adc_reset(void) {
  PRU0_R30 |= (1 << PIN_RESET);
  __delay_cycles(100); // ~500ns
  PRU0_R30 &= ~(1 << PIN_RESET);
  __delay_cycles(100);
}

/**
 * Assert CS signal
 */
static inline void adc_assert_cs(void) { PRU0_R30 &= ~(1 << PIN_CS); }

/**
 * Deassert CS signal
 */
static inline void adc_deassert_cs(void) { PRU0_R30 |= (1 << PIN_CS); }

/**
 * Read BUSY signal state
 * Returns: 1 if busy, 0 if ready
 */
static inline uint32_t adc_read_busy(void) {
  return (PRU0_R31 & (1 << PIN_BUSY)) ? 1 : 0;
}

/**
 * Assemble 16-bit word from GPIO banks
 */
static inline uint16_t adc_assemble_word(void) {
  uint32_t r0 = (*(volatile uint32_t *)(GPIO0_BASE + GPIO_DATAIN));
  uint32_t r1 = (*(volatile uint32_t *)(GPIO1_BASE + GPIO_DATAIN));
  uint32_t r2 = (*(volatile uint32_t *)(GPIO2_BASE + GPIO_DATAIN));
  uint16_t word = 0;

  // DB1/0: P8.7/8 -> GPIO2_2/3
  word |= ((r2 >> 3) & 1) << 0;
  word |= ((r2 >> 2) & 1) << 1;
  // DB3/2: P8.9/10 -> GPIO2_5/4
  word |= ((r2 >> 4) & 1) << 2;
  word |= ((r2 >> 5) & 1) << 3;
  // DB5/4: P8.11/12 -> GPIO1_13/12
  word |= ((r1 >> 12) & 1) << 4;
  word |= ((r1 >> 13) & 1) << 5;
  // DB7/6: P8.13/14 -> GPIO0_23/26
  word |= ((r0 >> 26) & 1) << 6;
  word |= ((r0 >> 23) & 1) << 7;
  // DB9/8: P8.15/16 -> GPIO1_15/14
  word |= ((r1 >> 14) & 1) << 8;
  word |= ((r1 >> 15) & 1) << 9;
  // DB11/10: P8.17/18 -> GPIO0_27 / GPIO2_1
  word |= ((r2 >> 1) & 1) << 10;
  word |= ((r0 >> 27) & 1) << 11;
  // DB13/12: P8.19 / P8.26 -> GPIO0_22 / GPIO1_29
  word |= ((r1 >> 29) & 1) << 12;
  word |= ((r0 >> 22) & 1) << 13;
  // DB15/14: P8.27 / P8.28 -> GPIO2_22 / GPIO2_24
  word |= ((r2 >> 24) & 1) << 14;
  word |= ((r2 >> 22) & 1) << 15;

  return word;
}

/**
 * Read 16-bit parallel data for the next channel
 */
static inline uint16_t adc_read_next(void) {
  uint16_t val;
  // Pulse RD (Falling edge triggers read)
  PRU0_R30 &= ~(1 << PIN_RD);
  __delay_cycles(10); // Minimum RD pulse width (20ns)
  val = adc_assemble_word();
  PRU0_R30 |= (1 << PIN_RD);
  __delay_cycles(10);
  return val;
}

// Backward compatibility for main loop
static inline uint16_t adc_read_channel(uint8_t channel) {
  return adc_read_next();
}

/**
 * Trigger conversion and wait for completion
 */
static inline int adc_trigger_and_wait(void) {
  adc_assert_convst();
  __delay_cycles(CONVST_PULSE_CYCLES);
  adc_deassert_convst();

  // Wait for BUSY to go high then low
  uint32_t timeout = BUSY_TIMEOUT_CYCLES;
  while (!adc_read_busy() && timeout > 0)
    timeout--;
  timeout = BUSY_TIMEOUT_CYCLES;
  while (adc_read_busy() && timeout > 0)
    timeout--;

  if (timeout == 0)
    return -1;
  return 0;
}

#endif // ADC_PARALLEL_H
