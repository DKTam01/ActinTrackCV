# ActinTrackCV

## User Documentation

ActinTrackCV is a desktop application for organizing and analyzing 2D Arabidopsis F-actin fluorescence microscopy time-lapse data. The current workflow supports AVI and MP4 time-lapse data. It helps researchers confirm the automatic cell boundary, set a measurement cutoff, optionally mark the nucleus, run metrics, inspect overlays, and compare results across biological groups.

This guide is written for biological researchers. It avoids software implementation details unless they help explain how to use the app safely.

Current workflow:

```text
Condition Group -> Add Sample -> Cell Boundary -> Measurement Cutoff -> optional Nucleus -> Run Metrics -> Metric Analysis -> Analysis
```

Current supported data type: 2D AVI/MP4 time-lapse data.

Image sequences, 3D image stacks, and raw microscopy formats are postponed and should not be treated as active import workflows.

---

## 1. Quick Start

Use this short path when starting a new analysis session.

1. Open ActinTrackCV and open or create a workspace.
2. Select a Condition Group in the left panel.
3. Choose Sample -> Add Sample, then select one or more AVI or MP4 data files. Each file becomes one Sample in the selected Condition Group.
4. Confirm the automatic Cell Boundary. Adjust sensitivity if needed.
5. Set the Measurement Cutoff. Optionally mark the Nucleus (required only for Toward Nucleus and F-actin Orientation).
6. Click Run Metrics. Review Sample Results, then open Metric Analysis to inspect overlays.
7. Open Analysis to compare Samples and Condition Groups. The Workbench uses detected video timing for µm/s.

Run command from the project folder:

```bash
python run_app.py
```

On macOS or Linux, `./run_app.sh` is also available. On Windows, use `run_app.bat`.

---

## 2. Core Concepts / Glossary

| Term | Meaning |
|------|---------|
| Condition Group | A researcher-defined experimental grouping such as a genotype, chemical treatment, control, mutant, environmental condition, or other experimental setup (e.g. `Control` or `LatB Treatment`). You create custom names per workspace. |
| Sample | One imported AVI/MP4 data file plus its project state: cell boundary, cutoff, optional nucleus, notes, metrics, and analysis status. |
| Data | The AVI/MP4 file selected by the user for a Sample. The app stores a project-managed internal copy so the workspace can be reopened later. |
| Cell Boundary | Automatically detected cell outline. This is the scientific analysis region. Sensitivity can be adjusted. |
| Measurement Cutoff | Required horizontal line. Tracking uses the cell on the side of the cutoff with smaller image y. |
| Nucleus | Optional center mark on the cutoff. Needed for Toward Nucleus and F-actin Orientation. Not required for General Movement or Optical Flow. |
| Metric Analysis | Inspection of a persisted metrics run (Template Tracking, Optical Flow, or F-actin Orientation). It does not recompute science. |
| Sample Results | Concise current metrics beside the video: General Movement, Optical Flow, Toward Nucleus, Orientation, tracks, and timing. |
| Analysis | Read-only tables that summarize current measurements by Sample and Condition Group: General Movement, Optical Flow, Toward Nucleus, and F-actin Orientation. Historical image-direction metrics are optional. |
| Workspace/project files | The folders and metadata files ActinTrackCV uses to remember Samples, scientific annotations, tracking results, and outputs. |

---

## 3. Recommended Workflow

The recommended workflow is Sample-driven. A Sample represents one AVI/MP4 data file and its derived project state.

```text
Select Condition Group
  -> Add Sample by choosing AVI/MP4 Data
  -> Confirm Cell Boundary
  -> Set Measurement Cutoff
  -> Optionally mark Nucleus
  -> Run Metrics
  -> Inspect Metric Analysis
  -> Open Analysis
```

| Step | What you do | What the app stores or updates |
|------|-------------|--------------------------------|
| Select Condition Group | Choose the experimental group in the left panel. | The Sample list filters to that Condition Group. |
| Add Sample | Select one or more AVI or MP4 files. | One Sample per file: a Sample record, project-managed internal data copy, and metadata row. |
| Cell Boundary | Confirm the automatic outline; adjust sensitivity if needed. | CellRegion metadata and an internal computational crop. |
| Measurement Cutoff | Place or drag the horizontal cutoff. | CutoffBoundary metadata. Moving it does not silently move a saved nucleus. |
| Nucleus (optional) | Click the nucleus center; it snaps to the cutoff. | NucleusReference metadata. Needed for Toward Nucleus and Orientation. |
| Run Metrics | Compute tracking and optical flow for the current Sample. | Persisted run with an analysis_run_id. |
| Metric Analysis | Inspect overlays for the current non-stale run. | No recompute. Missing modes show a message in the preview area. |
| Analysis | Open the Analysis tab/menu item. | Analysis reads saved results and aggregates by Condition Group and Sample. |

