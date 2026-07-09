"""Guard the user-facing "Condition Group" terminology (formerly "Breed").

These checks read source/doc text rather than launching the GUI, so they stay
stable in headless environments. Internal compatibility names (``breed``,
``BreedSummaryRow``, ``last_import_breed``, the ``breed`` metadata key, etc.)
are intentionally left untouched and are not asserted against here.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class UserFacingTerminologyTests(unittest.TestCase):
    def test_gui_has_no_user_facing_breed_labels(self) -> None:
        src = _read("actintrack_app/gui.py")
        layout_src = _read("actintrack_app/gui_layout_builders.py")
        combined = src + layout_src
        # The workspace tree and dialog text must not expose "Breed".
        self.assertNotIn('"Breed:"', src)
        self.assertNotIn("this Breed?", src)
        self.assertIn("Condition Group", src)
        self.assertIn("Delete this empty Condition Group?", src)
        self.assertIn("Delete this Sample?", src)
        self.assertIn("Condition Group Not Empty", src)
        self.assertIn("tree_samples", combined)
        self.assertNotIn("Full Sample Preview — orient the data", src)
        self.assertNotIn('"◀ Prev"', src)
        self.assertNotIn('"Next ▶"', src)
        self.assertNotIn("btn_refresh_samples", src)
        self.assertIn("Refresh Explorer", src)
        self.assertIn("_LEFT_PANEL_MIN_WIDTH", src)
        self.assertIn("setCollapsible", layout_src)
        self.assertIn("_DEFAULT_SPLITTER_SIZES", src)
        self.assertNotIn('addTab(preview, "Frame")', combined)
        self.assertNotIn("Selected Data File", src)
        self.assertIn("btn_playback_toggle", combined)
        self.assertIn("_sample_playback_host", combined)
        self.assertIn("btn_run_metrics", combined)
        self.assertIn("lbl_metric_status", combined)
        self.assertIn("lbl_last_analyzed", combined)
        self.assertNotIn("preview_crop_row", combined)
        self.assertNotIn("btn_playback_play", combined)
        self.assertNotIn("btn_playback_pause", combined)
        self.assertIn("_populate_roi_actions_menu", src)
        self.assertIn("inside_roi", src)
        self.assertIn("build_roi_workflow_strip", layout_src)
        self.assertIn("build_metric_status_labels_row", layout_src)
        self.assertIn("slider_sample_frame", combined)
        self.assertIn("lbl_sample_frame", combined)
        self.assertIn("combo_sample_playback_speed", combined)
        self.assertIn("chk_playback_loop", combined)
        self.assertIn("combo_metric_mode", combined)
        self.assertIn("btn_return_full_preview", combined)
        self.assertIn("assemble_playback_controls_layout", layout_src)
        self.assertNotIn("preview_transport_row", combined)
        self.assertNotIn("sample_transport_row", combined)
        self.assertIn("_build_hidden_frame_controls", src)
        self.assertIn("Return to Samples", layout_src)
        self.assertIn("Export ROI", src)
        self.assertIn("NoWheelSpinBox", combined)
        self.assertIn("NoWheelDoubleSpinBox", combined)
        orient_block = layout_src.split("def build_hidden_orientation_controls", 1)[1].split(
            "def build_analysis_page", 1
        )[0]
        hidden_orient_block = layout_src.split("def build_hidden_orientation_host", 1)[
            1
        ].split("def build_hidden_export_host", 1)[0]
        workflow_block = layout_src.split("def build_roi_workflow_strip", 1)[1].split(
            "def build_metric_status_labels_row", 1
        )[0]
        metric_labels_block = layout_src.split(
            "def build_metric_status_labels_row", 1
        )[1].split("def create_metric_action_buttons", 1)[0]
        self.assertIn("sample_sidebar_display_label(sample)", src)
        self.assertIn("tracking_result_group_title", combined)
        self.assertNotIn("Tracking Result: No sample selected", combined)
        self.assertNotIn("'s Tracking Result", combined)
        self.assertNotIn("build_export_name_panel(window)", workflow_block)
        self.assertNotIn("build_export_name_panel(window)", metric_labels_block)
        self.assertIn("build_hidden_export_host(window)", layout_src)
        self.assertIn("configure_orient_panel_action_button", layout_src)
        self.assertNotIn('QGroupBox("Orient and ROI")', workflow_block)
        self.assertNotIn('QGroupBox("Export Name")', workflow_block)
        export_name_block = layout_src.split("def build_export_name_panel", 1)[1].split(
            "def build_hidden_orientation_controls", 1
        )[0]
        hidden_export_block = layout_src.split("def build_hidden_export_host", 1)[1].split(
            "def build_export_name_panel", 1
        )[0]
        self.assertIn('"Export name"', export_name_block)
        self.assertNotIn('"Export name:"', export_name_block)
        self.assertNotIn('QGroupBox("Export Name")', export_name_block)
        self.assertIn("build_export_name_panel(window)", hidden_export_block)
        self.assertIn("Scale proportionally to frame size", src)
        self.assertNotIn("Dr. Ju", src)
        self.assertIn('"Metric Analysis"', layout_src)
        self.assertNotIn("Select a data file first", src)
        self.assertNotIn("roi_section", workflow_block)
        self.assertNotIn("orient_actions_row", hidden_orient_block)
        self.assertNotIn('QLabel("Rotation:")', hidden_orient_block)
        self.assertNotIn("Mirror Y-Axis", workflow_block)
        self.assertIn("build_hidden_orientation_controls", layout_src)
        self.assertNotIn("build_export_name_panel(window)", workflow_block)
        self.assertNotIn("orient_extras", workflow_block)
        self.assertNotIn('addTab(sample_tab, "Sample")', layout_src)

    def test_workbench_center_image_scaffold(self) -> None:
        layout_src = _read("actintrack_app/gui_layout_builders.py")
        center_block = layout_src.split("def build_center_preview_page", 1)[1].split(
            "def build_preview_workspace_host", 1
        )[0]
        workspace_block = layout_src.split("def build_preview_workspace_host", 1)[1].split(
            "def build_preview_images_panel", 1
        )[0]
        preview_panel_block = layout_src.split("def build_preview_images_panel", 1)[1].split(
            "def build_roi_preview_panel", 1
        )[0]
        roi_preview_block = layout_src.split("def build_roi_preview_panel", 1)[1].split(
            "def build_roi_workflow_strip", 1
        )[0]
        self.assertIn("build_preview_workspace_host(window)", center_block)
        self.assertIn("images_layout = QHBoxLayout(panel)", preview_panel_block)
        self.assertIn("build_roi_workflow_strip(window, layout)", workspace_block)
        self.assertIn("build_metric_status_labels_row(window, layout)", workspace_block)
        self.assertIn("build_sample_playback_controls(window, layout)", workspace_block)
        self.assertNotIn(
            "build_sample_playback_controls(window, center_layout)",
            center_block,
        )
        self.assertIn("window.roi_preview_canvas", roi_preview_block)
        self.assertIn("set_interactive(False)", roi_preview_block)
        self.assertIn("configure_workbench_adjacent_panel(host)", roi_preview_block)
        self.assertNotIn("def build_right_sidebar", layout_src)
        self.assertNotIn("build_right_sidebar(window)", layout_src)
        self.assertIn("build_main_workspace", layout_src)
        self.assertIn("window._adjacent_panel_stack", preview_panel_block)
        self.assertIn("build_metric_settings_host(window)", preview_panel_block)
        self.assertNotIn('"ROI preview"', roi_preview_block)

    def test_roi_workflow_controls_near_image_not_in_orient_panel(self) -> None:
        layout_src = _read("actintrack_app/gui_layout_builders.py")
        hidden_orient_block = layout_src.split("def build_hidden_orientation_controls", 1)[
            1
        ].split("def build_analysis_page", 1)[0]
        workflow_block = layout_src.split("def build_roi_workflow_strip", 1)[1].split(
            "def build_metric_status_labels_row", 1
        )[0]
        metric_labels_block = layout_src.split(
            "def build_metric_status_labels_row", 1
        )[1].split("def create_metric_action_buttons", 1)[0]
        workspace_block = layout_src.split("def build_preview_workspace_host", 1)[1].split(
            "def build_preview_images_panel", 1
        )[0]

        self.assertIn("window.lbl_roi_save_status", workflow_block)
        self.assertIn("window.lbl_metric_status", metric_labels_block)
        self.assertIn("window.lbl_last_analyzed", metric_labels_block)
        self.assertNotIn("window.btn_roi_actions", workflow_block)
        self.assertNotIn("Right-click the preview to suggest or clear ROI.", workflow_block)
        self.assertNotIn("window.btn_roi_actions", hidden_orient_block)
        self.assertNotIn("window.lbl_roi_save_status", hidden_orient_block)
        self.assertNotIn("build_roi_workflow_strip", hidden_orient_block)
        self.assertIn("window.spin_custom_angle", hidden_orient_block)
        self.assertNotIn("window.btn_process", workflow_block)
        self.assertNotIn("build_export_name_panel(window)", workflow_block)
        self.assertIn("build_roi_workflow_strip(window, layout)", workspace_block)

    def test_metric_status_labels_in_workbench_not_metric_strip(self) -> None:
        layout_src = _read("actintrack_app/gui_layout_builders.py")
        gui_src = _read("actintrack_app/gui.py")
        workflow_block = layout_src.split("def build_roi_workflow_strip", 1)[1].split(
            "def build_metric_status_labels_row", 1
        )[0]
        metric_labels_block = layout_src.split(
            "def build_metric_status_labels_row", 1
        )[1].split("def create_metric_action_buttons", 1)[0]
        metric_buttons_block = layout_src.split("def create_metric_action_buttons", 1)[1].split(
            "def build_sample_playback_controls", 1
        )[0]

        self.assertNotIn("window.lbl_metric_status", workflow_block)
        self.assertNotIn("window.lbl_last_analyzed", workflow_block)
        self.assertIn("window.lbl_metric_status", metric_labels_block)
        self.assertIn("window.lbl_last_analyzed", metric_labels_block)
        self.assertNotIn("window.lbl_metric_status", metric_buttons_block)
        self.assertNotIn("window.lbl_last_analyzed", metric_buttons_block)
        self.assertIn("window.btn_metric_analysis", metric_buttons_block)
        self.assertIn("window.btn_run_metrics", metric_buttons_block)
        self.assertIn("def _update_metric_freshness_label", gui_src)
        self.assertIn("self.lbl_metric_status.setText", gui_src)
        self.assertIn("self.lbl_last_analyzed.setText", gui_src)
        self.assertIn("def build_analysis_page", layout_src)
        self.assertIn("btn_refresh_analysis", layout_src)
        self.assertIn("btn_return_to_samples", layout_src)

    def test_sample_tab_and_notes_ui_removed(self) -> None:
        layout_src = _read("actintrack_app/gui_layout_builders.py")
        gui_src = _read("actintrack_app/gui.py")
        samples_panel_block = layout_src.split("def build_samples_panel", 1)[1].split(
            "def build_center_preview_page", 1
        )[0]
        analysis_page_block = layout_src.split("def build_analysis_page", 1)[1].split(
            "def build_metric_settings_host", 1
        )[0]

        self.assertNotIn("sample_tab = QWidget()", layout_src)
        self.assertNotIn('addTab(sample_tab, "Sample")', layout_src)
        self.assertNotIn("build_notes_panel", layout_src)
        self.assertNotIn("build_tracking_result_panel", layout_src)
        self.assertNotIn("window.txt_notes", layout_src)
        self.assertNotIn("build_notes_panel(window)", samples_panel_block)
        self.assertIn("btn_refresh_analysis", analysis_page_block)
        self.assertIn("btn_return_to_samples", analysis_page_block)
        self.assertIn("_loaded_sample_notes", gui_src)
        self.assertIn("notes=self._loaded_sample_notes", gui_src)
        self.assertNotIn("txt_notes", gui_src)

    def test_gui_refreshes_roi_preview_panel(self) -> None:
        src = _read("actintrack_app/gui.py")
        self.assertIn("def _refresh_roi_preview_panel", src)
        self.assertIn("crop_rect_roi", src)
        self.assertIn("_refresh_roi_preview_panel()", src)

    def test_preview_canvas_has_roi_context_menu(self) -> None:
        src = _read("actintrack_app/gui_canvas.py")
        self.assertIn("_on_context_menu", src)
        self.assertIn("_populate_roi_actions_menu", src)

        gui = _read("actintrack_app/gui.py")
        self.assertIn("Suggest ROI from F-actin Signal", gui)
        self.assertIn("Clear ROI", gui)
        self.assertIn("Export ROI", gui)
        self.assertIn("inside_roi", gui)

    def test_analysis_view_headers_use_condition_group(self) -> None:
        src = _read("actintrack_app/analysis_view.py")
        self.assertNotIn("Breed Summary", src)
        self.assertNotIn("Breed Comparison", src)
        self.assertIn("Condition Group Summary", src)
        self.assertIn("Condition Group Comparison", src)
        self.assertIn('"Condition Group"', src)

    def test_menu_and_purge_labels_use_condition_group(self) -> None:
        menus = _read("actintrack_app/gui_menus.py")
        self.assertNotIn('"Breed:"', menus)
        self.assertIn('"Condition Group:"', menus)

        self.assertIn("Getting Started", menus)
        self.assertNotIn("How to Run App", menus)
        self.assertIn("Advanced Filtered Cleanup", menus)
        self.assertNotIn("Filtered Purge (advanced)", menus)
        self.assertIn("processing_status_display", menus)
        self.assertNotIn('"proportional_scaled"', menus.split("PropagateDialog")[0])

        purge = _read("actintrack_app/purge_cleanup_dialog.py")
        self.assertNotIn("app database", purge)
        self.assertIn("copied video", purge)
        self.assertNotIn("Breed Annotations Only", purge)
        self.assertNotIn("Complete Breed Purge", purge)
        self.assertNotIn("raw/", purge)
        self.assertIn("Condition Group Annotations Only", purge)
        self.assertIn("Complete Condition Group Purge", purge)

    def test_readme_uses_condition_group(self) -> None:
        readme = _read("README.md")
        # No capitalized user-facing "Breed" token should remain.
        self.assertNotIn("**Breed**", readme)
        self.assertNotIn("by Breed", readme)
        self.assertIn("Condition Group", readme)

    def test_workbench_has_two_pane_splitter_without_right_sidebar(self) -> None:
        layout_src = _read("actintrack_app/gui_layout_builders.py")
        workspace_block = layout_src.split("def build_main_workspace", 1)[1].split(
            "def build_left_sidebar", 1
        )[0]
        self.assertIn("DEFAULT_SPLITTER_SIZES = [LEFT_PANEL_MIN_WIDTH, 900]", layout_src)
        self.assertNotIn("RIGHT_PANEL_MIN_WIDTH", layout_src)
        self.assertNotIn("build_right_sidebar", workspace_block)
        self.assertNotIn("window._right_sidebar", workspace_block)
        self.assertEqual(workspace_block.count("splitter.addWidget"), 2)

    def test_metric_settings_and_analysis_routing(self) -> None:
        layout_src = _read("actintrack_app/gui_layout_builders.py")
        gui_src = _read("actintrack_app/gui.py")
        self.assertIn("build_metric_settings_stack", layout_src)
        self.assertIn("window._right_stack = stack", layout_src)
        self.assertIn("build_analysis_page(window)", layout_src)
        self.assertIn("def show_analysis_view", gui_src)
        self.assertIn("self._center_stack.setCurrentIndex(1)", gui_src)
        self.assertIn("self._right_stack.setCurrentIndex(0)", gui_src)
        self.assertIn("self._right_stack.setCurrentIndex(1)", gui_src)
        self.assertNotIn("_on_right_tab_changed", gui_src)
        self.assertNotIn("_right_tabs", gui_src)

    def test_user_doc_uses_condition_group(self) -> None:
        doc = _read("ActinTrackCV_User_Documentation_Refined.md")
        self.assertIn("Condition Group", doc)
        # The legacy-terminology note still records the old name as legacy.
        self.assertIn("| Breed | Condition Group |", doc)


if __name__ == "__main__":
    unittest.main()
