"""Filesystem path helpers for development and frozen (packaged) runs.

Separates read-only bundled resources from user-writable workspace data so the
app never tries to write into its installation directory (Program Files, a
macOS ``.app`` bundle, PyInstaller's ``_internal`` / ``_MEIPASS``) when frozen.
"""

from __future__ import annotations

import sys
from pathlib import Path

#: Folder name used for the default user-writable workspace.
WORKSPACE_DIR_NAME = "ActinTrackCV"

#: Runtime icon candidates (relative to ``resource_root()``), preferred first.
#: PNG/ICO are usable by ``QIcon`` at runtime; ``.icns`` is bundle-only.
ICON_CANDIDATES = (
    ("packaging", "assets", "app", "actintrackcv.png"),
    ("packaging", "assets", "app", "actintrackcv.ico"),
)


def is_frozen() -> bool:
    """True when running from a frozen build (PyInstaller, etc.)."""
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """Source repository root (the directory containing ``actintrack_app``)."""
    return Path(__file__).resolve().parents[1]


def resource_root() -> Path:
    """Base directory for read-only bundled resources.

    Frozen: PyInstaller's extraction directory (``sys._MEIPASS``) when present,
    otherwise the executable's folder. Development: the source repository root.
    """
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return app_root()


def resource_path(*parts: str) -> Path:
    """Path to a read-only bundled resource, e.g. ``resource_path("README.md")``."""
    return resource_root().joinpath(*parts)


def _documents_dir() -> Path | None:
    docs = Path.home() / "Documents"
    return docs if docs.is_dir() else None


def default_workspace_root() -> Path:
    """User-writable default workspace directory, created if missing.

    Prefers ``~/Documents/ActinTrackCV``; falls back to ``~/ActinTrackCV``;
    last resort is the home directory. Never the installation directory.
    """
    candidates: list[Path] = []
    docs = _documents_dir()
    if docs is not None:
        candidates.append(docs / WORKSPACE_DIR_NAME)
    candidates.append(Path.home() / WORKSPACE_DIR_NAME)
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue
    # Home always exists; project-creation errors are handled by the caller.
    return Path.home()


def default_source_root() -> Path:
    """Initial directory for the Add Sample file picker.

    User Documents when available, otherwise the home directory. Never inside
    the application bundle.
    """
    docs = _documents_dir()
    return docs if docs is not None else Path.home()


def icon_path() -> Path | None:
    """Path to a runtime ``QIcon``-compatible app icon, or ``None`` if missing.

    Resolves bundled icon assets through :func:`resource_path` so it works both
    in development and in frozen builds.
    """
    for parts in ICON_CANDIDATES:
        candidate = resource_path(*parts)
        if candidate.is_file():
            return candidate
    return None
