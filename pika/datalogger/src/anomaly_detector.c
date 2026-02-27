#include "anomaly_detector.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Static result buffer — avoids heap allocation per event */
static anomaly_event_t g_event_result;

/* Helper: cooldown in ns from ms */
static inline uint64_t ms_to_ns(uint32_t ms) {
  return (uint64_t)ms * 1000000ULL;
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

  /* --- Compute derived window sizes (sample-rate-aware) --- */
  uint32_t samples_per_cycle = nominal_rate_hz / detection.ac_freq_hz;
  if (samples_per_cycle == 0)
    samples_per_cycle = 1; /* safety */

  ad->rms_window_samples = samples_per_cycle * detection.rms_window_cycles;
  if (ad->rms_window_samples == 0)
    ad->rms_window_samples = 1;

  ad->learn_samples_total = samples_per_cycle * detection.learn_cycles;
  ad->learn_samples_left = ad->learn_samples_total;

  /* EMA alpha: a smaller alpha means more smoothing (slower response).
   * Using half the RMS window gives a DC removal time constant equal to
   * ~0.5 * rms_window_samples — responsive but stable. */
  ad->ema_alpha = 1.0f / (float)ad->rms_window_samples;

  /* Allocate the sq_ring circular buffer */
  ad->sq_ring = (float *)calloc(ad->rms_window_samples, sizeof(float));
  if (!ad->sq_ring) {
    fprintf(stderr,
            "[Detector] Failed to allocate RMS ring buffer (%u floats)\n",
            ad->rms_window_samples);
    return -1;
  }

  /* Debounce cooldowns */
  ad->sag_cooldown_ns = ms_to_ns(debounce.sag_cooldown_ms);
  ad->swell_cooldown_ns = ms_to_ns(debounce.swell_cooldown_ms);
  ad->spike_cooldown_ns = ms_to_ns(debounce.spike_cooldown_ms);

  /* nominal_vrms starts at 0 → learning phase */
  ad->nominal_vrms = 0.0f;
  ad->learn_sq_sum = 0.0f;
  ad->learn_count = 0;

  printf("[Detector] Init: rate=%u Hz, rms_window=%u samples (%u cycles), "
         "learn=%u samples (%u cycles), adc_vref=%.1f, initial_ratio=%.1f (will auto-calibrate)\n",
         nominal_rate_hz, ad->rms_window_samples, detection.rms_window_cycles,
         ad->learn_samples_total, detection.learn_cycles, sensor.adc_vref,
         sensor.transformer_ratio);

  return 0;
}

void anomaly_detector_free(anomaly_detector_t *ad) {
  free(ad->sq_ring);
  ad->sq_ring = NULL;
}

/* ------------------------------------------------------------------ */
/*  Internal helpers                                                   */
/* ------------------------------------------------------------------ */

static inline float adc_to_volts(int16_t raw, float adc_vref,
                                 uint32_t adc_bits) {
  /* Signed two's-complement: max positive = 2^(bits-1) - 1 ≈ 2^(bits-1) */
  float full_scale = (float)(1u << (adc_bits - 1));
  return (float)raw * (adc_vref / full_scale);
}

