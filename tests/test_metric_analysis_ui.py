"""CLEAN1 Metric Analysis empty-state and orientation-legend helpers."""

from __future__ import annotations

import unittest

from actintrack_app.metric_analysis_ui import (
    ORIENTATION_LEGEND_TEXT,
    cached_analysis_matches_draft_run,
    draft_analysis_run_id,
    empty_state_message_for_mode,
)
from actintrack_app.workflow_state import nucleus_requires_alignment_review


class _Point:
    def __init__(self, y: float) -> None:
        self.y = y


class MetricAnalysisUiTests(unittest.TestCase):
    def test_empty_state_matches_inspection_mode(self) -> None:
        self.assertEqual(
            empty_state_message_for_mode("orientation"),
            "F-actin Orientation has not been generated for this sample.",
        )
        self.assertEqual(
            empty_state_message_for_mode("optical_flow"),
            "Optical Flow has not been generated for this sample.",
        )
        self.assertEqual(
            empty_state_message_for_mode("template"),
            "Tracking results have not been generated for this sample.",
        )
        self.assertEqual(
            empty_state_message_for_mode(None),
            empty_state_message_for_mode("template"),
        )

    def test_orientation_legend_is_compact_and_explicit(self) -> None:
        self.assertEqual(ORIENTATION_LEGEND_TEXT, "0° = radial · 90° = tangential")
        self.assertIn("0° = radial", ORIENTATION_LEGEND_TEXT)
        self.assertIn("90° = tangential", ORIENTATION_LEGEND_TEXT)
        self.assertNotIn("motion", ORIENTATION_LEGEND_TEXT.lower())
        self.assertEqual(ORIENTATION_LEGEND_TEXT.lower().count("radial"), 1)
        self.assertEqual(ORIENTATION_LEGEND_TEXT.lower().count("tangential"), 1)

    def test_cached_analysis_matches_current_draft_run_only(self) -> None:
        self.assertEqual(
            draft_analysis_run_id({"analysis_run_id": "run-2"}),
            "run-2",
        )
        self.assertTrue(cached_analysis_matches_draft_run("run-2", "run-2"))
        self.assertFalse(cached_analysis_matches_draft_run("run-1", "run-2"))
        self.assertTrue(cached_analysis_matches_draft_run("run-1", ""))


class NucleusAlignmentReviewTests(unittest.TestCase):
    def test_aligned_nucleus_does_not_need_review(self) -> None:
        self.assertFalse(
            nucleus_requires_alignment_review(_Point(12.0), _Point(12.0))
        )
        self.assertFalse(
            nucleus_requires_alignment_review(_Point(12.2), _Point(12.0))
        )

    def test_misaligned_nucleus_needs_review_without_mutating(self) -> None:
        nucleus = _Point(8.0)
        cutoff = _Point(16.0)
        self.assertTrue(nucleus_requires_alignment_review(nucleus, cutoff))
        self.assertEqual(nucleus.y, 8.0)
        self.assertEqual(cutoff.y, 16.0)

    def test_missing_nucleus_or_cutoff_is_not_review(self) -> None:
        self.assertFalse(nucleus_requires_alignment_review(None, _Point(10.0)))
        self.assertFalse(nucleus_requires_alignment_review(_Point(10.0), None))


if __name__ == "__main__":
    unittest.main()
