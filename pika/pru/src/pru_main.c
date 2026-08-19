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

/*
 * DDR is outside the PRU near address space. Build with --mem_model:data=far
 * so absolute pointers (0x8xxxxxxx+) use full 32-bit addressing.
 *
 * clpru's far/__far qualifies DATA SYMBOLS, not MS-DOS-style far pointers.
 * Do not write `typedef T * far` or `volatile far T *` on locals — those are
 * error #41 / #81 with this toolchain.
 */
extern void delay_cycles_runtime(uint32_t iterations);

static inline uint32_t ccnt_read(void) { return PRU_CCNT_REG; }

static inline void ccnt_accum(uint32_t *last_cycles, uint64_t *total_cycles) {
  uint32_t current = ccnt_read();
  *total_cycles += (uint32_t)(current - *last_cycles);
  *last_cycles = current;
}

void main(void) {
  /* Enable OCP master port — required before any DDR access */
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
  shm->error_flags = 0xDEAD00DDu;
  shm->ch_enable[0] = 1;
  for (i = 1; i < 8; i++)
    shm->ch_enable[i] = 0;

  shm->magic = SHM_MAGIC;

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
  volatile uint8_t *ddr_base = (volatile uint8_t *)ddr_phys;

  if ((uint32_t)num_blocks * block_total_size > ddr_size) {
    num_blocks = ddr_size / block_total_size;
    if (num_blocks == 0)
      num_blocks = 1;
    shm->num_blocks = num_blocks;
  }

  /* Probe DDR; hang here means addressing/OCP is still wrong */
  {
    volatile uint32_t *probe = (volatile uint32_t *)ddr_phys;
    probe[0] = 0xA5A55A5Au;
    shm->heartbeat++;
  }

  {
    volatile uint32_t *p = (volatile uint32_t *)ddr_phys;
    for (i = 0; i < (int)(block_total_size / 4); i++)
      p[i] = 0;
  }
  shm->heartbeat++;

  uint32_t current_blk = 0;
  uint32_t smp_in_blk = 0;
  uint64_t block_start_cycles = 0;
  uint64_t block_end_cycles = 0;

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

    /* Stamp end-of-block period before trailing pace delay on last sample. */
    if (smp_in_blk == block_size - 1)
      block_end_cycles = total_cycles;

    volatile uint8_t *b_base = ddr_base + (current_blk * block_total_size);
    volatile uint32_t *desc_words = (volatile uint32_t *)(uint32_t)b_base;
    volatile uint16_t *b_data =
        (volatile uint16_t *)(uint32_t)(b_base + BLOCK_DESCRIPTOR_SIZE);

    /*
     * Descriptor layout (little-endian, packed 24 B):
     *   [0..1] timestamp_cycles u64
     *   [2]    num_samples
     *   [3]    flags
     *   [4]    period_cycles
     *   [5]    reserved
     */
    if (smp_in_blk == 0) {
      desc_words[0] = (uint32_t)(total_cycles & 0xFFFFFFFFu);
      desc_words[1] = (uint32_t)(total_cycles >> 32);
      desc_words[2] = 0;
      desc_words[3] = 0;
      desc_words[4] = 0;
      desc_words[5] = 0;
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
      uint32_t period = period_target;
      if (block_size > 1) {
        uint64_t end_cycles =
            (block_end_cycles > block_start_cycles) ? block_end_cycles
                                                    : total_cycles;
        period = (uint32_t)((end_cycles - block_start_cycles) / (block_size - 1));
      }
      desc_words[4] = period;
      desc_words[2] = smp_in_blk;
      desc_words[3] = BLOCK_FLAG_COMPLETE;
      current_blk = (current_blk + 1) % num_blocks;
      shm->write_block_idx = current_blk;
      smp_in_blk = 0;
      shm->sample_count += block_size;
    }
  }
}
