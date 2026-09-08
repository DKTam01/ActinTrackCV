# R7A Structural F-actin Orientation Research

## Quantity under study

The required quantity is the local **physical cable orientation relative to the
radial line from a researcher-confirmed nucleus**:

```text
theta = acos(abs(F dot R))
```

where `F` is an axial filament unit vector and `R` is the radial unit vector.
The absolute dot product makes traversal direction irrelevant and yields
`0–90°`:

- `0°`: radial;
- `90°`: tangential.

This is not motion direction, trajectory angle, or turning angle.

## Candidate methods

Four methods were implemented behind a research-only interface:

1. structure tensor orientation;
2. thresholded local PCA;
3. morphological skeleton plus local PCA tangent;
4. Canny plus probabilistic Hough line segments.

All use only current NumPy/OpenCV dependencies and accept a crop-local validity
mask. Foreground selection combines a configured percentile with a robust
contrast floor so low-background pixels do not dominate.

## Synthetic evidence

The comparison used deterministic straight cables at `0°, 30°, 45°, 60°, 90°`
plus curved, crossing, weak, brightness-varying, and noisy fixtures.

Straight-cable axial error:

| Method | Median error | Maximum error |
|--------|--------------|---------------|
| Structure tensor | 0.28° | 0.87° |
| Local PCA | 0.04° | 3.20° |
| Skeleton tangent | 0.89° | 1.28° |
| Hough lines | 0.14° | 1.34° |

Stress fixtures exposed the important differences:

- Weak 30° cable: structure tensor 29.53°, local PCA 38.95°, skeleton
  39.69°, Hough 31.54° but with only 13 segments.
- Noisy 60° cable: structure tensor 59.76°, local PCA 58.63°, skeleton
  46.24°, Hough 59.41° but with only 7 segments.
- Curved cables: structure tensor and local PCA preserve many local
  measurements; Hough collapses them into a small set of straight segments.
- Crossings: structure-tensor coherence falls at the isotropic crossing center;
  branch-arm measurements remain high-confidence. A global axial mean at a
  crossing is not interpreted as one filament.

## Real-sample method stability

The complete five-video WT550 and five-video Mutant515 RectROI set was analyzed
on reference frame 0. These samples lack saved CellRegion, cutoff, nucleus, and
manual structural-angle truth, so this comparison evaluates method behavior,
not biological angles.

| Method | Median local measurements | Mean confidence | Median threshold span | Maximum threshold span | Mean runtime |
|--------|---------------------------|-----------------|-----------------------|------------------------|--------------|
| Structure tensor | 1194.5 | 0.54 | 1.22° | 4.59° | 15.9 ms |
| Local PCA | 1169.0 | 0.40 | 3.80° | 9.36° | 75.3 ms |
| Skeleton tangent | 1014.0 | 0.40 | 3.31° | 7.72° | 54.7 ms |
| Hough lines | 587.5 | 0.06 | 5.62° | 25.92° | 8.3 ms |

The angle values themselves are not reported as nucleus-relative results
because no nucleus was confirmed.

## Selection

**Structure tensor is selected for R7B production integration.**

Evidence supporting selection:

- sub-degree straight-fixture maximum error;
- best weak/noisy combined behavior without depending on a handful of line
  segments;
- lowest real-sample threshold sensitivity;
- local measurements survive curved cables;
- coherence provides a meaningful local quality measure and exposes ambiguous
  crossings;
- approximately five times faster than local PCA on these crops;
- no new dependency or custom skeleton traversal.

Local PCA remains a useful research comparator. Skeleton and Hough are rejected
as production defaults because segmentation/topology and line-fragment
sensitivity are materially less stable on real and stress fixtures.

## Remaining limitations

- Real-sample angle MAE/RMSE remains unavailable without blinded expert angle
  annotations.
- Audit samples lack confirmed nucleus references, so production
  nucleus-relative values cannot yet be reviewed biologically.
- Lossy AVI/MP4 reference frames may not preserve all weak cable structure.
- Production integration must preserve multiple local measurements, confidence,
  reference frame, valid-domain provenance, and an uncluttered overlay.

Reproduce the machine-readable comparison with:

```bash
.venv/bin/python scripts/run_orientation_method_comparison.py
```

Output is written under the gitignored `outputs/orientation_research/`.
