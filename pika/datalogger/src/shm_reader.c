#define _GNU_SOURCE
#include "shm_reader.h"
#include <fcntl.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#define REMOTEPROC_BASE "/sys/class/remoteproc"

static char discovered_remoteproc_path[256] = "";

static const char *discover_pru0_info(uint32_t *out_shm_phys) {
  if (discovered_remoteproc_path[0] != '\0') {
    // We already have it, but we need to re-parse the address for the caller if
    // desired
    return discovered_remoteproc_path;
  }

  uint32_t shm_phys = 0x4a310000; // Default fallback

  for (int i = 0; i < 5; i++) {
    char name_path[256];
    char name_buf[256];
    snprintf(name_path, sizeof(name_path),
             "/sys/class/remoteproc/remoteproc%d/name", i);
    FILE *f = fopen(name_path, "r");
    if (f) {
      if (fgets(name_buf, sizeof(name_buf), f)) {
        // Typical strings: "4a334000.pru" (PRU0) or "4a338000.pru" (PRU1)
        if (strstr(name_buf, "4a334000") || strstr(name_buf, "pru0")) {
          // Parse out the hex address to calculate Shared RAM location
          unsigned int ctrl_addr = 0;
          if (sscanf(name_buf, "%x", &ctrl_addr) == 1) {
            // Standard AM335x offsets from PRUSS Base (0x4a300000):
            // Shared RAM = Base + 0x10000
            // PRU0 CTRL  = Base + 0x22000
            // PRU0 IRAM  = Base + 0x34000 (This is often what's in 'name')

            uint32_t pruss_base = 0;
            if ((ctrl_addr & 0xFFFFF000) == 0x4a334000)
              pruss_base = ctrl_addr - 0x34000;
            else if ((ctrl_addr & 0xFFFFF000) == 0x4a322000)
              pruss_base = ctrl_addr - 0x22000;
            else
              pruss_base = ctrl_addr & 0xFFF80000; // Guess alignment

            shm_phys = pruss_base + 0x10000;
          }

          snprintf(discovered_remoteproc_path,
                   sizeof(discovered_remoteproc_path),
                   "/sys/class/remoteproc/remoteproc%d/state", i);
          fclose(f);
          printf("[SHM Reader] Discovered PRU0 at remoteproc%d (%s)\n", i,
                 name_buf);
          printf("[SHM Reader] Calculated Shared RAM Physical: 0x%08X\n",
                 shm_phys);

          if (out_shm_phys)
            *out_shm_phys = shm_phys;
          return discovered_remoteproc_path;
        }
      }
      fclose(f);
    }
  }

  if (out_shm_phys)
    *out_shm_phys = shm_phys;
  return "/sys/class/remoteproc/remoteproc1/state";
}

int shm_reader_init(shm_reader_t *reader) {
  uint32_t shm_phys = 0;
  discover_pru0_info(&shm_phys);
  reader->pru_shm_phys_addr = shm_phys;

  reader->mem_fd = open("/dev/mem", O_RDWR | O_SYNC);
  if (reader->mem_fd < 0) {
    perror("open /dev/mem");
    return -1;
  }

  reader->mmap_base =
      mmap(NULL, PRU_SHM_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED,
           reader->mem_fd, reader->pru_shm_phys_addr);
  if (reader->mmap_base == MAP_FAILED) {
    perror("mmap");
    close(reader->mem_fd);
    return -1;
  }

  reader->header = (volatile pru_shared_memory_t *)reader->mmap_base;

  // Safety: If header looks uninitialized, we can zero it, but DON'T wipe a
  // valid magic This allows the datalogger to reconnect to a running PRU.
  if (reader->header->magic != SHM_MAGIC) {
    printf("[SHM Reader] Header uninitialized (magic=0x%08X), preparing clean "
           "state...\n",
           (uint32_t)reader->header->magic);
    reader->header->magic = 0;
    reader->header->num_blocks = 0;
    reader->header->write_block_idx = 0;
  }

  // Use UINT32_MAX as "unsynced" sentinel. First poll will latch current
  // write_block_idx to avoid consuming potentially stale pre-start data.
  reader->last_read_block_idx = UINT32_MAX;

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
  const char *path = discover_pru0_info(NULL);
  int fd = open(path, O_WRONLY);
  if (fd < 0) {
    perror("open remoteproc state");
    return -1;
  }
  write(fd, state, strlen(state));
  close(fd);
  return 0;
}

