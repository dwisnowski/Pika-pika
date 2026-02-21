/* Bare-metal test: NO includes, NO dependencies */
#include <stdint.h>

/* PRU Core registers */
volatile register uint32_t __R30;

/* Resource table is linked from resource_table.obj */

void main(void) {
  /* 1. Disable IDLE and STANDBY (PRU_ICSS_CFG base is 0x26000) */
  /* This ensures the hardware doesn't cut the clock while we are running */
  (*(volatile uint32_t *)0x26004) = 0x00000001;

  /* 2. Slow down the blink so the Logic Analyzer can't miss it (10Hz) */
  while (1) {
    __R30 |= (1 << 5);        /* P9.27 HIGH */
    __delay_cycles(10000000); /* 50ms */

    __R30 &= ~(1 << 5);       /* P9.27 LOW */
    __delay_cycles(10000000); /* 50ms */
  }
}