### Condition Groups

New workspaces start with no Condition Groups. Create one before adding Samples:

1. **Workspace → New Condition Group…** (or **New Group** in the left panel)
2. Enter a custom name such as `Control`, `LatB Treatment`, or `Mutant + Chemical`
3. Select the group in the **Condition Group** dropdown before **Add Sample**

Use **Rename** or **Workspace → Rename Condition Group…** to change a group name. Samples stay assigned to the renamed group.

Use **Delete** or **Workspace → Delete Condition Group…** to remove an **empty** group. Deletion is blocked while the group still has Samples or Data.

Older workspaces that used legacy preset folder names (for example `1_WT_218`) still load those groups automatically.

### Adding a Sample

Create a Condition Group first. Then use Sample -> Add Sample, or right-click the empty area in the Sample list and choose Add Sample. Select one or more AVI or MP4 data files. Each file becomes one Sample in the selected Condition Group. If a file cannot be read, that file is skipped and reported in an import summary; successfully imported Samples remain.

### Replacing Data

Use Replace Data when a Sample should point to a different AVI/MP4 file. Replacing Data can clear ROI, tracking, processed outputs, and analysis state for that Sample because those results may no longer match the new file.

### Deleting a Sample

Deleting a Sample removes the Sample from the project, including ROI, tracking results, notes, and analysis data. The original data file on your computer is not deleted. If the app offers the checkbox "Also remove the project's internal data copy", that checkbox only refers to the project-managed copy inside the workspace.

---

## 4. App Interface Guide

| App area | What it is for | Notes |
|----------|----------------|-------|
| Condition Group/Sample list | Select the Condition Group and current Sample. | Right-click a Sample header or data row to rename, delete, or replace the Sample. |
| Add Sample flow | Choose one or more AVI/MP4 files to create Samples. | Canceling the file picker creates nothing. Partial failures show a summary; successful imports are kept. |
| Video / setup preview | View the full frame with Cell Boundary, Measurement Cutoff, and optional Nucleus. | Cell Boundary is automatic. Researchers no longer draw a rectangle. |
| Sample Results | Current General Movement, Optical Flow, Toward Nucleus, and Orientation values. | Toward Nucleus and Orientation require a nucleus. |
| Metric Analysis | Inspect a persisted run: Template Tracking, Optical Flow, or F-actin Orientation. | Does not recompute science. Missing modes show a message in the preview area. |
| Analysis | Read-only tables grouped by Condition Group and Sample. | Opening Analysis does not rerun tracking. |
| Purge/Cleanup | Advanced project cleanup tools. | Use carefully. These actions are for maintenance and troubleshooting. |
| Export ROI | Exports the internal computational crop to the `processed/` folder. | Optional sharing/export step, not required to run metrics. |

---

## 5. Workspace and File Structure Guide

An ActinTrackCV workspace is a project folder managed by the app. The app creates and updates the folders below.

```text
<workspace>/
  raw/
    <ConditionGroup>/
      <SampleName>/
        <sample_id>.avi or <sample_id>.mp4
  processed/
    <ConditionGroup>/
      <SampleName>/
        exported crops and motion-index outputs, if exported
  previews/
    <ConditionGroup>/
      optional preview files
  metadata/
    data_files.csv
    sample_registry.json
    crop_metadata.json
    draft_tracking/
      <sample_id>.json
    f_actin_motion_index_summary.csv
    workspace.json
    recent_workspaces.json
```

