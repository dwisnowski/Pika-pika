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

#include <stdint.h>
#include "timing.h"
#include "pru_config.h"
#include <pru_cfg.h>
#include "resource_table.h"


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
 * 
 * Note: The task description mentions 200,000 cycles which would give
 * 1 ms toggle interval = 500 Hz square wave. Using 100,000 cycles for
 * 1 kHz as specified in requirements 7.1.
 * 
 * Requirements:
 * - 7.1: Toggle GPIO pins at known frequency (1 kHz)
 * - 7.2: No shared memory dependencies
 * - 7.3: Use simple cycle-based delays
 */
void main(void) {

    /* Clear SYSCFG[STANDBY_INIT] to enable OCP master port */
    /* This ensures the PRU can actually talk to the outside world */
    (*(volatile uint32_t *)0x26004) &= ~(1 << 4);

    /* Use it once so the linker doesn't throw it away */
    (void)pru_remoteproc_ResourceTable; 

    /* Calculate toggle period for 1 kHz square wave
     * 1 kHz = 1000 Hz frequency
     * Period = 1/1000 = 1 ms = 1000 µs
     * Half period (time between toggles) = 500 µs
     * Cycles = 500 µs × 200 cycles/µs = 100,000 cycles
     * 
     * This creates a 1 kHz square wave (1 ms period, 500 µs high, 500 µs low)
     */
    uint32_t toggle_period = 100000;  // 500 µs @ 200 MHz = 1 kHz square wave
    
    
    /* Infinite loop: toggle CONVST pin at regular intervals */
    while (1) {
        /* Toggle CONVST pin (XOR with bit mask) */
        __R30 ^= (1 << PIN_CONVST); 
        
        /* Wait for next toggle time  uses __delay_cycles(cycles) internally which is a busy-wait */
        wait_cycles(toggle_period);
    }
    
    /* This point is never reached - firmware runs forever */
}
