#ifndef ANOMALY_DETECTOR_H
#define ANOMALY_DETECTOR_H

#include "event_types.h"
#include "logger_config.h"
#include "time_utils.h"
#include <stdint.h>

#define AD_MAX_NOTIFICATIONS 8

typedef enum {
  AD_NOTIFY_STARTED = 1,
  AD_NOTIFY_COMPLETED = 2,
} ad_notify_kind_t;

typedef struct {
  ad_notify_kind_t kind;
  anomaly_event_t event;
} ad_notification_t;

typedef struct {
  anomaly_config_t config;
  sensor_config_t sensor;
  detection_config_t detection;
  uint32_t nominal_rate_hz;
  uint64_t ns_per_sample;

  float sq_sum;
  uint32_t rms_window_samples;
  float *sq_ring;
  uint32_t sq_head;
  uint32_t sq_count;

  float dc_ema;
  float ema_alpha;

  float nominal_vrms;
  uint32_t learn_samples_total;
  uint32_t learn_samples_left;
  float learn_sq_sum;
  uint32_t learn_count;

  uint32_t sag_min_duration_samples;
  uint32_t swell_min_duration_samples;

  int in_event;
  event_type_t current_type;
  uint32_t current_duration;
  uint64_t start_time_ns;
  int16_t peak_raw;

  uint64_t last_event_end_ns[5];

  uint64_t sag_cooldown_ns;
  uint64_t swell_cooldown_ns;
  uint64_t spike_cooldown_ns;
} anomaly_detector_t;

int anomaly_detector_init(anomaly_detector_t *ad, anomaly_config_t config,
                          sensor_config_t sensor, detection_config_t detection,
                          debounce_config_t debounce, uint32_t nominal_rate_hz);

void anomaly_detector_free(anomaly_detector_t *ad);

/**
 * Process one sample. Writes at most one notification. Returns 1 if written.
 */
int anomaly_detector_process_sample(anomaly_detector_t *ad, int16_t raw,
                                  uint64_t sample_time_ns,
                                  ad_notification_t *out);

#endif /* ANOMALY_DETECTOR_H */
