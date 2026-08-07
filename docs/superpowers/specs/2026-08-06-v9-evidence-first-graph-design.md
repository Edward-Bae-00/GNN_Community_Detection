# V9 Evidence-First Explanation Graph Design

**Date:** 2026-08-06

## Goal

Make the explanation graph in the V9 results tab understandable at a glance.
The default view should foreground the strongest published GNN explanation
evidence while preserving the existing first-hop, second-hop, component-pool,
and rank-fusion stages. Relationship type and model evidence weight must remain
visually distinct.

This is a presentation-only change. It does not change model scores, graph
construction, sidecar contents, strict as-of validation, sampling limits, or
the complete community tables.

## Design Read

This is a dense research dashboard for technical reviewers. The graph should
use a restrained evidence-reader language: quiet community context, explicit
relationship semantics, one functional evidence highlight, stable labels, and
controls grouped by the question they answer.

The selected direction is the approved dual-channel edge treatment. Visible UI
copy uses **Model evidence weight**. Supporting copy may identify this as
GNNExplainer attribution.

## Current Problems

The existing graph uses the same edge stroke to communicate relationship type,
stage emphasis, and attribution. Attributed edges become gold, which hides
whether an edge is co-travel, residence, or shared plate. The toolbar also mixes
view mode, explanation stage, zoom, search, and label density without group
labels.

The current Grounded narrative panel renders an unavailable sentence when its
narrative payload does not pass the strict validator. In the published schema-3
bundle, unsupported narrative metadata can therefore leave the most prominent
explanation section without case-specific evidence even though ranked node and
edge attribution is available.

## Graph Visual Encoding

### Edge layers

Each attributed edge uses two strokes:

1. A wider gold underlay communicates **Model evidence weight**. Its width and
   opacity are deterministic functions of the unsigned median explainer weight.
2. A narrower relationship stroke sits above the underlay and communicates the
   observable edge type using both color and pattern.

The relationship mapping is:

- Co-travel: green, solid.
- Residence: blue, dashed.
- Shared plate: violet, dotted.
- Unknown future relationship types: neutral gray, long dash, with the literal
  relationship name retained in labels and the table.

Non-attributed context edges never receive the gold underlay. They retain the
same relationship color and pattern at lower opacity. In Evidence first mode,
stage-relevant context is visible at medium emphasis and remaining community
context is quiet. In Full community mode, the base context becomes more visible
while attributed edges keep their gold underlay.

This keeps two facts independent: the inner stroke says what the relationship
is, while the outer stroke says how strongly the explainer relied on it. The
gold weight is unsigned salience, not causal direction or proof of wrongdoing.

### Edge labels

The three strongest attributed edges in the current stage and relationship
selection receive inline labels. Labels use the stable ordering already carried
by attribution rank when valid, then weight descending and edge ID as a stable
fallback.

Each label contains the display rank, plain-language relationship name, and
formatted model evidence weight, for example `#1 Co-travel 0.91`. Labels use a
dark backed rectangle and a short leader when necessary. The renderer places
labels in priority order and skips a lower-priority label if its box would
overlap a higher-priority label or node marker.

Key node labels remain visible for the target, search match, and endpoints of
the labeled evidence edges. The complete graph table remains the authoritative
non-canvas source for every endpoint, edge ID, relation, rank, and weight.

### Nodes

- The selected target keeps the green double-ring marker.
- A caught-before-snapshot node keeps the blue fill.
- An attributed node receives a gold evidence ring whose weight follows the
  same unsigned evidence semantics as edge underlays.
- Search matches receive a separate high-contrast outline.

Shape, ring, pattern, and text accompany color so the graph does not depend on
color alone.

## Controls and Defaults

The toolbar becomes a small set of labeled control groups.

### View

- **Evidence first** is the default and replaces the ambiguous Flow label.
- **Full community** replaces All.

This is a presentation rename and refinement of the current modes. It does not
change the authoritative graph or table data.

### Stage

The existing mutually exclusive stages remain unchanged:

- First hop, selected by default.
- Second hop.
- Component pool.
- Rank fusion.

A short stage description below the controls updates with the selection so the
user can understand what the stage emphasizes before reading the graph.

### Relationship

The graph adds an **All types** selection followed by the relationship types
present in the current drawable graph, ordered as Co-travel, Residence, Shared
plate, then any unknown types alphabetically. Selecting a relationship filters
only the canvas presentation and its inline labels. The complete table remains
unfiltered and complete.

