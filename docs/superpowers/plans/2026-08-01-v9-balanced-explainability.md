# V9 Balanced Recovery Explainability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a leak-safe V9 Results explainability workspace with full-cohort score/rank summaries, up to 20 detailed Hybrid-win GNN explanations, and up to 10 Baseline-win community-only controls.

**Architecture:** Keep model explanation offline and extend the existing recovery artifact pipeline with a partial-coverage schema 3.0. The producer freezes a deterministic 20/10 case selection before explanation work, runs exact two-hop GNNExplainer only for eligible Hybrid cases, writes structural sidecars for Baseline controls, and publishes content-addressed lazy evidence. The existing recovery explorer remains the dashboard mount; its view model branches by detail kind rather than creating a second UI.

**Tech Stack:** Python 3.14, pandas/numpy, PyTorch Geometric, vanilla JavaScript/CSS dashboard assets, JSON sidecars, SQLite-backed recovery bundle staging, pytest, static dashboard builder.

---

## File map

### Domain and producer

- Modify `gnn/recovery_observability.py` to generalize exclusive recovery cases,
  materialize the aggregate recovered-by-both anchor, and freeze deterministic
  20/10 selection metadata.
- Modify `gnn/sage_explainer.py` to expose exact-subgraph eligibility preflight
  without pruning explainer inputs.
- Modify `gnn/observability_artifact.py` to build and validate schema-3 full
  summaries, selected Hybrid explanations, Baseline structural controls, and
  explicit partial coverage.
- Modify `gnn/recovery_bundle.py` to publish selected schema-3 detail cases
  without requiring every Hybrid-only case to be explained.
- Modify `gnn/giant_observability_benchmark.py` to measure the selected Hybrid
  explainer work and assert that Baseline controls make zero explainer calls.
- Modify `gnn/run_demo.py` to expose separate `hybrid_detail_limit=20` and
  `baseline_control_limit=10` settings for initial and resumed observability
  generation.

### Dashboard and sidecars

- Modify `Documents/Data/scripts/v9_recovery_sidecars.py` to validate and stage
  schema-3 partial indexes while preserving schema-2 validation behavior.
- Modify `Documents/Data/scripts/build_v9_dashboard.py` to load schema 3.0,
  publish its sidecar bundle, and retain legacy schema-1/schema-2 fallback.
- Modify `Documents/Data/scripts/v9_recovery_explainer_ui.py` to render the
  three-cohort summary, 20/10 case filters, score/rank cards, Hybrid technical
  evidence, Baseline structural-only evidence, and partial/failure states.
- Modify `Documents/Data/scripts/v9_dashboard_ui.py` only if the existing
  recovery mount needs a new summary placement; preserve the mount ID and
  existing Results-tab order.

### Tests and documentation

- Create `tests/test_balanced_recovery_explainability.py` for pure selection,
  score-summary, schema-3 artifact, and producer-policy contracts.
- Modify `tests/test_sage_explainer.py` for exact-subgraph eligibility and
  oversized-case behavior.
- Modify `tests/test_recovery_bundle.py` for schema-3 partial publication and
  Baseline structural-only case validation.
- Modify `tests/test_v9_recovery_explainer_ui.py` for schema-3 view-model,
  score/rank, detail-kind, stage, and fallback contracts.
- Modify `tests/test_v9_dashboard_builder.py` for schema-3 loading and mount
  preservation.
- Modify `Documents/Data/changes_3.md` with the balanced observability policy
  and actual generated coverage only after the artifact is regenerated.
- Update `PROJECT_MEMORY.md` with the durable 20/10 selection and schema-3
  decision after implementation is verified.

## Task 1: Lock balanced cohort and selection behavior with failing tests

**Files:**
- Create: `tests/test_balanced_recovery_explainability.py`
- Modify: `tests/test_v9_corpus_snapshot.py` only if the fixture needs an
  existing V9dev as-of timestamp helper; otherwise leave it unchanged.

- [ ] **Step 1: Add a minimal frozen-case fixture.**

Create small immutable case dictionaries containing `person_id`, event/day
anchor, Baseline/GNN/Hybrid ranks and percentiles, relationship categories, and
the cohort label. Include at least four relationship signatures and two scoring
periods so the diversity selector can be tested without loading the full V9
corpus.