| File or folder | Purpose | User should edit manually? | Safe to delete manually? | Notes |
|----------------|---------|----------------------------|--------------------------|-------|
| `raw/` | Project-managed internal copies of imported AVI/MP4 data. | No. | Usually no. Use the app's delete options instead. | These copies let the project reopen even if the original file moves. |
| `processed/` | Exported cropped ROI videos/images and finalized output files. | No, unless you are intentionally copying results out. | Only if you understand they are generated outputs and no longer need them. | Deleting manually can make Analysis or previews appear incomplete. |
| `previews/` | Optional generated preview files. | No. | Usually safe if you only want to remove cached previews, but app cleanup tools are preferred. | The app may regenerate some previews. |
| `metadata/data_files.csv` | Main data index for Samples. | No. | No. | App-managed record of Sample data paths and statuses. |
| `metadata/sample_registry.json` | Sample registry grouped by Condition Group. | No. | No. | App-managed list of Samples. |
| `metadata/crop_metadata.json` | Cell boundary, cutoff, nucleus, orientation, and internal crop metadata. | No. | No. | Deleting this removes scientific setup state. |
| `metadata/draft_tracking/` | Draft tracking/index JSON files for Samples. | No. | Only through app cleanup or if intentionally clearing draft results. | Analysis can read these results. |
| `metadata/f_actin_motion_index_summary.csv` | Workspace-level summary of finalized motion-index outputs, when present. | No. | Only if you understand it is generated summary data. | Draft Analysis can also read per-Sample draft tracking JSON. |
| `metadata/workspace.json` | Workspace schema/version information. | No. | No. | Needed for current workspace compatibility. |
| `metadata/recent_workspaces.json` | Recent workspace list. | No. | Low risk, but not necessary. | Cosmetic/user preference data. |
| `raw_source/` | Optional source tree outside the normal app workflow. | Only as normal file organization. | Depends on your lab data policy. | Treat original source data as read-only. |

Safety rule: if a file is inside `metadata/`, let the app manage it. If you need to clean a workspace, prefer Workspace -> Purge / Cleanup rather than manually deleting files.

---

## 6. Data Import and Sample Management

### Supported input

ActinTrackCV currently supports AVI and MP4 data files in the active 2D workflow.

| Data type | Current support |
|-----------|-----------------|
| `.avi` | Supported |
| `.mp4` | Supported |
| Image sequence | Postponed |
| TIFF stack | Postponed for active import |
| `.oib`, `.oif`, `.oir` raw microscopy files | Postponed |
| 3D microscopy formats | Postponed |

### Sample meaning

A Sample is one imported AVI/MP4 data file plus its project state. The project state can include:

- data path/reference
- ROI/orientation metadata
- cropped ROI preview state
- tracking/index results
- analysis metrics
- notes/status

### Rename, delete, and replace

Right-click the Sample header or the indented data row to access:

- Rename Sample
- Delete Sample
- Replace Data

Replace Data should be used carefully. It can invalidate previous cell-boundary, cutoff, nucleus, and metrics results because those results were measured from the previous data file.

Delete Sample removes project state and derived results. It does not delete the original external file on your computer. If the project has an internal copy, the app may ask whether to remove that internal project copy.

---

## 7. Cell Boundary, Cutoff, and Nucleus

Researchers do not draw a rectangle. The app detects a Cell Boundary automatically. A Measurement Cutoff is required. A Nucleus mark is optional.

The internal computational crop (RectROI) is derived from the Cell Boundary for processing. It is not a researcher drawing tool.

### Why orientation matters

Orientation affects how the frame is displayed and how scientific annotations are applied. Rotate or flip the full preview until the region is visually consistent with the analysis goal. Downward motion is interpreted internally as increasing y-coordinate in the image; this direction is fixed and is not shown as a GUI control. Current product timing uses detected video FPS, not a global 30 s/frame default.

### Autosave

Cell Boundary, cutoff, and nucleus changes autosave. There is no Save ROI button.

### How to verify setup

Before Run Metrics:

- Confirm the data loaded correctly.
- Confirm the Cell Boundary follows the cell, including concavities.
- Set the Measurement Cutoff through the intended analysis limit.
- If you mark a nucleus, place it on the cutoff. If you later move the cutoff, the nucleus stays put and is shown as needing review until you re-select it.
- General Movement and Optical Flow do not require a nucleus. Toward Nucleus and F-actin Orientation do.

There is no Suggest ROI or Clear ROI researcher action.

---

## 8. Metric Analysis

Metric Analysis inspects the current persisted metrics run. It does not recompute tracking, optical flow, or orientation.

In this mode, the app:

- keeps Explorer, Sample Results, inspection controls, playback, Return to Full Preview, and Run Metrics
- shows Template Tracking, Optical Flow, or F-actin Orientation overlays from the saved run
- shows a centered message in the preview area when that mode has not been generated

If setup changes after a run, results become outdated. Run Metrics again to create a new run.

F-actin Orientation is a structural 0–90° nucleus-relative angle (0° radial, 90° tangential), not a motion direction. The compact legend stays a fixed UI size and does not scale with the cutoff crop.

### Controls

