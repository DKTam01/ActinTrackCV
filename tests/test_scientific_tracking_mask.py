"""Hard scientific-validity domain for point tracking (Phase R3)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from actintrack_app.annotation_schema import build_sample_annotation
from actintrack_app.gui import MainWindow
from actintrack_app.motion_index import (
    TRACKING_METHOD_BRIGHTEST_LOCAL,
    TRACKING_METHOD_TEMPLATE,
    MotionIndexParams,
    _brightest_point_in_window,
    _match_template_in_window,
    _refine_starting_point_with_filament_support,
    _try_match_step,
    select_starting_points,
    track_points,
    TrackPoint,
)
from actintrack_app.orientation import OrientationState, RectROI
from actintrack_app.preview_workflow import analyze_cropped_preview
from actintrack_app.scientific_annotations import (
    CellRegion,
    CutoffBoundary,
    scientific_valid_mask_for_tracking,
    valid_mask_crop_local,
)


def _spot_frame(
    spots: list[tuple[float, float, float]],
    *,
    shape: tuple[int, int] = (80, 80),
) -> np.ndarray:
    frame = np.zeros(shape, dtype=np.float32)
    for x, y, intensity in spots:
        cx = int(round(x))
        cy = int(round(y))
        frame[max(0, cy - 1) : cy + 2, max(0, cx - 1) : cx + 2] = intensity
    return frame


def _params(**kwargs: object) -> MotionIndexParams:
    defaults: dict[str, object] = {
        "num_starting_points": 1,
        "min_point_spacing_px": 8,
        "search_radius_px": 8,
        "min_template_confidence": 0.15,
        "template_patch_size_px": 5,
        "microns_per_pixel": 1.0,
        "seconds_per_frame": 1.0,
        "lookahead_frames": 0,
        "tracking_method": TRACKING_METHOD_BRIGHTEST_LOCAL,
    }
    defaults.update(kwargs)
    return MotionIndexParams(**defaults)  # type: ignore[arg-type]


def _rect_mask(h: int, w: int, x: int, y: int, width: int, height: int) -> np.ndarray:
    mask = np.zeros((h, w), dtype=bool)
    mask[y : y + height, x : x + width] = True
    return mask


class SeedValidityMaskTests(unittest.TestCase):
    def test_all_true_mask_matches_legacy_starts(self) -> None:
        frame = _spot_frame([(20, 24, 200), (50, 24, 180)])
        params = _params(num_starting_points=2)
        legacy = select_starting_points(frame, params)
        masked = select_starting_points(
            frame, params, valid_mask=np.ones((80, 80), dtype=bool)
        )
        self.assertEqual(len(legacy), len(masked))
        for (x0, y0), (x1, y1) in zip(legacy, masked):
            self.assertAlmostEqual(x0, x1, places=5)
            self.assertAlmostEqual(y0, y1, places=5)

    def test_invalid_bright_point_outside_region_never_selected(self) -> None:
        frame = _spot_frame([(20, 24, 80), (55, 24, 255)])
        mask = _rect_mask(80, 80, 10, 10, 25, 30)
        params = _params(num_starting_points=2)
        starts = select_starting_points(frame, params, valid_mask=mask)
        self.assertGreaterEqual(len(starts), 1)
        for x, y in starts:
            self.assertTrue(mask[int(round(y)), int(round(x))])
            self.assertGreater(abs(x - 55.0), 8.0)
        self.assertLess(starts[0][0], 40)
        self.assertAlmostEqual(starts[0][0], 20.0, delta=3.0)

    def test_invalid_brighter_point_cannot_beat_dimmer_valid_point(self) -> None:
        frame = _spot_frame([(22, 24, 90), (60, 24, 250)])
        mask = _rect_mask(80, 80, 8, 8, 30, 40)
        starts = select_starting_points(frame, _params(), valid_mask=mask)
        self.assertEqual(len(starts), 1)
        self.assertAlmostEqual(starts[0][0], 22.0, delta=2.0)

    def test_cutoff_excludes_otherwise_good_starting_point(self) -> None:
        frame = _spot_frame([(24, 20, 200), (24, 55, 220)])
        crop = RectROI(0, 0, 80, 80)
        mask = valid_mask_crop_local(crop, cutoff=CutoffBoundary(y=35.0))
        starts = select_starting_points(
            frame, _params(num_starting_points=2), valid_mask=mask
        )
        self.assertGreaterEqual(len(starts), 1)
        for _x, y in starts:
            self.assertLessEqual(y, 35.0)
        self.assertAlmostEqual(starts[0][0], 24.0, delta=3.0)
        self.assertAlmostEqual(starts[0][1], 20.0, delta=3.0)

    def test_all_false_mask_returns_no_starting_points(self) -> None:
        frame = _spot_frame([(24, 24, 255)])
        starts = select_starting_points(
            frame, _params(), valid_mask=np.zeros((80, 80), dtype=bool)
        )
        self.assertEqual(starts, [])

    def test_mask_shape_mismatch_fails_clearly(self) -> None:
        frame = _spot_frame([(24, 24, 255)])
        with self.assertRaises(ValueError) as ctx:
            select_starting_points(
                frame, _params(), valid_mask=np.ones((10, 10), dtype=bool)
            )
        self.assertIn("valid_mask shape", str(ctx.exception))

    def test_spacing_remains_among_valid_points(self) -> None:
        frame = _spot_frame([(18, 24, 200), (28, 24, 190), (55, 24, 255)])
        mask = _rect_mask(80, 80, 8, 8, 40, 40)
        starts = select_starting_points(
            frame,
            _params(num_starting_points=2, min_point_spacing_px=12),
            valid_mask=mask,
        )
        self.assertEqual(len(starts), 2)
        dx = starts[0][0] - starts[1][0]
        dy = starts[0][1] - starts[1][1]
        self.assertGreaterEqual((dx * dx) + (dy * dy), 12.0 * 12.0)

    def test_weak_filament_refinement_cannot_land_outside_mask(self) -> None:
        frame = np.zeros((80, 80), dtype=np.float32)
        frame[24, 16:60] = 180
        frame[23:26, 16:60] = 160
        frame[24, 18] = 220
        signal = frame
        mask = np.ones((80, 80), dtype=bool)
        mask[:, 40:] = False
        seed_mask = np.ones((80, 80), dtype=bool)
        x, y = _refine_starting_point_with_filament_support(
            signal,
            18.0,
            24.0,
            valid_mask=seed_mask & mask,
            border_half=2,
            search_radius_px=20,
        )
        self.assertTrue(mask[int(round(y)), int(round(x))])
        self.assertLess(x, 40.0)


class TrackingValidityMaskTests(unittest.TestCase):
    def test_point_inside_valid_region_matches_legacy_track(self) -> None:
        frames = [_spot_frame([(24 + i, 24, 220)]) for i in range(4)]
        params = _params(search_radius_px=6)
        starts = select_starting_points(frames[0], params)
        legacy = track_points(frames, starts, params)
        masked = track_points(
            frames, starts, params, valid_mask=np.ones((80, 80), dtype=bool)
        )
        self.assertEqual(len(legacy[0].points), len(masked[0].points))
        self.assertEqual(masked[0].end_reason, "reached_last_frame")

    def test_brightest_local_does_not_jump_to_invalid_distractor(self) -> None:
        frames = [
            _spot_frame([(24, 24, 180)]),
            _spot_frame([(26, 24, 120), (50, 24, 255)]),
        ]
        mask = _rect_mask(80, 80, 8, 8, 30, 40)
        params = _params(search_radius_px=30)
        tracks = track_points(frames, [(24.0, 24.0)], params, valid_mask=mask)
        self.assertEqual(len(tracks[0].points), 2)
        self.assertLess(tracks[0].points[1].x, 40.0)

    def test_template_does_not_accept_invalid_candidate_center(self) -> None:
        frames = [
            _spot_frame([(24, 24, 200)]),
            _spot_frame([(26, 24, 140), (52, 24, 255)]),
        ]
        mask = _rect_mask(80, 80, 8, 8, 30, 40)
        params = _params(
            search_radius_px=30,
            tracking_method=TRACKING_METHOD_TEMPLATE,
            min_template_confidence=0.05,
        )
        tracks = track_points(frames, [(24.0, 24.0)], params, valid_mask=mask)
        if len(tracks[0].points) > 1:
            self.assertLess(tracks[0].points[1].x, 40.0)
        else:
            self.assertIn("lost_at_frame", tracks[0].end_reason)

    def test_track_terminates_when_next_candidate_is_below_cutoff(self) -> None:
        frames = [
            _spot_frame([(24, 20, 220)]),
            _spot_frame([(24, 24, 220)]),
            _spot_frame([(24, 42, 220)]),
        ]
        crop = RectROI(0, 0, 80, 80)
        mask = valid_mask_crop_local(crop, cutoff=CutoffBoundary(y=30.0))
        params = _params(search_radius_px=20)
        tracks = track_points(frames, [(24.0, 20.0)], params, valid_mask=mask)
        ys = [pt.y for pt in tracks[0].points]
        self.assertTrue(all(y <= 30.0 for y in ys))
        self.assertLess(len(tracks[0].points), 3)
        self.assertFalse(tracks[0].active)

    def test_candidate_outside_cell_region_is_rejected(self) -> None:
        frames = [
            _spot_frame([(24, 24, 200)]),
            _spot_frame([(50, 24, 255)]),
        ]
        mask = _rect_mask(80, 80, 8, 8, 28, 28)
        tracks = track_points(
            frames, [(24.0, 24.0)], _params(search_radius_px=30), valid_mask=mask
        )
        self.assertEqual(len(tracks[0].points), 1)
        self.assertFalse(tracks[0].active)

    def test_dimmer_valid_candidate_wins_over_invalid_brighter(self) -> None:
        signal = _spot_frame([(28, 24, 90), (55, 24, 255)])
        mask = _rect_mask(80, 80, 8, 8, 30, 40)
        x, y, conf = _brightest_point_in_window(
            signal,
            24.0,
            24.0,
            30,
            centroid_radius_px=2,
            valid_mask=mask,
        )
        self.assertGreater(conf, 0.0)
        self.assertLess(x, 40.0)

    def test_lookahead_matcher_cannot_accept_invalid_position(self) -> None:
        frames = [
            _spot_frame([(24, 24, 200)]),
            _spot_frame([(24, 24, 40), (52, 24, 255)]),
        ]
        mask = _rect_mask(80, 80, 8, 8, 30, 40)
        params = _params(search_radius_px=8, lookahead_frames=2)
        prev = TrackPoint(track_id=0, frame_index=0, x=24.0, y=24.0, confidence=1.0)
        signals = [frame.astype(np.float32) for frame in frames]
        x, y, conf = _try_match_step(
            signals,
            prev,
            1,
            params,
            search_radius_px=params.search_radius_px * 2,
            valid_mask=mask,
        )
        if conf >= params.min_template_confidence:
            self.assertTrue(mask[int(round(y)), int(round(x))])
        else:
            self.assertFalse(mask[24, 52] and conf >= params.min_template_confidence)

    def test_template_response_center_outside_mask_is_skipped(self) -> None:
        template = np.full((5, 5), 200, dtype=np.float32)
        frame = _spot_frame([(50, 24, 255)])
        mask = np.zeros((80, 80), dtype=bool)
        x, y, conf = _match_template_in_window(
            frame,
            template,
            24.0,
            24.0,
            30,
            valid_mask=mask,
        )
        self.assertLess(conf, 0.0)
        self.assertAlmostEqual(x, 24.0)
        self.assertAlmostEqual(y, 24.0)


class AnalysisPathMaskTests(unittest.TestCase):
    def test_preview_path_uses_annotation_mask(self) -> None:
        frames = [
            _spot_frame([(24, 20, 220)]),
            _spot_frame([(24, 22, 200), (24, 50, 255)]),
        ]
        crop = RectROI(0, 0, 80, 80)
        cell = CellRegion.from_rect(RectROI(8, 8, 40, 30))
        cutoff = CutoffBoundary(y=32.0)
        ann = build_sample_annotation(
            sample_id="s1",
            group="g1",
            original_file="a.mp4",
            stored_raw_path="raw/a.mp4",
            reference_frame_index=0,
            orientation=OrientationState(),
            roi=crop,
            original_dimensions={"width": 80, "height": 80},
            oriented_dimensions={"width": 80, "height": 80},
            cell_region=cell,
            cutoff_boundary=cutoff,
        )
        mask = scientific_valid_mask_for_tracking(crop, ann)
        analysis = analyze_cropped_preview(
            frames, params=_params(search_radius_px=30), valid_mask=mask
        )
        self.assertGreaterEqual(len(analysis.starting_points), 1)
        for x, y in analysis.starting_points:
            self.assertTrue(mask[int(round(y)), int(round(x))])
        for track in analysis.tracks:
            for pt in track.points:
                self.assertTrue(mask[int(round(pt.y)), int(round(pt.x))])

    def test_legacy_rect_only_annotation_is_all_true_domain(self) -> None:
        crop = RectROI(0, 0, 80, 80)
        ann = build_sample_annotation(
            sample_id="s1",
            group="g1",
            original_file="a.mp4",
            stored_raw_path="raw/a.mp4",
            reference_frame_index=0,
            orientation=OrientationState(),
            roi=crop,
            original_dimensions={"width": 80, "height": 80},
            oriented_dimensions={"width": 80, "height": 80},
        )
        mask = scientific_valid_mask_for_tracking(crop, ann)
        self.assertEqual(mask.shape, (80, 80))
        self.assertTrue(np.all(mask))
        frames = [_spot_frame([(24 + i, 24, 220)]) for i in range(3)]
        params = _params(search_radius_px=6)
        legacy = analyze_cropped_preview(frames, params=params, valid_mask=None)
        masked = analyze_cropped_preview(frames, params=params, valid_mask=mask)
        self.assertEqual(len(legacy.starting_points), len(masked.starting_points))
        self.assertEqual(
            legacy.num_tracks_with_valid_steps, masked.num_tracks_with_valid_steps
        )

    def test_run_metrics_helper_uses_saved_annotation(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._project_root = MagicMock()
        crop = RectROI(0, 0, 40, 30)
        cell = CellRegion.from_rect(RectROI(2, 2, 20, 12))
        ann = build_sample_annotation(
            sample_id="S1",
            group="g1",
            original_file="a.mp4",
            stored_raw_path="raw/a.mp4",
            reference_frame_index=0,
            orientation=OrientationState(),
            roi=crop,
            original_dimensions={"width": 40, "height": 30},
            oriented_dimensions={"width": 40, "height": 30},
            cell_region=cell,
            cutoff_boundary=CutoffBoundary(y=10.0),
        )
        with patch("actintrack_app.gui.get_sample_annotation", return_value=ann):
            mask = MainWindow._saved_scientific_valid_mask_for_sample(
                window, "S1", crop
            )
        self.assertIsNotNone(mask)
        self.assertEqual(mask.shape, (30, 40))
        self.assertFalse(np.all(mask))
        self.assertTrue(np.any(mask))


if __name__ == "__main__":
    unittest.main()
