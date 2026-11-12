#include "harmonic_analyzer.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

static void rotate_jsonl_if_needed(harmonic_analyzer_t *ha) {
  if (ha->max_bytes == 0)
    return;
  FILE *f = fopen(ha->path, "ab");
  if (!f)
    return;
  long pos = ftell(f);
  fclose(f);
  if (pos < 0 || (uint64_t)pos < ha->max_bytes)
    return;

  char old_path[300];
  snprintf(old_path, sizeof(old_path), "%s.old", ha->path);
  rename(ha->path, old_path);
  printf("[Harmonics] Rotated %s -> %s\n", ha->path, old_path);
}

static float goertzel_mag(const float *x, uint32_t n, float freq_hz,
                          float sample_rate_hz) {
  if (n == 0 || sample_rate_hz <= 0.0f || freq_hz <= 0.0f)
    return 0.0f;
  float k = 0.5f + (freq_hz * (float)n / sample_rate_hz);
  float w = (float)(2.0 * M_PI * k / (float)n);
  float coeff = 2.0f * cosf(w);
  float s0 = 0.0f, s1 = 0.0f, s2 = 0.0f;
  for (uint32_t i = 0; i < n; i++) {
    s0 = x[i] + coeff * s1 - s2;
    s2 = s1;
    s1 = s0;
  }
  float real = s1 - s2 * cosf(w);
  float imag = s2 * sinf(w);
  return sqrtf(real * real + imag * imag) * 2.0f / (float)n;
}

static void analyze_window(harmonic_analyzer_t *ha, uint64_t ts_ns) {
  if (ha->count < 8)
    return;

  float fund = (float)ha->ac_freq_hz;
  float rate = (float)ha->nominal_rate_hz;
  float mag[HARMONIC_MAX_ORDER + 1];
  memset(mag, 0, sizeof(mag));

  for (uint32_t h = 1; h <= HARMONIC_MAX_ORDER; h++) {
    mag[h] = goertzel_mag(ha->buf, ha->count, fund * (float)h, rate);
  }

  if (mag[1] < 1e-6f)
    return;

  float thd_num = 0.0f;
  float harm_pct[HARMONIC_MAX_ORDER + 1];
  memset(harm_pct, 0, sizeof(harm_pct));
  harm_pct[1] = 100.0f;
  for (uint32_t h = 2; h <= HARMONIC_MAX_ORDER; h++) {
    float pct = (mag[h] / mag[1]) * 100.0f;
    harm_pct[h] = pct;
    thd_num += mag[h] * mag[h];
  }
  float thd_pct = (sqrtf(thd_num) / mag[1]) * 100.0f;

  ha->windows_since_emit++;
  if (ha->windows_since_emit < ha->emit_every)
    return;
  ha->windows_since_emit = 0;

  rotate_jsonl_if_needed(ha);

  FILE *f = fopen(ha->path, "a");
  if (!f) {
    perror("[Harmonics] fopen");
    return;
  }

  fprintf(f, "{\"ts_ns\":%llu,\"thd_pct\":%.3f,\"h\":[",
          (unsigned long long)ts_ns, thd_pct);
  for (uint32_t h = 1; h <= HARMONIC_MAX_ORDER; h++) {
    if (h > 1)
      fputc(',', f);
    fprintf(f, "%.3f", harm_pct[h]);
  }
  fprintf(f, "]}\n");
  fclose(f);
}

int harmonic_analyzer_init(harmonic_analyzer_t *ha, const char *base_path,
                           uint32_t nominal_rate_hz, uint32_t ac_freq_hz,
                           uint32_t iec_cycles, uint32_t emit_every,
                           uint32_t max_mb) {
  if (!ha)
    return -1;
  memset(ha, 0, sizeof(*ha));

  if (nominal_rate_hz == 0)
    nominal_rate_hz = 10000;
  if (ac_freq_hz == 0)
    ac_freq_hz = 60;
  if (iec_cycles == 0)
    iec_cycles = (ac_freq_hz == 50) ? 10U : 12U;
  if (emit_every == 0)
    emit_every = 15;

  ha->nominal_rate_hz = nominal_rate_hz;
  ha->ac_freq_hz = ac_freq_hz;
  ha->samples_per_window = (nominal_rate_hz * iec_cycles) / ac_freq_hz;
  if (ha->samples_per_window == 0)
    ha->samples_per_window = 1;
  ha->capacity = ha->samples_per_window;
  ha->emit_every = emit_every;
  ha->max_bytes = (uint64_t)max_mb * 1024ULL * 1024ULL;
  ha->adc_vref = 5.0f;
  ha->adc_bits = 16;
  ha->transformer_ratio = 120.0f;
  ha->ema_alpha = 1.0f / (float)ha->samples_per_window;

  snprintf(ha->path, sizeof(ha->path), "%s/harmonics.jsonl",
           base_path ? base_path : "data");

  ha->buf = (float *)calloc(ha->capacity, sizeof(float));
  if (!ha->buf) {
    fprintf(stderr, "[Harmonics] Failed to allocate %u floats\n", ha->capacity);
    return -1;
  }

  mkdir(base_path ? base_path : "data", 0777);
  printf("[Harmonics] IEC window=%u samples, emit every %u windows, "
         "file=%s (max %u MB)\n",
         ha->samples_per_window, ha->emit_every, ha->path, max_mb);
  return 0;
}

void harmonic_analyzer_set_calibration(harmonic_analyzer_t *ha, float adc_vref,
                                       uint32_t adc_bits,
                                       float transformer_ratio) {
  if (!ha)
    return;
  if (adc_vref > 0.0f)
    ha->adc_vref = adc_vref;
  if (adc_bits > 0)
    ha->adc_bits = adc_bits;
  if (transformer_ratio > 0.0f)
    ha->transformer_ratio = transformer_ratio;
}

void harmonic_analyzer_free(harmonic_analyzer_t *ha) {
  if (!ha)
    return;
  free(ha->buf);
  ha->buf = NULL;
}

int harmonic_analyzer_process(harmonic_analyzer_t *ha, int16_t sample,
                              uint64_t sample_time_ns) {
  if (!ha || !ha->buf)
    return 0;

  float full_scale = (float)(1u << (ha->adc_bits - 1));
  float v_adc = (float)sample * (ha->adc_vref / full_scale);
  if (!ha->dc_initialized) {
    ha->dc_ema = v_adc;
    ha->dc_initialized = 1;
  }
  ha->dc_ema = ha->ema_alpha * v_adc + (1.0f - ha->ema_alpha) * ha->dc_ema;
  float v_mains = (v_adc - ha->dc_ema) * ha->transformer_ratio;

  if (ha->count < ha->capacity)
    ha->buf[ha->count++] = v_mains;

  if (ha->count < ha->samples_per_window)
    return 0;

  uint64_t window_start =
      sample_time_ns -
      (uint64_t)(ha->samples_per_window - 1) *
          (1000000000ULL / (ha->nominal_rate_hz ? ha->nominal_rate_hz : 1));
  analyze_window(ha, window_start);
  ha->count = 0;
  return 1;
}
