/**
 * Unit tests for PRU configuration constants
 * 
 * Tests the configuration constants defined in pru_config.h
 * Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
 */

#include <stdio.h>
#include <stdint.h>
#include <assert.h>
#include "../../include/pru_config.h"

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
 * Test PRU hardware constants
 * Requirement: 2.1 - PRU clock frequency constant
 */
void test_pru_hardware_constants(void) {
    /* Test PRU clock frequency (200 MHz) */
    ASSERT_EQ(PRU_CLOCK_HZ, 200000000, "PRU_CLOCK_HZ should be 200 MHz");
    
    /* Test cycles per microsecond calculation */
    ASSERT_EQ(CYCLES_PER_US, 200, "CYCLES_PER_US should be 200");
    
    /* Verify the calculation is correct */
    uint32_t expected_cycles_per_us = PRU_CLOCK_HZ / 1000000;
    ASSERT_EQ(CYCLES_PER_US, expected_cycles_per_us, 
              "CYCLES_PER_US calculation should be correct");
}

/**
 * Test timing constraint constants
 * Requirement: 2.2 - Minimum and maximum sample period limits
 */
void test_timing_constraints(void) {
    /* Test minimum sample period */
    ASSERT_EQ(MIN_SAMPLE_PERIOD_US, 10, 
              "MIN_SAMPLE_PERIOD_US should be 10 µs");
    
    /* Test maximum sample period */
    ASSERT_EQ(MAX_SAMPLE_PERIOD_US, 100000, 
              "MAX_SAMPLE_PERIOD_US should be 100 ms (100000 µs)");
    
    /* Test minimum sample period in cycles */
    uint32_t expected_min_cycles = MIN_SAMPLE_PERIOD_US * CYCLES_PER_US;
    ASSERT_EQ(MIN_SAMPLE_PERIOD_CYCLES, expected_min_cycles, 
              "MIN_SAMPLE_PERIOD_CYCLES calculation");
    ASSERT_EQ(MIN_SAMPLE_PERIOD_CYCLES, 2000, 
              "MIN_SAMPLE_PERIOD_CYCLES should be 2000 cycles");
    
    /* Test maximum sample period in cycles */
    uint32_t expected_max_cycles = MAX_SAMPLE_PERIOD_US * CYCLES_PER_US;
    ASSERT_EQ(MAX_SAMPLE_PERIOD_CYCLES, expected_max_cycles, 
              "MAX_SAMPLE_PERIOD_CYCLES calculation");
    ASSERT_EQ(MAX_SAMPLE_PERIOD_CYCLES, 20000000, 
              "MAX_SAMPLE_PERIOD_CYCLES should be 20000000 cycles");
    
    /* Verify min < max */
    ASSERT_TRUE(MIN_SAMPLE_PERIOD_CYCLES < MAX_SAMPLE_PERIOD_CYCLES,
                "MIN_SAMPLE_PERIOD_CYCLES should be less than MAX_SAMPLE_PERIOD_CYCLES");
}

/**
 * Test AD7606 timing constants
 * Requirement: 2.4 - AD7606 timing constants
 */
void test_ad7606_timing(void) {
    /* Test CONVST pulse width (250 ns minimum = 50 cycles @ 200 MHz) */
    ASSERT_EQ(CONVST_PULSE_CYCLES, 50, 
              "CONVST_PULSE_CYCLES should be 50 cycles (250 ns)");
    
    /* Verify CONVST pulse meets minimum timing (>= 250 ns) */
    uint32_t convst_ns = (CONVST_PULSE_CYCLES * 1000) / CYCLES_PER_US;
    ASSERT_TRUE(convst_ns >= 250, 
                "CONVST pulse should be at least 250 ns");
    
    /* Test BUSY timeout (5 µs) */
    ASSERT_EQ(BUSY_TIMEOUT_CYCLES, 1000, 
              "BUSY_TIMEOUT_CYCLES should be 1000 cycles (5 µs)");
    
    /* Verify BUSY timeout is reasonable */
    uint32_t busy_timeout_us = BUSY_TIMEOUT_CYCLES / CYCLES_PER_US;
    ASSERT_EQ(busy_timeout_us, 5, 
              "BUSY timeout should be 5 µs");
    
    /* Test typical conversion time */
    ASSERT_EQ(CONVERSION_TIME_CYCLES, 800, 
              "CONVERSION_TIME_CYCLES should be 800 cycles (~4 µs)");
    
    /* Verify conversion time is less than timeout */
    ASSERT_TRUE(CONVERSION_TIME_CYCLES < BUSY_TIMEOUT_CYCLES,
                "Conversion time should be less than timeout");
}

