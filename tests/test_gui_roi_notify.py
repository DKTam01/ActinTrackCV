"""Tests for ROI change notification and metric stale marking."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import numpy as np
from PyQt6.QtWidgets import QApplication

from actintrack_app.gui import MainWindow
from actintrack_app.gui_canvas import ImageCanvas, _roi_geometry_equal
from actintrack_app.orientation import RectROI


class RoiGeometryEqualTests(unittest.TestCase):
    def test_equal_rectangles(self) -> None:
        left = RectROI(1, 2, 10, 12)
        right = RectROI(1, 2, 10, 12)
        self.assertTrue(_roi_geometry_equal(left, right))

    def test_none_handling(self) -> None:
        self.assertTrue(_roi_geometry_equal(None, None))
        self.assertFalse(_roi_geometry_equal(RectROI(0, 0, 1, 1), None))


class ImageCanvasRoiNotifyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.main_window = MagicMock()
        self.canvas = ImageCanvas(self.main_window)
        frame = np.zeros((100, 200, 3), dtype=np.uint8)
        self.canvas.set_frame(frame, keep_roi=False)
        self.main_window.on_roi_changed.reset_mock()

    def test_set_rect_roi_notifies_on_first_set(self) -> None:
        self.canvas.set_rect_roi(RectROI(10, 20, 50, 40))
        self.main_window.on_roi_changed.assert_called_once()

    def test_set_rect_roi_does_not_notify_when_unchanged(self) -> None:
        roi = RectROI(10, 20, 50, 40)
        self.canvas.set_rect_roi(roi)
        self.main_window.on_roi_changed.reset_mock()
        self.canvas.set_rect_roi(RectROI(10, 20, 50, 40))
        self.main_window.on_roi_changed.assert_not_called()

    def test_set_rect_roi_notifies_when_geometry_changes(self) -> None:
        self.canvas.set_rect_roi(RectROI(10, 20, 50, 40))
        self.main_window.on_roi_changed.reset_mock()
        self.canvas.set_rect_roi(RectROI(11, 20, 50, 40))
        self.main_window.on_roi_changed.assert_called_once()

    def test_refresh_display_pattern_no_spurious_notify(self) -> None:
        """Reclamp during display refresh must not fire user-edit change paths."""
        roi = RectROI(10, 20, 50, 40)
        self.canvas.set_rect_roi(roi)
        self.main_window.on_roi_changed.reset_mock()

        oriented = np.zeros((100, 200, 3), dtype=np.uint8)
        self.canvas.set_frame(oriented, keep_roi=True)
        self.canvas.set_rect_roi(roi.clamp(oriented.shape[1], oriented.shape[0]))

        self.main_window.on_roi_changed.assert_not_called()


class OnRoiChangedStaleTests(unittest.TestCase):
    def test_on_roi_changed_does_not_mark_metric_results_stale(self) -> None:
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

    def test_metric_state_shows_stale_after_roi_change(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window._metrics_inflight = set()
        window._tracking_result_stale_by_sample = {"S1": True}
        window._optical_flow_stale_by_sample = {"S1": True}
        window._metric_error_by_sample = {}

        def _sample_has_roi(_sid: str) -> bool:
            return True

        def _read_track(_sid: str) -> dict:
            return {"num_tracks_with_valid_steps": 3}

        def _read_of(_sid: str) -> dict:
            return {"has_valid_result": True}

        window._sample_has_valid_data_and_roi = _sample_has_roi
        window._read_draft_tracking_payload = _read_track
        window._read_draft_optical_flow_payload = _read_of

        self.assertEqual(window._metric_state_for_sample("S1"), "stale")


if __name__ == "__main__":
    unittest.main()
