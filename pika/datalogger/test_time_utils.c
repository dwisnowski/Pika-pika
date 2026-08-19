/*
 * Unit-style regression test for pru_elapsed_cycles_to_ns overflow safety.
 * Build: gcc -Wall -O2 -I./include test_time_utils.c src/time_utils.c -o test_time_utils -lrt
 * Run:   ./test_time_utils
 */
#include "time_utils.h"
#include <stdio.h>
#include <stdlib.h>

static int failures = 0;

static void expect_u64(const char *name, uint64_t got, uint64_t want) {
  if (got != want) {
    fprintf(stderr, "FAIL %s: got %llu want %llu\n", name,
            (unsigned long long)got, (unsigned long long)want);
    failures++;
  } else {
    printf("PASS %s\n", name);
  }
}

int main(void) {
  /* 200 MHz: 5 ns/cycle */
  expect_u64("zero", pru_elapsed_cycles_to_ns(0, 200000000U), 0);
  expect_u64("one_second",
             pru_elapsed_cycles_to_ns(200000000ULL, 200000000U),
             1000000000ULL);

  /*
   * Regression: old formula overflowed near 1.84e10 cycles (~92 s @ 200 MHz).
   * 300 s = 60e9 cycles → 300e9 ns.
   */
  uint64_t cycles_300s = 300ULL * 200000000ULL;
  expect_u64("300s_no_overflow",
             pru_elapsed_cycles_to_ns(cycles_300s, 200000000U),
             300ULL * 1000000000ULL);

  /* cycles_to_realtime_ns after long elapsed time */
  time_sync_t sync;
  time_sync_init_at(&sync, 1000ULL, 200000000U, 1700000000000000000ULL);
  uint64_t t = cycles_to_realtime_ns(&sync, 1000ULL + cycles_300s);
  expect_u64("realtime_anchor",
             t,
             1700000000000000000ULL + 300ULL * 1000000000ULL);

  /* sample_time_from_block uses cycle-accurate reconstruction */
  uint64_t s0 = sample_time_from_block(&sync, 5000ULL, 2000U, 0);
  uint64_t s1 = sample_time_from_block(&sync, 5000ULL, 2000U, 1);
  expect_u64("sample_spacing", s1 - s0, pru_elapsed_cycles_to_ns(2000U, 200000000U));

  if (failures != 0) {
    fprintf(stderr, "%d test(s) failed\n", failures);
    return EXIT_FAILURE;
  }

  printf("All time_utils tests passed.\n");
  return EXIT_SUCCESS;
}
