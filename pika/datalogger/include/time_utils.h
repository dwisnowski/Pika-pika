#ifndef TIME_UTILS_H
#define TIME_UTILS_H

#include <stdint.h>
#include <time.h>

typedef struct {
  uint64_t start_time_ns; /* CLOCK_REALTIME ns at anchor cycle count */
  uint64_t start_cycles;
  uint32_t pru_clock_hz;
} time_sync_t;

/**
 * Initializes time synchronization using CLOCK_REALTIME at the anchor point.
 */
void time_sync_init(time_sync_t *sync, uint64_t initial_cycles,
                    uint32_t pru_clock_hz);

/**
 * Initializes time synchronization using an explicit CLOCK_REALTIME base time.
 */
void time_sync_init_at(time_sync_t *sync, uint64_t initial_cycles,
                       uint32_t pru_clock_hz, uint64_t base_time_ns);

/**
 * Converts PRU elapsed cycles to nanoseconds without uint64 overflow.
 */
uint64_t pru_elapsed_cycles_to_ns(uint64_t elapsed_cycles, uint32_t pru_clock_hz);

/**
 * Converts a PRU cycle count to CLOCK_REALTIME nanoseconds.
 */
uint64_t cycles_to_realtime_ns(time_sync_t *sync, uint64_t cycles);

/**
 * Per-sample time: cycles_to_realtime_ns(timestamp_cycles + index * period_cycles).
 */
uint64_t sample_time_from_block(time_sync_t *sync, uint64_t block_timestamp_cycles,
                                uint32_t period_cycles, uint32_t sample_index);

/** @deprecated Use cycles_to_realtime_ns — kept for existing call sites. */
uint64_t cycles_to_ns(time_sync_t *sync, uint64_t cycles);

/**
 * Returns CLOCK_MONOTONIC nanoseconds.
 */
uint64_t get_monotonic_ns(void);

/**
 * Returns CLOCK_REALTIME nanoseconds (Unix epoch).
 */
uint64_t get_realtime_ns(void);

/** @deprecated Use get_monotonic_ns. */
uint64_t get_now_ns(void);

#endif /* TIME_UTILS_H */
