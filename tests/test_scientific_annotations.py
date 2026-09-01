"""NucleusReference and CutoffBoundary persistence and conversions."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from actintrack_app.annotation_schema import (
    annotation_from_legacy,
    build_sample_annotation,
    scientific_annotations_from_annotation,
)
from actintrack_app.batch_annotation import propagate_annotation
from actintrack_app.orientation import (
    COORDINATE_SPACE_ORIENTED_FRAME_PIXELS,
    COORDINATE_SPACE_RAW_FRAME_PIXELS,
    OrientationState,
    RectROI,
)
from actintrack_app.scientific_annotations import (
    ANNOTATION_FIELD_CUTOFF_BOUNDARY,
    ANNOTATION_FIELD_NUCLEUS_REFERENCE,
    CutoffBoundary,
    NucleusReference,
    ScientificAnnotationError,
    cutoff_boundary_from_annotation,
    nucleus_reference_from_annotation,
)


def _base_annotation_kwargs() -> dict:
    return {
        "sample_id": "s1",
        "group": "g1",
        "original_file": "clip.mp4",
        "stored_raw_path": "raw/clip.mp4",
        "reference_frame_index": 0,
        "orientation": OrientationState(),
        "roi": RectROI(3, 4, 10, 12),
        "original_dimensions": {"width": 40, "height": 30},
        "oriented_dimensions": {"width": 40, "height": 30},
    }


class NucleusReferenceTests(unittest.TestCase):
    def test_requires_oriented_space(self) -> None:
        with self.assertRaises(ScientificAnnotationError):
            NucleusReference(1.0, 2.0, coordinate_space=COORDINATE_SPACE_RAW_FRAME_PIXELS)

    def test_fractional_round_trip_dict(self) -> None:
        nucleus = NucleusReference(12.375, 40.0625, source="manual")
        loaded = NucleusReference.from_dict(nucleus.to_dict())
        self.assertEqual(loaded.x, 12.375)
        self.assertEqual(loaded.y, 40.0625)
        self.assertEqual(loaded.coordinate_space, COORDINATE_SPACE_ORIENTED_FRAME_PIXELS)
        self.assertEqual(loaded.source, "manual")

    def test_crop_local_conversion(self) -> None:
        crop = RectROI(5, 8, 20, 15)
        nucleus = NucleusReference(9.5, 11.25)
        lx, ly = nucleus.to_crop_local(crop)
        self.assertEqual((lx, ly), (4.5, 3.25))
        restored = NucleusReference.from_crop_local(lx, ly, crop)
        self.assertEqual(restored.x, nucleus.x)
        self.assertEqual(restored.y, nucleus.y)


class CutoffBoundaryTests(unittest.TestCase):
    def test_requires_oriented_space(self) -> None:
        with self.assertRaises(ScientificAnnotationError):
            CutoffBoundary(10.0, coordinate_space=COORDINATE_SPACE_RAW_FRAME_PIXELS)

    def test_round_trip_dict(self) -> None:
        cutoff = CutoffBoundary(22.5)
        loaded = CutoffBoundary.from_dict(cutoff.to_dict())
        self.assertEqual(loaded.y, 22.5)
        self.assertEqual(loaded.coordinate_space, COORDINATE_SPACE_ORIENTED_FRAME_PIXELS)

    def test_crop_local_conversion(self) -> None:
        crop = RectROI(5, 8, 20, 15)
        cutoff = CutoffBoundary(19.0)
        self.assertEqual(cutoff.to_crop_local(crop), 11.0)
        restored = CutoffBoundary.from_crop_local(11.0, crop)
        self.assertEqual(restored.y, 19.0)


class AnnotationPersistenceTests(unittest.TestCase):
    def test_optional_fields_absent_by_default(self) -> None:
        ann = build_sample_annotation(**_base_annotation_kwargs())
        self.assertNotIn(ANNOTATION_FIELD_NUCLEUS_REFERENCE, ann)
        self.assertNotIn(ANNOTATION_FIELD_CUTOFF_BOUNDARY, ann)
        self.assertIsNone(nucleus_reference_from_annotation(ann))
        self.assertIsNone(cutoff_boundary_from_annotation(ann))

    def test_save_load_fractional_nucleus_and_cutoff(self) -> None:
        nucleus = NucleusReference(7.25, 18.5, source="manual")
        cutoff = CutoffBoundary(21.125)
        ann = build_sample_annotation(
            **_base_annotation_kwargs(),
            nucleus_reference=nucleus,
            cutoff_boundary=cutoff,
        )
        loaded_n, loaded_c = scientific_annotations_from_annotation(ann)
        self.assertIsNotNone(loaded_n)
        self.assertIsNotNone(loaded_c)
        self.assertEqual(loaded_n.x, 7.25)
        self.assertEqual(loaded_n.y, 18.5)
        self.assertEqual(loaded_c.y, 21.125)
        self.assertEqual(ann[ANNOTATION_FIELD_NUCLEUS_REFERENCE]["coordinate_space"],
                         COORDINATE_SPACE_ORIENTED_FRAME_PIXELS)
        self.assertEqual(ann[ANNOTATION_FIELD_CUTOFF_BOUNDARY]["coordinate_space"],
                         COORDINATE_SPACE_ORIENTED_FRAME_PIXELS)

    def test_null_payload_is_absent(self) -> None:
        ann = {"nucleus_reference": None, "cutoff_boundary": ""}
        self.assertIsNone(nucleus_reference_from_annotation(ann))
        self.assertIsNone(cutoff_boundary_from_annotation(ann))

    def test_invalid_coordinate_space_fails(self) -> None:
        with self.assertRaises(ScientificAnnotationError):
            nucleus_reference_from_annotation(
                {
                    "nucleus_reference": {
                        "x": 1,
                        "y": 2,
                        "coordinate_space": "crop_local_pixels",
                    }
                }
            )
        with self.assertRaises(ScientificAnnotationError):
            cutoff_boundary_from_annotation(
                {
                    "cutoff_boundary": {
                        "y": 8,
                        "coordinate_space": "raw_frame_pixels",
                    }
                }
            )

    def test_legacy_cutoff_y_is_not_promoted(self) -> None:
        ann = {
            "rotation_angle_degrees": 0.0,
            "flipped_180": False,
            "mirror_y_axis": False,
            "cutoff_y": 40,
            "cutoff_y_rotated": 40,
            "original_dimensions": {"width": 80, "height": 60},
            "tracking_roi": {"x0": 0, "x1": 80},
        }
        _orientation, roi = annotation_from_legacy(ann)
        self.assertIsNotNone(roi)
        self.assertIsNone(cutoff_boundary_from_annotation(ann))
        self.assertIsNone(nucleus_reference_from_annotation(ann))

    def test_legacy_analysis_region_still_loads_roi(self) -> None:
        ann = {
            "rotation_angle_degrees": 0.0,
            "analysis_region_coords": {"x0": 2, "y0": 3, "x1": 12, "y1": 20},
            "excluded_region_coords": {"x0": 0, "y0": 20, "x1": 40, "y1": 30},
        }
        _orientation, roi = annotation_from_legacy(ann)
        self.assertEqual(roi, RectROI.from_xyxy(2, 3, 12, 20))
        n, c = scientific_annotations_from_annotation(ann)
        self.assertIsNone(n)
        self.assertIsNone(c)

    def test_legacy_rectangle_roi_loads_without_scientific_fields(self) -> None:
        ann = build_sample_annotation(**_base_annotation_kwargs())
        orientation, roi = annotation_from_legacy(ann)
        self.assertEqual(orientation.rotation_angle_degrees, 0.0)
        self.assertEqual(roi, RectROI(3, 4, 10, 12))
        self.assertIsNone(nucleus_reference_from_annotation(ann))


class PropagationSafetyTests(unittest.TestCase):
    @patch("actintrack_app.batch_annotation.load_media_frame")
    def test_propagate_does_not_copy_nucleus_or_cutoff(self, mock_load) -> None:
        frame = np.zeros((30, 40, 3), dtype=np.uint8)
        mock_load.return_value = (frame, 0, 1)
        source = build_sample_annotation(
            **_base_annotation_kwargs(),
            nucleus_reference=NucleusReference(9.5, 10.25),
            cutoff_boundary=CutoffBoundary(18.0),
        )
        target = {
            "sample_id": "t1",
            "group": "g1",
            "stored_path": "raw/t.mp4",
            "original_filename": "t.mp4",
            "batch_name": "batch1",
            "batch_id": "b1",
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = propagate_annotation(Path(tmp), source, target)
        self.assertNotIn(ANNOTATION_FIELD_NUCLEUS_REFERENCE, result)
        self.assertNotIn(ANNOTATION_FIELD_CUTOFF_BOUNDARY, result)
        self.assertEqual(result["annotation_source"], "propagated")
        self.assertIn("rectangle_roi", result)


if __name__ == "__main__":
    unittest.main()
