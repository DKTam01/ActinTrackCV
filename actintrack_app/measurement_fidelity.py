"""V1 measurement-fidelity audit helpers.

Pure diagnostics for comparing sparse point tracking and Optical Flow on
identical frames. Does not tune thresholds or apply correction multipliers.
"""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

import cv2
import numpy as np

from actintrack_app.motion_index import (
    DEFAULT_MICRONS_PER_PIXEL,
    DEFAULT_SECONDS_PER_FRAME,
    METRIC_DEFINITION_VERSION,
    MOVEMENT_OUTPUT_SCHEMA_VERSION,
    MotionIndexParams,
    PointTrack,
    StepMetrics,
    TRACKING_METHOD_BRIGHTEST_LOCAL,
    TRACKING_METHOD_TEMPLATE,
    compute_motion_indices,
    compute_track_statistics,
    compute_velocity_summary,
    iter_track_step_metrics,
    select_starting_points,
    track_points,
)
from actintrack_app.optical_flow_motion_index import (
    OpticalFlowSettings,
    compute_optical_flow_motion_index,
)
from actintrack_app.orientation import OrientationState, RectROI
from actintrack_app.preview_workflow import load_cropped_frames_from_video

CANDIDATE_SECONDS_PER_FRAME = (
    ("stored_or_run", None),
    ("historical_default_0p2", 0.2),
    ("container_playback_6fps", 1.0 / 6.0),
    ("documented_hypothesis_30", 30.0),
)

# Historical group summaries reported by researchers (provenance only).
HISTORICAL_GROUP_SANITY = {
    "2_WT_550": {
        "general_movement": 9.5861,
        "optical_flow_general_movement": 6.2972,
    },
    "3_Mutant_515": {
        "general_movement": 6.0534,
        "optical_flow_general_movement": 4.6765,
    },
}

# Stable sample corpus for V1 fidelity work.
DEFAULT_AUDIT_SAMPLES: tuple[dict[str, Any], ...] = (
    {
        "sample_id": "WT550_0001",
        "condition": "2_WT_550",
        "role": "bright/easy control",
        "source": "testsamples/2_WT_550/01.avi",
        "roi_key": "WT550_0001",
    },
    {
        "sample_id": "WT550_0002",
        "condition": "2_WT_550",
        "role": "weak-tip / tapering filament",
        "source": "testsamples/2_WT_550/02.avi",
        "roi_key": "WT550_0002",
    },
    {
        "sample_id": "WT550_0003",
        "condition": "2_WT_550",
        "role": "WT replicate",
        "source": "testsamples/2_WT_550/03.avi",
        "roi_key": "WT550_0003",
    },
    {
        "sample_id": "WT550_0004",
        "condition": "2_WT_550",
        "role": "WT replicate",
        "source": "testsamples/2_WT_550/04.avi",
        "roi_key": "WT550_0004",
    },
    {
        "sample_id": "WT550_0005",
        "condition": "2_WT_550",
        "role": "WT replicate",
        "source": "testsamples/2_WT_550/05.avi",
        "roi_key": "WT550_0005",
    },
    {
        "sample_id": "MUT515_0001",
        "condition": "3_Mutant_515",
        "role": "Mutant515 replicate",
        "source": "testsamples/3_Mutant_515/01_676-8-2.avi",
        "roi_key": "MUT515_0001",
    },
    {
        "sample_id": "MUT515_0002",
        "condition": "3_Mutant_515",
        "role": "crowded filaments",
        "source": "testsamples/3_Mutant_515/02_676-6-2.mp4",
        "roi_key": "MUT515_0002",
    },
    {
        "sample_id": "MUT515_0003",
        "condition": "3_Mutant_515",
        "role": "weak-tip / crowded",
        "source": "testsamples/3_Mutant_515/03_676-6-3.mp4",
        "roi_key": "MUT515_0003",
    },
    {
        "sample_id": "MUT515_0004",
        "condition": "3_Mutant_515",
        "role": "Mutant515 replicate",
        "source": "testsamples/3_Mutant_515/04_676-6-3.mp4",
        "roi_key": "MUT515_0004",
    },
    {
        "sample_id": "MUT515_0005",
        "condition": "3_Mutant_515",
        "role": "Mutant515 replicate",
        "source": "testsamples/3_Mutant_515/05_676-8-3.mp4",
        "roi_key": "MUT515_0005",
    },
)


