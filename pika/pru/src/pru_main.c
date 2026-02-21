#include "adc_parallel.h"
#include "pru_config.h"
#include "shm_layout.h"
#include <stdint.h>

/* PRU0 Local Data RAM is at 0x0000. Put SHM at 0x1000 (4KB offset) */
#define SHM_BASE_ADDRESS 0x00001000

void main(void) {
  /* 1. Disable IDLE and STANDBY (PRU_ICSS_CFG base is 0x26000) */
  /* This ensures the hardware doesn't cut the clock while we are running */
  (*(volatile uint32_t *)0x26004) = 0x00000001;

  /* PANIC PULSE: The logic analyzer MUST see this first! */
  /* Pulse PIN_CONVST (P9.27) high for 500ms */
  __R30 |= (1 << PIN_CONVST);
  __delay_cycles(100000000); // wait for 500ms
  __R30 &= ~(1 << PIN_CONVST);
  __delay_cycles(100000000); // wait for 500ms

  volatile pru_shared_memory_t *shm =
      (volatile pru_shared_memory_t *)SHM_BASE_ADDRESS;

  /* Step 1: Heartbeat */
  shm->reserved[0] = 0x12345678;

  /* Hardcoded defaults */
  uint32_t sample_period = 20000;
  uint32_t block_size = 128;
  uint32_t num_blocks = 4;
  uint32_t block_total_size = 16 + (block_size * 8 * 2);

  uint32_t current_blk = 0;
  uint32_t smp_in_blk = 0;

  /* Idle Pins */
  __R30 |= (1 << PIN_RD); // this sets the pin high
  __R30 |= (1 << PIN_CONVST); // this sets the pin high
  __R30 &= ~(1 << PIN_CS); // this sets the pin low

  /* Reset the AD7606 (Pulse RST High for at least 50ns) */
  /* Here we pulse it for about 10us to be safe */
  __R30 |= (1 << PIN_RESET); // this sets the pin high
  __delay_cycles(200000);
  __R30 &= ~(1 << PIN_RESET); // this sets the pin low
  __delay_cycles(10000000); // wait for 10ms

  while (1) {
    /* Simple software delay loop (~2 cycles per iteration overhead) */
    uint32_t delay_loops = (sample_period >> 1) / 2;
    while (delay_loops > 0) {
      delay_loops--;
    }

    if (adc_trigger_and_wait() != 0) {
      shm->error_flags = 0xDEAD0002;
      __delay_cycles(1000000);
      continue;
    }

    uint8_t *b_base = ((uint8_t *)shm) + 64 + (current_blk * block_total_size);
    block_descriptor_t *desc = (block_descriptor_t *)b_base;
    uint16_t *b_data = (uint16_t *)(b_base + 16);

    uint32_t ch_ptr = smp_in_blk * 8;
    int ch;
    for (ch = 0; ch < 8; ch++) {
      b_data[ch_ptr + ch] = adc_read_next();
    }

    smp_in_blk++;
    shm->sample_count++;
    shm->reserved[1] = shm->sample_count;

    if (smp_in_blk >= block_size) {
      desc->num_samples = smp_in_blk;
      desc->flags = 0xAA55AA55;
      current_blk = (current_blk + 1) % num_blocks;
      shm->write_block_idx = current_blk;
      smp_in_blk = 0;
    }
  }
}
