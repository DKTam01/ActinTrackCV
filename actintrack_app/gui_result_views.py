"""Display DTOs and formatting for template-tracking / optical-flow result panels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from actintrack_app.optical_flow_motion_index import OpticalFlowResult
from actintrack_app.preview_workflow import CroppedPreviewAnalysis


@dataclass
class SampleTrackingResultView:
    """Display-ready tracking/index values for one sample."""

    status: str  # success, failed, none
    downward_velocity: float = 0.0
    general_movement: float = 0.0
    tracks_used: int = 0
    tracks_requested: int = 0
    valid_steps: int = 0
    failure_reason: str = ""


@dataclass
class OpticalFlowResultView:
    """Display-ready optical-flow motion index values for one sample."""

    status: str  # success, failed, none
    general_movement: Optional[float] = None
    downward_motion: Optional[float] = None
    net_y_velocity: Optional[float] = None
    directionality_ratio: Optional[float] = None
    valid_pixel_fraction: Optional[float] = None
    saturated_pixel_fraction: Optional[float] = None
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


def tracking_result_view_from_dict(data: dict[str, Any]) -> SampleTrackingResultView:
    tracks_used = int(data.get("num_tracks_with_valid_steps", 0) or 0)
    tracks_started = int(
        data.get("num_tracks_started", data.get("num_tracks_requested", tracks_used))
        or 0
    )
    if tracks_used <= 0:
        reason = str(
            data.get("tracking_warning")
            or data.get("track_preview_error")
            or data.get("failure_reason")
            or ""
        ).strip()
        return SampleTrackingResultView(status="failed", failure_reason=reason)
    return SampleTrackingResultView(
        status="success",
        downward_velocity=float(data.get("downward_velocity_index_um_per_s", 0.0)),
        general_movement=float(
            data.get(
                "absolute_velocity_index_um_per_s",
                data.get("general_movement_index_um_per_s", 0.0),
            )
        ),
        tracks_used=tracks_used,
        tracks_requested=max(tracks_started, tracks_used),
        valid_steps=int(data.get("total_valid_steps", 0) or 0),
    )


def tracking_result_view_from_preview(
    analysis: CroppedPreviewAnalysis,
) -> SampleTrackingResultView:
    if is_tracking_failed(analysis):
        return SampleTrackingResultView(
            status="failed",
            failure_reason=analysis.tracking_warning,
        )
    requested = len(analysis.starting_points)
    if analysis.params is not None:
        requested = max(requested, analysis.params.num_starting_points)
    return SampleTrackingResultView(
        status="success",
        downward_velocity=analysis.downward_velocity_index_um_per_s,
        general_movement=analysis.general_movement_index_um_per_s,
        tracks_used=analysis.num_tracks_with_valid_steps,
        tracks_requested=max(requested, analysis.num_tracks_started),
        valid_steps=analysis.total_valid_steps,
    )


def optical_flow_result_view_from_dict(data: dict[str, Any]) -> OpticalFlowResultView:
    if not data.get("has_valid_result"):
        reason = str(data.get("failure_reason", "")).strip()
        return OpticalFlowResultView(status="failed", failure_reason=reason)
    return OpticalFlowResultView(
        status="success",
        general_movement=optional_gui_float(data.get("optical_flow_general_movement_um_s")),
        downward_motion=optional_gui_float(data.get("optical_flow_downward_motion_um_s")),
        net_y_velocity=optional_gui_float(data.get("optical_flow_net_y_velocity_um_s")),
        directionality_ratio=optional_gui_float(data.get("optical_flow_directionality_ratio")),
        valid_pixel_fraction=optional_gui_float(data.get("optical_flow_valid_pixel_fraction")),
        saturated_pixel_fraction=optional_gui_float(
            data.get("optical_flow_saturated_pixel_fraction")
        ),
    )


def optical_flow_result_view_from_result(
    result: OpticalFlowResult,
) -> OpticalFlowResultView:
    if not result.has_valid_result:
        return OpticalFlowResultView(
            status="failed",
            failure_reason=result.failure_reason,
        )
    return OpticalFlowResultView(
        status="success",
        general_movement=result.optical_flow_general_movement_um_s,
        downward_motion=result.optical_flow_downward_motion_um_s,
        net_y_velocity=result.optical_flow_net_y_velocity_um_s,
        directionality_ratio=result.optical_flow_directionality_ratio,
        valid_pixel_fraction=result.optical_flow_valid_pixel_fraction,
        saturated_pixel_fraction=result.optical_flow_saturated_pixel_fraction,
    )


def format_tracking_result_panel_lines(
    template_view: Optional[SampleTrackingResultView],
    optical_flow_view: Optional[OpticalFlowResultView],
    *,
    template_stale: bool = False,
    optical_flow_stale: bool = False,
    optical_flow_qc_status: str,
    optical_flow_frame_pair_count: str,
) -> str:
    lines: list[str] = []

    lines.append("Template Tracking Motion Index")
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
            [
                f"Absolute Velocity: {template_view.general_movement:.4f} µm/s",
                f"Downward Velocity: {template_view.downward_velocity:.4f} µm/s",
                tracks_line,
                f"Valid Steps: {template_view.valid_steps}",
            ]
        )

    lines.append("")
    lines.append("Optical Flow Motion Index (Draft)")
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
        lines.extend(
            [
                f"Frame pairs used: {optical_flow_frame_pair_count}",
                f"General Movement: {fmt_optional_float(optical_flow_view.general_movement)} µm/s",
                f"Downward Motion: {fmt_optional_float(optical_flow_view.downward_motion)} µm/s",
                f"Net Y Velocity: {fmt_optional_float(optical_flow_view.net_y_velocity)} µm/s",
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
