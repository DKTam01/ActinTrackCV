# PERF2 — IMAGE selection reuse, mixed-media groups, Explorer drop feedback

PERF2 addresses Explorer lag when selecting an already-imported IMAGE sample,
keeps mixed VIDEO+IMAGE Condition Groups first-class, and adds external
drag/drop target highlighting.

Scientific freeze as of PERF2: 60 s/frame protocol timing, motion/optical-flow/
orientation formulas, CellRegion segmentation algorithm, cutoff/nucleus
semantics, MEDIA1 capability matrix. CAL1 later added per-sample acquisition
interval and µm/pixel; see `CAL1_SCIENTIFIC_CALIBRATION.md`.

## IMAGE selection pipeline (audit)

Explorer click → `currentItemChanged` / `_load_sample_from_tree_item` →
sample lookup → `load_media_frame` / decode cache → dtype conversion inside
`video_processing` → `apply_orientation` → load persisted annotation
(CellRegion, cutoff, nucleus, orientation) → display validity mask
(`valid_mask_crop_local`) → QImage/QPixmap → canvas.

Import and selection are separate. First import may decode, suggest CellRegion,
and persist. Later selection loads persisted scientific state and renders.

## CellRegion on selection

A persisted valid CellRegion is **loaded**, not scientifically regenerated.

| Action | CellRegion segmentation? |
| --- | --- |
| Select already-imported IMAGE with persisted CellRegion | No |
| IMAGE A → IMAGE B → IMAGE A (unchanged source/annotations) | No (A is reloaded from disk + decode cache) |
| VIDEO → IMAGE → VIDEO | No (IMAGE CellRegion is not a VIDEO path) |
| Click already-selected sample | No load; preview left as-is |
| First-time sample / missing CellRegion | Yes (`suggest_conservative_cell_region`) |
| Cell Boundary Tighter/Broader | Yes (`regenerate_cell=True`) |
| Replace source / orientation change that invalidates coordinates | Yes after invalidation; decode cache dropped on replace |

Selection alone does not invalidate scientific state. Disk/project annotations
remain authoritative; the decode cache never stores CellRegion/cutoff/nucleus.

## Bottleneck (before)

Persisted IMAGE reselection (~640×480) was dominated by **display overlay
rasterization**, not CellRegion segmentation:

- `suggest_conservative_cell_region` count = 0
- `valid_mask_crop_local` ran ~3× per selection (~115 ms each at 640×480) via
  a Python per-pixel `pointPolygonTest` loop over the **full frame**
- duplicate pixmap rebuilds, IMAGE FPS probing, and selection autosave added
  smaller costs
- large 3200×2400 PNG was ~10 s, almost entirely the same full-frame mask
- same-sample click was already ~0.5–1 ms (no reload)

## After (local benchmark, not a CI gate)

640×480 uint8 JPG/PNG/TIFF persisted reselection: **~109–114 ms** (suggest=0,
autosave=0). IMAGE A→B→A decode cache hit on return (`load_media_frame` n=0).
Same-sample click: **~0.4–0.9 ms**. First-time PNG/TIFF (CellRegion generate +
persist): **~162–165 ms**. 16-bit 1000×800 TIFF persisted: **~143 ms**. Large
3200×2400 PNG first-time **~968 ms** (was ~10 s); persisted **~496 ms**, now
dominated by Qt pixmap conversion (~340 ms), not CellRegion or mask fill.

No QThread. Typical lab IMAGE selection stays synchronous. Very large stills
remain display-bound on pixmap conversion.

## Optimization architecture

1. **Scanline polygon rasterize** (`region._rasterize_polygon_mask`) with a
   cheap inclusive on-edge pass. Pixel-identical to the scalar OpenCV
   `pointPolygonTest >= 0` reference (`_rasterize_polygon_mask_reference`).
2. **Coalesce display updates** (`ImageCanvas.begin_display_update` /
   `end_display_update`) so one selection rebuilds the pixmap once.
3. **Reuse decoded scientific frames** in a 2-slot LRU (`SampleMediaCache`).
4. **Cache oriented frames** keyed by `(id(base_frame), orientation)`.
5. **Cache display validity masks** on the current cached sample entry,
   keyed by sample id + CellRegion geometry + cutoff + size.
6. **Skip same-sample reload** when Explorer re-clicks the current sample.
7. **Skip IMAGE FPS probe and selection autosave** (`persist_observed=False`
   on persisted annotation load).

No QThread. After eliminating redundant work, selection stays synchronous.

## Scientific vs display cache

| Layer | What | Key | Invalidation | Bound |
| --- | --- | --- | --- | --- |
| Decoded scientific frame | `load_media_frame` uint8 BGR | sample_id + resolved path + mtime_ns + size + frame index | source replace, mtime/size change, LRU eviction | 2 samples |
| Oriented scientific frame | `apply_orientation(decoded)` | `id(base_frame)` + orientation tuple | new base frame or orientation change | 1 current |
| Display validity mask | overlay raster of CellRegion/cutoff | sample + geometry + cutoff + (w,h) | CellRegion/cutoff/size change; follows decode entry | stored on current cache entry |
| Rendered pixmap | Qt preview | canvas dirty flag | coalesced end of display update | current canvas only |

Display-normalized / pixmap state is never fed back into scientific analysis.
Annotations are always re-read from the project on sample load.

## Mixed-media Condition Groups

Condition Groups are biological conditions, not media-type containers.
Canonical import (`create_samples_from_data_files`, `classify_paths`,
`DATA_IMPORT_FILTER`) already accepts mixed AVI/MP4 + JPG/JPEG/PNG/TIF/TIFF
in one group. PERF2 adds regression coverage; no homogeneity rule was found
to remove.

Capabilities remain **per sample media type**. Analysis n is metric-specific:
VIDEO contributes General Movement / Optical Flow / Toward Nucleus; IMAGE
contributes Orientation. Unsupported combinations stay N/A, never zero.

## Explorer external-drop highlight

State is local to `ExplorerTreeWidget`:

- `current_external_drop_target` / `_external_drop_target_group_id`
- `_resolve_external_drop_target`
- `_apply_external_drop_highlight` / `_clear_external_drop_highlight`
- delegate role `EXPLORER_EXTERNAL_DROP_TARGET_ROLE`

Visual: slightly brighter group background (`#243040`) and a 1 px accent
outline (`#4a7fa3`). Highlight follows the group under the pointer, clears on
leave/drop/internal Sample MIME. Unsupported-only payloads are not highlighted.
Internal reorder MIME (`application/x-actintrack-sample-id`) never enters the
external highlight path.
