#include "writer.h"
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

int writer_init(writer_t *w, const char *base_path) {
  mkdir(base_path, 0777);

  char path[256];

  sprintf(path, "%s/decimated.bin", base_path);
  w->decimated_file = fopen(path, "ab");

  sprintf(path, "%s/events.bin", base_path);
  w->event_file = fopen(path, "ab");

  sprintf(path, "%s/index.bin", base_path);
  w->index_file = fopen(path, "ab");

  w->event_counter = 0;

  return (w->decimated_file && w->event_file && w->index_file) ? 0 : -1;
}

void writer_cleanup(writer_t *w) {
  if (w->decimated_file)
    fclose(w->decimated_file);
  if (w->event_file)
    fclose(w->event_file);
  if (w->index_file)
    fclose(w->index_file);
}

void writer_write_decimated(writer_t *w, decimated_chunk_header_t *header,
                            uint16_t *data) {
  fwrite(header, sizeof(decimated_chunk_header_t), 1, w->decimated_file);
  fwrite(data, sizeof(uint16_t), header->sample_count * header->channels,
         w->decimated_file);
  fflush(w->decimated_file);
}

void writer_write_event(writer_t *w, event_index_record_t *index,
                        uint16_t *data, uint32_t data_size) {
  index->event_id = w->event_counter++;
  index->file_offset = ftell(w->event_file);

  fwrite(data, 1, data_size, w->event_file);
  fwrite(index, sizeof(event_index_record_t), 1, w->index_file);

  fflush(w->event_file);
  fflush(w->index_file);
}
