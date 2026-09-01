"""Orientation state, rectangular ROI, and canonical coordinate transforms.

Coordinate spaces
-----------------
raw_frame_pixels
    Pixel coordinates of the imported frame before orientation. Legacy ROI
    persistence uses the alias ``original_frame_pixels`` for this space.

oriented_frame_pixels
    Pixel coordinates after ``apply_orientation()``. This is the canonical
    space for RectROI (computational crop), Region geometry, NucleusReference,
    and CutoffBoundary.

crop_local_pixels
    Coordinates relative to a RectROI crop: ``(x - roi.x, y - roi.y)``.
    Tracking and metric code operate in this space.

canvas_display
    Widget/display coordinates in the preview canvas. UI-only; never persist.

``apply_orientation()`` operation order (do not change, do not drift):

    1. rotation          (``rotate_image_and_mask`` / warpAffine)
    2. mirror_y_axis     (``cv2.flip(..., 1)`` — horizontal flip)
    3. flipped_180       (``cv2.rotate(..., ROTATE_180)``)

Inverse point/ROI maps undo those operations in reverse order.
Point helpers keep float precision. ROI helpers treat rectangles as half-open
pixel sets ``[x, x+width) × [y, y+height)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from actintrack_app.image_processing import apply_flip, rotate_image_and_mask

# Canonical coordinate-space names. Persist scientific geometry in oriented
# frame pixels. raw_frame_pixels is the imported frame; original_frame_pixels
# is the legacy persistence alias for that same space.
COORDINATE_SPACE_RAW_FRAME_PIXELS = "raw_frame_pixels"
COORDINATE_SPACE_ORIGINAL_FRAME_PIXELS = "original_frame_pixels"
COORDINATE_SPACE_ORIENTED_FRAME_PIXELS = "oriented_frame_pixels"
COORDINATE_SPACE_CROP_LOCAL_PIXELS = "crop_local_pixels"
COORDINATE_SPACE_CANVAS_DISPLAY = "canvas_display"

_ANGLE_EPS = 1e-6


@dataclass
class RectROI:
    """Axis-aligned computational crop in oriented-frame pixels (x, y, width, height).

    RectROI is the product-facing crop. It is not a scientific CellRegion.
    Bounds are half-open: columns ``[x, x+width)`` and rows ``[y, y+height)``.
    """

    x: int
    y: int
    width: int
    height: int

    def as_dict(self) -> dict[str, int]:
        return {
            "x": int(self.x),
            "y": int(self.y),
            "width": int(self.width),
            "height": int(self.height),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RectROI:
        if "width" in data and "height" in data:
            return cls(
                int(data["x"]),
                int(data["y"]),
                int(data["width"]),
                int(data["height"]),
            )
        x0 = int(data.get("x0", data.get("x", 0)))
        y0 = int(data.get("y0", data.get("y", 0)))
        x1 = int(data.get("x1", x0 + int(data.get("width", 0))))
        y1 = int(data.get("y1", y0 + int(data.get("height", 0))))
        return cls(x0, y0, max(1, x1 - x0), max(1, y1 - y0))

    @classmethod
    def from_xyxy(cls, x0: int, y0: int, x1: int, y1: int) -> RectROI:
        return cls(
            min(x0, x1),
            min(y0, y1),
            max(1, abs(x1 - x0)),
            max(1, abs(y1 - y0)),
        )

    @property
    def x1(self) -> int:
        return self.x + self.width

    @property
    def y1(self) -> int:
        return self.y + self.height

    def clamp(self, image_width: int, image_height: int) -> RectROI:
        w, h = int(image_width), int(image_height)
        x = max(0, min(self.x, w - 1))
        y = max(0, min(self.y, h - 1))
        width = max(1, min(self.width, w - x))
        height = max(1, min(self.height, h - y))
        return RectROI(x, y, width, height)

    def crop_slice(self) -> tuple[slice, slice]:
        return slice(self.y, self.y + self.height), slice(self.x, self.x + self.width)


@dataclass
class OrientationState:
    rotation_angle_degrees: float = 0.0
    flipped_180: bool = False
    mirror_y_axis: bool = False
    manual_rotation_steps: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "rotation_angle_degrees": float(self.rotation_angle_degrees),
            "flipped_180": bool(self.flipped_180),
            "mirror_y_axis": bool(self.mirror_y_axis),
            "manual_rotation_steps": list(self.manual_rotation_steps),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OrientationState:
        steps = data.get("manual_rotation_steps") or []
        if isinstance(steps, str):
            steps = [steps] if steps else []
        return cls(
            rotation_angle_degrees=float(data.get("rotation_angle_degrees") or 0.0),
            flipped_180=bool(data.get("flipped_180")),
            mirror_y_axis=bool(data.get("mirror_y_axis")),
            manual_rotation_steps=[str(s) for s in steps],
        )


def apply_orientation(image: np.ndarray, state: OrientationState) -> np.ndarray:
    """Apply rotation, then optional y-axis mirror, then optional 180° flip.

    Operation order is part of the coordinate contract and must stay aligned
    with ``raw_point_to_oriented`` / ``oriented_point_to_raw``:

        rotation → mirror_y_axis → flipped_180

    ``mirror_y_axis`` is a horizontal flip (``cv2.flip(image, 1)``).
    Image resampling behavior here must not change.
    """
    import cv2

    out = image
    angle = float(state.rotation_angle_degrees)
    if abs(angle) > _ANGLE_EPS:
        out, _ = rotate_image_and_mask(out, None, angle)
    if state.mirror_y_axis:
        out = cv2.flip(out, 1)
    if state.flipped_180:
        out = apply_flip(out, True)
    return out


def crop_rect_roi(image: np.ndarray, roi: RectROI) -> np.ndarray:
    roi = roi.clamp(image.shape[1], image.shape[0])
    sy, sx = roi.crop_slice()
    return image[sy, sx].copy()


def scale_roi_to_frame(
    roi: RectROI,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
    method: str,
) -> RectROI:
    """Map ROI from source oriented frame to target oriented frame dimensions."""
    if source_width == target_width and source_height == target_height:
        return roi.clamp(target_width, target_height)

    if method == "same_coordinates":
        return roi.clamp(target_width, target_height)

    sx = target_width / max(1, source_width)
    sy = target_height / max(1, source_height)
    scaled = RectROI(
        int(round(roi.x * sx)),
        int(round(roi.y * sy)),
        max(1, int(round(roi.width * sx))),
        max(1, int(round(roi.height * sy))),
    )
    return scaled.clamp(target_width, target_height)


def tracking_crop_to_rect(crop: Any) -> RectROI:
    """Convert legacy TrackingCrop to RectROI."""
    return RectROI.from_xyxy(int(crop.x0), int(crop.y0), int(crop.x1), int(crop.y1))


def rotation_affine_matrix(
    raw_width: int,
    raw_height: int,
    angle_deg: float,
) -> tuple[np.ndarray, int, int]:
    """Return the warpAffine matrix used by ``rotate_image_and_mask``.

    The expanded canvas size matches ``apply_orientation()`` after the rotation
    step (before mirror / 180). Positive angles are counter-clockwise.
    """
    import cv2

    orig_w, orig_h = int(raw_width), int(raw_height)
    center = (orig_w / 2.0, orig_h / 2.0)
    matrix = cv2.getRotationMatrix2D(center, float(angle_deg), 1.0)
    cos = abs(matrix[0, 0])
    sin = abs(matrix[0, 1])
    new_w = int(orig_h * sin + orig_w * cos)
    new_h = int(orig_h * cos + orig_w * sin)
    matrix[0, 2] += (new_w / 2.0) - center[0]
    matrix[1, 2] += (new_h / 2.0) - center[1]
    return matrix, new_w, new_h


def oriented_frame_size(
    raw_width: int,
    raw_height: int,
    state: OrientationState,
) -> tuple[int, int]:
    """Oriented-frame ``(width, height)`` matching ``apply_orientation()`` output."""
    angle = float(state.rotation_angle_degrees)
    if abs(angle) > _ANGLE_EPS:
        _matrix, rot_w, rot_h = rotation_affine_matrix(raw_width, raw_height, angle)
        return int(rot_w), int(rot_h)
    return int(raw_width), int(raw_height)


def _rotation_size(
    raw_width: int,
    raw_height: int,
    state: OrientationState,
) -> tuple[np.ndarray | None, int, int]:
    angle = float(state.rotation_angle_degrees)
    if abs(angle) > _ANGLE_EPS:
        matrix, rot_w, rot_h = rotation_affine_matrix(raw_width, raw_height, angle)
        return matrix, int(rot_w), int(rot_h)
    return None, int(raw_width), int(raw_height)


def _apply_affine(x: float, y: float, matrix: np.ndarray) -> tuple[float, float]:
    import cv2

    pts = np.array([[[float(x), float(y)]]], dtype=np.float64)
    out = cv2.transform(pts, matrix)
    return float(out[0, 0, 0]), float(out[0, 0, 1])


def raw_point_to_oriented(
    x: float,
    y: float,
    *,
    raw_width: int,
    raw_height: int,
    state: OrientationState,
) -> tuple[float, float]:
    """Map a point from raw_frame_pixels to oriented_frame_pixels.

    Order matches ``apply_orientation()``: rotation → mirror_y_axis → flipped_180.
    ``mirror_y_axis`` uses the pixel-index horizontal flip ``x' = width - 1 - x``.
    """
    xo, yo = float(x), float(y)
    matrix, rot_w, rot_h = _rotation_size(raw_width, raw_height, state)
    if matrix is not None:
        xo, yo = _apply_affine(xo, yo, matrix)
    if state.mirror_y_axis:
        xo = rot_w - 1.0 - xo
    if state.flipped_180:
        xo = rot_w - 1.0 - xo
        yo = rot_h - 1.0 - yo
    return xo, yo


def oriented_point_to_raw(
    x: float,
    y: float,
    *,
    raw_width: int,
    raw_height: int,
    state: OrientationState,
) -> tuple[float, float]:
    """Map a point from oriented_frame_pixels to raw_frame_pixels.

    Inverse of ``raw_point_to_oriented``: undo flipped_180, then mirror_y_axis,
    then inverse rotation.
    """
    import cv2

    xo, yo = float(x), float(y)
    matrix, rot_w, rot_h = _rotation_size(raw_width, raw_height, state)
    if state.flipped_180:
        xo = rot_w - 1.0 - xo
        yo = rot_h - 1.0 - yo
    if state.mirror_y_axis:
        xo = rot_w - 1.0 - xo
    if matrix is not None:
        inv = cv2.invertAffineTransform(matrix)
        xo, yo = _apply_affine(xo, yo, inv)
    return xo, yo


def _roi_after_rotation(
    roi: RectROI,
    matrix: np.ndarray | None,
    rot_w: int,
    rot_h: int,
) -> RectROI:
    """Map a half-open rectangle through the rotation affine only."""
    if matrix is None:
        return roi
    corners = (
        (float(roi.x), float(roi.y)),
        (float(roi.x1), float(roi.y)),
        (float(roi.x1), float(roi.y1)),
        (float(roi.x), float(roi.y1)),
    )
    mapped = [_apply_affine(cx, cy, matrix) for cx, cy in corners]
    xs = [p[0] for p in mapped]
    ys = [p[1] for p in mapped]
    x0 = int(round(min(xs)))
    y0 = int(round(min(ys)))
    x1 = int(round(max(xs)))
    y1 = int(round(max(ys)))
    return RectROI.from_xyxy(x0, y0, x1, y1).clamp(rot_w, rot_h)


def _roi_horizontal_flip(roi: RectROI, frame_width: int) -> RectROI:
    """Half-open horizontal flip matching ``cv2.flip(..., 1)``."""
    return RectROI(
        int(frame_width) - roi.x - roi.width,
        roi.y,
        roi.width,
        roi.height,
    )


def _roi_rotate_180(roi: RectROI, frame_width: int, frame_height: int) -> RectROI:
    """Half-open 180° matching ``cv2.rotate(..., ROTATE_180)``."""
    return RectROI(
        int(frame_width) - roi.x - roi.width,
        int(frame_height) - roi.y - roi.height,
        roi.width,
        roi.height,
    )


def raw_roi_to_oriented(
    roi: RectROI,
    *,
    raw_width: int,
    raw_height: int,
    state: OrientationState,
) -> RectROI:
    """Map a RectROI from raw_frame_pixels to oriented_frame_pixels."""
    matrix, rot_w, rot_h = _rotation_size(raw_width, raw_height, state)
    oriented = _roi_after_rotation(roi, matrix, rot_w, rot_h)
    if state.mirror_y_axis:
        oriented = _roi_horizontal_flip(oriented, rot_w)
    if state.flipped_180:
        oriented = _roi_rotate_180(oriented, rot_w, rot_h)
    return oriented.clamp(rot_w, rot_h)


def oriented_roi_to_raw(
    roi: RectROI,
    *,
    raw_width: int,
    raw_height: int,
    state: OrientationState,
) -> RectROI:
    """Map a RectROI from oriented_frame_pixels to raw_frame_pixels."""
    import cv2

    matrix, rot_w, rot_h = _rotation_size(raw_width, raw_height, state)
    raw_rect = roi
    if state.flipped_180:
        raw_rect = _roi_rotate_180(raw_rect, rot_w, rot_h)
    if state.mirror_y_axis:
        raw_rect = _roi_horizontal_flip(raw_rect, rot_w)
    if matrix is not None:
        inv = cv2.invertAffineTransform(matrix)
        raw_rect = _roi_after_rotation(raw_rect, inv, int(raw_width), int(raw_height))
    return raw_rect.clamp(int(raw_width), int(raw_height))


def oriented_xy_to_crop_local(
    x: float,
    y: float,
    crop: RectROI,
) -> tuple[float, float]:
    """Convert oriented-frame XY to crop-local pixels for ``crop``."""
    return float(x) - float(crop.x), float(y) - float(crop.y)


def crop_local_xy_to_oriented(
    x: float,
    y: float,
    crop: RectROI,
) -> tuple[float, float]:
    """Convert crop-local pixels to oriented-frame XY for ``crop``."""
    return float(x) + float(crop.x), float(y) + float(crop.y)


def oriented_y_to_crop_local(y: float, crop: RectROI) -> float:
    """Convert an oriented-frame horizontal boundary y to crop-local y."""
    return float(y) - float(crop.y)


def crop_local_y_to_oriented(y: float, crop: RectROI) -> float:
    """Convert a crop-local horizontal boundary y to oriented-frame y."""
    return float(y) + float(crop.y)
