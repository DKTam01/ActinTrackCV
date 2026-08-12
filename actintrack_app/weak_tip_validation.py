"""Validation-only diagnostics for weak filament tip detection and tracking.

This module exercises the production motion-index tracker unchanged. It does not
modify workspace persistence, GUI workflow, or scientific defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import cv2
import numpy as np

from actintrack_app.motion_index import (
    MotionIndexParams,
    PointTrack,
    draw_start_points_preview,
    frame_to_signal,
    render_track_preview_frame,
    select_starting_points,
    track_points,
)

# Reuse private helpers read-only for candidate ranking diagnostics only.
from actintrack_app.motion_index import (  # noqa: PLC2701
    _bright_region_centroid,
    _local_maxima_mask,
    _odd_size,
    _starting_point_valid_mask,
)


@dataclass(frozen=True)
class TipAnnotation:
    """Expected filament tip location for validation (test-only, not persisted)."""

    frame_index: int
    x: float
    y: float
    tolerance_px: float
    label: str
    note: str = ""


@dataclass(frozen=True)
class WeakTipFixture:
    """Deterministic frame sequence plus expected tip ground truth."""

    name: str
    frames: tuple[np.ndarray, ...]
    tips: tuple[TipAnnotation, ...]
    description: str = ""
    competitor: TipAnnotation | None = None


@dataclass(frozen=True)
class RankedCandidate:
    rank: int
    x: float
    y: float
    signal: float
    selected: bool


@dataclass(frozen=True)
class CandidateDiagnostic:
    tip: TipAnnotation
    nearest_start: tuple[float, float] | None
    distance_px: float
    within_tolerance: bool
    nearest_rank: int | None
    nearest_signal: float | None
    expected_signal: float


@dataclass(frozen=True)
class FrameTrackDiagnostic:
    frame_index: int
    x: float
    y: float
    confidence: float
    distance_to_expected_px: float


@dataclass(frozen=True)
class TrackingDiagnostic:
    tip: TipAnnotation
    track_id: int | None
    frames: tuple[FrameTrackDiagnostic, ...]
    survival_frames: int
    lost_frame: int | None
    jumped_to_competitor: bool
    min_distance_to_expected_px: float
    final_distance_to_expected_px: float


@dataclass(frozen=True)
class FixtureBaselineResult:
    fixture_name: str
    candidate_diagnostics: tuple[CandidateDiagnostic, ...]
    tracking_diagnostics: tuple[TrackingDiagnostic, ...]
    starting_points: tuple[tuple[float, float], ...]
    tracks: tuple[PointTrack, ...]
    candidate_recall: float
    mean_endpoint_error_px: float | None
    precision_proxy: float | None


DEFAULT_VALIDATION_PARAMS = MotionIndexParams(
    num_starting_points=5,
    min_point_spacing_px=12,
    search_radius_px=8,
    template_patch_size_px=11,
    min_template_confidence=0.55,
    microns_per_pixel=1.0,
    seconds_per_frame=1.0,
)


def _distance(x0: float, y0: float, x1: float, y1: float) -> float:
    return float(np.hypot(x0 - x1, y0 - y1))


def _bgr_from_gray(gray: np.ndarray) -> np.ndarray:
    clipped = np.clip(gray, 0, 255).astype(np.uint8)
    return cv2.cvtColor(clipped, cv2.COLOR_GRAY2BGR)


def _draw_tapering_filament(
    shape: tuple[int, int],
    *,
    start_xy: tuple[float, float],
    end_xy: tuple[float, float],
    start_intensity: float,
    end_intensity: float,
    width_px: float = 2.0,
    background: float = 10.0,
) -> np.ndarray:
    """Return a grayscale filament whose brightness tapers toward ``end_xy``."""
    h, w = shape
    image = np.full((h, w), background, dtype=np.float32)
    length = max(1.0, _distance(start_xy[0], start_xy[1], end_xy[0], end_xy[1]))
    steps = int(max(2, round(length * 2)))
    for i in range(steps + 1):
        t = i / steps
        x = start_xy[0] + (t * (end_xy[0] - start_xy[0]))
        y = start_xy[1] + (t * (end_xy[1] - start_xy[1]))
        intensity = start_intensity + (t * (end_intensity - start_intensity))
        cv2.line(
            image,
            (int(round(x)), int(round(y))),
            (int(round(x)), int(round(y))),
            float(intensity),
            thickness=max(1, int(round(width_px))),
            lineType=cv2.LINE_AA,
        )
    return image


def bright_control_fixture(*, seed: int = 20260812) -> WeakTipFixture:
    """Bright isolated spot the current detector should already seed."""
    _ = seed
    gray = np.full((96, 112), 12.0, dtype=np.float32)
    cx, cy = 56.0, 48.0
    yy, xx = np.mgrid[0:96, 0:112]
    gray += 200.0 * np.exp(-(((xx - cx) ** 2) + ((yy - cy) ** 2)) / (2.0 * 1.4**2))
    frame = _bgr_from_gray(gray)
    tip = TipAnnotation(
        frame_index=0,
        x=cx,
        y=cy,
        tolerance_px=4.0,
        label="bright_control",
        note="bright_control",
    )
    return WeakTipFixture(
        name="bright_control",
        frames=(frame,),
        tips=(tip,),
        description="Isolated bright Gaussian spot.",
    )


def tapering_filament_fixture(*, seed: int = 20260812) -> WeakTipFixture:
    """Filament brightness decreases toward one endpoint."""
    _ = seed
    gray = _draw_tapering_filament(
        (96, 112),
        start_xy=(24.0, 48.0),
        end_xy=(86.0, 48.0),
        start_intensity=220.0,
        end_intensity=28.0,
        width_px=2.5,
    )
    frame = _bgr_from_gray(gray)
    tip = TipAnnotation(
        frame_index=0,
        x=86.0,
        y=48.0,
        tolerance_px=5.0,
        label="weak_tip",
        note="weak_tip",
    )
    return WeakTipFixture(
        name="tapering_filament",
        frames=(frame,),
        tips=(tip,),
        description="Brightness tapers toward the right endpoint.",
    )


def bleaching_sequence_fixture(
    *,
    seed: int = 20260812,
    frame_count: int = 8,
) -> WeakTipFixture:
    """A moving bright feature that bleaches over successive frames."""
    _ = seed
    frames: list[np.ndarray] = []
    path_x = np.linspace(24.0, 24.0 + (2.0 * (frame_count - 1)), frame_count)
    path_y = np.linspace(48.0, 48.0 + (1.0 * (frame_count - 1)), frame_count)
    for index in range(frame_count):
        peak = 220.0 * max(0.12, 1.0 - (0.11 * index))
        gray = np.full((96, 112), 12.0, dtype=np.float32)
        yy, xx = np.mgrid[0:96, 0:112]
        gray += peak * np.exp(
            -(((xx - path_x[index]) ** 2) + ((yy - path_y[index]) ** 2)) / (2.0 * 1.3**2)
        )
        frames.append(_bgr_from_gray(gray))
    tip = TipAnnotation(
        frame_index=0,
        x=float(path_x[0]),
        y=float(path_y[0]),
        tolerance_px=4.0,
        label="bleach_start",
        note="weak_tip",
    )
    return WeakTipFixture(
        name="bleaching_sequence",
        frames=tuple(frames),
        tips=(tip,),
        description="Feature bleaches while drifting diagonally.",
    )


def competing_bright_fixture(*, seed: int = 20260812) -> WeakTipFixture:
    """Weak tapered endpoint beside a much brighter nearby structure."""
    _ = seed
    gray = _draw_tapering_filament(
        (96, 112),
        start_xy=(20.0, 62.0),
        end_xy=(58.0, 62.0),
        start_intensity=95.0,
        end_intensity=24.0,
        width_px=2.0,
    )
    yy, xx = np.mgrid[0:96, 0:112]
    gray += 235.0 * np.exp(-(((xx - 78.0) ** 2) + ((yy - 38.0) ** 2)) / (2.0 * 2.0**2))
    frame = _bgr_from_gray(gray)
    weak_tip = TipAnnotation(
        frame_index=0,
        x=58.0,
        y=62.0,
        tolerance_px=5.0,
        label="weak_tip",
        note="weak_tip",
    )
    competitor = TipAnnotation(
        frame_index=0,
        x=78.0,
        y=38.0,
        tolerance_px=4.0,
        label="bright_competitor",
        note="competitor_nearby",
    )
    return WeakTipFixture(
        name="competing_bright",
        frames=(frame,),
        tips=(weak_tip,),
        competitor=competitor,
        description="Dim taper near a brighter Gaussian bundle.",
    )


def boundary_tip_fixture(*, seed: int = 20260812) -> WeakTipFixture:
    """Thin endpoint close to the crop boundary."""
    _ = seed
    gray = _draw_tapering_filament(
        (96, 112),
        start_xy=(48.0, 48.0),
        end_xy=(102.0, 48.0),
        start_intensity=180.0,
        end_intensity=35.0,
        width_px=2.0,
    )
    frame = _bgr_from_gray(gray)
    tip = TipAnnotation(
        frame_index=0,
        x=100.0,
        y=48.0,
        tolerance_px=5.0,
        label="boundary_tip",
        note="weak_tip",
    )
    return WeakTipFixture(
        name="boundary_tip",
        frames=(frame,),
        tips=(tip,),
        description="Tapering endpoint near the right image border.",
    )


def all_weak_tip_fixtures() -> tuple[WeakTipFixture, ...]:
    return (
        bright_control_fixture(),
        tapering_filament_fixture(),
        bleaching_sequence_fixture(),
        competing_bright_fixture(),
        boundary_tip_fixture(),
    )


def enumerate_starting_point_candidates(
    first_frame: np.ndarray,
    params: MotionIndexParams,
) -> list[RankedCandidate]:
    """Mirror production starting-point ranking without mutating selection logic."""
    signal = frame_to_signal(first_frame)
    h, w = signal.shape[:2]
    patch = _odd_size(max(3, params.template_patch_size_px))
    half = patch // 2
    valid_mask = _starting_point_valid_mask(signal)
    mask = _local_maxima_mask(signal, patch_size=5)
    ys, xs = np.where(mask)
    if ys.size == 0:
        return []

    scores = signal[ys, xs]
    order = np.argsort(scores)[::-1]
    selected_coords: list[tuple[float, float]] = []
    min_dist = float(params.min_point_spacing_px)
    min_dist_sq = min_dist * min_dist
    ranked: list[RankedCandidate] = []

    for rank_index, idx in enumerate(order, start=1):
        x = float(xs[idx])
        y = float(ys[idx])
        refined_x, refined_y = _bright_region_centroid(
            signal,
            x,
            y,
            radius_px=max(2, half),
        )
        cx_i = int(round(refined_x))
        cy_i = int(round(refined_y))
        eligible = (
            0 <= cx_i < w
            and 0 <= cy_i < h
            and valid_mask[cy_i, cx_i]
            and refined_x >= half
            and refined_y >= half
            and refined_x < w - half
            and refined_y < h - half
        )
        too_close = False
        if eligible:
            for sx, sy in selected_coords:
                dx = refined_x - sx
                dy = refined_y - sy
                if (dx * dx) + (dy * dy) < min_dist_sq:
                    too_close = True
                    break
        selected = False
        if eligible and not too_close and len(selected_coords) < params.num_starting_points:
            selected_coords.append((refined_x, refined_y))
            selected = True
        ranked.append(
            RankedCandidate(
                rank=rank_index,
                x=refined_x,
                y=refined_y,
                signal=float(signal[cy_i, cx_i]) if eligible else float(scores[idx]),
                selected=selected,
            )
        )
    return ranked


def diagnose_candidates(
    first_frame: np.ndarray,
    tips: Sequence[TipAnnotation],
    params: MotionIndexParams,
    *,
    starting_points: Sequence[tuple[float, float]] | None = None,
) -> list[CandidateDiagnostic]:
    """Report how production starting-point selection relates to expected tips."""
    signal = frame_to_signal(first_frame)
    starts = (
        list(starting_points)
        if starting_points is not None
        else select_starting_points(first_frame, params)
    )
    ranked = enumerate_starting_point_candidates(first_frame, params)
    diagnostics: list[CandidateDiagnostic] = []

    for tip in tips:
        if tip.frame_index != 0:
            diagnostics.append(
                CandidateDiagnostic(
                    tip=tip,
                    nearest_start=None,
                    distance_px=float("inf"),
                    within_tolerance=False,
                    nearest_rank=None,
                    nearest_signal=None,
                    expected_signal=float(
                        signal[
                            int(np.clip(round(tip.y), 0, signal.shape[0] - 1)),
                            int(np.clip(round(tip.x), 0, signal.shape[1] - 1)),
                        ]
                    ),
                )
            )
            continue

        nearest_start: tuple[float, float] | None = None
        nearest_distance = float("inf")
        for start in starts:
            dist = _distance(start[0], start[1], tip.x, tip.y)
            if dist < nearest_distance:
                nearest_distance = dist
                nearest_start = start

        nearest_rank: int | None = None
        nearest_signal: float | None = None
        best_candidate_distance = float("inf")
        for candidate in ranked:
            dist = _distance(candidate.x, candidate.y, tip.x, tip.y)
            if dist < best_candidate_distance:
                best_candidate_distance = dist
                nearest_rank = candidate.rank
                nearest_signal = candidate.signal

        expected_y = int(np.clip(round(tip.y), 0, signal.shape[0] - 1))
        expected_x = int(np.clip(round(tip.x), 0, signal.shape[1] - 1))
        diagnostics.append(
            CandidateDiagnostic(
                tip=tip,
                nearest_start=nearest_start,
                distance_px=nearest_distance if nearest_start is not None else float("inf"),
                within_tolerance=(
                    nearest_start is not None and nearest_distance <= tip.tolerance_px
                ),
                nearest_rank=nearest_rank,
                nearest_signal=nearest_signal,
                expected_signal=float(signal[expected_y, expected_x]),
            )
        )
    return diagnostics


def _find_track_for_start(
    tracks: Sequence[PointTrack],
    start_xy: tuple[float, float],
    *,
    tolerance_px: float = 3.0,
) -> PointTrack | None:
    best: PointTrack | None = None
    best_distance = float("inf")
    for track in tracks:
        dist = _distance(track.start_x, track.start_y, start_xy[0], start_xy[1])
        if dist < best_distance:
            best_distance = dist
            best = track
    if best is None or best_distance > tolerance_px:
        return None
    return best


def diagnose_tracking(
    frames: Sequence[np.ndarray],
    tip: TipAnnotation,
    tracks: Sequence[PointTrack],
    *,
    starting_point: tuple[float, float] | None,
    competitor: TipAnnotation | None = None,
) -> TrackingDiagnostic:
    """Follow one production track and compare it to expected tip motion."""
    track = (
        _find_track_for_start(tracks, starting_point)
        if starting_point is not None
        else None
    )
    if track is None:
        return TrackingDiagnostic(
            tip=tip,
            track_id=None,
            frames=(),
            survival_frames=0,
            lost_frame=None,
            jumped_to_competitor=False,
            min_distance_to_expected_px=float("inf"),
            final_distance_to_expected_px=float("inf"),
        )

    frame_diag: list[FrameTrackDiagnostic] = []
    min_distance = float("inf")
    jumped = False
    for point in track.points:
        if point.frame_index >= len(frames):
            break
        dist_expected = _distance(point.x, point.y, tip.x, tip.y)
        min_distance = min(min_distance, dist_expected)
        frame_diag.append(
            FrameTrackDiagnostic(
                frame_index=point.frame_index,
                x=point.x,
                y=point.y,
                confidence=point.confidence,
                distance_to_expected_px=dist_expected,
            )
        )
        if competitor is not None and point.frame_index > 0:
            dist_competitor = _distance(point.x, point.y, competitor.x, competitor.y)
            dist_expected_now = dist_expected
            if dist_competitor + 2.0 < dist_expected_now:
                jumped = True

    lost_frame: int | None = None
    if track.end_reason.startswith("lost_at_frame_"):
        try:
            lost_frame = int(track.end_reason.rsplit("_", maxsplit=1)[-1])
        except ValueError:
            lost_frame = None
    survival = len(frame_diag)
    final_distance = frame_diag[-1].distance_to_expected_px if frame_diag else float("inf")
    return TrackingDiagnostic(
        tip=tip,
        track_id=track.track_id,
        frames=tuple(frame_diag),
        survival_frames=survival,
        lost_frame=lost_frame,
        jumped_to_competitor=jumped,
        min_distance_to_expected_px=min_distance,
        final_distance_to_expected_px=final_distance,
    )


def candidate_recall(diagnostics: Sequence[CandidateDiagnostic]) -> float:
    if not diagnostics:
        return 0.0
    hits = sum(1 for item in diagnostics if item.within_tolerance)
    return hits / len(diagnostics)


def mean_endpoint_error_px(diagnostics: Sequence[CandidateDiagnostic]) -> float | None:
    distances = [item.distance_px for item in diagnostics if np.isfinite(item.distance_px)]
    if not distances:
        return None
    return float(np.mean(distances))


def candidate_precision_proxy(
    first_frame: np.ndarray,
    tips: Sequence[TipAnnotation],
    params: MotionIndexParams,
    *,
    intended_notes: set[str] | None = None,
) -> float | None:
    """Fraction of selected starts associated with an intended structure."""
    notes = intended_notes or {"bright_control", "weak_tip", "competitor_nearby"}
    selected = [
        candidate
        for candidate in enumerate_starting_point_candidates(first_frame, params)
        if candidate.selected
    ]
    if not selected:
        return None
    hits = 0
    for candidate in selected:
        for tip in tips:
            if tip.note not in notes:
                continue
            if _distance(candidate.x, candidate.y, tip.x, tip.y) <= tip.tolerance_px:
                hits += 1
                break
    return hits / len(selected)


def run_fixture_baseline(
    fixture: WeakTipFixture,
    params: MotionIndexParams | None = None,
) -> FixtureBaselineResult:
    """Run unchanged production selection + tracking and summarize diagnostics."""
    params = params or DEFAULT_VALIDATION_PARAMS
    first_frame = fixture.frames[0]
    starts = select_starting_points(first_frame, params)
    tracks = track_points(fixture.frames, starts, params) if len(fixture.frames) >= 2 else []
    candidate_diag = diagnose_candidates(
        first_frame,
        fixture.tips,
        params,
        starting_points=starts,
    )
    tracking_diag: list[TrackingDiagnostic] = []
    for tip in fixture.tips:
        nearest: tuple[float, float] | None = None
        for diagnostic in candidate_diag:
            if diagnostic.tip.label == tip.label:
                nearest = diagnostic.nearest_start
                break
        tracking_diag.append(
            diagnose_tracking(
                fixture.frames,
                tip,
                tracks,
                starting_point=nearest,
                competitor=fixture.competitor,
            )
        )
    recall = candidate_recall(candidate_diag)
    endpoint_error = mean_endpoint_error_px(candidate_diag)
    precision = candidate_precision_proxy(first_frame, fixture.tips, params)
    return FixtureBaselineResult(
        fixture_name=fixture.name,
        candidate_diagnostics=tuple(candidate_diag),
        tracking_diagnostics=tuple(tracking_diag),
        starting_points=tuple(starts),
        tracks=tuple(tracks),
        candidate_recall=recall,
        mean_endpoint_error_px=endpoint_error,
        precision_proxy=precision,
    )


def render_diagnostic_overlay(
    frame: np.ndarray,
    tips: Sequence[TipAnnotation],
    starting_points: Sequence[tuple[float, float]],
    tracks: Sequence[PointTrack],
    frame_index: int,
) -> np.ndarray:
    """Debug-only overlay: expected tips, seeds, and tracked positions."""
    if tracks:
        out = render_track_preview_frame(frame, tracks, frame_index)
    else:
        out = frame.copy()
    out = draw_start_points_preview(out, starting_points)
    for tip in tips:
        if tip.frame_index != frame_index:
            continue
        center = (int(round(tip.x)), int(round(tip.y)))
        cv2.circle(out, center, int(round(tip.tolerance_px)), (0, 180, 255), 1, lineType=cv2.LINE_AA)
        cv2.drawMarker(
            out,
            center,
            (0, 180, 255),
            markerType=cv2.MARKER_CROSS,
            markerSize=12,
            thickness=1,
            line_type=cv2.LINE_AA,
        )
        cv2.putText(
            out,
            tip.label,
            (center[0] + 8, center[1] - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 180, 255),
            1,
            cv2.LINE_AA,
        )
    return out


def diagnose_video_frame(
    video_path: str | Path,
    tip: TipAnnotation,
    *,
    frame_index: int = 0,
    params: MotionIndexParams | None = None,
) -> CandidateDiagnostic:
    """Manual diagnostic helper for one annotated tip on a real video frame.

    Requires an explicit ``video_path``; this helper is not used by automated tests.
    """
    path = Path(video_path)
    if not path.is_file():
        raise FileNotFoundError(f"Video not found: {path}")
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        raise OSError(f"Cannot open video: {path}")
    try:
        if frame_index > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
        ok, frame = cap.read()
    finally:
        cap.release()
    if not ok or frame is None:
        raise OSError(f"Cannot read frame {frame_index} from {path}")
    params = params or DEFAULT_VALIDATION_PARAMS
    diagnostics = diagnose_candidates(frame, (tip,), params)
    if not diagnostics:
        raise ValueError("No diagnostics produced for the supplied tip.")
    return diagnostics[0]


def baseline_summary_rows(
    fixtures: Sequence[WeakTipFixture] | None = None,
    params: MotionIndexParams | None = None,
) -> list[dict[str, Any]]:
    """Compact table rows for reporting current tracker behavior."""
    params = params or DEFAULT_VALIDATION_PARAMS
    rows: list[dict[str, Any]] = []
    for fixture in fixtures or all_weak_tip_fixtures():
        result = run_fixture_baseline(fixture, params=params)
        tip = fixture.tips[0]
        candidate = result.candidate_diagnostics[0]
        tracking = result.tracking_diagnostics[0]
        rows.append(
            {
                "fixture": fixture.name,
                "candidate_detected": candidate.within_tolerance,
                "endpoint_error_px": round(candidate.distance_px, 2),
                "track_survival_frames": tracking.survival_frames,
                "jumped_to_competitor": tracking.jumped_to_competitor,
                "lost_frame": tracking.lost_frame,
                "candidate_recall": round(result.candidate_recall, 3),
            }
        )
    return rows
