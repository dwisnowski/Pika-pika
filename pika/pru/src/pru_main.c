/**
 * PRU Main Sampling Loop
 * 
 * This file implements the main entry point and sampling loop for the PRU
 * firmware that performs deterministic data acquisition from an AD7606 ADC.
 * 
 * The firmware:
 * 1. Validates shared memory initialization (magic number)
 * 2. Reads and validates configuration parameters
 * 3. Initializes sampling state
 * 4. Runs the main sampling loop with cycle-accurate timing
 * 5. Manages ring buffer for continuous data streaming
 * 
 * Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 6.1, 6.3
 */

#include <stdint.h>
#include "shm_layout.h"
#include "pru_config.h"
#include "timing.h"
#include "adc_parallel.h"

/**
 * Shared memory base address
 * 
 * This address is where Linux userspace maps the shared memory region
 * that the PRU can access. The actual address is typically configured
 * via the remoteproc framework and device tree.
 * 
 * For BeagleBone Black, PRU can access DDR memory starting at 0x00010000
 * in the PRU address space (mapped to physical DDR).
 */
#define SHM_BASE_ADDRESS 0x00010000

/**
 * Local staging buffer size
 * 
 * Using a small local buffer (32 samples) allows us to:
 * 1. Minimize DDR access during time-critical sampling
 * 2. Burst-write to DDR when buffer is full (better efficiency)
 * 3. Keep buffer small enough to fit in PRU local memory
 * 
 * 32 samples × 8 channels × 2 bytes = 512 bytes (well within 8KB PRU RAM)
 */
#define LOCAL_BUFFER_SAMPLES 32

/**
 * Count the number of enabled channels in a channel mask
 * 
 * @param channel_mask Bit mask where bit N represents channel N
 * @return Number of bits set in the mask (0-8)
 */
static inline uint8_t count_enabled_channels(uint32_t channel_mask) {
    uint8_t count = 0;
    uint8_t i;
    for (i = 0; i < NUM_ADC_CHANNELS; i++) {
        if (channel_mask & (1 << i)) {
            count++;
        }
    }
    return count;
}

/**
 * Main entry point for PRU firmware
 * 
 * This function:
 * 1. Maps shared memory and verifies magic number (Req 5.2, 6.1)
 * 2. Reads configuration from shared memory (Req 5.1)
 * 3. Validates configuration parameters (Req 6.3)
 * 4. Initializes sampling state variables (Req 6.1, 6.3)
 * 5. Enters the main sampling loop (implemented in task 7)
 * 
 * On any error, sets appropriate error flag and halts.
 */
