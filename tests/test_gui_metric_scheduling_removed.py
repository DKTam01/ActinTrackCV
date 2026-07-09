"""Regression guards: implicit metric scheduling infrastructure removed (Phase 5.7D)."""

from __future__ import annotations

import inspect
import unittest
from unittest.mock import MagicMock, patch

from actintrack_app.gui import MainWindow
from actintrack_app.orientation import RectROI


_REMOVED_ATTRIBUTES = (
    "_schedule_debounced_metrics",
    "_schedule_metric_settings_refresh",
    "_on_metric_debounce_fired",
    "_on_metric_settings_debounce_fired",
    "_on_metric_flush_timer",
    "ensure_metrics_scheduled_for_sample_if_needed",
    "_metric_debounce_timer",
    "_metric_settings_timer",
    "_metric_flush_timer",
    "_metric_compute_queue",
    "_pending_tracking_snapshot",
    "_pending_optical_flow_snapshot",
    "_tracking_job_running",
    "_optical_flow_job_running",
    "_cancel_pending_debounced_tracking",
)


class MetricSchedulingInfrastructureRemovedTests(unittest.TestCase):
    def test_removed_helpers_are_not_on_main_window(self) -> None:
        for name in _REMOVED_ATTRIBUTES:
            with self.subTest(name=name):
                self.assertFalse(hasattr(MainWindow, name))

    def test_explicit_run_metrics_helpers_remain(self) -> None:
        for name in (
            "run_metrics_for_sample_id",
            "run_metrics_now_for_current_sample",
            "_compute_metrics_for_sample",
            "_ctx_run_metrics_for_sample",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(MainWindow, name))
                self.assertTrue(callable(getattr(MainWindow, name)))

    def test_metric_state_never_returns_scheduled(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window._metrics_inflight = set()
        window._tracking_result_stale_by_sample = {}
        window._optical_flow_stale_by_sample = {}
        window._metric_error_by_sample = {}
        window._sample_has_valid_data_and_roi = lambda _sid: True
        window._read_draft_tracking_payload = lambda _sid: None
        window._read_draft_optical_flow_payload = lambda _sid: None

        self.assertEqual(window._metric_state_for_sample("S1"), "not_analyzed")

    def test_selection_path_does_not_reference_removed_scheduler(self) -> None:
        source = inspect.getsource(MainWindow._load_sample_from_tree_item)
        for token in (
            "_schedule_debounced_metrics",
            "ensure_metrics_scheduled_for_sample_if_needed",
            "_metric_compute_queue",
            "_metric_debounce_timer",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, source)

    def test_roi_changed_path_does_not_reference_removed_scheduler(self) -> None:
        source = inspect.getsource(MainWindow.on_roi_changed)
        for token in (
            "_schedule_debounced_metrics",
            "ensure_metrics_scheduled_for_sample_if_needed",
            "_metric_compute_queue",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, source)

    def test_autosave_path_does_not_reference_removed_scheduler(self) -> None:
        source = inspect.getsource(MainWindow._autosave_roi)
        for token in (
            "_schedule_debounced_metrics",
            "ensure_metrics_scheduled_for_sample_if_needed",
            "_metric_compute_queue",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, source)


class ExplicitRunMetricsStillWorksTests(unittest.TestCase):
    def test_toolbar_run_metrics_delegates_to_sample_id_helper(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window.run_metrics_for_sample_id = MagicMock(return_value="analyzed")

        MainWindow.run_metrics_now_for_current_sample(window)

        window.run_metrics_for_sample_id.assert_called_once_with(
            "S1",
            show_dialog_on_block=False,
        )

    def test_explorer_context_run_metrics_unchanged(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window.run_metrics_for_sample_id = MagicMock(return_value="analyzed")

        MainWindow._ctx_run_metrics_for_sample(window, "S2")

        window.run_metrics_for_sample_id.assert_called_once_with(
            "S2",
            show_dialog_on_block=True,
        )
        self.assertEqual(window._current_sample_id, "S1")

    def test_roi_drag_does_not_schedule_metrics(self) -> None:
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

        window._update_metric_freshness_label.assert_not_called()

    def test_autosave_does_not_schedule_metrics(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._project_root = MagicMock()
        window._current_sample = {"sample_id": "S1", "processing_status": "roi_marked"}
        window.canvas = MagicMock()
        window.canvas.rect_roi.return_value = RectROI(5, 6, 20, 24)
        window._current_annotation_dict = MagicMock(
            return_value={
                "sample_id": "S1",
                "notes": "",
                "annotation_source": "manual",
                "review_status": "approved",
            }
        )
        window._saved_roi_key_for_sample = MagicMock(return_value=(1, 2, 10, 12))
        window._sample_has_measurable_draft_results = MagicMock(return_value=True)
        window._mark_metrics_stale_if_saved_roi_changed = MagicMock()
        window._set_roi_save_status = MagicMock()
        window._update_sample_list_row_for_id = MagicMock()
        window._update_metric_freshness_label = MagicMock()
        window._metric_error_by_sample = {}

        with patch("actintrack_app.gui.save_sample_crop_annotation"), patch(
            "actintrack_app.gui.update_samples_csv"
        ):
            MainWindow._autosave_roi(window, quiet=True)

        window._mark_metrics_stale_if_saved_roi_changed.assert_called_once()
        window._update_metric_freshness_label.assert_called_once()


if __name__ == "__main__":
    unittest.main()
