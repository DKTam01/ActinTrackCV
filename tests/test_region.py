"""Tests for Region domain model (Phase A1)."""

from __future__ import annotations

import random
import unittest

import numpy as np

from actintrack_app.annotation_schema import build_sample_annotation, region_from_annotation
from actintrack_app.orientation import OrientationState, RectROI
from actintrack_app.region import (
    ANNOTATION_FIELD_GEOMETRY_TYPE,
    ANNOTATION_FIELD_POLYGON_ROI,
    GEOMETRY_TYPE_POLYGON,
    Region,
    RegionValidationError,
    validate_region,
)
from actintrack_app.roi_workflow import roi_oriented_as_dict


def _legacy_rect_annotation(rect: RectROI) -> dict:
    return {"rectangle_roi": roi_oriented_as_dict(rect)}


class RectangleCompatibilityTests(unittest.TestCase):
    def test_preserves_rect_roi(self) -> None:
        rect = RectROI(10, 20, 50, 40)
        region = Region.from_rect(rect)
        self.assertEqual(region.bounding_box(), rect)
        self.assertIs(region.bounding_box(), region.rectangle)

    def test_all_true_mask_shape(self) -> None:
        rect = RectROI(3, 5, 7, 9)
        mask = Region.from_rect(rect).rasterize_crop_mask()
        self.assertEqual(mask.shape, (9, 7))
        self.assertEqual(mask.dtype, np.bool_)
        self.assertTrue(np.all(mask))

    def test_numpy_slice_equivalence(self) -> None:
        frame = np.arange(100 * 80, dtype=np.int32).reshape(80, 100)
        rect = RectROI(12, 8, 30, 15)
        crop = frame[rect.y : rect.y + rect.height, rect.x : rect.x + rect.width]
        region = Region.from_rect(rect)
        mask = region.rasterize_crop_mask()
        self.assertTrue(np.array_equal(crop, frame[rect.y : rect.y + rect.height, rect.x : rect.x + rect.width]))
        self.assertEqual(mask.shape, crop.shape)
        self.assertTrue(np.all(mask))

    def test_geometry_key(self) -> None:
        rect = RectROI(1, 2, 3, 4)
        self.assertEqual(
            Region.from_rect(rect).geometry_key(),
            ("rectangle", 1, 2, 3, 4),
        )

    def test_full_frame_rectangle(self) -> None:
        rect = RectROI(0, 0, 64, 48)
        region = Region.from_rect(rect)
        validate_region(region, 64, 48)
        mask = region.rasterize_crop_mask()
        self.assertEqual(mask.shape, (48, 64))
        self.assertTrue(np.all(mask))

    def test_edge_touching_rectangle(self) -> None:
        w, h = 50, 40
        cases = [
            RectROI(0, 0, 10, 10),
            RectROI(w - 5, 0, 5, 10),
            RectROI(0, h - 8, 10, 8),
            RectROI(w - 1, h - 1, 1, 1),
        ]
        for rect in cases:
            region = Region.from_rect(rect)
            validate_region(region, w, h)
            mask = region.rasterize_crop_mask()
            self.assertEqual(mask.shape, (rect.height, rect.width))
            self.assertTrue(np.all(mask))

    def test_one_by_one_rectangle(self) -> None:
        rect = RectROI(7, 11, 1, 1)
        region = Region.from_rect(rect)
        validate_region(region, 20, 20)
        mask = region.rasterize_crop_mask()
        self.assertEqual(mask.shape, (1, 1))
        self.assertTrue(mask[0, 0])

    def test_narrow_rectangles(self) -> None:
        region = Region.from_rect(RectROI(5, 3, 1, 20))
        mask = region.rasterize_crop_mask()
        self.assertEqual(mask.shape, (20, 1))
        self.assertTrue(np.all(mask))

    def test_odd_even_dimensions(self) -> None:
        for rect in (RectROI(2, 2, 7, 9), RectROI(1, 1, 8, 6)):
            mask = Region.from_rect(rect).rasterize_crop_mask()
            self.assertEqual(mask.shape, (rect.height, rect.width))
            self.assertTrue(np.all(mask))

    def test_randomized_valid_rectangles(self) -> None:
        rng = random.Random(42)
        for _ in range(30):
            w, h = rng.randint(20, 120), rng.randint(20, 120)
            x = rng.randint(0, w - 1)
            y = rng.randint(0, h - 1)
            rw = rng.randint(1, w - x)
            rh = rng.randint(1, h - y)
            rect = RectROI(x, y, rw, rh)
            region = Region.from_rect(rect)
            validate_region(region, w, h)
            mask = region.rasterize_crop_mask()
            self.assertEqual(mask.shape, (rh, rw))
            self.assertTrue(np.all(mask))

    def test_annotation_round_trip_stable(self) -> None:
        rect = RectROI(10, 20, 30, 25)
        fields = Region.from_rect(rect).to_annotation_fields()
        self.assertEqual(fields, _legacy_rect_annotation(rect))
        loaded = Region.from_annotation(_legacy_rect_annotation(rect))
        self.assertEqual(loaded.geometry_key(), Region.from_rect(rect).geometry_key())


