# PRU Shared Memory Map

## Overview

Communication between PRU firmware and Linux uses two regions:

1. **PRU Shared RAM (control)** — header, config, status (`pru_shared_memory_t`)
2. **DDR sample ring** — block descriptors + interleaved ADC samples

**Key Characteristics:**
- Control plane in 12 KB Shared RAM (fast, uncached)
- Deep sample ring in carved-out DDR (≥50–100 ms at high SPS)
- Block-level PRU cycle timestamps; host reconstructs per-sample times
- Disk stores decimated overview + anomaly event windows only (no full-rate archive)

Layout version: **`SHM_VERSION = 2`** (see [`pika/pru/include/shm_layout.h`](../pika/pru/include/shm_layout.h)).

## Memory Regions

### AM335x

| Region | PRU view | ARM physical | Size | Role |
|--------|----------|--------------|------|------|
| Shared RAM | `0x00010000` | `0x4A310000` | 12 KB | Control header only |
| DDR carveout | phys from remoteproc | same as phys | 1 MiB | Sample ring (`pika_sample_ring`) |

### DDR sample ring (remoteproc carveout)

The sample ring is **not** a fixed physical address. The PRU firmware requests 1 MiB via a `TYPE_CARVEOUT` entry in its resource table (`pika_sample_ring`). Linux remoteproc allocates contiguous CMA/DDR, patches `da`/`pa` into the resource table, and the PRU publishes that address in `pru_shared_memory_t.ddr_phys_addr`.

The datalogger reads `ddr_phys_addr` after `magic` appears and `mmap`s `/dev/mem` at that PA.

`mem=448M` in `uEnv.txt` is **not required** for this path (it was for an earlier fixed-PA approach). Keeping it is harmless.

## Control Header (`pru_shared_memory_t`)

Located at Shared RAM offset 0; first **128 bytes** reserved (`SHM_HEADER_OFFSET`).

| Field | Type | Access | Description |
|-------|------|--------|-------------|
| magic | u32 | R/W | `0xDEADBEEF` when PRU is alive |
| version | u32 | R | Layout version (`2`) |
| sample_period_cycles | u32 | R/W | Target period in PRU cycles; **`0` = free-run / max-rate** |
| block_size | u32 | R | Samples per block (default 128) |
| num_blocks | u32 | R | Ring depth (default 256) |
| write_block_idx | u32 | R | Next block PRU will write |
| error_flags | u32 | R | Error bits |
| sample_count | u32 | R | Total samples acquired (progress source of truth) |
| sample_rate | u32 | R/W | Hz from datalogger; `0` = free-run |
| pru_clock_hz | u32 | R | 200000000 on BBB |
| heartbeat | u32 | R | Incremented in acquisition loop |
| ch_enable[8] | u32×8 | R/W | Per-channel enable (1 = RD that channel) |
| ddr_phys_addr | u32 | R | Physical base of sample ring |
| ddr_size_bytes | u32 | R | Ring size in bytes |
| block_desc_size | u32 | R | `sizeof(block_descriptor_t)` = 24 |

## Block Descriptor (`block_descriptor_t`) — 24 bytes

Each DDR ring slot:

```c
typedef struct {
  uint64_t timestamp_cycles; /* first sample (accumulated PRU CCNT) */
  uint32_t num_samples;
  uint32_t flags;            /* 0xAA55AA55 when complete */
  uint32_t period_cycles;    /* measured mean period this block */
  uint32_t reserved;
} block_descriptor_t;
```

**Payload:** always `block_size × 8 × sizeof(int16)` interleaved channels (disabled channels store 0).

```
block_total_size = 24 + block_size × 8 × 2
```

Default: `128` samples → `2072` bytes/block; `256` blocks → ~518 KiB (fits in 1 MiB ring).

## Timestamps

- **Authoritative time base:** PRU cycle counter (CCNT), 5 ns @ 200 MHz.
- **Per block:** `timestamp_cycles` at post-BUSY / start of first sample readout; `period_cycles` on block close.
- **Per sample (host):**  
  `t[i] = cycles_to_ns(timestamp_cycles + i × period_cycles)`  
  YAML `nominal_rate_hz` is pacing intent / fallback only.

## Paced vs free-run

| Mode | Config | PRU behavior |
|------|--------|--------------|
| Paced | `sample_rate > 0`, `sample_period_cycles = 200e6 / rate` | Wait remaining cycles after each conversion+read |
| Free-run | `sample_rate == 0`, `sample_period_cycles == 0` | No wait; measured `period_cycles` still valid |

Host re-applies rate/channels after PRU sets `magic` (PRU wipes the header on boot).

## Ring Buffer Layout (DDR)

```
DDR @ 0x9C000000:
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
/* DDR sample ring — physical address from header after PRU start */
mmap(..., header->ddr_size_bytes, ..., fd, header->ddr_phys_addr);
```

See [`pika/datalogger/src/shm_reader.c`](../pika/datalogger/src/shm_reader.c).
