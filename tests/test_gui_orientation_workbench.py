"""Tests for hidden Workbench orientation controls and backend compatibility."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

from actintrack_app.annotation_schema import annotation_from_legacy
from actintrack_app.gui import MainWindow
from actintrack_app.orientation import OrientationState, apply_orientation


class OrientationWorkbenchUiTests(unittest.TestCase):
    def test_hidden_orientation_controls_not_in_visible_panel_layout(self) -> None:
        layout_src = (
            Path(__file__).resolve().parents[1]
            / "actintrack_app/gui_layout_builders.py"
        ).read_text(encoding="utf-8")
        orient_block = layout_src.split("def build_unified_orient_roi_panel", 1)[1].split(
            "def create_tracking_setting_widgets", 1
        )[0]
        hidden_block = layout_src.split("def build_hidden_orientation_controls", 1)[
            1
        ].split("def build_unified_orient_roi_panel", 1)[0]

        self.assertIn("build_hidden_orientation_controls(window, panel)", orient_block)
        self.assertNotIn("rotation_row", orient_block)
        self.assertNotIn("orient_actions_row", orient_block)
        self.assertNotIn('QLabel("Rotation:")', orient_block)
        self.assertIn("window.spin_custom_angle", hidden_block)
        self.assertIn("window.chk_mirror_y", hidden_block)
        self.assertIn(".hide()", hidden_block)

    def test_orientation_backend_symbols_remain(self) -> None:
        gui_src = (
            Path(__file__).resolve().parents[1] / "actintrack_app/gui.py"
        ).read_text(encoding="utf-8")
        self.assertIn("OrientationState", gui_src)
        self.assertIn("apply_orientation", gui_src)
        self.assertIn("def _on_apply_custom_angle", gui_src)
        self.assertIn("def _on_mirror_y_axis", gui_src)
        self.assertIn("def _on_flip_180", gui_src)
        self.assertIn("def _on_reset_orientation", gui_src)


class SavedOrientationCompatibilityTests(unittest.TestCase):
    def test_legacy_annotation_orientation_applies_to_frame(self) -> None:
        ann = {
            "rotation_angle_degrees": 90.0,
            "mirror_y_axis": True,
            "flipped_180": False,
            "manual_rotation_steps": [],
            "rectangle_roi": {"x": 0, "y": 0, "width": 4, "height": 4},
        }
        orientation, _roi = annotation_from_legacy(ann)
        frame = np.arange(12, dtype=np.uint8).reshape(3, 4, 1)
        oriented = apply_orientation(frame, orientation)
        self.assertNotEqual(oriented.shape, frame.shape)

    def test_update_orientation_label_syncs_hidden_widgets(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._orientation = OrientationState(
            rotation_angle_degrees=45.0,
            mirror_y_axis=True,
        )
        window.chk_mirror_y = MagicMock()
        window.spin_custom_angle = MagicMock()

        MainWindow._update_orientation_label(window)

        window.chk_mirror_y.setChecked.assert_called_once_with(True)
        window.spin_custom_angle.setValue.assert_called_once_with(45.0)


if __name__ == "__main__":
    unittest.main()
