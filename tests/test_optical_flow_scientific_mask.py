"""Tests for Optical Flow scientific-domain parity (Phase R8)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

from actintrack_app.optical_flow_motion_index import (
    DenseFlowPair,
    OpticalFlowSettings,
    build_optical_flow_fingerprint,
    compute_optical_flow_motion_index,
    result_from_dict,
    result_to_dict,
)


def _frames() -> list[np.ndarray]:
    return [
        np.full((8, 8), 100 + index, dtype=np.uint8)
        for index in range(3)
    ]


def _controlled_pair(
    _prev: np.ndarray,
    _next: np.ndarray,
    _settings: OpticalFlowSettings,
    *,
    frame_a: int,
    frame_b: int,
) -> DenseFlowPair:
    flow = np.zeros((8, 8, 2), dtype=np.float32)
    flow[:, :4, 0] = 1.0
    flow[:, 4:, 0] = 5.0
    return DenseFlowPair(
        flow=flow,
        mask=np.ones((8, 8), dtype=bool),
        prev_gray=np.full((8, 8), 100.0, dtype=np.float32),
        frame_a=frame_a,
        frame_b=frame_b,
    )


class OpticalFlowScientificMaskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = OpticalFlowSettings(
            mask_percentile=0.0,
            gaussian_blur_kernel=0,
            microns_per_pixel=1.0,
            seconds_per_frame=1.0,
        )

    @patch(
        "actintrack_app.optical_flow_motion_index.compute_dense_flow_pair",
        side_effect=_controlled_pair,
    )
    def test_aggregation_restricts_existing_flow_without_recomputing(
        self,
        mocked_flow,
    ) -> None:
        unmasked = compute_optical_flow_motion_index(_frames(), self.settings)
        valid = np.zeros((8, 8), dtype=bool)
        valid[:, :4] = True
        masked = compute_optical_flow_motion_index(
            _frames(),
            self.settings,
            valid_mask=valid,
        )

        self.assertEqual(mocked_flow.call_count, 4)
        self.assertAlmostEqual(unmasked.mean_magnitude_px_frame or 0.0, 3.0)
        self.assertAlmostEqual(masked.mean_magnitude_px_frame or 0.0, 1.0)
        self.assertTrue(masked.scientific_valid_mask_applied)
        self.assertEqual(masked.scientific_valid_pixel_count, 32)
        self.assertAlmostEqual(
            masked.frame_pair_summaries[0].valid_pixel_fraction,
            0.5,
        )
        self.assertAlmostEqual(
            masked.frame_pair_summaries[0]
            .valid_pixel_fraction_of_scientific_domain
            or 0.0,
            1.0,
        )

    @patch(
        "actintrack_app.optical_flow_motion_index.compute_dense_flow_pair",
        side_effect=_controlled_pair,
    )
    def test_all_true_mask_is_numerically_identical(self, _mocked_flow) -> None:
        legacy = compute_optical_flow_motion_index(_frames(), self.settings)
        masked = compute_optical_flow_motion_index(
            _frames(),
            self.settings,
            valid_mask=np.ones((8, 8), dtype=bool),
        )
        self.assertEqual(
            legacy.mean_magnitude_px_frame,
            masked.mean_magnitude_px_frame,
        )
        self.assertEqual(
            legacy.optical_flow_general_movement_um_s,
            masked.optical_flow_general_movement_um_s,
        )
        self.assertEqual(
            [row.mean_magnitude_px_frame for row in legacy.frame_pair_summaries],
            [row.mean_magnitude_px_frame for row in masked.frame_pair_summaries],
        )

    @patch(
        "actintrack_app.optical_flow_motion_index.compute_dense_flow_pair",
        side_effect=_controlled_pair,
    )
    def test_all_false_scientific_mask_produces_explicit_non_result(
        self,
        _mocked_flow,
    ) -> None:
        result = compute_optical_flow_motion_index(
            _frames(),
            self.settings,
            valid_mask=np.zeros((8, 8), dtype=bool),
        )
        self.assertFalse(result.has_valid_result)
        self.assertIn("No valid pixels", result.failure_reason)
        self.assertTrue(result.scientific_valid_mask_applied)
        self.assertEqual(result.scientific_valid_pixel_count, 0)

    def test_mask_shape_mismatch_fails_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "valid_mask shape"):
            compute_optical_flow_motion_index(
                _frames(),
                self.settings,
                valid_mask=np.ones((4, 4), dtype=bool),
            )

    def test_fingerprint_includes_scientific_mask_identity(self) -> None:
        kwargs = {
            "sample_id": "sample_1",
            "roi_bounds": (0, 0, 8, 8),
            "settings": self.settings,
            "frame_count": 3,
        }
        no_mask = build_optical_flow_fingerprint(**kwargs)
        left = np.zeros((8, 8), dtype=bool)
        left[:, :4] = True
        right = np.fliplr(left)
        self.assertNotEqual(
            no_mask,
            build_optical_flow_fingerprint(**kwargs, valid_mask=left),
        )
        self.assertNotEqual(
            build_optical_flow_fingerprint(**kwargs, valid_mask=left),
            build_optical_flow_fingerprint(**kwargs, valid_mask=right),
        )

    @patch(
        "actintrack_app.optical_flow_motion_index.compute_dense_flow_pair",
        side_effect=_controlled_pair,
    )
    def test_mask_provenance_round_trip(self, _mocked_flow) -> None:
        valid = np.zeros((8, 8), dtype=bool)
        valid[:, :4] = True
        original = compute_optical_flow_motion_index(
            _frames(),
            self.settings,
            valid_mask=valid,
        )
        payload = result_to_dict(original)
        self.assertEqual(
            payload["aggregation_mask_definition"],
            "brightness_mask intersect scientific_valid_mask",
        )
        restored = result_from_dict(payload)
        self.assertTrue(restored.scientific_valid_mask_applied)
        self.assertEqual(restored.scientific_valid_pixel_count, 32)
        self.assertEqual(
            restored.scientific_valid_mask_sha256,
            original.scientific_valid_mask_sha256,
        )


if __name__ == "__main__":
    unittest.main()
