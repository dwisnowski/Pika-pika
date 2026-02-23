#ifndef LOGGER_CONFIG_H
#define LOGGER_CONFIG_H

#include <stdint.h>

typedef struct {
  int32_t sag_threshold_pct;
  uint32_t sag_min_duration_ms;

  int32_t swell_threshold_pct;
  uint32_t swell_min_duration_ms;

  int32_t spike_threshold_pct;
  uint32_t spike_max_duration_ms;

  int32_t dip_threshold_pct;
  uint32_t dip_max_duration_ms;
} anomaly_config_t;

typedef struct {
  uint32_t nominal_rate_hz;
  uint32_t channels;
  uint32_t normal_decimation_rate;

  anomaly_config_t anomalies;

  double pre_event_sec;
  double post_event_sec;

  uint32_t ram_flush_mb;
} logger_config_t;

/**
 * Loads configuration from a YAML file.
 * Returns 0 on success.
 */
int config_load(const char *path, logger_config_t *config);

#endif // LOGGER_CONFIG_H
