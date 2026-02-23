#ifndef STORAGE_FORMAT_H
#define STORAGE_FORMAT_H

#include <stdint.h>

/**
 * Decimated Data Chunk Header
 */
typedef struct {
  uint64_t start_time_ns;
  uint32_t sample_rate;
  uint32_t sample_count;
  uint32_t channels;
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
