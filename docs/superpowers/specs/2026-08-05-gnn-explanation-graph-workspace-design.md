# GNN Explanation Graph Workspace Design

**Date:** 2026-08-05  
**Status:** Approved for implementation

## Goal

Reorganize the schema-3 GNN explanation explorer so the selected explanation
dominates the page, the graph becomes the primary visual workspace, and the
supporting evidence remains easy to read with deliberate spacing.

This design refines the layout direction in
`2026-08-05-explanation-dashboard-readability-design.md`. Its numeric-format,
typography, evidence, and accessibility contracts remain in force. This design
supersedes only that document's narrative-first spatial order: the selected
case header and rank comparison now lead into the graph, with the grounded
narrative immediately below it.

## Current problems

The current explorer uses several nested grids at once:

- six summary cards and a standalone “Showing GNN explanations only” status
  consume the top of the section before the selected case appears;
- the case list and selected detail use a 40/60 split, but the case list has no
  bounded height, rail surface, or independent scrolling;
- the detail then creates another narrow evidence/graph split, leaving the
  narrative, factors, graph, controls, and tables competing for width;
- dense technical sections remain expanded, which produces a long and uneven
  page beside an unbounded case list;
- the containing section references `v9-recovery-title` with
  `aria-labelledby`, but the rendered heading does not currently receive that
  identifier; and
- duplicate status CSS declarations make the intended visual hierarchy
  unclear.

These are presentation problems. The published schema-3 artifact, explained
case eligibility, lazy sidecar loading, as-of validation, graph commands, and
model outputs are not changing.

## Approved direction

Use a graph-first evidence workspace with five clear zones:

1. a full-width selected-case header with explanation count, event context,
   strict as-of provenance, and the single-seed scope note;
2. a full-width Baseline / Seed-0 GNN / Seed-0 Hybrid rank strip;
3. a bounded case rail beside a large graph workspace;
4. an open grounded narrative and key-factor row directly below the graph;
5. collapsed technical disclosures for stability, faithfulness, attribution,
   complete tables, and recovery-cohort context.

The selected case owns the visual hierarchy. The case rail is secondary
navigation, not an equal content column.

## Visual system

Continue the existing V9 design system rather than introducing a new theme:

- Outfit remains the heading and prose face;
- JetBrains Mono remains the face for ranks, IDs, dates, scores, and tables;
- the existing dark canvas and surface tokens remain authoritative;
- the selected state, Hybrid rank, focus, and primary interaction use the
  existing green accent;
- amber, blue, and red remain semantic graph/evidence/warning colors only;
- the graph canvas uses a quiet sunk surface and restrained inner separation,
  without adding decorative multicolor gradients or glow; and
- prose uses a comfortable measure and at least 13px where space permits.

Spacing and hierarchy, rather than more cards or more color, should create the
premium treatment.

## Component design

### Selected-case header

Replace the large section-level introduction, six-card summary, and standalone
GNN-only status bar with one selected-case header.

The header contains:

- “19 published GNN explanations” or the actual eligible count;
- “Why case `<person id>` surfaced”;
- event ID and scoring day;
- a concise strict as-of statement;
- “GraphSAGE seed 0”; and
- “Hybrid score is percentile fusion, not probability.”

The heading receives `id="v9-recovery-title"` so the existing containing
section has a valid accessible name. The eligible count and copy derive from
the existing schema-3 view model; no count is hardcoded. The strict as-of slot
shows a pending state until the selected sidecar validates, then renders the
published snapshot and rules. It renders an unavailable/error state instead
of asserting a boundary before validation succeeds.

### Rank strip

Render the three existing ranks directly below the header in aligned cells:

- Baseline rank;
- Seed-0 GNN rank; and
- Seed-0 Hybrid rank.

The Hybrid cell receives the strongest treatment. Its label includes the
plain-language movement relative to Baseline, such as “127 places higher.”
Existing number formatting and rank semantics remain unchanged. Secondary raw
scores and percentiles move into the recovery-cohort or technical disclosure
instead of sitting loose below the strip.

### Case rail

On screens wider than 900px, use a 214px secondary rail with
`max-height: min(70vh, 720px)`, independent vertical scrolling, and
`position: sticky` at 16px from the top of its explanation workspace.

Each row shows:

- case identifier;
- Hybrid rank; and
- rank movement relative to Baseline.

The selected row uses the existing accent, `aria-current="true"`, and a clear
inset marker. The rail header states that these are published GNN explanations
and displays the eligible count. Only the existing `gnn_explanation` records
remain selectable.

### Graph workspace

The graph receives the largest uninterrupted surface in the selected-case
detail. Its toolbar, graph-stage controls, mode controls, zoom controls, label
density, legend, sampled-context note, and canvas remain one visual unit.

The default state remains:

- flow mode;
- first-hop stage;
- automatic label density; and
- fitted initial transform.

Above 900px, the graph height is `clamp(420px, 52vh, 560px)`. From 701px to
900px, it is `clamp(360px, 48vh, 470px)`. At 700px and below, it is 340px with
a 300px minimum. The complete non-canvas table remains the authoritative
accessible fallback.

### Narrative and key factors

Immediately below the graph, render an asymmetric two-column row:

- the grounded narrative receives the wider reading column; and
- the stable measured factors receive the narrower supporting column.

The narrative retains source references, validation status, and the existing
non-causal wording. Each factor keeps its stability label, signed rank effect,
and measured-effect semantics. The row collapses to one column on narrow
screens.

