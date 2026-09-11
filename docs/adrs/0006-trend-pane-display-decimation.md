# ADR-0006: Trend-Pane Display Decimation

**Status:** Accepted  
**Date:** 2026-09-10  
**Branch:** `beagleboneblack`

## Context

[ADR-0004](0004-iec-aligned-trend-decimation.md) stores contiguous IEC 12-cycle
Vrms intervals at ~5 Hz and raised the dashboard history depth to ~1 hour
(`history_max_points: 20000`). That product window is right, but the pane
loaded it by parsing all of `decimated.bin`, sending every interval to the
browser, and rebuilding Chart.js from scratch. The 250px card stayed blank
with no loading feedback. ADC `nominal_rate_hz` does not change IEC point
count; the ratio that matters is the stored trend rate.

Operators also need to trade lookback versus chart weight without restarting
acquisition.

## Decision

1. Keep full-rate IEC intervals on disk. Decimate **only** the trend-pane
   payload: tail-read the configured lookback, then min/mean/max bucket to
   `history_display_points` (~800).
2. Size the source window from **IEC trend rate**, not ADC rate:
   `source_points = history_window_minutes × 60 × iec_rate`.
3. Show a loading overlay on first paint, then a header chip
   (`Last 60 min · 800 pts`) on refresh. Update Chart.js in place.
4. Expose lookback minutes (1–720) and chart points (100–2000) on a trend-pane
   settings popover. Persist to `pika.yaml` and reload webapp config only —
   no `pika-run-all` restart.

## Consequences

- The chart stays near one point per CSS pixel; extrema survive in the
  envelope series. Zoom/pan survive 5 s refreshes.
- Raising ADC rate no longer (incorrectly) implies a shorter window. If the
  stored IEC rate ever rises, the same minutes automatically read more
  intervals and bucket heavier.
- `history_max_points` remains a fallback when window minutes is unset.
- Related: [ADR-0004](0004-iec-aligned-trend-decimation.md).
