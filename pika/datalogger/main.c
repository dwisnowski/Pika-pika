/**
 * Pika Datalogger - Verbose Debug Edition
 */

#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#include "../pru/include/shm_layout.h"

#define PRU_SHM_PHYS_BASE 0x4a310000
#define PRU_SHM_SIZE 0x3000
#define REMOTEPROC_STATE "/sys/class/remoteproc/remoteproc0/state"

static int pru_state_write(const char *value) {
  int fd = open(REMOTEPROC_STATE, O_WRONLY);
  if (fd < 0)
    return -1;
  write(fd, value, strlen(value));
  close(fd);
  return 0;
}

int main(void) {
  const uint32_t channel_mask = 0xFF; // 8 channels
  const uint32_t block_size = 128;
  const uint32_t num_blocks = 4;
  const uint32_t block_total_size = 16 + (block_size * 8 * 2);

  int fd = open("/dev/mem", O_RDWR | O_SYNC);
  if (fd < 0) {
    perror("open /dev/mem");
    return 1;
  }
  void *base = mmap(NULL, PRU_SHM_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd,
                    PRU_SHM_PHYS_BASE);
  close(fd);

  volatile pru_shared_memory_t *shm = (volatile pru_shared_memory_t *)base;

  printf("Resetting PRU and Shared Memory...\n");
  pru_state_write("stop");
  memset((void *)base, 0, sizeof(pru_shared_memory_t));

  shm->version = SHM_VERSION;
  shm->sample_period_cycles = 20000; // 100us = 10kHz
  shm->channel_mask = channel_mask;
  shm->block_size = block_size;
  shm->num_blocks = num_blocks;

  __sync_synchronize();
  shm->magic = SHM_MAGIC;

  printf("Starting PRU...\n");
  pru_state_write("start");

  printf("AD7606 Debug Logger (Interval: 0.2s). Press Ctrl+C to stop.\n");

  struct timespec last_print;
  clock_gettime(CLOCK_MONOTONIC, &last_print);

  while (1) {
    // Immediate Error Check
    if (shm->error_flags != 0) {
      uint32_t err = shm->error_flags;
      printf("\nFATAL: PRU HALTED with Error 0x%08x\n", err);
      if (err == 0x02)
        printf("  Meaning: BUSY signal never went HIGH (Check CONVST/BUSY/VCC "
               "wiring)\n");
      if (err == 0x04)
        printf("  Meaning: BUSY signal stuck HIGH (Check BUSY wiring)\n");
      break;
    }

    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    double elapsed = (now.tv_sec - last_print.tv_sec) +
                     (now.tv_nsec - last_print.tv_nsec) / 1e9;

    if (elapsed >= 0.2) {
      uint32_t b_idx = shm->write_block_idx;
      uint8_t *b_ptr = (uint8_t *)base + 64 + (b_idx * block_total_size);
      volatile block_descriptor_t *d = (volatile block_descriptor_t *)b_ptr;
      uint16_t *data = (uint16_t *)(b_ptr + 16);

      printf("STAT: clk=%-6u | HB=%08x | blk=%u flg=%08x | CH0: %4.3fV\n",
             shm->sample_count, shm->reserved[0], b_idx, d->flags,
             (float)(int16_t)data[0] * 5.0f / 32768.0f);

      last_print = now;
    }

    usleep(10000);
  }

  pru_state_write("stop");
  munmap(base, PRU_SHM_SIZE);
  return 0;
}
