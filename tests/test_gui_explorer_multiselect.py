"""Tests for constrained Explorer multi-selection (Phase 5.7F)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt, QItemSelectionModel
from PyQt6.QtWidgets import QApplication, QAbstractItemView, QTreeWidgetItem

from actintrack_app.explorer_sidebar import (
    ITEM_TYPE_CONDITION_GROUP,
    ITEM_TYPE_EMPTY_SAMPLE,
    ITEM_TYPE_SAMPLE,
    condition_group_tree_meta,
    empty_sample_tree_meta,
    sample_tree_meta,
    tree_item_condition_group_id,
    tree_item_sample_id,
)
from actintrack_app.explorer_tree import (
    ExplorerTreeWidget,
    normalize_explorer_tree_selection,
)
from actintrack_app.gui import MainWindow
from actintrack_app.orientation import RectROI


def _sample_item(
    *,
    sample_id: str,
    group_id: str,
    label: str,
) -> QTreeWidgetItem:
    item = QTreeWidgetItem([label])
    item.setData(
        0,
        Qt.ItemDataRole.UserRole,
        sample_tree_meta(
            {
                "sample_id": sample_id,
                "group": group_id,
                "batch_name": label,
                "original_filename": label,
            }
        ),
    )
    return item


def _group_item(group_id: str, label: str) -> QTreeWidgetItem:
    item = QTreeWidgetItem([label])
    item.setData(
        0,
        Qt.ItemDataRole.UserRole,
        condition_group_tree_meta(group_id),
    )
    return item


class NormalizeExplorerSelectionTests(unittest.TestCase):
    def test_same_group_samples_remain_selected(self) -> None:
        s1 = _sample_item(sample_id="S1", group_id="cg_a", label="a1.mp4")
        s2 = _sample_item(sample_id="S2", group_id="cg_a", label="a2.mp4")
        keep, normalized = normalize_explorer_tree_selection(
            [s1, s2],
            current_item=s2,
        )
        self.assertFalse(normalized)
        self.assertEqual(keep, [s1, s2])

    def test_cross_group_samples_normalize_to_anchor_group(self) -> None:
        s1 = _sample_item(sample_id="S1", group_id="cg_a", label="a1.mp4")
        s2 = _sample_item(sample_id="S2", group_id="cg_b", label="b1.mp4")
        keep, normalized = normalize_explorer_tree_selection(
            [s1, s2],
            current_item=s2,
        )
        self.assertTrue(normalized)
        self.assertEqual(keep, [s2])

    def test_mixed_condition_group_and_sample_keeps_samples_only(self) -> None:
        group = _group_item("cg_a", "Group A")
        sample = _sample_item(sample_id="S1", group_id="cg_a", label="a1.mp4")
        keep, normalized = normalize_explorer_tree_selection(
            [group, sample],
            current_item=sample,
        )
        self.assertTrue(normalized)
        self.assertEqual(keep, [sample])

    def test_multiple_condition_groups_keep_current_only(self) -> None:
        g1 = _group_item("cg_a", "Group A")
        g2 = _group_item("cg_b", "Group B")
        keep, normalized = normalize_explorer_tree_selection(
            [g1, g2],
            current_item=g2,
        )
        self.assertTrue(normalized)
        self.assertEqual(keep, [g2])

    def test_placeholder_rows_are_dropped_when_samples_selected(self) -> None:
        sample = _sample_item(sample_id="S1", group_id="cg_a", label="a1.mp4")
        placeholder = QTreeWidgetItem(["(no data)"])
        placeholder.setData(
            0,
            Qt.ItemDataRole.UserRole,
            empty_sample_tree_meta("cg_a", "Batch 1"),
        )
        keep, normalized = normalize_explorer_tree_selection(
            [sample, placeholder],
            current_item=sample,
        )
        self.assertTrue(normalized)
        self.assertEqual(keep, [sample])

    def test_normalization_uses_condition_group_id_not_display_name(self) -> None:
        s1 = _sample_item(sample_id="S1", group_id="cg_alpha", label="Alpha clip")
        s2 = _sample_item(sample_id="S2", group_id="cg_alpha", label="Also Alpha")
        meta = s1.data(0, Qt.ItemDataRole.UserRole)
        self.assertEqual(tree_item_condition_group_id(meta), "cg_alpha")
        keep, normalized = normalize_explorer_tree_selection(
            [s1, s2],
            current_item=s1,
        )
        self.assertFalse(normalized)
        self.assertEqual(len(keep), 2)
        self.assertIn(s1, keep)
        self.assertIn(s2, keep)


class ExplorerTreeWidgetMultiSelectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_extended_selection_mode_enabled(self) -> None:
        tree = ExplorerTreeWidget()
        self.assertEqual(
            tree.selectionMode().name,
            "ExtendedSelection",
        )

    def test_right_click_does_not_change_selection(self) -> None:
        tree = ExplorerTreeWidget()
        g1 = _group_item("cg_a", "Group A")
        s1 = _sample_item(sample_id="S1", group_id="cg_a", label="a1.mp4")
        tree.addTopLevelItem(g1)
        g1.addChild(s1)
        tree.setCurrentItem(s1)
        tree.selectionModel().select(
            tree.indexFromItem(s1),
            QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )

        from PyQt6.QtGui import QContextMenuEvent
        from PyQt6.QtCore import QPointF

        before = list(tree.selectedItems())
        event = QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse,
            tree.viewport().rect().center(),
        )
        tree.contextMenuEvent(event)
        self.assertEqual(tree.selectedItems(), before)


class MainWindowExplorerSelectionApiTests(unittest.TestCase):
    def test_selected_sample_ids_in_single_condition_group(self) -> None:
        window = MainWindow.__new__(MainWindow)
        s1 = _sample_item(sample_id="S1", group_id="cg_a", label="a1.mp4")
        s2 = _sample_item(sample_id="S2", group_id="cg_a", label="a2.mp4")
        window.tree_samples = MagicMock()
        window.tree_samples.selectedItems.return_value = [s1, s2]
        window._tree_item_meta = MainWindow._tree_item_meta.__get__(window, MainWindow)
        window._item_condition_group_id = MainWindow._item_condition_group_id.__get__(
            window, MainWindow
        )
        window._item_sample_id = MainWindow._item_sample_id.__get__(window, MainWindow)

        self.assertEqual(
            MainWindow.selected_sample_ids_in_single_condition_group(window),
            ["S1", "S2"],
        )

    def test_selected_sample_ids_in_single_condition_group_empty_when_mixed(
        self,
    ) -> None:
        window = MainWindow.__new__(MainWindow)
        s1 = _sample_item(sample_id="S1", group_id="cg_a", label="a1.mp4")
        s2 = _sample_item(sample_id="S2", group_id="cg_b", label="b1.mp4")
        window.tree_samples = MagicMock()
        window.tree_samples.selectedItems.return_value = [s1, s2]
        window._tree_item_meta = MainWindow._tree_item_meta.__get__(window, MainWindow)
        window._item_condition_group_id = MainWindow._item_condition_group_id.__get__(
            window, MainWindow
        )
        window._item_sample_id = MainWindow._item_sample_id.__get__(window, MainWindow)

        self.assertEqual(
            MainWindow.selected_sample_ids_in_single_condition_group(window),
            [],
        )


class ExplorerSelectionBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_normalize_explorer_selection_updates_tree_selection(self) -> None:
        window = MainWindow.__new__(MainWindow)
        tree = ExplorerTreeWidget()
        window.tree_samples = tree
        window._normalizing_explorer_selection = False
        window._current_sample_id = "S2"
        window._status = MagicMock()
        window._load_sample_from_tree_item = MagicMock()

        g1 = _group_item("cg_a", "Group A")
        g2 = _group_item("cg_b", "Group B")
        s1 = _sample_item(sample_id="S1", group_id="cg_a", label="a1.mp4")
        s2 = _sample_item(sample_id="S2", group_id="cg_b", label="b1.mp4")
        tree.addTopLevelItem(g1)
        tree.addTopLevelItem(g2)
        g1.addChild(s1)
        g2.addChild(s2)

        tree.setCurrentItem(s2)
        for item in (s1, s2):
            tree.selectionModel().select(
                tree.indexFromItem(item),
                QItemSelectionModel.SelectionFlag.Select,
            )

        MainWindow._normalize_explorer_selection(window)

        self.assertEqual(tree.selectedItems(), [s2])
        window._status.assert_called_once()

    def test_selection_change_does_not_schedule_metrics(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._normalizing_explorer_selection = False
        window._metric_analysis_view_active = False
        window._preview_playing = False
        window._playback_pause = MagicMock()
        window._set_active_sample = MagicMock()
        window._current_condition_group = MagicMock(return_value="cg_a")
        window._refresh_condition_group_combo = MagicMock()
        window._preview_page = MagicMock()
        window.reset_preview_state = MagicMock()
        window.update_tracking_result_panel = MagicMock()
        window._load_full_roi_preview_for_current_sample = MagicMock()
        window._refresh_roi_save_status_from_context = MagicMock()
        window._update_metric_freshness_label = MagicMock()
        window._compute_metrics_for_sample = MagicMock()
        window.run_metrics_for_sample_id = MagicMock()

        item = MagicMock()
        item.data.return_value = {
            "item_type": ITEM_TYPE_SAMPLE,
            "sample_id": "S2",
            "group": "cg_a",
            "processing_status": "roi_marked",
        }
        window._tree_item_meta = MagicMock(return_value=item.data.return_value)
        window._project_root = MagicMock()
        window._is_sample_tree_item = MagicMock(return_value=True)

        with patch(
            "actintrack_app.gui.condition_group_exists",
            return_value=True,
        ):
            MainWindow._load_sample_from_tree_item(window, item)

        window.run_metrics_for_sample_id.assert_not_called()
        window._compute_metrics_for_sample.assert_not_called()

    def test_ctx_run_metrics_still_targets_without_loading_sample(self) -> None:
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

    def test_on_roi_changed_still_does_not_schedule_metrics(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window._tracking_result_stale_by_sample = {}
        window._optical_flow_stale_by_sample = {}
        window._roi_user_adjusted = False
        window._roi_autosave_pending = False
        window._loaded_annotation_source = ""
        window._set_roi_save_status = MagicMock()
        window._refresh_roi_preview_panel = MagicMock()
        window._update_metric_freshness_label = MagicMock()

        MainWindow.on_roi_changed(window, RectROI(1, 2, 10, 12))

        window._update_metric_freshness_label.assert_not_called()


    def test_selection_changed_skipped_during_normalization(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._normalizing_explorer_selection = True
        window._load_sample_from_tree_item = MagicMock()
        window._sync_combo_from_tree_selection = MagicMock()
        item = _sample_item(sample_id="S1", group_id="cg_a", label="a1.mp4")

        MainWindow._on_explorer_selection_changed(window, item, None)

        window._load_sample_from_tree_item.assert_not_called()
        window._sync_combo_from_tree_selection.assert_not_called()

    def test_single_click_loads_sample_once(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._normalizing_explorer_selection = False
        window._metric_analysis_view_active = False
        window._preview_playing = False
        window._playback_pause = MagicMock()
        window._load_sample_from_tree_item = MagicMock()
        window._sync_combo_from_tree_selection = MagicMock()
        item = _sample_item(sample_id="S2", group_id="cg_a", label="a2.mp4")

        MainWindow._on_explorer_selection_changed(window, item, None)

        window._load_sample_from_tree_item.assert_called_once_with(item)

    def test_normalize_returns_immediately_when_already_normalizing(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._normalizing_explorer_selection = True
        window.tree_samples = MagicMock()
        MainWindow._normalize_explorer_selection(window)
        window.tree_samples.selectedItems.assert_not_called()

    def test_normalization_does_not_reload_current_sample(self) -> None:
        window = MainWindow.__new__(MainWindow)
        tree = ExplorerTreeWidget()
        window.tree_samples = tree
        window._normalizing_explorer_selection = False
        window._current_sample_id = "S2"
        window._status = MagicMock()
        window._load_sample_from_tree_item = MagicMock()
        window._item_sample_id = MainWindow._item_sample_id.__get__(window, MainWindow)
        window._tree_item_meta = MainWindow._tree_item_meta.__get__(window, MainWindow)

        g1 = _group_item("cg_a", "Group A")
        g2 = _group_item("cg_b", "Group B")
        s1 = _sample_item(sample_id="S1", group_id="cg_a", label="a1.mp4")
        s2 = _sample_item(sample_id="S2", group_id="cg_b", label="b1.mp4")
        tree.addTopLevelItem(g1)
        tree.addTopLevelItem(g2)
        g1.addChild(s1)
        g2.addChild(s2)

        tree.setCurrentItem(s2)
        for item in (s1, s2):
            tree.selectionModel().select(
                tree.indexFromItem(item),
                QItemSelectionModel.SelectionFlag.Select,
            )

        MainWindow._normalize_explorer_selection(window)

        self.assertEqual(tree.selectedItems(), [s2])
        window._load_sample_from_tree_item.assert_not_called()

    def test_normalization_loads_once_when_current_sample_changes(self) -> None:
        window = MainWindow.__new__(MainWindow)
        tree = ExplorerTreeWidget()
        window.tree_samples = tree
        window._normalizing_explorer_selection = False
        window._current_sample_id = "S1"
        window._status = MagicMock()
        window._load_sample_from_tree_item = MagicMock()
        window._item_sample_id = MainWindow._item_sample_id.__get__(window, MainWindow)
        window._tree_item_meta = MainWindow._tree_item_meta.__get__(window, MainWindow)

        group = _group_item("cg_a", "Group A")
        s1 = _sample_item(sample_id="S1", group_id="cg_a", label="a1.mp4")
        s2 = _sample_item(sample_id="S2", group_id="cg_a", label="a2.mp4")
        tree.addTopLevelItem(group)
        group.addChild(s1)
        group.addChild(s2)

        tree.setCurrentItem(group)
        tree.selectionModel().select(
            tree.indexFromItem(group),
            QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        tree.selectionModel().select(
            tree.indexFromItem(s2),
            QItemSelectionModel.SelectionFlag.Select,
        )

        MainWindow._normalize_explorer_selection(window)

        window._load_sample_from_tree_item.assert_called_once()
        loaded_item = window._load_sample_from_tree_item.call_args[0][0]
        self.assertEqual(window._item_sample_id(loaded_item), "S2")

    def test_right_click_on_unselected_sample_preserves_selection(self) -> None:
        tree = ExplorerTreeWidget()
        tree.resize(400, 300)
        tree.show()
        QApplication.processEvents()
        group = _group_item("cg_a", "Group A")
        s1 = _sample_item(sample_id="S1", group_id="cg_a", label="a1.mp4")
        s2 = _sample_item(sample_id="S2", group_id="cg_a", label="a2.mp4")
        tree.addTopLevelItem(group)
        group.addChild(s1)
        group.addChild(s2)
        group.setExpanded(True)
        tree.setCurrentItem(s1)
        tree.selectionModel().select(
            tree.indexFromItem(s1),
            QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )

        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QMouseEvent

        s2_index = tree.indexFromItem(s2)
        s2_rect = tree.visualRect(s2_index)
        press_pos = QPointF(s2_rect.center())
        press_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            press_pos,
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )
        tree.mousePressEvent(press_event)

        self.assertEqual(tree.currentItem(), s1)
        self.assertEqual(tree.selectedItems(), [s1])
        tree.hide()


if __name__ == "__main__":
    unittest.main()
