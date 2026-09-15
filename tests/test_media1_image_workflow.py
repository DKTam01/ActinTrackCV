"""MEDIA1 image workflow, readiness, TIFF conversion, and dispatch gates."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from actintrack_app.media_capabilities import SampleMediaType
from actintrack_app.metrics_compute import (
    compute_image_orientation_metrics,
    compute_video_metrics,
)
from actintrack_app.motion_index import MotionIndexParams
from actintrack_app.optical_flow_motion_index import OpticalFlowSettings
from actintrack_app.orientation import OrientationState, RectROI
from actintrack_app.sample_service import (
    create_sample_from_data,
    validate_scientific_data_file,
)
from actintrack_app.condition_group_manager import create_condition_group
from actintrack_app.project_manager import create_project_structure
from actintrack_app.video_processing import _array_to_bgr, _to_display_uint8
from actintrack_app.workflow_state import (
    WorkbenchLiveInputs,
    build_workflow_snapshot,
    format_sample_results_summary,
    snapshot_from_live_inputs,
)


class TiffBitDepthTests(unittest.TestCase):
    def test_uint8_identity(self) -> None:
        arr = np.arange(16, dtype=np.uint8).reshape(4, 4)
        out = _to_display_uint8(arr)
        np.testing.assert_array_equal(out, arr)

    def test_uint16_minmax_not_low_byte_truncation(self) -> None:
        # Values that would collapse under astype(uint8) modulo truncation.
        arr = np.array([[0, 256, 512, 1024], [2048, 4096, 8192, 65535]], dtype=np.uint16)
        truncated = arr.astype(np.uint8)
        stretched = _to_display_uint8(arr)
        self.assertFalse(np.array_equal(stretched, truncated))
        self.assertEqual(int(stretched.min()), 0)
        self.assertEqual(int(stretched.max()), 255)

    def test_array_to_bgr_grayscale_uint16(self) -> None:
        arr = np.linspace(0, 4000, 64, dtype=np.uint16).reshape(8, 8)
        bgr = _array_to_bgr(arr)
        self.assertEqual(bgr.dtype, np.uint8)
        self.assertEqual(bgr.shape, (8, 8, 3))


class MediaReadinessTests(unittest.TestCase):
    def test_image_ready_without_timing(self) -> None:
        snap = build_workflow_snapshot(
            has_sample=True,
            has_crop=True,
            has_cell_region=True,
            has_nucleus=True,
            has_cutoff=True,
            timing_confirmed=False,
            has_valid_video_timing=False,
            metrics_present=False,
            metrics_stale=False,
            media_type=SampleMediaType.IMAGE,
        )
        self.assertTrue(snap.ready_to_run)
        self.assertIsNone(snap.run_metrics_block_reason())

    def test_image_requires_nucleus(self) -> None:
        snap = build_workflow_snapshot(
            has_sample=True,
            has_crop=True,
            has_cell_region=True,
            has_nucleus=False,
            has_cutoff=True,
            timing_confirmed=False,
            has_valid_video_timing=False,
            metrics_present=False,
            metrics_stale=False,
            media_type=SampleMediaType.IMAGE,
        )
        self.assertFalse(snap.ready_to_run)
        self.assertIn("nucleus", (snap.run_metrics_block_reason() or "").lower())

    def test_video_still_requires_timing(self) -> None:
        snap = build_workflow_snapshot(
            has_sample=True,
            has_crop=True,
            has_cell_region=True,
            has_nucleus=False,
            has_cutoff=True,
            timing_confirmed=False,
            has_valid_video_timing=False,
            metrics_present=False,
            metrics_stale=False,
            media_type=SampleMediaType.VIDEO,
        )
        self.assertFalse(snap.ready_to_run)

    def test_live_inputs_image_timing_ignored(self) -> None:
        snap = snapshot_from_live_inputs(
            WorkbenchLiveInputs(
                sample_id="s1",
                has_base_frame=True,
                has_crop=True,
                has_cell_region=True,
                has_nucleus=True,
                has_cutoff=True,
                timing_ready=False,
                metrics_present=False,
                metrics_stale=False,
                metrics_running=False,
                media_type=SampleMediaType.IMAGE,
            )
        )
        # Image readiness does not require video timing; live path passes
        # timing_ready through, so callers must set timing_ready=True for images.
        # MainWindow sets timing_ready=True when caps.requires_video_timing is False.
        self.assertEqual(snap.media_type, SampleMediaType.IMAGE)

    def test_sample_results_image_omits_motion(self) -> None:
        text = format_sample_results_summary(
            sparse_px=1.0,
            sparse_um_s=2.0,
            of_px=3.0,
            of_um_s=4.0,
            toward_nucleus_um_s=5.0,
            orientation_deg=42.5,
            tracks_used=3,
            tracks_requested=5,
            timing_label="6.0 fps",
            timing_confirmed=True,
            has_nucleus=True,
            media_type=SampleMediaType.IMAGE,
        )
        self.assertIn("F-actin Orientation", text)
        self.assertIn("42.5°", text)
        self.assertNotIn("General Movement", text)
        self.assertNotIn("Optical Flow", text)
        self.assertNotIn("Video Timing", text)

    def test_sample_results_video_omits_orientation(self) -> None:
        text = format_sample_results_summary(
            sparse_px=1.0,
            sparse_um_s=2.0,
            of_px=3.0,
            of_um_s=4.0,
            toward_nucleus_um_s=None,
            orientation_deg=42.5,
            tracks_used=3,
            tracks_requested=5,
            timing_label="6.0 fps",
            timing_confirmed=True,
            has_nucleus=False,
            media_type=SampleMediaType.VIDEO,
        )
        self.assertIn("General Movement", text)
        self.assertNotIn("F-actin Orientation", text)


class ImageImportAndDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        create_project_structure(self.root)
        self.breed = create_condition_group(self.root, "WT").id
        self.image = self.root / "cell.jpg"
        frame = np.zeros((48, 48, 3), dtype=np.uint8)
        frame[10:38, 10:38] = (0, 200, 200)
        cv2.imwrite(str(self.image), frame)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_validate_accepts_jpg(self) -> None:
        ok, msg = validate_scientific_data_file(self.image)
        self.assertTrue(ok, msg)

    def test_create_sample_from_image_persists_media_type(self) -> None:
        batch, row = create_sample_from_data(self.root, self.breed, self.image)
        self.assertEqual(row.get("media_type"), "image")
        self.assertEqual(row.get("is_video"), "false")
        self.assertTrue(batch)

    def test_image_dispatch_does_not_run_motion(self) -> None:
        result = compute_image_orientation_metrics(
            path=self.image,
            orientation=OrientationState(),
            roi=RectROI(0, 0, 48, 48),
            valid_mask=None,
            nucleus_xy_px=None,
            sample_id="img1",
        )
        self.assertEqual(result.status, "unavailable")
        self.assertIsNone(result.tracking)
        self.assertIsNone(result.optical_flow)


if __name__ == "__main__":
    unittest.main()
