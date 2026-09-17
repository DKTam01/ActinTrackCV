"""CAL1 per-sample scientific calibration model, fallbacks, and persistence."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from actintrack_app.annotation_schema import build_sample_annotation
from actintrack_app.metadata import get_sample_annotation, save_sample_crop_annotation
from actintrack_app.orientation import OrientationState, RectROI
from actintrack_app.project_manager import create_project_structure
from actintrack_app.scientific_calibration import (
    CALIBRATION_SOURCE_PROTOCOL_DEFAULT,
    CALIBRATION_SOURCE_RESEARCHER_ENTERED,
    InvalidScientificCalibration,
    LEGACY_ACQUISITION_INTERVAL_S,
    LEGACY_MICRONS_PER_PIXEL,
    SampleScientificCalibration,
    calibration_from_annotation,
    calibration_from_result_payload,
    format_calibration_number,
    legacy_default_calibration,
    merge_calibration_into_annotation,
    parse_calibration_number,
    validate_positive_finite,
)
from actintrack_app.timing_provenance import (
    TIMING_SOURCE_PROTOCOL_STANDARD,
    TIMING_SOURCE_RESEARCHER_ENTERED,
    TIMING_SOURCE_VIDEO_HEADER,
    TimingMetadata,
)
from actintrack_app.utils import CROP_METADATA_JSON, METADATA_DIR


class FallbackTests(unittest.TestCase):
    def test_missing_timing_falls_back_to_sixty_seconds(self) -> None:
        cal = calibration_from_annotation({})
        self.assertAlmostEqual(cal.acquisition_interval_s, 60.0)
        self.assertEqual(cal.acquisition_interval_source, CALIBRATION_SOURCE_PROTOCOL_DEFAULT)
        self.assertEqual(LEGACY_ACQUISITION_INTERVAL_S, 60.0)

    def test_missing_spatial_falls_back_to_legacy_microns(self) -> None:
        cal = calibration_from_annotation(None)
        self.assertAlmostEqual(cal.microns_per_pixel, 0.265)
        self.assertEqual(cal.spatial_calibration_source, CALIBRATION_SOURCE_PROTOCOL_DEFAULT)
        self.assertEqual(LEGACY_MICRONS_PER_PIXEL, 0.265)

    def test_pre_cal1_timing_block_is_not_promoted(self) -> None:
        # PERF1 ignored custom/header intervals. CAL1 must keep 60 s until explicit.
        cal = calibration_from_annotation(
            {
                "timing": {
                    "analysis_seconds_per_frame": 30.0,
                    "timing_source": "lab_default",
                    "timing_confirmed": True,
                }
            }
        )
        self.assertAlmostEqual(cal.acquisition_interval_s, 60.0)
        self.assertAlmostEqual(cal.microns_per_pixel, 0.265)


class ValidationTests(unittest.TestCase):
    def test_rejects_zero_negative_and_nonfinite(self) -> None:
        for value in (0, -1, float("nan"), float("inf"), "", None, "abc"):
            with self.assertRaises(InvalidScientificCalibration):
                parse_calibration_number(value)

    def test_accepts_researcher_spatial_values(self) -> None:
        self.assertAlmostEqual(parse_calibration_number("0.265"), 0.265)
        self.assertAlmostEqual(parse_calibration_number("0.157836335086282"), 0.157836335086282)
        self.assertAlmostEqual(parse_calibration_number("0.138"), 0.138)
        self.assertAlmostEqual(validate_positive_finite(30), 30.0)
        self.assertAlmostEqual(validate_positive_finite(60), 60.0)

    def test_format_does_not_invent_noise(self) -> None:
        self.assertEqual(format_calibration_number(60.0), "60")
        self.assertEqual(format_calibration_number(30.0), "30")
        self.assertEqual(format_calibration_number(0.265), "0.265")


class PersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        create_project_structure(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_new_sample_persists_and_reloads_exactly(self) -> None:
        cal = SampleScientificCalibration(
            acquisition_interval_s=30.0,
            microns_per_pixel=0.157836335086282,
            acquisition_interval_source=CALIBRATION_SOURCE_RESEARCHER_ENTERED,
            spatial_calibration_source=CALIBRATION_SOURCE_RESEARCHER_ENTERED,
        )
        ann = build_sample_annotation(
            sample_id="S1",
            group="g",
            original_file="a.avi",
            stored_raw_path="raw/a.avi",
            reference_frame_index=0,
            orientation=OrientationState(),
            roi=RectROI(1, 2, 10, 12),
            original_dimensions={"width": 20, "height": 30},
            oriented_dimensions={"width": 20, "height": 30},
            scientific_calibration=cal,
        )
        path = self.root / METADATA_DIR / CROP_METADATA_JSON
        save_sample_crop_annotation(path, "S1", ann)
        loaded_ann = get_sample_annotation(self.root, "S1")
        loaded = calibration_from_annotation(loaded_ann)
        self.assertAlmostEqual(loaded.acquisition_interval_s, 30.0)
        self.assertEqual(loaded.microns_per_pixel, 0.157836335086282)
        self.assertEqual(
            loaded.acquisition_interval_source, CALIBRATION_SOURCE_RESEARCHER_ENTERED
        )
        self.assertEqual(
            loaded.spatial_calibration_source, CALIBRATION_SOURCE_RESEARCHER_ENTERED
        )

    def test_merge_does_not_rewrite_unrelated_geometry(self) -> None:
        base = {"sample_id": "S1", "nucleus_reference": {"x": 1, "y": 2}}
        cal = SampleScientificCalibration(
            acquisition_interval_s=30.0,
            microns_per_pixel=0.138,
            acquisition_interval_source=CALIBRATION_SOURCE_RESEARCHER_ENTERED,
            spatial_calibration_source=CALIBRATION_SOURCE_RESEARCHER_ENTERED,
        )
        merged = merge_calibration_into_annotation(base, cal)
        self.assertEqual(merged["nucleus_reference"], {"x": 1, "y": 2})
        self.assertIn("scientific_calibration", merged)
        self.assertAlmostEqual(merged["timing"]["analysis_seconds_per_frame"], 30.0)


class TimingBridgeTests(unittest.TestCase):
    def test_default_calibration_is_protocol_standard_ready(self) -> None:
        timing = legacy_default_calibration().to_timing_metadata(observed_video_fps=3.0)
        self.assertEqual(timing.timing_source, TIMING_SOURCE_PROTOCOL_STANDARD)
        self.assertAlmostEqual(timing.analysis_seconds_per_frame, 60.0)
        self.assertTrue(timing.is_calibrated_analysis_ready)
        self.assertAlmostEqual(timing.observed_video_fps or 0.0, 3.0)

    def test_researcher_entered_thirty_seconds_is_ready(self) -> None:
        cal = SampleScientificCalibration(
            acquisition_interval_s=30.0,
            microns_per_pixel=0.265,
            acquisition_interval_source=CALIBRATION_SOURCE_RESEARCHER_ENTERED,
        )
        timing = cal.to_timing_metadata(observed_video_fps=1.0)
        self.assertEqual(timing.timing_source, TIMING_SOURCE_RESEARCHER_ENTERED)
        self.assertAlmostEqual(timing.analysis_seconds_per_frame, 30.0)
        self.assertTrue(timing.is_calibrated_analysis_ready)

    def test_container_fps_is_not_scientific_dt(self) -> None:
        header = TimingMetadata.from_video_header(3.0)
        self.assertIsNotNone(header)
        assert header is not None
        self.assertEqual(header.timing_source, TIMING_SOURCE_VIDEO_HEADER)
        self.assertFalse(header.is_calibrated_analysis_ready)

    def test_result_payload_snapshot_survives_sample_edit(self) -> None:
        snapshot = SampleScientificCalibration(
            acquisition_interval_s=60.0,
            microns_per_pixel=0.265,
        ).to_dict()
        payload = {
            "scientific_calibration": snapshot,
            "parameters": {"seconds_per_frame": 60.0, "microns_per_pixel": 0.265},
            "general_movement_index_um_per_s": 0.0220833,
        }
        current = SampleScientificCalibration(
            acquisition_interval_s=30.0,
            microns_per_pixel=0.157836,
            acquisition_interval_source=CALIBRATION_SOURCE_RESEARCHER_ENTERED,
            spatial_calibration_source=CALIBRATION_SOURCE_RESEARCHER_ENTERED,
        )
        loaded = calibration_from_result_payload(payload)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertAlmostEqual(loaded.acquisition_interval_s, 60.0)
        self.assertAlmostEqual(loaded.microns_per_pixel, 0.265)
        self.assertNotAlmostEqual(loaded.acquisition_interval_s, current.acquisition_interval_s)
        self.assertNotAlmostEqual(loaded.microns_per_pixel, current.microns_per_pixel)


if __name__ == "__main__":
    unittest.main()
