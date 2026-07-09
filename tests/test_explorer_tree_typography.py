"""Tests for Explorer tree typography hierarchy (presentation only)."""

from __future__ import annotations

import unittest

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QBrush, QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication, QStyleOptionViewItem, QTreeWidgetItem

from actintrack_app import gui_styles
from actintrack_app.explorer_sidebar import (
    ITEM_TYPE_CONDITION_GROUP,
    ITEM_TYPE_EMPTY_SAMPLE,
    ITEM_TYPE_SAMPLE,
    condition_group_tree_meta,
    empty_sample_tree_meta,
    sample_tree_meta,
)
from actintrack_app.explorer_tree import (
    ExplorerTreeItemDelegate,
    ExplorerTreeWidget,
    _index_depth,
    _paint_indent_guides,
)


class ExplorerTypographyStyleTests(unittest.TestCase):
    def test_group_text_is_brighter_than_sample_text(self) -> None:
        group_value = int(gui_styles.COLOR_EXPLORER_GROUP_TEXT[1:], 16)
        sample_value = int(gui_styles.COLOR_EXPLORER_SAMPLE_TEXT[1:], 16)
        self.assertGreater(group_value, sample_value)

    def test_group_and_sample_share_base_font_weight(self) -> None:
        from PyQt6.QtGui import QFont

        base = QFont()
        group = gui_styles.explorer_condition_group_font(base)
        sample = gui_styles.explorer_sample_font(base)
        self.assertEqual(int(group.weight()), int(sample.weight()))
        self.assertEqual(int(group.weight()), int(QFont.Weight.Normal))


class ExplorerTreeDelegateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _style_option_for_item(self, item: QTreeWidgetItem) -> QStyleOptionViewItem:
        tree = ExplorerTreeWidget()
        tree.addTopLevelItem(item)
        index = tree.indexFromItem(item)
        option = QStyleOptionViewItem()
        delegate = ExplorerTreeItemDelegate(tree)
        delegate.initStyleOption(option, index)
        return option

    def test_condition_group_uses_brighter_text_than_samples(self) -> None:
        item = QTreeWidgetItem(["WT Control"])
        item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            condition_group_tree_meta("cg_test"),
        )
        option = self._style_option_for_item(item)
        self.assertEqual(
            int(option.font.weight()),
            int(gui_styles.explorer_condition_group_font(option.font).weight()),
        )
        self.assertEqual(
            option.palette.color(option.palette.ColorRole.Text).name(),
            QColor(gui_styles.COLOR_EXPLORER_GROUP_TEXT).name(),
        )

    def test_sample_uses_regular_muted_text_by_default(self) -> None:
        item = QTreeWidgetItem(["clip.mp4"])
        item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            sample_tree_meta({"sample_id": "s1", "original_filename": "clip.mp4"}),
        )
        option = self._style_option_for_item(item)
        self.assertEqual(int(option.font.weight()), int(gui_styles.explorer_sample_font(option.font).weight()))
        self.assertEqual(
            option.palette.color(option.palette.ColorRole.Text).name(),
            QColor(gui_styles.COLOR_EXPLORER_SAMPLE_TEXT).name(),
        )

    def test_sample_preserves_status_foreground_when_set(self) -> None:
        item = QTreeWidgetItem(["clip.mp4"])
        item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            sample_tree_meta(
                {
                    "sample_id": "s1",
                    "original_filename": "clip.mp4",
                    "processing_status": "processed",
                }
            ),
        )
        item.setForeground(0, QBrush(QColor("#3ddc84")))
        option = self._style_option_for_item(item)
        self.assertEqual(
            option.palette.color(option.palette.ColorRole.Text).name(),
            "#3ddc84",
        )

    def test_selected_rows_use_selection_text_color(self) -> None:
        item = QTreeWidgetItem(["WT Control"])
        item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            condition_group_tree_meta("cg_test"),
        )
        tree = ExplorerTreeWidget()
        tree.addTopLevelItem(item)
        tree.setCurrentItem(item)
        index = tree.indexFromItem(item)
        option = QStyleOptionViewItem()
        option.state |= tree.style().StateFlag.State_Selected
        ExplorerTreeItemDelegate(tree).initStyleOption(option, index)
        self.assertEqual(
            option.palette.color(option.palette.ColorRole.Text).name(),
            QColor(gui_styles.COLOR_EXPLORER_SELECTION_TEXT).name(),
        )

    def test_empty_sample_placeholder_keeps_custom_foreground(self) -> None:
        item = QTreeWidgetItem(["(no data — right-click Replace Data)"])
        item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            empty_sample_tree_meta("cg_test", "Batch 1"),
        )
        item.setForeground(0, QBrush(QColor("#666666")))
        option = self._style_option_for_item(item)
        self.assertEqual(
            option.palette.color(option.palette.ColorRole.Text).name(),
            "#666666",
        )

    def test_tree_installs_typography_delegate(self) -> None:
        tree = ExplorerTreeWidget()
        self.assertIsInstance(tree.itemDelegate(), ExplorerTreeItemDelegate)

    def test_tree_uses_shared_indentation(self) -> None:
        tree = ExplorerTreeWidget()
        self.assertEqual(tree.indentation(), gui_styles.EXPLORER_TREE_INDENTATION)

    def test_tree_content_left_inset_nests_groups_under_root(self) -> None:
        self.assertEqual(
            gui_styles.EXPLORER_TREE_CONTENT_LEFT_PADDING,
            gui_styles.EXPLORER_CONTENT_LEFT_PADDING
            + gui_styles.EXPLORER_TREE_ROOT_OFFSET,
        )

    def test_tree_has_custom_branch_drawing(self) -> None:
        self.assertTrue(hasattr(ExplorerTreeWidget, "drawBranches"))


class ExplorerIndentGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _sample_tree_with_child(self) -> tuple[ExplorerTreeWidget, QTreeWidgetItem]:
        tree = ExplorerTreeWidget()
        group = QTreeWidgetItem(["WT Control"])
        group.setData(
            0,
            Qt.ItemDataRole.UserRole,
            condition_group_tree_meta("cg_test"),
        )
        sample = QTreeWidgetItem(["clip.mp4"])
        sample.setData(
            0,
            Qt.ItemDataRole.UserRole,
            sample_tree_meta({"sample_id": "s1", "original_filename": "clip.mp4"}),
        )
        group.addChild(sample)
        tree.addTopLevelItem(group)
        group.setExpanded(True)
        return tree, sample

    def test_sample_row_has_nested_depth(self) -> None:
        tree, sample = self._sample_tree_with_child()
        index = tree.indexFromItem(sample)
        self.assertEqual(_index_depth(index), 1)

    def test_top_level_group_has_zero_depth(self) -> None:
        tree, _sample = self._sample_tree_with_child()
        group = tree.topLevelItem(0)
        index = tree.indexFromItem(group)
        self.assertEqual(_index_depth(index), 0)

    def test_indent_guides_paint_for_nested_sample_rows(self) -> None:
        tree, sample = self._sample_tree_with_child()
        index = tree.indexFromItem(sample)
        indent = gui_styles.EXPLORER_TREE_INDENTATION
        image = QImage(indent * 2, 28, QImage.Format.Format_RGB32)
        image.fill(0)

        painter = QPainter(image)
        tree.drawBranches(painter, QRect(0, 0, indent * 2, 28), index)
        painter.end()

        guide_color = QColor(gui_styles.COLOR_EXPLORER_INDENT_GUIDE)
        guide_x = indent // 2
        painted = QColor(image.pixel(guide_x, 7))
        self.assertEqual(painted.rgb() & 0xFFFFFF, guide_color.rgb() & 0xFFFFFF)

    def test_indent_guides_skip_top_level_rows(self) -> None:
        image = QImage(36, 28, QImage.Format.Format_RGB32)
        image.fill(0)
        tree, _sample = self._sample_tree_with_child()
        group = tree.topLevelItem(0)
        index = tree.indexFromItem(group)

        painter = QPainter(image)
        _paint_indent_guides(
            painter,
            QRect(0, 0, 36, 28),
            index,
            depth=_index_depth(index),
            model=tree.model(),
        )
        painter.end()

        guide_color = QColor(gui_styles.COLOR_EXPLORER_INDENT_GUIDE)
        found = any(
            QColor(image.pixel(x, y)) == guide_color
            for y in range(image.height())
            for x in range(image.width())
        )
        self.assertFalse(found)


if __name__ == "__main__":
    unittest.main()
