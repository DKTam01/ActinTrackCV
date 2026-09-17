#!/usr/bin/env python3
"""Local CellRegion stage benchmark (not part of unit-test thresholds).

Reports dimensions, frame count, and wall times for representative videos.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import cv2

from actintrack_app.cell_detection import (
    prepare_cell_signal,
    suggest_conservative_cell_region,
)
from actintrack_app.video_processing import get_video_frame_count, load_video_frame


def _benchmark(path: Path) -> None:
    t0 = time.perf_counter()
    n = get_video_frame_count(path)
    t_count = time.perf_counter()
    frame = load_video_frame(path, 0)
    t_load = time.perf_counter()
    prepared = prepare_cell_signal(frame)
    t_prep = time.perf_counter()
    cell = suggest_conservative_cell_region(
        frame, sensitivity=0.5, prepared=prepared
    )
    t_detect = time.perf_counter()
    for s in (0.0, 0.25, 0.5, 0.75, 1.0):
        suggest_conservative_cell_region(frame, sensitivity=s, prepared=prepared)
    t_sweep = time.perf_counter()
    h, w = frame.shape[:2]
    print(f"{path}")
    print(f"  size_bytes={path.stat().st_size}  frames={n}  {w}x{h}")
    print(f"  get_frame_count_ms={(t_count - t0) * 1000:.1f}")
    print(f"  load_frame0_ms={(t_load - t_count) * 1000:.1f}")
    print(f"  prepare_signal_ms={(t_prep - t_load) * 1000:.1f}")
    print(f"  detect_ms={(t_detect - t_prep) * 1000:.1f}  verts={len(cell.region.vertices or ())}")
    print(f"  sensitivity_sweep_5_ms={(t_sweep - t_detect) * 1000:.1f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "videos",
        nargs="*",
        type=Path,
        help="Video paths (default: testsamples AVIs)",
    )
    args = parser.parse_args()
    videos = list(args.videos)
    if not videos:
        root = Path(__file__).resolve().parents[1] / "testsamples"
        videos = sorted(p for p in root.rglob("*.avi") if "MAX" not in str(p))
        videos += sorted(root.rglob("*.mp4"))
    if not videos:
        print("No videos found.")
        return 1
    for path in videos:
        if not path.is_file():
            print(f"skip missing {path}")
            continue
        _benchmark(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