/**
 * Test PRU pin assignments
 * Requirement: 2.4 - Pin assignments
 */
void test_pin_assignments(void) {
    /* Test CONVST pin (R30.0 output) */
    ASSERT_EQ(PIN_CONVST, 0, "PIN_CONVST should be pin 0");
    
    /* Test BUSY pin (R31.0 input) */
    ASSERT_EQ(PIN_BUSY, 0, "PIN_BUSY should be pin 0");
    
    /* Test data base pin (R31.1-16 inputs) */
    ASSERT_EQ(PIN_DATA_BASE, 1, "PIN_DATA_BASE should be pin 1");
    
    /* Verify data pins don't overlap with control pins */
    ASSERT_TRUE(PIN_DATA_BASE > PIN_BUSY, 
                "Data pins should start after BUSY pin");
}

/**
 * Test channel configuration constants
 * Requirement: 2.3 - Number of ADC channels
 */
void test_channel_configuration(void) {
    /* Test number of ADC channels */
    ASSERT_EQ(NUM_ADC_CHANNELS, 8, 
              "NUM_ADC_CHANNELS should be 8");
    
    /* Test ADC resolution */
    ASSERT_EQ(ADC_RESOLUTION_BITS, 16, 
              "ADC_RESOLUTION_BITS should be 16");
    
    /* Verify channel count is reasonable */
    ASSERT_TRUE(NUM_ADC_CHANNELS > 0 && NUM_ADC_CHANNELS <= 16,
                "NUM_ADC_CHANNELS should be between 1 and 16");
}

/**
 * Test block size constants
 * Requirement: 2.5 - Block size constraints
 */
void test_block_size_constants(void) {
    /* Test minimum block size */
    ASSERT_EQ(MIN_BLOCK_SIZE, 64, 
              "MIN_BLOCK_SIZE should be 64");
    
    /* Test maximum block size */
    ASSERT_EQ(MAX_BLOCK_SIZE, 1024, 
              "MAX_BLOCK_SIZE should be 1024");
    
    /* Test default block size */
    ASSERT_EQ(DEFAULT_BLOCK_SIZE, 256, 
              "DEFAULT_BLOCK_SIZE should be 256");
    
    /* Test default number of blocks */
    ASSERT_EQ(DEFAULT_NUM_BLOCKS, 4, 
              "DEFAULT_NUM_BLOCKS should be 4");
    
    /* Verify min < default < max */
    ASSERT_TRUE(MIN_BLOCK_SIZE <= DEFAULT_BLOCK_SIZE,
                "MIN_BLOCK_SIZE should be <= DEFAULT_BLOCK_SIZE");
    ASSERT_TRUE(DEFAULT_BLOCK_SIZE <= MAX_BLOCK_SIZE,
                "DEFAULT_BLOCK_SIZE should be <= MAX_BLOCK_SIZE");
    
    /* Verify all block sizes are powers of 2 */
    ASSERT_TRUE((MIN_BLOCK_SIZE & (MIN_BLOCK_SIZE - 1)) == 0,
                "MIN_BLOCK_SIZE should be power of 2");
    ASSERT_TRUE((MAX_BLOCK_SIZE & (MAX_BLOCK_SIZE - 1)) == 0,
                "MAX_BLOCK_SIZE should be power of 2");
    ASSERT_TRUE((DEFAULT_BLOCK_SIZE & (DEFAULT_BLOCK_SIZE - 1)) == 0,
                "DEFAULT_BLOCK_SIZE should be power of 2");
}

/**
 * Test error flag definitions
 * Requirement: 2.4 - Error flag bit definitions
 */
