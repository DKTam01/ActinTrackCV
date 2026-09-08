# V2 Scientific Validation Harness

V2 extends the V1 measurement-fidelity audit into a durable regression system for
the workspace test corpus.

## Scope

Per-sample machine-readable records preserve:

- condition group / sample id / source path / hash
- crop and scientific-domain provenance
- tracker and Optical Flow parameters
- raw px/frame and calibrated µm/s
- sparse tracking summaries and per-track counts
- temporal reacquisition provenance (`lookahead`, recovered tracks/points)
- nucleus-relative summaries when a NucleusReference exists
- structural orientation summaries when a nucleus exists
- Optical Flow results, including scientific-mask application status

## Constraints preserved from V1

- No correction multipliers
- Acquisition interval remains unresolved for this export corpus
- Production `30 s/frame` default is not changed to chase historical magnitude
- WT550 > Mutant515 is a researcher-confirmed **investigation flag**, never a
  tuning target or hard scientific failure

## Manual quantitative comparison

If a manual measurements JSON is supplied, V2 computes signed/absolute/relative
error, MAE, RMSE, and optional rank agreement. Until such values exist, those
sections remain empty.

Example:

```json
{
  "measurements": [
    {
      "sample_id": "WT550_0001",
      "method": "sparse_mean_px_per_frame",
      "value": 5.0,
      "units": "px/frame",
      "notes": "researcher manual estimate"
    }
  ]
}
```

Supported methods:

- `sparse_general_movement`
- `optical_flow_general_movement`
- `sparse_mean_px_per_frame`
- `optical_flow_mean_px_per_frame`

## CLI

```bash
.venv/bin/python scripts/run_scientific_validation_benchmark.py
.venv/bin/python scripts/run_scientific_validation_benchmark.py \
  --lookahead-frames 2 \
  --manual-measurements path/to/manual.json
```

Outputs are written under gitignored `outputs/scientific_validation/`.
