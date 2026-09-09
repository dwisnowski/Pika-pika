# PRU development on BeagleBone Black (Pika)

Hard-won notes for editing PRU firmware and the Linux datalogger that consumes it. Prefer this over stale narrative docs when behavior disagrees.

Canonical contracts:

- [`pika/pru/include/shm_layout.h`](../pika/pru/include/shm_layout.h) — SHM header and block descriptor
- [`pika/pru/include/resource_table.h`](../pika/pru/include/resource_table.h) — explicit remoteproc resource table
- [`pika/pru/src/pru_main.c`](../pika/pru/src/pru_main.c) — acquisition loop
- [`pika/datalogger/src/shm_reader.c`](../pika/datalogger/src/shm_reader.c) — host mapping and block polling

---

## Mental model

```text
AD7606 ──(CONVST/BUSY/RD + parallel DB)──► PRU0
                                            │
                                            ▼
                                    Shared RAM 12KB
                                 (header + four blocks)
                                            │
                                            ▼
                                       datalogger
                                      │
                          decimated.bin + events only
```

- **PRU clock:** 200 MHz → 5 ns/cycle. CCNT at local `0x2200C`; enable with CTRL bit `CTR_EN` (`0x22000` bit 3).
- **OCP/DDR:** clear `CT_CFG.SYSCFG_bit.STANDBY_INIT` before any external memory access.
- **Pins:** `__R30` / `__R31` for PRU GPO/GPI; data bus is bit-banged via GPIO `DATAIN` banks (see `pru_config.h` / `adc_parallel.h`).

---

## Memory: what works and what does not

### Shared RAM (always use for control)

| View | Address | Size |
|------|---------|------|
| PRU | `0x00010000` | 12 KB |
| ARM | `0x4A310000` | map `0x3000` |

The first 128 bytes hold `pru_shared_memory_t`. The remaining bytes hold four
128-sample blocks beginning at PRU address `0x00010080`. This provides 51.2 ms
of buffering at 10 kHz and uses the already coherent Shared RAM mapping.

### Ring address calculations

TI `clpru` 2.3.3 generated unreliable hardware and software multiplication
sequences for the ring stride on this target. The four fixed block offsets
(`0`, `2072`, `4144`, `6216`) are intentional. Derive ring pointers directly
from the live `shm` pointer; do not retain a numeric ring-base local across the
acquisition loop.

### Host-side compile check (macOS)

Install TI’s macOS `clpru` once and build firmware on the Mac before syncing to the BBB:

```bash
./scripts/install-pru-toolchain-macos.sh
make -C pika/pru check-toolchain
make -C pika/pru build
```

