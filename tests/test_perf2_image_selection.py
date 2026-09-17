"""PERF2 IMAGE selection reuse: persisted CellRegion, decode cache, invalidation."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
from PyQt6.QtWidgets import QApplication

from actintrack_app.condition_group_manager import create_condition_group
from actintrack_app.gui import MainWindow
from actintrack_app.metadata import get_sample_annotation
from actintrack_app.orientation import OrientationState, RectROI
from actintrack_app.project_manager import create_project_structure
from actintrack_app.sample_preview_cache import (
    CachedSampleMedia,
    SampleMediaCache,
    source_file_identity,
)
from actintrack_app.sample_service import create_samples_from_data_files
from actintrack_app.scientific_annotations import CellRegion
from actintrack_app.video_processing import load_image


def _write_png(path: Path, h: int = 48, w: int = 64) -> None:
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[8:40, 10:54] = (30, 200, 40)
    cv2.imwrite(str(path), frame)


class SampleMediaCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.png = self.root / "a.png"
        _write_png(self.png)
        frame = load_image(self.png)
        ident = source_file_identity(self.png)
        assert ident is not None
        self.entry = CachedSampleMedia(
            sample_id="S1",
            path_key=ident[0],
            mtime_ns=ident[1],
            size=ident[2],
            frame=frame,
            frame_index=0,
            total_frames=1,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_hit_then_invalidate_on_source_change(self) -> None:
        cache = SampleMediaCache(max_entries=2)
        cache.put(self.entry)
        hit = cache.get("S1", self.png, frame_index=0)
        self.assertIs(hit, self.entry)
        self.png.write_bytes(self.png.read_bytes() + b"\x00")
        self.assertIsNone(cache.get("S1", self.png, frame_index=0))

    def test_lru_bound_is_two_and_no_cross_sample_contamination(self) -> None:
        cache = SampleMediaCache(max_entries=2)
        b = self.root / "b.png"
        c = self.root / "c.png"
        _write_png(b)
        _write_png(c)
        cache.put(self.entry)
        ident_b = source_file_identity(b)
        ident_c = source_file_identity(c)
        assert ident_b is not None and ident_c is not None
        cache.put(
            CachedSampleMedia(
                sample_id="S2",
                path_key=ident_b[0],
                mtime_ns=ident_b[1],
                size=ident_b[2],
                frame=load_image(b),
                frame_index=0,
                total_frames=1,
            )
        )
        cache.put(
            CachedSampleMedia(
                sample_id="S3",
                path_key=ident_c[0],
                mtime_ns=ident_c[1],
                size=ident_c[2],
                frame=load_image(c),
                frame_index=0,
                total_frames=1,
            )
        )
        self.assertEqual(len(cache), 2)
        self.assertIsNone(cache.peek("S1"))
        self.assertIsNotNone(cache.peek("S2"))
        self.assertIsNotNone(cache.peek("S3"))
        self.assertIsNone(cache.get("S2", c, frame_index=0))


class PersistedCellRegionSelectionTests(unittest.TestCase):
    def test_apply_annotation_does_not_call_segmentation(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._orientation = OrientationState()
        window._base_frame = np.zeros((20, 24, 3), dtype=np.uint8)
        window._cell_region = None
        window._nucleus_reference = None
        window._cutoff_boundary = None
        window._project_root = None
        window._current_sample = None
        window.canvas = MagicMock()
        window.canvas.rect_roi.return_value = RectROI(1, 1, 8, 8)
        window.canvas.begin_display_update = MagicMock()
        window.canvas.end_display_update = MagicMock()
        window._refresh_display = MagicMock()
        window._oriented_frame = MagicMock(return_value=window._base_frame)
        window._set_computational_crop = MagicMock()
        window._update_orientation_label = MagicMock()
        window._refresh_roi_save_status_from_context = MagicMock()
        window._refresh_roi_preview_panel = MagicMock()
        window._sync_cell_boundary_slider = MagicMock()
        window._sync_scientific_overlay = MagicMock()
        window._update_metric_freshness_label = MagicMock()
        window._ensure_timing_for_current_sample = MagicMock()
        window._mark_nucleus_cutoff_alignment_review = MagicMock()
        window.lbl_timing_detected = MagicMock()
        saved = CellRegion.from_rect(RectROI(2, 2, 10, 8), source="manual")
        ann = {
            "cell_region": saved.to_dict(),
            "rotation_angle_degrees": 0,
            "mirror_y_axis": False,
            "flipped_180": False,
            "reference_frame_index": 0,
            "notes": "",
            "annotation_source": "manual",
        }
        with patch(
            "actintrack_app.gui.suggest_conservative_cell_region",
            side_effect=AssertionError("CellRegion must not regenerate"),
        ):
            MainWindow._apply_annotation_from_dict(window, ann, render_canvas=True)
        self.assertEqual(window._cell_region.geometry_key(), saved.geometry_key())
        window._sync_scientific_overlay.assert_called_once()
        window._ensure_timing_for_current_sample.assert_called_once_with(
            persist_observed=False
        )

    def test_same_sample_reselection_skips_reload(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._metric_analysis_view_active = False
        window._current_sample_id = "S1"
        window._base_frame = np.zeros((8, 8, 3), dtype=np.uint8)
        window._preview_mode = "full"
        window._set_active_sample = MagicMock()
        window.reset_preview_state = MagicMock()
        window._load_full_roi_preview_for_current_sample = MagicMock()
        item = MagicMock()
        window._tree_item_meta = MagicMock(
            return_value={"item_type": "sample", "sample_id": "S1", "group": "g"}
        )
        MainWindow._load_sample_from_tree_item(window, item)
        window.reset_preview_state.assert_not_called()
        window._load_full_roi_preview_for_current_sample.assert_not_called()

    def test_oriented_frame_cache_invalidates_on_orientation_change(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._base_frame = np.zeros((8, 10, 3), dtype=np.uint8)
        window._orientation = OrientationState()
        window._oriented_frame_cache = None
        window._oriented_frame_cache_key = None
        first = MainWindow._oriented_frame(window)
        second = MainWindow._oriented_frame(window)
        self.assertIs(first, second)
        window._orientation = OrientationState(rotation_angle_degrees=90.0)
        rotated = MainWindow._oriented_frame(window)
        self.assertIsNot(first, rotated)
        self.assertEqual(rotated.shape[0], 10)
        self.assertEqual(rotated.shape[1], 8)


class ImageSelectionReuseIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_a_b_a_reuses_decode_and_does_not_regenerate_cell(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        create_project_structure(root)
        gid = create_condition_group(root, "WT").id
        src = root / "src"
        src.mkdir()
        a = src / "a.png"
        b = src / "b.png"
        _write_png(a)
        _write_png(b, h=40, w=50)
        results = create_samples_from_data_files(root, gid, [a, b])
        self.assertTrue(all(r.succeeded for r in results))
        sid_a = str(results[0].row["sample_id"])
        sid_b = str(results[1].row["sample_id"])

        with patch("actintrack_app.gui.default_workspace_root", return_value=root), patch(
            "actintrack_app.gui.DEFAULT_SOURCE_ROOT", root
        ):
            window = MainWindow()
        window._load_project(root, "PERF2")
        item_a = window._find_sample_tree_item(sid_a)
        item_b = window._find_sample_tree_item(sid_b)
        self.assertIsNotNone(item_a)
        self.assertIsNotNone(item_b)
        window._load_sample_from_tree_item(item_a)
        window._load_sample_from_tree_item(item_b)
        window._load_sample_from_tree_item(item_a)
        self.assertIsNotNone(window._cell_region)
        cell_a = window._cell_region.geometry_key()
        ann = get_sample_annotation(root, sid_a)
        self.assertIsNotNone(ann)
        self.assertIn("cell_region", ann or {})
        frame_a = window._base_frame.copy()

        with patch(
            "actintrack_app.gui.suggest_conservative_cell_region",
            side_effect=AssertionError("persisted CellRegion regenerated"),
        ), patch(
            "actintrack_app.gui.load_media_frame",
        ) as load_fn:
            window._load_sample_from_tree_item(item_b)
            window._load_sample_from_tree_item(item_a)
            self.assertEqual(window._current_sample_id, sid_a)
            self.assertEqual(window._cell_region.geometry_key(), cell_a)
            np.testing.assert_array_equal(window._base_frame, frame_a)
            load_fn.assert_not_called()
        window.close()
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
