"""ANALYSIS1: researcher-facing Analysis table layout and missing-data display."""

from __future__ import annotations

import inspect
import unittest

from PyQt6.QtWidgets import QApplication

from actintrack_app.analysis_service import (
    AnalysisReport,
    BreedComparisonRow,
    BreedSummaryRow,
    SampleAnalysisRow,
    SampleMetrics,
)
from actintrack_app.analysis_view import (
    COMPARISON_HEADERS,
    HISTORICAL_SAMPLE_HEADERS,
    HISTORICAL_SUMMARY_HEADERS,
    PRIMARY_SUMMARY_HEADERS,
    SAMPLE_DETAIL_HEADERS,
    AnalysisViewWidget,
)


def _headers(table) -> list[str]:
    return [
        table.horizontalHeaderItem(i).text() for i in range(table.columnCount())
    ]


def _row_index(table, col: int, text: str) -> int:
    for row in range(table.rowCount()):
        item = table.item(row, col)
        if item is not None and item.text() == text:
            return row
    raise AssertionError(f"no row with {text!r} in column {col}")


def _report() -> AnalysisReport:
    with_nucleus = SampleAnalysisRow(
        breed="Control",
        sample_label="Sample 1",
        batch_name="a",
        status="Draft tracking result",
        data_status="motion_index_generated",
        metrics=SampleMetrics(
            general_movement=0.12,
            downward_velocity=0.04,
            motion_index=0.12,
            of_general_movement=0.08,
            of_downward_motion=0.03,
            of_net_y_velocity=0.02,
            of_directionality_ratio=0.5,
            toward_nucleus_velocity=0.05,
            orientation_median_deg=41.25,
            has_valid_result=True,
            of_has_valid_result=True,
            orientation_has_valid_result=True,
        ),
        sample_ids=("S1",),
    )
    without_nucleus = SampleAnalysisRow(
        breed="Control",
        sample_label="Sample 2",
        batch_name="b",
        status="Draft tracking result",
        data_status="motion_index_generated",
        metrics=SampleMetrics(
            general_movement=0.20,
            downward_velocity=0.00,
            motion_index=0.20,
            of_general_movement=0.10,
            of_downward_motion=0.01,
            of_net_y_velocity=-0.01,
            of_directionality_ratio=0.1,
            toward_nucleus_velocity=None,
            orientation_median_deg=None,
            has_valid_result=True,
            of_has_valid_result=True,
            orientation_has_valid_result=False,
        ),
        sample_ids=("S2",),
    )
    mutant = SampleAnalysisRow(
        breed="Mutant",
        sample_label="Sample 1",
        batch_name="c",
        status="Draft tracking result",
        data_status="motion_index_generated",
        metrics=SampleMetrics(
            general_movement=0.30,
            downward_velocity=0.09,
            motion_index=0.30,
            of_general_movement=0.22,
            toward_nucleus_velocity=0.11,
            orientation_median_deg=55.0,
            has_valid_result=True,
            of_has_valid_result=True,
            orientation_has_valid_result=True,
        ),
        sample_ids=("S3",),
    )
    summary_control = BreedSummaryRow(
        breed="Control",
        sample_count=2,
        samples_with_results=2,
        avg_downward_velocity=0.02,
        avg_general_movement=0.16,
        avg_motion_index=0.16,
        std_downward_velocity=0.028284,
        std_general_movement=0.056568,
        avg_of_general_movement=0.09,
        avg_of_downward_motion=0.02,
        avg_of_net_y_velocity=0.005,
        avg_of_directionality_ratio=0.3,
        samples_with_of_results=2,
        avg_toward_nucleus_velocity=0.05,
        avg_orientation_median_deg=41.25,
        samples_with_orientation_results=1,
        samples_with_toward_nucleus_results=1,
    )
    summary_mutant = BreedSummaryRow(
        breed="Mutant",
        sample_count=1,
        samples_with_results=1,
        avg_downward_velocity=0.09,
        avg_general_movement=0.30,
        avg_motion_index=0.30,
        avg_of_general_movement=0.22,
        samples_with_of_results=1,
        avg_toward_nucleus_velocity=0.11,
        avg_orientation_median_deg=55.0,
        samples_with_orientation_results=1,
        samples_with_toward_nucleus_results=1,
    )
    return AnalysisReport(
        breed_summaries=[summary_control, summary_mutant],
        sample_details=[with_nucleus, without_nucleus, mutant],
        breed_comparisons=[
            BreedComparisonRow(
                rank=1,
                breed="Mutant",
                avg_downward_velocity=0.09,
                avg_general_movement=0.30,
                avg_motion_index=0.30,
                avg_toward_nucleus_velocity=0.11,
                avg_orientation_median_deg=55.0,
                avg_of_general_movement=0.22,
                valid_sample_count=1,
            ),
            BreedComparisonRow(
                rank=2,
                breed="Control",
                avg_downward_velocity=0.02,
                avg_general_movement=0.16,
                avg_motion_index=0.16,
                avg_toward_nucleus_velocity=0.05,
                avg_orientation_median_deg=41.25,
                avg_of_general_movement=0.09,
                valid_sample_count=2,
            ),
        ],
    )


class AnalysisViewPrimaryTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.widget = AnalysisViewWidget()
        self.widget.refresh(_report())

    def test_primary_headers_show_current_science_only(self) -> None:
        for table in (
            self.widget.tbl_breed_summary,
            self.widget.tbl_sample_details,
            self.widget.tbl_comparison,
        ):
            headers = " ".join(_headers(table))
            self.assertIn("General Movement", headers)
            self.assertIn("Optical Flow", headers)
            self.assertIn("Toward Nucleus", headers)
            self.assertIn("F-actin Orientation", headers)
            self.assertNotIn("Legacy", headers)
            self.assertNotIn("Motion Index", headers)
            self.assertNotIn("Downward", headers)
            self.assertNotIn("motion angle", headers.lower())

        self.assertEqual(_headers(self.widget.tbl_breed_summary), PRIMARY_SUMMARY_HEADERS)
        self.assertEqual(_headers(self.widget.tbl_sample_details), SAMPLE_DETAIL_HEADERS)
        self.assertEqual(_headers(self.widget.tbl_comparison), COMPARISON_HEADERS)

    def test_group_summary_shows_metric_specific_n(self) -> None:
        row = _row_index(self.widget.tbl_breed_summary, 0, "Control")
        gm = self.widget.tbl_breed_summary.item(row, 2)
        of_item = self.widget.tbl_breed_summary.item(row, 3)
        tn = self.widget.tbl_breed_summary.item(row, 4)
        ori = self.widget.tbl_breed_summary.item(row, 5)
        self.assertIn("0.1600", gm.text())
        self.assertIn("n=2", gm.text())
        self.assertIn("0.0900", of_item.text())
        self.assertIn("n=2", of_item.text())
        self.assertIn("0.0500", tn.text())
        self.assertIn("n=1", tn.text())
        self.assertIn("41.25", ori.text())
        self.assertIn("n=1", ori.text())
        self.assertEqual(self.widget.tbl_breed_summary.item(row, 1).text(), "2")

    def test_missing_nucleus_metrics_are_unavailable_not_zero(self) -> None:
        row = _row_index(self.widget.tbl_sample_details, 1, "Sample 2")
        gm = self.widget.tbl_sample_details.item(row, 3)
        of_item = self.widget.tbl_sample_details.item(row, 4)
        tn = self.widget.tbl_sample_details.item(row, 5)
        ori = self.widget.tbl_sample_details.item(row, 6)
        self.assertIn("0.20", gm.text())
        self.assertIn("0.10", of_item.text())
        self.assertEqual(tn.text(), "—")
        self.assertEqual(ori.text(), "—")
        self.assertNotEqual(tn.text(), "0")
        self.assertNotEqual(tn.text(), "0.0000")
        self.assertIn("nucleus", tn.toolTip().lower())
        self.assertIn("nucleus", ori.toolTip().lower())

    def test_true_zero_downward_is_not_converted_in_historical_table(self) -> None:
        self.widget.chk_show_historical.setChecked(True)
        row = _row_index(self.widget.tbl_historical_samples, 1, "Sample 2")
        downward = self.widget.tbl_historical_samples.item(row, 2)
        self.assertEqual(downward.text(), "0.0000")

    def test_historical_metrics_are_hidden_until_requested(self) -> None:
        self.assertFalse(self.widget.chk_show_historical.isChecked())
        self.assertTrue(self.widget.historical_host.isHidden())
        self.widget.chk_show_historical.setChecked(True)
        self.assertFalse(self.widget.historical_host.isHidden())
        hist_headers = " ".join(
            _headers(self.widget.tbl_historical_summary)
            + _headers(self.widget.tbl_historical_samples)
        )
        self.assertIn("Tracking Downward", hist_headers)
        self.assertNotIn("Motion Index", hist_headers)
        self.assertNotIn("Legacy", hist_headers)
        self.assertEqual(
            _headers(self.widget.tbl_historical_summary), HISTORICAL_SUMMARY_HEADERS
        )
        self.assertEqual(
            _headers(self.widget.tbl_historical_samples), HISTORICAL_SAMPLE_HEADERS
        )
        row = _row_index(self.widget.tbl_historical_summary, 0, "Control")
        self.assertIn("0.0200", self.widget.tbl_historical_summary.item(row, 1).text())

    def test_comparison_ranks_current_metrics_without_legacy_columns(self) -> None:
        row = _row_index(self.widget.tbl_comparison, 1, "Mutant")
        self.assertEqual(self.widget.tbl_comparison.item(row, 0).text(), "1")
        self.assertIn("0.3000", self.widget.tbl_comparison.item(row, 2).text())
        self.assertIn("0.2200", self.widget.tbl_comparison.item(row, 3).text())
        self.assertIn("0.1100", self.widget.tbl_comparison.item(row, 4).text())
        self.assertIn("55.00", self.widget.tbl_comparison.item(row, 5).text())

    def test_orientation_hint_is_structural(self) -> None:
        text = self.widget.lbl_metric_hint.text()
        self.assertIn("0° radial", text)
        self.assertIn("90° tangential", text)
        self.assertIn("not a motion angle", text.lower())
        headers = " ".join(
            _headers(self.widget.tbl_breed_summary)
            + _headers(self.widget.tbl_sample_details)
        )
        self.assertNotIn("motion angle", headers.lower())

    def test_view_does_not_recompute_science(self) -> None:
        src = inspect.getsource(AnalysisViewWidget.refresh)
        self.assertNotIn("run_motion_index", src)
        self.assertNotIn("compute_optical_flow", src)
        self.assertNotIn("compute_structural_orientation", src)
        self.assertIn("breed_summaries", src)


if __name__ == "__main__":
    unittest.main()
