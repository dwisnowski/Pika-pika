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
 * 4. Runs the main sampling loop with __delay_cycles (P9.27 CONVST, same as
 * pru_bringup.c)
 * 5. Manages ring buffer for continuous data streaming
 *
 * Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 6.1, 6.3
 */

#include "adc_parallel.h"
#include "pru_config.h"
#include "shm_layout.h"
#include <stdint.h>

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

/* PRU remoteproc resource table */
extern const uint32_t pru_remoteproc_ResourceTable[];

/** Runtime variable-cycle delay (assembly). Argument = iterations; each
 * iteration = 2 cycles. */
extern void delay_cycles_runtime(uint32_t iterations);

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
  /* prevent linker from discarding resource table */
  (void)pru_remoteproc_ResourceTable;

  /* Clear SYSCFG[STANDBY_INIT] to enable OCP master port (same as
   * pru_bringup.c) */
  (*(volatile uint32_t *)0x26004) &= ~(1 << 4);

  // Map shared memory to PRU address space (Requirement 5.1)
  volatile pru_shared_memory_t *shm =
      (volatile pru_shared_memory_t *)SHM_BASE_ADDRESS;

  // Wait for magic number (Requirements 5.2, 6.1)
  // The ARM writes this last after initializing the config
  uint32_t wait_count = 0;
  while (shm->magic != SHM_MAGIC) {
    wait_count++;
    if (wait_count > 1000000) {
      // Timeout - shouldn't happen if datalogger is running
      __halt();
    }
  }

  // Read configuration fields (Requirement 5.1)
  uint32_t sample_period = shm->sample_period_cycles;
  uint32_t channel_mask = shm->channel_mask;
  uint32_t block_size = shm->block_size;
  uint32_t num_blocks = shm->num_blocks;

  // Diagnostic handshake: Write sizes back to ARM for verification
  // shm->version: [pru_shm_size(16) | block_desc_size(16)]
  // shm->reserved: [block_data_size(16) | block_total_size(16)]
  shm->version = ((uint32_t)sizeof(pru_shared_memory_t) << 16) |
                 (uint32_t)sizeof(block_descriptor_t);

  // Count enabled channels to calculate sizes
  uint8_t num_channels = count_enabled_channels(channel_mask);
  uint32_t block_data_size = block_size * num_channels * sizeof(uint16_t);
  uint32_t block_total_size = sizeof(block_descriptor_t) + block_data_size;

  shm->reserved[0] = (block_data_size << 16) | (block_total_size & 0xFFFF);

  // Validate configuration (Requirements 6.3)
  // Check sample period is within valid range
  if (sample_period < MIN_SAMPLE_PERIOD_CYCLES ||
      sample_period > MAX_SAMPLE_PERIOD_CYCLES) {
    shm->error_flags = ERROR_INVALID_CONFIG | ERROR_CFG_PERIOD;
    __halt();
  }

  // Check channel mask has at least one channel enabled
  if (channel_mask == 0) {
    shm->error_flags = ERROR_INVALID_CONFIG | ERROR_CFG_MASK;
    __halt();
  }

  // Check block size is within valid range
  if (block_size < MIN_BLOCK_SIZE || block_size > MAX_BLOCK_SIZE) {
    shm->error_flags = ERROR_INVALID_CONFIG | ERROR_CFG_BLOCKSIZE;
    __halt();
  }

  // On error, dump these to the status area for the ARM to read
  if (num_blocks < 2) {
    shm->error_flags = ERROR_INVALID_CONFIG | ERROR_CFG_NUMBLOCKS;
    shm->write_block_idx = num_blocks; // Echo back for debugging
    __halt();
  }

  // Allocate local staging buffer in PRU RAM (avoids DDR stalls during
  // sampling) This buffer holds samples temporarily before burst-writing to
  // shared memory
  // NOTE: Using static storage to avoid stack overflow (512 bytes is too large
  // for PRU stack)
  static uint16_t local_buffer[LOCAL_BUFFER_SAMPLES][MAX_CHANNELS];
  uint32_t local_buffer_idx = 0;

  // Initialize sampling state variables (Requirement 6.3)
  uint32_t current_block = 0;   // Start with block 0
  uint32_t sample_in_block = 0; // No samples in current block yet

  // Main sampling loop (Requirements 5.3-5.10, 1.7)
  while (1) {
    delay_cycles_runtime(sample_period >> 1); /* 2 cycles per iteration */

    // Trigger ADC conversion and wait for completion (Requirement 5.3, 5.4)
    adc_trigger_and_wait();

    // Read enabled channels using channel_mask and store to local buffer
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

    // Calculate base address of the current block
    uint32_t block_offset =
        sizeof(pru_shared_memory_t) + (current_block * block_total_size);
    uint8_t *block_base = ((uint8_t *)shm) + block_offset;
    block_descriptor_t *desc = (block_descriptor_t *)block_base;

    // DEBUG: Push internal state to header so ARM can see it live
    shm->reserved[0] = current_block;
    shm->reserved[1] = block_offset;
    shm->reserved[2] = sample_in_block;
    shm->reserved[3] = local_buffer_idx;

    // Flush local buffer to shared memory when full or block complete
    if (local_buffer_idx >= LOCAL_BUFFER_SAMPLES ||
        sample_in_block >= block_size) {

      // Pointer to data (offset 16 in block - NEW DESCRIPTOR SIZE)
      uint16_t *block_data =
          (uint16_t *)(block_base + sizeof(block_descriptor_t));

      // Burst-write local buffer to shared memory
      uint32_t i;
      uint8_t j;
      uint32_t start_sample = sample_in_block - local_buffer_idx;
      for (i = 0; i < local_buffer_idx; i++) {
        uint32_t sample_offset = (start_sample + i) * num_channels;
        for (j = 0; j < num_channels; j++) {
          block_data[sample_offset + j] = local_buffer[i][j];
        }
      }

      // Reset local buffer index
      local_buffer_idx = 0;
    }

    // Check for block completion and finalize descriptor
    if (sample_in_block >= block_size) {
      // Finalize block descriptor with 32-bit writes
      desc->num_samples = (uint32_t)block_size;
      desc->timestamp_cycles = shm->sample_count;
      desc->flags = 0;

      // Move to next block and wrap
      current_block = (current_block + 1) % num_blocks;

      // Update write_block_idx atomically
      shm->write_block_idx = current_block;

      // Reset sample counter for new block
      sample_in_block = 0;
    }
  }
}
