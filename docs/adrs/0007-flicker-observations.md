# ADR-0007: Flicker Notes Searched Against the Existing Trend

**Status:** Accepted  
**Date:** 2026-10-24  
**Branch:** `beagleboneblack`

## Context

Visible lamp flicker and television picture dropouts are hard to line up with
Recent Events. The datalogger already records IEEE 1159 sags and swells
([ADR-0003](0003-ieee-1159-sag-swell-detection.md)) and ~200 ms Vrms intervals
([ADR-0004](0004-iec-aligned-trend-decimation.md)). A person notices the blink
up to about a day later, and the time they remember is only good to about
±2 minutes.

A small anomaly model on the BeagleBone was considered and rejected. Sag and
swell detection is a voltage threshold. The board records one voltage channel.
An unsupervised model trained on RMS cannot name an appliance, cannot see
harmonics that RMS already discarded, and cannot be trained on a ±2 minute
label.

Television dropouts in this house last about 0.8 seconds, sometimes up to
1.5 seconds. Sound and picture both go, the show continues, and the set does
not reboot. Lamps can dim on a much smaller change than the 90% / 110% event
log.

## Decision

1. Store manual flicker notes in `observations.jsonl`, separate from
   `events.bin`. Deleting event data does not delete notes.
2. Each note has an approximate time. Correlation always searches **±2 minutes**
   around that time.
3. Search the full sag/swell index and `decimated.bin` (including `.old`).
   Report logged events, the lowest and highest interval Vrms against nominal
   and against the median Vrms in the window, and the longest run of intervals
   away from that median, in seconds.
4. On disk, each interval’s min and max are the AC waveform envelope
   (about ±Vpeak), not a lowest RMS. The dip and the low run use **interval
   Vrms**. The envelope is used only to notice a one-sided notch inside a
   single ~200 ms bucket.
5. The note records what was seen (lights, television, or both) and, for a
   television, how many sets, whether they seemed simultaneous, the source,
   how long the picture was gone, and whether the set rebooted. Those answers
   shape the sentence. They do not change the voltage search.
6. Do not add an on-device model and do not change sag/swell log thresholds.

## Consequences

- A note from the next day can still be compared with the trend, because the
  decimated file holds days of 5 Hz intervals at the current size cap.
- A low run of about 0.5–2 seconds is the mains moving for about as long as
  the television blank. A single short bucket means the set may have held the
  mute after a briefer dip. A flat window means the stored line did not move
  for the length of the blackout.
- Notes whose approximate time falls inside the loaded trend lookback (or the
  focused ±2 minute window) appear as scatter markers on the supply voltage
  chart. Notes outside that span stay off the chart. Selecting a marker or
  list row opens a detail popover with disruption numbers (lowest Vrms,
  percent below median/nominal, low-run duration) and a ±2 minute mini-chart.
- Revisit a model only if notes show a repeating waveform shape this search
  cannot describe, and only on waveform samples or a future current channel.

## Related

- [ADR-0003](0003-ieee-1159-sag-swell-detection.md) — sag/swell logging
- [ADR-0004](0004-iec-aligned-trend-decimation.md) — 12-cycle Vrms trend
- Notes and search: `pika/webapp/app/services/observation_service.py`
