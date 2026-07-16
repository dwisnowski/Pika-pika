#ifndef ANOMALY_DETECTOR_H
#define ANOMALY_DETECTOR_H

#include "event_types.h"
#include "logger_config.h"
#include <stdint.h>

typedef struct {
  anomaly_config_t config;
  sensor_config_t sensor;
  detection_config_t detection;
  uint32_t nominal_rate_hz;
  /* Nanoseconds per sample for event timestamps (updated from measured PRU period) */
  uint64_t ns_per_sample;

  /* RMS sliding window — circular buffer of squared AC voltages */
  float sq_sum;                /* Running sum of squared AC voltage samples */
  uint32_t rms_window_samples; /* = (nominal_rate_hz / ac_freq_hz) *
                                  rms_window_cycles */
  float *sq_ring;              /* Heap-allocated circular buffer */
  uint32_t sq_head;
  uint32_t sq_count;

  /* DC bias removal — exponential moving average */
  float dc_ema;
  float ema_alpha; /* = 1.0f / rms_window_samples */

  /* Auto-learn nominal VRMS state */
  float nominal_vrms; /* 0 = still learning */
  uint32_t
      learn_samples_total; /* = (nominal_rate_hz / ac_freq_hz) * learn_cycles */
  uint32_t learn_samples_left; /* countdown; when 0 learning is complete */
  float learn_sq_sum; /* accumulates squared vrms_mains for RMS of RMS */
  uint32_t learn_count;

  /* Event state */
  int in_event;
  event_type_t current_type;
  uint32_t current_duration;
  uint64_t start_time_ns;

  /* Per-type debounce: nanosecond timestamp of last event END */
  uint64_t last_event_end_ns[5]; /* indexed by event_type_t (0=NONE..4=DIP) */

  /* Debounce cooldowns in nanoseconds */
  uint64_t sag_cooldown_ns;
  uint64_t swell_cooldown_ns;
  uint64_t spike_cooldown_ns;
} anomaly_detector_t;

/**
 * Initialize the anomaly detector.
 * Allocates the internal RMS ring buffer on the heap.
 * Returns 0 on success, -1 on allocation failure.
 */
int anomaly_detector_init(anomaly_detector_t *ad, anomaly_config_t config,
                          sensor_config_t sensor, detection_config_t detection,
                          debounce_config_t debounce, uint32_t nominal_rate_hz);

/**
 * Free resources allocated by anomaly_detector_init.
 */
void anomaly_detector_free(anomaly_detector_t *ad);

/**
 * Process a block of raw ADC samples (channel 0 used for detection).
 * samples  : interleaved multi-channel buffer, channel 0 is samples[i *
 * channels]. count    : number of sample frames (not total int16 values).
 * channels : number of channels per frame.
 * base_time_ns : timestamp_ns of the first sample in this block.
 *
 * Returns a pointer to a static anomaly_event_t if an event completed this
 * block, otherwise NULL.
 */
anomaly_event_t *anomaly_detector_process(anomaly_detector_t *ad,
                                          int16_t *samples, uint32_t count,
                                          uint32_t channels,
                                          uint64_t base_time_ns);

#endif // ANOMALY_DETECTOR_H
