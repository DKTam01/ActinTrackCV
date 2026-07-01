"""No-wheel spin boxes ignore mouse wheel without blocking other input."""

from __future__ import annotations

import unittest

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QApplication

from actintrack_app.qt_spin_boxes import NoWheelDoubleSpinBox, NoWheelSpinBox


class NoWheelSpinBoxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_spin_box_ignores_wheel(self) -> None:
        spin = NoWheelSpinBox()
        spin.setRange(0, 100)
        spin.setValue(10)
        event = QWheelEvent(
            QPointF(0, 0),
            QPointF(0, 0),
            QPoint(0, 120),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        spin.wheelEvent(event)
        self.assertEqual(spin.value(), 10)

    def test_double_spin_box_ignores_wheel(self) -> None:
        spin = NoWheelDoubleSpinBox()
        spin.setRange(0.0, 100.0)
        spin.setValue(2.5)
        event = QWheelEvent(
            QPointF(0, 0),
            QPointF(0, 0),
            QPoint(0, 120),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        spin.wheelEvent(event)
        self.assertAlmostEqual(spin.value(), 2.5)


if __name__ == "__main__":
    unittest.main()
