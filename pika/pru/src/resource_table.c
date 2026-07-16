#include "resource_table.h"
#include "shm_layout.h"
#include <stddef.h>

#pragma DATA_SECTION(pru_remoteproc_ResourceTable, ".resource_table")
#pragma RETAIN(pru_remoteproc_ResourceTable)
struct my_resource_table pru_remoteproc_ResourceTable = {
    {
        1, /* ver */
        1, /* num entries */
        {0, 0},
    },
    {
        offsetof(struct my_resource_table, sample_ring),
    },
    {
        RPROC_RSC_CARVEOUT,
        RPROC_FW_RSC_ADDR_ANY, /* da — filled by host */
        0,                     /* pa — filled by host */
        PIKA_DDR_RING_SIZE,
        0,
        0,
        "pika_sample_ring",
    },
};
