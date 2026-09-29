"""Serialize persisted measurement series for clipboard and CSV export.

Reads ``MetricMeasurementSeries`` columns and rows. Does not read table
display text and does not recompute metric values.
"""

from __future__ import annotations

import csv
import math
import re
from io import StringIO
from pathlib import Path
from typing import Any

from actintrack_app.measurement_series import MetricMeasurementSeries
from actintrack_app.media_capabilities import MetricId

METRIC_DISPLAY_TITLES = {
    MetricId.GENERAL_MOVEMENT: "General Movement",
    MetricId.OPTICAL_FLOW: "Optical Flow",
    MetricId.TOWARD_NUCLEUS: "Toward Nucleus",
    MetricId.ORIENTATION: "F-actin Orientation",
}

# Repeated on every CSV row so the file stays a single rectangular table.
PROVENANCE_HEADERS = (
    "Sample",
    "Condition Group",
    "Metric",
    "Analysis run",
)

_FILENAME_UNSAFE = re.compile(r"[^\w.\-]+", re.UNICODE)


def metric_display_name(metric_id: MetricId) -> str:
    return METRIC_DISPLAY_TITLES.get(metric_id, metric_id.value)


def serialize_measurement_value(value: Any) -> str:
    """Locale-independent text for one persisted cell.

    Integers stay integers. Floats use Python's round-trip ``repr``.
    ``None`` is an empty field. ``NaN`` is the explicit token ``nan``.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _serialize_float(value)
    if isinstance(value, str):
        return value
    item = getattr(value, "item", None)
    if callable(item):
        try:
            converted = item()
        except (TypeError, ValueError):
            converted = value
        else:
            if converted is not value and not isinstance(converted, type(value)):
                return serialize_measurement_value(converted)
    return str(value)


def _serialize_float(value: float) -> str:
    if math.isnan(value):
        return "nan"
    if math.isinf(value):
        return "inf" if value > 0 else "-inf"
    return repr(float(value))


def measurement_table(series: MetricMeasurementSeries) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    """Header and rows in persisted scientific order."""
    headers = tuple(column.label for column in series.columns)
    keys = [column.key for column in series.columns]
    rows = tuple(
        tuple(serialize_measurement_value(row.get(key)) for key in keys)
        for row in series.rows
    )
    return headers, rows


def provenance_values(series: MetricMeasurementSeries) -> tuple[str, ...]:
    sample = (series.sample_label or series.sample_id or "").strip()
    return (
        sample,
        str(series.condition_group or ""),
        metric_display_name(series.metric_id),
        str(series.analysis_run_id or ""),
    )


def csv_table(
    series: MetricMeasurementSeries,
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    """Rectangular CSV: provenance columns, then persisted measurement columns."""
    headers, rows = measurement_table(series)
    provenance = provenance_values(series)
    return (
        PROVENANCE_HEADERS + headers,
        tuple(provenance + row for row in rows),
    )


def _tsv_cell(text: str) -> str:
    return text.replace("\t", " ").replace("\r", " ").replace("\n", " ")


def measurements_to_tsv(series: MetricMeasurementSeries) -> str:
    """Tab-separated measurement table only, in persisted row order."""
    headers, rows = measurement_table(series)
    lines = ["\t".join(_tsv_cell(cell) for cell in headers)]
    lines.extend("\t".join(_tsv_cell(cell) for cell in row) for row in rows)
    return "\n".join(lines)


def measurements_to_csv(series: MetricMeasurementSeries) -> str:
    """UTF-8 CSV text with lightweight provenance columns."""
    headers, rows = csv_table(series)
    buffer = StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue()


def suggested_measurements_csv_name(series: MetricMeasurementSeries) -> str:
    sample = (series.sample_label or series.sample_id or "sample").strip() or "sample"
    metric = metric_display_name(series.metric_id)
    stem = _FILENAME_UNSAFE.sub("_", f"{sample}_{metric}_measurements")
    stem = stem.strip("._") or "measurements"
    return f"{stem}.csv"


def ensure_csv_extension(path: str) -> str:
    text = str(path).strip()
    if not text:
        return text
    if Path(text).suffix.lower() == ".csv":
        return text
    return text + ".csv"


def write_measurements_csv(series: MetricMeasurementSeries, path: str | Path) -> None:
    destination = Path(path)
    destination.write_text(measurements_to_csv(series), encoding="utf-8", newline="")
