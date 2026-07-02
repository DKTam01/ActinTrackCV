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
        # The workspace tree and dialog text must not expose "Breed".
        self.assertNotIn('"Breed:"', src)
        self.assertNotIn("this Breed?", src)
        self.assertIn("Condition Group", src)
        self.assertIn("Delete this empty Condition Group?", src)
        self.assertIn("Delete this Sample?", src)
        self.assertIn("Condition Group Not Empty", src)
        self.assertIn("tree_samples", src)
        self.assertNotIn("Full Sample Preview — orient the data", src)
        self.assertNotIn('"◀ Prev"', src)
        self.assertNotIn('"Next ▶"', src)
        self.assertNotIn("btn_refresh_samples", src)
        self.assertIn("Refresh Explorer", src)
        self.assertIn("_LEFT_PANEL_MIN_WIDTH", src)
        self.assertIn("setCollapsible", src)
        self.assertIn("_DEFAULT_SPLITTER_SIZES", src)
        self.assertNotIn('addTab(preview, "Frame")', src)
        self.assertNotIn("Selected Data File", src)
        self.assertIn("btn_playback_toggle", src)
        self.assertIn("_metric_status_host", src)
        self.assertIn("btn_run_metrics", src)
        self.assertIn("lbl_metric_status", src)
        self.assertIn("lbl_last_analyzed", src)
        self.assertNotIn("preview_crop_row", src)
        self.assertNotIn("btn_playback_play", src)
        self.assertNotIn("btn_playback_pause", src)
        self.assertIn("Right-click the preview to suggest or clear ROI.", src)
        self.assertIn("btn_roi_actions", src)
        self.assertIn("_populate_roi_actions_menu", src)
        self.assertIn("slider_sample_frame", src)
        self.assertIn("lbl_sample_frame", src)
        self.assertIn("combo_sample_playback_speed", src)
        self.assertIn("chk_playback_loop", src)
        self.assertIn("btn_preview_toggle", src)
        self.assertIn("slider_cropped_frame", src)
        self.assertIn("lbl_cropped_frame", src)
        self.assertIn("combo_preview_speed", src)
        self.assertIn("btn_return_full_preview", src)
        self.assertIn("_assemble_playback_controls_layout", src)
        self.assertNotIn("preview_transport_row", src)
        self.assertNotIn("sample_transport_row", src)
        self.assertIn("_build_hidden_frame_controls", src)
        self.assertIn("Return to Samples", src)
        self.assertIn('"Export ROI"', src)
        self.assertIn("NoWheelSpinBox", src)
        self.assertIn("NoWheelDoubleSpinBox", src)
        orient_block = src.split("def _build_unified_orient_roi_panel", 1)[1].split(
            "def _configure_tracking_field", 1
        )[0]
        sample_tab_block = src.split("sample_tab = QWidget()", 1)[1].split(
            "analysis_tab = QWidget()", 1
        )[0]
        self.assertIn("sample_sidebar_display_label(sample)", src)
        self.assertIn("tracking_result_group_title", src)
        self.assertNotIn("Tracking Result: No sample selected", src)
        self.assertNotIn("'s Tracking Result", src)
        self.assertIn("_build_export_name_panel()", orient_block)
        self.assertIn("configure_orient_panel_action_button", orient_block)
        self.assertNotIn('QGroupBox("Orient and ROI")', orient_block)
        self.assertNotIn('QGroupBox("Export Name")', orient_block)
        export_name_block = src.split("def _build_export_name_panel", 1)[1].split(
            "def _configure_orient_roi_control", 1
        )[0]
        self.assertIn('"Export name"', export_name_block)
        self.assertNotIn('"Export name:"', export_name_block)
        self.assertNotIn('QGroupBox("Export Name")', export_name_block)
        self.assertIn("Scale proportionally to frame size", src)
        self.assertNotIn("Dr. Ju", src)
        self.assertIn('"Metric Analysis"', src)
        self.assertNotIn("Select a data file first", src)
        self.assertIn("roi_section", orient_block)
        self.assertIn("orient_actions_row", orient_block)
        self.assertNotIn("orient_extras", orient_block)
        self.assertNotIn("_build_export_name_panel()", sample_tab_block)
        self.assertLess(
            orient_block.index("_build_export_name_panel()"),
            orient_block.index("self.btn_process ="),
        )

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
