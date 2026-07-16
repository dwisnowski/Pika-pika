#ifndef _RSC_TABLE_PRU_H_
#define _RSC_TABLE_PRU_H_

#include <stddef.h>
#include <stdint.h>
#include <rsc_types.h>

#include "shm_layout.h"

/* Older PRU SSP headers omit these; match Linux remoteproc / TI conventions. */
#ifndef FW_RSC_ADDR_ANY
#define FW_RSC_ADDR_ANY ((uint32_t)0xFFFFFFFFU)
#endif
#ifndef TYPE_CARVEOUT
#ifdef RSC_CARVEOUT
#define TYPE_CARVEOUT RSC_CARVEOUT
#else
#define TYPE_CARVEOUT 0
#endif
#endif

/**
 * Resource table with a DDR carveout for the sample ring.
 * remoteproc allocates contiguous memory and fills da/pa before the PRU starts.
 */
struct my_resource_table {
  struct resource_table base;
  uint32_t offset[1];
  struct fw_rsc_carveout sample_ring;
};

#endif