- [ ] **Step 2: Test exact cohort algebra including recovered-by-both.**

Add a test that constructs Baseline and Hybrid recovered ID sets and asserts the
summary contains the exact values from `RecoveryOverlap.summary`, including
`recovered_by_both`, `hybrid_only_recovered`, `baseline_only_recovered`, and
`net_gain`. Add a second assertion that a materialized both-arm record uses the
earlier first-recovery anchor and records `recovery_anchor_arm`.

- [ ] **Step 3: Test the frozen 20/10 selector.**

Call the planned pure selector with more than 20 Hybrid candidates and more than
10 Baseline candidates. Assert that it returns no more than 20/10, preserves
cohort disjointness, includes relationship/period diversity before score ties,
and returns the same ordered IDs on repeated calls.

- [ ] **Step 4: Test no post-explanation replacement.**

Mark one selected Hybrid ID as failed in a generated-result map and assert that
the serialized selection still contains that ID with `detail_status="failed"`
and a failure reason rather than replacing it with the next candidate.

- [ ] **Step 5: Test lightweight score coverage.**

Assert that every full-cohort summary record exposes:

```python
required = {
    "baseline_raw", "baseline_percentile", "baseline_rank",
    "seed0_gnn_probability", "seed0_gnn_percentile", "seed0_gnn_rank",
    "seed0_hybrid_score", "seed0_hybrid_rank", "detail_status",
}
assert required <= record.keys()
```

Also assert that the Hybrid score is labeled as a fusion score in the policy or
field metadata and is never serialized under a probability field.

- [ ] **Step 6: Run the new tests before implementation.**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_balanced_recovery_explainability.py
```

Expected: FAIL because the balanced selector, aggregate anchor, and schema-3
summary functions do not yet exist.

## Task 2: Generalize recovery cases and freeze deterministic selection

**Files:**
- Modify: `gnn/recovery_observability.py`
- Modify: `tests/test_balanced_recovery_explainability.py`

- [ ] **Step 1: Add a cohort-aware recovery case type without breaking old imports.**

Introduce a `RecoveryCase` dataclass containing the current
`HybridOnlyCase` fields plus:

```python
cohort: str
recovery_anchor_arm: str
```

Validate `cohort` in `{"hybrid_only", "baseline_only", "recovered_by_both"}`
and `recovery_anchor_arm` in `{"baseline", "hybrid_seed0", "both"}`. Keep
`HybridOnlyCase` as a compatibility alias or constructor wrapper for existing
tests and callers, with `cohort="hybrid_only"` and
`recovery_anchor_arm="hybrid_seed0"`.

- [ ] **Step 2: Add both-arm anchor construction.**

Implement a pure helper that receives a person’s Baseline and Hybrid
`RecoveryAnchor` values, chooses the earlier `(scoring_day, inspected_rank,
event_id)` anchor, and returns the selected anchor plus
`recovery_anchor_arm`. Reject missing anchors instead of inventing a timestamp.

- [ ] **Step 3: Add `select_balanced_detail_cases`.**

Implement the selector with this interface:

```python
def select_balanced_detail_cases(
    hybrid_cases,
    baseline_cases,
    *,
    hybrid_limit=20,
    baseline_limit=10,
    eligible_hybrid_ids=None,
):
    """Return frozen ordered selections and a JSON-safe policy record."""
```

Sort by score gap first, then round-robin across normalized relationship
signatures and scoring periods, then use `person_id` as the final tie-break.
Use `eligible_hybrid_ids` only as a pre-explanation eligibility result. Select
the first 20/10 IDs from that frozen order and never replace a selected ID after
GNNExplainer, narrative, or stability generation.

- [ ] **Step 4: Add selection fingerprint material.**

Serialize quotas, limits, relationship signature normalization, tie-break order,
eligible Hybrid IDs, selected IDs, restart seeds, epochs, checkpoint ID, corpus
identity, and the current selection-policy version. Hash the canonical JSON with
the existing length-framed SHA-256 helper.

- [ ] **Step 5: Add tests for compatibility and fingerprint stability.**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_balanced_recovery_explainability.py \
  tests/test_sage_explainer.py -k "recovery or rank_reference"
```

Expected: the new balanced tests pass; existing recovery-observability tests
remain green.

- [ ] **Step 6: Record a focused commit or Merget checkpoint.**

