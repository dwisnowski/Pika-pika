#include "time_utils.h"

void time_sync_init_at(time_sync_t *sync, uint64_t initial_cycles,
                       uint32_t pru_clock_hz, uint64_t base_time_ns) {
  sync->start_time_ns = base_time_ns;
  sync->start_cycles = initial_cycles;
  sync->pru_clock_hz = (pru_clock_hz == 0) ? 200000000U : pru_clock_hz;
}

void time_sync_init(time_sync_t *sync, uint64_t initial_cycles,
                    uint32_t pru_clock_hz) {
  time_sync_init_at(sync, initial_cycles, pru_clock_hz, get_now_ns());
}

uint64_t get_now_ns(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint64_t)ts.tv_sec * 1000000000ULL + ts.tv_nsec;
}

uint64_t cycles_to_ns(time_sync_t *sync, uint64_t cycles) {
  if (cycles < sync->start_cycles) {
    return sync->start_time_ns;
  }

  uint64_t elapsed_cycles = cycles - sync->start_cycles;
  uint64_t elapsed_ns =
      (elapsed_cycles * 1000000000ULL) / (uint64_t)sync->pru_clock_hz;

  return sync->start_time_ns + elapsed_ns;
}
