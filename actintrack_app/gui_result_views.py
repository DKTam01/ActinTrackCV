"""Display DTOs and formatting for sparse-tracking / orientation / optical-flow panels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from actintrack_app.optical_flow_motion_index import OpticalFlowResult
from actintrack_app.preview_workflow import CroppedPreviewAnalysis
from actintrack_app.timing_provenance import (
    implied_px_per_frame,
    timing_from_result_payload,
)


@dataclass
class SampleTrackingResultView:
    """Display-ready tracking/index values for one sample."""

    status: str  # success, failed, none
    downward_velocity: float = 0.0
    general_movement: float = 0.0
    general_movement_px_per_frame: Optional[float] = None
    tracks_used: int = 0
    tracks_requested: int = 0
    valid_steps: int = 0
    toward_nucleus_velocity: Optional[float] = None
    failure_reason: str = ""
    analysis_seconds_per_frame: Optional[float] = None
    timing_source: str = ""
    timing_confirmed: bool = False


@dataclass
class OpticalFlowResultView:
    """Display-ready optical-flow motion index values for one sample."""

    status: str  # success, failed, none
    general_movement: Optional[float] = None
    general_movement_px_per_frame: Optional[float] = None
    downward_motion: Optional[float] = None
    net_y_velocity: Optional[float] = None
    directionality_ratio: Optional[float] = None
    valid_pixel_fraction: Optional[float] = None
    saturated_pixel_fraction: Optional[float] = None
    failure_reason: str = ""
    analysis_seconds_per_frame: Optional[float] = None
    timing_source: str = ""
    timing_confirmed: bool = False


@dataclass
class StructuralOrientationResultView:
    status: str  # success, failed, none
    median_angle_deg: Optional[float] = None
    mean_angle_deg: Optional[float] = None
    measurement_count: int = 0
    mean_coherence: Optional[float] = None
    failure_reason: str = ""


def optional_gui_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_optional_float(value: Optional[float], *, places: int = 4) -> str:
    if value is None:
        return "—"
    return f"{value:.{places}f}"


def is_tracking_failed(analysis: CroppedPreviewAnalysis) -> bool:
    return analysis.num_tracks_with_valid_steps == 0


def _timing_fields_from_payload(data: dict[str, Any]) -> tuple[Optional[float], str, bool]:
    timing = timing_from_result_payload(data)
    if timing is not None:
        return (
            timing.analysis_seconds_per_frame,
            timing.timing_source,
            timing.confirmed,
        )
    params = data.get("parameters") or data.get("settings") or {}
    if isinstance(params, dict) and params.get("seconds_per_frame") is not None:
        try:
            return float(params["seconds_per_frame"]), "legacy_default", False
        except (TypeError, ValueError):
            pass
    return None, "", False


def _sparse_px_from_payload(data: dict[str, Any], general_movement: float) -> Optional[float]:
    tracking = data.get("tracking_result") or {}
    summary = tracking.get("summary") if isinstance(tracking, dict) else None
    if isinstance(summary, dict):
        px = optional_gui_float(summary.get("mean_displacement_px_per_frame"))
        if px is not None:
            return px
    px = optional_gui_float(data.get("mean_displacement_px_per_frame"))
    if px is not None:
        return px
    spf, _, _ = _timing_fields_from_payload(data)
    params = data.get("parameters") or {}
    mpp = optional_gui_float(
        params.get("microns_per_pixel") if isinstance(params, dict) else None
    )
    if spf is None or mpp is None or mpp <= 0:
        return None
    try:
        return implied_px_per_frame(
            general_movement, seconds_per_frame=spf, microns_per_pixel=mpp
        )
    except ValueError:
        return None


def tracking_result_view_from_dict(data: dict[str, Any]) -> SampleTrackingResultView:
    tracks_used = int(data.get("num_tracks_with_valid_steps", 0) or 0)
    tracks_started = int(
        data.get("num_tracks_started", data.get("num_tracks_requested", tracks_used))
        or 0
    )
    spf, source, confirmed = _timing_fields_from_payload(data)
    if tracks_used <= 0:
        reason = str(
            data.get("tracking_warning")
            or data.get("track_preview_error")
            or data.get("failure_reason")
            or ""
        ).strip()
        return SampleTrackingResultView(
            status="failed",
            failure_reason=reason,
            analysis_seconds_per_frame=spf,
            timing_source=source,
            timing_confirmed=confirmed,
        )
    general = float(
        data.get(
            "absolute_velocity_index_um_per_s",
            data.get("general_movement_index_um_per_s", 0.0),
        )
    )
    return SampleTrackingResultView(
        status="success",
        downward_velocity=float(data.get("downward_velocity_index_um_per_s", 0.0)),
        general_movement=general,
        general_movement_px_per_frame=_sparse_px_from_payload(data, general),
        tracks_used=tracks_used,
        tracks_requested=max(tracks_started, tracks_used),
        valid_steps=int(data.get("total_valid_steps", 0) or 0),
        toward_nucleus_velocity=optional_gui_float(
            data.get("toward_nucleus_velocity_um_per_s")
        ),
        analysis_seconds_per_frame=spf,
        timing_source=source,
        timing_confirmed=confirmed,
    )


def tracking_result_view_from_preview(
    analysis: CroppedPreviewAnalysis,
    *,
    timing_confirmed: bool = False,
    timing_source: str = "",
) -> SampleTrackingResultView:
    if is_tracking_failed(analysis):
        return SampleTrackingResultView(
            status="failed",
            failure_reason=analysis.tracking_warning,
            timing_confirmed=timing_confirmed,
            timing_source=timing_source,
        )
    requested = len(analysis.starting_points)
    spf = None
    mpp = None
    if analysis.params is not None:
        requested = max(requested, analysis.params.num_starting_points)
        spf = float(analysis.params.seconds_per_frame)
        mpp = float(analysis.params.microns_per_pixel)
    px = None
    if spf is not None and mpp is not None and mpp > 0:
        try:
            px = implied_px_per_frame(
                analysis.general_movement_index_um_per_s,
                seconds_per_frame=spf,
                microns_per_pixel=mpp,
            )
        except ValueError:
            px = None
    return SampleTrackingResultView(
        status="success",
        downward_velocity=analysis.downward_velocity_index_um_per_s,
        general_movement=analysis.general_movement_index_um_per_s,
        general_movement_px_per_frame=px,
        tracks_used=analysis.num_tracks_with_valid_steps,
        tracks_requested=max(requested, analysis.num_tracks_started),
        valid_steps=analysis.total_valid_steps,
        toward_nucleus_velocity=analysis.toward_nucleus_velocity_um_per_s,
        analysis_seconds_per_frame=spf,
        timing_source=timing_source,
        timing_confirmed=timing_confirmed,
    )


def optical_flow_result_view_from_dict(data: dict[str, Any]) -> OpticalFlowResultView:
    spf, source, confirmed = _timing_fields_from_payload(data)
    if not data.get("has_valid_result"):
        reason = str(data.get("failure_reason", "")).strip()
        return OpticalFlowResultView(
            status="failed",
            failure_reason=reason,
            analysis_seconds_per_frame=spf,
            timing_source=source,
            timing_confirmed=confirmed,
        )
    return OpticalFlowResultView(
        status="success",
        general_movement=optional_gui_float(data.get("optical_flow_general_movement_um_s")),
        general_movement_px_per_frame=optional_gui_float(
            data.get("mean_magnitude_px_frame")
        ),
        downward_motion=optional_gui_float(data.get("optical_flow_downward_motion_um_s")),
        net_y_velocity=optional_gui_float(data.get("optical_flow_net_y_velocity_um_s")),
        directionality_ratio=optional_gui_float(data.get("optical_flow_directionality_ratio")),
        valid_pixel_fraction=optional_gui_float(data.get("optical_flow_valid_pixel_fraction")),
        saturated_pixel_fraction=optional_gui_float(
            data.get("optical_flow_saturated_pixel_fraction")
        ),
        analysis_seconds_per_frame=spf,
        timing_source=source,
        timing_confirmed=confirmed,
    )


def optical_flow_result_view_from_result(
    result: OpticalFlowResult,
    *,
    timing_confirmed: bool = False,
    timing_source: str = "",
) -> OpticalFlowResultView:
    if not result.has_valid_result:
        return OpticalFlowResultView(
            status="failed",
            failure_reason=result.failure_reason,
            timing_confirmed=timing_confirmed,
            timing_source=timing_source,
        )
    spf = None
    if result.settings is not None:
        spf = float(result.settings.seconds_per_frame)
    return OpticalFlowResultView(
        status="success",
        general_movement=result.optical_flow_general_movement_um_s,
        general_movement_px_per_frame=result.mean_magnitude_px_frame,
        downward_motion=result.optical_flow_downward_motion_um_s,
        net_y_velocity=result.optical_flow_net_y_velocity_um_s,
        directionality_ratio=result.optical_flow_directionality_ratio,
        valid_pixel_fraction=result.optical_flow_valid_pixel_fraction,
        saturated_pixel_fraction=result.optical_flow_saturated_pixel_fraction,
        analysis_seconds_per_frame=spf,
        timing_source=timing_source,
        timing_confirmed=timing_confirmed,
    )


def structural_orientation_view_from_dict(
    data: dict[str, Any],
) -> StructuralOrientationResultView:
    if not data.get("has_valid_result"):
        return StructuralOrientationResultView(
            status="failed",
            failure_reason=str(data.get("failure_reason", "")).strip(),
        )
    return StructuralOrientationResultView(
        status="success",
        median_angle_deg=optional_gui_float(
            data.get("median_angle_relative_nucleus_deg")
        ),
        mean_angle_deg=optional_gui_float(
            data.get("mean_angle_relative_nucleus_deg")
        ),
        measurement_count=int(data.get("measurement_count", 0) or 0),
        mean_coherence=optional_gui_float(data.get("mean_coherence")),
    )


def _calibrated_velocity_lines(
    *,
    label: str,
    um_s: Optional[float],
    px_frame: Optional[float],
    timing_confirmed: bool,
) -> list[str]:
    lines = [
        f"General Movement: {fmt_optional_float(px_frame)} px/frame",
        f"Calibrated Velocity: {fmt_optional_float(um_s)} µm/s",
    ]
    if um_s is not None and not timing_confirmed:
        lines.append("Timing unconfirmed")
    if label:
        pass
    return lines


def format_tracking_result_panel_lines(
    template_view: Optional[SampleTrackingResultView],
    optical_flow_view: Optional[OpticalFlowResultView],
    *,
    structural_orientation_view: Optional[
        StructuralOrientationResultView
    ] = None,
    template_stale: bool = False,
    optical_flow_stale: bool = False,
    optical_flow_qc_status: str,
    optical_flow_frame_pair_count: str,
) -> str:
    lines: list[str] = []

    lines.append("Sparse Tracking")
    if template_stale:
        lines.append("May not match current settings.")
    elif template_view is None or template_view.status == "none":
        lines.append("Not generated yet")
    elif template_view.status == "failed":
        lines.append("Failed")
        if template_view.failure_reason:
            lines.append(template_view.failure_reason)
    else:
        tracks_line = f"Tracks Used: {template_view.tracks_used}"
        if template_view.tracks_requested > template_view.tracks_used:
            tracks_line = (
                f"Tracks Used: {template_view.tracks_used} / "
                f"{template_view.tracks_requested}"
            )
        lines.extend(
            _calibrated_velocity_lines(
                label="sparse",
                um_s=template_view.general_movement,
                px_frame=template_view.general_movement_px_per_frame,
                timing_confirmed=template_view.timing_confirmed,
            )
        )
        if template_view.toward_nucleus_velocity is not None:
            lines.append(
                "Toward Nucleus: "
                f"{template_view.toward_nucleus_velocity:.4f} µm/s "
                "(signed)"
            )
        lines.extend(
            [
                "Legacy Downward Velocity: "
                f"{template_view.downward_velocity:.4f} µm/s",
                tracks_line,
                f"Valid Steps: {template_view.valid_steps}",
            ]
        )

    lines.append("")
    lines.append("F-actin Orientation Relative to Nucleus")
    if (
        structural_orientation_view is None
        or structural_orientation_view.status == "none"
    ):
        lines.append("Not generated yet")
    elif structural_orientation_view.status == "failed":
        lines.append("Not available")
        if structural_orientation_view.failure_reason:
            lines.append(structural_orientation_view.failure_reason)
    else:
        lines.extend(
            [
                "Median Structural Angle: "
                f"{fmt_optional_float(structural_orientation_view.median_angle_deg, places=2)}° "
                "(0–90°; 0=radial to nucleus)",
                f"Local Measurements: {structural_orientation_view.measurement_count}",
                "Mean Coherence: "
                f"{fmt_optional_float(structural_orientation_view.mean_coherence, places=3)}",
            ]
        )

    lines.append("")
    lines.append("Optical Flow")
    lines.append(f"Status: {optical_flow_qc_status}")
    if optical_flow_stale:
        lines.append("May not match current settings.")
    elif optical_flow_view is None or optical_flow_view.status == "none":
        if optical_flow_qc_status == "Not computed":
            lines.append("Not generated yet")
    elif optical_flow_view.status == "failed":
        lines.append("Failed")
        if optical_flow_view.failure_reason:
            lines.append(optical_flow_view.failure_reason)
    else:
        lines.append(f"Frame pairs used: {optical_flow_frame_pair_count}")
        lines.extend(
            _calibrated_velocity_lines(
                label="of",
                um_s=optical_flow_view.general_movement,
                px_frame=optical_flow_view.general_movement_px_per_frame,
                timing_confirmed=optical_flow_view.timing_confirmed,
            )
        )
        lines.extend(
            [
                "Legacy Downward Motion: "
                f"{fmt_optional_float(optical_flow_view.downward_motion)} µm/s",
                "Legacy Net Y Velocity: "
                f"{fmt_optional_float(optical_flow_view.net_y_velocity)} µm/s",
                f"Directionality Ratio: {fmt_optional_float(optical_flow_view.directionality_ratio)}",
                f"Valid Pixel Fraction: {fmt_optional_float(optical_flow_view.valid_pixel_fraction)}",
            ]
        )
        if optical_flow_view.saturated_pixel_fraction is not None:
            lines.append(
                "Saturated Pixel Fraction: "
                f"{fmt_optional_float(optical_flow_view.saturated_pixel_fraction)}"
            )

    return "\n".join(lines)
