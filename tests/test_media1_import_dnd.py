"""Tests for MEDIA1 multi-file import and Explorer external drops."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import cv2
import numpy as np
from PyQt6.QtCore import QMimeData, QUrl

from actintrack_app.batch_manager import list_batches
from actintrack_app.condition_group_manager import create_condition_group
from actintrack_app.explorer_tree import ExplorerTreeWidget
from actintrack_app.metadata import load_samples_csv
from actintrack_app.project_manager import create_project_structure
from actintrack_app.sample_service import (
    create_samples_from_data_files,
    format_sample_import_summary,
)
from actintrack_app.utils import DATA_FILES_CSV, METADATA_DIR


def _write_jpg(path: Path) -> None:
    frame = np.zeros((24, 24, 3), dtype=np.uint8)
    frame[:, :] = (40, 180, 180)
    cv2.imwrite(str(path), frame)


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


class MultiFileImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        create_project_structure(self.root)
        self.breed = create_condition_group(self.root, "WT").id
        self.video = self.root / "a.mp4"
        self.image = self.root / "b.jpg"
        self.bad = self.root / "notes.txt"
        _write_video(self.video)
        _write_jpg(self.image)
        self.bad.write_text("nope", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_mixed_batch_partial_failure(self) -> None:
        results = create_samples_from_data_files(
            self.root,
            self.breed,
            [self.video, self.bad, self.image],
        )
        self.assertEqual(len(results), 3)
        self.assertTrue(results[0].succeeded)
        self.assertFalse(results[1].succeeded)
        self.assertTrue(results[2].succeeded)
        summary = format_sample_import_summary(results)
        self.assertIn("Imported 2 of 3", summary)
        self.assertIn("notes.txt", summary)
        batches = list_batches(self.root, self.breed)
        self.assertEqual(len(batches), 2)
        df = load_samples_csv(self.root / METADATA_DIR / DATA_FILES_CSV)
        media = set(df["media_type"].astype(str).tolist())
        self.assertEqual(media, {"video", "image"})

    def test_windows_style_path_string(self) -> None:
        # Path objects normalize separators; ensure string with backslashes works.
        weird = Path(str(self.image).replace("/", "\\") if False else self.image)
        results = create_samples_from_data_files(self.root, self.breed, [weird])
        self.assertTrue(results[0].succeeded)

    def test_target_group_is_argument(self) -> None:
        other = create_condition_group(self.root, "Mutant").id
        results = create_samples_from_data_files(self.root, other, [self.image])
        self.assertTrue(results[0].succeeded)
        self.assertEqual(results[0].row.get("group"), other)


class ExplorerExternalDropMimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def test_local_paths_from_mime_preserves_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "one.jpg"
            b = root / "two.tif"
            a.write_bytes(b"x")
            b.write_bytes(b"y")
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(a)), QUrl.fromLocalFile(str(b))])
            paths = ExplorerTreeWidget.local_paths_from_mime(mime)
            self.assertEqual([p.name for p in paths], ["one.jpg", "two.tif"])

    def test_internal_sample_mime_not_treated_as_external(self) -> None:
        tree = ExplorerTreeWidget()
        mime = QMimeData()
        mime.setData("application/x-actintrack-sample-id", b"S1")
        self.assertFalse(tree._mime_has_external_files(mime))


if __name__ == "__main__":
    unittest.main()