Record only the recovery-observability implementation and its tests using the
repository’s Merget/Historian workflow.

## Task 3: Add exact explainer eligibility and structural-control helpers

**Files:**
- Modify: `gnn/sage_explainer.py`
- Modify: `gnn/observability_artifact.py`
- Modify: `tests/test_sage_explainer.py`
- Modify: `tests/test_balanced_recovery_explainability.py`

- [ ] **Step 1: Add exact-subgraph eligibility preflight.**

Implement:

```python
def explainability_eligibility(
    engine,
    person_id,
    scoring_day,
    *,
    max_nodes=MAX_LOCAL_EXPLANATION_NODES,
    max_edges=MAX_LOCAL_EXPLANATION_EDGES,
):
    """Measure the exact two-hop input; never prune it for eligibility."""
```

Call `member_subgraph(engine, person_id, scoring_day)`, read the exact local
node and directed-edge counts, and return JSON-safe `eligible`, `node_count`,
`edge_count`, `max_nodes`, `max_edges`, and `reason`. If the counts exceed the
limits, return `eligible=False` without slicing the tensors.

- [ ] **Step 2: Keep `run_member_explanation` exact for eligible cases.**

Do not change its local/full-logit parity behavior. Add an explicit guard so a
caller cannot pass an over-limit local graph into the final selected-case path
without an eligibility record.

- [ ] **Step 3: Add structural-only case materialization.**

Add a producer helper that obtains `Seed0ExplanationEngine.community` and
`build_flow_stages` for a Baseline control, retaining target/caught status,
relationship categories, component counts, and as-of provenance while omitting
GNNExplainer masks, counterfactual factors, and overlay fields.

- [ ] **Step 4: Test exactness and oversized behavior.**

Add tests that:

- return `eligible=True` for a fixture within 128 nodes/256 directed edges;
- return `eligible=False` with a stable reason for an oversized fixture;
- prove the oversized tensors were not pruned before rejection; and
- prove a Baseline structural record contains no `explanation` or
  `overlay_evidence` key.

- [ ] **Step 5: Run focused tests.**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_sage_explainer.py \
  tests/test_balanced_recovery_explainability.py
```

Expected: all focused explainer and eligibility tests pass.

## Task 4: Build and validate the schema-3 partial-coverage artifact

**Files:**
- Modify: `gnn/observability_artifact.py`
- Modify: `gnn/run_demo.py`
- Modify: `tests/test_balanced_recovery_explainability.py`
- Modify: `tests/test_run_demo_smoke.py`

- [ ] **Step 1: Add schema-3 policy constants and API parameters.**

Add named defaults:

```python
BALANCED_ARTIFACT_SCHEMA = "3.0"
DEFAULT_HYBRID_DETAIL_LIMIT = 20
DEFAULT_BASELINE_CONTROL_LIMIT = 10
EXPLAINER_RESTART_SEEDS = (0, 1, 2)
EXPLAINER_EPOCHS = 150
```

Extend `build_observability_artifact`, `build_observability_bundle`, and
`resume_observability` with `hybrid_detail_limit` and
`baseline_control_limit`. Keep the legacy `explanation_limit` argument as a
compatibility alias for the Hybrid limit and reject conflicting values.

- [ ] **Step 2: Build all lightweight summary cohorts.**

Generate exclusive Hybrid and Baseline case records as before, add the
recovered-by-both summary records using the earliest anchor helper, and place
the exact score/rank fields from the frozen rank reference into each record.
Set `detail_status="not_selected"` and `community_key=None` for non-selected
records.

- [ ] **Step 3: Preflight and freeze the 20 Hybrid IDs.**

Call `explainability_eligibility` for all Hybrid candidates before any
explanation generation. Pass only the eligible IDs to
`select_balanced_detail_cases`; persist the selected IDs and preflight reasons
in the run fingerprint and summary records.

- [ ] **Step 4: Generate one attempt per selected Hybrid ID.**

Replace the current “attempt until success limit” behavior with a frozen-prefix
attempt loop. For each selected ID, run the existing exact explanation and
validated narrative path once. On failure, record `detail_status="failed"`,
`failure_reason`, and no replacement ID. A successful deterministic narrative
fallback remains valid Hybrid evidence.

- [ ] **Step 5: Generate one community-only record per selected Baseline ID.**

Materialize and validate the strict as-of community without calling
`run_member_explanation`, `make_gnn_explainer`, or any counterfactual scorer.
Set `detail_kind="community_control"` and serialize the Baseline/GNN/Hybrid
score ledger alongside the community reference.

- [ ] **Step 6: Serialize the schema-3 shape.**

Write:

```python
{
    "schema_version": "3.0",
    "policy": {...},
    "summary": {...},
    "coverage": {
        "hybrid_requested": 20,
        "baseline_requested": 10,
        "hybrid_selected": int,
        "baseline_selected": int,
        "hybrid_explained": int,
        "baseline_community": int,
        "failed_count": int,
        "shortfall_reasons": [...],
    },
    "cohorts": {
        "hybrid_only": [...],
        "baseline_only": [...],
        "recovered_by_both": [...],
    },
    "detail_index": {...},
    "community_index": {...},
    "catalog_index": {...},
    "run_fingerprint": {...},
}
```

Validate that detail indexes are subsets of the full summary IDs, that no
Baseline detail has explanation/overlay fields, that all score fields are
finite and aligned, and that partial coverage is allowed but explicit.

- [ ] **Step 7: Add producer tests.**

Test complete summary algebra, 20/10 frozen selection, score fields, selected
detail statuses, Hybrid failure shortfall, Baseline no-explainer call count,
schema-3 JSON safety, and rejection of future/same-snapshot evidence.

- [ ] **Step 8: Run focused producer tests.**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_balanced_recovery_explainability.py \
  tests/test_run_demo_smoke.py
```

