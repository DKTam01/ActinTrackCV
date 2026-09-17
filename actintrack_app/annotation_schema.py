"""Build and merge sample annotations.

Additive scientific fields (nucleus_reference, cutoff_boundary, cell_region)
are optional and omitted when absent. RectROI is also optional: an annotation
document may persist scientific state with no computational crop.

Workspace schema version is unchanged: this is backward-compatible JSON,
not a v2→v3 migration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from actintrack_app.orientation import OrientationState, RectROI
from actintrack_app.region import Region
from actintrack_app.roi_workflow import (
    ORIENTED_ROI_COORDINATE_SPACE,
    original_roi_to_oriented,
    roi_from_original_dict,
    roi_oriented_as_dict,
    roi_original_as_dict,
)
from actintrack_app.scientific_calibration import (
    SampleScientificCalibration,
    merge_calibration_into_annotation,
)
from actintrack_app.scientific_annotations import (
    ANNOTATION_FIELD_CELL_BOUNDARY_SENSITIVITY,
    ANNOTATION_FIELD_CELL_DETECTION,
    ANNOTATION_FIELD_CELL_REGION,
    ANNOTATION_FIELD_CUTOFF_BOUNDARY,
    ANNOTATION_FIELD_CUTOFF_CLEARED,
    ANNOTATION_FIELD_NUCLEUS_REFERENCE,
    CellRegion,
    CutoffBoundary,
    NucleusReference,
    cell_region_from_annotation,
    cutoff_boundary_from_annotation,
    nucleus_reference_from_annotation,
)
from actintrack_app.timing_provenance import (
    ANNOTATION_FIELD_TIMING,
    TimingMetadata,
)
from actintrack_app.workflow_state import ANNOTATION_FIELD_CROP_CONFIRMED


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_sample_annotation(
    *,
    sample_id: str,
    group: str,
    batch_name: str = "",
    batch_id: str = "",
    original_file: str,
    stored_raw_path: str,
    reference_frame_index: int,
    orientation: OrientationState,
    roi: RectROI | None = None,
    roi_original: RectROI | None = None,
    original_dimensions: dict[str, int],
    oriented_dimensions: dict[str, int],
    notes: str = "",
    annotation_source: str = "manual",
    suggestion_method: str | None = None,
    roi_method: str = "manual_rectangle",
    segmentation_method: str | None = None,
    segmentation_parameters: dict[str, Any] | None = None,
    cell_mask_path: str | None = None,
    propagated_from: dict[str, Any] | None = None,
    processed_output_path: str | None = None,
    cropped_dimensions: dict[str, int] | None = None,
    status: str = "roi_marked",
    requires_review: bool = False,
    review_status: str = "approved",
    nucleus_reference: NucleusReference | None = None,
    cutoff_boundary: CutoffBoundary | None = None,
    cutoff_cleared: bool | None = None,
    cell_region: CellRegion | None = None,
    timing: TimingMetadata | None = None,
    scientific_calibration: SampleScientificCalibration | None = None,
    crop_confirmed: bool | None = None,
    cell_boundary_sensitivity: float | None = None,
    cell_detection_parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Structured annotation for training and export.

    Optional ``nucleus_reference``, ``cutoff_boundary``, ``cell_region``,
    ``timing``, ``scientific_calibration``, ``crop_confirmed``, and ``roi`` persist
    in oriented_frame_pixels (timing/calibration/crop_confirmed are workflow
    metadata, not geometry). They are omitted when None so old projects stay
    unchanged and a missing crop does not erase scientific state. Legacy
    cutoff_y is not written here and is not promoted on load.
    """
    ann: dict[str, Any] = {
        "sample_id": str(sample_id),
        "group": str(group),
        "batch_name": str(batch_name),
        "batch_id": str(batch_id),
        "original_file": str(original_file),
        "stored_raw_path": str(stored_raw_path),
        "reference_frame_index": int(reference_frame_index),
        "rotation_angle_degrees": float(orientation.rotation_angle_degrees),
        "flipped_180": bool(orientation.flipped_180),
        "mirror_y_axis": bool(orientation.mirror_y_axis),
        "manual_rotation_steps": list(orientation.manual_rotation_steps),
        "annotation_source": annotation_source,
        "original_dimensions": original_dimensions,
        "oriented_dimensions": oriented_dimensions,
        "segmentation_method": segmentation_method or "not_applied",
        "segmentation_parameters": segmentation_parameters or {},
        "processing_date": _utc_now_iso(),
        "status": status,
        "requires_review": requires_review,
        "review_status": review_status,
        "notes": notes,
    }
    if roi is not None:
        ann["rectangle_roi"] = roi_oriented_as_dict(roi)
        ann["roi_method"] = roi_method
        ann["roi_coordinate_space"] = ORIENTED_ROI_COORDINATE_SPACE
        if roi_original is not None:
            ann.update(roi_original_as_dict(roi_original))
    if suggestion_method:
        ann["suggestion_method"] = suggestion_method
    if cell_mask_path:
        ann["cell_mask_path"] = cell_mask_path
    if propagated_from:
        ann["propagation"] = propagated_from
    if processed_output_path:
        ann["processed_output_path"] = processed_output_path
    if cropped_dimensions:
        ann["cropped_dimensions"] = cropped_dimensions
    if nucleus_reference is not None:
        ann[ANNOTATION_FIELD_NUCLEUS_REFERENCE] = nucleus_reference.to_dict()
    if cutoff_boundary is not None:
        ann[ANNOTATION_FIELD_CUTOFF_BOUNDARY] = cutoff_boundary.to_dict()
    elif cutoff_cleared:
        ann[ANNOTATION_FIELD_CUTOFF_CLEARED] = True
    if cell_region is not None:
        ann[ANNOTATION_FIELD_CELL_REGION] = cell_region.to_dict()
    if timing is not None:
        ann[ANNOTATION_FIELD_TIMING] = timing.to_dict()
    if scientific_calibration is not None:
        fps = None
        if timing is not None:
            fps = timing.observed_video_fps
        ann = merge_calibration_into_annotation(
            ann, scientific_calibration, observed_video_fps=fps
        )
    if crop_confirmed is not None:
        ann[ANNOTATION_FIELD_CROP_CONFIRMED] = bool(crop_confirmed)
    if cell_boundary_sensitivity is not None:
        ann[ANNOTATION_FIELD_CELL_BOUNDARY_SENSITIVITY] = float(
            cell_boundary_sensitivity
        )
    if cell_detection_parameters:
        ann[ANNOTATION_FIELD_CELL_DETECTION] = dict(cell_detection_parameters)
    return ann


