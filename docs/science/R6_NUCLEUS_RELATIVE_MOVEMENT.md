# R6 Nucleus-Relative Movement

## Scientific definition

For a measured point `P_t`, nucleus reference `N`, and actual elapsed time
`dt`:

```text
d_t = ||P_t - N||
toward_displacement = d_t - d_(t+1)
toward_velocity = toward_displacement / dt
```

Sign convention:

- positive: toward the nucleus;
- negative: away from the nucleus;
- zero: no radial-distance change.

This is a radial-distance difference, not motion-angle projection. General
Movement remains absolute XY displacement and is unchanged.

## Coordinate and time handling

`NucleusReference` remains persisted in oriented-frame pixels. Run Metrics
converts it to crop-local pixels before measurement. All point and nucleus
coordinates therefore share the same space. Spatial conversion uses the run's
`microns_per_pixel`.

Temporal reacquisition gaps use:

```text
dt = seconds_per_frame * frame_gap
```

No missing point or nucleus reference is fabricated.

## Persistence

When a nucleus exists, trajectory CSV and the versioned R5 tracking result add:

- previous and current distance to nucleus;
- signed distance change;
- signed toward-nucleus velocity;
- per-track nucleus-relative summary;
- video-level step-weighted and time-weighted summaries;
- nucleus coordinate-space provenance.

Historical payloads and runs without a nucleus omit nucleus-relative JSON
fields. CSV columns remain blank when no nucleus is supplied.

## Validation

Deterministic synthetic tests cover:

- pure toward and pure away movement;
- equal-radius tangential movement;
- zero displacement;
- a 45-degree radial step;
- temporal frame gaps;
- rotation and mirror invariance;
- missing-nucleus omission;
- scientific-validity mask invariance;
- CSV, per-track, video, draft, and result-display paths.

## Real-sample status

The saved WT550_0001–0005 and MUT515_0001–0005 records in the local
`testsamples/` audit workspace have RectROI annotations but **no persisted
NucleusReference**. R6 therefore correctly produces no real-sample
nucleus-relative distribution for this corpus. No image-derived or default
nucleus was invented.

Quantitative real-sample nucleus-relative review remains blocked until
researcher-confirmed nucleus centers are saved. Existing raw px/frame General
Movement and WT550 > Mutant515 diagnostic ordering are unaffected by R6.
