#ifndef ADC_PARALLEL_H
#define ADC_PARALLEL_H

#include "pru_config.h"
#include <stdint.h>

/* PRU Special Core Registers (Direct I/O) */
/* These are intrinsic to the PRU and do not have memory addresses */
volatile register uint32_t __R30;
volatile register uint32_t __R31;

#define PIN_CONVST 5 // P9.27
#define PIN_RD 2     // P9.30
#define PIN_CS 3     // P9.28
#define PIN_RESET 1  // P9.29
#define PIN_BUSY 7   // P9.25

static inline void adc_assert_cs(void) { __R30 &= ~(1 << PIN_CS); }
static inline void adc_deassert_cs(void) { __R30 |= (1 << PIN_CS); }

static inline uint32_t adc_read_busy(void) { return (__R31 & (1 << PIN_BUSY)); }

/**
 * Assemble 16-bit word from GPIO banks
 */
static inline uint16_t adc_assemble_word(void) {
  uint32_t r0 = *(volatile uint32_t *)(GPIO0_BASE + GPIO_DATAIN);
  uint32_t r1 = *(volatile uint32_t *)(GPIO1_BASE + GPIO_DATAIN);
  uint32_t r2 = *(volatile uint32_t *)(GPIO2_BASE + GPIO_DATAIN);
  uint16_t word = 0;

  // DB1/0: P8.29/30 -> GPIO2_23/25
  word |= ((r2 >> 25) & 1) << 0;
  word |= ((r2 >> 23) & 1) << 1;
  // DB3/2: P9.23 / P8.10 -> GPIO1_17 / GPIO2_4
  word |= ((r2 >> 4) & 1) << 2;
  word |= ((r1 >> 17) & 1) << 3;
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

static inline int adc_trigger_and_wait(void) {
  /* AD7606 requires a rising edge on CONVST to start conversion.
   * Based on user testing, pulling it LOW, waiting longer (~10us),
   * and rising it HIGH perfectly triggers the BUSY signal. */
  __R30 &= ~(1 << PIN_CONVST); /* Pull CONVST LOW */
  uint32_t cycles = 2000;
  while (cycles--) {
    __asm__(" NOP");
  }
  __R30 |= (1 << PIN_CONVST); /* Pull CONVST HIGH to trigger */

  uint32_t timeout = 2000000; // 1ms timeout
  while (!adc_read_busy() && timeout > 0) {
    timeout--;
  }
  if (timeout == 0)
    return -1; // BUSY never went HIGH

  timeout = 2000000;
  while (adc_read_busy() && timeout > 0) {
    timeout--;
  }
  if (timeout == 0)
    return -2; // BUSY stuck HIGH

  return 0;
}

static inline uint16_t adc_read_next(void) {
  uint16_t val;
  __R30 &= ~(1 << PIN_RD);
  uint32_t cycles = 100;
  while (cycles--) {
    __asm__(" NOP");
  }
  val = adc_assemble_word();
  __R30 |= (1 << PIN_RD);
  cycles = 100;
  while (cycles--) {
    __asm__(" NOP");
  }
  return val;
}

#endif
