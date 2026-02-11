ENTRY(main);

MEMORY
{
    IRAM : origin = 0x00000, length = 0x8000
    DRAM : origin = 0x8000, length = 0x8000
}

SECTIONS
{
    .text : > IRAM
    .data : > DRAM
    .bss  : > DRAM
}
