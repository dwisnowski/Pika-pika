"""Manual flicker notes and a ±2 minute search of the voltage already on disk."""

from __future__ import annotations

import csv
import io
import json
import math
import os
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None

from app.core.config import settings
from app.services.config_service import config_service
from app.services.event_service import event_service
from app.services.history_service import history_service

_CHART_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "flicker_export_chart.html"

WINDOW_S = 120
AWAY_FRACTION = 0.01
NOTCH_FRACTION = 0.85
MAX_NOTE_CHARS = 500
MAX_AGE_S = 7 * 24 * 3600
MAX_FUTURE_S = 5 * 60
LIST_LIMIT = 30

KINDS = {"lights", "tv", "both"}
TV_COUNTS = {"one", "several", "unsure"}
SAME_MOMENTS = {"together", "unsure"}
TV_SOURCES = {"internal", "external", "mixed", "unsure"}
RECOVERIES = {"av_continue", "reboot"}


def _pct_below(reference: float, value: float) -> Optional[float]:
    if reference is None or reference == 0 or value is None:
        return None
    return (reference - value) / reference * 100.0


def _pct_above(reference: float, value: float) -> Optional[float]:
    if reference is None or reference == 0 or value is None:
        return None
    return (value - reference) / reference * 100.0


def _bucket_ns(timestamps: List[int]) -> int:
    if len(timestamps) < 2:
        return 200_000_000
    deltas = [
        timestamps[i] - timestamps[i - 1]
        for i in range(1, len(timestamps))
        if timestamps[i] > timestamps[i - 1]
    ]
    if not deltas:
        return 200_000_000
    deltas.sort()
    return int(deltas[len(deltas) // 2])


def _longest_run(timestamps: List[int], flags: List[bool], bucket_ns: int) -> Optional[Dict[str, int]]:
    gap = max(bucket_ns * 2, 1)
    best = None
    i = 0
    n = len(flags)
    while i < n:
        if not flags[i]:
            i += 1
            continue
        j = i
        while (
            j + 1 < n
            and flags[j + 1]
            and timestamps[j + 1] - timestamps[j] <= gap
        ):
            j += 1
        dur = timestamps[j] - timestamps[i] + bucket_ns
        if best is None or dur > best["duration_ns"]:
            best = {
                "start_ns": timestamps[i],
                "end_ns": timestamps[j],
                "duration_ns": dur,
            }
        i = j + 1
    return best


def _chart_intervals(
    vrms: List[float], mins: List[float], maxs: List[float], timestamps: List[int], cap: int = 2000
) -> Dict[str, Any]:
    n = len(vrms)
    if n <= cap:
        samples, sample_mins, sample_maxs, stamps = vrms, mins, maxs, timestamps
    else:
        bucket = math.ceil(n / cap)
        samples, sample_mins, sample_maxs, stamps = [], [], [], []
        for i in range(0, n, bucket):
            end = min(i + bucket, n)
            chunk = vrms[i:end]
            samples.append(sum(chunk) / len(chunk))
            sample_mins.append(min(mins[i:end]))
            sample_maxs.append(max(maxs[i:end]))
            stamps.append(timestamps[end - 1])
    return {
        "samples": [round(float(v), 2) for v in samples],
        "samples_min": [round(float(v), 2) for v in sample_mins],
        "samples_max": [round(float(v), 2) for v in sample_maxs],
        "timestamps": [int(ts) for ts in stamps],
    }


def _median(values: List[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _ns_to_iso(ns: Optional[int]) -> str:
    if ns is None:
        return ""
    try:
        seconds = int(ns) / 1_000_000_000
        return (
            datetime.fromtimestamp(seconds, tz=timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
    except (OverflowError, OSError, ValueError):
        return ""


def _full_intervals(
    vrms: List[float], mins: List[float], maxs: List[float], timestamps: List[int]
) -> Dict[str, Any]:
    return {
        "samples": [round(float(v), 2) for v in vrms],
        "samples_min": [round(float(v), 2) for v in mins],
        "samples_max": [round(float(v), 2) for v in maxs],
        "timestamps": [int(ts) for ts in timestamps],
    }


def _notch(vrms: List[float], mins: List[float], maxs: List[float], timestamps: List[int]) -> Optional[Dict[str, Any]]:
    """A one-sided peak well below that interval's own Vrms."""
    best = None
    for v, mn, mx, ts in zip(vrms, mins, maxs, timestamps):
        if v <= 1.0:
            continue
        sided = min(abs(mn), abs(mx))
        if sided <= 1.0:
            continue
        implied = sided / math.sqrt(2.0)
        if implied >= v * NOTCH_FRACTION:
            continue
        drop = (v - implied) / v
        if best is None or drop > best["drop"]:
            best = {
                "drop": drop,
                "implied_vrms": round(implied, 1),
                "vrms": round(v, 1),
                "timestamp_ns": int(ts),
            }
    return best


def build_summary(note: Dict[str, Any], stats: Dict[str, Any]) -> str:
    """Plain-language reading of one ±2 minute window."""
    kind = note.get("kind") or "both"
    tv_count = note.get("tv_count")
    blank_s = note.get("blank_s")
    sentences: List[str] = []

    events = stats.get("events") or []
    if events:
        bits = []
        for event in events[:4]:
            dur = event.get("duration_ms")
            dur_s = f"{dur / 1000.0:.2f} s" if isinstance(dur, (int, float)) else "an unknown length"
            bits.append(
                f"{event.get('type', 'event')} to {event.get('peak_rms_v', '—')} V for {dur_s}"
            )
        extra = ""
        if len(events) > 4:
            extra = f" and {len(events) - 4} more"
        sentences.append(
            "Logged in this ±2 minutes: " + ", ".join(bits) + extra + "."
        )
    else:
        sentences.append("No sag or swell was logged in this ±2 minutes.")

    if not stats.get("interval_count"):
        sentences.append(
            "No voltage trend was stored for this window. It may have rotated off disk."
        )
        return " ".join(sentences)

    if stats.get("coverage") == "partial":
        sentences.append("The stored trend only covers part of this window.")

    low = stats.get("lowest_vrms_v")
    nominal = stats.get("nominal_v")
    median = stats.get("median_vrms_v")
    sag_v = stats.get("sag_log_v")
    if low is not None:
        vs_nom = stats.get("lowest_vs_nominal_pct")
        vs_med = stats.get("lowest_vs_median_pct")
        nom_bit = (
            f", {vs_nom:.1f}% below {nominal:.0f} V"
            if vs_nom is not None and nominal
            else ""
        )
        med_bit = (
            f", {vs_med:.1f}% below the local median of {median:.1f} V"
            if vs_med is not None and median
            else ""
        )
        sentences.append(
            f"The lowest interval Vrms was {low:.1f} V{nom_bit}{med_bit}."
        )

    high = stats.get("highest_vrms_v")
    if high is not None:
        high_nom = stats.get("highest_vs_nominal_pct")
        high_med = stats.get("highest_vs_median_pct")
        high_bits = []
        if high_nom is not None and nominal and abs(high_nom) >= 0.05:
            direction = "above" if high_nom >= 0 else "below"
            high_bits.append(f"{abs(high_nom):.1f}% {direction} {nominal:.0f} V")
        if high_med is not None and median and abs(high_med) >= 0.05:
            direction = "above" if high_med >= 0 else "below"
            high_bits.append(f"{abs(high_med):.1f}% {direction} the local median")
        tail = f" ({', '.join(high_bits)})" if high_bits else ""
        sentences.append(f"The highest interval Vrms was {high:.1f} V{tail}.")

    if low is not None and sag_v is not None and not events:
        if low <= sag_v + 0.05:
            sentences.append(
                f"That reached the sag log line ({sag_v:.0f} V)."
            )
        else:
            sentences.append(
                f"That stayed above the sag log line ({sag_v:.0f} V), so it did not appear in Recent Events."
            )

    run_s = float(stats.get("low_run_s") or 0.0)
    depth = stats.get("lowest_vs_median_pct") or 0.0
    if run_s >= 0.5 and run_s <= 2.0:
        sentences.append(
            f"The line was low for {run_s:.1f} s, about as long as a television dropout."
        )
    elif run_s > 2.0 and depth < 3.0:
        sentences.append(
            f"The line sat slightly low for {run_s:.1f} s. That is a slow change, not a brief dropout."
        )
    elif run_s > 2.0:
        sentences.append(
            f"The line was low for {run_s:.1f} s, longer than a picture blank of about a second."
        )
    elif run_s > 0:
        held = ""
        if kind in ("tv", "both"):
            held = " The set can hold the mute after a brief dip without rebooting."
        blank_label = f"{float(blank_s):.1f}" if blank_s else "0.8"
        sentences.append(
            f"The voltage move lasted {run_s:.1f} s, shorter than a {blank_label} s picture blank.{held}"
        )
    elif kind in ("tv", "both"):
        if tv_count == "several":
            sentences.append(
                "The line did not move for as long as the blackout. Several sets blanking together with a quiet line is unresolved."
            )
        elif tv_count == "one":
            sentences.append(
                "The line did not move for as long as the blackout. A quiet window on a single set points away from the mains."
            )
        else:
            sentences.append(
                "The line did not move for as long as the blackout. A short notch can still hide inside one 200 ms minimum."
            )

    notch = stats.get("notch")
    if notch:
        sentences.append(
            f"One 200 ms interval has a lopsided peak (about {notch['implied_vrms']:.0f} V versus that interval's {notch['vrms']:.0f} V average), so a shorter notch may be hidden there."
        )

    if kind in ("lights", "both") and depth >= 2.0:
        sentences.append("A dip of this size can dim lamps.")
    elif kind == "lights" and depth < 1.0 and run_s == 0:
        sentences.append(
            "The line barely moved. A fast repetitive wobble can still flicker a lamp after the 200 ms average smooths it."
        )

    if kind in ("tv", "both") and blank_s and run_s >= 0.5:
        sentences.append(
            f"The note says the picture was gone for about {float(blank_s):.1f} s."
        )

    return " ".join(sentences)


class ObservationService:
    def __init__(self, data_dir: str, history=None, events=None, config=None):
        self.data_dir = data_dir
        self.history = history if history is not None else history_service
        self.events = events if events is not None else event_service
        self.config = config if config is not None else config_service

    def _path(self) -> str:
        return os.path.join(self.data_dir, "observations.jsonl")

    def _read_all(self) -> List[dict]:
        path = self._path()
        if not os.path.exists(path):
            return []
        notes = []
        try:
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        notes.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError as exc:
            print(f"[ObservationService] Error reading notes: {exc}")
        return notes

    def _append(self, note: dict) -> None:
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self._path(), "a", encoding="utf-8") as handle:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.write(json.dumps(note, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def list_notes(self, limit: int = LIST_LIMIT) -> List[dict]:
        notes = self._read_all()
        slim = []
        for note in notes[-limit:]:
            slim.append(self._public_note(note, include_match=False))
        slim.reverse()
        return slim

    def get_note(self, note_id: str) -> Optional[dict]:
        for note in reversed(self._read_all()):
            if note.get("id") == note_id:
                return self._with_correlation(note)
        return None

    def create_note(self, body: dict) -> dict:
        note = self._validate(body)
        note["id"] = uuid.uuid4().hex
        note["created_at_ns"] = time.time_ns()
        correlated = self._with_correlation(note)
        stored = dict(note)
        stored["summary"] = correlated["correlation"]["summary"]
        stored["lowest_vrms_v"] = correlated["correlation"].get("lowest_vrms_v")
        stored["low_run_s"] = correlated["correlation"].get("low_run_s")
        stored["event_count"] = len(correlated["correlation"].get("events") or [])
        self._append(stored)
        return correlated

    def correlate(self, note: dict, *, full_intervals: bool = False) -> dict:
        observed = int(note["observed_at_ns"])
        half = WINDOW_S * 1_000_000_000
        start_ns = observed - half
        end_ns = observed + half

        nominal = float(self.config.get_target_mains_vrms())
        sag_pct = float(self.config.get_sag_threshold_pct())
        swell_pct = float(self.config.get_swell_threshold_pct())
        sag_v = nominal * (1.0 + sag_pct / 100.0)
        swell_v = nominal * (1.0 + swell_pct / 100.0)

        intervals = self.history.intervals_between(start_ns, end_ns)
        vrms = [float(v) for v in intervals.get("samples") or []]
        mins = [float(v) for v in intervals.get("samples_min") or []]
        maxs = [float(v) for v in intervals.get("samples_max") or []]
        timestamps = [int(v) for v in intervals.get("timestamps") or []]

        events = self.events.events_between(start_ns, end_ns)
        event_rows = [
            {
                "id": event.get("id"),
                "type": event.get("type"),
                "timestamp": event.get("timestamp"),
                "peak_rms_v": event.get("peak_rms_v"),
                "duration_ms": event.get("duration_ms"),
                "needs_review": event.get("needs_review"),
            }
            for event in events
        ]

        stats: Dict[str, Any] = {
            "window_s": WINDOW_S,
            "window_start_ns": start_ns,
            "window_end_ns": end_ns,
            "nominal_v": round(nominal, 1),
            "sag_log_v": round(sag_v, 1),
            "swell_log_v": round(swell_v, 1),
            "interval_count": len(vrms),
            "coverage": "none",
            "events": event_rows,
            "low_run_s": 0.0,
            "intervals": {"samples": [], "samples_min": [], "samples_max": [], "timestamps": []},
        }

        if not vrms:
            stats["summary"] = build_summary(note, stats)
            return stats

        bucket = _bucket_ns(timestamps)
        if timestamps[0] <= start_ns + bucket and timestamps[-1] >= end_ns - bucket:
            stats["coverage"] = "full"
        else:
            stats["coverage"] = "partial"

        median = _median(vrms)
        low_i = min(range(len(vrms)), key=lambda i: vrms[i])
        high_i = max(range(len(vrms)), key=lambda i: vrms[i])
        low_flags = [v <= median * (1.0 - AWAY_FRACTION) for v in vrms]
        high_flags = [v >= median * (1.0 + AWAY_FRACTION) for v in vrms]
        low_run = _longest_run(timestamps, low_flags, bucket)
        high_run = _longest_run(timestamps, high_flags, bucket)
        notch = _notch(vrms, mins, maxs, timestamps)

        stats.update({
            "median_vrms_v": round(median, 2),
            "lowest_vrms_v": round(vrms[low_i], 2),
            "lowest_vrms_ns": timestamps[low_i],
            "lowest_vs_nominal_pct": round(_pct_below(nominal, vrms[low_i]) or 0.0, 2),
            "lowest_vs_median_pct": round(_pct_below(median, vrms[low_i]) or 0.0, 2),
            "highest_vrms_v": round(vrms[high_i], 2),
            "highest_vrms_ns": timestamps[high_i],
            "highest_vs_nominal_pct": round(_pct_above(nominal, vrms[high_i]) or 0.0, 2),
            "highest_vs_median_pct": round(_pct_above(median, vrms[high_i]) or 0.0, 2),
            "low_run_s": round((low_run["duration_ns"] / 1e9), 2) if low_run else 0.0,
            "low_run_start_ns": low_run["start_ns"] if low_run else None,
            "low_run_end_ns": low_run["end_ns"] if low_run else None,
            "high_run_s": round((high_run["duration_ns"] / 1e9), 2) if high_run else 0.0,
            "notch": notch,
        })
        if full_intervals:
            stats["intervals"] = _full_intervals(vrms, mins, maxs, timestamps)
        else:
            stats["intervals"] = _chart_intervals(vrms, mins, maxs, timestamps)
        stats["summary"] = build_summary(note, stats)
        return stats

    def export_zip(self) -> bytes:
        """Build notes.csv, windows.csv, and chart.html for all stored notes."""
        notes = list(reversed(self._read_all()))
        note_rows: List[Dict[str, Any]] = []
        window_rows: List[Dict[str, Any]] = []
        chart_notes: List[Dict[str, Any]] = []

        for note in notes:
            stats = self.correlate(note, full_intervals=True)
            note_rows.append(self._export_note_row(note, stats))
            window_rows.extend(self._export_window_rows(note, stats))
            chart_notes.append(self._export_chart_note(note, stats))

        notes_csv = self._csv_bytes(
            note_rows,
            [
                "id", "kind", "note", "tv_count", "same_moment", "tv_source", "blank_s", "recovery",
                "created_at_iso", "observed_at_iso", "observed_at_ns",
                "window_start_iso", "window_end_iso",
                "nominal_v", "median_vrms_v",
                "lowest_vrms_v", "lowest_vrms_iso", "lowest_vs_nominal_pct", "lowest_vs_median_pct",
                "highest_vrms_v", "highest_vrms_iso",
                "low_run_s", "high_run_s", "event_count", "event_types", "coverage", "summary",
            ],
        )
        windows_csv = self._csv_bytes(
            window_rows,
            [
                "note_id", "kind", "observed_at_iso",
                "timestamp_iso", "timestamp_ns", "vrms_v", "vmin_v", "vmax_v",
            ],
        )
        chart_html = self._render_chart_html(chart_notes)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("notes.csv", notes_csv)
            zf.writestr("windows.csv", windows_csv)
            zf.writestr("chart.html", chart_html)
        return buf.getvalue()

    @staticmethod
    def _csv_bytes(rows: List[Dict[str, Any]], fieldnames: List[str]) -> bytes:
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
        return out.getvalue().encode("utf-8")

    @staticmethod
    def _export_note_row(note: dict, stats: dict) -> Dict[str, Any]:
        events = stats.get("events") or []
        types = [str(e.get("type") or "") for e in events if e.get("type")]
        return {
            "id": note.get("id") or "",
            "kind": note.get("kind") or "",
            "note": note.get("note") or "",
            "tv_count": note.get("tv_count") if note.get("tv_count") is not None else "",
            "same_moment": note.get("same_moment") if note.get("same_moment") is not None else "",
            "tv_source": note.get("tv_source") if note.get("tv_source") is not None else "",
            "blank_s": note.get("blank_s") if note.get("blank_s") is not None else "",
            "recovery": note.get("recovery") if note.get("recovery") is not None else "",
            "created_at_iso": _ns_to_iso(note.get("created_at_ns")),
            "observed_at_iso": _ns_to_iso(note.get("observed_at_ns")),
            "observed_at_ns": note.get("observed_at_ns") or "",
            "window_start_iso": _ns_to_iso(stats.get("window_start_ns")),
            "window_end_iso": _ns_to_iso(stats.get("window_end_ns")),
            "nominal_v": stats.get("nominal_v", ""),
            "median_vrms_v": stats.get("median_vrms_v", ""),
            "lowest_vrms_v": stats.get("lowest_vrms_v", ""),
            "lowest_vrms_iso": _ns_to_iso(stats.get("lowest_vrms_ns")),
            "lowest_vs_nominal_pct": stats.get("lowest_vs_nominal_pct", ""),
            "lowest_vs_median_pct": stats.get("lowest_vs_median_pct", ""),
            "highest_vrms_v": stats.get("highest_vrms_v", ""),
            "highest_vrms_iso": _ns_to_iso(stats.get("highest_vrms_ns")),
            "low_run_s": stats.get("low_run_s", ""),
            "high_run_s": stats.get("high_run_s", ""),
            "event_count": len(events),
            "event_types": "|".join(types),
            "coverage": stats.get("coverage") or "",
            "summary": stats.get("summary") or note.get("summary") or "",
        }

    @staticmethod
    def _export_window_rows(note: dict, stats: dict) -> List[Dict[str, Any]]:
        intervals = stats.get("intervals") or {}
        samples = intervals.get("samples") or []
        mins = intervals.get("samples_min") or []
        maxs = intervals.get("samples_max") or []
        stamps = intervals.get("timestamps") or []
        observed_iso = _ns_to_iso(note.get("observed_at_ns"))
        note_id = note.get("id") or ""
        kind = note.get("kind") or ""
        rows = []
        for i, ts in enumerate(stamps):
            rows.append({
                "note_id": note_id,
                "kind": kind,
                "observed_at_iso": observed_iso,
                "timestamp_iso": _ns_to_iso(ts),
                "timestamp_ns": ts,
                "vrms_v": samples[i] if i < len(samples) else "",
                "vmin_v": mins[i] if i < len(mins) else "",
                "vmax_v": maxs[i] if i < len(maxs) else "",
            })
        return rows

    @staticmethod
    def _export_chart_note(note: dict, stats: dict) -> Dict[str, Any]:
        intervals = stats.get("intervals") or {}
        samples = intervals.get("samples") or []
        stamps = intervals.get("timestamps") or []
        observed_ns = int(note.get("observed_at_ns") or 0)
        events = []
        for event in stats.get("events") or []:
            ts = event.get("timestamp")
            if ts is None:
                continue
            events.append({
                "t_ms": int(ts) / 1_000_000.0,
                "type": event.get("type") or "event",
                "peak_rms_v": event.get("peak_rms_v"),
            })
        marker_y = stats.get("lowest_vrms_v")
        if marker_y is None and samples:
            # Nearest sample to observed time
            best_i = min(range(len(stamps)), key=lambda i: abs(stamps[i] - observed_ns))
            marker_y = samples[best_i]
        return {
            "id": note.get("id") or "",
            "kind": note.get("kind") or "",
            "note": note.get("note") or "",
            "observed_at_ms": observed_ns / 1_000_000.0,
            "observed_at_iso": _ns_to_iso(observed_ns),
            "summary": stats.get("summary") or note.get("summary") or "",
            "nominal_v": stats.get("nominal_v"),
            "lowest_vrms_v": stats.get("lowest_vrms_v"),
            "marker_y": marker_y,
            "series": {
                "t_ms": [int(ts) / 1_000_000.0 for ts in stamps],
                "vrms": [float(v) for v in samples],
            },
            "events": events,
        }

    @staticmethod
    def _render_chart_html(chart_notes: List[Dict[str, Any]]) -> str:
        template = _CHART_TEMPLATE_PATH.read_text(encoding="utf-8")
        payload = json.dumps({"notes": chart_notes}, separators=(",", ":"))
        # Escape </script> so inlined JSON cannot break out of the script tag.
        safe_payload = payload.replace("<", "\\u003c")
        return template.replace("__PAYLOAD__", safe_payload)

    def _with_correlation(self, note: dict) -> dict:
        public = self._public_note(note, include_match=True)
        public["correlation"] = self.correlate(note)
        return public

    @staticmethod
    def _public_note(note: dict, include_match: bool) -> dict:
        public = {
            "id": note.get("id"),
            "created_at_ns": note.get("created_at_ns"),
            "observed_at_ns": note.get("observed_at_ns"),
            "window_s": WINDOW_S,
            "kind": note.get("kind"),
            "note": note.get("note") or "",
            "tv_count": note.get("tv_count"),
            "same_moment": note.get("same_moment"),
            "tv_source": note.get("tv_source"),
            "blank_s": note.get("blank_s"),
            "recovery": note.get("recovery"),
            "summary": note.get("summary") or "",
            "lowest_vrms_v": note.get("lowest_vrms_v"),
            "low_run_s": note.get("low_run_s"),
            "event_count": note.get("event_count"),
        }
        if not include_match:
            return public
        return public

    def _validate(self, body: dict) -> dict:
        if not isinstance(body, dict):
            raise ValueError("Expected a JSON object")
        kind = str(body.get("kind") or "").strip().lower()
        if kind not in KINDS:
            raise ValueError("kind must be lights, tv, or both")

        try:
            observed_ms = int(body.get("observed_at_ms"))
        except (TypeError, ValueError):
            raise ValueError("observed_at_ms is required")
        observed_ns = observed_ms * 1_000_000
        now_ns = time.time_ns()
        if observed_ns > now_ns + MAX_FUTURE_S * 1_000_000_000:
            raise ValueError("Time is too far in the future")
        if observed_ns < now_ns - MAX_AGE_S * 1_000_000_000:
            raise ValueError("Time is older than 7 days")

        text = str(body.get("note") or "").strip()
        if len(text) > MAX_NOTE_CHARS:
            raise ValueError(f"Note must be {MAX_NOTE_CHARS} characters or fewer")

        note: Dict[str, Any] = {
            "observed_at_ns": observed_ns,
            "window_s": WINDOW_S,
            "kind": kind,
            "note": text,
        }
        if kind == "lights":
            return note

        tv_count = str(body.get("tv_count") or "unsure").strip().lower()
        if tv_count not in TV_COUNTS:
            raise ValueError("tv_count must be one, several, or unsure")
        same = body.get("same_moment")
        if tv_count == "several":
            same = str(same or "unsure").strip().lower()
            if same not in SAME_MOMENTS:
                raise ValueError("same_moment must be together or unsure")
        else:
            same = None

        source = str(body.get("tv_source") or "unsure").strip().lower()
        if source not in TV_SOURCES:
            raise ValueError("tv_source must be internal, external, mixed, or unsure")

        try:
            blank_s = float(body.get("blank_s", 0.8))
        except (TypeError, ValueError):
            raise ValueError("blank_s must be a number of seconds")
        if not (0.1 <= blank_s <= 10.0):
            raise ValueError("blank_s must be between 0.1 and 10 seconds")

        recovery = str(body.get("recovery") or "av_continue").strip().lower()
        if recovery not in RECOVERIES:
            raise ValueError("recovery must be av_continue or reboot")

        note.update({
            "tv_count": tv_count,
            "same_moment": same,
            "tv_source": source,
            "blank_s": round(blank_s, 2),
            "recovery": recovery,
        })
        return note


observation_service = ObservationService(settings.data_dir)
