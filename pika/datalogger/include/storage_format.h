#ifndef STORAGE_FORMAT_H
#define STORAGE_FORMAT_H

#include <stdint.h>

/** Index record layout version (v2 adds waveform_start_ns + ns_per_sample). */
#define EVENT_INDEX_FORMAT_VERSION 2

/**
 * Decimated Data Chunk Header
 */
typedef struct {
  uint64_t start_time_ns;
  uint32_t sample_rate;
  uint32_t sample_count;
  uint32_t channels;
  uint32_t values_per_sample;
} __attribute__((packed)) decimated_chunk_header_t;

/**
 * Event Index Record (v2)
 *
 * timestamp_ns       — event onset (Unix epoch ns)
 * waveform_start_ns  — first sample in events.bin (Unix epoch ns)
 * ns_per_sample      — measured spacing between waveform samples
 */
typedef struct {
  uint64_t event_id;
  uint64_t timestamp_ns;
  uint64_t waveform_start_ns;
  uint64_t ns_per_sample;
  uint8_t event_type;
  int16_t peak_value;
  uint32_t duration_samples;
  uint64_t file_offset;
} __attribute__((packed)) event_index_record_t;

#endif /* STORAGE_FORMAT_H */
