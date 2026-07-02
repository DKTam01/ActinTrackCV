"""Tests for metric freshness / scheduled-state regression guards."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from actintrack_app.gui import MainWindow


class MetricScheduledStateTests(unittest.TestCase):
    def _stub_window(self) -> MainWindow:
        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window._metrics_inflight = set()
        window._tracking_job_running = False
        window._optical_flow_job_running = False
        window._metric_compute_queue = []
        window._metric_debounce_timer = MagicMock(isActive=lambda: False)
        window._metric_settings_timer = MagicMock(isActive=lambda: False)
        window._pending_tracking_snapshot = object()
        window._pending_optical_flow_snapshot = object()
        window._tracking_result_stale_by_sample = {}
        window._optical_flow_stale_by_sample = {}
        window._metric_error_by_sample = {}
        window._sample_has_valid_data_and_roi = lambda _sid: True
        window._read_draft_tracking_payload = lambda _sid: {
            "num_tracks_with_valid_steps": 2
        }
        window._read_draft_optical_flow_payload = lambda _sid: {
            "has_valid_result": True
        }
        return window

    def test_pending_snapshots_without_active_timer_not_scheduled(self) -> None:
        """Stale pending snapshots must not keep status scheduled after debounce."""
        window = self._stub_window()
        self.assertEqual(window._metric_state_for_sample("S1"), "analyzed")

    def test_active_timer_with_pending_is_scheduled(self) -> None:
        window = self._stub_window()
        window._metric_debounce_timer = MagicMock(isActive=lambda: True)
        self.assertEqual(window._metric_state_for_sample("S1"), "scheduled")

    def test_active_timer_without_pending_not_scheduled(self) -> None:
        window = self._stub_window()
        window._metric_debounce_timer = MagicMock(isActive=lambda: True)
        window._pending_tracking_snapshot = None
        window._pending_optical_flow_snapshot = None
        self.assertEqual(window._metric_state_for_sample("S1"), "analyzed")

    def test_on_metric_debounce_fired_clears_pending_and_refreshes(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._preview_mode = "full"
        window._pending_tracking_snapshot = MagicMock(name="track_snap")
        window._pending_optical_flow_snapshot = MagicMock(name="of_snap")
        window._run_draft_tracking_for_snapshot = MagicMock(return_value=True)
        window._run_optical_flow_for_snapshot = MagicMock(return_value=True)
        window._update_metric_freshness_label = MagicMock()

        MainWindow._on_metric_debounce_fired(window)

        window._run_draft_tracking_for_snapshot.assert_called_once()
        window._run_optical_flow_for_snapshot.assert_called_once()
        self.assertIsNone(window._pending_tracking_snapshot)
        self.assertIsNone(window._pending_optical_flow_snapshot)
        window._update_metric_freshness_label.assert_called_once()

    def test_on_metric_debounce_fired_refreshes_even_when_jobs_skip(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window._preview_mode = "full"
        window._pending_tracking_snapshot = MagicMock(name="track_snap")
        window._pending_optical_flow_snapshot = None
        window._run_draft_tracking_for_snapshot = MagicMock(return_value=False)
        window._run_optical_flow_for_snapshot = MagicMock(return_value=False)
        window._update_metric_freshness_label = MagicMock()

        MainWindow._on_metric_debounce_fired(window)

        self.assertIsNone(window._pending_tracking_snapshot)
        window._update_metric_freshness_label.assert_called_once()


if __name__ == "__main__":
    unittest.main()
