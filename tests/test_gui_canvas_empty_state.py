"""Canvas empty-state and fixed-size orientation legend (CLEAN1 UX)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import numpy as np
from PyQt6.QtWidgets import QApplication

from actintrack_app.gui_canvas import ImageCanvas
from actintrack_app.metric_analysis_ui import ORIENTATION_LEGEND_TEXT


class CanvasEmptyStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_empty_state_replaces_blank_preview(self) -> None:
        canvas = ImageCanvas(MagicMock())
        canvas.resize(480, 360)
        canvas.set_empty_state(
            "F-actin Orientation has not been generated for this sample."
        )
        pixmap = canvas.pixmap()
        self.assertIsNotNone(pixmap)
        self.assertGreater(pixmap.width(), 0)
        self.assertEqual(
            canvas._empty_state_message,
            "F-actin Orientation has not been generated for this sample.",
        )

    def test_preview_frame_clears_empty_state_and_can_show_legend(self) -> None:
        canvas = ImageCanvas(MagicMock())
        canvas.resize(480, 360)
        canvas.set_empty_state("Tracking results have not been generated for this sample.")
        frame = np.zeros((40, 50, 3), dtype=np.uint8)
        canvas.set_preview_frame(frame)
        self.assertIsNone(canvas._empty_state_message)
        canvas.set_orientation_legend_visible(True)
        self.assertTrue(canvas._orientation_legend_visible)
        self.assertIn("radial", ORIENTATION_LEGEND_TEXT)

    def test_nucleus_review_flag_does_not_change_coordinates(self) -> None:
        canvas = ImageCanvas(MagicMock())
        canvas.resize(480, 360)
        canvas.set_frame(np.zeros((40, 50, 3), dtype=np.uint8))
        canvas.set_scientific_overlay(
            cutoff_y=12.0,
            nucleus_xy=(8.0, 4.0),
            nucleus_needs_review=True,
        )
        self.assertEqual(canvas._nucleus_xy, (8.0, 4.0))
        self.assertTrue(canvas._nucleus_needs_review)
        self.assertEqual(canvas._cutoff_y, 12.0)


if __name__ == "__main__":
    unittest.main()
