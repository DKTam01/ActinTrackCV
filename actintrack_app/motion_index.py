"""F-actin motion-index tracking for processed ROI videos and image sequences."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import cv2
import numpy as np

from actintrack_app.export_naming import motion_index_output_paths
from actintrack_app.project_manager import get_processed_batch_dir
from actintrack_app.utils import (
    F_ACTIN_MOTION_INDEX_SUMMARY_CSV,
    IMAGE_EXTENSIONS,
    METADATA_DIR,
    VIDEO_EXTENSIONS,
)
from actintrack_app.video_processing import MediaLoadError, get_video_frame_count

TRACK_PALETTE = [
    (80, 220, 120),
    (120, 180, 255),
    (255, 160, 80),
    (220, 120, 255),
    (255, 120, 120),
    (120, 255, 255),
    (180, 255, 120),
    (255, 220, 120),
    (120, 120, 255),
    (255, 120, 220),
]

MOTION_INDEX_SUMMARY_COLUMNS = [
    "sample_id",
    "group",
    "batch_name",
    "final_export_name",
    "source_path",
    "analysis_timestamp_utc",
    "downward_velocity_index_um_per_s",
    "general_movement_index_um_per_s",
    "num_tracks_started",
    "num_tracks_with_valid_steps",
    "total_valid_steps",
    "mean_track_length_frames",
    "frame_count",
    "trajectory_csv",
    "summary_json",
    "track_preview",
]

DEFAULT_MICRONS_PER_PIXEL = 0.2650
DEFAULT_SECONDS_PER_FRAME = 0.2000


@dataclass(frozen=True)
class MotionIndexParams:
    """Parameters for bright-spot template-matching motion-index analysis."""

    num_starting_points: int = 5
    min_point_spacing_px: int = 40
    search_radius_px: int = 15
    template_patch_size_px: int = 11
    min_template_confidence: float = 0.70
    lookahead_frames: int = 3
    microns_per_pixel: float = DEFAULT_MICRONS_PER_PIXEL
    seconds_per_frame: float = DEFAULT_SECONDS_PER_FRAME
    downward_direction: str = "increasing_y"

    def __post_init__(self) -> None:
        if self.num_starting_points < 1:
            raise ValueError("num_starting_points must be at least 1.")
        if self.min_point_spacing_px < 1:
            raise ValueError("min_point_spacing_px must be at least 1.")
        if self.search_radius_px < 1:
            raise ValueError("search_radius_px must be at least 1.")
        patch = int(self.template_patch_size_px)
        if patch < 3 or patch % 2 == 0:
            raise ValueError("template_patch_size_px must be an odd integer >= 3.")
        if not 0.0 <= self.min_template_confidence <= 1.0:
            raise ValueError("min_template_confidence must be between 0 and 1.")
        if self.lookahead_frames < 0:
            raise ValueError("lookahead_frames must be >= 0.")
        if self.microns_per_pixel <= 0:
            raise ValueError("microns_per_pixel must be positive.")
        if self.seconds_per_frame <= 0:
            raise ValueError("seconds_per_frame must be positive.")
        if self.downward_direction != "increasing_y":
            raise ValueError("Only downward_direction='increasing_y' is supported.")


@dataclass
class TrackPoint:
    track_id: int
    frame_index: int
    x: float
    y: float
    confidence: float
    recovered_with_lookahead: bool = False


@dataclass
class PointTrack:
    track_id: int
    start_x: float
    start_y: float
    points: list[TrackPoint] = field(default_factory=list)
    active: bool = True
    end_reason: str = ""

    def last_point(self) -> TrackPoint:
        return self.points[-1]


@dataclass(frozen=True)
class ProcessedInputOption:
    """One discoverable processed ROI input for motion-index analysis."""

    label: str
    path: Path
    input_kind: str  # "video" | "image_sequence"
    frame_paths: tuple[Path, ...] = ()


@dataclass
class MotionIndexResult:
    source_path: str
    output_dir: str
    frame_count: int
    frame_width: int
    frame_height: int
    params: MotionIndexParams
    tracks: list[PointTrack]
    trajectory_csv: str
    summary_json: str
    start_points_preview: str
    tracks_overlay_preview: str
    track_preview_video: str
    downward_velocity_index_um_per_s: float
    general_movement_index_um_per_s: float
    track_summaries: list[dict[str, Any]]
    final_export_name: str = ""
    sample_id: str = ""
    num_tracks_with_valid_steps: int = 0
    total_valid_steps: int = 0
    mean_track_length_frames: float = 0.0
    track_preview_error: str = ""

    def summary_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "output_dir": self.output_dir,
            "final_export_name": self.final_export_name,
            "sample_id": self.sample_id,
            "frame_count": self.frame_count,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "analysis_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "parameters": asdict(self.params),
            "downward_velocity_index_um_per_s": self.downward_velocity_index_um_per_s,
            "general_movement_index_um_per_s": self.general_movement_index_um_per_s,
            "num_tracks_started": len(self.tracks),
            "num_tracks_with_valid_steps": self.num_tracks_with_valid_steps,
            "total_valid_steps": self.total_valid_steps,
            "mean_track_length_frames": self.mean_track_length_frames,
            "num_tracks_completed_full_sequence": sum(
                1
                for t in self.tracks
                if t.points and t.points[-1].frame_index == self.frame_count - 1
            ),
            "track_summaries": self.track_summaries,
            "track_preview_error": self.track_preview_error,
            "outputs": {
                "trajectory_csv": self.trajectory_csv,
                "summary_json": self.summary_json,
                "starting_points_png": self.start_points_preview,
                "track_overlay_png": self.tracks_overlay_preview,
                "track_preview_mp4": self.track_preview_video,
            },
        }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _odd_size(value: int) -> int:
    size = max(3, int(value))
    return size if size % 2 == 1 else size + 1


def frame_to_signal(frame: np.ndarray) -> np.ndarray:
    """Grayscale actin-dominant signal used for peak detection and matching."""
    if frame.ndim == 2:
        return frame.astype(np.float32)
    b = frame[..., 0].astype(np.float32)
    g = frame[..., 1].astype(np.float32)
    r = frame[..., 2].astype(np.float32)
    gray = (0.114 * b) + (0.587 * g) + (0.299 * r)
    cyan_actin = np.maximum(b, g) - (0.25 * r)
    cyan_actin = np.clip(cyan_actin, 0.0, None)
    if float(np.percentile(cyan_actin, 99) - np.percentile(cyan_actin, 5)) < 5.0:
        return gray
    return cyan_actin


def _is_image_sequence_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    images = [
        p
        for p in sorted(path.iterdir())
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    ]
    return len(images) >= 2


def _sorted_image_paths(directory: Path) -> list[Path]:
    images = [
        p
        for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    ]
    return sorted(images, key=lambda p: p.name.lower())


def _sequence_paths_for_export(batch_dir: Path, final_export_name: str) -> list[Path]:
    """Return sorted processed image-sequence frames for one export prefix."""
    pattern = f"{final_export_name}--*.png"
    paths = sorted(batch_dir.glob(pattern), key=lambda p: p.name.lower())
    if len(paths) >= 2:
        return paths
    jpg_paths = sorted(
        batch_dir.glob(f"{final_export_name}--*.jpg"),
        key=lambda p: p.name.lower(),
    )
    if len(jpg_paths) >= 2:
        return jpg_paths
    return []


def discover_processed_inputs(
    root: Path,
    sample_row: dict[str, Any],
) -> list[ProcessedInputOption]:
    """
    Find processed/cropped ROI inputs for one sample.

    Returns zero or more candidates (video and/or image sequence).
    """
    root = Path(root).resolve()
    group = str(sample_row.get("group", "")).strip()
    batch_name = str(sample_row.get("batch_name", "")).strip()
    final_name = str(sample_row.get("final_export_name", "")).strip()
    if not group or not batch_name or not final_name:
        return []

    batch_dir = get_processed_batch_dir(root, group, batch_name)
    if not batch_dir.is_dir():
        return []

    options: list[ProcessedInputOption] = []
    for ext in (".mp4", ".avi"):
        video_path = batch_dir / f"{final_name}{ext}"
        if video_path.is_file():
            options.append(
                ProcessedInputOption(
                    label=f"Processed video ({video_path.name})",
                    path=video_path,
                    input_kind="video",
                )
            )
            break

    seq_paths = _sequence_paths_for_export(batch_dir, final_name)
    if len(seq_paths) >= 2:
        options.append(
            ProcessedInputOption(
                label=(
                    f"Processed image sequence ({len(seq_paths)} frames, "
                    f"{seq_paths[0].name} …)"
                ),
                path=seq_paths[0],
                input_kind="image_sequence",
                frame_paths=tuple(seq_paths),
            )
        )

    return options


def load_frames_from_paths(frame_paths: Sequence[Path]) -> tuple[list[np.ndarray], dict[str, Any]]:
    """Load an explicit ordered list of image frames."""
    if len(frame_paths) < 2:
        raise MediaLoadError("Image sequence must contain at least 2 frames.")
    frames = [cv2.imread(str(p), cv2.IMREAD_COLOR) for p in frame_paths]
    frames = [f for f in frames if f is not None]
    if len(frames) < 2:
        raise MediaLoadError("Need at least 2 readable frames in the image sequence.")
    return frames, {
        "source_path": str(frame_paths[0].parent),
        "loader": "image_sequence",
        "frame_paths": [str(p) for p in frame_paths],
    }


def load_frame_sequence(source: str | Path) -> tuple[list[np.ndarray], dict[str, Any]]:
    """
    Load a processed ROI video or image sequence.

    Accepts:
    - video files (.mp4, .avi)
    - directories containing two or more image frames
    - multi-frame TIFF stacks (when tifffile is available)
    """
    path = Path(source).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Input path does not exist: {path}")

    meta: dict[str, Any] = {"source_path": str(path), "loader": ""}

    if path.is_dir():
        frame_paths = _sorted_image_paths(path)
        if len(frame_paths) < 2:
            raise MediaLoadError(f"Directory does not contain an image sequence: {path}")
        frames = [cv2.imread(str(p), cv2.IMREAD_COLOR) for p in frame_paths]
        frames = [f for f in frames if f is not None]
        if len(frames) < 2:
            raise MediaLoadError(f"Need at least 2 readable frames in: {path}")
        meta["loader"] = "image_sequence"
        meta["frame_paths"] = [str(p) for p in frame_paths]
        return frames, meta

    ext = path.suffix.lower()
    if ext in VIDEO_EXTENSIONS:
        count = get_video_frame_count(path)
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            cap.release()
            raise MediaLoadError(f"Cannot open video: {path}")
        frames: list[np.ndarray] = []
        try:
            while True:
                ok, frame = cap.read()
                if not ok or frame is None:
                    break
                frames.append(frame)
        finally:
            cap.release()
        if len(frames) < 2:
            raise MediaLoadError(f"Video must contain at least 2 frames: {path}")
        meta["loader"] = "video"
        meta["reported_frame_count"] = count
        return frames, meta

    if ext in {".tif", ".tiff"}:
        try:
            import tifffile

            with tifffile.TiffFile(str(path)) as tif:
                arrays = [page.asarray() for page in tif.pages]
        except ImportError as exc:
            raise MediaLoadError(
                "Multi-frame TIFF loading requires tifffile. "
                "Install with: pip install tifffile"
            ) from exc

        frames = []
        for arr in arrays:
            if arr.ndim == 2:
                frames.append(cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_GRAY2BGR))
            elif arr.ndim == 3 and arr.shape[2] >= 3:
                frames.append(cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_RGB2BGR))
            else:
                raise MediaLoadError(f"Unsupported TIFF page shape: {arr.shape}")
        if len(frames) < 2:
            raise MediaLoadError(f"TIFF stack must contain at least 2 frames: {path}")
        meta["loader"] = "tiff_stack"
        return frames, meta

    if ext in IMAGE_EXTENSIONS:
        frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if frame is None:
            raise MediaLoadError(f"Cannot open image: {path}")
        meta["loader"] = "single_image"
        raise MediaLoadError(
            "Single image provided; motion-index analysis needs a video or image sequence."
        )

    raise MediaLoadError(f"Unsupported motion-index input: {path}")


def _local_maxima_mask(signal: np.ndarray, patch_size: int) -> np.ndarray:
    kernel = np.ones((patch_size, patch_size), dtype=np.uint8)
    dilated = cv2.dilate(signal, kernel)
    return signal >= (dilated - 1e-6)


def select_starting_points(
    first_frame: np.ndarray,
    params: MotionIndexParams,
) -> list[tuple[float, float]]:
    """
    Pick bright local maxima from the first frame with minimum spacing.

    Returns (x, y) coordinates in image pixels.
    """
    signal = frame_to_signal(first_frame)
    h, w = signal.shape[:2]
    patch = _odd_size(max(3, params.template_patch_size_px))
    half = patch // 2

    mask = _local_maxima_mask(signal, patch_size=5)
    ys, xs = np.where(mask)
    if ys.size == 0:
        raise ValueError("No local maxima found in the first frame.")

    scores = signal[ys, xs]
    order = np.argsort(scores)[::-1]

    selected: list[tuple[float, float]] = []
    min_dist = float(params.min_point_spacing_px)
    min_dist_sq = min_dist * min_dist

    for idx in order:
        x = float(xs[idx])
        y = float(ys[idx])
        if x < half or y < half or x >= w - half or y >= h - half:
            continue
        too_close = False
        for sx, sy in selected:
            dx = x - sx
            dy = y - sy
            if (dx * dx) + (dy * dy) < min_dist_sq:
                too_close = True
                break
        if too_close:
            continue
        selected.append((x, y))
        if len(selected) >= params.num_starting_points:
            break

    if not selected:
        raise ValueError("No valid starting points after spacing and border checks.")
    return selected


def _extract_patch(signal: np.ndarray, x: float, y: float, patch_size: int) -> np.ndarray:
    half = patch_size // 2
    cx = int(round(x))
    cy = int(round(y))
    y0 = cy - half
    y1 = cy + half + 1
    x0 = cx - half
    x1 = cx + half + 1
    patch = signal[y0:y1, x0:x1]
    if patch.shape != (patch_size, patch_size):
        raise ValueError("Patch extraction failed near image border.")
    return patch.astype(np.float32)


def _match_template_in_window(
    frame_signal: np.ndarray,
    template: np.ndarray,
    center_x: float,
    center_y: float,
    search_radius_px: int,
) -> tuple[float, float, float]:
    h, w = frame_signal.shape[:2]
    patch_h, patch_w = template.shape[:2]
    half_y = patch_h // 2
    half_x = patch_w // 2

    cx = int(round(center_x))
    cy = int(round(center_y))
    radius = int(search_radius_px)

    x0 = max(0, cx - radius - half_x)
    y0 = max(0, cy - radius - half_y)
    x1 = min(w, cx + radius + half_x + 1)
    y1 = min(h, cy + radius + half_y + 1)

    search_region = frame_signal[y0:y1, x0:x1]
    if search_region.shape[0] < patch_h or search_region.shape[1] < patch_w:
        return center_x, center_y, -1.0

    result = cv2.matchTemplate(search_region, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    match_x = float(x0 + max_loc[0] + half_x)
    match_y = float(y0 + max_loc[1] + half_y)
    return match_x, match_y, float(max_val)


def _try_match_step(
    signals: Sequence[np.ndarray],
    prev_point: TrackPoint,
    target_frame_idx: int,
    patch_size: int,
    search_radius_px: int,
) -> tuple[float, float, float]:
    template = _extract_patch(
        signals[prev_point.frame_index],
        prev_point.x,
        prev_point.y,
        patch_size,
    )
    return _match_template_in_window(
        signals[target_frame_idx],
        template,
        prev_point.x,
        prev_point.y,
        search_radius_px,
    )


def track_points(
    frames: Sequence[np.ndarray],
    starting_points: Sequence[tuple[float, float]],
    params: MotionIndexParams,
) -> list[PointTrack]:
    """Track starting bright points across frames using local template matching."""
    if len(frames) < 2:
        raise ValueError("At least two frames are required for tracking.")

    patch_size = _odd_size(params.template_patch_size_px)
    signals = [frame_to_signal(frame) for frame in frames]

    tracks: list[PointTrack] = []
    for track_id, (sx, sy) in enumerate(starting_points):
        tracks.append(
            PointTrack(
                track_id=track_id,
                start_x=sx,
                start_y=sy,
                points=[
                    TrackPoint(
                        track_id=track_id,
                        frame_index=0,
                        x=sx,
                        y=sy,
                        confidence=1.0,
                    )
                ],
            )
        )

    for track in tracks:
        while track.active:
            prev_point = track.last_point()
            next_frame = prev_point.frame_index + 1
            if next_frame >= len(frames):
                track.active = False
                track.end_reason = "reached_last_frame"
                break

            match_x, match_y, confidence = _try_match_step(
                signals,
                prev_point,
                next_frame,
                patch_size,
                params.search_radius_px,
            )

            if confidence >= params.min_template_confidence:
                track.points.append(
                    TrackPoint(
                        track_id=track.track_id,
                        frame_index=next_frame,
                        x=match_x,
                        y=match_y,
                        confidence=confidence,
                    )
                )
                continue

            recovered = False
            if params.lookahead_frames > 0:
                lookahead_frame = next_frame + params.lookahead_frames
                if lookahead_frame < len(frames):
                    match_x, match_y, confidence = _try_match_step(
                        signals,
                        prev_point,
                        lookahead_frame,
                        patch_size,
                        params.search_radius_px,
                    )
                    if confidence >= params.min_template_confidence:
                        track.points.append(
                            TrackPoint(
                                track_id=track.track_id,
                                frame_index=lookahead_frame,
                                x=match_x,
                                y=match_y,
                                confidence=confidence,
                                recovered_with_lookahead=True,
                            )
                        )
                        recovered = True

            if recovered:
                continue

            track.active = False
            track.end_reason = f"lost_at_frame_{next_frame}"

    return tracks


def _iter_consecutive_points(track: PointTrack) -> list[tuple[TrackPoint, TrackPoint]]:
    pairs: list[tuple[TrackPoint, TrackPoint]] = []
    for i in range(1, len(track.points)):
        pairs.append((track.points[i - 1], track.points[i]))
    return pairs


def compute_motion_indices(
    tracks: Sequence[PointTrack],
    params: MotionIndexParams,
) -> tuple[float, float, list[dict[str, Any]]]:
    """
    Compute aggregate motion indices and per-track summaries.

    Downward Velocity Index:
        Mean positive downward speed (dy > 0, increasing y) in microns/s.

    General Movement Index:
        Mean Euclidean displacement speed in microns/s across all valid steps.
    """
    mpp = float(params.microns_per_pixel)
    dt = float(params.seconds_per_frame)

    downward_speeds: list[float] = []
    general_speeds: list[float] = []
    track_summaries: list[dict[str, Any]] = []

    for track in tracks:
        track_downward: list[float] = []
        track_general: list[float] = []
        total_downward_um = 0.0
        total_path_um = 0.0
        total_time_s = 0.0

        for prev_pt, next_pt in _iter_consecutive_points(track):
            frame_gap = max(1, next_pt.frame_index - prev_pt.frame_index)
            step_dt = dt * frame_gap
            dx_px = next_pt.x - prev_pt.x
            dy_px = next_pt.y - prev_pt.y
            dx_um = dx_px * mpp
            dy_um = dy_px * mpp
            displacement_um = float(np.hypot(dx_um, dy_um))
            speed_general = displacement_um / step_dt

            track_general.append(speed_general)
            general_speeds.append(speed_general)
            total_path_um += displacement_um
            total_time_s += step_dt

            if dy_px > 0:
                speed_down = dy_um / step_dt
                track_downward.append(speed_down)
                downward_speeds.append(speed_down)
                total_downward_um += dy_um

        track_summaries.append(
            {
                "track_id": track.track_id,
                "start_x_px": round(track.start_x, 3),
                "start_y_px": round(track.start_y, 3),
                "num_points": len(track.points),
                "last_frame_index": track.points[-1].frame_index if track.points else None,
                "active_to_end": track.active,
                "end_reason": track.end_reason,
                "downward_velocity_index_um_per_s": round(
                    float(np.mean(track_downward)) if track_downward else 0.0, 6
                ),
                "general_movement_index_um_per_s": round(
                    float(np.mean(track_general)) if track_general else 0.0, 6
                ),
                "total_downward_displacement_um": round(total_downward_um, 6),
                "total_path_length_um": round(total_path_um, 6),
                "tracked_time_s": round(total_time_s, 6),
            }
        )

    downward_index = float(np.mean(downward_speeds)) if downward_speeds else 0.0
    general_index = float(np.mean(general_speeds)) if general_speeds else 0.0
    return downward_index, general_index, track_summaries


def compute_track_statistics(tracks: Sequence[PointTrack]) -> tuple[int, int, float]:
    """Return (tracks_with_valid_steps, total_valid_steps, mean_track_length_frames)."""
    valid_lengths: list[int] = []
    total_steps = 0
    for track in tracks:
        n = len(track.points)
        if n >= 2:
            valid_lengths.append(n)
            total_steps += n - 1
    mean_len = float(np.mean(valid_lengths)) if valid_lengths else 0.0
    return len(valid_lengths), total_steps, mean_len


def _default_output_dir(source: Path, final_export_name: str | None = None) -> Path:
    if final_export_name:
        return source.parent if source.is_file() else source
    if source.is_dir():
        return source
    return source.parent


def save_trajectory_csv(path: Path, tracks: Sequence[PointTrack]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "track_id",
                "frame_index",
                "x_px",
                "y_px",
                "confidence",
                "recovered_with_lookahead",
            ],
        )
        writer.writeheader()
        for track in tracks:
            for point in track.points:
                writer.writerow(
                    {
                        "track_id": point.track_id,
                        "frame_index": point.frame_index,
                        "x_px": round(point.x, 3),
                        "y_px": round(point.y, 3),
                        "confidence": round(point.confidence, 4),
                        "recovered_with_lookahead": point.recovered_with_lookahead,
                    }
                )


def draw_start_points_preview(
    first_frame: np.ndarray,
    starting_points: Sequence[tuple[float, float]],
) -> np.ndarray:
    out = first_frame.copy()
    for idx, (x, y) in enumerate(starting_points):
        cx, cy = int(round(x)), int(round(y))
        cv2.circle(out, (cx, cy), 5, (0, 255, 255), 1, lineType=cv2.LINE_AA)
        cv2.circle(out, (cx, cy), 2, (0, 255, 255), -1, lineType=cv2.LINE_AA)
        cv2.putText(
            out,
            str(idx + 1),
            (cx + 6, cy - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return out


def _track_visible_at_frame(track: PointTrack, frame_index: int) -> list[TrackPoint]:
    pts = [p for p in track.points if p.frame_index <= frame_index]
    if not pts:
        return []
    last = pts[-1]
    if not track.active and last.frame_index < frame_index:
        return []
    return pts


def render_track_preview_frame(
    frame: np.ndarray,
    tracks: Sequence[PointTrack],
    frame_index: int,
    *,
    trail_length: int = 6,
) -> np.ndarray:
    """Draw tracked points, short trails, and IDs on one cropped ROI frame."""
    out = frame.copy()
    for track in tracks:
        pts = _track_visible_at_frame(track, frame_index)
        if not pts:
            continue
        color = TRACK_PALETTE[track.track_id % len(TRACK_PALETTE)]
        draw_pts = pts[-max(1, trail_length) :]
        for i in range(1, len(draw_pts)):
            p0 = (int(round(draw_pts[i - 1].x)), int(round(draw_pts[i - 1].y)))
            p1 = (int(round(draw_pts[i].x)), int(round(draw_pts[i].y)))
            cv2.line(out, p0, p1, color, 1, lineType=cv2.LINE_AA)
        last = pts[-1]
        cx, cy = int(round(last.x)), int(round(last.y))
        cv2.circle(out, (cx, cy), 4, color, 1, lineType=cv2.LINE_AA)
        cv2.circle(out, (cx, cy), 2, color, -1, lineType=cv2.LINE_AA)
        cv2.putText(
            out,
            str(track.track_id + 1),
            (cx + 5, cy - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            color,
            1,
            cv2.LINE_AA,
        )
    return out


def write_track_preview_video(
    path: Path,
    frames: Sequence[np.ndarray],
    tracks: Sequence[PointTrack],
    *,
    fps: float = 5.0,
) -> None:
    """Write watchable trajectory preview MP4 from processed ROI frames."""
    if not frames:
        raise ValueError("Cannot write track preview: no frames.")
    path.parent.mkdir(parents=True, exist_ok=True)
    h, w = frames[0].shape[:2]
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        max(1.0, float(fps)),
        (w, h),
    )
    if not writer.isOpened():
        raise OSError(f"Could not open video writer for track preview: {path}")
    try:
        for frame_index, frame in enumerate(frames):
            preview = render_track_preview_frame(frame, tracks, frame_index)
            writer.write(preview)
    finally:
        writer.release()


def draw_tracks_overlay_preview(
    first_frame: np.ndarray,
    tracks: Sequence[PointTrack],
) -> np.ndarray:
    out = first_frame.copy()

    for track in tracks:
        color = TRACK_PALETTE[track.track_id % len(TRACK_PALETTE)]
        if not track.points:
            continue
        pts = [(int(round(p.x)), int(round(p.y))) for p in track.points]
        for i in range(1, len(pts)):
            cv2.line(out, pts[i - 1], pts[i], color, 1, lineType=cv2.LINE_AA)
        cv2.circle(out, pts[0], 4, color, 1, lineType=cv2.LINE_AA)
        cv2.circle(out, pts[-1], 3, color, -1, lineType=cv2.LINE_AA)
    return out


def update_workspace_motion_index_summary(
    root: Path,
    result: MotionIndexResult,
    *,
    group: str,
    batch_name: str,
) -> Path:
    """Append or update one row in metadata/f_actin_motion_index_summary.csv."""
    root = Path(root).resolve()
    summary_path = root / METADATA_DIR / F_ACTIN_MOTION_INDEX_SUMMARY_CSV
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    row = {
        "sample_id": result.sample_id,
        "group": group,
        "batch_name": batch_name,
        "final_export_name": result.final_export_name,
        "source_path": result.source_path,
        "analysis_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "downward_velocity_index_um_per_s": round(
            result.downward_velocity_index_um_per_s, 6
        ),
        "general_movement_index_um_per_s": round(
            result.general_movement_index_um_per_s, 6
        ),
        "num_tracks_started": len(result.tracks),
        "num_tracks_with_valid_steps": result.num_tracks_with_valid_steps,
        "total_valid_steps": result.total_valid_steps,
        "mean_track_length_frames": round(result.mean_track_length_frames, 3),
        "frame_count": result.frame_count,
        "trajectory_csv": result.trajectory_csv,
        "summary_json": result.summary_json,
        "track_preview": result.track_preview_video,
    }

    existing_rows: list[dict[str, Any]] = []
    if summary_path.is_file():
        with summary_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for item in reader:
                existing_rows.append(item)

    key = (result.sample_id, result.final_export_name)
    updated = False
    for item in existing_rows:
        if (item.get("sample_id"), item.get("final_export_name")) == key:
            item.update({k: str(v) for k, v in row.items()})
            updated = True
            break
    if not updated:
        existing_rows.append({k: str(v) for k, v in row.items()})

    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MOTION_INDEX_SUMMARY_COLUMNS)
        writer.writeheader()
        for item in existing_rows:
            writer.writerow({col: item.get(col, "") for col in MOTION_INDEX_SUMMARY_COLUMNS})
    return summary_path


def save_motion_index_outputs(
    *,
    output_dir: Path,
    final_export_name: str,
    first_frame: np.ndarray,
    frames: Sequence[np.ndarray],
    starting_points: Sequence[tuple[float, float]],
    tracks: Sequence[PointTrack],
    result: MotionIndexResult,
    preview_fps: float = 5.0,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = motion_index_output_paths(output_dir, final_export_name)

    save_trajectory_csv(paths["trajectory_csv"], tracks)

    cv2.imwrite(
        str(paths["starting_points"]),
        draw_start_points_preview(first_frame, starting_points),
    )
    cv2.imwrite(
        str(paths["track_overlay"]),
        draw_tracks_overlay_preview(first_frame, tracks),
    )

    preview_error = ""
    try:
        write_track_preview_video(
            paths["track_preview"],
            frames,
            tracks,
            fps=preview_fps,
        )
    except OSError as exc:
        preview_error = str(exc)

    result.track_preview_error = preview_error
    summary_payload = result.summary_dict()
    summary_payload["written_at_utc"] = _utc_now_iso()
    paths["summary_json"].write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    return {
        "trajectory_csv": str(paths["trajectory_csv"]),
        "summary_json": str(paths["summary_json"]),
        "start_points_preview": str(paths["starting_points"]),
        "tracks_overlay_preview": str(paths["track_overlay"]),
        "track_preview_video": str(paths["track_preview"]),
        "track_preview_error": preview_error,
    }


def run_motion_index_analysis(
    source: str | Path,
    *,
    output_dir: str | Path | None = None,
    final_export_name: str | None = None,
    sample_id: str = "",
    params: MotionIndexParams | None = None,
    preview_fps: float = 5.0,
    frame_paths: Sequence[Path] | None = None,
) -> MotionIndexResult:
    """
    Run the full motion-index workflow on one processed ROI video or image sequence.
    """
    params = params or MotionIndexParams()
    source_path = Path(source).resolve()
    export_name = (final_export_name or source_path.stem).strip()
    out_dir = (
        Path(output_dir).resolve()
        if output_dir
        else _default_output_dir(source_path, export_name)
    )

    patch = _odd_size(params.template_patch_size_px)
    radius = int(params.search_radius_px)
    min_dim = patch + (2 * radius) + 2

    if frame_paths:
        frames, _loader_meta = load_frames_from_paths(frame_paths)
    else:
        frames, _loader_meta = load_frame_sequence(source_path)
    first_frame = frames[0]
    h, w = first_frame.shape[:2]
    h_crop, w_crop = h, w
    if min(h, w) < min_dim:
        raise ValueError(
            f"Cropped ROI ({w}x{h} px) is too small for patch size "
            f"{patch} and search radius {radius}."
        )

    starting_points = select_starting_points(first_frame, params)
    if not starting_points:
        raise ValueError("No bright starting points found in the first frame.")

    tracks = track_points(frames, starting_points, params)
    if not any(len(t.points) >= 2 for t in tracks):
        raise ValueError("No tracks survived with valid motion steps.")

    downward_index, general_index, track_summaries = compute_motion_indices(tracks, params)
    valid_tracks, total_steps, mean_len = compute_track_statistics(tracks)

    result = MotionIndexResult(
        source_path=str(source_path),
        output_dir=str(out_dir),
        frame_count=len(frames),
        frame_width=w,
        frame_height=h,
        params=params,
        tracks=tracks,
        trajectory_csv="",
        summary_json="",
        start_points_preview="",
        tracks_overlay_preview="",
        track_preview_video="",
        downward_velocity_index_um_per_s=downward_index,
        general_movement_index_um_per_s=general_index,
        track_summaries=track_summaries,
        final_export_name=export_name,
        sample_id=sample_id,
        num_tracks_with_valid_steps=valid_tracks,
        total_valid_steps=total_steps,
        mean_track_length_frames=mean_len,
    )

    outputs = save_motion_index_outputs(
        output_dir=out_dir,
        final_export_name=export_name,
        first_frame=first_frame,
        frames=frames,
        starting_points=starting_points,
        tracks=tracks,
        result=result,
        preview_fps=preview_fps,
    )

    result.trajectory_csv = outputs["trajectory_csv"]
    result.summary_json = outputs["summary_json"]
    result.start_points_preview = outputs["start_points_preview"]
    result.tracks_overlay_preview = outputs["tracks_overlay_preview"]
    result.track_preview_video = outputs["track_preview_video"]
    result.track_preview_error = outputs.get("track_preview_error", "")
    return result


def run_motion_index_test(
    source: str | Path,
    *,
    output_dir: str | Path | None = None,
    final_export_name: str | None = None,
    params: MotionIndexParams | None = None,
) -> dict[str, Any]:
    """
    Convenience wrapper for manual testing before GUI integration.

    Prints a short summary and returns the analysis payload.
    """
    result = run_motion_index_analysis(
        source,
        output_dir=output_dir,
        final_export_name=final_export_name,
        params=params,
    )
    print(f"Source: {result.source_path}")
    print(f"Frames: {result.frame_count} ({result.frame_width}x{result.frame_height})")
    print(f"Tracks started: {len(result.tracks)}")
    print(
        "Downward Velocity Index: "
        f"{result.downward_velocity_index_um_per_s:.4f} um/s"
    )
    print(
        "General Movement Index: "
        f"{result.general_movement_index_um_per_s:.4f} um/s"
    )
    print(f"Trajectory CSV: {result.trajectory_csv}")
    print(f"Summary JSON: {result.summary_json}")
    print(f"Start points preview: {result.start_points_preview}")
    print(f"Tracks overlay preview: {result.tracks_overlay_preview}")
    print(f"Track preview video: {result.track_preview_video}")
    if result.track_preview_error:
        print(f"Track preview warning: {result.track_preview_error}")
    return result.summary_dict()
