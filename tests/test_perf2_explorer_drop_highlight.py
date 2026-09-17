"""PERF2 Explorer external-drop target highlight (not screenshot-based)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QMimeData, QPointF, Qt, QUrl
from PyQt6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent
from PyQt6.QtWidgets import QApplication, QTreeWidgetItem

from actintrack_app.explorer_sidebar import (
    EXPLORER_SAMPLE_MIME,
    condition_group_tree_meta,
    sample_tree_meta,
)
from actintrack_app.explorer_tree import (
    EXPLORER_EXTERNAL_DROP_TARGET_ROLE,
    ExplorerTreeWidget,
)


def _group_item(group_id: str, label: str) -> QTreeWidgetItem:
    item = QTreeWidgetItem([label])
    item.setData(0, Qt.ItemDataRole.UserRole, condition_group_tree_meta(group_id))
    return item


def _sample_item(sample_id: str, group_id: str, label: str) -> QTreeWidgetItem:
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


class ExplorerDropHighlightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tree = ExplorerTreeWidget()
        self.g1 = _group_item("cg_a", "WT")
        self.g2 = _group_item("cg_b", "Mutant")
        self.s1 = _sample_item("S1", "cg_a", "a.png")
        self.s2 = _sample_item("S2", "cg_b", "b.mp4")
        self.tree.addTopLevelItem(self.g1)
        self.tree.addTopLevelItem(self.g2)
        self.g1.addChild(self.s1)
        self.g2.addChild(self.s2)
        self.g1.setExpanded(True)
        self.g2.setExpanded(True)
        self.tree.resize(280, 240)
        self.tree.show()
        self._app.processEvents()

    def test_highlight_follows_group_and_clears(self) -> None:
        self.tree._apply_external_drop_highlight("cg_a")
        self.assertEqual(self.tree.current_external_drop_target(), "cg_a")
        self.assertTrue(bool(self.g1.data(0, EXPLORER_EXTERNAL_DROP_TARGET_ROLE)))
        self.assertFalse(bool(self.g2.data(0, EXPLORER_EXTERNAL_DROP_TARGET_ROLE)))
        self.tree._apply_external_drop_highlight("cg_b")
        self.assertEqual(self.tree.current_external_drop_target(), "cg_b")
        self.assertFalse(bool(self.g1.data(0, EXPLORER_EXTERNAL_DROP_TARGET_ROLE)))
        self.assertTrue(bool(self.g2.data(0, EXPLORER_EXTERNAL_DROP_TARGET_ROLE)))
        self.tree._clear_external_drop_highlight()
        self.assertIsNone(self.tree.current_external_drop_target())
        self.assertFalse(bool(self.g2.data(0, EXPLORER_EXTERNAL_DROP_TARGET_ROLE)))

    def test_supported_files_flag_and_internal_mime_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "cell.png"
            txt = Path(tmp) / "notes.txt"
            png.write_bytes(b"x")
            txt.write_bytes(b"y")
            good = QMimeData()
            good.setUrls([QUrl.fromLocalFile(str(png))])
            self.assertTrue(self.tree._external_drop_has_supported_files(good))
            bad = QMimeData()
            bad.setUrls([QUrl.fromLocalFile(str(txt))])
            self.assertFalse(self.tree._external_drop_has_supported_files(bad))
            internal = QMimeData()
            internal.setData(EXPLORER_SAMPLE_MIME, b"S1")
            internal.setUrls([QUrl.fromLocalFile(str(png))])
            self.assertFalse(self.tree._external_drop_has_supported_files(internal))
            mixed = QMimeData()
            mixed.setUrls(
                [QUrl.fromLocalFile(str(png)), QUrl.fromLocalFile(str(txt))]
            )
            self.assertTrue(self.tree._external_drop_has_supported_files(mixed))

    def test_internal_drag_does_not_set_external_highlight(self) -> None:
        mime = QMimeData()
        mime.setData(EXPLORER_SAMPLE_MIME, b"S1")
        pos = self.tree.visualItemRect(self.g1).center()
        event = QDragMoveEvent(
            pos,
            Qt.DropAction.MoveAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.tree.dragMoveEvent(event)
        self.assertIsNone(self.tree.current_external_drop_target())

    def test_drag_leave_clears_highlight(self) -> None:
        self.tree._apply_external_drop_highlight("cg_a")
        event = QDragLeaveEvent()
        self.tree.dragLeaveEvent(event)
        self.assertIsNone(self.tree.current_external_drop_target())

    def test_drop_clears_highlight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "cell.png"
            png.write_bytes(b"x")
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(png))])
            self.tree._apply_external_drop_highlight("cg_a")
            pos = QPointF(self.tree.visualItemRect(self.g1).center())
            event = QDropEvent(
                pos,
                Qt.DropAction.CopyAction,
                mime,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            emitted: list[tuple[str, list]] = []
            self.tree.external_files_drop_requested.connect(
                lambda gid, paths: emitted.append((gid, paths))
            )
            self.tree.dropEvent(event)
            self.assertIsNone(self.tree.current_external_drop_target())
            self.assertEqual(len(emitted), 1)
            self.assertEqual(emitted[0][0], "cg_a")

    def test_invalid_file_does_not_highlight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            txt = Path(tmp) / "notes.txt"
            txt.write_bytes(b"y")
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(txt))])
            pos = self.tree.visualItemRect(self.g1).center()
            event = QDragEnterEvent(
                pos,
                Qt.DropAction.CopyAction,
                mime,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            self.tree.dragEnterEvent(event)
            self.assertIsNone(self.tree.current_external_drop_target())
            self.assertFalse(event.isAccepted())


if __name__ == "__main__":
    unittest.main()
