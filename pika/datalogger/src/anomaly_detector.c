#include "anomaly_detector.h"
#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static inline uint64_t ms_to_ns(uint32_t ms) {
  return (uint64_t)ms * 1000000ULL;
}

static inline uint32_t ms_to_samples(uint32_t ms, uint32_t rate_hz) {
  if (rate_hz == 0)
    return 1;
  uint32_t s = (ms * rate_hz) / 1000U;
  return (s == 0) ? 1U : s;
}

int anomaly_detector_init(anomaly_detector_t *ad, anomaly_config_t config,
                          sensor_config_t sensor, detection_config_t detection,
                          debounce_config_t debounce,
                          uint32_t nominal_rate_hz) {
  memset(ad, 0, sizeof(*ad));

  ad->config = config;
  ad->sensor = sensor;
  ad->detection = detection;
  ad->nominal_rate_hz = nominal_rate_hz;
  ad->ns_per_sample =
      (nominal_rate_hz > 0) ? (1000000000ULL / nominal_rate_hz) : 100000ULL;

  uint32_t samples_per_cycle = nominal_rate_hz / detection.ac_freq_hz;
  if (samples_per_cycle == 0)
    samples_per_cycle = 1;

  ad->rms_window_samples = samples_per_cycle * detection.rms_window_cycles;
  if (ad->rms_window_samples == 0)
    ad->rms_window_samples = 1;

  ad->learn_samples_total = samples_per_cycle * detection.learn_cycles;
  ad->learn_samples_left = ad->learn_samples_total;
  ad->ema_alpha = 1.0f / (float)ad->rms_window_samples;

  ad->sq_ring = (float *)calloc(ad->rms_window_samples, sizeof(float));
  if (!ad->sq_ring) {
    fprintf(stderr,
            "[Detector] Failed to allocate RMS ring buffer (%u floats)\n",
            ad->rms_window_samples);
    return -1;
  }

  ad->sag_cooldown_ns = ms_to_ns(debounce.sag_cooldown_ms);
  ad->swell_cooldown_ns = ms_to_ns(debounce.swell_cooldown_ms);
  ad->spike_cooldown_ns = ms_to_ns(debounce.spike_cooldown_ms);

  ad->sag_min_duration_samples =
      ms_to_samples(config.sag_min_duration_ms, nominal_rate_hz);
  ad->swell_min_duration_samples =
      ms_to_samples(config.swell_min_duration_ms, nominal_rate_hz);

  printf("[Detector] Init: rate=%u Hz, rms_window=%u samples (%u cycles), "
         "learn=%u samples (%u cycles), sag_min=%u swell_min=%u samples\n",
         nominal_rate_hz, ad->rms_window_samples, detection.rms_window_cycles,
         ad->learn_samples_total, detection.learn_cycles,
         ad->sag_min_duration_samples, ad->swell_min_duration_samples);

  return 0;
}

void anomaly_detector_free(anomaly_detector_t *ad) {
  free(ad->sq_ring);
  ad->sq_ring = NULL;
}

static inline float adc_to_volts(int16_t raw, float adc_vref,
                                 uint32_t adc_bits) {
  float full_scale = (float)(1u << (adc_bits - 1));
  return (float)raw * (adc_vref / full_scale);
}

static float push_rms_ring(anomaly_detector_t *ad, float sq_val) {
  if (ad->sq_count >= ad->rms_window_samples) {
    ad->sq_sum -= ad->sq_ring[ad->sq_head];
  } else {
    ad->sq_count++;
  }
  ad->sq_ring[ad->sq_head] = sq_val;
  ad->sq_sum += sq_val;
  ad->sq_head = (ad->sq_head + 1) % ad->rms_window_samples;
  return (ad->sq_count >= ad->rms_window_samples)
             ? sqrtf(ad->sq_sum / (float)ad->rms_window_samples)
             : -1.0f;
}

