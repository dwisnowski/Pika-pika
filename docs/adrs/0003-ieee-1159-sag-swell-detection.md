# ADR-0003: IEEE 1159 Sag/Swell Detection and Professional Review Flags

**Status:** Accepted  
**Date:** 2026-09-09  
**Branch:** `beagleboneblack`

## Context

Pika monitors residential line-to-neutral AC (typically 120 V, 60 Hz in North
America) so a homeowner can tell whether voltage problems warrant calling the
utility or an electrician. Detection lived in the datalogger with ±10% RMS
thresholds, but:

1. Event duration/peak reporting had bugs (0.0 ms durations, crest voltage
   labeled as VAC) that undermined trust for real reports.
2. User-tunable logging sensitivity and “should a professional look at this?”
   were conflated — dialing log thresholds would also change severity meaning.
3. There was no documented mapping to IEEE 1159 / ANSI C84.1 practice.

## Decision

### Log thresholds (user-configurable)

Default logging follows IEEE 1159 short-duration definitions on calibrated
1-cycle RMS:

- **Sag:** RMS below **90%** of site nominal for ≥ **~0.5 cycle** (9 ms @ 60 Hz)
- **Swell:** RMS above **110%** of site nominal for the same minimum duration
- Site nominal defaults to **120 V** (`target_mains_vrms`)

Users may change these via the Recent Events gear → `pika.yaml` → acquisition
restart. Changing log thresholds only changes what is stored.

### Professional-review policy (fixed)

Every logged event is scored at **read time** against a fixed policy
(independent of log settings):

| Condition | Flag |
|-----------|------|
| Extreme RMS ≤ 10% of nominal | Interruption-class → review |
| Sag extreme RMS ≤ 70% of nominal | Deep sag → review |
| Swell extreme RMS ≥ 120% of nominal | Damaging swell → review |
| Duration ≥ 60 s and RMS outside ANSI C84.1 utilization Range B (~104–127 V @ 120 V) | Sustained → review |

Mild logged events remain visible without a review badge. The `?` help popover
explains both layers and contact guidance (utility vs electrician).

### Detector correctness

- Track **extreme RMS** during an event (min for sag, max for swell) and store
  it in index records (format v3).
- Propagate COMPLETED on sag↔swell type flip.
- On capture max-duration truncate, force-complete the detector so duration and
  extreme RMS are written (no more 0.0 ms saves from START metadata).

## Consequences

- Homeowners always see whether an event warrants professional attention, even
  if logging is set very sensitive.
- Review criteria cannot be “configured away” in the settings gear.
- Old v2 index files remain readable; peak display falls back to crest≈RMS/√2
  approximation until new events are recorded.
- Still not a certified PQ meter; spike/transient and dedicated interruption /
  sustained event *types* remain future work.

## Related

- [ADR-0001](0001-pru-timing-accuracy.md) — timing accuracy for sag/swell review
- Detector: `pika/datalogger/src/anomaly_detector.c`
- Review policy: `pika/webapp/app/services/review_policy.py`
