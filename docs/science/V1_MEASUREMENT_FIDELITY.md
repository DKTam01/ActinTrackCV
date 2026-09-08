# V1 Measurement Fidelity Audit

**Status:** evidence report (not a calibration change)  
**Branch / phase:** `phase-v1-measurement-fidelity`  
**Corpus:** `testsamples/` (complete 15-video lab set); active `raw/` is incomplete and contains cross-condition duplicates  
**Constraint:** no correction multipliers, no genotype-aware tuning, no production timing change without independent acquisition proof

## 1. Purpose

ActinTrackCV must produce **reproducible absolute XY movement measurements**. This audit separates:

1. **Raw tracking / flow** (px/frame)
2. **Temporal / spatial calibration** (µm/px, s/frame)
3. **Aggregation / UI semantics** (step-weighted vs time-weighted; draft vs finalized precedence)

Values below `1 µm/s` are an **investigation trigger**, not a failure criterion. The researcher-confirmed qualitative ground truth that **WT550 is biologically faster than Mutant515** is treated as an external sanity check, never as an optimization target.

## 2. Competing temporal evidence

| Claim | Value | Source | Applies to | Confidence |
|-------|-------|--------|------------|------------|
| Current code default | `30.0` s/frame | `DEFAULT_SECONDS_PER_FRAME` in `motion_index.py` / Optical Flow | production defaults, PyQt/Shiny UI | code fact |
| Historical code default | `0.2` s/frame | first motion-index implementation; workspace draft JSON | draft tracking/OF through ~2026-06 | code/history fact |
| Container playback | `6.000` fps ≈ `0.1667` s/frame | OpenCV `CAP_PROP_FPS` on all inspected testsamples AVI/MP4 | export playback timing | container metadata fact |
| Lab documentation | `30` sec/frame, 15 frames | `PROJECT_OVERVIEW.md` citing slide deck | acquisition hypothesis | documentation claim |
| Draft WT550_0001 tracking | `seconds_per_frame=0.2`, GM ≈ `11.74` µm/s | `metadata/draft_tracking/WT550_0001.json` | that draft run | workspace artifact |
| Draft MUT515_0002 tracking | `seconds_per_frame=0.2`, GM ≈ `4.99` µm/s | `metadata/draft_tracking/MUT515_0002.json` | that draft run | workspace artifact |
| Draft WT550_0001 OF | `0.2` s/frame, mag ≈ `4.50` px/frame, OF GM ≈ `5.96` µm/s | `metadata/draft_optical_flow/WT550_0001.json` | that draft run | workspace artifact |
| Draft MUT515_0002 OF | `0.2` s/frame, mag ≈ `2.42` px/frame, OF GM ≈ `3.20` µm/s | `metadata/draft_optical_flow/MUT515_0002.json` | that draft run | workspace artifact |

**Conclusion for this corpus:** the exact biological acquisition interval of these **lossy exports** remains **unresolved**. Encoded `6 fps` is playback metadata. `30 s/frame` is the current documented hypothesis and production default; it is **not** validated here as the true interval for these files. Physical µm/s conclusions for this corpus remain **provisional**.

Why the first default was exactly `0.2` despite exports reporting `6 fps` is not recoverable from a single authoritative metadata source in-repo; the value appears as the original MotionIndexParams default and was persisted into draft outputs. The later change to `30` aligns with lab notes/slide-deck wording about acquisition interval, not with container FPS.

## 3. Historical group sanity values (provenance)

Researcher-facing historical Condition Group summaries (units/scale under investigation):

| Condition | Sparse General Movement | Optical Flow General Movement |
|-----------|-------------------------|-------------------------------|
| WT550 | ≈ 9.5861 | ≈ 6.2972 |
| Mutant515 | ≈ 6.0534 | ≈ 4.6765 |

Implied mean px/frame if those scalars used `0.265` µm/px and `0.2` s/frame:

- WT550 sparse ≈ `9.5861 * 0.2 / 0.265 ≈ 7.24` px/frame  
- Mut515 sparse ≈ `6.0534 * 0.2 / 0.265 ≈ 4.57` px/frame  
- WT550 OF ≈ `6.2972 * 0.2 / 0.265 ≈ 4.75` px/frame  
- Mut515 OF ≈ `4.6765 * 0.2 / 0.265 ≈ 3.53` px/frame  

