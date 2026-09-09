"""Derive Workbench setup readiness from canonical persisted fields.

No second redundant workflow enum is stored. Callers compose crop confirmation,
CellRegion, nucleus, timing, and metric freshness into UI gating.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


ANNOTATION_FIELD_CROP_CONFIRMED = "crop_confirmed"


@dataclass(frozen=True)
class WorkflowSnapshot:
    """UI-facing readiness derived from live/persisted scientific state."""

    has_sample: bool = False
    has_crop: bool = False
    crop_confirmed: bool = False
    has_cell_region: bool = False
    has_nucleus: bool = False
    timing_confirmed: bool = False
    metrics_present: bool = False
    metrics_stale: bool = False
    metrics_running: bool = False

    @property
    def ready_to_run(self) -> bool:
        return (
            self.has_sample
            and self.has_crop
            and self.crop_confirmed
            and self.has_cell_region
            and self.has_nucleus
            and self.timing_confirmed
            and not self.metrics_running
        )

    @property
    def metrics_current(self) -> bool:
        return self.metrics_present and not self.metrics_stale and not self.metrics_running

    @property
    def metric_analysis_allowed(self) -> bool:
        """Metric Analysis inspects current results only — never a prerequisite."""
        return self.metrics_current

    def run_metrics_block_reason(self) -> str | None:
        if not self.has_sample:
            return "Select a sample first"
        if self.metrics_running:
            return "Metrics are running"
        if not self.has_crop:
            return "Select a crop first"
        if not self.crop_confirmed:
            return "Confirm the crop"
        if not self.has_cell_region:
            return "Confirm the crop to identify the cell"
        if not self.has_nucleus:
            return "Select the nucleus"
        if not self.timing_confirmed:
            return "Confirm analysis timing"
        return None

    def metric_analysis_block_reason(self) -> str | None:
        if not self.has_sample:
            return "Select a sample first"
        if self.metrics_running:
            return "Wait for Run Metrics to finish"
        if not self.metrics_present:
            return "Run Metrics first"
        if self.metrics_stale:
            return "Results are outdated — run Metrics again"
        return None

    def next_action_hint(self) -> str:
        if not self.has_sample:
            return "Select a sample to begin."
        if not self.has_crop:
            return "Draw the computational crop around the cell."
        if not self.crop_confirmed:
            return "Confirm the crop to identify the cell boundary."
        if not self.has_cell_region:
            return "Confirm the crop to identify the cell boundary."
        if not self.has_nucleus:
            return "Select the nucleus center."
        if not self.timing_confirmed:
            return "Confirm analysis timing."
        if self.metrics_running:
            return "Running metrics…"
        if self.metrics_stale:
            return "Setup changed — run Metrics again."
        if not self.metrics_present:
            return "Ready — click Run Metrics."
        return "Metrics current. Open Metric Analysis for detail, or switch samples."


def crop_confirmed_from_annotation(ann: dict[str, Any] | None) -> bool:
    """Load crop confirmation; infer True for legacy annotations with a saved crop.

    Rule: explicit ``crop_confirmed`` wins. When the field is missing and a
    rectangular crop is persisted, treat the crop as confirmed so existing
    projects are not forced through the new Confirm step.
    """
    if not ann:
        return False
    if ANNOTATION_FIELD_CROP_CONFIRMED in ann:
        return bool(ann.get(ANNOTATION_FIELD_CROP_CONFIRMED))
    has_roi = bool(ann.get("rectangle_roi") or ann.get("roi"))
    return has_roi


def build_workflow_snapshot(
    *,
    has_sample: bool,
    has_crop: bool,
    crop_confirmed: bool,
    has_cell_region: bool,
    has_nucleus: bool,
    timing_confirmed: bool,
    metrics_present: bool,
    metrics_stale: bool,
    metrics_running: bool = False,
) -> WorkflowSnapshot:
    return WorkflowSnapshot(
        has_sample=bool(has_sample),
        has_crop=bool(has_crop),
        crop_confirmed=bool(crop_confirmed) and bool(has_crop),
        has_cell_region=bool(has_cell_region),
        has_nucleus=bool(has_nucleus),
        timing_confirmed=bool(timing_confirmed),
        metrics_present=bool(metrics_present),
        metrics_stale=bool(metrics_stale),
        metrics_running=bool(metrics_running),
    )


def format_sample_results_summary(
    *,
    sparse_px: Optional[float],
    sparse_um_s: Optional[float],
    of_px: Optional[float],
    of_um_s: Optional[float],
    toward_nucleus_um_s: Optional[float],
    orientation_deg: Optional[float],
    tracks_used: Optional[int],
    tracks_requested: Optional[int],
    timing_label: str,
    timing_confirmed: bool,
    stale: bool = False,
) -> str:
    """Concise Workbench Sample Results text from persisted display values."""

    def _px(value: Optional[float]) -> str:
        if value is None:
            return "—"
        return f"{float(value):.2f} px/frame"

    def _um(value: Optional[float]) -> str:
        if value is None:
            return "—"
        return f"{float(value):.2f} µm/s"

    lines = ["SAMPLE RESULTS"]
    if stale:
        lines.append("Outdated — run Metrics again")
    lines.extend(
        [
            "",
            "General Movement",
            _px(sparse_px),
            _um(sparse_um_s),
        ]
    )
    if sparse_um_s is not None and not timing_confirmed:
        lines.append("Timing unconfirmed")
    lines.extend(
        [
            "",
            "Optical Flow",
            _px(of_px),
            _um(of_um_s),
        ]
    )
    if of_um_s is not None and not timing_confirmed:
        lines.append("Timing unconfirmed")
    lines.append("")
    lines.append("Toward Nucleus")
    lines.append(_um(toward_nucleus_um_s) if toward_nucleus_um_s is not None else "—")
    lines.append("")
    lines.append("F-actin Orientation")
    if orientation_deg is None:
        lines.append("—")
    else:
        lines.append(f"{float(orientation_deg):.1f}°")
    lines.append("")
    lines.append("Tracks")
    if tracks_used is None:
        lines.append("—")
    elif tracks_requested is not None and tracks_requested > tracks_used:
        lines.append(f"{tracks_used} valid / {tracks_requested} requested")
    else:
        lines.append(f"{tracks_used} valid")
    lines.append("")
    lines.append("Timing")
    lines.append(timing_label or "—")
    return "\n".join(lines)
