# BUILD2 — researcher build and release process

This phase prepares a documented, traceable researcher build from the
integrated MEDIA1 → BUILD1 → PERF1 → PERF2 → CAL1 product. It does not
redesign science or the Workbench.

## Version

Application version is the single string in `actintrack_app/__version__.py`.
PyInstaller specs, About, and artifact names read that value.

Published GitHub release **v1.0.0** (2026-09-15) is the last tagged public
cut. This source tree is **1.1.0**: IMAGE analysis, mixed-media groups,
Orientation, Toward Nucleus inspection, per-sample calibration, and the
performance work after v1.0.0.

Do not reuse the `v1.0.0` artifact names for a new package. Do not tag or
create a GitHub release until that step is explicitly requested.

## Traceability

A researcher package must record:

- `__version__`
- exact Git commit (`git rev-parse HEAD`)
- branch name
- platform / architecture
- unsigned / not notarized status

Help → About shows the version. Commit provenance belongs in the zip name
sidecar, release notes, and this build record — not a large new UI.

## macOS package (local)

From the repo root, with the same interpreter used for tests:

```bash
python -m pip install -r requirements-build.txt
bash packaging/macos/build_macos.sh
ditto -c -k --keepParent dist/ActinTrackCV.app ActinTrackCV-1.1.0-macos-arm64.zip
```

`dist/` and `*.zip` are gitignored. Do not commit generated binaries.

The app is unsigned. First launch on another Mac needs right-click → Open or
System Settings → Privacy & Security → Open Anyway.

Details: [`packaging/macos/README.md`](../packaging/macos/README.md).

## Windows package

PyInstaller does not cross-compile. A Mac cannot produce `ActinTrackCV.exe`.

Established path: GitHub Actions workflow
`.github/workflows/package-windows.yml`.

- Manual: Actions → Package Windows → Run workflow
- Optional `release_tag` attaches the zip to an **existing** GitHub release
- Automatic: pushing a `v*` tag (do not do this as part of BUILD2)

Local Windows 10/11 x64:

```powershell
python -m pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File packaging\windows\build_windows.ps1
```

Details: [`packaging/windows/README.md`](../packaging/windows/README.md).

## Validation expected before a researcher zip

```bash
python -m compileall actintrack_app tests
python -m unittest discover -s tests -v
python scripts/validate_tracker.py
python scripts/validate_optical_flow.py
```

Plus the focused CAL1 / PERF2 / PERF1 / MEDIA1 / BUILD1 / inspector suites.
Interactive researcher smoke is listed in the BUILD2 report; Cursor cannot
claim that interactive pass for the developer.

## Repository reconciliation

Lab origin: `https://github.com/Sapkota-Lab/ActinTrackCV.git` (`origin`)
Personal fork: `https://github.com/DKTam01/ActinTrackCV.git` (`fork`)

Default remote branch is `origin/main`. BUILD2 must not push until the
explicit push plan in the phase report is accepted. Preferred: no force push.
Do not push phase branches unless there is a reason to keep them remotely.

## What this build does not claim

- Equivalence with historical ImageJ arbitrary-unit measurements
- Automatic microscopy-metadata calibration
- Signed/notarized installers
- 3D stack thickness/depth analysis
- That Shiny has full parity with the PyQt Workbench

## Draft release notes (1.1.0)

Researcher-facing changes since the published **v1.0.0** GitHub release.
These notes do not claim biological validation beyond the synthetic gates
and lab exercises already documented.

- IMAGE analysis: JPG, JPEG, PNG, TIF, and TIFF imports
- Mixed VIDEO + IMAGE samples in one Condition Group
- Structural F-actin Orientation (structure tensor; 0° radial, 90° tangential)
- Nucleus-relative Toward Nucleus (positive = toward, negative = away)
- Measurement Inspector / Show All Measurements, with numeric sorting
- Per-sample acquisition interval (30 s / 60 s presets; custom positive values)
- Per-sample µm/pixel spatial calibration
- Biological timing is independent of AVI/MP4 playback FPS
- CellRegion and IMAGE-selection performance improvements
- Explorer drag/drop and mixed-group import improvements
- Analysis uses metric-specific `n`; unsupported metrics are — not zero
- Each analysis run stores the calibration used at execution time

Not in this build: automatic metadata-derived calibration; matching historical
ImageJ arbitrary-unit numbers; signed/notarized installers.

## Researcher smoke checklist

VIDEO

- [ ] Import a real AVI
- [ ] CellRegion appears and persists on reselection
- [ ] Set Measurement Cutoff
- [ ] Optional nucleus
- [ ] Set 60 s/frame and the correct µm/pixel
- [ ] Run Metrics
- [ ] Inspect General Movement, Optical Flow, Toward Nucleus
- [ ] Change to 30 s; results become stale
- [ ] Rerun; calibrated velocity doubles if pixel motion is unchanged
- [ ] A 1 FPS vs 3 FPS export of the same acquisition does not change µm/s

IMAGE

- [ ] Import PNG, TIFF, and JPEG
- [ ] CellRegion, cutoff, nucleus, spatial calibration
- [ ] Orientation result; 0° radial / 90° tangential
- [ ] Inspector numeric sorting
- [ ] Coherence tooltip (0–1 dominant-orientation measure, not accuracy)

MIXED GROUP

- [ ] VIDEO + IMAGE in the same Condition Group
- [ ] Analysis metric-specific `n`
- [ ] Unsupported metrics are — not 0

PERSISTENCE

- [ ] Save, close, reopen
- [ ] Calibration and annotations preserved
- [ ] Existing results still inspectable under the run's original calibration
