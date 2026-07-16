// src/pru_main.c - AD7606 acquisition with block timestamps + DDR ring

#include "adc_parallel.h"
#include "pru_config.h"
#include "shm_layout.h"
#include <pru_cfg.h>
#include <stdint.h>

/* Control header in PRU Shared RAM; sample blocks in host-published DDR */
#define SHM_BASE_ADDRESS 0x00010000

#define PRU_CTRL_REG (*(volatile uint32_t *)(0x22000))
#define PRU_CCNT_REG (*(volatile uint32_t *)(0x2200C))

extern void delay_cycles_runtime(uint32_t iterations);

static inline uint32_t ccnt_read(void) { return PRU_CCNT_REG; }

static inline void ccnt_accum(uint32_t *last_cycles, uint64_t *total_cycles) {
  uint32_t current = ccnt_read();
  *total_cycles += (uint32_t)(current - *last_cycles);
  *last_cycles = current;
}

void main(void) {
  CT_CFG.SYSCFG_bit.STANDBY_INIT = 0;
  PRU_CTRL_REG |= (1 << 3);

  __R30 |= PIN_CONVST;
  __delay_cycles(20000000);
  __R30 &= ~PIN_CONVST;
  __delay_cycles(20000000);

  volatile pru_shared_memory_t *shm =
      (volatile pru_shared_memory_t *)SHM_BASE_ADDRESS;

  int i;
  for (i = 0; i < 64; i++) {
    ((volatile uint32_t *)shm)[i] = 0;
  }

  shm->version = SHM_VERSION;
  shm->num_blocks = PIKA_DEFAULT_NUM_BLOCKS;
  shm->block_size = PIKA_DEFAULT_BLOCK_SIZE;
  shm->sample_period_cycles = 0;
  shm->write_block_idx = 0;
  shm->sample_count = 0;
  shm->pru_clock_hz = PRU_CLOCK_HZ;
  shm->sample_rate = 0;
  shm->ddr_phys_addr = 0; /* host must publish */
  shm->ddr_size_bytes = PIKA_DDR_RING_SIZE;
  shm->block_desc_size = BLOCK_DESCRIPTOR_SIZE;
  shm->error_flags = 0xDEAD00DDu; /* waiting for host DDR PA */
  shm->ch_enable[0] = 1;
  for (i = 1; i < 8; i++)
    shm->ch_enable[i] = 0;

  shm->magic = SHM_MAGIC;

  /* Host verifies R/W then writes ddr_phys_addr (typically 0x9C000000 + mem=448M) */
  while (shm->ddr_phys_addr == 0) {
    shm->heartbeat++;
    __delay_cycles(20000000);
  }

  uint32_t ddr_phys = shm->ddr_phys_addr;
  uint32_t ddr_size = shm->ddr_size_bytes;
  if (ddr_size == 0)
    ddr_size = PIKA_DDR_RING_SIZE;

  shm->error_flags = 0;

  uint32_t block_size = shm->block_size;
  uint32_t num_blocks = shm->num_blocks;
  uint32_t block_total_size = BLOCK_TOTAL_SIZE(block_size);
  volatile uint8_t *ddr_base = (volatile uint8_t *)(uint32_t)ddr_phys;

  if ((uint32_t)num_blocks * block_total_size > ddr_size) {
    num_blocks = ddr_size / block_total_size;
    if (num_blocks == 0)
      num_blocks = 1;
    shm->num_blocks = num_blocks;
  }

  /* Probe: confirm PRU can store to the published PA before sampling */
  {
    volatile uint32_t *probe = (volatile uint32_t *)ddr_base;
    probe[0] = 0xA5A55A5Au;
  }

  {
    volatile uint32_t *p = (volatile uint32_t *)ddr_base;
    for (i = 0; i < (int)(block_total_size / 4); i++)
      p[i] = 0;
  }

  uint32_t current_blk = 0;
  uint32_t smp_in_blk = 0;
  uint64_t block_start_cycles = 0;

  __R30 |= PIN_RD;
  __R30 |= PIN_CONVST;
  __R30 &= ~PIN_CS;

  __R30 |= PIN_RESET;
  __delay_cycles(2000);
  __R30 &= ~PIN_RESET;
  __delay_cycles(200000);

  uint32_t last_cycles = ccnt_read();
  uint64_t total_cycles = 0;

  while (1) {
    uint32_t period_target = shm->sample_period_cycles;

    if (smp_in_blk % 10 == 0) {
      shm->heartbeat++;
    }

    uint32_t sample_start_ccnt = ccnt_read();

    if (adc_trigger_and_wait() != 0) {
      shm->error_flags = 0xDEAD0002;
      shm->heartbeat++;
      __delay_cycles(1000000);
      continue;
    }

    ccnt_accum(&last_cycles, &total_cycles);

    volatile uint8_t *b_base = ddr_base + (current_blk * block_total_size);
    volatile block_descriptor_t *desc = (volatile block_descriptor_t *)b_base;
    volatile uint16_t *b_data =
        (volatile uint16_t *)(b_base + BLOCK_DESCRIPTOR_SIZE);

    if (smp_in_blk == 0) {
      desc->timestamp_cycles = total_cycles;
      desc->flags = 0;
      desc->num_samples = 0;
      desc->period_cycles = 0;
      block_start_cycles = total_cycles;
    }

    uint32_t ch_ptr = smp_in_blk * 8;

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

    if (period_target > 0) {
      uint32_t elapsed = ccnt_read() - sample_start_ccnt;
      if (elapsed < period_target) {
        uint32_t remaining = period_target - elapsed;
        delay_cycles_runtime(remaining >> 1);
      }
      ccnt_accum(&last_cycles, &total_cycles);
    }

    smp_in_blk++;

    if (smp_in_blk >= block_size) {
      if (block_size > 1) {
        desc->period_cycles =
            (uint32_t)((total_cycles - block_start_cycles) / (block_size - 1));
      } else {
        desc->period_cycles = period_target;
      }
      desc->num_samples = smp_in_blk;
      /* flags last — host must not see a partial descriptor as complete */
      desc->flags = BLOCK_FLAG_COMPLETE;
      current_blk = (current_blk + 1) % num_blocks;
      shm->write_block_idx = current_blk;
      smp_in_blk = 0;
      /* bump sample_count only after the block is visible as complete */
      shm->sample_count += block_size;
    }
  }
}
