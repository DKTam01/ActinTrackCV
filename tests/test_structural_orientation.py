"""Tests for production structural F-actin orientation (Phase R7B)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from actintrack_app.gui import MainWindow
from actintrack_app.schema_compat import (
    draft_structural_orientation_path,
    resolve_draft_structural_orientation_path,
)
from actintrack_app.structural_orientation import (
    ALGORITHM_NAME,
    StructuralOrientationSettings,
    compute_structural_orientation,
    render_structural_orientation_overlay,
    result_from_dict,
)


def _cable_frame(angle_deg: float, *, weak: bool = False) -> np.ndarray:
    rng = np.random.default_rng(707 + int(angle_deg * 10))
    frame = rng.normal(10.0, 3.0, (128, 128)).clip(0, 255).astype(np.uint8)
    center = np.array([88.0, 64.0])
    direction = np.array(
        [np.cos(np.deg2rad(angle_deg)), np.sin(np.deg2rad(angle_deg))]
    )
    p0 = tuple(np.round(center - direction * 25).astype(int))
    p1 = tuple(np.round(center + direction * 25).astype(int))
    cv2.line(frame, p0, p1, 55 if weak else 220, 3, cv2.LINE_AA)
    return cv2.GaussianBlur(frame, (3, 3), 0)


class StructuralOrientationScientificTests(unittest.TestCase):
    def setUp(self) -> None:
        self.nucleus = (20.0, 64.0)
        self.settings = StructuralOrientationSettings(
            threshold_percentile=70.0,
            tensor_window_size_px=15,
            sample_spacing_px=4,
            minimum_coherence=0.2,
        )

    def test_known_relative_angles_near_reference_location(self) -> None:
        for expected in (0.0, 30.0, 45.0, 60.0, 90.0):
            with self.subTest(expected=expected):
                result = compute_structural_orientation(
                    _cable_frame(expected),
                    nucleus_xy_px=self.nucleus,
                    settings=self.settings,
                    reference_frame_index=3,
                )
                self.assertTrue(result.has_valid_result, result.failure_reason)
                nearest = min(
                    result.measurements,
                    key=lambda item: np.hypot(item.x_px - 88.0, item.y_px - 64.0),
                )
                self.assertLess(
                    abs(nearest.angle_relative_nucleus_deg - expected),
                    8.0,
                )
                self.assertEqual(result.reference_frame_index, 3)

    def test_missing_nucleus_is_explicit_non_result(self) -> None:
        result = compute_structural_orientation(
            _cable_frame(30.0),
            nucleus_xy_px=None,
            settings=self.settings,
            sample_id="sample_1",
        )
        self.assertFalse(result.has_valid_result)
        self.assertIn("NucleusReference", result.failure_reason)
        payload = result.summary_dict()
        self.assertNotIn("nucleus_reference", payload)
        self.assertEqual(payload["measurements"], [])

    def test_valid_mask_is_respected(self) -> None:
        frame = _cable_frame(45.0)
        valid = np.zeros(frame.shape, dtype=bool)
        valid[35:95, 55:110] = True
        result = compute_structural_orientation(
            frame,
            nucleus_xy_px=self.nucleus,
            valid_mask=valid,
            settings=self.settings,
        )
        self.assertTrue(result.has_valid_result)
        for measurement in result.measurements:
            self.assertTrue(
                valid[int(measurement.y_px), int(measurement.x_px)]
            )

    def test_weak_cable_produces_multiple_local_measurements(self) -> None:
        result = compute_structural_orientation(
            _cable_frame(30.0, weak=True),
            nucleus_xy_px=self.nucleus,
            settings=self.settings,
        )
        self.assertTrue(result.has_valid_result, result.failure_reason)
        self.assertGreaterEqual(
            len(result.measurements),
            self.settings.minimum_measurements,
        )

    def test_payload_preserves_multiple_measurements_and_definition(self) -> None:
        result = compute_structural_orientation(
            _cable_frame(60.0),
            nucleus_xy_px=self.nucleus,
            settings=self.settings,
            sample_id="sample_1",
        )
        payload = result.summary_dict()
        self.assertEqual(payload["algorithm"], ALGORITHM_NAME)
        self.assertGreater(payload["measurement_count"], 3)
        self.assertEqual(
            len(payload["measurements"]),
            payload["measurement_count"],
        )
        self.assertTrue(
            payload["angle_definition"]["traversal_direction_invariant"]
        )
        self.assertTrue(payload["angle_definition"]["not_motion_or_trajectory_angle"])

    def test_round_trip_preserves_measurements_and_provenance(self) -> None:
        original = compute_structural_orientation(
            _cable_frame(45.0),
            nucleus_xy_px=self.nucleus,
            settings=self.settings,
            sample_id="sample_1",
            reference_frame_index=2,
        )
        restored = result_from_dict(original.summary_dict())
        self.assertEqual(restored.sample_id, "sample_1")
        self.assertEqual(restored.reference_frame_index, 2)
        self.assertEqual(
            len(restored.measurements),
            len(original.measurements),
        )
        self.assertEqual(restored.nucleus_reference_xy_px, self.nucleus)

    def test_overlay_contains_nucleus_and_sparse_tangents(self) -> None:
        frame = _cable_frame(45.0)
        result = compute_structural_orientation(
            frame,
            nucleus_xy_px=self.nucleus,
            settings=self.settings,
        )
        overlay = render_structural_orientation_overlay(
            frame,
            result,
            maximum_glyphs=20,
        )
        self.assertEqual(overlay.shape, (128, 128, 3))
        self.assertFalse(
            np.array_equal(overlay, cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR))
        )


class StructuralOrientationPathTests(unittest.TestCase):
    def test_draft_path_is_sample_scoped_and_resolvable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = draft_structural_orientation_path(root, "sample_1")
            self.assertEqual(
                path,
                root.resolve()
                / "metadata"
                / "draft_structural_orientation"
                / "sample_1.json",
            )
            self.assertIsNone(
                resolve_draft_structural_orientation_path(root, "sample_1")
            )
            path.parent.mkdir(parents=True)
            path.write_text("{}", encoding="utf-8")
            self.assertEqual(
                resolve_draft_structural_orientation_path(root, "sample_1"),
                path,
            )

    def test_gui_draft_writer_persists_versioned_result(self) -> None:
        result = compute_structural_orientation(
            _cable_frame(30.0),
            nucleus_xy_px=(20.0, 64.0),
            sample_id="sample_1",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            window = MainWindow.__new__(MainWindow)
            window._project_root = root
            MainWindow._save_draft_structural_orientation_result(
                window,
                "sample_1",
                result,
            )
            path = draft_structural_orientation_path(root, "sample_1")
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(payload["has_valid_result"])
        self.assertEqual(payload["algorithm"], ALGORITHM_NAME)
        self.assertGreater(payload["measurement_count"], 3)


if __name__ == "__main__":
    unittest.main()