Expected: all schema-3 producer and smoke tests pass.

## Task 5: Publish schema-3 selected sidecars without weakening schema 2

**Files:**
- Modify: `gnn/recovery_bundle.py`
- Modify: `Documents/Data/scripts/v9_recovery_sidecars.py`
- Modify: `tests/test_recovery_bundle.py`

- [ ] **Step 1: Preserve schema-2 validation as a separate path.**

Keep the existing schema-2 complete-coverage validator unchanged for legacy
artifacts. Add a schema-3 validator rather than changing schema-2 semantics.

- [ ] **Step 2: Add schema-3 partial finalization.**

Add a `finalize_schema3` path that accepts the selected Hybrid and Baseline
detail IDs, the three lightweight cohorts, policy, coverage, summary, and run
fingerprint. It must require every selected detail case to have its referenced
community and sidecars, but it must not require all full-cohort cases to have
detail records.

- [ ] **Step 3: Extend case validation by detail kind.**

Keep Hybrid validation requiring complete explanation parity, validated grounded
narrative metadata, and nonempty overlay evidence. Add a Baseline structural
case path that requires a complete as-of community and score ledger while
rejecting `explanation`, `validation_metadata`, and `overlay_evidence`.

- [ ] **Step 4: Add schema-3 sidecar manifest validation.**

Implement `_validate_schema3_artifact` in
`v9_recovery_sidecars.py`. Verify:

- `schema_version == "3.0"`;
- exact three-cohort summary algebra;
- detail indexes contain only selected IDs;
- community references resolve for selected structural cases;
- catalog/chunk offsets and hashes are valid; and
- a Baseline control cannot reference an attribution overlay.

- [ ] **Step 5: Test partial publication and legacy isolation.**

Add tests that publish 20/10-style partial detail, reject missing selected
communities, accept unselected full-cohort cases without sidecars, reject a
Baseline overlay, and keep all existing schema-2 tests passing.

- [ ] **Step 6: Run bundle and sidecar tests.**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_recovery_bundle.py \
  tests/test_balanced_recovery_explainability.py
```

Expected: schema-2 regression tests and schema-3 partial-publication tests
pass together.

## Task 6: Load and render schema-3 evidence in the dashboard

**Files:**
- Modify: `Documents/Data/scripts/build_v9_dashboard.py`
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py`
- Modify: `Documents/Data/scripts/v9_dashboard_ui.py` only if mount placement
  requires it
- Modify: `tests/test_v9_recovery_explainer_ui.py`
- Modify: `tests/test_v9_dashboard_builder.py`

- [ ] **Step 1: Add schema-3 builder loading.**