static float push_rms_ring(anomaly_detector_t *ad, float sq_val) {
  /* Evict the oldest sample if ring is full */
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
             : -1.0f; /* sentinel: window not yet full */
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

/* ------------------------------------------------------------------ */
/*  Main processing function                                           */
/* ------------------------------------------------------------------ */

anomaly_event_t *anomaly_detector_process(anomaly_detector_t *ad,
                                          int16_t *samples, uint32_t count,
                                          uint32_t channels,
                                          uint64_t base_time_ns) {
  /* Nanoseconds per sample at nominal rate */
  uint64_t ns_per_sample = 1000000000ULL / ad->nominal_rate_hz;

  for (uint32_t i = 0; i < count; i++) {
    /* --- Channel 0 only for detection --- */
    int16_t raw = samples[i * channels]; /* ch0 */

    /* 1. Convert raw ADC count → volts */
    float v = adc_to_volts(raw, ad->sensor.adc_vref, ad->sensor.adc_bits);

    /* 2. Remove DC bias with an EMA */
    ad->dc_ema = ad->ema_alpha * v + (1.0f - ad->ema_alpha) * ad->dc_ema;
    float v_ac = v - ad->dc_ema;

    /* 3. Push v_ac^2 into the RMS ring, get current RMS (ADC-side) */
    float rms_adc = push_rms_ring(ad, v_ac * v_ac);

    /* If RMS window not yet full, skip detection entirely */
    if (rms_adc < 0.0f)
      continue;

    /* 4. Apply transformer ratio to get estimated mains VRMS */
    float vrms_mains = rms_adc * ad->sensor.transformer_ratio;

    /* 5. Auto-learn nominal VRMS and calibrate transformer ratio */
    if (ad->learn_samples_left > 0) {
      /* Accumulate squared ADC-side RMS (before transformer scaling) */
      ad->learn_sq_sum += rms_adc * rms_adc;
      ad->learn_count++;
      ad->learn_samples_left--;

      if (ad->learn_samples_left == 0) {
        /* Learning complete: compute RMS-equivalent average of ADC voltage */
        float measured_adc_rms = sqrtf(ad->learn_sq_sum / (float)ad->learn_count);
        
        /* Assume steady-state should be 120V RMS (US mains standard) */
        const float TARGET_MAINS_VRMS = 120.0f;
        
        /* Auto-calibrate transformer ratio: ratio = mains_voltage / adc_voltage */
        if (measured_adc_rms > 0.001f) {  /* avoid divide-by-zero */
          ad->sensor.transformer_ratio = TARGET_MAINS_VRMS / measured_adc_rms;
          ad->nominal_vrms = TARGET_MAINS_VRMS;
          
          printf("[Detector] Auto-calibration complete:\n");
          printf("  Measured ADC RMS: %.4f V\n", measured_adc_rms);
          printf("  Target Mains: %.1f V\n", TARGET_MAINS_VRMS);
          printf("  Learned transformer_ratio: %.2f\n", ad->sensor.transformer_ratio);
          printf("  Nominal VRMS set to: %.1f V\n", ad->nominal_vrms);
        } else {
          /* Fallback: use config value if measurement failed */
          ad->nominal_vrms = TARGET_MAINS_VRMS;
          printf("[Detector] WARNING: ADC RMS too low (%.4f V), using config transformer_ratio=%.2f\n",
                 measured_adc_rms, ad->sensor.transformer_ratio);
        }
      }
      /* Still learning — suppress event detection */
      continue;
    }

    /* 6. Compute thresholds from learned nominal */
    float sag_threshold_vrms =
        ad->nominal_vrms * (1.0f + ad->config.sag_threshold_pct / 100.0f);
    float swell_threshold_vrms =
        ad->nominal_vrms * (1.0f + ad->config.swell_threshold_pct / 100.0f);

    /* Determine which event type is active right now */
    event_type_t cur_type = EVENT_TYPE_NONE;
    if (vrms_mains < sag_threshold_vrms) {
      cur_type = EVENT_TYPE_SAG;
    } else if (vrms_mains > swell_threshold_vrms) {
      cur_type = EVENT_TYPE_SWELL;
    }

    uint64_t sample_time_ns = base_time_ns + (uint64_t)i * ns_per_sample;

    /* 7. Event state machine */
    if (cur_type != EVENT_TYPE_NONE) {
      if (!ad->in_event) {
        /* Check debounce before starting a new event */
        uint64_t cooldown = cooldown_for_type(ad, cur_type);
        if ((sample_time_ns - ad->last_event_end_ns[cur_type]) < cooldown) {
          /* Still within cooldown — suppress */
          continue;
        }
        /* Start event */
        ad->in_event = 1;
        ad->current_type = cur_type;
        ad->start_time_ns = sample_time_ns;
        ad->current_duration = 1;
        printf("[Detector] Event STARTED: Type %d, VRMS=%.2f V (nominal=%.2f "
               "V) at %llu ns\n",
               cur_type, vrms_mains, ad->nominal_vrms,
               (unsigned long long)sample_time_ns);
      } else if (cur_type == ad->current_type) {
        ad->current_duration++;
      } else {
        /* Type changed mid-event — end current, will re-evaluate next iter */
        goto end_event;
      }
    } else if (ad->in_event) {
    end_event:;
      /* Event just ended */
      g_event_result.type = ad->current_type;
      g_event_result.timestamp_ns = ad->start_time_ns;
      g_event_result.duration_samples = ad->current_duration;
      g_event_result.peak_value = raw;
      g_event_result.rms_vrms = vrms_mains;

      printf(
          "[Detector] Event ENDED: Type %d, Duration %u samples, VRMS=%.2f V\n",
          ad->current_type, ad->current_duration, vrms_mains);

      /* 8. Record end time for debounce */
      ad->last_event_end_ns[ad->current_type] = sample_time_ns;

      ad->in_event = 0;
      ad->current_type = EVENT_TYPE_NONE;
      return &g_event_result;
    }
  }

  return NULL;
}
