#ifndef EVENT_WINDOW_H
#define EVENT_WINDOW_H

#include "event_types.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef enum {
  EW_IDLE = 0,
  EW_CAPTURING,
  EW_POST,
} ew_state_t;

typedef struct {
  int16_t *pre_buffer;
  uint32_t pre_capacity;
  uint32_t pre_head;
  uint32_t pre_count;

  int16_t *capture;
  uint32_t capture_capacity;
  uint32_t capture_count;

  ew_state_t state;
  bool ready;
  bool post_skip_decrement_once;
  anomaly_event_t ready_event;

  uint64_t waveform_start_ns;
  uint64_t ns_per_sample;
  uint32_t post_samples_remaining;
  uint32_t post_samples_total;
  uint32_t max_event_samples;
  uint32_t pre_samples_at_start;

  uint32_t sample_rate;
} event_window_t;

int event_window_init(event_window_t *ew, double pre_event_sec,
                      double post_event_sec, uint32_t sample_rate,
                      double max_event_sec);

void event_window_free(event_window_t *ew);

void event_window_set_timing(event_window_t *ew, uint64_t ns_per_sample);

void event_window_push_sample(event_window_t *ew, int16_t ch0_sample);

void event_window_on_start(event_window_t *ew, const anomaly_event_t *event);

void event_window_on_end(event_window_t *ew, const anomaly_event_t *event);

bool event_window_poll_ready(event_window_t *ew, anomaly_event_t *out_event,
                             int16_t **out_samples, uint32_t *out_count,
                             uint64_t *out_waveform_start_ns,
                             uint64_t *out_ns_per_sample);

#endif /* EVENT_WINDOW_H */
