/**
 * PRU Resource Table for Linux Remoteproc
 *
 * The Linux remoteproc framework requires a resource_table in PRU firmware
 * when loaded via sysfs (e.g. echo start > /sys/class/remoteproc/remoteproc1/state).
 * Without it, the kernel refuses to power up the PRU ("Invalid argument" when
 * writing to the state file).
 *
 * This file provides an EMPTY resource table for firmware that does NOT use:
 * - RPMsg (ARM-PRU message passing)
 * - INTC configuration via resource table
 *
 * For Linux kernel 5.4 or earlier: required for ALL PRU firmware loaded by Linux.
 * For Linux kernel 5.10 or later: only required if using RPMsg (this table is
 * harmless if present).
 *
 * The table is placed in the .resource_table section via the linker script.
 * Format follows Linux kernel include/linux/remoteproc.h:
 *   - ver: resource table format version (1)
 *   - num: number of resource entries (0 = empty)
 *   - reserved: must be zero
 */

#include <stdint.h>

/* Place resource table in the section expected by the Linux remoteproc ELF loader.
 * The linker command file must map .resource_table to a loadable memory region.
 */
#pragma DATA_SECTION(pru_remoteproc_ResourceTable, ".resource_table")

const uint32_t pru_remoteproc_ResourceTable[] = {
    1,  /* Version: format version 1 */
    0,  /* Num: number of resource entries (0 = empty table) */
    0,  /* Reserved */
    0   /* Reserved */
};
