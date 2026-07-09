"""Tests for Explorer context-menu Run Metrics (Phase 5.7C/5.7G/5.7I)."""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QApplication, QMenu, QTreeWidget, QTreeWidgetItem

from actintrack_app.explorer_sidebar import (
    ITEM_TYPE_CONDITION_GROUP,
    ITEM_TYPE_EMPTY_SAMPLE,
    ITEM_TYPE_SAMPLE,
    is_draggable_sample_meta,
)
from actintrack_app.gui import (
    MainWindow,
    format_missing_roi_menu_note_for_samples,
    format_missing_roi_tooltip_for_samples,
)


class ExplorerRunMetricsTargetTests(unittest.TestCase):
    def test_sample_row_is_run_metrics_target(self) -> None:
        meta = {
            "item_type": ITEM_TYPE_SAMPLE,
            "sample_id": "sid-42",
            "group": "cg_a",
            "batch_name": "clip.mp4",
        }
        self.assertTrue(is_draggable_sample_meta(meta))

    def test_condition_group_is_not_run_metrics_target(self) -> None:
        meta = {
            "item_type": ITEM_TYPE_CONDITION_GROUP,
            "condition_group_id": "cg_a",
        }
        self.assertFalse(is_draggable_sample_meta(meta))

    def test_empty_sample_placeholder_is_not_run_metrics_target(self) -> None:
        meta = {
            "item_type": ITEM_TYPE_EMPTY_SAMPLE,
            "group": "cg_a",
            "batch_name": "Batch 1",
        }
        self.assertFalse(is_draggable_sample_meta(meta))


