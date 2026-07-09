"""Explorer tree widget with internal Sample drag/drop between Condition Groups."""

from __future__ import annotations

from PyQt6.QtCore import QMimeData, QModelIndex, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QDrag,
    QColor,
    QFontMetrics,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
)

from actintrack_app import gui_styles
from actintrack_app.explorer_sidebar import (
    EXPLORER_SAMPLE_MIME,
    ITEM_TYPE_CONDITION_GROUP,
    ITEM_TYPE_EMPTY_SAMPLE,
    ITEM_TYPE_SAMPLE,
    is_draggable_sample_meta,
    is_valid_sample_drop_target_meta,
    sample_sidebar_display_label,
    tree_item_condition_group_id,
)


def configure_condition_group_tree_item(item: QTreeWidgetItem) -> None:
    """Condition Groups always show a folder disclosure affordance."""
    item.setChildIndicatorPolicy(
        QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
    )


def collect_condition_group_expansion_state(tree: QTreeWidget) -> dict[str, bool]:
    """Snapshot expanded/collapsed state keyed by stable ``condition_group_id``."""
    remembered: dict[str, bool] = {}
    for top_idx in range(tree.topLevelItemCount()):
        top = tree.topLevelItem(top_idx)
        if top is None:
            continue
        meta = top.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(meta, dict):
            continue
        if meta.get("item_type") != ITEM_TYPE_CONDITION_GROUP:
            continue
        gid = str(meta.get("condition_group_id", "")).strip()
        if gid:
            remembered[gid] = top.isExpanded()
    return remembered


def default_expanded_state_for_condition_group(
    group_id: str,
    *,
    has_children: bool,
    remembered: dict[str, bool],
) -> bool:
    """Default non-empty groups expanded and empty groups collapsed unless remembered."""
    if group_id in remembered:
        return remembered[group_id]
    return has_children


def restore_selected_sample_by_id(
    tree: QTreeWidget,
    sample_id: str,
) -> QTreeWidgetItem | None:
    """Select a Sample row by stable ``sample_id`` when it still exists."""
    target = str(sample_id).strip()
    if not target:
        return None

    def walk(parent: QTreeWidgetItem) -> QTreeWidgetItem | None:
        for idx in range(parent.childCount()):
            child = parent.child(idx)
            meta = child.data(0, Qt.ItemDataRole.UserRole)
            if (
                isinstance(meta, dict)
                and meta.get("item_type") == ITEM_TYPE_SAMPLE
                and str(meta.get("sample_id", "")).strip() == target
            ):
                return child
            found = walk(child)
            if found is not None:
                return found
        return None

    for top_idx in range(tree.topLevelItemCount()):
        top = tree.topLevelItem(top_idx)
        if top is None:
            continue
        meta = top.data(0, Qt.ItemDataRole.UserRole)
        if (
            isinstance(meta, dict)
            and meta.get("item_type") == ITEM_TYPE_SAMPLE
            and str(meta.get("sample_id", "")).strip() == target
        ):
            tree.setCurrentItem(top)
            return top
        found = walk(top)
        if found is not None:
            tree.setCurrentItem(found)
            return found
    return None


def tree_index_shows_branch_indicator(tree: QTreeWidget, index) -> bool:
    """True when a row should paint the custom Explorer branch chevron."""
    model = tree.model()
    if model is None or not index.isValid():
        return False
    if model.hasChildren(index):
        return True
    item = tree.itemFromIndex(index)
    if item is None:
        return False
    return (
        item.childIndicatorPolicy()
        == QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
    )


def _drag_pixmap_for_label(label: str, font_metrics: QFontMetrics) -> QPixmap:
    text = label.strip() or "Sample"
    padding_x = 12
    padding_y = 6
    width = max(64, font_metrics.horizontalAdvance(text) + padding_x * 2)
    height = font_metrics.height() + padding_y * 2
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(45, 45, 48, 235))
    painter = QPainter(pixmap)
    painter.setPen(QColor(230, 230, 230))
    painter.drawText(padding_x, padding_y + font_metrics.ascent(), text)
    painter.end()
    return pixmap