### Labels, search, and navigation

- Labels: Key labels, All labels, None. Key labels replaces Auto and is the
  default.
- Search remains a node-identifier search and continues to mark the matching
  node without deleting graph evidence.
- Navigation retains Zoom in, Zoom out, and Reset view. Redundant controls with
  identical behavior are removed.
- When the selected case first loads in Evidence first mode, the viewport fits
  the target and attributed evidence endpoints with padding. Reset view returns
  to that evidence framing. Full community mode resets to the full normalized
  community frame.

On narrow screens the groups stack in the same order. Every interactive target
remains at least 44 pixels tall, labels wrap without page-level horizontal
overflow, and the graph keeps its existing bounded height.

## Grounded Narrative Fallback

Narrative validation remains strict and unchanged.

- When a narrative passes validation, the Grounded narrative panel renders it
  as it does today. Highest-attribution evidence remains available in its
  technical disclosure.
- When a narrative is unavailable or rejected, the Grounded narrative panel
  renders the existing deterministic Highest-attribution evidence component in
  place of the generic unavailable sentence.
- In that fallback state, the separate attribution disclosure is omitted to
  avoid showing the same evidence twice.
- When neither a validated narrative nor valid attribution ranking is
  available, the panel states that no validated narrative or ranked attribution
  is available. It does not infer or fabricate a story.

The fallback continues to show at most three nodes and three connections, with
rank, stable identifiers, relationship type, edge ID, and unsigned median model
evidence weight.

## Data Flow and Boundaries

The existing SHA-256-verified sidecar loader and schema-3 detail builder remain
the only data sources.

Presentation state gains a relationship selection and clearer view-mode names.
The draw-command builder continues to produce the bounded canvas nodes and
edges plus complete table rows. Relationship filtering derives a canvas-only
edge list from those validated commands. Evidence-label selection derives from
validated attributed edges and never reads unverified payload fields.

Edge rendering separates relationship styling from evidence styling instead of
overwriting one with the other. No published artifact is rewritten, and no
edge or node is added by the UI.

## Accessibility

- Each control group has an accessible name and each segmented option retains
  `aria-pressed` state.
- The canvas accessible name includes the case, view, stage, selected
  relationship, visible node and edge counts, and the meaning of model evidence
  weight.
- The legend names each relationship color and pattern, the gold weight
  underlay, target marker, caught-before-snapshot marker, and attributed-node
  ring.
- Inline canvas labels are supplementary. The complete table and
  Highest-attribution evidence panel remain the accessible text equivalents.
- Keyboard focus restoration, pan and zoom input, reduced-motion behavior, and
  strict-bound failure states remain intact.

## Failure and Empty States

- A missing or invalid evidence boundary still fails closed before the graph or
  fallback evidence renders.
- Missing or malformed attribution removes the gold evidence treatment and
  produces the existing explicit unavailable state. It never falls back to an
  inferred weight.
- A relationship selection with no drawable edges shows the target and a short
  empty-state message, with a direct All types control available.
- Oversized communities keep the existing 1,500-node and 4,000-edge canvas
  limits and the complete paginated tables.

## Verification

Focused tests will cover:

- Evidence first and First hop defaults.
- View, stage, relationship, label, and navigation control copy and accessible
  state.
- Relationship filter behavior without mutation or loss of complete table
  rows.
- Relationship color and pattern mapping, including the neutral unknown type.
- Gold evidence underlay scaling independently from the relationship core.
- Stable strongest-edge label selection and overlap suppression.
- Canvas accessible descriptions and expanded legend semantics.
- Grounded narrative behavior for validated narrative, attribution fallback,
  and fully unavailable evidence.
- Suppression of the duplicate attribution disclosure in fallback mode.
- JavaScript syntax, mount cleanup, focus restoration, responsive controls, and
  existing schema-3 sidecar and as-of validation contracts.

The focused recovery explainer and V9 dashboard-builder test suites will run,
followed by Python compilation, dashboard rebuild validation, `merget diff`
review, and `git diff --check`. The rebuilt desktop and narrow layouts will be
visually inspected when local browser tooling is available.

## Non-Goals

- No model training, ranking, scoring, explainer-generation, or evaluation
  changes.
- No artifact schema or published sidecar changes.
- No change to strict as-of evidence rules or fail-closed validation.
- No force-directed layout or new graph dependency.
- No case-cohort filtering redesign outside the selected explanation graph.
- No narrative-validator expansion in this pass.
