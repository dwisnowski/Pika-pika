#include "logger_config.h"
#include <stdio.h>
#include <string.h>
#include <yaml.h>

/**
 * YAML config loader using libyaml.
 * Handles nested sections via a simple state machine tracking the last
 * parent section key seen.
 */
int config_load(const char *path, logger_config_t *config) {
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

  /* ---- Defaults ---- */
  config->nominal_rate_hz = 10000;
  config->channels = 8;
  config->normal_decimation_rate = 1000;
  config->ram_flush_mb = 64;
  config->pre_event_sec = 0.5;
  config->post_event_sec = 0.5;

  /* storage */
  config->storage.max_decimated_mb = 250;
  config->storage.max_events_mb = 250;

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
  config->sensor.active_channels = 1;

  /* anomalies */
  config->anomalies.sag_threshold_pct = -10;
  config->anomalies.sag_min_duration_ms = 8;
  config->anomalies.swell_threshold_pct = 10;
  config->anomalies.swell_min_duration_ms = 8;
  config->anomalies.spike_threshold_pct = 20;
  config->anomalies.spike_max_duration_ms = 100;

  /* ---- Parse ---- */
  char section[64] = ""; /* top-level section tracker */
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
        /* This is a key */
        free(last_key);
        last_key = strdup(val);
        /* Track top-level section changes */
        if (strcmp(val, "sampling") == 0 || strcmp(val, "decimation") == 0 ||
            strcmp(val, "anomalies") == 0 || strcmp(val, "sag") == 0 ||
            strcmp(val, "swell") == 0 || strcmp(val, "spike") == 0 ||
            strcmp(val, "event_window") == 0 || strcmp(val, "storage") == 0 ||
            strcmp(val, "debounce") == 0 || strcmp(val, "detection") == 0 ||
            strcmp(val, "sensor") == 0 || strcmp(val, "buffers") == 0) {
          strncpy(section, val, sizeof(section) - 1);
        }
      } else {
        /* This is a value — map key+section to struct field */
        if (!last_key)
          break;

        /* sampling */
        if (strcmp(last_key, "nominal_rate_hz") == 0)
          config->nominal_rate_hz = (uint32_t)atoi(val);
        else if (strcmp(last_key, "channels") == 0)
          config->channels = (uint32_t)atoi(val);
        /* decimation */
        else if (strcmp(last_key, "normal_rate") == 0)
          config->normal_decimation_rate = (uint32_t)atoi(val);
        /* event_window */
        else if (strcmp(last_key, "pre_event_sec") == 0)
          config->pre_event_sec = atof(val);
        else if (strcmp(last_key, "post_event_sec") == 0)
          config->post_event_sec = atof(val);
        /* buffers */
        else if (strcmp(last_key, "ram_flush_mb") == 0)
          config->ram_flush_mb = (uint32_t)atoi(val);
        /* storage */
        else if (strcmp(last_key, "max_decimated_mb") == 0)
          config->storage.max_decimated_mb = (uint32_t)atoi(val);
        else if (strcmp(last_key, "max_events_mb") == 0)
          config->storage.max_events_mb = (uint32_t)atoi(val);
        /* debounce */
        else if (strcmp(last_key, "sag_cooldown_ms") == 0)
          config->debounce.sag_cooldown_ms = (uint32_t)atoi(val);
        else if (strcmp(last_key, "swell_cooldown_ms") == 0)
          config->debounce.swell_cooldown_ms = (uint32_t)atoi(val);
        else if (strcmp(last_key, "spike_cooldown_ms") == 0)
          config->debounce.spike_cooldown_ms = (uint32_t)atoi(val);
        /* detection */
        else if (strcmp(last_key, "rms_window_cycles") == 0)
          config->detection.rms_window_cycles = (uint32_t)atoi(val);
        else if (strcmp(last_key, "learn_cycles") == 0)
          config->detection.learn_cycles = (uint32_t)atoi(val);
        else if (strcmp(last_key, "ac_freq_hz") == 0)
          config->detection.ac_freq_hz = (uint32_t)atoi(val);
        /* sensor */
        else if (strcmp(last_key, "adc_vref") == 0)
          config->sensor.adc_vref = (float)atof(val);
        else if (strcmp(last_key, "adc_bits") == 0)
          config->sensor.adc_bits = (uint32_t)atoi(val);
        else if (strcmp(last_key, "transformer_ratio") == 0)
          config->sensor.transformer_ratio = (float)atof(val);
        else if (strcmp(last_key, "active_channels") == 0)
          config->sensor.active_channels = (uint32_t)atoi(val);
        /* anomalies — use section to disambiguate threshold_pct/min_duration */
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

  printf("[Config] nominal_rate=%u, rms_window_cycles=%u, learn_cycles=%u, "
         "ac_freq=%u, transformer_ratio=%.1f, max_events_mb=%u\n",
         config->nominal_rate_hz, config->detection.rms_window_cycles,
         config->detection.learn_cycles, config->detection.ac_freq_hz,
         config->sensor.transformer_ratio, config->storage.max_events_mb);

  return 0;
}
