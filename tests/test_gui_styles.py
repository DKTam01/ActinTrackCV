"""Regression tests for shared GUI style tokens."""

from __future__ import annotations

import unittest

from actintrack_app import gui_styles


class GuiStylesTests(unittest.TestCase):
    def test_tracking_result_group_title_no_sample(self) -> None:
        self.assertEqual(
            gui_styles.tracking_result_group_title(None),
            "Tracking / Motion Index Results: No sample selected",
        )
        self.assertEqual(
            gui_styles.tracking_result_group_title(""),
            "Tracking / Motion Index Results: No sample selected",
        )

    def test_tracking_result_group_title_with_sample(self) -> None:
        self.assertEqual(
            gui_styles.tracking_result_group_title("Control / clip.mp4"),
            "Tracking / Motion Index Results: Control / clip.mp4",
        )

    def test_hint_and_status_styles_use_shared_font_sizes(self) -> None:
        self.assertIn(f"font-size: {gui_styles.FONT_SIZE_HINT}px", gui_styles.STYLE_HINT_LABEL)
        self.assertIn(str(gui_styles.FONT_SIZE_SMALL), gui_styles.STYLE_SMALL_LABEL)

    def test_apply_status_style_saved_and_warning(self) -> None:
        from unittest.mock import Mock

        label = Mock()
        gui_styles.apply_status_style(label, saved=True)
        saved_style = label.setStyleSheet.call_args[0][0]
        self.assertIn(gui_styles.COLOR_STATUS_SAVED, saved_style)
        self.assertIn(f"font-size: {gui_styles.FONT_SIZE_STATUS}px", saved_style)

        label.reset_mock()
        gui_styles.apply_status_style(label, saved=False)
        warning_style = label.setStyleSheet.call_args[0][0]
        self.assertIn(gui_styles.COLOR_STATUS_WARNING, warning_style)

    def test_panel_margin_constants(self) -> None:
        self.assertEqual(gui_styles.PANEL_MARGIN, 6)
        self.assertEqual(gui_styles.PANEL_INNER_MARGIN, 8)

    def test_metric_status_panel_style_tokens(self) -> None:
        self.assertEqual(gui_styles.METRIC_STATUS_PANEL_OBJECT_NAME, "metricStatusPanel")
        self.assertIn(
            gui_styles.METRIC_STATUS_PANEL_OBJECT_NAME,
            gui_styles.STYLE_METRIC_STATUS_PANEL,
        )
        self.assertIn("transparent", gui_styles.STYLE_METRIC_STATUS_PANEL)
        self.assertIn("border: none", gui_styles.STYLE_METRIC_STATUS_PANEL)
        self.assertEqual(gui_styles.METRIC_STATUS_INNER_SPACING, 6)
        self.assertEqual(gui_styles.METRIC_STATUS_LABEL_SPACING, 2)

    def test_playback_control_size_tokens(self) -> None:
        self.assertEqual(gui_styles.PLAYBACK_FRAME_LABEL_MIN_WIDTH, 72)
        self.assertEqual(gui_styles.PLAYBACK_SLIDER_MIN_WIDTH, 120)
        self.assertEqual(gui_styles.PLAYBACK_SPEED_COMBO_MIN_WIDTH, 72)
        self.assertEqual(gui_styles.WORKBENCH_ACTION_CONTROL_MIN_WIDTH, 132)
        self.assertEqual(gui_styles.WORKBENCH_CONTROL_HEIGHT, 24)
        self.assertEqual(gui_styles.WORKBENCH_SPEED_ROW_SPACING, 6)
        self.assertEqual(gui_styles.PLAYBACK_RETURN_ROW_HEIGHT, 28)

    def test_workbench_surface_style_tokens(self) -> None:
        self.assertEqual(gui_styles.EXPLORER_PANEL_OBJECT_NAME, "explorerPanel")
        self.assertEqual(gui_styles.EXPLORER_ROOT_ROW_OBJECT_NAME, "explorerRootRow")
        self.assertEqual(gui_styles.EXPLORER_ROOT_PATH_OBJECT_NAME, "explorerRootPath")
        self.assertIn(gui_styles.COLOR_EXPLORER_BACKGROUND, gui_styles.STYLE_EXPLORER_PANEL)
        self.assertIn(gui_styles.COLOR_EXPLORER_ROOT_BACKGROUND, gui_styles.STYLE_EXPLORER_PANEL)
        self.assertIn(gui_styles.COLOR_EXPLORER_TEXT, gui_styles.STYLE_EXPLORER_PANEL)
        self.assertEqual(gui_styles.COLOR_EXPLORER_SAMPLE_TEXT, "#a8b0bd")
        self.assertEqual(gui_styles.COLOR_EXPLORER_SELECTION, "#2a4a66")
        self.assertEqual(gui_styles.COLOR_EXPLORER_SELECTION_TEXT, "#e0e0e0")
        self.assertEqual(gui_styles.EXPLORER_CONTENT_LEFT_PADDING, 6)
        self.assertEqual(
            gui_styles.EXPLORER_TREE_ROOT_OFFSET,
            gui_styles.EXPLORER_TREE_INDENTATION,
        )
        self.assertEqual(
            gui_styles.COLOR_EXPLORER_ROOT_BACKGROUND,
            gui_styles.COLOR_EXPLORER_BACKGROUND,
        )
        self.assertIn(gui_styles.COLOR_EXPLORER_SELECTION, gui_styles.STYLE_EXPLORER_PANEL)
        self.assertEqual(gui_styles.COLOR_EXPLORER_INDENT_GUIDE, "#383838")
        self.assertEqual(gui_styles.EXPLORER_INDENT_GUIDE_WIDTH, 1)
        self.assertGreater(
            int(gui_styles.COLOR_EXPLORER_GROUP_TEXT[1:], 16),
            int(gui_styles.COLOR_EXPLORER_SAMPLE_TEXT[1:], 16),
        )
        self.assertIn(gui_styles.COLOR_WORKSPACE_DIVIDER, gui_styles.STYLE_MAIN_SPLITTER)
        self.assertIn(gui_styles.COLOR_WORKSPACE_BACKGROUND, gui_styles.STYLE_WORKSPACE_PREVIEW_PANEL)
        self.assertIn(gui_styles.COLOR_INSPECTOR_BACKGROUND, gui_styles.STYLE_INSPECTOR_PANEL)
        self.assertLess(
            int(gui_styles.COLOR_EXPLORER_BACKGROUND[1:], 16),
            int(gui_styles.COLOR_WORKSPACE_BACKGROUND[1:], 16),
        )
        self.assertEqual(
            gui_styles.explorer_workspace_display_name("/tmp/My Workspace"),
            "My Workspace",
        )
        self.assertEqual(gui_styles.explorer_workspace_display_name(None), "—")

    def test_workbench_button_style_tokens(self) -> None:
        self.assertIn(
            gui_styles.WORKBENCH_ACTION_BUTTON_OBJECT_NAME,
            gui_styles.STYLE_WORKBENCH_ACTION_BUTTON,
        )
        self.assertIn(
            gui_styles.WORKBENCH_PLAYBACK_BUTTON_OBJECT_NAME,
            gui_styles.STYLE_WORKBENCH_PLAYBACK_BUTTON,
        )
        self.assertIn(gui_styles.COLOR_CONTROL_BACKGROUND, gui_styles.STYLE_WORKBENCH_ACTION_BUTTON)
        self.assertEqual(
            gui_styles.COLOR_BUTTON_BACKGROUND,
            gui_styles.COLOR_CONTROL_BACKGROUND,
        )
        self.assertEqual(
            gui_styles.COLOR_INSPECTOR_FIELD_BACKGROUND,
            gui_styles.COLOR_CONTROL_BACKGROUND,
        )
        self.assertIn(
            gui_styles.WORKBENCH_PLAYBACK_SPEED_COMBO_OBJECT_NAME,
            gui_styles.STYLE_WORKBENCH_PLAYBACK_SPEED_COMBO,
        )
        self.assertIn(
            gui_styles.WORKBENCH_CONTROLS_PANEL_OBJECT_NAME,
            gui_styles.STYLE_WORKBENCH_CONTROLS_PANEL,
        )
        self.assertNotIn("transparent", gui_styles.STYLE_WORKBENCH_ACTION_BUTTON)
        self.assertIn(
            gui_styles.WORKBENCH_SETTINGS_COMBO_OBJECT_NAME,
            gui_styles.STYLE_WORKBENCH_SETTINGS_COMBO,
        )
        self.assertIn("::drop-down", gui_styles.STYLE_WORKBENCH_SETTINGS_COMBO)
        self.assertIn(
            f"min-height: {gui_styles.WORKBENCH_CONTROL_HEIGHT}px",
            gui_styles.STYLE_WORKBENCH_ACTION_BUTTON,
        )
        self.assertNotIn("border: 1px solid", gui_styles.STYLE_WORKBENCH_ACTION_BUTTON)

    def test_orient_panel_layout_tokens(self) -> None:
        self.assertEqual(gui_styles.ORIENT_PANEL_BUTTON_MIN_HEIGHT, 28)
        self.assertEqual(gui_styles.ROI_HINT_STATUS_SPACING, 2)

    def test_configure_orient_panel_action_button(self) -> None:
        from unittest.mock import Mock

        button = Mock()
        gui_styles.configure_orient_panel_action_button(button)
        button.setSizePolicy.assert_called_once()
        button.setMinimumHeight.assert_called_once_with(
            gui_styles.ORIENT_PANEL_BUTTON_MIN_HEIGHT
        )


if __name__ == "__main__":
    unittest.main()
