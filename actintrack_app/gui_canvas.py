"""Preview canvas with draggable rectangular ROI."""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

import cv2
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QLabel, QMenu

from actintrack_app.orientation import RectROI

if TYPE_CHECKING:
    from actintrack_app.gui import MainWindow


def numpy_bgr_to_qimage(frame: np.ndarray) -> QImage:
    h, w = frame.shape[:2]
    if frame.ndim == 2:
        bytes_per_line = w
        return QImage(
            frame.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8
        ).copy()
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    bytes_per_line = 3 * w
    return QImage(
        rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888
    ).copy()


class DragMode(Enum):
    NONE = auto()
    DRAW = auto()
    MOVE = auto()
    RESIZE = auto()
    CUTOFF = auto()


def _roi_geometry_equal(
    left: Optional[RectROI], right: Optional[RectROI]
) -> bool:
    if left is None or right is None:
        return left is right
    return (left.x, left.y, left.width, left.height) == (
        right.x,
        right.y,
        right.width,
        right.height,
    )


class ImageCanvas(QLabel):
    """Displays oriented frame with adjustable rectangular analysis ROI."""

    HANDLE_RADIUS = 8

    def __init__(self, main_window: MainWindow, parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self.setMinimumSize(480, 360)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #1e1e1e; border: 1px solid #444;")
        self._frame: Optional[np.ndarray] = None
        self._pixmap: Optional[QPixmap] = None
        self._roi: Optional[RectROI] = None
        self._scale = 1.0
        self._offset_x = 0
        self._offset_y = 0
        self._drag_mode = DragMode.NONE
        self._resize_handle: Optional[str] = None
        self._drag_start_img: Optional[tuple[int, int]] = None
        self._roi_at_drag_start: Optional[RectROI] = None
        self._cell_mask_overlay: Optional[np.ndarray] = None
        self._validity_mask: Optional[np.ndarray] = None
        self._cutoff_y: Optional[float] = None
        self._nucleus_xy: Optional[tuple[float, float]] = None
        self._interactive = True
        self._draw_roi = True
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

    def clear_preview(self) -> None:
        self._frame = None
        self._pixmap = None
        self._roi = None
        self._cell_mask_overlay = None
        self._validity_mask = None
        self._cutoff_y = None
        self._nucleus_xy = None
        self.clear()

    def set_interactive(self, enabled: bool) -> None:
        self._interactive = enabled

    def set_preview_frame(self, frame: np.ndarray) -> None:
        """Display a read-only preview frame without ROI handles."""
        self._frame = frame
        self._draw_roi = False
        self._update_pixmap()

    def set_frame(self, frame: np.ndarray, *, keep_roi: bool = False) -> None:
        self._draw_roi = True
        self._frame = frame
        if not keep_roi:
            self._roi = None
        elif self._roi is not None:
            self._roi = self._roi.clamp(frame.shape[1], frame.shape[0])
        self._update_pixmap()

    def set_scientific_overlay(
        self,
        *,
        validity_mask: Optional[np.ndarray] = None,
        cutoff_y: Optional[float] = None,
        nucleus_xy: Optional[tuple[float, float]] = None,
    ) -> None:
        """Update scientific visualization. Mask is oriented-frame bool, or None."""
        self._validity_mask = validity_mask
        self._cutoff_y = None if cutoff_y is None else float(cutoff_y)
        self._nucleus_xy = None if nucleus_xy is None else (float(nucleus_xy[0]), float(nucleus_xy[1]))
        if self._pixmap is not None or self._frame is not None:
            self._update_pixmap()

    def set_cell_mask_overlay(self, mask: Optional[np.ndarray]) -> None:
        self._cell_mask_overlay = mask
        self._redraw()

    def set_rect_roi(self, roi: Optional[RectROI]) -> None:
        if self._frame is None:
            self._roi = roi
            return
        if roi is None:
            new_roi = None
        else:
            new_roi = roi.clamp(self._frame.shape[1], self._frame.shape[0])
        if _roi_geometry_equal(self._roi, new_roi):
            return
        self._roi = new_roi
        self._redraw()
        if new_roi is not None:
            self._main_window.on_roi_changed(self._roi)

    def rect_roi(self) -> Optional[RectROI]:
        return self._roi

    def _update_pixmap(self) -> None:
        if self._frame is None:
            self._pixmap = None
            self.clear()
            return
        display = self._frame.copy()
        if (
            self._draw_roi
            and self._validity_mask is not None
            and self._validity_mask.shape[:2] == display.shape[:2]
        ):
            invalid = ~self._validity_mask.astype(bool)
            if np.any(invalid):
                darkened = (display[invalid].astype(np.float32) * 0.48).astype(
                    display.dtype
                )
                display[invalid] = darkened
            contours, _ = cv2.findContours(
                self._validity_mask.astype(np.uint8),
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )
            if contours:
                cv2.drawContours(display, contours, -1, (180, 160, 70), 1)
        elif self._cell_mask_overlay is not None:
            contours, _ = cv2.findContours(
                (self._cell_mask_overlay > 0).astype(np.uint8),
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )
            cv2.drawContours(display, contours, -1, (255, 255, 0), 1)
        qimg = numpy_bgr_to_qimage(display)
        self._pixmap = QPixmap.fromImage(qimg)
        self._redraw()

    def _widget_to_image(self, wx: int, wy: int) -> Optional[tuple[int, int]]:
        """Map canvas_display widget coords to oriented_frame_pixels.

        Image coords are oriented_frame_pixels of the displayed frame.
        Widget coords are canvas_display only and are never persisted.
        """
        if self._frame is None or self._pixmap is None:
            return None
        sx = wx - self._offset_x
        sy = wy - self._offset_y
        if sx < 0 or sy < 0:
            return None
        img_w, img_h = self._frame.shape[1], self._frame.shape[0]
        max_sx = int(img_w * self._scale)
        max_sy = int(img_h * self._scale)
        if sx > max_sx or sy > max_sy:
            return None
        ix = int(round(sx / self._scale))
        iy = int(round(sy / self._scale))
        return (
            max(0, min(ix, img_w - 1)),
            max(0, min(iy, img_h - 1)),
        )

    def _image_to_widget(self, ix: float, iy: float) -> tuple[int, int]:
        return (
            self._offset_x + int(ix * self._scale),
            self._offset_y + int(iy * self._scale),
        )

    def _cutoff_hit(self, ix: int, iy: int) -> bool:
        if self._cutoff_y is None or self._frame is None:
            return False
        tol = max(1.0, 6.0 / max(self._scale, 1e-6))
        return abs(float(iy) - float(self._cutoff_y)) <= tol

    def _handle_at(self, wx: int, wy: int) -> Optional[str]:
        if self._roi is None or self._frame is None:
            return None
        r = self._roi
        points = {
            "tl": (r.x, r.y),
            "tr": (r.x1, r.y),
            "bl": (r.x, r.y1),
            "br": (r.x1, r.y1),
            "tm": (r.x + r.width // 2, r.y),
            "bm": (r.x + r.width // 2, r.y1),
            "lm": (r.x, r.y + r.height // 2),
            "rm": (r.x1, r.y + r.height // 2),
        }
        hr = self.HANDLE_RADIUS
        for name, (ix, iy) in points.items():
            sx, sy = self._image_to_widget(ix, iy)
            if abs(wx - sx) <= hr and abs(wy - sy) <= hr:
                return name
        return None

    def _redraw(self) -> None:
        if self._pixmap is None:
            return
        target = self.size()
        scaled = self._pixmap.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._scale = scaled.height() / self._pixmap.height()
        self._offset_x = (target.width() - scaled.width()) // 2
        self._offset_y = (target.height() - scaled.height()) // 2

        composite = QPixmap(target)
        composite.fill(QColor("#1e1e1e"))
        painter = QPainter(composite)
        painter.drawPixmap(self._offset_x, self._offset_y, scaled)

        if self._draw_roi and self._roi is not None and self._frame is not None:
            r = self._roi
            x0, y0 = self._image_to_widget(r.x, r.y)
            x1, y1 = self._image_to_widget(r.x1, r.y1)
            pen = QPen(QColor(80, 220, 120), 2)
            painter.setPen(pen)
            painter.drawRect(x0, y0, x1 - x0, y1 - y0)
            painter.setFont(QFont("Helvetica", 9, QFont.Weight.Bold))
            painter.setPen(QColor(100, 220, 120))
            painter.drawText(x0 + 6, y0 + 16, "F-actin analysis ROI")
            for hx, hy in (
                (r.x, r.y),
                (r.x1, r.y),
                (r.x, r.y1),
                (r.x1, r.y1),
            ):
                sx, sy = self._image_to_widget(hx, hy)
                painter.setBrush(QBrush(QColor(80, 220, 120)))
                painter.drawEllipse(
                    sx - 4, sy - 4, 8, 8
                )

        if self._draw_roi and self._frame is not None:
            if self._cutoff_y is not None:
                y = float(self._cutoff_y)
                x0, y0 = self._image_to_widget(0, y)
                x1, y1 = self._image_to_widget(self._frame.shape[1], y)
                cutoff_pen = QPen(QColor(230, 150, 70), 2)
                cutoff_pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(cutoff_pen)
                painter.drawLine(x0, y0, x1, y1)
                painter.setFont(QFont("Helvetica", 9, QFont.Weight.Bold))
                painter.setPen(QColor(230, 160, 80))
                painter.drawText(x0 + 6, max(12, y0 - 6), "Cutoff")

            if self._nucleus_xy is not None:
                nx, ny = self._nucleus_xy
                sx, sy = self._image_to_widget(nx, ny)
                painter.setPen(QPen(QColor(255, 90, 160), 2))
                painter.setBrush(QBrush(QColor(255, 90, 160)))
                painter.drawEllipse(sx - 5, sy - 5, 10, 10)
                painter.drawLine(sx - 9, sy, sx + 9, sy)
                painter.drawLine(sx, sy - 9, sx, sy + 9)

        painter.end()
        self.setPixmap(composite)

    def _context_menu_targets_roi(self, pos) -> bool:
        """True when the click is inside the ROI or on its outline/handles."""
        wx, wy = int(pos.x()), int(pos.y())
        if self._handle_at(wx, wy):
            return True
        img_pt = self._widget_to_image(wx, wy)
        if img_pt is None or self._roi is None:
            return False
        ix, iy = img_pt
        r = self._roi
        if r.x <= ix < r.x1 and r.y <= iy < r.y1:
            return True
        x0, y0 = self._image_to_widget(r.x, r.y)
        x1, y1 = self._image_to_widget(r.x1, r.y1)
        margin = self.HANDLE_RADIUS
        outer = (
            x0 - margin <= wx <= x1 + margin and y0 - margin <= wy <= y1 + margin
        )
        inner = x0 + margin < wx < x1 - margin and y0 + margin < wy < y1 - margin
        return bool(outer and not inner)

    def _on_context_menu(self, pos) -> None:
        mw = self._main_window
        if not self._interactive or self._frame is None:
            return
        if mw._metric_analysis_view_active or mw._preview_mode != "full":
            return
        if mw._base_frame is None:
            return
        menu = QMenu(self)
        inside_roi = self._context_menu_targets_roi(pos)
        self._main_window._populate_roi_actions_menu(menu, inside_roi=inside_roi)
        action = menu.exec(self.mapToGlobal(pos))
        if action is None:
            return

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._redraw()

    def mousePressEvent(self, event):
        if not self._interactive:
            return
        if event.button() != Qt.MouseButton.LeftButton or self._frame is None:
            return
        wx, wy = int(event.position().x()), int(event.position().y())
        img_pt = self._widget_to_image(wx, wy)
        if img_pt is None:
            return
        ix, iy = img_pt
        placement = getattr(self._main_window, "_scientific_placement_mode", None)
        if placement == "nucleus":
            self._main_window.on_nucleus_placed(float(ix), float(iy))
            return
        if placement == "cutoff":
            self._main_window.on_cutoff_placed(float(iy))
            return

        if self._cutoff_hit(ix, iy):
            self._drag_mode = DragMode.CUTOFF
            self._drag_start_img = (ix, iy)
            return

        handle = self._handle_at(wx, wy)
        if handle and self._roi is not None:
            self._drag_mode = DragMode.RESIZE
            self._resize_handle = handle
            self._roi_at_drag_start = RectROI(
                self._roi.x, self._roi.y, self._roi.width, self._roi.height
            )
            self._drag_start_img = (ix, iy)
            return

        if self._roi is not None:
            r = self._roi
            if r.x <= ix < r.x1 and r.y <= iy < r.y1:
                self._drag_mode = DragMode.MOVE
                self._roi_at_drag_start = RectROI(r.x, r.y, r.width, r.height)
                self._drag_start_img = (ix, iy)
                return

        self._drag_mode = DragMode.DRAW
        self._drag_start_img = (ix, iy)
        self._roi = RectROI(ix, iy, 1, 1)
        self._redraw()

    def mouseMoveEvent(self, event):
        if not self._interactive:
            return
        if self._drag_mode == DragMode.NONE or self._frame is None:
            return
        wx, wy = int(event.position().x()), int(event.position().y())
        img_pt = self._widget_to_image(wx, wy)
        if img_pt is None:
            return
        ix, iy = img_pt
        w_img, h_img = self._frame.shape[1], self._frame.shape[0]

        if self._drag_mode == DragMode.CUTOFF:
            y = max(0, min(int(iy), h_img - 1))
            self._cutoff_y = float(y)
            self._redraw()
            self._main_window.on_cutoff_dragged(float(y))
            return

        if self._drag_mode == DragMode.DRAW and self._drag_start_img is not None:
            x0, y0 = self._drag_start_img
            self._roi = RectROI.from_xyxy(x0, y0, ix, iy).clamp(w_img, h_img)
            self._redraw()
            self._main_window.on_roi_changed(self._roi)
            return

        if (
            self._drag_mode == DragMode.MOVE
            and self._roi_at_drag_start is not None
            and self._drag_start_img is not None
        ):
            dx = ix - self._drag_start_img[0]
            dy = iy - self._drag_start_img[1]
            r0 = self._roi_at_drag_start
            self._roi = RectROI(
                r0.x + dx, r0.y + dy, r0.width, r0.height
            ).clamp(w_img, h_img)
            self._redraw()
            self._main_window.on_roi_changed(self._roi)
            return

        if (
            self._drag_mode == DragMode.RESIZE
            and self._roi_at_drag_start is not None
            and self._resize_handle
        ):
            r0 = self._roi_at_drag_start
            x0, y0, x1, y1 = r0.x, r0.y, r0.x1, r0.y1
            if "l" in self._resize_handle:
                x0 = ix
            if "r" in self._resize_handle:
                x1 = ix
            if "t" in self._resize_handle:
                y0 = iy
            if "b" in self._resize_handle:
                y1 = iy
            self._roi = RectROI.from_xyxy(x0, y0, x1, y1).clamp(w_img, h_img)
            self._redraw()
            self._main_window.on_roi_changed(self._roi)

    def mouseReleaseEvent(self, event):
        had_drag = self._drag_mode != DragMode.NONE
        cutoff_drag = self._drag_mode == DragMode.CUTOFF
        self._drag_mode = DragMode.NONE
        self._resize_handle = None
        if self._roi is not None and self._roi.width < 4 and self._roi.height < 4:
            self._roi = None
            self._redraw()
        if cutoff_drag:
            self._main_window.on_cutoff_edit_finished()
            return
        if had_drag:
            self._main_window.on_roi_edit_finished()
