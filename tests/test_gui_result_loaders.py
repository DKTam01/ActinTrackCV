"""Unit tests for tracking/optical-flow result view loaders."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from actintrack_app.export_naming import motion_index_summary_json_path
from actintrack_app.gui_result_loaders import (
    load_latest_optical_flow_result_view,
    load_latest_tracking_result_view,
    motion_index_summary_path_for_sample,
)
from actintrack_app.motion_index import MotionIndexParams, PointTrack
from actintrack_app.optical_flow_motion_index import OpticalFlowResult
from actintrack_app.preview_workflow import CroppedPreviewAnalysis
from actintrack_app.project_manager import get_processed_batch_dir
from actintrack_app.schema_compat import draft_optical_flow_path, draft_tracking_path
from actintrack_app.utils import STATUS_MOTION_INDEX_FAILED


def _tracking_payload(*, general_movement: float) -> dict:
    return {
        "num_tracks_with_valid_steps": 4,
        "num_tracks_started": 6,
        "downward_velocity_index_um_per_s": general_movement / 2,
        "absolute_velocity_index_um_per_s": general_movement,
        "total_valid_steps": 20,
    }


def _optical_flow_payload(*, general_movement: float) -> dict:
    return {
        "has_valid_result": True,
        "optical_flow_general_movement_um_s": general_movement,
        "optical_flow_downward_motion_um_s": general_movement / 2,
        "optical_flow_net_y_velocity_um_s": general_movement / 3,
        "optical_flow_directionality_ratio": 0.5,
        "optical_flow_valid_pixel_fraction": 0.8,
    }


def _preview_analysis(*, general_movement: float) -> CroppedPreviewAnalysis:
    frames = [np.zeros((32, 32), dtype=np.uint8) for _ in range(3)]
    tracks = [PointTrack(track_id=0, start_x=1.0, start_y=1.0)]
    return CroppedPreviewAnalysis(
        frames=frames,
        tracks=tracks,
        starting_points=[(1.0, 1.0)],
        downward_velocity_index_um_per_s=general_movement / 2,
        general_movement_index_um_per_s=general_movement,
        num_tracks_with_valid_steps=1,
        total_valid_steps=5,
        mean_track_length_frames=5.0,
        params=MotionIndexParams(),
    )


def _optical_flow_result(*, general_movement: float) -> OpticalFlowResult:
    return OpticalFlowResult(
        has_valid_result=True,
        optical_flow_general_movement_um_s=general_movement,
        optical_flow_downward_motion_um_s=general_movement / 2,
        optical_flow_net_y_velocity_um_s=general_movement / 3,
        optical_flow_directionality_ratio=0.5,
        optical_flow_valid_pixel_fraction=0.8,
        frame_pair_count=3,
    )


def _sample_row(
    *,
    sample_id: str = "sample_1",
    group: str = "1_WT_218",
    batch_name: str = "Batch 1",
    final_export_name: str = "export_a",
    processing_status: str = "processed",
) -> dict:
    return {
        "sample_id": sample_id,
        "group": group,
        "batch_name": batch_name,
        "final_export_name": final_export_name,
        "processing_status": processing_status,
    }


class MotionIndexSummaryPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_returns_path_when_summary_exists(self) -> None:
        row = _sample_row()
        batch_dir = get_processed_batch_dir(self.root, row["group"], row["batch_name"])
        batch_dir.mkdir(parents=True)
        summary = motion_index_summary_json_path(batch_dir, row["final_export_name"])
        summary.write_text("{}", encoding="utf-8")
        path = motion_index_summary_path_for_sample(self.root, row)
        self.assertEqual(path, summary)

    def test_missing_metadata_fields_returns_none(self) -> None:
        row = _sample_row(final_export_name="")
        self.assertIsNone(motion_index_summary_path_for_sample(self.root, row))

    def test_missing_file_returns_none(self) -> None:
        self.assertIsNone(motion_index_summary_path_for_sample(self.root, _sample_row()))

    def test_none_project_root_returns_none(self) -> None:
        self.assertIsNone(motion_index_summary_path_for_sample(None, _sample_row()))


class TrackingLoaderPriorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.sample_id = "sample_1"
        self.row = _sample_row(sample_id=self.sample_id)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_processed_summary(self, general_movement: float) -> None:
        batch_dir = get_processed_batch_dir(self.root, self.row["group"], self.row["batch_name"])
        batch_dir.mkdir(parents=True)
        path = motion_index_summary_json_path(batch_dir, self.row["final_export_name"])
        path.write_text(json.dumps(_tracking_payload(general_movement=general_movement)), encoding="utf-8")

    def _write_draft_tracking(self, general_movement: float) -> None:
        path = draft_tracking_path(self.root, self.sample_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_tracking_payload(general_movement=general_movement)), encoding="utf-8")

    def test_processed_wins_over_draft_and_cache(self) -> None:
        self._write_processed_summary(1.0)
        self._write_draft_tracking(2.0)
        view = load_latest_tracking_result_view(
            self.sample_id,
            project_root=self.root,
            sample_row=self.row,
            cached_preview=_preview_analysis(general_movement=3.0),
        )
        self.assertEqual(view.status, "success")
        self.assertEqual(view.general_movement, 1.0)

    def test_draft_wins_over_cache(self) -> None:
        self._write_draft_tracking(2.0)
        view = load_latest_tracking_result_view(
            self.sample_id,
            project_root=self.root,
            sample_row=self.row,
            cached_preview=_preview_analysis(general_movement=3.0),
        )
        self.assertEqual(view.status, "success")
        self.assertEqual(view.general_movement, 2.0)

    def test_cache_used_when_no_disk_sources(self) -> None:
        view = load_latest_tracking_result_view(
            self.sample_id,
            project_root=self.root,
            sample_row=self.row,
            cached_preview=_preview_analysis(general_movement=3.0),
        )
        self.assertEqual(view.status, "success")
        self.assertEqual(view.general_movement, 3.0)

    def test_corrupt_processed_falls_through_to_draft(self) -> None:
        batch_dir = get_processed_batch_dir(self.root, self.row["group"], self.row["batch_name"])
        batch_dir.mkdir(parents=True)
        path = motion_index_summary_json_path(batch_dir, self.row["final_export_name"])
        path.write_text("{not json", encoding="utf-8")
        self._write_draft_tracking(2.0)
        view = load_latest_tracking_result_view(
            self.sample_id,
            project_root=self.root,
            sample_row=self.row,
            cached_preview=None,
        )
        self.assertEqual(view.general_movement, 2.0)

    def test_corrupt_draft_falls_through_to_cache(self) -> None:
        path = draft_tracking_path(self.root, self.sample_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{bad", encoding="utf-8")
        view = load_latest_tracking_result_view(
            self.sample_id,
            project_root=self.root,
            sample_row=self.row,
            cached_preview=_preview_analysis(general_movement=3.0),
        )
        self.assertEqual(view.general_movement, 3.0)

    def test_motion_index_failed_fallback(self) -> None:
        row = _sample_row(processing_status=STATUS_MOTION_INDEX_FAILED)
        view = load_latest_tracking_result_view(
            self.sample_id,
            project_root=self.root,
            sample_row=row,
            cached_preview=None,
        )
        self.assertEqual(view.status, "failed")
        self.assertEqual(view.failure_reason, "Motion index generation failed.")

    def test_draft_readable_without_sample_row(self) -> None:
        self._write_draft_tracking(2.0)
        view = load_latest_tracking_result_view(
            self.sample_id,
            project_root=self.root,
            sample_row=None,
            cached_preview=None,
        )
        self.assertEqual(view.general_movement, 2.0)

    def test_no_sources_returns_none(self) -> None:
        view = load_latest_tracking_result_view(
            self.sample_id,
            project_root=self.root,
            sample_row=self.row,
            cached_preview=None,
        )
        self.assertIsNone(view)


class OpticalFlowLoaderPriorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.sample_id = "sample_1"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_draft_optical_flow(self, general_movement: float) -> None:
        path = draft_optical_flow_path(self.root, self.sample_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_optical_flow_payload(general_movement=general_movement)), encoding="utf-8")

    def test_draft_wins_over_cache(self) -> None:
        self._write_draft_optical_flow(1.0)
        view = load_latest_optical_flow_result_view(
            self.sample_id,
            project_root=self.root,
            cached_result=_optical_flow_result(general_movement=2.0),
        )
        self.assertEqual(view.status, "success")
        self.assertEqual(view.general_movement, 1.0)

    def test_cache_used_when_no_draft(self) -> None:
        view = load_latest_optical_flow_result_view(
            self.sample_id,
            project_root=self.root,
            cached_result=_optical_flow_result(general_movement=2.0),
        )
        self.assertEqual(view.status, "success")
        self.assertEqual(view.general_movement, 2.0)

    def test_corrupt_draft_falls_through_to_cache(self) -> None:
        path = draft_optical_flow_path(self.root, self.sample_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not-json", encoding="utf-8")
        view = load_latest_optical_flow_result_view(
            self.sample_id,
            project_root=self.root,
            cached_result=_optical_flow_result(general_movement=2.0),
        )
        self.assertEqual(view.general_movement, 2.0)

    def test_no_sources_returns_none(self) -> None:
        view = load_latest_optical_flow_result_view(
            self.sample_id,
            project_root=self.root,
            cached_result=None,
        )
        self.assertIsNone(view)

    def test_cache_when_project_root_none(self) -> None:
        view = load_latest_optical_flow_result_view(
            self.sample_id,
            project_root=None,
            cached_result=_optical_flow_result(general_movement=2.0),
        )
        self.assertEqual(view.general_movement, 2.0)


if __name__ == "__main__":
    unittest.main()
