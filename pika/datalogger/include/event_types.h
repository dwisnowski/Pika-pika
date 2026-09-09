#ifndef EVENT_TYPES_H
#define EVENT_TYPES_H

#include <stdint.h>

typedef enum {
  EVENT_TYPE_NONE = 0,
  EVENT_TYPE_SAG,
  EVENT_TYPE_SWELL,
  EVENT_TYPE_SPIKE,
  EVENT_TYPE_DIP
} event_type_t;

typedef struct {
  uint64_t timestamp_ns;
  event_type_t type;
  float rms_vrms; /* Extreme 1-cycle RMS during event (min sag / max swell) */
  int16_t peak_value; /* Raw ADC peak (wire-level debug only) */
  uint32_t duration_samples;
} anomaly_event_t;

#endif // EVENT_TYPES_H
