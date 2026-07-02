# ActinTrackCV UI Design Language

Phase 5.5 design reference for the PyQt6 desktop workbench. Use this guide when polishing panels, labels, spacing, and layout hierarchy. It does **not** authorize scientific or workflow changes.

---

## Product Design Philosophy

ActinTrackCV is a **scientific desktop workbench**, not a consumer app or marketing site. Users spend most of their time judging F-actin fluorescence in microscopy previews. The interface should stay out of the way.

- **The microscopy preview is the visual hero.** Center-column canvas space, contrast, and calm surrounding chrome take priority over decorative sidebar treatment.
- **UI should quietly support analysis.** Controls explain what to do next; they should not compete with the image for attention.
- **Correctness beats polish.** Never sacrifice scientific behavior, data integrity, or backward compatibility for aesthetics.

User-facing terminology is fixed: **Condition Group**, **Sample**, **ROI** (not legacy internal names like Breed/Batch in labels).

---

## Core Principles

### Layout and hierarchy

1. **Image first** — preserve preview area; shrink or simplify side panels before shrinking the canvas.
2. **Reduce chrome** — remove redundant frames, titles, and boxes that repeat information already visible elsewhere.
3. **Prefer whitespace over borders** — use spacing constants (`PANEL_SECTION_SPACING`, `FORM_SECTION_SPACING`) before adding `QGroupBox` or custom framed panels.
4. **No nested group boxes unless strongly justified** — one level of grouping is usually enough. A tab title plus an inner group box with the same meaning is redundant.
5. **One concept per section** — orientation controls, ROI actions, export naming, and playback belong in distinct visual sections, not stacked titles for the same idea.
6. **Align controls to a simple grid** — equal-width action rows, consistent row spacing, and predictable label/control alignment (see Orient/ROI action buttons and playback rows).

### Typography and copy

7. **Three typography levels**
   - **Primary** — body labels and control text (`STYLE_BODY_LABEL`, default widgets).
   - **Secondary** — section headers and supporting labels (`apply_small_secondary_style`).
   - **Muted** — hints, empty states, and low-priority guidance (`apply_hint_style`, `apply_muted_hint_style`).
8. **Every label must add new information** — do not repeat a tab name, group-box title, and field label for the same concept.
9. **Preserve scientific terminology** — tracking, optical flow, ROI, motion index, and Condition Group language stay precise.
10. **Remove implementation/developer wording from user-facing UI** — no internal IDs, schema names, or engineer jargon in labels users see during normal work.

### Implementation posture

11. **Prefer native Qt widgets over heavy custom styling** — reuse `actintrack_app/gui_styles.py` helpers before inventing new QSS.
12. **Preserve workflows and scientific behavior** — polish is visual hierarchy and copy, not feature redesign.

Shared style tokens live in `actintrack_app/gui_styles.py`. New panels should reuse existing margin, spacing, and label helpers rather than hardcoding values.

---

## Concrete Examples

### Export name (Orient/ROI panel)

| Avoid | Prefer |
|-------|--------|
| `QGroupBox("Export Name")` **and** a field label `Export name:` | One section label **Export name** plus the input |
| Three layers of naming for one field | Tab/section context + single label + placeholder/hint |

**Why:** The group title and colon label said the same thing. One secondary section label is enough; the placeholder and auto-name hint carry the rest.

### Tab vs inner titles

| Avoid | Prefer |
|-------|--------|
| Tab **Orient && ROI** plus inner `QGroupBox("Orient and ROI")` | Tab provides context; inner sections describe **actions** (rotation, ROI Actions, export name) |
| Tab **Analysis** plus a group box that only repeats **Analysis** | Tab provides context; inner group describes **Analysis Actions** (Refresh, Return) when multiple controls need grouping |

**Why:** Tabs already establish where the user is. Inner chrome should subdivide tasks, not restate the tab name.

### Labels and hints

| Avoid | Prefer |
|-------|--------|
| Status line that repeats the section title | Status that reports **state** (saved, stale, missing ROI) |
| `"Optical Flow (Draft)"` hidden from users when it is intentional preview copy | Keep preview indicators when they communicate scientific limitation; do not rename without review |

---

## Implementation Rules

UI polish passes must obey project constraints:

1. **Do not change scientific algorithms** — tracking, optical flow, ROI math, orientation, metric formulas, and analysis aggregation stay untouched.
2. **Do not change workspace schema** — folder layout, metadata formats, and migrations are out of scope for polish.
3. **Keep widget object names stable** unless explicitly approved — tests and workflows may depend on attribute names (`edit_export_name`, `btn_roi_actions`, etc.).
4. **Prefer small, reviewable visual hierarchy changes** — one panel or tab per diff when possible; easy to revert.
5. **Update regression tests when labels, titles, or layout guards change** — especially `tests/test_terminology.py` and `tests/test_gui_styles.py` for string and token guards.
6. **Do not rename user workflows** — no new steps, removed buttons, or shortcut additions during polish unless scoped separately.

Before merging polish work, run:

```bash
.venv/bin/python -m compileall actintrack_app tests
.venv/bin/python -m unittest discover -s tests
```

---

## Cursor Usage

When using Cursor (or any agent) on UI work:

1. **Reference this document** in prompts for Phase 5.5 polish tasks.
2. **Audit the target panel against this guide before editing** — list redundant titles, nested boxes, and duplicate labels first.
3. **If uncertain, report options instead of guessing** — e.g. flat section vs single group box, with trade-offs; do not silently redesign workflows.
4. **Scope control** — documentation-only tasks stay in docs; polish tasks touch only the requested panel and its tests.
5. **Never commit unless explicitly requested** — especially avoid staging `.cursor/`, workspaces, or runtime data.

Example prompt fragment:

> Phase 5.5 panel polish — follow `docs/design/ui_design_system.md`. Reduce chrome on [panel]. No algorithm, schema, or workflow changes.

---

## Related References

- Project rules: `.cursor/rules/actintrack.mdc`
- Style tokens: `actintrack_app/gui_styles.py`
- User terminology guards: `tests/test_terminology.py`
- Completed hierarchy example: Orient/ROI export section (commit `b765bfa` — flat export name section, no nested Export Name group box)

---

## Open Questions / Ambiguities

These are intentionally deferred; resolve with a human before large visual passes:

1. **Bordered panel hosts** — metric status uses a framed host; playback borders are deferred. When is a border justified vs whitespace only?
2. **Global QSS / dark theme** — canvas target `#1e1e1e` vs native palette; full theme pass not started.
3. **Preview-scientific labels** — e.g. **Optical Flow (Draft)** signals preview-only behavior; changing copy needs PI/scientific review.
4. **Analysis table column UX** — table polish is separate from sidebar hierarchy rules above.

When in doubt, propose two layouts and stop.
