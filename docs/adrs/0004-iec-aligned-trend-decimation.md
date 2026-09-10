# ADR-0004: IEC-Aligned Trend Decimation (12-cycle Vrms)

**Status:** Accepted  
**Date:** 2026-09-09  
**Branch:** `beagleboneblack`

## Context

Continuous overview storage used peak-hold min/max bucketing (~50 Hz). That is a
waveform-envelope compressor, not how IEEE 1159 / IEC 61000-4-30 express supply
voltage magnitude over time. The dashboard also discarded stored minima and only
plotted maxima, and `history_max_points: 1000` showed ~20 s of data.

IEEE 1159 defines short-duration events (handled by the anomaly detector). IEC
61000-4-30 defines contiguous **10/12-cycle (~200 ms)** RMS magnitude intervals,
then longer aggregations (≈3 s, 10 min, 2 h).

## Decision

1. Replace envelope-only decimation with **IEC-inspired Class S–style** intervals:
   contiguous **12 cycles @ 60 Hz** (10 @ 50 Hz) → ~**5 Hz** trend points.
2. Store per interval: calibrated **Vrms** plus instantaneous **min/max** envelope
   (`values_per_sample = 3`, centivolts on disk).
3. Chart **Vrms** as the primary series with optional peak envelope.
4. Keep a best-effort **10-minute Vrms min/avg/max** JSONL rollup for ANSI C84.1
   Range A/B context (not Class A UTC-tick synchronized).
5. Raise default history depth to ~1 hour of 5 Hz points (`history_max_points: 20000`).

Explicit non-goals: Class A certification, harmonics/THD trends, flicker, CIC
anti-alias before the envelope.

## Consequences

- Trend language matches what utilities expect for **sustained voltage** vs
  event captures for **sags/swells**.
- Old `vps==2` chunks remain readable (legacy max→approx Vrms).
- After upgrade, rotate/clear `decimated.bin` for a clean v2 stream.
- Related: [ADR-0001](0001-pru-timing-accuracy.md), [ADR-0003](0003-ieee-1159-sag-swell-detection.md).
