"""Tests for V1 measurement-fidelity helpers and movement provenance."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from actintrack_app.measurement_fidelity import (
    condition_ordering,
    implied_px_per_frame,
    summarize_sparse_tracks,
)
from actintrack_app.motion_index import (
    METRIC_DEFINITION_VERSION,
    MOVEMENT_OUTPUT_SCHEMA_VERSION,
    MotionIndexParams,
    PointTrack,
    TrackPoint,
    compute_motion_indices,
    compute_step_metrics,
    compute_velocity_summary,
    iter_track_step_metrics,
    run_motion_index_analysis,
    save_trajectory_csv,
)


def _track_with_steps(
    points: list[tuple[int, float, float]],
    *,
    track_id: int = 1,
) -> PointTrack:
    track = PointTrack(
        track_id=track_id,
        start_x=points[0][1],
        start_y=points[0][2],
        end_reason="reached_last_frame",
    )
    for frame_index, x, y in points:
        track.points.append(
            TrackPoint(
                track_id=track_id,
                frame_index=frame_index,
                x=x,
                y=y,
                confidence=1.0,
            )
        )
    return track


class StepMetricsCentralizationTests(unittest.TestCase):
    def test_raw_displacement_and_temporal_scaling(self) -> None:
        params = MotionIndexParams(
            microns_per_pixel=0.265,
            seconds_per_frame=0.2,
        )
        prev = TrackPoint(1, 0, 10.0, 20.0, 1.0)
        nxt = TrackPoint(1, 1, 13.0, 24.0, 1.0)
        step = compute_step_metrics(prev, nxt, params)

        self.assertEqual(step.frame_gap, 1)
        self.assertAlmostEqual(step.dx_px, 3.0)
        self.assertAlmostEqual(step.dy_px, 4.0)
        self.assertAlmostEqual(step.displacement_px, 5.0)
        self.assertAlmostEqual(step.displacement_um, 5.0 * 0.265)
        self.assertAlmostEqual(step.absolute_velocity_um_per_s, (5.0 * 0.265) / 0.2)

        params_30 = MotionIndexParams(
            microns_per_pixel=0.265,
            seconds_per_frame=30.0,
        )
        step_30 = compute_step_metrics(prev, nxt, params_30)
        self.assertAlmostEqual(step_30.displacement_px, 5.0)
        self.assertAlmostEqual(
            step.absolute_velocity_um_per_s / step_30.absolute_velocity_um_per_s,
            30.0 / 0.2,
        )

    def test_frame_gap_scales_dt_without_inventing_points(self) -> None:
        params = MotionIndexParams(
            microns_per_pixel=1.0,
            seconds_per_frame=2.0,
        )
        prev = TrackPoint(1, 0, 0.0, 0.0, 1.0)
        nxt = TrackPoint(1, 3, 3.0, 4.0, 1.0)
        step = compute_step_metrics(prev, nxt, params)
        self.assertEqual(step.frame_gap, 3)
        self.assertAlmostEqual(step.dt_s, 6.0)
        self.assertAlmostEqual(step.absolute_velocity_um_per_s, 5.0 / 6.0)

    def test_step_and_time_weighted_aggregates_agree_with_csv_rows(self) -> None:
        params = MotionIndexParams(
            microns_per_pixel=1.0,
            seconds_per_frame=1.0,
        )
        track = _track_with_steps(
            [
                (0, 0.0, 0.0),
                (1, 3.0, 4.0),  # 5 px, 1 frame
                (3, 6.0, 8.0),  # 5 px, 2 frames
            ]
        )
        steps = iter_track_step_metrics(track, params)
        self.assertEqual(len(steps), 2)
        speeds = [s.absolute_velocity_um_per_s for s in steps]
        path_um = sum(s.displacement_um for s in steps)
        time_s = sum(s.dt_s for s in steps)

        downward, general, _ = compute_motion_indices([track], params)
        velocity = compute_velocity_summary([track], params)

        self.assertAlmostEqual(general, float(np.mean(speeds)))
        self.assertAlmostEqual(
            velocity.time_weighted_mean_speed_um_per_s,
            path_um / time_s,
        )
        self.assertNotAlmostEqual(general, velocity.time_weighted_mean_speed_um_per_s)

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "traj.csv"
            save_trajectory_csv(csv_path, [track], params)
            text = csv_path.read_text(encoding="utf-8")
            self.assertIn("absolute_velocity_um_per_s", text)
            self.assertIn("5.0", text.replace("5.000000", "5.0"))

    def test_direction_invariance_of_absolute_speed(self) -> None:
        params = MotionIndexParams(microns_per_pixel=1.0, seconds_per_frame=1.0)
        a = compute_step_metrics(
            TrackPoint(1, 0, 0.0, 0.0, 1.0),
            TrackPoint(1, 1, 3.0, 4.0, 1.0),
            params,
        )
        b = compute_step_metrics(
            TrackPoint(1, 0, 0.0, 0.0, 1.0),
            TrackPoint(1, 1, -3.0, -4.0, 1.0),
            params,
        )
        self.assertAlmostEqual(a.absolute_velocity_um_per_s, b.absolute_velocity_um_per_s)
        self.assertAlmostEqual(a.downward_velocity_um_per_s, 4.0)
        self.assertAlmostEqual(b.downward_velocity_um_per_s, 0.0)

    def test_summary_provenance_and_populated_output_paths(self) -> None:
        import cv2

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            frame_paths: list[Path] = []
            for i in range(4):
                frame = np.zeros((64, 64, 3), dtype=np.uint8)
                x = 20 + (2 * i)
                y = 30 + (2 * i)
                frame[y - 1 : y + 2, x - 1 : x + 2] = (255, 255, 255)
                path = tmp_path / f"frame_{i:03d}.png"
                cv2.imwrite(str(path), frame)
                frame_paths.append(path)

            out_dir = tmp_path / "out"
            result = run_motion_index_analysis(
                tmp_path,
                output_dir=out_dir,
                final_export_name="synthetic",
                params=MotionIndexParams(
                    num_starting_points=1,
                    min_point_spacing_px=8,
                    search_radius_px=6,
                    microns_per_pixel=1.0,
                    seconds_per_frame=1.0,
                ),
                frame_paths=frame_paths,
            )
            summary_path = Path(result.summary_json)
            self.assertTrue(summary_path.is_file())
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["metric_definition_version"], METRIC_DEFINITION_VERSION)
            self.assertEqual(
                payload["movement_output_schema_version"],
                MOVEMENT_OUTPUT_SCHEMA_VERSION,
            )
            self.assertIn("movement_definition", payload)
            self.assertEqual(payload["tracking_result"]["schema_version"], 1)
            self.assertEqual(len(payload["tracking_result"]["tracks"]), 1)
            outputs = payload.get("outputs") or {}
            self.assertTrue(str(outputs.get("trajectory_csv", "")).endswith(".csv"))
            self.assertTrue(str(outputs.get("summary_json", "")).endswith(".json"))
            self.assertTrue(Path(outputs["trajectory_csv"]).is_file())
            self.assertTrue(Path(result.trajectory_csv).is_file())


class MeasurementFidelityHelperTests(unittest.TestCase):
    def test_implied_px_per_frame_reconstructs_historical_scale(self) -> None:
        # 9.5861 µm/s at 0.2 s/frame and 0.265 µm/px ≈ 7.24 px/frame
        px = implied_px_per_frame(9.5861, seconds_per_frame=0.2, microns_per_pixel=0.265)
        self.assertAlmostEqual(px, 9.5861 * 0.2 / 0.265, places=6)
        px_30 = implied_px_per_frame(
            9.5861, seconds_per_frame=30.0, microns_per_pixel=0.265
        )
        self.assertAlmostEqual(px_30 / px, 30.0 / 0.2)

    def test_condition_ordering_uses_raw_px_means(self) -> None:
        rows = [
            {
                "condition": "2_WT_550",
                "sparse_tracking": {"mean_displacement_px_per_frame": 5.0},
                "optical_flow": {"mean_magnitude_px_frame": 4.0},
            },
            {
                "condition": "2_WT_550",
                "sparse_tracking": {"mean_displacement_px_per_frame": 7.0},
                "optical_flow": {"mean_magnitude_px_frame": 5.0},
            },
            {
                "condition": "3_Mutant_515",
                "sparse_tracking": {"mean_displacement_px_per_frame": 3.0},
                "optical_flow": {"mean_magnitude_px_frame": 2.0},
            },
            {
                "condition": "3_Mutant_515",
                "sparse_tracking": {"mean_displacement_px_per_frame": 4.0},
                "optical_flow": {"mean_magnitude_px_frame": 3.0},
            },
        ]
        ordering = condition_ordering(rows)
        self.assertTrue(ordering["observed_sparse_wt_gt_mutant"])
        self.assertTrue(ordering["observed_of_wt_gt_mutant"])
        self.assertAlmostEqual(
            ordering["by_condition"]["2_WT_550"]["mean_sparse_px_per_frame"],
            6.0,
        )

    def test_summarize_sparse_tracks_reports_px_before_calibration(self) -> None:
        params = MotionIndexParams(
            microns_per_pixel=0.265,
            seconds_per_frame=30.0,
        )
        track = _track_with_steps([(0, 0.0, 0.0), (1, 3.0, 4.0)])
        summary = summarize_sparse_tracks("WT550_0001", [track], params)
        self.assertAlmostEqual(summary.mean_displacement_px, 5.0)
        self.assertAlmostEqual(summary.mean_displacement_px_per_frame, 5.0)
        self.assertIn("documented_hypothesis_30", summary.calibrated_by_interval)
        self.assertIn("historical_default_0p2", summary.calibrated_by_interval)
        self.assertAlmostEqual(
            summary.calibrated_by_interval["historical_default_0p2"][
                "general_movement_um_per_s"
            ],
            5.0 * 0.265 / 0.2,
        )


if __name__ == "__main__":
    unittest.main()
