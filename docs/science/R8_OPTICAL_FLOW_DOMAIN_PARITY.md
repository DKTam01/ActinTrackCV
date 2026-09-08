# R8 Optical Flow Scientific-Domain Parity

## Change

Farnebäck preprocessing and flow-field calculation are unchanged.

For each frame pair, accepted vectors now use:

```text
brightness_mask intersect scientific_valid_mask
```

The same static crop-local mask used by point tracking is supplied by desktop
Run Metrics. Flow vectors outside CellRegion or below CutoffBoundary are not
aggregated. No vectors are clipped or projected onto the boundary.

Calls that omit `valid_mask` retain the historical rectangle-only behavior.
An all-true validity mask is numerically identical to the legacy calculation.

## Provenance

Optical Flow JSON now records:

- whether the scientific mask was applied;
- scientific-domain pixel count and fraction;
- SHA-256 identity of mask shape/content;
- per-pair accepted fraction relative to the scientific domain;
- the aggregation-mask definition.

The mask hash is included in the Optical Flow fingerprint, so annotation-domain
changes make older results stale.

## Synthetic validation

A controlled dense flow field with `1 px/frame` motion in the valid half and
`5 px/frame` in the excluded half produced:

- rectangle-only mean: `3 px/frame`;
- scientifically masked mean: `1 px/frame`.

The flow field itself was supplied unchanged to both aggregations. Tests also
cover all-true invariance, all-false explicit failure, shape mismatch,
fingerprint changes, and JSON round trip.

## Real-sample comparison

The five WT550 and five Mutant515 saved audit ROIs lack CellRegion/cutoff
annotations. Their effective fallback mask is all true, so R8 correctly causes
zero numerical change:

| Condition | Legacy OF px/frame | Masked OF px/frame | Delta |
|-----------|---------------------|--------------------|-------|
| WT550 | 4.56823 | 4.56823 | 0.00000 |
| Mutant515 | 3.56420 | 3.56420 | 0.00000 |

All ten sample-level deltas were exactly zero in the matched run. The
researcher-confirmed diagnostic ordering remained WT550 > Mutant515.

This does not validate nontrivial real CellRegion/cutoff effects; annotated
real samples are still required for that review.

## Compatibility

- Existing Optical Flow result keys remain available.
- Historical JSON without domain fields loads with rectangle-only provenance.
- Shiny/CLI runs that do not supply scientific annotations remain
  rectangle-only. Cross-frontend annotation parity remains a release-readiness
  item rather than silently inventing a web-side domain.
