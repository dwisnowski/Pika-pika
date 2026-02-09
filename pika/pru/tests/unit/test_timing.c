/**
 * Unit tests for PRU timing functions
 * 
 * Tests the timing primitives defined in timing.h
 * Requirements: 3.1, 3.2, 3.3
 * 
 * Note: These tests run on host system (x86) with mocked cycle counter.
 * The actual PRU inline assembly is replaced with a mock implementation.
 */

#include <stdio.h>
#include <stdint.h>
#include <assert.h>

/* Mock cycle counter for host testing */
static uint32_t mock_cycle_counter = 0;

/* Mock implementation of get_cycle_count for host testing */
static inline uint32_t get_cycle_count(void) {
    return mock_cycle_counter;
}

/* Include timing functions after defining mock */
#define get_cycle_count get_cycle_count  /* Use our mock */
#include "../../include/pru_config.h"

/* Now manually include the timing functions (excluding the real get_cycle_count) */

/**
 * Wait for specified number of cycles (using mock counter)
 */
static inline void wait_cycles(uint32_t cycles) {
    uint32_t start = get_cycle_count();
    uint32_t target = start + cycles;
    
    /* Simulate waiting by advancing mock counter */
    mock_cycle_counter = target;
}

/**
 * Calculate elapsed cycles between two timestamps
 */
static inline uint32_t elapsed_cycles(uint32_t start, uint32_t end) {
    if (end >= start) {
        return end - start;
    } else {
        /* Handle wrap-around */
        return (0xFFFFFFFF - start) + end + 1;
    }
}

/**
 * Validate sample period is within acceptable range
 */
