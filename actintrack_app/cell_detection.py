"""Conservative whole-cell CellRegion suggestion.

This is not filament segmentation. The detector favors over-inclusion so that
uncertain background is preferred over excluding real cell/F-actin.
``segment_cell()`` is not used: it is an Otsu+open orientation helper and is
too aggressive for a scientific validity domain.
"""

from __future__ import annotations

import numpy as np

from actintrack_app.image_processing import actin_signal_image
from actintrack_app.orientation import RectROI
from actintrack_app.region import RegionValidationError, validate_region
from actintrack_app.scientific_annotations import (
    CELL_REGION_SOURCE_AUTO,
    CellRegion,
    fallback_cell_region,
)


def suggest_conservative_cell_region(
    oriented_frame: np.ndarray,
    *,
    fallback_rect: RectROI | None = None,
) -> CellRegion:
    """Return a conservative CellRegion in oriented-frame pixels.

    On failure, falls back to ``fallback_rect`` (computational crop) if given,
    otherwise the full oriented frame. Never returns an empty region.
    """
    fh, fw = int(oriented_frame.shape[0]), int(oriented_frame.shape[1])
    try:
        cell = _detect_conservative_cell_region(oriented_frame)
        validate_region(cell.region, fw, fh)
        bbox = cell.bounding_box()
        if bbox.width < 4 or bbox.height < 4:
            raise ValueError("Detected CellRegion is too small.")
        return cell
    except (ValueError, RegionValidationError):
        return fallback_cell_region(
            frame_width=fw, frame_height=fh, crop=fallback_rect
        )


def _detect_conservative_cell_region(oriented_frame: np.ndarray) -> CellRegion:
    import cv2

    signal, _source = actin_signal_image(oriented_frame)
    signal_u8 = (signal * 255).astype(np.uint8)
    otsu_value, _ = cv2.threshold(
        signal_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    # Lower than tracking-crop detection: include dim cell body / halo.
    threshold = max(0.02, min(0.08, float(otsu_value / 255.0) * 0.30))
    mask = (signal > threshold).astype(np.uint8)
    close_k = np.ones((7, 7), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_k, iterations=3)
    dilate_k = np.ones((5, 5), dtype=np.uint8)
    mask = cv2.dilate(mask, dilate_k, iterations=2)

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
    hull = cv2.convexHull(largest)
    vertices = _unique_hull_vertices(
        hull, frame_width=int(oriented_frame.shape[1]),
        frame_height=int(oriented_frame.shape[0]),
    )
    return CellRegion.from_polygon(vertices, source=CELL_REGION_SOURCE_AUTO)


def _unique_hull_vertices(
    hull: np.ndarray,
    *,
    frame_width: int,
    frame_height: int,
) -> list[tuple[int, int]]:
    pts: list[tuple[int, int]] = []
    for item in np.asarray(hull).reshape(-1, 2):
        x = max(0, min(int(round(item[0])), frame_width - 1))
        y = max(0, min(int(round(item[1])), frame_height - 1))
        if not pts or pts[-1] != (x, y):
            pts.append((x, y))
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    pts = _drop_consecutive_collinear(pts)
    if len(pts) < 3:
        raise ValueError("Convex hull collapsed below three vertices.")
    return pts


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
