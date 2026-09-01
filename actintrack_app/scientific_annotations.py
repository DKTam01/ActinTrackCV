"""Scientific annotation types in oriented-frame pixels.

NucleusReference and CutoffBoundary are persistence/geometry primitives for
later tracker and metric phases. They are not GUI controls and they are not
CellRegion.

Canonical storage space is oriented_frame_pixels. Absence means unknown:
callers must not invent a default nucleus or cutoff.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from actintrack_app.orientation import (
    COORDINATE_SPACE_ORIENTED_FRAME_PIXELS,
    RectROI,
    crop_local_xy_to_oriented,
    crop_local_y_to_oriented,
    oriented_xy_to_crop_local,
    oriented_y_to_crop_local,
)

ANNOTATION_FIELD_NUCLEUS_REFERENCE = "nucleus_reference"
ANNOTATION_FIELD_CUTOFF_BOUNDARY = "cutoff_boundary"


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
