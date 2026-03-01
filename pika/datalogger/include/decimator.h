#ifndef DECIMATOR_H
#define DECIMATOR_H

#include <stdint.h>

typedef struct {
  uint32_t total_buckets;     /* Total number of buckets to collect */
  uint32_t samples_per_bucket; /* Samples per bucket */
  uint32_t current_bucket;    /* Current bucket index */
  uint32_t samples_in_bucket; /* Samples collected in current bucket */
  int16_t min_val;            /* Min value in current bucket */
  int16_t max_val;            /* Max value in current bucket */
} decimator_t;

/**
 * Initialize decimator with min/max bucketing.
 * Calculates buckets based on: samples_per_bucket = nominal_rate_hz / target_output_rate_hz
 * 
 * @param dec Decimator state
 * @param nominal_rate_hz ADC sampling rate (e.g., 10000 Hz)
 * @param target_output_rate_hz Target decimated output rate (e.g., 50 Hz)
 */
void decimator_init(decimator_t *dec, uint32_t nominal_rate_hz, 
                    uint32_t target_output_rate_hz);

/**
 * Process a sample and return bucket data when complete.
 * Returns 1 when a bucket is complete (min/max ready), 0 otherwise.
 * When returning 1, read dec->min_val and dec->max_val for the bucket.
 */
int decimator_process(decimator_t *dec, int16_t sample);

#endif // DECIMATOR_H
