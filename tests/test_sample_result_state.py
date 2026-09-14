"""Direct tests for sample result freshness and scientific-edit invalidation."""

from __future__ import annotations

import unittest

from actintrack_app.sample_result_state import (
    classify_metric_state,
    clear_sample_stale,
    draft_results_are_measurable,
    inspection_is_blocked_by_staleness,
    invalidation_for_scientific_edit,
    sample_is_stale,
    scientific_state_key_from_annotation,
    set_sample_stale,
)
from actintrack_app.workflow_state import (
    WorkbenchLiveInputs,
    snapshot_from_live_inputs,
)


class DraftMeasurableTests(unittest.TestCase):
    def test_tracking_or_of_is_enough(self) -> None:
        self.assertTrue(
            draft_results_are_measurable(
                {"num_tracks_with_valid_steps": 2},
                None,
            )
        )
        self.assertTrue(
            draft_results_are_measurable(None, {"has_valid_result": True})
        )
        self.assertFalse(draft_results_are_measurable(None, None))
        self.assertFalse(
            draft_results_are_measurable({"num_tracks_with_valid_steps": 0}, None)
        )


class FreshnessFlagTests(unittest.TestCase):
    def test_either_flag_marks_sample_stale(self) -> None:
        track = {"S1": True}
        of_flags: dict[str, bool] = {}
        self.assertTrue(sample_is_stale(track, of_flags, "S1"))
        self.assertFalse(sample_is_stale(track, of_flags, "S2"))
        set_sample_stale(track, of_flags, "S2")
        self.assertTrue(sample_is_stale(track, of_flags, "S2"))
        clear_sample_stale(track, of_flags, "S2")
        self.assertFalse(sample_is_stale(track, of_flags, "S2"))

    def test_stale_blocks_inspection(self) -> None:
        self.assertTrue(
            inspection_is_blocked_by_staleness({"S1": True}, {}, "S1")
        )
        self.assertFalse(
            inspection_is_blocked_by_staleness({}, {}, "S1")
        )


class InvalidationPolicyTests(unittest.TestCase):
    def test_no_geometry_change_is_a_noop(self) -> None:
        effects = invalidation_for_scientific_edit(
            had_measurable_results=True,
            geometry_changed=False,
        )
        self.assertFalse(effects.mark_stale)
        self.assertFalse(effects.clear_live_caches)

    def test_geometry_change_without_results_clears_caches_only(self) -> None:
        effects = invalidation_for_scientific_edit(
            had_measurable_results=False,
            geometry_changed=True,
        )
        self.assertFalse(effects.mark_stale)
        self.assertTrue(effects.clear_live_caches)
        self.assertTrue(effects.discard_inspection_if_current)

    def test_geometry_change_with_results_marks_stale(self) -> None:
        effects = invalidation_for_scientific_edit(
            had_measurable_results=True,
            geometry_changed=True,
        )
        self.assertTrue(effects.mark_stale)
        self.assertTrue(effects.clear_live_caches)
        self.assertTrue(effects.discard_inspection_if_current)


class MetricStateClassificationTests(unittest.TestCase):
    def test_no_nucleus_does_not_affect_gm_of_state(self) -> None:
        state = classify_metric_state(
            sample_id="S1",
            has_valid_data_and_roi=True,
            running=False,
            track={"num_tracks_with_valid_steps": 3},
            optical_flow={"has_valid_result": True},
            stale=False,
            error_flag=False,
        )
        self.assertEqual(state, "analyzed")

    def test_stale_wins_over_present_results(self) -> None:
        state = classify_metric_state(
            sample_id="S1",
            has_valid_data_and_roi=True,
            running=False,
            track={"num_tracks_with_valid_steps": 3},
            optical_flow={"has_valid_result": True},
            stale=True,
            error_flag=False,
        )
        self.assertEqual(state, "stale")

    def test_running_before_payload_inspection(self) -> None:
        state = classify_metric_state(
            sample_id="S1",
            has_valid_data_and_roi=False,
            running=True,
            track=None,
            optical_flow=None,
            stale=False,
            error_flag=False,
        )
        self.assertEqual(state, "running")


class ScientificStateKeyTests(unittest.TestCase):
    def test_empty_annotation_is_empty_key(self) -> None:
        self.assertEqual(scientific_state_key_from_annotation(None), ())
        self.assertEqual(scientific_state_key_from_annotation({}), ())


class LiveReadinessTests(unittest.TestCase):
    def test_run_metrics_without_nucleus(self) -> None:
        snap = snapshot_from_live_inputs(
            WorkbenchLiveInputs(
                sample_id="S1",
                has_base_frame=True,
                has_crop=True,
                has_cell_region=True,
                has_nucleus=False,
                has_cutoff=True,
                timing_ready=True,
                metrics_present=False,
                metrics_stale=False,
                metrics_running=False,
            )
        )
        self.assertTrue(snap.ready_to_run)
        self.assertFalse(snap.can_compute_nucleus_metrics)
        self.assertFalse(snap.metric_analysis_allowed)

    def test_cell_region_implies_computational_crop(self) -> None:
        snap = snapshot_from_live_inputs(
            WorkbenchLiveInputs(
                sample_id="S1",
                has_base_frame=True,
                has_crop=False,
                has_cell_region=True,
                has_nucleus=True,
                has_cutoff=True,
                timing_ready=True,
                metrics_present=True,
                metrics_stale=False,
                metrics_running=False,
            )
        )
        self.assertTrue(snap.has_crop)
        self.assertTrue(snap.ready_to_run)
        self.assertTrue(snap.can_compute_nucleus_metrics)
        self.assertTrue(snap.metric_analysis_allowed)

    def test_alignment_review_does_not_block_run(self) -> None:
        snap = snapshot_from_live_inputs(
            WorkbenchLiveInputs(
                sample_id="S1",
                has_base_frame=True,
                has_crop=True,
                has_cell_region=True,
                has_nucleus=True,
                has_cutoff=True,
                timing_ready=True,
                metrics_present=True,
                metrics_stale=True,
                metrics_running=False,
                nucleus_alignment_needs_review=True,
            )
        )
        self.assertTrue(snap.ready_to_run)
        self.assertTrue(snap.nucleus_alignment_needs_review)
        self.assertFalse(snap.metric_analysis_allowed)


if __name__ == "__main__":
    unittest.main()
