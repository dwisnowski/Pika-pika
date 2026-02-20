#ifndef ADC_PARALLEL_H
#define ADC_PARALLEL_H

#include "pru_config.h"
#include <stdint.h>

/* PRU0 R30/R31 Bit Mappings */
#define PRU0_R30 (*((volatile uint32_t *)0x22000))
#define PRU0_R31 (*((volatile uint32_t *)0x22000))

#define PIN_CONVST 5 // P9.27 (R30 bit 5)
#define PIN_RD 2     // P9.30 (R30 bit 2)
#define PIN_CS 3     // P9.28 (R30 bit 3, though user says it's grounded)
#define PIN_BUSY 7   // P9.25 (R31 bit 7)

static inline void adc_assert_cs(void) { PRU0_R30 &= ~(1 << PIN_CS); }
static inline void adc_deassert_cs(void) { PRU0_R30 |= (1 << PIN_CS); }

static inline uint32_t adc_read_busy(void) {
  return (PRU0_R31 & (1 << PIN_BUSY));
}

/**
 * Assemble 16-bit word from GPIO banks
 * We read all three banks once to minimize OCP transaction overhead.
 */
static inline uint16_t adc_assemble_word(void) {
  uint32_t r0 = (*(volatile uint32_t *)(GPIO0_BASE + GPIO_DATAIN));
  uint32_t r1 = (*(volatile uint32_t *)(GPIO1_BASE + GPIO_DATAIN));
  uint32_t r2 = (*(volatile uint32_t *)(GPIO2_BASE + GPIO_DATAIN));
  uint16_t word = 0;

  // DB1/0: P8.29/30 -> GPIO2_23/25
  word |= ((r2 >> 25) & 1) << 0;
  word |= ((r2 >> 23) & 1) << 1;
  // DB3/2: P8.31/10 -> GPIO0_10 / GPIO2_4
  word |= ((r2 >> 4) & 1) << 2;
  word |= ((r0 >> 10) & 1) << 3;
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
 * Trigger CONVST and wait for BUSY cycles.
 * Returns: 0 = OK, -1 = BUSY never went High, -2 = BUSY never went Low
 */
static inline int adc_trigger_and_wait(void) {
  // CONVST Start: Falling edge initiates
  PRU0_R30 |= (1 << PIN_CONVST);
  __delay_cycles(200); // Wait 1us
  PRU0_R30 &= ~(1 << PIN_CONVST);
  __delay_cycles(200); // 1us pulse width
  PRU0_R30 |= (1 << PIN_CONVST);

  // Wait for BUSY Rising Edge
  uint32_t timeout = 500000;
  while (!adc_read_busy() && timeout > 0)
    timeout--;
  if (timeout == 0)
    return -1;

  // Wait for BUSY Falling Edge
  timeout = 500000;
  while (adc_read_busy() && timeout > 0)
    timeout--;
  if (timeout == 0)
    return -2;

  return 0;
}

static inline uint16_t adc_read_next(void) {
  uint16_t val;
  // Pulse RD low
  PRU0_R30 &= ~(1 << PIN_RD);
  __delay_cycles(100); // 500ns stabilization
  val = adc_assemble_word();
  PRU0_R30 |= (1 << PIN_RD);
  __delay_cycles(100);
  return val;
}

#endif
