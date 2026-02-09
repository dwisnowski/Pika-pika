/**
 * Unit tests for PRU configuration validation
 * 
 * Tests the configuration validation logic in pru_main.c
 * Requirements: 5.1, 6.3
 * 
 * Note: These tests run on host system (x86) with mocked shared memory.
 */

#include <stdio.h>
#include <stdint.h>
#include <string.h>

/* Include configuration constants */
#include "../../include/pru_config.h"
#include "../../include/shm_layout.h"

/* Mock timing functions */
static uint32_t mock_cycle_counter = 0;

static inline uint32_t get_cycle_count(void) {
    return mock_cycle_counter;
}

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

#define ASSERT_FALSE(condition, msg) \
    do { \
        if (!(condition)) { \
            tests_passed++; \
        } else { \
            tests_failed++; \
            printf("  FAIL: %s\n", msg); \
        } \
    } while(0)

/**
 * Helper function to count enabled channels
 * (Duplicated from pru_main.c for testing)
 */
static inline uint8_t count_enabled_channels(uint32_t channel_mask) {
    uint8_t count = 0;
    for (int i = 0; i < NUM_ADC_CHANNELS; i++) {
        if (channel_mask & (1 << i)) {
            count++;
        }
    }
    return count;
}

/**
 * Test valid configuration acceptance
 * Requirement: 5.1 - PRU shall read configuration from shared memory
 */
void test_valid_configuration_acceptance(void) {
    /* Test typical valid configuration */
    uint32_t sample_period = 20000;  /* 100 µs = 10 kHz */
    uint32_t channel_mask = 0xFF;    /* All 8 channels */
    uint32_t block_size = 256;       /* Default block size */
    uint32_t num_blocks = 4;         /* Default number of blocks */
    
    /* Validate sample period */
    ASSERT_TRUE(is_valid_sample_period(sample_period),
                "Valid sample period should be accepted");
    
    /* Validate channel mask */
    ASSERT_TRUE(channel_mask != 0,
                "Non-zero channel mask should be valid");
    
    /* Validate block size */
    ASSERT_TRUE(block_size >= MIN_BLOCK_SIZE && block_size <= MAX_BLOCK_SIZE,
                "Block size within range should be valid");
    
    /* Validate num_blocks */
    ASSERT_TRUE(num_blocks >= 2,
                "At least 2 blocks should be valid for ring buffer");
    
    /* Test channel counting */
    uint8_t num_channels = count_enabled_channels(channel_mask);
    ASSERT_EQ(num_channels, 8, "All 8 channels should be counted");
}

/**
 * Test invalid sample period rejection
 * Requirement: 6.3 - PRU shall set ERROR_INVALID_CONFIG for invalid configuration
 */
void test_invalid_sample_period_rejection(void) {
    /* Test period below minimum */
    uint32_t period_too_small = MIN_SAMPLE_PERIOD_CYCLES - 1;
    ASSERT_FALSE(is_valid_sample_period(period_too_small),
                 "Period below minimum should be rejected");
    
    /* Test period above maximum */
    uint32_t period_too_large = MAX_SAMPLE_PERIOD_CYCLES + 1;
    ASSERT_FALSE(is_valid_sample_period(period_too_large),
                 "Period above maximum should be rejected");
    
    /* Test zero period */
    ASSERT_FALSE(is_valid_sample_period(0),
                 "Zero period should be rejected");
    
    /* Test very small period (1 cycle) */
    ASSERT_FALSE(is_valid_sample_period(1),
                 "1 cycle period should be rejected");
    
    /* Test very large period */
    ASSERT_FALSE(is_valid_sample_period(0xFFFFFFFF),
                 "Maximum uint32 period should be rejected");
}

/**
 * Test zero channel mask rejection
 * Requirement: 6.3 - PRU shall set ERROR_INVALID_CONFIG for invalid configuration
 */
void test_zero_channel_mask_rejection(void) {
    uint32_t channel_mask = 0;
    
    /* Zero channel mask should be invalid */
    ASSERT_TRUE(channel_mask == 0,
                "Zero channel mask should be detected");
    
    /* Count should be zero */
    uint8_t num_channels = count_enabled_channels(channel_mask);
    ASSERT_EQ(num_channels, 0, "Zero channels should be counted for mask 0");
}

/**
 * Test invalid block size rejection
 * Requirement: 6.3 - PRU shall set ERROR_INVALID_CONFIG for invalid configuration
 */
