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
#include "shm_reader.h"
#include "time_utils.h"
#include "writer.h"

// Global state
volatile int keep_running = 1;
logger_config_t global_config;
ring_buffer_t raw_block_rb;
shm_reader_t shm_reader;
writer_t disk_writer;

void handle_sigint(int sig) { keep_running = 0; }

// Reader Thread: Pulls from PRU SHM, pushes to Ring Buffer
void *reader_thread_func(void *arg) {
  printf("[Reader] Started\n");
  while (keep_running) {
    uint8_t *data;
    volatile block_descriptor_t *desc = shm_reader_poll(&shm_reader, &data);

    if (desc) {
      // New block found!
      // Calculate total size: 16 (desc) + (samples * channels * 2)
      size_t data_size = desc->num_samples * global_config.channels * 2;

      // For now, let's just copy exactly what we need
      // In a better version, we'd use zero-copy or pre-allocated chunks
      uint8_t temp_buf[2064];
      memcpy(temp_buf, (void *)desc, 16);
      memcpy(temp_buf + 16, data, data_size);

      if (!ring_buffer_push(&raw_block_rb, temp_buf)) {
        fprintf(stderr, "[Reader] Warning: Ring buffer overflow!\n");
      }
    }

    usleep(1000); // 1ms poll
  }
  printf("[Reader] Stopped\n");
  return NULL;
}

// Processor Thread: Pops from Ring Buffer, runs Decimator and Anomaly Detector
void *processor_thread_func(void *arg) {
  printf("[Processor] Started\n");

  anomaly_detector_t ad;
  anomaly_detector_init(&ad, global_config.anomalies,
                        20000); // Placeholder nominal peak

  decimator_t dec;
  decimator_init(&dec, global_config.normal_decimation_rate);

  time_sync_t t_sync;
  time_sync_init(&t_sync, 0, global_config.nominal_rate_hz);

  event_window_t ew;
  event_window_init(&ew, global_config.pre_event_sec,
                    global_config.post_event_sec, global_config.nominal_rate_hz,
                    global_config.channels);

  uint8_t temp_buf[2064];
  uint16_t decimated_samples[128 * 8];
  uint32_t decimated_count = 0;

  while (keep_running) {
    if (ring_buffer_pop(&raw_block_rb, temp_buf)) {
      block_descriptor_t *desc = (block_descriptor_t *)temp_buf;
      uint16_t *samples = (uint16_t *)(temp_buf + 16);

      uint64_t block_time = cycles_to_ns(&t_sync, desc->timestamp_cycles);

      // 1. Snapshot for history
      event_window_push_block(&ew, samples);

      // 2. Anomaly Detection
      anomaly_event_t *event =
          anomaly_detector_process(&ad, samples, desc->num_samples, block_time);
      if (event) {
        printf("[Processor] EVENT DETECTED: Type %d at %llu\n", event->type,
               event->timestamp_ns);
        event_window_trigger(&ew, *event);
      }

      // 3. Check for finished captures
      size_t event_data_size;
      anomaly_event_t captured_event;
      uint8_t *event_data =
          event_window_get_ready(&ew, &event_data_size, &captured_event);
      if (event_data) {
        printf("[Processor] Saving high-res event data to disk (%zu bytes)\n",
               event_data_size);
        event_index_record_t index = {
            .timestamp_ns = captured_event.timestamp_ns,
            .event_type = (uint8_t)captured_event.type,
            .peak_value = captured_event.peak_value,
            .duration_samples = captured_event.duration_samples};
        writer_write_event(&disk_writer, &index, (uint16_t *)event_data,
                           event_data_size);
      }

      // 4. Decimation
      for (uint32_t i = 0; i < desc->num_samples; i++) {
        if (decimator_process(&dec)) {
          // Keep this sample
          memcpy(&decimated_samples[decimated_count * 8], &samples[i * 8],
                 8 * 2);
          decimated_count++;

          if (decimated_count >= 10) { // Batch writes
            printf("[Processor] Flushing %u decimated samples to disk\n",
                   decimated_count);
            decimated_chunk_header_t header = {
                .start_time_ns = block_time,
                .sample_rate = global_config.nominal_rate_hz /
                               global_config.normal_decimation_rate,
                .sample_count = decimated_count,
                .channels = global_config.channels};
            writer_write_decimated(&disk_writer, &header, decimated_samples);
            decimated_count = 0;
          }
        }
      }
    } else {
      usleep(5000); // Wait for data
    }
  }
  printf("[Processor] Stopped\n");
  event_window_free(&ew);
  return NULL;
}

int main(int argc, char **argv) {
  signal(SIGINT, handle_sigint);
  signal(SIGTERM, handle_sigint);

  printf("Pika Datalogger starting...\n");

  // 1. Load Config
  if (config_load("config/logger.yaml", &global_config) != 0) {
    fprintf(stderr, "Failed to load config, using defaults\n");
  }

  // 2. Init SHM Reader
  if (shm_reader_init(&shm_reader) != 0) {
    return 1;
  }

  // 3. Init Ring Buffer
  // Element size = 16 (desc) + (128 samples * 8 channels * 2 bytes) = 2064
  // bytes
  size_t element_size = 16 + (128 * 8 * 2);
  ring_buffer_init(&raw_block_rb, 100, element_size);

  // 4. Init Writer
  if (writer_init(&disk_writer, "data") != 0) {
    fprintf(stderr, "Failed to init writer\n");
    return 1;
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

  printf("Datalogger exited cleanly.\n");
  return 0;
}
