"""Load tracking and optical-flow result views from disk and in-memory caches."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from actintrack_app.export_naming import motion_index_summary_json_path
from actintrack_app.gui_result_views import (
    OpticalFlowResultView,
    SampleTrackingResultView,
    optical_flow_result_view_from_dict,
    optical_flow_result_view_from_result,
    tracking_result_view_from_dict,
    tracking_result_view_from_preview,
)
from actintrack_app.optical_flow_motion_index import OpticalFlowResult
from actintrack_app.preview_workflow import CroppedPreviewAnalysis
from actintrack_app.project_manager import get_processed_batch_dir
from actintrack_app.utils import STATUS_MOTION_INDEX_FAILED


def motion_index_summary_path_for_sample(
    project_root: Path | None,
    sample: dict[str, Any],
) -> Path | None:
    if project_root is None:
        return None
    group = str(sample.get("group", "")).strip()
    batch_name = str(sample.get("batch_name", "")).strip()
    final_name = str(sample.get("final_export_name", "")).strip()
    if not group or not batch_name or not final_name:
        return None
    batch_dir = get_processed_batch_dir(project_root, group, batch_name)
    path = motion_index_summary_json_path(batch_dir, final_name)
    return path if path.is_file() else None


def load_latest_tracking_result_view(
    sample_id: str,
    *,
    project_root: Path | None,
    sample_row: dict[str, Any] | None,
    cached_preview: CroppedPreviewAnalysis | None,
) -> SampleTrackingResultView | None:
    if project_root is not None:
        if sample_row is not None:
            summary_path = motion_index_summary_path_for_sample(project_root, sample_row)
            if summary_path is not None:
                try:
                    data = json.loads(summary_path.read_text(encoding="utf-8"))
                    return tracking_result_view_from_dict(data)
                except (OSError, json.JSONDecodeError):
                    pass
        from actintrack_app.schema_compat import resolve_draft_tracking_path

        draft_path = resolve_draft_tracking_path(project_root, sample_id)
        if draft_path is not None:
            try:
                data = json.loads(draft_path.read_text(encoding="utf-8"))
                return tracking_result_view_from_dict(data)
            except (OSError, json.JSONDecodeError):
                pass
    if cached_preview is not None:
        return tracking_result_view_from_preview(cached_preview)
    if sample_row is not None:
        proc_status = str(sample_row.get("processing_status", ""))
        if proc_status == STATUS_MOTION_INDEX_FAILED:
            return SampleTrackingResultView(
                status="failed",
                failure_reason="Motion index generation failed.",
            )
    return None


def load_latest_optical_flow_result_view(
    sample_id: str,
    *,
    project_root: Path | None,
    cached_result: OpticalFlowResult | None,
) -> OpticalFlowResultView | None:
    if project_root is not None:
        from actintrack_app.schema_compat import resolve_draft_optical_flow_path

        draft_path = resolve_draft_optical_flow_path(project_root, sample_id)
        if draft_path is not None:
            try:
                data = json.loads(draft_path.read_text(encoding="utf-8"))
                return optical_flow_result_view_from_dict(data)
            except (OSError, json.JSONDecodeError):
                pass
    if cached_result is not None:
        return optical_flow_result_view_from_result(cached_result)
    return None
