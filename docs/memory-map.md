# PRU Shared Memory Map

## Overview

Communication between PRU firmware and Linux uses one 12 KiB region:

1. **PRU Shared RAM** — header, config, status, and four sample blocks

**Key Characteristics:**
- Header and sample ring share fast, uncached PRUSS Shared RAM
- Four 128-sample blocks provide 51.2 ms of buffering at 10 kHz
- Block-level PRU cycle timestamps; host reconstructs per-sample times
- Disk stores decimated overview + anomaly event windows only (no full-rate archive)

Layout version: **`SHM_VERSION = 2`** (see [`pika/pru/include/shm_layout.h`](../pika/pru/include/shm_layout.h)).

## Memory Regions

### AM335x

| Region | PRU view | ARM physical | Size | Role |
|--------|----------|--------------|------|------|
| Shared RAM | `0x00010000` | `0x4A310000` | 12 KB | 128-byte control header + sample ring |

### Shared RAM sample ring

The ring begins at PRU address `0x00010080`, immediately after the reserved
128-byte header. Linux accesses the same bytes at offset `0x80` in its existing
`0x4A310000` Shared RAM mapping.

The previous fixed DDR window at `0x9C000000` was not coherent with PRU0 on the
deployed 4.19-ti kernel. `mem=448M` is no longer required by the sample path.

## Control Header (`pru_shared_memory_t`)

Located at Shared RAM offset 0; first **128 bytes** reserved (`SHM_HEADER_OFFSET`).

| Field | Type | Access | Description |
|-------|------|--------|-------------|
| magic | u32 | R/W | `0xDEADBEEF` when PRU is alive |
| version | u32 | R | Layout version (`2`) |
| sample_period_cycles | u32 | R/W | Target period in PRU cycles; **`0` = free-run / max-rate** |
| block_size | u32 | R | Samples per block (default 128) |
| num_blocks | u32 | R | Ring depth (default 4) |
| write_block_idx | u32 | R | Next block PRU will write |
| error_flags | u32 | R | Error bits |
| sample_count | u32 | R | Total samples acquired (progress source of truth) |
| sample_rate | u32 | R/W | Hz from datalogger; `0` = free-run |
| pru_clock_hz | u32 | R | 200000000 on BBB |
| heartbeat | u32 | R | Incremented in acquisition loop |
| ch_enable[8] | u32×8 | R/W | Per-channel enable (1 = RD that channel) |
| ddr_phys_addr | u32 | R | PRU-local sample ring base (`0x00010080`) |
| ddr_size_bytes | u32 | R | Available ring area (12160 bytes) |
| block_desc_size | u32 | R | `sizeof(block_descriptor_t)` = 24 |
| block_complete_flag | u32 | R | Stable publication marker (`0xAA55AA55`) |

## Block Descriptor (`block_descriptor_t`) — 24 bytes

Each Shared RAM ring slot:

```c
typedef struct {
  uint64_t timestamp_cycles; /* raw CCNT seed from PRU */
  uint32_t num_samples;
  uint32_t flags;            /* 0xAA55AA55 when complete */
  uint32_t period_cycles;    /* configured period for this block */
  uint32_t reserved;
} block_descriptor_t;
```

**Payload:** always `block_size × 8 × sizeof(int16)` interleaved channels (disabled channels store 0).

```
block_total_size = 24 + block_size × 8 × 2
```

Default: `128` samples → `2072` bytes/block; four blocks consume 8288 bytes.

## Timestamps

- **Authoritative time base:** PRU cycle counter (CCNT), 5 ns @ 200 MHz.
- **Per block:** PRU publishes raw CCNT as the initial time seed. Linux advances
  subsequent block timestamps by `num_samples × period_cycles`, avoiding the
  PRU CCNT's ~21.47-second saturation limit.
- **Per sample (host):**  
  `t[i] = cycles_to_ns(timestamp_cycles + i × period_cycles)`  
  YAML `nominal_rate_hz` is pacing intent / fallback only.

## Paced vs free-run

| Mode | Config | PRU behavior |
|------|--------|--------------|
| Paced | `sample_rate > 0`, `sample_period_cycles = 200e6 / rate` | Wait remaining cycles after each conversion+read |
| Free-run | `sample_rate == 0`, `sample_period_cycles == 0` | No pacing delay |

Host re-applies rate/channels after PRU sets `magic` (PRU wipes the header on boot).

## Ring Buffer Layout

```
Shared RAM @ offset 0x80:
┌─────────────────────────────────────────┐
│ Block 0: descriptor (24) + samples      │
│ Block 1: ...                            │
│ ...                                     │
│ Block N-1                               │
└─────────────────────────────────────────┘
```

Progress: consumer uses `sample_count / block_size` (not `write_block_idx` alone). Reader drains **all** completed blocks per poll cycle.

## Sample Data Organization

```
[s0_ch0][s0_ch1]...[s0_ch7]
[s1_ch0][s1_ch1]...[s1_ch7]
...
```

## Error Flags

| Value | Meaning |
|-------|---------|
| `0xDEAD0002` | BUSY timeout / conversion failure |

## Host Mapping

```c
/* Shared RAM header */
mmap(..., 0x3000, ..., fd, 0x4A310000);
/* Sample ring aliases the same mapping at byte offset 128. */
ring = (uint8_t *)shared_ram + SHM_HEADER_OFFSET;
```

See [`pika/datalogger/src/shm_reader.c`](../pika/datalogger/src/shm_reader.c).
