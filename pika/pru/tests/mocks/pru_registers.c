/**
 * Mock PRU Registers for Host Testing
 * 
 * This file provides mock implementations of PRU R30 (output) and R31 (input)
 * registers for testing PRU firmware on a host system (x86/ARM Linux).
 * 
 * The PRU has direct access to GPIO through special registers:
 * - R30: Output register for controlling GPIO pins
 * - R31: Input register for reading GPIO pins
 * 
 * These mocks allow unit and property tests to verify firmware logic
 * without requiring actual PRU hardware.
 */

#include <stdint.h>

/* Mock PRU register storage */
volatile uint32_t mock_pru_r30 = 0;  /* Output register */
volatile uint32_t mock_pru_r31 = 0;  /* Input register */

/**
 * Reset mock registers to initial state
 * Call this at the beginning of each test
 */
void mock_pru_registers_reset(void) {
    mock_pru_r30 = 0;
    mock_pru_r31 = 0;
}

/**
 * Set a specific bit in R31 (simulate input pin going high)
 * @param bit_position: Bit position (0-31)
 */
void mock_pru_r31_set_bit(uint8_t bit_position) {
    if (bit_position < 32) {
        mock_pru_r31 |= (1U << bit_position);
    }
}

/**
 * Clear a specific bit in R31 (simulate input pin going low)
 * @param bit_position: Bit position (0-31)
 */
void mock_pru_r31_clear_bit(uint8_t bit_position) {
    if (bit_position < 32) {
        mock_pru_r31 &= ~(1U << bit_position);
    }
}

/**
 * Set R31 to a specific value (simulate parallel input)
 * @param value: 32-bit value to set
 */
void mock_pru_r31_set_value(uint32_t value) {
    mock_pru_r31 = value;
}

/**
 * Get current R30 value (read output register)
 * @return: Current R30 value
 */
uint32_t mock_pru_r30_get_value(void) {
    return mock_pru_r30;
}

/**
 * Check if a specific bit in R30 is set
 * @param bit_position: Bit position (0-31)
 * @return: 1 if bit is set, 0 otherwise
 */
int mock_pru_r30_is_bit_set(uint8_t bit_position) {
    if (bit_position < 32) {
        return (mock_pru_r30 & (1U << bit_position)) ? 1 : 0;
    }
    return 0;
}