static uint64_t cooldown_for_type(anomaly_detector_t *ad, event_type_t t) {
  switch (t) {
  case EVENT_TYPE_SAG:
    return ad->sag_cooldown_ns;
  case EVENT_TYPE_SWELL:
    return ad->swell_cooldown_ns;
  case EVENT_TYPE_SPIKE:
    return ad->spike_cooldown_ns;
  default:
    return ad->sag_cooldown_ns;
  }
}

static uint32_t min_duration_for_type(anomaly_detector_t *ad, event_type_t t) {
  switch (t) {
  case EVENT_TYPE_SAG:
    return ad->sag_min_duration_samples;
  case EVENT_TYPE_SWELL:
    return ad->swell_min_duration_samples;
  default:
    return 1;
  }
}

static void update_extreme_rms(anomaly_detector_t *ad, float vrms_mains) {
  if (ad->current_type == EVENT_TYPE_SAG) {
    if (vrms_mains < ad->extreme_rms_v)
      ad->extreme_rms_v = vrms_mains;
  } else if (ad->current_type == EVENT_TYPE_SWELL) {
    if (vrms_mains > ad->extreme_rms_v)
      ad->extreme_rms_v = vrms_mains;
  }
}

static void update_peak_raw(anomaly_detector_t *ad, int16_t raw_ac) {
  int32_t cur = raw_ac >= 0 ? raw_ac : -raw_ac;
  int32_t prev = ad->peak_raw >= 0 ? ad->peak_raw : -ad->peak_raw;
  if (cur > prev)
    ad->peak_raw = raw_ac;
}

static int finish_event_sample(anomaly_detector_t *ad, event_type_t ended_type,
                               uint64_t sample_time_ns, ad_notification_t *out) {
  uint32_t min_dur = min_duration_for_type(ad, ended_type);

  if (ad->current_duration >= min_dur) {
    out->kind = AD_NOTIFY_COMPLETED;
    out->event = (anomaly_event_t){
        .timestamp_ns = ad->start_time_ns,
        .type = ended_type,
        .rms_vrms = ad->extreme_rms_v,
        .peak_value = ad->peak_raw,
        .duration_samples = ad->current_duration,
    };

    printf("[Detector] Event ENDED: Type %d, Duration %u samples, "
           "extreme_RMS=%.2f V\n",
           ended_type, ad->current_duration, ad->extreme_rms_v);
  } else {
    printf("[Detector] Event discarded (duration %u < min %u samples)\n",
           ad->current_duration, min_dur);
    ad->last_event_end_ns[ended_type] = sample_time_ns;
    ad->in_event = 0;
    ad->current_type = EVENT_TYPE_NONE;
    ad->current_duration = 0;
    ad->extreme_rms_v = 0.0f;
    return 0;
  }

  ad->last_event_end_ns[ended_type] = sample_time_ns;
  ad->in_event = 0;
  ad->current_type = EVENT_TYPE_NONE;
  ad->current_duration = 0;
  ad->extreme_rms_v = 0.0f;
  return 1;
}

int anomaly_detector_force_complete(anomaly_detector_t *ad,
                                    uint64_t sample_time_ns,
                                    ad_notification_t *out) {
  if (!ad || !out || !ad->in_event)
    return 0;
  return finish_event_sample(ad, ad->current_type, sample_time_ns, out);
}

