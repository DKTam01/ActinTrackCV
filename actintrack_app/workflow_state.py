"""Derive Workbench setup readiness from canonical persisted fields.

No second redundant workflow enum is stored. Callers compose CellRegion,
derived computational crop, optional nucleus, required cutoff, media
capabilities, timing (video only), and metric freshness into UI gating.

Legacy ``crop_confirmed`` remains readable for old projects but no longer
drives researcher-facing readiness. Product gating uses CellRegion, cutoff,
media capabilities, and (for VIDEO) valid video timing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from actintrack_app.media_capabilities import (
    SampleMediaType,
    capabilities_for,
)


ANNOTATION_FIELD_CROP_CONFIRMED = "crop_confirmed"
NUCLEUS_CUTOFF_ALIGNMENT_TOLERANCE_PX = 0.5


def _coerce_media_type(media_type: SampleMediaType | str) -> SampleMediaType:
    if isinstance(media_type, SampleMediaType):
        return media_type
    text = str(media_type or "").strip().lower()
    if text == SampleMediaType.IMAGE.value:
        return SampleMediaType.IMAGE
    return SampleMediaType.VIDEO


@dataclass(frozen=True)
class WorkflowSnapshot:
    """UI-facing readiness derived from live/persisted scientific state."""

    has_sample: bool = False
    has_crop: bool = False
    crop_confirmed: bool = False
    has_cell_region: bool = False
    has_nucleus: bool = False
    has_cutoff: bool = False
    timing_confirmed: bool = False
    has_valid_video_timing: bool = False
    metrics_present: bool = False
    metrics_stale: bool = False
    metrics_running: bool = False
    nucleus_alignment_needs_review: bool = False
    media_type: SampleMediaType = SampleMediaType.VIDEO

    @property
    def capabilities(self):
        return capabilities_for(self.media_type)

    @property
    def cell_region_ready(self) -> bool:
        return self.has_sample and self.has_cell_region

    @property
    def nucleus_set(self) -> bool:
        return self.cell_region_ready and self.has_nucleus

    @property
    def can_compute_nucleus_metrics(self) -> bool:
        return self.has_nucleus

    @property
    def ready_to_run(self) -> bool:
        if not (
            self.has_sample
            and self.has_cell_region
            and self.has_crop
            and self.has_cutoff
            and not self.metrics_running
        ):
            return False
        caps = self.capabilities
        if caps.requires_video_timing and not self.has_valid_video_timing:
            return False
        if caps.requires_nucleus_for_run and not self.has_nucleus:
            return False
        return True

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
        if not self.has_cell_region:
            return "Wait for the cell boundary to be identified"
        if not self.has_crop:
            return "Cell boundary is not ready"
        if not self.has_cutoff:
            return "Set the Measurement Cutoff to continue."
        caps = self.capabilities
        if caps.requires_video_timing and not self.has_valid_video_timing:
            return "Valid acquisition timing is required"
        if caps.requires_nucleus_for_run and not self.has_nucleus:
            return "Set the nucleus to run F-actin Orientation"
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
        if not self.has_cell_region:
            return "Identifying the cell boundary…"
        if not self.has_cutoff:
            return "Set the Measurement Cutoff to continue."
        caps = self.capabilities
        if caps.requires_nucleus_for_run and not self.has_nucleus:
            return "Set the nucleus to continue."
        if caps.requires_video_timing and not self.has_valid_video_timing:
            return "Acquisition timing is unavailable — calibrated metrics cannot run."
        if self.metrics_running:
            return "Running metrics…"
        if self.metrics_stale:
            return "Setup changed — run Metrics again."
        if not self.metrics_present:
            if caps.is_image:
                return "Ready — click Run Metrics (F-actin Orientation)."
            if self.has_nucleus:
                return "Ready — click Run Metrics."
            return "Ready — click Run Metrics (nucleus optional for Toward Nucleus)."
        if caps.is_image:
            return "Metrics current. Open Metric Analysis for orientation detail."
        return "Metrics current. Open Metric Analysis for detail, or switch samples."


def nucleus_requires_alignment_review(
    nucleus: Any,
    cutoff: Any,
    *,
    tolerance_px: float = NUCLEUS_CUTOFF_ALIGNMENT_TOLERANCE_PX,
) -> bool:
    """True when a persisted nucleus is off the current cutoff (UI status only)."""
    if nucleus is None or cutoff is None:
        return False
    try:
        return abs(float(nucleus.y) - float(cutoff.y)) > float(tolerance_px)
    except (AttributeError, TypeError, ValueError):
        return False


def crop_confirmed_from_annotation(ann: dict[str, Any] | None) -> bool:
    """Load crop confirmation for legacy documents only.

    Explicit ``crop_confirmed`` wins. When the field is missing and a
    rectangular crop is persisted, treat the crop as confirmed so existing
    projects are not forced through a removed Confirm step.
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
    crop_confirmed: bool = False,
    has_cell_region: bool,
    has_nucleus: bool,
    timing_confirmed: bool,
    metrics_present: bool,
    metrics_stale: bool,
    metrics_running: bool = False,
    has_valid_video_timing: bool | None = None,
    has_cutoff: bool = False,
    nucleus_alignment_needs_review: bool = False,
    media_type: SampleMediaType | str = SampleMediaType.VIDEO,
) -> WorkflowSnapshot:
    video_timing_ready = (
        bool(timing_confirmed)
        if has_valid_video_timing is None
        else bool(has_valid_video_timing)
    )
    return WorkflowSnapshot(
        has_sample=bool(has_sample),
        has_crop=bool(has_crop),
        crop_confirmed=bool(crop_confirmed) and bool(has_crop),
        has_cell_region=bool(has_cell_region),
        has_nucleus=bool(has_nucleus),
        has_cutoff=bool(has_cutoff),
        timing_confirmed=bool(timing_confirmed) or video_timing_ready,
        has_valid_video_timing=video_timing_ready,
        metrics_present=bool(metrics_present),
        metrics_stale=bool(metrics_stale),
        metrics_running=bool(metrics_running),
        nucleus_alignment_needs_review=bool(nucleus_alignment_needs_review),
        media_type=_coerce_media_type(media_type),
    )