Update `_load_recovery_artifact` to recognize schema 3.0, call the schema-3
sidecar publisher, and continue accepting schema 1.0 and 2.0 legacy artifacts.
Do not change the V9 recovery mount ID or embed large detail payloads into the
initial HTML.

- [ ] **Step 2: Extend the UI view model for three cohorts and coverage.**

Add a schema-3 branch that validates `summary`, `coverage`, all three cohort
arrays, `detail_index`, and `community_index`. Build a case map from lightweight
records and expose `detailStatus`, `detailKind`, `selectionReason`, and
`failureReason` to the renderer.

- [ ] **Step 3: Add summary and filters.**

Render full-cohort overlap metrics, Hybrid/Baseline detail coverage, and the
retrospective-cohort scope note. Add filters for `all`, `hybrid_only`,
`baseline_only`, `gnn_explanation`, `community_control`, and `all detail`. Keep
unselected and failed cases in the list.

- [ ] **Step 4: Add score/rank comparison cards.**

Render the exact fields with explicit labels:

```text
Baseline score / percentile / rank
Seed-0 GNN probability / percentile / rank
Hybrid percentile-fusion score / rank
```

Never label `seed0_hybrid_score` as a probability.

- [ ] **Step 5: Render Hybrid technical evidence.**

Reuse the existing staged graph, attribution, factor, stability, faithfulness,
narrative, and provenance panels for `detailKind === "gnn_explanation"`. Keep the
unsigned-mask caveat and the strict evidence-boundary panel visible.

- [ ] **Step 6: Render Baseline structural controls.**

Reuse the same graph-stage controls and as-of community renderer, but keep edge
emphasis neutral and suppress attribution/factor panels. Add the exact copy:

```text
Community context only — GNNExplainer was not run for this baseline control.
```

- [ ] **Step 7: Add failure and accessibility states.**

Render explicit messages for unavailable sidecars, hash failures, oversized
Hybrid cases, missing narratives, and partial coverage. Preserve keyboard
stage controls, relation labels, dynamic chart/graph accessible names, and the
non-canvas data table fallback.

- [ ] **Step 8: Add UI contract tests.**

Test three-cohort summary, 20/10 coverage labels, score semantics, Hybrid versus
Baseline detail branching, structural-only copy, failure states, filters, lazy
sidecar requests, stale-response discard, and accessibility fallbacks.

- [ ] **Step 9: Run UI and builder tests.**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_v9_recovery_explainer_ui.py \
  tests/test_v9_dashboard_builder.py
```

Expected: all existing legacy UI contracts and new schema-3 contracts pass.

## Task 7: Wire generation, resume, benchmark instrumentation, and diagnostics

**Files:**
- Modify: `gnn/run_demo.py`
- Modify: `gnn/giant_observability_benchmark.py`
- Modify: `tests/test_run_demo_smoke.py`
- Modify: `tests/test_giant_observability_benchmark.py`

- [ ] **Step 1: Wire separate generation limits.**

Pass `hybrid_detail_limit=20` and `baseline_control_limit=10` from both
`main(..., observability=True)` and `resume_observability(...)` into the schema-3
artifact builder. Preserve checkpoint/model/corpus fingerprints.

- [ ] **Step 2: Preserve resumability.**

Store the frozen selected IDs and each selected attempt’s status in the recovery
checkpoint. A resume must retry only unfinished selected IDs and must not create
a new selection order.

- [ ] **Step 3: Instrument explainer and baseline calls.**

Keep the existing encoder-forward counters for Hybrid GNNExplainer runs. Add a
Baseline-control counter and assert it remains zero for
`gnnexplainer_encoder_forward_count`. Record exact eligible/oversized counts and
wall time for the 20-case selection.

- [ ] **Step 4: Add smoke tests.**

Test that the defaults are 20/10, resume preserves selected IDs, the Baseline
path never calls `run_member_explanation`, and diagnostics report actual
shortfalls rather than claiming full coverage.

- [ ] **Step 5: Run benchmark and smoke tests.**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_run_demo_smoke.py \
  tests/test_giant_observability_benchmark.py
```

Expected: no Baseline explainer calls and stable selected-ID fingerprints.

## Task 8: Regenerate the artifact, rebuild the dashboard, and verify end to end

