"""CellRegion, conservative suggestion, and crop-local validity mask."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from actintrack_app.cell_detection import suggest_conservative_cell_region
from actintrack_app.gui import MainWindow
from actintrack_app.orientation import (
    COORDINATE_SPACE_ORIENTED_FRAME_PIXELS,
    COORDINATE_SPACE_RAW_FRAME_PIXELS,
    OrientationState,
    RectROI,
)
from actintrack_app.scientific_annotations import (
    ANNOTATION_FIELD_CELL_REGION,
    CELL_REGION_SOURCE_AUTO,
    CELL_REGION_SOURCE_FALLBACK_FRAME,
    CELL_REGION_SOURCE_FALLBACK_ROI,
    CellRegion,
    CutoffBoundary,
    NucleusReference,
    ScientificAnnotationError,
    cell_region_from_annotation,
    fallback_cell_region,
    reorient_cell_region,
    reorient_cutoff_boundary,
    reorient_nucleus_reference,
    valid_mask_crop_local,
)
from actintrack_app.annotation_schema import build_sample_annotation
from actintrack_app.batch_annotation import propagate_annotation


def _bright_blob_frame(h: int = 40, w: int = 50) -> np.ndarray:
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[8:32, 10:40] = (40, 220, 40)
    return frame


class CellRegionModelTests(unittest.TestCase):
    def test_from_rect_bbox_and_mask(self) -> None:
        cell = CellRegion.from_rect(RectROI(4, 5, 10, 8), source="manual")
        self.assertEqual(cell.bounding_box(), RectROI(4, 5, 10, 8))
        crop = RectROI(2, 3, 16, 12)
        mask = cell.rasterize_crop_mask(crop)
        self.assertEqual(mask.shape, (12, 16))
        self.assertTrue(np.all(mask[2:10, 2:12]))
        self.assertFalse(np.any(mask[0:2, :]))

    def test_from_polygon_and_persistence_round_trip(self) -> None:
        cell = CellRegion.from_polygon(
            ((2, 1), (8, 1), (7, 6), (2, 6)), source=CELL_REGION_SOURCE_AUTO
        )
        loaded = CellRegion.from_dict(cell.to_dict())
        self.assertEqual(loaded.region.geometry_key(), cell.region.geometry_key())
        self.assertEqual(loaded.source, CELL_REGION_SOURCE_AUTO)
        self.assertEqual(loaded.to_dict()["coordinate_space"], COORDINATE_SPACE_ORIENTED_FRAME_PIXELS)

    def test_rejects_wrong_coordinate_space(self) -> None:
        with self.assertRaises(ScientificAnnotationError):
            CellRegion.from_dict(
                {
                    "coordinate_space": COORDINATE_SPACE_RAW_FRAME_PIXELS,
                    "geometry_type": "rectangle",
                    "rectangle": {"x": 0, "y": 0, "width": 4, "height": 4},
                }
            )

    def test_annotation_round_trip_not_confused_with_rect_roi(self) -> None:
        cell = CellRegion.from_rect(RectROI(1, 2, 6, 5))
        ann = build_sample_annotation(
            sample_id="s1",
            group="g1",
            original_file="a.mp4",
            stored_raw_path="raw/a.mp4",
            reference_frame_index=0,
            orientation=OrientationState(),
            roi=RectROI(0, 0, 20, 15),
            original_dimensions={"width": 40, "height": 30},
            oriented_dimensions={"width": 40, "height": 30},
            cell_region=cell,
        )
        self.assertEqual(ann["rectangle_roi"]["width"], 20)
        self.assertEqual(ann[ANNOTATION_FIELD_CELL_REGION]["rectangle"]["width"], 6)
        loaded = cell_region_from_annotation(ann)
        self.assertEqual(loaded.bounding_box(), RectROI(1, 2, 6, 5))

    def test_rejects_unknown_geometry_and_bad_payload(self) -> None:
        with self.assertRaises(ScientificAnnotationError):
            CellRegion.from_dict({"geometry_type": "ellipse", "coordinate_space": COORDINATE_SPACE_ORIENTED_FRAME_PIXELS})
        with self.assertRaises(ScientificAnnotationError):
            CellRegion.from_dict("not a mapping")
        with self.assertRaises(ScientificAnnotationError):
            CellRegion.from_dict(
                {
                    "coordinate_space": COORDINATE_SPACE_ORIENTED_FRAME_PIXELS,
                    "geometry_type": "rectangle",
                }
            )

    def test_missing_cell_region_is_none(self) -> None:
        self.assertIsNone(
            cell_region_from_annotation(
                {"rectangle_roi": {"x": 0, "y": 0, "width": 4, "height": 4}}
            )
        )


class ValidityMaskTests(unittest.TestCase):
    def test_both_missing_is_all_true(self) -> None:
        crop = RectROI(3, 4, 10, 8)
        mask = valid_mask_crop_local(crop)
        self.assertEqual(mask.shape, (8, 10))
        self.assertTrue(np.all(mask))

    def test_cell_only(self) -> None:
        crop = RectROI(0, 0, 10, 8)
        cell = CellRegion.from_rect(RectROI(2, 2, 4, 3))
        mask = valid_mask_crop_local(crop, cell_region=cell)
        self.assertTrue(np.all(mask[2:5, 2:6]))
        self.assertFalse(np.any(mask[0:2, :]))

    def test_cutoff_only_above_means_small_y(self) -> None:
        crop = RectROI(0, 0, 6, 8)
        mask = valid_mask_crop_local(crop, cutoff=CutoffBoundary(y=3.0))
        self.assertTrue(np.all(mask[0:4, :]))
        self.assertFalse(np.any(mask[4:, :]))

    def test_both_cell_and_cutoff(self) -> None:
        crop = RectROI(2, 1, 8, 10)
        cell = CellRegion.from_rect(RectROI(3, 2, 4, 6))
        mask = valid_mask_crop_local(
            crop, cell_region=cell, cutoff=CutoffBoundary(y=5.0)
        )
        self.assertEqual(mask.shape, (10, 8))
        # crop-local row 0 is oriented y=1; cell starts y=2; cutoff includes y<=5
        self.assertFalse(np.any(mask[0, :]))
        self.assertTrue(mask[1, 1])
        self.assertTrue(mask[4, 1])  # oriented y=5
        self.assertFalse(np.any(mask[5:, :]))

    def test_cutoff_above_crop_all_false(self) -> None:
        crop = RectROI(0, 10, 5, 4)
        mask = valid_mask_crop_local(crop, cutoff=CutoffBoundary(y=3.0))
        self.assertFalse(np.any(mask))

    def test_cutoff_below_crop_no_y_exclusion(self) -> None:
        crop = RectROI(0, 2, 5, 4)
        mask = valid_mask_crop_local(crop, cutoff=CutoffBoundary(y=100.0))
        self.assertTrue(np.all(mask))

    def test_partial_cell_crop_intersection(self) -> None:
        crop = RectROI(4, 4, 6, 6)
        cell = CellRegion.from_rect(RectROI(0, 0, 6, 6))
        mask = valid_mask_crop_local(crop, cell_region=cell)
        self.assertTrue(np.all(mask[0:2, 0:2]))
        self.assertFalse(np.any(mask[2:, :]))
        self.assertFalse(np.any(mask[:, 2:]))


class FallbackAndDetectionTests(unittest.TestCase):
    def test_fallback_prefers_rect_roi(self) -> None:
        crop = RectROI(2, 3, 8, 7)
        cell = fallback_cell_region(frame_width=20, frame_height=15, crop=crop)
        self.assertEqual(cell.source, CELL_REGION_SOURCE_FALLBACK_ROI)
        self.assertEqual(cell.bounding_box(), crop)

    def test_fallback_full_frame_without_crop(self) -> None:
        cell = fallback_cell_region(frame_width=20, frame_height=15, crop=None)
        self.assertEqual(cell.source, CELL_REGION_SOURCE_FALLBACK_FRAME)
        self.assertEqual(cell.bounding_box(), RectROI(0, 0, 20, 15))

    def test_suggestion_overincludes_bright_blob(self) -> None:
        frame = _bright_blob_frame()
        cell = suggest_conservative_cell_region(frame)
        bbox = cell.bounding_box()
        self.assertLessEqual(bbox.x, 10)
        self.assertLessEqual(bbox.y, 8)
        self.assertGreaterEqual(bbox.x1, 40)
        self.assertGreaterEqual(bbox.y1, 32)
        self.assertIn(cell.source, (CELL_REGION_SOURCE_AUTO, CELL_REGION_SOURCE_FALLBACK_FRAME))

    def test_failed_segmentation_uses_roi_fallback(self) -> None:
        frame = np.zeros((24, 30, 3), dtype=np.uint8)
        crop = RectROI(3, 4, 10, 8)
        cell = suggest_conservative_cell_region(frame, fallback_rect=crop)
        self.assertEqual(cell.source, CELL_REGION_SOURCE_FALLBACK_ROI)
        self.assertEqual(cell.bounding_box(), crop)

    def test_failed_segmentation_without_roi_uses_full_frame(self) -> None:
        frame = np.zeros((24, 30, 3), dtype=np.uint8)
        cell = suggest_conservative_cell_region(frame)
        self.assertEqual(cell.source, CELL_REGION_SOURCE_FALLBACK_FRAME)
        self.assertEqual(cell.bounding_box(), RectROI(0, 0, 30, 24))


class ReorientAnnotationTests(unittest.TestCase):
    def test_nucleus_survives_mirror(self) -> None:
        old = OrientationState()
        new = OrientationState(mirror_y_axis=True)
        nucleus = NucleusReference(2.0, 3.0, source="manual")
        out = reorient_nucleus_reference(
            nucleus, raw_width=13, raw_height=8, old_state=old, new_state=new
        )
        self.assertAlmostEqual(out.x, 13 - 1 - 2.0, places=6)
        self.assertAlmostEqual(out.y, 3.0, places=6)

    def test_cutoff_survives_flip180_stays_horizontal(self) -> None:
        old = OrientationState()
        new = OrientationState(flipped_180=True)
        cutoff = CutoffBoundary(y=3.0)
        out = reorient_cutoff_boundary(
            cutoff,
            old_oriented_width=13,
            raw_width=13,
            raw_height=8,
            old_state=old,
            new_state=new,
        )
        self.assertIsNotNone(out)
        self.assertAlmostEqual(out.y, 8 - 1 - 3.0, places=5)

    def test_cutoff_cleared_on_90_rotation(self) -> None:
        old = OrientationState()
        new = OrientationState(rotation_angle_degrees=90.0)
        cutoff = CutoffBoundary(y=3.0)
        out = reorient_cutoff_boundary(
            cutoff,
            old_oriented_width=13,
            raw_width=13,
            raw_height=8,
            old_state=old,
            new_state=new,
        )
        self.assertIsNone(out)

    def test_cell_rect_survives_mirror(self) -> None:
        old = OrientationState()
        new = OrientationState(mirror_y_axis=True)
        cell = CellRegion.from_rect(RectROI(2, 1, 4, 3))
        out = reorient_cell_region(
            cell,
            raw_width=13,
            raw_height=8,
            old_state=old,
            new_state=new,
            new_frame_width=13,
            new_frame_height=8,
        )
        self.assertEqual(out.bounding_box().width, 4)
        self.assertEqual(out.bounding_box().y, 1)
        self.assertEqual(out.bounding_box().x, 13 - 2 - 4)

    def test_cell_polygon_survives_flip180(self) -> None:
        old = OrientationState()
        new = OrientationState(flipped_180=True)
        cell = CellRegion.from_polygon(((2, 1), (8, 1), (7, 6), (2, 6)))
        out = reorient_cell_region(
            cell,
            raw_width=13,
            raw_height=8,
            old_state=old,
            new_state=new,
            new_frame_width=13,
            new_frame_height=8,
        )
        self.assertIsNotNone(out)
        bbox = out.bounding_box()
        self.assertGreaterEqual(bbox.width, 4)
        self.assertGreaterEqual(bbox.height, 4)


class GuiScientificWorkflowTests(unittest.TestCase):
    def test_place_replace_and_clear_nucleus(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._nucleus_reference = None
        window._cutoff_boundary = CutoffBoundary(y=20.0)
        window._cell_region = None
        window._scientific_placement_mode = "nucleus"
        window._current_sample_id = "S1"
        window._nucleus_cutoff_alignment_review = False
        window._sync_scientific_overlay = MagicMock()
        window._autosave_roi = MagicMock(return_value=True)
        window._mark_draft_metrics_stale = MagicMock()
        window._update_metric_freshness_label = MagicMock()
        window._status = MagicMock()
        window.btn_select_nucleus = MagicMock()
        window.canvas = MagicMock()

        MainWindow.on_nucleus_placed(window, 8.25, 14.5)
        self.assertEqual(window._nucleus_reference.x, 8.25)
        self.assertEqual(window._nucleus_reference.y, 20.0)
        self.assertEqual(window._nucleus_reference.source, "manual")
        self.assertIsNone(window._scientific_placement_mode)
        window._mark_draft_metrics_stale.assert_called_with("S1")
        window._autosave_roi.assert_called()

        MainWindow.on_nucleus_placed(window, 9.0, 10.0)
        self.assertEqual(window._nucleus_reference.x, 9.0)
        self.assertEqual(window._nucleus_reference.y, 20.0)

        MainWindow._on_clear_nucleus(window)
        self.assertIsNone(window._nucleus_reference)

    def test_roi_change_does_not_redefine_cutoff(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._cutoff_boundary = CutoffBoundary(y=18.0)
        window._loaded_annotation_source = "manual"
        window._set_roi_save_status = MagicMock()
        window._refresh_roi_preview_panel = MagicMock()
        MainWindow.on_roi_changed(window, RectROI(1, 2, 10, 12))
        self.assertEqual(window._cutoff_boundary.y, 18.0)

    def test_load_existing_annotation_does_not_regenerate_cell(self) -> None:
        from unittest.mock import patch

        window = MainWindow.__new__(MainWindow)
        window._loaded_sample_notes = ""
        window._orientation = OrientationState()
        window._reference_frame_index = 0
        window._loaded_annotation_source = ""
        window._roi_user_adjusted = False
        window._roi_autosave_pending = False
        window._nucleus_reference = None
        window._cutoff_boundary = None
        window._cell_region = None
        window._refresh_display = MagicMock()
        window.canvas = MagicMock()
        window.canvas.rect_roi.return_value = None
        window._oriented_frame = MagicMock(return_value=None)
        window._update_orientation_label = MagicMock()
        window._refresh_roi_save_status_from_context = MagicMock()
        window._refresh_roi_preview_panel = MagicMock()
        window._update_metric_freshness_label = MagicMock()
        cell = CellRegion.from_rect(RectROI(2, 3, 8, 9), source=CELL_REGION_SOURCE_AUTO)
        ann = {
            "sample_id": "S1",
            "reference_frame_index": 0,
            "notes": "",
            "annotation_source": "manual",
            "rotation_angle_degrees": 0.0,
            "flipped_180": False,
            "mirror_y_axis": False,
            "rectangle_roi": {"x": 1, "y": 2, "width": 10, "height": 12},
            "cell_region": cell.to_dict(),
            "cutoff_boundary": {
                "y": 11.0,
                "coordinate_space": COORDINATE_SPACE_ORIENTED_FRAME_PIXELS,
            },
        }
        with patch(
            "actintrack_app.gui.suggest_conservative_cell_region"
        ) as mock_suggest:
            MainWindow._apply_annotation_from_dict(window, ann, render_canvas=False)
            mock_suggest.assert_not_called()
        self.assertEqual(window._cell_region.bounding_box(), RectROI(2, 3, 8, 9))
        self.assertEqual(window._cutoff_boundary.y, 11.0)

    def test_auto_suggest_does_not_overwrite_existing_annotations(self) -> None:
        from unittest.mock import patch

        from actintrack_app.image_processing import TrackingCrop

        existing_cell = CellRegion.from_rect(RectROI(1, 1, 8, 8), source="manual")
        window = MainWindow.__new__(MainWindow)
        window._cell_region = existing_cell
        window._cutoff_boundary = CutoffBoundary(y=9.0)
        window._nucleus_reference = NucleusReference(2.0, 3.0, source="manual")
        window._loaded_annotation_source = "manual"
        window._roi_user_adjusted = False
        window.canvas = MagicMock()
        window.canvas.rect_roi.return_value = RectROI(0, 0, 12, 16)
        window._oriented_frame = MagicMock(
            return_value=np.zeros((20, 30, 3), dtype=np.uint8)
        )
        window._sync_scientific_overlay = MagicMock()
        window._autosave_roi = MagicMock(return_value=True)
        fake_crop = TrackingCrop(
            x0=2,
            y0=1,
            x1=20,
            y1=16,
            cutoff_y=11,
            foreground_bbox={"x0": 2, "y0": 1, "x1": 20, "y1": 16},
            confidence=0.9,
            method="test",
            signal_source="test",
            notes="",
        )
        with patch("actintrack_app.gui.detect_tracking_crop", return_value=fake_crop):
            with patch("actintrack_app.gui.suggest_conservative_cell_region") as mock_s:
                MainWindow._apply_auto_suggested_roi(window, render_canvas=True)
                mock_s.assert_not_called()
        self.assertIs(window._cell_region, existing_cell)
        self.assertEqual(window._cutoff_boundary.y, 9.0)
        self.assertEqual(window._nucleus_reference.x, 2.0)

    def test_auto_suggest_cutoff_uses_crop_cutoff_not_roi_bottom(self) -> None:
        from unittest.mock import patch

        from actintrack_app.image_processing import TrackingCrop

        window = MainWindow.__new__(MainWindow)
        window._cell_region = None
        window._cutoff_boundary = None
        window._nucleus_reference = None
        window._loaded_annotation_source = "manual"
        window._roi_user_adjusted = False
        window.canvas = MagicMock()
        window.canvas.rect_roi.return_value = RectROI(2, 1, 18, 15)
        window._oriented_frame = MagicMock(
            return_value=np.zeros((20, 30, 3), dtype=np.uint8)
        )
        window._sync_scientific_overlay = MagicMock()
        window._autosave_roi = MagicMock(return_value=True)
        window._project_root = Path("/tmp")
        window._current_sample = {"sample_id": "S1"}
        fake_crop = TrackingCrop(
            x0=2,
            y0=1,
            x1=20,
            y1=16,
            cutoff_y=11,
            foreground_bbox={"x0": 2, "y0": 1, "x1": 20, "y1": 16},
            confidence=0.9,
            method="test",
            signal_source="test",
            notes="",
        )
        suggested_cell = CellRegion.from_rect(
            RectROI(0, 0, 30, 20), source=CELL_REGION_SOURCE_FALLBACK_FRAME
        )
        with patch(
            "actintrack_app.cell_detection.detect_tracking_crop",
            return_value=fake_crop,
        ):
            with patch(
                "actintrack_app.gui.suggest_conservative_cell_region",
                return_value=suggested_cell,
            ):
                MainWindow._apply_auto_suggested_roi(window, render_canvas=True)
        self.assertEqual(window._cutoff_boundary.y, 11.0)
        self.assertNotEqual(window._cutoff_boundary.y, 16.0)
        window._autosave_roi.assert_called()

    def test_stale_metrics_are_marked_not_deleted_or_rerun(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._tracking_result_stale_by_sample = {}
        window._optical_flow_stale_by_sample = {}
        window._sample_has_measurable_draft_results = MagicMock(return_value=True)
        window._compute_metrics_for_sample = MagicMock()
        window.run_metrics_for_sample_id = MagicMock()
        MainWindow._mark_draft_metrics_stale(window, "S1")
        self.assertTrue(window._tracking_result_stale_by_sample["S1"])
        self.assertTrue(window._optical_flow_stale_by_sample["S1"])
        window._compute_metrics_for_sample.assert_not_called()
        window.run_metrics_for_sample_id.assert_not_called()

    def test_cutoff_drag_does_not_auto_run_metrics(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._cutoff_boundary = CutoffBoundary(y=12.0)
        window._current_sample_id = "S1"
        window._sync_scientific_overlay = MagicMock()
        window._autosave_roi = MagicMock(return_value=True)
        window._mark_draft_metrics_stale = MagicMock()
        window._update_metric_freshness_label = MagicMock()
        window._compute_metrics_for_sample = MagicMock()
        window.run_metrics_for_sample_id = MagicMock()

        MainWindow.on_cutoff_dragged(window, 18.0)
        self.assertEqual(window._cutoff_boundary.y, 18.0)
        MainWindow.on_cutoff_edit_finished(window)
        window._mark_draft_metrics_stale.assert_called_with("S1")
        window._compute_metrics_for_sample.assert_not_called()
        window.run_metrics_for_sample_id.assert_not_called()

    def test_menu_has_no_polygon_authoring(self) -> None:
        from pathlib import Path

        gui_src = Path(__file__).resolve().parents[1].joinpath(
            "actintrack_app/gui.py"
        ).read_text(encoding="utf-8")
        canvas_src = Path(__file__).resolve().parents[1].joinpath(
            "actintrack_app/gui_canvas.py"
        ).read_text(encoding="utf-8")
        self.assertIn("Set Nucleus", gui_src)
        self.assertIn("Set Cutoff", gui_src)
        self.assertNotIn("Clear ROI", gui_src)
        self.assertNotIn("Draw Polygon", gui_src)
        self.assertNotIn("polygon authoring", canvas_src.lower())
        self.assertNotIn("DragMode.POLYGON", canvas_src)


class PropagationCellRegionTests(unittest.TestCase):
    def test_propagate_does_not_copy_cell_region(self) -> None:
        from unittest.mock import patch
        from pathlib import Path
        import tempfile

        frame = np.zeros((30, 40, 3), dtype=np.uint8)
        source = build_sample_annotation(
            sample_id="s1",
            group="g1",
            original_file="clip.mp4",
            stored_raw_path="raw/clip.mp4",
            reference_frame_index=0,
            orientation=OrientationState(),
            roi=RectROI(3, 4, 10, 12),
            original_dimensions={"width": 40, "height": 30},
            oriented_dimensions={"width": 40, "height": 30},
            nucleus_reference=NucleusReference(9.5, 10.25),
            cutoff_boundary=CutoffBoundary(18.0),
            cell_region=CellRegion.from_rect(RectROI(1, 2, 20, 16)),
        )
        target = {
            "sample_id": "t1",
            "group": "g1",
            "stored_path": "raw/t.mp4",
            "original_filename": "t.mp4",
            "batch_name": "batch1",
            "batch_id": "b1",
        }
        with patch(
            "actintrack_app.batch_annotation.load_media_frame",
            return_value=(frame, 0, 1),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                result = propagate_annotation(Path(tmp), source, target)
        self.assertNotIn(ANNOTATION_FIELD_CELL_REGION, result)
        self.assertNotIn("nucleus_reference", result)
        self.assertNotIn("cutoff_boundary", result)


def _annotation_window(
    *,
    roi: RectROI | None,
    nucleus: NucleusReference | None = None,
    cutoff: CutoffBoundary | None = None,
    cell: CellRegion | None = None,
) -> MainWindow:
    window = MainWindow.__new__(MainWindow)
    window._loaded_sample_notes = ""
    window._roi_user_adjusted = False
    window._current_sample = {
        "sample_id": "S1",
        "group": "Col-0",
        "batch_name": "batch1",
        "batch_id": "b1",
        "original_filename": "clip.mp4",
        "stored_path": "raw/S1.avi",
        "processing_status": "roi_marked",
    }
    window._current_sample_id = "S1"
    window._reference_frame_index = 0
    window._orientation = OrientationState()
    window._loaded_annotation_source = "manual"
    window._nucleus_reference = nucleus
    window._cutoff_boundary = cutoff
    window._cell_region = cell
    window._base_frame = np.zeros((30, 40, 3), dtype=np.uint8)
    window.canvas = MagicMock()
    window.canvas.rect_roi.return_value = roi
    window._oriented_frame = MagicMock(return_value=np.zeros((30, 40, 3), dtype=np.uint8))
    if roi is not None:
        check = MagicMock()
        check.ok = True
        check.roi_oriented = roi
        check.roi_original = roi
        window._validate_current_roi = MagicMock(return_value=check)
    window._suggestion_method_for_save = MagicMock(return_value=None)
    return window


class AnnotationDecoupledFromRoiTests(unittest.TestCase):
    def test_document_persists_scientific_fields_without_rect_roi(self) -> None:
        cell = CellRegion.from_rect(RectROI(2, 3, 8, 9))
        window = _annotation_window(
            roi=None,
            nucleus=NucleusReference(8.25, 14.5, source="manual"),
            cutoff=CutoffBoundary(22.0),
            cell=cell,
        )
        ann = MainWindow._current_annotation_dict(
            window, status="unannotated", require_roi=False
        )
        self.assertNotIn("rectangle_roi", ann)
        self.assertEqual(ann["nucleus_reference"]["x"], 8.25)
        self.assertEqual(ann["cutoff_boundary"]["y"], 22.0)
        self.assertEqual(ann["cell_region"]["rectangle"]["width"], 8)

    def test_set_nucleus_without_roi_persists(self) -> None:
        window = _annotation_window(roi=None, cutoff=CutoffBoundary(y=11.0))
        window._scientific_placement_mode = "nucleus"
        window._sync_scientific_overlay = MagicMock()
        window._autosave_roi = MagicMock(return_value=True)
        window._mark_draft_metrics_stale = MagicMock()
        window._update_metric_freshness_label = MagicMock()
        window._status = MagicMock()
        window.btn_select_nucleus = MagicMock()
        MainWindow.on_nucleus_placed(window, 5.5, 6.25)
        self.assertEqual(window._nucleus_reference.x, 5.5)
        self.assertEqual(window._nucleus_reference.y, 11.0)
        window._autosave_roi.assert_called()

    def test_set_cutoff_without_roi_persists(self) -> None:
        window = _annotation_window(roi=None)
        window._scientific_placement_mode = "cutoff"
        window._sync_scientific_overlay = MagicMock()
        window._autosave_roi = MagicMock(return_value=True)
        window._mark_draft_metrics_stale = MagicMock()
        window._update_metric_freshness_label = MagicMock()
        window._status = MagicMock()
        MainWindow.on_cutoff_placed(window, 17.0)
        self.assertEqual(window._cutoff_boundary.y, 17.0)
        window._autosave_roi.assert_called()

    def test_clear_roi_keeps_scientific_state_and_does_not_delete_pack(self) -> None:
        from unittest.mock import patch

        cell = CellRegion.from_rect(RectROI(1, 2, 12, 10), source=CELL_REGION_SOURCE_AUTO)
        window = _annotation_window(
            roi=None,
            nucleus=NucleusReference(9.0, 8.0, source="manual"),
            cutoff=CutoffBoundary(16.0),
            cell=cell,
        )
        window._project_root = MagicMock()
        window._exit_cropped_preview_mode = MagicMock()
        window._set_roi_save_status = MagicMock()
        window._sync_scientific_overlay = MagicMock()
        window._update_metric_freshness_label = MagicMock()
        window._refresh_roi_preview_panel = MagicMock()
        window._mark_draft_metrics_stale = MagicMock()
        window._refresh_analysis_if_visible = MagicMock()
        window._autosave_roi = MagicMock(return_value=True)
        window._compute_metrics_for_sample = MagicMock()
        window.run_metrics_for_sample_id = MagicMock()
        window._invalidate_tracking_result_for_sample = MagicMock()

        import inspect

        persist_src = inspect.getsource(MainWindow._persist_roi_cleared_for_current_sample)
        self.assertNotIn("remove_sample_crop_annotation", persist_src)
        MainWindow._on_clear_roi(window)

        self.assertEqual(window._nucleus_reference.x, 9.0)
        self.assertEqual(window._cutoff_boundary.y, 16.0)
        self.assertEqual(window._cell_region.bounding_box(), RectROI(1, 2, 12, 10))
        window._autosave_roi.assert_called()
        window._mark_draft_metrics_stale.assert_called_with("S1")
        window._invalidate_tracking_result_for_sample.assert_not_called()
        window._compute_metrics_for_sample.assert_not_called()
        window.run_metrics_for_sample_id.assert_not_called()

    def test_reload_after_roi_clear_restores_scientific_fields(self) -> None:
        cell = CellRegion.from_rect(RectROI(2, 3, 8, 9), source=CELL_REGION_SOURCE_AUTO)
        window = _annotation_window(roi=None)
        window._refresh_display = MagicMock()
        window._update_orientation_label = MagicMock()
        window._refresh_roi_save_status_from_context = MagicMock()
        window._refresh_roi_preview_panel = MagicMock()
        window._update_metric_freshness_label = MagicMock()
        window._roi_autosave_pending = False
        ann = {
            "sample_id": "S1",
            "reference_frame_index": 0,
            "notes": "",
            "annotation_source": "manual",
            "rotation_angle_degrees": 0.0,
            "flipped_180": False,
            "mirror_y_axis": False,
            "nucleus_reference": {
                "x": 8.25,
                "y": 14.5,
                "coordinate_space": COORDINATE_SPACE_ORIENTED_FRAME_PIXELS,
            },
            "cutoff_boundary": {
                "y": 22.0,
                "coordinate_space": COORDINATE_SPACE_ORIENTED_FRAME_PIXELS,
            },
            "cell_region": cell.to_dict(),
        }
        MainWindow._apply_annotation_from_dict(window, ann, render_canvas=False)
        self.assertEqual(window._nucleus_reference.x, 8.25)
        self.assertEqual(window._cutoff_boundary.y, 22.0)
        self.assertEqual(window._cell_region.bounding_box(), RectROI(2, 3, 8, 9))

    def test_recreating_roi_does_not_overwrite_scientific_annotations(self) -> None:
        cell = CellRegion.from_rect(RectROI(1, 1, 8, 8), source="manual")
        window = _annotation_window(
            roi=None,
            nucleus=NucleusReference(2.0, 3.0, source="manual"),
            cutoff=CutoffBoundary(9.0),
            cell=cell,
        )
        window._set_roi_save_status = MagicMock()
        window._refresh_roi_preview_panel = MagicMock()
        MainWindow.on_roi_changed(window, RectROI(4, 5, 10, 12))
        self.assertIs(window._cell_region, cell)
        self.assertEqual(window._nucleus_reference.x, 2.0)
        self.assertEqual(window._cutoff_boundary.y, 9.0)

    def test_clear_nucleus_does_not_clear_cutoff_or_cell(self) -> None:
        cell = CellRegion.from_rect(RectROI(1, 2, 6, 7))
        window = _annotation_window(
            roi=RectROI(0, 0, 20, 20),
            nucleus=NucleusReference(3.0, 4.0, source="manual"),
            cutoff=CutoffBoundary(12.0),
            cell=cell,
        )
        window._scientific_placement_mode = None
        window._sync_scientific_overlay = MagicMock()
        window._autosave_roi = MagicMock(return_value=True)
        window._mark_draft_metrics_stale = MagicMock()
        window._update_metric_freshness_label = MagicMock()
        window._status = MagicMock()
        MainWindow._on_clear_nucleus(window)
        self.assertIsNone(window._nucleus_reference)
        self.assertEqual(window._cutoff_boundary.y, 12.0)
        self.assertIs(window._cell_region, cell)

    def test_clear_cutoff_does_not_clear_nucleus_or_cell(self) -> None:
        cell = CellRegion.from_rect(RectROI(1, 2, 6, 7))
        window = _annotation_window(
            roi=RectROI(0, 0, 20, 20),
            nucleus=NucleusReference(3.0, 4.0, source="manual"),
            cutoff=CutoffBoundary(12.0),
            cell=cell,
        )
        window._scientific_placement_mode = None
        window._sync_scientific_overlay = MagicMock()
        window._autosave_roi = MagicMock(return_value=True)
        window._mark_draft_metrics_stale = MagicMock()
        window._update_metric_freshness_label = MagicMock()
        window._status = MagicMock()
        MainWindow._on_clear_cutoff(window)
        self.assertIsNone(window._cutoff_boundary)
        self.assertEqual(window._nucleus_reference.x, 3.0)
        self.assertIs(window._cell_region, cell)

    def test_legacy_rectangle_only_annotation_still_loads(self) -> None:
        window = _annotation_window(roi=None)
        window._project_root = None
        window._refresh_display = MagicMock()
        window._update_orientation_label = MagicMock()
        window._refresh_roi_save_status_from_context = MagicMock()
        window._refresh_roi_preview_panel = MagicMock()
        window._update_metric_freshness_label = MagicMock()
        window._sync_scientific_overlay = MagicMock()
        window._roi_autosave_pending = False
        ann = {
            "sample_id": "S1",
            "reference_frame_index": 0,
            "notes": "",
            "annotation_source": "manual",
            "rotation_angle_degrees": 0.0,
            "flipped_180": False,
            "mirror_y_axis": False,
            "rectangle_roi": {"x": 1, "y": 2, "width": 10, "height": 12},
        }
        with patch(
            "actintrack_app.gui.suggest_conservative_cell_region",
            return_value=CellRegion.from_rect(RectROI(1, 2, 10, 12), source="auto_suggested"),
        ) as mock_suggest:
            MainWindow._apply_annotation_from_dict(window, ann, render_canvas=False)
            mock_suggest.assert_called_once()
        window.canvas.set_rect_roi.assert_called()
        self.assertIsNone(window._nucleus_reference)
        self.assertIsNotNone(window._cell_region)
        self.assertIsNotNone(window._cutoff_boundary)

    def test_missing_cell_region_is_generated_on_load(self) -> None:
        window = _annotation_window(roi=RectROI(1, 2, 10, 12))
        window._project_root = None
        window._cell_region = None
        window._refresh_display = MagicMock()
        window._update_orientation_label = MagicMock()
        window._refresh_roi_save_status_from_context = MagicMock()
        window._refresh_roi_preview_panel = MagicMock()
        window._update_metric_freshness_label = MagicMock()
        window._sync_scientific_overlay = MagicMock()
        window._autosave_roi = MagicMock(return_value=True)
        window._roi_autosave_pending = False
        suggested = CellRegion.from_polygon(
            ((2, 3), (9, 3), (8, 12), (2, 11)), source="auto_suggested"
        )
        ann = {
            "sample_id": "S1",
            "reference_frame_index": 0,
            "notes": "",
            "annotation_source": "manual",
            "rotation_angle_degrees": 0.0,
            "flipped_180": False,
            "mirror_y_axis": False,
            "rectangle_roi": {"x": 1, "y": 2, "width": 10, "height": 12},
        }
        with patch(
            "actintrack_app.gui.suggest_conservative_cell_region",
            return_value=suggested,
        ) as mock_suggest:
            MainWindow._apply_annotation_from_dict(window, ann, render_canvas=False)
            mock_suggest.assert_called_once()
        self.assertIs(window._cell_region, suggested)
        # No project root → ensure must not attempt autosave persistence.
        window._autosave_roi.assert_not_called()


if __name__ == "__main__":
    unittest.main()
