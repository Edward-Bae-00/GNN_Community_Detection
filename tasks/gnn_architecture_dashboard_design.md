# Standalone GNN Architecture Dashboard Comparison

**Date:** 2026-07-30

## Goal

Restore a dashboard section that compares every GNN architecture currently
available in the repository:

- GraphSAGE (`sage`)
- typed RGCN (`rgcn`)
- GAT (`gat`)
- GIN (`gin`)
- approximate KPI-AA (`kpiaa`)

This is a GNN-only comparison. The workflow must not fit, score, evaluate, or
publish the tabular Baseline, Hybrid, or oracle-Hybrid arms.

## Evaluation Contract

All five architectures use the same:

- V9 corpus, temporal train/validation/test split, and oracle identity substrate;
- graph identity universe and as-of edge construction;
- caught-label supervision available strictly before the training cutoff;
- three seeds: `0`, `1`, and `2`;
- epoch count and training bucket;
- validation and test event ordering;
- inspection depths and daily budgets.

Training uses the deployment-observable caught label (`detected_flag`).
`false_negative_flag` remains evaluation-only. Future outcomes, lifetime
catches, hidden organization labels, outcome aggregates, Baseline scores, and
Hybrid scores are not model inputs.

The artifact records enough provenance to reject mixed or stale runs: schema
version, corpus identity, substrate, seeds, epochs, training bucket, feature
schema, relation schema, inspection depths, daily budgets, and architecture
metadata. Publication is atomic so the dashboard never reads a partial run.

## Architecture

Add a dedicated GNN bake-off runner rather than calling `gnn.run_demo.main()`
five times. It prepares the shared corpus, graph, caught times, training labels,
and evaluation pools once, then trains each registered `GNN_ARMS` architecture
for the three standard seeds.

The runner emits one architecture-only artifact under `gnn/diagnostics/`.
It contains no Baseline, Hybrid, oracle-Hybrid, fusion-weight, or recovery
explainer fields.

For each architecture, the artifact includes:

- ensemble whole-pool found, precision, recall, and F1 at each global depth;
- ensemble found and recall for the observable, dark, and lone strata;
- ensemble fixed-daily-budget results;
- per-seed found and recall at every global depth, without embedding event-level
  scores or model weights.

The existing canonical `demo_comparison_v9.json`, GraphSAGE/Hybrid headline,
checkpoint workflow, and recovery explorer remain unchanged.

## Dashboard Design

The V9 dashboard builder loads the bake-off artifact independently of the
canonical demo artifact and validates its schema and corpus identity before
embedding it.

This change is strictly additive. It must not remove, replace, reorder, rename,
or alter any existing dashboard section, navigation entry, chart, table,
artifact, interaction, accessibility behavior, or generated result. The new
section is inserted at one stable boundary in the existing V9 Results tab and
uses its own element identifiers and rendering state.

Add a distinct **GNN architecture comparison** section to the V9 Results tab.
It contains only the five GNNs and provides:

1. a population toggle for whole pool versus observable slice;
2. an inspection-depth selector;
3. an accessible comparison chart showing recall for every architecture at the
   selected depth;
4. an exact-value table with architecture, ensemble found and recall, plus the
   minimum and maximum per-seed found and recall values;
5. a collapsed daily-budget table with found, precision, recall, and F1 for
   every architecture;
6. a compact provenance note listing corpus, seeds, epochs, and training bucket.

Whole-pool precision and F1 stay in the artifact and daily table but are omitted
from the population comparison table because the observable-slice artifact
contract contains found and recall only. This keeps the population toggle
semantically consistent.

The typed RGCN and approximate KPI-AA labels remain explicit so the chart does
not imply that all architectures use identical message-passing semantics.

If the artifact is absent, invalid, incomplete, or belongs to another corpus,
the section renders a clear unavailable state and the exact rerun command. It
must not silently substitute the canonical GraphSAGE result or hide missing
architectures.

## Error Handling

- Reject unknown, missing, or duplicate architecture identifiers.
- Require exactly the complete current `GNN_ARMS` registry.
- Reject non-finite metrics, incompatible seeds/configuration, mismatched corpus
  identity, and inconsistent denominators.
- Preserve the last complete artifact if a training run fails.
- Report the failed architecture and leave a nonzero process exit status.
- Let the dashboard build continue with an unavailable comparison state when
  the optional artifact is missing or invalid.

## Verification

- Unit-test that the bake-off runner trains every registered architecture and
  never calls Baseline or Hybrid fitting/fusion code.
- Test deterministic three-seed aggregation and artifact validation.
- Test dashboard loading, wrong-corpus rejection, missing/incomplete artifact
  behavior, and the exact five-model UI contract.
- Test that all pre-existing dashboard sections, identifiers, navigation
  entries, and render invocations remain present and in their original order.
- Run the bake-off on the V9 development corpus as a smoke test.
- Run the full V9 five-architecture, three-seed comparison.
- Rebuild the dashboard and verify the section visually, including keyboard
  operation, responsive layout, accessibility labels, and exact table values.
- Re-run the affected source tests.
