#!/usr/bin/env python3
"""Local IMAGE sample-selection stage benchmark (not a CI wall-clock gate).

Profiles Explorer selection of persisted IMAGE samples: decode, orientation,
CellRegion load vs regenerate, overlay rasterization, Qt pixmap conversion.

Reports dimensions/dtype and stage wall times for JPG/PNG/TIFF plus a large
and a 16-bit TIFF when generated locally.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import cv2
import numpy as np
import tifffile
from PyQt6.QtWidgets import QApplication

from actintrack_app.cell_detection import suggest_conservative_cell_region
from actintrack_app.condition_group_manager import create_condition_group
from actintrack_app.gui import MainWindow
from actintrack_app.gui_styles import apply_application_design_system
from actintrack_app.metadata import get_sample_annotation
from actintrack_app.project_manager import create_project_structure
from actintrack_app.sample_service import create_samples_from_data_files
from actintrack_app.scientific_annotations import valid_mask_crop_local
from actintrack_app.video_processing import load_image, load_media_frame


def _write_jpg(path: Path, h: int, w: int) -> None:
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[h // 8 : h * 7 // 8, w // 8 : w * 7 // 8] = (40, 200, 180)
    cv2.imwrite(str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])


def _write_png(path: Path, h: int, w: int) -> None:
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[h // 8 : h * 7 // 8, w // 8 : w * 7 // 8] = (30, 210, 40)
    cv2.imwrite(str(path), frame)


def _write_tiff_u8(path: Path, h: int, w: int) -> None:
    arr = np.zeros((h, w), dtype=np.uint8)
    arr[h // 8 : h * 7 // 8, w // 8 : w * 7 // 8] = 200
    tifffile.imwrite(str(path), arr)


def _write_tiff_u16(path: Path, h: int, w: int) -> None:
    arr = np.zeros((h, w), dtype=np.uint16)
    arr[h // 8 : h * 7 // 8, w // 8 : w * 7 // 8] = 40000
    tifffile.imwrite(str(path), arr)


class StageProbe:
    def __init__(self) -> None:
        self.counts: dict[str, int] = defaultdict(int)
        self.ms: dict[str, list[float]] = defaultdict(list)
        self._orig: list[tuple[Any, str, Any]] = []

    def wrap(self, obj: Any, name: str, label: str | None = None) -> None:
        orig = getattr(obj, name)
        key = label or name

        def wrapped(*args: Any, **kwargs: Any):
            self.counts[key] += 1
            t0 = time.perf_counter()
            try:
                return orig(*args, **kwargs)
            finally:
                self.ms[key].append((time.perf_counter() - t0) * 1000.0)

        setattr(obj, name, wrapped)
        self._orig.append((obj, name, orig))

    def wrap_fn(self, module: Any, name: str, label: str | None = None) -> Callable:
        orig = getattr(module, name)
        key = label or name

        def wrapped(*args: Any, **kwargs: Any):
            self.counts[key] += 1
            t0 = time.perf_counter()
            try:
                return orig(*args, **kwargs)
            finally:
                self.ms[key].append((time.perf_counter() - t0) * 1000.0)

        setattr(module, name, wrapped)
        self._orig.append((module, name, orig))
        return wrapped

    def reset(self) -> None:
        self.counts.clear()
        self.ms.clear()

    def restore(self) -> None:
        for obj, name, orig in reversed(self._orig):
            setattr(obj, name, orig)
        self._orig.clear()

    def report(self, title: str) -> None:
        print(f"  {title}")
        if not self.counts:
            print("    (no instrumented calls)")
            return
        for key in sorted(self.counts):
            times = self.ms[key]
            total = sum(times)
            print(
                f"    {key:36s} n={self.counts[key]:3d}  "
                f"total={total:7.1f} ms  last={times[-1]:7.1f} ms"
            )


def _instrument(window: MainWindow, probe: StageProbe) -> None:
    import actintrack_app.gui as gui_mod
    import actintrack_app.video_processing as vp
    import actintrack_app.orientation as orient
    import actintrack_app.scientific_annotations as sa
    import actintrack_app.timing_provenance as tp
    import actintrack_app.cell_detection as cd
    import actintrack_app.metadata as meta

    probe.wrap(window, "_load_sample_from_tree_item")
    probe.wrap(window, "_load_sample_data_context")
    probe.wrap(window, "_apply_annotation_from_dict")
    probe.wrap(window, "_ensure_cell_first_setup")
    probe.wrap(window, "_refresh_display")
    probe.wrap(window, "_oriented_frame")
    probe.wrap(window, "_sync_scientific_overlay")
    probe.wrap(window, "_autosave_roi")
    probe.wrap(window, "_ensure_timing_for_current_sample")
    probe.wrap(window, "reset_preview_state")
    probe.wrap(window, "update_tracking_result_panel")
    probe.wrap(window.canvas, "_update_pixmap")
    probe.wrap(window.canvas, "set_frame")
    probe.wrap(window.canvas, "set_scientific_overlay")
    probe.wrap_fn(gui_mod, "load_media_frame", "gui.load_media_frame")
    probe.wrap_fn(gui_mod, "suggest_conservative_cell_region", "gui.suggest_cell")
    probe.wrap_fn(gui_mod, "prepare_cell_signal", "gui.prepare_cell_signal")
    probe.wrap_fn(gui_mod, "probe_video_playback_fps", "gui.probe_fps")
    probe.wrap_fn(gui_mod, "apply_orientation", "gui.apply_orientation")
    probe.wrap_fn(gui_mod, "valid_mask_crop_local", "gui.valid_mask")
    probe.wrap_fn(vp, "load_image", "vp.load_image")
    probe.wrap_fn(vp, "load_media_frame", "vp.load_media_frame")
    probe.wrap_fn(cd, "suggest_conservative_cell_region", "cd.suggest_cell")
    probe.wrap_fn(cd, "prepare_cell_signal", "cd.prepare_cell_signal")
    probe.wrap_fn(orient, "apply_orientation", "apply_orientation")
    probe.wrap_fn(sa, "valid_mask_crop_local", "valid_mask_crop_local")
    probe.wrap_fn(tp, "probe_video_playback_fps", "probe_fps")
    probe.wrap_fn(meta, "get_sample_annotation", "get_sample_annotation")
    _ = (
        load_image,
        load_media_frame,
        suggest_conservative_cell_region,
        valid_mask_crop_local,
        get_sample_annotation,
    )


def _select(window: MainWindow, sample_id: str) -> float:
    item = window._find_sample_tree_item(sample_id)
    if item is None:
        raise RuntimeError(f"sample not in tree: {sample_id}")
    t0 = time.perf_counter()
    window.tree_samples.setCurrentItem(item)
    QApplication.processEvents()
    return (time.perf_counter() - t0) * 1000.0


def _describe_frame(path: Path) -> str:
    frame = load_image(path)
    raw_note = ""
    if path.suffix.lower() in {".tif", ".tiff"}:
        with tifffile.TiffFile(str(path)) as tif:
            arr = tif.pages[0].asarray()
            raw_note = f" raw_dtype={arr.dtype} raw_shape={arr.shape}"
    h, w = frame.shape[:2]
    return f"{w}x{h} decoded_dtype={frame.dtype}{raw_note}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--large-w", type=int, default=3200)
    parser.add_argument("--large-h", type=int, default=2400)
    args = parser.parse_args()

    app = QApplication.instance() or QApplication([])
    apply_application_design_system(app)

    tmp = tempfile.TemporaryDirectory(prefix="actintrack-perf2-")
    root = Path(tmp.name)
    create_project_structure(root)
    gid = create_condition_group(root, "WT").id
    src = root / "src"
    src.mkdir()

    specs = [
        ("cell.jpg", lambda p: _write_jpg(p, 480, 640)),
        ("cell.png", lambda p: _write_png(p, 480, 640)),
        ("cell.tif", lambda p: _write_tiff_u8(p, 480, 640)),
        ("large.png", lambda p: _write_png(p, args.large_h, args.large_w)),
        ("u16.tiff", lambda p: _write_tiff_u16(p, 800, 1000)),
    ]
    paths = []
    print("SOURCE FILES")
    for name, writer in specs:
        path = src / name
        writer(path)
        print(f"  {name}: {path.stat().st_size} bytes  {_describe_frame(path)}")
        paths.append(path)

    results = create_samples_from_data_files(root, gid, paths)
    ids = []
    for result, spec in zip(results, specs):
        if not result.succeeded or result.row is None:
            print(f"IMPORT FAILED {spec[0]}: {result.error}")
            return 1
        ids.append(str(result.row["sample_id"]))
        print(f"  imported {spec[0]} -> {ids[-1]}")

    from unittest.mock import patch

    with patch("actintrack_app.gui.default_workspace_root", return_value=root), patch(
        "actintrack_app.gui.DEFAULT_SOURCE_ROOT", root
    ):
        window = MainWindow()
    window._load_project(root, "PERF2 benchmark")
    window.show()
    QApplication.processEvents()

    probe = StageProbe()
    _instrument(window, probe)

    labels = [spec[0] for spec in specs]
    print("\nFIRST SELECTION (may generate CellRegion if missing)")
    for sid, label in zip(ids, labels):
        probe.reset()
        ms = _select(window, sid)
        cell = window._cell_region
        print(
            f"\n{label} ({sid}) wall={ms:.1f} ms  "
            f"cell={'present' if cell is not None else 'NONE'}  "
            f"suggest_n={probe.counts.get('gui.suggest_cell', 0)}"
        )
        probe.report("stages")

    print("\nPERSISTED RESELECTION A→B→A AND SAME-SAMPLE")
    a_id, b_id = ids[1], ids[2]  # png, tif
    sequences = [
        ("PNG first after other", a_id, "cell.png"),
        ("TIFF A→B", b_id, "cell.tif"),
        ("PNG B→A", a_id, "cell.png"),
        ("PNG same-sample", a_id, "cell.png"),
        ("large PNG", ids[3], "large.png"),
        ("16-bit TIFF", ids[4], "u16.tiff"),
        ("16-bit TIFF reselect", ids[4], "u16.tiff"),
        ("JPG after 16-bit", ids[0], "cell.jpg"),
        ("JPG same-sample", ids[0], "cell.jpg"),
    ]
    # Switch away so first of each pair is a real change.
    _select(window, ids[0])
    for title, sid, label in sequences:
        probe.reset()
        ms = _select(window, sid)
        print(
            f"\n{title} [{label}] wall={ms:.1f} ms  "
            f"suggest_n={probe.counts.get('gui.suggest_cell', 0)}  "
            f"load_media_n={probe.counts.get('gui.load_media_frame', 0)}  "
            f"pixmap_n={probe.counts.get('_update_pixmap', 0)}  "
            f"autosave_n={probe.counts.get('_autosave_roi', 0)}  "
            f"overlay_n={probe.counts.get('_sync_scientific_overlay', 0)}"
        )
        probe.report("stages")

    probe.restore()
    window.close()
    tmp.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
