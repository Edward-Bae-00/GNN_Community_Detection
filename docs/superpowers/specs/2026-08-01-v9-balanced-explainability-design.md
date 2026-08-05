# V9 Balanced Recovery Explainability Design

## Status

Approved design direction; pending written-spec review before implementation.

This design extends the earlier hybrid-only recovery explainer specification in
`docs/superpowers/specs/2026-07-16-v9-hybrid-recovery-explainer-design.md`.
The existing three-seed V9 headline evaluation remains unchanged.

## Goal

Add a balanced explainability workspace to the V9 Results dashboard that:

1. summarizes recovery evidence for the complete retrospective recovery cohort;
2. provides detailed GNNExplainer-backed propagation stories for 20 selected
   Hybrid-win cases;
3. provides community-only comparison views for 10 selected Baseline-win cases;
4. shows Baseline, seed-0 GNN, and Hybrid scores, percentiles, and ranks for
   every displayed case; and
5. makes partial explanation coverage, as-of boundaries, and model scope
   explicit.

GNNExplainer runs offline against the checkpointed model. The browser loads and
renders verified artifacts only.

## Scope and terminology

The dashboard is a retrospective research/observability surface. `Hybrid-win`
and `Baseline-win` are post-hoc recovery cohorts under the same fixed
single-seed observability policy; they are not deployable labels or model
features.

- **Hybrid-win:** recovered by the seed-0 Hybrid and not by Baseline.
- **Baseline-win:** recovered by Baseline and not by the seed-0 Hybrid.
- **Recovered by both:** recovered by both arms; included in aggregate summary
  metrics but not required to receive a curated graph. If a lightweight record
  is materialized, its anchor is the earlier of the two arms' first-recovery
  anchors and it records `recovery_anchor_arm`; it is never eligible for the
  curated detail indexes.
- **Hybrid detail:** exact two-hop GraphSAGE message explanation, selected
  GNNExplainer attribution, measured counterfactual effects, and as-of
  community/provenance evidence.
- **Baseline control detail:** as-of community structure and score/rank
  comparison without GNNExplainer or attribution claims.
- **Published projection:** the graph representation serialized for dashboard
  display. It may be bounded for rendering, but it must disclose counts and
  truncation. It is not the explainer input unless the input passed the same
  preflight eligibility cap.

All detailed cases use GraphSAGE seed 0, the existing single-seed observability
policy, and the same daily inspection budget used by the recovery artifact.
Surrounding headline metrics continue to use the three-seed ensemble.

## Approved coverage policy

The full summary includes three cohort counts and exact overlap algebra:

- Baseline recovered;
- recovered by both;
- Hybrid-only recovered;
- Baseline-only recovered;
- Hybrid total; and
- net gain.

The curated detail policy requests:

- 20 Hybrid-win cases with detailed GNN explanations;
- 10 Baseline-win cases with community-only controls.

The artifact records requested, selected, generated, fallback, and failed
counts. A shortfall is visible and is never silently filled with a case chosen
because its explanation looked attractive.

## Score and rank semantics

Every lightweight case record exposes the values required by the dashboard:

- `baseline_raw` — Baseline model score;
- `baseline_percentile` and `baseline_rank`;
- `seed0_gnn_probability` and `seed0_gnn_percentile`;
- `seed0_gnn_rank`;
- `seed0_hybrid_score` — percentile-fusion score, not a probability; and
- `seed0_hybrid_rank`.

Raw Baseline and GNN values remain separately labeled because they are on
different model scales. Percentiles, ranks, and the Hybrid fusion score are the
primary comparison lens.

## Deterministic case selection

Selection is completed before any GNNExplainer, counterfactual, narrative, or
stability result is available.

### Hybrid-win selection

1. Build the complete Hybrid-win candidate set from the frozen recovery
   reference and as-of metadata.
2. Run a deterministic explainer-eligibility preflight for each candidate.
   The exact two-hop GraphSAGE subgraph must be no larger than the fixed
   eligibility limits of 128 nodes and 256 directed message edges. Candidates
   over the limit are not pruned for explanation; they receive community-only
   fallback treatment or remain unselected.
3. Order eligible candidates by rank improvement, GNN-versus-Baseline
   percentile separation, relationship signature, scoring period, and stable
   synthetic person ID.
4. Round-robin across available relationship signatures and scoring periods to
   avoid selecting 20 near-duplicates.
