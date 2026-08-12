"""Tests for weak filament tip validation fixtures and diagnostics."""

from __future__ import annotations

import unittest

import numpy as np

from actintrack_app.weak_tip_validation import (
    DEFAULT_VALIDATION_PARAMS,
    TipAnnotation,
    all_weak_tip_fixtures,
    baseline_summary_rows,
    bleaching_sequence_fixture,
    boundary_tip_fixture,
    bright_control_fixture,
    candidate_precision_proxy,
    candidate_recall,
    competing_bright_fixture,
    diagnose_candidates,
    enumerate_starting_point_candidates,
    mean_endpoint_error_px,
    render_diagnostic_overlay,
    run_fixture_baseline,
    tapering_filament_fixture,
)


class WeakTipFixtureTests(unittest.TestCase):
    def test_all_fixtures_are_deterministic(self) -> None:
        first = [fixture.name for fixture in all_weak_tip_fixtures()]
        second = [fixture.name for fixture in all_weak_tip_fixtures()]
        self.assertEqual(first, second)
        self.assertEqual(
            first,
            [
                "bright_control",
                "tapering_filament",
                "bleaching_sequence",
                "competing_bright",
                "boundary_tip",
            ],
        )

    def test_fixture_frame_shapes_are_stable(self) -> None:
        for fixture in all_weak_tip_fixtures():
            with self.subTest(fixture=fixture.name):
                self.assertGreaterEqual(len(fixture.frames), 1)
                shape = fixture.frames[0].shape
                for frame in fixture.frames:
                    self.assertEqual(frame.shape, shape)

    def test_bright_control_fixture_has_positive_tip_signal(self) -> None:
        fixture = bright_control_fixture()
        diagnostics = diagnose_candidates(fixture.frames[0], fixture.tips, DEFAULT_VALIDATION_PARAMS)
        self.assertGreater(diagnostics[0].expected_signal, 100.0)


class CandidateDiagnosticTests(unittest.TestCase):
    def test_nearest_candidate_distance_calculation(self) -> None:
        fixture = bright_control_fixture()
        diagnostics = diagnose_candidates(fixture.frames[0], fixture.tips, DEFAULT_VALIDATION_PARAMS)
        self.assertEqual(len(diagnostics), 1)
        self.assertLess(diagnostics[0].distance_px, fixture.tips[0].tolerance_px)

    def test_tolerance_handling(self) -> None:
        fixture = bright_control_fixture()
        tip = fixture.tips[0]
        loose = TipAnnotation(
            frame_index=tip.frame_index,
            x=tip.x + 25.0,
            y=tip.y + 18.0,
            tolerance_px=3.0,
            label=tip.label,
            note=tip.note,
        )
        diagnostics = diagnose_candidates(fixture.frames[0], (loose,), DEFAULT_VALIDATION_PARAMS)
        self.assertFalse(diagnostics[0].within_tolerance)

    def test_candidate_ranking_is_reproducible(self) -> None:
        fixture = bright_control_fixture()
        first = enumerate_starting_point_candidates(fixture.frames[0], DEFAULT_VALIDATION_PARAMS)
        second = enumerate_starting_point_candidates(fixture.frames[0], DEFAULT_VALIDATION_PARAMS)
        self.assertEqual(first, second)
        self.assertTrue(any(candidate.selected for candidate in first))


class BaselineBehaviorTests(unittest.TestCase):
    def test_bright_control_baseline_succeeds(self) -> None:
        result = run_fixture_baseline(bright_control_fixture())
        self.assertEqual(result.candidate_recall, 1.0)
        self.assertTrue(result.candidate_diagnostics[0].within_tolerance)
        self.assertIsNotNone(result.mean_endpoint_error_px)
        assert result.mean_endpoint_error_px is not None
        self.assertLess(result.mean_endpoint_error_px, 4.0)

    def test_tapering_tip_baseline_records_current_failure(self) -> None:
        result = run_fixture_baseline(tapering_filament_fixture())
        candidate = result.candidate_diagnostics[0]
        self.assertFalse(candidate.within_tolerance)
        self.assertGreater(candidate.distance_px, candidate.tip.tolerance_px)
        self.assertLess(result.candidate_recall, 1.0)

    def test_bleaching_baseline_records_tracking_survival(self) -> None:
        result = run_fixture_baseline(bleaching_sequence_fixture())
        tracking = result.tracking_diagnostics[0]
        self.assertGreaterEqual(tracking.survival_frames, 1)
        if tracking.track_id is not None:
            self.assertGreaterEqual(tracking.survival_frames, 2)

    def test_competitor_fixture_reports_jump_diagnostic_field(self) -> None:
        result = run_fixture_baseline(competing_bright_fixture())
        tracking = result.tracking_diagnostics[0]
        self.assertIsInstance(tracking.jumped_to_competitor, bool)

    def test_boundary_fixture_baseline_is_measurable(self) -> None:
        result = run_fixture_baseline(boundary_tip_fixture())
        candidate = result.candidate_diagnostics[0]
        self.assertGreater(candidate.distance_px, 0.0)
        self.assertIsNotNone(candidate.nearest_rank)

    def test_baseline_summary_rows_cover_all_fixtures(self) -> None:
        rows = baseline_summary_rows()
        self.assertEqual(len(rows), 5)
        names = {row["fixture"] for row in rows}
        self.assertIn("bright_control", names)
        self.assertIn("tapering_filament", names)

    def test_diagnostic_metrics_are_reproducible(self) -> None:
        fixture = tapering_filament_fixture()
        first = run_fixture_baseline(fixture)
        second = run_fixture_baseline(fixture)
        self.assertEqual(first.candidate_recall, second.candidate_recall)
        self.assertEqual(
            first.candidate_diagnostics[0].distance_px,
            second.candidate_diagnostics[0].distance_px,
        )

    def test_candidate_recall_and_precision_helpers(self) -> None:
        fixture = bright_control_fixture()
        diagnostics = diagnose_candidates(fixture.frames[0], fixture.tips, DEFAULT_VALIDATION_PARAMS)
        self.assertEqual(candidate_recall(diagnostics), 1.0)
        precision = candidate_precision_proxy(
            fixture.frames[0],
            fixture.tips,
            DEFAULT_VALIDATION_PARAMS,
        )
        self.assertIsNotNone(precision)
        self.assertGreater(precision or 0.0, 0.0)
        error = mean_endpoint_error_px(diagnostics)
        self.assertIsNotNone(error)


class DiagnosticOverlayTests(unittest.TestCase):
    def test_render_diagnostic_overlay_returns_image(self) -> None:
        fixture = bright_control_fixture()
        result = run_fixture_baseline(fixture)
        overlay = render_diagnostic_overlay(
            fixture.frames[0],
            fixture.tips,
            result.starting_points,
            result.tracks,
            0,
        )
        self.assertEqual(overlay.shape, fixture.frames[0].shape)
        self.assertFalse(np.array_equal(overlay, fixture.frames[0]))


if __name__ == "__main__":
    unittest.main()
