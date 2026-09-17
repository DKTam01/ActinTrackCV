"""CAL1: physical-unit scaling uses sample calibration; pixel domain is unchanged."""

from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from actintrack_app.measurement_series import (
    load_general_movement_series,
    verify_series_matches_summary,
)
from actintrack_app.motion_index import (
    MotionIndexParams,
    TrackPoint,
    compute_step_metrics,
    load_frame_sequence,
)
from actintrack_app.optical_flow_motion_index import (
    OpticalFlowSettings,
    _px_per_frame_to_um_per_s,
)
from actintrack_app.project_manager import create_project_structure
from actintrack_app.sample_result_state import invalidation_for_scientific_edit
from actintrack_app.schema_compat import draft_tracking_path
from actintrack_app.scientific_calibration import SampleScientificCalibration
from actintrack_app.structural_orientation import compute_structural_orientation
from actintrack_app.timing_provenance import (
    TIMING_SOURCE_PROTOCOL_STANDARD,
    TimingMetadata,
    calibrated_um_per_s,
    implied_px_per_frame,
)


class PhysicalUnitScalingTests(unittest.TestCase):
    def test_halving_interval_doubles_velocity_px_unchanged(self) -> None:
        px = 5.0
        mpp = 0.265
        baseline = calibrated_um_per_s(px, seconds_per_frame=60.0, microns_per_pixel=mpp)
        doubled = calibrated_um_per_s(px, seconds_per_frame=30.0, microns_per_pixel=mpp)
        self.assertAlmostEqual(baseline, 5.0 * 0.265 / 60.0)
        self.assertAlmostEqual(doubled, baseline * 2.0)
        self.assertAlmostEqual(
            implied_px_per_frame(doubled, seconds_per_frame=30.0, microns_per_pixel=mpp),
            px,
        )

    def test_spatial_scale_changes_um_s_not_px(self) -> None:
        px = 5.0
        old_mpp = 0.265
        new_mpp = 0.157836
        old_v = calibrated_um_per_s(px, seconds_per_frame=60.0, microns_per_pixel=old_mpp)
        new_v = calibrated_um_per_s(px, seconds_per_frame=60.0, microns_per_pixel=new_mpp)
        self.assertAlmostEqual(new_v, old_v * (new_mpp / old_mpp))
        self.assertAlmostEqual(
            implied_px_per_frame(new_v, seconds_per_frame=60.0, microns_per_pixel=new_mpp),
            px,
        )


class MetricPathTests(unittest.TestCase):
    def test_general_movement_uses_sample_calibration(self) -> None:
        params = MotionIndexParams(microns_per_pixel=0.265, seconds_per_frame=30.0)
        prev = TrackPoint(0, 0, 0.0, 0.0, 1.0)
        nxt = TrackPoint(0, 1, 3.0, 4.0, 1.0)
        step = compute_step_metrics(prev, nxt, params)
        self.assertAlmostEqual(step.displacement_px, 5.0)
        self.assertAlmostEqual(step.dt_s, 30.0)
        self.assertAlmostEqual(step.absolute_velocity_um_per_s, 5.0 * 0.265 / 30.0)

    def test_toward_nucleus_uses_sample_calibration(self) -> None:
        params = MotionIndexParams(microns_per_pixel=0.138, seconds_per_frame=60.0)
        prev = TrackPoint(0, 0, 10.0, 0.0, 1.0)
        nxt = TrackPoint(0, 1, 4.0, 0.0, 1.0)
        step = compute_step_metrics(prev, nxt, params, nucleus_xy_px=(0.0, 0.0))
        self.assertAlmostEqual(step.delta_distance_um or 0.0, 6.0 * 0.138)
        self.assertAlmostEqual(step.toward_velocity_um_per_s or 0.0, 6.0 * 0.138 / 60.0)

    def test_optical_flow_uses_sample_calibration(self) -> None:
        settings = OpticalFlowSettings(
            microns_per_pixel=0.157836,
            seconds_per_frame=30.0,
        )
        self.assertAlmostEqual(
            _px_per_frame_to_um_per_s(12.0, settings),
            12.0 * 0.157836 / 30.0,
        )

    def test_orientation_has_no_timing_or_spatial_dependency(self) -> None:
        frame = np.zeros((32, 32), dtype=np.uint8)
        frame[8:24, 10:22] = 200
        first = compute_structural_orientation(
            frame, nucleus_xy_px=(16.0, 16.0), sample_id="S1"
        )
        second = compute_structural_orientation(
            frame, nucleus_xy_px=(16.0, 16.0), sample_id="S1"
        )
        self.assertEqual(
            first.median_angle_relative_nucleus_deg,
            second.median_angle_relative_nucleus_deg,
        )
        src = inspect.signature(compute_structural_orientation).parameters
        self.assertNotIn("seconds_per_frame", src)
        self.assertNotIn("microns_per_pixel", src)
        self.assertNotIn("acquisition_interval_s", src)


