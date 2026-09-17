"""PERF1 protocol timing: 60 s/frame scientific dt independent of container FPS."""

from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from actintrack_app.motion_index import (
    MotionIndexParams,
    PointTrack,
    TrackPoint,
    compute_step_metrics,
    load_frame_sequence,
)
from actintrack_app.optical_flow_motion_index import (
    OpticalFlowSettings,
    _px_per_frame_to_um_per_s,
)
from actintrack_app.timing_provenance import (
    STANDARD_ACQUISITION_INTERVAL_S,
    TIMING_SOURCE_PROTOCOL_STANDARD,
    TimingMetadata,
    calibrated_um_per_s,
    implied_px_per_frame,
)


ROOT = Path(__file__).resolve().parents[1]


class ProtocolTimingScienceTests(unittest.TestCase):
    def test_gm_uses_sixty_second_dt(self) -> None:
        params = MotionIndexParams(
            microns_per_pixel=1.0,
            seconds_per_frame=STANDARD_ACQUISITION_INTERVAL_S,
        )
        prev = TrackPoint(0, 0, 0.0, 0.0, 1.0)
        nxt = TrackPoint(0, 1, 3.0, 4.0, 1.0)
        step = compute_step_metrics(prev, nxt, params)
        self.assertAlmostEqual(step.dt_s, 60.0)
        self.assertAlmostEqual(step.displacement_px, 5.0)
        self.assertAlmostEqual(step.absolute_velocity_um_per_s, 5.0 / 60.0)

    def test_toward_nucleus_uses_sixty_second_dt(self) -> None:
        params = MotionIndexParams(
            microns_per_pixel=1.0,
            seconds_per_frame=STANDARD_ACQUISITION_INTERVAL_S,
        )
        prev = TrackPoint(0, 0, 10.0, 0.0, 1.0)
        nxt = TrackPoint(0, 1, 4.0, 0.0, 1.0)
        step = compute_step_metrics(
            prev, nxt, params, nucleus_xy_px=(0.0, 0.0)
        )
        self.assertAlmostEqual(step.dt_s, 60.0)
        self.assertIsNotNone(step.delta_distance_um)
        assert step.delta_distance_um is not None
        # Moved from distance 10 to distance 4 → toward nucleus (positive).
        self.assertAlmostEqual(step.delta_distance_um, 6.0)
        self.assertAlmostEqual(step.toward_velocity_um_per_s or 0.0, 6.0 / 60.0)

    def test_optical_flow_uses_sixty_second_dt(self) -> None:
        settings = OpticalFlowSettings(
            seconds_per_frame=STANDARD_ACQUISITION_INTERVAL_S,
            microns_per_pixel=1.0,
        )
        self.assertAlmostEqual(
            _px_per_frame_to_um_per_s(12.0, settings), 12.0 / 60.0
        )

    def test_velocity_scales_from_old_dt_to_protocol(self) -> None:
        px = 8.175608
        mpp = 0.265
        old_dt = 1.0 / 6.0
        new_dt = 60.0
        old_v = calibrated_um_per_s(px, seconds_per_frame=old_dt, microns_per_pixel=mpp)
        new_v = calibrated_um_per_s(px, seconds_per_frame=new_dt, microns_per_pixel=mpp)
        self.assertAlmostEqual(new_v, old_v * old_dt / new_dt, places=9)
        self.assertAlmostEqual(
            implied_px_per_frame(new_v, seconds_per_frame=new_dt, microns_per_pixel=mpp),
            px,
            places=9,
        )

    def test_different_container_fps_same_scientific_velocity(self) -> None:
        px = 4.5
        mpp = 0.265
        velocities = []
        for fps in (6.0, 12.0, None):
            timing = TimingMetadata.from_protocol_standard(observed_video_fps=fps)
            self.assertEqual(timing.timing_source, TIMING_SOURCE_PROTOCOL_STANDARD)
            velocities.append(
                calibrated_um_per_s(
                    px,
                    seconds_per_frame=timing.analysis_seconds_per_frame,
                    microns_per_pixel=mpp,
                )
            )
        self.assertTrue(all(abs(v - velocities[0]) < 1e-12 for v in velocities))


class FrameSequenceSelectionTests(unittest.TestCase):
    def test_video_loads_all_sequential_frames(self) -> None:
        path = ROOT / "testsamples/2_WT_550/01.avi"
        if not path.is_file():
            self.skipTest("testsamples AVI not present")
        frames, meta = load_frame_sequence(path)
        n = len(frames)
        self.assertEqual(n, 15)
        self.assertEqual(meta.get("loader"), "video")
        self.assertEqual(n - 1, 14)  # N frames → N-1 transitions
        for frame in frames:
            self.assertEqual(frame.ndim, 3)
            self.assertGreater(frame.size, 0)


if __name__ == "__main__":
    unittest.main()
