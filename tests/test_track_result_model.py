"""Tests for canonical per-track scientific result persistence (Phase R5)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from actintrack_app.gui import MainWindow
from actintrack_app.motion_index import (
    TRACKING_RESULT_SCHEMA_VERSION,
    MotionIndexParams,
    PointTrack,
    TrackPoint,
    point_tracks_from_video_result,
    serialize_video_tracking_result,
)
from actintrack_app.preview_workflow import (
    CroppedPreviewAnalysis,
    cropped_preview_analysis_from_draft,
)


def _track() -> PointTrack:
    return PointTrack(
        track_id=7,
        start_x=10.0,
        start_y=12.0,
        points=[
            TrackPoint(7, 0, 10.0, 12.0, 1.0),
            TrackPoint(
                7,
                2,
                16.0,
                20.0,
                0.8,
                recovered_with_lookahead=True,
            ),
            TrackPoint(7, 3, 18.0, 20.0, 0.9),
        ],
        active=False,
        end_reason="reached_last_frame",
    )


class TrackResultSerializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.params = MotionIndexParams(
            microns_per_pixel=0.5,
            seconds_per_frame=2.0,
            lookahead_frames=1,
        )

    def test_serialized_result_preserves_points_steps_and_recovery(self) -> None:
        payload = serialize_video_tracking_result([_track()], self.params)
        self.assertEqual(payload["schema_version"], TRACKING_RESULT_SCHEMA_VERSION)
        self.assertEqual(payload["summary"]["num_tracks_started"], 1)
        self.assertEqual(payload["summary"]["total_valid_steps"], 2)
        self.assertEqual(payload["summary"]["tracks_recovered_with_lookahead"], 1)

        row = payload["tracks"][0]
        self.assertEqual(row["track_id"], 7)
        self.assertEqual([p["frame_index"] for p in row["points"]], [0, 2, 3])
        self.assertEqual(len(row["valid_steps"]), 2)
        self.assertEqual(row["valid_steps"][0]["frame_gap"], 2)
        self.assertAlmostEqual(row["valid_steps"][0]["dt_s"], 4.0)
        self.assertEqual(
            row["recovered_gaps"],
            [
                {
                    "from_frame_index": 0,
                    "to_frame_index": 2,
                    "frame_gap": 2,
                    "missing_frame_count": 1,
                }
            ],
        )
        self.assertAlmostEqual(
            row["absolute_movement_summary"]["total_path_length_px"],
            12.0,
        )
        self.assertEqual(
            row["measurement_provenance"]["frame_gap_handling"],
            "actual_frame_index_delta",
        )

    def test_round_trip_reconstructs_runtime_track_without_fabrication(self) -> None:
        payload = {"tracking_result": serialize_video_tracking_result([_track()], self.params)}
        restored = point_tracks_from_video_result(payload)
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0].track_id, 7)
        self.assertEqual(
            [(p.frame_index, p.x, p.y) for p in restored[0].points],
            [(0, 10.0, 12.0), (2, 16.0, 20.0), (3, 18.0, 20.0)],
        )
        self.assertTrue(restored[0].points[1].recovered_with_lookahead)
        self.assertEqual(restored[0].end_reason, "reached_last_frame")

    def test_legacy_payload_without_tracking_result_remains_readable(self) -> None:
        frames = [np.zeros((24, 24), dtype=np.uint8) for _ in range(2)]
        analysis = cropped_preview_analysis_from_draft(
            frames,
            {
                "general_movement_index_um_per_s": 2.5,
                "num_tracks_with_valid_steps": 3,
                "total_valid_steps": 9,
                "parameters": {
                    "microns_per_pixel": 0.5,
                    "seconds_per_frame": 2.0,
                },
            },
        )
        self.assertEqual(analysis.tracks, [])
        self.assertEqual(analysis.general_movement_index_um_per_s, 2.5)
        self.assertEqual(analysis.num_tracks_with_valid_steps, 3)

    def test_draft_run_metrics_embeds_canonical_tracking_result(self) -> None:
        frames = [np.zeros((24, 24), dtype=np.uint8) for _ in range(4)]
        analysis = CroppedPreviewAnalysis(
            frames=frames,
            tracks=[_track()],
            starting_points=[(10.0, 12.0)],
            downward_velocity_index_um_per_s=1.0,
            general_movement_index_um_per_s=2.0,
            num_tracks_with_valid_steps=1,
            total_valid_steps=2,
            mean_track_length_frames=3.0,
            params=self.params,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft.json"
            window = MainWindow.__new__(MainWindow)
            window._project_root = Path(tmp)
            window._draft_tracking_json_path = lambda _sample_id: path
            MainWindow._save_draft_tracking_result(
                window,
                "sample_1",
                analysis,
                self.params,
            )
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["sample_id"], "sample_1")
        self.assertEqual(
            payload["tracking_result"]["schema_version"],
            TRACKING_RESULT_SCHEMA_VERSION,
        )
        self.assertEqual(len(payload["tracking_result"]["tracks"]), 1)
        self.assertIn("general_movement_index_um_per_s", payload)

    def test_draft_reload_restores_tracks_for_overlay(self) -> None:
        frames = [np.zeros((24, 24), dtype=np.uint8) for _ in range(4)]
        draft = {
            "parameters": {
                key: value
                for key, value in self.params.__dict__.items()
            },
            "tracking_result": serialize_video_tracking_result([_track()], self.params),
            "general_movement_index_um_per_s": 2.0,
            "num_tracks_with_valid_steps": 1,
            "total_valid_steps": 2,
        }
        analysis = cropped_preview_analysis_from_draft(frames, draft)
        self.assertEqual(len(analysis.tracks), 1)
        self.assertEqual(analysis.starting_points, [(10.0, 12.0)])
        self.assertEqual(
            [point.frame_index for point in analysis.tracks[0].points],
            [0, 2, 3],
        )


if __name__ == "__main__":
    unittest.main()