void test_error_flags(void) {
    /* Test individual error flags */
    ASSERT_EQ(ERROR_INVALID_MAGIC, (1 << 0), 
              "ERROR_INVALID_MAGIC should be bit 0");
    ASSERT_EQ(ERROR_BUSY_TIMEOUT, (1 << 1), 
              "ERROR_BUSY_TIMEOUT should be bit 1");
    ASSERT_EQ(ERROR_INVALID_CONFIG, (1 << 2), 
              "ERROR_INVALID_CONFIG should be bit 2");
    ASSERT_EQ(ERROR_BUFFER_OVERRUN, (1 << 3), 
              "ERROR_BUFFER_OVERRUN should be bit 3");
    
    /* Verify error flags are mutually exclusive (unique bits) */
    uint32_t all_errors = ERROR_INVALID_MAGIC | ERROR_BUSY_TIMEOUT | 
                          ERROR_INVALID_CONFIG | ERROR_BUFFER_OVERRUN;
    ASSERT_EQ(all_errors, 0x0F, 
              "Error flags should be mutually exclusive");
    
    /* Verify no overlap between error flags */
    ASSERT_EQ(ERROR_INVALID_MAGIC & ERROR_BUSY_TIMEOUT, 0,
              "ERROR_INVALID_MAGIC and ERROR_BUSY_TIMEOUT should not overlap");
    ASSERT_EQ(ERROR_INVALID_MAGIC & ERROR_INVALID_CONFIG, 0,
              "ERROR_INVALID_MAGIC and ERROR_INVALID_CONFIG should not overlap");
    ASSERT_EQ(ERROR_INVALID_MAGIC & ERROR_BUFFER_OVERRUN, 0,
              "ERROR_INVALID_MAGIC and ERROR_BUFFER_OVERRUN should not overlap");
    ASSERT_EQ(ERROR_BUSY_TIMEOUT & ERROR_INVALID_CONFIG, 0,
              "ERROR_BUSY_TIMEOUT and ERROR_INVALID_CONFIG should not overlap");
    ASSERT_EQ(ERROR_BUSY_TIMEOUT & ERROR_BUFFER_OVERRUN, 0,
              "ERROR_BUSY_TIMEOUT and ERROR_BUFFER_OVERRUN should not overlap");
    ASSERT_EQ(ERROR_INVALID_CONFIG & ERROR_BUFFER_OVERRUN, 0,
              "ERROR_INVALID_CONFIG and ERROR_BUFFER_OVERRUN should not overlap");
}

/**
 * Test timing constant calculations
 * Verifies that derived constants are calculated correctly
 */
void test_timing_calculations(void) {
    /* Test that cycle calculations are consistent */
    uint32_t min_cycles_from_us = MIN_SAMPLE_PERIOD_US * CYCLES_PER_US;
    ASSERT_EQ(MIN_SAMPLE_PERIOD_CYCLES, min_cycles_from_us,
              "MIN_SAMPLE_PERIOD_CYCLES should match calculation from microseconds");
    
    uint32_t max_cycles_from_us = MAX_SAMPLE_PERIOD_US * CYCLES_PER_US;
    ASSERT_EQ(MAX_SAMPLE_PERIOD_CYCLES, max_cycles_from_us,
              "MAX_SAMPLE_PERIOD_CYCLES should match calculation from microseconds");
    
    /* Test that CYCLES_PER_US is correct */
    ASSERT_EQ(PRU_CLOCK_HZ / 1000000, CYCLES_PER_US,
              "CYCLES_PER_US should equal PRU_CLOCK_HZ / 1000000");
    
    /* Verify timing ranges make sense */
    /* Min: 10 µs = 100 kHz max sample rate */
    uint32_t max_sample_rate_khz = 1000 / MIN_SAMPLE_PERIOD_US;
    ASSERT_EQ(max_sample_rate_khz, 100, 
              "Maximum sample rate should be 100 kHz");
    
    /* Max: 100 ms = 10 Hz min sample rate */
    uint32_t min_sample_rate_hz = 1000000 / MAX_SAMPLE_PERIOD_US;
    ASSERT_EQ(min_sample_rate_hz, 10, 
              "Minimum sample rate should be 10 Hz");
}

/**
 * Main test runner
 */
int main(void) {
    printf("=== PRU Configuration Constants Unit Tests ===\n\n");
    
    TEST(pru_hardware_constants);
    TEST(timing_constraints);
    TEST(ad7606_timing);
    TEST(pin_assignments);
    TEST(channel_configuration);
    TEST(block_size_constants);
    TEST(error_flags);
    TEST(timing_calculations);
    
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
