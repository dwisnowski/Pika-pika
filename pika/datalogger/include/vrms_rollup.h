#ifndef VRMS_ROLLUP_H
#define VRMS_ROLLUP_H

#include <stdint.h>

/**
 * Best-effort 10-minute Vrms min/avg/max aggregator for ANSI C84.1 context.
 * Not Class A UTC-tick synchronized — uses wall-clock realtime ns.
 */
typedef struct {
  uint64_t window_start_ns;
  uint64_t window_ns;
  double sum_vrms;
  float min_vrms;
  float max_vrms;
  uint32_t count;
  char path[256];
  int initialized;
} vrms_rollup_t;

int vrms_rollup_init(vrms_rollup_t *r, const char *base_path,
                     uint32_t window_sec);

/** Feed one interval Vrms (volts). May append a completed 10-min record. */
void vrms_rollup_add(vrms_rollup_t *r, float vrms, uint64_t sample_time_ns);

void vrms_rollup_flush(vrms_rollup_t *r, uint64_t sample_time_ns);

#endif /* VRMS_ROLLUP_H */
