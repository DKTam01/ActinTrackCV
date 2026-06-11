"""Tests for sample create/replace/clear/delete workflow."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from actintrack_app.batch_manager import create_batch, get_batch_by_name
from actintrack_app.metadata import (
    get_sample_annotation,
    load_samples_csv,
    save_sample_crop_annotation,
)
from actintrack_app.project_manager import create_project_structure
from actintrack_app.sample_service import (
    batch_has_auto_generated_name,
    clear_sample_derived_state,
    create_sample_from_data,
    default_sample_name_from_path,
    delete_sample_and_artifacts,
    get_primary_data_row,
    replace_sample_data,
    sample_has_derived_state,
    validate_av_mp4_data_file,
)
from actintrack_app.utils import DATA_FILES_CSV, GROUP_WT_218, METADATA_DIR, SAMPLE_REGISTRY_JSON


def _write_test_video(path: Path, frames: int = 3) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


class SampleServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        create_project_structure(self.root)
        self.breed = GROUP_WT_218
        self.video_a = self.root / "source_a.mp4"
        self.video_b = self.root / "source_b.mp4"
        _write_test_video(self.video_a)
        _write_test_video(self.video_b)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_default_sample_name_from_path(self) -> None:
        self.assertEqual(
            default_sample_name_from_path(Path("/tmp/My Clip.avi")),
            "My Clip",
        )

    def test_validate_rejects_non_video(self) -> None:
        bad = self.root / "notes.txt"
        bad.write_text("x", encoding="utf-8")
        ok, msg = validate_av_mp4_data_file(bad)
        self.assertFalse(ok)
        self.assertTrue(msg)

    def test_validate_accepts_mp4(self) -> None:
        ok, msg = validate_av_mp4_data_file(self.video_a)
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_create_sample_from_data(self) -> None:
        batch, row = create_sample_from_data(self.root, self.breed, self.video_a)
        self.assertEqual(batch["batch_name"], "source_a")
        self.assertEqual(row["original_filename"], "source_a.mp4")
        self.assertTrue(batch_has_auto_generated_name(self.root, self.breed, "source_a"))
        df = load_samples_csv(self.root / METADATA_DIR / DATA_FILES_CSV)
        self.assertEqual(len(df), 1)
        registry = json.loads(
            (self.root / METADATA_DIR / SAMPLE_REGISTRY_JSON).read_text(encoding="utf-8")
        )
        entry = registry[self.breed][0]
        self.assertTrue(entry.get("auto_generated_name"))
        self.assertEqual(entry.get("source_filename"), "source_a.mp4")

    def test_replace_on_legacy_empty_sample(self) -> None:
        batch = create_batch(self.root, self.breed, "LegacyEmpty", batch_number=1)
        row = replace_sample_data(
            self.root, self.breed, batch["batch_name"], self.video_a
        )
        self.assertEqual(row["original_filename"], "source_a.mp4")
        self.assertIsNotNone(get_primary_data_row(self.root, self.breed, "LegacyEmpty"))

    def test_replace_clears_derived_state(self) -> None:
        batch, row = create_sample_from_data(self.root, self.breed, self.video_a)
        sid = str(row["sample_id"])
        crop_path = self.root / METADATA_DIR / "crop_metadata.json"
        save_sample_crop_annotation(
            crop_path,
            sid,
            {"sample_id": sid, "group": self.breed, "status": "roi_marked"},
        )
        self.assertTrue(sample_has_derived_state(self.root, sid))
        replace_sample_data(
            self.root, self.breed, batch["batch_name"], self.video_b
        )
        self.assertFalse(sample_has_derived_state(self.root, sid))
        updated = get_primary_data_row(self.root, self.breed, "source_b")
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["original_filename"], "source_b.mp4")
        self.assertEqual(updated["processing_status"], "raw_imported")

    def test_clear_sample_derived_state(self) -> None:
        _batch, row = create_sample_from_data(self.root, self.breed, self.video_a)
        sid = str(row["sample_id"])
        crop_path = self.root / METADATA_DIR / "crop_metadata.json"
        save_sample_crop_annotation(
            crop_path,
            sid,
            {"sample_id": sid, "group": self.breed, "status": "roi_marked"},
        )
        clear_sample_derived_state(self.root, sid)
        self.assertIsNone(get_sample_annotation(self.root, sid))
        self.assertFalse(sample_has_derived_state(self.root, sid))

    def test_delete_sample_and_artifacts(self) -> None:
        batch, _row = create_sample_from_data(self.root, self.breed, self.video_a)
        stats = delete_sample_and_artifacts(self.root, self.breed, batch["batch_name"])
        self.assertGreaterEqual(stats.get("samples_removed", 0), 1)
        self.assertIsNone(get_batch_by_name(self.root, self.breed, batch["batch_name"]))
        df = load_samples_csv(self.root / METADATA_DIR / DATA_FILES_CSV)
        self.assertTrue(df.empty)

    def test_create_rolls_back_on_import_failure(self) -> None:
        with patch(
            "actintrack_app.sample_service.import_files",
            side_effect=OSError("copy failed"),
        ):
            with self.assertRaises(OSError):
                create_sample_from_data(self.root, self.breed, self.video_a)
        self.assertIsNone(get_batch_by_name(self.root, self.breed, "source_a"))


if __name__ == "__main__":
    unittest.main()
