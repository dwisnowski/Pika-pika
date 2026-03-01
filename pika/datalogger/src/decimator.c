#include "decimator.h"
#include <stdio.h>
#include <stdint.h>
#include <limits.h>

void decimator_init(decimator_t *dec, uint32_t nominal_rate_hz, 
                    uint32_t target_output_rate_hz) {
  /* Calculate samples per bucket to achieve target output rate */
  /* samples_per_bucket = nominal_rate_hz / target_output_rate_hz */
  dec->samples_per_bucket = nominal_rate_hz / target_output_rate_hz;
  
  /* Ensure at least 1 sample per bucket */
  if (dec->samples_per_bucket == 0) dec->samples_per_bucket = 1;
  
  dec->total_buckets = 0;  /* Not used with output rate approach */
  dec->current_bucket = 0;
  dec->samples_in_bucket = 0;
  dec->min_val = INT16_MAX;
  dec->max_val = INT16_MIN;
  
  printf("[Decimator] Initialized: samples_per_bucket=%u (target_output_rate=%u Hz)\n",
         dec->samples_per_bucket, target_output_rate_hz);
}

int decimator_process(decimator_t *dec, int16_t sample) {
  /* Track min/max for current bucket */
  if (sample < dec->min_val) dec->min_val = sample;
  if (sample > dec->max_val) dec->max_val = sample;
  
  dec->samples_in_bucket++;
  
  /* Check if bucket is complete */
  if (dec->samples_in_bucket >= dec->samples_per_bucket) {
    dec->samples_in_bucket = 0;
    dec->current_bucket++;
    
    /* Return 1 to indicate bucket is ready (caller reads min_val/max_val)
       Caller will read min_val/max_val, then call again for next bucket */
    return 1;
  }
  
  return 0;
}
