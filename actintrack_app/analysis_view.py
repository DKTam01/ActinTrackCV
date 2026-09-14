"""PyQt widgets for the read-only Analysis view."""

from __future__ import annotations

from typing import Any, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
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
from actintrack_app.gui_styles import (
    apply_hint_italic_style,
    apply_muted_hint_style,
    apply_panel_inner_margins,
)

UNAVAILABLE = "—"
NUCLEUS_REQUIRED_TIP = "Requires nucleus annotation"
ORIENTATION_HINT = (
    "F-actin Orientation is structural (0° radial · 90° tangential), "
    "not a motion angle. Toward Nucleus and Orientation require a nucleus. "
    "Group values are means of samples that have that metric; n is shown "
    "under each value."
)

PRIMARY_SUMMARY_HEADERS = [
    "Condition Group",
    "Samples",
    "General Movement (µm/s)",
    "Optical Flow (µm/s)",
    "Toward Nucleus (µm/s)",
    "F-actin Orientation (°)",
]
SAMPLE_DETAIL_HEADERS = [
    "Condition Group",
    "Sample",
    "Status",
    "General Movement (µm/s)",
    "Optical Flow (µm/s)",
    "Toward Nucleus (µm/s)",
    "F-actin Orientation (°)",
]
COMPARISON_HEADERS = [
    "Rank",
    "Condition Group",
    "General Movement (µm/s)",
    "Optical Flow (µm/s)",
    "Toward Nucleus (µm/s)",
    "F-actin Orientation (°)",
]
HISTORICAL_SUMMARY_HEADERS = [
    "Condition Group",
    "Tracking Downward (µm/s)",
    "Tracking Downward Std Dev (µm/s)",
    "OF Downward Motion (µm/s)",
    "OF Net Y Velocity (µm/s)",
    "OF Directionality Ratio",
]
HISTORICAL_SAMPLE_HEADERS = [
    "Condition Group",
    "Sample",
    "Tracking Downward (µm/s)",
    "OF Downward Motion (µm/s)",
    "OF Net Y Velocity (µm/s)",
    "OF Directionality Ratio",
]


def _fmt_float(value: Optional[float], *, places: int = 4) -> str:
    if value is None:
        return UNAVAILABLE
    return f"{value:.{places}f}"


def _fmt_group_metric(
    value: Optional[float],
    n: int,
    *,
    places: int = 4,
    missing_tip: str = "",
) -> tuple[str, str]:
    """Format a group mean without inventing a value when data are missing."""
    if value is None:
        return UNAVAILABLE, missing_tip
    count = int(n)
    text = f"{value:.{places}f}\nn={count}"
    noun = "sample" if count == 1 else "samples"
    return text, f"Mean of {count} {noun}"


def _set_table_cell(
    table: QTableWidget,
    row: int,
    col: int,
    text: str,
    *,
    sort_value: Any = None,
    numeric: bool = False,
    tooltip: str = "",
) -> None:
    item = QTableWidgetItem(text)
    if numeric:
        item.setTextAlignment(
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        )
        if sort_value is not None:
            item.setData(Qt.ItemDataRole.UserRole, sort_value)
        else:
            item.setData(Qt.ItemDataRole.UserRole, float("-inf"))
    if tooltip:
        item.setToolTip(tooltip)
    table.setItem(row, col, item)


