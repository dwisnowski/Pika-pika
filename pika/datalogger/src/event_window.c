#include "event_window.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int event_window_init(event_window_t *ew, double pre_event_sec,
                      double post_event_sec, uint32_t sample_rate,
                      uint32_t channels) {
  // Calculate sizing
  // block_size is fixed at 128 samples * channels * 2
  ew->block_size = 128 * channels * 2;

  uint32_t samples_per_sec = sample_rate;
  uint32_t pre_blocks = (uint32_t)((pre_event_sec * samples_per_sec) / 128) + 1;
  uint32_t post_blocks =
      (uint32_t)((post_event_sec * samples_per_sec) / 128) + 1;

  ew->num_blocks = pre_blocks;
  ew->buffer = malloc(ew->num_blocks * ew->block_size);
  if (!ew->buffer)
    return -1;

  // The output buffer needs to hold PRE + POST
  ew->event_output_size = (pre_blocks + post_blocks) * ew->block_size;
  ew->event_output = malloc(ew->event_output_size);
  if (!ew->event_output) {
    free(ew->buffer);
    return -1;
  }

  ew->write_idx = 0;
  ew->capturing_post = false;

  return 0;
}

void event_window_free(event_window_t *ew) {
  if (ew->buffer)
    free(ew->buffer);
  if (ew->event_output)
    free(ew->event_output);
}

void event_window_push_block(event_window_t *ew, const void *block) {
  // 1. Update circular history
  memcpy(ew->buffer + (ew->write_idx * ew->block_size), block, ew->block_size);
  ew->write_idx = (ew->write_idx + 1) % ew->num_blocks;

  // 2. If we are in the middle of a post-event capture, copy this block to the
  // output
  if (ew->capturing_post) {
    // Find where we are in the post-capture
    // This is a simplified version; in a production system we'd use a more
    // robust state machine to handle overlapping events.

    // For now, we'll just append if we haven't reached the end.
    // (Implementation omitted for brevity in POC, but structure is here)
  }
}

bool event_window_trigger(event_window_t *ew, anomaly_event_t event) {
  if (ew->capturing_post)
    return false; // Already busy

  ew->active_event = event;
  ew->capturing_post = true;

  // Copy the entire circular history (Pre-event data) into the start of output
  // We need to unroll the circular buffer
  for (size_t i = 0; i < ew->num_blocks; i++) {
    size_t source_idx = (ew->write_idx + i) % ew->num_blocks;
    memcpy(ew->event_output + (i * ew->block_size),
           ew->buffer + (source_idx * ew->block_size), ew->block_size);
  }

  // Set a "stop" threshold (e.g. 0.5s worth of blocks later)
  ew->post_samples_remaining = 32; // Simplified: 32 blocks = ~0.4s @ 10kHz

  return true;
}

uint8_t *event_window_get_ready(event_window_t *ew, size_t *out_size,
                                anomaly_event_t *out_event) {
  // In this POC, we'll immediately "ready" the pre-event window
  // to demonstrate the file writing.
  if (ew->capturing_post) {
    ew->capturing_post = false; // Reset for next trigger
    *out_size = ew->num_blocks * ew->block_size;
    *out_event = ew->active_event;
    return ew->event_output;
  }
  return NULL;
}
