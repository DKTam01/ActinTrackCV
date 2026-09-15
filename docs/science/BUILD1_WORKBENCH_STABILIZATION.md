# BUILD1 — Post-MEDIA1 Workbench Stabilization

## Regression

MEDIA1 commit `d4c0242` inserted `closeEvent` above the existing
`MainWindow.__init__` startup tail. That accidentally moved:

- `setup_application_menus`
- `_load_project(self._workspace_root, …)`

into `closeEvent`. Startup therefore painted an empty Explorer (workspace
label `—` only) with no menus and no Condition Groups — which looked like a
collapsed left pane.

Fusion / global QSS were **not** the root cause. They remain for cross-platform
visual consistency; Explorer width is owned by splitter + `LEFT_PANEL_MIN_WIDTH`
contracts and `sanitize_main_splitter_sizes`.

## Fix

Startup belongs in `__init__` again. `closeEvent` only closes modeless
measurement inspectors. Near-zero restored splitter sizes recover to defaults
without discarding valid researcher resize (≥ 200 px Explorer).
