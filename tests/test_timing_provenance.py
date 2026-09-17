"""Phase T1/T2 timing provenance and researcher confirmation tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from actintrack_app.gui_result_views import (
    OpticalFlowResultView,
    SampleTrackingResultView,
    format_tracking_result_panel_lines,
    tracking_result_view_from_dict,
)
from actintrack_app.motion_index import (
    MotionIndexParams,
    iter_track_step_metrics,
    PointTrack,
    TrackPoint,
)
from actintrack_app.optical_flow_motion_index import OpticalFlowSettings
from actintrack_app.timing_provenance import (
    LAB_DEFAULT_SECONDS_PER_FRAME,
    TIMING_SOURCE_CUSTOM,
    TIMING_SOURCE_LAB_DEFAULT,
    TIMING_SOURCE_LEGACY_DEFAULT,
    TIMING_SOURCE_PROTOCOL_STANDARD,
    TIMING_SOURCE_VIDEO_HEADER,
    TimingMetadata,
    calibrated_um_per_s,
    frame_interval_from_fps,
    implied_px_per_frame,
    probe_video_playback_fps,
    timing_from_annotation,
    timing_from_dict,
    timing_from_result_payload,
    validate_observed_fps,
)


class VideoFpsProbeTests(unittest.TestCase):
    def test_representative_avi_reports_six_fps(self) -> None:
        path = Path("testsamples/2_WT_550/01.avi")
        if not path.is_file():
            self.skipTest("testsamples AVI not present")
        fps = probe_video_playback_fps(path)
        self.assertIsNotNone(fps)
        self.assertAlmostEqual(float(fps), 6.0, places=3)
        interval = frame_interval_from_fps(fps)
        self.assertIsNotNone(interval)
        self.assertAlmostEqual(float(interval), 1.0 / 6.0, places=6)

    def test_invalid_fps_handled_safely(self) -> None:
        self.assertIsNone(validate_observed_fps(None))
        self.assertIsNone(validate_observed_fps(0))
        self.assertIsNone(validate_observed_fps(-1))
        self.assertIsNone(validate_observed_fps(float("nan")))
        self.assertIsNone(validate_observed_fps(float("inf")))
        self.assertIsNone(validate_observed_fps(1e6))
        self.assertIsNone(frame_interval_from_fps(None))
        self.assertIsNone(probe_video_playback_fps("/no/such/file.avi"))


class TimingMetadataPersistenceTests(unittest.TestCase):
    def test_video_header_custom_and_lab_persistence(self) -> None:
        video = TimingMetadata.from_observed_fps(6.0, confirmed=False)
        self.assertEqual(video.timing_source, TIMING_SOURCE_PROTOCOL_STANDARD)
        self.assertAlmostEqual(video.analysis_seconds_per_frame, 60.0, places=6)
        self.assertFalse(video.confirmed)

        confirmed = video.confirm()
        self.assertTrue(confirmed.confirmed)
        loaded = timing_from_dict(confirmed.to_dict())
        self.assertIsNotNone(loaded)
        self.assertTrue(loaded.confirmed)
        self.assertEqual(loaded.timing_source, TIMING_SOURCE_PROTOCOL_STANDARD)

        legacy_header = TimingMetadata.from_observed_fps(
            6.0, prefer_video_header=True, confirmed=True
        )
        self.assertEqual(legacy_header.timing_source, TIMING_SOURCE_VIDEO_HEADER)
        self.assertAlmostEqual(
            legacy_header.analysis_seconds_per_frame, 1.0 / 6.0, places=6
        )

        lab = TimingMetadata.lab_default(observed_video_fps=6.0, confirmed=True)
        self.assertEqual(lab.timing_source, TIMING_SOURCE_LAB_DEFAULT)
        self.assertAlmostEqual(lab.analysis_seconds_per_frame, LAB_DEFAULT_SECONDS_PER_FRAME)

        custom = TimingMetadata.custom(0.2, observed_video_fps=6.0, confirmed=True)
        self.assertEqual(custom.timing_source, TIMING_SOURCE_CUSTOM)
        self.assertAlmostEqual(custom.analysis_seconds_per_frame, 0.2)

        ann = {"timing": lab.to_dict()}
        from_ann = timing_from_annotation(ann)
        self.assertIsNotNone(from_ann)
        self.assertEqual(from_ann.timing_source, TIMING_SOURCE_LAB_DEFAULT)

    def test_legacy_result_load(self) -> None:
        payload = {
            "parameters": {
                "seconds_per_frame": 0.2,
                "microns_per_pixel": 0.265,
            },
            "absolute_velocity_index_um_per_s": 1.325,
            "num_tracks_with_valid_steps": 2,
            "total_valid_steps": 4,
        }
        timing = timing_from_result_payload(payload)
        self.assertIsNotNone(timing)
        self.assertEqual(timing.timing_source, TIMING_SOURCE_LEGACY_DEFAULT)
        self.assertAlmostEqual(timing.analysis_seconds_per_frame, 0.2)
        self.assertFalse(timing.confirmed)

        view = tracking_result_view_from_dict(payload)
        self.assertEqual(view.status, "success")
        self.assertAlmostEqual(view.general_movement_px_per_frame or 0.0, 1.0, places=5)


class SparseOfTimingConsistencyTests(unittest.TestCase):
    def test_sparse_and_of_consume_identical_confirmed_timing(self) -> None:
        timing = TimingMetadata.from_observed_fps(6.0, confirmed=True)
        params = MotionIndexParams(seconds_per_frame=timing.analysis_seconds_per_frame)
        of_settings = OpticalFlowSettings(
            seconds_per_frame=timing.analysis_seconds_per_frame
        )
        self.assertEqual(params.seconds_per_frame, of_settings.seconds_per_frame)
        self.assertAlmostEqual(params.seconds_per_frame, 60.0, places=6)
        self.assertEqual(timing.timing_source, TIMING_SOURCE_PROTOCOL_STANDARD)

    def test_frame_gap_velocity_uses_confirmed_timing(self) -> None:
        params = MotionIndexParams(
            microns_per_pixel=1.0,
            seconds_per_frame=2.0,
        )
        track = PointTrack(track_id=0, start_x=0.0, start_y=0.0)
        track.points = [
            TrackPoint(track_id=0, frame_index=0, x=0.0, y=0.0, confidence=1.0),
            TrackPoint(track_id=0, frame_index=2, x=0.0, y=4.0, confidence=1.0),
        ]
        steps = list(iter_track_step_metrics(track, params))
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].frame_gap, 2)
        self.assertAlmostEqual(steps[0].dt_s, 4.0)
        self.assertAlmostEqual(steps[0].absolute_velocity_um_per_s, 1.0)

    def test_px_frame_invariant_and_ums_scales(self) -> None:
        px = 5.0
        mpp = 0.265
        values = {}
        for label, spf in (
            ("30", 30.0),
            ("0.2", 0.2),
            ("avi", 1.0 / 6.0),
        ):
            um_s = calibrated_um_per_s(px, seconds_per_frame=spf, microns_per_pixel=mpp)
            back = implied_px_per_frame(
                um_s, seconds_per_frame=spf, microns_per_pixel=mpp
            )
            self.assertAlmostEqual(back, px, places=9)
            values[label] = um_s
        self.assertAlmostEqual(values["0.2"] / values["30"], 150.0, places=6)
        self.assertAlmostEqual(values["avi"] / values["0.2"], 1.2, places=6)


class ResultDisplayTimingTests(unittest.TestCase):
    def test_panel_shows_px_frame_and_unconfirmed_marker(self) -> None:
        template = SampleTrackingResultView(
            status="success",
            general_movement=0.05,
            general_movement_px_per_frame=3.0,
            tracks_used=2,
            tracks_requested=2,
            valid_steps=4,
            timing_confirmed=False,
        )
        of_view = OpticalFlowResultView(
            status="success",
            general_movement=0.04,
            general_movement_px_per_frame=2.5,
            timing_confirmed=False,
        )
        text = format_tracking_result_panel_lines(
            template,
            of_view,
            optical_flow_qc_status="OK",
            optical_flow_frame_pair_count="4",
        )
        self.assertIn("General Movement: 3.0000 px/frame", text)
        self.assertIn("Calibrated Velocity: 0.0500 µm/s", text)
        self.assertIn("Timing unconfirmed", text)
        self.assertIn("General Movement: 2.5000 px/frame", text)


class WtMutantOrderingSanityTests(unittest.TestCase):
    def test_raw_ordering_invariant_across_timing(self) -> None:
        wt_px = 8.175608
        mut_px = 4.488575
        self.assertGreater(wt_px, mut_px)
        mpp = 0.265
        for spf in (30.0, 0.2, 1.0 / 6.0):
            wt = calibrated_um_per_s(wt_px, seconds_per_frame=spf, microns_per_pixel=mpp)
            mut = calibrated_um_per_s(mut_px, seconds_per_frame=spf, microns_per_pixel=mpp)
            self.assertGreater(wt, mut)


class AnnotationTimingRoundtripTests(unittest.TestCase):
    def test_build_sample_annotation_includes_timing(self) -> None:
        from actintrack_app.annotation_schema import build_sample_annotation
        from actintrack_app.orientation import OrientationState, RectROI

        timing = TimingMetadata.from_observed_fps(6.0, confirmed=True)
        ann = build_sample_annotation(
            sample_id="S1",
            group="g",
            original_file="a.avi",
            stored_raw_path="raw/a.avi",
            reference_frame_index=0,
            orientation=OrientationState(),
            roi=RectROI(1, 2, 10, 12),
            original_dimensions={"width": 20, "height": 30},
            oriented_dimensions={"width": 20, "height": 30},
            timing=timing,
        )
        self.assertIn("timing", ann)
        self.assertTrue(ann["timing"]["timing_confirmed"])
        self.assertAlmostEqual(ann["timing"]["analysis_seconds_per_frame"], 60.0)
        self.assertEqual(ann["timing"]["timing_source"], TIMING_SOURCE_PROTOCOL_STANDARD)


if __name__ == "__main__":
    unittest.main()