@dataclass(frozen=True)
class TemporalEvidenceItem:
    claim: str
    value: Any
    source: str
    applies_to: str
    confidence: str
    notes: str = ""


@dataclass
class SparseDisplacementSummary:
    sample_id: str
    num_starting_points: int = 0
    num_tracks_with_valid_steps: int = 0
    total_valid_steps: int = 0
    mean_track_length_frames: float = 0.0
    end_reason_counts: dict[str, int] = field(default_factory=dict)
    frame_gap_counts: dict[str, int] = field(default_factory=dict)
    mean_displacement_px: float = 0.0
    median_displacement_px: float = 0.0
    mean_dx_px: float = 0.0
    mean_dy_px: float = 0.0
    mean_displacement_px_per_frame: float = 0.0
    total_path_px: float = 0.0
    total_frame_gaps: float = 0.0
    general_movement_um_per_s: float = 0.0
    time_weighted_mean_speed_um_per_s: float = 0.0
    params: dict[str, Any] = field(default_factory=dict)
    track_summaries: list[dict[str, Any]] = field(default_factory=list)
    calibrated_by_interval: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class OpticalFlowDisplacementSummary:
    sample_id: str
    has_valid_result: bool = False
    failure_reason: str = ""
    mean_magnitude_px_frame: Optional[float] = None
    mean_downward_px_frame: Optional[float] = None
    mean_net_y_px_frame: Optional[float] = None
    valid_pixel_fraction: Optional[float] = None
    frame_pair_count: int = 0
    general_movement_um_s: Optional[float] = None
    settings: dict[str, Any] = field(default_factory=dict)
    calibrated_by_interval: dict[str, dict[str, float]] = field(default_factory=dict)


def sha256_file(path: Path, *, nbytes: int | None = None) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        if nbytes is None:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        else:
            digest.update(handle.read(int(nbytes)))
    return digest.hexdigest()


def probe_video_container(path: Path) -> dict[str, Any]:
    path = Path(path)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        return {
            "path": str(path),
            "readable": False,
            "error": "cannot_open",
        }
    try:
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    finally:
        cap.release()
    playback_interval = (1.0 / fps) if fps > 0 else None
    return {
        "path": str(path.resolve()),
        "readable": True,
        "frame_count": frame_count,
        "playback_fps": fps,
        "playback_seconds_per_frame": playback_interval,
        "width": width,
        "height": height,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "note": (
            "playback_fps is container/export metadata and is not automatically "
            "biological acquisition interval"
        ),
    }


def load_crop_roi_for_sample(
    crop_metadata_path: Path,
    sample_key: str,
) -> tuple[OrientationState, RectROI] | None:
    path = Path(crop_metadata_path)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    samples = data.get("data_files") or data.get("samples") or {}
    row = samples.get(sample_key)
    if not isinstance(row, dict):
        return None
    rect = row.get("rectangle_roi") or {
        "x": row.get("roi_x"),
        "y": row.get("roi_y"),
        "width": row.get("roi_width"),
        "height": row.get("roi_height"),
    }
    if rect.get("x") is None or rect.get("width") is None:
        return None
    orientation = OrientationState(
        rotation_angle_degrees=float(row.get("rotation_angle_degrees", 0.0) or 0.0),
        flipped_180=bool(row.get("flipped_180", False)),
        mirror_y_axis=bool(row.get("mirror_y_axis", False)),
    )
    roi = RectROI(
        int(rect["x"]),
        int(rect["y"]),
        int(rect["width"]),
        int(rect["height"]),
    )
    return orientation, roi


def historical_tracker_params(
    *,
    seconds_per_frame: float = 0.2,
    microns_per_pixel: float = DEFAULT_MICRONS_PER_PIXEL,
) -> MotionIndexParams:
    """Defaults from the first motion-index implementation (template matching)."""
    return MotionIndexParams(
        num_starting_points=5,
        min_point_spacing_px=40,
        search_radius_px=15,
        template_patch_size_px=11,
        min_template_confidence=0.70,
        lookahead_frames=3,
        microns_per_pixel=microns_per_pixel,
        seconds_per_frame=seconds_per_frame,
        tracking_method=TRACKING_METHOD_TEMPLATE,
    )


