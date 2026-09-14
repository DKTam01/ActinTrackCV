# Legacy Metrics Audit (CLEAN1)

This note records what the Workbench **Analysis** view currently labels
`Legacy …`. It does **not** change formulas, persistence, or the Analysis
layout. Analysis-screen redesign is a later product phase.

**Product decision for CLEAN1:** keep these columns. The word “Legacy” is a
label. Several fields are still calculated on every Run Metrics. Removing
them now would change reproducibility of saved Analysis tables and exports.

## How to read this audit

- **Label** — column header in Analysis.
- **Source field** — persisted JSON key loaded by `analysis_service.py`.
- **Formula** — current definition (not a historical reconstruction).
- **Category**
  - **B** — historical scientific metric still calculated and used.
  - **C** — current metric with an unfortunate “Legacy” label (alias).
  - **A** would be dead file-format compatibility only. None of these
    Analysis columns are category A.

## Tracking (template) fields

### Legacy Avg Downward / Legacy Downward Velocity

| Question | Answer |
|---|---|
| Persisted source | `downward_velocity_index_um_per_s` |
| Analysis field | `SampleMetrics.downward_velocity` → `BreedSummaryRow.avg_downward_velocity` |
| Formula | Mean of per-step speeds where **image dy > 0** (increasing image Y), converted to µm/s. Documented in `compute_motion_indices` as “mean positive downward speed”. Payload also stores `downward_velocity_index_definition`: `mean(dy/dt \| dy > 0); increasing image y is downward`. |
| Still calculated today? | Yes, on every tracking run. |
| Duplicates a current metric? | No. **General Movement** is Euclidean speed (`absolute_velocity_index_um_per_s` / `general_movement_index_um_per_s`) and includes all directions. Downward is image-Y–only, positive-dy only. |
| Image-Y / downward? | Yes. This is the old primary “toward the bottom of the image” index. |
| Used by | Analysis tables; Python `analysis_service`; **not** the Workbench Sample Results panel (that panel shows General Movement). Shiny still surfaces downward velocity in group summaries (`mean_downward_velocity`) and trajectory/flow tables. Tests and tracker validation still assert downward values. |
| Removal impact | Would drop a still-computed scientific index from Analysis. Old papers/notes that used “downward velocity” would lose the on-screen column. Do not remove without a product decision. |
| Label vs metric | The **label** is “Legacy” because General Movement replaced it as the **primary** Workbench number. The **metric itself is not obsolete**. |

### Legacy Avg Motion Index / Legacy Motion Index / Legacy Std Dev Downward

| Question | Answer |
|---|---|
| Persisted source | Motion Index: `primary_velocity_index_um_per_s` (fallback: General Movement). Std Dev Downward: std of `downward_velocity` across samples. |
| Formula | Today `primary_velocity_metric` is `absolute_velocity_index_um_per_s`, and `primary_velocity_index_um_per_s` is written as **the same number as General Movement**. So **Legacy Motion Index currently equals General Movement** for current runs. Older payloads could theoretically store a different primary metric; the loader still honors `primary_velocity_index_um_per_s` if present. |
| Still calculated today? | The field is still written. Numerically it aliases General Movement on current runs. |
| Duplicates a current metric? | **Yes, for current payloads.** `Legacy Avg Motion Index` and `Avg General Movement` will match when `primary_velocity_index_um_per_s` was written by the current tracker. |
| Image-Y / downward? | Not for Motion Index (it is the primary scalar, currently Euclidean). Std Dev Downward is the spread of the downward index. |
| Used by | Analysis tables only as displayed columns. Sample Results does not show “Motion Index”. |
| Removal impact | Removing the column would not change stored JSON, but it **is entangled** with General Movement. CLEAN1 does **not** delete it. Analysis redesign should decide: drop the duplicate column, or keep it as an explicit alias with a non-“Legacy” name. |
| Label vs metric | The **label** is leftover from when “motion index” was the headline name. The **value is the current primary speed**, not an abandoned formula. |

**STOP-worthy finding (documented, not acted on):** Legacy Motion Index and General Movement are the same number on current runs. Separating or deleting that column is an Analysis-screen product decision, not a cleanup task.

## Optical-flow fields

All of the following are still computed by `optical_flow_motion_index.py` on every OF run (`DOWNWARD_DIRECTION = increasing_y`).

### Legacy OF Downward Motion (µm/s)

| | |
|---|---|
| Source | `optical_flow_downward_motion_um_s` |
| Formula | Mean Farnebäck downward component (`mean_downward_px_frame`) converted to µm/s. Image-Y positive. |
| Current counterpart | **OF General Movement** is mean flow *magnitude* (`optical_flow_general_movement_um_s` / `mean_magnitude_px_frame`). Not a duplicate. |
| Used by | Analysis tables; Shiny OF pair tables (`mean_downward_px_frame`, `downward_velocity_um_s`); OF validation. |

### Legacy OF Net Y Velocity (µm/s)

| | |
|---|---|
| Source | `optical_flow_net_y_velocity_um_s` |
| Formula | Mean signed net Y flow (`mean_net_y_px_frame`) converted to µm/s. Unlike Downward Motion, this includes negative (upward) Y. |
| Duplicate? | No. Downward Motion is the positive-downward summary; net Y is signed. |
| Used by | Analysis tables; persisted OF JSON. |

### Legacy OF Directionality Ratio

| | |
|---|---|
| Source | `optical_flow_directionality_ratio` |
| Formula | `mean_downward_px_frame / mean_magnitude_px_frame` when magnitude > 0. |
| Duplicate? | No. Dimensionless downward-vs-magnitude ratio. |
| Used by | Analysis tables; persisted OF JSON. |

## What CLEAN1 did not do

- Did not hide, rename, or remove Analysis columns.
- Did not change `motion_index.py` or `optical_flow_motion_index.py`.
- Did not change Shiny summaries.

Recommended next phase (not CLEAN1): Analysis-screen redesign should present **General Movement** and **Toward Nucleus** as primary tracking numbers, keep downward/net-Y as explicitly named **image-Y** diagnostics if the lab still wants them, and drop or relabel the Motion Index alias after confirming no external reader depends on the “Legacy Motion Index” heading.

## ANALYSIS1 UI decision (2026-09)

The Workbench Analysis view no longer shows Legacy Motion Index as a column. The persisted field `primary_velocity_index_um_per_s` / `SampleMetrics.motion_index` is still loaded and aggregated. On current runs it remains an alias of General Movement.

Legacy Downward and the related OF image-Y metrics remain calculated and persisted. They are not primary Analysis columns. Researchers can open **Show historical image-direction metrics** to see:

- Tracking Downward (µm/s)
- Tracking Downward Std Dev (µm/s)
- OF Downward Motion (µm/s)
- OF Net Y Velocity (µm/s)
- OF Directionality Ratio

Exports and Shiny were not changed in ANALYSIS1.

