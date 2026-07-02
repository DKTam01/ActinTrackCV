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
        self.assertEqual(gui_styles.METRIC_STATUS_INNER_SPACING, 6)
        self.assertEqual(gui_styles.METRIC_STATUS_LABEL_SPACING, 2)

    def test_playback_control_size_tokens(self) -> None:
        self.assertEqual(gui_styles.PLAYBACK_FRAME_LABEL_MIN_WIDTH, 72)
        self.assertEqual(gui_styles.PLAYBACK_SLIDER_MIN_WIDTH, 120)
        self.assertEqual(gui_styles.PLAYBACK_SPEED_COMBO_MIN_WIDTH, 72)

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
