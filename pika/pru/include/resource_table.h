#ifndef _RSC_TABLE_PRU_H_
#define _RSC_TABLE_PRU_H_

#include <stdint.h>

/* Minimal remoteproc table; DDR ring PA is host-published via SHM. */
struct my_resource_table {
  uint32_t ver;
  uint32_t num;
  uint32_t reserved[2];
  uint32_t offset[1];
};

#endif
