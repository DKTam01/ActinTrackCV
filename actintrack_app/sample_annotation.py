"""Propagate orientation + ROI within samples and breeds."""

from __future__ import annotations

from actintrack_app.batch_annotation import (  # noqa: F401
    propagate_annotation,
    resolve_propagation_targets,
    save_propagated_annotations,
)
