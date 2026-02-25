#include "writer.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

/* Internal helper: rename current file to .old, then re-open fresh.
 * The existing .old is silently overwritten (keeps disk use bounded). */
static void rotate_file(FILE **fp, const char *path) {
  if (*fp) {
    fclose(*fp);
    *fp = NULL;
  }

  /* Build .old path */
  char old_path[300];
  snprintf(old_path, sizeof(old_path), "%s.old", path);

  /* rename() replaces old_path if it exists — exactly what we want */
  rename(path, old_path);

  /* Re-open the fresh file */
  *fp = fopen(path, "wb");
  if (!*fp) {
    perror("[Writer] Failed to re-open file after rotation");
  } else {
    printf("[Writer] Rotated: %s -> %s\n", path, old_path);
  }
}

/* Check if a file should be rotated and do so if necessary. */
static void maybe_rotate(FILE **fp, const char *path, uint64_t max_bytes) {
  if (max_bytes == 0 || !*fp)
    return;
  long pos = ftell(*fp);
  if (pos < 0)
    return;
  if ((uint64_t)pos >= max_bytes) {
    printf("[Writer] Size limit reached for %s (%ld bytes >= %llu MB limit), "
           "rotating.\n",
           path, pos, (unsigned long long)(max_bytes / (1024ULL * 1024ULL)));
    rotate_file(fp, path);
  }
}

int writer_init(writer_t *w, const char *base_path, uint32_t max_decimated_mb,
                uint32_t max_events_mb) {
  memset(w, 0, sizeof(*w));
  mkdir(base_path, 0777);

  strncpy(w->base_path, base_path, sizeof(w->base_path) - 1);
  w->max_decimated_bytes = (uint64_t)max_decimated_mb * 1024ULL * 1024ULL;
  w->max_events_bytes = (uint64_t)max_events_mb * 1024ULL * 1024ULL;

  char path[300];

  snprintf(path, sizeof(path), "%s/decimated.bin", base_path);
  w->decimated_file = fopen(path, "ab");

  snprintf(path, sizeof(path), "%s/events.bin", base_path);
  w->event_file = fopen(path, "ab");

  snprintf(path, sizeof(path), "%s/index.bin", base_path);
  w->index_file = fopen(path, "ab");

  w->event_counter = 0;

  if (!w->decimated_file || !w->event_file || !w->index_file) {
    perror("[Writer] Failed to open one or more data files");
    return -1;
  }

  printf("[Writer] Initialized: base='%s', max_decimated=%u MB, max_events=%u "
         "MB\n",
         base_path, max_decimated_mb, max_events_mb);
  return 0;
}

void writer_cleanup(writer_t *w) {
  if (w->decimated_file) {
    fclose(w->decimated_file);
    w->decimated_file = NULL;
  }
  if (w->event_file) {
    fclose(w->event_file);
    w->event_file = NULL;
  }
  if (w->index_file) {
    fclose(w->index_file);
    w->index_file = NULL;
  }
}

void writer_write_decimated(writer_t *w, decimated_chunk_header_t *header,
                            uint16_t *data) {
  if (!w->decimated_file)
    return;

  fwrite(header, sizeof(decimated_chunk_header_t), 1, w->decimated_file);
  fwrite(data, sizeof(uint16_t), header->sample_count * header->channels,
         w->decimated_file);
  fflush(w->decimated_file);

  /* Check rotation after write */
  char path[300];
  snprintf(path, sizeof(path), "%s/decimated.bin", w->base_path);
  maybe_rotate(&w->decimated_file, path, w->max_decimated_bytes);
}

void writer_write_event(writer_t *w, event_index_record_t *index,
                        int16_t *data_ch0, uint32_t sample_count) {
  if (!w->event_file || !w->index_file)
    return;

  index->event_id = w->event_counter++;
  index->file_offset = (uint64_t)ftell(w->event_file);

  /* Write channel-0-only samples */
  fwrite(data_ch0, sizeof(int16_t), sample_count, w->event_file);
  fwrite(index, sizeof(event_index_record_t), 1, w->index_file);

  fflush(w->event_file);
  fflush(w->index_file);

  /* Check rotation of events file */
  char path[300];
  snprintf(path, sizeof(path), "%s/events.bin", w->base_path);
  maybe_rotate(&w->event_file, path, w->max_events_bytes);
}
