"""Tests for Explorer Condition Group expansion and selection state."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import cv2
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QTreeWidgetItem

from actintrack_app.condition_group_manager import (
    create_condition_group,
    rename_condition_group,
)
from actintrack_app.explorer_sidebar import (
    condition_group_tree_meta,
    sample_tree_meta,
)
from actintrack_app.explorer_tree import (
    ExplorerTreeWidget,
    collect_condition_group_expansion_state,
    configure_condition_group_tree_item,
    default_expanded_state_for_condition_group,
    restore_selected_sample_by_id,
    tree_index_shows_branch_indicator,
)
from actintrack_app.gui import MainWindow
from actintrack_app.project_manager import create_project_structure
from actintrack_app.sample_service import create_sample_from_data
from actintrack_app.sample_transfer import move_sample_to_condition_group


def _write_test_video(path: Path, frames: int = 3) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        10.0,
        (32, 32),
    )
    for i in range(frames):
        frame = np.zeros((32, 32, 3), dtype=np.uint8)
        frame[:, :] = (i * 40, 0, 0)
        writer.write(frame)
    writer.release()


class ExplorerExpansionHelperTests(unittest.TestCase):
    def test_empty_group_defaults_collapsed_without_remembered_state(self) -> None:
        self.assertFalse(
            default_expanded_state_for_condition_group(
                "cg_empty",
                has_children=False,
                remembered={},
            )
        )

    def test_non_empty_group_defaults_expanded_without_remembered_state(self) -> None:
        self.assertTrue(
            default_expanded_state_for_condition_group(
                "cg_full",
                has_children=True,
                remembered={},
            )
        )

    def test_remembered_collapsed_state_overrides_non_empty_default(self) -> None:
        self.assertFalse(
            default_expanded_state_for_condition_group(
                "cg_full",
                has_children=True,
                remembered={"cg_full": False},
            )
        )

    def test_remembered_expanded_state_overrides_empty_default(self) -> None:
        self.assertTrue(
            default_expanded_state_for_condition_group(
                "cg_empty",
                has_children=False,
                remembered={"cg_empty": True},
            )
        )


class ExplorerTreeWidgetStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _add_group(self, tree: ExplorerTreeWidget, group_id: str, name: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([name])
        item.setData(0, Qt.ItemDataRole.UserRole, condition_group_tree_meta(group_id))
        configure_condition_group_tree_item(item)
        tree.addTopLevelItem(item)
        return item

    def test_empty_condition_group_shows_disclosure_indicator(self) -> None:
        tree = ExplorerTreeWidget()
        group = self._add_group(tree, "cg_empty", "Empty Group")
        index = tree.indexFromItem(group)

        self.assertEqual(
            group.childIndicatorPolicy(),
            QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator,
        )
        self.assertTrue(tree_index_shows_branch_indicator(tree, index))

    def test_empty_condition_group_can_expand_without_children(self) -> None:
        tree = ExplorerTreeWidget()
        group = self._add_group(tree, "cg_empty", "Empty Group")
        group.setExpanded(True)
        self.assertTrue(group.isExpanded())
        self.assertEqual(group.childCount(), 0)

    def test_collect_expansion_state_uses_condition_group_id(self) -> None:
        tree = ExplorerTreeWidget()
        group_a = self._add_group(tree, "cg_alpha", "Alpha")
        group_b = self._add_group(tree, "cg_beta", "Beta")
        group_a.setExpanded(True)
        group_b.setExpanded(False)

        remembered = collect_condition_group_expansion_state(tree)
        self.assertEqual(remembered, {"cg_alpha": True, "cg_beta": False})

    def test_restore_selected_sample_by_id_follows_moved_sample(self) -> None:
        tree = ExplorerTreeWidget()
        group = self._add_group(tree, "cg_a", "Group A")
        sample = QTreeWidgetItem(["clip.mp4"])
        sample.setData(
            0,
            Qt.ItemDataRole.UserRole,
            sample_tree_meta({"sample_id": "sid-42", "original_filename": "clip.mp4"}),
        )
        group.addChild(sample)
        group.setExpanded(True)

        restored = restore_selected_sample_by_id(tree, "sid-42")
        self.assertIs(restored, sample)
        self.assertIs(tree.currentItem(), sample)

    def test_display_name_changes_do_not_break_expansion_restoration(self) -> None:
        tree = ExplorerTreeWidget()
        group = self._add_group(tree, "cg_stable", "Old Name")
        group.setExpanded(True)

        remembered = collect_condition_group_expansion_state(tree)
        tree.clear()
        renamed = self._add_group(tree, "cg_stable", "New Name")
        renamed.setExpanded(
            default_expanded_state_for_condition_group(
                "cg_stable",
                has_children=False,
                remembered=remembered,
            )
        )
        self.assertTrue(renamed.isExpanded())


class ExplorerRefreshIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _make_window(self, root: Path) -> MainWindow:
        window = MainWindow.__new__(MainWindow)
        window._explorer_group_expansion_by_id = {}
        window.tree_samples = ExplorerTreeWidget()
        window.lbl_explorer_empty = QLabel()
        window._project_root = root
        window._current_sample = None
        window._set_active_sample = MagicMock()
        window._clear_preview_pane = MagicMock()
        window._sync_combo_from_tree_selection = MagicMock()
        window._load_sample_from_tree_item = MagicMock()
        return window

    def _group_item(self, window: MainWindow, group_id: str) -> QTreeWidgetItem | None:
        for top_idx in range(window.tree_samples.topLevelItemCount()):
            top = window.tree_samples.topLevelItem(top_idx)
            if top is None:
                continue
            meta = top.data(0, Qt.ItemDataRole.UserRole)
            if (
                isinstance(meta, dict)
                and str(meta.get("condition_group_id", "")) == group_id
            ):
                return top
        return None

    def test_initial_refresh_expands_non_empty_and_collapses_empty_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_project_structure(root)
            empty = create_condition_group(root, "Empty Group")
            full = create_condition_group(root, "Full Group")
            video = root / "clip.mp4"
            _write_test_video(video)
            _batch, row = create_sample_from_data(root, full.id, video)

            window = self._make_window(root)
            window._refresh_sample_list()

            empty_item = self._group_item(window, empty.id)
            full_item = self._group_item(window, full.id)
            self.assertIsNotNone(empty_item)
            self.assertIsNotNone(full_item)
            assert empty_item is not None
            assert full_item is not None
            self.assertFalse(empty_item.isExpanded())
            self.assertTrue(full_item.isExpanded())

            restored = restore_selected_sample_by_id(
                window.tree_samples,
                str(row["sample_id"]),
            )
            self.assertIsNotNone(restored)

    def test_user_collapsed_non_empty_group_stays_collapsed_after_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_project_structure(root)
            group = create_condition_group(root, "Control")
            video = root / "clip.mp4"
            _write_test_video(video)
            create_sample_from_data(root, group.id, video)

            window = self._make_window(root)
            window._refresh_sample_list()
            group_item = self._group_item(window, group.id)
            assert group_item is not None
            group_item.setExpanded(False)

            window._refresh_sample_list()
            group_item = self._group_item(window, group.id)
            assert group_item is not None
            self.assertFalse(group_item.isExpanded())

    def test_user_expanded_empty_group_stays_expanded_after_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_project_structure(root)
            group = create_condition_group(root, "Empty Group")

            window = self._make_window(root)
            window._refresh_sample_list()
            group_item = self._group_item(window, group.id)
            assert group_item is not None
            group_item.setExpanded(True)

            window._refresh_sample_list()
            group_item = self._group_item(window, group.id)
            assert group_item is not None
            self.assertTrue(group_item.isExpanded())

    def test_expansion_survives_sample_move_and_selection_follows_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_project_structure(root)
            source = create_condition_group(root, "Source")
            target = create_condition_group(root, "Target")
            video = root / "clip.mp4"
            _write_test_video(video)
            _batch, row = create_sample_from_data(root, source.id, video)
            sample_id = str(row["sample_id"])

            window = self._make_window(root)
            window._current_sample = {"sample_id": sample_id}
            window._refresh_sample_list()

            source_item = self._group_item(window, source.id)
            target_item = self._group_item(window, target.id)
            assert source_item is not None
            assert target_item is not None
            source_item.setExpanded(True)
            target_item.setExpanded(False)

            move_sample_to_condition_group(root, sample_id, target.id)
            window._refresh_sample_list()

            source_item = self._group_item(window, source.id)
            target_item = self._group_item(window, target.id)
            assert source_item is not None
            assert target_item is not None
            self.assertTrue(source_item.isExpanded())
            self.assertFalse(target_item.isExpanded())
            self.assertEqual(
                source_item.childIndicatorPolicy(),
                QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator,
            )

            restored = restore_selected_sample_by_id(window.tree_samples, sample_id)
            self.assertIsNotNone(restored)
            self.assertIs(window.tree_samples.currentItem(), restored)

    def test_rename_display_name_preserves_expansion_by_condition_group_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_project_structure(root)
            group = create_condition_group(root, "Control")

            window = self._make_window(root)
            window._refresh_sample_list()
            group_item = self._group_item(window, group.id)
            assert group_item is not None
            group_item.setExpanded(True)

            rename_condition_group(root, group.id, "Renamed Control")
            window._refresh_sample_list()
            group_item = self._group_item(window, group.id)
            assert group_item is not None
            self.assertTrue(group_item.isExpanded())
            self.assertEqual(group_item.text(0), "Renamed Control")


if __name__ == "__main__":
    unittest.main()
