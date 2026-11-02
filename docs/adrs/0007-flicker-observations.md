# ADR-0007: Flicker Notes Searched Against the Existing Trend

**Status:** Accepted  
**Date:** 2026-10-24  
**Updated:** 2026-11-02  
**Branch:** `beagleboneblack`

## Context

Visible lamp flicker and television picture dropouts are hard to line up with
Recent Events. The datalogger already records IEEE 1159 sags and swells
([ADR-0003](0003-ieee-1159-sag-swell-detection.md)) and ~200 ms Vrms intervals
([ADR-0004](0004-iec-aligned-trend-decimation.md)). Notes are entered almost
as soon as the blink is noticed, so the noted time is the end of the
disturbance, not a vague memory hours later.

A small anomaly model on the BeagleBone was considered and rejected. Sag and
swell detection is a voltage threshold. The board records one voltage channel.
An unsupervised model trained on RMS cannot name an appliance, cannot see
harmonics that RMS already discarded, and cannot be trained on a short
lookback label.

Television dropouts in this house last about 0.8 seconds, sometimes up to
1.5 seconds. Sound and picture both go, the show continues, and the set does
not reboot. Lamps can dim on a much smaller change than the 90% / 110% event
log.

## Decision

1. Store manual flicker notes in `observations.jsonl`, separate from
   `events.bin`. Deleting event data does not delete notes.
2. Each note has an observed time. Correlation searches the **prior 60 seconds**
   ending at that time (`[observed_at - 60s, observed_at]`), with no forward
   multi-minute pad.
3. Search the full sag/swell index and `decimated.bin` (including `.old`).
   Report logged events, the lowest and highest interval Vrms against nominal
   and against the median Vrms in the window, and the longest run of intervals
   away from that median, in seconds. Trend readers must resync past corrupt
   chunks so a hole in `.old` does not hide later valid segments.
4. On disk, each interval’s min and max are the AC waveform envelope
   (about ±Vpeak), not a lowest RMS. The dip and the low run use **interval
   Vrms**. The envelope is used only to notice a one-sided notch inside a
   single ~200 ms bucket.
5. The note records what was seen (lights, television, or both) and, for a
   television, how many sets, whether they seemed simultaneous, the source,
   how long the picture was gone, and whether the set rebooted. Those answers
   shape the sentence. They do not change the voltage search.
6. Do not add an on-device model and do not change sag/swell log thresholds for
   the sake of flicker notes alone (operators may still restore IEEE log
   defaults so short deep dips can capture waveforms).

## Consequences

- A note from the next day can still be compared with the trend, because the
  decimated file holds days of 5 Hz intervals at the current size cap.
- A low run of about 0.5–2 seconds is the mains moving for about as long as
  the television blank. A single short bucket means the set may have held the
  mute after a briefer dip. A flat window means the stored line did not move
  for the length of the blackout.
- Notes whose approximate time falls inside the loaded trend lookback (or the
  focused prior-minute window) appear as scatter markers on the supply voltage
  chart. Notes outside that span stay off the chart. Selecting a marker or
  list row opens a detail popover with disruption numbers (lowest Vrms,
  percent below median/nominal, low-run duration) and a prior-minute mini-chart.
- Revisit a model only if notes show a repeating waveform shape this search
  cannot describe, and only on waveform samples or a future current channel.

## Related

- [ADR-0003](0003-ieee-1159-sag-swell-detection.md) — sag/swell logging
- [ADR-0004](0004-iec-aligned-trend-decimation.md) — 12-cycle Vrms trend
- Notes and search: `pika/webapp/app/services/observation_service.py`
