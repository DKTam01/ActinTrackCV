# ActinTrackCV

Desktop app for **Arabidopsis** 2D fluorescence microscopy time-lapse data showing labeled F-actin cables near the egg apparatus / nucleus-adjacent region. Organize **Data** by **Breed** and **Sample**, orient frames, draw a rectangular **ROI**, preview cropped tracking, and review F-actin motion index results.

**Active import formats:** AVI and MP4 only. Image sequences and 3D/raw microscopy formats are postponed.

## Install dependencies

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Requirements: Python 3.10+, OpenCV, NumPy, pandas, PyQt6, tifffile.

## Run the app

**To run the app, use:** `python run_app.py` from the project root (with your virtual environment activated).

**If you are on macOS/Linux, run:**

```bash
chmod +x run_app.sh    # once
./run_app.sh
```

**If you are on Windows, run:**

```bat
run_app.bat
```

**The main entry point is:** `actintrack_app.main` → `actintrack_app.gui.run_app()`

Equivalent commands:

```bash
python run_app.py
python -m actintrack_app.main
```

Launchers activate `.venv` or `venv` automatically when present. If dependencies are missing, `run_app.py` prints install instructions.

## Terminology

| Term | Meaning |
|------|---------|
| **Breed** | Biological / experimental group (e.g. `1_WT_218`, `2_WT_550`, `3_Mutant_515`, `4_Mutant_175`) |
| **Sample** | One imported AVI/MP4 **Data** file plus derived project state (ROI, tracking/index, analysis, notes) |
| **Data** | User-facing import wording for an AVI/MP4 file |
| **ROI** | Rectangular region of interest around the usable actin-rich area; autosaves as you work |

## Workflow

1. **Open or create a workspace** — **File → New Workspace…** or **File → Open Workspace…**
2. **Add Sample** — **Sample → Add Sample…** (or right-click a Breed/Sample row) and select an AVI/MP4 file
3. **Select Data** — choose a Sample in the left panel to load its Data
4. **Orient and ROI** — rotate/flip the frame as needed, then draw a rectangle around the actin-rich region (ROI autosaves; there is no Save ROI button)
5. **Preview Cropped ROI** — enter cropped ROI/tracking preview mode; playback loops continuously; use the frame slider to scrub manually; playback speeds: **0.25×, 0.5×, 1×, 1.5×, 2×**
6. **Draft tracking / F-actin motion index** — runs automatically during cropped ROI preview; **Advanced Tracking Settings** are available in that preview mode
7. **Analysis** — **Analysis → View Analysis…** for read-only aggregation by Breed and Sample

### Sample management

Right-click a Sample or Data row in the left panel:

| Action | Effect |
|--------|--------|
| **Rename Sample…** | Change the Sample display name |
| **Replace Data…** | Select a new AVI/MP4 file; clears derived ROI, tracking, and analysis state |
| **Delete Sample…** | Removes project state and derived results from the workspace; does **not** delete the original external Data file unless you opt to remove the project's internal copy |

## Project layout

Workspace folders are created locally when you use the app and are **not** committed to git:

```text
ActinTrackCV/                    ← project root (workspace)
  raw/                           ← optional internal copies of imported Data
    <breed>/
      <sample_id>.avi
  processed/                     ← cropped exports and motion-index outputs
  metadata/                      ← runtime registry and annotations
    data_files.csv
    sample_registry.json
    crop_metadata.json
    draft_tracking/
```

Opening an older workspace automatically migrates legacy v1 metadata (`samples.csv`, `batches.json`) to the current v2 schema.

## Application menu

| Menu | Actions |
|------|---------|
| **File** | New/Open workspace, recent workspaces, exit |
| **Workspace** | Refresh workspace, open folder, remove missing files, purge/cleanup |
| **Sample** | Add Sample, Rename Sample |
| **Analysis** | View Analysis |
| **Help** | How to Run App, About |

Context menu (right-click Sample or Data row): Rename Sample, Replace Data, Delete Sample.

## Tests

```bash
python -m unittest discover -s tests -v
```

## User documentation

See [`ActinTrackCV_User_Documentation_Refined.docx`](ActinTrackCV_User_Documentation_Refined.docx) for the full user guide.

Regenerate the DOCX from Markdown (if pandoc is installed):

```bash
bash scripts/build_refined_user_documentation.sh
```

## Not implemented

- Optical flow motion index (planned for a future release)
- Image sequence import
- 3D / raw microscopy format import (`.oib`, `.oir`, multi-page TIFF stacks, etc.)

## Other scripts

- `extract_2d_frames.py` — extract PNG frames from videos (legacy pipeline)
- `preprocess_ab_regions.py` — CLI crop using actin-signal ROI detection
- `python -m actintrack_app.main` — same GUI as `run_app.py`

See `PROJECT_OVERVIEW.md` for broader project context.
