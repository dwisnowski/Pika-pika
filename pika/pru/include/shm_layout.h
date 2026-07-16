#ifndef SHM_LAYOUT_H
#define SHM_LAYOUT_H

#include <stdint.h>

/**
 * Shared Memory Layout for PRU-Linux Communication
 *
 * Control/header lives in PRU Shared RAM (12 KB).
 * Sample ring blocks live in a carved-out DDR region (see ddr_phys_addr).
 *
 * Time base: PRU cycle counter (CCNT @ pru_clock_hz). Each block carries
 * timestamp_cycles (first sample) and period_cycles (measured mean). The
 * host reconstructs per-sample times; YAML nominal_rate_hz is config intent
 * / fallback only.
 */

#define SHM_MAGIC 0xDEADBEEF
#define SHM_VERSION 2
#define SHM_HEADER_OFFSET                                                      \
  128 /* Bytes reserved for pru_shared_memory_t structure */

/** Block descriptor size in bytes (must match block_descriptor_t) */
#define BLOCK_DESCRIPTOR_SIZE 24

/** Interleaved payload: always 8 channel slots × int16 */
#define BLOCK_CHANNELS 8
#define BLOCK_PAYLOAD_BYTES(block_size)                                        \
  ((uint32_t)(block_size) * BLOCK_CHANNELS * 2u)
#define BLOCK_TOTAL_SIZE(block_size)                                           \
  (BLOCK_DESCRIPTOR_SIZE + BLOCK_PAYLOAD_BYTES(block_size))

/**
 * DDR sample ring.
 * Preferred: host publishes a verified physical address in ddr_phys_addr.
 * Fallback PA when cmdline has mem=448M (top of 512 MiB BBB DRAM unused by Linux).
 */
#define PIKA_DDR_RING_PHYS 0x9C000000u
#define PIKA_DDR_RING_SIZE 0x00100000u /* 1 MiB */

/** Defaults for DDR-backed ring (must fit in PIKA_DDR_RING_SIZE) */
#define PIKA_DEFAULT_BLOCK_SIZE 128u
#define PIKA_DEFAULT_NUM_BLOCKS 256u

/** Block complete flag */
#define BLOCK_FLAG_COMPLETE 0xAA55AA55u

typedef struct {
  uint64_t timestamp_cycles; /* first sample of block (PRU CCNT accum) */
  uint32_t num_samples;
  uint32_t flags;            /* BLOCK_FLAG_COMPLETE when ready */
  uint32_t period_cycles;    /* measured mean period this block */
  uint32_t reserved;
} __attribute__((packed)) block_descriptor_t;

typedef struct {
  volatile uint32_t magic;
  volatile uint32_t version;
  volatile uint32_t sample_period_cycles; /* 0 = free-run / max-rate mode */
  volatile uint32_t block_size;
  volatile uint32_t num_blocks;
  volatile uint32_t write_block_idx;
  volatile uint32_t error_flags;
  volatile uint32_t sample_count;
  volatile uint32_t
      sample_rate; /* ADC sampling rate in Hz (0 = free-run; set by host) */
  volatile uint32_t
      pru_clock_hz;            /* PRU clock frequency in Hz (200MHz on BBB) */
  volatile uint32_t heartbeat; /* Incremented in the acquisition loop */
  /* Per-channel enable flags (1 = read, 0 = skip) */
  volatile uint32_t
      ch_enable[8]; /* ch_enable[0] = CH0, ch_enable[1] = CH1, etc. */
  /* DDR sample ring geometry (physical); host mmaps the same region */
  volatile uint32_t ddr_phys_addr;
  volatile uint32_t ddr_size_bytes;
  volatile uint32_t block_desc_size; /* sizeof(block_descriptor_t) */
} __attribute__((packed)) pru_shared_memory_t;

#endif /* SHM_LAYOUT_H */