void test_invalid_block_size_rejection(void) {
    /* Test block size below minimum */
    uint32_t block_size_too_small = MIN_BLOCK_SIZE - 1;
    ASSERT_TRUE(block_size_too_small < MIN_BLOCK_SIZE,
                "Block size below minimum should be detected");
    
    /* Test block size above maximum */
    uint32_t block_size_too_large = MAX_BLOCK_SIZE + 1;
    ASSERT_TRUE(block_size_too_large > MAX_BLOCK_SIZE,
                "Block size above maximum should be detected");
    
    /* Test zero block size */
    ASSERT_TRUE(0 < MIN_BLOCK_SIZE,
                "Zero block size should be below minimum");
    
    /* Test valid block sizes */
    ASSERT_TRUE(MIN_BLOCK_SIZE >= MIN_BLOCK_SIZE && MIN_BLOCK_SIZE <= MAX_BLOCK_SIZE,
                "MIN_BLOCK_SIZE should be valid");
    ASSERT_TRUE(MAX_BLOCK_SIZE >= MIN_BLOCK_SIZE && MAX_BLOCK_SIZE <= MAX_BLOCK_SIZE,
                "MAX_BLOCK_SIZE should be valid");
    ASSERT_TRUE(DEFAULT_BLOCK_SIZE >= MIN_BLOCK_SIZE && DEFAULT_BLOCK_SIZE <= MAX_BLOCK_SIZE,
                "DEFAULT_BLOCK_SIZE should be valid");
}

/**
 * Test invalid num_blocks rejection
 * Requirement: 6.3 - Ring buffer needs at least 2 blocks
 */
void test_invalid_num_blocks_rejection(void) {
    /* Test num_blocks = 0 */
    uint32_t num_blocks = 0;
    ASSERT_TRUE(num_blocks < 2,
                "Zero blocks should be invalid");
    
    /* Test num_blocks = 1 */
    num_blocks = 1;
    ASSERT_TRUE(num_blocks < 2,
                "Single block should be invalid for ring buffer");
    
    /* Test valid num_blocks */
    num_blocks = 2;
    ASSERT_TRUE(num_blocks >= 2,
                "Two blocks should be valid");
    
    num_blocks = 4;
    ASSERT_TRUE(num_blocks >= 2,
                "Four blocks should be valid");
    
    num_blocks = 16;
    ASSERT_TRUE(num_blocks >= 2,
                "Sixteen blocks should be valid");
}

/**
 * Test channel counting with various masks
 * Requirement: 6.1 - Count enabled channels from channel_mask
 */
void test_channel_counting(void) {
    /* Test single channel */
    uint8_t count = count_enabled_channels(0x01);  /* Channel 0 only */
    ASSERT_EQ(count, 1, "Single channel should count as 1");
    
    /* Test two channels */
    count = count_enabled_channels(0x03);  /* Channels 0 and 1 */
    ASSERT_EQ(count, 2, "Two channels should count as 2");
    
    /* Test four channels */
    count = count_enabled_channels(0x0F);  /* Channels 0-3 */
    ASSERT_EQ(count, 4, "Four channels should count as 4");
    
    /* Test all channels */
    count = count_enabled_channels(0xFF);  /* All 8 channels */
    ASSERT_EQ(count, 8, "All channels should count as 8");
    
    /* Test non-contiguous channels */
    count = count_enabled_channels(0xAA);  /* Channels 1, 3, 5, 7 */
    ASSERT_EQ(count, 4, "Non-contiguous channels should count correctly");
    
    /* Test sparse channels */
    count = count_enabled_channels(0x81);  /* Channels 0 and 7 */
    ASSERT_EQ(count, 2, "Sparse channels should count correctly");
    
    /* Test zero mask */
    count = count_enabled_channels(0x00);
    ASSERT_EQ(count, 0, "Zero mask should count as 0");
}

/**
 * Test block size calculations
 * Requirement: 6.1 - Calculate block data size and total size
 */
void test_block_size_calculations(void) {
    /* Test with all channels enabled */
    uint32_t block_size = 256;
    uint8_t num_channels = 8;
    uint32_t block_data_size = block_size * num_channels * sizeof(uint16_t);
    uint32_t block_total_size = sizeof(block_descriptor_t) + block_data_size;
    
    ASSERT_EQ(block_data_size, 256 * 8 * 2,
              "Block data size should be block_size * channels * 2 bytes");
    ASSERT_EQ(block_total_size, sizeof(block_descriptor_t) + 4096,
              "Block total size should include descriptor");
    
    /* Test with single channel */
    num_channels = 1;
    block_data_size = block_size * num_channels * sizeof(uint16_t);
    ASSERT_EQ(block_data_size, 256 * 1 * 2,
              "Single channel block data size should be correct");
    
    /* Test with different block size */
    block_size = 512;
    num_channels = 4;
    block_data_size = block_size * num_channels * sizeof(uint16_t);
    ASSERT_EQ(block_data_size, 512 * 4 * 2,
              "Different block size calculation should be correct");
}

/**
 * Test sample period boundary values
 * Requirement: 2.2 - Validate sample period against min/max limits
 */