@dataclass(frozen=True)
class WorkbenchLiveInputs:
    """Explicit live Workbench facts used to derive readiness.

    MainWindow gathers these; it does not reconstruct ready_to_run itself.
    """

    sample_id: str | None
    has_base_frame: bool
    has_crop: bool
    has_cell_region: bool
    has_nucleus: bool
    has_cutoff: bool
    timing_ready: bool
    metrics_present: bool
    metrics_stale: bool
    metrics_running: bool
    nucleus_alignment_needs_review: bool = False
    media_type: SampleMediaType = SampleMediaType.VIDEO


def snapshot_from_live_inputs(inputs: WorkbenchLiveInputs) -> WorkflowSnapshot:
    """Canonical readiness path for the current sample."""
    has_sample = bool(inputs.sample_id) and bool(inputs.has_base_frame)
    return build_workflow_snapshot(
        has_sample=has_sample,
        has_crop=bool(inputs.has_crop) or bool(inputs.has_cell_region),
        has_cell_region=bool(inputs.has_cell_region),
        has_nucleus=bool(inputs.has_nucleus),
        has_cutoff=bool(inputs.has_cutoff),
        timing_confirmed=bool(inputs.timing_ready),
        has_valid_video_timing=bool(inputs.timing_ready),
        metrics_present=bool(inputs.metrics_present),
        metrics_stale=bool(inputs.metrics_stale),
        metrics_running=bool(inputs.metrics_running),
        nucleus_alignment_needs_review=bool(inputs.nucleus_alignment_needs_review),
        media_type=inputs.media_type,
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
    has_nucleus: bool = True,
    media_type: SampleMediaType | str = SampleMediaType.VIDEO,
) -> str:
    """Concise Workbench Sample Results text from persisted display values."""
    caps = capabilities_for(_coerce_media_type(media_type))

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

    if caps.supports_general_movement:
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
    if caps.supports_optical_flow:
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
    if caps.supports_toward_nucleus:
        lines.append("")
        lines.append("Toward Nucleus")
        if not has_nucleus:
            lines.append("Nucleus required")
        else:
            lines.append(
                _um(toward_nucleus_um_s) if toward_nucleus_um_s is not None else "—"
            )
    if caps.supports_orientation:
        lines.append("")
        lines.append("F-actin Orientation")
        if not has_nucleus:
            lines.append("Nucleus required")
        elif orientation_deg is None:
            lines.append("—")
        else:
            lines.append(f"{float(orientation_deg):.1f}°")
    if caps.supports_general_movement:
        lines.append("")
        lines.append("Tracks")
        if tracks_used is None:
            lines.append("—")
        elif tracks_requested is not None and tracks_requested > tracks_used:
            lines.append(f"{tracks_used} valid / {tracks_requested} requested")
        else:
            lines.append(f"{tracks_used} valid")
    if caps.requires_video_timing:
        lines.append("")
        lines.append("Acquisition Interval")
        lines.append(timing_label or "—")
    return "\n".join(lines)


def format_delete_samples_confirmation(
    *,
    count: int,
    group_name: str | None = None,
) -> tuple[str, str]:
    """Title and body for sample-deletion confirmation.

    One confirmation covers the whole selection. Count 1 keeps the existing
    single-sample wording.
    """
    n = max(0, int(count))
    group = str(group_name or "").strip()
    if n <= 1:
        return "Delete Sample", "Delete this Sample?"
    title = f"Delete {n} Samples"
    if group:
        return title, f"Delete {n} Samples from {group}?"
    return title, f"Delete {n} Samples?"
