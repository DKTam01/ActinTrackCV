"""Tests for display-only Metric Analysis View entry (Phase 6.9B)."""

from __future__ import annotations

import inspect
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from actintrack_app.gui import MainWindow
from actintrack_app.motion_index import MotionIndexParams, PointTrack
from actintrack_app.orientation import OrientationState, RectROI
from actintrack_app.preview_workflow import CroppedPreviewAnalysis
from actintrack_app.roi_workflow import RoiValidationResult


def _preview_analysis(*, general_movement: float = 2.0) -> CroppedPreviewAnalysis:
    frames = [np.zeros((32, 32), dtype=np.uint8) for _ in range(3)]
    tracks = [PointTrack(track_id=0, start_x=1.0, start_y=1.0)]
    return CroppedPreviewAnalysis(
        frames=frames,
        tracks=tracks,
        starting_points=[(1.0, 1.0)],
        downward_velocity_index_um_per_s=general_movement / 2,
        general_movement_index_um_per_s=general_movement,
        num_tracks_with_valid_steps=1,
        total_valid_steps=5,
        mean_track_length_frames=5.0,
        params=MotionIndexParams(),
    )


class MetricAnalysisDisplayOnlyTests(unittest.TestCase):
    def _stub_window(self) -> MainWindow:
        window = MainWindow.__new__(MainWindow)
        window._project_root = MagicMock()
        window._current_sample = {"sample_id": "S1", "stored_path": "raw/cg/S1.mp4"}
        window._current_sample_id = "S1"
        window._orientation = OrientationState()
        window._tracking_results_by_sample = {}
        window._tracking_result_stale_by_sample = {}
        window._optical_flow_stale_by_sample = {}
        window._autosave_roi = MagicMock()
        window._validate_current_roi = MagicMock(
            return_value=RoiValidationResult(
                True,
                "",
                roi_oriented=RectROI(0, 0, 64, 64),
            )
        )
        window._sample_file_path = MagicMock(return_value=MagicMock(exists=lambda: True))
        window._status = MagicMock()
        window._display_metric_analysis_view_for_current_sample = MagicMock()
        window._show_metric_analysis_placeholder = MagicMock()
        window._report_metric_view_blocked = MagicMock()
        window._tracking_params_from_ui = MagicMock(return_value=MotionIndexParams())
        return window

    def _allow_metric_analysis(self, window: MainWindow) -> None:
        window._base_frame = object()
        window._crop_confirmed = True
        window._cell_region = object()
        window._nucleus_reference = object()
        window._timing = MagicMock(confirmed=True)
        window._sample_has_measurable_draft_results = MagicMock(return_value=True)
        window._metrics_inflight = set()

    def test_enter_metric_analysis_does_not_call_compute_helpers(self) -> None:
        source = inspect.getsource(MainWindow.enter_metric_analysis_view_for_current_sample)
        for token in (
            "analyze_cropped_preview",
            "compute_optical_flow_motion_index",
            "_commit_tracking_result",
            "_commit_optical_flow_result",
            "_save_draft_tracking_result",
            "_save_draft_optical_flow_result",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, source)

    def test_enter_with_existing_in_memory_metrics_delegates_to_display(self) -> None:
        window = self._stub_window()
        self._allow_metric_analysis(window)
        window._tracking_results_by_sample["S1"] = _preview_analysis()

        with patch("actintrack_app.gui.is_supported_video_path", return_value=True):
            ok = MainWindow.enter_metric_analysis_view_for_current_sample(window)

        self.assertTrue(ok)
        window._display_metric_analysis_view_for_current_sample.assert_called_once()

    def test_enter_with_stale_draft_metrics_is_blocked(self) -> None:
        window = self._stub_window()
        self._allow_metric_analysis(window)
        window._tracking_result_stale_by_sample["S1"] = True
        window._sample_has_measurable_draft_results = MagicMock(return_value=True)

        ok = MainWindow.enter_metric_analysis_view_for_current_sample(window)

        self.assertFalse(ok)
        window._report_metric_view_blocked.assert_called()
        window._display_metric_analysis_view_for_current_sample.assert_not_called()

    def test_enter_without_metrics_is_blocked(self) -> None:
        window = self._stub_window()
        window._base_frame = object()
        window._sample_has_measurable_draft_results = MagicMock(return_value=False)
        window._metrics_inflight = set()

        ok = MainWindow.enter_metric_analysis_view_for_current_sample(window)

        self.assertFalse(ok)
        window._report_metric_view_blocked.assert_called()
        window._display_metric_analysis_view_for_current_sample.assert_not_called()

    def test_display_uses_cached_analysis_without_recompute(self) -> None:
        window = self._stub_window()
        analysis = _preview_analysis()
        window._tracking_results_by_sample["S1"] = analysis
        window._ensure_metric_view_shell_visible = MagicMock()
        window.update_tracking_result_panel = MagicMock()
        window._update_optical_flow_qc_readout = MagicMock()
        window._enter_cropped_preview_mode = MagicMock()
        window._preview_play = MagicMock()

        MainWindow._display_metric_analysis_view_for_current_sample(window)

        window._enter_cropped_preview_mode.assert_called_once_with(analysis)

    def test_display_with_stale_draft_loads_frames_not_tracking(self) -> None:
        window = self._stub_window()
        window._tracking_result_stale_by_sample["S1"] = True
        window._read_draft_tracking_payload = MagicMock(
            return_value={
                "num_tracks_with_valid_steps": 2,
                "general_movement_index_um_per_s": 1.5,
                "downward_velocity_index_um_per_s": 0.75,
                "total_valid_steps": 10,
            }
        )
        window._read_draft_optical_flow_payload = MagicMock(return_value=None)
        window._ensure_metric_view_shell_visible = MagicMock()
        window.update_tracking_result_panel = MagicMock()
        window._update_optical_flow_qc_readout = MagicMock()
        window._enter_cropped_preview_mode = MagicMock()
        frames = [np.zeros((16, 16), dtype=np.uint8) for _ in range(2)]

        with patch("actintrack_app.gui.is_supported_video_path", return_value=True), patch(
            "actintrack_app.gui.load_cropped_frames_from_video",
            return_value=frames,
        ) as load_frames, patch(
            "actintrack_app.gui.analyze_cropped_preview",
        ) as analyze:
            MainWindow._display_metric_analysis_view_for_current_sample(window)

        load_frames.assert_called_once()
        analyze.assert_not_called()
        window._enter_cropped_preview_mode.assert_called_once()
        displayed = window._enter_cropped_preview_mode.call_args.args[0]
        self.assertEqual(displayed.general_movement_index_um_per_s, 1.5)
        self.assertEqual(displayed.num_tracks_with_valid_steps, 2)

    def test_display_without_metrics_shows_placeholder(self) -> None:
        window = self._stub_window()
        window._read_draft_tracking_payload = MagicMock(return_value=None)
        window._read_draft_optical_flow_payload = MagicMock(return_value=None)
        window._ensure_metric_view_shell_visible = MagicMock()
        window.update_tracking_result_panel = MagicMock()
        window._update_optical_flow_qc_readout = MagicMock()
        window._enter_cropped_preview_mode = MagicMock()
        window._show_metric_analysis_placeholder = MagicMock()

        MainWindow._display_metric_analysis_view_for_current_sample(window)

        window._enter_cropped_preview_mode.assert_not_called()
        window._show_metric_analysis_placeholder.assert_called_once_with(
            "Run Metrics to generate the analysis preview."
        )

    def test_enter_cropped_preview_mode_does_not_persist_results(self) -> None:
        source = inspect.getsource(MainWindow._enter_cropped_preview_mode)
        self.assertNotIn("_commit_tracking_result", source)
        self.assertNotIn("_save_draft_tracking_result", source)