### Technical disclosures

The following sections are closed by default and use accessible disclosure
semantics:

1. restart stability and removal faithfulness;
2. highest-attribution nodes and relationships;
3. complete community node and relationship tables; and
4. recovery-cohort context, including the six existing summary metrics and
   coverage counts.

Use native `<details>`/`<summary>` elements. Preserve their open state during
graph-control rerenders for the selected case, and reset the state when a new
case is selected. The complete table disclosure keeps its existing pagination
and contained horizontal overflow.

## Responsive behavior

### Above 900px

- Use the bounded 214px case rail beside the graph workspace.
- Keep the selected-case header and rank strip full width.
- Keep the narrative/factor row asymmetric.

### At 900px and below

- Replace the rail with a compact native case picker above the selected-case
  detail.
- Give the graph the full available width.
- Keep rank cells in one row while their labels remain readable.

### At 700px and below

- Keep the three rank cells in one compact row down to a 360px container; stack
  them only below 360px.
- Stack narrative and factor panels.
- Render graph controls as a wrapping two-column grid with 44px minimum touch
  targets.
- Prevent page-level horizontal scrolling; only bounded tables may scroll
  horizontally.

## Data flow and interaction contracts

Case selection continues to use the existing schema-3 path:

1. select an eligible manifest record;
2. load its SHA-256-verified case sidecar;
3. load the referenced community sidecar and node/edge chunks;
4. load and validate the explanation overlay chunks;
5. assemble the strict as-of community and explanation presentation; and
6. render the graph, narrative, factors, and disclosures.

Keep the request token that discards stale asynchronous results when the user
changes cases. Keep focus restoration after rerenders, graph cleanup, pointer
and wheel behavior, ResizeObserver cleanup, deterministic bounded-context
selection, and table pagination.

No new dependency, framework, graph layout, or artifact field is introduced.

## Loading, empty, and error states

### Loading

Keep the rail or narrow case picker interactive while the selected evidence
loads. Mark the detail region `aria-busy="true"` and render layout-shaped
skeletons for the graph, narrative, and factors, together with explicit
“Loading selected evidence” text for assistive technology. Skeleton motion is
disabled under `prefers-reduced-motion`.

### Empty

If no published GNN explanations exist, render one composed empty state that
states why no cases are selectable and keeps recovery-cohort context available
when the manifest summary is valid.

### Error

Render sidecar, integrity, and validation failures inside the selected-case
workspace without replacing the case rail. Show the existing evidence-safe
error copy and a “Retry evidence” action that calls the existing selected-case
load path. Do not infer, substitute, or draw evidence after a failed contract.

If the strict as-of evidence boundary is missing or invalid, continue to fail
closed: do not render the graph, narrative, factors, attribution, or technical
evidence for that case.

## Accessibility

- Fix the `v9-recovery-title` accessible-name reference.
- Preserve explicit labels for ranks, graph modes, stages, zoom, label density,
  evidence weights, and pagination.
- Preserve `aria-current` on the active case and restore focus after selection
  or graph-control rerenders.
- Give loading, empty, and error regions appropriate status semantics.
- Keep all narrow-screen controls at least 44px high.
- Preserve the canvas description and complete non-canvas data tables.
- Keep color paired with labels, shapes, or text; color never carries evidence
  meaning alone.
- Continue respecting `prefers-reduced-motion`.

## Implementation boundary

The primary implementation surface is
`Documents/Data/scripts/v9_recovery_explainer_ui.py`, with focused assertions
in `tests/test_v9_recovery_explainer_ui.py` and integration checks in
`tests/test_v9_dashboard_builder.py` where required.

Do not rewrite or regenerate source artifacts. Do not change
`build_v9_dashboard.py` artifact selection, schema-3 packaging, recovery
sidecars, graph evidence semantics, model code, or evaluation logic as part of
this redesign.

The working tree already contains a large schema-3 cleanup diff. Implement the
redesign on top of the current file and review the scoped diff carefully so
removed legacy schema-1/schema-2 code is not restored.

## Testing and verification

Add or update focused tests for:

- selected-case header and valid `v9-recovery-title` linkage;
- graph-before-narrative DOM order;
- bounded desktop rail and narrow-screen case picker;
- rank strip and plain-language rank movement;
- default-closed technical disclosures and state reset on case selection;
- loading skeleton, `aria-busy`, empty state, inline error, retry action, and
  strict-bound fail-closed behavior;
- responsive graph, control, prose, and table rules;
- focus restoration, listener cleanup, canvas cleanup, and stale-request
  protection; and
- continued explained-only filtering and eligible-count accuracy.

Verification must include:

1. focused recovery UI tests;
2. focused dashboard builder and design-system tests;
3. generated JavaScript syntax validation;
4. Python compilation for changed generator modules;
5. dashboard rebuild from unchanged source artifacts;
6. desktop and narrow visual inspection of the rebuilt GNN explanation view;
7. `git diff --check`; and
8. a scoped diff review confirming that source artifacts and unrelated
   dashboard sections did not change.

## Out of scope

- Model training, scoring, explainability generation, or evaluation changes.
- Artifact, manifest, sidecar, or corpus schema changes.
- New case eligibility, filters, cohorts, or baseline-control UI.
- A new frontend framework, styling library, or graph dependency.
- Redesigning other V9 Results sections or other dashboard tabs.
- Removing the complete evidence tables or weakening strict as-of validation.
