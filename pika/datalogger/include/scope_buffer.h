#ifndef SCOPE_BUFFER_H
#define SCOPE_BUFFER_H

#include <stdbool.h>
#include <stdint.h>

#define SCOPE_SHM_NAME "/pika_scope_shm"
#define SCOPE_CHANNELS 8
// 1,048,576 samples per channel (~5.8 seconds @ 180kHz)
#define SCOPE_CAPACITY 1048576
#define SCOPE_MAGIC 0x5C09E000

typedef struct {
  uint32_t magic;
  uint32_t sample_rate;
  uint32_t channels;
  uint32_t capacity;

  // Total multi-channel samples written.
  // Array index = (total_samples % capacity) * channels
  uint64_t total_samples;

  // Interleaved data: ch0, ch1, ... ch7
  int16_t data[SCOPE_CAPACITY * SCOPE_CHANNELS];
} scope_shm_t;

typedef struct {
  int fd;
  scope_shm_t *shm;
} scope_buffer_t;

/**
 * Initialize and memory-map the large /dev/shm ring buffer.
 */
int scope_buffer_init(scope_buffer_t *sb, uint32_t sample_rate);

/**
 * Free memory mappings and close the handle.
 */
void scope_buffer_cleanup(scope_buffer_t *sb);

/**
 * Push interleaved samples into the circular buffer.
 * @param interleaved_samples The raw ADC block (ch0..ch7 repeating)
 * @param num_samples_per_channel The number of complete 8-channel frames
 */
void scope_buffer_push(scope_buffer_t *sb, const int16_t *interleaved_samples,
                       uint32_t num_samples_per_channel);

#endif // SCOPE_BUFFER_H
