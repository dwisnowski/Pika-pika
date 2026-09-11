# ADR-0005: Operator Status Dashboard

**Status:** Accepted  
**Date:** 2026-09-10  
**Branch:** `beagleboneblack`

## Context

`make daemon-status` printed `systemctl status pika-run-all.service`. While the
pipeline is running, that unit's journal is dominated by datalogger tick and
writer lines, so the operator cannot see whether the PRU is online, whether
samples are advancing, or how full the SD card is.

Those facts already exist elsewhere: remoteproc sysfs, `GET /health`,
`pika.yaml`, `make startscreen` host counters, and process/port checks. They
were never composed into one read-only view.

## Decision

1. Replace the raw unit dump with a composed CLI dashboard
   (`pika/scripts/pika_status.py`, invoked by `make daemon-status`).
2. Gather status from existing sources only: `systemctl show`, remoteproc
   sysfs (name-based PRU discovery), `pgrep`, port 8888, `GET /health`,
   `pika.yaml`, `/proc` + `df`/`free`, and the datalogger data directory.
   Do not mmap `/dev/mem` and do not add a new daemon.
3. Keep the live journal on `make daemon-logs`. Print a few journal lines
   from status only when the unit is `failed` or `activating`.
4. Style with xterm-256 colors when the TTY supports them. Honor `NO_COLOR`
   and emit plain text when stdout is not a TTY.

## Consequences

- Operators get PRU, datalogger, web, config, and host resource state in one
  screen without scrolling systemd noise.
- `/health` fields disappear if the webapp is down; process and port rows
  still report independently.
- Piped or `NO_COLOR` output is uncolored so scripts can scrape it.
- Related: [ADR-0002](0002-oscilloscope-sample-rate-control.md).
