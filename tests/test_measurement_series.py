"""Tests for persisted contributing-measurement series and aggregation invariants."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from actintrack_app.measurement_series import (
    MetricId,
    aggregate_general_movement_um_s,
    aggregate_optical_flow_um_s,
    aggregate_orientation_median_deg,
    aggregate_toward_nucleus_um_s,
    load_general_movement_series,
    load_optical_flow_series,
    load_orientation_series,
    load_toward_nucleus_series,
    verify_series_matches_summary,
)
from actintrack_app.project_manager import create_project_structure
from actintrack_app.schema_compat import (
    draft_optical_flow_path,
    draft_structural_orientation_path,
    draft_tracking_path,
)


class AggregationHelpersTests(unittest.TestCase):
    def test_general_movement_mean(self) -> None:
        self.assertAlmostEqual(
            aggregate_general_movement_um_s([1.0, 3.0, 5.0]),
            3.0,
        )

    def test_toward_nucleus_time_weighted(self) -> None:
        # ΣΔd=3 over Σdt=2 → 1.5 (not mean of 1 and 2)
        self.assertAlmostEqual(
            aggregate_toward_nucleus_um_s([1.0, 2.0], [1.0, 1.0]),
            1.5,
        )

    def test_orientation_median(self) -> None:
        self.assertAlmostEqual(
            aggregate_orientation_median_deg([10.0, 20.0, 90.0]),
            20.0,
        )

    def test_optical_flow_pair_mean_to_um_s(self) -> None:
        self.assertAlmostEqual(
            aggregate_optical_flow_um_s(
                [2.0, 4.0],
                microns_per_pixel=0.5,
                seconds_per_frame=0.5,
            ),
            3.0,  # mean px=3 → 3*0.5/0.5
        )


class PersistedSeriesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        create_project_structure(self.root)
        self.sid = "S001"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_general_movement_series_from_draft(self) -> None:
        path = draft_tracking_path(self.root, self.sid)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "analysis_run_id": "run-gm",
            "general_movement_index_um_per_s": 2.0,
            "tracking_result": {
                "tracks": [
                    {
                        "track_id": 1,
                        "valid_steps": [
                            {
                                "prev_frame_index": 0,
                                "frame_index": 1,
                                "frame_gap": 1,
                                "dx_px": 1.0,
                                "dy_px": 0.0,
                                "absolute_velocity_um_per_s": 1.0,
                            },
                            {
                                "prev_frame_index": 1,
                                "frame_index": 2,
                                "frame_gap": 1,
                                "dx_px": 2.0,
                                "dy_px": 0.0,
                                "absolute_velocity_um_per_s": 3.0,
                            },
                        ],
                    }
                ]
            },
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        series = load_general_movement_series(self.root, self.sid)
        self.assertTrue(series.available)
        self.assertEqual(series.measurement_count, 2)
        self.assertEqual(series.analysis_run_id, "run-gm")
        self.assertTrue(verify_series_matches_summary(series))

    def test_toward_nucleus_series_sign_and_formula(self) -> None:
        path = draft_tracking_path(self.root, self.sid)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "analysis_run_id": "run-tn",
            "toward_nucleus_velocity_um_per_s": 0.25,
            "tracking_result": {
                "tracks": [
                    {
                        "track_id": 7,
                        "valid_steps": [
                            {
                                "prev_frame_index": 0,
                                "frame_index": 1,
                                "toward_velocity_um_per_s": 1.0,
                                "delta_distance_um": 1.0,
                                "dt_s": 1.0,
                            },
                            {
                                "prev_frame_index": 1,
                                "frame_index": 2,
                                "toward_velocity_um_per_s": -0.5,
                                "delta_distance_um": -0.5,
                                "dt_s": 1.0,
                            },
                        ],
                    }
                ]
            },
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        series = load_toward_nucleus_series(self.root, self.sid)
        self.assertEqual(series.rows[0]["sign"], "toward")
        self.assertEqual(series.rows[1]["sign"], "away")
        self.assertTrue(verify_series_matches_summary(series))

    def test_optical_flow_frame_pair_series(self) -> None:
        path = draft_optical_flow_path(self.root, self.sid)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "analysis_run_id": "run-of",
            "has_valid_result": True,
            "optical_flow_general_movement_um_s": 3.0,
            "settings": {"microns_per_pixel": 0.5, "seconds_per_frame": 0.5},
            "frame_pair_summaries": [
                {
                    "frame_a": 0,
                    "frame_b": 1,
                    "mean_magnitude_px_frame": 2.0,
                    "valid_pixel_count": 10,
                },
                {
                    "frame_a": 1,
                    "frame_b": 2,
                    "mean_magnitude_px_frame": 4.0,
                    "valid_pixel_count": 12,
                },
            ],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        series = load_optical_flow_series(self.root, self.sid)
        self.assertEqual(series.row_kind, "frame_pair")
        self.assertEqual(series.measurement_count, 2)
        self.assertTrue(
            verify_series_matches_summary(
                series, microns_per_pixel=0.5, seconds_per_frame=0.5
            )
        )

    def test_orientation_series_median(self) -> None:
        path = draft_structural_orientation_path(self.root, self.sid)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "analysis_run_id": "run-ori",
            "has_valid_result": True,
            "median_angle_relative_nucleus_deg": 20.0,
            "measurements": [
                {"angle_relative_nucleus_deg": 10.0, "x_px": 1, "y_px": 2, "coherence": 0.5},
                {"angle_relative_nucleus_deg": 20.0, "x_px": 3, "y_px": 4, "coherence": 0.6},
                {"angle_relative_nucleus_deg": 90.0, "x_px": 5, "y_px": 6, "coherence": 0.7},
            ],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        series = load_orientation_series(self.root, self.sid)
        self.assertEqual(series.metric_id, MetricId.ORIENTATION)
        self.assertTrue(verify_series_matches_summary(series))


if __name__ == "__main__":
    unittest.main()
