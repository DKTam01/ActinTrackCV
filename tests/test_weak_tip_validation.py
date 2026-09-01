"""Tests for weak filament tip validation fixtures and diagnostics."""

from __future__ import annotations

import math
import unittest

import cv2
import numpy as np

from actintrack_app.motion_index import MotionIndexParams, select_starting_points
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

    def test_tapering_tip_localizes_within_tolerance(self) -> None:
        result = run_fixture_baseline(tapering_filament_fixture())
        candidate = result.candidate_diagnostics[0]
        self.assertTrue(candidate.within_tolerance)
        self.assertLess(candidate.distance_px, candidate.tip.tolerance_px)
        self.assertEqual(result.candidate_recall, 1.0)

    def test_competing_bright_localizes_weak_tip_without_jumping(self) -> None:
        result = run_fixture_baseline(competing_bright_fixture())
        candidate = result.candidate_diagnostics[0]
        self.assertTrue(candidate.within_tolerance)
        tracking = result.tracking_diagnostics[0]
        self.assertFalse(tracking.jumped_to_competitor)

    def test_boundary_tip_localizes_within_tolerance(self) -> None:
        result = run_fixture_baseline(boundary_tip_fixture())
        candidate = result.candidate_diagnostics[0]
        self.assertTrue(candidate.within_tolerance)

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


class WeakFilamentCandidateSelectionTests(unittest.TestCase):
    def test_bright_control_seed_unchanged(self) -> None:
        fixture = bright_control_fixture()
        tip = fixture.tips[0]
        starts = select_starting_points(fixture.frames[0], DEFAULT_VALIDATION_PARAMS)
        nearest = min(starts, key=lambda s: math.hypot(s[0] - tip.x, s[1] - tip.y))
        self.assertLess(math.hypot(nearest[0] - tip.x, nearest[1] - tip.y), tip.tolerance_px)

    def test_taper_extension_reaches_supported_weak_structure(self) -> None:
        fixture = tapering_filament_fixture()
        tip = fixture.tips[0]
        starts = select_starting_points(fixture.frames[0], DEFAULT_VALIDATION_PARAMS)
        nearest = min(starts, key=lambda s: math.hypot(s[0] - tip.x, s[1] - tip.y))
        self.assertGreater(nearest[0], 70.0)
        self.assertAlmostEqual(nearest[1], tip.y, delta=2.0)
        self.assertLess(math.hypot(nearest[0] - tip.x, nearest[1] - tip.y), tip.tolerance_px)

    def test_round_dim_blob_is_not_extended(self) -> None:
        frame = np.full((96, 112, 3), 12, dtype=np.uint8)
        center = (56, 48)
        cv2.circle(frame, center, 4, (28, 28, 28), thickness=-1)
        params = MotionIndexParams(
            num_starting_points=1,
            min_point_spacing_px=12,
            search_radius_px=8,
            template_patch_size_px=11,
            min_template_confidence=0.55,
        )
        starts = select_starting_points(frame, params)
        self.assertEqual(len(starts), 1)
        x, y = starts[0]
        self.assertLess(math.hypot(x - center[0], y - center[1]), 6.0)

    def test_competitor_does_not_steal_supported_weak_tip(self) -> None:
        fixture = competing_bright_fixture()
        tip = fixture.tips[0]
        starts = select_starting_points(fixture.frames[0], DEFAULT_VALIDATION_PARAMS)
        nearest = min(starts, key=lambda s: math.hypot(s[0] - tip.x, s[1] - tip.y))
        self.assertLess(math.hypot(nearest[0] - tip.x, nearest[1] - tip.y), tip.tolerance_px)
        self.assertGreater(nearest[1], 50.0)

    def test_candidate_ordering_is_deterministic(self) -> None:
        fixture = tapering_filament_fixture()
        first = select_starting_points(fixture.frames[0], DEFAULT_VALIDATION_PARAMS)
        second = select_starting_points(fixture.frames[0], DEFAULT_VALIDATION_PARAMS)
        self.assertEqual(first, second)

    def test_spacing_remains_enforced_after_extension(self) -> None:
        frame = np.full((120, 120, 3), 12, dtype=np.uint8)
        for offset in (0, 40):
            cv2.line(
                frame,
                (20, 60 + offset),
                (95, 60 + offset),
                (220 - (offset * 2), 220 - (offset * 2), 220 - (offset * 2)),
                thickness=2,
                lineType=cv2.LINE_AA,
            )
        params = MotionIndexParams(
            num_starting_points=4,
            min_point_spacing_px=20,
            search_radius_px=8,
            template_patch_size_px=11,
            min_template_confidence=0.55,
        )
        starts = select_starting_points(frame, params)
        for i, (x0, y0) in enumerate(starts):
            for x1, y1 in starts[i + 1 :]:
                self.assertGreaterEqual(math.hypot(x0 - x1, y0 - y1), params.min_point_spacing_px)

    def test_all_validation_fixtures_meet_recall_target(self) -> None:
        for fixture in all_weak_tip_fixtures():
            with self.subTest(fixture=fixture.name):
                result = run_fixture_baseline(fixture)
                self.assertEqual(result.candidate_recall, 1.0)


if __name__ == "__main__":
    unittest.main()
