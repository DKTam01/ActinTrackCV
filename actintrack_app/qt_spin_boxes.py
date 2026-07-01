"""Spin boxes that ignore mouse-wheel events to prevent accidental value changes."""

from __future__ import annotations

from PyQt6.QtWidgets import QDoubleSpinBox, QSpinBox


class NoWheelSpinBox(QSpinBox):
    """QSpinBox that passes wheel events to the parent scroll area."""

    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox that passes wheel events to the parent scroll area."""

    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()
