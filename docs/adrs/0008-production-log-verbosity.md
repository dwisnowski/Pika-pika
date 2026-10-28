# ADR-0008: Production Log Verbosity

**Status:** Accepted  
**Date:** 2026-10-28  
**Branch:** `beagleboneblack`

## Context

`pika-run-all.service` captures datalogger and webapp stdout/stderr into the
systemd journal, which rsyslog also writes to `/var/log/daemon.log`. On the
BBB eMMC that path filled the root filesystem: ungated C `printf`s
(`[SHM Reader] Tick`, `[Writer] Decimated write…`, `[Reader] Polling…`) plus
uvicorn HTTP access lines from dashboard polling dominated the log.

[ADR-0005](0005-operator-status-dashboard.md) worked around journal noise for
operators with `pika_status.py` but did not stop the flood.

## Decision

1. Gate datalogger progress/tick `printf`s behind `PIKA_DEBUG` (env, default
   off) via `PIKA_DBG` / `pika_debug_enabled()`. Startup one-shots and all
   `fprintf(stderr, …)` failure paths remain always on.
2. Keep webapp `logging.level` for application and uvicorn error loggers.
   Set `uvicorn.access` to WARNING unless `logging.level` is `debug`.
3. Do not redirect systemd away from the journal; quiet at the source so
   real errors still appear in `journalctl -u pika-run-all.service`.

## Consequences

- Production journals stay small; eMMC is less likely to fill from logging.
- Bring-up: set `Environment=PIKA_DEBUG=1` on the unit (or export it for a
  foreground `make run-all`) and/or `logging.level: debug` in `pika.yaml`.
- Related: [ADR-0005](0005-operator-status-dashboard.md).
