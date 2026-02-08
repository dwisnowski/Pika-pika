Real PRU C code skeleton — not pseudo-marketing fluff, but something that could actually compile and evolve into your final firmware.
⸻

PRU C Skeleton – AD7606 Parallel Continuous Sampler

Target:
	•	BeagleBone Black
	•	PRU0 or PRU1
	•	Remoteproc + RPMsg (Linux side later)
	•	Parallel AD7606
	•	Cycle-count timing
	•	Configurable via shared memory

⸻

1️⃣ Memory Map Assumptions

We assume:
	•	PRU DRAM for config + control
	•	DDR (shared) for sample blocks

Typical layout (example addresses):

#define PRU_SHARED_RAM   0x00010000
#define PRU_DDR_BASE     0x80000000

Linux will mmap the DDR region and write config into shared RAM.

⸻

2️⃣ Config + Data Structures

These match what Linux will write.

#include <stdint.h>
#include <pru_cfg.h>
#include <pru_ctrl.h>
#include <pru_intc.h>

volatile register uint32_t __R30;
volatile register uint32_t __R31;

/* ================= CONFIG STRUCT ================= */

typedef struct {
    uint32_t sample_rate_hz;
    uint32_t sample_period_cycles;
    uint8_t  channel_mask;        // bitmask: bit0 = CH1
    uint8_t  num_channels;
    uint16_t reserved;
    uint32_t block_samples;
    uint32_t run;
    uint32_t error_flags;
} pru_config_t;

/* ================= SAMPLE BLOCK ================= */

#define MAX_CHANNELS 8
#define LOCAL_BUF_SAMPLES 32

typedef struct {
    uint32_t block_id;
    uint32_t sample_count;
    uint64_t t_start_cycles;
    uint16_t samples[][MAX_CHANNELS]; // variable length
} sample_block_t;


⸻

3️⃣ Hardware Pin Defines (Placeholder)

You’ll refine these later when we map BBB pins.

// Control pins
#define PIN_CONVST   (1 << 0)
#define PIN_RESET    (1 << 1)

// Status pin
#define PIN_BUSY     (1 << 8)

// Parallel data assumed on R31 bits 16–31
#define DATA_SHIFT   16
#define DATA_MASK    0xFFFF


⸻

4️⃣ Timing Helpers (Critical Section)

Cycle counter access is extremely fast and deterministic.

static inline uint32_t get_cycle_count(void) {
    return __builtin_pru_read_cycle_counter();
}

static inline void wait_until(uint32_t target) {
    while ((int32_t)(target - get_cycle_count()) > 0);
}

No sleeps. No interrupts. No Linux calls.

⸻

5️⃣ ADC Control Helpers

These are timing-critical but small.

static inline void trigger_convst(void) {
    __R30 |= PIN_CONVST;
    __delay_cycles(10);
    __R30 &= ~PIN_CONVST;
}

static inline void wait_busy_low(void) {
    uint32_t timeout = get_cycle_count() + 2000;
    while (__R31 & PIN_BUSY) {
        if ((int32_t)(timeout - get_cycle_count()) < 0) {
            // BUSY timeout
            return;
        }
    }
}


⸻

6️⃣ Parallel Channel Read

This is where parallel mode shines.

static inline uint16_t read_parallel_sample(void) {
    return (uint16_t)((__R31 >> DATA_SHIFT) & DATA_MASK);
}

Channel selection depends on your AD7606 wiring (ADDR pins).

⸻

7️⃣ Main PRU Loop (Core Logic)

This is the heart of the design.

void main(void) {

    volatile pru_config_t *cfg =
        (volatile pru_config_t *)(PRU_SHARED_RAM);

    uint16_t local_buf[LOCAL_BUF_SAMPLES][MAX_CHANNELS];
    uint32_t local_idx = 0;
    uint32_t block_id = 0;

    volatile uint16_t *ddr_ptr =
        (volatile uint16_t *)(PRU_DDR_BASE);

    // Enable cycle counter
    CT_CFG.SYSCFG_bit.STANDBY_INIT = 0;

    // Wait for Linux to set run flag
    while (!cfg->run);

    while (cfg->run) {

        uint32_t block_start = get_cycle_count();
        uint32_t samples_taken = 0;

        for (uint32_t i = 0; i < cfg->block_samples; i++) {

            uint32_t t0 = get_cycle_count();

            trigger_convst();
            wait_busy_low();

            uint8_t ch_idx = 0;
            for (uint8_t ch = 0; ch < 8; ch++) {
                if (cfg->channel_mask & (1 << ch)) {
                    // Set channel address pins here if needed
                    local_buf[local_idx][ch_idx++] =
                        read_parallel_sample();
                }
            }

            local_idx++;
            samples_taken++;

            if (local_idx == LOCAL_BUF_SAMPLES) {
                // Burst copy to DDR
                for (uint32_t s = 0; s < LOCAL_BUF_SAMPLES; s++) {
                    for (uint8_t c = 0; c < cfg->num_channels; c++) {
                        *ddr_ptr++ = local_buf[s][c];
                    }
                }
                local_idx = 0;
            }

            wait_until(t0 + cfg->sample_period_cycles);
        }

        // Flush remaining samples
        for (uint32_t s = 0; s < local_idx; s++) {
            for (uint8_t c = 0; c < cfg->num_channels; c++) {
                *ddr_ptr++ = local_buf[s][c];
            }
        }

        // TODO: write block header + notify Linux via RPMsg
        block_id++;
    }
}


⸻

8️⃣ Why This Looks “Harder” Than MCU Code — But Isn’t

Compared to Arduino:
	•	No HAL
	•	No drivers
	•	No safety net

But compared to real DAQ firmware:
	•	This is actually very readable
	•	Deterministic
	•	Explicit timing
	•	No hidden jitter

Once you’ve written one PRU loop like this, the fear disappears.

⸻

9️⃣ What We Deliberately Left Out (For Now)

On purpose:
	•	RPMsg boilerplate
	•	Channel address pin logic
	•	Trigger modes
	•	DMA tricks
	•	Oversampling
	•	Calibration

Those come after first light.
