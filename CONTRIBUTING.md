# Contributing to ActinTrackCV

ActinTrackCV is a scientific measurement application for Arabidopsis F-actin
fluorescence time-lapse data. Changes must prioritize:

1. Scientific correctness
2. Data integrity
3. Maintainability
4. Backward compatibility
5. Researcher workflow

## Scientific invariants

- General Movement is absolute XY displacement over elapsed acquisition time.
- Encoded playback FPS is not automatically the biological acquisition interval.
- Keep RectROI, CellRegion, CutoffBoundary, and NucleusReference as distinct
  concepts and coordinate spaces.
- Preserve the 2D AVI/MP4 workflow. Other microscopy formats are out of scope
  unless a change explicitly introduces and validates them.
- Do not add correction multipliers, genotype-aware behavior, or parameter
  tuning intended to force expected condition ordering or magnitude.
- Keep sparse point tracking and dense Optical Flow as separate measurements.
- Include parameters, units, algorithm versions, and reference geometry in
  persisted scientific provenance.

## Architecture

Keep scientific and persistence logic independent of Qt widgets where practical.
The primary analysis pipeline is in `actintrack_app.motion_index`; both desktop
and Shiny entry points must preserve its contracts. Extend existing services and
schema-compatibility helpers rather than duplicating workflows.

Condition Groups and Samples use stable identifiers. Display names are mutable
and must never replace identifiers for lookups or storage paths.

## User-facing terminology

Use **Condition Group**, **Sample**, **Data**, and **ROI**. Legacy internal names
such as `breed`, `batch`, and `batch_id` may remain where compatibility requires
them.

## Testing

For behavior changes, add focused regression tests and run:

```bash
python -m compileall actintrack_app tests
python -m unittest discover -s tests
```

Run the relevant synthetic scientific gates:

```bash
python scripts/validate_tracker.py
python scripts/validate_optical_flow.py
```

Scientific changes should also be inspected on the repository's real
`testsamples/` corpus. Report raw px/frame before calibrated units and do not
modify source sample data.

## Repository hygiene

Do not commit workspaces, imported data, generated outputs, build artifacts,
logs, local metadata, editor configuration, or release archives. Do not commit
or push unless the current work explicitly authorizes it.
