# R4 Temporal Reacquisition

## Definition

When an immediate point match fails and `lookahead_frames > 0`, tracking checks
the next configured future frames. A successful continuation:

- is a measured point in the future frame;
- passes the same confidence and scientific-validity mask as a normal match;
- claims that future-frame location to prevent track collisions;
- is marked `recovered_with_lookahead`;
- leaves missing frames absent from the point sequence.

Search radius expands by the actual frame gap. Movement calculations use:

```text
dt = seconds_per_frame * (current_frame_index - previous_frame_index)
```

No coordinates are interpolated, clipped, or projected onto CellRegion or
CutoffBoundary.

## Synthetic acceptance

Deterministic tests cover one- and two-frame disappearance, beyond-lookahead
termination, CellRegion and cutoff exclusions, an invalid brighter distractor,
future-frame collision claims, both tracking methods, gap-aware elapsed time,
weak bleaching, and no-gap invariance.

## Real-sample comparison

The complete matched five-video WT550 and five-video Mutant515 audit used saved
RectROI crops and current tracker parameters. `lookahead_frames=0` was compared
with `lookahead_frames=2`; no CellRegion/cutoff annotations were available, so
this is not an R3-domain validation.

| Condition | Lookahead | Tracks started | Tracks recovered | Valid steps | Mean raw px/frame |
|-----------|-----------|----------------|------------------|-------------|-------------------|
| WT550 | 0 | 50 | 0 | 561 | 5.476 |
| WT550 | 2 | 50 | 16 | 657 | 5.480 |
| Mutant515 | 0 | 50 | 0 | 619 | 4.644 |
| Mutant515 | 2 | 50 | 10 | 683 | 4.647 |

Median per-video median track length remained 15 frames in both groups.
Reacquisition mostly converted early losses into full-sequence tracks. Mean raw
displacement changed by less than 0.01 px/frame at the group level.

The external qualitative ordering remained:

```text
WT550 > Mutant515
```

This observation is a diagnostic check, not a tuning target. Tracker defaults,
including the production default `lookahead_frames=0`, remain unchanged.