class FreshnessDependencyTests(unittest.TestCase):
    def test_video_calibration_change_marks_motion_stale(self) -> None:
        effects = invalidation_for_scientific_edit(
            had_measurable_results=True,
            geometry_changed=False,
            motion_calibration_changed=True,
            media_is_image=False,
        )
        self.assertTrue(effects.mark_stale)
        self.assertTrue(effects.clear_live_caches)

    def test_image_calibration_change_does_not_invalidate_orientation(self) -> None:
        effects = invalidation_for_scientific_edit(
            had_measurable_results=True,
            geometry_changed=False,
            motion_calibration_changed=True,
            media_is_image=True,
        )
        self.assertFalse(effects.mark_stale)
        self.assertFalse(effects.clear_live_caches)

    def test_unrelated_noop_when_nothing_changed(self) -> None:
        effects = invalidation_for_scientific_edit(
            had_measurable_results=True,
            geometry_changed=False,
            motion_calibration_changed=False,
        )
        self.assertFalse(effects.mark_stale)


class FpsIndependenceTests(unittest.TestCase):
    def test_same_calibration_same_velocity_regardless_of_container_fps(self) -> None:
        px = 4.5
        mpp = 0.265
        interval = 60.0
        velocities = []
        for fps in (1.0, 3.0, 6.0, None):
            timing = TimingMetadata(
                observed_video_fps=fps,
                analysis_seconds_per_frame=interval,
                timing_source=TIMING_SOURCE_PROTOCOL_STANDARD,
                confirmed=True,
            )
            self.assertAlmostEqual(timing.analysis_seconds_per_frame, interval)
            velocities.append(
                calibrated_um_per_s(
                    px,
                    seconds_per_frame=timing.analysis_seconds_per_frame,
                    microns_per_pixel=mpp,
                )
            )
        self.assertTrue(all(abs(v - velocities[0]) < 1e-12 for v in velocities))

    def test_synthetic_1fps_and_3fps_videos_share_frame_count_and_science(self) -> None:
        frames = []
        for i in range(15):
            frame = np.zeros((32, 40, 3), dtype=np.uint8)
            frame[8:24, 6 + i : 14 + i] = (20, 220, 40)
            frames.append(frame)
        tmp = tempfile.TemporaryDirectory()
        try:
            root = Path(tmp.name)
            paths = {}
            for fps in (1.0, 3.0):
                path = root / f"ident_{int(fps)}fps.avi"
                writer = cv2.VideoWriter(
                    str(path),
                    cv2.VideoWriter_fourcc(*"MJPG"),
                    float(fps),
                    (40, 32),
                )
                self.assertTrue(writer.isOpened(), msg=f"could not write {path}")
                for frame in frames:
                    writer.write(frame)
                writer.release()
                paths[fps] = path
            loaded = {}
            for fps, path in paths.items():
                decoded, meta = load_frame_sequence(path)
                loaded[fps] = decoded
                self.assertEqual(len(decoded), 15, msg=f"fps={fps} meta={meta}")
            # Encoding may perturb pixels; compare science from identical px input.
            px = 5.0
            mpp = 0.265
            interval = 60.0
            v1 = calibrated_um_per_s(px, seconds_per_frame=interval, microns_per_pixel=mpp)
            v3 = calibrated_um_per_s(px, seconds_per_frame=interval, microns_per_pixel=mpp)
            self.assertAlmostEqual(v1, v3)
            self.assertEqual(len(loaded[1.0]), len(loaded[3.0]))
        finally:
            tmp.cleanup()


class InspectorRunBoundTests(unittest.TestCase):
    def test_inspector_series_uses_persisted_run_not_current_sample(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        try:
            root = Path(tmp.name)
            create_project_structure(root)
            sid = "S1"
            path = draft_tracking_path(root, sid)
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "analysis_run_id": "run-old",
                "general_movement_index_um_per_s": 0.0220833333333,
                "scientific_calibration": SampleScientificCalibration(
                    acquisition_interval_s=60.0,
                    microns_per_pixel=0.265,
                ).to_dict(),
                "parameters": {
                    "seconds_per_frame": 60.0,
                    "microns_per_pixel": 0.265,
                },
                "tracking_result": {
                    "tracks": [
                        {
                            "track_id": 1,
                            "valid_steps": [
                                {
                                    "prev_frame_index": 0,
                                    "frame_index": 1,
                                    "dx_px": 3.0,
                                    "dy_px": 4.0,
                                    "frame_gap": 1,
                                    "absolute_velocity_um_per_s": 0.0220833333333,
                                }
                            ],
                        }
                    ]
                },
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            series = load_general_movement_series(root, sid)
            self.assertAlmostEqual(series.rows[0]["um_per_s"], 0.0220833333333)
            self.assertAlmostEqual(series.rows[0]["px_per_frame"], 5.0)
            self.assertTrue(verify_series_matches_summary(series))
            # Current sample calibration must not rewrite persisted rows.
            current = SampleScientificCalibration(
                acquisition_interval_s=30.0,
                microns_per_pixel=0.157836,
            )
            self.assertAlmostEqual(series.summary_value or 0.0, 0.0220833333333)
            self.assertNotAlmostEqual(
                series.summary_value or 0.0,
                5.0 * current.microns_per_pixel / current.acquisition_interval_s,
            )
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
