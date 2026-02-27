#include "scope_buffer.h"
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

int scope_buffer_init(scope_buffer_t *sb, uint32_t sample_rate) {
  memset(sb, 0, sizeof(*sb));

  // Open POSIX shared memory object
  int fd = shm_open(SCOPE_SHM_NAME, O_CREAT | O_RDWR, 0666);
  if (fd < 0) {
    perror("shm_open failed for scope_buffer");
    return -1;
  }

  // Set size
  size_t size = sizeof(scope_shm_t);
  if (ftruncate(fd, size) < 0) {
    perror("ftruncate failed for scope_buffer");
    close(fd);
    return -1;
  }

  // Map into memory
  void *ptr = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
  if (ptr == MAP_FAILED) {
    perror("mmap failed for scope_buffer");
    close(fd);
    return -1;
  }

  sb->fd = fd;
  sb->shm = (scope_shm_t *)ptr;

  // Initialize header
  sb->shm->magic = SCOPE_MAGIC;
  sb->shm->sample_rate = sample_rate;
  sb->shm->channels = SCOPE_CHANNELS;
  sb->shm->capacity = SCOPE_CAPACITY;
  sb->shm->pru_clock_hz = 200000000;  /* 200 MHz on BeagleBone Black */
  sb->shm->sample_period_cycles = 0;  /* Will be set by datalogger */
  // Don't reset total_samples if another reader is already synced?
  // Actually, safest to reset so we know the buffer is fresh on startup.
  sb->shm->total_samples = 0;

  printf("[ScopeBuffer] Initialized %u MB circular buffer in /dev/shm%s\n",
         (uint32_t)(size / (1024 * 1024)), SCOPE_SHM_NAME);

  return 0;
}

void scope_buffer_cleanup(scope_buffer_t *sb) {
  if (sb->shm && sb->shm != MAP_FAILED) {
    munmap(sb->shm, sizeof(scope_shm_t));
    sb->shm = NULL;
  }
  if (sb->fd >= 0) {
    close(sb->fd);
    sb->fd = -1;
  }
}

void scope_buffer_push(scope_buffer_t *sb, const int16_t *interleaved_samples,
                       uint32_t num_samples_per_channel) {
  if (!sb->shm)
    return;

  uint32_t capacity = sb->shm->capacity;
  uint32_t channels = sb->shm->channels;
  uint64_t head = sb->shm->total_samples % capacity;

  uint32_t space_until_wrap = capacity - head;

  if (num_samples_per_channel <= space_until_wrap) {
    // Fits perfectly without wrapping
    memcpy(&sb->shm->data[head * channels], interleaved_samples,
           num_samples_per_channel * channels * sizeof(int16_t));
  } else {
    // Writes span the boundary
    uint32_t first_part = space_until_wrap;
    uint32_t second_part = num_samples_per_channel - space_until_wrap;

    memcpy(&sb->shm->data[head * channels], interleaved_samples,
           first_part * channels * sizeof(int16_t));

    memcpy(&sb->shm->data[0], &interleaved_samples[first_part * channels],
           second_part * channels * sizeof(int16_t));
  }

  // Update the global monotonic counter
  sb->shm->total_samples += num_samples_per_channel;
}
