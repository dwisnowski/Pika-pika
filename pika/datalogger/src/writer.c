#include "writer.h"
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

/* Probe that we can create/write/fsync in the output directory. */
static void writer_probe_io(const char *base_path) {
  char probe_path[300];
  snprintf(probe_path, sizeof(probe_path), "%s/write_probe.txt", base_path);

  FILE *pf = fopen(probe_path, "w");
  if (!pf) {
    fprintf(stderr, "[Writer] PROBE FAIL: fopen(%s) failed: %s\n", probe_path,
            strerror(errno));
    return;
  }

  int w = fprintf(pf, "writer_probe_ok\n");
  if (w < 0) {
    fprintf(stderr, "[Writer] PROBE FAIL: fprintf(%s) failed: %s\n", probe_path,
            strerror(errno));
    fclose(pf);
    return;
  }

  if (fflush(pf) != 0) {
    fprintf(stderr, "[Writer] PROBE FAIL: fflush(%s) failed: %s\n", probe_path,
            strerror(errno));
    fclose(pf);
    return;
  }

  if (fsync(fileno(pf)) != 0) {
    fprintf(stderr, "[Writer] PROBE FAIL: fsync(%s) failed: %s\n", probe_path,
            strerror(errno));
    fclose(pf);
    return;
  }

  long final_pos = ftell(pf);
  fclose(pf);

  printf("[Writer] PROBE OK: wrote %ld bytes to %s\n", final_pos, probe_path);
}

/* Optional startup self-test that appends one tiny valid decimated chunk.
 * Enabled with PIKA_WRITER_SELFTEST_DECIMATED=1. */
static void writer_selftest_decimated(writer_t *w) {
  const char *enabled = getenv("PIKA_WRITER_SELFTEST_DECIMATED");
  if (!enabled || strcmp(enabled, "1") != 0) {
    return;
  }

  if (!w->decimated_file) {
    fprintf(stderr,
            "[Writer] SELFTEST skipped: decimated_file handle is not open\n");
    return;
  }

  decimated_chunk_header_t header = {
      .start_time_ns = 1,
      .sample_rate = 10000,
      .sample_count = 1,
      .channels = 1,
      .values_per_sample = 2,
  };
  int16_t payload[2] = {0, 0};

  long before = ftell(w->decimated_file);
  size_t header_written =
      fwrite(&header, sizeof(decimated_chunk_header_t), 1, w->decimated_file);
  size_t payload_written = fwrite(payload, sizeof(int16_t), 2, w->decimated_file);

  if (header_written != 1 || payload_written != 2 || ferror(w->decimated_file)) {
    fprintf(stderr,
            "[Writer] SELFTEST FAIL: decimated.bin write failed "
            "header_written=%zu payload_written=%zu errno=%d (%s)\n",
            header_written, payload_written, errno, strerror(errno));
    clearerr(w->decimated_file);
    return;
  }

  if (fflush(w->decimated_file) != 0) {
    fprintf(stderr,
            "[Writer] SELFTEST FAIL: decimated.bin fflush failed errno=%d (%s)\n",
            errno, strerror(errno));
    return;
  }

  long after = ftell(w->decimated_file);
  printf("[Writer] SELFTEST OK: appended debug decimated chunk to data/decimated.bin "
         "(before=%ld after=%ld bytes)\n",
         before, after);
}

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

  writer_probe_io(base_path);
  writer_selftest_decimated(w);

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
                            int16_t *data) {
  if (!w->decimated_file)
    return;

  uint32_t total_values =
      header->sample_count * header->channels * header->values_per_sample;

  long before = ftell(w->decimated_file);
  printf("[Writer] Decimated write attempt: start_time_ns=%llu sample_rate=%u "
         "sample_count=%u channels=%u values_per_sample=%u total_values=%u "
         "file_pos_before=%ld\n",
         (unsigned long long)header->start_time_ns, header->sample_rate,
         header->sample_count, header->channels, header->values_per_sample,
         total_values, before);

  size_t header_written =
      fwrite(header, sizeof(decimated_chunk_header_t), 1, w->decimated_file);
  size_t values_written =
      fwrite(data, sizeof(int16_t), total_values, w->decimated_file);

  if (header_written != 1 || values_written != total_values ||
      ferror(w->decimated_file)) {
    fprintf(stderr,
            "[Writer] Decimated write FAIL: header_written=%zu values_written=%zu/%u "
            "errno=%d (%s)\n",
            header_written, values_written, total_values, errno,
            strerror(errno));
    clearerr(w->decimated_file);
    return;
  }

  if (fflush(w->decimated_file) != 0) {
    fprintf(stderr, "[Writer] Decimated fflush FAIL: errno=%d (%s)\n", errno,
            strerror(errno));
    return;
  }

  long after = ftell(w->decimated_file);
  printf("[Writer] Decimated write OK: file_pos_after=%ld bytes_written=%ld\n",
         after, (after >= before && before >= 0) ? (after - before) : -1L);

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
