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
  uint32_t max_decimated_mb; // Rotate decimated.bin when it exceeds this
  uint32_t max_events_mb;    // Rotate events.bin when it exceeds this
} storage_config_t;

typedef struct {
  uint32_t sag_cooldown_ms;
  uint32_t swell_cooldown_ms;
  uint32_t spike_cooldown_ms;
} debounce_config_t;

typedef struct {
  uint32_t rms_window_cycles; // RMS window = N full AC cycles
  uint32_t learn_cycles;      // Auto-learn nominal VRMS from first N cycles
  uint32_t ac_freq_hz;        // Mains AC frequency (60 or 50)
} detection_config_t;

typedef struct {
  float adc_vref;           // AD7606 input range (e.g. 5.0 for +/-5V)
  uint32_t adc_bits;        // ADC resolution (16)
  float transformer_ratio;  // ZMPT101B: mains_vrms / adc_output_amplitude
  uint32_t active_channels; // Channels actively in use (1 = ch0 only)
} sensor_config_t;

typedef struct {
  uint32_t nominal_rate_hz;
  uint32_t channels;
  uint32_t normal_decimation_rate;

  anomaly_config_t anomalies;
  storage_config_t storage;
  debounce_config_t debounce;
  detection_config_t detection;
  sensor_config_t sensor;

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
