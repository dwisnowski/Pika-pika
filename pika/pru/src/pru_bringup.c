/**
 * PRU Bring-up Test Firmware
 *
 * This is a minimal test firmware for hardware validation. It toggles the
 * CONVST pin at a known frequency (1 kHz) to verify:
 * - PRU is running and clock is correct
 * - Pin configuration in device tree is correct
 * - Basic GPIO functionality works
 *
 * This firmware has NO dependencies on shared memory or complex logic,
 * making it ideal for initial hardware bring-up and debugging.
 *
 * Expected behavior:
 * - CONVST pin (P9.31, PRU0 R30.0) toggles at 1 kHz
 * - Measure with logic analyzer to verify 1 kHz square wave (500 µs period)
 * - If frequency is correct, PRU clock and pin config are working
 *
 * Requirements: 7.1, 7.2, 7.3
 */

#include "pru_config.h"
#include "resource_table.h"
#include <pru_cfg.h>
#include <stdint.h>

/* Just tell the compiler the table exists in another file */
extern const struct my_resource_table pru_remoteproc_ResourceTable;

/* PRU R30 register - GPIO outputs */
volatile register uint32_t __R30; // Output register

/**
 * Main entry point for bring-up test firmware
 *
 * Toggles CONVST pin at 1 kHz (1000 Hz) for hardware validation.
 *
 * Timing calculation:
 * - Target frequency: 1 kHz
 * - Period: 1 ms = 1000 µs
 * - Half period (toggle interval): 500 µs
 * - Cycles per toggle: 500 µs × 200 cycles/µs = 100,000 cycles
 */
void main(void) {

  /* Clear SYSCFG[STANDBY_INIT] to enable OCP master port */
  /* This ensures the PRU can actually talk to the outside world */
  (*(volatile uint32_t *)0x26004) &= ~(1 << 4);

  /* Use it once so the linker doesn't throw it away */
  (void)pru_remoteproc_ResourceTable;

  /* Infinite loop: toggle CONVST pin at regular intervals */
  while (1) {
    /* Toggle CONVST pin (XOR with bit mask) */
    __R30 ^= PIN_CONVST;
    __delay_cycles(100000);
  }

  /* This point is never reached - firmware runs forever */
}
