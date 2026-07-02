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
        self.assertIn("_metric_status_host", combined)
        self.assertIn("btn_run_metrics", combined)
        self.assertIn("lbl_metric_status", combined)
        self.assertIn("lbl_last_analyzed", combined)
        self.assertNotIn("preview_crop_row", combined)
        self.assertNotIn("btn_playback_play", combined)
        self.assertNotIn("btn_playback_pause", combined)
        self.assertIn("_populate_roi_actions_menu", src)
        self.assertIn("build_roi_workflow_strip", layout_src)
        self.assertIn("slider_sample_frame", combined)
        self.assertIn("lbl_sample_frame", combined)
        self.assertIn("combo_sample_playback_speed", combined)
        self.assertIn("chk_playback_loop", combined)
        self.assertIn("btn_preview_toggle", combined)
        self.assertIn("slider_cropped_frame", combined)
        self.assertIn("lbl_cropped_frame", combined)
        self.assertIn("combo_preview_speed", combined)
        self.assertIn("btn_return_full_preview", combined)
        self.assertIn("_assemble_playback_controls_layout", src)
        self.assertNotIn("preview_transport_row", combined)
        self.assertNotIn("sample_transport_row", combined)
        self.assertIn("_build_hidden_frame_controls", src)
        self.assertIn("Return to Samples", layout_src)
        self.assertIn('"Export ROI"', layout_src)
        self.assertIn("NoWheelSpinBox", combined)
        self.assertIn("NoWheelDoubleSpinBox", combined)
        orient_block = layout_src.split("def build_unified_orient_roi_panel", 1)[1].split(
            "def create_tracking_setting_widgets", 1
        )[0]
        right_sidebar_block = layout_src.split("def build_right_sidebar", 1)[1].split(
            "def build_export_name_panel", 1
        )[0]
        self.assertIn("sample_sidebar_display_label(sample)", src)
        self.assertIn("tracking_result_group_title", combined)
        self.assertNotIn("Tracking Result: No sample selected", combined)
        self.assertNotIn("'s Tracking Result", combined)
        self.assertIn("build_export_name_panel(window)", orient_block)
        self.assertIn("configure_orient_panel_action_button", orient_block)
        self.assertNotIn('QGroupBox("Orient and ROI")', orient_block)
        self.assertNotIn('QGroupBox("Export Name")', orient_block)
        export_name_block = layout_src.split("def build_export_name_panel", 1)[1].split(
            "def build_unified_orient_roi_panel", 1
        )[0]
        self.assertIn('"Export name"', export_name_block)
        self.assertNotIn('"Export name:"', export_name_block)
        self.assertNotIn('QGroupBox("Export Name")', export_name_block)
        self.assertIn("Scale proportionally to frame size", src)
        self.assertNotIn("Dr. Ju", src)
        self.assertIn('"Metric Analysis"', layout_src)
        self.assertNotIn("Select a data file first", src)
        self.assertNotIn("roi_section", orient_block)
        self.assertIn("orient_actions_row", orient_block)
        self.assertNotIn("orient_extras", orient_block)
        self.assertNotIn('addTab(sample_tab, "Sample")', right_sidebar_block)
        self.assertLess(
            orient_block.index("build_export_name_panel(window)"),
            orient_block.index("window.btn_process ="),
        )

    def test_workbench_center_image_scaffold(self) -> None:
        layout_src = _read("actintrack_app/gui_layout_builders.py")
        center_block = layout_src.split("def build_center_preview_page", 1)[1].split(
            "def build_image_workspace_row", 1
        )[0]
        workspace_block = layout_src.split("def build_image_workspace_row", 1)[1].split(
            "def build_roi_preview_panel", 1
        )[0]
        roi_preview_block = layout_src.split("def build_roi_preview_panel", 1)[1].split(
            "def build_metric_status_strip", 1
        )[0]
        self.assertIn("build_image_workspace_row(window)", center_block)
        self.assertIn("window._main_image_column", workspace_block)
        self.assertIn("build_roi_workflow_strip(window, main_image_layout)", workspace_block)
        self.assertIn("build_sample_playback_controls(window, main_image_layout)", workspace_block)
        self.assertNotIn(
            "build_sample_playback_controls(window, center_layout)",
            center_block,
        )
        self.assertIn("window.roi_preview_canvas", roi_preview_block)
        self.assertIn("set_interactive(False)", roi_preview_block)
        self.assertIn("ROI_PREVIEW_PANEL_OBJECT_NAME", roi_preview_block)
        self.assertIn("def build_right_sidebar", layout_src)
        self.assertIn('"Orient && ROI"', layout_src)
        self.assertIn("build_main_workspace", layout_src)
        self.assertIn("build_right_sidebar(window)", layout_src)

    def test_roi_workflow_controls_near_image_not_in_orient_panel(self) -> None:
        layout_src = _read("actintrack_app/gui_layout_builders.py")
        orient_block = layout_src.split("def build_unified_orient_roi_panel", 1)[1].split(
            "def create_tracking_setting_widgets", 1
        )[0]
        workflow_block = layout_src.split("def build_roi_workflow_strip", 1)[1].split(
            "def build_metric_status_strip", 1
        )[0]
        workspace_block = layout_src.split("def build_image_workspace_row", 1)[1].split(
            "def build_roi_preview_panel", 1
        )[0]

        self.assertIn("window.lbl_roi_save_status", workflow_block)
        self.assertIn("window.lbl_metric_status", workflow_block)
        self.assertIn("window.lbl_last_analyzed", workflow_block)
        self.assertNotIn("window.btn_roi_actions", workflow_block)
        self.assertNotIn("Right-click the preview to suggest or clear ROI.", workflow_block)
        self.assertNotIn("window.btn_roi_actions", orient_block)
        self.assertNotIn("window.lbl_roi_save_status", orient_block)
        self.assertNotIn("build_roi_workflow_strip", orient_block)
        self.assertIn("window.chk_mirror_y", orient_block)
        self.assertIn("window.btn_process", orient_block)
        self.assertIn("build_export_name_panel(window)", orient_block)
        self.assertIn("build_roi_workflow_strip(window, main_image_layout)", workspace_block)

    def test_metric_status_labels_in_workbench_not_metric_strip(self) -> None:
        layout_src = _read("actintrack_app/gui_layout_builders.py")
        gui_src = _read("actintrack_app/gui.py")
        workflow_block = layout_src.split("def build_roi_workflow_strip", 1)[1].split(
            "def build_metric_status_strip", 1
        )[0]
        metric_strip_block = layout_src.split("def build_metric_status_strip", 1)[1].split(
            "def build_sample_playback_controls", 1
        )[0]

        self.assertIn("window.lbl_metric_status", workflow_block)
        self.assertIn("window.lbl_last_analyzed", workflow_block)
        self.assertNotIn("window.lbl_metric_status", metric_strip_block)
        self.assertNotIn("window.lbl_last_analyzed", metric_strip_block)
        self.assertIn("window.btn_metric_analysis", metric_strip_block)
        self.assertIn("window.btn_run_metrics", metric_strip_block)
        self.assertIn("def _update_metric_freshness_label", gui_src)
        self.assertIn("self.lbl_metric_status.setText", gui_src)
        self.assertIn("self.lbl_last_analyzed.setText", gui_src)
        self.assertIn("def build_right_sidebar", layout_src)
        self.assertIn('"Analysis"', layout_src)

    def test_sample_tab_and_notes_ui_removed(self) -> None:
        layout_src = _read("actintrack_app/gui_layout_builders.py")
        gui_src = _read("actintrack_app/gui.py")
        samples_panel_block = layout_src.split("def build_samples_panel", 1)[1].split(
            "def build_center_preview_page", 1
        )[0]
        right_sidebar_block = layout_src.split("def build_right_sidebar", 1)[1].split(
            "def build_export_name_panel", 1
        )[0]

        self.assertNotIn("sample_tab = QWidget()", layout_src)
        self.assertNotIn('addTab(sample_tab, "Sample")', layout_src)
        self.assertNotIn("build_notes_panel", layout_src)
        self.assertNotIn("build_tracking_result_panel", layout_src)
        self.assertNotIn("window.txt_notes", layout_src)
        self.assertNotIn("build_notes_panel(window)", samples_panel_block)
        self.assertIn('"Orient && ROI"', right_sidebar_block)
        self.assertIn('"Analysis"', right_sidebar_block)
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

    def test_user_doc_uses_condition_group(self) -> None:
        doc = _read("ActinTrackCV_User_Documentation_Refined.md")
        self.assertIn("Condition Group", doc)
        # The legacy-terminology note still records the old name as legacy.
        self.assertIn("| Breed | Condition Group |", doc)


if __name__ == "__main__":
    unittest.main()
