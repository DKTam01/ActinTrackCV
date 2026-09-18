# ActinTrackCV

Desktop app for **Arabidopsis** reproductive-cell fluorescence microscopy (Lifeact + H2B reporters). Organize **Data** by **Condition Group** and **Sample**, review the automatic **CellRegion**, set the **Measurement Cutoff**, place a **Nucleus** when required, set **per-sample scientific calibration**, run **Metrics**, inspect results, and compare Condition Groups in **Analysis**.

The current tracker is traditional computer vision, not a trained model: it follows bright F-actin landmarks from the first usable frame and converts calibrated displacement into velocity. Numerical tracker validation is in [`docs/TRACKER_VALIDATION_PROTOCOL.md`](docs/TRACKER_VALIDATION_PROTOCOL.md). Scientific methods are summarized in [`docs/science/CURRENT_SCIENTIFIC_METHODS.md`](docs/science/CURRENT_SCIENTIFIC_METHODS.md).

**Experimental design (current dataset):** WT lines **218** and **550** versus mutants **515** (`scar2`) and **175** (`xig`).

## Supported media and metrics

Condition Groups are biological groups. They are **not** tied to one media type and may contain mixed VIDEO and IMAGE samples. Capability is per **Sample**.

| Sample type | Formats | Metrics |
|-------------|---------|---------|
| **VIDEO** | AVI, MP4 | General Movement, Optical Flow, Toward Nucleus (nucleus required) |
| **IMAGE** | JPG, JPEG, PNG, TIF, TIFF | F-actin Orientation (nucleus required) |

Unsupported metrics display as **N/A / —**, never as zero. Do not infer a group's capabilities from its first sample.

F-actin Orientation is **structural** (not motion): **0° = radial** to the nucleus, **90° = tangential**.

3D / raw microscopy stacks (`.oir`, multi-page depth analysis, etc.) are not part of the current 2D product path.

## Researcher workflow

1. Create or open a project (workspace).
2. Create a Condition Group.
3. Import VIDEO and/or IMAGE samples.
4. Review the automatic **CellRegion** (Tighter/Broader if needed).
5. Set the **Measurement Cutoff**.
6. Place a **Nucleus** when Toward Nucleus or Orientation is required.
7. Configure **scientific calibration** for that sample.
8. Click **Run Metrics**.
9. Inspect Sample Results and individual measurements.
10. Compare Condition Groups in **Analysis**.

Nucleus is optional for General Movement and Optical Flow. It is required for Toward Nucleus and F-actin Orientation.

## Scientific calibration

Calibration is **per sample**, persisted with the sample, and snapshotted into each analysis run. Historical results stay bound to the calibration used when they were computed.

**Acquisition Interval** — the biological time between consecutive acquired frames, in seconds/frame. Shown for VIDEO samples. Presets: **30 s** and **60 s**. Custom positive values are valid. Samples without an explicit value keep the legacy fallback of **60 s/frame**.

**Spatial Calibration** — the physical distance represented by one image pixel, in µm/pixel. Shown for IMAGE and VIDEO. Samples without an explicit value keep the legacy fallback of **0.265 µm/pixel**.

Those fallbacks are compatibility defaults, not universal microscope constants. Lab examples have included approximately 0.265, 0.157836, and 0.138 µm/pixel depending on zoom and acquisition settings. Enter the scale that belongs to **that sample**.

### Acquisition interval is not playback FPS

AVI/MP4 FPS is export/playback metadata. It is **not** biological timing.

A 15-frame biological series acquired every 60 seconds contains **14 biological intervals** = 840 seconds = **14 minutes**, whether the exported AVI plays at 1 FPS or 3 FPS. The same pixel motion at 30 s/frame yields twice the µm/s of 60 s/frame.

The app does not infer calibration from FPS, DPI, filename, magnification, or a scale bar. Earlier ImageJ work sometimes used arbitrary units; ActinTrackCV µm/s values are **not** expected to match those historical numbers.

Details: [`docs/science/CAL1_SCIENTIFIC_CALIBRATION.md`](docs/science/CAL1_SCIENTIFIC_CALIBRATION.md).

## Download for macOS

