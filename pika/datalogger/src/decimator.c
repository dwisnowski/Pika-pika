#include "decimator.h"
#include <math.h>
#include <stdio.h>

void decimator_set_calibration(decimator_t *dec, float adc_vref,
                               uint32_t adc_bits, float transformer_ratio) {
  if (!dec)
    return;
  if (adc_vref > 0.0f)
    dec->adc_vref = adc_vref;
  if (adc_bits > 0)
    dec->adc_bits = adc_bits;
  if (transformer_ratio > 0.0f)
    dec->transformer_ratio = transformer_ratio;
}

void decimator_init_iec(decimator_t *dec, uint32_t nominal_rate_hz,
                        uint32_t ac_freq_hz, uint32_t iec_cycles) {
  if (!dec)
    return;

  if (nominal_rate_hz == 0)
    nominal_rate_hz = 10000;
  if (ac_freq_hz == 0)
    ac_freq_hz = 60;
  if (iec_cycles == 0) {
    iec_cycles = (ac_freq_hz == 50) ? DECIMATOR_IEC_CYCLES_50HZ
                                    : DECIMATOR_IEC_CYCLES_60HZ;
  }

  dec->samples_per_bucket =
      (nominal_rate_hz * iec_cycles) / ac_freq_hz;
  if (dec->samples_per_bucket == 0)
    dec->samples_per_bucket = 1;

  dec->output_rate_hz = ac_freq_hz / iec_cycles;
  if (dec->output_rate_hz == 0)
    dec->output_rate_hz = 1;

  dec->samples_in_bucket = 0;
  dec->sum = 0.0;
  dec->sum_sq = 0.0;
  dec->min_mains = 0.0f;
  dec->max_mains = 0.0f;

  dec->adc_vref = 5.0f;
  dec->adc_bits = 16;
  dec->transformer_ratio = 120.0f;

  dec->dc_ema = 0.0f;
  dec->dc_initialized = 0;
  dec->ema_alpha = 1.0f / (float)dec->samples_per_bucket;

  printf("[Decimator] IEC init: rate=%u Hz, ac=%u Hz, cycles=%u, "
         "samples/bucket=%u, output≈%u Hz\n",
         nominal_rate_hz, ac_freq_hz, iec_cycles, dec->samples_per_bucket,
         dec->output_rate_hz);
}

static float adc_counts_to_volts(const decimator_t *dec, int16_t sample) {
  float full_scale = (float)(1u << (dec->adc_bits - 1));
  return (float)sample * (dec->adc_vref / full_scale);
}

static int16_t clamp_centivolts(float volts) {
  float cv = volts * 100.0f;
  if (cv > 32767.0f)
    return 32767;
  if (cv < -32768.0f)
    return -32768;
  return (int16_t)roundf(cv);
}

int decimator_process(decimator_t *dec, int16_t sample,
                      decimated_interval_t *out) {
  if (!dec || !out)
    return 0;

  float v_adc = adc_counts_to_volts(dec, sample);
  if (!dec->dc_initialized) {
    dec->dc_ema = v_adc;
    dec->dc_initialized = 1;
  }
  dec->dc_ema =
      dec->ema_alpha * v_adc + (1.0f - dec->ema_alpha) * dec->dc_ema;
  float v_ac = v_adc - dec->dc_ema;
  float v_mains = v_ac * dec->transformer_ratio;

  if (dec->samples_in_bucket == 0) {
    dec->min_mains = v_mains;
    dec->max_mains = v_mains;
    dec->sum = 0.0;
    dec->sum_sq = 0.0;
  }

  if (v_mains < dec->min_mains)
    dec->min_mains = v_mains;
  if (v_mains > dec->max_mains)
    dec->max_mains = v_mains;

  dec->sum += (double)v_mains;
  dec->sum_sq += (double)v_mains * (double)v_mains;
  dec->samples_in_bucket++;

  if (dec->samples_in_bucket < dec->samples_per_bucket)
    return 0;

  double n = (double)dec->samples_in_bucket;
  double mean = dec->sum / n;
  double var = dec->sum_sq / n - mean * mean;
  if (var < 0.0)
    var = 0.0;
  float vrms = (float)sqrt(var);

  out->vrms_centivolts = clamp_centivolts(vrms);
  out->min_centivolts = clamp_centivolts(dec->min_mains);
  out->max_centivolts = clamp_centivolts(dec->max_mains);

  dec->samples_in_bucket = 0;
  return 1;
}
