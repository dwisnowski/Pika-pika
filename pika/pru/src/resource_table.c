#include "resource_table.h"
#include "shm_layout.h"
#include <stddef.h>
#include <stdint.h>

#pragma DATA_SECTION(pru_remoteproc_ResourceTable, ".resource_table")
#pragma RETAIN(pru_remoteproc_ResourceTable)
struct my_resource_table pru_remoteproc_ResourceTable = {
    {
        1, /* ver */
        1, /* num entries */
        {
            0,
            0,
        }, /* reserved */
    },
    {
        offsetof(struct my_resource_table, sample_ring),
    },
    {
        TYPE_CARVEOUT,
        FW_RSC_ADDR_ANY,     /* da — filled by host */
        0,                   /* pa — filled by host */
        PIKA_DDR_RING_SIZE,  /* 1 MiB sample ring */
        0,                   /* flags */
        0,                   /* reserved */
        "pika_sample_ring",
    },
};
