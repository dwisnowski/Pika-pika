#ifndef ADC_PARALLEL_H
#define ADC_PARALLEL_H

#include <stdint.h>
#include "pru_config.h"


static inline void adc_assert_cs(void) { __R30 &= ~PIN_CS; }
static inline void adc_deassert_cs(void) { __R30 |= PIN_CS; }

static inline uint32_t adc_read_busy(void) { return (__R31 & PIN_BUSY); }

static inline uint16_t adc_assemble_word(void) {
  /* Read each bank ONCE for performance and consistency */
  uint32_t r0 = GPIO0_DATAIN_REG;
  uint32_t r1 = GPIO1_DATAIN_REG;
  uint32_t r2 = GPIO2_DATAIN_REG;

  uint16_t word = 0;

  /* Map bits to the 16-bit word (LSB first: DB0 = bit 0) */
  if (r2 & M_GPIO2_DB0)
    word |= (1 << 0);
  if (r2 & M_GPIO2_DB1)
    word |= (1 << 1);
  if (r2 & M_GPIO2_DB2)
    word |= (1 << 2);
  if (r1 & M_GPIO1_DB3)
    word |= (1 << 3);
  if (r1 & M_GPIO1_DB4)
    word |= (1 << 4);
  if (r1 & M_GPIO1_DB5)
    word |= (1 << 5);
  if (r0 & M_GPIO0_DB6)
    word |= (1 << 6);
  if (r0 & M_GPIO0_DB7)
    word |= (1 << 7);
  if (r1 & M_GPIO1_DB8)
    word |= (1 << 8);
  if (r1 & M_GPIO1_DB9)
    word |= (1 << 9);
  if (r2 & M_GPIO2_DB10)
    word |= (1 << 10);
  if (r0 & M_GPIO0_DB11)
    word |= (1 << 11);
  if (r1 & M_GPIO1_DB12)
    word |= (1 << 12);
  if (r0 & M_GPIO0_DB13)
    word |= (1 << 13);
  if (r2 & M_GPIO2_DB14)
    word |= (1 << 14);
  if (r2 & M_GPIO2_DB15)
    word |= (1 << 15);

  return word;
}

static inline int adc_trigger_and_wait(void) {
  /* AD7606 requires a rising edge on CONVST to start conversion.
   * Based on user testing, pulling it LOW, waiting longer (~10us),
   * and rising it HIGH perfectly triggers the BUSY signal. */
  __R30 &= ~PIN_CONVST; /* Pull CONVST LOW */
  uint32_t timeout = 10;
  while (timeout > 0) {
    timeout--;
  }
  __R30 |= PIN_CONVST; /* Pull CONVST HIGH to trigger */

  timeout = 2000000; // 1ms timeout
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
  __R30 &= ~PIN_RD;
  uint32_t timeout = 100;
  while (timeout > 0) {
    timeout--;
  }
  val = adc_assemble_word();
  __R30 |= PIN_RD; // set RD high to latch the data
  timeout = 100;
  while (timeout > 0) {
    timeout--;
  }
  return val;
}

#endif