Most users do not need Python or the source code — download the prebuilt app from the [**Releases**](https://github.com/Sapkota-Lab/ActinTrackCV/releases) page.

1. Download `ActinTrackCV-1.0.0-macos-arm64.zip` from the [`v1.0.0` release](https://github.com/Sapkota-Lab/ActinTrackCV/releases/tag/v1.0.0) (macOS Apple Silicon).
2. Unzip it (double-click in Finder).
3. Open `ActinTrackCV.app`.
4. Because this build is **unsigned**, macOS may block the first launch. If so, open
   **System Settings → Privacy & Security**, scroll to the message that *"ActinTrackCV" was blocked*,
   and click **Open Anyway**. After the first approval, it opens normally.

Notes:

- Unsigned Apple Silicon pre-release / internal test build — not notarized; no Intel/universal `.dmg` yet.
- Project data defaults to **`~/Documents/ActinTrackCV`**.
- External media files stay outside the app.

This source tree is preparing the next researcher build (**1.1.0**). Use Help → About to see the running version.

## Download for Windows

A **Windows 10/11 x64** build ships as a one-folder zip (not an installer wizard).

1. Download `ActinTrackCV-1.0.0-windows-x64-onefolder.zip` from the [`v1.0.0` release](https://github.com/Sapkota-Lab/ActinTrackCV/releases/tag/v1.0.0).
2. Unzip it.
3. Open the `ActinTrackCV` folder.
4. Double-click `ActinTrackCV.exe`.
5. **Keep the whole folder together** — do not move `ActinTrackCV.exe` out on its own.

Notes:

- Unsigned pre-release / internal test build. SmartScreen may warn: **More info → Run anyway**.
- Project data defaults to **`Documents\ActinTrackCV`**.
- A signed setup wizard is future work.

## Install from source

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Requirements: Python 3.10+, OpenCV, NumPy, pandas, PyQt6, tifffile.

```bash
python run_app.py                  # or: python -m actintrack_app.main
./run_app.sh                       # macOS/Linux
run_app.bat                        # Windows
```

The R Shiny app (`shiny_app/`) remains an alternate review frontend over the same Python analysis core. See [`shiny_app/README.md`](shiny_app/README.md).

## Terminology

| Term | Meaning |
|------|---------|
| **Condition Group** | Biological grouping you name (genotype, treatment, control, …) |
| **Sample** | One imported VIDEO or IMAGE file plus derived project state |
| **Data** | The imported media file |
| **CellRegion** | Automatic cell outline used as the scientific region (intersected with the area above the Measurement Cutoff) |
| **Measurement Cutoff** | Researcher-set boundary required for metrics |
| **Nucleus** | Optional for General Movement / Optical Flow; required for Toward Nucleus / Orientation |
| **General Movement** | Sparse-tracking absolute XY speed (µm/s) |
| **Optical Flow** | Dense Farnebäck motion over valid pixels (µm/s) |
| **Toward Nucleus** | Signed radial distance-change speed (µm/s; positive = toward) |
| **F-actin Orientation** | Structural angle relative to the nucleus (°) |

## Tests

```bash
python -m unittest discover -s tests -v
python scripts/validate_tracker.py
python scripts/validate_optical_flow.py
```

## User and science documentation

- Researcher guide: [`ActinTrackCV_User_Documentation_Refined.md`](ActinTrackCV_User_Documentation_Refined.md)
- Current methods: [`docs/science/CURRENT_SCIENTIFIC_METHODS.md`](docs/science/CURRENT_SCIENTIFIC_METHODS.md)
- Calibration: [`docs/science/CAL1_SCIENTIFIC_CALIBRATION.md`](docs/science/CAL1_SCIENTIFIC_CALIBRATION.md)
- Packaging / researcher build: [`docs/BUILD2_RESEARCHER_BUILD.md`](docs/BUILD2_RESEARCHER_BUILD.md)
- Developer notes: [`CLAUDE.md`](CLAUDE.md), [`CONTRIBUTING.md`](CONTRIBUTING.md)

## Build from source

The frozen app never writes into its own bundle. Default workspace: `~/Documents/ActinTrackCV`.

**macOS** (unsigned `.app`, Apple Silicon):

```bash
python -m pip install -r requirements-build.txt
bash packaging/macos/build_macos.sh
ditto -c -k --keepParent dist/ActinTrackCV.app ActinTrackCV-1.1.0-macos-arm64.zip
```

See [`packaging/macos/README.md`](packaging/macos/README.md).

**Windows** (must run on Windows 10/11 x64, or GitHub Actions `windows-latest`):

```powershell
python -m pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File packaging\windows\build_windows.ps1
Compress-Archive -Path dist\ActinTrackCV -DestinationPath ActinTrackCV-1.1.0-windows-x64-onefolder.zip -Force
```

See [`packaging/windows/README.md`](packaging/windows/README.md).

## Related: SeedThermal (separate project)

FLIR ONE Edge seed thermal phenotyping lives in **[`SeedThermal/`](SeedThermal/README.md)** and is not part of this pipeline.