class RunMetricsForSampleIdTests(unittest.TestCase):
    def test_run_metrics_for_sample_id_does_not_change_current_sample(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window._metrics_inflight = set()
        window._sample_has_valid_data_and_roi = MagicMock(return_value=True)
        window._compute_metrics_for_sample = MagicMock(return_value="analyzed")
        window._status = MagicMock()
        window._update_metric_freshness_label = MagicMock()

        result = MainWindow.run_metrics_for_sample_id(window, "S2")

        self.assertEqual(result, "analyzed")
        self.assertEqual(window._current_sample_id, "S1")
        window._compute_metrics_for_sample.assert_called_once_with("S2")

    def test_run_metrics_for_sample_id_blocked_without_saved_roi(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window._metrics_inflight = set()
        window._metric_compute_queue = []
        window._sample_has_valid_data_and_roi = MagicMock(return_value=False)
        window._compute_metrics_for_sample = MagicMock()
        window._status = MagicMock()
        window._update_metric_freshness_label = MagicMock()

        with patch("actintrack_app.gui.gui_dialogs.warning") as warning:
            result = MainWindow.run_metrics_for_sample_id(
                window,
                "S2",
                show_dialog_on_block=True,
            )

        self.assertEqual(result, "unavailable")
        window._compute_metrics_for_sample.assert_not_called()
        window._status.assert_called_once()
        warning.assert_called_once()

    def test_run_metrics_now_delegates_to_sample_id_helper(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window.run_metrics_for_sample_id = MagicMock(return_value="analyzed")

        MainWindow.run_metrics_now_for_current_sample(window)

        window.run_metrics_for_sample_id.assert_called_once_with(
            "S1",
            show_dialog_on_block=False,
        )


class ExplorerContextMenuRunMetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _menu_action_labels(self, menu: QMenu) -> list[str]:
        return [action.text() for action in menu.actions() if not action.isSeparator()]

    def test_sample_context_menu_includes_run_metrics(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._project_root = MagicMock()
        window._require_project_root = MagicMock(return_value=window._project_root)
        window._ensure_filter_group_valid = MagicMock(return_value="cg_a")
        window._sample_has_valid_data_and_roi = MagicMock(return_value=True)
        window.selected_sample_ids_in_single_condition_group = MagicMock(
            return_value=["sid-42"]
        )
        window._ctx_run_metrics_for_sample = MagicMock()
        window._ctx_replace_sample_data = MagicMock()
        window._ctx_rename_batch = MagicMock()
        window._ctx_delete_batch = MagicMock()
        window._add_explorer_refresh_action = MagicMock()

        item = MagicMock()
        window.tree_samples = MagicMock()
        window.tree_samples.selectedItems.return_value = [item]
        window.tree_samples.itemAt.return_value = item
        window.tree_samples.viewport.return_value.mapToGlobal.return_value = QPoint(
            0, 0
        )
        window._tree_item_meta = MagicMock(
            return_value={
                "item_type": ITEM_TYPE_SAMPLE,
                "sample_id": "sid-42",
                "group": "cg_a",
                "batch_name": "clip.mp4",
            }
        )

        captured: dict[str, QMenu] = {}

        def make_menu(*_args, **_kwargs) -> QMenu:
            menu = QMenu()
            captured["menu"] = menu
            return menu

        with patch("actintrack_app.gui.QMenu", side_effect=make_menu):
            with patch.object(QMenu, "exec"):
                window._on_explorer_context_menu(QPoint(0, 0))

        menu = captured["menu"]
        self.assertIn("Run Metrics", self._menu_action_labels(menu))
        run_action = next(
            action for action in menu.actions() if action.text() == "Run Metrics"
        )
        self.assertTrue(run_action.isEnabled())

    def test_empty_condition_group_context_menu_excludes_run_metrics(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._project_root = MagicMock()
        window._require_project_root = MagicMock(return_value=window._project_root)
        window.sample_ids_for_condition_group = MagicMock(return_value=[])
        window._on_add_sample = MagicMock()
        window._ctx_rename_condition_group = MagicMock()
        window._ctx_delete_condition_group = MagicMock()
        window._add_explorer_refresh_action = MagicMock()

        item = MagicMock()
        window.tree_samples = MagicMock()
        window.tree_samples.itemAt.return_value = item
        window.tree_samples.viewport.return_value.mapToGlobal.return_value = QPoint(
            0, 0
        )
        window._tree_item_meta = MagicMock(
            return_value={
                "item_type": ITEM_TYPE_CONDITION_GROUP,
                "condition_group_id": "cg_a",
            }
        )

        captured: dict[str, QMenu] = {}

        def make_menu(*_args, **_kwargs) -> QMenu:
            menu = QMenu()
            captured["menu"] = menu
            return menu

        with patch("actintrack_app.gui.QMenu", side_effect=make_menu):
            with patch.object(QMenu, "exec"):
                window._on_explorer_context_menu(QPoint(0, 0))

        labels = self._menu_action_labels(captured["menu"])
        self.assertNotIn("Run Metrics", labels)
        self.assertNotIn("Run Metrics for Condition Group", labels)

    def test_ctx_run_metrics_does_not_load_sample(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window._load_sample_from_tree_item = MagicMock()
        window.run_metrics_for_sample_id = MagicMock(return_value="analyzed")

        MainWindow._ctx_run_metrics_for_sample(window, "S2")

        window.run_metrics_for_sample_id.assert_called_once_with(
            "S2",
            show_dialog_on_block=True,
        )
        window._load_sample_from_tree_item.assert_not_called()
        self.assertEqual(window._current_sample_id, "S1")


class MissingRoiTooltipTests(unittest.TestCase):
    def test_single_invalid_sample(self) -> None:
        self.assertEqual(
            format_missing_roi_tooltip_for_samples(["Sample A"]),
            "Sample A is missing an ROI.",
        )

    def test_multiple_invalid_samples(self) -> None:
        self.assertEqual(
            format_missing_roi_tooltip_for_samples(["A", "B", "C"]),
            "A, B, C are missing ROIs.",
        )

    def test_capped_invalid_sample_list(self) -> None:
        self.assertEqual(
            format_missing_roi_tooltip_for_samples(
                ["A", "B", "C", "D", "E", "F", "G"]
            ),
            "A, B, C, and 4 more samples are missing ROIs.",
        )


class MissingRoiMenuNoteTests(unittest.TestCase):
    def test_single_invalid_sample(self) -> None:
        self.assertEqual(
            format_missing_roi_menu_note_for_samples(["Sample A"]),
            "    Missing ROI: Sample A",
        )

    def test_multiple_invalid_samples(self) -> None:
        self.assertEqual(
            format_missing_roi_menu_note_for_samples(["A", "B", "C"]),
            "    Missing ROIs: A, B, C",
        )

    def test_two_invalid_samples_uses_plural_label(self) -> None:
        self.assertEqual(
            format_missing_roi_menu_note_for_samples(["A", "B"]),
            "    Missing ROIs: A, B",
        )

    def test_capped_invalid_sample_list(self) -> None:
        self.assertEqual(
            format_missing_roi_menu_note_for_samples(
                ["A", "B", "C", "D", "E", "F", "G"]
            ),
            "    Missing ROIs: A, B, C, and 4 more",
        )


class RunMetricsForSelectedSamplesTests(unittest.TestCase):
    def test_run_metrics_for_sample_ids_runs_sequentially_without_loading(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window._sample_has_valid_data_and_roi = MagicMock(return_value=True)
        window._sample_display_label_for_id = MagicMock(
            side_effect=lambda sid: f"Label-{sid}"
        )
        window._status = MagicMock()
        window._update_metric_freshness_label = MagicMock()
        window._refresh_analysis_if_visible = MagicMock()
        window.run_metrics_for_sample_id = MagicMock(return_value="analyzed")

        with patch("actintrack_app.gui.QApplication.processEvents"):
            MainWindow.run_metrics_for_sample_ids(window, ["S2", "S3", "S4"])

        window.run_metrics_for_sample_id.assert_has_calls(
            [
                call("S2", show_dialog_on_block=False),
                call("S3", show_dialog_on_block=False),
                call("S4", show_dialog_on_block=False),
            ]
        )
        self.assertEqual(window._current_sample_id, "S1")
        window._status.assert_any_call("Running metrics 1 of 3: Label-S2")
        window._status.assert_any_call("Metrics complete for 3 samples.")

    def test_run_metrics_for_sample_ids_blocks_when_any_missing_roi(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._missing_roi_display_names_for_samples = MagicMock(
            return_value=["Sample B"]
        )
        window._status = MagicMock()
        window.run_metrics_for_sample_id = MagicMock()

        with patch("actintrack_app.gui.gui_dialogs.warning") as warning:
            MainWindow.run_metrics_for_sample_ids(
                window,
                ["S1", "S2"],
                show_dialog_on_block=True,
            )

        window.run_metrics_for_sample_id.assert_not_called()
        window._status.assert_called_once()
        warning.assert_called_once()

    def test_ctx_run_metrics_for_selected_samples_delegates(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window.run_metrics_for_sample_ids = MagicMock()

        MainWindow._ctx_run_metrics_for_selected_samples(window, ["S1", "S2"])

        window.run_metrics_for_sample_ids.assert_called_once_with(
            ["S1", "S2"],
            show_dialog_on_block=True,
        )


class ExplorerMultiSelectRunMetricsMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _menu_action_labels(self, menu: QMenu) -> list[str]:
        return [action.text() for action in menu.actions() if not action.isSeparator()]

    def _run_context_menu(self, window: MainWindow, item: MagicMock) -> QMenu:
        window.tree_samples.itemAt.return_value = item
        captured: dict[str, QMenu] = {}

        def make_menu(*_args, **_kwargs) -> QMenu:
            menu = QMenu()
            captured["menu"] = menu
            return menu

        with patch("actintrack_app.gui.QMenu", side_effect=make_menu):
            with patch.object(QMenu, "exec"):
                window._on_explorer_context_menu(QPoint(0, 0))
        return captured["menu"]

    def test_multi_selected_sample_shows_selected_samples_action(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._project_root = MagicMock()
        window._require_project_root = MagicMock(return_value=window._project_root)
        window._ensure_filter_group_valid = MagicMock(return_value="cg_a")
        window._sample_has_valid_data_and_roi = MagicMock(return_value=True)
        window._missing_roi_display_names_for_samples = MagicMock(return_value=[])
        window.selected_sample_ids_in_single_condition_group = MagicMock(
            return_value=["S1", "S2", "S3"]
        )
        window._ctx_run_metrics_for_selected_samples = MagicMock()
        window._ctx_replace_sample_data = MagicMock()
        window._ctx_rename_batch = MagicMock()
        window._ctx_delete_batch = MagicMock()
        window._add_explorer_refresh_action = MagicMock()

        item = MagicMock()
        window.tree_samples = MagicMock()
        window.tree_samples.selectedItems.return_value = [item, MagicMock()]
        window.tree_samples.viewport.return_value.mapToGlobal.return_value = QPoint(
            0, 0
        )
        window._tree_item_meta = MagicMock(
            return_value={
                "item_type": ITEM_TYPE_SAMPLE,
                "sample_id": "S1",
                "group": "cg_a",
                "batch_name": "clip1.mp4",
            }
        )

        menu = self._run_context_menu(window, item)
        labels = self._menu_action_labels(menu)
        self.assertIn("Run Metrics for Selected Samples", labels)
        self.assertNotIn("Run Metrics", labels)

    def test_unselected_sample_shows_single_run_metrics_action(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._project_root = MagicMock()
        window._require_project_root = MagicMock(return_value=window._project_root)
        window._ensure_filter_group_valid = MagicMock(return_value="cg_a")
        window._sample_has_valid_data_and_roi = MagicMock(return_value=True)
        window.selected_sample_ids_in_single_condition_group = MagicMock(
            return_value=["S1", "S2"]
        )
        window._ctx_run_metrics_for_sample = MagicMock()
        window._ctx_replace_sample_data = MagicMock()
        window._ctx_rename_batch = MagicMock()
        window._ctx_delete_batch = MagicMock()
        window._add_explorer_refresh_action = MagicMock()

        item = MagicMock()
        other = MagicMock()
        window.tree_samples = MagicMock()
        window.tree_samples.selectedItems.return_value = [other]
        window.tree_samples.viewport.return_value.mapToGlobal.return_value = QPoint(
            0, 0
        )
        window._tree_item_meta = MagicMock(
            return_value={
                "item_type": ITEM_TYPE_SAMPLE,
                "sample_id": "S9",
                "group": "cg_a",
                "batch_name": "clip9.mp4",
            }
        )

        menu = self._run_context_menu(window, item)
        labels = self._menu_action_labels(menu)
        self.assertIn("Run Metrics", labels)
        self.assertNotIn("Run Metrics for Selected Samples", labels)

    def test_selected_samples_action_disabled_with_menu_note_when_roi_missing(
        self,
    ) -> None:
        window = MainWindow.__new__(MainWindow)
        window._project_root = MagicMock()
        window._require_project_root = MagicMock(return_value=window._project_root)
        window._ensure_filter_group_valid = MagicMock(return_value="cg_a")
        window.selected_sample_ids_in_single_condition_group = MagicMock(
            return_value=["S1", "S2"]
        )
        window._missing_roi_display_names_for_samples = MagicMock(
            return_value=["Sample B"]
        )
        window._ctx_replace_sample_data = MagicMock()
        window._ctx_rename_batch = MagicMock()
        window._ctx_delete_batch = MagicMock()
        window._add_explorer_refresh_action = MagicMock()

        item = MagicMock()
        window.tree_samples = MagicMock()
        window.tree_samples.selectedItems.return_value = [item, MagicMock()]
        window.tree_samples.viewport.return_value.mapToGlobal.return_value = QPoint(
            0, 0
        )
        window._tree_item_meta = MagicMock(
            return_value={
                "item_type": ITEM_TYPE_SAMPLE,
                "sample_id": "S1",
                "group": "cg_a",
                "batch_name": "clip1.mp4",
            }
        )

        menu = self._run_context_menu(window, item)
        action = next(
            a
            for a in menu.actions()
            if a.text() == "Run Metrics for Selected Samples"
        )
        note = next(
            a
            for a in menu.actions()
            if a.text() == "    Missing ROI: Sample B"
        )
        self.assertFalse(action.isEnabled())
        self.assertEqual(action.toolTip(), "Sample B is missing an ROI.")
        self.assertFalse(note.isEnabled())


class ConditionGroupSampleIdCollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _make_group_with_samples(self) -> tuple[QTreeWidget, QTreeWidgetItem]:
        tree = QTreeWidget()
        group = QTreeWidgetItem(["Group A"])
        group.setData(
            0,
            Qt.ItemDataRole.UserRole,
            {
                "item_type": ITEM_TYPE_CONDITION_GROUP,
                "condition_group_id": "cg_a",
            },
        )
        for sid, label in (("S1", "clip1.mp4"), ("S2", "clip2.mp4")):
            child = QTreeWidgetItem([label])
            child.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {
                    "item_type": ITEM_TYPE_SAMPLE,
                    "sample_id": sid,
                    "group": "cg_a",
                    "batch_name": label,
                },
            )
            group.addChild(child)
        empty = QTreeWidgetItem(["Batch 3"])
        empty.setData(
            0,
            Qt.ItemDataRole.UserRole,
            {
                "item_type": ITEM_TYPE_EMPTY_SAMPLE,
                "group": "cg_a",
                "batch_name": "Batch 3",
            },
        )
        group.addChild(empty)
        tree.addTopLevelItem(group)
        return tree, group

    def test_sample_ids_for_explorer_group_item_skips_placeholders(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._tree_item_meta = MainWindow._tree_item_meta.__get__(
            window, MainWindow
        )
        _, group = self._make_group_with_samples()

        ids = MainWindow._sample_ids_for_explorer_group_item(window, group)

        self.assertEqual(ids, ["S1", "S2"])

    def test_sample_ids_for_condition_group_uses_group_item(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._tree_item_meta = MainWindow._tree_item_meta.__get__(
            window, MainWindow
        )
        _, group = self._make_group_with_samples()

        ids = MainWindow.sample_ids_for_condition_group(
            window,
            "cg_a",
            group_item=group,
        )

        self.assertEqual(ids, ["S1", "S2"])


class ConditionGroupRunMetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _menu_action_labels(self, menu: QMenu) -> list[str]:
        return [action.text() for action in menu.actions() if not action.isSeparator()]

    def _run_context_menu(self, window: MainWindow, item: MagicMock) -> QMenu:
        window.tree_samples.itemAt.return_value = item
        captured: dict[str, QMenu] = {}

        def make_menu(*_args, **_kwargs) -> QMenu:
            menu = QMenu()
            captured["menu"] = menu
            return menu

        with patch("actintrack_app.gui.QMenu", side_effect=make_menu):
            with patch.object(QMenu, "exec"):
                window._on_explorer_context_menu(QPoint(0, 0))
        return captured["menu"]

    def test_condition_group_context_menu_includes_run_metrics(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._project_root = MagicMock()
        window._require_project_root = MagicMock(return_value=window._project_root)
        window.sample_ids_for_condition_group = MagicMock(
            return_value=["S1", "S2", "S3"]
        )
        window._missing_roi_display_names_for_samples = MagicMock(return_value=[])
        window._ctx_run_metrics_for_condition_group = MagicMock()
        window._on_add_sample = MagicMock()
        window._ctx_rename_condition_group = MagicMock()
        window._ctx_delete_condition_group = MagicMock()
        window._add_explorer_refresh_action = MagicMock()

        item = MagicMock()
        window.tree_samples = MagicMock()
        window.tree_samples.viewport.return_value.mapToGlobal.return_value = QPoint(
            0, 0
        )
        window._tree_item_meta = MagicMock(
            return_value={
                "item_type": ITEM_TYPE_CONDITION_GROUP,
                "condition_group_id": "cg_a",
            }
        )

        menu = self._run_context_menu(window, item)
        labels = self._menu_action_labels(menu)
        self.assertIn("Run Metrics for Condition Group", labels)
        window.sample_ids_for_condition_group.assert_called_once_with(
            "cg_a",
            group_item=item,
        )

    def test_condition_group_action_disabled_with_menu_note_when_roi_missing(
        self,
    ) -> None:
        window = MainWindow.__new__(MainWindow)
        window._project_root = MagicMock()
        window._require_project_root = MagicMock(return_value=window._project_root)
        window.sample_ids_for_condition_group = MagicMock(return_value=["S1", "S2"])
        window._missing_roi_display_names_for_samples = MagicMock(
            return_value=["Sample B"]
        )
        window._on_add_sample = MagicMock()
        window._ctx_rename_condition_group = MagicMock()
        window._ctx_delete_condition_group = MagicMock()
        window._add_explorer_refresh_action = MagicMock()

        item = MagicMock()
        window.tree_samples = MagicMock()
        window.tree_samples.viewport.return_value.mapToGlobal.return_value = QPoint(
            0, 0
        )
        window._tree_item_meta = MagicMock(
            return_value={
                "item_type": ITEM_TYPE_CONDITION_GROUP,
                "condition_group_id": "cg_a",
            }
        )

        menu = self._run_context_menu(window, item)
        action = next(
            a
            for a in menu.actions()
            if a.text() == "Run Metrics for Condition Group"
        )
        note = next(
            a
            for a in menu.actions()
            if a.text() == "    Missing ROI: Sample B"
        )
        self.assertFalse(action.isEnabled())
        self.assertEqual(action.toolTip(), "Sample B is missing an ROI.")
        self.assertFalse(note.isEnabled())

    def test_run_metrics_for_condition_group_delegates_to_sample_ids_helper(
        self,
    ) -> None:
        window = MainWindow.__new__(MainWindow)
        window.run_metrics_for_sample_ids = MagicMock()

        MainWindow._ctx_run_metrics_for_condition_group(window, ["S1", "S2"])

        window.run_metrics_for_sample_ids.assert_called_once_with(
            ["S1", "S2"],
            show_dialog_on_block=True,
        )

    def test_condition_group_run_does_not_change_current_sample(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S0"
        window._sample_has_valid_data_and_roi = MagicMock(return_value=True)
        window._sample_display_label_for_id = MagicMock(
            side_effect=lambda sid: f"Label-{sid}"
        )
        window._status = MagicMock()
        window._update_metric_freshness_label = MagicMock()
        window._refresh_analysis_if_visible = MagicMock()
        window.run_metrics_for_sample_id = MagicMock(return_value="analyzed")
        window._load_sample_from_tree_item = MagicMock()

        with patch("actintrack_app.gui.QApplication.processEvents"):
            MainWindow.run_metrics_for_sample_ids(window, ["S1", "S2"])

        self.assertEqual(window._current_sample_id, "S0")
        window._load_sample_from_tree_item.assert_not_called()


class ConditionGroupMissingRoiTargetingTests(unittest.TestCase):
    """Integration tests for Condition Group missing-ROI targeting (Phase 5.8D)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        import tempfile

        import cv2
        import numpy as np

        from actintrack_app.batch_manager import rename_batch
        from actintrack_app.condition_group_manager import create_condition_group
        from actintrack_app.metadata import save_sample_crop_annotation
        from actintrack_app.project_manager import create_project_structure
        from actintrack_app.sample_service import create_sample_from_data
        from actintrack_app.sample_transfer import move_sample_to_condition_group
        from actintrack_app.utils import CROP_METADATA_JSON, METADATA_DIR

        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        create_project_structure(self.root)
        self.group_a = create_condition_group(self.root, "Group A")
        self.group_b = create_condition_group(self.root, "Group B")

        def write_video(path: Path) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            writer = cv2.VideoWriter(
                str(path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                10.0,
                (32, 32),
            )
            for i in range(3):
                frame = np.zeros((32, 32, 3), dtype=np.uint8)
                frame[:, :] = (i * 40, 0, 0)
                writer.write(frame)
            writer.release()

        def import_sample(group_id: str, filename: str) -> dict:
            video = self.root / filename
            write_video(video)
            _batch, row = create_sample_from_data(self.root, group_id, video)
            return dict(row)

        def save_roi(sample_id: str, group_id: str) -> None:
            crop_path = self.root / METADATA_DIR / CROP_METADATA_JSON
            save_sample_crop_annotation(
                crop_path,
                sample_id,
                {
                    "sample_id": sample_id,
                    "group": group_id,
                    "condition_group_id": group_id,
                    "rectangle_roi": {"x": 1, "y": 2, "width": 10, "height": 12},
                    "status": "roi_marked",
                },
            )

        self._import_sample = import_sample
        self._save_roi = save_roi
        self._rename_batch = rename_batch
        self._move_sample = move_sample_to_condition_group

        self.row_a1 = import_sample(self.group_a.id, "a1.mp4")
        self.row_a2 = import_sample(self.group_a.id, "a2.mp4")
        self.row_b1 = import_sample(self.group_b.id, "b1.mp4")
        self.row_b2 = import_sample(self.group_b.id, "b2.mp4")
        save_roi(str(self.row_a2["sample_id"]), self.group_a.id)
        save_roi(str(self.row_b2["sample_id"]), self.group_b.id)

        self.window = MainWindow.__new__(MainWindow)
        self.window._project_root = self.root
        self.window._current_sample_id = str(self.row_b2["sample_id"])
        self.window._current_sample = dict(self.row_b2)
        self.window._tree_item_meta = MainWindow._tree_item_meta.__get__(
            self.window, MainWindow
        )
        self.window.tree_samples = MagicMock()
        self.window.tree_samples.topLevelItemCount.return_value = 0

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _make_group_tree_item(
        self,
        group_id: str,
        *,
        children: list[dict[str, Any]] | None = None,
    ) -> QTreeWidgetItem:
        group = QTreeWidgetItem(["Group"])
        group.setData(
            0,
            Qt.ItemDataRole.UserRole,
            {
                "item_type": ITEM_TYPE_CONDITION_GROUP,
                "condition_group_id": group_id,
            },
        )
        for child_meta in children or []:
            child = QTreeWidgetItem([child_meta.get("label", "sample")])
            child.setData(0, Qt.ItemDataRole.UserRole, child_meta)
            group.addChild(child)
        return group

    def test_missing_roi_names_target_sample_in_each_group(self) -> None:
        ids_a = MainWindow.sample_ids_for_condition_group(
            self.window, self.group_a.id
        )
        ids_b = MainWindow.sample_ids_for_condition_group(
            self.window, self.group_b.id
        )
        missing_a = MainWindow._missing_roi_display_names_for_samples(
            self.window, ids_a
        )
        missing_b = MainWindow._missing_roi_display_names_for_samples(
            self.window, ids_b
        )
        self.assertEqual(missing_a, ["a1.mp4"])
        self.assertEqual(missing_b, ["b1.mp4"])

    def test_stale_tree_child_from_other_group_is_ignored(self) -> None:
        stale_group = self._make_group_tree_item(
            self.group_a.id,
            children=[
                {
                    "item_type": ITEM_TYPE_SAMPLE,
                    "sample_id": str(self.row_a1["sample_id"]),
                    "group": self.group_a.id,
                    "batch_name": "a1.mp4",
                    "label": "a1.mp4",
                },
                {
                    "item_type": ITEM_TYPE_SAMPLE,
                    "sample_id": str(self.row_b1["sample_id"]),
                    "group": self.group_b.id,
                    "batch_name": "b1.mp4",
                    "label": "b1.mp4",
                },
            ],
        )
        ids = MainWindow.sample_ids_for_condition_group(
            self.window,
            self.group_a.id,
            group_item=stale_group,
        )
        missing = MainWindow._missing_roi_display_names_for_samples(
            self.window, ids
        )
        self.assertEqual(ids, [str(self.row_a1["sample_id"]), str(self.row_a2["sample_id"])])
        self.assertEqual(missing, ["a1.mp4"])

    def test_renamed_missing_sample_uses_persisted_display_name(self) -> None:
        self._rename_batch(
            self.root,
            self.group_a.id,
            str(self.row_a1["batch_name"]),
            "RenamedA1",
        )
        self.window._current_sample = {
            **self.row_a1,
            "batch_name": str(self.row_a1["batch_name"]),
        }
        ids = MainWindow.sample_ids_for_condition_group(
            self.window, self.group_a.id
        )
        missing = MainWindow._missing_roi_display_names_for_samples(
            self.window, ids
        )
        self.assertEqual(missing, ["RenamedA1"])

    def test_moved_missing_sample_updates_group_targeting(self) -> None:
        sample_id = str(self.row_a1["sample_id"])
        self._move_sample(self.root, sample_id, self.group_b.id)
        missing_a = MainWindow._missing_roi_display_names_for_samples(
            self.window,
            MainWindow.sample_ids_for_condition_group(self.window, self.group_a.id),
        )
        missing_b = MainWindow._missing_roi_display_names_for_samples(
            self.window,
            MainWindow.sample_ids_for_condition_group(self.window, self.group_b.id),
        )
        self.assertEqual(missing_a, [])
        self.assertEqual(sorted(missing_b), sorted(["a1.mp4", "b1.mp4"]))

    def test_different_current_selection_does_not_change_group_validation(self) -> None:
        self.window._current_sample_id = str(self.row_b2["sample_id"])
        self.window._current_sample = dict(self.row_b2)
        missing_a = MainWindow._missing_roi_display_names_for_samples(
            self.window,
            MainWindow.sample_ids_for_condition_group(self.window, self.group_a.id),
        )
        self.assertEqual(missing_a, ["a1.mp4"])

    def test_condition_group_context_menu_uses_project_backed_missing_names(
        self,
    ) -> None:
        group_item = self._make_group_tree_item(self.group_a.id)
        self.window._require_project_root = MagicMock(return_value=self.root)
        self.window._ctx_run_metrics_for_condition_group = MagicMock()
        self.window._on_add_sample = MagicMock()
        self.window._ctx_rename_condition_group = MagicMock()
        self.window._ctx_delete_condition_group = MagicMock()
        self.window._add_explorer_refresh_action = MagicMock()
        self.window.tree_samples = MagicMock()
        self.window.tree_samples.viewport.return_value.mapToGlobal.return_value = (
            QPoint(0, 0)
        )
        self.window._tree_item_meta = MagicMock(
            return_value={
                "item_type": ITEM_TYPE_CONDITION_GROUP,
                "condition_group_id": self.group_a.id,
            }
        )

        captured: dict[str, QMenu] = {}

        def make_menu(*_args, **_kwargs) -> QMenu:
            menu = QMenu()
            captured["menu"] = menu
            return menu

        with patch("actintrack_app.gui.QMenu", side_effect=make_menu):
            with patch.object(QMenu, "exec"):
                self.window.tree_samples.itemAt.return_value = group_item
                self.window._on_explorer_context_menu(QPoint(0, 0))

        menu = captured["menu"]
        labels = [action.text() for action in menu.actions() if not action.isSeparator()]
        self.assertIn("Run Metrics for Condition Group", labels)
        self.assertIn("    Missing ROI: a1.mp4", labels)


if __name__ == "__main__":
    unittest.main()
