#ifndef DECIMATOR_H
#define DECIMATOR_H

#include <stdint.h>

/** IEC 61000-4-30 base window: 12 cycles @ 60 Hz, 10 cycles @ 50 Hz. */
#define DECIMATOR_IEC_CYCLES_60HZ 12U
#define DECIMATOR_IEC_CYCLES_50HZ 10U

/**
 * Decimated interval record on disk:
 *   vps=2 (legacy): min, max ADC counts
 *   vps=3 (IEC):    vrms, env_min, env_max (centivolts)
 *   vps=6 (ADR-0009): vrms, env_min, env_max, qtr_rms_min, qtr_rms_max,
 *                     freq_centihertz (6000 = 60.00 Hz)
 */
typedef struct {
  int16_t vrms_centivolts;
  int16_t min_centivolts;
  int16_t max_centivolts;
  int16_t qtr_min_rms_centivolts;
  int16_t qtr_max_rms_centivolts;
  int16_t freq_centihertz;
} decimated_interval_t;

typedef struct {
  uint32_t samples_per_bucket;
  uint32_t samples_in_bucket;
  uint32_t samples_per_quarter;
  uint32_t output_rate_hz;
  uint32_t nominal_rate_hz;
  uint32_t ac_freq_hz;

  double sum;
  double sum_sq;
  float min_mains;
  float max_mains;

  /* ¼-cycle RMS extrema within the IEC bucket */
  double qtr_sum_sq;
  uint32_t qtr_count;
  float qtr_min_rms;
  float qtr_max_rms;
  int qtr_have;

  /* Zero-crossing frequency estimate over the IEC bucket */
  float prev_ac;
  int have_prev_ac;
  uint32_t last_zc_sample;
  int have_zc;
  double period_sum_samples;
  uint32_t period_count;
  float last_freq_hz;

  float adc_vref;
  uint32_t adc_bits;
  float transformer_ratio;

  float dc_ema;
  int dc_initialized;
  float ema_alpha;
  uint32_t valid_in_bucket;
} decimator_t;

/**
 * Initialize for IEC-aligned contiguous cycle windows.
 * samples_per_bucket = nominal_rate_hz * iec_cycles / ac_freq_hz
 * output_rate_hz ≈ ac_freq_hz / iec_cycles (5 Hz @ 60 Hz / 12 cycles)
 */
void decimator_init_iec(decimator_t *dec, uint32_t nominal_rate_hz,
                        uint32_t ac_freq_hz, uint32_t iec_cycles);

/** Update live calibration (call after auto-learn / whenever ratio changes). */
void decimator_set_calibration(decimator_t *dec, float adc_vref,
                               uint32_t adc_bits, float transformer_ratio);

/**
 * Process one ADC sample. Returns 1 when an interval is complete.
 * On success, fills *out with calibrated centivolt / frequency fields.
 */
int decimator_process(decimator_t *dec, int16_t sample,
                      decimated_interval_t *out);

#endif /* DECIMATOR_H */
