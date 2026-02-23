#include "time_utils.h"

void time_sync_init(time_sync_t *sync, uint64_t initial_cycles,
                    uint32_t sample_rate_hz) {
  clock_gettime(CLOCK_MONOTONIC, &sync->start_time);
  sync->start_cycles = initial_cycles;

  // PRU clock is 200MHz
  sync->cycles_per_ns = 0.2;
}

uint64_t get_now_ns(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint64_t)ts.tv_sec * 1000000000ULL + ts.tv_nsec;
}

uint64_t cycles_to_ns(time_sync_t *sync, uint64_t cycles) {
  uint64_t elapsed_cycles = cycles - sync->start_cycles;
  uint64_t elapsed_ns =
      (uint64_t)((double)elapsed_cycles / sync->cycles_per_ns);

  uint64_t base_ns = (uint64_t)sync->start_time.tv_sec * 1000000000ULL +
                     sync->start_time.tv_nsec;
  return base_ns + elapsed_ns;
}
