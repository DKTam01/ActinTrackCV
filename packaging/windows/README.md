# Windows build (PyInstaller, one-folder)

Builds a debuggable one-folder, windowed Windows app. No installer yet.

> **Status:** scaffolded but **not yet validated**. The current pre-release focus
> is macOS (see `packaging/macos/`). This Windows build is a future validation
> target and has not been run/verified on a clean Windows machine.

## Prerequisites

- Windows 10/11
- Python 3.10+ on PATH
- Build environment (runtime deps + PyInstaller):

```powershell
python -m pip install -r requirements-build.txt
```

This installs `requirements.txt` plus `pyinstaller`. The build script verifies
PyInstaller is present but does not install anything for you.

## Build

From the repo root (or anywhere — the script locates the root):

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build_windows.ps1
```

Output: `dist\ActinTrackCV\ActinTrackCV.exe`

## What gets bundled

- `README.md` → bundle root, read via `resource_path("README.md")`.
- `packaging/assets/app/actintrackcv.png` → `packaging/assets/app/`, read via `icon_path()`.
- OpenCV FFmpeg/videoio DLLs (`collect_dynamic_libs("cv2")`) for AVI/MP4.

Frozen builds resolve resources under PyInstaller's `sys._MEIPASS` via
`actintrack_app.paths.resource_root()`.

## What is NOT bundled (by design)

User/project data stays in the workspace at runtime, not in the app:
`raw/`, `processed/`, `previews/`, `metadata/`, `raw_source/`, `frames/`, sample
videos. First launch creates/uses `~/Documents/ActinTrackCV`.

## TODO before the installer phase

- Add `packaging/assets/app/actintrackcv.ico` (the spec wires the EXE icon
  automatically once the file exists).
- Manually validate AVI/MP4 loading on a clean Windows VM without Python.
