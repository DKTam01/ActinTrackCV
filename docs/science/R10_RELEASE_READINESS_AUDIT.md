# R10 Release-Readiness Audit

**Audit date:** 2026-09-08  
**Branch:** `phase-v1-measurement-fidelity`  
**HEAD at audit:** `d69edcc` (Phase V2)  
**Scope:** scientific completeness, product parity, packaging, documentation, hygiene  
**Policy:** identify gaps; do not auto-implement every issue in this phase

## Executive verdict

The scientific core from V1 through V2 is coherent enough for an internal
research workbench milestone, but **not** yet for an unqualified public
scientific release claiming validated absolute µm/s or fully annotated
nucleus-relative/orientation biology on the current export corpus.

Blocking scientific gaps are evidence/process gaps, not missing UI plumbing:

1. acquisition interval for these exports remains unresolved
2. no researcher-confirmed NucleusReference on the WT550/Mutant515 audit corpus
3. no quantitative manual measurement file for MAE/RMSE
4. Shiny does not yet expose R6/R7/R8 scientific outputs at parity with PyQt

## Completed scientific phases (accepted context)

| Commit | Phase |
|--------|-------|
| `f56bfe7` | Clean development metadata / tracker redundancy |
| `c2fa176` | R4 temporal reacquisition |
| `d143606` | R5 per-track scientific results |
| `b10bffd` | R6 nucleus-relative movement |
| `ff520f9` | R7A orientation method research |
| `545f09e` | R7B orientation production integration |
| `817dd11` | R8 Optical Flow scientific-domain parity |
| `143a6b7` | R9 results/analysis integration |
| `d69edcc` | V2 durable scientific validation harness |

## Scientific completeness

### Ready

- Absolute General Movement definition centralized and provenance-versioned
- Sparse tracking R3 domain enforcement
- Temporal reacquisition with gap-aware `dt`
- Per-track persistence in primary tracking result schema
- Nucleus-relative signed radial velocity (positive toward nucleus)
- Structural orientation module with explicit 0–90° nucleus-relative convention
- Optical Flow aggregation can intersect scientific validity mask
- Analysis/result panels prioritize GM / Toward Nucleus / Orientation / OF GM

### Incomplete for release claims

| Gap | Severity | Notes |
|-----|----------|-------|
| Acquisition timing unresolved (`0.2` vs container `6 fps` vs `30`) | **Blocker for absolute µm/s claims** | Keep 30 as default hypothesis; report px/frame |
| No NucleusReference on audit corpus | **Blocker for R6/R7 biology review** | Correctly returns missing; no fabricated nucleus |
| No quantitative manual values | **Blocker for accuracy claims** | V2 hooks exist; empty until supplied |
| ROI-only real runs without CellRegion/cutoff | Medium | Not R3-domain validation |
| `raw/` cross-condition duplicates | Medium | Documented; not silently repaired |
| Shiny R6/R7/R8 parity | High for product release | PyQt ahead of Shiny |

## R4 reacquisition quality

- Implemented and synthetically tested
- Production default remains `lookahead_frames=0`
- Real-corpus V2 runs with default lookahead report no recoveries (expected)
- Manual GUI verification still needed with `lookahead_frames>0` on weak-tip videos

## Per-track persistence (R5)

- Canonical `tracking_result` serialization exists
- Primary UI remains summary-first (correct for concision)
- Older draft JSONs in workspace may still lack `tracks` (legacy-compatible)

## Nucleus-relative / orientation (R6/R7)

- Definitions are implemented and tested synthetically
- Real-sample distributions unavailable until nuclei are saved
- Structural angle is explicitly not trajectory/motion angle

## Optical Flow parity (R8)

- Desktop Run Metrics can apply scientific mask
- Calls without mask retain rectangle-only legacy behavior
- Shiny bridge still needs explicit contract confirmation for mask persistence

## Shiny / CLI parity

| Surface | Sparse GM | OF GM | Nucleus-relative | Structural angle | Scientific OF mask |
|---------|-----------|-------|------------------|------------------|--------------------|
| PyQt workbench | Yes | Yes | Yes (if nucleus) | Yes (if nucleus) | Yes when annotation present |
| Analysis view | Yes | Yes | Yes | Yes | via saved OF draft |
| Shiny | Partial | Partial | No | No | Uncertain / ROI-oriented |
| CLI / V2 harness | Yes | Yes | Yes when nucleus | Yes when nucleus | Optional |

