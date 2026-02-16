#ifndef ADC_PARALLEL_H
#define ADC_PARALLEL_H

#include <stdint.h>
#include "pru_config.h"

/**
 * ADC Parallel Interface
 * 
 * Low-level hardware interface to AD7606 using PRU GPIO registers.
 * All functions are inline for zero overhead in the hot loop.
 * 
 * Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
 */

// PRU register access
#define PRU0_R30 (*((volatile uint32_t *)0x00000000))  // Output register
#define PRU0_R31 (*((volatile uint32_t *)0x00000004))  // Input register

/**
 * Assert CONVST signal (start conversion)
 * Requirements: 4.1, 4.6
 */
static inline void adc_assert_convst(void) {
    PRU0_R30 |= (1 << PIN_CONVST);
}

/**
 * Deassert CONVST signal
 * Requirements: 4.2, 4.6
 */
static inline void adc_deassert_convst(void) {
    PRU0_R30 &= ~(1 << PIN_CONVST);
}

/**
 * Read BUSY signal state
 * Returns: 1 if busy, 0 if ready
 * Requirements: 4.3, 4.5
 */
static inline uint32_t adc_read_busy(void) {
    return (PRU0_R31 >> PIN_BUSY) & 0x1;
}

/**
 * Read 16-bit parallel data from specified channel
 * 
 * Note: For AD7606, channel selection is typically done via CS/RD signals
 * during the read sequence. This simplified version reads the 16-bit data
 * present on the parallel bus. The actual implementation depends on hardware
 * wiring and may need additional channel select logic.
 * 
 * Requirements: 4.4, 4.5
 */
static inline uint16_t adc_read_channel(uint8_t channel) {
    // Read 16 bits from data pins (R31.1-16)
    uint32_t data = (PRU0_R31 >> PIN_DATA_BASE) & 0xFFFF;
    return (uint16_t)data;
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
    
    // Wait for BUSY to go high (conversion started)
    uint32_t timeout = BUSY_TIMEOUT_CYCLES;
    while (!adc_read_busy() && timeout > 0) {
        timeout--;
    }
    if (timeout == 0) return -1;  // Timeout error
    
    // Wait for BUSY to go low (conversion complete)
    timeout = BUSY_TIMEOUT_CYCLES;
    while (adc_read_busy() && timeout > 0) {
        timeout--;
    }
    if (timeout == 0) return -1;  // Timeout error
    
    return 0;  // Success
}

#endif // ADC_PARALLEL_H
