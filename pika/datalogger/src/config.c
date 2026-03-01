#include "logger_config.h"
#include <stdio.h>
#include <string.h>
#include <yaml.h>

/**
 * YAML config loader using libyaml.
 * Handles nested sections via a simple state machine tracking the last
 * parent section key seen.
 * 
 * Loads pika.yaml which contains all configuration for all components.
 */
static int config_load_file(const char *path, logger_config_t *config) {
  FILE *fh = fopen(path, "r");
  if (!fh) {
    perror("Failed to open config file");
    return -1;
  }

  yaml_parser_t parser;
  yaml_token_t token;

  if (!yaml_parser_initialize(&parser)) {
    fclose(fh);
    return -1;
  }

  yaml_parser_set_input_file(&parser, fh);

  char section[64] = "";
  char *last_key = NULL;
  int expect_val = 0;

  while (1) {
    yaml_parser_scan(&parser, &token);
    if (token.type == YAML_STREAM_END_TOKEN) {
      yaml_token_delete(&token);
      break;
    }

    switch (token.type) {
    case YAML_KEY_TOKEN:
      expect_val = 0;
      break;

    case YAML_VALUE_TOKEN:
      expect_val = 1;
      break;

    case YAML_SCALAR_TOKEN: {
      char *val = (char *)token.data.scalar.value;

      if (!expect_val) {
        free(last_key);
        last_key = strdup(val);
        if (strcmp(val, "sampling") == 0 || strcmp(val, "anomalies") == 0 || 
            strcmp(val, "sag") == 0 || strcmp(val, "swell") == 0 || 
            strcmp(val, "spike") == 0 || strcmp(val, "storage") == 0 || 
            strcmp(val, "decimation") == 0 || strcmp(val, "events") == 0 ||
            strcmp(val, "debounce") == 0 || strcmp(val, "detection") == 0 ||
            strcmp(val, "sensor") == 0 || strcmp(val, "buffers") == 0) {
          strncpy(section, val, sizeof(section) - 1);
        }
      } else {
        if (!last_key)
          break;

        /* sampling (shared config) */
        if (strcmp(last_key, "nominal_rate_hz") == 0)
          config->nominal_rate_hz = (uint32_t)atoi(val);
        /* buffers (datalogger config) */
        else if (strcmp(last_key, "ram_flush_mb") == 0)
          config->ram_flush_mb = (uint32_t)atoi(val);
        /* storage.decimation (datalogger config) */
        else if (strcmp(section, "decimation") == 0 && strcmp(last_key, "target_output_rate_hz") == 0)
          config->storage.decimation.target_output_rate_hz = (uint32_t)atoi(val);
        else if (strcmp(section, "decimation") == 0 && strcmp(last_key, "max_mb") == 0)
          config->storage.decimation.max_mb = (uint32_t)atoi(val);
        /* storage.events (datalogger config) */
        else if (strcmp(section, "events") == 0 && strcmp(last_key, "pre_sec") == 0)
          config->storage.events.pre_sec = atof(val);
        else if (strcmp(section, "events") == 0 && strcmp(last_key, "post_sec") == 0)
          config->storage.events.post_sec = atof(val);
        else if (strcmp(section, "events") == 0 && strcmp(last_key, "max_mb") == 0)
          config->storage.events.max_mb = (uint32_t)atoi(val);
        /* debounce (datalogger config) */
        else if (strcmp(last_key, "sag_cooldown_ms") == 0)
          config->debounce.sag_cooldown_ms = (uint32_t)atoi(val);
        else if (strcmp(last_key, "swell_cooldown_ms") == 0)
          config->debounce.swell_cooldown_ms = (uint32_t)atoi(val);
        else if (strcmp(last_key, "spike_cooldown_ms") == 0)
          config->debounce.spike_cooldown_ms = (uint32_t)atoi(val);
        /* detection (shared config) */
        else if (strcmp(last_key, "rms_window_cycles") == 0)
          config->detection.rms_window_cycles = (uint32_t)atoi(val);
        else if (strcmp(last_key, "learn_cycles") == 0)
          config->detection.learn_cycles = (uint32_t)atoi(val);
        else if (strcmp(last_key, "ac_freq_hz") == 0)
          config->detection.ac_freq_hz = (uint32_t)atoi(val);
        /* sensor (shared config) */
        else if (strcmp(last_key, "adc_vref") == 0)
          config->sensor.adc_vref = (float)atof(val);
        else if (strcmp(last_key, "adc_bits") == 0)
          config->sensor.adc_bits = (uint32_t)atoi(val);
        else if (strcmp(last_key, "transformer_ratio") == 0)
          config->sensor.transformer_ratio = (float)atof(val);
        else if (strcmp(last_key, "target_mains_vrms") == 0)
          config->sensor.target_mains_vrms = (float)atof(val);
        else if (strcmp(last_key, "active_channels") == 0)
          config->sensor.active_channels = (uint32_t)atoi(val);
        else if (strcmp(last_key, "ch0_enable") == 0)
          config->sensor.ch_enable[0] = (uint32_t)atoi(val);
        else if (strcmp(last_key, "ch1_enable") == 0)
          config->sensor.ch_enable[1] = (uint32_t)atoi(val);
        else if (strcmp(last_key, "ch2_enable") == 0)
          config->sensor.ch_enable[2] = (uint32_t)atoi(val);
        else if (strcmp(last_key, "ch3_enable") == 0)
          config->sensor.ch_enable[3] = (uint32_t)atoi(val);
        else if (strcmp(last_key, "ch4_enable") == 0)
          config->sensor.ch_enable[4] = (uint32_t)atoi(val);
        else if (strcmp(last_key, "ch5_enable") == 0)
          config->sensor.ch_enable[5] = (uint32_t)atoi(val);
        else if (strcmp(last_key, "ch6_enable") == 0)
          config->sensor.ch_enable[6] = (uint32_t)atoi(val);
        else if (strcmp(last_key, "ch7_enable") == 0)
          config->sensor.ch_enable[7] = (uint32_t)atoi(val);
        /* anomalies (shared config) */
        else if (strcmp(last_key, "threshold_pct") == 0) {
          if (strcmp(section, "sag") == 0)
            config->anomalies.sag_threshold_pct = atoi(val);
          else if (strcmp(section, "swell") == 0)
            config->anomalies.swell_threshold_pct = atoi(val);
          else if (strcmp(section, "spike") == 0)
            config->anomalies.spike_threshold_pct = atoi(val);
        } else if (strcmp(last_key, "min_duration_ms") == 0) {
          if (strcmp(section, "sag") == 0)
            config->anomalies.sag_min_duration_ms = (uint32_t)atoi(val);
          else if (strcmp(section, "swell") == 0)
            config->anomalies.swell_min_duration_ms = (uint32_t)atoi(val);
        } else if (strcmp(last_key, "max_duration_ms") == 0) {
          if (strcmp(section, "spike") == 0)
            config->anomalies.spike_max_duration_ms = (uint32_t)atoi(val);
        }

        expect_val = 0;
      }
      break;
    }

    default:
      break;
    }

    yaml_token_delete(&token);
  }

  free(last_key);
  yaml_parser_delete(&parser);
  fclose(fh);

  return 0;
}

