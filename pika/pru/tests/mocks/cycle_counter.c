/**
 * Mock PRU Cycle Counter for Host Testing
 * 
 * This file provides a mock implementation of the PRU cycle counter
 * for testing timing-critical firmware on a host system.
 * 
 * The PRU has a hardware cycle counter (CTRL.CYCLE register) that
 * increments at 200 MHz (5 ns per cycle). This mock simulates the
 * counter behavior including wrap-around at 32-bit boundary.
 * 
 * The mock counter can be advanced manually or automatically to
 * simulate the passage of time in tests.
 */

#include <stdint.h>

/* Mock cycle counter storage */
static uint32_t mock_cycle_counter = 0;

/* Automatic advancement mode */
static int auto_advance_enabled = 0;
static uint32_t auto_advance_increment = 1;

/**
 * Reset mock cycle counter to zero
 * Call this at the beginning of each test
 */
void mock_cycle_counter_reset(void) {
    mock_cycle_counter = 0;
    auto_advance_enabled = 0;
    auto_advance_increment = 1;
}

/**
 * Set mock cycle counter to a specific value
 * Useful for testing wrap-around behavior
 * @param value: Value to set counter to
 */
void mock_cycle_counter_set(uint32_t value) {
    mock_cycle_counter = value;
}

/**
 * Get current mock cycle counter value
 * @return: Current counter value
 */
uint32_t mock_cycle_counter_get(void) {
    uint32_t value = mock_cycle_counter;
    
    /* Auto-advance if enabled */
    if (auto_advance_enabled) {
        mock_cycle_counter += auto_advance_increment;
    }
    
    return value;
}

/**
 * Advance mock cycle counter by specified number of cycles
 * @param cycles: Number of cycles to advance
 */
void mock_cycle_counter_advance(uint32_t cycles) {
    mock_cycle_counter += cycles;
}

/**
 * Enable automatic counter advancement
 * When enabled, each read of the counter advances it automatically
 * @param increment: Number of cycles to advance per read (default: 1)
 */
void mock_cycle_counter_enable_auto_advance(uint32_t increment) {
    auto_advance_enabled = 1;
    auto_advance_increment = increment;
}

/**
 * Disable automatic counter advancement
 */
void mock_cycle_counter_disable_auto_advance(void) {
    auto_advance_enabled = 0;
}

/**
 * Mock implementation of get_cycle_count() for testing
 * This replaces the inline assembly version in timing.c
 * @return: Current cycle count
 */
uint32_t get_cycle_count(void) {
    return mock_cycle_counter_get();
}
