# Schema-3 explanation graph presentation design

**Date:** 2026-08-04

## Goal

Make the schema-3 recovery explorer show only cases with published GNN explanations and make the full as-of community graph readable by visually separating quiet network context from weighted explanation evidence.

## Design read

This is a dense research dashboard for technical analysts. The graph should use a restrained dark observability language: low-contrast structural context, one high-signal attribution accent, compact monospace identifiers, and explicit evidence semantics rather than decorative network art.

## Scope

The change applies only to the schema-3 recovery explorer. It will:

- restrict the visible recovery-case list to records whose `detailKind` is `gnn_explanation`;
- load the bounded explanation overlay only for those records;
- merge overlay attribution medians into matching community edges and nodes;
- render base community context with low visual weight and explanation evidence with weight-driven stroke/ring emphasis;
- keep stage controls, search, zoom, labels, and the complete evidence tables;
- provide a bounded context canvas for oversized communities while retaining every explanation node and edge and stating that the context layer is sampled.

Baseline controls and records without a published explanation remain in the underlying manifest and summary for provenance, but they are not selectable in this explanation-focused explorer.

## User experience

The recovery explorer opens on the explained-case view. The case list count describes the visible explained set, and each row represents a published GNN explanation rather than a structural control or an unselected candidate.

The graph has two visual layers:

1. **Community context:** all drawable as-of nodes and relationships use muted relation colors, thin strokes, and low opacity. Target, previously caught, pooled, and search-matched nodes retain distinct accessible markers.
2. **Explanation evidence:** overlay edges and nodes are matched by stable IDs. Edge `explainer_median` controls stroke width and opacity; attributed nodes receive a visible ring and a radius proportional to their normalized weight. The target remains visually primary. Flow mode adds arrows to the stage-emphasized evidence while preserving quiet context.

The legend names both layers and explains that the evidence scale is unsigned explainer salience, not a causal effect. Default labels show the target and attributed endpoints; the existing label-density control can reveal all identifiers.

For a community above the current interactive node/edge budget, the renderer deterministically retains the target, every explanation node, every explanation edge, and a bounded set of context nodes/edges selected by stable identifier order. The panel states the full community counts and that the displayed context is sampled for performance. The paginated full node and relationship tables remain authoritative and complete.

## Data flow and contracts

The existing SHA-256-verified sidecar loader remains the only source of published data. For an explained case, schema-3 selection loads the case sidecar, community sidecar, community chunks, and the case's `overlay_evidence.node_chunks` and `overlay_evidence.edge_chunks`. Overlay rows are accepted only when their owner/schema contracts are valid and their IDs match the loaded community universe. Missing or conflicting IDs fail closed to the existing evidence error state; an absent optional overlay produces a neutral graph only if the case payload itself remains valid.

The merged graph model keeps the original community rows intact and adds presentation fields (`importance`, `attributed`, and bounded-view membership) at the renderer boundary. This avoids rewriting published sidecars and keeps provenance/table output separate from canvas styling.

## Accessibility and performance

- Canvas receives an accessible description that names the case, stage, mode, visible context policy, and evidence-layer meaning.
- The non-canvas graph table remains rendered for every explained case.
- Keyboard controls and existing focus restoration remain unchanged.
- Sampling is deterministic, so the same case and mode produce the same visual context.
- No new dependency or force simulation is introduced; canvas work stays bounded and uses existing pointer/zoom interaction.

## Verification

Tests will cover:

- explained-only schema-3 filtering and stable ordering;
- overlay weights merging into matching edge/node presentation fields;
- invalid, missing, duplicate, or out-of-community overlay IDs failing closed;
- bounded context selection retaining the target and all explanation evidence;
- graph rendering copy and accessibility hooks remaining present;
- the existing schema-2 renderer and baseline structural-control policy remaining unchanged.

The generated dashboard will be rebuilt from the feature worktree and checked with the focused UI/builder test suites, JavaScript syntax validation, HTTP serving smoke checks, and a headless screenshot when browser tooling is available.

## Non-goals

This change does not alter GNN scores, explainer generation, sidecar schemas, as-of evidence rules, published metrics, baseline behavior outside the schema-3 explorer, or the underlying complete community tables.
