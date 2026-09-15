"""Media-aware Run Metrics compute dispatch (no GUI dependency).

VIDEO → tracking + Optical Flow (+ Toward Nucleus when nucleus present)
IMAGE → structural F-actin Orientation only

Does not fabricate timing or synthesize frames for images.
Does not compute orientation on video samples.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np

from actintrack_app.media_capabilities import SampleMediaType
from actintrack_app.motion_index import MotionIndexParams
from actintrack_app.optical_flow_motion_index import (
    OpticalFlowResult,
    OpticalFlowSettings,
    build_optical_flow_fingerprint,
    compute_optical_flow_motion_index,
)
from actintrack_app.orientation import OrientationState, RectROI
from actintrack_app.preview_workflow import (
    CroppedPreviewAnalysis,
    analyze_cropped_preview,
    load_cropped_frame_from_image,
    load_cropped_frames_from_video,
)
from actintrack_app.structural_orientation import (
    StructuralOrientationResult,
    compute_structural_orientation,
)
from actintrack_app.timing_provenance import TimingMetadata, probe_video_playback_fps


@dataclass
class MetricsComputeResult:
    """Outcome of one Run Metrics dispatch for a sample."""

    status: str  # analyzed | error | unavailable
    analysis_run_id: str = ""
    media_type: SampleMediaType = SampleMediaType.VIDEO
    tracking: CroppedPreviewAnalysis | None = None
    optical_flow: OpticalFlowResult | None = None
    orientation: StructuralOrientationResult | None = None
    timing: TimingMetadata | None = None
    had_error: bool = False
    ok_any: bool = False
    error_messages: list[str] = field(default_factory=list)


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_video_metrics(
    *,
    path: Path,
    orientation: OrientationState,
    roi: RectROI,
    params: MotionIndexParams,
    of_settings: OpticalFlowSettings,
    valid_mask: np.ndarray | None,
    nucleus_xy_px: tuple[float, float] | None,
    sample_id: str,
    cutoff_y_crop_px: float | None = None,
) -> MetricsComputeResult:
    """Run motion pipelines for a VIDEO sample (no structural orientation)."""
    timing = TimingMetadata.from_video_header(probe_video_playback_fps(path))
    if timing is None or not timing.is_calibrated_analysis_ready:
        return MetricsComputeResult(
            status="unavailable",
            media_type=SampleMediaType.VIDEO,
            error_messages=["Valid video timing is required"],
        )

    run_id = _utc_run_id()
    result = MetricsComputeResult(
        status="analyzed",
        analysis_run_id=run_id,
        media_type=SampleMediaType.VIDEO,
        timing=timing,
    )
    try:
        frames = load_cropped_frames_from_video(path, orientation, roi)
    except Exception as exc:
        result.status = "error"
        result.had_error = True
        result.error_messages.append(str(exc))
        return result

    try:
        analysis = analyze_cropped_preview(
            frames,
            params=params,
            valid_mask=valid_mask,
            nucleus_xy_px=nucleus_xy_px,
        )
        analysis.analysis_run_id = run_id
        analysis.valid_mask = (
            None if valid_mask is None else np.array(valid_mask, copy=True)
        )
        if cutoff_y_crop_px is not None:
            analysis.cutoff_y_crop_px = float(cutoff_y_crop_px)
        result.tracking = analysis
        if analysis.num_tracks_with_valid_steps == 0:
            result.had_error = True
        else:
            result.ok_any = True
    except Exception as exc:
        result.had_error = True
        result.error_messages.append(str(exc))

    roi_bounds = (int(roi.x), int(roi.y), int(roi.width), int(roi.height))
    try:
        fingerprint = build_optical_flow_fingerprint(
            sample_id=sample_id,
            roi_bounds=roi_bounds,
            settings=of_settings,
            data_identity=str(path.resolve()),
            frame_count=len(frames),
            valid_mask=valid_mask,
        )
        of_result = compute_optical_flow_motion_index(
            frames,
            of_settings,
            sample_id=sample_id,
            data_identity=str(path.resolve()),
            roi_bounds=roi_bounds,
            fingerprint=fingerprint,
            valid_mask=valid_mask,
        )
        result.optical_flow = of_result
        if of_result.has_valid_result:
            result.ok_any = True
        else:
            result.had_error = True
    except Exception as exc:
        result.had_error = True
        result.error_messages.append(str(exc))

    if result.had_error and not result.ok_any:
        result.status = "error"
    return result


def compute_image_orientation_metrics(
    *,
    path: Path,
    orientation: OrientationState,
    roi: RectROI,
    valid_mask: np.ndarray | None,
    nucleus_xy_px: tuple[float, float] | None,
    sample_id: str,
) -> MetricsComputeResult:
    """Run structural orientation for an IMAGE sample (no motion pipelines)."""
    run_id = _utc_run_id()
    result = MetricsComputeResult(
        status="analyzed",
        analysis_run_id=run_id,
        media_type=SampleMediaType.IMAGE,
    )
    if nucleus_xy_px is None:
        result.status = "unavailable"
        result.had_error = True
        result.error_messages.append("Nucleus is required for F-actin Orientation")
        return result

    try:
        frame = load_cropped_frame_from_image(path, orientation, roi)
    except Exception as exc:
        result.status = "error"
        result.had_error = True
        result.error_messages.append(str(exc))
        return result

    try:
        orientation_result = compute_structural_orientation(
            frame,
            nucleus_xy_px=nucleus_xy_px,
            valid_mask=valid_mask,
            sample_id=sample_id,
            reference_frame_index=0,
        )
        result.orientation = orientation_result
        if orientation_result.has_valid_result:
            result.ok_any = True
        else:
            result.had_error = True
    except Exception as exc:
        result.had_error = True
        result.error_messages.append(str(exc))

    if result.had_error and not result.ok_any:
        result.status = "error"
    return result


def dispatch_metrics_compute(
    *,
    media_type: SampleMediaType,
    path: Path,
    orientation: OrientationState,
    roi: RectROI,
    params: MotionIndexParams,
    of_settings: OpticalFlowSettings,
    valid_mask: np.ndarray | None,
    nucleus_xy_px: tuple[float, float] | None,
    sample_id: str,
    cutoff_y_crop_px: float | None = None,
) -> MetricsComputeResult:
    if media_type is SampleMediaType.IMAGE:
        return compute_image_orientation_metrics(
            path=path,
            orientation=orientation,
            roi=roi,
            valid_mask=valid_mask,
            nucleus_xy_px=nucleus_xy_px,
            sample_id=sample_id,
        )
    return compute_video_metrics(
        path=path,
        orientation=orientation,
        roi=roi,
        params=params,
        of_settings=of_settings,
        valid_mask=valid_mask,
        nucleus_xy_px=nucleus_xy_px,
        sample_id=sample_id,
        cutoff_y_crop_px=cutoff_y_crop_px,
    )
