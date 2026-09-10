"""Phase UX2: automatic cell-first workflow, sensitivity, multi-delete."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

import numpy as np
from PyQt6.QtCore import QItemSelectionModel, Qt
from PyQt6.QtWidgets import QApplication, QTreeWidgetItem

from actintrack_app.cell_detection import (
    CELL_BOUNDARY_SENSITIVITY_BROADER,
    CELL_BOUNDARY_SENSITIVITY_DEFAULT,
    CELL_BOUNDARY_SENSITIVITY_TIGHTER,
    DEFAULT_COMPUTATIONAL_CROP_PADDING_PX,
    computational_crop_from_cell_region,
    detection_parameters_payload,
    map_boundary_sensitivity,
    suggest_conservative_cell_region,
)
from actintrack_app.explorer_sidebar import sample_tree_meta
from actintrack_app.explorer_tree import ExplorerTreeWidget
from actintrack_app.gui import MainWindow
from actintrack_app.gui_canvas import ImageCanvas
from actintrack_app.orientation import OrientationState, RectROI
from actintrack_app.scientific_annotations import (
    CELL_REGION_SOURCE_AUTO,
    CUTOFF_SOURCE_AUTO,
    CUTOFF_SOURCE_MANUAL,
    CellRegion,
    CutoffBoundary,
    NucleusReference,
)
from actintrack_app.timing_provenance import TimingMetadata
from actintrack_app.workflow_state import (
    build_workflow_snapshot,
    format_delete_samples_confirmation,
)


def _halo_cell_frame(h: int = 80, w: int = 100) -> np.ndarray:
    """Bright core plus a dim halo over black background (intensity, not hue)."""
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[18:62, 20:80] = (28, 28, 28)
    frame[28:52, 32:68] = (40, 220, 40)
    return frame


class DerivedCropAndSensitivityTests(unittest.TestCase):
    def test_new_sample_detects_cell_and_derives_crop(self) -> None:
        frame = _halo_cell_frame()
        cell = suggest_conservative_cell_region(frame)
        crop = computational_crop_from_cell_region(
            cell, frame.shape[1], frame.shape[0]
        )
        bbox = cell.bounding_box()
        self.assertGreaterEqual(bbox.width, 4)
        self.assertGreaterEqual(bbox.height, 4)
        self.assertLessEqual(crop.x, bbox.x)
        self.assertLessEqual(crop.y, bbox.y)
        self.assertGreaterEqual(crop.x1, bbox.x1)
        self.assertGreaterEqual(crop.y1, bbox.y1)
        self.assertLessEqual(bbox.x - crop.x, DEFAULT_COMPUTATIONAL_CROP_PADDING_PX)
        self.assertLessEqual(crop.x1 - bbox.x1, DEFAULT_COMPUTATIONAL_CROP_PADDING_PX)

    def test_default_sensitivity_matches_unparameterized_call(self) -> None:
        frame = _halo_cell_frame()
        a = suggest_conservative_cell_region(frame)
        b = suggest_conservative_cell_region(
            frame, sensitivity=CELL_BOUNDARY_SENSITIVITY_DEFAULT
        )
        self.assertEqual(a.region.geometry_key(), b.region.geometry_key())

    def test_tighter_reduces_background_inclusion(self) -> None:
        frame = _halo_cell_frame()
        default = suggest_conservative_cell_region(
            frame, sensitivity=CELL_BOUNDARY_SENSITIVITY_DEFAULT
        )
        tight = suggest_conservative_cell_region(
            frame, sensitivity=CELL_BOUNDARY_SENSITIVITY_TIGHTER
        )
        full = RectROI(0, 0, frame.shape[1], frame.shape[0])
        default_area = int(default.rasterize_crop_mask(full).sum())
        tight_area = int(tight.rasterize_crop_mask(full).sum())
        self.assertLess(tight_area, default_area)
        self.assertFalse(bool(tight.rasterize_crop_mask(full)[0, 0]))

    def test_broader_preserves_dim_cell_signal(self) -> None:
        frame = _halo_cell_frame()
        default = suggest_conservative_cell_region(
            frame, sensitivity=CELL_BOUNDARY_SENSITIVITY_DEFAULT
        )
        broad = suggest_conservative_cell_region(
            frame, sensitivity=CELL_BOUNDARY_SENSITIVITY_BROADER
        )
        full = RectROI(0, 0, frame.shape[1], frame.shape[0])
        default_area = int(default.rasterize_crop_mask(full).sum())
        broad_area = int(broad.rasterize_crop_mask(full).sum())
        self.assertGreaterEqual(broad_area, default_area)
        self.assertTrue(bool(broad.rasterize_crop_mask(full)[30, 40]))

    def test_detection_parameter_payload_persists_version(self) -> None:
        payload = detection_parameters_payload(0.25)
        self.assertEqual(payload["version"], "conservative_cell_v2")
        self.assertIn("otsu_scale", payload)
        self.assertEqual(payload["sensitivity"], 0.25)
        default_params = map_boundary_sensitivity(0.5)
        self.assertEqual(default_params.otsu_scale, 0.30)
        self.assertEqual(default_params.dilate_iterations, 2)


class WorkflowGatingUx2Tests(unittest.TestCase):
    def test_run_metrics_requires_cell_nucleus_timing_not_crop_confirmed(self) -> None:
        snap = build_workflow_snapshot(
            has_sample=True,
            has_crop=True,
            crop_confirmed=False,
            has_cell_region=True,
            has_nucleus=True,
            timing_confirmed=True,
            metrics_present=False,
            metrics_stale=False,
        )
        self.assertTrue(snap.ready_to_run)
        self.assertIsNone(snap.run_metrics_block_reason())
        self.assertFalse(snap.metric_analysis_allowed)

    def test_metric_analysis_still_gated_on_current_metrics(self) -> None:
        snap = build_workflow_snapshot(
            has_sample=True,
            has_crop=True,
            has_cell_region=True,
            has_nucleus=True,
            timing_confirmed=True,
            metrics_present=True,
            metrics_stale=True,
        )
        self.assertTrue(snap.ready_to_run)
        self.assertFalse(snap.metric_analysis_allowed)

    def test_no_confirm_crop_in_hints(self) -> None:
        snap = build_workflow_snapshot(
            has_sample=True,
            has_crop=True,
            crop_confirmed=False,
            has_cell_region=True,
            has_nucleus=False,
            timing_confirmed=False,
            metrics_present=False,
            metrics_stale=False,
        )
        self.assertNotIn("crop", snap.next_action_hint().lower())
        self.assertNotIn("Confirm the crop", snap.run_metrics_block_reason() or "")


class CanvasNoManualCropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_no_confirm_chip_or_crop_label(self) -> None:
        from pathlib import Path

        src = Path(__file__).resolve().parents[1].joinpath(
            "actintrack_app/gui_canvas.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('label = "Confirm"', src)
        self.assertNotIn('painter.drawText(x0 + 6, y0 + 14, "Crop")', src)
        layout = Path(__file__).resolve().parents[1].joinpath(
            "actintrack_app/gui_layout_builders.py"
        ).read_text(encoding="utf-8")
        self.assertIn("slider_cell_boundary", layout)
        self.assertIn("Tighter", layout)
        self.assertIn("Broader", layout)
        gui = Path(__file__).resolve().parents[1].joinpath(
            "actintrack_app/gui.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Clear ROI", gui)
        self.assertNotIn('menu.addAction("Confirm Crop")', gui)
        self.assertNotIn("btn_confirm_crop", gui)

    def test_canvas_does_not_start_draw_mode(self) -> None:
        from PyQt6.QtWidgets import QWidget

        host = QWidget()
        host._scientific_placement_mode = None
        canvas = ImageCanvas(host)
        canvas._frame = np.zeros((40, 50, 3), dtype=np.uint8)
        canvas._interactive = True
        from PyQt6.QtGui import QMouseEvent
        from PyQt6.QtCore import QPointF

        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(10, 10),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        canvas._widget_to_image = MagicMock(return_value=(8, 9))
        canvas.mousePressEvent(event)
        self.assertEqual(canvas._drag_mode.name, "NONE")


class CellFirstGuiTests(unittest.TestCase):
    def _stub(self) -> MainWindow:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window._current_sample = {"sample_id": "S1"}
        window._project_root = None
        window._cell_region = None
        window._nucleus_reference = None
        window._cutoff_boundary = None
        window._timing = None
        window._cell_boundary_sensitivity = CELL_BOUNDARY_SENSITIVITY_DEFAULT
        window._tracking_result_stale_by_sample = {}
        window._optical_flow_stale_by_sample = {}
        window._metrics_inflight = set()
        window.canvas = MagicMock()
        window.canvas.rect_roi.return_value = None
        window._oriented_frame = MagicMock(return_value=_halo_cell_frame())
        window._sync_scientific_overlay = MagicMock()
        window._autosave_roi = MagicMock(return_value=True)
        window._update_metric_freshness_label = MagicMock()
        window._status = MagicMock()
        window._sync_workflow_controls = MagicMock()
        window._set_computational_crop = MagicMock()
        window._mark_draft_metrics_stale = MagicMock()
        return window

    def test_saved_cell_is_not_regenerated(self) -> None:
        window = self._stub()
        saved = CellRegion.from_rect(
            RectROI(2, 3, 8, 9), source=CELL_REGION_SOURCE_AUTO
        )
        window._cell_region = saved
        window.canvas.rect_roi.return_value = RectROI(1, 2, 12, 14)
        with mock.patch(
            "actintrack_app.gui.suggest_conservative_cell_region"
        ) as suggest:
            MainWindow._ensure_cell_first_setup(window, persist=True, regenerate_cell=False)
            suggest.assert_not_called()
        self.assertIs(window._cell_region, saved)

    def test_slider_commit_stales_metrics_and_does_not_run(self) -> None:
        window = self._stub()
        window._nucleus_reference = NucleusReference(10.0, 12.0, source="manual")
        window._timing = TimingMetadata.lab_default(confirmed=True)
        window._cutoff_boundary = CutoffBoundary(20.0, source=CUTOFF_SOURCE_MANUAL)
        window.run_metrics_for_sample_id = MagicMock()
        window._compute_metrics_for_sample = MagicMock()
        window._update_metric_freshness_label = MagicMock()
        window._status = MagicMock()
        MainWindow._commit_cell_boundary_sensitivity(window)
        window._mark_draft_metrics_stale.assert_called_with("S1")
        window.run_metrics_for_sample_id.assert_not_called()
        window._compute_metrics_for_sample.assert_not_called()
        self.assertEqual(window._nucleus_reference.x, 10.0)
        self.assertTrue(window._timing.confirmed)
        self.assertEqual(window._cutoff_boundary.y, 20.0)
        self.assertEqual(window._cutoff_boundary.source, CUTOFF_SOURCE_MANUAL)

    def test_slider_preview_does_not_persist_or_run_metrics(self) -> None:
        window = self._stub()
        window.run_metrics_for_sample_id = MagicMock()
        MainWindow._preview_cell_boundary_from_slider(window)
        window._autosave_roi.assert_not_called()
        window.run_metrics_for_sample_id.assert_not_called()
        self.assertIsNotNone(window._cell_region)

    def test_auto_cutoff_on_new_sample(self) -> None:
        window = self._stub()
        fake_cell = CellRegion.from_rect(RectROI(4, 5, 20, 24))
        fake_cutoff = CutoffBoundary(18.0, source=CUTOFF_SOURCE_AUTO)
        with mock.patch(
            "actintrack_app.gui.suggest_conservative_cell_region",
            return_value=fake_cell,
        ):
            with mock.patch(
                "actintrack_app.gui.suggest_default_cutoff_boundary",
                return_value=fake_cutoff,
            ):
                MainWindow._ensure_cell_first_setup(window, persist=False)
        self.assertEqual(window._cutoff_boundary.source, CUTOFF_SOURCE_AUTO)
        self.assertEqual(window._cutoff_boundary.y, 18.0)

    def test_sensitivity_persists_in_annotation_dict(self) -> None:
        from actintrack_app.annotation_schema import (
            ANNOTATION_FIELD_CELL_BOUNDARY_SENSITIVITY,
            cell_boundary_sensitivity_from_annotation,
        )

        window = self._stub()
        window._base_frame = np.zeros((30, 40, 3), dtype=np.uint8)
        window._orientation = OrientationState()
        window._loaded_sample_notes = ""
        window._reference_frame_index = 0
        window._cell_boundary_sensitivity = 0.2
        window._current_sample = {
            "sample_id": "S1",
            "group": "g",
            "batch_name": "b",
            "batch_id": "id",
            "original_filename": "a.mp4",
            "stored_path": "raw/a.mp4",
            "review_status": "approved",
        }
        window._validate_current_roi = MagicMock()
        window._validate_current_roi.return_value.ok = True
        window._validate_current_roi.return_value.roi_oriented = RectROI(0, 0, 10, 10)
        window._validate_current_roi.return_value.roi_original = RectROI(0, 0, 10, 10)
        window.canvas.rect_roi.return_value = RectROI(0, 0, 10, 10)
        window._suggestion_method_for_save = MagicMock(return_value=None)
        window._annotation_source_for_save = MagicMock(return_value="auto_suggested")
        ann = MainWindow._current_annotation_dict(window, status="roi_marked", require_roi=False)
        self.assertEqual(ann[ANNOTATION_FIELD_CELL_BOUNDARY_SENSITIVITY], 0.2)
        self.assertEqual(cell_boundary_sensitivity_from_annotation(ann), 0.2)
        self.assertEqual(ann["cell_detection"]["version"], "conservative_cell_v2")


class ExplorerMultiSelectDeleteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_extended_selection_and_ctrl_toggle(self) -> None:
        tree = ExplorerTreeWidget()
        self.assertEqual(tree.selectionMode().name, "ExtendedSelection")
        group = QTreeWidgetItem(["Group"])
        tree.addTopLevelItem(group)
        items = []
        for i in range(3):
            child = QTreeWidgetItem([f"s{i}"])
            child.setData(
                0,
                Qt.ItemDataRole.UserRole,
                sample_tree_meta(
                    {
                        "sample_id": f"S{i}",
                        "group": "cg_a",
                        "batch_name": f"s{i}",
                        "original_filename": f"s{i}.mp4",
                    }
                ),
            )
            group.addChild(child)
            items.append(child)
        group.setExpanded(True)
        tree.setCurrentItem(items[0])
        tree.selectionModel().select(
            tree.indexFromItem(items[0]),
            QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        tree.selectionModel().select(
            tree.indexFromItem(items[2]),
            QItemSelectionModel.SelectionFlag.Toggle,
        )
        selected = {tree_item_id(item) for item in tree.selectedItems()}
        self.assertEqual(selected, {"S0", "S2"})

        tree.selectionModel().select(
            tree.indexFromItem(items[0]),
            QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        tree.selectionModel().select(
            tree.indexFromItem(items[2]),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Clear,
        )
        # Shift-style contiguous range via Select from first to last after anchor.
        tree.setCurrentItem(items[0])
        tree.selectionModel().select(
            tree.indexFromItem(items[0]),
            QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        start = tree.indexFromItem(items[0])
        end = tree.indexFromItem(items[2])
        from PyQt6.QtCore import QItemSelection

        selection = QItemSelection(start, end)
        tree.selectionModel().select(
            selection, QItemSelectionModel.SelectionFlag.ClearAndSelect
        )
        self.assertEqual(len(tree.selectedItems()), 3)

    def test_delete_confirmation_count_wording(self) -> None:
        title, text = format_delete_samples_confirmation(count=1)
        self.assertEqual(title, "Delete Sample")
        self.assertEqual(text, "Delete this Sample?")
        title, text = format_delete_samples_confirmation(
            count=5, group_name="WT 550"
        )
        self.assertEqual(title, "Delete 5 Samples")
        self.assertEqual(text, "Delete 5 Samples from WT 550?")

    def test_multi_delete_reuses_canonical_and_reports_failure(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._project_root = Path("/tmp/ws")
        window._current_sample_id = "S1"
        window._confirm_delete_samples = MagicMock(return_value=True)
        window._persisted_sample_row_for_id = MagicMock(
            side_effect=lambda sid: {
                "sample_id": sid,
                "group": "cg_a",
                "batch_name": sid,
            }
        )
        window._delete_one_sample_canonical = MagicMock(
            side_effect=[None, ValueError("locked")]
        )
        window._invalidate_tracking_result_for_sample = MagicMock()
        window._set_active_sample = MagicMock()
        window._after_purge_refresh = MagicMock()
        window._refresh_analysis_if_visible = MagicMock()
        window._sample_display_label_for_id = MagicMock(side_effect=lambda sid: sid)
        with mock.patch("actintrack_app.gui.gui_dialogs.warning") as warn:
            MainWindow._ctx_delete_selected_samples(
                window, ["S1", "S2"], group_name="Group A"
            )
        self.assertEqual(window._delete_one_sample_canonical.call_count, 2)
        warn.assert_called_once()
        message = warn.call_args[0][2]
        self.assertIn("Deleted 1 of 2", message)
        self.assertIn("S2", message)

    def test_single_delete_still_uses_canonical(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._project_root = Path("/tmp/ws")
        window._confirm_delete_samples = MagicMock(return_value=True)
        window._delete_one_sample_canonical = MagicMock(return_value={"ok": True})
        window._set_active_sample = MagicMock()
        window._after_purge_refresh = MagicMock()
        window._refresh_analysis_if_visible = MagicMock()
        window._status = MagicMock()
        MainWindow._ctx_delete_batch(window, "cg_a", "Sample 1")
        window._delete_one_sample_canonical.assert_called_once_with("cg_a", "Sample 1")


def tree_item_id(item: QTreeWidgetItem) -> str:
    meta = item.data(0, Qt.ItemDataRole.UserRole)
    return str(meta.get("sample_id", ""))


class LegacyLoadTests(unittest.TestCase):
    def test_legacy_crop_without_cell_generates_cell_once(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._cell_region = None
        window._cutoff_boundary = None
        window._nucleus_reference = NucleusReference(4.0, 5.0, source="manual")
        window._timing = TimingMetadata.lab_default(confirmed=True)
        window._cell_boundary_sensitivity = CELL_BOUNDARY_SENSITIVITY_DEFAULT
        window._project_root = None
        window._current_sample = None
        window.canvas = MagicMock()
        window.canvas.rect_roi.return_value = RectROI(2, 3, 10, 12)
        window._oriented_frame = MagicMock(return_value=_halo_cell_frame())
        window._sync_scientific_overlay = MagicMock()
        window._autosave_roi = MagicMock()
        window._set_computational_crop = MagicMock()
        fake = CellRegion.from_rect(RectROI(3, 4, 8, 9), source=CELL_REGION_SOURCE_AUTO)
        with mock.patch(
            "actintrack_app.gui.suggest_conservative_cell_region", return_value=fake
        ) as suggest:
            with mock.patch(
                "actintrack_app.gui.suggest_default_cutoff_boundary", return_value=None
            ):
                MainWindow._ensure_missing_cell_region(window, persist=False)
                suggest.assert_called_once()
        self.assertIs(window._cell_region, fake)
        self.assertEqual(window._nucleus_reference.x, 4.0)
        self.assertTrue(window._timing.confirmed)


if __name__ == "__main__":
    unittest.main()
