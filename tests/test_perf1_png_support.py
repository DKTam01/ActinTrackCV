"""PERF1 PNG IMAGE support through the MEDIA1 capability path."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from actintrack_app.batch_manager import list_batches
from actintrack_app.cell_detection import suggest_conservative_cell_region
from actintrack_app.condition_group_manager import create_condition_group
from actintrack_app.import_classifier import ImportKind, classify_paths
from actintrack_app.media_capabilities import (
    MetricId,
    SampleMediaType,
    capabilities_for,
    classify_media_path,
)
from actintrack_app.metadata import load_samples_csv
from actintrack_app.project_manager import create_project_structure
from actintrack_app.sample_service import create_samples_from_data_files
from actintrack_app.structural_orientation import compute_structural_orientation
from actintrack_app.utils import DATA_FILES_CSV, METADATA_DIR
from actintrack_app.video_processing import load_image, load_media_frame
from actintrack_app.workflow_state import format_sample_results_summary


def _write_png(path: Path, *, mode: str = "bgr8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "bgr8":
        frame = np.zeros((32, 28, 3), dtype=np.uint8)
        frame[8:24, 6:22] = (40, 200, 40)
        cv2.imwrite(str(path), frame)
        return
    if mode == "gray8":
        frame = np.zeros((32, 28), dtype=np.uint8)
        frame[8:24, 6:22] = 200
        cv2.imwrite(str(path), frame)
        return
    if mode == "gray16":
        frame = np.zeros((32, 28), dtype=np.uint16)
        frame[8:24, 6:22] = 40000
        cv2.imwrite(str(path), frame)
        return
    if mode == "rgba":
        frame = np.zeros((32, 28, 4), dtype=np.uint8)
        frame[8:24, 6:22, :3] = (40, 200, 40)
        frame[:, :, 3] = 0
        frame[8:24, 6:22, 3] = 255
        # OpenCV imwrite BGRA
        cv2.imwrite(str(path), frame)
        return
    raise ValueError(mode)


class PngClassificationTests(unittest.TestCase):
    def test_png_case_insensitive_classification(self) -> None:
        self.assertEqual(classify_media_path("a.png"), SampleMediaType.IMAGE)
        self.assertEqual(classify_media_path("a.PNG"), SampleMediaType.IMAGE)
        self.assertEqual(classify_media_path(Path("x.PnG")), SampleMediaType.IMAGE)

    def test_png_capability_matrix(self) -> None:
        caps = capabilities_for(SampleMediaType.IMAGE)
        self.assertFalse(caps.supports(MetricId.GENERAL_MOVEMENT))
        self.assertFalse(caps.supports(MetricId.OPTICAL_FLOW))
        self.assertFalse(caps.supports(MetricId.TOWARD_NUCLEUS))
        self.assertTrue(caps.supports(MetricId.ORIENTATION))
        self.assertFalse(caps.requires_video_timing)
        self.assertTrue(caps.orientation_requires_nucleus)


class PngLoadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_load_grayscale_rgb_rgba_and_16bit(self) -> None:
        gray = self.root / "g.png"
        rgb = self.root / "c.png"
        rgba = self.root / "a.png"
        g16 = self.root / "u16.png"
        _write_png(gray, mode="gray8")
        _write_png(rgb, mode="bgr8")
        _write_png(rgba, mode="rgba")
        _write_png(g16, mode="gray16")

        for path in (gray, rgb, rgba, g16):
            frame = load_image(path)
            self.assertEqual(frame.dtype, np.uint8)
            self.assertEqual(frame.ndim, 3)
            self.assertEqual(frame.shape[2], 3)
            self.assertGreater(int(frame.max()), 0)

        # 16-bit must not silently truncate to low byte (40000 % 256 == 64).
        frame16 = load_image(g16)
        self.assertGreater(int(frame16.max()), 200)

        # RGBA alpha dropped: transparent background stays near zero, not opaque fill.
        frame_a = load_image(rgba)
        self.assertLess(int(frame_a[0, 0].max()), 30)
        self.assertGreater(int(frame_a[12, 12].max()), 30)

    def test_preview_loader_reports_single_frame(self) -> None:
        path = self.root / "p.PNG"
        _write_png(path)
        frame, idx, total = load_media_frame(path, 0)
        self.assertEqual(idx, 0)
        self.assertEqual(total, 1)
        self.assertEqual(frame.shape[2], 3)


class PngImportWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        create_project_structure(self.root)
        self.breed = create_condition_group(self.root, "WT").id
        self.png = self.root / "cell.png"
        self.png_upper = self.root / "cell2.PNG"
        _write_png(self.png)
        _write_png(self.png_upper)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_classify_and_import_png(self) -> None:
        kind, files, msg = classify_paths([self.png, self.png_upper])
        self.assertEqual(kind, ImportKind.IMAGE)
        self.assertEqual(msg, "")
        self.assertEqual(len(files), 2)
        results = create_samples_from_data_files(
            self.root, self.breed, [self.png, self.png_upper]
        )
        self.assertTrue(all(r.succeeded for r in results))
        df = load_samples_csv(self.root / METADATA_DIR / DATA_FILES_CSV)
        self.assertEqual(set(df["media_type"].astype(str)), {"image"})
        self.assertEqual(len(list_batches(self.root, self.breed)), 2)

    def test_cell_region_and_orientation_dispatch(self) -> None:
        frame = load_image(self.png)
        cell = suggest_conservative_cell_region(frame, sensitivity=0.5)
        self.assertIsNotNone(cell)
        result = compute_structural_orientation(
            frame,
            nucleus_xy_px=(14.0, 16.0),
            sample_id="png1",
        )
        self.assertTrue(result.has_valid_result)

    def test_sample_results_omit_timing(self) -> None:
        text = format_sample_results_summary(
            sparse_px=None,
            sparse_um_s=None,
            of_px=None,
            of_um_s=None,
            toward_nucleus_um_s=None,
            orientation_deg=12.5,
            tracks_used=None,
            tracks_requested=None,
            timing_label="60 s between frames",
            timing_confirmed=True,
            has_nucleus=True,
            media_type=SampleMediaType.IMAGE,
        )
        self.assertIn("F-actin Orientation", text)
        self.assertIn("12.5°", text)
        self.assertNotIn("Acquisition Interval", text)
        self.assertNotIn("General Movement", text)


if __name__ == "__main__":
    unittest.main()
