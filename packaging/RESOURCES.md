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
    actintrackcv.ico      ← Windows .exe / installer icon
    actintrackcv.icns     ← macOS .app bundle icon
  screenshots/            ← reserved for future docs screenshots
```

## Must bundle
- `README.md` — shown by Help → How to Run.
- `packaging/assets/app/actintrackcv.png` — runtime window/app icon (QIcon).

## Icon assets
- `packaging/assets/app/actintrackcv.png` — present (final app icon).
- `packaging/assets/app/actintrackcv.ico` — present (Windows .exe icon).
- `packaging/assets/app/actintrackcv.icns` — present (macOS .app bundle icon).

The `.png` is used at runtime by Qt. The `.ico`/`.icns` are consumed by the
platform build steps and are not normally loaded by the running app. The Windows
spec embeds the `.ico` into the EXE (and bundles it as a runtime fallback); the
macOS spec wires the `.icns` into the `.app` bundle.

## Platform builds

- **macOS** — PyInstaller `.app` bundle (`packaging/macos/`):
  `dist/ActinTrackCV.app`. Unsigned/un-notarized for now (Gatekeeper warning;
  right-click → Open for internal builds). `.dmg`, code signing, and notarization
  are future work.
- **Windows** — PyInstaller one-folder build (`packaging/windows/`, output
  `dist/ActinTrackCV/ActinTrackCV.exe`), packaged as a zip pre-release. Must be
  built on Windows 10/11 x64 (no cross-compile). Unsigned (SmartScreen warning;
  More info → Run anyway). Installer wizard and code signing are future work.

Both bundle `README.md` and `packaging/assets/app/actintrackcv.png`, and neither
bundles user/project data folders.

> No `.dmg` or installer-wizard scripts live here yet — those are later phases.