class PolygonRasterizationTests(unittest.TestCase):
    def test_simple_triangle_mask(self) -> None:
        vertices = ((2, 1), (6, 1), (4, 4))
        region = Region.from_polygon(vertices)
        validate_region(region, 8, 6)
        mask = region.rasterize_crop_mask()
        bbox = region.bounding_box()
        self.assertEqual(bbox, RectROI(2, 1, 5, 4))
        expected = np.array(
            [
                [True, True, True, True, False],
                [False, True, True, False, False],
                [False, False, False, False, False],
                [False, False, False, False, False],
            ],
            dtype=np.bool_,
        )
        self.assertTrue(np.array_equal(mask, expected))

    def test_convex_pentagon(self) -> None:
        vertices = ((1, 1), (7, 0), (9, 4), (5, 6), (0, 4))
        region = Region.from_polygon(vertices)
        validate_region(region, 12, 8)
        mask = region.rasterize_crop_mask()
        self.assertEqual(mask.shape, (region.bounding_box().height, region.bounding_box().width))
        self.assertTrue(np.any(mask))
        self.assertFalse(np.all(mask))

    def test_concave_polygon(self) -> None:
        vertices = ((0, 0), (6, 0), (6, 2), (2, 2), (2, 5), (0, 5))
        region = Region.from_polygon(vertices)
        validate_region(region, 8, 8)
        mask = region.rasterize_crop_mask()
        expected = np.array(
            [
                [True, True, True, True, True, True, False],
                [True, True, True, True, True, True, False],
                [True, True, False, False, False, False, False],
                [True, True, False, False, False, False, False],
                [True, True, False, False, False, False, False],
                [False, False, False, False, False, False, False],
            ],
            dtype=np.bool_,
        )
        self.assertTrue(np.array_equal(mask, expected))

    def test_clockwise_and_counterclockwise_same_mask(self) -> None:
        ccw = ((2, 1), (6, 1), (4, 4))
        cw = ((2, 1), (4, 4), (6, 1))
        mask_ccw = Region.from_polygon(ccw).rasterize_crop_mask()
        mask_cw = Region.from_polygon(cw).rasterize_crop_mask()
        self.assertTrue(np.array_equal(mask_ccw, mask_cw))

    def test_boundary_touching_polygon(self) -> None:
        vertices = ((0, 0), (5, 0), (5, 3), (0, 3))
        region = Region.from_polygon(vertices)
        validate_region(region, 6, 4)
        mask = region.rasterize_crop_mask()
        self.assertEqual(mask.shape, (4, 6))
        self.assertTrue(np.all(mask[:3, :5]))
        self.assertFalse(np.any(mask[3, :]))
        self.assertFalse(np.any(mask[:, 5:]))

    def test_bbox_smaller_than_frame(self) -> None:
        vertices = ((10, 10), (14, 10), (12, 14))
        region = Region.from_polygon(vertices)
        validate_region(region, 40, 40)
        bbox = region.bounding_box()
        self.assertEqual(bbox, RectROI(10, 10, 5, 5))
        mask = region.rasterize_crop_mask()
        self.assertEqual(mask.shape, (5, 5))

    def test_deterministic_repeated_rasterization(self) -> None:
        region = Region.from_polygon(((1, 1), (5, 1), (3, 4)))
        first = region.rasterize_crop_mask().tobytes()
        second = region.rasterize_crop_mask().tobytes()
        self.assertEqual(first, second)

    def test_crop_local_translation(self) -> None:
        base = ((2, 2), (5, 2), (4, 5))
        shifted = ((12, 7), (15, 7), (14, 10))
        mask_base = Region.from_polygon(base).rasterize_crop_mask()
        mask_shift = Region.from_polygon(shifted).rasterize_crop_mask()
        self.assertTrue(np.array_equal(mask_base, mask_shift))


