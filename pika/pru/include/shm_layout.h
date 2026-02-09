#ifndef SHM_LAYOUT_H
#define SHM_LAYOUT_H

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
#define ERROR_INVALID_MAGIC    (1 << 0)  /* Magic number mismatch */
#define ERROR_BUSY_TIMEOUT     (1 << 1)  /* ADC BUSY signal timeout */
#define ERROR_INVALID_CONFIG   (1 << 2)  /* Invalid configuration parameters */
#define ERROR_BUFFER_OVERRUN   (1 << 3)  /* Ring buffer overrun */

/**
 * Block descriptor structure
 * 
 * Each ring buffer block has a descriptor containing metadata about
 * the samples in that block.
 */
typedef struct {
    uint32_t timestamp_cycles;   /* Cycle count when block started */
    uint16_t num_samples;        /* Number of samples in this block */
    uint16_t flags;              /* Block status flags */
} block_descriptor_t;

/**
 * PRU shared memory structure
 * 
 * This structure defines the layout of shared memory accessible by both
 * PRU and Linux userspace. The ring buffer data follows this header.
 * 
 * Memory Layout:
 * [pru_shared_memory_t header]
 * [block_descriptor_t][block 0 data]
 * [block_descriptor_t][block 1 data]
 * ...
 * [block_descriptor_t][block N-1 data]
 */
typedef struct {
    /* Header - read-only after initialization */
    uint32_t magic;              /* Magic number for verification (SHM_MAGIC) */
    uint32_t version;            /* Layout version (SHM_VERSION) */
    
    /* Configuration - written by Linux, read by PRU */
    uint32_t sample_period_cycles;  /* Cycles between samples */
    uint32_t channel_mask;          /* Bit mask of enabled channels (0-7) */
    uint32_t block_size;            /* Samples per block (power of 2) */
    uint32_t num_blocks;            /* Number of ring buffer blocks */
    
    /* Status - written by PRU, read by Linux */
    volatile uint32_t write_block_idx;  /* Current block being written by PRU */
    volatile uint32_t error_flags;      /* Error status bits */
    volatile uint32_t sample_count;     /* Total samples acquired */
    
    /* Ring buffer follows this header in memory */
} pru_shared_memory_t;

#endif /* SHM_LAYOUT_H */
