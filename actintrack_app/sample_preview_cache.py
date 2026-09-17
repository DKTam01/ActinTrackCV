"""Small current/recent-sample cache for decoded scientific frames.

Persisted annotations remain authoritative and are not stored here. Callers
reload CellRegion / cutoff / nucleus from the project, then reuse immutable
decoded pixels when the source file identity has not changed.

Bound: at most two full-resolution frames (current + previous sample).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


def source_file_identity(path: Path) -> tuple[str, int, int] | None:
    """Return ``(resolved_path, mtime_ns, size)`` or None if the file is missing."""
    try:
        resolved = Path(path).resolve()
        stat = resolved.stat()
    except OSError:
        return None
    mtime_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1e9)))
    return (str(resolved), mtime_ns, int(stat.st_size))


@dataclass
class CachedSampleMedia:
    sample_id: str
    path_key: str
    mtime_ns: int
    size: int
    frame: np.ndarray
    frame_index: int
    total_frames: int
    validity_mask: np.ndarray | None = None
    validity_key: tuple | None = None


class SampleMediaCache:
    """LRU of decoded scientific frames for at most ``max_entries`` samples."""

    def __init__(self, max_entries: int = 2) -> None:
        self.max_entries = max(1, int(max_entries))
        self._entries: dict[str, CachedSampleMedia] = {}
        self._order: list[str] = []

    def __len__(self) -> int:
        return len(self._entries)

    def peek(self, sample_id: str) -> CachedSampleMedia | None:
        return self._entries.get(str(sample_id))

    def get(
        self,
        sample_id: str,
        path: Path,
        *,
        frame_index: int | None = None,
    ) -> CachedSampleMedia | None:
        identity = source_file_identity(path)
        if identity is None:
            return None
        path_key, mtime_ns, size = identity
        entry = self._entries.get(sample_id)
        if entry is None:
            return None
        if (
            entry.path_key != path_key
            or entry.mtime_ns != mtime_ns
            or entry.size != size
        ):
            self.invalidate(sample_id)
            return None
        if frame_index is not None and int(entry.frame_index) != int(frame_index):
            return None
        self._touch(sample_id)
        return entry

    def put(self, entry: CachedSampleMedia) -> None:
        sid = str(entry.sample_id)
        self._entries[sid] = entry
        self._touch(sid)
        while len(self._order) > self.max_entries:
            evict = self._order.pop(0)
            if evict != sid:
                self._entries.pop(evict, None)

    def store_validity_mask(
        self,
        sample_id: str,
        mask: np.ndarray,
        key: tuple,
    ) -> None:
        entry = self._entries.get(sample_id)
        if entry is None:
            return
        entry.validity_mask = mask
        entry.validity_key = key

    def invalidate(self, sample_id: str) -> None:
        sid = str(sample_id)
        self._entries.pop(sid, None)
        if sid in self._order:
            self._order.remove(sid)

    def clear(self) -> None:
        self._entries.clear()
        self._order.clear()

    def _touch(self, sample_id: str) -> None:
        if sample_id in self._order:
            self._order.remove(sample_id)
        self._order.append(sample_id)
