# CAL1 Scientific Calibration

ActinTrackCV converts pixel motion into physical units using **per-sample**
calibration. This is researcher-controlled metadata, not something inferred
from the video file.

## Acquisition interval

`acquisition_interval_s` is the biological time between consecutive acquired
frames, in seconds/frame.

AVI/MP4 **FPS is playback/container metadata**. The same 15-frame experiment
exported at 1 FPS (~15 s playback) or 3 FPS (~5 s playback) still has 14
biological intervals. If those frames were acquired 60 s apart, both files
represent 14 × 60 s = 840 s = 14 minutes.

Do not use container FPS as scientific timing.

Common lab intervals are **30 s/frame** and **60 s/frame**. Any positive finite
seconds/frame value is valid. The application does not special-case those two
numbers in the science.

## Spatial calibration

`microns_per_pixel` is the physical image scale.

Example values already seen in lab metadata include approximately 0.265, 0.157836,
and 0.138 µm/pixel. Scale can change with zoom or confocal settings. CAL1 does
not extract this from AVI, MP4, JPEG DPI, TIFF tags, OIR/OIB, objective
magnification, or a drawn scale bar.

## Conversion

For a displacement measured in pixels:

```
displacement_um = displacement_px * microns_per_pixel
velocity_um_per_s = displacement_px * microns_per_pixel / acquisition_interval_s
```

Equivalent form for existing px/frame quantities:

```
velocity_um_per_s = velocity_px_per_frame * microns_per_pixel / acquisition_interval_s
```

Example: 5 px/frame × 0.265 µm/px / 60 s = 0.0220833 µm/s.

Changing only the acquisition interval from 60 to 30 doubles physical velocity.
Changing only µm/pixel scales physical velocity by the ratio of the new scale
to the old scale. Pixel-domain measurements (coordinates, displacement_px,
velocity_px_per_frame) stay the same.

F-actin Orientation is an angle measurement and does not use these calibration
fields.

## Persistence and provenance

Calibration belongs to the **Sample** and is stored in the project annotation
as `scientific_calibration`. Compute receives the values explicitly.

Each analysis run snapshots the calibration that produced its physical-unit
results. If the researcher later edits the sample from 60 s / 0.265 µm/px to
30 s / 0.157836 µm/px, the old persisted run remains interpretable with the
old calibration. Measurement Inspector reads that run; it does not recompute
with the current sample values.

## Legacy projects

Samples without an explicit CAL1 block keep PERF1 effective behavior:

- `acquisition_interval_s = 60.0`
- `microns_per_pixel = 0.265`

Pre-CAL1 timing provenance (video header, lab default, custom) is still
readable but is not promoted into live analysis. Researchers do not need to
recreate existing projects.

## Historical ImageJ values

Earlier ImageJ quantification used arbitrary units (a.u.). ActinTrackCV does
not assume those values equal ActinTrackCV physical velocity. Comparison is a
later scientific step.

## Automatic metadata calibration

Not implemented in CAL1. Exported media often drops microscopy calibration
tags, so automatic extraction needs its own provenance/validation phase.
