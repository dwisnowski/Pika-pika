#ifndef TIMING_H
#define TIMING_H

#include <stdint.h>
#include "pru_config.h"

/**
 * Timing System for PRU Firmware
 * 
 * This module provides cycle-accurate timing primitives for deterministic
 * data acquisition. All functions are static inline for zero overhead.
 * 
 * Requirements: 3.1, 3.2, 3.3
 */

/**
 * Read the current PRU cycle counter value
 * 
 * Reads the CTRL.CYCLE register which provides a free-running 32-bit cycle counter.
 * 
 * @return Current cycle count (wraps at 2^32)
 * 
 * Requirement 3.1: Provide function to read cycle counter
 */
static inline uint32_t get_cycle_count(void) {
    volatile uint32_t *cycle_reg = (volatile uint32_t *)(0x22000 + 0x0C);
    return *cycle_reg;
}

/**
 * Wait for a specified number of cycles using busy-wait
 * 
 * This function provides deterministic timing by busy-waiting until
 * the specified number of cycles have elapsed. Handles 32-bit counter
 * wrap-around correctly.
 * 
 * @param cycles Number of cycles to wait
 * 
 * Requirements:
 * - 3.2: Provide function to wait for specified cycles
 * - 3.3: Busy-wait using cycle counter comparison
 * - 3.4: No floating-point arithmetic
 * - 3.5: No division operations
 */
static inline void wait_cycles(uint32_t cycles) {
    uint32_t start = get_cycle_count();
    uint32_t target = start + cycles;
    
    if (target < start) {
        while (get_cycle_count() >= start);
    }
    
    while (get_cycle_count() < target);
}

/**
 * Calculate elapsed cycles between two timestamps
 * 
 * Correctly handles 32-bit counter wrap-around by checking if end < start.
 * 
 * @param start Starting cycle count
 * @param end Ending cycle count
 * @return Number of cycles elapsed (handles wrap-around)
 * 
 * Requirement 3.3: Handle wrap-around in timing calculations
 */
static inline uint32_t elapsed_cycles(uint32_t start, uint32_t end) {
    if (end >= start) {
        return end - start;
    } else {
        return (0xFFFFFFFF - start) + end + 1;
    }
}

/**
 * Validate that a sample period is within acceptable range
 * 
 * Checks that the period is between MIN_SAMPLE_PERIOD_CYCLES and
 * MAX_SAMPLE_PERIOD_CYCLES as defined in pru_config.h.
 * 
 * @param period_cycles Sample period in cycles to validate
 * @return 1 if valid, 0 if invalid
 * 
 * Requirement 2.2: Validate sample period against min/max limits
 */
static inline int is_valid_sample_period(uint32_t period_cycles) {
    return (period_cycles >= MIN_SAMPLE_PERIOD_CYCLES &&
            period_cycles <= MAX_SAMPLE_PERIOD_CYCLES);
}

#endif /* TIMING_H */
