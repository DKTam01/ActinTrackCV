"""Tests for hidden notes compatibility and sidebar tab routing."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from actintrack_app.gui import MainWindow
from actintrack_app.orientation import OrientationState, RectROI


class NotesCompatibilityTests(unittest.TestCase):
    def test_apply_annotation_stores_legacy_notes(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._loaded_sample_notes = ""
        window._orientation = OrientationState()
        window._reference_frame_index = 0
        window._loaded_annotation_source = ""
        window._roi_user_adjusted = False
        window._roi_autosave_pending = False
        window._refresh_display = MagicMock()
        window.canvas = MagicMock()
        window.canvas.rect_roi.return_value = None
        window._oriented_frame = MagicMock(return_value=None)
        window._update_orientation_label = MagicMock()
        window._refresh_roi_save_status_from_context = MagicMock()
        window._refresh_roi_preview_panel = MagicMock()
        window._update_metric_freshness_label = MagicMock()
        window._schedule_debounced_metrics = MagicMock()

        ann = {
            "sample_id": "S1",
            "reference_frame_index": 0,
            "notes": "legacy lab note",
            "annotation_source": "manual",
            "rotation_angle_degrees": 0.0,
            "flipped_180": False,
            "mirror_y_axis": False,
            "rectangle_roi": {"x": 1, "y": 2, "width": 10, "height": 12},
        }
        MainWindow._apply_annotation_from_dict(window, ann, render_canvas=False)

        self.assertEqual(window._loaded_sample_notes, "legacy lab note")

    def test_update_tracking_result_panel_without_sidebar_widget(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"

        MainWindow.update_tracking_result_panel(window, "S1")

    def test_on_return_to_samples_without_sample_tab(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._center_stack = MagicMock()
        window._center_stack.currentIndex.return_value = 1
        window._set_left_explorer_visible = MagicMock()

        MainWindow._on_return_to_samples(window)

        window._center_stack.setCurrentIndex.assert_called_once_with(0)
        window._set_left_explorer_visible.assert_called_once_with(True)


class LoadedNotesForSaveTests(unittest.TestCase):
    def test_loaded_notes_used_for_annotation_dict(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._loaded_sample_notes = " preserved "
        window._roi_user_adjusted = False
        window._current_sample = {
            "sample_id": "S1",
            "group": "Col-0",
            "batch_name": "batch1",
            "batch_id": "b1",
            "original_filename": "clip.mp4",
            "stored_path": "raw/S1.avi",
        }
        window._reference_frame_index = 0
        window._orientation = OrientationState()
        window._loaded_annotation_source = "manual"
        window._base_frame = MagicMock()
        window._base_frame.shape = (100, 200, 3)
        window.canvas = MagicMock()
        window.canvas.rect_roi.return_value = RectROI(1, 2, 10, 12)

        check = MagicMock()
        check.ok = True
        check.roi_oriented = RectROI(1, 2, 10, 12)
        check.roi_original = RectROI(1, 2, 10, 12)
        window._validate_current_roi = MagicMock(return_value=check)
        window._suggestion_method_for_save = MagicMock(return_value="manual")

        ann = MainWindow._current_annotation_dict(window, status="roi_marked")

        self.assertEqual(ann["notes"], "preserved")


if __name__ == "__main__":
    unittest.main()
