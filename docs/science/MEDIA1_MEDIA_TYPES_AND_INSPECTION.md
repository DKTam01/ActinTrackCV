# MEDIA1 — Scientific media types, measurement inspection & import UX

Post-v1.0.0 researcher workflow.

## Media classes

| Media | Formats | Metrics |
|-------|---------|---------|
| **VIDEO** | `.avi`, `.mp4` | General Movement, Optical Flow, Toward Nucleus (nucleus required) |
| **IMAGE** | `.jpg`, `.jpeg`, `.tif`, `.tiff` | F-actin Orientation only (nucleus required) |

F-actin Orientation is **structural** (0° radial · 90° tangential), not movement direction. It is not computed for video samples in the normal workflow (no silent first-frame orientation).

Capability policy lives in `actintrack_app/media_capabilities.py`. Persist `media_type` at import.

## Import

- File picker multi-select and Explorer drag/drop of multiple files onto a **Condition Group**.
- Drop target determines destination group (not the previously selected group).
- Partial failures: successful files keep; one summary dialog for failures.
- Internal Sample reorder remains distinct from external file drops.

## TIFF intensity

Scientific TIFF pages may be 8-bit or 16-bit. Loading converts wider-than-uint8 arrays with an **explicit min–max stretch to uint8** before the shared BGR preview/science path (`video_processing._to_display_uint8`). This avoids silent low-byte truncation. Multi-page TIFF is treated as IMAGE (page 0 for orientation).

## Analysis → Show All Measurements

In Analysis → Sample Details, right-click a primary metric cell with a value:

**Show All Measurements**

Opens a **modeless** window bound to that sample’s persisted analysis run. Does not recompute science. Multiple inspectors may stay open. Closing the project/app closes them.

Contributing units (from the analysis run):

| Metric | One measurement | Sample scalar |
|--------|-----------------|---------------|
| General Movement | Valid track step | Mean of step µm/s |
| Toward Nucleus | Signed step | Time-weighted ΣΔd/Σdt |
| Optical Flow | Frame-pair mean magnitude | Mean of pair means → µm/s |
| F-actin Orientation | Local angle sample | Median angle (°) |

## Packaging note

Frozen builds must continue to collect OpenCV video codecs and `tifffile` (already pulled via imports). Validate TIFF load on a clean Windows/macOS frozen build before the next release — source-tree success does not guarantee packaged codecs.
