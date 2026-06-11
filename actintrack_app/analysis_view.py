"""PyQt widgets for the read-only Analysis view."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGroupBox,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from actintrack_app.analysis_service import (
    AnalysisReport,
    BreedComparisonRow,
    BreedSummaryRow,
    SampleAnalysisRow,
)


def _fmt_float(value: Optional[float], *, places: int = 4) -> str:
    if value is None:
        return "—"
    return f"{value:.{places}f}"


def _fmt_int(value: Optional[int]) -> str:
    if value is None:
        return "—"
    return str(value)


class AnalysisViewWidget(QWidget):
    """Read-only tables for breed summaries, sample details, and breed comparison."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        intro = QLabel(
            "Tracking and motion-index metrics aggregated by Breed and Sample. "
            "Results are read from saved sample data; opening this view does not "
            "re-run tracking."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #666; margin-bottom: 6px;")
        layout.addWidget(intro)

        self.lbl_empty = QLabel("")
        self.lbl_empty.setWordWrap(True)
        self.lbl_empty.setStyleSheet("color: #888; font-style: italic;")
        self.lbl_empty.hide()
        layout.addWidget(self.lbl_empty)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)

        self.tbl_breed_summary = self._make_table(
            [
                "Breed",
                "Samples",
                "Samples with Results",
                "Avg Downward Velocity",
                "Avg General Movement",
                "Avg Motion Index",
                "Std Dev Downward Velocity",
                "Std Dev General Movement",
            ]
        )
        body_layout.addWidget(self._wrap_group("Breed Summary", self.tbl_breed_summary))

        self.tbl_sample_details = self._make_table(
            [
                "Breed",
                "Sample",
                "Status",
                "Data Status",
                "Downward Velocity",
                "General Movement",
                "Motion Index",
                "Valid Tracks",
                "Valid Steps",
                "Confidence",
                "Result Updated At",
            ]
        )
        body_layout.addWidget(self._wrap_group("Sample Details", self.tbl_sample_details))

        self.tbl_comparison = self._make_table(
            [
                "Rank",
                "Breed",
                "Avg Downward Velocity",
                "Avg General Movement",
                "Avg Motion Index",
                "Valid Sample Count",
            ]
        )
        body_layout.addWidget(self._wrap_group("Breed Comparison", self.tbl_comparison))
        body_layout.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll, stretch=1)

    @staticmethod
    def _wrap_group(title: str, table: QTableWidget) -> QGroupBox:
        box = QGroupBox(title)
        box_layout = QVBoxLayout(box)
        box_layout.addWidget(table)
        return box

    @staticmethod
    def _make_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        return table

    def refresh(self, report: AnalysisReport) -> None:
        if report.empty_message:
            self.lbl_empty.setText(report.empty_message)
            self.lbl_empty.show()
        else:
            self.lbl_empty.hide()

        self._fill_breed_summary(report.breed_summaries)
        self._fill_sample_details(report.sample_details)
        self._fill_comparison(report.breed_comparisons)

    def _fill_breed_summary(self, rows: list[BreedSummaryRow]) -> None:
        table = self.tbl_breed_summary
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [
                row.breed,
                str(row.sample_count),
                str(row.samples_with_results),
                _fmt_float(row.avg_downward_velocity),
                _fmt_float(row.avg_general_movement),
                _fmt_float(row.avg_motion_index),
                _fmt_float(row.std_downward_velocity),
                _fmt_float(row.std_general_movement),
            ]
            for c, text in enumerate(values):
                item = QTableWidgetItem(text)
                if c >= 3:
                    item.setTextAlignment(
                        int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    )
                table.setItem(r, c, item)

    def _fill_sample_details(self, rows: list[SampleAnalysisRow]) -> None:
        table = self.tbl_sample_details
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            m = row.metrics
            tracks = f"{m.valid_tracks}" if m.valid_tracks is not None else "—"
            values = [
                row.breed,
                row.sample_label,
                row.status,
                row.data_status,
                _fmt_float(m.downward_velocity),
                _fmt_float(m.general_movement),
                _fmt_float(m.motion_index),
                tracks,
                _fmt_int(m.valid_steps),
                _fmt_float(m.confidence, places=2),
                m.result_updated_at or "—",
            ]
            for c, text in enumerate(values):
                item = QTableWidgetItem(text)
                if c >= 4:
                    item.setTextAlignment(
                        int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    )
                table.setItem(r, c, item)

    def _fill_comparison(self, rows: list[BreedComparisonRow]) -> None:
        table = self.tbl_comparison
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [
                str(row.rank),
                row.breed,
                _fmt_float(row.avg_downward_velocity),
                _fmt_float(row.avg_general_movement),
                _fmt_float(row.avg_motion_index),
                str(row.valid_sample_count),
            ]
            for c, text in enumerate(values):
                item = QTableWidgetItem(text)
                if c >= 2:
                    item.setTextAlignment(
                        int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    )
                table.setItem(r, c, item)
