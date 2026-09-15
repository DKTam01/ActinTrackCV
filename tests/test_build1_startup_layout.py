"""BUILD1 — startup layout and Explorer usability regression coverage."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication

from actintrack_app.gui import MainWindow
from actintrack_app.gui_layout_builders import (
    DEFAULT_SPLITTER_SIZES,
    LEFT_PANEL_INVALID_WIDTH,
    LEFT_PANEL_MIN_WIDTH,
    sanitize_main_splitter_sizes,
)
from actintrack_app.gui_styles import (
    apply_application_design_system,
    build_application_palette,
)
from actintrack_app.project_manager import create_project_structure


def _qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class SanitizeSplitterSizesTests(unittest.TestCase):
    def test_defaults_when_missing_or_short(self) -> None:
        self.assertEqual(
            sanitize_main_splitter_sizes(None), list(DEFAULT_SPLITTER_SIZES)
        )
        self.assertEqual(
            sanitize_main_splitter_sizes([10]), list(DEFAULT_SPLITTER_SIZES)
        )

    def test_rejects_near_zero_explorer_width(self) -> None:
        bad = sanitize_main_splitter_sizes([5, 1200])
        self.assertEqual(bad[0], LEFT_PANEL_MIN_WIDTH)
        self.assertGreaterEqual(bad[0], LEFT_PANEL_INVALID_WIDTH)

    def test_preserves_valid_researcher_resize(self) -> None:
        sizes = sanitize_main_splitter_sizes([260, 1000])
        self.assertEqual(sizes[0], 260)
        self.assertEqual(sizes[1], 1000)

    def test_enforces_explorer_minimum(self) -> None:
        sizes = sanitize_main_splitter_sizes([80, 1000])
        # 80 is above invalid_below(40) but below contract minimum → floor.
        self.assertEqual(sizes[0], LEFT_PANEL_MIN_WIDTH)


class StartupExplorerLayoutTests(unittest.TestCase):
    """Instantiate real MainWindow; Explorer must be usable after show."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qapp()
        apply_application_design_system(cls.app)

    def _open_window(self, root: Path) -> MainWindow:
        create_project_structure(root)
        with patch(
            "actintrack_app.gui.default_workspace_root", return_value=root
        ), patch("actintrack_app.gui.DEFAULT_SOURCE_ROOT", root):
            return MainWindow()

    def test_startup_explorer_has_usable_width_and_loads_workspace(self) -> None:
        from actintrack_app.condition_group_manager import (
            create_condition_group,
            list_condition_group_records,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ws"
            create_project_structure(root)
            create_condition_group(root, "BUILD1 Control")
            self.assertGreaterEqual(len(list_condition_group_records(root)), 1)
            with patch(
                "actintrack_app.gui.default_workspace_root", return_value=root
            ), patch("actintrack_app.gui.DEFAULT_SOURCE_ROOT", root):
                win = MainWindow()
            try:
                win.resize(1280, 720)
                win.show()
                for _ in range(5):
                    self.app.processEvents()

                sidebar = win._left_sidebar
                splitter = win._main_splitter
                self.assertTrue(sidebar.isVisible())
                self.assertGreaterEqual(sidebar.width(), LEFT_PANEL_MIN_WIDTH)
                self.assertGreaterEqual(sidebar.minimumWidth(), LEFT_PANEL_MIN_WIDTH)
                sizes = splitter.sizes()
                self.assertGreaterEqual(sizes[0], LEFT_PANEL_MIN_WIDTH)
                self.assertGreater(
                    sizes[0],
                    LEFT_PANEL_INVALID_WIDTH,
                    "Explorer pane must not be a near-zero strip",
                )
                self.assertGreater(win._center_stack.width(), 100)
                self.assertIsNotNone(win._project_root)
                self.assertGreaterEqual(win.tree_samples.topLevelItemCount(), 1)
                self.assertGreaterEqual(len(win.menuBar().actions()), 1)

                # Guard the exact MEDIA1 regression: startup must not live in closeEvent.
                src = (
                    Path(__file__).resolve().parents[1]
                    / "actintrack_app"
                    / "gui.py"
                )
                text = src.read_text(encoding="utf-8")
                close_idx = text.index("def closeEvent")
                close_block = text[close_idx : close_idx + 350]
                self.assertNotIn("_load_project", close_block)
                self.assertNotIn("setup_application_menus", close_block)
            finally:
                win.close()
                self.app.processEvents()

    def test_empty_workspace_shows_explorer_hint_not_collapse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ws"
            win = self._open_window(root)
            try:
                win.resize(1280, 720)
                win.show()
                for _ in range(5):
                    self.app.processEvents()
                self.assertGreaterEqual(win._left_sidebar.width(), LEFT_PANEL_MIN_WIDTH)
                self.assertTrue(win.lbl_explorer_empty.isVisible())
                self.assertEqual(win.tree_samples.topLevelItemCount(), 0)
            finally:
                win.close()
                self.app.processEvents()

    def test_near_zero_restored_sizes_recover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ws"
            win = self._open_window(root)
            try:
                win.resize(1280, 720)
                win.show()
                self.app.processEvents()
                win._main_splitter.setSizes([8, 1200])
                win._ensure_main_splitter_layout(preferred_sizes=[8, 1200])
                self.app.processEvents()
                self.assertGreaterEqual(
                    win._main_splitter.sizes()[0], LEFT_PANEL_MIN_WIDTH
                )
                self.assertGreaterEqual(
                    win._left_sidebar.width(), LEFT_PANEL_MIN_WIDTH
                )
            finally:
                win.close()
                self.app.processEvents()

    def test_window_resize_does_not_collapse_explorer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ws"
            win = self._open_window(root)
            try:
                for size in ((1280, 720), (1100, 700), (1600, 900), (960, 600)):
                    win.resize(*size)
                    win.show()
                    for _ in range(3):
                        self.app.processEvents()
                    win._ensure_main_splitter_layout()
                    self.app.processEvents()
                    self.assertGreaterEqual(
                        win._left_sidebar.width(),
                        LEFT_PANEL_MIN_WIDTH,
                        msg=f"collapsed at {size}",
                    )
                    self.assertGreater(win._center_stack.width(), 50)
            finally:
                win.close()
                self.app.processEvents()


class DesignSystemInitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _qapp()

    def test_palette_roles_are_populated(self) -> None:
        palette = build_application_palette()
        self.assertTrue(bool(palette.color(QPalette.ColorRole.Window).name()))
        self.assertTrue(bool(palette.color(QPalette.ColorRole.Text).name()))
        self.assertTrue(bool(palette.color(QPalette.ColorRole.Highlight).name()))

    def test_apply_design_system_is_idempotent_enough(self) -> None:
        apply_application_design_system(self.app)
        sheet = self.app.styleSheet() or ""
        self.assertIn("QMenu", sheet)
        apply_application_design_system(self.app)
        self.assertTrue(bool(self.app.styleSheet()))


if __name__ == "__main__":
    unittest.main()
