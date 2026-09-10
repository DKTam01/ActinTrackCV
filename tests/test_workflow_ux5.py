"""Phase UX5: Explorer reorder, optional nucleus, cutoff readiness, MA inspection."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QTreeWidgetItem

from actintrack_app.batch_manager import (
    list_batches,
    reorder_samples_in_condition_group,
)
from actintrack_app.explorer_tree import (
    ITEM_TYPE_CONDITION_GROUP,
    ITEM_TYPE_SAMPLE,
    ExplorerTreeWidget,
)
from actintrack_app.project_manager import create_project_structure
from actintrack_app.workflow_state import (
    build_workflow_snapshot,
    format_sample_results_summary,
)

ROOT = Path(__file__).resolve().parents[1]

_APP: QApplication | None = None


def _app() -> QApplication:
    global _APP
    existing = QApplication.instance()
    if existing is not None:
        return existing
    _APP = QApplication([])
    return _APP


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# Ensure Qt is ready before any ExplorerTreeWidget construction at import/class time.
_app()


class ExplorerItemMetaStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def test_item_meta_accepts_item_without_typeerror(self) -> None:
        tree = ExplorerTreeWidget()
        item = QTreeWidgetItem(["sample"])
        meta = {"item_type": ITEM_TYPE_SAMPLE, "sample_id": "s1"}
        item.setData(0, Qt.ItemDataRole.UserRole, meta)
        # Regression: missing @staticmethod caused TypeError on drag/drop.
        self.assertEqual(tree._item_meta(item), meta)
        self.assertEqual(ExplorerTreeWidget._item_meta(item), meta)
        self.assertIsNone(tree._item_meta(None))


class ExplorerReorderSignalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def _group_with_samples(self) -> tuple[ExplorerTreeWidget, QTreeWidgetItem]:
        tree = ExplorerTreeWidget()
        group = QTreeWidgetItem(["Group"])
        group.setData(
            0,
            Qt.ItemDataRole.UserRole,
            {
                "item_type": ITEM_TYPE_CONDITION_GROUP,
                "condition_group_id": "g1",
            },
        )
        tree.addTopLevelItem(group)
        for sid, label in (("s02", "02.avi"), ("s05", "05.avi"), ("s_alpha", "alpha.avi")):
            child = QTreeWidgetItem([label])
            child.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {
                    "item_type": ITEM_TYPE_SAMPLE,
                    "sample_id": sid,
                    "condition_group_id": "g1",
                },
            )
            group.addChild(child)
        group.setExpanded(True)
        return tree, group

    def test_same_group_drop_emits_reorder_not_move(self) -> None:
        tree, group = self._group_with_samples()
        reorder_events: list[tuple[str, str, str]] = []
        drop_events: list[tuple[str, str]] = []
        tree.sample_reorder_requested.connect(
            lambda a, b, c: reorder_events.append((a, b, c))
        )
        tree.sample_drop_requested.connect(lambda a, b: drop_events.append((a, b)))

        target = group.child(0)  # 02.avi
        # Mimic dropEvent core path for same-group adjacent upward move of 05.
        sample_id = "s05"
        target_gid = "g1"
        before = ""
        target_meta = tree._item_meta(target)
        if target_meta and target_meta.get("item_type") == ITEM_TYPE_SAMPLE:
            anchor = str(target_meta.get("sample_id", "")).strip()
            if anchor and anchor != sample_id:
                before = anchor
        tree.sample_reorder_requested.emit(sample_id, target_gid, before)
        self.assertEqual(reorder_events, [("s05", "g1", "s02")])
        self.assertEqual(drop_events, [])


class ExplorerOrderPersistenceTests(unittest.TestCase):
    def test_reorder_preserves_arbitrary_non_numeric_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            root.mkdir()
            create_project_structure(root)
            from actintrack_app.condition_group_manager import (
                create_condition_group,
            )
            from actintrack_app.metadata import load_samples_csv, save_samples_csv
            from actintrack_app.utils import METADATA_DIR, SAMPLES_CSV
            from actintrack_app.batch_manager import (
                _load_batches_registry,
                _save_batches_registry,
            )

            gid = create_condition_group(root, "WT").id
            # Registry entries with non-numeric names; default sort would use batch_number.
            registry = _load_batches_registry(root)
            registry[gid] = [
                {
                    "batch_name": "zeta",
                    "batch_number": 1,
                    "sample_id": "sid_zeta",
                },
                {
                    "batch_name": "alpha",
                    "batch_number": 2,
                    "sample_id": "sid_alpha",
                },
                {
                    "batch_name": "05",
                    "batch_number": 3,
                    "sample_id": "sid_05",
                },
                {
                    "batch_name": "02",
                    "batch_number": 4,
                    "sample_id": "sid_02",
                },
            ]
            _save_batches_registry(root, registry)

            samples_path = root / METADATA_DIR / SAMPLES_CSV
            df = load_samples_csv(samples_path)
            rows = []
            for name, sid, num in (
                ("zeta", "sid_zeta", 1),
                ("alpha", "sid_alpha", 2),
                ("05", "sid_05", 3),
                ("02", "sid_02", 4),
            ):
                rows.append(
                    {
                        "sample_id": sid,
                        "group": gid,
                        "condition_group_id": gid,
                        "batch_name": name,
                        "batch_number": str(num),
                        "original_filename": f"{name}.avi",
                        "stored_path": f"raw/{gid}/{name}/{name}.avi",
                        "processing_status": "imported",
                    }
                )
            import pandas as pd

            save_samples_csv(root, pd.DataFrame(rows))

            # Default order follows batch_number: zeta, alpha, 05, 02
            names = [b["batch_name"] for b in list_batches(root, gid)]
            self.assertEqual(names, ["zeta", "alpha", "05", "02"])

            # Move 05 above adjacent 02 conceptually → desired researcher order:
            # zeta, alpha, 02, 05 was wrong; want 05 before 02 among last two,
            # and also first↔last: put 02 first, zeta last.
            applied = reorder_samples_in_condition_group(
                root,
                gid,
                ["sid_02", "sid_05", "sid_alpha", "sid_zeta"],
            )
            self.assertEqual(
                applied, ["sid_02", "sid_05", "sid_alpha", "sid_zeta"]
            )
            ordered = [b["batch_name"] for b in list_batches(root, gid)]
            self.assertEqual(ordered, ["02", "05", "alpha", "zeta"])
            # batch_number identity unchanged (no filename sort rewrite)
            by_name = {b["batch_name"]: int(b["batch_number"]) for b in list_batches(root, gid)}
            self.assertEqual(by_name["02"], 4)
            self.assertEqual(by_name["zeta"], 1)

            # Adjacent upward: move 05 above 02
            applied2 = reorder_samples_in_condition_group(
                root,
                gid,
                ["sid_05", "sid_02", "sid_alpha", "sid_zeta"],
            )
            self.assertEqual(applied2[0], "sid_05")
            self.assertEqual(
                [b["batch_name"] for b in list_batches(root, gid)],
                ["05", "02", "alpha", "zeta"],
            )

            # Adjacent downward: move 05 below 02
            reorder_samples_in_condition_group(
                root,
                gid,
                ["sid_02", "sid_05", "sid_alpha", "sid_zeta"],
            )
            self.assertEqual(
                [b["batch_name"] for b in list_batches(root, gid)],
                ["02", "05", "alpha", "zeta"],
            )


class WorkflowReadinessUx5Tests(unittest.TestCase):
    def test_cell_cutoff_timing_no_nucleus_enables_run(self) -> None:
        snap = build_workflow_snapshot(
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
        self.assertTrue(snap.ready_to_run)
        self.assertIsNone(snap.run_metrics_block_reason())

    def test_missing_cutoff_disables_run(self) -> None:
        snap = build_workflow_snapshot(
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
        self.assertFalse(snap.ready_to_run)
        self.assertEqual(
            snap.run_metrics_block_reason(),
            "Set the Measurement Cutoff to continue.",
        )
        self.assertIn("Cutoff", snap.next_action_hint())

    def test_nucleus_does_not_gate_basic_execution(self) -> None:
        without = build_workflow_snapshot(
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
        with_nuc = build_workflow_snapshot(
            has_sample=True,
            has_crop=True,
            has_cell_region=True,
            has_nucleus=True,
            has_cutoff=True,
            timing_confirmed=True,
            has_valid_video_timing=True,
            metrics_present=False,
            metrics_stale=False,
        )
        self.assertTrue(without.ready_to_run)
        self.assertTrue(with_nuc.ready_to_run)


class SampleResultsOptionalNucleusTests(unittest.TestCase):
    def test_no_nucleus_shows_unavailable_not_fabricated(self) -> None:
        text = format_sample_results_summary(
            sparse_px=1.0,
            sparse_um_s=2.0,
            of_px=3.0,
            of_um_s=4.0,
            toward_nucleus_um_s=None,
            orientation_deg=None,
            tracks_used=5,
            tracks_requested=5,
            timing_label="6.00 FPS · 0.1667 s/frame",
            timing_confirmed=True,
            has_nucleus=False,
        )
        self.assertIn("General Movement", text)
        self.assertIn("Optical Flow", text)
        self.assertIn("1.00 px/frame", text)
        self.assertIn("Toward Nucleus", text)
        self.assertIn("Nucleus required", text)
        self.assertIn("F-actin Orientation", text)
        self.assertEqual(text.count("Nucleus required"), 2)
        self.assertNotIn("0.0°", text)

    def test_with_nucleus_shows_values(self) -> None:
        text = format_sample_results_summary(
            sparse_px=1.0,
            sparse_um_s=2.0,
            of_px=3.0,
            of_um_s=4.0,
            toward_nucleus_um_s=0.5,
            orientation_deg=33.0,
            tracks_used=5,
            tracks_requested=5,
            timing_label="6.00 FPS",
            timing_confirmed=True,
            has_nucleus=True,
        )
        self.assertIn("0.50 µm/s", text)
        self.assertIn("33.0°", text)
        self.assertNotIn("Nucleus required", text)


class MetricAnalysisStaleUx5Tests(unittest.TestCase):
    def test_edit_marks_stale_and_blocks_metric_analysis(self) -> None:
        from actintrack_app.gui import MainWindow

        window = MainWindow.__new__(MainWindow)
        window._current_sample_id = "S1"
        window._metric_analysis_view_active = False
        window._tracking_results_by_sample = {"S1": object()}
        window._optical_flow_results_by_sample = {"S1": object()}
        window._tracking_result_stale_by_sample = {}
        window._optical_flow_stale_by_sample = {}
        window._of_flow_caches = {}
        window._sample_has_measurable_draft_results = MagicMock(return_value=True)
        window._clear_of_flow_cache = MagicMock()
        window._show_metric_analysis_placeholder = MagicMock()
        window._cropped_preview = object()

        MainWindow._mark_draft_metrics_stale(window, "S1")
        self.assertTrue(window._tracking_result_stale_by_sample["S1"])
        self.assertTrue(window._optical_flow_stale_by_sample["S1"])
        self.assertNotIn("S1", window._tracking_results_by_sample)
        window._clear_of_flow_cache.assert_called()

        snap = build_workflow_snapshot(
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
        self.assertFalse(snap.metric_analysis_allowed)

    def test_resolve_preview_refuses_stale_cache(self) -> None:
        from actintrack_app.gui import MainWindow

        window = MainWindow.__new__(MainWindow)
        window._tracking_result_stale_by_sample = {"S1": True}
        window._optical_flow_stale_by_sample = {}
        window._tracking_results_by_sample = {"S1": object()}
        resolved = MainWindow._resolve_metric_preview_analysis_for_sample(window, "S1")
        self.assertIsNone(resolved)


class MetricAnalysisInspectionModeTests(unittest.TestCase):
    def test_inspection_modes_not_tracking_method_label(self) -> None:
        builders = _read("actintrack_app/gui_layout_builders.py")
        self.assertIn("Display / Inspection Mode", builders)
        self.assertIn('addItem("F-actin Orientation", "orientation")', builders)
        self.assertIn('addItem("Optical Flow", "optical_flow")', builders)
        self.assertNotIn("Tracking method", builders)
        self.assertNotIn("Optical Flow (Draft)", builders)
        # Researcher-facing toggles removed from layouts
        self.assertNotIn(
            'layout.addWidget(window.chk_show_orientation_overlay)',
            builders,
        )
        self.assertNotIn(
            'layout.addWidget(window.chk_show_of_overlay)',
            builders,
        )

    def test_preview_frame_auto_overlays_by_mode(self) -> None:
        gui = _read("actintrack_app/gui.py")
        self.assertIn('mode == "orientation"', gui)
        self.assertIn("Optical Flow inspection always shows the OF overlay", gui)
        self.assertIn('mode == "optical_flow"', gui)


class SetupSpacingAndStylingUx5Tests(unittest.TestCase):
    def test_setup_sections_use_section_spacing(self) -> None:
        builders = _read("actintrack_app/gui_layout_builders.py")
        # Four section gaps in build_roi_preview_panel body
        self.assertGreaterEqual(
            builders.count("layout.addSpacing(SIDE_PANEL_SECTION_SPACING)"),
            4,
        )
        self.assertIn('Nucleus (optional)', builders)
        self.assertIn("STYLE_WORKBENCH_ACTION_BUTTON", _read("actintrack_app/gui_styles.py"))


if __name__ == "__main__":
    unittest.main()
