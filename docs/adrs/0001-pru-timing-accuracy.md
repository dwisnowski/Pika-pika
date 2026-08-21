# ADR-0001: PRU-to-Linux Timing Accuracy for Sag/Swell Review

**Status:** Accepted  
**Date:** 2026-08-19  
**Branch:** `beagleboneblack` / `cursor/pru-timing-8186`

## Context

Pika uses a BeagleBone Black PRU to sample an AD7606 ADC at up to 100 kHz.
The goal is to store highly decimated trend data (50 Hz min/max) for normal
browsing, while preserving full-rate waveforms around power quality events
(sags, swells) so they can be reviewed at high accuracy in the browser.

A timing review of the current implementation revealed that the architecture
is sound — block-level CCNT timestamps, host-side per-sample reconstruction,
and a split storage path — but several bugs prevent high-accuracy event review:

1. `cycles_to_ns` overflows `uint64` after ~92 seconds of runtime.
2. Stored timestamps use `CLOCK_MONOTONIC` but the browser interprets them as
   Unix epoch time.
3. The event window captures data ending at event *end*, tagged with event
   *start* time, producing a misaligned waveform.
4. The 30-cycle (~500 ms) RMS window is too slow to detect short sags or tag
   onset accurately. `min_duration_ms` is loaded but never enforced.
5. The anomaly detector returns mid-block on event end, dropping the remaining
   samples in the block from both detection and decimation.
6. `period_cycles` includes trailing pacing delay, biasing inter-sample time
   by ~0.75% at 10 kHz.
7. The history API drops per-chunk `start_time_ns` and reports rate as 10 kHz
   instead of 50 Hz, so the trend chart has no real time axis.

## Decision

Fix the timing pipeline end-to-end across seven work items:

### 1. Overflow-safe `cycles_to_ns`

Replace `elapsed_cycles * 1_000_000_000 / pru_clock_hz` with
`elapsed_cycles * 5` (exact at 200 MHz) or a split divide/mod for
general clock rates. Add a regression test for elapsed >> 92 s.

**Files:** `pika/datalogger/src/time_utils.c`

### 2. Anchor to `CLOCK_REALTIME`

At the first-block sync point, capture `realtime_ns - monotonic_ns` and add
that offset to all stored timestamps. PRU CCNT remains the source of truth
for relative sample spacing. Optionally refresh the offset periodically
(without stretching sample intervals) to track NTP corrections.

**Files:** `pika/datalogger/src/time_utils.c`, `pika/datalogger/main.c`

### 3. Correct `period_cycles` measurement

Stamp the last sample's CCNT *before* the pacing delay so `period_cycles`
reflects only conversion + readout time. Reconstruct per-sample time as
`timestamp_cycles + i * period_cycles` (matching the documented contract).

**Files:** `pika/pru/src/pru_main.c`

### 4. Fix event window capture

Trigger the circular-buffer snapshot at event *onset* (not end). Continue
recording through the event and into a configurable post-event tail. Store
`waveform_start_ns` and `ns_per_sample` in the index record so the browser
can align the waveform to the event tag.

Add a max-duration cap so a sustained undervoltage still produces a saved
event (truncated at the cap).

**Files:** `pika/datalogger/src/event_window.c`,
`pika/datalogger/include/event_window.h`,
`pika/datalogger/include/storage_format.h`,
`pika/datalogger/main.c`

### 5. Fix anomaly detector block processing

Do not `return` mid-block. Accumulate completed events into a small queue and
continue scanning the full 128-sample block. Enforce `min_duration_ms` before
emitting an event. Default `rms_window_cycles` to 1 (one AC cycle) for onset
accuracy; keep the existing 30-cycle window as a separate slow statistic for
the dashboard "line voltage" display.

**Files:** `pika/datalogger/src/anomaly_detector.c`,
`pika/datalogger/include/anomaly_detector.h`

### 6. Fix history API timestamps and rate

Return per-chunk `start_time_ns` from the decimated file. Report the actual
decimated rate (50 Hz) instead of the ADC rate (10 kHz). Use these in the
dashboard trend chart so events can be overlaid on a real time axis.

**Files:** `pika/webapp/app/services/history_service.py`,
`pika/webapp/app/services/event_service.py`,
`pika/webapp/app/templates/dashboard.html`,
`pika/webapp/app/templates/events.html`

### 7. Add a `validate_timestamps` integration check

Extend `pika/datalogger/validate_data.py` (or add a companion script) to
read `decimated.bin` and `index.bin`, verify monotonicity, check that
timestamps are plausible Unix epoch values, and confirm event waveform
alignment (waveform start <= event start <= waveform end).

**Files:** `pika/datalogger/validate_data.py` (or new
`pika/datalogger/validate_timestamps.py`)

## Consequences

- All stored timestamps will be Unix-epoch nanoseconds, directly usable by
  `new Date(ts / 1e6)` in the browser.
- Event waveforms will be correctly aligned to the tagged onset, with pre-
  and post-context.
- Short sags (down to half-cycle / 8 ms) will be detected and tagged within
  one AC cycle of onset.
- The trend chart will have a real time axis, allowing visual correlation with
  event markers.
- `event_index_record_t` gains two fields (`waveform_start_ns`,
  `ns_per_sample`), which is a storage format change. Old `index.bin` files
  will not be readable without migration or a version check.
- PRU firmware changes (item 3) require rebuilding with the TI PRU C compiler
  and reloading via remoteproc.

## Alternatives Considered

- **IEP timer instead of CCNT:** IEP is defined in `pru_config.h` but unused.
  CCNT is simpler (no shared-resource contention) and sufficient at 5 ns
  resolution. IEP would only matter if CCNT proved unreliable, which has not
  been observed.
- **PTP / PPS sync:** Would give sub-microsecond absolute time but requires
  hardware (GPS PPS or PTP-capable Ethernet) not present on the current board.
  `CLOCK_REALTIME` with NTP is adequate for wall-clock tagging; relative
  accuracy comes from PRU CCNT.
- **Per-sample timestamp arrays in DDR:** Rejected — doubles DDR bandwidth and
  cuts max sample rate in half. Block-level stamps + measured period are
  sufficient.
