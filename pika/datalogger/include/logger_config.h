#ifndef LOGGER_CONFIG_H
#define LOGGER_CONFIG_H

#include <stdint.h>

/* AD7606 always has 8 channels */
#define CHANNELS 8

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
  uint32_t rate;             // Store 1/Nth of samples
  uint32_t max_mb;           // Rotate decimated.bin when it exceeds this
} decimation_config_t;

typedef struct {
  double pre_sec;            // Seconds of data before event
  double post_sec;           // Seconds of data after event
  uint32_t max_mb;           // Rotate events.bin when it exceeds this
} events_config_t;

typedef struct {
  decimation_config_t decimation;
  events_config_t events;
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
  uint32_t ch_enable[8];    // Per-channel enable flags (1 = read, 0 = skip)
} sensor_config_t;

typedef struct {
  uint32_t nominal_rate_hz;

  anomaly_config_t anomalies;
  storage_config_t storage;
  debounce_config_t debounce;
  detection_config_t detection;
  sensor_config_t sensor;

  uint32_t ram_flush_mb;
} logger_config_t;

/**
 * Loads configuration from a YAML file.
 * Returns 0 on success.
 */
int config_load(const char *path, logger_config_t *config);

#endif // LOGGER_CONFIG_H
