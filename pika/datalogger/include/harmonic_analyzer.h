#ifndef HARMONIC_ANALYZER_H
#define HARMONIC_ANALYZER_H

#include <stdint.h>

#define HARMONIC_MAX_ORDER 32

typedef struct {
  uint64_t timestamp_ns;
  float thd_pct;
  float harm_pct[HARMONIC_MAX_ORDER + 1]; /* [1]=100 (fundamental), [2..32] */
} harmonic_record_t;

typedef struct {
  uint32_t samples_per_window;
  uint32_t capacity;
  uint32_t count;
  float *buf; /* calibrated mains AC volts */

  float adc_vref;
  uint32_t adc_bits;
  float transformer_ratio;
  float dc_ema;
  int dc_initialized;
  float ema_alpha;

  uint32_t emit_every;
  uint32_t windows_since_emit;
  uint32_t ac_freq_hz;
  uint32_t nominal_rate_hz;

  char path[256];
  uint64_t max_bytes;
} harmonic_analyzer_t;

int harmonic_analyzer_init(harmonic_analyzer_t *ha, const char *base_path,
                           uint32_t nominal_rate_hz, uint32_t ac_freq_hz,
                           uint32_t iec_cycles, uint32_t emit_every,
                           uint32_t max_mb);

void harmonic_analyzer_set_calibration(harmonic_analyzer_t *ha, float adc_vref,
                                       uint32_t adc_bits,
                                       float transformer_ratio);

void harmonic_analyzer_free(harmonic_analyzer_t *ha);

/**
 * Feed one ADC sample. May append a harmonics.jsonl record when a window
 * completes and emit_every is satisfied. Returns 1 if a record was written.
 */
int harmonic_analyzer_process(harmonic_analyzer_t *ha, int16_t sample,
                              uint64_t sample_time_ns);

#endif /* HARMONIC_ANALYZER_H */
