/**
 * Unit tests for shared memory layout
 * 
 * Tests the structure definitions, constants, and memory layout
 * of the PRU-Linux shared memory interface.
 */

#include <stdio.h>
#include <stdint.h>
#include <stddef.h>
#include <assert.h>
#include "../../include/shm_layout.h"

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
 * Test that magic number is at offset 0
 * Requirement: 1.1 - Magic number field at offset 0
 */
void test_magic_at_offset_0(void) {
    pru_shared_memory_t shm;
    
    /* Verify magic field is at offset 0 */
    size_t magic_offset = offsetof(pru_shared_memory_t, magic);
    ASSERT_EQ(magic_offset, 0, "Magic number should be at offset 0");
    
    /* Verify magic field size */
    ASSERT_EQ(sizeof(shm.magic), sizeof(uint32_t), 
              "Magic field should be 4 bytes");
}

/**
 * Test field accessibility and sizes
 * Requirements: 1.2, 1.3, 1.4, 1.5
 */
void test_field_accessibility_and_sizes(void) {
    pru_shared_memory_t shm;
    
    /* Test header fields */
    ASSERT_EQ(sizeof(shm.magic), sizeof(uint32_t), 
              "magic field size");
    ASSERT_EQ(sizeof(shm.version), sizeof(uint32_t), 
              "version field size");
    
    /* Test configuration fields */
    ASSERT_EQ(sizeof(shm.sample_period_cycles), sizeof(uint32_t), 
              "sample_period_cycles field size");
    ASSERT_EQ(sizeof(shm.channel_mask), sizeof(uint32_t), 
              "channel_mask field size");
    ASSERT_EQ(sizeof(shm.block_size), sizeof(uint32_t), 
              "block_size field size");
    ASSERT_EQ(sizeof(shm.num_blocks), sizeof(uint32_t), 
              "num_blocks field size");
    
    /* Test status fields */
    ASSERT_EQ(sizeof(shm.write_block_idx), sizeof(uint32_t), 
              "write_block_idx field size");
    ASSERT_EQ(sizeof(shm.error_flags), sizeof(uint32_t), 
              "error_flags field size");
    ASSERT_EQ(sizeof(shm.sample_count), sizeof(uint32_t), 
              "sample_count field size");
    
    /* Test field accessibility by writing and reading */
    shm.magic = SHM_MAGIC;
    ASSERT_EQ(shm.magic, SHM_MAGIC, "magic field read/write");
    
    shm.version = SHM_VERSION;
    ASSERT_EQ(shm.version, SHM_VERSION, "version field read/write");
    
    shm.sample_period_cycles = 1000;
    ASSERT_EQ(shm.sample_period_cycles, 1000, 
              "sample_period_cycles field read/write");
    
    shm.channel_mask = 0xFF;
    ASSERT_EQ(shm.channel_mask, 0xFF, "channel_mask field read/write");
    
    shm.block_size = 256;
    ASSERT_EQ(shm.block_size, 256, "block_size field read/write");
    
    shm.num_blocks = 4;
    ASSERT_EQ(shm.num_blocks, 4, "num_blocks field read/write");
    
    shm.write_block_idx = 0;
    ASSERT_EQ(shm.write_block_idx, 0, "write_block_idx field read/write");
    
    shm.error_flags = 0;
    ASSERT_EQ(shm.error_flags, 0, "error_flags field read/write");
    
    shm.sample_count = 0;
    ASSERT_EQ(shm.sample_count, 0, "sample_count field read/write");
}

/**
 * Test structure alignment
 * Ensures structures are properly aligned for efficient access
 */