void main(void) {
    // Map shared memory to PRU address space (Requirement 5.1)
    volatile pru_shared_memory_t *shm = 
        (volatile pru_shared_memory_t *)SHM_BASE_ADDRESS;
    
    // Verify magic number (Requirements 5.2, 6.1)
    if (shm->magic != SHM_MAGIC) {
        shm->error_flags = ERROR_INVALID_MAGIC;
        __halt();
    }
    
    // Read configuration fields (Requirement 5.1)
    uint32_t sample_period = shm->sample_period_cycles;
    uint32_t channel_mask = shm->channel_mask;
    uint32_t block_size = shm->block_size;
    uint32_t num_blocks = shm->num_blocks;
    
    // Validate configuration (Requirements 6.3)
    // Check sample period is within valid range
    if (!is_valid_sample_period(sample_period)) {
        shm->error_flags = ERROR_INVALID_CONFIG;
        __halt();
    }
    
    // Check channel mask has at least one channel enabled
    if (channel_mask == 0) {
        shm->error_flags = ERROR_INVALID_CONFIG;
        __halt();
    }
    
    // Check block size is within valid range
    if (block_size < MIN_BLOCK_SIZE || block_size > MAX_BLOCK_SIZE) {
        shm->error_flags = ERROR_INVALID_CONFIG;
        __halt();
    }
    
    // Check num_blocks is reasonable (at least 2 for ring buffer)
    if (num_blocks < 2) {
        shm->error_flags = ERROR_INVALID_CONFIG;
        __halt();
    }
    
    // Count enabled channels from channel_mask (Requirement 6.1)
    uint8_t num_channels = count_enabled_channels(channel_mask);
    
    // Calculate block data size and total size (Requirement 6.1)
    // Each sample is 16 bits (2 bytes), and we have num_channels per sample
    uint32_t block_data_size = block_size * num_channels * sizeof(uint16_t);
    uint32_t block_total_size = sizeof(block_descriptor_t) + block_data_size;
    
    // Allocate local staging buffer in PRU RAM (avoids DDR stalls during sampling)
    // This buffer holds samples temporarily before burst-writing to shared memory
    uint16_t local_buffer[LOCAL_BUFFER_SAMPLES][MAX_CHANNELS];
    uint32_t local_buffer_idx = 0;
    
    // Initialize sampling state variables (Requirement 6.3)
    uint32_t current_block = 0;           // Start with block 0
    uint32_t sample_in_block = 0;         // No samples in current block yet
    uint32_t next_sample_time = get_cycle_count() + sample_period;  // Schedule first sample
    
    // Main sampling loop (Requirements 5.3-5.10, 1.7)
    while (1) {
        // Calculate wait time until next_sample_time with drift compensation (Requirement 5.10)
        uint32_t now = get_cycle_count();
        uint32_t elapsed = elapsed_cycles(now, next_sample_time);
        
        // Check if we're behind schedule (drift compensation)
        if (elapsed > sample_period) {
            // We're behind schedule - skip to next interval to avoid accumulating drift
            next_sample_time = now + sample_period;
        } else {
            // Wait until next sample time
            while (get_cycle_count() < next_sample_time);
        }
        
        // Trigger ADC conversion and wait for completion (Requirements 5.3, 5.4)
        if (adc_trigger_and_wait() != 0) {
            // BUSY timeout error (Requirement 6.2)
            shm->error_flags = ERROR_BUSY_TIMEOUT;
            __halt();
        }
        
        // Read enabled channels using channel_mask and store to local buffer (Requirements 5.5, 5.6)
        // Using local buffer avoids DDR access during time-critical sampling
        uint32_t ch_idx = 0;
        uint8_t ch;
        for (ch = 0; ch < NUM_ADC_CHANNELS; ch++) {
            if (channel_mask & (1 << ch)) {
                local_buffer[local_buffer_idx][ch_idx++] = adc_read_channel(ch);
            }
        }
        
        // Increment counters
        local_buffer_idx++;
        sample_in_block++;
        shm->sample_count++;
        
        // Flush local buffer to shared memory when full or block complete
        if (local_buffer_idx >= LOCAL_BUFFER_SAMPLES || sample_in_block >= block_size) {
            // Calculate pointers to current block descriptor and data buffer
            // Memory layout: [header][block0_desc][block0_data][block1_desc][block1_data]...
            uint8_t *block_base = ((uint8_t *)shm) + 
                                  sizeof(pru_shared_memory_t) +
                                  (current_block * block_total_size);
            block_descriptor_t *desc = (block_descriptor_t *)block_base;
            uint16_t *data = (uint16_t *)(block_base + sizeof(block_descriptor_t));
            
            // Burst-write local buffer to shared memory
            uint32_t i;
            uint8_t j;
            uint32_t start_sample = sample_in_block - local_buffer_idx;
            for (i = 0; i < local_buffer_idx; i++) {
                uint32_t data_idx = (start_sample + i) * num_channels;
                for (j = 0; j < num_channels; j++) {
                    data[data_idx + j] = local_buffer[i][j];
                }
            }
            
            // Reset local buffer index
            local_buffer_idx = 0;
            
            // Check for block completion and finalize descriptor (Requirements 5.7, 5.8)
            if (sample_in_block >= block_size) {
                // Finalize block descriptor
                desc->num_samples = block_size;
                desc->timestamp_cycles = next_sample_time - (block_size * sample_period);
                desc->flags = 0;
                
                // Move to next block and wrap to block 0 when reaching num_blocks (Requirement 5.9)
                current_block = (current_block + 1) % num_blocks;
                
                // Update write_block_idx atomically on block completion (Requirements 1.7, 5.7)
                shm->write_block_idx = current_block;
                
                // Reset sample counter for new block
                sample_in_block = 0;
            }
        }
        
        // Schedule next sample by incrementing next_sample_time (Requirement 5.10)
        next_sample_time += sample_period;
    }
}