# ActinTrackCV UI Design Language

Design reference for the ActinTrackCV PyQt6 scientific workbench.

This guide supports UI layout, hierarchy, copy, and interaction decisions. It does **not** authorize scientific, schema, or algorithm changes.

---

## Product Design Philosophy

ActinTrackCV is a **digital scientific instrument** for F-actin fluorescence microscopy analysis.

It should not feel like a generic desktop form application.

Researchers spend most of their attention judging microscopy previews, ROI placement, and analysis readiness. The interface should serve that work quietly.

The microscope image is the visual hero.

The app should help researchers move samples through:

```text
Imported → Prepared → Analyzed
```

with minimal friction.

Correctness, data integrity, and backward compatibility always outrank polish.

---

## Core Workbench Principles

### 1. The image is the hero

The microscope image should receive the most visual space and attention.

Prefer large central image area, minimal surrounding chrome, calm UI density, subdued panels, and direct image interaction.

Avoid large permanent control panels, redundant labels, decorative borders, and statistics competing with the image during preparation.

---

### 2. The app should feel like a scientific instrument

The interface should feel focused, calm, and purposeful.

The researcher should feel like they are working with a microscopy instrument, not navigating a collection of software tabs.

Use UI only where it supports the experiment.

Ask before adding controls:

> Does this help the researcher understand or act on the image right now?

If not, hide it, defer it, or move it to a contextual surface.

---

### 3. Workspace-first, not tab-first

The user should feel like they are inside one workspace.

The selected Condition Group or Sample determines context.

Avoid designing around rigid pages such as Sample tab, Analysis tab, or Metrics tab.

Prefer:

```text
Explorer selection → workspace updates
```

The Sample tab is not a long-term destination. Sample-related information should be shown only where it supports the current task.

---

### 4. Explorer is navigation, not the workspace

The Explorer belongs on the left.

It should show Condition Groups and Samples, preserve selection context, support project navigation, and eventually show simple sample state indicators.

It should not become a dense control panel.

Target layout direction:

```text
Explorer (~20%) | Microscope image + ROI preview + playback
```

Explorer should span the full height of the workspace and should not be interrupted by playback controls.

---

### 5. No permanent right sidebar

The long-term Workbench direction removes the permanent right-side controls panel.

Controls should move to more appropriate places:

- image actions → canvas or image-adjacent controls
- ROI actions → ROI/context menu
- playback → directly beneath the image
- project navigation → Explorer
- analysis metrics → deferred review/popup/workbench surface

Do not add a new permanent right inspector unless explicitly requested.

---

### 6. ROI is a first-class canvas object

The ROI should increasingly behave like an object on the microscope image.

Initial direction:

- user interacts with ROI on the canvas
- ROI preview remains visible near the image
- ROI context menu exposes focused actions

Initial ROI context menu:

```text
Clear ROI
Suggest ROI
Export ROI
```

Avoid speculative ROI actions such as duplicate, copy, paste, center, or templates unless explicitly requested.

Future direction:

- rotated ROI on the image
- downstream analysis still receives upright rectangular crops
- whole-image rotation becomes deemphasized

---

### 7. Hide whole-image orientation controls from the main UI

The researcher should primarily think:

> I am defining the ROI.

not:

> I am rotating the image.

Whole-image orientation controls should be hidden from the main Prepare workspace for now.

Do not remove backend orientation support until the rotated ROI pipeline fully replaces it and the change is explicitly requested.

---

### 8. ROI preview should be always available but secondary

The cropped ROI preview should be visible near the main image.

It should be smaller than the main image, visually separate from the main image, synchronized with the selected sample/ROI, and distinguishable without being visually loud.

It should not require opening a separate dialog during normal preparation.

---

### 9. Playback belongs to the image

Playback controls should sit directly beneath the microscope image.

They should not extend beneath the Explorer.

They should visually belong to the image/video workspace, not the whole window.

---

### 10. Analysis metrics are deferred

Do not show sample statistics in the main Prepare workspace for now.

Metrics, graphs, tables, and analysis spreadsheets should be designed later as a review/analysis experience.

The current direction allows for Analysis to become a popup or dedicated review surface, but that decision is intentionally deferred.

---

## Layout and Hierarchy Rules

1. Image first — preserve preview area; simplify panels before shrinking the canvas.
2. Reduce chrome — remove redundant frames, titles, and boxes.
3. Prefer whitespace over borders — use spacing constants before adding frames.
4. Avoid nested group boxes unless strongly justified.
5. One concept per section — avoid stacking multiple labels for the same idea.
6. Keep controls near the thing they affect:
   - ROI actions near ROI
   - playback near image
   - sample navigation in Explorer
