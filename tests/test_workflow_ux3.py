"""Phase UX3: concavity-preserving CellRegion, Metric Analysis domain, results layout."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import cv2
import numpy as np
from PyQt6.QtWidgets import QApplication

from actintrack_app.cell_detection import (
    CELL_BOUNDARY_SENSITIVITY_BROADER,
    CELL_BOUNDARY_SENSITIVITY_DEFAULT,
    CELL_BOUNDARY_SENSITIVITY_TIGHTER,
    CONTOUR_MODE_EXTERNAL_APPROX,
    detection_parameters_payload,
    suggest_conservative_cell_region,
)
from actintrack_app.gui import MainWindow
from actintrack_app.gui_result_loaders import load_latest_structural_orientation_result
from actintrack_app.orientation import RectROI
from actintrack_app.preview_workflow import CroppedPreviewAnalysis
from actintrack_app.scientific_annotations import (
    CELL_REGION_SOURCE_AUTO,
    CellRegion,
    CutoffBoundary,
    apply_scientific_domain_to_preview,
    valid_mask_crop_local,
)
from actintrack_app.structural_orientation import (
    FilamentOrientationMeasurement,
    StructuralOrientationResult,
    render_structural_orientation_overlay,
    result_from_dict,
)


def _c_shaped_cell_frame(h: int = 80, w: int = 90) -> np.ndarray:
    """Bright C-shape with a large black concavity on the right."""
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[12:68, 14:32] = (30, 210, 40)
    frame[12:24, 14:74] = (30, 210, 40)
    frame[56:68, 14:74] = (30, 210, 40)
    return frame


def _concavity_pixel() -> tuple[int, int]:
    """Row, col inside the C-shape notch (black background)."""
    return 40, 52


class ConcavityPreservingDetectorTests(unittest.TestCase):
    def test_detector_does_not_use_convex_hull(self) -> None:
        src = Path(__file__).resolve().parents[1].joinpath(
            "actintrack_app/cell_detection.py"
        ).read_text(encoding="utf-8")
        self.assertIn("_concavity_preserving_contour_vertices", src)
        self.assertIn(CONTOUR_MODE_EXTERNAL_APPROX, src)
        self.assertIn("last-resort fallback", src)

    def test_c_shape_concavity_is_excluded_while_cell_signal_is_kept(self) -> None:
        frame = _c_shaped_cell_frame()
        cell = suggest_conservative_cell_region(frame)
        self.assertEqual(cell.source, CELL_REGION_SOURCE_AUTO)
        full = RectROI(0, 0, frame.shape[1], frame.shape[0])
        mask = cell.rasterize_crop_mask(full)
        cy, cx = _concavity_pixel()
        self.assertFalse(bool(mask[cy, cx]), "concavity should stay outside CellRegion")
        self.assertTrue(bool(mask[20, 22]), "C-shape stem should remain inside")
        self.assertTrue(bool(mask[18, 50]), "top arm should remain inside")

        hull = cv2.convexHull(
            np.asarray(cell.region.vertices, dtype=np.int32).reshape((-1, 1, 2))
        )
        hull_mask = np.zeros(mask.shape, dtype=np.uint8)
        cv2.fillConvexPoly(hull_mask, hull.reshape((-1, 2)), 1)
        self.assertTrue(bool(hull_mask[cy, cx]), "convex hull would fill the notch")
        self.assertLess(int(mask.sum()), int(hull_mask.sum()))

    def test_tighter_still_reduces_area_on_c_shape(self) -> None:
        frame = _c_shaped_cell_frame()
        full = RectROI(0, 0, frame.shape[1], frame.shape[0])
        default = suggest_conservative_cell_region(
            frame, sensitivity=CELL_BOUNDARY_SENSITIVITY_DEFAULT
        )
        tight = suggest_conservative_cell_region(
            frame, sensitivity=CELL_BOUNDARY_SENSITIVITY_TIGHTER
        )
        broad = suggest_conservative_cell_region(
            frame, sensitivity=CELL_BOUNDARY_SENSITIVITY_BROADER
        )
        default_area = int(default.rasterize_crop_mask(full).sum())
        tight_area = int(tight.rasterize_crop_mask(full).sum())
        broad_area = int(broad.rasterize_crop_mask(full).sum())
        self.assertLessEqual(tight_area, default_area)
        self.assertGreaterEqual(broad_area, default_area)
        cy, cx = _concavity_pixel()
        self.assertFalse(bool(tight.rasterize_crop_mask(full)[cy, cx]))

    def test_detection_payload_records_v2_contour_mode(self) -> None:
        payload = detection_parameters_payload(0.5)
        self.assertEqual(payload["version"], "conservative_cell_v2")
        self.assertEqual(payload["contour_mode"], CONTOUR_MODE_EXTERNAL_APPROX)


class ScientificDomainPreviewTests(unittest.TestCase):
    def test_preview_uses_same_valid_mask_as_tracking(self) -> None:
        crop = RectROI(0, 0, 20, 16)
        cell = CellRegion.from_rect(RectROI(0, 0, 20, 16))
        cutoff = CutoffBoundary(y=7.0)
        mask = valid_mask_crop_local(crop, cell_region=cell, cutoff=cutoff)
        frame = np.full((16, 20, 3), 80, dtype=np.uint8)
        preview = apply_scientific_domain_to_preview(frame, mask)
        self.assertTrue(np.all(preview[0:8] == 80))
        self.assertTrue(np.all(preview[8:] == 0))

    def test_metric_analysis_applies_cutoff_domain(self) -> None:
        window = MainWindow.__new__(MainWindow)
        frames = [np.full((12, 10, 3), 90, dtype=np.uint8)]
        window._cropped_preview = CroppedPreviewAnalysis(
            frames=frames,
            tracks=[],
            starting_points=[],
            downward_velocity_index_um_per_s=0.0,
            general_movement_index_um_per_s=0.0,
            num_tracks_with_valid_steps=0,
            total_valid_steps=0,
            mean_track_length_frames=0.0,
        )
        window._cell_region = CellRegion.from_rect(RectROI(0, 0, 10, 12))
        window._cutoff_boundary = CutoffBoundary(y=5.0)
        window.canvas = MagicMock()
        window.canvas.rect_roi.return_value = RectROI(0, 0, 10, 12)
        mask = MainWindow._metric_analysis_valid_mask(window)
        self.assertIsNotNone(mask)
        assert mask is not None
        self.assertEqual(mask.shape, (12, 10))
        self.assertTrue(bool(mask[5, 4]))
        self.assertFalse(bool(mask[6, 4]))
        preview = apply_scientific_domain_to_preview(frames[0], mask)
        self.assertTrue(np.all(preview[6:] == 0))
        self.assertTrue(np.all(preview[0:6] == 90))


class PersistedOrientationOverlayTests(unittest.TestCase):
    def test_overlay_loads_persisted_measurements_without_recompute(self) -> None:
        payload = StructuralOrientationResult(
            has_valid_result=True,
            sample_id="S1",
            nucleus_reference_xy_px=(4.0, 5.0),
            measurements=[
                FilamentOrientationMeasurement(
                    x_px=8.0,
                    y_px=6.0,
                    angle_relative_nucleus_deg=30.0,
                    local_orientation_deg=20.0,
                    coherence=0.8,
                )
            ],
            median_angle_relative_nucleus_deg=30.0,
        ).summary_dict()
        restored = result_from_dict(payload)
        frame = np.zeros((16, 16, 3), dtype=np.uint8)
        overlay = render_structural_orientation_overlay(frame, restored, maximum_glyphs=10)
        self.assertEqual(overlay.shape, (16, 16, 3))
        self.assertGreater(int(overlay.sum()), 0)
        src = Path(__file__).resolve().parents[1].joinpath(
            "actintrack_app/gui.py"
        ).read_text(encoding="utf-8")
        show_fn = src.split("def _show_cropped_preview_frame", 1)[1].split(
            "def _on_auto_suggest_roi", 1
        )[0]
        self.assertIn("load_latest_structural_orientation_result", show_fn)
        self.assertIn("render_structural_orientation_overlay", show_fn)
        self.assertNotIn("compute_structural_orientation", show_fn)

    def test_loader_reads_draft_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sid = "sample_abc"
            from actintrack_app.schema_compat import draft_structural_orientation_path

            path = draft_structural_orientation_path(root, sid)
            path.parent.mkdir(parents=True, exist_ok=True)
            result = StructuralOrientationResult(
                has_valid_result=True,
                sample_id=sid,
                nucleus_reference_xy_px=(1.0, 2.0),
                measurements=[
                    FilamentOrientationMeasurement(
                        x_px=3.0,
                        y_px=4.0,
                        angle_relative_nucleus_deg=90.0,
                        local_orientation_deg=10.0,
                        coherence=0.5,
                    )
                ],
            )
            path.write_text(json.dumps(result.summary_dict()), encoding="utf-8")
            loaded = load_latest_structural_orientation_result(
                sid, project_root=root
            )
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(len(loaded.measurements), 1)
            self.assertEqual(loaded.measurements[0].angle_relative_nucleus_deg, 90.0)


class SampleResultsPlacementTests(unittest.TestCase):
    def test_results_are_beside_canvas_not_in_setup_sidebar(self) -> None:
        layout = Path(__file__).resolve().parents[1].joinpath(
            "actintrack_app/gui_layout_builders.py"
        ).read_text(encoding="utf-8")
        setup = layout.split("def build_roi_preview_panel", 1)[1].split(
            "def build_roi_workflow_strip", 1
        )[0]
        images = layout.split("def build_preview_images_panel", 1)[1].split(
            "def build_sample_results_beside_canvas", 1
        )[0]
        results = layout.split("def build_sample_results_beside_canvas", 1)[1].split(
            "def build_roi_preview_panel", 1
        )[0]
        self.assertIn("window.lbl_sample_results", results)
        self.assertNotIn("window.lbl_sample_results", setup)
        self.assertIn("build_sample_results_beside_canvas(window)", images)
        self.assertIn("slider_cell_boundary", setup)
        self.assertIn("Select Nucleus", setup)
        self.assertIn("Video Timing", layout)
        self.assertNotIn("Confirm Timing", layout)
        self.assertNotIn("radio_timing_video", layout)
        self.assertNotIn("Custom s/frame", layout)


class MetricAnalysisOrientationCheckboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_orientation_is_inspection_mode_not_tracking_checkbox(self) -> None:
        layout = Path(__file__).resolve().parents[1].joinpath(
            "actintrack_app/gui_layout_builders.py"
        ).read_text(encoding="utf-8")
        create_block = layout.split("def create_metric_mode_widgets", 1)[1].split(
            "def build_metric_mode_selector_section", 1
        )[0]
        section_block = layout.split("def build_metric_mode_selector_section", 1)[1].split(
            "def build_workbench_action_mode_slot", 1
        )[0]
        self.assertIn("Display / Inspection Mode", section_block)
        self.assertIn('addItem("F-actin Orientation", "orientation")', create_block)
        self.assertNotIn("layout.addWidget(window.chk_show_orientation_overlay)", section_block)


if __name__ == "__main__":
    unittest.main()