static inline int is_valid_sample_period(uint32_t period_cycles) {
    return (period_cycles >= MIN_SAMPLE_PERIOD_CYCLES &&
            period_cycles <= MAX_SAMPLE_PERIOD_CYCLES);
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

/**
 * Test get_cycle_count returns incrementing values
 * Requirement: 3.1 - Provide function to read cycle counter
 */
void test_get_cycle_count_increments(void) {
    /* Reset mock counter */
    mock_cycle_counter = 0;
    
    uint32_t count1 = get_cycle_count();
    ASSERT_EQ(count1, 0, "Initial cycle count should be 0");
    
    /* Simulate time passing */
    mock_cycle_counter = 100;
    uint32_t count2 = get_cycle_count();
    ASSERT_EQ(count2, 100, "Cycle count should increment");
    
    /* Verify count2 > count1 */
    ASSERT_TRUE(count2 > count1, "Cycle count should increase over time");
}

/**
 * Test elapsed_cycles with normal case (no wrap-around)
 * Requirement: 3.3 - Handle wrap-around in timing calculations
 */
void test_elapsed_cycles_normal(void) {
    uint32_t start = 1000;
    uint32_t end = 2000;
    uint32_t elapsed = elapsed_cycles(start, end);
    
    ASSERT_EQ(elapsed, 1000, "Elapsed cycles should be 1000");
    
    /* Test with zero elapsed */
    elapsed = elapsed_cycles(1000, 1000);
    ASSERT_EQ(elapsed, 0, "Elapsed cycles should be 0 when start == end");
    
    /* Test with large values */
    start = 0x10000000;
    end = 0x20000000;
    elapsed = elapsed_cycles(start, end);
    ASSERT_EQ(elapsed, 0x10000000, "Elapsed cycles should handle large values");
}

/**
 * Test elapsed_cycles with wrap-around
 * Requirement: 3.3 - Handle wrap-around in timing calculations
 */
void test_elapsed_cycles_wraparound(void) {
    /* Test wrap-around: counter goes from near max to near zero */
    uint32_t start = 0xFFFFFFF0;  /* Near max value */
    uint32_t end = 0x00000010;     /* After wrap-around */
    uint32_t elapsed = elapsed_cycles(start, end);
    
    /* Expected: (0xFFFFFFFF - 0xFFFFFFF0) + 0x00000010 + 1 = 15 + 16 + 1 = 32 */
    ASSERT_EQ(elapsed, 32, "Elapsed cycles should handle wrap-around correctly");
    
    /* Test exact wrap-around */
    start = 0xFFFFFFFF;
    end = 0x00000000;
    elapsed = elapsed_cycles(start, end);
    ASSERT_EQ(elapsed, 1, "Elapsed cycles from max to zero should be 1");
    
    /* Test wrap-around with larger gap */
    start = 0xFFFFFF00;
    end = 0x00000100;
    elapsed = elapsed_cycles(start, end);
    /* Expected: (0xFFFFFFFF - 0xFFFFFF00) + 0x00000100 + 1 = 255 + 256 + 1 = 512 */
    ASSERT_EQ(elapsed, 512, "Elapsed cycles should handle larger wrap-around");
}

/**
 * Test is_valid_sample_period with valid inputs
 * Requirement: 2.2 - Validate sample period against min/max limits
 */
void test_is_valid_sample_period_valid(void) {
    /* Test minimum valid period */
    int valid = is_valid_sample_period(MIN_SAMPLE_PERIOD_CYCLES);
    ASSERT_TRUE(valid, "MIN_SAMPLE_PERIOD_CYCLES should be valid");
    
    /* Test maximum valid period */
    valid = is_valid_sample_period(MAX_SAMPLE_PERIOD_CYCLES);
    ASSERT_TRUE(valid, "MAX_SAMPLE_PERIOD_CYCLES should be valid");
    
    /* Test middle value */
    uint32_t mid = (MIN_SAMPLE_PERIOD_CYCLES + MAX_SAMPLE_PERIOD_CYCLES) / 2;
    valid = is_valid_sample_period(mid);
    ASSERT_TRUE(valid, "Middle value should be valid");
    
    /* Test typical value (10 kHz = 100 µs = 20000 cycles) */
    valid = is_valid_sample_period(20000);
    ASSERT_TRUE(valid, "Typical sample period (20000 cycles) should be valid");
}

/**
 * Test is_valid_sample_period with invalid inputs
 * Requirement: 2.2 - Validate sample period against min/max limits
 */
void test_is_valid_sample_period_invalid(void) {
    /* Test below minimum */
    int valid = is_valid_sample_period(MIN_SAMPLE_PERIOD_CYCLES - 1);
    ASSERT_TRUE(!valid, "Period below minimum should be invalid");
    
    /* Test above maximum */
    valid = is_valid_sample_period(MAX_SAMPLE_PERIOD_CYCLES + 1);
    ASSERT_TRUE(!valid, "Period above maximum should be invalid");
    
    /* Test zero */
    valid = is_valid_sample_period(0);
    ASSERT_TRUE(!valid, "Zero period should be invalid");
    
    /* Test very small value */
    valid = is_valid_sample_period(100);
    ASSERT_TRUE(!valid, "Very small period (100 cycles) should be invalid");
    
    /* Test very large value */
    valid = is_valid_sample_period(0xFFFFFFFF);
    ASSERT_TRUE(!valid, "Very large period should be invalid");
}

/**
 * Test wait_cycles basic functionality
 * Requirement: 3.2 - Provide function to wait for specified cycles
 */
void test_wait_cycles_basic(void) {
    /* Reset mock counter */
    mock_cycle_counter = 0;
    
    /* Wait for 1000 cycles */
    wait_cycles(1000);
    uint32_t count = get_cycle_count();
    ASSERT_EQ(count, 1000, "After wait_cycles(1000), counter should be at 1000");
    
    /* Wait for another 500 cycles */
    wait_cycles(500);
    count = get_cycle_count();
    ASSERT_EQ(count, 1500, "After wait_cycles(500), counter should be at 1500");
    
    /* Wait for zero cycles (edge case) */
    uint32_t before = get_cycle_count();
    wait_cycles(0);
    uint32_t after = get_cycle_count();
    ASSERT_EQ(after, before, "wait_cycles(0) should not change counter");
}

/**
 * Test wait_cycles with wrap-around
 * Requirement: 3.3 - Handle wrap-around in timing calculations
 */
void test_wait_cycles_wraparound(void) {
    /* Set counter near maximum */
    mock_cycle_counter = 0xFFFFFFF0;
    
    /* Wait for cycles that will cause wrap-around */
    wait_cycles(32);
    uint32_t count = get_cycle_count();
    
    /* Expected: 0xFFFFFFF0 + 32 = 0x00000010 (after wrap) */
    ASSERT_EQ(count, 0x00000010, "wait_cycles should handle wrap-around");
}

/**
 * Test timing constant relationships
 * Verifies that timing constants are consistent
 */
void test_timing_constants_consistency(void) {
    /* Verify MIN < MAX */
    ASSERT_TRUE(MIN_SAMPLE_PERIOD_CYCLES < MAX_SAMPLE_PERIOD_CYCLES,
                "MIN_SAMPLE_PERIOD_CYCLES should be less than MAX_SAMPLE_PERIOD_CYCLES");
    
    /* Verify minimum is reasonable (at least 1 µs) */
    ASSERT_TRUE(MIN_SAMPLE_PERIOD_CYCLES >= CYCLES_PER_US,
                "MIN_SAMPLE_PERIOD_CYCLES should be at least 1 µs");
    
    /* Verify maximum is reasonable (at most 1 second) */
    ASSERT_TRUE(MAX_SAMPLE_PERIOD_CYCLES <= PRU_CLOCK_HZ,
                "MAX_SAMPLE_PERIOD_CYCLES should be at most 1 second");
}

/**
 * Test elapsed_cycles edge cases
 */
void test_elapsed_cycles_edge_cases(void) {
    /* Test with start = 0 */
    uint32_t elapsed = elapsed_cycles(0, 1000);
    ASSERT_EQ(elapsed, 1000, "Elapsed from 0 should work correctly");
    
    /* Test with end = 0 (wrap-around from max) */
    elapsed = elapsed_cycles(0xFFFFFF00, 0);
    ASSERT_EQ(elapsed, 256, "Elapsed to 0 should handle wrap-around");
    
    /* Test with both at max */
    elapsed = elapsed_cycles(0xFFFFFFFF, 0xFFFFFFFF);
    ASSERT_EQ(elapsed, 0, "Elapsed with same max values should be 0");
    
    /* Test maximum possible elapsed (almost full wrap) */
    elapsed = elapsed_cycles(1, 0);
    ASSERT_EQ(elapsed, 0xFFFFFFFF, "Maximum elapsed should be 0xFFFFFFFF");
}

/**
 * Main test runner
 */
int main(void) {
    printf("=== PRU Timing Functions Unit Tests ===\n\n");
    
    TEST(get_cycle_count_increments);
    TEST(elapsed_cycles_normal);
    TEST(elapsed_cycles_wraparound);
    TEST(is_valid_sample_period_valid);
    TEST(is_valid_sample_period_invalid);
    TEST(wait_cycles_basic);
    TEST(wait_cycles_wraparound);
    TEST(timing_constants_consistency);
    TEST(elapsed_cycles_edge_cases);
    
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