class AnalysisViewWidget(QWidget):
    """Read-only tables for condition-group summaries, sample details, and comparison."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        apply_panel_inner_margins(layout)

        self.lbl_empty = QLabel("")
        self.lbl_empty.setWordWrap(True)
        apply_hint_italic_style(self.lbl_empty)
        self.lbl_empty.hide()
        layout.addWidget(self.lbl_empty)

        self.lbl_metric_hint = QLabel(ORIENTATION_HINT)
        self.lbl_metric_hint.setWordWrap(True)
        apply_muted_hint_style(self.lbl_metric_hint)
        layout.addWidget(self.lbl_metric_hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)

        self.tbl_breed_summary = self._make_table(PRIMARY_SUMMARY_HEADERS)
        body_layout.addWidget(
            self._wrap_group("Condition Group Summary", self.tbl_breed_summary)
        )

        self.tbl_sample_details = self._make_table(SAMPLE_DETAIL_HEADERS)
        body_layout.addWidget(
            self._wrap_group("Sample Details", self.tbl_sample_details)
        )

        self.tbl_comparison = self._make_table(COMPARISON_HEADERS)
        body_layout.addWidget(
            self._wrap_group("Condition Group Comparison", self.tbl_comparison)
        )

        self.chk_show_historical = QCheckBox(
            "Show historical image-direction metrics"
        )
        self.chk_show_historical.setChecked(False)
        self.chk_show_historical.setToolTip(
            "Image-Y downward / net-Y optical-flow metrics. These are not "
            "nucleus-relative and are not the current primary comparison."
        )
        body_layout.addWidget(self.chk_show_historical)

        self.historical_host = QWidget()
        historical_layout = QVBoxLayout(self.historical_host)
        historical_layout.setContentsMargins(0, 0, 0, 0)
        self.tbl_historical_summary = self._make_table(HISTORICAL_SUMMARY_HEADERS)
        historical_layout.addWidget(
            self._wrap_group(
                "Historical image-direction metrics — condition groups",
                self.tbl_historical_summary,
            )
        )
        self.tbl_historical_samples = self._make_table(HISTORICAL_SAMPLE_HEADERS)
        historical_layout.addWidget(
            self._wrap_group(
                "Historical image-direction metrics — samples",
                self.tbl_historical_samples,
            )
        )
        self.historical_host.hide()
        self.chk_show_historical.toggled.connect(self.historical_host.setVisible)
        body_layout.addWidget(self.historical_host)

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
        table.setSortingEnabled(False)
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
        self._fill_historical_summary(report.breed_summaries)
        self._fill_historical_samples(report.sample_details)

    def _fill_breed_summary(self, rows: list[BreedSummaryRow]) -> None:
        table = self.tbl_breed_summary
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            gm_text, gm_tip = _fmt_group_metric(
                row.avg_general_movement, row.samples_with_results
            )
            of_text, of_tip = _fmt_group_metric(
                row.avg_of_general_movement, row.samples_with_of_results
            )
            tn_text, tn_tip = _fmt_group_metric(
                row.avg_toward_nucleus_velocity,
                row.samples_with_toward_nucleus_results,
                missing_tip=NUCLEUS_REQUIRED_TIP,
            )
            ori_text, ori_tip = _fmt_group_metric(
                row.avg_orientation_median_deg,
                row.samples_with_orientation_results,
                places=2,
                missing_tip=NUCLEUS_REQUIRED_TIP,
            )
            values: list[tuple[str, Any, bool, str]] = [
                (row.breed, row.breed, False, ""),
                (str(row.sample_count), row.sample_count, True, ""),
                (gm_text, row.avg_general_movement, True, gm_tip),
                (of_text, row.avg_of_general_movement, True, of_tip),
                (tn_text, row.avg_toward_nucleus_velocity, True, tn_tip),
                (ori_text, row.avg_orientation_median_deg, True, ori_tip),
            ]
            for c, (text, sort_value, numeric, tooltip) in enumerate(values):
                _set_table_cell(
                    table,
                    r,
                    c,
                    text,
                    sort_value=sort_value,
                    numeric=numeric,
                    tooltip=tooltip,
                )
        table.resizeRowsToContents()
        header = table.horizontalHeader()
        header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        table.setSortingEnabled(True)

    def _fill_sample_details(self, rows: list[SampleAnalysisRow]) -> None:
        table = self.tbl_sample_details
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            m = row.metrics
            tn_missing = m.toward_nucleus_velocity is None
            ori_missing = m.orientation_median_deg is None
            values: list[tuple[str, Any, bool, str]] = [
                (row.breed, row.breed, False, ""),
                (row.sample_label, row.sample_label, False, ""),
                (row.status, row.status, False, ""),
                (
                    _fmt_float(m.general_movement),
                    m.general_movement,
                    True,
                    "",
                ),
                (
                    _fmt_float(m.of_general_movement),
                    m.of_general_movement,
                    True,
                    "",
                ),
                (
                    _fmt_float(m.toward_nucleus_velocity),
                    m.toward_nucleus_velocity,
                    True,
                    NUCLEUS_REQUIRED_TIP if tn_missing else "",
                ),
                (
                    _fmt_float(m.orientation_median_deg, places=2),
                    m.orientation_median_deg,
                    True,
                    NUCLEUS_REQUIRED_TIP if ori_missing else "",
                ),
            ]
            for c, (text, sort_value, numeric, tooltip) in enumerate(values):
                _set_table_cell(
                    table,
                    r,
                    c,
                    text,
                    sort_value=sort_value,
                    numeric=numeric,
                    tooltip=tooltip,
                )
        table.resizeRowsToContents()
        header = table.horizontalHeader()
        header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        table.setSortingEnabled(True)

    def _fill_comparison(self, rows: list[BreedComparisonRow]) -> None:
        table = self.tbl_comparison
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values: list[tuple[str, Any, bool, str]] = [
                (str(row.rank), row.rank, True, ""),
                (row.breed, row.breed, False, ""),
                (
                    _fmt_float(row.avg_general_movement),
                    row.avg_general_movement,
                    True,
                    "",
                ),
                (
                    _fmt_float(row.avg_of_general_movement),
                    row.avg_of_general_movement,
                    True,
                    "",
                ),
                (
                    _fmt_float(row.avg_toward_nucleus_velocity),
                    row.avg_toward_nucleus_velocity,
                    True,
                    NUCLEUS_REQUIRED_TIP
                    if row.avg_toward_nucleus_velocity is None
                    else "",
                ),
                (
                    _fmt_float(row.avg_orientation_median_deg, places=2),
                    row.avg_orientation_median_deg,
                    True,
                    NUCLEUS_REQUIRED_TIP
                    if row.avg_orientation_median_deg is None
                    else "",
                ),
            ]
            for c, (text, sort_value, numeric, tooltip) in enumerate(values):
                _set_table_cell(
                    table,
                    r,
                    c,
                    text,
                    sort_value=sort_value,
                    numeric=numeric,
                    tooltip=tooltip,
                )
        table.resizeRowsToContents()
        header = table.horizontalHeader()
        header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        table.setSortingEnabled(True)

    def _fill_historical_summary(self, rows: list[BreedSummaryRow]) -> None:
        table = self.tbl_historical_summary
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values: list[tuple[str, Any, bool]] = [
                (row.breed, row.breed, False),
                (_fmt_float(row.avg_downward_velocity), row.avg_downward_velocity, True),
                (
                    _fmt_float(row.std_downward_velocity),
                    row.std_downward_velocity,
                    True,
                ),
                (
                    _fmt_float(row.avg_of_downward_motion),
                    row.avg_of_downward_motion,
                    True,
                ),
                (
                    _fmt_float(row.avg_of_net_y_velocity),
                    row.avg_of_net_y_velocity,
                    True,
                ),
                (
                    _fmt_float(row.avg_of_directionality_ratio),
                    row.avg_of_directionality_ratio,
                    True,
                ),
            ]
            for c, (text, sort_value, numeric) in enumerate(values):
                _set_table_cell(
                    table, r, c, text, sort_value=sort_value, numeric=numeric
                )
        table.resizeRowsToContents()
        header = table.horizontalHeader()
        header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        table.setSortingEnabled(True)

    def _fill_historical_samples(self, rows: list[SampleAnalysisRow]) -> None:
        table = self.tbl_historical_samples
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            m = row.metrics
            values: list[tuple[str, Any, bool]] = [
                (row.breed, row.breed, False),
                (row.sample_label, row.sample_label, False),
                (_fmt_float(m.downward_velocity), m.downward_velocity, True),
                (_fmt_float(m.of_downward_motion), m.of_downward_motion, True),
                (_fmt_float(m.of_net_y_velocity), m.of_net_y_velocity, True),
                (
                    _fmt_float(m.of_directionality_ratio),
                    m.of_directionality_ratio,
                    True,
                ),
            ]
            for c, (text, sort_value, numeric) in enumerate(values):
                _set_table_cell(
                    table, r, c, text, sort_value=sort_value, numeric=numeric
                )
        table.resizeRowsToContents()
        header = table.horizontalHeader()
        header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        table.setSortingEnabled(True)