`Rscript` was unavailable on the audit machine; Shiny helper/workflow gates were
**not run** and must not be marked passing.

## Schema / provenance

- Additive schema versions present for movement, tracking result, orientation, OF mask
- Finalized-vs-draft precedence remains: finalized motion-index wins when present
- Stale metric flags remain for tracking/OF; orientation invalidation exists on recompute paths
- Draft optical-flow / structural-orientation migration coverage should be reviewed for ID renames

## Performance

- 15-frame cropped audits complete in seconds for 10 samples
- No packaging/performance profiling of long videos in this audit
- Orientation sampling is sparse by design; acceptable for current ROI sizes

## GUI workflow

- Primary scientific outputs now clearer after R9
- Legacy downward metrics retained and labeled
- Manual verification still required for:
  - Run Metrics end-to-end with nucleus + cell/cutoff
  - Analysis refresh after annotation edits
  - Stale banners for orientation after nucleus moves
  - Multi-sample explorer run metrics

## Public repository hygiene

- `.cursor/` is gitignored
- Cleanup commit removed tracked Cursor artifacts
- Remaining editor-oriented wording exists in `docs/design/ui_design_system.md` (“Cursor Usage”) and should be neutralized
- Do not commit `outputs/`, `raw/`, `processed/`, draft metrics, or agent logs

## Packaging / release engineering

| Item | Status |
|------|--------|
| Version | `0.2.2` |
| macOS PyInstaller | Present; unsigned/unnotarized |
| Windows packaging | Present; historically lagged (`0.2.1` messaging) |
| Clean-machine AVI/MP4 codec verification | Still required |
| Background workers | Not required for this scientific milestone |

## Validation status at audit

Executed locally:

- `python -m compileall actintrack_app tests`
- `python -m unittest discover -s tests` → **613 OK** (after V2)
- `scripts/validate_tracker.py` (brightest_local)
- `scripts/validate_optical_flow.py`
- V2 real-sample benchmark (10 WT550/Mut515): WT > Mutant preserved in raw px/frame; no investigation alerts; 0 nuclei / 0 orientation results

Not executed:

- `Rscript tests/test_shiny_helpers.R`
- full `scripts/validate_shiny_workflow.py` (requires R)
- template tracker gate in the final R10 pass (was green earlier in the series)
- Windows packaging build

## Prioritized release roadmap

### P0 — required before scientific absolute-unit claims

1. Resolve acquisition interval for the exact export corpus (or keep µm/s provisional forever for these files)
2. Collect researcher-confirmed NucleusReference (+ CellRegion/cutoff) on WT550/Mut515
3. Provide quantitative manual measurements with units, timing, ROI/procedure for V2 MAE/RMSE

### P1 — required before product/parity release

4. Shiny/CLI parity for nucleus-relative and structural orientation outputs
5. Confirm Shiny Optical Flow uses the same scientific-domain mask contract as desktop
6. Manual GUI verification checklist for R4–R9 workflows
7. Neutralize remaining editor-specific wording in design docs

### P2 — hardening

8. Expand V2 baseline snapshots checked into CI-friendly fixtures (non-data hashes/summaries only)
9. Draft/finalized timestamp precedence policy decision (document or fix)
10. macOS notarization / Windows version alignment / clean-machine media tests
11. Repair/quarantine misfiled `raw/` duplicates with explicit researcher approval

### Explicitly deferred

- Arbitrary calibration changes to match historical 0.2 s/frame magnitudes
- Genotype-aware tuning
- Statistical conclusion engines in Analysis
- Automatic biological interpretation of orientation/toward-nucleus distributions

## Recommended next release work

Treat the next milestone as **“Annotated Corpus + Timing Evidence”**, not more
algorithm churn:

1. Save nuclei/cell/cutoff on the 10-video audit set
2. Re-run V2 and R9 Analysis spot-checks
3. Decide absolute-unit messaging (provisional vs validated) based on timing evidence
4. Bring Shiny to parity only after those scientific inputs exist
