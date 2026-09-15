"""Phase UX1 scientific Workbench workflow consolidation tests."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

from actintrack_app.workflow_state import (
    ANNOTATION_FIELD_CROP_CONFIRMED,
    WorkflowSnapshot,
    build_workflow_snapshot,
    crop_confirmed_from_annotation,
    format_sample_results_summary,
)


class WorkflowSnapshotGatingTests(unittest.TestCase):
    def test_no_crop_disables_run_and_metric_analysis(self) -> None:
        snap = build_workflow_snapshot(
            has_sample=True,
            has_crop=False,
            crop_confirmed=False,
            has_cell_region=False,
            has_nucleus=False,
            timing_confirmed=False,
            metrics_present=False,
            metrics_stale=False,
        )
        self.assertFalse(snap.ready_to_run)
        self.assertFalse(snap.metric_analysis_allowed)
        self.assertEqual(snap.run_metrics_block_reason(), "Wait for the cell boundary to be identified")
        self.assertEqual(snap.metric_analysis_block_reason(), "Run Metrics first")

    def test_unconfirmed_crop_does_not_block_run(self) -> None:
        snap = build_workflow_snapshot(
            has_sample=True,
            has_crop=True,
            crop_confirmed=False,
            has_cell_region=True,
            has_nucleus=False,
            has_cutoff=True,
            timing_confirmed=True,
            metrics_present=False,
            metrics_stale=False,
        )
        self.assertTrue(snap.ready_to_run)
        self.assertIsNone(snap.run_metrics_block_reason())

    def test_cell_without_nucleus_still_ready(self) -> None:
        snap = build_workflow_snapshot(
            has_sample=True,
            has_crop=True,
            crop_confirmed=True,
            has_cell_region=True,
            has_nucleus=False,
            has_cutoff=True,
            timing_confirmed=True,
            metrics_present=False,
            metrics_stale=False,
        )
        self.assertTrue(snap.ready_to_run)
        self.assertFalse(snap.can_compute_nucleus_metrics)
        self.assertIsNone(snap.run_metrics_block_reason())

    def test_missing_cutoff_blocks_run(self) -> None:
        snap = build_workflow_snapshot(
            has_sample=True,
            has_crop=True,
            crop_confirmed=True,
            has_cell_region=True,
            has_nucleus=True,
            has_cutoff=False,
            timing_confirmed=True,
            metrics_present=False,
            metrics_stale=False,
        )
        self.assertEqual(
            snap.run_metrics_block_reason(),
            "Set the Measurement Cutoff to continue.",
        )

    def test_timing_unconfirmed_blocks_run(self) -> None:
        snap = build_workflow_snapshot(
            has_sample=True,
            has_crop=True,
            crop_confirmed=True,
            has_cell_region=True,
            has_nucleus=True,
            has_cutoff=True,
            timing_confirmed=False,
            metrics_present=False,
            metrics_stale=False,
        )
        self.assertEqual(snap.run_metrics_block_reason(), "Valid video timing is required")

    def test_ready_enables_run_but_not_metric_analysis(self) -> None:
        snap = build_workflow_snapshot(
            has_sample=True,
            has_crop=True,
            crop_confirmed=True,
            has_cell_region=True,
            has_nucleus=True,
            has_cutoff=True,
            timing_confirmed=True,
            metrics_present=False,
            metrics_stale=False,
        )
        self.assertTrue(snap.ready_to_run)
        self.assertIsNone(snap.run_metrics_block_reason())
        self.assertFalse(snap.metric_analysis_allowed)

    def test_current_metrics_enable_metric_analysis(self) -> None:
        snap = build_workflow_snapshot(
            has_sample=True,
            has_crop=True,
            crop_confirmed=True,
            has_cell_region=True,
            has_nucleus=True,
            has_cutoff=True,
            timing_confirmed=True,
            metrics_present=True,
            metrics_stale=False,
        )
        self.assertTrue(snap.metric_analysis_allowed)
        self.assertTrue(snap.metrics_current)

    def test_stale_metrics_disable_metric_analysis(self) -> None:
        snap = build_workflow_snapshot(
            has_sample=True,
            has_crop=True,
            crop_confirmed=True,
            has_cell_region=True,
            has_nucleus=True,
            has_cutoff=True,
            timing_confirmed=True,
            metrics_present=True,
            metrics_stale=True,
        )
        self.assertFalse(snap.metric_analysis_allowed)
        self.assertEqual(
            snap.metric_analysis_block_reason(),
            "Results are outdated — run Metrics again",
        )
        self.assertTrue(snap.ready_to_run)


class CropConfirmedLegacyTests(unittest.TestCase):
    def test_explicit_false_wins(self) -> None:
        self.assertFalse(
            crop_confirmed_from_annotation(
                {"rectangle_roi": {"x": 1}, ANNOTATION_FIELD_CROP_CONFIRMED: False}
            )
        )

    def test_legacy_roi_infers_confirmed(self) -> None:
        self.assertTrue(
            crop_confirmed_from_annotation({"rectangle_roi": {"x": 0, "y": 0}})
        )

    def test_missing_roi_unconfirmed(self) -> None:
        self.assertFalse(crop_confirmed_from_annotation({"sample_id": "S1"}))


class SampleResultsFormattingTests(unittest.TestCase):
    def test_panel_uses_persisted_values_not_recompute(self) -> None:
        text = format_sample_results_summary(
            sparse_px=8.18,
            sparse_um_s=13.0,
            of_px=4.52,
            of_um_s=7.19,
            toward_nucleus_um_s=1.2,
            orientation_deg=33.5,
            tracks_used=8,
            tracks_requested=10,
            timing_label="video_header · 0.1667 s/frame",
            timing_confirmed=True,
            stale=False,
        )
        self.assertIn("SAMPLE RESULTS", text)
        self.assertIn("8.18 px/frame", text)
        self.assertIn("13.00 µm/s", text)
        self.assertIn("4.52 px/frame", text)
        self.assertIn("Toward Nucleus", text)
        self.assertNotIn("F-actin Orientation", text)
        self.assertNotIn("33.5°", text)
        self.assertIn("8 valid / 10 requested", text)
        self.assertIn("Video Timing", text)
        self.assertIn("video_header", text)
        self.assertNotIn("Timing unconfirmed", text)

    def test_unconfirmed_timing_marker(self) -> None:
        text = format_sample_results_summary(
            sparse_px=1.0,
            sparse_um_s=0.5,
            of_px=None,
            of_um_s=None,
            toward_nucleus_um_s=None,
            orientation_deg=None,
            tracks_used=2,
            tracks_requested=2,
            timing_label="lab_default · 30.0000 s/frame",
            timing_confirmed=False,
        )
        self.assertIn("Timing unconfirmed", text)


class GuiWorkflowIntegrationTests(unittest.TestCase):
    """Lightweight MainWindow stubs — no Qt widget construction required."""

    def _stub(self) -> MagicMock:
        from actintrack_app.gui import MainWindow

        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window._base_frame = object()
        window._crop_confirmed = False
        window._cell_region = None
        window._nucleus_reference = None
        window._timing = None
        window._cell_boundary_sensitivity = 0.5
        window._tracking_result_stale_by_sample = {}
        window._optical_flow_stale_by_sample = {}
        window._metrics_inflight = set()
        window.canvas = MagicMock()
        window.canvas.rect_roi.return_value = None
        window._sample_has_measurable_draft_results = MagicMock(return_value=False)
        return window

    def test_crop_confirmed_generates_cell_once(self) -> None:
        from actintrack_app.gui import MainWindow
        from actintrack_app.orientation import RectROI
        from actintrack_app.scientific_annotations import CellRegion

        window = self._stub()
        window._project_root = Path("/tmp")
        window._current_sample = {"sample_id": "S1"}
        window.canvas.rect_roi.return_value = RectROI(10, 10, 40, 40)
        oriented = MagicMock()
        oriented.shape = (100, 100, 3)
        window._oriented_frame = MagicMock(return_value=oriented)
        fake_cell = CellRegion.from_rect(RectROI(12, 12, 30, 30))
        window._sync_scientific_overlay = MagicMock()
        window._autosave_roi = MagicMock(return_value=True)
        window._update_metric_freshness_label = MagicMock()
        window._status = MagicMock()
        window._sync_cell_boundary_slider = MagicMock()
        window._set_computational_crop = MagicMock()
        window._derive_computational_crop_from_cell = MagicMock()

        with mock.patch(
            "actintrack_app.gui.suggest_conservative_cell_region",
            return_value=fake_cell,
        ) as suggest:
            with mock.patch(
                "actintrack_app.gui.suggest_default_cutoff_boundary",
                return_value=None,
            ):
                MainWindow.on_crop_confirmed(window)
                suggest.assert_called_once()
        self.assertIs(window._cell_region, fake_cell)

    def test_roi_edit_does_not_clear_cell_region(self) -> None:
        from actintrack_app.gui import MainWindow
        from actintrack_app.orientation import RectROI

        window = self._stub()
        window._crop_confirmed = True
        window._cell_region = object()
        window._mark_draft_metrics_stale = MagicMock()
        window._set_roi_save_status = MagicMock()
        window._loaded_annotation_source = "manual"
        window._refresh_roi_preview_panel = MagicMock()
        window._sync_workflow_controls = MagicMock()
        MainWindow.on_roi_changed(window, RectROI(1, 1, 20, 20))
        self.assertIsNotNone(window._cell_region)
        window._mark_draft_metrics_stale.assert_not_called()


if __name__ == "__main__":
    unittest.main()