_RECT_ROI_DOCUMENT_KEYS = (
    "rectangle_roi",
    "roi_x",
    "roi_y",
    "roi_width",
    "roi_height",
    "roi_method",
    "roi_coordinate_space",
)


def annotation_without_rect_roi(annotation: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with computational RectROI fields removed.

    Scientific fields, orientation, and processed-output metadata are kept.
    """
    out = dict(annotation)
    for key in _RECT_ROI_DOCUMENT_KEYS:
        out.pop(key, None)
    return out


def merge_processed_into_annotation(
    annotation: dict[str, Any],
    process_result: dict[str, Any],
) -> dict[str, Any]:
    """Update annotation after successful export."""
    out = dict(annotation)
    out["processed_output_path"] = process_result.get("processed_output_path")
    out["cropped_dimensions"] = process_result.get("cropped_dimensions")
    out["frame_count_exported"] = process_result.get("frame_count")
    out["status"] = "processed"
    out["requires_review"] = False
    out["processing_date"] = _utc_now_iso()
    return out


def annotation_from_legacy(ann: dict[str, Any]) -> tuple[OrientationState, RectROI | None]:
    """Load orientation and ROI from Phase 1 or Phase 2 metadata.

    Legacy cutoff_y / cutoff_y_rotated / analysis_region_coords may reconstruct
    a RectROI. They are not CutoffBoundary and are not promoted to that type.
    """
    orientation = OrientationState.from_dict(ann)
    # Prefer oriented-space rectangle_roi when present (matches the on-canvas box at save).
    # Reconstructing from roi_original via corner mapping inflates the box after rotation.
    if ann.get("rectangle_roi"):
        return orientation, RectROI.from_dict(ann["rectangle_roi"])
    w = int(
        ann.get("original_dimensions", {}).get("width", 0)
        or ann.get("original_frame_width", 0)
        or ann.get("oriented_dimensions", {}).get("width", 0)
    )
    h = int(
        ann.get("original_dimensions", {}).get("height", 0)
        or ann.get("original_frame_height", 0)
        or ann.get("oriented_dimensions", {}).get("height", 0)
    )
    roi_orig = roi_from_original_dict(ann)
    if roi_orig is not None and w and h:
        return orientation, original_roi_to_oriented(
            roi_orig, orig_w=w, orig_h=h, state=orientation
        )

    if ann.get("analysis_region_coords"):
        coords = ann["analysis_region_coords"]
        return orientation, RectROI.from_xyxy(
            int(coords.get("x0", 0)),
            int(coords.get("y0", 0)),
            int(coords.get("x1", w)),
            int(coords.get("y1", ann.get("cutoff_y", h))),
        )
    if ann.get("cutoff_y") is not None and w and h:
        y = int(ann["cutoff_y"])
        tracking = ann.get("tracking_roi") or {}
        x0 = int(tracking.get("x0", 0))
        x1 = int(tracking.get("x1", w))
        return orientation, RectROI(x0, 0, max(1, x1 - x0), max(1, y))
    return orientation, None


def region_from_annotation(annotation: dict[str, Any]) -> Region:
    """Optional adapter: parse Region geometry from annotation fields."""
    return Region.from_annotation(annotation)


def scientific_annotations_from_annotation(
    annotation: dict[str, Any] | None,
) -> tuple[NucleusReference | None, CutoffBoundary | None]:
    """Load optional nucleus/cutoff. Missing fields return None, not defaults."""
    return (
        nucleus_reference_from_annotation(annotation),
        cutoff_boundary_from_annotation(annotation),
    )


def cell_region_from_sample_annotation(
    annotation: dict[str, Any] | None,
) -> CellRegion | None:
    """Load optional CellRegion. Missing fields return None, not defaults."""
    return cell_region_from_annotation(annotation)


def cell_boundary_sensitivity_from_annotation(
    annotation: dict[str, Any] | None,
) -> float | None:
    """Load persisted Cell Boundary Sensitivity. Missing returns None."""
    if not annotation:
        return None
    raw = annotation.get(ANNOTATION_FIELD_CELL_BOUNDARY_SENSITIVITY)
    if raw in (None, ""):
        detection = annotation.get(ANNOTATION_FIELD_CELL_DETECTION)
        if isinstance(detection, dict) and detection.get("sensitivity") is not None:
            raw = detection.get("sensitivity")
        else:
            return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
