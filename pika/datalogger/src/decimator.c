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

  dec->nominal_rate_hz = nominal_rate_hz;
  dec->ac_freq_hz = ac_freq_hz;
  dec->samples_per_bucket = (nominal_rate_hz * iec_cycles) / ac_freq_hz;
  if (dec->samples_per_bucket == 0)
    dec->samples_per_bucket = 1;

  dec->samples_per_quarter = nominal_rate_hz / (ac_freq_hz * 4U);
  if (dec->samples_per_quarter == 0)
    dec->samples_per_quarter = 1;

  dec->output_rate_hz = ac_freq_hz / iec_cycles;
  if (dec->output_rate_hz == 0)
    dec->output_rate_hz = 1;

  dec->samples_in_bucket = 0;
  dec->valid_in_bucket = 0;
  dec->sum = 0.0;
  dec->sum_sq = 0.0;
  dec->min_mains = 0.0f;
  dec->max_mains = 0.0f;

  dec->qtr_sum_sq = 0.0;
  dec->qtr_count = 0;
  dec->qtr_min_rms = 0.0f;
  dec->qtr_max_rms = 0.0f;
  dec->qtr_have = 0;

  dec->prev_ac = 0.0f;
  dec->have_prev_ac = 0;
  dec->last_zc_sample = 0;
  dec->have_zc = 0;
  dec->period_sum_samples = 0.0;
  dec->period_count = 0;
  dec->last_freq_hz = (float)ac_freq_hz;

  dec->adc_vref = 5.0f;
  dec->adc_bits = 16;
  dec->transformer_ratio = 120.0f;

  dec->dc_ema = 0.0f;
  dec->dc_initialized = 0;
  dec->ema_alpha = 1.0f / (float)dec->samples_per_bucket;

  printf("[Decimator] IEC init: rate=%u Hz, ac=%u Hz, cycles=%u, "
         "samples/bucket=%u, qtr=%u, output≈%u Hz\n",
         nominal_rate_hz, ac_freq_hz, iec_cycles, dec->samples_per_bucket,
         dec->samples_per_quarter, dec->output_rate_hz);
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

static int16_t clamp_centihertz(float hz) {
  float ch = hz * 100.0f;
  if (ch > 32767.0f)
    return 32767;
  if (ch < 0.0f)
    return 0;
  return (int16_t)roundf(ch);
}

static void finish_quarter(decimator_t *dec) {
  if (dec->qtr_count == 0)
    return;
  float rms = (float)sqrt(dec->qtr_sum_sq / (double)dec->qtr_count);
  if (!dec->qtr_have) {
    dec->qtr_min_rms = rms;
    dec->qtr_max_rms = rms;
    dec->qtr_have = 1;
  } else {
    if (rms < dec->qtr_min_rms)
      dec->qtr_min_rms = rms;
    if (rms > dec->qtr_max_rms)
      dec->qtr_max_rms = rms;
  }
  dec->qtr_sum_sq = 0.0;
  dec->qtr_count = 0;
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

  /* Ignore ADC rail hits — rare glitches saturate int16 envelopes. */
  const int near_rail = (sample <= -32000 || sample >= 32000);

  if (dec->samples_in_bucket == 0) {
    dec->min_mains = 0.0f;
    dec->max_mains = 0.0f;
    dec->sum = 0.0;
    dec->sum_sq = 0.0;
    dec->valid_in_bucket = 0;
    dec->qtr_sum_sq = 0.0;
    dec->qtr_count = 0;
    dec->qtr_have = 0;
    dec->period_sum_samples = 0.0;
    dec->period_count = 0;
    dec->have_zc = 0;
    dec->have_prev_ac = 0;
  }

  if (!near_rail) {
    if (dec->valid_in_bucket == 0) {
      dec->min_mains = v_mains;
      dec->max_mains = v_mains;
    } else {
      if (v_mains < dec->min_mains)
        dec->min_mains = v_mains;
      if (v_mains > dec->max_mains)
        dec->max_mains = v_mains;
    }
    dec->sum += (double)v_mains;
    dec->sum_sq += (double)v_mains * (double)v_mains;
    dec->valid_in_bucket++;

    dec->qtr_sum_sq += (double)v_mains * (double)v_mains;
    dec->qtr_count++;
    if (dec->qtr_count >= dec->samples_per_quarter)
      finish_quarter(dec);

    /* Rising zero-crossing period estimate on AC-coupled ADC volts. */
    if (dec->have_prev_ac && dec->prev_ac < 0.0f && v_ac >= 0.0f) {
      if (dec->have_zc) {
        uint32_t period = dec->samples_in_bucket - dec->last_zc_sample;
        if (period > 0) {
          dec->period_sum_samples += (double)period;
          dec->period_count++;
        }
      }
      dec->last_zc_sample = dec->samples_in_bucket;
      dec->have_zc = 1;
    }
    dec->prev_ac = v_ac;
    dec->have_prev_ac = 1;
  }
  dec->samples_in_bucket++;

  if (dec->samples_in_bucket < dec->samples_per_bucket)
    return 0;

  finish_quarter(dec);

  if (dec->valid_in_bucket == 0) {
    out->vrms_centivolts = 0;
    out->min_centivolts = 0;
    out->max_centivolts = 0;
    out->qtr_min_rms_centivolts = 0;
    out->qtr_max_rms_centivolts = 0;
    out->freq_centihertz = clamp_centihertz(dec->last_freq_hz);
    dec->samples_in_bucket = 0;
    return 1;
  }

  double n = (double)dec->valid_in_bucket;
  double mean = dec->sum / n;
  double var = dec->sum_sq / n - mean * mean;
  if (var < 0.0)
    var = 0.0;
  float vrms = (float)sqrt(var);

  float min_ac = dec->min_mains - (float)mean;
  float max_ac = dec->max_mains - (float)mean;
  float crest_cap = vrms * 2.2f;
  if (crest_cap < 80.0f)
    crest_cap = 80.0f;
  if (crest_cap > 320.0f)
    crest_cap = 320.0f;
  if (min_ac < -crest_cap)
    min_ac = -crest_cap;
  if (max_ac > crest_cap)
    max_ac = crest_cap;

  float qtr_min = dec->qtr_have ? dec->qtr_min_rms : vrms;
  float qtr_max = dec->qtr_have ? dec->qtr_max_rms : vrms;

  float freq_hz = dec->last_freq_hz;
  if (dec->period_count > 0 && dec->nominal_rate_hz > 0) {
    double avg_period = dec->period_sum_samples / (double)dec->period_count;
    if (avg_period > 0.0) {
      freq_hz = (float)((double)dec->nominal_rate_hz / avg_period);
      if (freq_hz >= 40.0f && freq_hz <= 70.0f)
        dec->last_freq_hz = freq_hz;
      else
        freq_hz = dec->last_freq_hz;
    }
  }

  out->vrms_centivolts = clamp_centivolts(vrms);
  out->min_centivolts = clamp_centivolts(min_ac);
  out->max_centivolts = clamp_centivolts(max_ac);
  out->qtr_min_rms_centivolts = clamp_centivolts(qtr_min);
  out->qtr_max_rms_centivolts = clamp_centivolts(qtr_max);
  out->freq_centihertz = clamp_centihertz(freq_hz);

  dec->samples_in_bucket = 0;
  return 1;
}
