"""Conservative whole-cell CellRegion suggestion.

This is not filament segmentation. The detector favors over-inclusion so that
uncertain background is preferred over excluding real cell/F-actin.
``segment_cell()`` is not used: it is an Otsu+open orientation helper and is
too aggressive for a scientific validity domain.

A single researcher-facing sensitivity maps onto a coherent set of
threshold/morphology parameters. Sensitivity ``0`` is tighter (excludes more
weak/background pixels); ``1`` is broader (retains more dim cell signal).
The default ``0.5`` keeps the original threshold/morphology mapping.

Geometry uses the external contour of the cleaned largest component, not a
convex hull, so visible cell concavities are not filled with black background.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from actintrack_app.image_processing import actin_signal_image, detect_tracking_crop
from actintrack_app.orientation import RectROI
from actintrack_app.region import RegionValidationError, validate_region
from actintrack_app.scientific_annotations import (
    CELL_REGION_SOURCE_AUTO,
    CUTOFF_SOURCE_AUTO,
    CellRegion,
    CutoffBoundary,
    fallback_cell_region,
)

CELL_DETECTION_VERSION = "conservative_cell_v2"
CONTOUR_MODE_EXTERNAL_APPROX = "external_approx_v1"
CELL_BOUNDARY_SENSITIVITY_DEFAULT = 0.5
CELL_BOUNDARY_SENSITIVITY_TIGHTER = 0.0
CELL_BOUNDARY_SENSITIVITY_BROADER = 1.0
DEFAULT_COMPUTATIONAL_CROP_PADDING_PX = 8

# Default (sensitivity 0.5) — original conservative detector.
_DEFAULT_OTSU_SCALE = 0.30
_DEFAULT_THRESHOLD_MIN = 0.02
_DEFAULT_THRESHOLD_MAX = 0.08
_DEFAULT_CLOSE_ITERATIONS = 3
_DEFAULT_DILATE_ITERATIONS = 2


@dataclass(frozen=True)
class CellDetectionParams:
    """Internal detector parameterization mapped from user sensitivity."""

    otsu_scale: float
    threshold_min: float
    threshold_max: float
    close_iterations: int
    dilate_iterations: int
    version: str = CELL_DETECTION_VERSION
    contour_mode: str = CONTOUR_MODE_EXTERNAL_APPROX

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "otsu_scale": float(self.otsu_scale),
            "threshold_min": float(self.threshold_min),
            "threshold_max": float(self.threshold_max),
            "close_iterations": int(self.close_iterations),
            "dilate_iterations": int(self.dilate_iterations),
            "contour_mode": self.contour_mode,
        }


def clamp_cell_boundary_sensitivity(value: float | None) -> float:
    if value is None:
        return CELL_BOUNDARY_SENSITIVITY_DEFAULT
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return CELL_BOUNDARY_SENSITIVITY_DEFAULT


def _lerp(a: float, b: float, t: float) -> float:
    return float(a) + (float(b) - float(a)) * float(t)


def map_boundary_sensitivity(sensitivity: float | None) -> CellDetectionParams:
    """Map normalized Tighter→Broader sensitivity onto detector parameters.

    Control points are piecewise-linear around the original default at 0.5 so
    the default path does not change scientific inclusion.
    """
    s = clamp_cell_boundary_sensitivity(sensitivity)
    if abs(s - CELL_BOUNDARY_SENSITIVITY_DEFAULT) < 1e-12:
        return CellDetectionParams(
            otsu_scale=_DEFAULT_OTSU_SCALE,
            threshold_min=_DEFAULT_THRESHOLD_MIN,
            threshold_max=_DEFAULT_THRESHOLD_MAX,
            close_iterations=_DEFAULT_CLOSE_ITERATIONS,
            dilate_iterations=_DEFAULT_DILATE_ITERATIONS,
        )
    if s < CELL_BOUNDARY_SENSITIVITY_DEFAULT:
        t = s / CELL_BOUNDARY_SENSITIVITY_DEFAULT
        return CellDetectionParams(
            otsu_scale=_lerp(0.50, _DEFAULT_OTSU_SCALE, t),
            threshold_min=_lerp(0.040, _DEFAULT_THRESHOLD_MIN, t),
            threshold_max=_lerp(0.14, _DEFAULT_THRESHOLD_MAX, t),
            close_iterations=int(round(_lerp(2.0, float(_DEFAULT_CLOSE_ITERATIONS), t))),
            dilate_iterations=int(round(_lerp(0.0, float(_DEFAULT_DILATE_ITERATIONS), t))),
        )
    t = (s - CELL_BOUNDARY_SENSITIVITY_DEFAULT) / (
        1.0 - CELL_BOUNDARY_SENSITIVITY_DEFAULT
    )
    return CellDetectionParams(
        otsu_scale=_lerp(_DEFAULT_OTSU_SCALE, 0.12, t),
        threshold_min=_lerp(_DEFAULT_THRESHOLD_MIN, 0.008, t),
        threshold_max=_lerp(_DEFAULT_THRESHOLD_MAX, 0.035, t),
        close_iterations=int(round(_lerp(float(_DEFAULT_CLOSE_ITERATIONS), 4.0, t))),
        dilate_iterations=int(round(_lerp(float(_DEFAULT_DILATE_ITERATIONS), 4.0, t))),
    )


def detection_parameters_payload(
    sensitivity: float | None,
) -> dict[str, Any]:
    """Persist detector version + mapped parameters for reproducibility."""
    s = clamp_cell_boundary_sensitivity(sensitivity)
    params = map_boundary_sensitivity(s)
    payload = params.as_dict()
    payload["sensitivity"] = s
    return payload


def computational_crop_from_cell_region(
    cell: CellRegion,
    frame_width: int,
    frame_height: int,
    *,
    padding_px: int = DEFAULT_COMPUTATIONAL_CROP_PADDING_PX,
) -> RectROI:
    """Derive an internal RectROI from the CellRegion bounding box + padding."""
    fw, fh = int(frame_width), int(frame_height)
    if fw <= 0 or fh <= 0:
        raise ValueError("Frame dimensions must be positive.")
    bbox = cell.bounding_box()
    pad = max(0, int(padding_px))
    x0 = max(0, int(bbox.x) - pad)
    y0 = max(0, int(bbox.y) - pad)
    x1 = min(fw, int(bbox.x1) + pad)
    y1 = min(fh, int(bbox.y1) + pad)
    width = max(1, x1 - x0)
    height = max(1, y1 - y0)
    return RectROI(x0, y0, width, height).clamp(fw, fh)


@dataclass(frozen=True)
class PreparedCellSignal:
    """Sensitivity-independent actin signal for one oriented frame.

    Threshold/morphology still depend on sensitivity; only signal + Otsu base
    are reusable across Tighter↔Broader adjustments for the same frame.
    """

    frame_key: int
    signal: np.ndarray
    signal_u8: np.ndarray
    otsu_value: float
    shape: tuple[int, int]


def cell_frame_cache_key(oriented_frame: np.ndarray) -> int:
    """Stable-enough identity for in-memory reuse within one sample session."""
    return id(np.asarray(oriented_frame))


def prepare_cell_signal(oriented_frame: np.ndarray) -> PreparedCellSignal:
    """Compute actin signal + Otsu once for sensitivity-independent reuse."""
    import cv2

    frame = np.asarray(oriented_frame)
    signal, _source = actin_signal_image(frame)
    signal_u8 = (signal * 255).astype(np.uint8)
    otsu_value, _ = cv2.threshold(
        signal_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    return PreparedCellSignal(
        frame_key=cell_frame_cache_key(frame),
        signal=signal,
        signal_u8=signal_u8,
        otsu_value=float(otsu_value),
        shape=(int(frame.shape[0]), int(frame.shape[1])),
    )


def suggest_conservative_cell_region(
    oriented_frame: np.ndarray,
    *,
    fallback_rect: RectROI | None = None,
    sensitivity: float | None = None,
    prepared: PreparedCellSignal | None = None,
) -> CellRegion:
    """Return a conservative CellRegion in oriented-frame pixels.

    On failure, falls back to ``fallback_rect`` (computational crop) if given,
    otherwise the full oriented frame. Never returns an empty region.

    When ``prepared`` matches this frame, signal/Otsu are not recomputed —
    only sensitivity-dependent threshold/morphology/contour work runs.
    """
    fh, fw = int(oriented_frame.shape[0]), int(oriented_frame.shape[1])
    params = map_boundary_sensitivity(sensitivity)
    try:
        cell = _detect_conservative_cell_region(
            oriented_frame, params, prepared=prepared
        )
        validate_region(cell.region, fw, fh)
        bbox = cell.bounding_box()
        if bbox.width < 4 or bbox.height < 4:
            raise ValueError("Detected CellRegion is too small.")
        return cell
    except (ValueError, RegionValidationError):
        return fallback_cell_region(
            frame_width=fw, frame_height=fh, crop=fallback_rect
        )


def suggest_default_cutoff_boundary(
    oriented_frame: np.ndarray,
    *,
    cell_region: CellRegion | None = None,
) -> CutoffBoundary | None:
    """Default Measurement Cutoff from the existing tracking-crop heuristic.

    Falls back to 65% of the CellRegion bbox height (inside the detector's
    0.35–0.82 search window) when gradient detection cannot run.
    """
    try:
        crop = detect_tracking_crop(oriented_frame)
        return CutoffBoundary(y=float(crop.cutoff_y), source=CUTOFF_SOURCE_AUTO)
    except ValueError:
        pass
    if cell_region is None:
        return None
    bbox = cell_region.bounding_box()
    y = float(bbox.y) + 0.65 * float(max(1, bbox.height))
    y = max(0.0, min(y, float(oriented_frame.shape[0] - 1)))
    return CutoffBoundary(y=y, source=CUTOFF_SOURCE_AUTO)


def _detect_conservative_cell_region(
    oriented_frame: np.ndarray,
    params: CellDetectionParams,
    *,
    prepared: PreparedCellSignal | None = None,
) -> CellRegion:
    import cv2

    frame = np.asarray(oriented_frame)
    if prepared is not None and prepared.shape == (
        int(frame.shape[0]),
        int(frame.shape[1]),
    ):
        signal = prepared.signal
        otsu_value = prepared.otsu_value
    else:
        prepared_now = prepare_cell_signal(frame)
        signal = prepared_now.signal
        otsu_value = prepared_now.otsu_value
    threshold = max(
        float(params.threshold_min),
        min(float(params.threshold_max), float(otsu_value / 255.0) * float(params.otsu_scale)),
    )
    mask = (signal > threshold).astype(np.uint8)
    close_k = np.ones((7, 7), dtype=np.uint8)
    close_iter = max(0, int(params.close_iterations))
    if close_iter:
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_k, iterations=close_iter)
    dilate_iter = max(0, int(params.dilate_iterations))
    if dilate_iter:
        dilate_k = np.ones((5, 5), dtype=np.uint8)
        mask = cv2.dilate(mask, dilate_k, iterations=dilate_iter)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if n_labels <= 1:
        raise ValueError("No foreground cell-like signal detected.")
    component_idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    area = int(stats[component_idx, cv2.CC_STAT_AREA])
    if area < 50:
        raise ValueError("Detected foreground is too small for a CellRegion.")
    component = (labels == component_idx).astype(np.uint8)
    contours, _ = cv2.findContours(
        component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        raise ValueError("No cell contour found.")
    largest = max(contours, key=cv2.contourArea)
    vertices = _concavity_preserving_contour_vertices(
        largest,
        component=component,
        frame_width=int(frame.shape[1]),
        frame_height=int(frame.shape[0]),
    )
    return CellRegion.from_polygon(vertices, source=CELL_REGION_SOURCE_AUTO)


def _concavity_preserving_contour_vertices(
    contour: np.ndarray,
    *,
    component: np.ndarray,
    frame_width: int,
    frame_height: int,
) -> list[tuple[int, int]]:
    """External contour of the cleaned component, without a convex hull.

    OpenCV contours of real cells can pinch. Persistence requires a simple
    polygon, so we increase polygonal approximation only until the ring is
    valid, preferring the smallest simplification that still covers the
    component. Convex hull is a last-resort fallback, never the default.
    """
    import cv2

    from actintrack_app.region import Region, RegionValidationError, validate_region

    peri = float(cv2.arcLength(contour, True))
    epsilons = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.0, 10.0]
    peri_eps = [0.002 * peri, 0.003 * peri, 0.005 * peri, 0.008 * peri]
    for value in peri_eps:
        if value > epsilons[-1]:
            epsilons.append(value)

    cover_crop = _component_cover_crop(component)

    for epsilon in epsilons:
        approx = cv2.approxPolyDP(contour, float(epsilon), True)
        vertices = _unique_contour_vertices(
            approx, frame_width=frame_width, frame_height=frame_height
        )
        if not _filled_polygon_covers_component_crop(
            vertices, cover_crop, lost_fraction=0.02
        ):
            continue
        try:
            validate_region(
                Region.from_polygon(vertices), frame_width, frame_height
            )
        except (ValueError, RegionValidationError):
            continue
        return vertices

    hull = cv2.convexHull(contour)
    return _unique_contour_vertices(
        hull, frame_width=frame_width, frame_height=frame_height
    )


def _component_cover_crop(component: np.ndarray) -> tuple[np.ndarray, int, int] | None:
    ys, xs = np.where(component.astype(bool))
    if ys.size == 0:
        return None
    y0 = int(ys.min())
    y1 = int(ys.max()) + 1
    x0 = int(xs.min())
    x1 = int(xs.max()) + 1
    return component[y0:y1, x0:x1].astype(bool), x0, y0


def _filled_polygon_covers_component_crop(
    vertices: list[tuple[int, int]],
    cover_crop: tuple[np.ndarray, int, int] | None,
    *,
    lost_fraction: float,
) -> bool:
    import cv2

    if cover_crop is None or len(vertices) < 3:
        return False
    crop, x0, y0 = cover_crop
    filled = np.zeros(crop.shape, dtype=np.uint8)
    local_pts = [(int(x) - x0, int(y) - y0) for (x, y) in vertices]
    pts = np.asarray(local_pts, dtype=np.int32).reshape((-1, 1, 2))
    cv2.fillPoly(filled, [pts], 1)
    kept = int(np.count_nonzero(crop))
    if kept <= 0:
        return False
    lost = int(np.count_nonzero(crop & (filled == 0)))
    return (lost / float(kept)) <= float(lost_fraction)


def _filled_polygon_covers_component(
    vertices: list[tuple[int, int]],
    component: np.ndarray,
    *,
    lost_fraction: float,
) -> bool:
    """Compatibility wrapper; prefers the precomputable bbox-crop path."""
    return _filled_polygon_covers_component_crop(
        vertices,
        _component_cover_crop(component),
        lost_fraction=lost_fraction,
    )


def _unique_contour_vertices(
    contour: np.ndarray,
    *,
    frame_width: int,
    frame_height: int,
) -> list[tuple[int, int]]:
    pts: list[tuple[int, int]] = []
    for item in np.asarray(contour).reshape(-1, 2):
        x = max(0, min(int(round(item[0])), frame_width - 1))
        y = max(0, min(int(round(item[1])), frame_height - 1))
        if not pts or pts[-1] != (x, y):
            pts.append((x, y))
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    pts = _drop_consecutive_collinear(pts)
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    deduped: list[tuple[int, int]] = []
    for pt in pts:
        if not deduped or deduped[-1] != pt:
            deduped.append(pt)
    if len(deduped) >= 2 and deduped[0] == deduped[-1]:
        deduped = deduped[:-1]
    if len(deduped) < 3:
        raise ValueError("Cell contour collapsed below three vertices.")
    return deduped


def _drop_consecutive_collinear(
    vertices: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    n = len(vertices)
    if n < 3:
        return vertices
    kept: list[tuple[int, int]] = []
    for i, pt in enumerate(vertices):
        prev = vertices[(i - 1) % n]
        nxt = vertices[(i + 1) % n]
        cross = (pt[0] - prev[0]) * (nxt[1] - prev[1]) - (pt[1] - prev[1]) * (
            nxt[0] - prev[0]
        )
        if cross != 0:
            kept.append(pt)
    return kept if len(kept) >= 3 else vertices
