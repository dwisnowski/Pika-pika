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
} writer_t;

int writer_init(writer_t *w, const char *base_path);
void writer_cleanup(writer_t *w);

void writer_write_decimated(writer_t *w, decimated_chunk_header_t *header,
                            uint16_t *data);
void writer_write_event(writer_t *w, event_index_record_t *index,
                        uint16_t *data, uint32_t data_size);

#endif // WRITER_H
