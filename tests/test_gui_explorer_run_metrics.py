"""Tests for Explorer context-menu Run Metrics (Phase 5.7C/5.7G)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, call, patch

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication, QMenu

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

    def test_condition_group_context_menu_excludes_run_metrics(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._project_root = MagicMock()
        window._require_project_root = MagicMock(return_value=window._project_root)
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

        self.assertNotIn("Run Metrics", self._menu_action_labels(captured["menu"]))

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


if __name__ == "__main__":
    unittest.main()
