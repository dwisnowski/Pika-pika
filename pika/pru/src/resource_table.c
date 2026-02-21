#include <stdint.h>

/* Minimalist Resource Table */
struct resource_table {
  uint32_t ver;
  uint32_t num;
  uint32_t reserved[2];
  uint32_t offset[1];
};

#pragma DATA_SECTION(pru_remoteproc_ResourceTable, ".resource_table")
#pragma RETAIN(pru_remoteproc_ResourceTable)
const struct resource_table pru_remoteproc_ResourceTable = {1, 0, {0, 0}, {0}};
