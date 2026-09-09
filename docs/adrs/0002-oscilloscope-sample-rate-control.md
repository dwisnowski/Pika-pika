# ADR-0002: Oscilloscope Sample-Rate Control

**Status:** Accepted  
**Date:** 2026-09-09  
**Branch:** `beagleboneblack`

## Context

The live oscilloscope needs a way to change the physical AD7606/PRU acquisition
rate from 10 S/s to 180 kS/s. The existing `/api/v1/config/sample-rate` endpoint
only accepted 1–100 kHz, wrote YAML without restarting acquisition, and had no
UI on the scope page. Rates below ~120 S/s cannot faithfully represent 60 Hz
mains, but are still useful for long-window diagnostics.

## Decision

1. The oscilloscope slider controls the **physical** acquisition rate
   (`sampling.nominal_rate_hz`), not display-only downsampling.
2. Allowed rates are discrete engineering steps:
   `10, 20, 50, 100, 200, 500, 1k, 2k, 5k, 10k, 20k, 50k, 100k, 150k, 180k` S/s.
3. Changing the rate persists YAML, then restarts `pika-run-all.service` so PRU
   pacing, detector windows, and scope buffers reinitialize together.
4. Rates below 120 S/s remain allowed, with an explicit aliasing warning in the UI.
5. When acquisition is slower than the configured 50 Hz decimated output rate,
   the effective decimated rate is clamped to the acquisition rate.

## Consequences

- Scope users can step through useful rates without SSH or config edits.
- Low rates lengthen block fill time; health checks must tolerate that.
- A restart briefly disconnects WebSocket clients; the UI must reconnect and
  confirm the effective rate from health data.
- High rates (150–180 kS/s) approach AD7606/GPIO bit-bang limits and may show
  more overrun under load.
