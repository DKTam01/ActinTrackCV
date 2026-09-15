"""Tests for MEDIA1 sample media type and metric capabilities."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from actintrack_app.import_classifier import ImportKind, classify_paths
from actintrack_app.media_capabilities import (
    IMAGE_CAPABILITIES,
    MetricId,
    PRODUCT_IMAGE_EXTENSIONS,
    PRODUCT_VIDEO_EXTENSIONS,
    SampleMediaType,
    VIDEO_CAPABILITIES,
    capabilities_for,
    capabilities_for_sample_row,
    classify_media_path,
    is_product_media_path,
    media_type_from_sample_row,
)


class MediaCapabilitiesTests(unittest.TestCase):
    def test_classify_video_extensions(self) -> None:
        for ext in PRODUCT_VIDEO_EXTENSIONS:
            self.assertEqual(classify_media_path(Path(f"a{ext}")), SampleMediaType.VIDEO)
            self.assertEqual(
                classify_media_path(Path(f"A{ext.upper()}")),
                SampleMediaType.VIDEO,
            )

    def test_classify_image_extensions(self) -> None:
        for ext in PRODUCT_IMAGE_EXTENSIONS:
            self.assertEqual(classify_media_path(Path(f"a{ext}")), SampleMediaType.IMAGE)
            self.assertEqual(
                classify_media_path(Path(f"cell{ext.upper()}")),
                SampleMediaType.IMAGE,
            )

    def test_classify_rejects_unsupported(self) -> None:
        for name in ("notes.txt", "stack.png", "raw.oir", "data.oib"):
            self.assertIsNone(classify_media_path(Path(name)))
            self.assertFalse(is_product_media_path(Path(name)))

    def test_video_capability_matrix(self) -> None:
        caps = capabilities_for(SampleMediaType.VIDEO)
        self.assertTrue(caps.supports_general_movement)
        self.assertTrue(caps.supports_optical_flow)
        self.assertTrue(caps.supports_toward_nucleus)
        self.assertFalse(caps.supports_orientation)
        self.assertTrue(caps.requires_video_timing)
        self.assertFalse(caps.requires_nucleus_for_run)
        self.assertEqual(caps.metric_analysis_modes, ("template", "optical_flow"))
        self.assertTrue(caps.supports(MetricId.GENERAL_MOVEMENT))
        self.assertFalse(caps.supports(MetricId.ORIENTATION))

    def test_image_capability_matrix(self) -> None:
        caps = capabilities_for(SampleMediaType.IMAGE)
        self.assertFalse(caps.supports_general_movement)
        self.assertFalse(caps.supports_optical_flow)
        self.assertFalse(caps.supports_toward_nucleus)
        self.assertTrue(caps.supports_orientation)
        self.assertFalse(caps.requires_video_timing)
        self.assertTrue(caps.requires_nucleus_for_run)
        self.assertEqual(caps.metric_analysis_modes, ("orientation",))
        self.assertTrue(caps.supports(MetricId.ORIENTATION))
        self.assertFalse(caps.supports(MetricId.OPTICAL_FLOW))

    def test_capability_singletons(self) -> None:
        self.assertIs(capabilities_for(SampleMediaType.VIDEO), VIDEO_CAPABILITIES)
        self.assertIs(capabilities_for(SampleMediaType.IMAGE), IMAGE_CAPABILITIES)

    def test_media_type_from_persisted_field(self) -> None:
        self.assertEqual(
            media_type_from_sample_row({"media_type": "image"}),
            SampleMediaType.IMAGE,
        )
        self.assertEqual(
            media_type_from_sample_row({"media_type": "video"}),
            SampleMediaType.VIDEO,
        )

    def test_media_type_fallback_pre_media1_row(self) -> None:
        self.assertEqual(
            media_type_from_sample_row(
                {"file_type": "tiff", "is_video": "false", "stored_path": "raw/g/s/x.tif"}
            ),
            SampleMediaType.IMAGE,
        )
        self.assertEqual(
            media_type_from_sample_row(
                {"file_type": "video", "is_video": "true", "stored_path": "raw/g/s/x.mp4"}
            ),
            SampleMediaType.VIDEO,
        )
        self.assertEqual(
            media_type_from_sample_row(
                {},
                fallback_path=Path("cell.JPEG"),
            ),
            SampleMediaType.IMAGE,
        )

    def test_capabilities_for_sample_row(self) -> None:
        caps = capabilities_for_sample_row({"media_type": "image"})
        self.assertTrue(caps.is_image)
        self.assertTrue(caps.supports_orientation)


class ImportClassifierMediaTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _touch(self, name: str) -> Path:
        path = self.root / name
        path.write_bytes(b"x")
        return path

    def test_classify_single_video(self) -> None:
        path = self._touch("a.mp4")
        kind, files, msg = classify_paths([path])
        self.assertEqual(kind, ImportKind.VIDEO)
        self.assertEqual(files, [path.resolve()])
        self.assertEqual(msg, "")

    def test_classify_single_image_jpg(self) -> None:
        path = self._touch("cell.jpg")
        kind, files, msg = classify_paths([path])
        self.assertEqual(kind, ImportKind.IMAGE)
        self.assertEqual(msg, "")
        self.assertEqual(files, [path.resolve()])

    def test_classify_tiff_is_image_not_wip(self) -> None:
        path = self._touch("frame.TIFF")
        kind, files, msg = classify_paths([path])
        self.assertEqual(kind, ImportKind.IMAGE)
        self.assertEqual(msg, "")

    def test_classify_multi_image(self) -> None:
        paths = [self._touch("a.jpg"), self._touch("b.jpeg"), self._touch("c.tif")]
        kind, files, msg = classify_paths(paths)
        self.assertEqual(kind, ImportKind.IMAGE)
        self.assertEqual(msg, "")
        self.assertEqual(len(files), 3)

    def test_classify_mixed_video_and_image_allowed(self) -> None:
        paths = [self._touch("a.mp4"), self._touch("b.jpg")]
        kind, files, msg = classify_paths(paths)
        self.assertEqual(kind, ImportKind.MIXED)
        self.assertEqual(msg, "")
        self.assertEqual(len(files), 2)

    def test_classify_rejects_txt(self) -> None:
        path = self._touch("bad.txt")
        kind, files, msg = classify_paths([path])
        self.assertEqual(kind, ImportKind.MIXED)
        self.assertEqual(files, [])
        self.assertIn("Unsupported", msg)

    def test_classify_rejects_png(self) -> None:
        path = self._touch("still.png")
        kind, files, msg = classify_paths([path])
        self.assertEqual(kind, ImportKind.MIXED)
        self.assertEqual(files, [])


if __name__ == "__main__":
    unittest.main()
