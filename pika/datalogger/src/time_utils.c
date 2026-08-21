#include "time_utils.h"

void time_sync_init_at(time_sync_t *sync, uint64_t initial_cycles,
                       uint32_t pru_clock_hz, uint64_t base_time_ns) {
  sync->start_time_ns = base_time_ns;
  sync->start_cycles = initial_cycles;
  sync->pru_clock_hz = (pru_clock_hz == 0) ? 200000000U : pru_clock_hz;
}

void time_sync_init(time_sync_t *sync, uint64_t initial_cycles,
                    uint32_t pru_clock_hz) {
  time_sync_init_at(sync, initial_cycles, pru_clock_hz, get_realtime_ns());
}

uint64_t get_monotonic_ns(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

uint64_t get_realtime_ns(void) {
  struct timespec ts;
  clock_gettime(CLOCK_REALTIME, &ts);
  return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

uint64_t get_now_ns(void) { return get_monotonic_ns(); }

uint64_t pru_elapsed_cycles_to_ns(uint64_t elapsed_cycles,
                                uint32_t pru_clock_hz) {
  if (pru_clock_hz == 0)
    return 0;

  /* Exact at 200 MHz: 5 ns per cycle, no multiply overflow. */
  if (pru_clock_hz == 200000000U)
    return elapsed_cycles * 5ULL;

  /*
   * General case: split divide to keep intermediate products below 2^64.
   * elapsed_ns = elapsed_cycles * 1e9 / pru_clock_hz
   */
  uint64_t whole_seconds = elapsed_cycles / pru_clock_hz;
  uint64_t rem_cycles = elapsed_cycles % pru_clock_hz;
  return whole_seconds * 1000000000ULL +
         (rem_cycles * 1000000000ULL) / pru_clock_hz;
}

uint64_t cycles_to_realtime_ns(time_sync_t *sync, uint64_t cycles) {
  if (cycles < sync->start_cycles)
    return sync->start_time_ns;

  uint64_t elapsed_cycles = cycles - sync->start_cycles;
  return sync->start_time_ns +
         pru_elapsed_cycles_to_ns(elapsed_cycles, sync->pru_clock_hz);
}

uint64_t cycles_to_ns(time_sync_t *sync, uint64_t cycles) {
  return cycles_to_realtime_ns(sync, cycles);
}

uint64_t sample_time_from_block(time_sync_t *sync, uint64_t block_timestamp_cycles,
                                uint32_t period_cycles, uint32_t sample_index) {
  uint64_t sample_cycles =
      block_timestamp_cycles + (uint64_t)sample_index * (uint64_t)period_cycles;
  return cycles_to_realtime_ns(sync, sample_cycles);
}
