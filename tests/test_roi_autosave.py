"""Tests for ROI autosave processing-status promotion rules."""

from __future__ import annotations

import unittest

from actintrack_app.gui import MainWindow
from actintrack_app.utils import (
    STATUS_IMPORTED,
    STATUS_MOTION_INDEX_FAILED,
    STATUS_MOTION_INDEX_GENERATED,
    STATUS_PROCESSED,
    STATUS_RAW_IMPORTED,
    STATUS_ROI_APPROVED,
    STATUS_ROI_MARKED,
    STATUS_ROI_PROPAGATED,
    STATUS_UNANNOTATED,
)


class StatusAfterRoiAutosaveTests(unittest.TestCase):
    def test_raw_imported_upgrades_to_roi_marked(self) -> None:
        self.assertEqual(
            MainWindow._status_after_roi_autosave(STATUS_RAW_IMPORTED),
            STATUS_ROI_MARKED,
        )

    def test_imported_and_unannotated_upgrade_to_roi_marked(self) -> None:
        self.assertEqual(
            MainWindow._status_after_roi_autosave(STATUS_IMPORTED),
            STATUS_ROI_MARKED,
        )
        self.assertEqual(
            MainWindow._status_after_roi_autosave(STATUS_UNANNOTATED),
            STATUS_ROI_MARKED,
        )

    def test_roi_marked_is_no_op(self) -> None:
        self.assertIsNone(MainWindow._status_after_roi_autosave(STATUS_ROI_MARKED))

    def test_advanced_statuses_are_no_op(self) -> None:
        for status in (
            STATUS_PROCESSED,
            STATUS_MOTION_INDEX_GENERATED,
            STATUS_MOTION_INDEX_FAILED,
        ):
            with self.subTest(status=status):
                self.assertIsNone(MainWindow._status_after_roi_autosave(status))

    def test_propagated_and_approved_are_no_op(self) -> None:
        self.assertIsNone(
            MainWindow._status_after_roi_autosave(STATUS_ROI_PROPAGATED)
        )
        self.assertIsNone(MainWindow._status_after_roi_autosave(STATUS_ROI_APPROVED))

    def test_blank_or_unknown_status_defaults_to_roi_marked(self) -> None:
        self.assertEqual(MainWindow._status_after_roi_autosave(""), STATUS_ROI_MARKED)
        self.assertEqual(
            MainWindow._status_after_roi_autosave("  "),
            STATUS_ROI_MARKED,
        )
        self.assertEqual(
            MainWindow._status_after_roi_autosave("legacy_custom_status"),
            STATUS_ROI_MARKED,
        )


if __name__ == "__main__":
    unittest.main()
