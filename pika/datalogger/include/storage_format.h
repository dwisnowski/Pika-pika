#ifndef STORAGE_FORMAT_H
#define STORAGE_FORMAT_H

#include <stdint.h>

/**
 * Decimated Data Chunk Header
 * 
 * For decimated waveform data with min/max bucketing:
 * - channels: Number of ADC channels (e.g., 8 for AD7606)
 * - values_per_sample: Number of values per sample per channel (e.g., 2 for [min, max])
 * - sample_count: Number of samples in this chunk
 * 
 * Data layout: For each sample, store values_per_sample values for each channel
 * Example with 8 channels and values_per_sample=2 (min/max):
 *   [ch0_min, ch0_max, ch1_min, ch1_max, ..., ch7_min, ch7_max]
 */
typedef struct {
  uint64_t start_time_ns;
  uint32_t sample_rate;
  uint32_t sample_count;
  uint32_t channels;           // Number of ADC channels
  uint32_t values_per_sample;  // Values per sample per channel (1=raw, 2=min/max, etc.)
} __attribute__((packed)) decimated_chunk_header_t;

/**
 * Event Index Record
 */
typedef struct {
  uint64_t event_id;
  uint64_t timestamp_ns;
  uint8_t event_type;
  int16_t peak_value;
  uint32_t duration_samples;
  uint64_t file_offset; // Offset in raw event data file
} __attribute__((packed)) event_index_record_t;

#endif // STORAGE_FORMAT_H
