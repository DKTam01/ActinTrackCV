# Bundled resources

Read-only resources that future packaging specs (PyInstaller, etc.) must include
so the frozen app can find them via `actintrack_app.paths.resource_path(...)`.

These are resolved relative to `resource_root()`:
- in development → source repo root
- when frozen → PyInstaller's `sys._MEIPASS`

## Asset layout

```text
packaging/assets/
  app/
    actintrackcv.png      ← runtime window/app icon (QIcon)
    actintrackcv.ico      ← TODO (Windows .exe / installer icon)
    actintrackcv.icns     ← TODO (macOS .app bundle icon)
  screenshots/            ← reserved for future docs screenshots
```

## Must bundle
- `README.md` — shown by Help → How to Run.
- `packaging/assets/app/actintrackcv.png` — runtime window/app icon (QIcon).

## Icon assets
- `packaging/assets/app/actintrackcv.png` — present (final app icon).
- `packaging/assets/app/actintrackcv.ico` — TODO (Windows .exe / installer icon).
- `packaging/assets/app/actintrackcv.icns` — TODO (macOS .app bundle icon).

The `.png` is used at runtime by Qt. The `.ico`/`.icns` are needed by the
installer/bundle steps in a later phase and are not loaded by the running app.
The Windows spec wires the `.ico` into the EXE automatically once the file
exists; until then the EXE uses the default PyInstaller icon.

> No installer scripts live here yet — that is a later phase.