int config_load(const char *path, logger_config_t *config) {
  /* ---- Defaults ---- */
  config->nominal_rate_hz = 10000;
  config->ram_flush_mb = 64;

  /* storage */
  config->storage.decimation.target_output_rate_hz = 50;
  config->storage.decimation.max_mb = 250;
  config->storage.events.pre_sec = 0.5;
  config->storage.events.post_sec = 0.5;
  config->storage.events.max_mb = 250;

  /* debounce */
  config->debounce.sag_cooldown_ms = 1000;
  config->debounce.swell_cooldown_ms = 1000;
  config->debounce.spike_cooldown_ms = 1000;

  /* detection */
  config->detection.rms_window_cycles = 30;
  config->detection.learn_cycles = 300;
  config->detection.ac_freq_hz = 60;

  /* sensor */
  config->sensor.adc_vref = 5.0f;
  config->sensor.adc_bits = 16;
  config->sensor.transformer_ratio = 120.0f;
  config->sensor.target_mains_vrms = 120.0f;
  config->sensor.active_channels = 1;
  for (int i = 0; i < 8; i++) {
    config->sensor.ch_enable[i] = (i == 0) ? 1 : 0;  /* Default: ch0 only */
  }

  /* anomalies */
  config->anomalies.sag_threshold_pct = -10;
  config->anomalies.sag_min_duration_ms = 8;
  config->anomalies.swell_threshold_pct = 10;
  config->anomalies.swell_min_duration_ms = 8;
  config->anomalies.spike_threshold_pct = 20;
  config->anomalies.spike_max_duration_ms = 100;

  /* Load pika.yaml (single source of truth) */
  if (config_load_file(path, config) != 0) {
    fprintf(stderr, "[Config] Warning: Failed to load config\n");
  }

  printf("[Config] nominal_rate=%u, rms_window_cycles=%u, learn_cycles=%u, "
         "ac_freq=%u, transformer_ratio=%.1f, max_events_mb=%u\n",
         config->nominal_rate_hz, config->detection.rms_window_cycles,
         config->detection.learn_cycles, config->detection.ac_freq_hz,
         config->sensor.transformer_ratio, config->storage.events.max_mb);

  return 0;
}
