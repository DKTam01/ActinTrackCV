"""Scientific tests for true temporal track reacquisition (Phase R4)."""

from __future__ import annotations

import unittest

import numpy as np

from actintrack_app.motion_index import (
    TRACKING_METHOD_BRIGHTEST_LOCAL,
    TRACKING_METHOD_TEMPLATE,
    MotionIndexParams,
    compute_step_metrics,
    track_points,
)
from actintrack_app.weak_tip_validation import bleaching_sequence_fixture


def _spot_frame(
    spots: list[tuple[float, float, float]],
    *,
    shape: tuple[int, int] = (80, 80),
    background: float = 0.0,
) -> np.ndarray:
    frame = np.full(shape, background, dtype=np.float32)
    for x, y, intensity in spots:
        cx = int(round(x))
        cy = int(round(y))
        frame[cy - 1 : cy + 2, cx - 1 : cx + 2] = intensity
    return frame


def _params(method: str, *, lookahead: int) -> MotionIndexParams:
    return MotionIndexParams(
        num_starting_points=1,
        min_point_spacing_px=8,
        search_radius_px=4,
        template_patch_size_px=5,
        min_template_confidence=0.15,
        lookahead_frames=lookahead,
        microns_per_pixel=1.0,
        seconds_per_frame=2.0,
        tracking_method=method,
    )


