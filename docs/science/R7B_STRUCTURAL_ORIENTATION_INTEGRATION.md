# R7B Structural Orientation Integration

R7B promotes the R7A-selected structure-tensor method into a GUI-independent
production module.

## Inputs

- one saved annotation reference frame, already oriented and cropped;
- the crop-local scientific-validity mask;
- a researcher-confirmed `NucleusReference`, converted from oriented-frame to
  crop-local coordinates;
- versioned, persisted algorithm settings.

If the nucleus is missing, the result is explicitly invalid and contains no
measurements. The implementation never substitutes image center or an
automatically inferred nucleus.

## Outputs

Each `FilamentOrientationMeasurement` preserves:

- crop-local `x`, `y`;
- local axial cable orientation;
- cable angle relative to the radial line from the nucleus;
- structure-tensor coherence.

The result also stores all local measurements, mean/median/standard deviation,
algorithm and schema versions, reference frame, settings, valid/foreground
pixel counts, timestamp, nucleus coordinates, and the exact angle convention.

Run Metrics writes the result to the Sample-scoped
`metadata/draft_structural_orientation/` directory. Clearing derived Sample
state removes it consistently with tracking and Optical Flow drafts.

## Visualization

`render_structural_orientation_overlay` draws:

- the nucleus reference;
- a bounded, sparse selection of local cable tangents;
- occasional radial links for angle interpretation.

The overlay preserves the underlying image and limits glyph count to avoid
hiding weak F-actin signal.

## Validation status

Synthetic production tests cover exact 0–90° semantics, weak cables, validity
masks, multiple measurements, round-trip persistence, reference-frame
provenance, and overlay output.

The ten WT550/Mutant515 audit records contain no confirmed NucleusReference.
All ten therefore return an explicit missing-nucleus non-result, as required.
Real-sample structural-angle distributions remain unavailable until nuclei and
manual review annotations are supplied.
