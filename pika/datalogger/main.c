#define _GNU_SOURCE
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "anomaly_detector.h"
#include "decimator.h"
#include "event_window.h"
#include "logger_config.h"
#include "ring_buffer.h"
#include "scope_buffer.h"
#include "shm_reader.h"
#include "time_utils.h"
#include "writer.h"

// Global state
volatile int keep_running = 1;
logger_config_t global_config;
ring_buffer_t raw_block_rb;
shm_reader_t shm_reader;
writer_t disk_writer;
scope_buffer_t live_scope_buffer;

void handle_sigint(int sig) { keep_running = 0; }

// Reader Thread: Pulls from PRU SHM, pushes to Ring Buffer

void *reader_thread_func(void *arg) {
  printf("[Reader] Started\n");

  uint64_t blocks_pushed = 0;
  uint64_t null_polls    = 0;
  uint32_t first_seen    = 0;

  while (keep_running) {
    uint8_t *data;
    volatile block_descriptor_t *desc = shm_reader_poll(&shm_reader, &data);

    if (desc) {
      if (!first_seen) {
        printf("[Reader] First valid block from PRU: num_samples=%u  "
               "timestamp_cycles=%llu  flags=0x%08X\n",
               desc->num_samples,
               (unsigned long long)desc->timestamp_cycles,
               desc->flags);
        first_seen = 1;
      }

      size_t data_size = desc->num_samples * CHANNELS * 2;

      uint8_t temp_buf[2064];
      memcpy(temp_buf, (void *)desc, 16);
      memcpy(temp_buf + 16, data, data_size);

      if (!ring_buffer_push(&raw_block_rb, temp_buf)) {
        fprintf(stderr, "[Reader] Warning: Ring buffer overflow!\n");
      } else {
        blocks_pushed++;
        if (blocks_pushed % 5000 == 0) {
          printf("[Reader] Blocks pushed to ring buffer: %llu\n",
                 (unsigned long long)blocks_pushed);
        }
      }
    } else {
      null_polls++;
      if (null_polls % 10000 == 0) {
        volatile pru_shared_memory_t *h = shm_reader.header;
        printf("[Reader] Polling (no new blocks): null_polls=%llu  "
               "write_block_idx=%u  heartbeat=%u  magic=0x%08X  "
               "blocks_pushed_ever=%llu\n",
               (unsigned long long)null_polls,
               h ? (uint32_t)h->write_block_idx : 0u,
               h ? (uint32_t)h->heartbeat        : 0u,
               h ? (uint32_t)h->magic             : 0u,
               (unsigned long long)blocks_pushed);
      }
    }

    usleep(1000); // 1ms poll
  }
  printf("[Reader] Stopped — total blocks pushed: %llu\n",
         (unsigned long long)blocks_pushed);
  return NULL;
}
// Extract channel 0 samples from an interleaved multi-channel buffer.
// out_ch0 must be pre-allocated with at least (total_frames) int16 slots.
static void extract_ch0(const int16_t *interleaved, uint32_t total_frames,
                        uint32_t channels, int16_t *out_ch0) {
  for (uint32_t i = 0; i < total_frames; i++) {
    out_ch0[i] = interleaved[i * channels];
  }
}

