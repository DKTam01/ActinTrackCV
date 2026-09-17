"""Classify files for the 2D import workflow vs unsupported formats."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from actintrack_app.media_capabilities import (
    PRODUCT_IMAGE_EXTENSIONS,
    PRODUCT_VIDEO_EXTENSIONS,
    SampleMediaType,
    UNSUPPORTED_MEDIA_MESSAGE,
    classify_media_path,
)
from actintrack_app.utils import RAW_MICROSCOPY_EXTENSIONS

WIP_MESSAGE = (
    "Raw / 3D microscopy formats (.oib, .oif, .oir) are not supported in the "
    "current 2D workflow."
)

UNSUPPORTED_2D_MESSAGE = UNSUPPORTED_MEDIA_MESSAGE

MIXED_MESSAGE = (
    "Cannot import unsupported formats together with scientific media. "
    "Import AVI/MP4 videos and JPG/JPEG/PNG/TIF/TIFF images only."
)

# Kept for older call sites; multi-file video import is now supported via
# create_samples_from_data_files (one Sample per file).
MULTI_VIDEO_MESSAGE = (
    "Select only one .avi or .mp4 data file at a time for import."
)


class ImportKind(str, Enum):
    IMAGE = "image"
    IMAGE_SEQUENCE = "image_sequence"  # legacy label; unused for successful import
    VIDEO = "video"
    WIP_RAW_3D = "wip_raw_3d"
    MIXED = "mixed"
    EMPTY = "empty"


def _per_file_kind(path: Path) -> str:
    media = classify_media_path(path)
    if media is SampleMediaType.VIDEO:
        return "video"
    if media is SampleMediaType.IMAGE:
        return "image"
    ext = path.suffix.lower()
    if ext in RAW_MICROSCOPY_EXTENSIONS:
        return "wip"
    return "unknown"


def classify_paths(paths: list[Path]) -> tuple[ImportKind, list[Path], str]:
    """
    Return (kind, valid_paths, user_message).

    message is empty when selection is valid for import.
    Mixed VIDEO+IMAGE selections are valid: callers import one Sample per file.
    """
    files = [Path(p).resolve() for p in paths if Path(p).is_file()]
    if not files:
        return ImportKind.EMPTY, [], "No data selected."

    kinds = {_per_file_kind(p) for p in files}
    if "unknown" in kinds or "unsupported_image" in kinds:
        unknown = [
            p.name
            for p in files
            if _per_file_kind(p) in {"unknown", "unsupported_image"}
        ]
        return (
            ImportKind.MIXED,
            [],
            f"Unsupported file type: {', '.join(unknown[:3])}. "
            f"{UNSUPPORTED_MEDIA_MESSAGE}",
        )

    if kinds & {"wip"}:
        if kinds <= {"wip"}:
            return ImportKind.WIP_RAW_3D, files, WIP_MESSAGE
        return ImportKind.MIXED, [], WIP_MESSAGE + "\n\n" + MIXED_MESSAGE

    if kinds <= {"video"}:
        return ImportKind.VIDEO, files, ""

    if kinds <= {"image"}:
        return ImportKind.IMAGE, files, ""

    if kinds <= {"video", "image"}:
        # Mixed scientific media is allowed for batch import (one Sample each).
        return ImportKind.MIXED, files, ""

    return ImportKind.MIXED, [], UNSUPPORTED_2D_MESSAGE


def import_kind_label(kind: ImportKind) -> str:
    labels = {
        ImportKind.IMAGE: "Static image — JPG/JPEG/PNG/TIF/TIFF (orientation)",
        ImportKind.IMAGE_SEQUENCE: "Postponed — image sequence (not importable)",
        ImportKind.VIDEO: "Video — AVI/MP4 timelapse (motion metrics)",
        ImportKind.WIP_RAW_3D: "Postponed — raw / 3D microscopy (not importable)",
        ImportKind.MIXED: "Mixed scientific media or invalid selection",
        ImportKind.EMPTY: "No data selected",
    }
    return labels.get(kind, str(kind.value))


def is_supported_product_extension(path: Path) -> bool:
    ext = path.suffix.lower()
    return ext in PRODUCT_VIDEO_EXTENSIONS or ext in PRODUCT_IMAGE_EXTENSIONS
