/**
 * Minimal Linux userspace datalogger for PRU AD7606 ADC.
 * Mmaps PRU shared memory, initializes config, starts PRU, reads ring buffer.
 *
 * Build with: -I../pru/include
 * PRU firmware must be installed first (e.g. make pru-load from top level).
 */

#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#include "shm_layout.h"

/* Physical base address for PRU shared memory.
 * PRU Shared RAM is at 0x4a310000 from the ARM's perspective. */
#define PRU_SHM_PHYS_BASE 0x4a310000
#define PRU_SHM_SIZE 0x3000 /* 12 KB PRU Shared RAM */

#define REMOTEPROC_STATE "/sys/class/remoteproc/remoteproc0/state"

static uint8_t count_channels(uint32_t mask) {
  uint8_t n = 0;
  for (int i = 0; i < MAX_CHANNELS; i++)
    if (mask & (1u << i))
      n++;
  return n;
}

static int pru_state_write(const char *value) {
  int fd = open(REMOTEPROC_STATE, O_WRONLY);
  if (fd < 0) {
    perror("open " REMOTEPROC_STATE);
    return -1;
  }
  size_t len = strlen(value);
  ssize_t n = write(fd, value, len);
  close(fd);
  if (n != (ssize_t)len) {
    perror("write state");
    return -1;
  }
  return 0;
}

static int pru_stop(void) { return pru_state_write("stop"); }

static int pru_start(void) { return pru_state_write("start"); }

int main(void) {
  const uint32_t channel_mask = 0x01; /* 1 channel */
  const uint32_t block_size = 256;
  const uint32_t num_blocks = 4;

  uint8_t num_channels = count_channels(channel_mask);
  uint32_t block_data_size =
      block_size * num_channels * (uint32_t)sizeof(uint16_t);
  uint32_t block_total_size =
      (uint32_t)sizeof(block_descriptor_t) + block_data_size;
  size_t shm_used =
      sizeof(pru_shared_memory_t) + (size_t)num_blocks * block_total_size;

  int fd = open("/dev/mem", O_RDWR | O_SYNC);
  if (fd < 0) {
    perror("open /dev/mem");
    return 1;
  }

  void *base = mmap(NULL, PRU_SHM_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd,
                    PRU_SHM_PHYS_BASE);
  if (base == MAP_FAILED) {
    perror("mmap");
    close(fd);
    return 1;
  }
  close(fd);

  volatile pru_shared_memory_t *shm = (volatile pru_shared_memory_t *)base;

  /* Stop PRU if running (idempotent) */
  if (pru_stop() != 0) {
    fprintf(stderr, "pru_stop failed (run as root?)\n");
    munmap((void *)base, PRU_SHM_SIZE);
    return 1;
  }

  /* Zero out shared memory first to ensure no stale data */
  memset((void *)base, 0, sizeof(pru_shared_memory_t));

  /* Initialize header for PRU - write magic LAST */
  shm->version = SHM_VERSION;
  shm->sample_period_cycles = 20000; /* 100 us @ 200 MHz = 10 kHz */
  shm->channel_mask = channel_mask;
  shm->block_size = block_size;
  shm->num_blocks = num_blocks;
  shm->write_block_idx = 0;
  shm->error_flags = 0;
  shm->sample_count = 0;

  /* Ensure ARM CPU flushes config before writing magic */
  __sync_synchronize();
  msync(base, PRU_SHM_SIZE, MS_SYNC);

  shm->magic = SHM_MAGIC;

  /* Ensure magic is flushed */
  __sync_synchronize();
  msync(base, PRU_SHM_SIZE, MS_SYNC);

  printf("datalogger: debug shm initialized (size=%zu)\n",
         sizeof(pru_shared_memory_t));
  printf("  magic: 0x%08x\n", shm->magic);
  printf("  period: %u\n", shm->sample_period_cycles);
  printf("  mask: 0x%x\n", shm->channel_mask);
  printf("  block_size: %u\n", shm->block_size);
  printf("  num_blocks: %u\n", shm->num_blocks);

  usleep(10000);

  if (pru_start() != 0) {
    fprintf(stderr, "pru_start failed\n");
    munmap((void *)base, PRU_SHM_SIZE);
    return 1;
  }

  /* Give PRU a moment to start and pass magic check */
  usleep(100000);

  if (shm->magic != SHM_MAGIC) {
    fprintf(stderr, "PRU did not accept magic (shm->magic=0x%08x)\n",
            shm->magic);
    munmap((void *)base, PRU_SHM_SIZE);
    return 1;
  }

  uint32_t read_block = 0;
  int blocks_printed = 0;
  int total_blocks_read = 0;
  const int max_blocks_to_print = 4;
  const int samples_per_block_to_print = 8;
  const int max_blocks_then_exit =
      20; /* exit after this many blocks for testing */

  printf("datalogger: reading blocks (channels=%u, block_size=%u, "
         "num_blocks=%u)\n",
         (unsigned)num_channels, (unsigned)block_size, (unsigned)num_blocks);

  while (total_blocks_read < max_blocks_then_exit) {
    if (shm->error_flags != 0) {
      uint32_t err = shm->error_flags;
      fprintf(stderr, "PRU Error detected: 0x%x\n", err);
      if (err & ERROR_CFG_PERIOD)
        fprintf(stderr, "  - ERROR_CFG_PERIOD\n");
      if (err & ERROR_CFG_MASK)
        fprintf(stderr, "  - ERROR_CFG_MASK\n");
      if (err & ERROR_CFG_BLOCKSIZE)
        fprintf(stderr, "  - ERROR_CFG_BLOCKSIZE\n");
      if (err & ERROR_CFG_NUMBLOCKS) {
        fprintf(stderr, "  - ERROR_CFG_NUMBLOCKS\n");
        fprintf(stderr, "  - PRU echoed val_num_blocks: %u\n",
                shm->write_block_idx);
        fprintf(stderr, "  - PRU echoed val_block_size: %u\n",
                shm->sample_count);
      }
      break;
    }

    uint32_t write_idx = shm->write_block_idx;

    while (read_block != write_idx &&
           total_blocks_read < max_blocks_then_exit) {
      uint8_t *block_base = (uint8_t *)base + sizeof(pru_shared_memory_t) +
                            (size_t)read_block * block_total_size;
      block_descriptor_t *desc = (block_descriptor_t *)block_base;
      uint16_t *data = (uint16_t *)(block_base + sizeof(block_descriptor_t));

      if (blocks_printed < max_blocks_to_print) {
        printf("block %u: num_samples=%u", (unsigned)read_block,
               (unsigned)desc->num_samples);
        int n = (int)desc->num_samples * (int)num_channels;
        if (n > samples_per_block_to_print)
          n = samples_per_block_to_print;
        for (int i = 0; i < n; i++)
          printf(" %u", (unsigned)data[i]);
        printf("\n");
        blocks_printed++;
      }

      read_block = (read_block + 1) % num_blocks;
      total_blocks_read++;
    }

    usleep(5000);
  }

  printf("datalogger: read %d blocks, exiting\n", total_blocks_read);
  munmap((void *)base, PRU_SHM_SIZE);
  (void)shm_used;
  return 0;
}