volatile block_descriptor_t *shm_reader_poll(shm_reader_t *reader,
                                             uint8_t **data_ptr) {
  static uint32_t poll_count = 0;
  static uint32_t invalid_idx_count = 0;
  static uint32_t unstable_idx_count = 0;
  poll_count++;

  // Safety: Don't trust the header until PRU has written the magic number
  if (reader->header->magic != SHM_MAGIC) {
    if (poll_count % 1000 == 0) {
      printf("[SHM Reader] Waiting for magic (found 0x%08X)... heartbeat=%u\n",
             (uint32_t)reader->header->magic,
             (uint32_t)reader->header->heartbeat);
    }
    return NULL;
  }

  uint32_t num_blocks = reader->header->num_blocks;
  if (num_blocks == 0 || num_blocks > 64) {
    if (poll_count % 5000 == 0) {
      printf("[SHM Reader] Waiting for valid num_blocks (got %u)\n",
             num_blocks);
    }
    return NULL;
  }

  // Read twice to avoid transient/torn observations while PRU updates SHM.
  uint32_t current_blk_a = reader->header->write_block_idx;
  uint32_t current_blk_b = reader->header->write_block_idx;
  if (current_blk_a != current_blk_b) {
    unstable_idx_count++;
    if (unstable_idx_count % 1000 == 0) {
      printf("[SHM Reader] Unstable write_idx read: a=%u b=%u (count=%u)\n",
             current_blk_a, current_blk_b, unstable_idx_count);
    }
    return NULL;
  }

  uint32_t current_blk = current_blk_b;
  if (current_blk >= num_blocks) {
    invalid_idx_count++;
    if (invalid_idx_count % 1000 == 0) {
      printf("[SHM Reader] Invalid write_idx=%u (num_blocks=%u, count=%u)\n",
             current_blk, num_blocks, invalid_idx_count);
    }
    return NULL;
  }

  if (poll_count % 5000 == 0) {
    // Periodic debug log
    printf("[SHM Reader] Tick: write_idx=%u, last_idx=%u, num_blocks=%u, "
           "heartbeat=%u, err=0x%08X\n",
           current_blk, reader->last_read_block_idx,
           num_blocks,
           (uint32_t)reader->header->heartbeat,
           (uint32_t)reader->header->error_flags);
  }

  // Initial synchronization: latch current writer position and wait for
  // PRU to advance before returning the first complete block.
  if (reader->last_read_block_idx == UINT32_MAX) {
    reader->last_read_block_idx = current_blk;
    return NULL;
  }

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

  uint32_t ready_idx = (current_blk + num_blocks - 1) % num_blocks;

  // If we've already read this "ready" block, nothing new.
  // This logic needs to handle the very first block correctly.
  // Let's keep it simple: if current_blk changed, update last_read and return
  // the PREVIOUS block.

  reader->last_read_block_idx = current_blk;

  // Calculate memory offset for the ready block
  // Header is 128 bytes (SHM_HEADER_OFFSET).
  // block_total_size = 16 (desc) + (samples * channels * 2)
  uint32_t block_size = reader->header->block_size;
  if (block_size == 0 || block_size > 1024) {
    return NULL; // Invalid block size
  }

  uint32_t block_total_size =
      16 + (block_size * 8 * 2); // 8 channels hardcoded for now

  uint8_t *b_base = ((uint8_t *)reader->mmap_base) + SHM_HEADER_OFFSET +
                    (ready_idx * block_total_size);

  if (data_ptr) {
    *data_ptr = b_base + 16;
  }

  volatile block_descriptor_t *desc = (volatile block_descriptor_t *)b_base;

  // Final safety: only consume finalized descriptors with plausible sample
  // count.
  if (desc->flags != 0xAA55AA55) {
    return NULL;
  }
  if (desc->num_samples == 0 || desc->num_samples > block_size) {
    return NULL;
  }

  return desc;
}
