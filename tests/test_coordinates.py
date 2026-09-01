"""Coordinate contract, orientation transforms, and crop-local conversion."""

from __future__ import annotations

import itertools
import unittest

import numpy as np

from actintrack_app.orientation import (
    COORDINATE_SPACE_CANVAS_DISPLAY,
    COORDINATE_SPACE_CROP_LOCAL_PIXELS,
    COORDINATE_SPACE_ORIENTED_FRAME_PIXELS,
    COORDINATE_SPACE_ORIGINAL_FRAME_PIXELS,
    COORDINATE_SPACE_RAW_FRAME_PIXELS,
    OrientationState,
    RectROI,
    apply_orientation,
    crop_local_xy_to_oriented,
    crop_local_y_to_oriented,
    oriented_frame_size,
    oriented_point_to_raw,
    oriented_roi_to_raw,
    oriented_xy_to_crop_local,
    oriented_y_to_crop_local,
    raw_point_to_oriented,
    raw_roi_to_oriented,
)
from actintrack_app.roi_workflow import (
    ORIENTED_ROI_COORDINATE_SPACE,
    ROI_COORDINATE_SPACE,
    original_point_to_oriented,
    original_roi_to_oriented,
    oriented_point_to_original,
    oriented_roi_to_original,
)

RAW_W = 13
RAW_H = 8
ROTATIONS = (0.0, 90.0, 180.0, 270.0)


def _all_orientation_states() -> list[OrientationState]:
    states: list[OrientationState] = []
    for angle, mirror, flip in itertools.product(ROTATIONS, (False, True), (False, True)):
        states.append(
            OrientationState(
                rotation_angle_degrees=angle,
                mirror_y_axis=mirror,
                flipped_180=flip,
            )
        )
    return states


def _state_label(state: OrientationState) -> str:
    return (
        f"rot={state.rotation_angle_degrees:g} "
        f"mirror={state.mirror_y_axis} flip180={state.flipped_180}"
    )


class CoordinateSpaceContractTests(unittest.TestCase):
    def test_canonical_space_names(self) -> None:
        self.assertEqual(COORDINATE_SPACE_RAW_FRAME_PIXELS, "raw_frame_pixels")
        self.assertEqual(COORDINATE_SPACE_ORIENTED_FRAME_PIXELS, "oriented_frame_pixels")
        self.assertEqual(COORDINATE_SPACE_CROP_LOCAL_PIXELS, "crop_local_pixels")
        self.assertEqual(COORDINATE_SPACE_CANVAS_DISPLAY, "canvas_display")
        self.assertEqual(COORDINATE_SPACE_ORIGINAL_FRAME_PIXELS, "original_frame_pixels")
        self.assertEqual(ROI_COORDINATE_SPACE, COORDINATE_SPACE_ORIGINAL_FRAME_PIXELS)
        self.assertEqual(ORIENTED_ROI_COORDINATE_SPACE, COORDINATE_SPACE_ORIENTED_FRAME_PIXELS)

    def test_oriented_size_matches_apply_orientation(self) -> None:
        raw = np.zeros((RAW_H, RAW_W, 3), dtype=np.uint8)
        for state in _all_orientation_states():
            oriented = apply_orientation(raw, state)
            ow, oh = oriented_frame_size(RAW_W, RAW_H, state)
            self.assertEqual(
                (oriented.shape[1], oriented.shape[0]),
                (ow, oh),
                msg=_state_label(state),
            )


