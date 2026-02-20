#ifndef SHM_LAYOUT_H
#define SHM_LAYOUT_H

#pragma pack(push, 1)

#include <stdint.h>

/**
 * Shared Memory Layout for PRU-Linux Communication
 *
 * This header defines the shared memory interface between PRU firmware
 * and Linux userspace for AD7606 data acquisition. The memory layout
 * provides configuration, status, and ring buffer structures.
 */

/* Magic number for shared memory verification */
#define SHM_MAGIC 0xDEADBEEF

/* Shared memory layout version */
#define SHM_VERSION 1

/* ADC configuration constants */
#define MAX_CHANNELS 8
#define DEFAULT_BLOCK_SIZE 256
#define DEFAULT_NUM_BLOCKS 4

/* Error flag bit definitions */
#define ERROR_INVALID_MAGIC (1 << 0)  /* Magic number mismatch */
#define ERROR_BUSY_TIMEOUT (1 << 1)   /* ADC BUSY signal timeout */
#define ERROR_INVALID_CONFIG (1 << 2) /* Invalid configuration parameters */
#define ERROR_BUFFER_OVERRUN (1 << 3) /* Ring buffer overrun */
#define ERROR_CFG_PERIOD (1 << 4)
#define ERROR_CFG_MASK (1 << 5)
#define ERROR_CFG_BLOCKSIZE (1 << 6)
#define ERROR_CFG_NUMBLOCKS (1 << 7)

/**
 * Block descriptor structure
 *
 * Each ring buffer block has a descriptor containing metadata about
 * the samples in that block.
 *
 * All fields are 32-bit to ensure perfect PRU/ARM alignment.
 * Total size: 16 bytes.
 */
typedef struct {
  uint32_t timestamp_cycles; /* 4 bytes */
  uint32_t num_samples;      /* 4 bytes */
  uint32_t flags;            /* 4 bytes */
  uint32_t reserved;         /* 4 bytes padding -> Total 16 bytes */
} __attribute__((packed)) block_descriptor_t;

/**
 * PRU shared memory structure
 *
 * Padded to exactly 64 bytes.
 */
typedef struct {
  /* Header - read-only after initialization */
  volatile uint32_t magic;   /* 4 bytes */
  volatile uint32_t version; /* 4 bytes */

  /* Configuration - written by Linux, read by PRU */
  volatile uint32_t sample_period_cycles; /* 4 bytes */
  volatile uint32_t channel_mask;         /* 4 bytes */
  volatile uint32_t block_size;           /* 4 bytes */
  volatile uint32_t num_blocks;           /* 4 bytes */

  /* Status - written by PRU, read by Linux */
  volatile uint32_t write_block_idx; /* 4 bytes */
  volatile uint32_t error_flags;     /* 4 bytes */
  volatile uint32_t sample_count;    /* 4 bytes */

  /* Padding to 64 bytes (16 words)
   * Current: 9 words used. Need 7 more. */
  uint32_t reserved[7];

  /* Ring buffer data follows this header at offset 64 */
} __attribute__((packed)) pru_shared_memory_t;

#pragma pack(pop)

#endif /* SHM_LAYOUT_H */
