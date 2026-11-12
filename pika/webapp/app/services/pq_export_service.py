"""PQ summary zip export (PowerLog-style quick package, not EN 50160)."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.services.config_service import config_service
from app.services.event_service import event_service
from app.services.history_service import history_service


def _iso(ns: int) -> str:
    if not ns:
        return ""
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).isoformat()


class PqExportService:
    def export_zip(self) -> bytes:
        history = history_service.get_decimated_data(
            max_points=config_service.get_history_max_points(),
            window_minutes=config_service.get_history_window_minutes(),
            max_display_points=config_service.get_history_display_points(),
        )
        event_rows = event_service.get_recent_events(limit=10000)
        harmonics = history_service.get_harmonics_trend(limit=2000)
        rollup = history.get("rollup_10min") or []

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("README.txt", self._readme())
            zf.writestr("voltage_trend.csv", self._trend_csv(history))
            zf.writestr("events.csv", self._events_csv(event_rows))
            zf.writestr("frequency_summary.csv", self._frequency_csv(history))
            zf.writestr("harmonics.csv", self._harmonics_csv(harmonics))
            zf.writestr("vrms_10min.csv", self._rollup_csv(rollup))
            zf.writestr(
                "summary.json",
                json.dumps(self._summary(history, event_rows, harmonics), indent=2),
            )
        return buf.getvalue()

    @staticmethod
    def _readme() -> str:
        return (
            "Pika PQ summary export\n"
            "======================\n"
            "Best-effort single-phase voltage quality package.\n"
            "Not IEC 61000-4-30 Class A / not a Fluke PowerLog substitute.\n"
            "Harmonic accuracy is limited by the sensor front-end.\n"
        )

    def _summary(
        self, history: Dict[str, Any], events: List[Dict[str, Any]], harmonics: List[Dict]
    ) -> Dict[str, Any]:
        samples = history.get("samples") or []
        freqs = [f for f in (history.get("frequency_hz") or []) if f]
        thds = [float(h.get("thd_pct", 0)) for h in harmonics if "thd_pct" in h]
        return {
            "generated_utc": datetime.now(tz=timezone.utc).isoformat(),
            "nominal_vrms": config_service.get_target_mains_vrms(),
            "trend_points": len(samples),
            "vrms_min": min(samples) if samples else None,
            "vrms_avg": (sum(samples) / len(samples)) if samples else None,
            "vrms_max": max(samples) if samples else None,
            "frequency_hz_avg": (sum(freqs) / len(freqs)) if freqs else None,
            "frequency_hz_min": min(freqs) if freqs else None,
            "frequency_hz_max": max(freqs) if freqs else None,
            "event_count": len(events),
            "thd_pct_avg": (sum(thds) / len(thds)) if thds else None,
            "harmonics_note": history.get("harmonics_note"),
        }

    @staticmethod
    def _trend_csv(history: Dict[str, Any]) -> str:
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(
            [
                "timestamp_utc",
                "timestamp_ns",
                "vrms",
                "env_min",
                "env_max",
                "qtr_rms_min",
                "qtr_rms_max",
                "frequency_hz",
            ]
        )
        ts = history.get("timestamps") or []
        vrms = history.get("samples") or []
        mins = history.get("samples_min") or []
        maxs = history.get("samples_max") or []
        qmn = history.get("samples_qtr_min") or []
        qmx = history.get("samples_qtr_max") or []
        freqs = history.get("frequency_hz") or []
        for i, stamp in enumerate(ts):
            w.writerow(
                [
                    _iso(int(stamp)),
                    stamp,
                    vrms[i] if i < len(vrms) else "",
                    mins[i] if i < len(mins) else "",
                    maxs[i] if i < len(maxs) else "",
                    qmn[i] if i < len(qmn) else "",
                    qmx[i] if i < len(qmx) else "",
                    freqs[i] if i < len(freqs) else "",
                ]
            )
        return out.getvalue()

    @staticmethod
    def _events_csv(events: List[Dict[str, Any]]) -> str:
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(
            [
                "event_id",
                "type",
                "timestamp_utc",
                "duration_ms",
                "extreme_rms_v",
                "needs_review",
                "review_reason",
            ]
        )
        for ev in events:
            stamp = int(ev.get("timestamp") or ev.get("timestamp_ns") or 0)
            w.writerow(
                [
                    ev.get("id") or ev.get("event_id") or "",
                    ev.get("type") or "",
                    _iso(stamp),
                    ev.get("duration_ms") or "",
                    ev.get("peak_rms_v") or ev.get("extreme_rms_v") or "",
                    ev.get("needs_review") or "",
                    ev.get("review_reason") or "",
                ]
            )
        return out.getvalue()

    @staticmethod
    def _frequency_csv(history: Dict[str, Any]) -> str:
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["timestamp_utc", "timestamp_ns", "frequency_hz"])
        ts = history.get("timestamps") or []
        freqs = history.get("frequency_hz") or []
        for i, stamp in enumerate(ts):
            if i >= len(freqs):
                break
            if not freqs[i]:
                continue
            w.writerow([_iso(int(stamp)), stamp, freqs[i]])
        return out.getvalue()

    @staticmethod
    def _harmonics_csv(rows: List[Dict[str, Any]]) -> str:
        out = io.StringIO()
        w = csv.writer(out)
        header = ["timestamp_utc", "timestamp_ns", "thd_pct"] + [
            f"h{h}" for h in range(1, 33)
        ]
        w.writerow(header)
        for row in rows:
            stamp = int(row.get("ts_ns") or 0)
            harm = row.get("h") or []
            cells = [_iso(stamp), stamp, row.get("thd_pct", "")]
            for h in range(32):
                cells.append(harm[h] if h < len(harm) else "")
            w.writerow(cells)
        return out.getvalue()

    @staticmethod
    def _rollup_csv(rows: List[Dict[str, Any]]) -> str:
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(
            ["start_utc", "end_utc", "count", "vrms_min", "vrms_avg", "vrms_max"]
        )
        for row in rows:
            w.writerow(
                [
                    _iso(int(row.get("start_ns") or 0)),
                    _iso(int(row.get("end_ns") or 0)),
                    row.get("count", ""),
                    row.get("vrms_min", ""),
                    row.get("vrms_avg", ""),
                    row.get("vrms_max", ""),
                ]
            )
        return out.getvalue()


pq_export_service = PqExportService()
