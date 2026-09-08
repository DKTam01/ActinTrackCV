"""V2 durable scientific validation harness.

Extends the V1 measurement-fidelity audit with per-sample provenance for
reacquisition, per-track results, nucleus-relative movement, structural
orientation, and Optical Flow scientific-domain parity.

Does not tune thresholds or apply correction multipliers. The researcher
confirmed WT550 > Mutant515 ordering is an investigation flag only.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np

from actintrack_app.measurement_fidelity import (
    CANDIDATE_SECONDS_PER_FRAME,
    DEFAULT_AUDIT_SAMPLES,
    HISTORICAL_GROUP_SANITY,
    OpticalFlowDisplacementSummary,
    collect_temporal_evidence,
    condition_ordering,
    current_optical_flow_settings,
    current_tracker_params,
    historical_optical_flow_settings,
    historical_tracker_params,
    load_crop_roi_for_sample,
    probe_video_container,
    summarize_sparse_tracks,
)
from actintrack_app.motion_index import (
    DEFAULT_SECONDS_PER_FRAME,
    METRIC_DEFINITION_VERSION,
    MOVEMENT_OUTPUT_SCHEMA_VERSION,
    MotionIndexParams,
    compute_nucleus_relative_summary,
    select_starting_points,
    serialize_video_tracking_result,
    track_points,
)
from actintrack_app.optical_flow_motion_index import (
    OpticalFlowSettings,
    compute_optical_flow_motion_index,
)
from actintrack_app.orientation import OrientationState, RectROI
from actintrack_app.preview_workflow import load_cropped_frames_from_video
from actintrack_app.scientific_annotations import (
    nucleus_reference_from_annotation,
    scientific_valid_mask_for_tracking,
)
from actintrack_app.structural_orientation import (
    StructuralOrientationSettings,
    compute_structural_orientation,
)

SCIENTIFIC_VALIDATION_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class ManualMeasurement:
    """Optional quantitative manual reference for one sample/method."""

    sample_id: str
    method: str  # sparse_general_movement | optical_flow_general_movement | ...
    value: float
    units: str
    seconds_per_frame: float | None = None
    microns_per_pixel: float | None = None
    notes: str = ""


@dataclass
class ManualComparisonStats:
    n: int = 0
    signed_errors: list[float] = field(default_factory=list)
    absolute_errors: list[float] = field(default_factory=list)
    relative_errors: list[float] = field(default_factory=list)

    @property
    def mae(self) -> Optional[float]:
        return (
            float(sum(self.absolute_errors) / len(self.absolute_errors))
            if self.absolute_errors
            else None
        )

    @property
    def rmse(self) -> Optional[float]:
        if not self.signed_errors:
            return None
        return float(
            math.sqrt(sum(e * e for e in self.signed_errors) / len(self.signed_errors))
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "mae": self.mae,
            "rmse": self.rmse,
            "mean_signed_error": (
                float(sum(self.signed_errors) / len(self.signed_errors))
                if self.signed_errors
                else None
            ),
            "mean_relative_error": (
                float(sum(self.relative_errors) / len(self.relative_errors))
                if self.relative_errors
                else None
            ),
        }


def load_crop_metadata_row(crop_metadata_path: Path, sample_key: str) -> dict[str, Any] | None:
    path = Path(crop_metadata_path)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    samples = data.get("data_files") or data.get("samples") or {}
    row = samples.get(sample_key)
    return dict(row) if isinstance(row, dict) else None


def load_manual_measurements(path: Path | None) -> list[ManualMeasurement]:
    if path is None or not Path(path).is_file():
        return []
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = payload.get("measurements") if isinstance(payload, dict) else payload
    out: list[ManualMeasurement] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            out.append(
                ManualMeasurement(
                    sample_id=str(row["sample_id"]),
                    method=str(row["method"]),
                    value=float(row["value"]),
                    units=str(row.get("units", "")),
                    seconds_per_frame=(
                        float(row["seconds_per_frame"])
                        if row.get("seconds_per_frame") not in (None, "")
                        else None
                    ),
                    microns_per_pixel=(
                        float(row["microns_per_pixel"])
                        if row.get("microns_per_pixel") not in (None, "")
                        else None
                    ),
                    notes=str(row.get("notes", "")),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def compare_to_manual(
    predicted: float | None,
    manual: ManualMeasurement,
) -> dict[str, Any]:
    if predicted is None:
        return {
            "sample_id": manual.sample_id,
            "method": manual.method,
            "manual_value": manual.value,
            "predicted_value": None,
            "status": "missing_prediction",
        }
    signed = float(predicted) - float(manual.value)
    abs_err = abs(signed)
    rel = abs_err / abs(float(manual.value)) if manual.value != 0 else None
    return {
        "sample_id": manual.sample_id,
        "method": manual.method,
        "manual_value": manual.value,
        "manual_units": manual.units,
        "predicted_value": float(predicted),
        "signed_error": signed,
        "absolute_error": abs_err,
        "relative_error": rel,
        "status": "compared",
        "notes": manual.notes,
    }


def evaluate_condition_sanity(
    ordering: dict[str, Any],
) -> dict[str, Any]:
    """Flag unexpected WT/Mutant reversals for investigation; never a hard fail."""
    sparse_ok = ordering.get("observed_sparse_wt_gt_mutant")
    of_ok = ordering.get("observed_of_wt_gt_mutant")
    alerts: list[str] = []
    if sparse_ok is False:
        alerts.append(
            "sparse_tracking_raw_px_frame_reversed_or_erased_WT_gt_Mutant515"
        )
    if of_ok is False:
        alerts.append(
            "optical_flow_raw_px_frame_reversed_or_erased_WT_gt_Mutant515"
        )
    return {
        "qualitative_ground_truth": "WT550 > Mutant515",
        "role": "external_sanity_check_not_tuning_target",
        "historical_group_sanity": HISTORICAL_GROUP_SANITY,
        "observed_sparse_wt_gt_mutant": sparse_ok,
        "observed_of_wt_gt_mutant": of_ok,
        "investigation_alerts": alerts,
        "hard_scientific_failure": False,
        "note": (
            "Unexpected reversals must be investigated. They do not by themselves "
            "invalidate the measurement definition."
        ),
    }


def summarize_optical_flow_with_mask(
    sample_id: str,
    frames: Sequence[np.ndarray],
    settings: OpticalFlowSettings,
    *,
    valid_mask: np.ndarray | None = None,
) -> OpticalFlowDisplacementSummary:
    result = compute_optical_flow_motion_index(
        frames,
        settings,
        sample_id=sample_id,
        valid_mask=valid_mask,
    )
    calibrated: dict[str, dict[str, float]] = {}
    mag = float(result.mean_magnitude_px_frame or 0.0)
    for label, seconds in CANDIDATE_SECONDS_PER_FRAME:
        spf = float(settings.seconds_per_frame if seconds is None else seconds)
        scale = float(settings.microns_per_pixel) / spf
        calibrated[label] = {
            "seconds_per_frame": spf,
            "optical_flow_general_movement_um_s": mag * scale,
        }
    return OpticalFlowDisplacementSummary(
        sample_id=sample_id,
        has_valid_result=result.has_valid_result,
        failure_reason=result.failure_reason,
        mean_magnitude_px_frame=result.mean_magnitude_px_frame,
        mean_downward_px_frame=result.mean_downward_px_frame,
        mean_net_y_px_frame=result.mean_net_y_px_frame,
        valid_pixel_fraction=result.optical_flow_valid_pixel_fraction,
        frame_pair_count=result.frame_pair_count,
        general_movement_um_s=result.optical_flow_general_movement_um_s,
        settings=asdict(settings),
        calibrated_by_interval=calibrated,
    )


def run_sample_scientific_benchmark(
    *,
    source_path: Path,
    sample_id: str,
    condition: str,
    role: str,
    orientation: OrientationState,
    roi: RectROI,
    tracker_params: MotionIndexParams,
    flow_settings: OpticalFlowSettings,
    crop_row: dict[str, Any] | None,
    domain_note: str,
) -> dict[str, Any]:
    """Run matched sparse/OF/orientation diagnostics for one sample."""
    source_path = Path(source_path).resolve()
    container = probe_video_container(source_path)
    frames = load_cropped_frames_from_video(source_path, orientation, roi)

    annotation = crop_row or {}
    nucleus = nucleus_reference_from_annotation(annotation)
    nucleus_xy: tuple[float, float] | None = None
    if nucleus is not None:
        nucleus_xy = nucleus.to_crop_local(roi)

    has_cell = bool(annotation.get("cell_region"))
    has_cutoff = bool(annotation.get("cutoff_boundary"))
    mask_applied = has_cell or has_cutoff
    valid_mask = scientific_valid_mask_for_tracking(roi, annotation)

    starts = select_starting_points(frames[0], tracker_params, valid_mask=valid_mask)
    tracks = (
        track_points(frames, starts, tracker_params, valid_mask=valid_mask)
        if starts
        else []
    )
    sparse = summarize_sparse_tracks(sample_id, tracks, tracker_params)
    tracking_result = serialize_video_tracking_result(
        tracks,
        tracker_params,
        nucleus_xy_px=nucleus_xy,
    )
    nucleus_summary = None
    if nucleus_xy is not None:
        nucleus_summary = asdict(
            compute_nucleus_relative_summary(tracks, tracker_params, nucleus_xy)
        )

    flow = summarize_optical_flow_with_mask(
        sample_id,
        frames,
        flow_settings,
        valid_mask=valid_mask if mask_applied else None,
    )

    orientation_result = compute_structural_orientation(
        frames[0],
        nucleus_xy_px=nucleus_xy,
        valid_mask=valid_mask if mask_applied else None,
        settings=StructuralOrientationSettings(),
        sample_id=sample_id,
        reference_frame_index=0,
    )

    return {
        "sample_id": sample_id,
        "condition": condition,
        "role": role,
        "source_path": str(source_path),
        "source_sha256": container.get("sha256"),
        "domain_note": domain_note,
        "crop_provenance": {
            "roi": roi.as_dict(),
            "orientation": {
                "rotation_angle_degrees": orientation.rotation_angle_degrees,
                "flipped_180": orientation.flipped_180,
                "mirror_y_axis": orientation.mirror_y_axis,
            },
            "has_cell_region": has_cell,
            "has_cutoff_boundary": has_cutoff,
            "has_nucleus_reference": nucleus_xy is not None,
            "scientific_mask_applied": mask_applied,
        },
        "container": container,
        "frame_count": len(frames),
        "tracker_params": asdict(tracker_params),
        "optical_flow_settings": asdict(flow_settings),
        "sparse_tracking": asdict(sparse),
        "tracking_result_summary": tracking_result.get("summary"),
        "per_track_count": len(tracking_result.get("tracks") or []),
        "reacquisition": {
            "lookahead_frames": int(tracker_params.lookahead_frames),
            "tracks_recovered_with_lookahead": (
                tracking_result.get("summary") or {}
            ).get("tracks_recovered_with_lookahead"),
            "recovered_point_count": (tracking_result.get("summary") or {}).get(
                "recovered_point_count"
            ),
        },
        "nucleus_relative": nucleus_summary,
        "optical_flow": asdict(flow),
        "structural_orientation": {
            "has_valid_result": orientation_result.has_valid_result,
            "failure_reason": orientation_result.failure_reason,
            "measurement_count": len(orientation_result.measurements),
            "median_angle_relative_nucleus_deg": (
                orientation_result.median_angle_relative_nucleus_deg
            ),
            "mean_angle_relative_nucleus_deg": (
                orientation_result.mean_angle_relative_nucleus_deg
            ),
            "mean_coherence": orientation_result.mean_coherence,
        },
        "comparison": {
            "sparse_mean_px_per_frame": sparse.mean_displacement_px_per_frame,
            "optical_flow_mean_px_per_frame": flow.mean_magnitude_px_frame,
            "same_frames": True,
            "same_roi": True,
        },
    }


def run_scientific_validation_benchmark(
    repo_root: Path,
    *,
    output_dir: Path | None = None,
    sample_ids: Sequence[str] | None = None,
    use_saved_roi: bool = True,
    tracker_mode: str = "current",
    flow_mode: str = "current",
    seconds_per_frame: float | None = None,
    lookahead_frames: int | None = None,
    manual_measurements_path: Path | None = None,
) -> dict[str, Any]:
    """Run the durable V2 scientific validation benchmark."""
    root = Path(repo_root).resolve()
    out = Path(output_dir or (root / "outputs" / "scientific_validation")).resolve()
    out.mkdir(parents=True, exist_ok=True)

    crop_meta = root / "metadata" / "crop_metadata.json"
    selected = [
        s
        for s in DEFAULT_AUDIT_SAMPLES
        if sample_ids is None or s["sample_id"] in set(sample_ids)
    ]

    if tracker_mode == "historical":
        tracker_params = historical_tracker_params(
            seconds_per_frame=(
                0.2 if seconds_per_frame is None else float(seconds_per_frame)
            )
        )
    else:
        tracker_params = current_tracker_params(
            seconds_per_frame=(
                DEFAULT_SECONDS_PER_FRAME
                if seconds_per_frame is None
                else float(seconds_per_frame)
            )
        )
    if lookahead_frames is not None:
        tracker_params = MotionIndexParams(
            **{
                **asdict(tracker_params),
                "lookahead_frames": int(lookahead_frames),
            }
        )

    if flow_mode == "historical_draft":
        flow_settings = historical_optical_flow_settings(
            seconds_per_frame=float(tracker_params.seconds_per_frame)
        )
    else:
        flow_settings = current_optical_flow_settings(
            seconds_per_frame=float(tracker_params.seconds_per_frame)
        )

    sample_rows: list[dict[str, Any]] = []
    for spec in selected:
        source = root / spec["source"]
        if not source.is_file():
            sample_rows.append(
                {
                    "sample_id": spec["sample_id"],
                    "condition": spec["condition"],
                    "role": spec["role"],
                    "error": f"missing_source:{source}",
                }
            )
            continue

        crop_row = load_crop_metadata_row(crop_meta, spec["roi_key"])
        orientation = OrientationState()
        roi: RectROI | None = None
        domain_note = "whole_frame_legacy_observation_no_saved_roi"
        if use_saved_roi:
            loaded = load_crop_roi_for_sample(crop_meta, spec["roi_key"])
            if loaded is not None:
                orientation, roi = loaded
                domain_note = (
                    "saved_rect_roi_crop; scientific CellRegion/cutoff applied "
                    "only when present in crop metadata"
                )
        if roi is None:
            probe = probe_video_container(source)
            roi = RectROI(0, 0, int(probe["width"]), int(probe["height"]))
            domain_note = "whole_frame_legacy_observation"

        try:
            row = run_sample_scientific_benchmark(
                source_path=source,
                sample_id=spec["sample_id"],
                condition=spec["condition"],
                role=spec["role"],
                orientation=orientation,
                roi=roi,
                tracker_params=tracker_params,
                flow_settings=flow_settings,
                crop_row=crop_row,
                domain_note=domain_note,
            )
        except Exception as exc:  # noqa: BLE001 - continue across corpus
            row = {
                "sample_id": spec["sample_id"],
                "condition": spec["condition"],
                "role": spec["role"],
                "source_path": str(source),
                "error": str(exc),
            }
        sample_rows.append(row)

    ok_rows = [r for r in sample_rows if "error" not in r]
    ordering = condition_ordering(ok_rows)
    sanity = evaluate_condition_sanity(ordering)

    manuals = load_manual_measurements(manual_measurements_path)
    manual_comparisons: list[dict[str, Any]] = []
    stats_by_method: dict[str, ManualComparisonStats] = {}
    by_id = {r["sample_id"]: r for r in ok_rows}
    for manual in manuals:
        row = by_id.get(manual.sample_id)
        predicted = None
        if row is not None:
            if manual.method == "sparse_general_movement":
                predicted = (row.get("sparse_tracking") or {}).get(
                    "general_movement_um_per_s"
                )
            elif manual.method == "optical_flow_general_movement":
                predicted = (row.get("optical_flow") or {}).get(
                    "general_movement_um_s"
                )
            elif manual.method == "sparse_mean_px_per_frame":
                predicted = (row.get("sparse_tracking") or {}).get(
                    "mean_displacement_px_per_frame"
                )
            elif manual.method == "optical_flow_mean_px_per_frame":
                predicted = (row.get("optical_flow") or {}).get(
                    "mean_magnitude_px_frame"
                )
        comparison = compare_to_manual(predicted, manual)
        manual_comparisons.append(comparison)
        if comparison.get("status") == "compared":
            bucket = stats_by_method.setdefault(
                manual.method, ManualComparisonStats()
            )
            bucket.n += 1
            bucket.signed_errors.append(float(comparison["signed_error"]))
            bucket.absolute_errors.append(float(comparison["absolute_error"]))
            if comparison.get("relative_error") is not None:
                bucket.relative_errors.append(float(comparison["relative_error"]))

    # Rank agreement only when enough manual sparse GM pairs exist.
    rank_agreement = None
    sparse_manual = [
        c
        for c in manual_comparisons
        if c.get("method") == "sparse_general_movement"
        and c.get("status") == "compared"
    ]
    if len(sparse_manual) >= 2:
        manual_order = sorted(sparse_manual, key=lambda c: -float(c["manual_value"]))
        pred_order = sorted(sparse_manual, key=lambda c: -float(c["predicted_value"]))
        rank_agreement = {
            "manual_rank_sample_ids": [c["sample_id"] for c in manual_order],
            "predicted_rank_sample_ids": [c["sample_id"] for c in pred_order],
            "same_order": [c["sample_id"] for c in manual_order]
            == [c["sample_id"] for c in pred_order],
        }

    payload: dict[str, Any] = {
        "audit_kind": "scientific_validation_v2",
        "schema_version": SCIENTIFIC_VALIDATION_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "metric_definition_version": METRIC_DEFINITION_VERSION,
        "movement_output_schema_version": MOVEMENT_OUTPUT_SCHEMA_VERSION,
        "repo_root": str(root),
        "tracker_mode": tracker_mode,
        "flow_mode": flow_mode,
        "tracker_params": asdict(tracker_params),
        "optical_flow_settings": asdict(flow_settings),
        "constraints": {
            "no_correction_multipliers": True,
            "values_below_1_um_s_are_investigation_trigger": True,
            "wt_gt_mutant_is_sanity_check_not_tuning_target": True,
            "acquisition_interval_unresolved_for_corpus": True,
            "production_seconds_per_frame_default_unchanged": True,
        },
        "temporal_evidence": collect_temporal_evidence(root),
        "condition_ordering": ordering,
        "condition_sanity": sanity,
        "manual_comparisons": manual_comparisons,
        "manual_stats_by_method": {
            method: stats.as_dict() for method, stats in stats_by_method.items()
        },
        "manual_rank_agreement": rank_agreement,
        "samples": sample_rows,
    }

    report_json = out / "scientific_validation_report.json"
    report_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    csv_path = out / "scientific_validation_sample_summary.csv"
    fieldnames = [
        "sample_id",
        "condition",
        "role",
        "domain_note",
        "has_nucleus_reference",
        "scientific_mask_applied",
        "sparse_mean_px_per_frame",
        "sparse_general_um_s",
        "sparse_valid_tracks",
        "sparse_valid_steps",
        "tracks_recovered_with_lookahead",
        "recovered_point_count",
        "toward_nucleus_um_s",
        "of_mean_px_per_frame",
        "of_general_um_s",
        "orientation_valid",
        "orientation_median_deg",
        "orientation_measurement_count",
        "error",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in sample_rows:
            sparse = row.get("sparse_tracking") or {}
            flow = row.get("optical_flow") or {}
            reacq = row.get("reacquisition") or {}
            nucleus = row.get("nucleus_relative") or {}
            orientation = row.get("structural_orientation") or {}
            crop = row.get("crop_provenance") or {}
            writer.writerow(
                {
                    "sample_id": row.get("sample_id", ""),
                    "condition": row.get("condition", ""),
                    "role": row.get("role", ""),
                    "domain_note": row.get("domain_note", ""),
                    "has_nucleus_reference": crop.get("has_nucleus_reference", ""),
                    "scientific_mask_applied": crop.get(
                        "scientific_mask_applied", ""
                    ),
                    "sparse_mean_px_per_frame": sparse.get(
                        "mean_displacement_px_per_frame", ""
                    ),
                    "sparse_general_um_s": sparse.get(
                        "general_movement_um_per_s", ""
                    ),
                    "sparse_valid_tracks": sparse.get(
                        "num_tracks_with_valid_steps", ""
                    ),
                    "sparse_valid_steps": sparse.get("total_valid_steps", ""),
                    "tracks_recovered_with_lookahead": reacq.get(
                        "tracks_recovered_with_lookahead", ""
                    ),
                    "recovered_point_count": reacq.get("recovered_point_count", ""),
                    "toward_nucleus_um_s": nucleus.get(
                        "time_weighted_toward_velocity_um_per_s", ""
                    ),
                    "of_mean_px_per_frame": flow.get("mean_magnitude_px_frame", ""),
                    "of_general_um_s": flow.get("general_movement_um_s", ""),
                    "orientation_valid": orientation.get("has_valid_result", ""),
                    "orientation_median_deg": orientation.get(
                        "median_angle_relative_nucleus_deg", ""
                    ),
                    "orientation_measurement_count": orientation.get(
                        "measurement_count", ""
                    ),
                    "error": row.get("error", ""),
                }
            )

    payload["report_json"] = str(report_json)
    payload["sample_csv"] = str(csv_path)
    return payload
