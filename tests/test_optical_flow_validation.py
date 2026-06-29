"""Tests for synthetic optical-flow ground-truth validation."""

from __future__ import annotations

import unittest

from actintrack_app.optical_flow_validation import (
    DEFAULT_SCENARIOS,
    OpticalFlowValidationThresholds,
    run_optical_flow_validation,
    validate_optical_flow_scenario,
)
from actintrack_app.tracker_validation import SyntheticScenario


class OpticalFlowValidationTests(unittest.TestCase):
    def test_clean_integer_scenario_passes(self) -> None:
        scenario = SyntheticScenario("clean_integer_down", 2.0, 1.0)
        result = validate_optical_flow_scenario(scenario, seed=20260629)
        self.assertTrue(result.passed, result.failure_reasons)
        self.assertAlmostEqual(result.expected_speed_px_per_frame, 2.236068, places=3)
        self.assertLess(result.speed_relative_error, 0.15)
        self.assertGreater(result.frame_pair_count, 0)

    def test_upward_motion_negative_vertical_bias_direction(self) -> None:
        scenario = SyntheticScenario(
            "upward",
            -0.40,
            -0.55,
            read_noise_sd=1.0,
            poisson_noise=True,
        )
        result = validate_optical_flow_scenario(scenario, seed=20260630)
        self.assertLess(result.measured_signed_vertical_px_per_frame, 0.0)
        self.assertAlmostEqual(
            result.expected_signed_vertical_px_per_frame,
            -0.55,
            places=2,
        )

    def test_failed_when_thresholds_tightened(self) -> None:
        scenario = SyntheticScenario("clean_integer_down", 2.0, 1.0)
        thresholds = OpticalFlowValidationThresholds(max_speed_relative_error=0.001)
        result = validate_optical_flow_scenario(
            scenario,
            thresholds=thresholds,
            seed=20260629,
        )
        self.assertFalse(result.passed)
        self.assertIn("speed_relative_error", result.failure_reasons)

    def test_run_validation_all_default_scenarios_pass(self) -> None:
        report = run_optical_flow_validation(output_dir=None, seed=20260629)
        self.assertEqual(report["scenario_count"], len(DEFAULT_SCENARIOS))
        self.assertTrue(report["passed"], report.get("results"))
        self.assertEqual(report["passed_scenario_count"], len(DEFAULT_SCENARIOS))

    def test_run_validation_writes_reports(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "of_val"
            report = run_optical_flow_validation(output_dir=output_dir, seed=20260629)
            self.assertTrue((output_dir / "optical_flow_validation_report.json").is_file())
            self.assertTrue((output_dir / "optical_flow_validation_scenarios.csv").is_file())
            self.assertIn("report_json", report)


if __name__ == "__main__":
    unittest.main()
