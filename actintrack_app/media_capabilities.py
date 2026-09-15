"""Explicit sample media type and metric capability policy.

ActinTrackCV distinguishes two scientifically distinct media classes:

VIDEO — temporal motion metrics (General Movement, Optical Flow, Toward Nucleus)
IMAGE — static structural F-actin Orientation

Metric availability derives from media capabilities, not ad-hoc filename checks
scattered through the GUI. Persist ``media_type`` at import; fall back to path
classification only for pre-MEDIA1 samples.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Optional


class SampleMediaType(str, Enum):
    VIDEO = "video"
    IMAGE = "image"


class MetricId(str, Enum):
    GENERAL_MOVEMENT = "general_movement"
    OPTICAL_FLOW = "optical_flow"
    TOWARD_NUCLEUS = "toward_nucleus"
    ORIENTATION = "orientation"


# Product import formats for MEDIA1 (case-insensitive via Path.suffix.lower()).
PRODUCT_VIDEO_EXTENSIONS = frozenset({".avi", ".mp4"})
PRODUCT_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".tif", ".tiff"})
PRODUCT_MEDIA_EXTENSIONS = PRODUCT_VIDEO_EXTENSIONS | PRODUCT_IMAGE_EXTENSIONS

UNSUPPORTED_MEDIA_MESSAGE = (
    "Unsupported file type. Supported formats: "
    "AVI, MP4 (video); JPG, JPEG, TIF, TIFF (image)."
)


@dataclass(frozen=True)
class SampleCapabilities:
    """Scientific metric availability for one media class."""

    media_type: SampleMediaType
    supports_general_movement: bool
    supports_optical_flow: bool
    supports_toward_nucleus: bool
    supports_orientation: bool
    requires_video_timing: bool
    requires_nucleus_for_run: bool
    toward_nucleus_requires_nucleus: bool
    orientation_requires_nucleus: bool

    def supports(self, metric: MetricId) -> bool:
        return {
            MetricId.GENERAL_MOVEMENT: self.supports_general_movement,
            MetricId.OPTICAL_FLOW: self.supports_optical_flow,
            MetricId.TOWARD_NUCLEUS: self.supports_toward_nucleus,
            MetricId.ORIENTATION: self.supports_orientation,
        }[metric]

    @property
    def is_video(self) -> bool:
        return self.media_type is SampleMediaType.VIDEO

    @property
    def is_image(self) -> bool:
        return self.media_type is SampleMediaType.IMAGE

    @property
    def metric_analysis_modes(self) -> tuple[str, ...]:
        """Inspection mode ids exposed in Metric Analysis for this media."""
        if self.is_video:
            return ("template", "optical_flow")
        return ("orientation",)


VIDEO_CAPABILITIES = SampleCapabilities(
    media_type=SampleMediaType.VIDEO,
    supports_general_movement=True,
    supports_optical_flow=True,
    supports_toward_nucleus=True,
    supports_orientation=False,
    requires_video_timing=True,
    requires_nucleus_for_run=False,
    toward_nucleus_requires_nucleus=True,
    orientation_requires_nucleus=False,
)

IMAGE_CAPABILITIES = SampleCapabilities(
    media_type=SampleMediaType.IMAGE,
    supports_general_movement=False,
    supports_optical_flow=False,
    supports_toward_nucleus=False,
    supports_orientation=True,
    requires_video_timing=False,
    requires_nucleus_for_run=True,
    toward_nucleus_requires_nucleus=False,
    orientation_requires_nucleus=True,
)


def capabilities_for(media_type: SampleMediaType) -> SampleCapabilities:
    if media_type is SampleMediaType.IMAGE:
        return IMAGE_CAPABILITIES
    return VIDEO_CAPABILITIES


def classify_media_path(path: str | Path) -> Optional[SampleMediaType]:
    """Return VIDEO/IMAGE for product formats, else None."""
    ext = Path(path).suffix.lower()
    if ext in PRODUCT_VIDEO_EXTENSIONS:
        return SampleMediaType.VIDEO
    if ext in PRODUCT_IMAGE_EXTENSIONS:
        return SampleMediaType.IMAGE
    return None


def is_product_media_path(path: str | Path) -> bool:
    return classify_media_path(path) is not None


def parse_media_type(value: Any) -> Optional[SampleMediaType]:
    text = str(value or "").strip().lower()
    if text in ("video", SampleMediaType.VIDEO.value):
        return SampleMediaType.VIDEO
    if text in ("image", SampleMediaType.IMAGE.value):
        return SampleMediaType.IMAGE
    return None


def media_type_from_sample_row(
    row: Mapping[str, Any] | None,
    *,
    fallback_path: str | Path | None = None,
) -> SampleMediaType:
    """Resolve media type from persisted fields, then path, then video flags."""
    if row:
        explicit = parse_media_type(row.get("media_type"))
        if explicit is not None:
            return explicit
        file_type = str(row.get("file_type", "")).strip().lower()
        if file_type == "video":
            return SampleMediaType.VIDEO
        if file_type in ("image", "tiff"):
            return SampleMediaType.IMAGE
        is_video = str(row.get("is_video", "")).strip().lower() == "true"
        if is_video:
            return SampleMediaType.VIDEO
        stored = str(row.get("stored_path") or row.get("original_filename") or "").strip()
        if stored:
            classified = classify_media_path(stored)
            if classified is not None:
                return classified
    if fallback_path is not None:
        classified = classify_media_path(fallback_path)
        if classified is not None:
            return classified
    return SampleMediaType.VIDEO


def capabilities_for_sample_row(
    row: Mapping[str, Any] | None,
    *,
    fallback_path: str | Path | None = None,
) -> SampleCapabilities:
    return capabilities_for(
        media_type_from_sample_row(row, fallback_path=fallback_path)
    )


def media_type_label(media_type: SampleMediaType) -> str:
    return "Video" if media_type is SampleMediaType.VIDEO else "Image"
