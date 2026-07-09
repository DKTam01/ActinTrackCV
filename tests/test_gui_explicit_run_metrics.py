"""Tests for explicit Run Metrics workflow (Phase 5.7B)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from actintrack_app.gui import MainWindow
from actintrack_app.metric_display import render_metric_status_text
from actintrack_app.orientation import RectROI


class ExplicitRunMetricsStateTests(unittest.TestCase):
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

    def test_fresh_metrics_report_analyzed(self) -> None:
        window = self._stub_window()
        self.assertEqual(window._metric_state_for_sample("S1"), "analyzed")

    def test_no_metrics_status_when_roi_exists_without_drafts(self) -> None:
        window = self._stub_window()
        window._read_draft_tracking_payload = lambda _sid: None
        window._read_draft_optical_flow_payload = lambda _sid: None
        self.assertEqual(window._metric_state_for_sample("S1"), "not_analyzed")
        self.assertEqual(
            render_metric_status_text("not_analyzed"),
            "Metric status: No Metrics",
        )

    def test_stale_status_copy(self) -> None:
        self.assertEqual(
            render_metric_status_text("stale"),
            "Metric status: Stale",
        )


class RoiEditExplicitRunTests(unittest.TestCase):
    def test_on_roi_changed_does_not_schedule_or_mark_stale(self) -> None:
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

        self.assertNotIn("S1", window._tracking_result_stale_by_sample)
        self.assertNotIn("S1", window._optical_flow_stale_by_sample)
        window._update_metric_freshness_label.assert_not_called()

    def test_autosave_marks_stale_only_when_geometry_changes_and_metrics_exist(
        self,
    ) -> None:
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

    def test_autosave_without_existing_metrics_does_not_mark_stale(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._tracking_result_stale_by_sample = {}
        window._optical_flow_stale_by_sample = {}
        window._sample_has_measurable_draft_results = MagicMock(return_value=False)
        MainWindow._mark_metrics_stale_if_saved_roi_changed(
            window,
            "S1",
            previous_roi_key=(1, 2, 10, 12),
            new_roi_key=(5, 6, 20, 24),
        )
        self.assertNotIn("S1", window._tracking_result_stale_by_sample)


class SampleSwitchExplicitRunTests(unittest.TestCase):
    def test_load_sample_does_not_queue_background_metrics(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._metric_analysis_view_active = False
        window._preview_playing = False
        window._playback_pause = MagicMock()
        window._set_active_sample = MagicMock()
        window._current_condition_group = MagicMock(return_value="cg_a")
        window._refresh_condition_group_combo = MagicMock()
        window._preview_page = MagicMock()
        window.reset_preview_state = MagicMock()
        window.update_tracking_result_panel = MagicMock()
        window._load_full_roi_preview_for_current_sample = MagicMock()
        window._refresh_roi_save_status_from_context = MagicMock()
        window._update_metric_freshness_label = MagicMock()

        item = MagicMock()
        item.data.return_value = {
            "item_type": "sample",
            "sample_id": "S2",
            "group": "cg_a",
            "processing_status": "roi_marked",
        }
        window._tree_item_meta = MagicMock(return_value=item.data.return_value)
        window._project_root = MagicMock()
        window._is_sample_tree_item = MagicMock(return_value=True)

        with patch(
            "actintrack_app.gui.condition_group_exists",
            return_value=True,
        ):
            MainWindow._load_sample_from_tree_item(window, item)

        self.assertFalse(hasattr(MainWindow, "ensure_metrics_scheduled_for_sample_if_needed"))

    def test_metric_analysis_switch_uses_display_only_path(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._metric_analysis_view_active = True
        window._preview_playing = False
        window._playback_pause = MagicMock()
        window._set_active_sample = MagicMock()
        window._current_condition_group = MagicMock(return_value="cg_a")
        window._refresh_condition_group_combo = MagicMock()
        window._preview_page = MagicMock()
        window._clear_sample_specific_metric_state = MagicMock()
        window._ensure_metric_view_shell_visible = MagicMock()
        window._set_preview_mode_banner = MagicMock()
        window._load_sample_data_context = MagicMock(return_value=True)
        window.update_tracking_result_panel = MagicMock()
        window._reload_metric_analysis_view_for_current_sample = MagicMock()
        window._display_metric_analysis_view_for_current_sample = MagicMock()
        window._refresh_roi_save_status_from_context = MagicMock()
        window._update_metric_freshness_label = MagicMock()

        item = MagicMock()
        item.data.return_value = {
            "item_type": "sample",
            "sample_id": "S2",
            "group": "cg_a",
            "processing_status": "roi_marked",
        }
        window._tree_item_meta = MagicMock(return_value=item.data.return_value)
        window._project_root = MagicMock()
        window._is_sample_tree_item = MagicMock(return_value=True)

        with patch(
            "actintrack_app.gui.condition_group_exists",
            return_value=True,
        ):
            MainWindow._load_sample_from_tree_item(window, item)

        window._display_metric_analysis_view_for_current_sample.assert_called_once()
        window._reload_metric_analysis_view_for_current_sample.assert_not_called()


class RunMetricsButtonTests(unittest.TestCase):
    def test_run_metrics_blocked_without_saved_roi(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window._metrics_inflight = set()
        window._sample_has_valid_data_and_roi = MagicMock(return_value=False)
        window._compute_metrics_for_sample = MagicMock()
        window._status = MagicMock()
        window._update_metric_freshness_label = MagicMock()

        result = MainWindow.run_metrics_for_sample_id(
            window,
            "S1",
            show_dialog_on_block=False,
        )

        self.assertEqual(result, "unavailable")
        window._compute_metrics_for_sample.assert_not_called()
        window._status.assert_called_once()
        window._update_metric_freshness_label.assert_called_once()

    def test_run_metrics_computes_current_sample_only(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window.run_metrics_for_sample_id = MagicMock(return_value="analyzed")

        MainWindow.run_metrics_now_for_current_sample(window)

        window.run_metrics_for_sample_id.assert_called_once_with(
            "S1",
            show_dialog_on_block=False,
        )


if __name__ == "__main__":
    unittest.main()