These implied displacements sit in the same ballpark as reproduced draft/matched runs (section 5). The same scalars under `30 s/frame` would imply ~150× larger pixel motion and are **not** consistent with observed ~3–9 px/frame motion. Therefore the historical µm/s magnitude is largely explained by **temporal calibration semantics (`0.2` vs `30`)**, not by a broken pixel tracker—while still leaving the true acquisition interval unresolved.

## 4. Corpus identity and domain notes

- Prefer **`testsamples/`** for V1: five WT550 + five Mutant515 (+ other groups unused here).
- All probed videos: **15 frames**, container FPS **6.000**.
- Saved RectROI crops exist in `metadata/crop_metadata.json` for WT550_0001–5 and MUT515_0001–5.
- These ROI runs **do not** include CellRegion/cutoff masks; they are **not** R3 scientific-domain validation.
- Active `raw/` contains incomplete coverage and **cross-condition duplicate hashes**, including:
  - `MUT515_0001.avi` duplicated under `raw/2_WT_550/.../WT550_0006.avi`
  - multiple WT550 videos duplicated under `4_Mutant_175`
- Identity findings are reported only; they are **not** silently repaired.

## 5. Matched raw-displacement experiment

Reproducible CLI:

```bash
.venv/bin/python scripts/run_measurement_fidelity_audit.py \
  --tracker-mode current --flow-mode historical_draft --seconds-per-frame 30

.venv/bin/python scripts/run_measurement_fidelity_audit.py \
  --tracker-mode historical --flow-mode historical_draft --seconds-per-frame 0.2 \
  --output-dir outputs/measurement_fidelity/historical_0p2
```

Machine-readable outputs land under `outputs/measurement_fidelity/` (gitignored).

### 5.1 Current sparse tracker + draft-matched Optical Flow (fixed timing label `30 s/frame`)

Condition means of **raw px/frame** (calibration-independent):

| Condition | Mean sparse px/frame | Mean OF px/frame |
|-----------|----------------------|------------------|
| WT550 (n=5) | ≈ 5.48 | ≈ 4.57 |
| Mutant515 (n=5) | ≈ 4.64 | ≈ 3.56 |
| WT > Mutant? | **yes** | **yes** |

Representative traces:

| Sample | Sparse mean px/frame | Valid steps | OF mean px/frame | Sparse GM @30 s (µm/s) | OF GM @30 s (µm/s) |
|--------|----------------------|-------------|------------------|------------------------|--------------------|
| WT550_0001 | 5.00 | 111 | 4.50 | 0.044 | 0.040 |
| WT550_0002 | 6.13 | 92 | 6.50 | 0.054 | 0.057 |
| MUT515_0002 | 3.75 | 137 | 2.42 | 0.033 | 0.021 |
| MUT515_0003 | 5.46 | 119 | 4.34 | 0.048 | 0.038 |

At `30 s/frame`, reported µm/s values are ≪ `1` even though pixel motion is several px/frame. That is expected arithmetic (`µm/s = px/frame × 0.265 / 30`), not evidence that tracks vanished.

### 5.2 Historical template tracker + draft Optical Flow (fixed timing `0.2 s/frame`)

| Condition | Mean sparse px/frame | Mean OF px/frame |
|-----------|----------------------|------------------|
| WT550 (n=5) | ≈ 7.82 | ≈ 4.57 |
| Mutant515 (n=5) | ≈ 4.55 | ≈ 3.56 |
| WT > Mutant? | **yes** | **yes** |

Representative:

| Sample | Sparse px/frame | Steps | Sparse GM @0.2 | OF px/frame | OF GM @0.2 |
|--------|-----------------|-------|----------------|-------------|------------|
| WT550_0001 | 7.87 | 14 | 10.43 | 4.50 | 5.96 |
| MUT515_0002 | 4.43 | 68 | 5.87 | 2.42 | 3.20 |

Notes:

- Optical Flow **px/frame** is identical across timing labels because magnitude is measured before unit conversion.
- Historical template tracking yields fewer, longer-displacement steps (search radius 15, lookahead 3, confidence gate) versus current brightest-local defaults (10 starts, radius 8, lookahead 0).
- Both methods preserve **WT550 > Mutant515** on this matched corpus in raw px/frame. No method disagreement that would motivate a calibration change.

### 5.3 Sensitivity of identical displacements to labeled intervals

For a measured `5.0` px/frame displacement at `0.265` µm/px:

| Interval label | s/frame | µm/s |
|----------------|---------|------|
| historical_default_0p2 | 0.2 | 6.625 |
| container_playback_6fps | ≈0.1667 | 7.95 |
| documented_hypothesis_30 | 30 | 0.0442 |