def _item_has_custom_foreground(index) -> bool:
    brush = index.data(Qt.ItemDataRole.ForegroundRole)
    return isinstance(brush, QBrush) and brush.style() != Qt.BrushStyle.NoBrush


def _index_depth(index) -> int:
    depth = 0
    parent = index.parent()
    while parent.isValid():
        depth += 1
        parent = parent.parent()
    return depth


def _has_following_sibling(model, index) -> bool:
    parent = index.parent()
    if parent.isValid():
        return index.row() < model.rowCount(parent) - 1
    return index.row() < model.rowCount(QModelIndex()) - 1


def _ancestor_at_level(index, level: int):
    ancestor = index
    for _ in range(_index_depth(index) - level - 1):
        ancestor = ancestor.parent()
    return ancestor


def _branch_chevron_polygon(*, expanded: bool, center_x: float, center_y: float) -> QPolygonF:
    half = float(gui_styles.EXPLORER_BRANCH_CHEVRON_SIZE)
    if expanded:
        return QPolygonF(
            [
                QPointF(center_x - half, center_y - half * 0.35),
                QPointF(center_x + half, center_y - half * 0.35),
                QPointF(center_x, center_y + half * 0.75),
            ]
        )
    return QPolygonF(
        [
            QPointF(center_x - half * 0.75, center_y - half),
            QPointF(center_x - half * 0.75, center_y + half),
            QPointF(center_x + half * 0.75, center_y),
        ]
    )


def _paint_indent_guides(
    painter: QPainter,
    rect,
    index,
    *,
    depth: int,
    model,
) -> None:
    """Cursor/VS Code-style vertical guides for nested Explorer rows."""
    if depth <= 0:
        return

    indent = gui_styles.EXPLORER_TREE_INDENTATION
    guide_pen = QPen(QColor(gui_styles.COLOR_EXPLORER_INDENT_GUIDE))
    guide_pen.setWidth(gui_styles.EXPLORER_INDENT_GUIDE_WIDTH)

    painter.save()
    painter.setPen(guide_pen)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

    top = rect.top()
    bottom = rect.bottom()
    center_y = rect.center().y()

    for level in range(depth):
        x = rect.left() + level * indent + indent // 2

        if level == depth - 1:
            parent = index.parent()
            if parent.isValid() and index.row() == model.rowCount(parent) - 1:
                segment_bottom = center_y
            else:
                segment_bottom = bottom
        else:
            ancestor = _ancestor_at_level(index, level)
            if not _has_following_sibling(model, ancestor):
                continue
            segment_bottom = bottom

        painter.drawLine(x, top, x, segment_bottom)

    painter.restore()


def _paint_branch_chevron(
    painter: QPainter,
    rect,
    *,
    expanded: bool,
    selected: bool,
) -> None:
    color = QColor(
        gui_styles.COLOR_EXPLORER_BRANCH_SELECTED
        if selected
        else gui_styles.COLOR_EXPLORER_BRANCH
    )
    center_x = rect.center().x()
    center_y = rect.center().y()
    polygon = _branch_chevron_polygon(
        expanded=expanded,
        center_x=center_x,
        center_y=center_y,
    )

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawPolygon(polygon)
    painter.restore()


def configure_explorer_tree(tree: QTreeWidget) -> None:
    """Shared Explorer tree presentation defaults."""
    tree.setIndentation(gui_styles.EXPLORER_TREE_INDENTATION)
    tree.setUniformRowHeights(True)


