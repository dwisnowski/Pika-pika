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
  void *mmap_base;     /* PRU Shared RAM (header) */
  void *ddr_mmap_base; /* DDR sample ring (mapped after PRU publishes PA) */
  uint32_t pru_shm_phys_addr;
  uint32_t ddr_phys_addr;
  uint32_t ddr_size_bytes;
  volatile pru_shared_memory_t *header;
  uint32_t last_read_block_idx;
  uint32_t last_completed_blocks;
} shm_reader_t;

/**
 * Initializes the SHM reader by mapping Shared RAM control header.
 * DDR ring is mapped later via shm_reader_map_ddr() once PRU publishes PA.
 */
int shm_reader_init(shm_reader_t *reader);

/**
 * Map the DDR sample ring using phys/size from the PRU header (or overrides).
 * Safe to call more than once; remaps if the address changes.
 * Returns 0 on success.
 */
int shm_reader_map_ddr(shm_reader_t *reader);

/**
 * If the PRU could not read the carveout PA from its resource table, discover
 * it from PRU0 DMEM (remoteproc-patched table) and publish it into the SHM
 * header so the PRU can proceed. Returns 0 on success.
 */
int shm_reader_publish_carveout_pa(shm_reader_t *reader);

/**
 * Cleans up SHM reader (unmaps memory).
 */
void shm_reader_cleanup(shm_reader_t *reader);

/**
 * Polls for a new completed block in the DDR ring.
 */
volatile block_descriptor_t *shm_reader_poll(shm_reader_t *reader,
                                             uint8_t **data_ptr);

/**
 * Sends a command to the PRU via sysfs.
 */
int shm_pru_set_state(const char *state);

#endif // SHM_READER_H
