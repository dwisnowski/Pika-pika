#ifndef WRITER_H
#define WRITER_H

#include "storage_format.h"
#include <stdint.h>
#include <stdio.h>

typedef struct {
  FILE *decimated_file;
  FILE *event_file;
  FILE *index_file;
  uint64_t event_counter;

  /* Paths — needed for rotation */
  char base_path[256];

  /* File size limits in bytes (0 = unlimited) */
  uint64_t max_decimated_bytes;
  uint64_t max_events_bytes;
} writer_t;

int writer_init(writer_t *w, const char *base_path, uint32_t max_decimated_mb,
                uint32_t max_events_mb);
void writer_cleanup(writer_t *w);

void writer_write_decimated(writer_t *w, decimated_chunk_header_t *header,
                            uint16_t *data);

/**
 * Write a single-channel event.
 * data_ch0     : channel-0 samples only
 * sample_count : number of int16 samples in data_ch0
 */
void writer_write_event(writer_t *w, event_index_record_t *index,
                        int16_t *data_ch0, uint32_t sample_count);

#endif // WRITER_H