class PointRoundTripTests(unittest.TestCase):
    def test_all_orientation_combinations_round_trip(self) -> None:
        points = [
            (0.0, 0.0),
            (RAW_W - 1.0, 0.0),
            (0.0, RAW_H - 1.0),
            (RAW_W - 1.0, RAW_H - 1.0),
            (1.0, 1.0),
            (6.0, 3.0),
            (4.25, 2.5),
            (9.75, 6.125),
        ]
        for state in _all_orientation_states():
            for x, y in points:
                ox, oy = raw_point_to_oriented(
                    x, y, raw_width=RAW_W, raw_height=RAW_H, state=state
                )
                rx, ry = oriented_point_to_raw(
                    ox, oy, raw_width=RAW_W, raw_height=RAW_H, state=state
                )
                self.assertAlmostEqual(rx, x, places=6, msg=_state_label(state))
                self.assertAlmostEqual(ry, y, places=6, msg=_state_label(state))

    def test_mirror_y_axis_is_horizontal_pixel_flip(self) -> None:
        state = OrientationState(mirror_y_axis=True)
        x, y = raw_point_to_oriented(
            2.0, 3.0, raw_width=RAW_W, raw_height=RAW_H, state=state
        )
        self.assertAlmostEqual(x, RAW_W - 1.0 - 2.0, places=9)
        self.assertAlmostEqual(y, 3.0, places=9)

    def test_flipped_180_uses_pixel_index_formula(self) -> None:
        state = OrientationState(flipped_180=True)
        x, y = raw_point_to_oriented(
            2.0, 3.0, raw_width=RAW_W, raw_height=RAW_H, state=state
        )
        self.assertAlmostEqual(x, RAW_W - 1.0 - 2.0, places=9)
        self.assertAlmostEqual(y, RAW_H - 1.0 - 3.0, places=9)

    def test_rotation_180_is_not_the_same_as_flipped_180(self) -> None:
        affine_180 = OrientationState(rotation_angle_degrees=180.0)
        discrete_180 = OrientationState(flipped_180=True)
        p = (0.0, 0.0)
        a = raw_point_to_oriented(*p, raw_width=RAW_W, raw_height=RAW_H, state=affine_180)
        b = raw_point_to_oriented(*p, raw_width=RAW_W, raw_height=RAW_H, state=discrete_180)
        self.assertNotEqual(a, b)

    def test_float_precision_survives_mirror_and_flip(self) -> None:
        state = OrientationState(mirror_y_axis=True, flipped_180=True)
        x, y = 3.375, 5.0625
        ox, oy = raw_point_to_oriented(
            x, y, raw_width=RAW_W, raw_height=RAW_H, state=state
        )
        rx, ry = oriented_point_to_raw(
            ox, oy, raw_width=RAW_W, raw_height=RAW_H, state=state
        )
        self.assertEqual(rx, x)
        self.assertEqual(ry, y)


class RoiRoundTripTests(unittest.TestCase):
    def test_identity_and_discrete_flips_round_trip(self) -> None:
        rois = [
            RectROI(0, 0, RAW_W, RAW_H),
            RectROI(2, 1, 5, 3),
            RectROI(0, 0, 1, 1),
            RectROI(RAW_W - 1, RAW_H - 1, 1, 1),
            RectROI(0, 3, RAW_W, 2),
        ]
        discrete = [
            OrientationState(),
            OrientationState(mirror_y_axis=True),
            OrientationState(flipped_180=True),
            OrientationState(mirror_y_axis=True, flipped_180=True),
        ]
        for state in discrete:
            for roi in rois:
                oriented = raw_roi_to_oriented(
                    roi, raw_width=RAW_W, raw_height=RAW_H, state=state
                )
                recovered = oriented_roi_to_raw(
                    oriented, raw_width=RAW_W, raw_height=RAW_H, state=state
                )
                self.assertEqual(
                    (recovered.x, recovered.y, recovered.width, recovered.height),
                    (roi.x, roi.y, roi.width, roi.height),
                    msg=f"{_state_label(state)} roi={roi}",
                )

    def test_all_combinations_interior_roi_round_trip(self) -> None:
        roi = RectROI(2, 1, 5, 3)
        for state in _all_orientation_states():
            oriented = raw_roi_to_oriented(
                roi, raw_width=RAW_W, raw_height=RAW_H, state=state
            )
            recovered = oriented_roi_to_raw(
                oriented, raw_width=RAW_W, raw_height=RAW_H, state=state
            )
            self.assertEqual(
                (recovered.x, recovered.y, recovered.width, recovered.height),
                (roi.x, roi.y, roi.width, roi.height),
                msg=_state_label(state),
            )

    def test_mirror_roi_half_open_formula(self) -> None:
        roi = RectROI(2, 1, 4, 3)
        state = OrientationState(mirror_y_axis=True)
        oriented = raw_roi_to_oriented(
            roi, raw_width=RAW_W, raw_height=RAW_H, state=state
        )
        self.assertEqual(oriented.x, RAW_W - roi.x - roi.width)
        self.assertEqual(oriented.y, roi.y)
        self.assertEqual(oriented.width, roi.width)
        self.assertEqual(oriented.height, roi.height)


