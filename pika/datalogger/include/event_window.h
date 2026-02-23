#ifndef EVENT_WINDOW_H
#define EVENT_WINDOW_H

#include "event_types.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/**
 * Manages a circular buffer of high-resolution blocks to provide
 * pre-event and post-event context for anomalies.
 */

typedef struct {
  uint8_t *buffer;   // Circular buffer of raw blocks
  size_t block_size; // Size of one block in bytes
  size_t num_blocks; // Total blocks in circular buffer
  size_t write_idx;  // Current write position

  // Tracking active window capture
  bool capturing_post;
  uint32_t post_samples_remaining;
  anomaly_event_t active_event;

  // Buffer for the final "event package"
  uint8_t *event_output;
  size_t event_output_size;
} event_window_t;

/**
 * Initializes the window manager.
 * pre_event_sec: seconds of history to keep.
 * sample_rate: nominal sample rate.
 */
int event_window_init(event_window_t *ew, double pre_event_sec,
                      double post_event_sec, uint32_t sample_rate,
                      uint32_t channels);

/**
 * Cleans up memory.
 */
void event_window_free(event_window_t *ew);

/**
 * Adds a new high-res block to the circular history.
 * If a capture is in progress, it also accumulates toward the final event
 * output.
 */
void event_window_push_block(event_window_t *ew, const void *block);

/**
 * Triggers a high-res capture starting with the current history.
 * Returns true if trigger accepted.
 */
bool event_window_trigger(event_window_t *ew, anomaly_event_t event);

/**
 * Checks if an event capture has finished.
 * If so, returns the pointer to the full event data (pre + post).
 */
uint8_t *event_window_get_ready(event_window_t *ew, size_t *out_size,
                                anomaly_event_t *out_event);

#endif // EVENT_WINDOW_H
