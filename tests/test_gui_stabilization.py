"""Regression tests for manual-only GUI failures (stabilization phase)."""

from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
from PyQt6.QtWidgets import QApplication, QLineEdit

from actintrack_app.analysis_service import (
    AnalysisReport,
    SampleAnalysisRow,
    SampleMetrics,
)
from actintrack_app.analysis_view import AnalysisViewWidget
from actintrack_app.file_importer import set_custom_export_name
from actintrack_app.gui import MainWindow, _install_gui_exception_reporting
from actintrack_app.gui_canvas import ImageCanvas
from actintrack_app.gui_result_views import (
    OpticalFlowResultView,
    SampleTrackingResultView,
    format_tracking_result_panel_lines,
)
from actintrack_app.metadata import load_samples_csv, save_samples_csv
from actintrack_app.project_manager import create_project_structure
from actintrack_app.utils import METADATA_DIR, SAMPLES_CSV


class ExportNameCallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_gui_imports_set_custom_export_name(self) -> None:
        import actintrack_app.gui as gui_mod

        self.assertIs(gui_mod.set_custom_export_name, set_custom_export_name)

    def test_on_export_name_edited_calls_canonical_helper(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._project_root = Path("/tmp/ws")
        window._current_sample = {
            "sample_id": "S1",
            "auto_export_name": "Breed--01",
            "final_export_name": "Breed--01",
        }
        window.edit_export_name = QLineEdit("CustomName")
        window._status = MagicMock()
        with patch(
            "actintrack_app.gui.set_custom_export_name",
            return_value={
                "auto_export_name": "Breed--01",
                "custom_export_name": "CustomName",
                "final_export_name": "CustomName",
            },
        ) as mock_set:
            MainWindow._on_export_name_edited(window)
        mock_set.assert_called_once_with(Path("/tmp/ws"), "S1", "CustomName")
        self.assertEqual(window._current_sample["final_export_name"], "CustomName")
        window._status.assert_called()

    def test_on_export_name_edited_noop_without_sample(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._project_root = None
        window._current_sample = None
        window.edit_export_name = QLineEdit("x")
        MainWindow._on_export_name_edited(window)


class AnalysisWithoutNucleusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_analysis_view_shows_general_movement_without_nucleus(self) -> None:
        widget = AnalysisViewWidget()
        report = AnalysisReport(
            breed_summaries=[],
            sample_details=[
                SampleAnalysisRow(
                    breed="2_WT_550",
                    sample_label="Sample 1",
                    batch_name="b1",
                    status="motion_index_generated",
                    data_status="ready",
                    metrics=SampleMetrics(
                        general_movement=0.12,
                        of_general_movement=0.08,
                        has_valid_result=True,
                        of_has_valid_result=True,
                        toward_nucleus_velocity=None,
                        orientation_median_deg=None,
                    ),
                    sample_ids=("S1",),
                )
            ],
            breed_comparisons=[],
        )
        widget.refresh(report)
        self.assertFalse(widget.lbl_empty.isVisible())
        gm_item = widget.tbl_sample_details.item(0, 4)
        nuc_item = widget.tbl_sample_details.item(0, 5)
        ori_item = widget.tbl_sample_details.item(0, 6)
        self.assertIsNotNone(gm_item)
        self.assertIn("0.12", gm_item.text())
        self.assertEqual(nuc_item.text(), "—")
        self.assertEqual(ori_item.text(), "—")

    def test_show_analysis_view_refreshes_and_does_not_require_nucleus(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._preview_mode = "full"
        window._exit_cropped_preview_mode = MagicMock()
        window._set_left_explorer_visible = MagicMock()
        window._center_stack = MagicMock()
        window.refresh_analysis_view = MagicMock()
        window._status = MagicMock()
        MainWindow.show_analysis_view(window)
        window._center_stack.setCurrentIndex.assert_called_with(1)
        window.refresh_analysis_view.assert_called_once()
        window._status.assert_called()

    def test_result_panel_keeps_gm_when_optional_fields_missing(self) -> None:
        template = SampleTrackingResultView(
            status="success",
            downward_velocity=0.01,
            general_movement=0.05,
            tracks_used=3,
            tracks_requested=5,
            valid_steps=10,
            toward_nucleus_velocity=None,
            failure_reason="",
        )
        of_view = OpticalFlowResultView(
            status="success",
            general_movement=0.04,
            downward_motion=0.01,
            net_y_velocity=0.0,
            directionality_ratio=0.5,
            valid_pixel_fraction=0.8,
            saturated_pixel_fraction=0.0,
            failure_reason="",
        )
        text = format_tracking_result_panel_lines(
            template,
            of_view,
            structural_orientation_view=None,
            optical_flow_stale=False,
            optical_flow_qc_status="OK",
            optical_flow_frame_pair_count="4",
        )
        self.assertIn("General Movement: 0.0500 µm/s", text)
        self.assertNotIn("Toward Nucleus:", text)
        self.assertIn("Not generated yet", text)


class CanvasScientificLabelTests(unittest.TestCase):
    def test_crop_label_is_secondary_not_scientific_roi(self) -> None:
        src = inspect.getsource(ImageCanvas._redraw)
        self.assertIn('"Crop"', src)
        self.assertNotIn("F-actin analysis ROI", src)
        self.assertIn("Cell Boundary", src)
        self.assertIn("Measurement Cutoff", src)
        self.assertIn("Nucleus", src)


class ExceptionReportingTests(unittest.TestCase):
    def test_exception_hook_installer_is_invoked_from_run_app(self) -> None:
        import actintrack_app.gui as gui_mod

        src = inspect.getsource(gui_mod.run_app)
        self.assertIn("_install_gui_exception_reporting", src)
        self.assertTrue(callable(_install_gui_exception_reporting))


class ExportNameIntegrationTests(unittest.TestCase):
    def test_set_custom_export_name_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ws"
            create_project_structure(root)
            path = root / METADATA_DIR / SAMPLES_CSV
            df = pd.DataFrame(
                [
                    {
                        "sample_id": "S1",
                        "group": "2_WT_550",
                        "batch_number": 1,
                        "batch_name": "batch1",
                        "batch_id": "b1",
                        "original_filename": "a.avi",
                        "stored_path": "raw/a.avi",
                        "file_type": "video",
                        "is_video": True,
                        "is_image_sequence": False,
                        "frame_number": "",
                        "auto_export_name": "WT550--01",
                        "custom_export_name": "",
                        "final_export_name": "WT550--01",
                        "import_date": "",
                        "processing_status": "imported",
                        "annotation_source": "",
                        "review_status": "approved",
                        "notes": "",
                    }
                ]
            )
            save_samples_csv(path, df)
            result = set_custom_export_name(root, "S1", "MyExport")
            self.assertEqual(result["final_export_name"], "MyExport")
            reloaded = load_samples_csv(path)
            self.assertEqual(str(reloaded.iloc[0]["final_export_name"]), "MyExport")


if __name__ == "__main__":
    unittest.main()