**Files:**
- Regenerate: `gnn/diagnostics/hybrid_recovery_explanations_v9.json`
- Regenerate: `gnn/diagnostics/recovery/current.json` and its selected sidecars
- Regenerate: `Documents/Data/v9_dashboard/index.html`
- Regenerate: `Documents/Data/v9_dashboard/data_v9.json`
- Modify: `Documents/Data/changes_3.md`
- Modify: `PROJECT_MEMORY.md`

- [ ] **Step 1: Run the focused source suite before full generation.**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_sage_explainer.py \
  tests/test_recovery_bundle.py \
  tests/test_balanced_recovery_explainability.py \
  tests/test_v9_recovery_explainer_ui.py \
  tests/test_v9_dashboard_builder.py \
  tests/test_run_demo_smoke.py \
  tests/test_giant_observability_benchmark.py
```

Expected: all focused tests pass before spending time on full V9 generation.

- [ ] **Step 2: Generate the balanced observability artifact from the verified checkpoint.**

Use the existing checkpoint/resume entry point with the default 20/10 limits.
Confirm the output reports the three-cohort algebra, selected IDs, actual
Hybrid explanation count, Baseline community count, and any shortfall.

- [ ] **Step 3: Validate artifact and sidecar integrity.**

Run the schema-3 validator against the generated manifest, then verify every
published selected sidecar hash and catalog/chunk offset. Confirm that no
Baseline case payload contains explanation or overlay keys.

- [ ] **Step 4: Rebuild the static dashboard.**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/python \
  Documents/Data/scripts/build_v9_dashboard.py
```

Expected: the builder accepts schema 3.0, publishes the selected sidecars, and
keeps the V9 recovery mount exactly once.

- [ ] **Step 5: Validate generated source and dashboard contracts.**

Run:

```bash
rtk .venv/bin/python -m py_compile \
  gnn/recovery_observability.py \
  gnn/sage_explainer.py \
  gnn/observability_artifact.py \
  gnn/recovery_bundle.py \
  Documents/Data/scripts/build_v9_dashboard.py \
  Documents/Data/scripts/v9_recovery_sidecars.py
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_v9_dashboard_builder.py
```

Expected: no syntax errors and all generated-dashboard source contracts pass.

- [ ] **Step 6: Perform the visual smoke check.**

Serve the generated dashboard with the repository’s documented local server and
inspect V9 Results at desktop and mobile widths. Verify:

- full summary appears before case details;
- Hybrid and Baseline filters work;
- Hybrid cases show attribution and technical panels;
- Baseline cases show neutral community graphs and the structural-only note;
- scores/ranks are labeled correctly;
- partial coverage and failure messages are visible; and
- keyboard/accessibility fallbacks remain usable.

- [ ] **Step 7: Record durable research notes.**

Append a concise dated entry to `Documents/Data/changes_3.md` stating the actual
generated coverage, the 20/10 selection policy, schema 3.0 partial coverage,
and the fact that Baseline controls are community-only. Update `PROJECT_MEMORY.md`
with the same durable decision and any measured runtime/shortfall risk. Do not
copy stale metric values from older artifacts.

- [ ] **Step 8: Record the completed implementation through Merget/Historian.**

Keep unrelated pre-existing worktree changes out of the record. Use the
repository’s Historian/Merget workflow for the completed task and include only
the implementation, tests, generated diagnostics, dashboard output, and the
two synchronized documentation updates.

## Plan self-review

- **Spec coverage:** The plan covers three-cohort summary, 20/10 frozen
  selection, exact explainer eligibility, schema-3 partial publication,
  Baseline structural controls, scores/ranks, lazy sidecars, as-of enforcement,
  failure states, accessibility, diagnostics, tests, and documentation.
- **Placeholder scan:** No step depends on an unspecified threshold, post-hoc
  selection decision, or future artifact shape. The exact explainer eligibility
  limits are 128 nodes and 256 directed edges; the explainer contract is seeds
  `(0, 1, 2)` and 150 epochs.
- **Type consistency:** `detail_status`, `detail_kind`, `selection_reason`,
  `failure_reason`, `hybrid_detail_limit`, `baseline_control_limit`, and
  `schema_version="3.0"` are used consistently across producer, bundle,
  sidecar, UI, and tests.
- **Legacy safety:** Schema-1/schema-2 loaders and validators remain separate
  from schema 3.0, and the existing V9 recovery mount is preserved.
