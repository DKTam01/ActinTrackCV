"""Load persisted contributing measurement series for Analysis inspection.

Does not recompute science. Rows come from the draft JSON written by the
analysis run that produced the displayed sample scalar.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np

from actintrack_app.media_capabilities import MetricId
from actintrack_app.metric_analysis_ui import draft_analysis_run_id
from actintrack_app.schema_compat import (
    resolve_draft_optical_flow_path,
    resolve_draft_structural_orientation_path,
    resolve_draft_tracking_path,
)


@dataclass(frozen=True)
class MeasurementColumn:
    key: str
    label: str
    sort_kind: str = "text"  # text | int | float
    header_tooltip: str = ""


@dataclass
class MetricMeasurementSeries:
    """Contributing observations for one sample-level metric from one run."""

    metric_id: MetricId
    sample_id: str
    sample_label: str
    condition_group: str
    analysis_run_id: str
    summary_value: Optional[float]
    summary_unit: str
    row_kind: str  # step | frame_pair | orientation_sample
    columns: list[MeasurementColumn]
    rows: list[dict[str, Any]] = field(default_factory=list)
    notes: tuple[str, ...] = ()
    available: bool = True
    unavailable_reason: str = ""

    @property
    def measurement_count(self) -> int:
        return len(self.rows)


def _read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def aggregate_general_movement_um_s(speeds: Sequence[float]) -> Optional[float]:
    """Existing GM sample statistic: unweighted mean of step speeds."""
    values = [float(v) for v in speeds]
    if not values:
        return None
    return float(np.mean(values))


def aggregate_toward_nucleus_um_s(
    delta_distance_um: Sequence[float],
    dt_s: Sequence[float],
) -> Optional[float]:
    """Existing Toward Nucleus sample statistic: time-weighted ΣΔd / Σdt."""
    total_d = 0.0
    total_t = 0.0
    for d, t in zip(delta_distance_um, dt_s):
        dt = float(t)
        if dt <= 0:
            continue
        total_d += float(d)
        total_t += dt
    if total_t <= 0:
        return None
    return total_d / total_t


def aggregate_optical_flow_um_s(
    pair_means_px: Sequence[float],
    *,
    microns_per_pixel: float,
    seconds_per_frame: float,
) -> Optional[float]:
    """Existing OF sample statistic: mean of frame-pair means, then µm/s."""
    values = [float(v) for v in pair_means_px]
    if not values or seconds_per_frame <= 0:
        return None
    mean_px = float(np.mean(values))
    return mean_px * float(microns_per_pixel) / float(seconds_per_frame)


def aggregate_orientation_median_deg(angles: Sequence[float]) -> Optional[float]:
    """Existing Orientation sample statistic: median of contributing angles."""
    values = [float(v) for v in angles]
    if not values:
        return None
    return float(np.median(values))


def load_general_movement_series(
    root: Path,
    sample_id: str,
    *,
    sample_label: str = "",
    condition_group: str = "",
) -> MetricMeasurementSeries:
    path = resolve_draft_tracking_path(root, sample_id)
    data = _read_json(path)
    if not data:
        return MetricMeasurementSeries(
            metric_id=MetricId.GENERAL_MOVEMENT,
            sample_id=sample_id,
            sample_label=sample_label,
            condition_group=condition_group,
            analysis_run_id="",
            summary_value=None,
            summary_unit="µm/s",
            row_kind="step",
            columns=[],
            available=False,
            unavailable_reason="No persisted tracking result",
        )
    rows: list[dict[str, Any]] = []
    tracking = data.get("tracking_result") or {}
    tracks = tracking.get("tracks") or []
    index = 0
    for track in tracks:
        track_id = track.get("track_id")
        for step in track.get("valid_steps") or []:
            index += 1
            dx = float(step.get("dx_px", 0.0) or 0.0)
            dy = float(step.get("dy_px", 0.0) or 0.0)
            gap = max(1, int(step.get("frame_gap", 1) or 1))
            px_per_frame = float(np.hypot(dx, dy)) / float(gap)
            rows.append(
                {
                    "n": index,
                    "track_id": track_id,
                    "prev_frame": step.get("prev_frame_index"),
                    "frame": step.get("frame_index"),
                    "px_per_frame": px_per_frame,
                    "um_per_s": step.get("absolute_velocity_um_per_s"),
                }
            )
    summary = data.get("general_movement_index_um_per_s")
    if summary is None:
        summary = data.get("absolute_velocity_index_um_per_s")
    return MetricMeasurementSeries(
        metric_id=MetricId.GENERAL_MOVEMENT,
        sample_id=sample_id,
        sample_label=sample_label,
        condition_group=condition_group,
        analysis_run_id=draft_analysis_run_id(data),
        summary_value=float(summary) if summary is not None else None,
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
        notes=("Each row is one valid track step contributing to the sample mean.",),
        available=bool(rows),
        unavailable_reason="" if rows else "No valid track steps",
    )


def load_toward_nucleus_series(
    root: Path,
    sample_id: str,
    *,
    sample_label: str = "",
    condition_group: str = "",
) -> MetricMeasurementSeries:
    path = resolve_draft_tracking_path(root, sample_id)
    data = _read_json(path)
    if not data or data.get("toward_nucleus_velocity_um_per_s") is None:
        return MetricMeasurementSeries(
            metric_id=MetricId.TOWARD_NUCLEUS,
            sample_id=sample_id,
            sample_label=sample_label,
            condition_group=condition_group,
            analysis_run_id=draft_analysis_run_id(data) if data else "",
            summary_value=None,
            summary_unit="µm/s",
            row_kind="step",
            columns=[],
            available=False,
            unavailable_reason="Toward Nucleus not available for this run",
        )
    rows: list[dict[str, Any]] = []
    tracking = data.get("tracking_result") or {}
    index = 0
    for track in tracking.get("tracks") or []:
        track_id = track.get("track_id")
        for step in track.get("valid_steps") or []:
            toward = step.get("toward_velocity_um_per_s")
            if toward is None:
                continue
            index += 1
            rows.append(
                {
                    "n": index,
                    "track_id": track_id,
                    "prev_frame": step.get("prev_frame_index"),
                    "frame": step.get("frame_index"),
                    "toward_um_s": toward,
                    "delta_distance_um": step.get("delta_distance_um"),
                    "dt_s": step.get("dt_s"),
                    "sign": (
                        "toward"
                        if float(toward) > 0
                        else ("away" if float(toward) < 0 else "none")
                    ),
                }
            )
    return MetricMeasurementSeries(
        metric_id=MetricId.TOWARD_NUCLEUS,
        sample_id=sample_id,
        sample_label=sample_label,
        condition_group=condition_group,
        analysis_run_id=draft_analysis_run_id(data),
        summary_value=float(data["toward_nucleus_velocity_um_per_s"]),
        summary_unit="µm/s",
        row_kind="step",
        columns=[
            MeasurementColumn("n", "Measurement #", sort_kind="int"),
            MeasurementColumn("track_id", "Track", sort_kind="int"),
            MeasurementColumn("prev_frame", "From frame", sort_kind="int"),
            MeasurementColumn("frame", "To frame", sort_kind="int"),
            MeasurementColumn("toward_um_s", "Toward velocity (µm/s)", sort_kind="float"),
            MeasurementColumn("sign", "Sign", sort_kind="text"),
            MeasurementColumn("delta_distance_um", "Δ distance (µm)", sort_kind="float"),
            MeasurementColumn("dt_s", "dt (s)", sort_kind="float"),
        ],
        rows=rows,
        notes=(
            "Positive = toward nucleus; negative = away.",
            "Sample result is time-weighted (ΣΔd / Σdt), not the step mean.",
        ),
        available=bool(rows),
        unavailable_reason="" if rows else "No nucleus-relative steps",
    )


def load_optical_flow_series(
    root: Path,
    sample_id: str,
    *,
    sample_label: str = "",
    condition_group: str = "",
) -> MetricMeasurementSeries:
    path = resolve_draft_optical_flow_path(root, sample_id)
    data = _read_json(path)
    if not data or not data.get("has_valid_result"):
        return MetricMeasurementSeries(
            metric_id=MetricId.OPTICAL_FLOW,
            sample_id=sample_id,
            sample_label=sample_label,
            condition_group=condition_group,
            analysis_run_id=draft_analysis_run_id(data) if data else "",
            summary_value=None,
            summary_unit="µm/s",
            row_kind="frame_pair",
            columns=[],
            available=False,
            unavailable_reason="No persisted Optical Flow result",
        )
    rows: list[dict[str, Any]] = []
    for index, pair in enumerate(data.get("frame_pair_summaries") or [], start=1):
        rows.append(
            {
                "n": index,
                "frame_a": pair.get("frame_a"),
                "frame_b": pair.get("frame_b"),
                "mean_px": pair.get("mean_magnitude_px_frame"),
                "valid_count": pair.get("valid_pixel_count"),
            }
        )
    settings = data.get("settings") or {}
    return MetricMeasurementSeries(
        metric_id=MetricId.OPTICAL_FLOW,
        sample_id=sample_id,
        sample_label=sample_label,
        condition_group=condition_group,
        analysis_run_id=draft_analysis_run_id(data),
        summary_value=(
            float(data["optical_flow_general_movement_um_s"])
            if data.get("optical_flow_general_movement_um_s") is not None
            else None
        ),
        summary_unit="µm/s",
        row_kind="frame_pair",
        columns=[
            MeasurementColumn("n", "Measurement #", sort_kind="int"),
            MeasurementColumn("frame_a", "Frame A", sort_kind="int"),
            MeasurementColumn("frame_b", "Frame B", sort_kind="int"),
            MeasurementColumn("mean_px", "Mean magnitude (px/frame)", sort_kind="float"),
            MeasurementColumn("valid_count", "Valid pixels", sort_kind="int"),
        ],
        rows=rows,
        notes=(
            "Each row is one frame-pair mean magnitude (not per-pixel vectors).",
            f"Sample µm/s uses mpp={settings.get('microns_per_pixel', '—')} "
            f"and s/frame={settings.get('seconds_per_frame', '—')}.",
        ),
        available=bool(rows),
        unavailable_reason="" if rows else "No frame-pair summaries",
    )


COHERENCE_HEADER_TOOLTIP = (
    "Coherence (0–1)\n\n"
    "Coherence is a 0–1 measure of how strongly the local image structure "
    "has one dominant orientation. Higher values mean a more clearly defined "
    "direction; lower values mean a less clearly defined direction. "
    "It is not accuracy, confidence that the angle is correct, or a "
    "radial/tangential score."
)


def load_orientation_series(
    root: Path,
    sample_id: str,
    *,
    sample_label: str = "",
    condition_group: str = "",
) -> MetricMeasurementSeries:
    path = resolve_draft_structural_orientation_path(root, sample_id)
    data = _read_json(path)
    if not data or not data.get("has_valid_result"):
        return MetricMeasurementSeries(
            metric_id=MetricId.ORIENTATION,
            sample_id=sample_id,
            sample_label=sample_label,
            condition_group=condition_group,
            analysis_run_id=draft_analysis_run_id(data) if data else "",
            summary_value=None,
            summary_unit="°",
            row_kind="orientation_sample",
            columns=[],
            available=False,
            unavailable_reason="No persisted F-actin Orientation result",
        )
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(data.get("measurements") or [], start=1):
        rows.append(
            {
                "n": index,
                "angle_deg": item.get("angle_relative_nucleus_deg"),
                "x_px": item.get("x_px"),
                "y_px": item.get("y_px"),
                "coherence": item.get("coherence"),
            }
        )
    return MetricMeasurementSeries(
        metric_id=MetricId.ORIENTATION,
        sample_id=sample_id,
        sample_label=sample_label,
        condition_group=condition_group,
        analysis_run_id=draft_analysis_run_id(data),
        summary_value=(
            float(data["median_angle_relative_nucleus_deg"])
            if data.get("median_angle_relative_nucleus_deg") is not None
            else None
        ),
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
        notes=(
            "0° = radial to the nucleus; 90° = tangential. "
            "Sample result is the median of these angles.",
        ),
        available=bool(rows),
        unavailable_reason="" if rows else "No orientation measurements",
    )


_LOADERS = {
    MetricId.GENERAL_MOVEMENT: load_general_movement_series,
    MetricId.TOWARD_NUCLEUS: load_toward_nucleus_series,
    MetricId.OPTICAL_FLOW: load_optical_flow_series,
    MetricId.ORIENTATION: load_orientation_series,
}


def load_metric_measurement_series(
    root: Path,
    sample_id: str,
    metric_id: MetricId,
    *,
    sample_label: str = "",
    condition_group: str = "",
) -> MetricMeasurementSeries:
    loader = _LOADERS[metric_id]
    return loader(
        root,
        sample_id,
        sample_label=sample_label,
        condition_group=condition_group,
    )


def verify_series_matches_summary(
    series: MetricMeasurementSeries,
    *,
    microns_per_pixel: float | None = None,
    seconds_per_frame: float | None = None,
) -> bool:
    """True when persisted rows reproduce the persisted summary (existing formulas)."""
    if not series.available or series.summary_value is None:
        return False
    if series.metric_id is MetricId.GENERAL_MOVEMENT:
        speeds = [float(r["um_per_s"]) for r in series.rows if r.get("um_per_s") is not None]
        agg = aggregate_general_movement_um_s(speeds)
    elif series.metric_id is MetricId.TOWARD_NUCLEUS:
        deltas = [
            float(r["delta_distance_um"])
            for r in series.rows
            if r.get("delta_distance_um") is not None
        ]
        dts = [float(r["dt_s"]) for r in series.rows if r.get("dt_s") is not None]
        agg = aggregate_toward_nucleus_um_s(deltas, dts)
    elif series.metric_id is MetricId.OPTICAL_FLOW:
        pair_means = [
            float(r["mean_px"]) for r in series.rows if r.get("mean_px") is not None
        ]
        if microns_per_pixel is None or seconds_per_frame is None:
            return False
        agg = aggregate_optical_flow_um_s(
            pair_means,
            microns_per_pixel=float(microns_per_pixel),
            seconds_per_frame=float(seconds_per_frame),
        )
    elif series.metric_id is MetricId.ORIENTATION:
        angles = [
            float(r["angle_deg"]) for r in series.rows if r.get("angle_deg") is not None
        ]
        agg = aggregate_orientation_median_deg(angles)
    else:
        return False
    if agg is None:
        return False
    return abs(float(agg) - float(series.summary_value)) <= max(
        1e-6, 1e-4 * abs(float(series.summary_value))
    )