| Control | Purpose |
|---------|---------|
| Inspection mode | Choose Template Tracking, Optical Flow, or F-actin Orientation. |
| Play | Start looping the analysis preview. |
| Pause | Pause playback. |
| Frame slider | Manually scrub through frames. |
| Speed | Change playback speed. Supported options include 0.25x, 0.5x, 1x, 1.5x, and 2x. |
| Return to Full Preview | Exit Metric Analysis and return to the full Sample preview. |

Changing speed takes effect immediately when playback is active. Manual scrubbing remains available.

### Advanced Tracking Settings

Advanced Tracking Settings appear beside Metric Analysis. Changing scientific settings marks results outdated; click Run Metrics to compute a new run.

---

## 9. Tracking / Motion Index

The tracking/index result is intended as an ROI-level and Sample-level motion estimate. It is not a claim that every individual filament has been tracked perfectly.

The current draft method uses bright-point/template tracking:

1. It selects bright F-actin signal points in the first cropped ROI frame.
2. It follows those local image patches across frames.
3. It calculates movement values from valid tracked steps.
4. It summarizes the result for the Sample.

### How to interpret the values

| Output | General meaning |
|--------|-----------------|
| Downward Velocity | Historical image-Y metric: average positive movement toward the bottom of the image (µm/s). Not the same as Toward Nucleus. Optional in Analysis. |
| General Movement | Average overall displacement speed, regardless of direction. |
| Motion Index | Internal stored alias of General Movement on current runs. Analysis does not show it as a separate column. |
| Toward Nucleus | Signed movement toward the annotated nucleus (µm/s). Missing when no nucleus is set. |
| F-actin Orientation | Structural angle relative to the nucleus (0° radial · 90° tangential). Not a motion direction. |

Use these results as draft comparison metrics. They may not always match visual intuition, especially when contrast is low, cables overlap, the sample drifts, or structures move out of plane.

### Default tracking settings

| Setting | Default |
|---------|---------|
| Starting points | 10 |
| Minimum point spacing | 20 px |
| Search radius | 8 px |
| Patch size | 11 px |
| Minimum match confidence | 0.55 |
| Lookahead frames | 0 |
| Tracking method | brightest_local |
| Microns per pixel | 0.2650 |
| Seconds per frame | 30.0 |
| Downward direction | `increasing_y` internally |

The `seconds per frame` value is especially important for velocity units. The current **30.0 s/frame** default is the documented acquisition hypothesis used by the application; it is **not** automatically proven by encoded playback FPS (often ~6 fps on exported AVI/MP4 files). Confirm against acquisition metadata or lab notes when possible. Values much smaller than ~1 µm/s can indicate a timing/units investigation rather than “no motion.” Sparse tracking and Optical Flow remain separate methods and should not be expected to match numerically. See `docs/science/V1_MEASUREMENT_FIDELITY.md`.

---

## 10. Analysis Section

Analysis is read-only. It does not rerun tracking. It reads saved results and summarizes them by Condition Group and Sample.

The Analysis view includes:

| Table | What it shows |
|-------|---------------|
| Condition Group Summary | Per-group means for General Movement, Optical Flow, Toward Nucleus, and F-actin Orientation. Each metric shows `n` = number of samples that have that value. |
| Sample Details | Per-Sample current measurements. Missing nucleus-dependent values appear as `—`, not zero. |
| Condition Group Comparison | Ranked group comparison using the same current metrics. |
| Historical image-direction metrics | Optional. Image-Y downward / OF net-Y values. Hidden until you check **Show historical image-direction metrics**. |

F-actin Orientation is structural (0° radial · 90° tangential), not a motion angle. Toward Nucleus and Orientation require a nucleus annotation. General Movement and Optical Flow do not.

Group values are means of the samples that have that metric. A group can have `n=5` for General Movement and `n=4` for Toward Nucleus. Analysis does not invent missing values.

Example organization:

| Condition Group | Sample | Result status | General Movement | Toward Nucleus |
|-------|--------|---------------|------------------|----------------|
| `1_WT_218` | Sample 1 | Result available | numeric value | numeric value |
| `1_WT_218` | Sample 2 | Result available, no nucleus | numeric value | — |
| `3_Mutant_515` | Sample 1 | Result available | numeric value | numeric value |
| `3_Mutant_515` | Sample 2 | Missing result | — | — |

Missing results should be treated as missing data, not as zero movement. Analysis helps compare trends, but it should not be interpreted as final biological proof by itself.

---

## 11. Suggested Quality Control Practices

Use visual inspection and metadata checks together.

