-stack 0x100
-heap 0x100

MEMORY {
      PAGE 0:
        PRU_IMEM     : org = 0x00000000 len = 0x00002000

      PAGE 1:
        PRU_DMEM_0_1 : org = 0x00000000 len = 0x00002000 CREGISTER=24
        PRU_SHAREDMEM: org = 0x00010000 len = 0x00003000 CREGISTER=28
        PRU_CFG      : org = 0x00026000 len = 0x00000044 CREGISTER=4
}

SECTIONS {
        .resource_table : {
            *(.resource_table)
        } > PRU_DMEM_0_1, PAGE 1
        
        .text       >  PRU_IMEM, PAGE 0
        .stack      >  PRU_DMEM_0_1, PAGE 1
        .bss        >  PRU_DMEM_0_1, PAGE 1
        .cio        >  PRU_DMEM_0_1, PAGE 1
        .const      >  PRU_DMEM_0_1, PAGE 1
        .data       >  PRU_DMEM_0_1, PAGE 1
        .switch     >  PRU_DMEM_0_1, PAGE 1
        .sysmem     >  PRU_DMEM_0_1, PAGE 1
        .cinit      >  PRU_DMEM_0_1, PAGE 1
        .rodata     >  PRU_DMEM_0_1, PAGE 1
        .farbss     >  PRU_DMEM_0_1, PAGE 1
        .fardata    >  PRU_DMEM_0_1, PAGE 1
}
