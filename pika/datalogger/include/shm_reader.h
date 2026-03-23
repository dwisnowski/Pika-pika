#ifndef SHM_READER_H
#define SHM_READER_H

#include "../../pru/include/shm_layout.h"
#include <stdbool.h>
#include <stdint.h>

// Constants from main.c / PRU config
#define PRU_SHM_PHYS_BASE 0x4a310000
#define PRU_SHM_SIZE 0x3000

typedef struct {
  int mem_fd;
  void *mmap_base;
  uint32_t pru_shm_phys_addr;
  volatile pru_shared_memory_t *header;
  uint32_t last_read_block_idx;
} shm_reader_t;

/**
 * Initializes the SHM reader by mapping /dev/mem.
 * Returns 0 on success.
 */
int shm_reader_init(shm_reader_t *reader);

/**
 * Cleans up SHM reader (unmaps memory).
 */
void shm_reader_cleanup(shm_reader_t *reader);

/**
 * Polls for a new block.
 * If a new block is available, returns pointer to the block descriptor.
 * Marks the block as "read" internally.
 */
volatile block_descriptor_t *shm_reader_poll(shm_reader_t *reader,
                                             uint8_t **data_ptr);

/**
 * Sends a command to the PRU via sysfs.
 */
int shm_pru_set_state(const char *state);

#endif // SHM_READER_H
