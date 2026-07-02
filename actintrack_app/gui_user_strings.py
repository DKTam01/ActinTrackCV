"""User-facing display labels (internal status codes and keys unchanged)."""

from __future__ import annotations

# Processing status codes → readable labels (Filtered Cleanup dialog, previews).
PROCESSING_STATUS_DISPLAY: dict[str, str] = {
    "raw_imported": "Imported",
    "unannotated": "Unannotated",
    "imported": "Imported",
    "roi_marked": "ROI marked",
    "roi_propagated_needs_review": "ROI propagated — needs review",
    "roi_approved": "ROI approved",
    "processed": "Processed",
    "motion_index_generated": "Metrics generated",
    "motion_index_failed": "Metrics failed",
    "failed": "Failed",
    "missing_file": "Missing file",
}


def processing_status_display(status_code: str) -> str:
    code = str(status_code).strip()
    if not code:
        return ""
    return PROCESSING_STATUS_DISPLAY.get(
        code,
        code.replace("_", " ").capitalize(),
    )