7. Do not show numbers before the researcher asks for numbers — stats belong in analysis/review, not preparation.

---

## Typography and Copy

Use three typography levels:

1. Primary — body labels and normal controls.
2. Secondary — section headers and supporting labels.
3. Muted — hints, empty states, and low-priority guidance.

Every label must add new information.

Avoid repeating tab names, repeating section names, implementation/developer wording, internal IDs, schema names, and legacy Breed/Batch terminology.

Use Condition Group, Sample, Data, and ROI.

Preserve scientific terminology: tracking, optical flow, motion index, ROI, and Condition Group.

---

## Explorer State Indicators

Future Explorer direction should include simple progress/status indicators:

```text
○ Imported
◐ Prepared
✓ Analyzed
```

Meaning:

- Imported — sample exists but preparation is incomplete.
- Prepared — sample has enough preparation state to be analyzed.
- Analyzed — saved analysis outputs exist.

Export is optional and should not be treated as the final required state.

Avoid heavy dashboards, progress bars, or dense metadata in the Explorer.

---

## Context Menu Philosophy

Use context menus for relevant object-specific actions.

Context menus should be small and focused.

ROI context menu direction:

```text
Clear ROI
Suggest ROI
Export ROI
```

Sample context menu may include actions such as:

```text
Analyze
Rename
Refresh
```

Do not add actions just because they are easy to implement.

A context menu action should be relevant to the selected object, useful during normal research workflow, and better hidden than permanently visible.

---

## Implementation Rules

UI redesign passes must obey project constraints:

1. Do not change scientific algorithms.
2. Do not change metric formulas.
3. Do not change workspace schema unless explicitly requested.
4. Do not remove backend orientation support while hiding orientation UI.
5. Keep widget object names stable unless explicitly approved.
6. Prefer small, reviewable layout changes.
7. Update regression tests when labels, titles, visibility, or layout guards change.
8. Avoid broad rewrites of `gui.py` unless explicitly scoped.
9. Reuse `actintrack_app/gui_styles.py` helpers and style tokens.
10. Prefer native Qt widgets over heavy custom styling.

Before reporting completion, run:

```bash
python -m compileall actintrack_app tests
python -m unittest discover -s tests
```

---

## Workbench Stage 1 Direction

Workbench Stage 1 focuses on the main window shell, not analysis redesign.

Target layout:

```text
┌──────────────────────────────────────────────────────────────┐
│ Native menu bar                                              │
├──────────────┬──────────────────────────────┬────────────────┤
│              │                              │                │
│              │                              │ ROI Preview    │
│              │                              │                │
│ Explorer     │      Microscope Image        │                │
│ full height  │                              │                │
│ ~20% width   │                              │                │
│              ├──────────────────────────────┤                │
│              │ Playback controls            │                │
└──────────────┴──────────────────────────────┴────────────────┘
```

Stage 1 should remove or hide:

- permanent right sidebar
- Sample statistics in Prepare workspace
- whole-image orientation controls
- excessive control chrome

Stage 1 should preserve:

- Explorer navigation
- sample selection
- existing analysis behavior
- existing ROI persistence
- existing orientation backend
- existing tracking/optical-flow behavior
- existing workspace compatibility

---

## Contributor UI-change checklist

When changing Workbench UI:

1. Reference this document.
2. Begin with a read-only audit before editing.
3. List affected widgets/modules.
4. Identify behavior that must remain unchanged.
5. Keep each change narrow and reversible.
6. Do not redesign Analysis metrics unless explicitly requested.
7. Do not commit unless explicitly approved.

Example task fragment:

```text
Workbench Stage 1 UI task. Follow docs/design/ui_design_system.md.
Audit first. Do not modify algorithms, schemas, metrics, or backend orientation behavior.
Keep the change narrowly scoped and update tests.
```

---

## Open Questions

These are intentionally deferred:

1. Exact Analysis metrics UI.
2. Whether Analysis opens as popup, review surface, or dedicated workbench.
3. Final rotated ROI implementation.
4. Whether Sample statistics appear anywhere outside Analysis.
5. Final ROI preview sizing and placement.
6. Whether the Sample tab is removed fully or migrated gradually.
7. Full dark theme/QSS pass.
8. Table/spreadsheet polish.
9. Export UX beyond ROI export context action.

When uncertain, propose two layouts and stop.
