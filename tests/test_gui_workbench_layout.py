"""Tests for Workbench Stage 1 layout polish and ROI context export."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu

from actintrack_app.gui import MainWindow
from actintrack_app.gui_canvas import ImageCanvas
from actintrack_app.orientation import RectROI

ROOT = Path(__file__).resolve().parents[1]


def _layout_src() -> str:
    return (ROOT / "actintrack_app/gui_layout_builders.py").read_text(encoding="utf-8")


class WorkbenchLayoutStructureTests(unittest.TestCase):
    def test_roi_preview_has_no_title_label(self) -> None:
        layout_src = _layout_src()
        roi_preview_block = layout_src.split("def build_roi_preview_panel", 1)[1].split(
            "def build_roi_workflow_strip", 1
        )[0]
        self.assertNotIn('"ROI preview"', roi_preview_block)
        self.assertNotIn("QLabel(\"ROI preview\")", roi_preview_block)

    def test_metric_status_labels_outside_roi_preview_panel(self) -> None:
        layout_src = _layout_src()
        roi_preview_block = layout_src.split("def build_roi_preview_panel", 1)[1].split(
            "def build_roi_workflow_strip", 1
        )[0]
        metric_labels_block = layout_src.split(
            "def build_metric_status_labels_row", 1
        )[1].split("def create_metric_action_buttons", 1)[0]
        workflow_block = layout_src.split("def build_roi_workflow_strip", 1)[1].split(
            "def build_metric_status_labels_row", 1
        )[0]

        self.assertIn("window.lbl_metric_status", metric_labels_block)
        self.assertIn("window.lbl_last_analyzed", metric_labels_block)
        self.assertNotIn("window.lbl_metric_status", roi_preview_block)
        self.assertNotIn("window.lbl_last_analyzed", roi_preview_block)
        self.assertNotIn("window.lbl_metric_status", workflow_block)

    def test_export_controls_not_in_visible_center_layout(self) -> None:
        layout_src = _layout_src()
        preview_panel_block = layout_src.split("def build_preview_images_panel", 1)[1].split(
            "def build_roi_preview_panel", 1
        )[0]
        workspace_block = layout_src.split("def build_preview_workspace_host", 1)[1].split(
            "def build_preview_images_panel", 1
        )[0]
        workflow_block = layout_src.split("def build_roi_workflow_strip", 1)[1].split(
            "def build_metric_status_labels_row", 1
        )[0]
        metric_labels_block = layout_src.split(
            "def build_metric_status_labels_row", 1
        )[1].split("def create_metric_action_buttons", 1)[0]
        hidden_export_block = layout_src.split("def build_hidden_export_host", 1)[1].split(
            "def build_export_name_panel", 1
        )[0]

        self.assertNotIn("build_export_name_panel(window)", preview_panel_block)
        self.assertNotIn("build_export_name_panel(window)", workspace_block)
        self.assertNotIn("build_export_name_panel(window)", workflow_block)
        self.assertNotIn("build_export_name_panel(window)", metric_labels_block)
        self.assertNotIn("btn_process", workflow_block)
        self.assertNotIn("btn_process", preview_panel_block)
        self.assertIn("build_hidden_export_host(window)", layout_src)
        self.assertIn("build_export_name_panel(window)", hidden_export_block)

    def test_canvases_share_image_row_with_matching_expanding_policy(self) -> None:
        layout_src = _layout_src()
        preview_panel_block = layout_src.split("def build_preview_images_panel", 1)[1].split(
            "def build_roi_preview_panel", 1
        )[0]
        workspace_block = layout_src.split("def build_preview_workspace_host", 1)[1].split(
            "def build_preview_images_panel", 1
        )[0]
        roi_preview_block = layout_src.split("def build_roi_preview_panel", 1)[1].split(
            "def build_roi_workflow_strip", 1
        )[0]

        self.assertIn("images_layout = QHBoxLayout(panel)", preview_panel_block)
        self.assertIn("images_layout.addWidget(window.canvas, stretch=1)", preview_panel_block)
        self.assertIn(
            "QSizePolicy.Policy.Expanding",
            preview_panel_block,
        )
        self.assertIn(
            "configure_workbench_adjacent_panel_stack",
            preview_panel_block,
        )
        self.assertIn(
            "configure_workbench_adjacent_panel(host)",
            roi_preview_block,
        )
        self.assertIn("build_sample_playback_controls(window, layout)", workspace_block)
        self.assertIn("layout.addWidget(build_preview_images_panel(window), stretch=1)", workspace_block)
        self.assertNotIn("window._main_image_column", preview_panel_block)
        self.assertNotIn("build_metric_status_strip", workspace_block)

    def test_metric_action_buttons_share_playback_speed_row(self) -> None:
        layout_src = _layout_src()
        playback_block = layout_src.split("def build_sample_playback_controls", 1)[1].split(
            "def build_hidden_frame_controls", 1
        )[0]
        metric_buttons_block = layout_src.split("def create_metric_action_buttons", 1)[1].split(
            "def build_sample_playback_controls", 1
        )[0]
        metric_settings_block = layout_src.split("def build_metric_settings_host", 1)[1].split(
            "def build_metric_settings_stack", 1
        )[0]
        mode_selector_block = layout_src.split("def build_metric_mode_selector_section", 1)[1].split(
            "def build_workbench_action_mode_slot", 1
        )[0]
        self.assertIn("create_metric_action_buttons(window)", playback_block)
        self.assertIn("build_workbench_action_mode_slot(window)", playback_block)
        self.assertIn("window.btn_metric_analysis", metric_buttons_block)
        self.assertIn("window.btn_run_metrics", metric_buttons_block)
        self.assertIn("window.btn_return_full_preview", playback_block)
        self.assertIn("window._workbench_action_mode_slot", playback_block)
        self.assertIn("configure_workbench_action_mode_slot", layout_src)
        self.assertIn("build_metric_mode_selector_section(window)", metric_settings_block)
        self.assertIn("window.combo_metric_mode", mode_selector_block)
        self.assertIn("apply_workbench_settings_combo", layout_src)
        self.assertIn("speed_row_after_stretch=", playback_block)
        self.assertNotIn("footer_row_after_stretch=(window.btn_return_full_preview,)", playback_block)
        self.assertNotIn("build_cropped_playback_controls", layout_src)
        self.assertNotIn("build_metric_mode_row", layout_src)
        self.assertNotIn("_metric_status_host", playback_block)

    def test_center_preview_page_has_no_separate_cropped_playback_host(self) -> None:
        layout_src = _layout_src()
        center_block = layout_src.split("def build_center_preview_page", 1)[1].split(
            "def build_preview_workspace_host", 1
        )[0]
        self.assertNotIn("build_cropped_playback_controls", center_block)
        self.assertNotIn("build_metric_mode_row", layout_src.split(
            "def build_preview_workspace_host", 1
        )[1].split("def build_preview_images_panel", 1)[0])

    def test_preview_workspace_reserves_consistent_mode_shell_spacing(self) -> None:
        layout_src = _layout_src()
        center_block = layout_src.split("def build_center_preview_page", 1)[1].split(
            "def build_preview_workspace_host", 1
        )[0]
        playback_block = layout_src.split("def build_sample_playback_controls", 1)[1].split(
            "def build_hidden_frame_controls", 1
        )[0]
        metric_settings_block = layout_src.split("def build_metric_settings_host", 1)[1].split(
            "def build_metric_settings_stack", 1
        )[0]
        tracking_settings_block = layout_src.split("def build_tracking_settings_form", 1)[1].split(
            "def build_tracking_settings_page", 1
        )[0]

        self.assertIn("build_hidden_preview_mode_banner(window)", center_block)
        self.assertNotIn("build_preview_mode_banner_host", layout_src)
        self.assertIn("apply_inspector_scroll_style", layout_src)
        self.assertIn("configure_workbench_adjacent_panel(host)", metric_settings_block)
        self.assertIn("apply_inspector_panel_style", layout_src)
        self.assertIn("build_preview_controls_divider", layout_src)
        self.assertIn("build_workbench_vertical_divider", layout_src)
        self.assertIn("apply_main_splitter_style", layout_src)
        self.assertIn("apply_explorer_panel_margins", layout_src)
        self.assertIn("build_explorer_root_row", layout_src)
        self.assertIn("build_explorer_tree_host", layout_src)
        self.assertNotIn("configure_explorer_root_affordance", layout_src)
        self.assertIn("apply_explorer_tree_content_margins", layout_src)
        self.assertIn("splitter.splitterMoved.connect(window._update_workspace_label)", layout_src)
        self.assertIn("apply_workbench_playback_button", layout_src)
        self.assertIn("apply_workbench_action_button(window.btn_return_full_preview)", playback_block)
        self.assertIn("apply_workbench_controls_panel_style", layout_src)
        self.assertIn("apply_workbench_playback_speed_combo", layout_src)
        self.assertIn("STYLE_WORKBENCH_VERTICAL_DIVIDER", layout_src)
        self.assertNotIn("QGroupBox", tracking_settings_block)
        self.assertIn("build_inspector_fields_section", layout_src)
        self.assertIn("apply_inspector_field_label_style", layout_src)
        self.assertIn("apply_inspector_scroll_style", layout_src)
        self.assertIn("apply_side_panel_inner_margins", layout_src)


class RoiContextMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _menu_labels(self, *, inside_roi: bool) -> list[str]:
        window = MainWindow.__new__(MainWindow)
        menu = QMenu()
        MainWindow._populate_roi_actions_menu(window, menu, inside_roi=inside_roi)
        return [action.text() for action in menu.actions()]

    def test_inside_roi_menu_includes_clear_suggest_and_export(self) -> None:
        labels = self._menu_labels(inside_roi=True)
        self.assertEqual(
            labels,
            [
                "Suggest ROI from F-actin Signal",
                "Clear ROI",
                "Export ROI",
            ],
        )

    def test_outside_roi_menu_offers_suggest_only(self) -> None:
        labels = self._menu_labels(inside_roi=False)
        self.assertEqual(labels, ["Suggest ROI from F-actin Signal"])

    def test_export_roi_menu_triggers_existing_process_handler(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._on_process_sample = MagicMock()
        menu = QMenu()
        MainWindow._populate_roi_actions_menu(window, menu, inside_roi=True)
        export_action = next(
            action for action in menu.actions() if action.text() == "Export ROI"
        )
        export_action.trigger()
        window._on_process_sample.assert_called_once()

    def test_context_menu_targets_roi_inside_rect(self) -> None:
        window = MainWindow.__new__(MainWindow)
        canvas = ImageCanvas(window)
        import numpy as np

        canvas._frame = np.zeros((100, 200, 3), dtype=np.uint8)
        canvas._roi = RectROI(40, 30, 60, 40)
        canvas._pixmap = QPixmap.fromImage(
            QImage(200, 100, QImage.Format.Format_RGB888)
        )
        canvas._scale = 1.0
        canvas._offset_x = 0
        canvas._offset_y = 0
        wx, wy = canvas._image_to_widget(70, 50)
        self.assertTrue(canvas._context_menu_targets_roi(QPoint(wx, wy)))

    def test_context_menu_outside_roi_is_not_targeted(self) -> None:
        window = MainWindow.__new__(MainWindow)
        canvas = ImageCanvas(window)
        import numpy as np

        canvas._frame = np.zeros((100, 200, 3), dtype=np.uint8)
        canvas._roi = RectROI(40, 30, 60, 40)
        canvas._pixmap = QPixmap.fromImage(
            QImage(200, 100, QImage.Format.Format_RGB888)
        )
        canvas._scale = 1.0
        canvas._offset_x = 0
        canvas._offset_y = 0
        self.assertFalse(canvas._context_menu_targets_roi(QPoint(5, 5)))


class ExportNameBehaviorTests(unittest.TestCase):
    def test_process_sample_uses_sample_final_export_name_not_edit_field(self) -> None:
        gui_src = (ROOT / "actintrack_app/gui.py").read_text(encoding="utf-8")
        process_block = gui_src.split("def _process_kwargs_from_sample", 1)[1].split(
            "def _confirm_overwrite", 1
        )[0]
        self.assertIn('self._current_sample.get("final_export_name"', process_block)
        self.assertNotIn("edit_export_name", process_block)


if __name__ == "__main__":
    unittest.main()
