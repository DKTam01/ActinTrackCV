# R9 Results / Analysis Integration

R9 integrates R5–R8 scientific outputs into researcher-facing Analysis and
result panels without recomputing science in the GUI.

## Primary scientific outputs

Displayed in this order when available:

1. **General Movement** — absolute XY sparse-tracking speed (`µm/s`)
2. **Toward Nucleus** — signed nucleus-relative radial speed (`µm/s`;
   positive = toward nucleus)
3. **F-actin Orientation Relative to Nucleus** — structural axial angle
   (`0–90°`; `0` = radial to nucleus, `90` = tangential)
4. **Optical Flow General Movement** — dense Farnebäck magnitude over the
   scientific validity domain when a mask is present

Legacy image-Y / downward metrics remain calculated. In the Workbench Analysis
view they are optional historical columns, not primary comparison metrics.
They do not dominate the primary panel or Analysis comparison columns.

## Hierarchy

```text
Condition Group
  → Sample
    → Video/Data file
      → multiple point tracks (R5 detail in persisted JSON/CSV)
      → multiple structural-angle measurements (R7 detail in draft JSON)
```

Primary UI stays concise: video/sample summaries plus counts. Per-track and
per-measurement detail remain in persisted scientific outputs rather than the
main summary tables.

## Persistence contracts reused

| Quantity | Canonical source |
|----------|------------------|
| Sparse tracking / nucleus-relative | finalized motion-index JSON if present, else draft tracking JSON |
| Optical Flow | draft optical-flow JSON (PyQt Analysis) |
| Structural orientation | draft structural-orientation JSON |

GUI loaders and Analysis service parse persisted fields only. Missing older
fields degrade to `—` / omitted without inventing values.

## Non-goals

- No statistical conclusions or genotype ranking claims beyond listing averages
- No changes to R4–R8 scientific formulas
- Structural angle is not trajectory/motion angle
- Acquisition timing remains unresolved; µm/s values stay provisional for this corpus
