"""Tests for the V2 scientific validation harness."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from actintrack_app.scientific_validation import (
    ManualMeasurement,
    compare_to_manual,
    evaluate_condition_sanity,
    load_manual_measurements,
)


class ScientificValidationHelperTests(unittest.TestCase):
    def test_condition_sanity_flags_reversal_without_hard_fail(self) -> None:
        ordering = {
            "observed_sparse_wt_gt_mutant": False,
            "observed_of_wt_gt_mutant": True,
        }
        sanity = evaluate_condition_sanity(ordering)
        self.assertFalse(sanity["hard_scientific_failure"])
        self.assertIn(
            "sparse_tracking_raw_px_frame_reversed_or_erased_WT_gt_Mutant515",
            sanity["investigation_alerts"],
        )
        self.assertEqual(sanity["role"], "external_sanity_check_not_tuning_target")

    def test_manual_comparison_metrics(self) -> None:
        manual = ManualMeasurement(
            sample_id="WT550_0001",
            method="sparse_mean_px_per_frame",
            value=5.0,
            units="px/frame",
        )
        compared = compare_to_manual(4.0, manual)
        self.assertEqual(compared["signed_error"], -1.0)
        self.assertEqual(compared["absolute_error"], 1.0)
        self.assertAlmostEqual(compared["relative_error"], 0.2)

        missing = compare_to_manual(None, manual)
        self.assertEqual(missing["status"], "missing_prediction")

    def test_load_manual_measurements_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manual.json"
            path.write_text(
                json.dumps(
                    {
                        "measurements": [
                            {
                                "sample_id": "WT550_0001",
                                "method": "sparse_general_movement",
                                "value": 1.2,
                                "units": "um/s",
                                "seconds_per_frame": 0.2,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            rows = load_manual_measurements(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].sample_id, "WT550_0001")
            self.assertEqual(rows[0].seconds_per_frame, 0.2)


if __name__ == "__main__":
    unittest.main()
