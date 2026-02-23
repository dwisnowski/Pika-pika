#include "anomaly_detector.h"
#include <stdio.h>
#include <stdlib.h>

static anomaly_event_t global_event_result; // For zero-malloc return

void anomaly_detector_init(anomaly_detector_t *ad, anomaly_config_t config,
                           int16_t nominal_peak) {
  ad->config = config;
  ad->nominal_peak = nominal_peak;
  ad->in_event = 0;
  ad->current_type = EVENT_TYPE_NONE;
  ad->current_duration = 0;
}

anomaly_event_t *anomaly_detector_process(anomaly_detector_t *ad,
                                          uint16_t *samples, uint32_t count,
                                          uint64_t base_time_ns) {
  // Basic threshold logic for Ch0 only as a proof of concept
  for (uint32_t i = 0; i < count; i++) {
    int16_t val = (int16_t)samples[i * 8]; // Assume 8 channels

    // Sag check (-10% of nominal)
    int sag_threshold =
        ad->nominal_peak * (100 + ad->config.sag_threshold_pct) / 100;

    if (abs(val) < sag_threshold) {
      if (!ad->in_event) {
        ad->in_event = 1;
        ad->current_type = EVENT_TYPE_SAG;
        ad->start_time_ns = base_time_ns + (i * 100000); // 10kHz sample rate
        ad->current_duration = 1;
        printf("[Detector] Event STARTED: Type SAG at %llu ns\n",
               ad->start_time_ns);
      } else {
        ad->current_duration++;
      }
    } else {
      if (ad->in_event && ad->current_type == EVENT_TYPE_SAG) {
        // Event ended
        global_event_result.type = EVENT_TYPE_SAG;
        global_event_result.timestamp_ns = ad->start_time_ns;
        global_event_result.duration_samples = ad->current_duration;
        global_event_result.peak_value = val;

        printf("[Detector] Event ENDED: Type SAG, Duration: %u samples\n",
               ad->current_duration);

        ad->in_event = 0;
        ad->current_type = EVENT_TYPE_NONE;
        return &global_event_result;
      }
    }
  }

  return NULL;
}
