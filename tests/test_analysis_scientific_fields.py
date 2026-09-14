"""Tests for Analysis service loading of R6/R7 scientific result fields."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from actintrack_app.analysis_service import (
    _merge_sample_metrics,
    load_structural_orientation_metrics_for_sample,
    load_tracking_metrics_for_sample,
)
from actintrack_app.schema_compat import (
    draft_structural_orientation_path,
    draft_tracking_path,
)


class AnalysisScientificFieldsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_tracking_payload_reads_toward_nucleus_and_legacy_ok(self) -> None:
        path = draft_tracking_path(self.root, "WT550_0001")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "num_tracks_with_valid_steps": 2,
                    "num_tracks_started": 2,
                    "total_valid_steps": 8,
                    "absolute_velocity_index_um_per_s": 0.05,
                    "general_movement_index_um_per_s": 0.05,
                    "downward_velocity_index_um_per_s": 0.01,
                    "toward_nucleus_velocity_um_per_s": 0.02,
                }
            ),
            encoding="utf-8",
        )
        metrics = load_tracking_metrics_for_sample(self.root, "WT550_0001")
        self.assertTrue(metrics.has_valid_result)
        self.assertEqual(metrics.general_movement, 0.05)
        self.assertEqual(metrics.toward_nucleus_velocity, 0.02)

    def test_legacy_tracking_payload_omits_toward_nucleus(self) -> None:
        path = draft_tracking_path(self.root, "LEGACY_1")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "num_tracks_with_valid_steps": 1,
                    "total_valid_steps": 3,
                    "absolute_velocity_index_um_per_s": 1.0,
                    "downward_velocity_index_um_per_s": 0.4,
                }
            ),
            encoding="utf-8",
        )
        metrics = load_tracking_metrics_for_sample(self.root, "LEGACY_1")
        self.assertTrue(metrics.has_valid_result)
        self.assertIsNone(metrics.toward_nucleus_velocity)

    def test_structural_orientation_loader_success_and_missing(self) -> None:
        missing = load_structural_orientation_metrics_for_sample(self.root, "NONE")
        self.assertFalse(missing.orientation_has_valid_result)

        path = draft_structural_orientation_path(self.root, "WT550_0001")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "has_valid_result": True,
                    "median_angle_relative_nucleus_deg": 41.2,
                    "mean_angle_relative_nucleus_deg": 39.0,
                    "measurement_count": 15,
                    "mean_coherence": 0.7,
                }
            ),
            encoding="utf-8",
        )
        metrics = load_structural_orientation_metrics_for_sample(
            self.root, "WT550_0001"
        )
        self.assertTrue(metrics.orientation_has_valid_result)
        self.assertEqual(metrics.orientation_median_deg, 41.2)
        self.assertEqual(metrics.orientation_measurement_count, 15)

    def test_merge_keeps_methods_separate(self) -> None:
        from actintrack_app.analysis_service import SampleMetrics

        template = SampleMetrics(
            general_movement=1.0,
            downward_velocity=0.2,
            has_valid_result=True,
            toward_nucleus_velocity=0.3,
        )
        optical = SampleMetrics(
            of_general_movement=2.0,
            of_has_valid_result=True,
        )
        orientation = SampleMetrics(
            orientation_median_deg=45.0,
            orientation_measurement_count=9,
            orientation_has_valid_result=True,
        )
        merged = _merge_sample_metrics(template, optical, orientation)
        self.assertEqual(merged.general_movement, 1.0)
        self.assertEqual(merged.of_general_movement, 2.0)
        self.assertEqual(merged.toward_nucleus_velocity, 0.3)
        self.assertEqual(merged.orientation_median_deg, 45.0)
        self.assertEqual(merged.orientation_measurement_count, 9)

    def test_current_payload_motion_index_aliases_general_movement(self) -> None:
        path = draft_tracking_path(self.root, "ALIAS_1")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "num_tracks_with_valid_steps": 1,
                    "total_valid_steps": 2,
                    "absolute_velocity_index_um_per_s": 0.44,
                    "general_movement_index_um_per_s": 0.44,
                    "primary_velocity_index_um_per_s": 0.44,
                    "downward_velocity_index_um_per_s": 0.11,
                }
            ),
            encoding="utf-8",
        )
        metrics = load_tracking_metrics_for_sample(self.root, "ALIAS_1")
        self.assertEqual(metrics.general_movement, 0.44)
        self.assertEqual(metrics.motion_index, 0.44)
        self.assertEqual(metrics.downward_velocity, 0.11)

    def test_group_means_use_available_values_only(self) -> None:
        from actintrack_app.analysis_service import (
            SampleAnalysisRow,
            SampleMetrics,
            compute_breed_analysis,
        )

        with_nucleus = SampleAnalysisRow(
            breed="Control",
            sample_label="Sample 1",
            batch_name="a",
            status="ok",
            data_status="ok",
            metrics=SampleMetrics(
                general_movement=0.10,
                downward_velocity=0.04,
                motion_index=0.10,
                of_general_movement=0.20,
                toward_nucleus_velocity=0.30,
                orientation_median_deg=40.0,
                has_valid_result=True,
                of_has_valid_result=True,
                orientation_has_valid_result=True,
            ),
        )
        without_nucleus = SampleAnalysisRow(
            breed="Control",
            sample_label="Sample 2",
            batch_name="b",
            status="ok",
            data_status="ok",
            metrics=SampleMetrics(
                general_movement=0.20,
                downward_velocity=0.06,
                motion_index=0.20,
                of_general_movement=0.40,
                toward_nucleus_velocity=None,
                orientation_median_deg=None,
                has_valid_result=True,
                of_has_valid_result=True,
                orientation_has_valid_result=False,
            ),
        )
        summary = compute_breed_analysis("Control", [with_nucleus, without_nucleus])
        self.assertEqual(summary.sample_count, 2)
        self.assertEqual(summary.samples_with_results, 2)
        self.assertEqual(summary.samples_with_of_results, 2)
        self.assertEqual(summary.samples_with_toward_nucleus_results, 1)
        self.assertEqual(summary.samples_with_orientation_results, 1)
        self.assertAlmostEqual(summary.avg_general_movement, 0.15)
        self.assertAlmostEqual(summary.avg_of_general_movement, 0.30)
        self.assertAlmostEqual(summary.avg_toward_nucleus_velocity, 0.30)
        self.assertAlmostEqual(summary.avg_orientation_median_deg, 40.0)
        self.assertAlmostEqual(summary.avg_downward_velocity, 0.05)
        self.assertAlmostEqual(summary.avg_motion_index, 0.15)


if __name__ == "__main__":
    unittest.main()
