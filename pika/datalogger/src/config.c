#include "logger_config.h"
#include <stdio.h>
#include <string.h>
#include <yaml.h>

/**
 * Basic YAML loader using libyaml.
 * This is a simplified version; in a real app, you might want more robust error
 * handling.
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

  char *last_key = NULL;

  // Default values
  config->nominal_rate_hz = 10000;
  config->channels = 8;
  config->normal_decimation_rate = 1000;
  config->ram_flush_mb = 64;

  while (1) {
    yaml_parser_scan(&parser, &token);
    if (token.type == YAML_STREAM_END_TOKEN)
      break;

    if (token.type == YAML_KEY_TOKEN) {
      // Next scalar is a key
    } else if (token.type == YAML_VALUE_TOKEN) {
      // Next scalar is a value
    } else if (token.type == YAML_SCALAR_TOKEN) {
      char *value = (char *)token.data.scalar.value;

      if (!last_key) {
        last_key = strdup(value);
      } else {
        // Determine which field to set
        if (strcmp(last_key, "nominal_rate_hz") == 0)
          config->nominal_rate_hz = atoi(value);
        else if (strcmp(last_key, "channels") == 0)
          config->channels = atoi(value);
        else if (strcmp(last_key, "normal_rate") == 0)
          config->normal_decimation_rate = atoi(value);
        else if (strcmp(last_key, "pre_event_sec") == 0)
          config->pre_event_sec = atof(value);
        else if (strcmp(last_key, "post_event_sec") == 0)
          config->post_event_sec = atof(value);
        else if (strcmp(last_key, "ram_flush_mb") == 0)
          config->ram_flush_mb = atoi(value);

        // Anomaly fields (simplified flat check for now)
        else if (strcmp(last_key, "threshold_pct") == 0) {
          // Logic to handle nested keys would go here
          // For now, we'll just set a placeholder or assume a specific order
        }

        free(last_key);
        last_key = NULL;
      }
    }
    yaml_token_delete(&token);
  }

  yaml_parser_delete(&parser);
  fclose(fh);
  return 0;
}
