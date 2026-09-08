"""Tests for signed nucleus-relative movement (Phase R6)."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from actintrack_app.gui import MainWindow
from actintrack_app.gui_result_views import (
    format_tracking_result_panel_lines,
    tracking_result_view_from_dict,
)
from actintrack_app.motion_index import (
    MotionIndexParams,
    PointTrack,
    TrackPoint,
    compute_nucleus_relative_summary,
    compute_step_metrics,
    save_trajectory_csv,
    serialize_video_tracking_result,
)
from actintrack_app.preview_workflow import analyze_cropped_preview
from actintrack_app.orientation import RectROI


def _params() -> MotionIndexParams:
    return MotionIndexParams(
        num_starting_points=1,
        min_point_spacing_px=6,
        search_radius_px=5,
        template_patch_size_px=5,
        min_template_confidence=0.15,
        microns_per_pixel=1.0,
        seconds_per_frame=1.0,
    )


def _step(
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    start_frame: int = 0,
    end_frame: int = 1,
    nucleus: tuple[float, float] = (0.0, 0.0),
):
    return compute_step_metrics(
        TrackPoint(0, start_frame, start[0], start[1], 1.0),
        TrackPoint(0, end_frame, end[0], end[1], 1.0),
        _params(),
        nucleus_xy_px=nucleus,
    )


class NucleusRelativeStepTests(unittest.TestCase):
    def test_pure_toward_is_positive(self) -> None:
        step = _step((10.0, 0.0), (8.0, 0.0))
        self.assertAlmostEqual(step.delta_distance_um or 0.0, 2.0)
        self.assertAlmostEqual(step.toward_velocity_um_per_s or 0.0, 2.0)

    def test_pure_away_is_negative(self) -> None:
        step = _step((8.0, 0.0), (10.0, 0.0))
        self.assertAlmostEqual(step.delta_distance_um or 0.0, -2.0)
        self.assertAlmostEqual(step.toward_velocity_um_per_s or 0.0, -2.0)

    def test_tangential_circle_step_is_zero_radial_change(self) -> None:
        step = _step((10.0, 0.0), (0.0, 10.0))
        self.assertAlmostEqual(step.delta_distance_um or 0.0, 0.0, places=10)
        self.assertGreater(step.displacement_um, 0.0)

    def test_zero_displacement_is_zero(self) -> None:
        step = _step((4.0, 3.0), (4.0, 3.0))
        self.assertAlmostEqual(step.toward_velocity_um_per_s or 0.0, 0.0)
        self.assertAlmostEqual(step.absolute_velocity_um_per_s, 0.0)

    def test_45_degree_toward_step_uses_radial_distance_difference(self) -> None:
        step = _step((10.0, 10.0), (9.0, 9.0))
        self.assertAlmostEqual(
            step.delta_distance_um or 0.0,
            np.sqrt(2.0),
            places=10,
        )
        self.assertAlmostEqual(
            step.absolute_velocity_um_per_s,
            np.sqrt(2.0),
            places=10,
        )

    def test_frame_gap_uses_actual_elapsed_time(self) -> None:
        step = _step(
            (10.0, 0.0),
            (6.0, 0.0),
            start_frame=1,
            end_frame=3,
        )
        self.assertEqual(step.frame_gap, 2)
        self.assertAlmostEqual(step.delta_distance_um or 0.0, 4.0)
        self.assertAlmostEqual(step.toward_velocity_um_per_s or 0.0, 2.0)

    def test_rotation_invariance(self) -> None:
        original = _step(
            (8.0, 3.0),
            (6.0, 2.0),
            nucleus=(1.0, -1.0),
        )
        rotated = _step(
            (-3.0, 8.0),
            (-2.0, 6.0),
            nucleus=(1.0, 1.0),
        )
        self.assertAlmostEqual(
            original.toward_velocity_um_per_s or 0.0,
            rotated.toward_velocity_um_per_s or 0.0,
            places=10,
        )

    def test_mirror_invariance(self) -> None:
        original = _step(
            (8.0, 3.0),
            (6.0, 2.0),
            nucleus=(1.0, -1.0),
        )
        mirrored = _step(
            (-8.0, 3.0),
            (-6.0, 2.0),
            nucleus=(-1.0, -1.0),
        )
        self.assertAlmostEqual(
            original.toward_velocity_um_per_s or 0.0,
            mirrored.toward_velocity_um_per_s or 0.0,
            places=10,
        )


class NucleusRelativePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.params = _params()
        self.track = PointTrack(
            track_id=0,
            start_x=10.0,
            start_y=0.0,
            points=[
                TrackPoint(0, 0, 10.0, 0.0, 1.0),
                TrackPoint(0, 2, 6.0, 0.0, 0.8, True),
            ],
            active=False,
            end_reason="reached_last_frame",
        )

    def test_video_and_track_summaries_use_signed_gap_aware_result(self) -> None:
        payload = serialize_video_tracking_result(
            [self.track],
            self.params,
            nucleus_xy_px=(0.0, 0.0),
        )
        video = payload["nucleus_relative_movement_summary"]
        track = payload["tracks"][0]["nucleus_relative_movement_summary"]
        self.assertAlmostEqual(
            video["time_weighted_toward_velocity_um_per_s"],
            2.0,
        )
        self.assertAlmostEqual(
            track["time_weighted_toward_velocity_um_per_s"],
            2.0,
        )
        self.assertEqual(
            payload["tracks"][0]["valid_steps"][0]["frame_gap"],
            2,
        )

    def test_missing_nucleus_omits_nucleus_fields(self) -> None:
        payload = serialize_video_tracking_result([self.track], self.params)
        self.assertNotIn("nucleus_reference", payload)
        self.assertNotIn("nucleus_relative_movement_summary", payload)
        self.assertNotIn(
            "toward_velocity_um_per_s",
            payload["tracks"][0]["valid_steps"][0],
        )
        self.assertNotIn(
            "nucleus_relative_movement_summary",
            payload["tracks"][0],
        )

    def test_trajectory_csv_has_distances_and_signed_velocity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trajectory.csv"
            save_trajectory_csv(
                path,
                [self.track],
                self.params,
                nucleus_xy_px=(0.0, 0.0),
            )
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["distance_to_nucleus_um"], "10.0")
        self.assertEqual(rows[0]["toward_velocity_um_per_s"], "")
        self.assertEqual(rows[1]["distance_to_nucleus_um"], "6.0")
        self.assertEqual(rows[1]["delta_distance_um"], "4.0")
        self.assertEqual(rows[1]["toward_velocity_um_per_s"], "2.0")

    def test_video_summary_matches_authoritative_step_summary(self) -> None:
        summary = compute_nucleus_relative_summary(
            [self.track],
            self.params,
            (0.0, 0.0),
        )
        self.assertEqual(summary.valid_step_count, 1)
        self.assertAlmostEqual(
            summary.time_weighted_toward_velocity_um_per_s,
            2.0,
        )

    def test_result_view_displays_signed_toward_nucleus_value(self) -> None:
        view = tracking_result_view_from_dict(
            {
                "num_tracks_with_valid_steps": 1,
                "num_tracks_started": 1,
                "total_valid_steps": 2,
                "absolute_velocity_index_um_per_s": 3.0,
                "downward_velocity_index_um_per_s": 1.0,
                "toward_nucleus_velocity_um_per_s": -0.25,
            }
        )
        text = format_tracking_result_panel_lines(
            view,
            None,
            optical_flow_qc_status="Not computed",
            optical_flow_frame_pair_count="—",
        )
        self.assertIn("Toward Nucleus: -0.2500 µm/s (signed)", text)


class NucleusRelativeMaskInvarianceTests(unittest.TestCase):
    @staticmethod
    def _frames() -> list[np.ndarray]:
        frames = []
        for index in range(3):
            frame = np.zeros((60, 60), dtype=np.float32)
            x = 20 + index
            frame[24:27, x - 1 : x + 2] = 220
            frame[44:47, 44:47] = 255
            frames.append(frame)
        return frames

    def test_nucleus_metric_does_not_change_valid_mask_tracking(self) -> None:
        valid = np.zeros((60, 60), dtype=bool)
        valid[10:38, 10:38] = True
        without = analyze_cropped_preview(
            self._frames(),
            params=_params(),
            valid_mask=valid,
        )
        with_nucleus = analyze_cropped_preview(
            self._frames(),
            params=_params(),
            valid_mask=valid,
            nucleus_xy_px=(30.0, 26.0),
        )
        self.assertEqual(
            [
                [(point.frame_index, point.x, point.y) for point in track.points]
                for track in without.tracks
            ],
            [
                [(point.frame_index, point.x, point.y) for point in track.points]
                for track in with_nucleus.tracks
            ],
        )
        self.assertIsNotNone(with_nucleus.toward_nucleus_velocity_um_per_s)
        for track in with_nucleus.tracks:
            for point in track.points:
                self.assertTrue(valid[int(round(point.y)), int(round(point.x))])

    def test_saved_oriented_nucleus_is_converted_to_crop_local_coordinates(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._project_root = Path("/tmp/workspace")
        annotation = {
            "nucleus_reference": {
                "x": 35.0,
                "y": 48.0,
                "coordinate_space": "oriented_frame_pixels",
            }
        }
        with patch("actintrack_app.gui.get_sample_annotation", return_value=annotation):
            xy = MainWindow._saved_nucleus_xy_crop_local(
                window,
                "sample_1",
                RectROI(10, 20, 50, 60),
            )
        self.assertEqual(xy, (25.0, 28.0))


if __name__ == "__main__":
    unittest.main()