int anomaly_detector_process_sample(anomaly_detector_t *ad, int16_t raw,
                                    uint64_t sample_time_ns,
                                    ad_notification_t *out) {
  if (!out)
    return 0;

  float v = adc_to_volts(raw, ad->sensor.adc_vref, ad->sensor.adc_bits);
  if (!ad->dc_initialized) {
    /*
     * The ZMPT101B output has a DC bias. Seed the filter from the first ADC
     * sample so startup settling is not mistaken for AC during calibration.
     */
    ad->dc_ema = v;
    ad->dc_initialized = 1;
  }
  ad->dc_ema = ad->ema_alpha * v + (1.0f - ad->ema_alpha) * ad->dc_ema;
  float v_ac = v - ad->dc_ema;
  float full_scale = (float)(1u << (ad->sensor.adc_bits - 1));
  int32_t raw_ac_i = (int32_t)(v_ac * full_scale / ad->sensor.adc_vref);
  if (raw_ac_i > INT16_MAX)
    raw_ac_i = INT16_MAX;
  else if (raw_ac_i < INT16_MIN)
    raw_ac_i = INT16_MIN;
  int16_t raw_ac = (int16_t)raw_ac_i;
  float rms_adc = push_rms_ring(ad, v_ac * v_ac);

  if (rms_adc < 0.0f)
    return 0;

  if (ad->learn_samples_left > 0) {
    ad->learn_sq_sum += v_ac * v_ac;
    ad->learn_count++;
    ad->learn_samples_left--;

    if (ad->learn_samples_left == 0) {
      float measured_adc_rms =
          sqrtf(ad->learn_sq_sum / (float)ad->learn_count);

      if (measured_adc_rms > 0.001f) {
        float target_vrms = ad->sensor.target_mains_vrms;
        ad->sensor.transformer_ratio = target_vrms / measured_adc_rms;
        ad->nominal_vrms = target_vrms;

        printf("[Detector] Auto-calibration complete: ADC RMS=%.4f V, "
               "ratio=%.2f, nominal=%.1f V\n",
               measured_adc_rms, ad->sensor.transformer_ratio, ad->nominal_vrms);

        FILE *status_file = fopen("data/calibration_status.txt", "w");
        if (status_file) {
          fprintf(status_file, "%.2f\n%.2f\n", ad->nominal_vrms,
                  ad->sensor.transformer_ratio);
          fclose(status_file);
        }
      } else {
        ad->nominal_vrms = ad->sensor.target_mains_vrms;
        fprintf(stderr,
                "[Detector] WARNING: ADC RMS too low, using defaults\n");
      }
    }
    return 0;
  }

  float vrms_mains = rms_adc * ad->sensor.transformer_ratio;
  float sag_threshold_vrms =
      ad->nominal_vrms * (1.0f + ad->config.sag_threshold_pct / 100.0f);
  float swell_threshold_vrms =
      ad->nominal_vrms * (1.0f + ad->config.swell_threshold_pct / 100.0f);

  event_type_t cur_type = EVENT_TYPE_NONE;
  if (vrms_mains < sag_threshold_vrms)
    cur_type = EVENT_TYPE_SAG;
  else if (vrms_mains > swell_threshold_vrms)
    cur_type = EVENT_TYPE_SWELL;

  if (cur_type != EVENT_TYPE_NONE) {
    if (!ad->in_event) {
      uint64_t cooldown = cooldown_for_type(ad, cur_type);
      if ((sample_time_ns - ad->last_event_end_ns[cur_type]) < cooldown)
        return 0;

      ad->in_event = 1;
      ad->current_type = cur_type;
      ad->start_time_ns = sample_time_ns;
      ad->current_duration = 1;
      ad->peak_raw = raw_ac;
      ad->extreme_rms_v = vrms_mains;

      out->kind = AD_NOTIFY_STARTED;
      out->event = (anomaly_event_t){
          .timestamp_ns = sample_time_ns,
          .type = cur_type,
          .rms_vrms = vrms_mains,
          .peak_value = raw_ac,
          .duration_samples = 0,
      };

      printf("[Detector] Event STARTED: Type %d, VRMS=%.2f V at %llu ns\n",
             cur_type, vrms_mains, (unsigned long long)sample_time_ns);
      return 1;
    }

    if (cur_type == ad->current_type) {
      ad->current_duration++;
      update_peak_raw(ad, raw_ac);
      update_extreme_rms(ad, vrms_mains);
      return 0;
    }

    /* Type flip: emit COMPLETED for the prior event; new type starts next
     * sample (at most one notification per call). */
    return finish_event_sample(ad, ad->current_type, sample_time_ns, out);
  }

  if (ad->in_event)
    return finish_event_sample(ad, ad->current_type, sample_time_ns, out);

  return 0;
}
