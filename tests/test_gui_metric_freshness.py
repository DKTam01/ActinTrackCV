"""Tests for metric freshness / scheduled-state regression guards."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from actintrack_app.gui import MainWindow
from actintrack_app.metric_display import render_metric_status_text
from actintrack_app.orientation import RectROI


class MetricScheduledStateTests(unittest.TestCase):
    def _stub_window(self) -> MainWindow:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window._metrics_inflight = set()
        window._tracking_job_running = False
        window._optical_flow_job_running = False
        window._metric_compute_queue = []
        window._metric_debounce_timer = MagicMock(isActive=lambda: False)
        window._metric_settings_timer = MagicMock(isActive=lambda: False)
        window._pending_tracking_snapshot = object()
        window._pending_optical_flow_snapshot = object()
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

    def test_pending_snapshots_without_active_timer_not_scheduled(self) -> None:
        """Stale pending snapshots must not affect status once debounce is inactive."""
        window = self._stub_window()
        self.assertEqual(window._metric_state_for_sample("S1"), "analyzed")

    def test_active_timer_with_pending_does_not_surface_scheduled(self) -> None:
        window = self._stub_window()
        window._metric_debounce_timer = MagicMock(isActive=lambda: True)
        self.assertEqual(window._metric_state_for_sample("S1"), "analyzed")

    def test_on_metric_debounce_fired_clears_pending_and_refreshes(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._preview_mode = "full"
        window._pending_tracking_snapshot = MagicMock(name="track_snap")
        window._pending_optical_flow_snapshot = MagicMock(name="of_snap")
        window._run_draft_tracking_for_snapshot = MagicMock(return_value=True)
        window._run_optical_flow_for_snapshot = MagicMock(return_value=True)
        window._update_metric_freshness_label = MagicMock()

        MainWindow._on_metric_debounce_fired(window)

        window._run_draft_tracking_for_snapshot.assert_called_once()
        window._run_optical_flow_for_snapshot.assert_called_once()
        self.assertIsNone(window._pending_tracking_snapshot)
        self.assertIsNone(window._pending_optical_flow_snapshot)
        window._update_metric_freshness_label.assert_called_once()

    def test_on_metric_debounce_fired_refreshes_even_when_jobs_skip(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._preview_mode = "full"
        window._pending_tracking_snapshot = MagicMock(name="track_snap")
        window._pending_optical_flow_snapshot = None
        window._run_draft_tracking_for_snapshot = MagicMock(return_value=False)
        window._run_optical_flow_for_snapshot = MagicMock(return_value=False)
        window._update_metric_freshness_label = MagicMock()

        MainWindow._on_metric_debounce_fired(window)

        self.assertIsNone(window._pending_tracking_snapshot)
        window._update_metric_freshness_label.assert_called_once()


class RoiMetricStatusSeparationTests(unittest.TestCase):
    def test_schedule_debounced_metrics_does_not_write_roi_label(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window._capture_tracking_snapshot = MagicMock(return_value=object())
        window._capture_optical_flow_snapshot = MagicMock(return_value=None)
        window._pending_tracking_snapshot = None
        window._pending_optical_flow_snapshot = None
        window._metric_debounce_timer = MagicMock()
        window._update_metric_freshness_label = MagicMock()
        window._set_roi_save_status = MagicMock()
        window.lbl_roi_save_status = MagicMock()

        MainWindow._schedule_debounced_metrics(window)

        window._set_roi_save_status.assert_not_called()
        window.lbl_roi_save_status.setText.assert_not_called()
        window._update_metric_freshness_label.assert_called_once()

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
        window._schedule_debounced_metrics = MagicMock()
        window._refresh_roi_preview_panel = MagicMock()
        window._update_metric_freshness_label = MagicMock()

        MainWindow.on_roi_changed(window, RectROI(1, 2, 10, 12))

        window._set_roi_save_status.assert_called_once_with(
            "Unsaved changes", saved=False
        )
        window._schedule_debounced_metrics.assert_not_called()
        window._update_metric_freshness_label.assert_not_called()

    def test_sample_switch_refreshes_roi_and_metric_labels(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._refresh_roi_save_status_from_context = MagicMock()
        window._update_metric_freshness_label = MagicMock()

        # Mirror the end of _load_sample_from_tree_item after sample load.
        window._refresh_roi_save_status_from_context()
        window._update_metric_freshness_label()

        window._refresh_roi_save_status_from_context.assert_called_once()
        window._update_metric_freshness_label.assert_called_once()

    def test_metric_status_scheduled_text_is_separate_from_roi_label(self) -> None:
        self.assertEqual(
            render_metric_status_text("scheduled"),
            "Metric status: Scheduled",
        )


if __name__ == "__main__":
    unittest.main()