class ExplorerTreeItemDelegate(QStyledItemDelegate):
    """Typography-only hierarchy for Condition Group vs Sample rows.

    Status/type badges are intentionally deferred until workflow states stabilize.
    """

    def initStyleOption(
        self,
        option: QStyleOptionViewItem,
        index,
    ) -> None:
        super().initStyleOption(option, index)
        if not index.isValid():
            return
        meta = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(meta, dict):
            return

        item_type = meta.get("item_type")
        selected = bool(option.state & QStyle.StateFlag.State_Selected)

        if item_type == ITEM_TYPE_CONDITION_GROUP:
            option.font = gui_styles.explorer_condition_group_font(option.font)
            text_color = QColor(
                gui_styles.COLOR_EXPLORER_SELECTION_TEXT
                if selected
                else gui_styles.COLOR_EXPLORER_GROUP_TEXT
            )
            option.palette.setColor(option.palette.ColorRole.Text, text_color)
            option.palette.setColor(option.palette.ColorRole.HighlightedText, text_color)
            return

        if item_type not in (ITEM_TYPE_SAMPLE, ITEM_TYPE_EMPTY_SAMPLE):
            return

        option.font = gui_styles.explorer_sample_font(option.font)
        if selected:
            text_color = QColor(gui_styles.COLOR_EXPLORER_SELECTION_TEXT)
            option.palette.setColor(option.palette.ColorRole.Text, text_color)
            option.palette.setColor(option.palette.ColorRole.HighlightedText, text_color)
            return

        if not _item_has_custom_foreground(index):
            text_color = QColor(gui_styles.COLOR_EXPLORER_SAMPLE_TEXT)
            option.palette.setColor(option.palette.ColorRole.Text, text_color)
            option.palette.setColor(option.palette.ColorRole.HighlightedText, text_color)


class ExplorerTreeWidget(QTreeWidget):
    """QTreeWidget that drags one Sample at a time onto a Condition Group target."""

    sample_drop_requested = pyqtSignal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setItemDelegate(ExplorerTreeItemDelegate(self))
        configure_explorer_tree(self)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def drawBranches(self, painter, rect, index) -> None:  # noqa: N802
        if not index.isValid() or index.column() != 0:
            return
        model = self.model()
        if model is None:
            return

        depth = _index_depth(index)
        if depth > 0:
            _paint_indent_guides(
                painter,
                rect,
                index,
                depth=depth,
                model=model,
            )

        if not tree_index_shows_branch_indicator(self, index):
            return

        selected = False
        selection_model = self.selectionModel()
        if selection_model is not None:
            selected = selection_model.isSelected(index)

        _paint_branch_chevron(
            painter,
            rect,
            expanded=self.isExpanded(index),
            selected=selected,
        )

    @staticmethod
    def _item_meta(item: QTreeWidgetItem | None) -> dict | None:
        if item is None:
            return None
        data = item.data(0, Qt.ItemDataRole.UserRole)
        return data if isinstance(data, dict) else None

    def _drop_target_group_id(self, item: QTreeWidgetItem | None) -> str | None:
        meta = self._item_meta(item)
        if not is_valid_sample_drop_target_meta(meta):
            return None
        return tree_item_condition_group_id(meta)

    def startDrag(self, supportedActions) -> None:  # noqa: N802
        item = self.currentItem()
        meta = self._item_meta(item)
        if not is_draggable_sample_meta(meta):
            return
        sample_id = str(meta.get("sample_id", "")).strip()
        if not sample_id:
            return
        mime = QMimeData()
        mime.setData(EXPLORER_SAMPLE_MIME, sample_id.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        label = sample_sidebar_display_label(meta)
        pixmap = _drag_pixmap_for_label(label, QFontMetrics(self.font()))
        drag.setPixmap(pixmap)
        drag.setHotSpot(pixmap.rect().center())
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if not event.mimeData().hasFormat(EXPLORER_SAMPLE_MIME):
            event.ignore()
            return
        target_gid = self._drop_target_group_id(self.itemAt(event.position().toPoint()))
        if target_gid:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if not event.mimeData().hasFormat(EXPLORER_SAMPLE_MIME):
            event.ignore()
            return
        target_gid = self._drop_target_group_id(self.itemAt(event.position().toPoint()))
        if target_gid:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        if not event.mimeData().hasFormat(EXPLORER_SAMPLE_MIME):
            event.ignore()
            return
        sample_id = bytes(event.mimeData().data(EXPLORER_SAMPLE_MIME)).decode("utf-8")
        target_gid = self._drop_target_group_id(self.itemAt(event.position().toPoint()))
        if not sample_id or not target_gid:
            event.ignore()
            return
        self.sample_drop_requested.emit(sample_id, target_gid)
        event.acceptProposedAction()
