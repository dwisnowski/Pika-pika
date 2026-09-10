#include "vrms_rollup.h"
#include <stdio.h>
#include <string.h>

int vrms_rollup_init(vrms_rollup_t *r, const char *base_path,
                     uint32_t window_sec) {
  if (!r)
    return -1;
  memset(r, 0, sizeof(*r));
  if (window_sec == 0)
    window_sec = 600;
  r->window_ns = (uint64_t)window_sec * 1000000000ULL;
  snprintf(r->path, sizeof(r->path), "%s/vrms_10min.jsonl",
           base_path ? base_path : "data");
  r->initialized = 1;
  printf("[VrmsRollup] Writing 10-min aggregates to %s\n", r->path);
  return 0;
}

static void reset_window(vrms_rollup_t *r, uint64_t start_ns) {
  r->window_start_ns = start_ns;
  r->sum_vrms = 0.0;
  r->min_vrms = 0.0f;
  r->max_vrms = 0.0f;
  r->count = 0;
}

static void append_record(vrms_rollup_t *r, uint64_t end_ns) {
  if (r->count == 0)
    return;
  float avg = (float)(r->sum_vrms / (double)r->count);
  FILE *f = fopen(r->path, "a");
  if (!f) {
    perror("[VrmsRollup] fopen");
    return;
  }
  fprintf(f,
          "{\"start_ns\":%llu,\"end_ns\":%llu,\"count\":%u,"
          "\"vrms_min\":%.2f,\"vrms_avg\":%.2f,\"vrms_max\":%.2f}\n",
          (unsigned long long)r->window_start_ns,
          (unsigned long long)end_ns, r->count, r->min_vrms, avg,
          r->max_vrms);
  fclose(f);
}

void vrms_rollup_add(vrms_rollup_t *r, float vrms, uint64_t sample_time_ns) {
  if (!r || !r->initialized)
    return;

  if (r->count == 0) {
    reset_window(r, sample_time_ns);
    r->min_vrms = vrms;
    r->max_vrms = vrms;
  }

  if (sample_time_ns >= r->window_start_ns + r->window_ns) {
    append_record(r, sample_time_ns);
    reset_window(r, sample_time_ns);
    r->min_vrms = vrms;
    r->max_vrms = vrms;
  }

  if (vrms < r->min_vrms)
    r->min_vrms = vrms;
  if (vrms > r->max_vrms)
    r->max_vrms = vrms;
  r->sum_vrms += (double)vrms;
  r->count++;
}

void vrms_rollup_flush(vrms_rollup_t *r, uint64_t sample_time_ns) {
  if (!r || !r->initialized || r->count == 0)
    return;
  append_record(r, sample_time_ns);
  reset_window(r, sample_time_ns);
}
