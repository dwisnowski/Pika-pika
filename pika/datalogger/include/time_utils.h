#ifndef TIME_UTILS_H
#define TIME_UTILS_H

#include <stdint.h>
#include <time.h>

typedef struct {
  struct timespec start_time;
  uint64_t start_cycles;
  double cycles_per_ns;
} time_sync_t;

/**
 * Initializes time synchronization using the current clock and PRU cycles.
 */
void time_sync_init(time_sync_t *sync, uint64_t initial_cycles,
                    uint32_t sample_rate_hz);

/**
 * Converts a PRU cycle count to a nanosecond timestamp (CLOCK_MONOTONIC).
 */
uint64_t cycles_to_ns(time_sync_t *sync, uint64_t cycles);

/**
 * Returns the current time in nanoseconds (CLOCK_MONOTONIC).
 */
uint64_t get_now_ns(void);

#endif // TIME_UTILS_H