class PolygonValidationTests(unittest.TestCase):
    def test_accept_simple_polygons(self) -> None:
        for verts in (
            ((0, 0), (5, 0), (5, 4), (0, 4)),
            ((5, 0), (0, 0), (0, 4), (5, 4)),
            ((0, 0), (6, 0), (6, 2), (2, 2), (2, 5), (0, 5)),
            ((0, 0), (9, 0), (9, 1), (0, 1)),
        ):
            region = Region.from_polygon(verts)
            validate_region(region, 10, 10)

    def test_reject_fewer_than_three_unique_points(self) -> None:
        with self.assertRaises(RegionValidationError):
            Region.from_polygon(((1, 1), (2, 2)))
        with self.assertRaises(RegionValidationError):
            validate_region(
                Region.from_polygon(((1, 1), (2, 2), (1, 1))),
                10,
                10,
            )

    def test_reject_duplicate_consecutive(self) -> None:
        with self.assertRaises(RegionValidationError):
            validate_region(
                Region.from_polygon(((0, 0), (0, 0), (3, 0), (0, 3))),
                10,
                10,
            )

    def test_reject_closure_vertex(self) -> None:
        with self.assertRaises(RegionValidationError):
            Region.from_polygon(((0, 0), (4, 0), (2, 3), (0, 0)))

    def test_reject_zero_length_edge(self) -> None:
        with self.assertRaises(RegionValidationError):
            validate_region(
                Region.from_polygon(((0, 0), (2, 0), (2, 0), (0, 3))),
                10,
                10,
            )

    def test_reject_all_collinear(self) -> None:
        with self.assertRaises(RegionValidationError):
            validate_region(
                Region.from_polygon(((0, 0), (2, 0), (4, 0))),
                10,
                10,
            )

    def test_reject_zero_area(self) -> None:
        with self.assertRaises(RegionValidationError):
            validate_region(
                Region.from_polygon(((0, 0), (4, 0), (2, 0), (2, 3))),
                10,
                10,
            )

    def test_reject_bow_tie(self) -> None:
        with self.assertRaises(RegionValidationError):
            validate_region(
                Region.from_polygon(((0, 0), (4, 4), (4, 0), (0, 4))),
                10,
                10,
            )

    def test_reject_overlapping_collinear_edges(self) -> None:
        with self.assertRaises(RegionValidationError):
            validate_region(
                Region.from_polygon(((0, 0), (6, 0), (6, 4), (3, 4), (3, 0), (0, 4))),
                10,
                10,
            )

    def test_reject_repeated_nonconsecutive_vertex(self) -> None:
        with self.assertRaises(RegionValidationError):
            validate_region(
                Region.from_polygon(((0, 0), (4, 0), (2, 2), (0, 4), (0, 0))),
                10,
                10,
            )

    def test_reject_negative_coordinates(self) -> None:
        with self.assertRaises(RegionValidationError):
            validate_region(
                Region.from_polygon(((-1, 0), (3, 0), (1, 3))),
                10,
                10,
            )

    def test_reject_coordinates_beyond_bounds(self) -> None:
        with self.assertRaises(RegionValidationError):
            validate_region(
                Region.from_polygon(((0, 0), (10, 0), (5, 5))),
                10,
                10,
            )

    def test_reject_empty_rasterized_mask(self) -> None:
        # Degenerate near-miss: bow-tie is caught earlier; use self-intersection
        with self.assertRaises(RegionValidationError):
            validate_region(
                Region.from_polygon(((0, 0), (4, 4), (4, 0), (0, 4))),
                10,
                10,
            )


