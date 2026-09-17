"""PERF1 CellRegion performance regression tests (architectural, not wall-clock)."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from actintrack_app.cell_detection import (
    prepare_cell_signal,
    suggest_conservative_cell_region,
)
from actintrack_app.gui import MainWindow


ROOT = Path(__file__).resolve().parents[1]


def _blob_frame(h: int = 80, w: int = 60) -> np.ndarray:
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[15:65, 10:50] = (30, 200, 30)
    return frame


class CellRegionPreparationReuseTests(unittest.TestCase):
    def test_prepared_signal_matches_unprepared_geometry(self) -> None:
        frame = _blob_frame()
        prepared = prepare_cell_signal(frame)
        for sensitivity in (0.0, 0.5, 1.0):
            a = suggest_conservative_cell_region(frame, sensitivity=sensitivity)
            b = suggest_conservative_cell_region(
                frame, sensitivity=sensitivity, prepared=prepared
            )
            self.assertEqual(
                a.region.geometry_key(),
                b.region.geometry_key(),
                msg=f"sensitivity={sensitivity}",
            )

    def test_sensitivity_reuses_preparation_without_recomputing_signal(self) -> None:
        frame = _blob_frame()
        prepared = prepare_cell_signal(frame)
        with patch(
            "actintrack_app.cell_detection.actin_signal_image",
            side_effect=AssertionError("signal must not recompute"),
        ):
            for sensitivity in (0.0, 0.25, 0.5, 0.75, 1.0):
                suggest_conservative_cell_region(
                    frame, sensitivity=sensitivity, prepared=prepared
                )

    def test_gui_cache_clears_across_samples(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._base_frame = _blob_frame()
        window._current_sample_id = "A"
        window._frame_index = 0
        window._orientation = MagicMock(
            rotation_angle_degrees=0, mirror_y_axis=False, flipped_180=False
        )
        window._prepared_cell_signal = None
        window._prepared_cell_signal_token = None
        oriented = window._base_frame
        first = MainWindow._prepared_cell_signal_for_oriented(window, oriented)
        second = MainWindow._prepared_cell_signal_for_oriented(window, oriented)
        self.assertIs(first, second)
        window._current_sample_id = "B"
        MainWindow._clear_prepared_cell_signal(window)
        self.assertIsNone(window._prepared_cell_signal)
        third = MainWindow._prepared_cell_signal_for_oriented(window, oriented)
        self.assertIsNot(third, first)


class CellRegionCorpusSmokeTests(unittest.TestCase):
    def test_representative_avi_detection(self) -> None:
        path = ROOT / "testsamples/2_WT_550/02.avi"
        if not path.is_file():
            self.skipTest("testsamples AVI not present")
        from actintrack_app.video_processing import load_video_frame

        frame = load_video_frame(path, 0)
        cell = suggest_conservative_cell_region(frame, sensitivity=0.5)
        bbox = cell.bounding_box()
        self.assertGreaterEqual(bbox.width, 4)
        self.assertGreaterEqual(bbox.height, 4)


if __name__ == "__main__":
    unittest.main()