// Processor Thread: Pops from Ring Buffer, runs Decimator and Anomaly Detector
void *processor_thread_func(void *arg) {
  printf("[Processor] Started\n");

  anomaly_detector_t ad;
  if (anomaly_detector_init(&ad, global_config.anomalies, global_config.sensor,
                            global_config.detection, global_config.debounce,
                            global_config.nominal_rate_hz) != 0) {
    fprintf(stderr,
            "[Processor] Failed to init anomaly detector, exiting thread\n");
    return NULL;
  }

  decimator_t dec;
  decimator_init(&dec, global_config.nominal_rate_hz,
                 global_config.storage.decimation.target_output_rate_hz);

  time_sync_t t_sync;
  time_sync_init(&t_sync, 0, 200000000U);

  event_window_t ew;
  event_window_init(&ew, global_config.storage.events.pre_sec,
                    global_config.storage.events.post_sec,
                    global_config.nominal_rate_hz, CHANNELS);

  uint8_t temp_buf[2064];
  int16_t decimated_samples[128 * 8];
  uint32_t decimated_count = 0;
  uint64_t decimated_chunk_start_ns = 0;

  uint32_t pru_clock_hz = 200000000U;
  if (shm_reader.header && shm_reader.header->pru_clock_hz) {
    pru_clock_hz = shm_reader.header->pru_clock_hz;
  }
  uint64_t ns_per_sample = 1000000000ULL / global_config.nominal_rate_hz;
  uint64_t current_bucket_start_ns = 0;

  // Scratch buffer for channel-0 extraction — large enough for max event window
  // Max event window: (pre + post) seconds * sample_rate samples * 2 bytes
  // 5 seconds * 10000 Hz = 50000 samples (conservative upper bound)
  int16_t *ch0_scratch = (int16_t *)malloc(50000 * sizeof(int16_t));
  if (!ch0_scratch) {
    fprintf(stderr, "[Processor] Failed to allocate ch0 scratch buffer\n");
    anomaly_detector_free(&ad);
    event_window_free(&ew);
    return NULL;
  }

  bool time_synced = false;
  while (keep_running) {
    if (ring_buffer_pop(&raw_block_rb, temp_buf)) {
      block_descriptor_t *desc = (block_descriptor_t *)temp_buf;
      int16_t *samples = (int16_t *)(temp_buf + 16);

      if (!time_synced) {
        uint64_t now_ns = get_now_ns();
        uint64_t block_duration_ns =
          (uint64_t)desc->num_samples * ns_per_sample;
        uint64_t first_sample_est_ns =
          (now_ns > block_duration_ns) ? (now_ns - block_duration_ns)
                        : now_ns;

        printf(
          "[Processor] First block received. Syncing time to %llu cycles "
          "(PRU %u Hz)\n",
          (unsigned long long)desc->timestamp_cycles, pru_clock_hz);
        time_sync_init_at(&t_sync, desc->timestamp_cycles, pru_clock_hz,
                  first_sample_est_ns);
        time_synced = true;
      }

      // Push raw interleaved frame to the real-time oscilloscope buffer
      scope_buffer_push(&live_scope_buffer, samples, desc->num_samples);

      uint64_t block_time = cycles_to_ns(&t_sync, desc->timestamp_cycles);

      // 1. Snapshot for pre-event history (full multi-channel block)
      event_window_push_block(&ew, samples);

      // 2. Anomaly Detection (processes ch0, applies RMS + debounce)
      anomaly_event_t *event = anomaly_detector_process(
          &ad, samples, desc->num_samples, CHANNELS, block_time);
      if (event) {
        printf("[Processor] EVENT DETECTED: Type %d, VRMS=%.2f V at %llu ns\n",
               event->type, event->rms_vrms,
               (unsigned long long)event->timestamp_ns);
        event_window_trigger(&ew, *event);
      }

      // 3. Check for finished captures — extract ch0 before writing
      size_t event_data_size;
      anomaly_event_t captured_event;
      uint8_t *event_data =
          event_window_get_ready(&ew, &event_data_size, &captured_event);
      if (event_data) {
        // event_data is interleaved multi-channel int16; extract ch0 only
        uint32_t total_frames = (uint32_t)(event_data_size / (CHANNELS * 2));
        uint32_t ch0_sample_count = total_frames;

        if (ch0_sample_count <= 50000) {
          extract_ch0((const int16_t *)event_data, total_frames, CHANNELS,
                      ch0_scratch);

          printf("[Processor] Saving ch0 event data: %u samples (~%zu KB)\n",
                 ch0_sample_count, (ch0_sample_count * sizeof(int16_t)) / 1024);

          event_index_record_t index = {
              .timestamp_ns = captured_event.timestamp_ns,
              .event_type = (uint8_t)captured_event.type,
              .peak_value = captured_event.peak_value,
              .duration_samples = captured_event.duration_samples};

          writer_write_event(&disk_writer, &index, ch0_scratch,
                             ch0_sample_count);
        } else {
          fprintf(stderr,
                  "[Processor] Event too large (%u samples), skipping\n",
                  ch0_sample_count);
        }
      }

      // 4. Decimation (multi-channel, min/max bucketing on ch0)
      for (uint32_t i = 0; i < desc->num_samples; i++) {
        uint64_t sample_time_ns = block_time + ((uint64_t)i * ns_per_sample);
        if (dec.samples_in_bucket == 0) {
          current_bucket_start_ns = sample_time_ns;
        }

        int16_t ch0_sample = samples[i * CHANNELS]; /* Extract channel 0 */
        if (decimator_process(&dec, ch0_sample)) {
          if (decimated_count == 0) {
            decimated_chunk_start_ns = current_bucket_start_ns;
          }

          /* Bucket complete - store min/max for ch0 only (we're decimating ch0)
           */
          decimated_samples[decimated_count * 2] = dec.min_val;
          decimated_samples[decimated_count * 2 + 1] = dec.max_val;
          decimated_count++;

          /* Reset for next bucket */
          dec.min_val = INT16_MAX;
          dec.max_val = INT16_MIN;

          if (decimated_count >= 10) {
            decimated_chunk_header_t header = {
                .start_time_ns = decimated_chunk_start_ns,
                .sample_rate = global_config.nominal_rate_hz,
                .sample_count = decimated_count,
                .channels = 1, /* Only decimating ch0 */
                .values_per_sample =
                    2}; /* Store min/max (2 values per sample) */

            printf("[Processor] Decimated chunk ready: start_time_ns=%llu "
                   "sample_count=%u (will call writer_write_decimated)\n",
                   (unsigned long long)header.start_time_ns,
                   header.sample_count);
            writer_write_decimated(&disk_writer, &header, decimated_samples);
            decimated_count = 0;
          }
        }
      }
    } else {
      usleep(5000);
    }
  }

  /* Flush any remaining decimated data */
  if (decimated_count > 0) {
    decimated_chunk_header_t header = {
        .start_time_ns = decimated_chunk_start_ns,
        .sample_rate = global_config.nominal_rate_hz,
        .sample_count = decimated_count,
        .channels = 1,           /* Only decimating ch0 */
        .values_per_sample = 2}; /* Store min/max (2 values per sample) */

    printf("[Processor] Final decimated flush: start_time_ns=%llu "
           "sample_count=%u\n",
           (unsigned long long)header.start_time_ns,
           header.sample_count);
    writer_write_decimated(&disk_writer, &header, decimated_samples);
    printf("[Processor] Flushed final %u decimated samples\n", decimated_count);
  }

  printf("[Processor] Stopped\n");
  free(ch0_scratch);
  anomaly_detector_free(&ad);
  event_window_free(&ew);
  return NULL;
}