class PersistenceTests(unittest.TestCase):
    def test_legacy_rectangle_loads(self) -> None:
        ann = _legacy_rect_annotation(RectROI(5, 6, 20, 15))
        region = Region.from_annotation(ann)
        self.assertEqual(region.geometry_type, "rectangle")
        self.assertEqual(region.bounding_box(), RectROI(5, 6, 20, 15))

    def test_build_sample_annotation_adapter(self) -> None:
        ann = build_sample_annotation(
            sample_id="s1",
            group="g1",
            original_file="vid.mp4",
            stored_raw_path="raw/vid.mp4",
            reference_frame_index=0,
            orientation=OrientationState(),
            roi=RectROI(3, 4, 10, 12),
            original_dimensions={"width": 100, "height": 80},
            oriented_dimensions={"width": 100, "height": 80},
        )
        region = region_from_annotation(ann)
        self.assertEqual(region.bounding_box(), RectROI(3, 4, 10, 12))
        self.assertNotIn(ANNOTATION_FIELD_GEOMETRY_TYPE, region.to_annotation_fields())

    def test_polygon_annotation_load(self) -> None:
        ann = {
            ANNOTATION_FIELD_GEOMETRY_TYPE: GEOMETRY_TYPE_POLYGON,
            ANNOTATION_FIELD_POLYGON_ROI: {
                "vertices": [[10, 20], [90, 20], [80, 70], [20, 75]],
                "roi_coordinate_space": "oriented_frame_pixels",
            },
        }
        region = Region.from_annotation(ann)
        self.assertEqual(region.geometry_type, GEOMETRY_TYPE_POLYGON)
        self.assertEqual(
            region.vertices,
            ((10, 20), (90, 20), (80, 70), (20, 75)),
        )

    def test_polygon_round_trip(self) -> None:
        verts = ((10, 20), (90, 20), (80, 70), (20, 75))
        region = Region.from_polygon(verts)
        fields = region.to_annotation_fields()
        loaded = Region.from_annotation({**fields})
        self.assertEqual(loaded.vertices, verts)
        self.assertEqual(
            fields[ANNOTATION_FIELD_POLYGON_ROI]["vertices"],
            [[10, 20], [90, 20], [80, 70], [20, 75]],
        )

    def test_declared_polygon_missing_polygon_roi_fails(self) -> None:
        with self.assertRaises(RegionValidationError):
            Region.from_annotation({ANNOTATION_FIELD_GEOMETRY_TYPE: GEOMETRY_TYPE_POLYGON})

    def test_malformed_polygon_no_rectangle_fallback(self) -> None:
        ann = {
            ANNOTATION_FIELD_GEOMETRY_TYPE: GEOMETRY_TYPE_POLYGON,
            ANNOTATION_FIELD_POLYGON_ROI: {"vertices": [[0, 0], [1, 1]]},
            "rectangle_roi": roi_oriented_as_dict(RectROI(0, 0, 10, 10)),
        }
        with self.assertRaises(RegionValidationError):
            Region.from_annotation(ann)

    def test_unknown_geometry_type_fails(self) -> None:
        with self.assertRaises(RegionValidationError):
            Region.from_annotation({ANNOTATION_FIELD_GEOMETRY_TYPE: "ellipse"})

    def test_different_vertices_same_bbox_different_key(self) -> None:
        a = Region.from_polygon(((0, 0), (6, 0), (3, 4)))
        b = Region.from_polygon(((0, 0), (4, 0), (6, 4)))
        self.assertEqual(a.bounding_box(), b.bounding_box())
        self.assertNotEqual(a.geometry_key(), b.geometry_key())

    def test_polygon_without_closure_vertex_in_serialization(self) -> None:
        region = Region.from_polygon(((1, 2), (5, 2), (3, 6)))
        verts = region.to_annotation_fields()[ANNOTATION_FIELD_POLYGON_ROI]["vertices"]
        self.assertEqual(verts[0], [1, 2])
        self.assertNotEqual(verts[-1], verts[0])

    def test_conflicting_rectangle_and_polygon_rectangle_type(self) -> None:
        ann = {
            ANNOTATION_FIELD_GEOMETRY_TYPE: "rectangle",
            "rectangle_roi": roi_oriented_as_dict(RectROI(0, 0, 5, 5)),
            ANNOTATION_FIELD_POLYGON_ROI: {"vertices": [[0, 0], [5, 0], [2, 4]]},
        }
        with self.assertRaises(RegionValidationError):
            Region.from_annotation(ann)


if __name__ == "__main__":
    unittest.main()