void test_structure_alignment(void) {
    /* Test that structure sizes are reasonable */
    size_t shm_size = sizeof(pru_shared_memory_t);
    ASSERT_TRUE(shm_size > 0, "pru_shared_memory_t has non-zero size");
    ASSERT_TRUE(shm_size % 4 == 0, 
                "pru_shared_memory_t is 4-byte aligned");
    
    size_t desc_size = sizeof(block_descriptor_t);
    ASSERT_TRUE(desc_size > 0, "block_descriptor_t has non-zero size");
    ASSERT_TRUE(desc_size % 4 == 0, 
                "block_descriptor_t is 4-byte aligned");
    
    /* Test block descriptor fields */
    block_descriptor_t desc;
    ASSERT_EQ(sizeof(desc.timestamp_cycles), sizeof(uint32_t), 
              "timestamp_cycles field size");
    ASSERT_EQ(sizeof(desc.num_samples), sizeof(uint16_t), 
              "num_samples field size");
    ASSERT_EQ(sizeof(desc.flags), sizeof(uint16_t), 
              "flags field size");
    
    /* Test field accessibility */
    desc.timestamp_cycles = 12345;
    ASSERT_EQ(desc.timestamp_cycles, 12345, 
              "timestamp_cycles field read/write");
    
    desc.num_samples = 256;
    ASSERT_EQ(desc.num_samples, 256, "num_samples field read/write");
    
    desc.flags = 0x1234;
    ASSERT_EQ(desc.flags, 0x1234, "flags field read/write");
}

/**
 * Test constant definitions
 * Verifies all required constants are defined with correct values
 */
void test_constants(void) {
    /* Test magic number */
    ASSERT_EQ(SHM_MAGIC, 0xDEADBEEF, "SHM_MAGIC value");
    
    /* Test version */
    ASSERT_EQ(SHM_VERSION, 1, "SHM_VERSION value");
    
    /* Test ADC constants */
    ASSERT_EQ(MAX_CHANNELS, 8, "MAX_CHANNELS value");
    ASSERT_EQ(DEFAULT_BLOCK_SIZE, 256, "DEFAULT_BLOCK_SIZE value");
    ASSERT_EQ(DEFAULT_NUM_BLOCKS, 4, "DEFAULT_NUM_BLOCKS value");
    
    /* Test error flags are unique bit positions */
    ASSERT_EQ(ERROR_INVALID_MAGIC, (1 << 0), "ERROR_INVALID_MAGIC value");
    ASSERT_EQ(ERROR_BUSY_TIMEOUT, (1 << 1), "ERROR_BUSY_TIMEOUT value");
    ASSERT_EQ(ERROR_INVALID_CONFIG, (1 << 2), "ERROR_INVALID_CONFIG value");
    ASSERT_EQ(ERROR_BUFFER_OVERRUN, (1 << 3), "ERROR_BUFFER_OVERRUN value");
    
    /* Verify error flags are mutually exclusive */
    uint32_t all_errors = ERROR_INVALID_MAGIC | ERROR_BUSY_TIMEOUT | 
                          ERROR_INVALID_CONFIG | ERROR_BUFFER_OVERRUN;
    ASSERT_EQ(all_errors, 0x0F, "Error flags are mutually exclusive");
}

/**
 * Test memory layout calculation
 * Verifies the ring buffer layout can be calculated correctly
 */
void test_memory_layout(void) {
    /* Calculate expected sizes */
    size_t header_size = sizeof(pru_shared_memory_t);
    size_t desc_size = sizeof(block_descriptor_t);
    
    /* Example: 256 samples, 3 channels enabled, 4 blocks */
    uint32_t block_size = 256;
    uint32_t num_channels = 3;
    uint32_t num_blocks = 4;
    
    size_t data_per_block = block_size * num_channels * sizeof(uint16_t);
    size_t total_per_block = desc_size + data_per_block;
    size_t total_size = header_size + (num_blocks * total_per_block);
    
    /* Verify calculations are reasonable */
    ASSERT_TRUE(header_size > 0, "Header size is positive");
    ASSERT_TRUE(desc_size > 0, "Descriptor size is positive");
    ASSERT_TRUE(data_per_block > 0, "Data per block is positive");
    ASSERT_TRUE(total_size > header_size, "Total size includes header");
    
    /* Expected: header (36 bytes) + 4 * (8 + 256*3*2) = 36 + 4 * 1544 = 6212 bytes */
    printf("  Memory layout: header=%zu, desc=%zu, data_per_block=%zu, "
           "total_per_block=%zu, total=%zu\n",
           header_size, desc_size, data_per_block, total_per_block, total_size);
}

/**
 * Main test runner
 */
int main(void) {
    printf("=== PRU Shared Memory Layout Unit Tests ===\n\n");
    
    TEST(magic_at_offset_0);
    TEST(field_accessibility_and_sizes);
    TEST(structure_alignment);
    TEST(constants);
    TEST(memory_layout);
    
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