def current_tracker_params(
    *,
    seconds_per_frame: float = DEFAULT_SECONDS_PER_FRAME,
    microns_per_pixel: float = DEFAULT_MICRONS_PER_PIXEL,
) -> MotionIndexParams:
    return MotionIndexParams(
        microns_per_pixel=microns_per_pixel,
        seconds_per_frame=seconds_per_frame,
        tracking_method=TRACKING_METHOD_BRIGHTEST_LOCAL,
    )


def historical_optical_flow_settings(
    *,
    seconds_per_frame: float = 0.2,
    microns_per_pixel: float = DEFAULT_MICRONS_PER_PIXEL,
) -> OpticalFlowSettings:
    return OpticalFlowSettings(
        mask_percentile=90.0,
        gaussian_blur_kernel=3,
        microns_per_pixel=microns_per_pixel,
        seconds_per_frame=seconds_per_frame,
    )


def current_optical_flow_settings(
    *,
    seconds_per_frame: float = DEFAULT_SECONDS_PER_FRAME,
    microns_per_pixel: float = DEFAULT_MICRONS_PER_PIXEL,
) -> OpticalFlowSettings:
    return OpticalFlowSettings(
        microns_per_pixel=microns_per_pixel,
        seconds_per_frame=seconds_per_frame,
    )


def _mean_or_zero(values: Sequence[float]) -> float:
    return float(statistics.fmean(values)) if values else 0.0


