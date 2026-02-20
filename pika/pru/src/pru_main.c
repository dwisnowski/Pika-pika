#include "adc_parallel.h"
#include "pru_config.h"
#include "shm_layout.h"
#include <stdint.h>

#define SHM_BASE_ADDRESS 0x00010000
extern const uint32_t pru_remoteproc_ResourceTable[];
extern void delay_cycles_runtime(uint32_t iterations);

void main(void) {
  (void)pru_remoteproc_ResourceTable;
  (*(volatile uint32_t *)0x26004) &= ~(1 << 4); // Enable OCP master

  volatile pru_shared_memory_t *shm =
      (volatile pru_shared_memory_t *)SHM_BASE_ADDRESS;

  // Wait for ARM to initialize
  while (shm->magic != SHM_MAGIC)
    ;

  uint32_t sample_period = shm->sample_period_cycles;
  uint32_t channel_mask = shm->channel_mask;
  uint32_t block_size = shm->block_size;
  uint32_t num_blocks = shm->num_blocks;

  uint32_t block_data_size = block_size * 8 * 2;
  uint32_t block_total_size = 16 + block_data_size;

  uint32_t current_blk = 0;
  uint32_t smp_in_blk = 0;

  // Setup ADC
  adc_deassert_cs();
  PRU0_R30 |= (1 << PIN_RD);
  __delay_cycles(2000); // 10us
  adc_assert_cs();

  while (1) {
    if (sample_period > 100)
      delay_cycles_runtime(sample_period >> 1);

    int err = adc_trigger_and_wait();
    if (err != 0) {
      shm->error_flags = (err == -1) ? (1 << 1) : (1 << 2);
      __halt();
    }

    uint8_t *b_base = ((uint8_t *)shm) + 64 + (current_blk * block_total_size);
    block_descriptor_t *desc = (block_descriptor_t *)b_base;
    uint16_t *b_data = (uint16_t *)(b_base + 16);

    // Read Channels
    uint32_t ch_ptr = smp_in_blk * 8;
    int ch;
    for (ch = 0; ch < 8; ch++) {
      b_data[ch_ptr + ch] = adc_read_next();
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
