# Current scientific methods (BUILD2)

This is the researcher/developer snapshot of **what ActinTrackCV currently
measures**. Phase documents remain the historical record; this page describes
the frozen BUILD2 product.

Do not treat these quantities as validated biological conclusions. They are
reproducible image measurements under stated definitions and calibration.

## Domain

Scientific computation uses **CellRegion ∩ area above the Measurement Cutoff**.
Persisted CellRegion is reused on sample selection. Tighter/Broader change
sensitivity only; they do not replace the algorithm.

Nucleus placement is researcher-authored. Moving the cutoff after a nucleus
exists preserves the nucleus and marks results for review/staleness as
implemented. Nucleus is optional for General Movement and Optical Flow, and
required for Toward Nucleus and F-actin Orientation.

## Calibration

Per-sample, persisted, and snapshotted into each analysis run:

- `acquisition_interval_s` — biological seconds between consecutive acquired frames (VIDEO)
- `microns_per_pixel` — physical scale (IMAGE and VIDEO)
- `acquisition_interval_source` / `spatial_calibration_source` — provenance

Legacy samples without an explicit CAL1 block keep **60 s/frame** and
**0.265 µm/pixel**. Those are compatibility fallbacks, not universal defaults.

Container FPS is playback provenance only. It never supplies scientific `dt`.

```
displacement_um = displacement_px * microns_per_pixel
velocity_um_per_s = displacement_px * microns_per_pixel / acquisition_interval_s
```

Changing only the acquisition interval from 60 s to 30 s doubles µm/s if pixel
motion is unchanged. 1 FPS and 3 FPS exports of the same acquisition must not
change scientific velocity.

See [`CAL1_SCIENTIFIC_CALIBRATION.md`](CAL1_SCIENTIFIC_CALIBRATION.md).

Earlier ImageJ quantification sometimes used arbitrary units. ActinTrackCV
µm/s values are not assumed to match those historical numbers.

## General Movement (VIDEO)

One **measurement** is one valid sparse-tracking step between consecutive
acquired frames (or a reacquisition gap with `dt` scaled by the frame gap).

1. Bright landmarks are chosen on the first usable frame.
2. Each later frame searches locally for the matching point
   (`brightest_local` by default; template matching remains available).
3. Pixel displacement is Euclidean in the analysis plane:
   `displacement_px = ||P_{t+1} - P_t||`.
4. Spatial conversion: `displacement_um = displacement_px * microns_per_pixel`.
5. Temporal conversion: `velocity_um_per_s = displacement_um / dt`,
   with `dt = acquisition_interval_s` for adjacent frames.

The sample scalar is the mean of valid step velocities (µm/s). Pixel-domain
`px/frame` remains the timing-invariant movement measure.

This is an ROI-level movement index, not a claim that every filament was
tracked as a unique biological object.

## Toward Nucleus (VIDEO)

Requires a researcher-placed nucleus `N`. For a tracked point `P_t`:

```
d_t = ||P_t - N||
v_toward = (d_t - d_{t+1}) / dt
```

- Positive = toward the nucleus
- Negative = away
- Zero = no radial-distance change

This is signed radial **distance change**, not motion-angle projection onto a
radial axis. General Movement is unchanged. Details:
[`R6_NUCLEUS_RELATIVE_MOVEMENT.md`](R6_NUCLEUS_RELATIVE_MOVEMENT.md).

## Optical Flow (VIDEO)

Dense OpenCV Farnebäck flow on consecutive cropped-frame pairs, aggregated over
bright pixels intersected with the scientific validity mask.

One **measurement** is one frame-pair mean magnitude (not a per-pixel table).
The sample scalar is the mean of those pair means, converted with the same
`microns_per_pixel` / `acquisition_interval_s` as sparse tracking.

Report both:

- `px/frame` — timing-invariant flow magnitude
- `µm/s` — calibrated using the run's snapshot

Sparse tracking and Optical Flow are complementary. They should not be expected
to match numerically. Details:
[`R8_OPTICAL_FLOW_DOMAIN_PARITY.md`](R8_OPTICAL_FLOW_DOMAIN_PARITY.md).

## F-actin Orientation (IMAGE)

Structural, not motion. Computed on a static IMAGE sample (not a video first
frame in the normal workflow). No skeletonization. No multi-frame orientation.

Method: structure tensor on valid CellRegion/cutoff pixels, with angles
referred to the nucleus:

- **0°** = radial (aligned with the nucleus)
- **90°** = tangential
- Direction-invariant (axial; 0–90°)

**Coherence** is a 0–1 measure of how strongly the local image structure has
one dominant orientation. It is not accuracy, confidence that the angle is
correct, filament quality, or a radial/tangential score.

The sample summary currently displayed is the **median** nucleus-relative
angle. Mean coherence is reported as a companion statistic.

Details: [`R7B_STRUCTURAL_ORIENTATION_INTEGRATION.md`](R7B_STRUCTURAL_ORIENTATION_INTEGRATION.md),
[`MEDIA1_MEDIA_TYPES_AND_INSPECTION.md`](MEDIA1_MEDIA_TYPES_AND_INSPECTION.md).

## Analysis aggregation

Condition Group tables average each metric only over samples that have that
metric. Mixed VIDEO+IMAGE groups therefore have metric-specific `n`. Missing
or unsupported values are **—**, not zero.

Measurement Inspector (**Show All Measurements**) reads the persisted analysis
run. It does not recompute with later calibration edits.

## Provenance

Each run records the calibration, algorithm settings, and reference geometry
used at execution time. Editing sample calibration after a run marks results
stale; the old run remains inspectable under its original snapshot.
