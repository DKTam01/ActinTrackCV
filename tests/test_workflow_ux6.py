"""Phase UX6: Metric Analysis rerun refresh, nucleus/cutoff snap, framing."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from PyQt6.QtWidgets import QApplication

from actintrack_app.gui import MainWindow
from actintrack_app.gui_canvas import ImageCanvas
from actintrack_app.gui_result_loaders import load_latest_tracking_result_view
from actintrack_app.gui_styles import SIDE_PANEL_SECTION_SPACING
from actintrack_app.orientation import RectROI
from actintrack_app.preview_workflow import (
    CroppedPreviewAnalysis,
    MetricAnalysisInspectionSession,
    cropped_preview_analysis_from_draft,
    draw_metric_analysis_guides,
)
from actintrack_app.roi_workflow import RoiValidationResult
from actintrack_app.scientific_annotations import (
    CellRegion,
    CutoffBoundary,
    analyzed_region_view_bounds,
    apply_scientific_domain_to_preview,
    crop_frame_to_view_bounds,
    valid_mask_crop_local,
)
from actintrack_app.structural_orientation import (
    FilamentOrientationMeasurement,
    StructuralOrientationResult,
)

ROOT = Path(__file__).resolve().parents[1]

_APP: QApplication | None = None


def _app() -> QApplication:
    global _APP
    existing = QApplication.instance()
    if existing is not None:
        return existing
    _APP = QApplication([])
    return _APP


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _analysis(
    *,
    run_id: str,
    nucleus: tuple[float, float] | None,
    cutoff_y: float | None,
    mask: np.ndarray | None,
    height: int = 24,
    width: int = 20,
) -> CroppedPreviewAnalysis:
    frames = [np.full((height, width, 3), 90, dtype=np.uint8) for _ in range(3)]
    return CroppedPreviewAnalysis(
        frames=frames,
        tracks=[],
        starting_points=[],
        downward_velocity_index_um_per_s=1.0,
        general_movement_index_um_per_s=2.0,
        num_tracks_with_valid_steps=1,
        total_valid_steps=4,
        mean_track_length_frames=3.0,
        nucleus_reference_xy_px=nucleus,
        analysis_run_id=run_id,
        cutoff_y_crop_px=cutoff_y,
        valid_mask=mask,
    )


def _mask(height: int, width: int, cutoff_y: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=bool)
    mask[: cutoff_y + 1, :] = True
    return mask


class NucleusCutoffSnapTests(unittest.TestCase):
    def _window(self, *, cutoff: CutoffBoundary | None) -> MainWindow:
        window = MainWindow.__new__(MainWindow)
        window._nucleus_reference = None
        window._cutoff_boundary = cutoff
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
        window.lbl_nucleus_cutoff_hint = MagicMock()
        return window

    def test_nucleus_y_snaps_to_cutoff_x_stays_user_x(self) -> None:
        window = self._window(cutoff=CutoffBoundary(y=17.0))
        MainWindow.on_nucleus_placed(window, 4.5, 9.0)
        self.assertEqual(window._nucleus_reference.x, 4.5)
        self.assertEqual(window._nucleus_reference.y, 17.0)

    def test_moving_cutoff_later_does_not_move_nucleus(self) -> None:
        window = self._window(cutoff=CutoffBoundary(y=17.0))
        MainWindow.on_nucleus_placed(window, 4.5, 9.0)
        MainWindow.on_cutoff_placed(window, 28.0)
        self.assertEqual(window._nucleus_reference.x, 4.5)
        self.assertEqual(window._nucleus_reference.y, 17.0)
        self.assertEqual(window._cutoff_boundary.y, 28.0)
        self.assertTrue(window._nucleus_cutoff_alignment_review)
        window._mark_draft_metrics_stale.assert_called()

    def test_cutoff_change_marks_results_stale(self) -> None:
        window = self._window(cutoff=CutoffBoundary(y=17.0))
        MainWindow.on_nucleus_placed(window, 4.5, 9.0)
        window._mark_draft_metrics_stale.reset_mock()
        MainWindow.on_cutoff_edit_finished(window)
        window._mark_draft_metrics_stale.assert_called_once_with("S1")

    def test_nucleus_without_cutoff_is_refused(self) -> None:
        window = self._window(cutoff=None)
        with patch("actintrack_app.gui.gui_dialogs.information") as info:
            MainWindow.on_nucleus_placed(window, 4.5, 9.0)
        self.assertIsNone(window._nucleus_reference)
        info.assert_called()

    def test_select_nucleus_prompts_when_cutoff_missing(self) -> None:
        window = self._window(cutoff=None)
        window._exit_cropped_preview_mode = MagicMock()
        with patch("actintrack_app.gui.gui_dialogs.information") as info:
            MainWindow._on_set_nucleus_mode(window)
        info.assert_called()
        window._exit_cropped_preview_mode.assert_not_called()
        self.assertIsNone(window._scientific_placement_mode)


class AlignmentGuidanceLayoutTests(unittest.TestCase):
    def test_alignment_guidance_present(self) -> None:
        builders = _read("actintrack_app/gui_layout_builders.py")
        self.assertIn("lbl_nucleus_cutoff_hint", builders)
        self.assertIn(
            "Place the Measurement Cutoff through the nucleus",
            builders,
        )
        self.assertIn("setCheckable(True)", builders)
        self.assertIn("Nucleus (optional)", builders)


class MetricAnalysisRerunRefreshTests(unittest.TestCase):
    def _stub(self) -> MainWindow:
        window = MainWindow.__new__(MainWindow)
        window._project_root = Path("/tmp/ux6")
        window._current_sample_id = "S1"
        window._current_sample = {"sample_id": "S1"}
        window._tracking_results_by_sample = {}
        window._tracking_result_stale_by_sample = {}
        window._optical_flow_stale_by_sample = {}
        window._optical_flow_results_by_sample = {}
        window._of_flow_caches = {}
        window._sample_has_measurable_draft_results = MagicMock(return_value=True)
        window._metric_analysis_view_active = False
        window._metric_analysis_session = None
        window._cropped_preview = None
        window._orientation = MagicMock()
        window.canvas = MagicMock()
        window._ensure_metric_view_shell_visible = MagicMock()
        window.update_tracking_result_panel = MagicMock()
        window._update_optical_flow_qc_readout = MagicMock()
        window._show_metric_analysis_placeholder = MagicMock()
        window._preview_play = MagicMock()
        window._validate_current_roi = MagicMock(
            return_value=RoiValidationResult(
                True, "", roi_oriented=RectROI(0, 0, 20, 24)
            )
        )
        return window

    def test_run_a_edit_run_b_binds_new_inspection_session(self) -> None:
        window = self._stub()
        mask_a = _mask(24, 20, 8)
        mask_b = _mask(24, 20, 16)
        analysis_a = _analysis(
            run_id="run-A", nucleus=(6.0, 8.0), cutoff_y=8.0, mask=mask_a
        )
        analysis_b = _analysis(
            run_id="run-B", nucleus=(12.0, 16.0), cutoff_y=16.0, mask=mask_b
        )
        window._tracking_results_by_sample["S1"] = analysis_a
        window._read_draft_tracking_payload = MagicMock(
            return_value={"analysis_run_id": "run-A", "analysis_timestamp_utc": "run-A"}
        )
        window._read_draft_optical_flow_payload = MagicMock(return_value=None)
        with patch(
            "actintrack_app.gui.load_latest_structural_orientation_result",
            return_value=StructuralOrientationResult(
                has_valid_result=True,
                sample_id="S1",
                nucleus_reference_xy_px=(6.0, 8.0),
                analysis_timestamp_utc="orient-A",
                measurements=[
                    FilamentOrientationMeasurement(
                        x_px=7.0,
                        y_px=4.0,
                        angle_relative_nucleus_deg=10.0,
                        local_orientation_deg=20.0,
                        coherence=0.8,
                    )
                ],
            ),
        ):
            MainWindow._discard_metric_analysis_inspection_state(window)
            session_a = MainWindow._bind_metric_analysis_inspection(window, analysis_a)
        self.assertIsInstance(session_a, MetricAnalysisInspectionSession)
        self.assertEqual(session_a.run_id, "run-A")
        self.assertEqual(session_a.nucleus_xy_crop, (6.0, 8.0))
        self.assertEqual(session_a.cutoff_y_crop, 8.0)
        self.assertTrue(bool(session_a.valid_mask[8, 4]))
        self.assertFalse(bool(session_a.valid_mask[9, 4]))
        self.assertEqual(session_a.orientation_run_id, "orient-A")
        object_a = id(session_a)
        analysis_object_a = id(session_a.analysis)

        MainWindow._mark_draft_metrics_stale(window, "S1")
        self.assertNotIn("S1", window._tracking_results_by_sample)
        self.assertIsNone(window._metric_analysis_session)

        window._tracking_result_stale_by_sample.clear()
        window._optical_flow_stale_by_sample.clear()
        window._tracking_results_by_sample["S1"] = analysis_b
        window._read_draft_tracking_payload = MagicMock(
            return_value={"analysis_run_id": "run-B", "analysis_timestamp_utc": "run-B"}
        )
        with patch(
            "actintrack_app.gui.load_latest_structural_orientation_result",
            return_value=StructuralOrientationResult(
                has_valid_result=True,
                sample_id="S1",
                nucleus_reference_xy_px=(12.0, 16.0),
                analysis_timestamp_utc="orient-B",
            ),
        ):
            resolved = MainWindow._resolve_metric_preview_analysis_for_sample(
                window, "S1"
            )
            self.assertIs(resolved, analysis_b)
            MainWindow._discard_metric_analysis_inspection_state(window)
            session_b = MainWindow._bind_metric_analysis_inspection(window, analysis_b)

        session_b = window._metric_analysis_session
        self.assertEqual(session_b.run_id, "run-B")
        self.assertEqual(session_b.nucleus_xy_crop, (12.0, 16.0))
        self.assertEqual(session_b.cutoff_y_crop, 16.0)
        self.assertTrue(bool(session_b.valid_mask[16, 4]))
        self.assertFalse(bool(session_b.valid_mask[17, 4]))
        self.assertEqual(session_b.orientation_run_id, "orient-B")
        self.assertNotEqual(id(session_b), object_a)
        self.assertNotEqual(id(session_b.analysis), analysis_object_a)
        self.assertIs(session_b.analysis, analysis_b)

    def test_nucleus_only_change_rebinds_nucleus_and_keeps_new_run(self) -> None:
        window = self._stub()
        mask = _mask(24, 20, 10)
        analysis_a = _analysis(
            run_id="run-A", nucleus=(5.0, 10.0), cutoff_y=10.0, mask=mask
        )
        analysis_b = _analysis(
            run_id="run-B", nucleus=(15.0, 10.0), cutoff_y=10.0, mask=mask
        )
        with patch(
            "actintrack_app.gui.load_latest_structural_orientation_result",
            return_value=StructuralOrientationResult(
                has_valid_result=True,
                nucleus_reference_xy_px=(5.0, 10.0),
                analysis_timestamp_utc="orient-A",
            ),
        ):
            session_a = MainWindow._bind_metric_analysis_inspection(window, analysis_a)
        MainWindow._discard_metric_analysis_inspection_state(window)
        with patch(
            "actintrack_app.gui.load_latest_structural_orientation_result",
            return_value=StructuralOrientationResult(
                has_valid_result=True,
                nucleus_reference_xy_px=(15.0, 10.0),
                analysis_timestamp_utc="orient-B",
            ),
        ):
            session_b = MainWindow._bind_metric_analysis_inspection(window, analysis_b)
        self.assertEqual(session_a.cutoff_y_crop, 10.0)
        self.assertEqual(session_b.cutoff_y_crop, 10.0)
        self.assertEqual(session_b.nucleus_xy_crop, (15.0, 10.0))
        self.assertNotEqual(session_a.nucleus_xy_crop, session_b.nucleus_xy_crop)
        self.assertNotEqual(id(session_a), id(session_b))
        self.assertEqual(session_b.orientation_run_id, "orient-B")

    def test_cutoff_only_change_rebinds_domain_and_cutoff(self) -> None:
        window = self._stub()
        analysis_a = _analysis(
            run_id="run-A",
            nucleus=(8.0, 6.0),
            cutoff_y=6.0,
            mask=_mask(24, 20, 6),
        )
        analysis_b = _analysis(
            run_id="run-B",
            nucleus=(8.0, 6.0),
            cutoff_y=14.0,
            mask=_mask(24, 20, 14),
        )
        with patch(
            "actintrack_app.gui.load_latest_structural_orientation_result",
            return_value=None,
        ):
            session_a = MainWindow._bind_metric_analysis_inspection(window, analysis_a)
            MainWindow._discard_metric_analysis_inspection_state(window)
            session_b = MainWindow._bind_metric_analysis_inspection(window, analysis_b)
        self.assertEqual(session_a.nucleus_xy_crop, session_b.nucleus_xy_crop)
        self.assertEqual(session_b.cutoff_y_crop, 14.0)
        self.assertTrue(bool(session_b.valid_mask[14, 3]))
        self.assertFalse(bool(session_b.valid_mask[15, 3]))
        self.assertFalse(bool(session_a.valid_mask[14, 3]))

    def test_stale_cache_from_run_a_is_not_used_for_run_b(self) -> None:
        window = self._stub()
        analysis_a = _analysis(
            run_id="run-A", nucleus=(1.0, 2.0), cutoff_y=2.0, mask=_mask(24, 20, 2)
        )
        window._tracking_results_by_sample["S1"] = analysis_a
        window._read_draft_tracking_payload = MagicMock(
            return_value={
                "analysis_run_id": "run-B",
                "analysis_timestamp_utc": "run-B",
                "num_tracks_with_valid_steps": 1,
                "nucleus_reference": {
                    "x_px": 9.0,
                    "y_px": 11.0,
                    "coordinate_space": "crop_local_pixels",
                },
                "cutoff_boundary": {
                    "y_px": 11.0,
                    "coordinate_space": "crop_local_pixels",
                },
            }
        )
        window._sample_file_path = MagicMock(return_value=MagicMock(exists=lambda: True))
        window._saved_scientific_valid_mask_for_sample = MagicMock(
            return_value=_mask(24, 20, 11)
        )
        frames = [np.zeros((24, 20, 3), dtype=np.uint8) for _ in range(3)]
        with patch("actintrack_app.gui.is_supported_video_path", return_value=True), patch(
            "actintrack_app.gui.load_cropped_frames_from_video",
            return_value=frames,
        ), patch(
            "actintrack_app.gui.analyze_cropped_preview",
        ) as analyze:
            rebuilt = MainWindow._resolve_metric_preview_analysis_for_sample(
                window, "S1"
            )
        analyze.assert_not_called()
        self.assertIsNotNone(rebuilt)
        assert rebuilt is not None
        self.assertIsNot(rebuilt, analysis_a)
        self.assertEqual(rebuilt.analysis_run_id, "run-B")
        self.assertEqual(rebuilt.nucleus_reference_xy_px, (9.0, 11.0))
        self.assertEqual(rebuilt.cutoff_y_crop_px, 11.0)


class MetricAnalysisDisplayFramingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def test_analyzed_region_bounds_include_margin(self) -> None:
        mask = np.zeros((40, 40), dtype=bool)
        mask[10:16, 12:18] = True
        bounds = analyzed_region_view_bounds(mask, margin_px=4)
        self.assertEqual(bounds, (8, 6, 22, 20))

    def test_guides_and_zoom_keep_overlay_alignment(self) -> None:
        frame = np.zeros((30, 40, 3), dtype=np.uint8)
        mask = np.zeros((30, 40), dtype=bool)
        mask[5:20, 8:28] = True
        guided = draw_metric_analysis_guides(
            frame,
            nucleus_xy=(18.0, 12.0),
            cutoff_y=12.0,
            valid_mask=mask,
        )
        bounds = analyzed_region_view_bounds(mask, margin_px=2)
        zoomed = crop_frame_to_view_bounds(guided, bounds)
        x0, y0, x1, y1 = bounds
        self.assertEqual(zoomed.shape[1], x1 - x0)
        self.assertEqual(zoomed.shape[0], y1 - y0)
        nx, ny = 18 - x0, 12 - y0
        self.assertGreater(int(zoomed[ny, nx].sum()), 0)

    def test_metric_analysis_preview_omits_cell_boundary_caption(self) -> None:
        canvas = ImageCanvas(MagicMock())
        frame = np.zeros((16, 16, 3), dtype=np.uint8)
        canvas.set_scientific_overlay(
            validity_mask=np.ones((16, 16), dtype=bool),
            cutoff_y=8.0,
            nucleus_xy=(4.0, 8.0),
            show_domain_caption=True,
        )
        canvas.set_preview_frame(frame)
        self.assertFalse(canvas._show_domain_caption)
        self.assertIsNone(canvas._nucleus_xy)
        self.assertIsNone(canvas._cutoff_y)
        self.assertIsNone(canvas._validity_mask)

    def test_full_preview_caption_path_unchanged(self) -> None:
        src = _read("actintrack_app/gui_canvas.py")
        self.assertIn('"Cell Boundary (analysis area)"', src)
        self.assertIn("self._show_domain_caption and self._validity_mask", src)
        gui = _read("actintrack_app/gui.py")
        self.assertIn("show_domain_caption=True", gui)

    def test_show_cropped_frame_uses_session_and_frames_to_analyzed_region(self) -> None:
        window = MainWindow.__new__(MainWindow)
        mask = np.zeros((24, 20), dtype=bool)
        mask[2:10, 4:16] = True
        analysis = _analysis(
            run_id="run-B",
            nucleus=(10.0, 6.0),
            cutoff_y=6.0,
            mask=mask,
        )
        window._cropped_preview = analysis
        window._cropped_metric_mode = "template"
        window._metric_analysis_session = MetricAnalysisInspectionSession(
            sample_id="S1",
            run_id="run-B",
            analysis=analysis,
            nucleus_xy_crop=(10.0, 6.0),
            cutoff_y_crop=6.0,
            valid_mask=mask,
            orientation_run_id="orient-B",
            view_bounds=analyzed_region_view_bounds(mask, margin_px=2),
        )
        window._metric_analysis_orientation = None
        window._preview_frame_index = 0
        captured: list[np.ndarray] = []
        window.canvas = MagicMock()
        window.canvas.set_preview_frame.side_effect = (
            lambda frame, **kwargs: captured.append(frame)
        )
        window.slider_frame = MagicMock()
        window.spin_frame = MagicMock()
        window.slider_sample_frame = MagicMock()
        window.lbl_sample_frame = MagicMock()
        window.lbl_frame_info = MagicMock()
        MainWindow._show_cropped_preview_frame(window, 0)
        self.assertEqual(len(captured), 1)
        shown = captured[0]
        x0, y0, x1, y1 = window._metric_analysis_session.view_bounds
        self.assertEqual(shown.shape[1], x1 - x0)
        self.assertEqual(shown.shape[0], y1 - y0)


class InspectionModeRegressionTests(unittest.TestCase):
    def test_inspection_modes_unchanged(self) -> None:
        builders = _read("actintrack_app/gui_layout_builders.py")
        self.assertIn("Display / Inspection Mode", builders)
        self.assertIn('addItem("Template Tracking", "template")', builders)
        self.assertIn('addItem("Optical Flow", "optical_flow")', builders)
        self.assertIn('addItem("F-actin Orientation", "orientation")', builders)
        self.assertNotIn(
            "layout.addWidget(window.chk_show_orientation_overlay)",
            builders,
        )
        self.assertNotIn(
            "layout.addWidget(window.chk_show_of_overlay)",
            builders,
        )
        gui = _read("actintrack_app/gui.py")
        self.assertIn("Optical Flow inspection always shows the OF overlay", gui)
        self.assertIn('mode == "orientation"', gui)


class SetupSpacingUx6Tests(unittest.TestCase):
    def test_section_spacing_token_increased(self) -> None:
        self.assertGreaterEqual(SIDE_PANEL_SECTION_SPACING, 16)
        builders = _read("actintrack_app/gui_layout_builders.py")
        self.assertGreaterEqual(
            builders.count("layout.addSpacing(SIDE_PANEL_SECTION_SPACING)"),
            4,
        )


class DraftCutoffRestoreTests(unittest.TestCase):
    def test_draft_restore_includes_run_id_cutoff_nucleus(self) -> None:
        frames = [np.zeros((8, 8, 3), dtype=np.uint8) for _ in range(2)]
        draft = {
            "analysis_run_id": "run-B",
            "analysis_timestamp_utc": "run-B",
            "num_tracks_with_valid_steps": 1,
            "nucleus_reference": {"x_px": 3.0, "y_px": 4.0},
            "cutoff_boundary": {"y_px": 4.0},
        }
        analysis = cropped_preview_analysis_from_draft(frames, draft)
        self.assertEqual(analysis.analysis_run_id, "run-B")
        self.assertEqual(analysis.nucleus_reference_xy_px, (3.0, 4.0))
        self.assertEqual(analysis.cutoff_y_crop_px, 4.0)


class ScientificDomainStillMatchesMaskTests(unittest.TestCase):
    def test_preview_domain_uses_same_mask(self) -> None:
        crop = RectROI(0, 0, 20, 16)
        cell = CellRegion.from_rect(RectROI(0, 0, 20, 16))
        cutoff = CutoffBoundary(y=7.0)
        mask = valid_mask_crop_local(crop, cell_region=cell, cutoff=cutoff)
        frame = np.full((16, 20, 3), 80, dtype=np.uint8)
        preview = apply_scientific_domain_to_preview(frame, mask)
        self.assertTrue(np.all(preview[0:8] == 80))
        self.assertTrue(np.all(preview[8:] == 0))


class CurrentDraftLoaderTests(unittest.TestCase):
    def test_current_draft_is_preferred_over_older_finalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            from actintrack_app.schema_compat import draft_tracking_path

            sid = "S1"
            path = draft_tracking_path(root, sid)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "num_tracks_with_valid_steps": 2,
                        "absolute_velocity_index_um_per_s": 9.0,
                        "analysis_run_id": "run-B",
                    }
                ),
                encoding="utf-8",
            )
            view = load_latest_tracking_result_view(
                sid,
                project_root=root,
                sample_row={
                    "group": "g",
                    "batch_name": "b",
                    "final_export_name": "out",
                },
                cached_preview=_analysis(
                    run_id="run-A",
                    nucleus=(1.0, 1.0),
                    cutoff_y=1.0,
                    mask=_mask(24, 20, 1),
                ),
            )
            self.assertIsNotNone(view)
            assert view is not None
            self.assertEqual(view.general_movement, 9.0)


class SampleSwitchAndCanvasSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def test_switching_samples_discards_previous_inspection_session(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window._of_flow_caches = {"S1": object(), "S2": object()}
        window.canvas = MagicMock()
        analysis_s1 = _analysis(
            run_id="run-S1",
            nucleus=(3.0, 4.0),
            cutoff_y=4.0,
            mask=_mask(24, 20, 4),
        )
        with patch(
            "actintrack_app.gui.load_latest_structural_orientation_result",
            return_value=None,
        ):
            session_s1 = MainWindow._bind_metric_analysis_inspection(
                window, analysis_s1
            )
        self.assertEqual(session_s1.sample_id, "S1")
        MainWindow._discard_metric_analysis_inspection_state(window)
        self.assertIsNone(window._metric_analysis_session)
        self.assertIsNone(window._cropped_preview)
        self.assertNotIn("S1", window._of_flow_caches)
        window._current_sample_id = "S2"

    def test_canvas_smoke_run_a_then_run_b_shows_new_guides(self) -> None:
        window = MainWindow.__new__(MainWindow)
        canvas = ImageCanvas(window)
        window.canvas = canvas
        window._cropped_metric_mode = "template"
        window._preview_frame_index = 0
        window.slider_frame = MagicMock()
        window.spin_frame = MagicMock()
        window.slider_sample_frame = MagicMock()
        window.lbl_sample_frame = MagicMock()
        window.lbl_frame_info = MagicMock()
        window._metric_analysis_orientation = None

        mask_a = _mask(24, 20, 6)
        mask_b = _mask(24, 20, 16)
        analysis_a = _analysis(
            run_id="run-A", nucleus=(5.0, 6.0), cutoff_y=6.0, mask=mask_a
        )
        analysis_b = _analysis(
            run_id="run-B", nucleus=(14.0, 16.0), cutoff_y=16.0, mask=mask_b
        )
        window._cropped_preview = analysis_a
        window._metric_analysis_session = MetricAnalysisInspectionSession(
            sample_id="S1",
            run_id="run-A",
            analysis=analysis_a,
            nucleus_xy_crop=(5.0, 6.0),
            cutoff_y_crop=6.0,
            valid_mask=mask_a,
            view_bounds=analyzed_region_view_bounds(mask_a, margin_px=2),
        )
        MainWindow._show_cropped_preview_frame(window, 0)
        frame_a = np.array(canvas._frame, copy=True)
        self.assertFalse(canvas._show_domain_caption)
        self.assertIsNone(canvas._nucleus_xy)

        window._cropped_preview = analysis_b
        window._metric_analysis_session = MetricAnalysisInspectionSession(
            sample_id="S1",
            run_id="run-B",
            analysis=analysis_b,
            nucleus_xy_crop=(14.0, 16.0),
            cutoff_y_crop=16.0,
            valid_mask=mask_b,
            view_bounds=analyzed_region_view_bounds(mask_b, margin_px=2),
        )
        MainWindow._show_cropped_preview_frame(window, 0)
        frame_b = np.array(canvas._frame, copy=True)
        self.assertNotEqual(frame_a.shape, frame_b.shape)
        self.assertFalse(np.array_equal(frame_a, frame_b))
        self.assertFalse(canvas._show_domain_caption)
        self.assertIsNone(canvas._validity_mask)


if __name__ == "__main__":
    unittest.main()