5. Select the first 20 cases from the frozen eligible order. If a selected
   case later fails a validation invariant or explanation generation, retain
   the selected ID, record the failure, and report the resulting shortfall.

### Baseline-win selection

1. Build the complete Baseline-win candidate set from the same frozen recovery
   reference.
2. Order by Baseline-versus-Hybrid rank gap, relationship signature, scoring
   period, and stable synthetic person ID.
3. Round-robin across relationship signatures and scoring periods.
4. Select the first 10 cases from the frozen order. No GNNExplainer
   eligibility or explainer-quality signal is used.

The selection policy, quotas, eligibility limits, tie-breaks, eligible-order
prefix, selected IDs, checkpoint identity, model-state fingerprint, corpus identity,
restart seeds, and epoch count are stored in the run fingerprint.

## Explainer computation boundary

For selected Hybrid-win cases that pass preflight, GNNExplainer runs against
the exact two-hop GraphSAGE subgraph required for local/full-logit parity. The
computation uses the existing deterministic restart contract `(0, 1, 2)` and
the existing 150-epoch policy. The published graph projection may reduce label
density or expose only the bounded display view, but it must preserve the
full-input counts and state whether any rows are not currently rendered.

The existing GNNExplainer masks remain unsigned salience measures. Directional
interpretation comes only from the separately measured signed counterfactual
effects. The final Hybrid decision is explained by the score/rank ledger and
counterfactuals; an edge mask alone is not treated as a causal explanation.

For selected Baseline-win controls, the producer builds the same strict as-of
community structure, but does not call GNNExplainer, compute explainer masks,
or emit attribution overlays. The community is structural context only.

Hybrid detail keeps the existing validated narrative contract. A local Gemma
narrative may be generated from the validated fact packet; if it is unavailable
or rejected, the deterministic evidence template is used. Baseline controls do
not require an LLM narrative.

## Artifact contract

Introduce a breaking recovery artifact schema version `3.0` for partial detail
coverage. Existing schema-1 and schema-2 artifacts remain readable as legacy
inputs where supported, but the balanced artifact is not forced through the
schema-2 complete-coverage validator.

The schema-3 artifact contains:

```text
schema_version: "3.0"
policy
summary
coverage
cohorts
detail_index
community_index
catalog_index
generation_diagnostics
run_fingerprint
```

### Full-cohort summary records

`cohorts.hybrid_only`, `cohorts.baseline_only`, and
`cohorts.recovered_by_both` contain lightweight records with:

```text
case_id
person_id
event_id
cohort
scoring_day
baseline_raw
baseline_percentile
baseline_rank
seed0_gnn_probability
seed0_gnn_percentile
seed0_gnn_rank
seed0_hybrid_score
seed0_hybrid_rank
hybrid_rank_uplift
gnn_percentile_uplift
relationship_categories
detail_status
detail_kind
selection_reason
failure_reason
```

`detail_status` is one of `not_selected`, `selected`, `available`,
`community_only`, `unavailable`, or `failed`. `detail_kind` is one of
`gnn_explanation`, `community_control`, or `null`.

### Detail indexes

`detail_index` and `community_index` contain only selected cases with detail
records. They do not need to cover the full recovery cohort.

- A Hybrid detail case has a case sidecar, complete as-of community evidence,
  GNNExplainer overlay data when available, decision ledger, factors, and
  validated narrative or deterministic fallback.
- A Baseline control has a case sidecar and community sidecar with the score
  ledger and structural graph only. It must not contain `explanation`,
  `overlay_evidence`, or attribution claims.
- A failed or oversized Hybrid candidate retains its lightweight summary and
  failure reason. If its structural community is available, the UI can render
  it as community-only fallback.

All sidecars remain content-addressed, atomically published, hash-verified, and
lazily loaded. The browser never receives model weights or LLM credentials.

## Dashboard information architecture

Use one V9 explainability workspace, extending the existing recovery explorer.

### Cohort summary

Show:

- exact overlap/recovery counts;
- Hybrid-win and Baseline-win detail coverage, such as `20 / N` and `10 / N`;
- relationship mix and common structural patterns;
- persistent single-seed observability scope; and
- a short note that cohorts are retrospective evaluation groups.

### Case explorer

Provide filters for:

- All / Hybrid wins / Baseline wins;
- detailed explanation / community only / all;
- relationship category; and
- stable factor status where applicable.

Each row shows the cohort badge, person ID, score/rank comparison, and detail
status. Cases without detail remain visible.

### Selected case

The detail workspace shows:

