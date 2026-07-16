#define _GNU_SOURCE
#include "shm_reader.h"
#include <fcntl.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

static char discovered_remoteproc_path[256] = "";

static const char *discover_pru0_info(uint32_t *out_shm_phys) {
  if (discovered_remoteproc_path[0] != '\0') {
    return discovered_remoteproc_path;
  }

  uint32_t shm_phys = PRU_SHM_PHYS_BASE;

  for (int i = 0; i < 5; i++) {
    char name_path[256];
    char name_buf[256];
    snprintf(name_path, sizeof(name_path),
             "/sys/class/remoteproc/remoteproc%d/name", i);
    FILE *f = fopen(name_path, "r");
    if (f) {
      if (fgets(name_buf, sizeof(name_buf), f)) {
        if (strstr(name_buf, "4a334000") || strstr(name_buf, "pru0")) {
          unsigned int ctrl_addr = 0;
          if (sscanf(name_buf, "%x", &ctrl_addr) == 1) {
            uint32_t pruss_base = 0;
            if ((ctrl_addr & 0xFFFFF000) == 0x4a334000)
              pruss_base = ctrl_addr - 0x34000;
            else if ((ctrl_addr & 0xFFFFF000) == 0x4a322000)
              pruss_base = ctrl_addr - 0x22000;
            else
              pruss_base = ctrl_addr & 0xFFF80000;

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
  memset(reader, 0, sizeof(*reader));
  reader->mem_fd = -1;
  reader->ddr_mmap_base = MAP_FAILED;
  reader->mmap_base = MAP_FAILED;

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
    perror("mmap Shared RAM");
    close(reader->mem_fd);
    reader->mem_fd = -1;
    return -1;
  }

  reader->header = (volatile pru_shared_memory_t *)reader->mmap_base;

  printf("[SHM Reader] Mapped Shared RAM @ phys 0x%08X\n",
         reader->pru_shm_phys_addr);

  if (reader->header->magic != SHM_MAGIC) {
    printf("[SHM Reader] Header uninitialized (magic=0x%08X), preparing clean "
           "state...\n",
           (uint32_t)reader->header->magic);
    reader->header->magic = 0;
    reader->header->num_blocks = 0;
    reader->header->write_block_idx = 0;
  }

  reader->last_read_block_idx = UINT32_MAX;
  reader->last_completed_blocks = UINT32_MAX;

  return 0;
}

int shm_reader_map_ddr(shm_reader_t *reader) {
  if (!reader->header)
    return -1;

  uint32_t phys = reader->header->ddr_phys_addr;
  uint32_t size = reader->header->ddr_size_bytes;
  if (phys == 0 || size == 0) {
    fprintf(stderr,
            "[SHM Reader] DDR ring not published yet (phys=0x%08X size=%u)\n",
            phys, size);
    return -1;
  }

  if (reader->ddr_mmap_base != MAP_FAILED && reader->ddr_mmap_base != NULL &&
      reader->ddr_phys_addr == phys && reader->ddr_size_bytes == size) {
    return 0; /* already mapped */
  }

  if (reader->ddr_mmap_base != MAP_FAILED && reader->ddr_mmap_base != NULL) {
    munmap(reader->ddr_mmap_base, reader->ddr_size_bytes);
    reader->ddr_mmap_base = MAP_FAILED;
  }

  reader->ddr_phys_addr = phys;
  reader->ddr_size_bytes = size;
  reader->ddr_mmap_base =
      mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, reader->mem_fd, phys);
  if (reader->ddr_mmap_base == MAP_FAILED) {
    perror("mmap DDR sample ring");
    return -1;
  }

  printf("[SHM Reader] Mapped DDR sample ring @ phys 0x%08X (%u bytes)\n",
         phys, size);
  return 0;
}

static int cmdline_has_mem_448m(void) {
  FILE *f = fopen("/proc/cmdline", "r");
  if (!f)
    return 0;
  char buf[512];
  size_t n = fread(buf, 1, sizeof(buf) - 1, f);
  fclose(f);
  if (n == 0)
    return 0;
  buf[n] = '\0';
  return strstr(buf, "mem=448M") != NULL || strstr(buf, "mem=448m") != NULL;
}

int shm_reader_publish_carveout_pa(shm_reader_t *reader) {
  if (!reader || reader->mem_fd < 0 || !reader->header)
    return -1;

  /*
   * Host owns the DDR PA. Always use the mem=448M reserved region so PRU and
   * ARM never disagree (do not trust carveout addresses from the PRU).
   */
  if (reader->header->ddr_phys_addr == PIKA_DDR_RING_PHYS &&
      reader->header->error_flags != 0xDEAD00DD) {
    return 0;
  }

  if (!cmdline_has_mem_448m()) {
    fprintf(stderr,
            "[SHM Reader] mem=448M not in /proc/cmdline — required for DDR "
            "ring at 0x%08X\n",
            PIKA_DDR_RING_PHYS);
    return -1;
  }

  uint32_t phys = PIKA_DDR_RING_PHYS;
  uint32_t len = PIKA_DDR_RING_SIZE;

  if (reader->header->ddr_phys_addr != 0 &&
      reader->header->ddr_phys_addr != phys) {
    printf("[SHM Reader] Replacing PRU DDR PA 0x%08X with host PA 0x%08X\n",
           (uint32_t)reader->header->ddr_phys_addr, phys);
  }

  void *p =
      mmap(NULL, len, PROT_READ | PROT_WRITE, MAP_SHARED, reader->mem_fd, phys);
  if (p == MAP_FAILED) {
    perror("mmap DDR ring for verify");
    return -1;
  }
  volatile uint32_t *w = (volatile uint32_t *)p;
  const uint32_t probe = 0xA5A55A5Au;
  w[0] = probe;
  uint32_t got = w[0];
  w[0] = 0;
  munmap(p, len);
  if (got != probe) {
    fprintf(stderr,
            "[SHM Reader] DDR ring @ 0x%08X did not retain probe write "
            "(got 0x%08X)\n",
            phys, got);
    return -1;
  }

  reader->header->ddr_phys_addr = phys;
  reader->header->ddr_size_bytes = len;
  if (reader->header->error_flags == 0xDEAD00DD)
    reader->header->error_flags = 0;

  /* Force remap on next map_ddr if we had mapped a different PA */
  if (reader->ddr_mmap_base != MAP_FAILED && reader->ddr_mmap_base != NULL &&
      reader->ddr_phys_addr != phys) {
    munmap(reader->ddr_mmap_base, reader->ddr_size_bytes);
    reader->ddr_mmap_base = MAP_FAILED;
  }

  printf("[SHM Reader] Published DDR PA 0x%08X (%u bytes) [mem=448M]\n", phys,
         len);
  return 0;
}

void shm_reader_cleanup(shm_reader_t *reader) {
  if (reader->ddr_mmap_base && reader->ddr_mmap_base != MAP_FAILED) {
    munmap(reader->ddr_mmap_base, reader->ddr_size_bytes);
    reader->ddr_mmap_base = NULL;
  }
  if (reader->mmap_base && reader->mmap_base != MAP_FAILED) {
    munmap(reader->mmap_base, PRU_SHM_SIZE);
    reader->mmap_base = NULL;
  }
  if (reader->mem_fd >= 0) {
    close(reader->mem_fd);
    reader->mem_fd = -1;
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
  static uint32_t unstable_idx_count = 0;
  static uint32_t invalid_idx_count = 0;
  static uint32_t rejected_desc_count = 0;
  poll_count++;

  if (reader->header->magic != SHM_MAGIC) {
    if (poll_count % 1000 == 0) {
      printf("[SHM Reader] Waiting for magic (found 0x%08X)... heartbeat=%u\n",
             (uint32_t)reader->header->magic,
             (uint32_t)reader->header->heartbeat);
    }
    return NULL;
  }

  if (reader->header->error_flags == 0xDEAD00DD ||
      reader->header->ddr_phys_addr == 0 ||
      reader->header->ddr_phys_addr != PIKA_DDR_RING_PHYS) {
    /* Publish at most once per ~100ms of polls to avoid log spam */
    if (poll_count == 1 || (poll_count % 1000) == 0 ||
        reader->header->ddr_phys_addr != PIKA_DDR_RING_PHYS) {
      if (shm_reader_publish_carveout_pa(reader) != 0) {
        if (poll_count % 1000 == 0) {
          printf("[SHM Reader] Waiting to publish DDR PA (err=0x%08X "
                 "ddr=0x%08X)\n",
                 (uint32_t)reader->header->error_flags,
                 (uint32_t)reader->header->ddr_phys_addr);
        }
        return NULL;
      }
    }
  }

  /* Remap if header PA differs from current mapping */
  if (reader->ddr_mmap_base != NULL &&
      reader->ddr_mmap_base != MAP_FAILED &&
      reader->ddr_phys_addr != reader->header->ddr_phys_addr) {
    munmap(reader->ddr_mmap_base, reader->ddr_size_bytes);
    reader->ddr_mmap_base = MAP_FAILED;
  }

  if (reader->ddr_mmap_base == NULL || reader->ddr_mmap_base == MAP_FAILED) {
    if (shm_reader_map_ddr(reader) != 0) {
      if (poll_count % 1000 == 0) {
        printf("[SHM Reader] Waiting to map DDR ring...\n");
      }
      return NULL;
    }
  }

  uint32_t num_blocks = reader->header->num_blocks;
  if (num_blocks == 0 || num_blocks > 1024) {
    if (poll_count % 5000 == 0) {
      printf("[SHM Reader] Waiting for valid num_blocks (got %u)\n",
             num_blocks);
    }
    return NULL;
  }

  uint32_t block_size = reader->header->block_size;
  if (block_size == 0 || block_size > 1024) {
    if (poll_count % 5000 == 0) {
      printf("[SHM Reader] Waiting for valid block_size (got %u)\n",
             block_size);
    }
    return NULL;
  }

  uint32_t current_blk_a = reader->header->write_block_idx;
  uint32_t current_blk_b = reader->header->write_block_idx;
  if (current_blk_a != current_blk_b) {
    unstable_idx_count++;
    if (unstable_idx_count % 1000 == 0) {
      printf("[SHM Reader] Unstable write_idx read: a=%u b=%u (count=%u)\n",
             current_blk_a, current_blk_b, unstable_idx_count);
    }
  }

  uint32_t raw_write_idx = current_blk_b;
  if (raw_write_idx >= num_blocks) {
    invalid_idx_count++;
    if (invalid_idx_count % 1000 == 0) {
      printf("[SHM Reader] Invalid raw write_idx=%u (num_blocks=%u, count=%u)\n",
             raw_write_idx, num_blocks, invalid_idx_count);
    }
  }

  uint32_t sample_count_a = reader->header->sample_count;
  uint32_t sample_count_b = reader->header->sample_count;
  uint32_t sample_count = sample_count_b;
  if (sample_count_a != sample_count_b && poll_count % 5000 == 0) {
    printf("[SHM Reader] sample_count moved during read: a=%u b=%u\n",
           sample_count_a, sample_count_b);
  }
  uint32_t completed_blocks = sample_count / block_size;
  uint32_t derived_write_idx = completed_blocks % num_blocks;

  if (poll_count % 5000 == 0) {
    printf("[SHM Reader] Tick: write_idx(raw=%u, derived=%u), "
           "last_idx=%u, num_blocks=%u, block_size=%u, sample_count=%u, "
           "completed_blocks=%u, heartbeat=%u, err=0x%08X, ddr=0x%08X\n",
           raw_write_idx, derived_write_idx, reader->last_read_block_idx,
           num_blocks, block_size, sample_count, completed_blocks,
           (uint32_t)reader->header->heartbeat,
           (uint32_t)reader->header->error_flags, reader->ddr_phys_addr);
  }

  if (reader->last_completed_blocks == UINT32_MAX) {
    reader->last_completed_blocks = completed_blocks;
    reader->last_read_block_idx =
        (completed_blocks == 0) ? UINT32_MAX
                                : ((completed_blocks - 1) % num_blocks);
    return NULL;
  }

  if (completed_blocks == reader->last_completed_blocks) {
    return NULL;
  }

  if (completed_blocks < reader->last_completed_blocks) {
    reader->last_completed_blocks = completed_blocks;
    reader->last_read_block_idx =
        (completed_blocks == 0) ? UINT32_MAX
                                : ((completed_blocks - 1) % num_blocks);
    return NULL;
  }

  uint32_t next_completed_blocks = reader->last_completed_blocks + 1;
  if (completed_blocks < next_completed_blocks) {
    return NULL;
  }

  uint32_t pending = completed_blocks - reader->last_completed_blocks;
  if (pending > num_blocks) {
    printf("[SHM Reader] Overrun: pending=%u blocks (ring=%u) — skipping to "
           "latest\n",
           pending, num_blocks);
    reader->last_completed_blocks = completed_blocks - num_blocks;
    next_completed_blocks = reader->last_completed_blocks + 1;
  }

  uint32_t ready_idx = (next_completed_blocks - 1) % num_blocks;

  uint32_t desc_size = reader->header->block_desc_size;
  if (desc_size == 0 || desc_size > 64)
    desc_size = BLOCK_DESCRIPTOR_SIZE;

  uint32_t block_total_size = desc_size + BLOCK_PAYLOAD_BYTES(block_size);

  uint8_t *b_base =
      ((uint8_t *)reader->ddr_mmap_base) + (ready_idx * block_total_size);

  if (data_ptr) {
    *data_ptr = b_base + desc_size;
  }

  volatile block_descriptor_t *desc = (volatile block_descriptor_t *)b_base;

  if (poll_count % 5000 == 0) {
    printf("[SHM Reader] Candidate desc: ready_idx=%u flags=0x%08X "
           "num_samples=%u timestamp_cycles=%llu period_cycles=%u\n",
           ready_idx, (uint32_t)desc->flags, (uint32_t)desc->num_samples,
           (unsigned long long)desc->timestamp_cycles,
           (uint32_t)desc->period_cycles);
  }

  if (desc->flags != BLOCK_FLAG_COMPLETE) {
    rejected_desc_count++;
    if (rejected_desc_count % 1000 == 0) {
      printf("[SHM Reader] Reject desc: ready_idx=%u bad flags=0x%08X "
             "num_samples=%u (count=%u)\n",
             ready_idx, (uint32_t)desc->flags, (uint32_t)desc->num_samples,
             rejected_desc_count);
    }
    return NULL;
  }
  if (desc->num_samples == 0 || desc->num_samples > block_size) {
    rejected_desc_count++;
    if (rejected_desc_count % 1000 == 0) {
      printf("[SHM Reader] Reject desc: ready_idx=%u invalid num_samples=%u "
             "flags=0x%08X (count=%u)\n",
             ready_idx, (uint32_t)desc->num_samples, (uint32_t)desc->flags,
             rejected_desc_count);
    }
    return NULL;
  }

  reader->last_completed_blocks = next_completed_blocks;
  reader->last_read_block_idx = ready_idx;

  return desc;
}
