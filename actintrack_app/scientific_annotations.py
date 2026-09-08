"""Scientific annotation types in oriented-frame pixels.

NucleusReference, CutoffBoundary, and CellRegion are persistence/geometry
primitives for later tracker and metric phases. They are not GUI controls
and CellRegion is not the computational crop (RectROI).

Canonical storage space is oriented_frame_pixels. Absence means unknown:
callers must not invent a default nucleus, cutoff, or narrow cell region.

Effective scientific validity (visualization in R2; tracker consumption in R3):

    CellRegion ∩ {pixels with oriented y <= cutoff.y}

with the existing image convention +y downward, so "above" the cutoff is
the side with smaller y.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from actintrack_app.orientation import (
    COORDINATE_SPACE_ORIENTED_FRAME_PIXELS,
    OrientationState,
    RectROI,
    crop_local_xy_to_oriented,
    crop_local_y_to_oriented,
    oriented_xy_to_crop_local,
    oriented_y_to_crop_local,
    reorient_horizontal_y,
    reorient_point,
    reorient_roi,
)
from actintrack_app.region import (
    GEOMETRY_TYPE_POLYGON,
    GEOMETRY_TYPE_RECTANGLE,
    Region,
    RegionValidationError,
    validate_region,
)

ANNOTATION_FIELD_NUCLEUS_REFERENCE = "nucleus_reference"
ANNOTATION_FIELD_CUTOFF_BOUNDARY = "cutoff_boundary"
ANNOTATION_FIELD_CELL_REGION = "cell_region"

CELL_REGION_SOURCE_AUTO = "auto_suggested"
CELL_REGION_SOURCE_FALLBACK_ROI = "fallback_rect_roi"
CELL_REGION_SOURCE_FALLBACK_FRAME = "fallback_full_frame"


class ScientificAnnotationError(ValueError):
    """Raised when nucleus or cutoff annotation data is invalid."""


def _require_oriented_space(space: str, *, label: str) -> None:
    if space != COORDINATE_SPACE_ORIENTED_FRAME_PIXELS:
        raise ScientificAnnotationError(
            f"{label} coordinate_space must be "
            f"{COORDINATE_SPACE_ORIENTED_FRAME_PIXELS!r}, got {space!r}."
        )


@dataclass(frozen=True)
class NucleusReference:
    """Nucleus-center XY reference in oriented-frame pixels."""

    x: float
    y: float
    coordinate_space: str = COORDINATE_SPACE_ORIENTED_FRAME_PIXELS
    source: str | None = None

    def __post_init__(self) -> None:
        _require_oriented_space(self.coordinate_space, label="NucleusReference")
        object.__setattr__(self, "x", float(self.x))
        object.__setattr__(self, "y", float(self.y))
        if self.source is not None:
            object.__setattr__(self, "source", str(self.source))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "x": float(self.x),
            "y": float(self.y),
            "coordinate_space": self.coordinate_space,
        }
        if self.source:
            payload["source"] = self.source
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NucleusReference:
        if not isinstance(data, dict):
            raise ScientificAnnotationError("nucleus_reference must be a mapping.")
        if "x" not in data or "y" not in data:
            raise ScientificAnnotationError("nucleus_reference requires x and y.")
        try:
            x = float(data["x"])
            y = float(data["y"])
        except (TypeError, ValueError) as exc:
            raise ScientificAnnotationError(
                "nucleus_reference x and y must be numeric."
            ) from exc
        space = str(
            data.get("coordinate_space", COORDINATE_SPACE_ORIENTED_FRAME_PIXELS)
        )
        source = data.get("source")
        return cls(
            x=x,
            y=y,
            coordinate_space=space,
            source=None if source in (None, "") else str(source),
        )

    def to_crop_local(self, crop: RectROI) -> tuple[float, float]:
        return oriented_xy_to_crop_local(self.x, self.y, crop)

    @classmethod
    def from_crop_local(
        cls,
        x: float,
        y: float,
        crop: RectROI,
        *,
        source: str | None = None,
    ) -> NucleusReference:
        ox, oy = crop_local_xy_to_oriented(x, y, crop)
        return cls(x=ox, y=oy, source=source)


@dataclass(frozen=True)
class CutoffBoundary:
    """Researcher-defined horizontal biological boundary in oriented-frame y."""

    y: float
    coordinate_space: str = COORDINATE_SPACE_ORIENTED_FRAME_PIXELS

    def __post_init__(self) -> None:
        _require_oriented_space(self.coordinate_space, label="CutoffBoundary")
        object.__setattr__(self, "y", float(self.y))

    def to_dict(self) -> dict[str, Any]:
        return {
            "y": float(self.y),
            "coordinate_space": self.coordinate_space,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CutoffBoundary:
        if not isinstance(data, dict):
            raise ScientificAnnotationError("cutoff_boundary must be a mapping.")
        if "y" not in data:
            raise ScientificAnnotationError("cutoff_boundary requires y.")
        try:
            y = float(data["y"])
        except (TypeError, ValueError) as exc:
            raise ScientificAnnotationError(
                "cutoff_boundary y must be numeric."
            ) from exc
        space = str(
            data.get("coordinate_space", COORDINATE_SPACE_ORIENTED_FRAME_PIXELS)
        )
        return cls(y=y, coordinate_space=space)

    def to_crop_local(self, crop: RectROI) -> float:
        return oriented_y_to_crop_local(self.y, crop)

    @classmethod
    def from_crop_local(cls, y: float, crop: RectROI) -> CutoffBoundary:
        return cls(y=crop_local_y_to_oriented(y, crop))


def nucleus_reference_from_annotation(
    annotation: dict[str, Any] | None,
) -> NucleusReference | None:
    """Load optional NucleusReference. Missing or null returns None.

    Legacy cutoff_y / analysis_region_coords are never promoted to a nucleus.
    """
    if not annotation:
        return None
    payload = annotation.get(ANNOTATION_FIELD_NUCLEUS_REFERENCE)
    if payload in (None, ""):
        return None
    return NucleusReference.from_dict(payload)


def cutoff_boundary_from_annotation(
    annotation: dict[str, Any] | None,
) -> CutoffBoundary | None:
    """Load optional CutoffBoundary. Missing or null returns None.

    Legacy cutoff_y / cutoff_y_rotated are not equivalent to this type and are
    not auto-promoted. Those fields remain ROI-reconstruction hints only.
    """
    if not annotation:
        return None
    payload = annotation.get(ANNOTATION_FIELD_CUTOFF_BOUNDARY)
    if payload in (None, ""):
        return None
    return CutoffBoundary.from_dict(payload)


@dataclass(frozen=True)
class CellRegion:
    """Pixels considered part of the cell in oriented-frame coordinates.

    Thin semantic wrapper over Region. RectROI remains the computational crop.
    """

    region: Region
    source: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.region, Region):
            raise ScientificAnnotationError("CellRegion requires a Region.")
        if self.region.coordinate_space != COORDINATE_SPACE_ORIENTED_FRAME_PIXELS:
            raise ScientificAnnotationError(
                "CellRegion must use oriented_frame_pixels."
            )
        if self.source is not None:
            object.__setattr__(self, "source", str(self.source))

    @classmethod
    def from_rect(cls, rect: RectROI, *, source: str | None = None) -> CellRegion:
        return cls(region=Region.from_rect(rect), source=source)

    @classmethod
    def from_polygon(
        cls,
        vertices: Sequence[Sequence[int]],
        *,
        source: str | None = None,
    ) -> CellRegion:
        return cls(region=Region.from_polygon(vertices), source=source)

    def bounding_box(self) -> RectROI:
        return self.region.bounding_box()

    def rasterize_crop_mask(self, crop: RectROI) -> np.ndarray:
        return self.region.rasterize_crop_mask(crop)

    def geometry_key(self) -> tuple[Any, ...]:
        return (self.region.geometry_key(), self.source)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "coordinate_space": COORDINATE_SPACE_ORIENTED_FRAME_PIXELS,
            "geometry_type": self.region.geometry_type,
        }
        if self.region.geometry_type == GEOMETRY_TYPE_RECTANGLE:
            rect = self.region.rectangle
            payload["rectangle"] = {
                "x": int(rect.x),
                "y": int(rect.y),
                "width": int(rect.width),
                "height": int(rect.height),
            }
        else:
            payload["vertices"] = [[int(x), int(y)] for x, y in self.region.vertices]
        if self.source:
            payload["source"] = self.source
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CellRegion:
        if not isinstance(data, dict):
            raise ScientificAnnotationError("cell_region must be a mapping.")
        space = str(
            data.get("coordinate_space", COORDINATE_SPACE_ORIENTED_FRAME_PIXELS)
        )
        _require_oriented_space(space, label="CellRegion")
        geom_type = data.get("geometry_type")
        source = data.get("source")
        source_s = None if source in (None, "") else str(source)
        if geom_type == GEOMETRY_TYPE_RECTANGLE:
            rect_data = data.get("rectangle")
            if not isinstance(rect_data, dict):
                raise ScientificAnnotationError(
                    "cell_region rectangle geometry requires rectangle."
                )
            return cls.from_rect(RectROI.from_dict(rect_data), source=source_s)
        if geom_type == GEOMETRY_TYPE_POLYGON:
            vertices = data.get("vertices")
            if vertices is None:
                raise ScientificAnnotationError(
                    "cell_region polygon geometry requires vertices."
                )
            try:
                return cls.from_polygon(vertices, source=source_s)
            except RegionValidationError as exc:
                raise ScientificAnnotationError(str(exc)) from exc
        raise ScientificAnnotationError(
            f"Unknown cell_region geometry_type: {geom_type!r}."
        )


def cell_region_from_annotation(
    annotation: dict[str, Any] | None,
) -> CellRegion | None:
    """Load optional CellRegion. Missing or null returns None.

    Does not interpret rectangle_roi / polygon_roi product fields as CellRegion.
    """
    if not annotation:
        return None
    payload = annotation.get(ANNOTATION_FIELD_CELL_REGION)
    if payload in (None, ""):
        return None
    return CellRegion.from_dict(payload)


def valid_mask_crop_local(
    crop: RectROI,
    *,
    cell_region: CellRegion | None = None,
    cutoff: CutoffBoundary | None = None,
) -> np.ndarray:
    """Crop-local boolean scientific-validity mask.

    Tracking consumes this mask as a hard spatial domain. Visualization uses
    the same function so preview and Run Metrics stay aligned.

    Semantics, +y downward:

        valid = CellRegion ∩ {oriented y <= cutoff.y}

    Missing annotations are conservative, not fabricated exclusions:

    - CellRegion missing: the whole crop is treated as cell (current tracking).
    - CutoffBoundary missing: no hidden y cutoff.
    - Both missing: all-True mask of shape (crop.height, crop.width).

    Cutoff above the crop (cutoff.y < crop.y) yields all-False.
    Cutoff at or below the last crop row excludes nothing via y.
    """
    h, w = int(crop.height), int(crop.width)
    if h <= 0 or w <= 0:
        raise ScientificAnnotationError("Crop dimensions must be positive.")
    if cell_region is None:
        mask = np.ones((h, w), dtype=np.bool_)
    else:
        mask = np.asarray(cell_region.rasterize_crop_mask(crop), dtype=np.bool_)
        if mask.shape != (h, w):
            raise ScientificAnnotationError(
                f"CellRegion crop mask shape {mask.shape} != {(h, w)}."
            )
    if cutoff is None:
        return mask
    oriented_rows = int(crop.y) + np.arange(h)
    row_valid = oriented_rows <= float(cutoff.y)
    return mask & row_valid[:, None]


def scientific_valid_mask_for_tracking(
    crop: RectROI,
    annotation: dict[str, Any] | None,
) -> np.ndarray:
    """Build the static crop-local tracking mask from a saved annotation.

    Missing CellRegion/cutoff keep the R2 fallback semantics (no fabricated
    exclusions). Callers must not silently resize this mask to a different crop.
    """
    return valid_mask_crop_local(
        crop,
        cell_region=cell_region_from_annotation(annotation),
        cutoff=cutoff_boundary_from_annotation(annotation),
    )


def fallback_cell_region(
    *,
    frame_width: int,
    frame_height: int,
    crop: RectROI | None = None,
) -> CellRegion:
    """Conservative fallback: computational crop if present, else full frame.

    Never returns an empty or tiny fabricated region.
    """
    if crop is not None and crop.width > 0 and crop.height > 0:
        return CellRegion.from_rect(crop, source=CELL_REGION_SOURCE_FALLBACK_ROI)
    fw, fh = int(frame_width), int(frame_height)
    if fw <= 0 or fh <= 0:
        raise ScientificAnnotationError(
            "Cannot build a fallback CellRegion without positive frame size."
        )
    return CellRegion.from_rect(
        RectROI(0, 0, fw, fh), source=CELL_REGION_SOURCE_FALLBACK_FRAME
    )


def reorient_nucleus_reference(
    nucleus: NucleusReference | None,
    *,
    raw_width: int,
    raw_height: int,
    old_state: OrientationState,
    new_state: OrientationState,
) -> NucleusReference | None:
    if nucleus is None:
        return None
    x, y = reorient_point(
        nucleus.x,
        nucleus.y,
        raw_width=raw_width,
        raw_height=raw_height,
        old_state=old_state,
        new_state=new_state,
    )
    return NucleusReference(x=x, y=y, source=nucleus.source)


def reorient_cutoff_boundary(
    cutoff: CutoffBoundary | None,
    *,
    old_oriented_width: int,
    raw_width: int,
    raw_height: int,
    old_state: OrientationState,
    new_state: OrientationState,
) -> CutoffBoundary | None:
    if cutoff is None:
        return None
    new_y = reorient_horizontal_y(
        cutoff.y,
        old_oriented_width=old_oriented_width,
        raw_width=raw_width,
        raw_height=raw_height,
        old_state=old_state,
        new_state=new_state,
    )
    if new_y is None:
        return None
    return CutoffBoundary(y=new_y)


def reorient_cell_region(
    cell: CellRegion | None,
    *,
    raw_width: int,
    raw_height: int,
    old_state: OrientationState,
    new_state: OrientationState,
    new_frame_width: int,
    new_frame_height: int,
) -> CellRegion | None:
    if cell is None:
        return None
    region = cell.region
    if region.geometry_type == GEOMETRY_TYPE_RECTANGLE:
        new_rect = reorient_roi(
            region.rectangle,
            raw_width=raw_width,
            raw_height=raw_height,
            old_state=old_state,
            new_state=new_state,
        ).clamp(new_frame_width, new_frame_height)
        return CellRegion.from_rect(new_rect, source=cell.source)
    new_vertices: list[tuple[int, int]] = []
    for x, y in region.vertices:
        nx, ny = reorient_point(
            float(x),
            float(y),
            raw_width=raw_width,
            raw_height=raw_height,
            old_state=old_state,
            new_state=new_state,
        )
        ix = max(0, min(int(round(nx)), int(new_frame_width) - 1))
        iy = max(0, min(int(round(ny)), int(new_frame_height) - 1))
        if not new_vertices or new_vertices[-1] != (ix, iy):
            new_vertices.append((ix, iy))
    try:
        reoriented = CellRegion.from_polygon(new_vertices, source=cell.source)
        validate_region(reoriented.region, new_frame_width, new_frame_height)
        return reoriented
    except (RegionValidationError, ScientificAnnotationError):
        bbox = reorient_roi(
            region.bounding_box(),
            raw_width=raw_width,
            raw_height=raw_height,
            old_state=old_state,
            new_state=new_state,
        ).clamp(new_frame_width, new_frame_height)
        return CellRegion.from_rect(bbox, source=cell.source)
