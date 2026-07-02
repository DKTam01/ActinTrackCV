"""Unit tests for tracking/optical-flow result view DTOs and panel formatting."""

from __future__ import annotations

import unittest

import numpy as np

from actintrack_app.gui_result_views import (
    OpticalFlowResultView,
    SampleTrackingResultView,
    fmt_optional_float,
    format_tracking_result_panel_lines,
    is_tracking_failed,
    optical_flow_result_view_from_dict,
    optical_flow_result_view_from_result,
    optional_gui_float,
    tracking_result_view_from_dict,
    tracking_result_view_from_preview,
)
from actintrack_app.motion_index import MotionIndexParams, PointTrack
from actintrack_app.optical_flow_motion_index import OpticalFlowResult
from actintrack_app.preview_workflow import CroppedPreviewAnalysis


def _preview_analysis(
    *,
    num_tracks_with_valid_steps: int = 3,
    tracking_warning: str = "",
    num_starting_points: int = 5,
) -> CroppedPreviewAnalysis:
    frames = [np.zeros((32, 32), dtype=np.uint8) for _ in range(3)]
    tracks = [
        PointTrack(track_id=i, start_x=1.0, start_y=1.0) for i in range(num_tracks_with_valid_steps)
    ]
    params = MotionIndexParams(num_starting_points=num_starting_points)
    return CroppedPreviewAnalysis(
        frames=frames,
        tracks=tracks,
        starting_points=[(1.0, 1.0)] * num_starting_points,
        downward_velocity_index_um_per_s=1.2345,
        general_movement_index_um_per_s=2.3456,
        num_tracks_with_valid_steps=num_tracks_with_valid_steps,
        total_valid_steps=12,
        mean_track_length_frames=4.0,
        tracking_warning=tracking_warning,
        params=params,
    )


class OptionalFloatTests(unittest.TestCase):
    def test_optional_gui_float(self) -> None:
        self.assertIsNone(optional_gui_float(None))
        self.assertIsNone(optional_gui_float(""))
        self.assertEqual(optional_gui_float("1.5"), 1.5)
        self.assertIsNone(optional_gui_float("bad"))

    def test_fmt_optional_float(self) -> None:
        self.assertEqual(fmt_optional_float(None), "—")
        self.assertEqual(fmt_optional_float(1.23456), "1.2346")


class TrackingDictViewTests(unittest.TestCase):
    def test_success(self) -> None:
        data = {
            "num_tracks_with_valid_steps": 4,
            "num_tracks_started": 6,
            "downward_velocity_index_um_per_s": 0.5,
            "absolute_velocity_index_um_per_s": 1.0,
            "total_valid_steps": 20,
        }
        view = tracking_result_view_from_dict(data)
        self.assertEqual(view.status, "success")
        self.assertEqual(view.downward_velocity, 0.5)
        self.assertEqual(view.general_movement, 1.0)
        self.assertEqual(view.tracks_used, 4)
        self.assertEqual(view.tracks_requested, 6)
        self.assertEqual(view.valid_steps, 20)

    def test_failure_with_reason(self) -> None:
        data = {
            "num_tracks_with_valid_steps": 0,
            "tracking_warning": "No valid tracks",
        }
        view = tracking_result_view_from_dict(data)
        self.assertEqual(view.status, "failed")
        self.assertEqual(view.failure_reason, "No valid tracks")


class PreviewAnalysisViewTests(unittest.TestCase):
    def test_is_tracking_failed(self) -> None:
        self.assertTrue(is_tracking_failed(_preview_analysis(num_tracks_with_valid_steps=0)))
        self.assertFalse(is_tracking_failed(_preview_analysis(num_tracks_with_valid_steps=1)))

    def test_success(self) -> None:
        view = tracking_result_view_from_preview(_preview_analysis())
        self.assertEqual(view.status, "success")
        self.assertEqual(view.downward_velocity, 1.2345)
        self.assertEqual(view.general_movement, 2.3456)
        self.assertEqual(view.tracks_used, 3)
        self.assertEqual(view.tracks_requested, 5)
        self.assertEqual(view.valid_steps, 12)

    def test_failure(self) -> None:
        view = tracking_result_view_from_preview(
            _preview_analysis(num_tracks_with_valid_steps=0, tracking_warning="Preview failed")
        )
        self.assertEqual(view.status, "failed")
        self.assertEqual(view.failure_reason, "Preview failed")


class OpticalFlowDictViewTests(unittest.TestCase):
    def test_success(self) -> None:
        data = {
            "has_valid_result": True,
            "optical_flow_general_movement_um_s": 1.1,
            "optical_flow_downward_motion_um_s": 0.9,
            "optical_flow_net_y_velocity_um_s": 0.7,
            "optical_flow_directionality_ratio": 0.5,
            "optical_flow_valid_pixel_fraction": 0.8,
            "optical_flow_saturated_pixel_fraction": 0.01,
        }
        view = optical_flow_result_view_from_dict(data)
        self.assertEqual(view.status, "success")
        self.assertEqual(view.general_movement, 1.1)
        self.assertEqual(view.saturated_pixel_fraction, 0.01)

    def test_failure(self) -> None:
        data = {"has_valid_result": False, "failure_reason": "Too few frames"}
        view = optical_flow_result_view_from_dict(data)
        self.assertEqual(view.status, "failed")
        self.assertEqual(view.failure_reason, "Too few frames")


