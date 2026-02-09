1. Fixed Hardware Capabilities (Non-Negotiable)

These are compile-time truths:
	•	PRU clock: 200 MHz
	•	Timing granularity: 5 ns per cycle
	•	AD7606 resolution: 16 bits
	•	Parallel mode: 16 data lines
	•	Continuous sampling
	•	Deterministic loop (no branching timing changes)

✔ Full 16-bit precision is absolutely supported on BBB PRU
✔ Parallel mode is the right choice

⸻

2. Configurable Parameters (Runtime)

These are written by Linux into shared memory before start.
The sample rate (0-180,000 sps) and number of channels (1-8) sampled need to be configurable.

Parameter	Type	Notes
sample_rate_hz	uint32	Default 180000
channels_enabled	bitmask	0b00000001 → CH1
num_channels	uint8	Derived from mask
block_samples	uint32	e.g. 1024
run	bool	Start/stop
error_flags	bitmask	PRU writes

Linux controls configuration
PRU never recalculates timing mid-block

⸻

3. Timing Math (Cycle Count)

Sample period

180 kSPS → 5.555... µs per sample

PRU cycles:

5.555 µs × 200 MHz = 1111 cycles

⚠ We must round down, not up:

SAMPLE_PERIOD_CYCLES = 1111
Actual rate ≈ 180,018 SPS (0.01% error)

Totally acceptable for oscilloscope use.

⸻

4. Timing Budget Breakdown (Per Sample)

Operation	Cycles (est)
CONVST pulse	~20
BUSY wait	~200–600 (ADC dependent)
Read 1 channel	~20
Loop overhead	~50
Safety margin	~100

Even at 8 channels, we’re well under 1111 cycles.

✔ 180 kSPS is comfortable
✔ Even 250 kSPS would likely work

⸻

5. Sampling Model

Continuous, block-based

[Sample][Sample][Sample]...[Sample]
   ↓
Block full → write to DDR → interrupt Linux

PRU never stops sampling unless:
	•	run == 0
	•	fatal error

⸻

6. Memory Layout (Shared Memory)

Config Structure (written by Linux)

struct pru_config {
    uint32_t magic;                 // Verification magic number
    uint32_t version;               // Layout version
    uint32_t sample_rate_hz;
    uint32_t sample_period_cycles;
    uint8_t  channel_mask;          // bit per channel
    uint8_t  num_channels;
    uint16_t reserved;
    uint32_t block_samples;
    uint32_t run;
    uint32_t error_flags;
};

Linux computes sample_period_cycles
PRU trusts it (no division in PRU)

Memory is a single contiguous region at 0x00010000 (PRU address space)
Linux mmaps this for zero-copy access

⸻

Data Block Structure

struct sample_block {
    uint32_t block_id;
    uint32_t sample_count;
    uint64_t t_start_cycles;
    uint16_t samples[BLOCK_SAMPLES][MAX_CHANNELS];
};

For 1 channel:

samples[n][0]

For 8 channels:

samples[n][0..7]


⸻

7. PRU Local RAM Strategy

PRU local RAM is only 8 KB, so we use a staging buffer strategy:

Local buffer = small staging area (32 samples)
Shared memory = ring buffer storage

Example:

uint16_t local_buf[32][8];  // ~512 bytes in PRU RAM

Flow:
	1.	Fill local buffer (fast, no DDR access)
	2.	Burst copy → shared memory ring buffer
	3.	Repeat

This avoids DDR stalls during time-critical sampling.
Burst writes are much more efficient than per-sample writes.

⸻

8. Channel Read Strategy (Parallel Mode)

Channel iteration

Channels are read sequentially only if enabled.

Example mask:

0b00010101 → CH1, CH3, CH5

PRU loop:

for (ch = 0; ch < 8; ch++) {
    if (channel_mask & (1 << ch)) {
        read_channel(ch);
    }
}

⚠ Important:
	•	Branching here is safe
	•	Channel count is fixed per run
	•	Timing stays deterministic

⸻

9. PRU Main Loop – Final Form

This is the mental model your code will follow.

wait_for_run_flag();

while (run) {

    block_start_cycle = get_cycle_count();
    block_sample_count = 0;

    for (i = 0; i < block_samples; i++) {

        cycle_start = get_cycle_count();

        trigger_convst();
        wait_busy_low();

        read_enabled_channels(local_buf[local_idx]);

        local_idx++;
        block_sample_count++;

        if (local_idx == LOCAL_BUF_SAMPLES) {
            copy_local_to_ddr();
            local_idx = 0;
        }

        wait_until(cycle_start + sample_period_cycles);
    }

    flush_local_buf();
    write_block_header();
    signal_linux();
}


⸻

10. Error Conditions PRU Should Detect

Minimal but important:

Error	Action
BUSY timeout	set error flag
DDR write overrun	set error flag
sample_period_cycles < MIN_SAFE	refuse to run

PRU never prints.
Linux logs everything.
