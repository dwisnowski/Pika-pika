// src/pru_main.c - Minimal PRU Hello World / Sanity Check

#include "adc_parallel.h"
#include "pru_config.h"
#include "shm_layout.h"
#include <pru_cfg.h>
#include <stdint.h>

/* Put SHM in PRU Shared RAM (0x10000) which is 12KB - enough for our blocks */
#define SHM_BASE_ADDRESS 0x00010000

void main(void) {
  /* 1. Clear SYSCFG[STANDBY_INIT] to enable OCP master port */
  CT_CFG.SYSCFG_bit.STANDBY_INIT = 0;

  /* 2. PANIC PULSE: The logic analyzer MUST see this first! */
  /* Pulse PIN_CONVST (P9.27) high for 100ms as a start indicator */
  __R30 |= PIN_CONVST;
  __delay_cycles(20000000);
  __R30 &= ~PIN_CONVST;
  __delay_cycles(20000000);

  /* 3. Initialize Shared Memory pointer */
  volatile pru_shared_memory_t *shm =
      (volatile pru_shared_memory_t *)SHM_BASE_ADDRESS;

  /* Initialize Header */
  shm->magic = SHM_MAGIC;
  shm->version = SHM_VERSION;
  shm->num_blocks = 4;
  shm->block_size = 128;
  shm->sample_period_cycles = 20000;
  shm->channel_mask = 0xFF; // All 8 channels
  shm->write_block_idx = 0;
  shm->sample_count = 0;

  /* Hardcoded defaults for local logic */
  uint32_t block_size = shm->block_size;
  uint32_t num_blocks = shm->num_blocks;
  uint32_t block_total_size = 16 + (block_size * 8 * 2);

  uint32_t current_blk = 0;
  uint32_t smp_in_blk = 0;

  /* 4. Idle Pins for AD7606 */
  __R30 |= PIN_RD;     // Set high
  __R30 |= PIN_CONVST; // Set high
  __R30 &= ~PIN_CS;    // Set low (active)

  /* 5. Reset the AD7606 (Pulse RST High for at least 50ns) */
  __R30 |= PIN_RESET;
  __delay_cycles(2000); // 10us reset pulse
  __R30 &= ~PIN_RESET;
  __delay_cycles(200000); // Wait 1ms for ADC to stabilize after reset

  /* 6. Main Acquisition Loop */
  while (1) {
    if (adc_trigger_and_wait() != 0) {
      shm->error_flags = 0xDEAD0002;
      __delay_cycles(1000000);
      continue;
    }

    uint8_t *b_base = ((uint8_t *)shm) + 64 + (current_blk * block_total_size);
    block_descriptor_t *desc = (block_descriptor_t *)b_base;
    uint16_t *b_data = (uint16_t *)(b_base + 16);

    // Track total cycles (approximate since we use fixed delay)
    static uint64_t total_cycles = 0;
    total_cycles += shm->sample_period_cycles;

    uint32_t ch_ptr = smp_in_blk * 8;
    int ch;
    for (ch = 0; ch < 8; ch++) {
      b_data[ch_ptr + ch] = adc_read_next();
    }

    smp_in_blk++;
    shm->sample_count++;

    if (smp_in_blk >= block_size) {
      desc->timestamp_cycles = total_cycles;
      desc->num_samples = smp_in_blk;
      desc->flags = 0xAA55AA55;
      current_blk = (current_blk + 1) % num_blocks;
      shm->write_block_idx = current_blk;
      smp_in_blk = 0;
    }
  }
}
