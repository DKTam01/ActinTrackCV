"""Metric Analysis inspection-mode display helpers.

Inspection modes are views of a persisted run. They do not recompute science.
Empty-state copy is mode-specific so a missing orientation result is not
confused with a missing tracking run.
"""

from __future__ import annotations

INSPECTION_MODE_TEMPLATE = "template"
INSPECTION_MODE_OPTICAL_FLOW = "optical_flow"
INSPECTION_MODE_ORIENTATION = "orientation"

INSPECTION_MODES = (
    INSPECTION_MODE_TEMPLATE,
    INSPECTION_MODE_OPTICAL_FLOW,
    INSPECTION_MODE_ORIENTATION,
)

ORIENTATION_LEGEND_TEXT = "F-actin Orientation · 0° radial → 90° tangential"

NUCLEUS_ALIGNMENT_REVIEW_HINT = "Cutoff moved — review nucleus alignment."

_EMPTY_STATE_BY_MODE = {
    INSPECTION_MODE_TEMPLATE: (
        "Tracking results have not been generated for this sample."
    ),
    INSPECTION_MODE_OPTICAL_FLOW: (
        "Optical Flow has not been generated for this sample."
    ),
    INSPECTION_MODE_ORIENTATION: (
        "F-actin Orientation has not been generated for this sample."
    ),
}


def empty_state_message_for_mode(mode: str | None) -> str:
    """Centered canvas copy for an inspection mode without a persisted result."""
    key = str(mode or INSPECTION_MODE_TEMPLATE).strip()
    return _EMPTY_STATE_BY_MODE.get(
        key,
        _EMPTY_STATE_BY_MODE[INSPECTION_MODE_TEMPLATE],
    )


def draft_analysis_run_id(payload: dict | None) -> str:
    """Identity of a persisted Metric Analysis run, if present."""
    if not isinstance(payload, dict):
        return ""
    return str(
        payload.get("analysis_run_id") or payload.get("analysis_timestamp_utc") or ""
    )


def cached_analysis_matches_draft_run(cached_run_id: str, draft_run_id: str) -> bool:
    """Reuse an in-memory analysis only when it is the current persisted run."""
    cached = str(cached_run_id or "")
    draft = str(draft_run_id or "")
    return (not draft) or cached == draft
