"""Tests for PQ summary export and interruption review labeling."""

from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from app.services.pq_export_service import PqExportService
from app.services.review_policy import evaluate_event_review


class ReviewInterruptionTest(unittest.TestCase):
    def test_interruption_type_needs_review(self):
        result = evaluate_event_review(
            event_type="INTERRUPTION",
            extreme_rms_v=5.0,
            duration_ms=50.0,
            nominal_vrms=120.0,
        )
        self.assertTrue(result["needs_review"])
        self.assertIn("Interruption", result["review_reason"])

    def test_legacy_deep_sag_still_interruption_class(self):
        result = evaluate_event_review(
            event_type="SAG",
            extreme_rms_v=8.0,
            duration_ms=50.0,
            nominal_vrms=120.0,
        )
        self.assertTrue(result["needs_review"])
        self.assertIn("legacy", result["review_reason"].lower())


class PqExportTest(unittest.TestCase):
    def test_export_zip_contents(self):
        history = {
            "samples": [120.0, 119.5],
            "samples_min": [-170.0, -169.0],
            "samples_max": [170.0, 169.0],
            "samples_qtr_min": [118.0, 117.5],
            "samples_qtr_max": [121.0, 120.5],
            "frequency_hz": [60.01, 59.98],
            "timestamps": [1_700_000_000_000_000_000, 1_700_000_000_200_000_000],
            "rollup_10min": [],
            "harmonics_note": "front-end limited",
        }
        events = [
            {
                "id": 1,
                "type": "INTERRUPTION",
                "timestamp": 1_700_000_000_000_000_000,
                "duration_ms": 40.0,
                "peak_rms_v": 4.0,
                "needs_review": True,
                "review_reason": "Interruption",
            }
        ]
        harmonics = [
            {"ts_ns": 1_700_000_000_000_000_000, "thd_pct": 2.5, "h": [100.0] + [0.5] * 31}
        ]

        with mock.patch(
            "app.services.pq_export_service.history_service.get_decimated_data",
            return_value=history,
        ), mock.patch(
            "app.services.pq_export_service.event_service.get_recent_events",
            return_value=events,
        ), mock.patch(
            "app.services.pq_export_service.history_service.get_harmonics_trend",
            return_value=harmonics,
        ), mock.patch(
            "app.services.pq_export_service.config_service.get_history_max_points",
            return_value=20000,
        ), mock.patch(
            "app.services.pq_export_service.config_service.get_history_window_minutes",
            return_value=60,
        ), mock.patch(
            "app.services.pq_export_service.config_service.get_history_display_points",
            return_value=800,
        ), mock.patch(
            "app.services.pq_export_service.config_service.get_target_mains_vrms",
            return_value=120.0,
        ):
            blob = PqExportService().export_zip()

        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            names = set(zf.namelist())
            self.assertIn("voltage_trend.csv", names)
            self.assertIn("events.csv", names)
            self.assertIn("frequency_summary.csv", names)
            self.assertIn("harmonics.csv", names)
            self.assertIn("summary.json", names)
            events_csv = zf.read("events.csv").decode()
            self.assertIn("INTERRUPTION", events_csv)


if __name__ == "__main__":
    unittest.main()
