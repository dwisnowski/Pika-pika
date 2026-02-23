#ifndef ANOMALY_DETECTOR_H
#define ANOMALY_DETECTOR_H

#include "event_types.h"
#include "logger_config.h"
#include <stdint.h>

typedef struct {
  anomaly_config_t config;
  int16_t nominal_peak;

  // State for detector
  int in_event;
  event_type_t current_type;
  uint32_t current_duration;
  uint64_t start_time_ns;
} anomaly_detector_t;

void anomaly_detector_init(anomaly_detector_t *ad, anomaly_config_t config,
                           int16_t nominal_peak);

/**
 * Processes a block of samples.
 * Returns an event if one was completed in this block, otherwise NULL.
 */
anomaly_event_t *anomaly_detector_process(anomaly_detector_t *ad,
                                          uint16_t *samples, uint32_t count,
                                          uint64_t base_time_ns);

#endif // ANOMALY_DETECTOR_H
