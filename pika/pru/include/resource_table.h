#ifndef _RSC_TABLE_PRU_H_
#define _RSC_TABLE_PRU_H_

#include <stddef.h>
#include <stdint.h>

#include "shm_layout.h"

/*
 * Explicit Linux remoteproc resource-table layout (do not rely on SSP
 * rsc_types.h field packing — versions differ and break carveout PA patching).
 *
 * Matching include/linux/remoteproc.h:
 *   struct resource_table { ver, num, reserved[2]; offsets follow }
 *   struct fw_rsc_carveout { type, da, pa, len, flags, reserved, name[32] }
 */
#define RPROC_RSC_CARVEOUT 0
#define RPROC_FW_RSC_ADDR_ANY ((uint32_t)0xFFFFFFFFu)

struct rproc_resource_table {
  uint32_t ver;
  uint32_t num;
  uint32_t reserved[2];
};

struct rproc_fw_rsc_carveout {
  uint32_t type;
  uint32_t da;
  uint32_t pa;
  uint32_t len;
  uint32_t flags;
  uint32_t reserved;
  char name[32];
};

/**
 * Resource table with a DDR carveout for the sample ring.
 * remoteproc allocates contiguous memory and fills da/pa before the PRU starts.
 */
struct my_resource_table {
  struct rproc_resource_table base;
  uint32_t offset[1];
  struct rproc_fw_rsc_carveout sample_ring;
};

#endif
