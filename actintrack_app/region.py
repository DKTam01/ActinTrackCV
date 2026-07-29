"""Region geometry domain model (rectangle and polygon) in oriented-frame pixels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence

import cv2
import numpy as np

from actintrack_app.orientation import RectROI
from actintrack_app.roi_workflow import ORIENTED_ROI_COORDINATE_SPACE, roi_oriented_as_dict

RegionGeometryType = Literal["rectangle", "polygon"]

GEOMETRY_TYPE_RECTANGLE: RegionGeometryType = "rectangle"
GEOMETRY_TYPE_POLYGON: RegionGeometryType = "polygon"

ANNOTATION_FIELD_GEOMETRY_TYPE = "region_geometry_type"
ANNOTATION_FIELD_POLYGON_ROI = "polygon_roi"


class RegionValidationError(ValueError):
    """Raised when Region geometry is invalid or annotation data is malformed."""


@dataclass(frozen=True)
class Region:
    """Immutable Region in oriented-frame pixel coordinates."""

    geometry_type: RegionGeometryType
    rectangle: RectROI | None = None
    vertices: tuple[tuple[int, int], ...] | None = None

    def __post_init__(self) -> None:
        if self.geometry_type == GEOMETRY_TYPE_RECTANGLE:
            if self.rectangle is None:
                raise RegionValidationError("Rectangle Region requires a RectROI.")
            if self.vertices is not None:
                raise RegionValidationError(
                    "Rectangle Region cannot carry polygon vertices."
                )
        elif self.geometry_type == GEOMETRY_TYPE_POLYGON:
            if self.vertices is None:
                raise RegionValidationError("Polygon Region requires vertices.")
            if self.rectangle is not None:
                raise RegionValidationError(
                    "Polygon Region cannot carry an authoritative RectROI."
                )
        else:
            raise RegionValidationError(
                f"Unknown geometry type: {self.geometry_type!r}."
            )

    @classmethod
    def from_rect(cls, rect: RectROI) -> Region:
        return cls(geometry_type=GEOMETRY_TYPE_RECTANGLE, rectangle=rect)

    @classmethod
    def from_polygon(cls, vertices: Sequence[Sequence[int]]) -> Region:
        normalized = _normalize_vertices(vertices)
        return cls(geometry_type=GEOMETRY_TYPE_POLYGON, vertices=normalized)

    @classmethod
    def from_annotation(cls, annotation: dict[str, Any]) -> Region:
        """Parse Region from sample annotation fields (additive polygon-aware)."""
        geom_type = annotation.get(ANNOTATION_FIELD_GEOMETRY_TYPE)
        has_rectangle = bool(annotation.get("rectangle_roi"))
        has_polygon_field = ANNOTATION_FIELD_POLYGON_ROI in annotation

        if geom_type is None:
            if has_polygon_field and not has_rectangle:
                raise RegionValidationError(
                    "polygon_roi present without region_geometry_type; "
                    "legacy annotations require rectangle_roi."
                )
            if has_rectangle:
                rect = RectROI.from_dict(annotation["rectangle_roi"])
                return cls.from_rect(rect)
            raise RegionValidationError(
                "Annotation has no rectangle_roi and no recognized Region geometry."
            )

        if geom_type == GEOMETRY_TYPE_RECTANGLE:
            if not has_rectangle:
                raise RegionValidationError(
                    "region_geometry_type is 'rectangle' but rectangle_roi is missing."
                )
            if has_polygon_field:
                raise RegionValidationError(
                    "Conflicting rectangle_roi and polygon_roi payloads."
                )
            return cls.from_rect(RectROI.from_dict(annotation["rectangle_roi"]))

        if geom_type == GEOMETRY_TYPE_POLYGON:
            if not has_polygon_field:
                raise RegionValidationError(
                    "region_geometry_type is 'polygon' but polygon_roi is missing."
                )
            polygon_data = annotation[ANNOTATION_FIELD_POLYGON_ROI]
            if not isinstance(polygon_data, dict):
                raise RegionValidationError("polygon_roi must be a mapping.")
            raw_vertices = polygon_data.get("vertices")
            if raw_vertices is None:
                raise RegionValidationError("polygon_roi.vertices is required.")
            space = polygon_data.get(
                "roi_coordinate_space", ORIENTED_ROI_COORDINATE_SPACE
            )
            if space != ORIENTED_ROI_COORDINATE_SPACE:
                raise RegionValidationError(
                    f"Unsupported polygon roi_coordinate_space: {space!r}."
                )
            return cls.from_polygon(raw_vertices)

        raise RegionValidationError(
            f"Unknown region_geometry_type: {geom_type!r}."
        )

    def bounding_box(self) -> RectROI:
        if self.geometry_type == GEOMETRY_TYPE_RECTANGLE:
            return self.rectangle  # type: ignore[return-value]
        return _polygon_bounding_box(self.vertices)  # type: ignore[arg-type]

    def rasterize_crop_mask(self) -> np.ndarray:
        if self.geometry_type == GEOMETRY_TYPE_RECTANGLE:
            rect = self.rectangle
            return np.ones((rect.height, rect.width), dtype=np.bool_)
        bbox = self.bounding_box()
        return _rasterize_polygon_mask(self.vertices, bbox)  # type: ignore[arg-type]

    def geometry_key(self) -> tuple[Any, ...]:
        if self.geometry_type == GEOMETRY_TYPE_RECTANGLE:
            rect = self.rectangle
            return (
                GEOMETRY_TYPE_RECTANGLE,
                rect.x,
                rect.y,
                rect.width,
                rect.height,
            )
        return (GEOMETRY_TYPE_POLYGON, self.vertices)

    def to_annotation_fields(self) -> dict[str, Any]:
        if self.geometry_type == GEOMETRY_TYPE_RECTANGLE:
            return {"rectangle_roi": roi_oriented_as_dict(self.rectangle)}
        return {
            ANNOTATION_FIELD_GEOMETRY_TYPE: GEOMETRY_TYPE_POLYGON,
            ANNOTATION_FIELD_POLYGON_ROI: _polygon_to_dict(self.vertices),
        }


def validate_region(
    region: Region,
    frame_width: int,
    frame_height: int,
) -> None:
    """Validate Region against oriented-frame dimensions; raise on failure."""
    fw, fh = int(frame_width), int(frame_height)
    if fw <= 0 or fh <= 0:
        raise RegionValidationError("Frame dimensions must be positive.")

    if region.geometry_type == GEOMETRY_TYPE_RECTANGLE:
        _validate_rectangle(region.rectangle, fw, fh)
        return

    _validate_polygon_vertices(region.vertices, fw, fh)
    bbox = region.bounding_box()
    _validate_rectangle(bbox, fw, fh, label="Polygon bounding box")
    mask = region.rasterize_crop_mask()
    if not np.any(mask):
        raise RegionValidationError("Polygon rasterizes to an empty inclusion mask.")


def _normalize_vertices(
    vertices: Sequence[Sequence[int]],
) -> tuple[tuple[int, int], ...]:
    if not vertices:
        raise RegionValidationError("Polygon requires at least three vertices.")
    out: list[tuple[int, int]] = []
    for item in vertices:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise RegionValidationError(
                "Each polygon vertex must be a pair of integers."
            )
        try:
            x, y = int(item[0]), int(item[1])
        except (TypeError, ValueError) as exc:
            raise RegionValidationError(
                "Polygon vertex coordinates must be integers."
            ) from exc
        out.append((x, y))
    if len(out) < 3:
        raise RegionValidationError("Polygon requires at least three vertices.")
    if len(out) >= 2 and out[0] == out[-1]:
        raise RegionValidationError(
            "Polygon closure vertex must not be repeated at the end."
        )
    return tuple(out)


def _validate_rectangle(
    rect: RectROI | None,
    frame_width: int,
    frame_height: int,
    *,
    label: str = "Region",
) -> None:
    if rect is None:
        raise RegionValidationError(f"{label} rectangle is missing.")
    if rect.width <= 0 or rect.height <= 0:
        raise RegionValidationError(f"{label} width and height must be positive.")
    if rect.x < 0 or rect.y < 0:
        raise RegionValidationError(f"{label} has negative coordinates.")
    if rect.x + rect.width > frame_width or rect.y + rect.height > frame_height:
        raise RegionValidationError(f"{label} extends outside frame bounds.")


def _validate_polygon_vertices(
    vertices: tuple[tuple[int, int], ...] | None,
    frame_width: int,
    frame_height: int,
) -> None:
    if vertices is None:
        raise RegionValidationError("Polygon vertices are missing.")

    if len(vertices) < 3:
        raise RegionValidationError("Polygon requires at least three vertices.")

    for i, (x, y) in enumerate(vertices):
        if x < 0 or y < 0:
            raise RegionValidationError(
                f"Polygon vertex {i} has negative coordinates."
            )
        if x >= frame_width or y >= frame_height:
            raise RegionValidationError(
                f"Polygon vertex {i} is outside frame bounds."
            )

    for i in range(len(vertices)):
        if vertices[i] == vertices[(i + 1) % len(vertices)]:
            raise RegionValidationError("Polygon has duplicate consecutive vertices.")

    unique = set(vertices)
    if len(unique) < 3:
        raise RegionValidationError(
            "Polygon requires at least three unique vertices."
        )

    for i in range(len(vertices)):
        for j in range(i + 2, len(vertices)):
            if j == len(vertices) - 1 and i == 0:
                continue
            if vertices[i] == vertices[j]:
                raise RegionValidationError(
                    "Polygon has a repeated non-consecutive vertex."
                )

    for i in range(len(vertices)):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % len(vertices)]
        if x1 == x2 and y1 == y2:
            raise RegionValidationError("Polygon has a zero-length edge.")

    if _all_collinear(vertices):
        raise RegionValidationError("Polygon vertices are all collinear.")

    signed_area = _signed_area(vertices)
    if abs(signed_area) < 1e-9:
        raise RegionValidationError("Polygon has zero area.")

    if _has_self_intersection(vertices):
        raise RegionValidationError("Polygon is self-intersecting.")

    if _has_overlapping_collinear_edges(vertices):
        raise RegionValidationError(
            "Polygon has overlapping non-adjacent collinear edges."
        )


def _polygon_bounding_box(
    vertices: tuple[tuple[int, int], ...],
) -> RectROI:
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return RectROI(
        min_x,
        min_y,
        max_x - min_x + 1,
        max_y - min_y + 1,
    )


def _polygon_to_dict(
    vertices: tuple[tuple[int, int], ...] | None,
) -> dict[str, Any]:
    if vertices is None:
        raise RegionValidationError("Polygon vertices are missing.")
    return {
        "vertices": [[x, y] for x, y in vertices],
        "roi_coordinate_space": ORIENTED_ROI_COORDINATE_SPACE,
    }


def _rasterize_polygon_mask(
    vertices: tuple[tuple[int, int], ...],
    bbox: RectROI,
) -> np.ndarray:
    """
    Crop-local boolean mask for polygon inclusion.

    Contract:
    - Integer vertices are oriented-frame pixel (column, row) coordinates.
    - Inclusion is evaluated at pixel centers (col + 0.5, row + 0.5).
    - Polygon boundaries are inclusive (on-edge centers are inside).
    - Mask shape is (bbox.height, bbox.width), dtype numpy.bool_.
  """
    h, w = bbox.height, bbox.width
    mask = np.zeros((h, w), dtype=np.bool_)
    contour = np.array(vertices, dtype=np.float32)
    for row in range(h):
        cy = bbox.y + row + 0.5
        for col in range(w):
            cx = bbox.x + col + 0.5
            if cv2.pointPolygonTest(contour, (cx, cy), False) >= 0.0:
                mask[row, col] = True
    return mask


def _signed_area(vertices: tuple[tuple[int, int], ...]) -> float:
    area = 0.0
    n = len(vertices)
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return area / 2.0


def _all_collinear(vertices: tuple[tuple[int, int], ...]) -> bool:
    if len(vertices) < 3:
        return True
    x0, y0 = vertices[0]
    x1, y1 = vertices[1]
    for x2, y2 in vertices[2:]:
        cross = (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0)
        if abs(cross) != 0:
            return False
    return True


def _segments_intersect(
    a1: tuple[int, int],
    a2: tuple[int, int],
    b1: tuple[int, int],
    b2: tuple[int, int],
) -> bool:
    def _orient(p, q, r) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def _on_segment(p, q, r) -> bool:
        return (
            min(p[0], r[0]) <= q[0] <= max(p[0], r[0])
            and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])
        )

    o1 = _orient(a1, a2, b1)
    o2 = _orient(a1, a2, b2)
    o3 = _orient(b1, b2, a1)
    o4 = _orient(b1, b2, a2)

    if o1 * o2 < 0 and o3 * o4 < 0:
        return True

    # Collinear overlap cases for non-adjacent edges are handled separately.
    if o1 == 0 and _on_segment(a1, b1, a2):
        return True
    if o2 == 0 and _on_segment(a1, b2, a2):
        return True
    if o3 == 0 and _on_segment(b1, a1, b2):
        return True
    if o4 == 0 and _on_segment(b1, a2, b2):
        return True
    return False


def _has_self_intersection(vertices: tuple[tuple[int, int], ...]) -> bool:
    n = len(vertices)
    edges = [
        (vertices[i], vertices[(i + 1) % n]) for i in range(n)
    ]
    for i, (a1, a2) in enumerate(edges):
        for j in range(i + 1, n):
            if j == i:
                continue
            if abs(i - j) <= 1 or (i == 0 and j == n - 1):
                continue
            b1, b2 = edges[j]
            if _segments_intersect(a1, a2, b1, b2):
                return True
    return False


def _edge_collinear_overlap(
    a1: tuple[int, int],
    a2: tuple[int, int],
    b1: tuple[int, int],
    b2: tuple[int, int],
) -> bool:
    def _orient(p, q, r) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    if _orient(a1, a2, b1) != 0 or _orient(a1, a2, b2) != 0:
        return False

    axis = 0 if a1[0] != a2[0] or b1[0] != b2[0] else 1
    a_lo = min(a1[axis], a2[axis])
    a_hi = max(a1[axis], a2[axis])
    b_lo = min(b1[axis], b2[axis])
    b_hi = max(b1[axis], b2[axis])
    overlap_lo = max(a_lo, b_lo)
    overlap_hi = min(a_hi, b_hi)
    return overlap_hi > overlap_lo


def _has_overlapping_collinear_edges(
    vertices: tuple[tuple[int, int], ...],
) -> bool:
    n = len(vertices)
    edges = [
        (vertices[i], vertices[(i + 1) % n]) for i in range(n)
    ]
    for i, (a1, a2) in enumerate(edges):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            b1, b2 = edges[j]
            if _edge_collinear_overlap(a1, a2, b1, b2):
                return True
    return False
