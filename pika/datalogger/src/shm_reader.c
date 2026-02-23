#define _GNU_SOURCE
#include "shm_reader.h"
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#define REMOTEPROC_STATE "/sys/class/remoteproc/remoteproc0/state"

int shm_reader_init(shm_reader_t *reader) {
  reader->mem_fd = open("/dev/mem", O_RDWR | O_SYNC);
  if (reader->mem_fd < 0) {
    perror("open /dev/mem");
    return -1;
  }

  reader->mmap_base = mmap(NULL, PRU_SHM_SIZE, PROT_READ | PROT_WRITE,
                           MAP_SHARED, reader->mem_fd, PRU_SHM_PHYS_BASE);
  if (reader->mmap_base == MAP_FAILED) {
    perror("mmap");
    close(reader->mem_fd);
    return -1;
  }

  reader->header = (volatile pru_shared_memory_t *)reader->mmap_base;
  reader->last_read_block_idx =
      0; // Initialize but PRU might already be running

  return 0;
}

void shm_reader_cleanup(shm_reader_t *reader) {
  if (reader->mmap_base) {
    munmap(reader->mmap_base, PRU_SHM_SIZE);
  }
  if (reader->mem_fd >= 0) {
    close(reader->mem_fd);
  }
}

int shm_pru_set_state(const char *state) {
  int fd = open(REMOTEPROC_STATE, O_WRONLY);
  if (fd < 0)
    return -1;
  write(fd, state, strlen(state));
  close(fd);
  return 0;
}

volatile block_descriptor_t *shm_reader_poll(shm_reader_t *reader,
                                             uint8_t **data_ptr) {
  uint32_t current_blk = reader->header->write_block_idx;

  // Check if PRU has advanced past our last read index
  if (current_blk == reader->last_read_block_idx) {
    return NULL;
  }

  // In a ring buffer, the PRU writes to block N then increments index.
  // The most recently COMPLETED block is (current_blk - 1) % num_blocks.
  // HOWEVER, the current PRU implementation (pru_main.c) does:
  //   current_blk = (current_blk + 1) % num_blocks;
  //   shm->write_block_idx = current_blk;
  // This means write_block_idx is where the PRU IS CURRENTLY WRITING or WILL
  // WRITE. So the data we want to read is at the PREVIOUS index.

  uint32_t num_blocks = reader->header->num_blocks;
  if (num_blocks == 0)
    return NULL; // SHM not initialized yet

  uint32_t ready_idx = (current_blk + num_blocks - 1) % num_blocks;

  // If we've already read this "ready" block, nothing new.
  // This logic needs to handle the very first block correctly.
  // Let's keep it simple: if current_blk changed, update last_read and return
  // the PREVIOUS block.

  reader->last_read_block_idx = current_blk;

  // Calculate memory offset for the ready block
  // Header is 64 bytes.
  // block_total_size = 16 (desc) + (samples * channels * 2)
  uint32_t block_size = reader->header->block_size;
  uint32_t block_total_size =
      16 + (block_size * 8 * 2); // 8 channels hardcoded for now

  uint8_t *b_base =
      ((uint8_t *)reader->mmap_base) + 64 + (ready_idx * block_total_size);

  if (data_ptr) {
    *data_ptr = b_base + 16;
  }

  return (volatile block_descriptor_t *)b_base;
}
