#ifndef _RSC_TABLE_PRU_H_
#define _RSC_TABLE_PRU_H_
#include <stddef.h>
#include <stdint.h>
#include <rsc_types.h>

struct my_resource_table {
    struct resource_table base;
    uint32_t offset;
};
#endif
