#include "event_window.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void pre_push(event_window_t *ew, int16_t sample) {
  ew->pre_buffer[ew->pre_head] = sample;
  ew->pre_head = (ew->pre_head + 1) % ew->pre_capacity;
  if (ew->pre_count < ew->pre_capacity)
    ew->pre_count++;
}

static void capture_append(event_window_t *ew, int16_t sample) {
  if (ew->capture_count >= ew->capture_capacity) {
    fprintf(stderr, "[EventWindow] Capture buffer full, truncating\n");
    return;
  }
  ew->capture[ew->capture_count++] = sample;
}

static void copy_pre_to_capture(event_window_t *ew) {
  ew->capture_count = 0;
  if (ew->pre_count == 0)
    return;

  uint32_t start =
      (ew->pre_head + ew->pre_capacity - ew->pre_count) % ew->pre_capacity;
  for (uint32_t i = 0; i < ew->pre_count; i++) {
    uint32_t idx = (start + i) % ew->pre_capacity;
    capture_append(ew, ew->pre_buffer[idx]);
  }
}

int event_window_init(event_window_t *ew, double pre_event_sec,
                      double post_event_sec, uint32_t sample_rate,
                      double max_event_sec) {
  memset(ew, 0, sizeof(*ew));

  if (sample_rate == 0)
    sample_rate = 10000;

  ew->sample_rate = sample_rate;
  ew->pre_capacity =
      (uint32_t)((pre_event_sec + 0.1) * (double)sample_rate) + 1U;
  ew->capture_capacity =
      (uint32_t)((pre_event_sec + max_event_sec + post_event_sec + 0.2) *
                 (double)sample_rate) +
      128U;
  ew->max_event_samples = (uint32_t)(max_event_sec * (double)sample_rate);
  if (ew->max_event_samples == 0)
    ew->max_event_samples = sample_rate * 30U;

  ew->post_samples_total = (uint32_t)(post_event_sec * (double)sample_rate);
  ew->post_samples_remaining = ew->post_samples_total;

  ew->pre_buffer = calloc(ew->pre_capacity, sizeof(int16_t));
  ew->capture = calloc(ew->capture_capacity, sizeof(int16_t));
  if (!ew->pre_buffer || !ew->capture) {
    event_window_free(ew);
    return -1;
  }

  printf("[EventWindow] pre=%u capture=%u post=%u max_event=%u samples @ %u Hz\n",
         ew->pre_capacity, ew->capture_capacity, ew->post_samples_remaining,
         ew->max_event_samples, sample_rate);

  return 0;
}

void event_window_free(event_window_t *ew) {
  free(ew->pre_buffer);
  free(ew->capture);
  ew->pre_buffer = NULL;
  ew->capture = NULL;
}

void event_window_set_timing(event_window_t *ew, uint64_t ns_per_sample) {
  if (ns_per_sample > 0)
    ew->ns_per_sample = ns_per_sample;
}

void event_window_push_sample(event_window_t *ew, int16_t ch0_sample) {
  pre_push(ew, ch0_sample);

  if (ew->state == EW_IDLE)
    return;

  capture_append(ew, ch0_sample);

  if (ew->state == EW_CAPTURING) {
    uint32_t event_samples = ew->capture_count - ew->pre_samples_at_start;
    if (event_samples >= ew->max_event_samples) {
      printf("[EventWindow] Max event duration reached, starting post-capture\n");
      ew->state = EW_POST;
      ew->post_samples_remaining = ew->post_samples_total;
    }
  } else if (ew->state == EW_POST) {
    if (ew->post_skip_decrement_once) {
      ew->post_skip_decrement_once = false;
    } else if (ew->post_samples_remaining > 0) {
      ew->post_samples_remaining--;
    }
    if (ew->post_samples_remaining == 0) {
      ew->ready = true;
      ew->state = EW_IDLE;
    }
  }
}

void event_window_on_start(event_window_t *ew, const anomaly_event_t *event) {
  if (ew->state != EW_IDLE || ew->ready) {
    fprintf(stderr, "[EventWindow] Ignoring START while busy\n");
    return;
  }

  ew->ready_event = *event;
  copy_pre_to_capture(ew);
  ew->pre_samples_at_start = ew->capture_count;

  if (ew->ns_per_sample > 0 && ew->pre_count > 0) {
    ew->waveform_start_ns =
        event->timestamp_ns - (uint64_t)ew->pre_count * ew->ns_per_sample;
  } else {
    ew->waveform_start_ns = event->timestamp_ns;
  }

  ew->state = EW_CAPTURING;
}

void event_window_on_end(event_window_t *ew, const anomaly_event_t *event) {
  if (ew->state != EW_CAPTURING)
    return;

  ew->ready_event = *event;
  ew->state = EW_POST;
  ew->post_samples_remaining = ew->post_samples_total;
  ew->post_skip_decrement_once = true;
}

bool event_window_poll_ready(event_window_t *ew, anomaly_event_t *out_event,
                             int16_t **out_samples, uint32_t *out_count,
                             uint64_t *out_waveform_start_ns,
                             uint64_t *out_ns_per_sample) {
  if (!ew->ready)
    return false;

  *out_event = ew->ready_event;
  *out_samples = ew->capture;
  *out_count = ew->capture_count;
  *out_waveform_start_ns = ew->waveform_start_ns;
  *out_ns_per_sample = ew->ns_per_sample;

  ew->ready = false;
  ew->capture_count = 0;
  ew->waveform_start_ns = 0;

  return true;
}
