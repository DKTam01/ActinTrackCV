"""Tests for shared Qt dialog helpers."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QMessageBox

from actintrack_app import gui_dialogs


class AskYesNoTests(unittest.TestCase):
    def _patch_message_box(self) -> tuple[MagicMock, MagicMock]:
        patcher = patch("actintrack_app.gui_dialogs.QMessageBox")
        mock_cls = patcher.start()
        self.addCleanup(patcher.stop)
        mock_cls.StandardButton = QMessageBox.StandardButton
        mock_cls.Icon = QMessageBox.Icon
        box = MagicMock()
        mock_cls.return_value = box
        return mock_cls, box

    def test_returns_true_when_user_clicks_yes(self) -> None:
        _mock_cls, box = self._patch_message_box()
        box.exec.return_value = QMessageBox.StandardButton.Yes

        result = gui_dialogs.ask_yes_no(None, "Confirm", "Proceed?")

        self.assertTrue(result)
        box.setWindowTitle.assert_called_once_with("Confirm")
        box.setText.assert_called_once_with("Proceed?")
        box.setStandardButtons.assert_called_once()

    def test_returns_false_when_user_clicks_no(self) -> None:
        _mock_cls, box = self._patch_message_box()
        box.exec.return_value = QMessageBox.StandardButton.No

        result = gui_dialogs.ask_yes_no(None, "Confirm", "Proceed?")

        self.assertFalse(result)

    def test_passes_informative_text_when_provided(self) -> None:
        _mock_cls, box = self._patch_message_box()
        box.exec.return_value = QMessageBox.StandardButton.Yes

        gui_dialogs.ask_yes_no(
            None,
            "Delete Sample",
            "Delete this Sample?",
            informative="This cannot be undone.",
        )

        box.setInformativeText.assert_called_once_with("This cannot be undone.")

    def test_omits_informative_text_when_empty(self) -> None:
        _mock_cls, box = self._patch_message_box()
        box.exec.return_value = QMessageBox.StandardButton.No

        gui_dialogs.ask_yes_no(None, "Confirm", "Proceed?")

        box.setInformativeText.assert_not_called()


if __name__ == "__main__":
    unittest.main()
