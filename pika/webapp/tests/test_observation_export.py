"""Smoke test for flicker note CSV + chart zip export."""

from __future__ import annotations

import csv
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
WEBAPP_ROOT = Path(__file__).resolve().parents[1]
if str(WEBAPP_ROOT) not in sys.path:
    sys.path.insert(0, str(WEBAPP_ROOT))

from app.services.observation_service import ObservationService, _ns_to_iso  # noqa: E402


class FakeHistory:
    def __init__(self, observed_ns: int):
        half = 120 * 1_000_000_000
        start = observed_ns - half
        # ~1 Hz for a compact fixture (still multi-point)
        self.timestamps = [start + i * 1_000_000_000 for i in range(241)]
        self.samples = [120.0 - (5.0 if i == 120 else 0.0) for i in range(241)]
        self.mins = [s - 0.5 for s in self.samples]
        self.maxs = [s + 0.5 for s in self.samples]

    def intervals_between(self, start_ns, end_ns):
        rows = [
            (ts, v, mn, mx)
            for ts, v, mn, mx in zip(self.timestamps, self.samples, self.mins, self.maxs)
            if start_ns <= ts <= end_ns
        ]
        return {
            "timestamps": [r[0] for r in rows],
            "samples": [r[1] for r in rows],
            "samples_min": [r[2] for r in rows],
            "samples_max": [r[3] for r in rows],
        }


class FakeEvents:
    def __init__(self, observed_ns: int):
        self.observed_ns = observed_ns

    def events_between(self, start_ns, end_ns):
        ts = self.observed_ns - 2_000_000_000
        if start_ns <= ts <= end_ns:
            return [{
                "id": 7,
                "type": "SAG",
                "timestamp": ts,
                "peak_rms_v": 102.0,
                "duration_ms": 80,
                "needs_review": False,
            }]
        return []


class FakeConfig:
    def get_target_mains_vrms(self):
        return 120.0

    def get_sag_threshold_pct(self):
        return -10.0

    def get_swell_threshold_pct(self):
        return 10.0


class ObservationExportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = self.tmp.name
        self.observed_ns = 1_700_000_000_000_000_000
        note = {
            "id": "abc123deadbeef",
            "created_at_ns": self.observed_ns + 60_000_000_000,
            "observed_at_ns": self.observed_ns,
            "window_s": 120,
            "kind": "lights",
            "note": "kitchen",
            "summary": "cached",
            "lowest_vrms_v": 115.0,
            "low_run_s": 1.0,
            "event_count": 1,
        }
        path = os.path.join(self.data_dir, "observations.jsonl")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(note) + "\n")

        self.service = ObservationService(
            self.data_dir,
            history=FakeHistory(self.observed_ns),
            events=FakeEvents(self.observed_ns),
            config=FakeConfig(),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_ns_to_iso(self):
        self.assertTrue(_ns_to_iso(self.observed_ns).endswith("Z"))
        self.assertEqual(_ns_to_iso(None), "")

    def test_export_zip_contents(self):
        blob = self.service.export_zip()
        self.assertGreater(len(blob), 100)

        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            names = set(zf.namelist())
            self.assertEqual(names, {"notes.csv", "windows.csv", "chart.html"})

            notes_text = zf.read("notes.csv").decode("utf-8")
            notes_reader = list(csv.DictReader(io.StringIO(notes_text)))
            self.assertEqual(len(notes_reader), 1)
            row = notes_reader[0]
            self.assertEqual(row["id"], "abc123deadbeef")
            self.assertEqual(row["kind"], "lights")
            self.assertEqual(row["note"], "kitchen")
            self.assertEqual(row["observed_at_ns"], str(self.observed_ns))
            self.assertTrue(row["observed_at_iso"].endswith("Z"))
            self.assertEqual(row["event_count"], "1")
            self.assertIn("SAG", row["event_types"])
            self.assertNotEqual(row["lowest_vrms_v"], "")
            self.assertIn("115", row["lowest_vrms_v"])

            windows_text = zf.read("windows.csv").decode("utf-8")
            windows_reader = list(csv.DictReader(io.StringIO(windows_text)))
            self.assertGreaterEqual(len(windows_reader), 200)
            self.assertEqual(windows_reader[0]["note_id"], "abc123deadbeef")
            self.assertTrue(windows_reader[0]["timestamp_iso"].endswith("Z"))

            html = zf.read("chart.html").decode("utf-8")
            self.assertIn("Flicker notes", html)
            self.assertIn("application/json", html)
            # Payload is inlined and escaped
            self.assertIn("abc123deadbeef", html)
            self.assertIn(str(self.observed_ns / 1_000_000.0), html)
            self.assertNotIn("__PAYLOAD__", html)

            # Extract JSON payload from the script tag
            start = html.index('type="application/json">') + len('type="application/json">')
            end = html.index("</script>", start)
            payload = json.loads(html[start:end])
            self.assertEqual(len(payload["notes"]), 1)
            chart_note = payload["notes"][0]
            self.assertEqual(chart_note["id"], "abc123deadbeef")
            self.assertEqual(chart_note["observed_at_ms"], self.observed_ns / 1_000_000.0)
            self.assertGreater(len(chart_note["series"]["t_ms"]), 100)
            self.assertEqual(len(chart_note["series"]["t_ms"]), len(chart_note["series"]["vrms"]))
            self.assertEqual(len(chart_note["events"]), 1)


if __name__ == "__main__":
    unittest.main()
