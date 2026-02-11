/* AM335x_PRU.cmd */

MEMORY
{
    PRU0_IRAM (RWX) : origin = 0x00000000, length = 0x2000
    PRU0_DRAM (RWX) : origin = 0x00002000, length = 0x1000
}

SECTIONS
{
    .text : > PRU0_IRAM
    .data : > PRU0_DRAM
    .bss  : > PRU0_DRAM
}