1. cohort label and scoring snapshot;
2. Baseline, GNN, and Hybrid scores/percentiles/ranks;
3. strict as-of evidence boundary;
4. four stage controls: first hop, second hop, component pooling, rank fusion;
5. the community graph; and
6. evidence panels appropriate to the detail kind.

Hybrid-win panels include top attributed edges/nodes, feature masks, signed
counterfactual effects, restart stability, faithfulness diagnostics, and
source-row provenance. Baseline-win panels include community nodes/edges,
caught-before-snapshot state, relationship types, component counts, and a
neutral structural label:

> Community context only — GNNExplainer was not run for this baseline control.

The graph must not use color alone to convey meaning. Relation labels, legend
text, keyboard-accessible stage controls, and the existing non-canvas data
fallback remain available.

## Leakage and safety requirements

- Edges must satisfy `available_time < snapshot`.
- Caught labels must satisfy `label_available_time_utc < snapshot`.
- Hidden organization labels, future outcomes, lifetime catches, future edges,
  and outcome aggregates cannot enter features or explanations.
- Retrospective cohort membership is labeled as evaluation metadata, never as a
  deployable input.
- Hybrid explanation wrappers must match the production seed-0 score and
  frozen rank reference before publication.
- Counterfactual rank effects must rebuild affected derived features and
  pooling against the frozen peer-score reference.
- Unsigned explainer masks must not be described as positive/negative causal
  effects.
- Missing or invalid evidence must produce an unavailable state, never a
  fabricated explanation.

## Failure and empty states

- No artifact: preserve the existing V9 Results surface and show evidence
  unavailable.
- Partial coverage: show actual generated counts and shortfall reasons.
- Oversized exact explainer input: retain the candidate summary and render
  community-only evidence when available.
- Invalid sidecar or hash mismatch: reject the payload and show an integrity
  error.
- Missing narrative: show measured factors and the deterministic template.
- No stable factor: preserve score/rank and community evidence while stating
  that no stable factor met the display threshold.
- Stale asynchronous case response: discard it when the selected case changes.

## Verification

Add or update focused tests for:

### Artifact and selection

- exact three-cohort overlap algebra;
- 20/10 quotas and deterministic selection;
- preflight eligibility and frozen-prefix selection without post-hoc replacement;
- selection fingerprint and selected IDs;
- score, percentile, and rank field preservation;
- partial coverage and per-case detail statuses;
- baseline detail records containing no explanation or overlay fields.

### Model and as-of behavior

- exact two-hop/full-logit parity for eligible Hybrid cases;
- strict-before edge and caught-label inclusion;
- future and same-snapshot evidence exclusion;
- counterfactual rebuild and frozen peer-percentile behavior;
- restart aggregation and stability metadata.

### Bundle and dashboard

- schema-3 manifest validation;
- lazy case/community sidecar loading and hash verification;
- Hybrid technical panels versus Baseline structural-only panels;
- oversized and failed-case fallbacks;
- stage order and graph membership;
- accessible labels and non-canvas fallback;
- score/rank display semantics, including Hybrid score not being called a
  probability.

Run the affected source tests, rebuild the static V9 dashboard, validate the
generated JavaScript, and inspect the V9 Results tab at desktop and mobile
widths before claiming completion.

## Non-goals

- Do not run GNNExplainer for every recovered case.
- Do not run GNNExplainer for Baseline-win controls.
- Do not change the three-seed headline metrics, model training, or evaluation
  budget.
- Do not use an LLM to discover factors, assign attribution, or recalculate
  scores.
- Do not select cases using explanation quality, narrative success, or
  attractive graph appearance.
- Do not silently replace failed explanations with heuristic attribution.
- Do not make the browser perform inference.
- Do not redesign unrelated V9 charts or restore stale research artifacts.

## Success criteria

The feature is complete when:

1. the schema-3 artifact reports full-cohort overlap and explicit partial detail
   coverage;
2. up to 20 deterministic Hybrid-win cases have validated detailed evidence;
3. up to 10 deterministic Baseline-win cases have community-only controls;
4. every selected case displays Baseline/GNN/Hybrid scores, percentiles, and
   ranks with correct scope labels;
5. Hybrid cases show the staged propagation story and expandable technical
   evidence;
6. Baseline controls show the same structural community without attribution
   claims;
7. all evidence is strict as-of and hash-verified;
8. failure and shortfall states are visible; and
9. focused tests, dashboard rebuild, generated-output validation, and visual
   smoke checks pass.
