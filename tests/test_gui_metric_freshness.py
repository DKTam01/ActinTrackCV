"""Tests for metric freshness display and ROI/metric label separation."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from actintrack_app.gui import MainWindow
from actintrack_app.orientation import RectROI


class MetricFreshnessStateTests(unittest.TestCase):
    def _stub_window(self) -> MainWindow:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window._metrics_inflight = set()
        window._tracking_result_stale_by_sample = {}
        window._optical_flow_stale_by_sample = {}
        window._metric_error_by_sample = {}
        window._sample_has_valid_data_and_roi = lambda _sid: True
        window._read_draft_tracking_payload = lambda _sid: {
            "num_tracks_with_valid_steps": 2
        }
        window._read_draft_optical_flow_payload = lambda _sid: {
            "has_valid_result": True
        }
        return window

    def test_analyzed_state_when_drafts_present(self) -> None:
        window = self._stub_window()
        self.assertEqual(window._metric_state_for_sample("S1"), "analyzed")

    def test_running_state_when_metrics_inflight(self) -> None:
        window = self._stub_window()
        window._metrics_inflight = {"S1"}
        self.assertEqual(window._metric_state_for_sample("S1"), "running")


class RoiMetricStatusSeparationTests(unittest.TestCase):
    def test_refresh_roi_save_status_reflects_saved_roi(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample = {"sample_id": "S1"}
        window._roi_user_adjusted = False
        window._roi_autosave_pending = False
        window.canvas = MagicMock()
        window.canvas.rect_roi.return_value = RectROI(1, 2, 10, 12)
        window.lbl_roi_save_status = MagicMock()

        with patch("actintrack_app.gui.apply_status_style") as apply_style:
            MainWindow._refresh_roi_save_status_from_context(window)

        window.lbl_roi_save_status.setText.assert_called_once_with("ROI saved")
        apply_style.assert_called_once()
        self.assertTrue(apply_style.call_args.kwargs.get("saved"))

    def test_refresh_roi_save_status_reflects_unsaved_edit(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample = {"sample_id": "S1"}
        window._roi_user_adjusted = True
        window._roi_autosave_pending = False
        window.canvas = MagicMock()
        window.canvas.rect_roi.return_value = RectROI(1, 2, 10, 12)
        window.lbl_roi_save_status = MagicMock()

        with patch("actintrack_app.gui.apply_status_style"):
            MainWindow._refresh_roi_save_status_from_context(window)

        window.lbl_roi_save_status.setText.assert_called_once_with("Unsaved changes")

    def test_on_roi_changed_does_not_schedule_metrics(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window._tracking_result_stale_by_sample = {}
        window._optical_flow_stale_by_sample = {}
        window._roi_user_adjusted = False
        window._roi_autosave_pending = False
        window._loaded_annotation_source = ""
        window._set_roi_save_status = MagicMock()
        window._refresh_roi_preview_panel = MagicMock()
        window._update_metric_freshness_label = MagicMock()

        MainWindow.on_roi_changed(window, RectROI(1, 2, 10, 12))

        window._set_roi_save_status.assert_called_once_with(
            "Unsaved changes", saved=False
        )
        window._update_metric_freshness_label.assert_not_called()

    def test_sample_switch_refreshes_roi_and_metric_labels(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._refresh_roi_save_status_from_context = MagicMock()
        window._update_metric_freshness_label = MagicMock()

        window._refresh_roi_save_status_from_context()
        window._update_metric_freshness_label()

        window._refresh_roi_save_status_from_context.assert_called_once()
        window._update_metric_freshness_label.assert_called_once()


if __name__ == "__main__":
    unittest.main()
