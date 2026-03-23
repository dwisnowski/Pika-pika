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

  /* 2. Enable Cycle Counter (CCNT) for accurate hardware timecoding */
  // CCNT is more universally reliable than IEP on some kernels
  // CTRL register is at 0x22000 locally. Bit 3 is CTR_EN.
  *(volatile uint32_t *)(0x22000) |= (1 << 3);

  /* 2. PANIC PULSE: The logic analyzer MUST see this first! */
  /* Pulse PIN_CONVST (P9.27) high for 100ms as a start indicator */
  __R30 |= PIN_CONVST;
  __delay_cycles(20000000);
  __R30 &= ~PIN_CONVST;
  __delay_cycles(20000000);

  /* 3. Initialize Shared Memory pointer and WIPE it */
  volatile pru_shared_memory_t *shm =
      (volatile pru_shared_memory_t *)SHM_BASE_ADDRESS;

  /* Force a hardware zero-out of the header space to clear stale heartbeats */
  int i;
  for (i = 0; i < 64; i++) {
    ((volatile uint32_t *)shm)[i] = 0;
  }

  /* Initialize Header */
  shm->magic = SHM_MAGIC;
  shm->version = SHM_VERSION;
  shm->num_blocks = 4;
  shm->block_size = 128;
  shm->sample_period_cycles = 20000;
  shm->write_block_idx = 0;
  shm->sample_count = 0;
  shm->pru_clock_hz = 200000000; /* 200 MHz on BeagleBone Black */
  shm->sample_rate = 0; /* Will be set by datalogger (default: 10000 Hz) */

  /* Default: CH0 only enabled */
  shm->ch_enable[0] = 1;
  shm->ch_enable[1] = 0;
  shm->ch_enable[2] = 0;
  shm->ch_enable[3] = 0;
  shm->ch_enable[4] = 0;
  shm->ch_enable[5] = 0;
  shm->ch_enable[6] = 0;
  shm->ch_enable[7] = 0;

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
  uint32_t last_cycles = 0;
  uint64_t total_cycles = 0;

  while (1) {
    if (smp_in_blk % 10 == 0) {
      shm->heartbeat++;
    }

    if (adc_trigger_and_wait() != 0) {
      shm->error_flags = 0xDEAD0002;
      shm->heartbeat++; // Incremement even on error so we see the loop is alive
      __delay_cycles(1000000); // Wait 5ms before retrying
      continue;
    }

    uint8_t *b_base =
        ((uint8_t *)shm) + SHM_HEADER_OFFSET + (current_blk * block_total_size);
    block_descriptor_t *desc = (block_descriptor_t *)b_base;
    uint16_t *b_data = (uint16_t *)(b_base + 16);

    // Track total cycles using hardware CCNT (Cycle Counter)
    // Register is at byte-offset 0x0C in the PRU CTRL space (0x22000)
    uint32_t current_cycles = *(volatile uint32_t *)(0x2200C);
    total_cycles += (uint32_t)(current_cycles - last_cycles);
    last_cycles = current_cycles;

    uint32_t ch_ptr = smp_in_blk * 8;

    /* Conditionally read each channel based on enable flags */
    if (shm->ch_enable[0])
      b_data[ch_ptr + 0] = adc_read_next();
    else
      b_data[ch_ptr + 0] = 0;
    if (shm->ch_enable[1])
      b_data[ch_ptr + 1] = adc_read_next();
    else
      b_data[ch_ptr + 1] = 0;
    if (shm->ch_enable[2])
      b_data[ch_ptr + 2] = adc_read_next();
    else
      b_data[ch_ptr + 2] = 0;
    if (shm->ch_enable[3])
      b_data[ch_ptr + 3] = adc_read_next();
    else
      b_data[ch_ptr + 3] = 0;
    if (shm->ch_enable[4])
      b_data[ch_ptr + 4] = adc_read_next();
    else
      b_data[ch_ptr + 4] = 0;
    if (shm->ch_enable[5])
      b_data[ch_ptr + 5] = adc_read_next();
    else
      b_data[ch_ptr + 5] = 0;
    if (shm->ch_enable[6])
      b_data[ch_ptr + 6] = adc_read_next();
    else
      b_data[ch_ptr + 6] = 0;
    if (shm->ch_enable[7])
      b_data[ch_ptr + 7] = adc_read_next();
    else
      b_data[ch_ptr + 7] = 0;

    if (smp_in_blk == 0) {
      desc->timestamp_cycles = total_cycles;
    }

    smp_in_blk++;
    shm->sample_count++;

    if (smp_in_blk >= block_size) {
      desc->num_samples = smp_in_blk;
      desc->flags = 0xAA55AA55;
      current_blk = (current_blk + 1) % num_blocks;
      shm->write_block_idx = current_blk;
      smp_in_blk = 0;
    }
  }
}
