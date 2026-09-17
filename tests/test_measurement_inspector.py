"""CAL1 Measurement Inspector sorting, labels, and Orientation help."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel

from actintrack_app.measurement_inspector_window import (
    MeasurementInspectorWindow,
    semantic_sort_value,
)
from actintrack_app.measurement_series import (
    COHERENCE_HEADER_TOOLTIP,
    MeasurementColumn,
    MetricMeasurementSeries,
)
from actintrack_app.media_capabilities import MetricId
from actintrack_app.metric_analysis_ui import ORIENTATION_LEGEND_TEXT


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _column_texts(window: MeasurementInspectorWindow, col: int) -> list[str]:
    table = window.table
    return [table.item(row, col).text() for row in range(table.rowCount())]


def _sort_column(window: MeasurementInspectorWindow, col: int, order: Qt.SortOrder) -> None:
    window.table.sortItems(col, order)


class SemanticSortHelperTests(unittest.TestCase):
    def test_int_and_float_keys(self) -> None:
        self.assertEqual(semantic_sort_value("10", "int"), 10)
        self.assertEqual(semantic_sort_value(10.1, "float"), 10.1)
        self.assertIsNone(semantic_sort_value("x", "int"))


class InspectorSortingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _app()

    def _movement_window(self) -> MeasurementInspectorWindow:
        ids = [1, 10, 11, 2, 9, 99, 100, 303]
        floats = [0.9, 0.12, 0.603, 9.8, 10.1, 30.4, 2.0, 0.01]
        rows = []
        for i, n in enumerate(ids):
            rows.append(
                {
                    "n": n,
                    "track_id": n,
                    "prev_frame": n,
                    "frame": n + 1,
                    "px_per_frame": floats[i],
                    "um_per_s": floats[i],
                }
            )
        series = MetricMeasurementSeries(
            metric_id=MetricId.GENERAL_MOVEMENT,
            sample_id="S1",
            sample_label="Sample 1",
            condition_group="WT",
            analysis_run_id="run-1",
            summary_value=1.0,
            summary_unit="µm/s",
            row_kind="step",
            columns=[
                MeasurementColumn("n", "Measurement #", sort_kind="int"),
                MeasurementColumn("track_id", "Track", sort_kind="int"),
                MeasurementColumn("prev_frame", "From frame", sort_kind="int"),
                MeasurementColumn("frame", "To frame", sort_kind="int"),
                MeasurementColumn("px_per_frame", "Velocity (px/frame)", sort_kind="float"),
                MeasurementColumn("um_per_s", "Velocity (µm/s)", sort_kind="float"),
            ],
            rows=rows,
        )
        return MeasurementInspectorWindow(series)

    def test_measurement_number_sorts_numerically(self) -> None:
        window = self._movement_window()
        self.assertEqual(window.table.horizontalHeaderItem(0).text(), "Measurement #")
        _sort_column(window, 0, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            [int(v) for v in _column_texts(window, 0)],
            [1, 2, 9, 10, 11, 99, 100, 303],
        )
        _sort_column(window, 0, Qt.SortOrder.DescendingOrder)
        self.assertEqual(
            [int(v) for v in _column_texts(window, 0)],
            [303, 100, 99, 11, 10, 9, 2, 1],
        )

    def test_track_and_frame_sort_numerically(self) -> None:
        window = self._movement_window()
        for col in (1, 2):
            _sort_column(window, col, Qt.SortOrder.AscendingOrder)
            values = [int(v) for v in _column_texts(window, col)]
            self.assertEqual(values, sorted(values))
            _sort_column(window, col, Qt.SortOrder.DescendingOrder)
            values = [int(v) for v in _column_texts(window, col)]
            self.assertEqual(values, sorted(values, reverse=True))

    def test_velocity_columns_sort_numerically(self) -> None:
        window = self._movement_window()
        expected = sorted([0.9, 0.12, 0.603, 9.8, 10.1, 30.4, 2.0, 0.01])
        for col in (4, 5):
            _sort_column(window, col, Qt.SortOrder.AscendingOrder)
            values = [float(v) for v in _column_texts(window, col)]
            self.assertEqual(values, expected)
            _sort_column(window, col, Qt.SortOrder.DescendingOrder)
            values = [float(v) for v in _column_texts(window, col)]
            self.assertEqual(values, list(reversed(expected)))

    def test_hash_label_is_measurement_number(self) -> None:
        window = self._movement_window()
        labels = [
            window.table.horizontalHeaderItem(c).text()
            for c in range(window.table.columnCount())
        ]
        self.assertIn("Measurement #", labels)
        self.assertNotIn("#", labels)


class OrientationInspectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _app()

    def _window(self) -> MeasurementInspectorWindow:
        rows = [
            {"n": 10, "angle_deg": 30.4, "x_px": 10.1, "y_px": 99.0, "coherence": 0.12},
            {"n": 2, "angle_deg": 0.9, "x_px": 0.12, "y_px": 1.0, "coherence": 0.9},
            {"n": 100, "angle_deg": 10.1, "x_px": 30.4, "y_px": 10.0, "coherence": 0.603},
            {"n": 1, "angle_deg": 0.12, "x_px": 9.8, "y_px": 303.0, "coherence": 0.01},
        ]
        series = MetricMeasurementSeries(
            metric_id=MetricId.ORIENTATION,
            sample_id="S1",
            sample_label="Sample 1",
            condition_group="WT",
            analysis_run_id="run-o",
            summary_value=20.0,
            summary_unit="°",
            row_kind="orientation_sample",
            columns=[
                MeasurementColumn("n", "Measurement #", sort_kind="int"),
                MeasurementColumn("angle_deg", "Angle (°)", sort_kind="float"),
                MeasurementColumn("x_px", "x (px)", sort_kind="float"),
                MeasurementColumn("y_px", "y (px)", sort_kind="float"),
                MeasurementColumn(
                    "coherence",
                    "Coherence",
                    sort_kind="float",
                    header_tooltip=COHERENCE_HEADER_TOOLTIP,
                ),
            ],
            rows=rows,
            notes=("Sample result is the median of these angles.",),
        )
        return MeasurementInspectorWindow(series)

    def test_orientation_numeric_columns_sort(self) -> None:
        window = self._window()
        _sort_column(window, 0, Qt.SortOrder.AscendingOrder)
        self.assertEqual([int(v) for v in _column_texts(window, 0)], [1, 2, 10, 100])
        _sort_column(window, 1, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            [float(v) for v in _column_texts(window, 1)],
            [0.12, 0.9, 10.1, 30.4],
        )
        _sort_column(window, 2, Qt.SortOrder.DescendingOrder)
        self.assertEqual(
            [float(v) for v in _column_texts(window, 2)],
            [30.4, 10.1, 9.8, 0.12],
        )
        _sort_column(window, 4, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            [float(v) for v in _column_texts(window, 4)],
            [0.01, 0.12, 0.603, 0.9],
        )

    def test_coherence_tooltip_and_single_legend(self) -> None:
        window = self._window()
        self.assertEqual(window.table.horizontalHeaderItem(0).text(), "Measurement #")
        tip = window.table.horizontalHeaderItem(4).toolTip()
        self.assertIn("Coherence (0–1)", tip)
        self.assertIn("dominant orientation", tip)
        self.assertNotIn("radialness", tip.lower())
        texts = [w.text() for w in window.findChildren(QLabel)]
        radial_lines = [t for t in texts if "radial" in t and "tangential" in t]
        self.assertEqual(radial_lines, [ORIENTATION_LEGEND_TEXT])
        self.assertEqual(ORIENTATION_LEGEND_TEXT, "0° = radial · 90° = tangential")
        self.assertTrue(any("median of these angles" in t for t in texts))


class TowardNucleusAndOpticalFlowSortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _app()

    def test_optical_flow_integer_and_float_columns(self) -> None:
        series = MetricMeasurementSeries(
            metric_id=MetricId.OPTICAL_FLOW,
            sample_id="S1",
            sample_label="S1",
            condition_group="WT",
            analysis_run_id="run-of",
            summary_value=1.0,
            summary_unit="µm/s",
            row_kind="frame_pair",
            columns=[
                MeasurementColumn("n", "Measurement #", sort_kind="int"),
                MeasurementColumn("frame_a", "Frame A", sort_kind="int"),
                MeasurementColumn("frame_b", "Frame B", sort_kind="int"),
                MeasurementColumn("mean_px", "Mean magnitude (px/frame)", sort_kind="float"),
                MeasurementColumn("valid_count", "Valid pixels", sort_kind="int"),
            ],
            rows=[
                {"n": 10, "frame_a": 10, "frame_b": 11, "mean_px": 10.1, "valid_count": 100},
                {"n": 2, "frame_a": 2, "frame_b": 3, "mean_px": 0.9, "valid_count": 2},
                {"n": 1, "frame_a": 1, "frame_b": 2, "mean_px": 30.4, "valid_count": 303},
            ],
        )
        window = MeasurementInspectorWindow(series)
        _sort_column(window, 0, Qt.SortOrder.AscendingOrder)
        self.assertEqual([int(v) for v in _column_texts(window, 0)], [1, 2, 10])
        _sort_column(window, 3, Qt.SortOrder.AscendingOrder)
        self.assertEqual([float(v) for v in _column_texts(window, 3)], [0.9, 10.1, 30.4])
        _sort_column(window, 4, Qt.SortOrder.AscendingOrder)
        self.assertEqual([int(v) for v in _column_texts(window, 4)], [2, 100, 303])


if __name__ == "__main__":
    unittest.main()
