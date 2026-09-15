"""Modeless Analysis window for inspecting contributing measurements."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from actintrack_app.gui_styles import apply_body_label_style, apply_hint_italic_style
from actintrack_app.measurement_series import MetricMeasurementSeries
from actintrack_app.media_capabilities import MetricId
from actintrack_app.metric_analysis_ui import ORIENTATION_LEGEND_TEXT

_METRIC_TITLES = {
    MetricId.GENERAL_MOVEMENT: "General Movement",
    MetricId.OPTICAL_FLOW: "Optical Flow",
    MetricId.TOWARD_NUCLEUS: "Toward Nucleus",
    MetricId.ORIENTATION: "F-actin Orientation",
}


class MeasurementInspectorWindow(QMainWindow):
    """Non-blocking inspector bound to one persisted analysis run."""

    def __init__(
        self,
        series: MetricMeasurementSeries,
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._series = series
        title = _METRIC_TITLES.get(series.metric_id, series.metric_id.value)
        self.setWindowTitle(f"Measurements — {title}")
        self.resize(720, 480)

        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        header = QLabel(
            f"Sample: {series.sample_label or series.sample_id}\n"
            f"Condition Group: {series.condition_group or '—'}\n"
            f"Metric: {title}\n"
            f"Analysis run: {series.analysis_run_id or '—'}"
        )
        header.setWordWrap(True)
        apply_body_label_style(header)
        layout.addWidget(header)

        summary_bits = [
            f"Displayed result: "
            f"{'—' if series.summary_value is None else f'{series.summary_value:.6g} {series.summary_unit}'}",
            f"Contributing measurements: {series.measurement_count}",
        ]
        summary = QLabel("\n".join(summary_bits))
        summary.setWordWrap(True)
        apply_body_label_style(summary)
        layout.addWidget(summary)

        if series.metric_id is MetricId.ORIENTATION:
            legend = QLabel(ORIENTATION_LEGEND_TEXT)
            apply_hint_italic_style(legend)
            layout.addWidget(legend)

        for note in series.notes:
            note_lbl = QLabel(note)
            note_lbl.setWordWrap(True)
            apply_hint_italic_style(note_lbl)
            layout.addWidget(note_lbl)

        table = QTableWidget(self)
        table.setColumnCount(len(series.columns))
        table.setHorizontalHeaderLabels([c.label for c in series.columns])
        table.setRowCount(len(series.rows))
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        keys = [c.key for c in series.columns]
        for r, row in enumerate(series.rows):
            for c, key in enumerate(keys):
                value = row.get(key, "")
                if isinstance(value, float):
                    text = f"{value:.6g}"
                else:
                    text = "" if value is None else str(value)
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(r, c, item)
        table.resizeColumnsToContents()
        layout.addWidget(table, stretch=1)

    @property
    def analysis_run_id(self) -> str:
        return self._series.analysis_run_id

    @property
    def sample_id(self) -> str:
        return self._series.sample_id

    @property
    def metric_id(self) -> MetricId:
        return self._series.metric_id
