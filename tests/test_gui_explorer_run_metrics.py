"""Tests for Explorer context-menu Run Metrics (Phase 5.7C)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication, QMenu

from actintrack_app.explorer_sidebar import (
    ITEM_TYPE_CONDITION_GROUP,
    ITEM_TYPE_EMPTY_SAMPLE,
    ITEM_TYPE_SAMPLE,
    is_draggable_sample_meta,
)
from actintrack_app.gui import MainWindow


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
        window._ctx_run_metrics_for_sample = MagicMock()
        window._ctx_replace_sample_data = MagicMock()
        window._ctx_rename_batch = MagicMock()
        window._ctx_delete_batch = MagicMock()
        window._add_explorer_refresh_action = MagicMock()

        item = MagicMock()
        window.tree_samples = MagicMock()
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


if __name__ == "__main__":
    unittest.main()
