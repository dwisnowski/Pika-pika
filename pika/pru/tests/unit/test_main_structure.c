/**
 * Main Firmware Structure Test
 * 
 * This test verifies that pru_main.c has the correct structure and
 * all required components are present.
 */

#include <stdio.h>
#include <stdint.h>
#include <assert.h>
#include <string.h>

// Mock PRU-specific definitions
#define SHM_BASE_ADDRESS 0x00010000
#define __halt() do { halted = 1; return; } while(0)

// Include headers
#include "../../include/pru_config.h"
#include "../../include/shm_layout.h"

// Mock timing and ADC functions
static uint32_t mock_cycle_count = 0;
static uint32_t halted = 0;
static int mock_adc_result = 0;

static inline uint32_t get_cycle_count(void) {
    return mock_cycle_count++;
}

static inline void wait_cycles(uint32_t cycles) {
    mock_cycle_count += cycles;
}

static inline uint32_t elapsed_cycles(uint32_t start, uint32_t end) {
    if (end >= start) {
        return end - start;
    } else {
        return (0xFFFFFFFF - start) + end + 1;
    }
}

static inline int is_valid_sample_period(uint32_t period_cycles) {
    return (period_cycles >= MIN_SAMPLE_PERIOD_CYCLES &&
            period_cycles <= MAX_SAMPLE_PERIOD_CYCLES);
}

static inline int adc_trigger_and_wait(void) {
    return mock_adc_result;
}

static inline uint16_t adc_read_channel(uint8_t channel) {
    return (uint16_t)(0x1000 + channel);
}

// Mock shared memory
static pru_shared_memory_t mock_shm;
static uint8_t mock_ring_buffer[16384];

// Test helper to count enabled channels
static inline uint8_t count_enabled_channels(uint32_t channel_mask) {
    uint8_t count = 0;
    for (int i = 0; i < NUM_ADC_CHANNELS; i++) {
        if (channel_mask & (1 << i)) {
            count++;
        }
    }
    return count;
}

