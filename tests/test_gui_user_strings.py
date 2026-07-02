"""Tests for user-facing display label helpers."""

from __future__ import annotations

import unittest

from actintrack_app.gui_user_strings import processing_status_display


class GuiUserStringsTests(unittest.TestCase):
    def test_processing_status_display_known_codes(self) -> None:
        self.assertEqual(processing_status_display("roi_marked"), "ROI marked")
        self.assertEqual(
            processing_status_display("motion_index_generated"),
            "Metrics generated",
        )

    def test_processing_status_display_unknown_code(self) -> None:
        self.assertEqual(
            processing_status_display("custom_lab_status"),
            "Custom lab status",
        )


if __name__ == "__main__":
    unittest.main()