- Confirm that the AVI/MP4 data loads correctly.
- Confirm the Cell Boundary and Measurement Cutoff match the intended analysis region.
- Confirm Metric Analysis overlays match visible F-actin.
- Watch the looping preview and compare it to Sample Results values.
- Check whether tracked movement aligns with visible F-actin movement.
- Watch for low contrast, photobleaching, sample drift, out-of-plane movement, tangled cables, and overlapping filaments.
- Compare multiple Samples per Condition Group.
- Avoid drawing conclusions from one Sample alone.
- Confirm video timing in Sample Results before interpreting µm/s as biological velocity. Encoded FPS is detected from the file; it is not a global 6 FPS or 30 s/frame default.

---

## 12. Troubleshooting

| Problem | Likely cause | Suggested fix |
|---------|--------------|---------------|
| Data will not load | File is not AVI/MP4, the file is unreadable, or the path is missing. | Re-export as AVI/MP4 or choose a readable file. Confirm it opens outside the app. |
| Add Sample creates nothing | The file picker was canceled or every selected file failed validation. | Select one or more valid AVI/MP4 files. Check the import summary for per-file errors. |
| ROI appears wrong | Cell Boundary sensitivity or cutoff is misplaced. | Adjust Cell Boundary sensitivity and the Measurement Cutoff, then Run Metrics again. |
| Cropped preview is blank | That inspection mode has no persisted result, or results are outdated. | Run Metrics. If Orientation is blank, set a nucleus first. |
| Tracking result looks unrealistic | Low contrast, overlapping filaments, sample drift, or unsuitable tracking settings. | Visually inspect Metric Analysis, adjust tracking settings, and Run Metrics again. |
| Analysis shows missing result | Run Metrics has not been completed for that Sample, or the result was cleared. | Select the Sample and click Run Metrics. |
| Sample was replaced and old analysis disappeared | Replace Data cleared derived state because the old results no longer matched the new file. | Reconfirm Cell Boundary/cutoff and Run Metrics. |
| Playback speed seems wrong | Speed selection may not match expectations or playback was paused. | Select the desired speed during Metric Analysis and press Play if paused. |
| Return to Full Preview does not show the expected frame | The app returned to full preview using the current Sample state. | Select the Sample again or adjust the full-frame slider. |

---

## 13. Limitations and Future Work

Current limitations:

- Active import supports AVI/MP4 only.
- Current analysis is 2D only.
- Image sequence import is postponed.
- 3D/raw microscopy formats are postponed.
- TIFF stacks and raw microscope formats should not be documented as active workflows.
- The current motion index / General Movement is a comparison metric.
- Metrics should be interpreted with visual inspection and experimental context.
- Analysis still calculates historical image-Y metrics; they are optional in the Analysis view, not primary columns. See `docs/science/LEGACY_METRICS_AUDIT.md`.

Possible future work:

- Image-sequence workflow.
- 3D/raw microscopy support.
- Multi-frame structural orientation.
- Researcher override UI for analysis timing (the provenance model already supports it).

---

## 14. Appendix

### Supported data types

| Type | Status |
|------|--------|
| AVI | Active |
| MP4 | Active |
| PNG/JPG image sequence | Postponed |
| TIFF image/stack | Postponed for active app import |
| OIB/OIF/OIR raw microscopy | Postponed |

### Legacy terminology note

Older project files and older documentation may use earlier names. The current user-facing terms are:

| Legacy term | Current term |
|-------------|--------------|
| Breed | Condition Group |
| biological batch / batch | Sample |
| video / import video | Data / Add Sample |
| samples.csv | `data_files.csv` in schema v2, with compatibility for older workspaces |
| batches.json | `sample_registry.json` in schema v2, with compatibility for older workspaces |

You may still see legacy names in internal filenames or code paths. That does not change the current app workflow.

### Minimal installation reminder

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_app.py
```

On Windows, activate the environment with `.venv\Scripts\activate` and use `run_app.bat` if preferred.

### What to avoid

- Do not manually edit `metadata/` files unless you are doing advanced troubleshooting.
- Do not treat missing Analysis values as zero.
- Do not interpret a single Sample as proof of a Condition Group-level biological effect.
- Do not treat image sequences or 3D/raw microscopy files as active import types in the current workflow.

---

## 15. Short Safety Summary

ActinTrackCV is designed to preserve the user's original data files. Adding a Sample creates project records and a project-managed copy. Replacing Data or deleting a Sample may clear project state and derived results, but the original external AVI/MP4 file should remain untouched unless the app explicitly asks about a project internal copy and the user confirms that deletion.