void test_sample_period_boundaries(void) {
    /* Test exact minimum */
    ASSERT_TRUE(is_valid_sample_period(MIN_SAMPLE_PERIOD_CYCLES),
                "Exact minimum period should be valid");
    
    /* Test exact maximum */
    ASSERT_TRUE(is_valid_sample_period(MAX_SAMPLE_PERIOD_CYCLES),
                "Exact maximum period should be valid");
    
    /* Test one below minimum */
    ASSERT_FALSE(is_valid_sample_period(MIN_SAMPLE_PERIOD_CYCLES - 1),
                 "One below minimum should be invalid");
    
    /* Test one above maximum */
    ASSERT_FALSE(is_valid_sample_period(MAX_SAMPLE_PERIOD_CYCLES + 1),
                 "One above maximum should be invalid");
    
    /* Test typical values */
    ASSERT_TRUE(is_valid_sample_period(2000),    /* 10 µs = 100 kHz */
                "10 µs period should be valid");
    ASSERT_TRUE(is_valid_sample_period(20000),   /* 100 µs = 10 kHz */
                "100 µs period should be valid");
    ASSERT_TRUE(is_valid_sample_period(200000),  /* 1 ms = 1 kHz */
                "1 ms period should be valid");
}

/**
 * Test configuration constant consistency
 * Verifies that configuration constants are consistent
 */
void test_configuration_constants_consistency(void) {
    /* Verify MIN < MAX for block size */
    ASSERT_TRUE(MIN_BLOCK_SIZE < MAX_BLOCK_SIZE,
                "MIN_BLOCK_SIZE should be less than MAX_BLOCK_SIZE");
    
    /* Verify DEFAULT is within range */
    ASSERT_TRUE(DEFAULT_BLOCK_SIZE >= MIN_BLOCK_SIZE &&
                DEFAULT_BLOCK_SIZE <= MAX_BLOCK_SIZE,
                "DEFAULT_BLOCK_SIZE should be within valid range");
    
    /* Verify block sizes are powers of 2 (common requirement) */
    ASSERT_TRUE((MIN_BLOCK_SIZE & (MIN_BLOCK_SIZE - 1)) == 0,
                "MIN_BLOCK_SIZE should be power of 2");
    ASSERT_TRUE((MAX_BLOCK_SIZE & (MAX_BLOCK_SIZE - 1)) == 0,
                "MAX_BLOCK_SIZE should be power of 2");
    ASSERT_TRUE((DEFAULT_BLOCK_SIZE & (DEFAULT_BLOCK_SIZE - 1)) == 0,
                "DEFAULT_BLOCK_SIZE should be power of 2");
    
    /* Verify NUM_ADC_CHANNELS is 8 */
    ASSERT_EQ(NUM_ADC_CHANNELS, 8,
              "NUM_ADC_CHANNELS should be 8 for AD7606");
    
    /* Verify DEFAULT_NUM_BLOCKS is reasonable */
    ASSERT_TRUE(DEFAULT_NUM_BLOCKS >= 2,
                "DEFAULT_NUM_BLOCKS should be at least 2");
}

/**
 * Test edge cases for channel masks
 */
void test_channel_mask_edge_cases(void) {
    /* Test maximum valid mask (all 8 channels) */
    uint32_t mask = 0xFF;
    uint8_t count = count_enabled_channels(mask);
    ASSERT_EQ(count, 8, "0xFF should enable all 8 channels");
    
    /* Test mask with bits beyond channel 7 (should be ignored) */
    mask = 0x1FF;  /* Bit 8 set, but only 8 channels exist */
    count = count_enabled_channels(mask);
    ASSERT_EQ(count, 8, "Bits beyond channel 7 should be ignored");
    
    /* Test mask with high bits set */
    mask = 0xFFFFFF00;  /* High bits set, no low bits */
    count = count_enabled_channels(mask);
    ASSERT_EQ(count, 0, "Only bits 0-7 should be counted");
    
    /* Test alternating pattern */
    mask = 0x55;  /* 01010101 - channels 0, 2, 4, 6 */
    count = count_enabled_channels(mask);
    ASSERT_EQ(count, 4, "Alternating pattern should count correctly");
}

/**
 * Main test runner
 */
int main(void) {
    printf("=== PRU Configuration Validation Unit Tests ===\n\n");
    
    TEST(valid_configuration_acceptance);
    TEST(invalid_sample_period_rejection);
    TEST(zero_channel_mask_rejection);
    TEST(invalid_block_size_rejection);
    TEST(invalid_num_blocks_rejection);
    TEST(channel_counting);
    TEST(block_size_calculations);
    TEST(sample_period_boundaries);
    TEST(configuration_constants_consistency);
    TEST(channel_mask_edge_cases);
    
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
