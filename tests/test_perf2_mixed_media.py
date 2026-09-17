"""PERF2 mixed-media Condition Groups and capability-aware Analysis n."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from actintrack_app.analysis_service import build_analysis_report
from actintrack_app.batch_manager import (
    list_batches,
    reorder_samples_in_condition_group,
)
from actintrack_app.condition_group_manager import create_condition_group
from actintrack_app.import_classifier import ImportKind, classify_paths
from actintrack_app.media_capabilities import (
    SampleMediaType,
    capabilities_for_sample_row,
    media_type_from_sample_row,
)
from actintrack_app.metadata import load_samples_csv
from actintrack_app.project_manager import create_project_structure
from actintrack_app.sample_service import (
    DATA_IMPORT_FILTER,
    create_samples_from_data_files,
)
from actintrack_app.schema_compat import (
    draft_structural_orientation_path,
    draft_tracking_path,
)
from actintrack_app.utils import DATA_FILES_CSV, METADATA_DIR


def _write_jpg(path: Path) -> None:
    frame = np.zeros((24, 24, 3), dtype=np.uint8)
    frame[:, :] = (40, 180, 180)
    cv2.imwrite(str(path), frame)


def _write_png(path: Path) -> None:
    frame = np.zeros((24, 24, 3), dtype=np.uint8)
    frame[:, :] = (30, 200, 40)
    cv2.imwrite(str(path), frame)


def _write_tiff(path: Path) -> None:
    frame = np.zeros((24, 24), dtype=np.uint8)
    frame[:, :] = 180
    import tifffile

    tifffile.imwrite(str(path), frame)


def _write_video(path: Path, frames: int = 3) -> None:
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        10.0,
        (32, 32),
    )
    for i in range(frames):
        frame = np.zeros((32, 32, 3), dtype=np.uint8)
        frame[:, :] = (i * 40, 0, 0)
        writer.write(frame)
    writer.release()


class MixedMediaImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        create_project_structure(self.root)
        self.gid = create_condition_group(self.root, "WT").id
        self.src = self.root / "src"
        self.src.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_video_then_png_same_group(self) -> None:
        video = self.src / "a.mp4"
        png = self.src / "b.png"
        _write_video(video)
        _write_png(png)
        first = create_samples_from_data_files(self.root, self.gid, [video])
        second = create_samples_from_data_files(self.root, self.gid, [png])
        self.assertTrue(first[0].succeeded)
        self.assertTrue(second[0].succeeded)
        df = load_samples_csv(self.root / METADATA_DIR / DATA_FILES_CSV)
        self.assertEqual(set(df["media_type"].astype(str)), {"video", "image"})
        self.assertEqual(set(df["group"].astype(str)), {self.gid})

    def test_png_then_avi_same_group(self) -> None:
        png = self.src / "cell.png"
        avi = self.src / "clip.avi"
        _write_png(png)
        _write_video(avi)
        self.assertTrue(
            create_samples_from_data_files(self.root, self.gid, [png])[0].succeeded
        )
        self.assertTrue(
            create_samples_from_data_files(self.root, self.gid, [avi])[0].succeeded
        )

    def test_mixed_multi_select_all_product_types(self) -> None:
        files = [
            self.src / "a.avi",
            self.src / "b.mp4",
            self.src / "c.jpg",
            self.src / "d.png",
            self.src / "e.tif",
        ]
        _write_video(files[0])
        _write_video(files[1])
        _write_jpg(files[2])
        _write_png(files[3])
        _write_tiff(files[4])
        results = create_samples_from_data_files(self.root, self.gid, files)
        self.assertTrue(all(r.succeeded for r in results))
        self.assertEqual(len(results), 5)
        df = load_samples_csv(self.root / METADATA_DIR / DATA_FILES_CSV)
        self.assertEqual(len(df), 5)
        self.assertEqual(set(df["group"].astype(str)), {self.gid})

    def test_save_reload_mixed_group_capabilities(self) -> None:
        video = self.src / "a.mp4"
        png = self.src / "b.png"
        _write_video(video)
        _write_png(png)
        create_samples_from_data_files(self.root, self.gid, [video, png])
        df = load_samples_csv(self.root / METADATA_DIR / DATA_FILES_CSV)
        rows = [row.to_dict() for _, row in df.iterrows()]
        types = {media_type_from_sample_row(row) for row in rows}
        self.assertEqual(types, {SampleMediaType.VIDEO, SampleMediaType.IMAGE})
        for row in rows:
            caps = capabilities_for_sample_row(row)
            if caps.is_video:
                self.assertTrue(caps.supports_general_movement)
                self.assertFalse(caps.supports_orientation)
            else:
                self.assertFalse(caps.supports_general_movement)
                self.assertTrue(caps.supports_orientation)

    def test_internal_reorder_after_mixed_import(self) -> None:
        video = self.src / "a.mp4"
        png = self.src / "b.png"
        _write_video(video)
        _write_png(png)
        results = create_samples_from_data_files(self.root, self.gid, [video, png])
        ids = [str(r.row["sample_id"]) for r in results]
        names = [str(r.row["batch_name"]) for r in results]
        applied = reorder_samples_in_condition_group(
            self.root, self.gid, list(reversed(ids))
        )
        self.assertEqual(applied, list(reversed(ids)))
        ordered = [b["batch_name"] for b in list_batches(self.root, self.gid)]
        self.assertEqual(ordered[:2], list(reversed(names)))

    def test_classify_paths_keeps_valid_when_mixed_with_txt(self) -> None:
        png = self.src / "cell.png"
        bad = self.src / "notes.txt"
        _write_png(png)
        bad.write_text("nope", encoding="utf-8")
        kind, files, msg = classify_paths([png, bad])
        self.assertEqual(kind, ImportKind.IMAGE)
        self.assertEqual(files, [png.resolve()])
        self.assertIn("Unsupported", msg)

    def test_classify_mixed_video_and_png(self) -> None:
        video = self.src / "clip.mp4"
        png = self.src / "cell.png"
        _write_video(video)
        _write_png(png)
        kind, files, msg = classify_paths([video, png])
        self.assertEqual(kind, ImportKind.MIXED)
        self.assertEqual(msg, "")
        self.assertEqual(len(files), 2)

    def test_file_picker_filter_includes_mixed_product_types(self) -> None:
        for ext in (".avi", ".mp4", ".jpg", ".jpeg", ".png", ".tif", ".tiff"):
            self.assertIn(ext, DATA_IMPORT_FILTER)


class MixedMediaAnalysisNTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        create_project_structure(self.root)
        self.gid = create_condition_group(self.root, "WT").id
        self.src = self.root / "src"
        self.src.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_metric_specific_n_ignores_unsupported_media(self) -> None:
        video = self.src / "a.mp4"
        png = self.src / "b.png"
        _write_video(video)
        _write_png(png)
        results = create_samples_from_data_files(self.root, self.gid, [video, png])
        vid_id = str(results[0].row["sample_id"])
        img_id = str(results[1].row["sample_id"])
        track_path = draft_tracking_path(self.root, vid_id)
        track_path.parent.mkdir(parents=True, exist_ok=True)
        track_path.write_text(
            json.dumps(
                {
                    "num_tracks_with_valid_steps": 2,
                    "total_valid_steps": 4,
                    "general_movement_index_um_per_s": 0.12,
                    "absolute_velocity_index_um_per_s": 0.12,
                }
            ),
            encoding="utf-8",
        )
        ori_path = draft_structural_orientation_path(self.root, img_id)
        ori_path.parent.mkdir(parents=True, exist_ok=True)
        ori_path.write_text(
            json.dumps(
                {
                    "has_valid_result": True,
                    "median_angle_relative_nucleus_deg": 33.0,
                    "measurement_count": 8,
                }
            ),
            encoding="utf-8",
        )
        report = build_analysis_report(self.root)
        self.assertEqual(len(report.sample_details), 2)
        by_id = {}
        for row in report.sample_details:
            sid = (row.sample_ids or ("",))[0]
            by_id[sid] = row
        self.assertTrue(by_id[vid_id].metrics.has_valid_result)
        self.assertFalse(by_id[vid_id].metrics.orientation_has_valid_result)
        self.assertIsNone(by_id[vid_id].metrics.orientation_median_deg)
        self.assertFalse(by_id[img_id].metrics.has_valid_result)
        self.assertIsNone(by_id[img_id].metrics.general_movement)
        self.assertTrue(by_id[img_id].metrics.orientation_has_valid_result)
        summary = report.breed_summaries[0]
        self.assertEqual(summary.sample_count, 2)
        self.assertEqual(summary.samples_with_results, 1)
        self.assertEqual(summary.samples_with_orientation_results, 1)
        self.assertAlmostEqual(summary.avg_general_movement or 0.0, 0.12)
        self.assertAlmostEqual(summary.avg_orientation_median_deg or 0.0, 33.0)


if __name__ == "__main__":
    unittest.main()