Same coordinates, different timing labels → ~150× scale swing between 0.2 and 30. Do **not** interpret that swing as a tracking regression.

## 6. Authoritative movement math (code changes in V1)

In `actintrack_app/motion_index.py`:

- Added `StepMetrics` + `compute_step_metrics()` / `iter_track_step_metrics()` as the single per-step path.
- Trajectory CSV rows and both aggregates (`compute_motion_indices`, `compute_velocity_summary`) reuse that path.
- Formulas are unchanged:
  - step absolute speed = displacement_um / (seconds_per_frame × frame_gap)
  - General Movement = unweighted mean of per-step absolute speeds (step-weighted)
  - time-weighted mean = total_path_um / total_tracked_time_s
- Additive provenance fields: `metric_definition_version`, `movement_output_schema_version`, `movement_definition.*`
- Fixed summary JSON **output path population** so `outputs.*` are written after paths are assigned (previously blank).

**Not changed:** tracker thresholds, spatial/temporal defaults, Optical Flow mathematics, R3 masks.

## 7. Aggregation hierarchy and UI/export semantics

| Layer | Metric | Weighting |
|-------|--------|-----------|
| Trajectory CSV | per-step absolute / downward | none (raw steps) |
| PyQt Analysis / motion-index summary primary GM | `general_movement_index_um_per_s` | step-weighted mean |
| Explicit velocity summary | `time_weighted_mean_speed_um_per_s` | path/time |
| Shiny helper primary scalar | prefers time-weighted when present | time-weighted |

Sparse tracking and Optical Flow remain **separate methods**. They share calibration inputs but answer different questions (localized features vs dense bright-pixel field).

### Draft vs finalized precedence

`analysis_service.load_tracking_metrics_for_sample` prefers a **finalized** processed motion-index JSON when a sample row resolves one, otherwise falls back to draft tracking JSON. Timestamp comparison is **not** performed. V1 leaves this as an unresolved workflow semantic: an older finalized file can hide a newer draft unless the researcher re-exports/finalizes. No silent precedence rewrite was applied because the intended product rule (finalized Analysis results) is still coherent; stale finalized files remain a researcher workflow risk to document, not auto-heal.

## 8. Optical Flow entry defaults

| Surface | Default `mask_percentile` | Default `seconds_per_frame` |
|---------|---------------------------|-----------------------------|
| `OpticalFlowSettings` dataclass | 65 | 30 |
| Historical draft workspace OF | 90 | 0.2 |
| V1 audit `--flow-mode historical_draft` | 90 | run override / mode |
| V1 audit `--flow-mode current` | 65 | run override / mode |

Farnebäck coefficients are otherwise unchanged. Dense OF domain masking with CellRegion/cutoff remains deferred (R8).

## 9. Reproducible diagnostics

- Module: `actintrack_app/measurement_fidelity.py`
- CLI: `scripts/run_measurement_fidelity_audit.py`
- Tests: `tests/test_measurement_fidelity.py` (raw displacement, temporal scaling, frame gaps, weighting, direction invariance, provenance, populated paths, condition ordering)

## 10. Documentation corrections accompanying V1

- README and refined user documentation no longer advertise stale `0.2 s/frame` / historical template defaults as current production defaults.
- `30 s/frame` is described as the **current default and documented hypothesis**, not as a corpus-validated acquisition interval.
- Sparse tracking and Optical Flow remain explicitly separate.

## 11. Unresolved / blocked

- Exact per-video acquisition interval for these exports
- Per-video manual absolute error, bias, MAE/RMSE, rank agreement (blocked until quantitative manual values + procedure are supplied)
- R4 temporal reacquisition, R6 nucleus-relative movement, R7 structural angle, R8 OF domain masking
- Silent repair of misfiled `raw/` duplicates

## 12. Bottom line

1. Pixel-scale motion on matched WT550/Mutant515 crops is typically **~3–9 px/frame** for sparse tracking and **~2–7 px/frame** for Optical Flow.
2. Historical ~5–10 µm/s magnitudes align with **0.2 s/frame** calibration of that pixel motion; current ~0.03–0.06 µm/s magnitudes are the same motion under **30 s/frame**.
3. On this corpus, **both** sparse tracking and Optical Flow preserve **WT550 > Mutant515** in raw px/frame.
4. Production timing default remains **unchanged** until independent acquisition evidence resolves the interval.
5. V1 hardens measurement **provenance and auditability** without retuning science.