int main(int argc, char **argv) {
  signal(SIGINT, handle_sigint);
  signal(SIGTERM, handle_sigint);

  printf("Pika Datalogger starting...\n");

  // 1. Load Config
  if (config_load("../pika.yaml", &global_config) != 0) {
    fprintf(stderr, "Failed to load config, using defaults\n");
  }

  // 2. Init SHM Reader
  if (shm_reader_init(&shm_reader) != 0) {
    return 1;
  }

  /* Set channel enable flags from config (PRU will use these to skip inactive
   * channels) */
  if (shm_reader.header) {
    for (int i = 0; i < 8; i++) {
      shm_reader.header->ch_enable[i] = global_config.sensor.ch_enable[i];
    }
    shm_reader.header->sample_rate = global_config.nominal_rate_hz;

    printf("[Main] Set PRU channel enables: ");
    for (int i = 0; i < 8; i++) {
      printf("%d ", global_config.sensor.ch_enable[i]);
    }
    printf("(%d active channels)\n", global_config.sensor.active_channels);
    printf("[Main] Set PRU sample_rate to %u Hz\n",
           global_config.nominal_rate_hz);
  }

  // 3. Init Ring Buffer
  size_t element_size = 16 + (128 * CHANNELS * 2);
  ring_buffer_init(&raw_block_rb, 100, element_size);

  // 4. Init Writer (with size limits from config)
  if (writer_init(&disk_writer, "data", global_config.storage.decimation.max_mb,
                  global_config.storage.events.max_mb) != 0) {
    fprintf(stderr, "Failed to init writer\n");
    return 1;
  }

  // 4.5. Init Real-time Scope Buffer
  if (scope_buffer_init(&live_scope_buffer, global_config.nominal_rate_hz) !=
      0) {
    fprintf(stderr, "Failed to init scope buffer\n");
    return 1;
  }

  /* Set PRU timing info in scope buffer for webapp */
  if (live_scope_buffer.shm) {
    live_scope_buffer.shm->pru_clock_hz = 200000000; /* 200 MHz on BBB */
    if (shm_reader.header) {
      live_scope_buffer.shm->sample_period_cycles =
          shm_reader.header->sample_period_cycles;
    }
  }

  // 5. Start PRU
  printf("Starting PRU firmware...\n");
  shm_pru_set_state("start");

  // 6. Spawn Threads
  pthread_t reader_tid, processor_tid;
  pthread_create(&reader_tid, NULL, reader_thread_func, NULL);
  pthread_create(&processor_tid, NULL, processor_thread_func, NULL);

  // 7. Wait for exit
  while (keep_running) {
    sleep(1);
  }

  // 8. Cleanup
  printf("Shutting down...\n");
  shm_pru_set_state("stop");

  pthread_join(reader_tid, NULL);
  pthread_join(processor_tid, NULL);

  shm_reader_cleanup(&shm_reader);
  ring_buffer_free(&raw_block_rb);
  writer_cleanup(&disk_writer);
  scope_buffer_cleanup(&live_scope_buffer);

  printf("Datalogger exited cleanly.\n");
  return 0;
}