class RunMetricsUnchangedTests(unittest.TestCase):
    def test_run_metrics_still_computes(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window._base_frame = object()
        window._metrics_inflight = set()
        window._sample_has_valid_data_and_roi = MagicMock(return_value=True)
        window._compute_metrics_for_sample = MagicMock(return_value="analyzed")
        window._crop_confirmed = True
        window._cell_region = object()
        window._nucleus_reference = object()
        window._timing = MagicMock(confirmed=True)
        window.canvas = MagicMock()
        window.canvas.rect_roi.return_value = object()
        window._sample_has_measurable_draft_results = MagicMock(return_value=False)
        window._tracking_result_stale_by_sample = {}
        window._optical_flow_stale_by_sample = {}
        window._status = MagicMock()
        window._sync_workflow_controls = MagicMock()

        result = MainWindow.run_metrics_for_sample_id(
            window,
            "S1",
            show_dialog_on_block=False,
        )

        self.assertEqual(result, "analyzed")
        window._compute_metrics_for_sample.assert_called_once_with("S1")

    def test_compute_path_still_uses_sid_commit_helpers(self) -> None:
        source = inspect.getsource(MainWindow._compute_metrics_for_sample)
        self.assertIn("_commit_tracking_result_for_sid", source)
        self.assertIn("_commit_optical_flow_result_for_sid", source)


if __name__ == "__main__":
    unittest.main()