This catches clpru syntax/errors (#41, #81, missing headers) without a round-trip to the board. `load` / `run-pru-datalogger` still run on the BBB.

### Remoteproc carveout (optional / fragile on 4.19-ti)

Requesting `TYPE_CARVEOUT` in the resource table can make Linux allocate CMA (e.g. `0x98A00000`). Pitfalls seen in practice:

- The PRU’s on-core copy of `.resource_table` often still shows unpatched `da/pa` (`0` / `0xFFFFFFFF`).
- Reading “resource table at PRU DMEM offset 0” via `/dev/mem` can return **garbage** (wrong placement / not the patched host copy).
- debugfs `.../remoteprocN/resource_table` may be absent unless debugfs is mounted.

The deployed 4.19-ti kernel also failed bidirectional coherence tests against
the fixed reserved DDR window at `0x9C000000`. Shared RAM is therefore the
supported production path; DDR carveouts remain experimental.

### Resource table authoring

- Use the **explicit** structs in `resource_table.h` (match Linux `remoteproc.h`), not whatever packing `rsc_types.h` from the PRU SSP happens to have.
- Define `RPROC_FW_RSC_ADDR_ANY` / carveout type locally; older SSP headers omit `FW_RSC_ADDR_ANY` and break `clpru` builds.
- Keep `.resource_table` in the linker cmd (`AM335x_PRU.cmd`); remoteproc requires the section even if empty-ish.

---

## SHM protocol (version 2)

### Header (`pru_shared_memory_t`)

Important fields:

| Field | Role |
|-------|------|
| `magic` | `0xDEADBEEF` when PRU init finished enough for host attach |
| `sample_period_cycles` | `0` = free-run / max rate; else paced period @ 200 MHz |
| `sample_rate` | Hz from datalogger (`0` = free-run intent) |
| `block_size` / `num_blocks` | defaults 128 / 4 for Shared RAM ring |
| `sample_count` | **source of truth** for completed samples |
| `write_block_idx` | diagnostics only; has been flaky on some reads |
| `ddr_phys_addr` / `ddr_size_bytes` | PRU-local Shared RAM ring geometry |
| `ch_enable[8]` | skip `adc_read_next` when 0; payload still 8 slots |
| `heartbeat` | alive counter |
| `error_flags` | `0xDEAD0002` BUSY timeout |

### Block descriptor (24 bytes) + payload

```c
timestamp_cycles  // u64 field carrying raw 32-bit CCNT from PRU
num_samples       // u32
flags             // u32, 0xAA55AA55 when complete
period_cycles     // u32, configured period this block
reserved          // u32
// then: num_samples × 8 × int16 interleaved
```

Linux extends CCNT wraps to 64 bits before applying
`t[i] = cycles_to_ns(timestamp_cycles + i * period_cycles)`.
YAML `nominal_rate_hz` is pacing intent / fallback only.

### Boot handshake (easy to get wrong)

1. Host may write config into SHM **before** start.
2. PRU **zeros** the header, then publishes geometry / magic.
3. Host must **wait for magic**, alias the Shared RAM ring, **re-apply** channel enables and sample period, then consume blocks.

Skipping step 3 looks like “PRU ignores config.”

### Consumer poll rules

- Prefer `completed_blocks = sample_count / block_size`.
- Require `flags == 0xAA55AA55` and sane `num_samples`.
- Drain **all** ready blocks per cycle; idle sleep ~100 µs (1 ms is too slow near 180 kSPS).
- On overrun (`pending > num_blocks`), skip forward; log it.

---

## Timing and the hot loop

- Stamp raw CCNT before conversion on `smp_in_blk == 0`; Linux extends wraps.
- On block close, publish the configured `period_cycles`.
- Pacing: measure elapsed since sample start; `delay_cycles_runtime(remaining >> 1)` — the asm loop is ~2 cycles per iteration.
- Accumulate 32-bit CCNT into `uint64_t` with wrap-safe subtract.
- At ~180 kSPS, period budget is ~5–5.5 µs; bit-bang GPIO assemble dominates. Do not add per-sample SHM timestamp stores.

---

## Build / load / run (on the BBB)

From `pika/` (repo’s `pika/pika` on device):

```bash
make stop
make pru                 # build + load + start PRU0 firmware
make run-datalogger      # build + run host
# or:
make run-pru-datalogger  # both
```

- PRU toolchain: `clpru` on device; `delay_cycles.asm` must stay linked into the main firmware.
- Firmware path: `/lib/firmware/am335x-pru0-fw` via remoteproc sysfs.
- Pinmux: `config-pin` in `pru/Makefile` `load` target — keep in sync with `pru_config.h`.

---

## Debugging without a PRU debugger

| Observe | How |
|---------|-----|
| Alive? | `heartbeat` increasing in SHM |
| Producing? | `sample_count` increasing |
| BUSY issues? | `error_flags == 0xDEAD0002` |
| Block valid? | Shared RAM descriptor has `flags == 0xAA55AA55` |

Logic analyzer: startup CONVST panic pulse in `pru_main.c` is intentional for bring-up.

---

## Product intent (don’t “fix” this away)

- Disk: **decimated overview** + **hi-fi anomaly event windows** only — not continuous full-rate archives.
- Anomaly math assumes a known rate when paced; free-run still needs measured `period_cycles` for timestamps.

---

## Checklist before merging PRU/SHM changes

- [ ] `shm_layout.h` and ARM consumer sizes agree (`BLOCK_DESCRIPTOR_SIZE`, ring element size)
- [ ] Host re-applies config after magic
- [ ] Four 2072-byte blocks still fit after the 128-byte header
- [ ] Firmware rebuilt **and** reloaded on hardware
- [ ] No per-sample timestamp arrays added “for accuracy”
- [ ] Docs updated only if they match the headers
