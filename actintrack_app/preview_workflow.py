"""In-app cropped ROI preview and draft motion-index analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from actintrack_app.motion_index import (
    MotionIndexParams,
    PointTrack,
    compute_motion_indices,
    compute_nucleus_relative_summary,
    compute_track_statistics,
    compute_velocity_summary,
    point_tracks_from_video_result,
    render_track_preview_frame,
    select_starting_points,
    track_points,
)
from actintrack_app.orientation import OrientationState, RectROI, apply_orientation, crop_rect_roi
from actintrack_app.utils import VIDEO_EXTENSIONS
from actintrack_app.video_processing import MediaLoadError, load_media_frame


@dataclass
class CroppedPreviewAnalysis:
    frames: list[np.ndarray]
    tracks: list[PointTrack]
    starting_points: list[tuple[float, float]]
    downward_velocity_index_um_per_s: float
    general_movement_index_um_per_s: float
    num_tracks_with_valid_steps: int
    total_valid_steps: int
    mean_track_length_frames: float
    time_weighted_mean_speed_um_per_s: float = 0.0
    signed_vertical_velocity_um_per_s: float = 0.0
    downward_velocity_contribution_um_per_s: float = 0.0
    tracking_warning: str = ""
    params: MotionIndexParams | None = None
    nucleus_reference_xy_px: tuple[float, float] | None = None
    mean_step_toward_nucleus_velocity_um_per_s: float | None = None
    toward_nucleus_velocity_um_per_s: float | None = None
    toward_nucleus_motion_contribution_um_per_s: float | None = None
    analysis_run_id: str = ""
    cutoff_y_crop_px: float | None = None
    valid_mask: np.ndarray | None = field(default=None, compare=False, repr=False)

    @property
    def num_tracks_started(self) -> int:
        return len(self.tracks)


@dataclass
class MetricAnalysisInspectionSession:
    """Inspection-only binding of Metric Analysis to one persisted run."""

    sample_id: str
    run_id: str
    analysis: CroppedPreviewAnalysis
    nucleus_xy_crop: tuple[float, float] | None
    cutoff_y_crop: float | None
    valid_mask: np.ndarray | None
    orientation_run_id: str | None = None
    view_bounds: tuple[int, int, int, int] | None = None


def load_cropped_frames_from_video(
    video_path: Path,
    orientation: OrientationState,
    roi_oriented: RectROI,
) -> list[np.ndarray]:
    """Load all frames from a video, orient, and crop to the ROI."""
    path = Path(video_path)
    if path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise MediaLoadError(
            "Only AVI and MP4 data files are supported in the current 2D workflow."
        )

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        raise MediaLoadError(f"Cannot open data file: {path}")

    frames: list[np.ndarray] = []
    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            oriented = apply_orientation(frame, orientation)
            cropped = crop_rect_roi(oriented, roi_oriented)
            frames.append(cropped)
    finally:
        cap.release()

    if len(frames) < 2:
        raise MediaLoadError(
            "Data file must contain at least 2 readable frames for preview."
        )
    return frames


def analyze_cropped_preview(
    frames: list[np.ndarray],
    *,
    params: MotionIndexParams | None = None,
    valid_mask: np.ndarray | None = None,
    nucleus_xy_px: tuple[float, float] | None = None,
) -> CroppedPreviewAnalysis:
    """Run draft motion-index tracking on in-memory cropped frames."""
    params = params or MotionIndexParams()
    if len(frames) < 2:
        raise ValueError("Need at least 2 cropped frames for tracking preview.")

    warning = ""
    try:
        starting_points = select_starting_points(
            frames[0], params, valid_mask=valid_mask
        )
    except ValueError as exc:
        return CroppedPreviewAnalysis(
            frames=frames,
            tracks=[],
            starting_points=[],
            downward_velocity_index_um_per_s=0.0,
            general_movement_index_um_per_s=0.0,
            num_tracks_with_valid_steps=0,
            total_valid_steps=0,
            mean_track_length_frames=0.0,
            tracking_warning=str(exc),
            params=params,
        )

    if not starting_points:
        return CroppedPreviewAnalysis(
            frames=frames,
            tracks=[],
            starting_points=[],
            downward_velocity_index_um_per_s=0.0,
            general_movement_index_um_per_s=0.0,
            num_tracks_with_valid_steps=0,
            total_valid_steps=0,
            mean_track_length_frames=0.0,
            tracking_warning="No starting points inside the scientific validity domain.",
            params=params,
        )

    if len(starting_points) < params.num_starting_points:
        warning = (
            f"Only {len(starting_points)} starting point(s) found "
            f"(requested {params.num_starting_points})."
        )

    try:
        tracks = track_points(
            frames, starting_points, params, valid_mask=valid_mask
        )
    except ValueError as exc:
        return CroppedPreviewAnalysis(
            frames=frames,
            tracks=[],
            starting_points=starting_points,
            downward_velocity_index_um_per_s=0.0,
            general_movement_index_um_per_s=0.0,
            num_tracks_with_valid_steps=0,
            total_valid_steps=0,
            mean_track_length_frames=0.0,
            tracking_warning=str(exc),
            params=params,
        )

    valid_tracks, total_steps, mean_len = compute_track_statistics(tracks)
    if valid_tracks == 0:
        return CroppedPreviewAnalysis(
            frames=frames,
            tracks=tracks,
            starting_points=starting_points,
            downward_velocity_index_um_per_s=0.0,
            general_movement_index_um_per_s=0.0,
            num_tracks_with_valid_steps=0,
            total_valid_steps=0,
            mean_track_length_frames=0.0,
            tracking_warning=(
                warning or "Tracking failed or too few points survived. "
                "Adjust ROI or tracking settings."
            ),
            params=params,
        )

    downward, general, _ = compute_motion_indices(tracks, params)
    velocity_summary = compute_velocity_summary(tracks, params)
    nucleus_summary = (
        compute_nucleus_relative_summary(tracks, params, nucleus_xy_px)
        if nucleus_xy_px is not None
        else None
    )
    return CroppedPreviewAnalysis(
        frames=frames,
        tracks=tracks,
        starting_points=starting_points,
        downward_velocity_index_um_per_s=downward,
        general_movement_index_um_per_s=general,
        num_tracks_with_valid_steps=valid_tracks,
        total_valid_steps=total_steps,
        mean_track_length_frames=mean_len,
        time_weighted_mean_speed_um_per_s=(
            velocity_summary.time_weighted_mean_speed_um_per_s
        ),
        signed_vertical_velocity_um_per_s=(
            velocity_summary.signed_vertical_velocity_um_per_s
        ),
        downward_velocity_contribution_um_per_s=(
            velocity_summary.downward_velocity_contribution_um_per_s
        ),
        tracking_warning=warning,
        params=params,
        nucleus_reference_xy_px=nucleus_xy_px,
        mean_step_toward_nucleus_velocity_um_per_s=(
            nucleus_summary.mean_step_toward_velocity_um_per_s
            if nucleus_summary is not None
            else None
        ),
        toward_nucleus_velocity_um_per_s=(
            nucleus_summary.time_weighted_toward_velocity_um_per_s
            if nucleus_summary is not None
            else None
        ),
        toward_nucleus_motion_contribution_um_per_s=(
            nucleus_summary.toward_motion_contribution_um_per_s
            if nucleus_summary is not None
            else None
        ),
    )


def cropped_preview_analysis_from_draft(
    frames: list[np.ndarray],
    draft: dict[str, Any],
) -> CroppedPreviewAnalysis:
    """Build a display-only cropped preview from persisted draft metrics."""
    params_data = draft.get("parameters")
    params: MotionIndexParams | None = None
    if isinstance(params_data, dict):
        try:
            params = MotionIndexParams(**params_data)
        except (TypeError, ValueError):
            params = None
    tracks = point_tracks_from_video_result(draft)
    starting_points = [
        (float(track.points[0].x), float(track.points[0].y))
        for track in tracks
        if track.points
    ]
    general = float(
        draft.get(
            "general_movement_index_um_per_s",
            draft.get("absolute_velocity_index_um_per_s", 0.0),
        )
        or 0.0
    )
    nucleus_payload = draft.get("nucleus_reference")
    nucleus_xy_px: tuple[float, float] | None = None
    if isinstance(nucleus_payload, dict):
        try:
            nucleus_xy_px = (
                float(nucleus_payload["x_px"]),
                float(nucleus_payload["y_px"]),
            )
        except (KeyError, TypeError, ValueError):
            nucleus_xy_px = None
    cutoff_y_crop_px: float | None = None
    cutoff_payload = draft.get("cutoff_boundary")
    if isinstance(cutoff_payload, dict) and cutoff_payload.get("y_px") is not None:
        try:
            cutoff_y_crop_px = float(cutoff_payload["y_px"])
        except (TypeError, ValueError):
            cutoff_y_crop_px = None
    run_id = str(
        draft.get("analysis_run_id") or draft.get("analysis_timestamp_utc") or ""
    )
    return CroppedPreviewAnalysis(
        frames=frames,
        tracks=tracks,
        starting_points=starting_points,
        downward_velocity_index_um_per_s=float(
            draft.get("downward_velocity_index_um_per_s", 0.0) or 0.0
        ),
        general_movement_index_um_per_s=general,
        num_tracks_with_valid_steps=int(
            draft.get("num_tracks_with_valid_steps", 0) or 0
        ),
        total_valid_steps=int(draft.get("total_valid_steps", 0) or 0),
        mean_track_length_frames=(
            float(np.mean([len(track.points) for track in tracks]))
            if tracks
            else 0.0
        ),
        time_weighted_mean_speed_um_per_s=float(
            draft.get("time_weighted_mean_speed_um_per_s", 0.0) or 0.0
        ),
        signed_vertical_velocity_um_per_s=float(
            draft.get("signed_vertical_velocity_um_per_s", 0.0) or 0.0
        ),
        downward_velocity_contribution_um_per_s=float(
            draft.get("downward_velocity_contribution_um_per_s", 0.0) or 0.0
        ),
        tracking_warning=str(draft.get("tracking_warning", "") or ""),
        params=params,
        nucleus_reference_xy_px=nucleus_xy_px,
        mean_step_toward_nucleus_velocity_um_per_s=(
            float(draft["mean_step_toward_nucleus_velocity_um_per_s"])
            if draft.get("mean_step_toward_nucleus_velocity_um_per_s") is not None
            else None
        ),
        toward_nucleus_velocity_um_per_s=(
            float(draft["toward_nucleus_velocity_um_per_s"])
            if draft.get("toward_nucleus_velocity_um_per_s") is not None
            else None
        ),
        toward_nucleus_motion_contribution_um_per_s=(
            float(draft["toward_nucleus_motion_contribution_um_per_s"])
            if draft.get("toward_nucleus_motion_contribution_um_per_s") is not None
            else None
        ),
        analysis_run_id=run_id,
        cutoff_y_crop_px=cutoff_y_crop_px,
    )


def cropped_preview_analysis_from_frames(
    frames: list[np.ndarray],
) -> CroppedPreviewAnalysis:
    """Build a frame-only cropped preview when only optical-flow drafts exist."""
    return CroppedPreviewAnalysis(
        frames=frames,
        tracks=[],
        starting_points=[],
        downward_velocity_index_um_per_s=0.0,
        general_movement_index_um_per_s=0.0,
        num_tracks_with_valid_steps=0,
        total_valid_steps=0,
        mean_track_length_frames=0.0,
    )


def render_cropped_tracking_frame(
    analysis: CroppedPreviewAnalysis,
    frame_index: int,
) -> np.ndarray:
    """Return one cropped ROI frame with optional tracking overlay."""
    index = max(0, min(frame_index, len(analysis.frames) - 1))
    frame = analysis.frames[index]
    if not analysis.tracks:
        return frame.copy()
    return render_track_preview_frame(frame, analysis.tracks, index)


def draw_metric_analysis_guides(
    frame: np.ndarray,
    *,
    nucleus_xy: tuple[float, float] | None = None,
    cutoff_y: float | None = None,
    valid_mask: np.ndarray | None = None,
    draw_nucleus: bool = True,
    draw_domain_contour: bool = True,
) -> np.ndarray:
    """Bake crop-local inspection guides into a Metric Analysis frame.

    Display-only. Does not alter persisted coordinates or metric values.
    """
    if frame.ndim == 2:
        output = cv2.cvtColor(frame.astype(np.uint8), cv2.COLOR_GRAY2BGR)
    else:
        output = np.array(frame, copy=True)
    height, width = output.shape[:2]
    if (
        draw_domain_contour
        and valid_mask is not None
        and tuple(valid_mask.shape[:2]) == (height, width)
    ):
        contours, _ = cv2.findContours(
            np.asarray(valid_mask, dtype=np.uint8),
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        if contours:
            cv2.drawContours(output, contours, -1, (220, 200, 60), 1)
    if cutoff_y is not None:
        y = int(round(float(cutoff_y)))
        if 0 <= y < height:
            cv2.line(output, (0, y), (width - 1, y), (70, 150, 230), 2, cv2.LINE_AA)
    if draw_nucleus and nucleus_xy is not None:
        nx, ny = (int(round(value)) for value in nucleus_xy)
        if 0 <= nx < width and 0 <= ny < height:
            cv2.drawMarker(
                output,
                (nx, ny),
                (255, 90, 160),
                cv2.MARKER_CROSS,
                12,
                2,
                cv2.LINE_AA,
            )
            cv2.circle(output, (nx, ny), 5, (255, 90, 160), 1, cv2.LINE_AA)
    return output


def is_supported_video_path(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def probe_video_frame_count(path: Path) -> int:
    _, _, total = load_media_frame(path, 0)
    return max(1, total)