class TemporalReacquisitionTests(unittest.TestCase):
    def test_one_missing_frame_recovers_in_both_modes(self) -> None:
        frames = [
            _spot_frame([(20, 24, 220)]),
            _spot_frame([]),
            _spot_frame([(24, 24, 200)]),
            _spot_frame([(26, 24, 190)]),
        ]
        for method in (TRACKING_METHOD_BRIGHTEST_LOCAL, TRACKING_METHOD_TEMPLATE):
            with self.subTest(method=method):
                track = track_points(
                    frames,
                    [(20.0, 24.0)],
                    _params(method, lookahead=1),
                )[0]
                self.assertEqual([p.frame_index for p in track.points], [0, 2, 3])
                self.assertTrue(track.points[1].recovered_with_lookahead)
                self.assertFalse(track.points[2].recovered_with_lookahead)
                self.assertEqual(track.end_reason, "reached_last_frame")

    def test_two_missing_frames_recover_only_when_lookahead_permits(self) -> None:
        frames = [
            _spot_frame([(20, 24, 220)]),
            _spot_frame([]),
            _spot_frame([]),
            _spot_frame([(26, 24, 200)]),
            _spot_frame([(28, 24, 190)]),
        ]
        for method in (TRACKING_METHOD_BRIGHTEST_LOCAL, TRACKING_METHOD_TEMPLATE):
            with self.subTest(method=method):
                recovered = track_points(
                    frames,
                    [(20.0, 24.0)],
                    _params(method, lookahead=2),
                )[0]
                self.assertEqual(
                    [p.frame_index for p in recovered.points],
                    [0, 3, 4],
                )
                self.assertTrue(recovered.points[1].recovered_with_lookahead)

                terminated = track_points(
                    frames,
                    [(20.0, 24.0)],
                    _params(method, lookahead=1),
                )[0]
                self.assertEqual(len(terminated.points), 1)
                self.assertEqual(
                    terminated.end_reason,
                    "lost_after_lookahead_from_frame_0",
                )

    def test_future_candidate_outside_cell_region_never_recovers(self) -> None:
        frames = [
            _spot_frame([(20, 24, 220)]),
            _spot_frame([]),
            _spot_frame([(42, 24, 255)]),
        ]
        valid = np.zeros((80, 80), dtype=bool)
        valid[8:60, 8:35] = True
        track = track_points(
            frames,
            [(20.0, 24.0)],
            _params(TRACKING_METHOD_BRIGHTEST_LOCAL, lookahead=1),
            valid_mask=valid,
        )[0]
        self.assertEqual(len(track.points), 1)
        self.assertEqual(track.end_reason, "lost_after_lookahead_from_frame_0")

    def test_future_candidate_below_cutoff_never_recovers(self) -> None:
        frames = [
            _spot_frame([(20, 20, 220)]),
            _spot_frame([]),
            _spot_frame([(24, 45, 255)]),
        ]
        valid = np.ones((80, 80), dtype=bool)
        valid[31:, :] = False
        track = track_points(
            frames,
            [(20.0, 20.0)],
            _params(TRACKING_METHOD_BRIGHTEST_LOCAL, lookahead=1),
            valid_mask=valid,
        )[0]
        self.assertEqual(len(track.points), 1)
        self.assertTrue(all(point.y <= 30.0 for point in track.points))

    def test_valid_dimmer_future_candidate_beats_invalid_brighter_distractor(self) -> None:
        frames = [
            _spot_frame([(20, 24, 220)]),
            _spot_frame([]),
            _spot_frame([(24, 24, 110), (35, 24, 255)]),
        ]
        valid = np.ones((80, 80), dtype=bool)
        valid[:, 30:] = False
        track = track_points(
            frames,
            [(20.0, 24.0)],
            _params(TRACKING_METHOD_BRIGHTEST_LOCAL, lookahead=1),
            valid_mask=valid,
        )[0]
        self.assertEqual([p.frame_index for p in track.points], [0, 2])
        self.assertAlmostEqual(track.points[-1].x, 24.0, delta=2.0)
        self.assertTrue(valid[int(round(track.points[-1].y)), int(round(track.points[-1].x))])

    def test_recovered_step_uses_actual_elapsed_time(self) -> None:
        frames = [
            _spot_frame([(20, 24, 220)]),
            _spot_frame([]),
            _spot_frame([(26, 24, 200)]),
        ]
        params = _params(TRACKING_METHOD_BRIGHTEST_LOCAL, lookahead=1)
        track = track_points(frames, [(20.0, 24.0)], params)[0]
        step = compute_step_metrics(track.points[0], track.points[1], params)
        self.assertEqual(step.frame_gap, 2)
        self.assertAlmostEqual(step.dt_s, 4.0)
        self.assertAlmostEqual(step.displacement_px, 6.0, delta=1.0)
        self.assertAlmostEqual(
            step.absolute_velocity_um_per_s,
            step.displacement_px / 4.0,
        )

    def test_future_claims_prevent_track_collision(self) -> None:
        frames = [
            _spot_frame([(20, 24, 220), (32, 24, 210)]),
            _spot_frame([]),
            _spot_frame([(26, 24, 220)]),
        ]
        params = MotionIndexParams(
            num_starting_points=2,
            min_point_spacing_px=8,
            search_radius_px=6,
            template_patch_size_px=5,
            min_template_confidence=0.15,
            lookahead_frames=1,
            microns_per_pixel=1.0,
            seconds_per_frame=1.0,
            tracking_method=TRACKING_METHOD_BRIGHTEST_LOCAL,
        )
        tracks = track_points(frames, [(20.0, 24.0), (32.0, 24.0)], params)
        recovered = [
            track
            for track in tracks
            if len(track.points) == 2
            and track.points[-1].recovered_with_lookahead
        ]
        self.assertEqual(len(recovered), 1)

    def test_no_gap_behavior_is_unchanged_when_lookahead_enabled(self) -> None:
        frames = [
            _spot_frame([(20 + (2 * index), 24 + index, 220 - index)])
            for index in range(5)
        ]
        for method in (TRACKING_METHOD_BRIGHTEST_LOCAL, TRACKING_METHOD_TEMPLATE):
            with self.subTest(method=method):
                without = track_points(
                    frames,
                    [(20.0, 24.0)],
                    _params(method, lookahead=0),
                )[0]
                with_lookahead = track_points(
                    frames,
                    [(20.0, 24.0)],
                    _params(method, lookahead=2),
                )[0]
                self.assertEqual(
                    [
                        (p.frame_index, p.x, p.y, p.confidence)
                        for p in without.points
                    ],
                    [
                        (p.frame_index, p.x, p.y, p.confidence)
                        for p in with_lookahead.points
                    ],
                )
                self.assertTrue(
                    all(not p.recovered_with_lookahead for p in with_lookahead.points)
                )

    def test_weak_bleaching_fixture_behavior_remains_valid(self) -> None:
        fixture = bleaching_sequence_fixture(frame_count=6)
        params = MotionIndexParams(
            num_starting_points=1,
            min_point_spacing_px=8,
            search_radius_px=5,
            template_patch_size_px=5,
            min_template_confidence=0.15,
            lookahead_frames=1,
            microns_per_pixel=1.0,
            seconds_per_frame=1.0,
            tracking_method=TRACKING_METHOD_BRIGHTEST_LOCAL,
        )
        track = track_points(
            fixture.frames,
            [(fixture.tips[0].x, fixture.tips[0].y)],
            params,
        )[0]
        self.assertGreaterEqual(len(track.points), 5)
        self.assertEqual(track.points[0].frame_index, 0)


if __name__ == "__main__":
    unittest.main()
