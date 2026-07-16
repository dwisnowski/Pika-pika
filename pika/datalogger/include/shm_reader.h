#ifndef SHM_READER_H
#define SHM_READER_H

#include "../../pru/include/shm_layout.h"
#include <stdbool.h>
#include <stdint.h>

/* Control header in PRU Shared RAM */
#define PRU_SHM_PHYS_BASE 0x4a310000
#define PRU_SHM_SIZE 0x3000

typedef struct {
  int mem_fd;
  void *mmap_base;       /* PRU Shared RAM (header) */
  void *ddr_mmap_base;   /* DDR sample ring */
  uint32_t pru_shm_phys_addr;
  uint32_t ddr_phys_addr;
  uint32_t ddr_size_bytes;
  volatile pru_shared_memory_t *header;
  uint32_t last_read_block_idx;
  uint32_t last_completed_blocks;
} shm_reader_t;

/**
 * Initializes the SHM reader by mapping /dev/mem (Shared RAM + DDR ring).
 * Returns 0 on success.
 */
int shm_reader_init(shm_reader_t *reader);

/**
 * Cleans up SHM reader (unmaps memory).
 */
void shm_reader_cleanup(shm_reader_t *reader);

/**
 * Polls for a new completed block.
 * If available, returns pointer to the block descriptor in the DDR mapping
 * and sets *data_ptr to the sample payload. Marks the block as consumed.
 */
volatile block_descriptor_t *shm_reader_poll(shm_reader_t *reader,
                                             uint8_t **data_ptr);

/**
 * Sends a command to the PRU via sysfs.
 */
int shm_pru_set_state(const char *state);

#endif // SHM_READER_H
