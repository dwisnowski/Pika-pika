#ifndef SHM_LAYOUT_H
#define SHM_LAYOUT_H

#include <stdint.h>

/**
 * Shared Memory Layout for PRU-Linux Communication
 */

#define SHM_MAGIC 0xDEADBEEF
#define SHM_VERSION 1
#define SHM_HEADER_OFFSET                                                      \
  128 /* Bytes reserved for pru_shared_memory_t structure */

typedef struct {
  uint64_t timestamp_cycles;
  uint32_t num_samples;
  uint32_t flags;
} __attribute__((packed)) block_descriptor_t;

typedef struct {
  volatile uint32_t magic;
  volatile uint32_t version;
  volatile uint32_t sample_period_cycles;
  volatile uint32_t block_size;
  volatile uint32_t num_blocks;
  volatile uint32_t write_block_idx;
  volatile uint32_t error_flags;
  volatile uint32_t sample_count;
  volatile uint32_t
      sample_rate; /* ADC sampling rate in Hz (set by datalogger) */
  volatile uint32_t
      pru_clock_hz;            /* PRU clock frequency in Hz (200MHz on BBB) */
  volatile uint32_t heartbeat; /* Incremented every main loop iteration */
  /* Per-channel enable flags (1 = read, 0 = skip) */
  volatile uint32_t
      ch_enable[8]; /* ch_enable[0] = CH0, ch_enable[1] = CH1, etc. */
  uint32_t reserved[1];
} __attribute__((packed)) pru_shared_memory_t;

#endif /* SHM_LAYOUT_H */
