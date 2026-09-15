"""Phase UX4: video-timing-only Workbench, control styling, terminology."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from actintrack_app.gui_styles import (
    STYLE_WORKBENCH_ACTION_BUTTON,
    WORKBENCH_ACTION_BUTTON_OBJECT_NAME,
    WORKBENCH_CONTROL_HEIGHT,
    apply_workbench_action_button,
)
from actintrack_app.timing_provenance import (
    ANALYSIS_USES_VIDEO_HEADER_ONLY,
    MISSING_VIDEO_TIMING_MESSAGE,
    TIMING_SOURCE_CUSTOM,
    TIMING_SOURCE_LAB_DEFAULT,
    TIMING_SOURCE_LEGACY_DEFAULT,
    TIMING_SOURCE_VIDEO_HEADER,
    TimingMetadata,
    calibrated_um_per_s,
    frame_interval_from_fps,
    probe_video_playback_fps,
    require_calibrated_timing,
    timing_from_dict,
    timing_from_result_payload,
)
from actintrack_app.workflow_state import (
    build_workflow_snapshot,
    format_sample_results_summary,
)

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class VideoTimingPolicyTests(unittest.TestCase):
    def test_valid_fps_derives_interval_and_is_ready_without_confirm_ui(self) -> None:
        self.assertTrue(ANALYSIS_USES_VIDEO_HEADER_ONLY)
        timing = TimingMetadata.from_video_header(6.0)
        self.assertIsNotNone(timing)
        assert timing is not None
        self.assertEqual(timing.timing_source, TIMING_SOURCE_VIDEO_HEADER)
        self.assertAlmostEqual(timing.analysis_seconds_per_frame, 1.0 / 6.0, places=6)
        self.assertTrue(timing.has_valid_video_timing)
        self.assertTrue(timing.is_calibrated_analysis_ready)
        self.assertEqual(timing.display_label(), "6.00 FPS · 0.1667 s/frame")
        require_calibrated_timing(timing)

    def test_six_fps_is_detected_not_hardcoded(self) -> None:
        path = ROOT / "testsamples/2_WT_550/01.avi"
        if not path.is_file():
            self.skipTest("testsamples AVI not present")
        fps = probe_video_playback_fps(path)
        self.assertIsNotNone(fps)
        self.assertAlmostEqual(float(fps), 6.0, places=3)
        interval = frame_interval_from_fps(fps)
        self.assertAlmostEqual(float(interval or 0.0), 1.0 / 6.0, places=6)
        for rel in (
            "actintrack_app/timing_provenance.py",
            "actintrack_app/gui.py",
            "actintrack_app/gui_layout_builders.py",
        ):
            src = _read(rel)
            self.assertNotIn("DEFAULT_VIDEO_FPS", src)
            self.assertNotIn("HARDCODED_FPS", src)
            self.assertNotIn("6.00 FPS · 0.1667", src)

    def test_invalid_fps_does_not_invent_timing_and_blocks_calibrated_run(self) -> None:
        self.assertIsNone(TimingMetadata.from_video_header(None))
        self.assertIsNone(TimingMetadata.from_video_header(0))
        self.assertIsNone(TimingMetadata.from_video_header(-3))
        unresolved = TimingMetadata.unresolved()
        self.assertFalse(unresolved.has_valid_video_timing)
        self.assertFalse(unresolved.is_calibrated_analysis_ready)
        with self.assertRaises(ValueError) as ctx:
            require_calibrated_timing(unresolved)
        self.assertIn("Valid video timing", str(ctx.exception))
        self.assertEqual(str(ctx.exception), MISSING_VIDEO_TIMING_MESSAGE)

    def test_provenance_persists_video_header_fields(self) -> None:
        timing = TimingMetadata.from_video_header(6.0)
        assert timing is not None
        payload = timing.to_dict()
        self.assertAlmostEqual(payload["observed_video_fps"], 6.0)
        self.assertAlmostEqual(payload["observed_frame_interval_s"], 1.0 / 6.0, places=6)
        self.assertAlmostEqual(payload["analysis_seconds_per_frame"], 1.0 / 6.0, places=6)
        self.assertEqual(payload["timing_source"], TIMING_SOURCE_VIDEO_HEADER)
        loaded = timing_from_dict(payload)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.timing_source, TIMING_SOURCE_VIDEO_HEADER)
        self.assertTrue(loaded.is_calibrated_analysis_ready)

    def test_old_timing_metadata_remains_readable(self) -> None:
        lab = timing_from_dict(
            {
                "observed_video_fps": 6.0,
                "observed_frame_interval_s": 1.0 / 6.0,
                "analysis_seconds_per_frame": 30.0,
                "timing_source": TIMING_SOURCE_LAB_DEFAULT,
                "timing_confirmed": True,
            }
        )
        self.assertIsNotNone(lab)
        assert lab is not None
        self.assertEqual(lab.timing_source, TIMING_SOURCE_LAB_DEFAULT)
        self.assertAlmostEqual(lab.analysis_seconds_per_frame, 30.0)
        self.assertTrue(lab.confirmed)
        self.assertFalse(lab.is_calibrated_analysis_ready)

        custom = TimingMetadata.custom(0.2, observed_video_fps=6.0, confirmed=True)
        self.assertEqual(custom.timing_source, TIMING_SOURCE_CUSTOM)
        restored = custom.with_source_choice(TIMING_SOURCE_VIDEO_HEADER, confirmed=True)
        self.assertEqual(restored.timing_source, TIMING_SOURCE_VIDEO_HEADER)

        legacy = timing_from_result_payload(
            {"parameters": {"seconds_per_frame": 0.2, "microns_per_pixel": 0.265}}
        )
        self.assertIsNotNone(legacy)
        assert legacy is not None
        self.assertEqual(legacy.timing_source, TIMING_SOURCE_LEGACY_DEFAULT)

    def test_px_per_frame_invariant_when_interval_changes(self) -> None:
        px = 4.5
        mpp = 0.265
        for spf in (30.0, 0.2, 1.0 / 6.0):
            um_s = calibrated_um_per_s(px, seconds_per_frame=spf, microns_per_pixel=mpp)
            back = um_s * spf / mpp
            self.assertAlmostEqual(back, px, places=9)


class WorkflowReadinessUx4Tests(unittest.TestCase):
    def test_run_metrics_uses_cell_cutoff_and_valid_video_timing(self) -> None:
        incomplete = build_workflow_snapshot(
            has_sample=True,
            has_crop=True,
            has_cell_region=True,
            has_nucleus=False,
            has_cutoff=True,
            timing_confirmed=False,
            has_valid_video_timing=False,
            metrics_present=False,
            metrics_stale=False,
        )
        self.assertFalse(incomplete.ready_to_run)
        self.assertEqual(
            incomplete.run_metrics_block_reason(),
            "Valid video timing is required",
        )

        ready = build_workflow_snapshot(
            has_sample=True,
            has_crop=True,
            has_cell_region=True,
            has_nucleus=False,
            has_cutoff=True,
            timing_confirmed=True,
            has_valid_video_timing=True,
            metrics_present=False,
            metrics_stale=False,
        )
        self.assertTrue(ready.ready_to_run)
        self.assertIsNone(ready.run_metrics_block_reason())
        self.assertFalse(ready.metric_analysis_allowed)

        no_cutoff = build_workflow_snapshot(
            has_sample=True,
            has_crop=True,
            has_cell_region=True,
            has_nucleus=True,
            has_cutoff=False,
            timing_confirmed=True,
            has_valid_video_timing=True,
            metrics_present=False,
            metrics_stale=False,
        )
        self.assertFalse(no_cutoff.ready_to_run)
        self.assertEqual(
            no_cutoff.run_metrics_block_reason(),
            "Set the Measurement Cutoff to continue.",
        )

    def test_metric_analysis_gating_unchanged(self) -> None:
        current = build_workflow_snapshot(
            has_sample=True,
            has_crop=True,
            has_cell_region=True,
            has_nucleus=True,
            has_cutoff=True,
            timing_confirmed=True,
            has_valid_video_timing=True,
            metrics_present=True,
            metrics_stale=False,
        )
        self.assertTrue(current.metric_analysis_allowed)
        stale = build_workflow_snapshot(
            has_sample=True,
            has_crop=True,
            has_cell_region=True,
            has_nucleus=True,
            has_cutoff=True,
            timing_confirmed=True,
            has_valid_video_timing=True,
            metrics_present=True,
            metrics_stale=True,
        )
        self.assertFalse(stale.metric_analysis_allowed)
        self.assertEqual(
            stale.metric_analysis_block_reason(),
            "Results are outdated — run Metrics again",
        )

    def test_sample_results_show_video_timing_and_px_frame(self) -> None:
        text = format_sample_results_summary(
            sparse_px=8.18,
            sparse_um_s=13.0,
            of_px=4.52,
            of_um_s=7.19,
            toward_nucleus_um_s=1.2,
            orientation_deg=33.5,
            tracks_used=8,
            tracks_requested=10,
            timing_label="6.00 FPS · 0.1667 s/frame",
            timing_confirmed=True,
        )
        self.assertIn("SAMPLE RESULTS", text)
        self.assertIn("General Movement", text)
        self.assertIn("8.18 px/frame", text)
        self.assertIn("Optical Flow", text)
        self.assertIn("Toward Nucleus", text)
        # MEDIA1: orientation is IMAGE-only; VIDEO Sample Results omit it.
        self.assertNotIn("F-actin Orientation", text)
        self.assertIn("Tracks", text)
        self.assertIn("Video Timing", text)
        self.assertIn("6.00 FPS · 0.1667 s/frame", text)


class WorkbenchLayoutUx4Tests(unittest.TestCase):
    def test_obsolete_timing_widgets_absent(self) -> None:
        layout = _read("actintrack_app/gui_layout_builders.py")
        gui = _read("actintrack_app/gui.py")
        self.assertNotIn("Confirm Timing", layout)
        self.assertNotIn("Confirm Timing", gui)
        self.assertNotIn("radio_timing_video", layout)
        self.assertNotIn("radio_timing_lab", layout)
        self.assertNotIn("radio_timing_custom", layout)
        self.assertNotIn("Custom s/frame", layout)
        self.assertNotIn("btn_confirm_timing", layout)
        self.assertNotIn("btn_confirm_timing", gui)
        self.assertIn("Video Timing", layout)
        setup = layout.split("def build_roi_preview_panel", 1)[1].split(
            "def build_roi_workflow_strip", 1
        )[0]
        self.assertIn("slider_cell_boundary", setup)
        self.assertIn("Select Nucleus", setup)
        self.assertIn("Measurement Cutoff", setup)
        self.assertNotIn("window.lbl_sample_results", setup)

    def test_sample_results_remain_beside_video(self) -> None:
        layout = _read("actintrack_app/gui_layout_builders.py")
        images = layout.split("def build_preview_images_panel", 1)[1].split(
            "def build_sample_results_beside_canvas", 1
        )[0]
        self.assertIn("build_sample_results_beside_canvas(window)", images)

    def test_no_stale_roi_saved_primary_copy(self) -> None:
        combined = (
            _read("actintrack_app/gui.py")
            + _read("actintrack_app/gui_layout_builders.py")
            + _read("actintrack_app/gui_user_strings.py")
            + _read("actintrack_app/workflow_state.py")
        )
        self.assertNotIn("ROI saved", combined)
        self.assertNotIn('"ROI marked"', combined)

    def test_science_modules_were_not_rewritten_in_this_phase(self) -> None:
        for rel in (
            "actintrack_app/motion_index.py",
            "actintrack_app/optical_flow_motion_index.py",
            "actintrack_app/cell_detection.py",
            "actintrack_app/structural_orientation.py",
        ):
            src = _read(rel)
            self.assertNotIn("ANALYSIS_USES_VIDEO_HEADER_ONLY", src)
            self.assertNotIn("from_video_header", src)


class WorkbenchControlStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def test_common_buttons_share_style_properties(self) -> None:
        from PyQt6.QtWidgets import QPushButton

        names = (
            "Metric Analysis",
            "Run Metrics",
            "Select Nucleus",
            "Clear",
            "Advanced: Adjust Cutoff",
            "Clear Cutoff",
        )
        buttons = []
        for name in names:
            btn = QPushButton(name)
            apply_workbench_action_button(btn)
            buttons.append(btn)
        styles = {btn.styleSheet() for btn in buttons}
        self.assertEqual(len(styles), 1)
        shared = next(iter(styles))
        self.assertEqual(shared, STYLE_WORKBENCH_ACTION_BUTTON)
        for btn in buttons:
            self.assertEqual(btn.objectName(), WORKBENCH_ACTION_BUTTON_OBJECT_NAME)
            self.assertEqual(btn.height(), WORKBENCH_CONTROL_HEIGHT)
        layout = _read("actintrack_app/gui_layout_builders.py")
        self.assertIn(
            "apply_workbench_action_button(window.btn_select_nucleus, expanding=True)",
            layout,
        )
        self.assertIn(
            "apply_workbench_action_button(window.btn_clear_nucleus, expanding=True)",
            layout,
        )
        self.assertIn(
            "apply_workbench_action_button(window.btn_advanced_cutoff, expanding=True)",
            layout,
        )
        self.assertIn(
            "apply_workbench_action_button(window.btn_clear_cutoff, expanding=True)",
            layout,
        )


class GuiTimingIntegrationTests(unittest.TestCase):
    def test_ensure_timing_uses_video_header_when_fps_valid(self) -> None:
        from actintrack_app.gui import MainWindow

        window = MainWindow.__new__(MainWindow)
        window._project_root = None
        window._current_sample = None
        window.lbl_timing_detected = MagicMock()
        window.lbl_timing_status = MagicMock()
        window._sample_file_path = MagicMock(
            return_value=ROOT / "testsamples/2_WT_550/01.avi"
        )
        path = window._sample_file_path()
        if not Path(path).is_file():
            self.skipTest("testsamples AVI not present")
        MainWindow._ensure_timing_for_current_sample(window, persist_observed=False)
        timing = window._timing
        self.assertEqual(timing.timing_source, TIMING_SOURCE_VIDEO_HEADER)
        self.assertAlmostEqual(timing.analysis_seconds_per_frame, 1.0 / 6.0, places=6)
        self.assertTrue(timing.is_calibrated_analysis_ready)

    def test_require_calibrated_timing_blocks_unresolved(self) -> None:
        from actintrack_app.gui import MainWindow

        window = MainWindow.__new__(MainWindow)
        window._timing = TimingMetadata.unresolved()
        with self.assertRaises(ValueError):
            MainWindow._require_calibrated_timing(window)


if __name__ == "__main__":
    unittest.main()