class PixelCorrespondenceTests(unittest.TestCase):
    def test_mirror_matches_apply_orientation_pixels(self) -> None:
        raw = np.arange(RAW_H * RAW_W, dtype=np.uint16).reshape(RAW_H, RAW_W)
        state = OrientationState(mirror_y_axis=True)
        oriented = apply_orientation(raw, state)
        for y in range(RAW_H):
            for x in range(RAW_W):
                ox, oy = raw_point_to_oriented(
                    float(x), float(y), raw_width=RAW_W, raw_height=RAW_H, state=state
                )
                self.assertEqual((ox, oy), (RAW_W - 1 - x, y))
                self.assertEqual(oriented[int(oy), int(ox)], raw[y, x])

    def test_flipped_180_matches_apply_orientation_pixels(self) -> None:
        raw = np.arange(RAW_H * RAW_W, dtype=np.uint16).reshape(RAW_H, RAW_W)
        state = OrientationState(flipped_180=True)
        oriented = apply_orientation(raw, state)
        for y in range(RAW_H):
            for x in range(RAW_W):
                ox, oy = raw_point_to_oriented(
                    float(x), float(y), raw_width=RAW_W, raw_height=RAW_H, state=state
                )
                self.assertEqual((int(ox), int(oy)), (RAW_W - 1 - x, RAW_H - 1 - y))
                self.assertEqual(oriented[int(oy), int(ox)], raw[y, x])

    def test_inverse_matches_identity_gradient_after_orientation(self) -> None:
        raw = np.zeros((RAW_H, RAW_W, 2), dtype=np.float32)
        ys, xs = np.mgrid[0:RAW_H, 0:RAW_W]
        raw[..., 0] = xs + 1.0
        raw[..., 1] = ys + 1.0
        for state in _all_orientation_states():
            oriented = apply_orientation(raw, state)
            oh, ow = oriented.shape[:2]
            sampled = 0
            for oy in range(oh):
                for ox in range(ow):
                    sx = float(oriented[oy, ox, 0]) - 1.0
                    sy = float(oriented[oy, ox, 1]) - 1.0
                    if oriented[oy, ox, 0] < 0.5 or oriented[oy, ox, 1] < 0.5:
                        continue
                    pred_x, pred_y = oriented_point_to_raw(
                        float(ox),
                        float(oy),
                        raw_width=RAW_W,
                        raw_height=RAW_H,
                        state=state,
                    )
                    self.assertAlmostEqual(
                        pred_x, sx, places=2, msg=_state_label(state)
                    )
                    self.assertAlmostEqual(
                        pred_y, sy, places=2, msg=_state_label(state)
                    )
                    sampled += 1
            self.assertGreater(sampled, 0, msg=_state_label(state))


class CompatibilityWrapperTests(unittest.TestCase):
    def test_wrappers_include_mirror_y_axis(self) -> None:
        state = OrientationState(mirror_y_axis=True)
        x, y = original_point_to_oriented(2, 3, orig_w=RAW_W, orig_h=RAW_H, state=state)
        self.assertEqual((x, y), (RAW_W - 1 - 2, 3))
        rx, ry = oriented_point_to_original(
            x,
            y,
            orig_w=RAW_W,
            orig_h=RAW_H,
            oriented_w=RAW_W,
            oriented_h=RAW_H,
            state=state,
        )
        self.assertEqual((rx, ry), (2, 3))

    def test_roi_wrappers_delegate(self) -> None:
        state = OrientationState(mirror_y_axis=True, flipped_180=True)
        roi = RectROI(2, 1, 4, 3)
        oriented = original_roi_to_oriented(
            roi, orig_w=RAW_W, orig_h=RAW_H, state=state
        )
        expected = raw_roi_to_oriented(
            roi, raw_width=RAW_W, raw_height=RAW_H, state=state
        )
        self.assertEqual(oriented, expected)
        recovered = oriented_roi_to_original(
            oriented,
            orig_w=RAW_W,
            orig_h=RAW_H,
            oriented_w=RAW_W,
            oriented_h=RAW_H,
            state=state,
        )
        self.assertEqual(recovered, roi)


class CropLocalConversionTests(unittest.TestCase):
    def test_oriented_to_crop_local_and_back(self) -> None:
        crop = RectROI(4, 6, 10, 8)
        lx, ly = oriented_xy_to_crop_local(7.5, 9.25, crop)
        self.assertEqual((lx, ly), (3.5, 3.25))
        ox, oy = crop_local_xy_to_oriented(lx, ly, crop)
        self.assertEqual((ox, oy), (7.5, 9.25))

    def test_cutoff_y_conversion(self) -> None:
        crop = RectROI(4, 6, 10, 8)
        self.assertEqual(oriented_y_to_crop_local(11.0, crop), 5.0)
        self.assertEqual(crop_local_y_to_oriented(5.0, crop), 11.0)


if __name__ == "__main__":
    unittest.main()