def _median_or_zero(values: Sequence[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def summarize_sparse_tracks(
    sample_id: str,
    tracks: Sequence[PointTrack],
    params: MotionIndexParams,
) -> SparseDisplacementSummary:
    all_steps: list[StepMetrics] = []
    end_reasons: dict[str, int] = {}
    gap_counts: dict[str, int] = {}
    track_rows: list[dict[str, Any]] = []

    for track in tracks:
        end_reasons[track.end_reason] = end_reasons.get(track.end_reason, 0) + 1
        steps = iter_track_step_metrics(track, params)
        all_steps.extend(steps)
        track_disp = [s.displacement_px for s in steps]
        track_rows.append(
            {
                "track_id": track.track_id,
                "num_points": len(track.points),
                "valid_steps": len(steps),
                "end_reason": track.end_reason,
                "mean_displacement_px": round(_mean_or_zero(track_disp), 6),
                "total_path_px": round(sum(track_disp), 6),
            }
        )
        for step in steps:
            key = str(step.frame_gap)
            gap_counts[key] = gap_counts.get(key, 0) + 1

    displacements = [s.displacement_px for s in all_steps]
    gaps = [float(s.frame_gap) for s in all_steps]
    total_path_px = float(sum(displacements))
    total_gaps = float(sum(gaps)) if gaps else 0.0
    mean_px_per_frame = (total_path_px / total_gaps) if total_gaps > 0 else 0.0
    downward, general, _ = compute_motion_indices(tracks, params)
    velocity = compute_velocity_summary(tracks, params)
    valid_tracks, total_steps, mean_len = compute_track_statistics(tracks)

    calibrated: dict[str, dict[str, float]] = {}
    for label, seconds in CANDIDATE_SECONDS_PER_FRAME:
        spf = float(params.seconds_per_frame if seconds is None else seconds)
        scale = float(params.microns_per_pixel) / spf
        calibrated[label] = {
            "seconds_per_frame": spf,
            "general_movement_um_per_s": mean_px_per_frame * scale,
            "of_like_from_sparse_mean_px_per_frame": mean_px_per_frame * scale,
        }

    return SparseDisplacementSummary(
        sample_id=sample_id,
        num_starting_points=len(tracks),
        num_tracks_with_valid_steps=valid_tracks,
        total_valid_steps=total_steps,
        mean_track_length_frames=mean_len,
        end_reason_counts=end_reasons,
        frame_gap_counts=gap_counts,
        mean_displacement_px=_mean_or_zero(displacements),
        median_displacement_px=_median_or_zero(displacements),
        mean_dx_px=_mean_or_zero([s.dx_px for s in all_steps]),
        mean_dy_px=_mean_or_zero([s.dy_px for s in all_steps]),
        mean_displacement_px_per_frame=mean_px_per_frame,
        total_path_px=total_path_px,
        total_frame_gaps=total_gaps,
        general_movement_um_per_s=general,
        time_weighted_mean_speed_um_per_s=velocity.time_weighted_mean_speed_um_per_s,
        params=asdict(params),
        track_summaries=track_rows,
        calibrated_by_interval=calibrated,
    )


def summarize_optical_flow(
    sample_id: str,
    frames: Sequence[np.ndarray],
    settings: OpticalFlowSettings,
) -> OpticalFlowDisplacementSummary:
    result = compute_optical_flow_motion_index(frames, settings, sample_id=sample_id)
    calibrated: dict[str, dict[str, float]] = {}
    mag = float(result.mean_magnitude_px_frame or 0.0)
    for label, seconds in CANDIDATE_SECONDS_PER_FRAME:
        spf = float(settings.seconds_per_frame if seconds is None else seconds)
        scale = float(settings.microns_per_pixel) / spf
        calibrated[label] = {
            "seconds_per_frame": spf,
            "optical_flow_general_movement_um_s": mag * scale,
        }
    return OpticalFlowDisplacementSummary(
        sample_id=sample_id,
        has_valid_result=result.has_valid_result,
        failure_reason=result.failure_reason,
        mean_magnitude_px_frame=result.mean_magnitude_px_frame,
        mean_downward_px_frame=result.mean_downward_px_frame,
        mean_net_y_px_frame=result.mean_net_y_px_frame,
        valid_pixel_fraction=result.optical_flow_valid_pixel_fraction,
        frame_pair_count=result.frame_pair_count,
        general_movement_um_s=result.optical_flow_general_movement_um_s,
        settings=asdict(settings),
        calibrated_by_interval=calibrated,
    )


def run_matched_sample_audit(
    *,
    source_path: Path,
    sample_id: str,
    condition: str,
    role: str,
    orientation: OrientationState,
    roi: RectROI,
    tracker_params: MotionIndexParams,
    flow_settings: OpticalFlowSettings,
    domain_note: str,
) -> dict[str, Any]:
    """Run sparse tracking and Optical Flow on identical cropped frames."""
    source_path = Path(source_path).resolve()
    container = probe_video_container(source_path)
    frames = load_cropped_frames_from_video(source_path, orientation, roi)
    starts = select_starting_points(frames[0], tracker_params)
    tracks = track_points(frames, starts, tracker_params) if starts else []
    sparse = summarize_sparse_tracks(sample_id, tracks, tracker_params)
    flow = summarize_optical_flow(sample_id, frames, flow_settings)

    return {
        "sample_id": sample_id,
        "condition": condition,
        "role": role,
        "source_path": str(source_path),
        "domain_note": domain_note,
        "roi": roi.as_dict(),
        "orientation": {
            "rotation_angle_degrees": orientation.rotation_angle_degrees,
            "flipped_180": orientation.flipped_180,
            "mirror_y_axis": orientation.mirror_y_axis,
        },
        "container": container,
        "crop_shape": [int(frames[0].shape[0]), int(frames[0].shape[1])],
        "frame_count": len(frames),
        "sparse_tracking": asdict(sparse),
        "optical_flow": asdict(flow),
        "comparison": {
            "sparse_mean_px_per_frame": sparse.mean_displacement_px_per_frame,
            "optical_flow_mean_px_per_frame": flow.mean_magnitude_px_frame,
            "same_frames": True,
            "same_roi": True,
            "note": (
                "Sparse tracking follows localized bright features; Optical Flow "
                "averages dense bright-pixel motion. Values need not match."
            ),
        },
    }


def collect_temporal_evidence(repo_root: Path) -> list[dict[str, Any]]:
    """Assemble competing temporal-calibration claims for the audit report."""
    root = Path(repo_root).resolve()
    items = [
        TemporalEvidenceItem(
            claim="current_code_default_seconds_per_frame",
            value=DEFAULT_SECONDS_PER_FRAME,
            source="actintrack_app/motion_index.py::DEFAULT_SECONDS_PER_FRAME",
            applies_to="current production defaults",
            confidence="code_fact",
            notes=(
                "Current default is 60.0 s/frame (PERF1 lab protocol: consecutive "
                "scientific acquisition frames are one minute apart). Container "
                "playback FPS remains provenance only and does not set velocity dt."
            ),
        ),
        TemporalEvidenceItem(
            claim="historical_code_default_seconds_per_frame",
            value=0.2,
            source="git commit 006350e (first motion-index implementation)",
            applies_to="historical draft tracking/OF results through ~2026-06-24",
            confidence="code_history_fact",
            notes=(
                "Original MotionIndexParams defaulted to 0.2000 s/frame. Draft "
                "workspace metrics for WT550/MUT515 were saved with this value."
            ),
        ),
        TemporalEvidenceItem(
            claim="exported_video_playback_fps",
            value=6.0,
            source="OpenCV CAP_PROP_FPS on testsamples AVI/MP4 exports",
            applies_to="all inspected testsamples WT550 and Mutant515 videos",
            confidence="container_metadata_fact",
            notes=(
                "Container reports 6 fps (≈0.1667 s/frame). This is export "
                "playback timing, not necessarily biological acquisition interval."
            ),
        ),
        TemporalEvidenceItem(
            claim="slide_deck_acquisition_interval",
            value="30 sec/frame, 15 frames",
            source="PROJECT_OVERVIEW.md citing local_context/F-actin imaging.pptx",
            applies_to="lab description of time-lapse acquisition",
            confidence="documentation_claim",
            notes=(
                "Independent acquisition metadata for these exact lossy exports "
                "has not been recovered in-repo. Treat as hypothesis until "
                "confirmed for the corpus."
            ),
        ),
        TemporalEvidenceItem(
            claim="historical_group_sanity_WT550_vs_MUT515",
            value=HISTORICAL_GROUP_SANITY,
            source="researcher-confirmed historical ActinTrackCV group summaries",
            applies_to="condition-group qualitative ordering",
            confidence="external_qualitative_ground_truth",
            notes=(
                "WT > Mutant is an external biological sanity check. Units/scale "
                "of the historical scalars remain under investigation."
            ),
        ),
    ]

    draft_dir = root / "metadata" / "draft_tracking"
    if draft_dir.is_dir():
        for sample_id in ("WT550_0001", "MUT515_0002"):
            path = draft_dir / f"{sample_id}.json"
            if not path.is_file():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            params = payload.get("parameters") or {}
            items.append(
                TemporalEvidenceItem(
                    claim=f"draft_tracking_seconds_per_frame_{sample_id}",
                    value=params.get("seconds_per_frame"),
                    source=str(path.relative_to(root)),
                    applies_to=sample_id,
                    confidence="workspace_artifact_fact",
                    notes=(
                        f"general_movement={payload.get('general_movement_index_um_per_s')}; "
                        f"tracks={payload.get('num_tracks_with_valid_steps')}; "
                        f"steps={payload.get('total_valid_steps')}"
                    ),
                )
            )

    draft_of = root / "metadata" / "draft_optical_flow"
    if draft_of.is_dir():
        for sample_id in ("WT550_0001", "MUT515_0002"):
            path = draft_of / f"{sample_id}.json"
            if not path.is_file():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            settings = payload.get("settings") or {}
            items.append(
                TemporalEvidenceItem(
                    claim=f"draft_optical_flow_seconds_per_frame_{sample_id}",
                    value=settings.get("seconds_per_frame"),
                    source=str(path.relative_to(root)),
                    applies_to=sample_id,
                    confidence="workspace_artifact_fact",
                    notes=(
                        f"of_general={payload.get('optical_flow_general_movement_um_s')}; "
                        f"mean_mag_px_frame={payload.get('mean_magnitude_px_frame')}; "
                        f"mask_percentile={settings.get('mask_percentile')}"
                    ),
                )
            )

    return [asdict(item) for item in items]


def condition_ordering(
    sample_rows: Sequence[dict[str, Any]],
    *,
    sparse_key: str = "sparse_tracking.mean_displacement_px_per_frame",
    of_key: str = "optical_flow.mean_magnitude_px_frame",
) -> dict[str, Any]:
    def _get(row: dict[str, Any], dotted: str) -> Optional[float]:
        cur: Any = row
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return None
            cur = cur[part]
        if cur is None or cur == "":
            return None
        return float(cur)

    by_condition: dict[str, dict[str, list[float]]] = {}
    for row in sample_rows:
        condition = str(row.get("condition", ""))
        bucket = by_condition.setdefault(
            condition, {"sparse_px_per_frame": [], "of_px_per_frame": []}
        )
        sparse = _get(row, sparse_key)
        of_val = _get(row, of_key)
        if sparse is not None:
            bucket["sparse_px_per_frame"].append(sparse)
        if of_val is not None:
            bucket["of_px_per_frame"].append(of_val)

    summary = {
        condition: {
            "n_sparse": len(vals["sparse_px_per_frame"]),
            "mean_sparse_px_per_frame": _mean_or_zero(vals["sparse_px_per_frame"]),
            "n_of": len(vals["of_px_per_frame"]),
            "mean_of_px_per_frame": _mean_or_zero(vals["of_px_per_frame"]),
        }
        for condition, vals in by_condition.items()
    }
    wt = summary.get("2_WT_550", {})
    mut = summary.get("3_Mutant_515", {})
    return {
        "by_condition": summary,
        "historical_sanity": HISTORICAL_GROUP_SANITY,
        "observed_sparse_wt_gt_mutant": (
            wt.get("mean_sparse_px_per_frame", 0.0)
            > mut.get("mean_sparse_px_per_frame", 0.0)
            if wt and mut
            else None
        ),
        "observed_of_wt_gt_mutant": (
            wt.get("mean_of_px_per_frame", 0.0) > mut.get("mean_of_px_per_frame", 0.0)
            if wt and mut
            else None
        ),
        "note": (
            "Ordering uses raw px/frame means to isolate tracking/feature "
            "semantics from temporal calibration."
        ),
    }


def run_measurement_fidelity_audit(
    repo_root: Path,
    *,
    output_dir: Path | None = None,
    sample_ids: Sequence[str] | None = None,
    use_saved_roi: bool = True,
    tracker_mode: str = "current",
    flow_mode: str = "historical_draft",
    seconds_per_frame: float | None = None,
) -> dict[str, Any]:
    """Run the V1 matched sparse/OF audit and write machine-readable reports."""
    root = Path(repo_root).resolve()
    out = Path(output_dir or (root / "outputs" / "measurement_fidelity")).resolve()
    out.mkdir(parents=True, exist_ok=True)

    crop_meta = root / "metadata" / "crop_metadata.json"
    selected = [
        s
        for s in DEFAULT_AUDIT_SAMPLES
        if sample_ids is None or s["sample_id"] in set(sample_ids)
    ]

    if tracker_mode == "historical":
        tracker_params = historical_tracker_params(
            seconds_per_frame=(
                0.2 if seconds_per_frame is None else float(seconds_per_frame)
            )
        )
    else:
        tracker_params = current_tracker_params(
            seconds_per_frame=(
                DEFAULT_SECONDS_PER_FRAME
                if seconds_per_frame is None
                else float(seconds_per_frame)
            )
        )

    if flow_mode == "current":
        flow_settings = current_optical_flow_settings(
            seconds_per_frame=float(tracker_params.seconds_per_frame)
        )
    else:
        # Match the workspace draft Optical Flow settings that produced the
        # researcher-facing OF magnitudes closest to historical summaries.
        flow_settings = historical_optical_flow_settings(
            seconds_per_frame=float(tracker_params.seconds_per_frame)
        )

    sample_rows: list[dict[str, Any]] = []
    for spec in selected:
        source = root / spec["source"]
        if not source.is_file():
            sample_rows.append(
                {
                    "sample_id": spec["sample_id"],
                    "condition": spec["condition"],
                    "role": spec["role"],
                    "error": f"missing_source:{source}",
                }
            )
            continue

        orientation = OrientationState()
        roi: RectROI | None = None
        domain_note = "whole_frame_legacy_observation_no_saved_roi"
        if use_saved_roi:
            loaded = load_crop_roi_for_sample(crop_meta, spec["roi_key"])
            if loaded is not None:
                orientation, roi = loaded
                domain_note = (
                    "saved_rect_roi_crop_without_cellregion_or_cutoff; "
                    "not an R3 scientific-domain validation"
                )
        if roi is None:
            probe = probe_video_container(source)
            roi = RectROI(0, 0, int(probe["width"]), int(probe["height"]))
            domain_note = "whole_frame_legacy_observation"

        try:
            row = run_matched_sample_audit(
                source_path=source,
                sample_id=spec["sample_id"],
                condition=spec["condition"],
                role=spec["role"],
                orientation=orientation,
                roi=roi,
                tracker_params=tracker_params,
                flow_settings=flow_settings,
                domain_note=domain_note,
            )
        except Exception as exc:  # noqa: BLE001 - audit must continue across samples
            row = {
                "sample_id": spec["sample_id"],
                "condition": spec["condition"],
                "role": spec["role"],
                "source_path": str(source),
                "error": str(exc),
            }
        sample_rows.append(row)

    payload: dict[str, Any] = {
        "audit_kind": "measurement_fidelity_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "metric_definition_version": METRIC_DEFINITION_VERSION,
        "movement_output_schema_version": MOVEMENT_OUTPUT_SCHEMA_VERSION,
        "repo_root": str(root),
        "tracker_mode": tracker_mode,
        "flow_mode": flow_mode,
        "tracker_params": asdict(tracker_params),
        "optical_flow_settings": asdict(flow_settings),
        "constraints": {
            "no_correction_multipliers": True,
            "values_below_1_um_s_are_investigation_trigger": True,
            "wt_gt_mutant_is_sanity_check_not_tuning_target": True,
            "acquisition_interval_unresolved_for_corpus": True,
        },
        "temporal_evidence": collect_temporal_evidence(root),
        "condition_ordering": condition_ordering(
            [r for r in sample_rows if "error" not in r]
        ),
        "samples": sample_rows,
    }

    report_json = out / "measurement_fidelity_report.json"
    report_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    csv_path = out / "measurement_fidelity_sample_summary.csv"
    fieldnames = [
        "sample_id",
        "condition",
        "role",
        "domain_note",
        "frame_count",
        "playback_fps",
        "sparse_starts",
        "sparse_valid_tracks",
        "sparse_valid_steps",
        "sparse_mean_track_length_frames",
        "sparse_mean_displacement_px",
        "sparse_median_displacement_px",
        "sparse_mean_px_per_frame",
        "sparse_general_um_s_at_run_spf",
        "of_mean_px_per_frame",
        "of_general_um_s_at_run_spf",
        "of_valid_pixel_fraction",
        "error",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in sample_rows:
            sparse = row.get("sparse_tracking") or {}
            flow = row.get("optical_flow") or {}
            container = row.get("container") or {}
            writer.writerow(
                {
                    "sample_id": row.get("sample_id", ""),
                    "condition": row.get("condition", ""),
                    "role": row.get("role", ""),
                    "domain_note": row.get("domain_note", ""),
                    "frame_count": row.get("frame_count", ""),
                    "playback_fps": container.get("playback_fps", ""),
                    "sparse_starts": sparse.get("num_starting_points", ""),
                    "sparse_valid_tracks": sparse.get("num_tracks_with_valid_steps", ""),
                    "sparse_valid_steps": sparse.get("total_valid_steps", ""),
                    "sparse_mean_track_length_frames": sparse.get(
                        "mean_track_length_frames", ""
                    ),
                    "sparse_mean_displacement_px": sparse.get("mean_displacement_px", ""),
                    "sparse_median_displacement_px": sparse.get(
                        "median_displacement_px", ""
                    ),
                    "sparse_mean_px_per_frame": sparse.get(
                        "mean_displacement_px_per_frame", ""
                    ),
                    "sparse_general_um_s_at_run_spf": sparse.get(
                        "general_movement_um_per_s", ""
                    ),
                    "of_mean_px_per_frame": flow.get("mean_magnitude_px_frame", ""),
                    "of_general_um_s_at_run_spf": flow.get("general_movement_um_s", ""),
                    "of_valid_pixel_fraction": flow.get("valid_pixel_fraction", ""),
                    "error": row.get("error", ""),
                }
            )

    payload["report_json"] = str(report_json)
    payload["sample_csv"] = str(csv_path)
    return payload


def implied_px_per_frame(
    speed_um_per_s: float,
    *,
    seconds_per_frame: float,
    microns_per_pixel: float = DEFAULT_MICRONS_PER_PIXEL,
) -> float:
    """Convert a reported µm/s scalar into implied mean px/frame displacement."""
    return float(speed_um_per_s) * float(seconds_per_frame) / float(microns_per_pixel)