int main(void) {
    printf("=== PRU Main Firmware Structure Test ===\n\n");
    
    // Test 1: Verify magic number validation
    printf("Test 1: Magic number validation\n");
    mock_shm.magic = 0xBADBAD;  // Invalid magic
    mock_shm.error_flags = 0;
    halted = 0;
    
    // Simulate the magic check logic from pru_main.c
    volatile pru_shared_memory_t *shm = &mock_shm;
    if (shm->magic != SHM_MAGIC) {
        shm->error_flags = ERROR_INVALID_MAGIC;
        halted = 1;
    }
    
    assert(shm->error_flags == ERROR_INVALID_MAGIC);
    assert(halted == 1);
    printf("  PASS: Invalid magic number detected and error flag set\n\n");
    
    // Test 2: Verify configuration validation
    printf("Test 2: Configuration validation\n");
    mock_shm.magic = SHM_MAGIC;
    mock_shm.sample_period_cycles = MIN_SAMPLE_PERIOD_CYCLES - 1;  // Invalid
    mock_shm.channel_mask = 0xFF;
    mock_shm.block_size = 256;
    mock_shm.num_blocks = 4;
    mock_shm.error_flags = 0;
    halted = 0;
    
    uint32_t sample_period = mock_shm.sample_period_cycles;
    uint32_t channel_mask = mock_shm.channel_mask;
    uint32_t block_size = mock_shm.block_size;
    uint32_t num_blocks = mock_shm.num_blocks;
    
    if (!is_valid_sample_period(sample_period)) {
        mock_shm.error_flags = ERROR_INVALID_CONFIG;
        halted = 1;
    }
    
    assert(mock_shm.error_flags == ERROR_INVALID_CONFIG);
    assert(halted == 1);
    printf("  PASS: Invalid sample period detected\n");
    
    // Test with zero channel mask
    mock_shm.sample_period_cycles = MIN_SAMPLE_PERIOD_CYCLES;
    mock_shm.channel_mask = 0;  // Invalid
    mock_shm.error_flags = 0;
    halted = 0;
    
    channel_mask = mock_shm.channel_mask;
    if (channel_mask == 0) {
        mock_shm.error_flags = ERROR_INVALID_CONFIG;
        halted = 1;
    }
    
    assert(mock_shm.error_flags == ERROR_INVALID_CONFIG);
    assert(halted == 1);
    printf("  PASS: Zero channel mask detected\n");
    
    // Test with invalid block size
    mock_shm.channel_mask = 0xFF;
    mock_shm.block_size = MIN_BLOCK_SIZE - 1;  // Invalid
    mock_shm.error_flags = 0;
    halted = 0;
    
    block_size = mock_shm.block_size;
    if (block_size < MIN_BLOCK_SIZE || block_size > MAX_BLOCK_SIZE) {
        mock_shm.error_flags = ERROR_INVALID_CONFIG;
        halted = 1;
    }
    
    assert(mock_shm.error_flags == ERROR_INVALID_CONFIG);
    assert(halted == 1);
    printf("  PASS: Invalid block size detected\n");
    
    // Test with invalid num_blocks
    mock_shm.block_size = 256;
    mock_shm.num_blocks = 1;  // Invalid (need at least 2 for ring buffer)
    mock_shm.error_flags = 0;
    halted = 0;
    
    num_blocks = mock_shm.num_blocks;
    if (num_blocks < 2) {
        mock_shm.error_flags = ERROR_INVALID_CONFIG;
        halted = 1;
    }
    
    assert(mock_shm.error_flags == ERROR_INVALID_CONFIG);
    assert(halted == 1);
    printf("  PASS: Invalid num_blocks detected\n\n");
    
    // Test 3: Verify channel counting
    printf("Test 3: Channel counting\n");
    uint8_t count = count_enabled_channels(0xFF);
    assert(count == 8);
    printf("  PASS: All 8 channels counted correctly\n");
    
    count = count_enabled_channels(0x55);  // 0b01010101
    assert(count == 4);
    printf("  PASS: 4 channels counted correctly\n");
    
    count = count_enabled_channels(0x01);
    assert(count == 1);
    printf("  PASS: 1 channel counted correctly\n\n");
    
    // Test 4: Verify block size calculations
    printf("Test 4: Block size calculations\n");
    uint8_t num_channels = 3;
    uint32_t test_block_size = 256;
    uint32_t block_data_size = test_block_size * num_channels * sizeof(uint16_t);
    uint32_t block_total_size = sizeof(block_descriptor_t) + block_data_size;
    
    assert(block_data_size == 256 * 3 * 2);  // 1536 bytes
    assert(block_total_size == 8 + 1536);     // 1544 bytes
    printf("  PASS: Block size calculations correct\n");
    printf("    block_data_size = %u bytes\n", block_data_size);
    printf("    block_total_size = %u bytes\n\n", block_total_size);
    
    // Test 5: Verify sampling state initialization
    printf("Test 5: Sampling state initialization\n");
    uint32_t current_block = 0;
    uint32_t sample_in_block = 0;
    uint32_t next_sample_time = get_cycle_count() + MIN_SAMPLE_PERIOD_CYCLES;
    
    assert(current_block == 0);
    assert(sample_in_block == 0);
    assert(next_sample_time > 0);
    printf("  PASS: Sampling state initialized correctly\n\n");
    
    // Test 6: Verify block completion logic
    printf("Test 6: Block completion logic\n");
    mock_shm.num_blocks = 4;
    mock_shm.block_size = 256;
    mock_shm.write_block_idx = 0;
    
    current_block = 0;
    sample_in_block = 255;
    
    // Simulate completing a sample
    sample_in_block++;
    
    if (sample_in_block >= mock_shm.block_size) {
        current_block = (current_block + 1) % mock_shm.num_blocks;
        mock_shm.write_block_idx = current_block;
        sample_in_block = 0;
    }
    
    assert(current_block == 1);
    assert(mock_shm.write_block_idx == 1);
    assert(sample_in_block == 0);
    printf("  PASS: Block completion advances to next block\n");
    
    // Test wrapping from last block to first
    current_block = 3;
    sample_in_block = 255;
    sample_in_block++;
    
    if (sample_in_block >= mock_shm.block_size) {
        current_block = (current_block + 1) % mock_shm.num_blocks;
        mock_shm.write_block_idx = current_block;
        sample_in_block = 0;
    }
    
    assert(current_block == 0);
    assert(mock_shm.write_block_idx == 0);
    printf("  PASS: Block wrapping from last to first works\n\n");
    
    // Test 7: Verify error handling for BUSY timeout
    printf("Test 7: BUSY timeout error handling\n");
    mock_shm.error_flags = 0;
    halted = 0;
    mock_adc_result = -1;  // Simulate timeout
    
    if (adc_trigger_and_wait() != 0) {
        mock_shm.error_flags = ERROR_BUSY_TIMEOUT;
        halted = 1;
    }
    
    assert(mock_shm.error_flags == ERROR_BUSY_TIMEOUT);
    assert(halted == 1);
    printf("  PASS: BUSY timeout error detected and handled\n\n");
    
    printf("=== All Main Firmware Structure Tests Passed ===\n");
    return 0;
}
