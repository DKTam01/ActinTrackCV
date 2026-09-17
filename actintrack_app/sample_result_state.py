"""Canonical per-sample result freshness and scientific-edit invalidation.

These helpers are UI-agnostic. They do not load videos, recompute tracking,
or persist JSON. MainWindow applies the returned policy to its caches.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping, Optional

from actintrack_app.annotation_schema import (
    annotation_from_legacy,
    cell_region_from_sample_annotation,
    scientific_annotations_from_annotation,
)


MetricState = str


@dataclass(frozen=True)
class ResultInvalidation:
    """Effects of a scientific setup edit on existing metric results."""

    mark_stale: bool
    clear_live_caches: bool
    discard_inspection_if_current: bool


def draft_results_are_measurable(
    track: Mapping[str, Any] | None,
    optical_flow: Mapping[str, Any] | None,
    orientation: Mapping[str, Any] | None = None,
) -> bool:
    """True when persisted drafts contain at least one usable metric."""
    track_ok = bool(
        track and int(track.get("num_tracks_with_valid_steps", 0) or 0) > 0
    )
    of_ok = bool(optical_flow and optical_flow.get("has_valid_result"))
    orientation_ok = bool(orientation and orientation.get("has_valid_result"))
    return track_ok or of_ok or orientation_ok


def sample_is_stale(
    tracking_stale: Mapping[str, Any],
    optical_flow_stale: Mapping[str, Any],
    sample_id: str | None,
) -> bool:
    if not sample_id:
        return False
    return bool(tracking_stale.get(sample_id) or optical_flow_stale.get(sample_id))


def set_sample_stale(
    tracking_stale: MutableMapping[str, bool],
    optical_flow_stale: MutableMapping[str, bool],
    sample_id: str,
) -> None:
    tracking_stale[sample_id] = True
    optical_flow_stale[sample_id] = True


def clear_sample_stale(
    tracking_stale: MutableMapping[str, bool],
    optical_flow_stale: MutableMapping[str, bool],
    sample_id: str,
) -> None:
    tracking_stale.pop(sample_id, None)
    optical_flow_stale.pop(sample_id, None)


def invalidation_for_scientific_edit(
    *,
    had_measurable_results: bool,
    geometry_changed: bool,
    motion_calibration_changed: bool = False,
    media_is_image: bool = False,
) -> ResultInvalidation:
    """Preserve current Workbench invalidation: stale only when results exist.

    Geometry edits invalidate every metric that used that geometry.
    Calibration edits change the meaning of physical-unit motion results
    (General Movement, Toward Nucleus, Optical Flow) but not F-actin
    Orientation. IMAGE samples therefore do not become stale from
    calibration-only edits.
    """
    setup_changed = bool(geometry_changed)
    if motion_calibration_changed and not media_is_image:
        setup_changed = True
    if not setup_changed:
        return ResultInvalidation(
            mark_stale=False,
            clear_live_caches=False,
            discard_inspection_if_current=False,
        )
    return ResultInvalidation(
        mark_stale=had_measurable_results,
        clear_live_caches=True,
        discard_inspection_if_current=True,
    )


def classify_metric_state(
    *,
    sample_id: Optional[str],
    has_valid_data_and_roi: bool,
    running: bool,
    track: Mapping[str, Any] | None,
    optical_flow: Mapping[str, Any] | None,
    stale: bool,
    error_flag: bool,
    orientation: Mapping[str, Any] | None = None,
    media_is_image: bool = False,
) -> MetricState:
    """Classify Workbench metric status without touching science."""
    if not sample_id:
        return "unavailable_no_roi"
    if running:
        return "running"
    if not has_valid_data_and_roi:
        return "unavailable_no_roi"
    track_present = track is not None
    of_present = optical_flow is not None
    orientation_present = orientation is not None
    if media_is_image:
        if not orientation_present:
            return "not_analyzed"
        orientation_ok = bool(orientation.get("has_valid_result"))
        if error_flag or not orientation_ok:
            return "error"
        if stale:
            return "stale"
        return "analyzed"
    if not track_present and not of_present:
        return "not_analyzed"
    track_ok = track_present and int(
        track.get("num_tracks_with_valid_steps", 0) or 0
    ) > 0
    of_ok = of_present and bool(optical_flow.get("has_valid_result"))
    error = bool(error_flag) or (track_present and not track_ok) or (
        of_present and not of_ok
    )
    if error:
        return "error"
    if stale:
        return "stale"
    if track_ok and of_ok:
        return "analyzed"
    return "stale"


def scientific_state_key_from_annotation(
    ann: dict[str, Any] | None,
) -> tuple[Any, ...]:
    """Geometry/setup identity used to detect scientific edits."""
    if not ann:
        return ()
    _orientation, roi = annotation_from_legacy(ann)
    nucleus, cutoff = scientific_annotations_from_annotation(ann)
    cell = cell_region_from_sample_annotation(ann)
    return (
        None if roi is None else (int(roi.x), int(roi.y), int(roi.width), int(roi.height)),
        None if nucleus is None else (float(nucleus.x), float(nucleus.y)),
        None if cutoff is None else float(cutoff.y),
        None if cell is None else cell.region.geometry_key(),
        float(ann.get("rotation_angle_degrees", 0.0) or 0.0),
        bool(ann.get("mirror_y_axis")),
        bool(ann.get("flipped_180")),
    )


def inspection_is_blocked_by_staleness(
    tracking_stale: Mapping[str, Any],
    optical_flow_stale: Mapping[str, Any],
    sample_id: str,
) -> bool:
    return sample_is_stale(tracking_stale, optical_flow_stale, sample_id)