class OpticalFlowResultViewTests(unittest.TestCase):
    def test_success(self) -> None:
        result = OpticalFlowResult(
            has_valid_result=True,
            optical_flow_general_movement_um_s=2.0,
            optical_flow_downward_motion_um_s=1.5,
            optical_flow_net_y_velocity_um_s=1.0,
            optical_flow_directionality_ratio=0.6,
            optical_flow_valid_pixel_fraction=0.75,
            frame_pair_count=4,
        )
        view = optical_flow_result_view_from_result(result)
        self.assertEqual(view.status, "success")
        self.assertEqual(view.general_movement, 2.0)
        self.assertIsNone(view.saturated_pixel_fraction)

    def test_failure(self) -> None:
        result = OpticalFlowResult(
            has_valid_result=False,
            failure_reason="ROI too small",
        )
        view = optical_flow_result_view_from_result(result)
        self.assertEqual(view.status, "failed")
        self.assertEqual(view.failure_reason, "ROI too small")


class FormatTrackingResultPanelLinesTests(unittest.TestCase):
    def test_template_success(self) -> None:
        template = SampleTrackingResultView(
            status="success",
            downward_velocity=0.1234,
            general_movement=0.5678,
            tracks_used=3,
            tracks_requested=5,
            valid_steps=10,
        )
        text = format_tracking_result_panel_lines(
            template,
            None,
            optical_flow_qc_status="Not computed",
            optical_flow_frame_pair_count="—",
        )
        self.assertIn("Template Tracking Motion Index", text)
        self.assertIn("Absolute Velocity: 0.5678 µm/s", text)
        self.assertIn("Downward Velocity: 0.1234 µm/s", text)
        self.assertIn("Tracks Used: 3 / 5", text)
        self.assertIn("Valid Steps: 10", text)
        self.assertIn("Optical Flow Motion Index (Draft)", text)
        self.assertIn("Status: Not computed", text)
        self.assertIn("Not generated yet", text)

    def test_template_failed(self) -> None:
        template = SampleTrackingResultView(
            status="failed",
            failure_reason="No valid tracks",
        )
        text = format_tracking_result_panel_lines(
            template,
            None,
            optical_flow_qc_status="Not computed",
            optical_flow_frame_pair_count="—",
        )
        self.assertIn("Failed", text)
        self.assertIn("No valid tracks", text)

    def test_template_stale(self) -> None:
        text = format_tracking_result_panel_lines(
            None,
            None,
            template_stale=True,
            optical_flow_qc_status="Not computed",
            optical_flow_frame_pair_count="—",
        )
        self.assertIn("May not match current settings.", text)

    def test_optical_flow_success(self) -> None:
        optical = OpticalFlowResultView(
            status="success",
            general_movement=1.0,
            downward_motion=0.8,
            net_y_velocity=0.6,
            directionality_ratio=0.5,
            valid_pixel_fraction=0.9,
            saturated_pixel_fraction=0.02,
        )
        text = format_tracking_result_panel_lines(
            None,
            optical,
            optical_flow_qc_status="Pass",
            optical_flow_frame_pair_count="3",
        )
        self.assertIn("Status: Pass", text)
        self.assertIn("Frame pairs used: 3", text)
        self.assertIn("General Movement: 1.0000 µm/s", text)
        self.assertIn("Downward Motion: 0.8000 µm/s", text)
        self.assertIn("Net Y Velocity: 0.6000 µm/s", text)
        self.assertIn("Directionality Ratio: 0.5000", text)
        self.assertIn("Valid Pixel Fraction: 0.9000", text)
        self.assertIn("Saturated Pixel Fraction: 0.0200", text)

    def test_optical_flow_failed(self) -> None:
        optical = OpticalFlowResultView(
            status="failed",
            failure_reason="Too few frames",
        )
        text = format_tracking_result_panel_lines(
            None,
            optical,
            optical_flow_qc_status="Fail",
            optical_flow_frame_pair_count="—",
        )
        self.assertIn("Status: Fail", text)
        self.assertIn("Failed", text)
        self.assertIn("Too few frames", text)

    def test_optical_flow_stale(self) -> None:
        text = format_tracking_result_panel_lines(
            None,
            None,
            optical_flow_stale=True,
            optical_flow_qc_status="Pass",
            optical_flow_frame_pair_count="—",
        )
        self.assertIn("May not match current settings.", text)


if __name__ == "__main__":
    unittest.main()
