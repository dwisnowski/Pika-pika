# ADR-0009: Software-First VR1710 Gap Closure

**Status:** Accepted  
**Date:** 2026-11-11  
**Branch:** `beagleboneblack`

## Context

Pika already logs IEEE 1159-style sags/swells ([ADR-0003](0003-ieee-1159-sag-swell-detection.md)),
IEC-inspired 12-cycle Vrms trends ([ADR-0004](0004-iec-aligned-trend-decimation.md)),
and manual flicker notes ([ADR-0007](0007-flicker-observations.md)). Compared with a
Fluke VR1710 Voltage Quality Recorder, the largest *software-only* gaps are
first-class interruptions, logged mains frequency, logged harmonics/THD, longer
retention, and a summary export. Full Pst/Plt and true >100 µs impulse capture
are deferred: Pst/Plt is a large IEC 61000-4-15 algorithm with weaker homeowner
ROI given ADR-0007 notes, and ZMPT101B bandwidth cannot honestly support
Fluke-class transient claims.

## Decision

1. Add first-class **INTERRUPTION** events (1-cycle RMS ≤ configurable % of
   nominal, classified before sag). Keep SPIKE/DIP enum values stable; do not
   emit impulse types in this slice.
2. Log **mains frequency** continuously (zero-crossing / cycle-period estimate
   per IEC trend window) in the expanded decimated payload.
3. Log **IEC-inspired harmonics (orders 2…32) + THD** from the C datalogger on
   contiguous windows aligned with ADR-0004. Accuracy is **front-end limited**;
   not Class A / EN 61000-4-7 certified.
4. Store **¼-cycle RMS min/max** inside each 12-cycle trend point (alongside
   the existing instantaneous envelope).
5. Raise rotate caps for multi-week trend/event campaigns and add a **PQ
   summary zip** export (trend, events, frequency, harmonics).
6. Keep flicker as **manual notes** (ADR-0007). Pst/Plt, Class A certification,
   CAT-rated metrology, and impulse capture remain non-goals until hardware
   revisit.

### Fluke VR1710 baseline (before → after this decision)

Hardware is unchanged. Later ADRs should update the “after” column rather than
reinventing the comparison.

| Capability | Fluke VR1710 | Pika **before** | Pika **after this plan** |
|---|---|---|---|
| Single-phase L–N voltage | Yes (+ N/G paths) | Yes (120 V L–N) | Same (no hardware change) |
| Continuous Vrms trend | Yes; long campaigns | ~5 Hz (12-cycle) + 10‑min rollup; ~days | Same metrics; **multi-week retention** via larger rotate caps |
| ¼-cycle Min/Max/Avg RMS | Yes (5 ms) | Instantaneous envelope over 12-cycle bucket | **¼-cycle RMS min/max** inside each 12-cycle point |
| Sag / swell (dips / overvoltages) | Yes | Yes (IEEE 1159-style) | Same |
| Interruptions | First-class | Review badge on deep sag only | **First-class `INTERRUPTION` events** + waveforms |
| Transient / impulse (>100 µs) | Yes | No | **Still no** (deferred; ZMPT-limited) |
| Event waveforms | Yes | Yes (sag/swell windows) | Yes, including **interruptions** |
| Harmonics / THD **logged** | EN 61000-4-7 to 32nd + trends | Live FFT only | **Logged THD + harmonics ~2…32** (IEC-inspired; accuracy front-end limited) |
| Flicker Pst/Plt | EN 61000-4-15 | Manual notes only | **Still notes only** (Pst/Plt deferred) |
| Frequency **logged** | Yes (±0.02 Hz claimed) | Display-only on live samples | **Continuous frequency series** |
| Accuracy / CAT / Class A | Published; CAT II 300 V | None claimed | **Still none claimed** (software plan only) |
| Recording duration | Days–months | Rotate-capped ~days | **Weeks-class trend/event retention** (SD-dependent) |
| Summary report / export | PowerLog | Flicker zip + raw APIs | **PQ summary zip** (trend, events, freq, harmonics) |
| Live remote scope / UI | Weak (download later) | Strong web UI | Same strength |

**Net movement:** ~25–35% of VR1710 product capability → ~55–65% of the
software-visible recorder feature set (still not “same quality”).

## Consequences

- Partially supersedes ADR-0003 “dedicated interruption … remain future work.”
- Revises ADR-0004 non-goals for harmonics/THD trends (still not Class A).
- Leaves ADR-0007 notes path intact; does not add an on-device flicker meter.
- Decimated `values_per_sample` bumps; readers must dual-read legacy vps=2/3.
- Explicit non-claim: not IEC 61000-4-30 Class A; not a certified Fluke substitute.

## Related

- [ADR-0003](0003-ieee-1159-sag-swell-detection.md)
- [ADR-0004](0004-iec-aligned-trend-decimation.md)
- [ADR-0007](0007-flicker-observations.md)
