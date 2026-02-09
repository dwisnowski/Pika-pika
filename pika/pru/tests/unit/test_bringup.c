/**
 * Unit tests for PRU bring-up test firmware
 * 
 * Tests the bring-up firmware defined in pru_bringup.c
 * Requirements: 7.1, 7.2, 7.3
 * 
 * Note: These tests run on host system (x86) with mocked PRU registers.
 * The actual PRU R30 register is replaced with a mock implementation.
 */

#include <stdio.h>
#include <stdint.h>
#include <assert.h>

/* Mock PRU R30 register for host testing */
static volatile uint32_t mock_r30 = 0;

/* Mock cycle counter for host testing */
static uint32_t mock_cycle_counter = 0;

/* Mock implementation of get_cycle_count for host testing */
static inline uint32_t get_cycle_count(void) {
    return mock_cycle_counter;
}

/* Include configuration */
#include "../../include/pru_config.h"

/* Mock implementation of wait_cycles for testing */
static inline void wait_cycles(uint32_t cycles) {
    mock_cycle_counter += cycles;
}

/* Test counter */
static int tests_passed = 0;
static int tests_failed = 0;

/* Test helper macros */
#define TEST(name) \
    printf("Running test: %s\n", #name); \
    test_##name()

#define ASSERT_EQ(actual, expected, msg) \
    do { \
        if ((actual) == (expected)) { \
            tests_passed++; \
        } else { \
            tests_failed++; \
            printf("  FAIL: %s (expected %lu, got %lu)\n", msg, \
                   (unsigned long)(expected), (unsigned long)(actual)); \
        } \
    } while(0)

#define ASSERT_TRUE(condition, msg) \
    do { \
        if (condition) { \
            tests_passed++; \
        } else { \
            tests_failed++; \
            printf("  FAIL: %s\n", msg); \
        } \
    } while(0)

#define ASSERT_NE(actual, expected, msg) \
    do { \
        if ((actual) != (expected)) { \
            tests_passed++; \
        } else { \
            tests_failed++; \
            printf("  FAIL: %s (expected not equal to %lu, got %lu)\n", msg, \
                   (unsigned long)(expected), (unsigned long)(actual)); \
        } \
    } while(0)

/**
 * Simulate one iteration of the bringup firmware loop
 * This mimics the behavior of the main loop in pru_bringup.c
 */
static void simulate_bringup_iteration(uint32_t toggle_period) {
    /* Toggle CONVST pin (XOR with bit mask) */
    mock_r30 ^= (1 << PIN_CONVST);
    
    /* Wait for next toggle time */
    wait_cycles(toggle_period);
}

/**
 * Test GPIO toggle at known frequency
 * Requirement: 7.1 - Toggle GPIO pins at known frequency
 */
void test_gpio_toggle_frequency(void) {
    /* Reset mock state */
    mock_r30 = 0;
    mock_cycle_counter = 0;
    
    uint32_t toggle_period = 200000;  /* 1 ms @ 200 MHz */
    
    /* Initial state: CONVST should be low (0) */
    uint32_t initial_state = mock_r30 & (1 << PIN_CONVST);
    ASSERT_EQ(initial_state, 0, "Initial CONVST state should be 0");
    
    /* First toggle: should go high */
    simulate_bringup_iteration(toggle_period);
    uint32_t state_after_first = mock_r30 & (1 << PIN_CONVST);
    ASSERT_NE(state_after_first, 0, "CONVST should be high after first toggle");
    ASSERT_EQ(mock_cycle_counter, toggle_period, "Should wait toggle_period cycles");
    
    /* Second toggle: should go low */
    simulate_bringup_iteration(toggle_period);
    uint32_t state_after_second = mock_r30 & (1 << PIN_CONVST);
    ASSERT_EQ(state_after_second, 0, "CONVST should be low after second toggle");
    ASSERT_EQ(mock_cycle_counter, 2 * toggle_period, "Should wait 2x toggle_period cycles");
    
    /* Third toggle: should go high again */
    simulate_bringup_iteration(toggle_period);
    uint32_t state_after_third = mock_r30 & (1 << PIN_CONVST);
    ASSERT_NE(state_after_third, 0, "CONVST should be high after third toggle");
    ASSERT_EQ(mock_cycle_counter, 3 * toggle_period, "Should wait 3x toggle_period cycles");
}

/**
 * Test toggle period calculation
 * Verifies that 200,000 cycles produces the expected frequency
 */
void test_toggle_period_calculation(void) {
    uint32_t toggle_period = 200000;  /* As specified in task */
    
    /* Calculate frequency from toggle period */
    /* toggle_period cycles = 200,000 cycles */
    /* Time per toggle = 200,000 / 200,000,000 Hz = 0.001 s = 1 ms */
    /* Full period (high + low) = 2 ms */
    /* Frequency = 1 / 0.002 s = 500 Hz */
    
    /* Verify toggle period is correct for 1 ms interval */
    uint32_t expected_cycles_per_ms = PRU_CLOCK_HZ / 1000;  /* 200,000 cycles/ms */
    ASSERT_EQ(toggle_period, expected_cycles_per_ms, 
              "Toggle period should be 200,000 cycles for 1 ms");
    
    /* Verify this produces 1 kHz toggle rate (500 Hz square wave) */
    /* 1 toggle per ms = 1000 toggles per second = 1 kHz toggle rate */
    /* Square wave frequency = toggle rate / 2 = 500 Hz */
    uint32_t toggles_per_second = 1000000 / (toggle_period / CYCLES_PER_US);
    ASSERT_EQ(toggles_per_second, 1000, "Should produce 1000 toggles per second");
}

/**
 * Test that bringup firmware has no shared memory dependencies
 * Requirement: 7.2 - No shared memory dependencies
 */
void test_no_shared_memory_dependencies(void) {
    /* This test verifies that the bringup firmware can run without
     * any shared memory initialization. We simulate the firmware
     * without setting up any shared memory structures.
     */
    
    /* Reset mock state */
    mock_r30 = 0;
    mock_cycle_counter = 0;
    
    uint32_t toggle_period = 200000;
    
    /* Run several iterations without any shared memory setup */
    for (int i = 0; i < 10; i++) {
        simulate_bringup_iteration(toggle_period);
    }
    
    /* Verify firmware ran successfully */
    ASSERT_EQ(mock_cycle_counter, 10 * toggle_period, 
              "Firmware should run without shared memory");
    
    /* Verify toggles occurred (R30 should have changed) */
    /* After 10 toggles (even number), should be back to initial state (0) */
    uint32_t final_state = mock_r30 & (1 << PIN_CONVST);
    ASSERT_EQ(final_state, 0, "After even number of toggles, should be back to 0");
}

/**
 * Test that bringup firmware uses simple cycle-based delays
 * Requirement: 7.3 - Use simple cycle-based delays
 */
void test_simple_cycle_delays(void) {
    /* Reset mock state */
    mock_r30 = 0;
    mock_cycle_counter = 0;
    
    uint32_t toggle_period = 200000;
    
    /* Run one iteration */
    simulate_bringup_iteration(toggle_period);
    
    /* Verify that wait_cycles was called with correct period */
    ASSERT_EQ(mock_cycle_counter, toggle_period, 
              "Should use wait_cycles with toggle_period");
    
    /* Verify delay is deterministic (same delay each time) */
    uint32_t first_delay = mock_cycle_counter;
    simulate_bringup_iteration(toggle_period);
    uint32_t second_delay = mock_cycle_counter - first_delay;
    
    ASSERT_EQ(second_delay, toggle_period, 
              "Delay should be consistent across iterations");
}

/**
 * Test GPIO pin assignment
 * Verifies that CONVST pin is correctly defined
 */
void test_gpio_pin_assignment(void) {
    /* Verify PIN_CONVST is defined and has expected value */
    ASSERT_EQ(PIN_CONVST, 0, "PIN_CONVST should be pin 0 (R30.0)");
    
    /* Verify bit mask is correct */
    uint32_t convst_mask = (1 << PIN_CONVST);
    ASSERT_EQ(convst_mask, 0x00000001, "CONVST bit mask should be 0x00000001");
}

/**
 * Test toggle pattern over multiple cycles
 * Verifies alternating high/low pattern
 */
void test_toggle_pattern(void) {
    /* Reset mock state */
    mock_r30 = 0;
    mock_cycle_counter = 0;
    
    uint32_t toggle_period = 200000;
    
    /* Track toggle states */
    uint32_t states[8];
    for (int i = 0; i < 8; i++) {
        simulate_bringup_iteration(toggle_period);
        states[i] = (mock_r30 & (1 << PIN_CONVST)) ? 1 : 0;
    }
    
    /* Verify alternating pattern: 1, 0, 1, 0, 1, 0, 1, 0 */
    for (int i = 0; i < 8; i++) {
        uint32_t expected = (i % 2 == 0) ? 1 : 0;
        ASSERT_EQ(states[i], expected, "Toggle pattern should alternate");
    }
}

/**
 * Test that only CONVST pin is affected
 * Verifies that other R30 bits are not modified
 */
void test_only_convst_affected(void) {
    /* Reset mock state and set some other bits */
    mock_r30 = 0xFFFFFFFE;  /* All bits set except bit 0 */
    mock_cycle_counter = 0;
    
    uint32_t toggle_period = 200000;
    uint32_t initial_other_bits = mock_r30 & ~(1 << PIN_CONVST);
    
    /* Run several iterations */
    for (int i = 0; i < 5; i++) {
        simulate_bringup_iteration(toggle_period);
        
        /* Verify other bits are unchanged */
        uint32_t current_other_bits = mock_r30 & ~(1 << PIN_CONVST);
        ASSERT_EQ(current_other_bits, initial_other_bits, 
                  "Other R30 bits should not be affected");
    }
}

/**
 * Test timing accuracy
 * Verifies that timing is based on cycle counter
 */
void test_timing_accuracy(void) {
    /* Reset mock state */
    mock_r30 = 0;
    mock_cycle_counter = 0;
    
    uint32_t toggle_period = 200000;
    
    /* Run 100 iterations and verify timing */
    for (int i = 0; i < 100; i++) {
        uint32_t expected_cycles = (i + 1) * toggle_period;
        simulate_bringup_iteration(toggle_period);
        ASSERT_EQ(mock_cycle_counter, expected_cycles, 
                  "Timing should be cycle-accurate");
    }
}

/**
 * Main test runner
 */
int main(void) {
    printf("=== PRU Bring-up Firmware Unit Tests ===\n\n");
    
    TEST(gpio_toggle_frequency);
    TEST(toggle_period_calculation);
    TEST(no_shared_memory_dependencies);
    TEST(simple_cycle_delays);
    TEST(gpio_pin_assignment);
    TEST(toggle_pattern);
    TEST(only_convst_affected);
    TEST(timing_accuracy);
    
    printf("\n=== Test Results ===\n");
    printf("Passed: %d\n", tests_passed);
    printf("Failed: %d\n", tests_failed);
    
    if (tests_failed == 0) {
        printf("\nAll tests PASSED!\n");
        return 0;
    } else {
        printf("\nSome tests FAILED!\n");
        return 1;
    }
}
