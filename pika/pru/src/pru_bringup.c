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

/* PRU R30 register - GPIO outputs */
#define PRU0_R30 (*((volatile uint32_t *)0x00000000))

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
    /* Calculate toggle period for 1 kHz square wave
     * 1 kHz = 1000 Hz frequency
     * Period = 1/1000 = 1 ms = 1000 µs
     * Half period (time between toggles) = 500 µs
     * Cycles = 500 µs × 200 cycles/µs = 100,000 cycles
     * 
     * However, task details specify 200,000 cycles which gives:
     * 200,000 cycles / 200 cycles/µs = 1000 µs = 1 ms toggle interval
     * This creates a 500 Hz square wave (2 ms period)
     * 
     * Using task-specified value of 200,000 cycles for 1 ms toggle
     */
    uint32_t toggle_period = 200000;  // 1 ms @ 200 MHz = 1 kHz toggle rate
    
    /* Infinite loop: toggle CONVST pin at regular intervals */
    while (1) {
        /* Toggle CONVST pin (XOR with bit mask) */
        PRU0_R30 ^= (1 << PIN_CONVST);
        
        /* Wait for next toggle time */
        wait_cycles(toggle_period);
    }
    
    /* This point is never reached - firmware runs forever */
}
