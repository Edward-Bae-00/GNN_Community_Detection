# V9 Hybrid-Only Recovery Explainer Design

## Goal

Add a case-level explanation section to the V9 Results tab that:

1. reports exact unique-person overlap between the Baseline and Hybrid under the
   same simulated 25-inspections-per-day policy; and
2. explains representative people recovered by the fixed-seed observability
   Hybrid but missed by the Baseline using strict as-of evidence, complete
   explanation communities, and measured counterfactual effects.

The feature must make the V9 positive-control result easier to audit without
changing inspection budgets or corpus design. One prerequisite model correction
is in scope: `SHARED_PLATE_HOT` must use official label-availability time rather
than seizure-event time. Corrected V9 scores and artifacts must be regenerated
before observability output is accepted.

## Terminology

- **Recovered** means a unique synthetic person counted as caught by the existing
  stateful simulated-catch evaluator after a selected hidden-positive event is
  inspected. Outside that simulator, the models surface events for inspection;
  they do not literally catch people.
- **Hybrid-only recovery** means a person in `hybrid_recovered_ids -
  baseline_recovered_ids` under the same 25/day policy.
- **Baseline-only recovery** means a person in `baseline_recovered_ids -
  hybrid_recovered_ids` under the same policy.
- **Observability seed** means fixed GraphSAGE seed 0. The recovery-overlap
  summary, representative cohort, counterfactuals, GNNExplainer masks, and case
  graphs all use this one seed. Existing headline and aggregate V9 panels remain
  based on the three-seed ensemble.
- **As-of snapshot** means the GNN scoring state at the UTC day start used by the
  production scoring path. Edges and observed catch labels must be available
  strictly before that timestamp.
- **Explanation community** means the complete set of people and active edges
  participating in message passing or pooling for the selected person's deployed
  GraphSAGE score: the selected person's COTRAVEL pooling component plus every
  two-hop GraphSAGE neighbor of every pooled component member. Graph-derived
  input features can summarize additional as-of relationships; their provenance
  is retained in the factor payload and expanded when that factor is selected.
- **Influence weight** means a normalized explainer or counterfactual effect used
  for visualization. Model parameters do not transfer through graph edges;
  node representations and messages do.

## Current Model And Observability Boundary

The headline V9 Hybrid uses the GraphSAGE arm, not the optional RGCN or GAT arms.
Three GraphSAGE models are trained with seeds 0, 1, and 2. Their probabilities
are averaged, percentile-ranked, and blended with the Baseline percentile rank.
The current diagnostic uses a 75% GNN rank weight.

The new observability block intentionally uses only GraphSAGE seed 0. It builds a
single-seed Hybrid from the existing Baseline percentile and seed-0 GNN
percentile using the same configured rank-blend weight. Its containment numbers
and Hybrid-only cases are therefore single-seed observability results, not the
three-seed headline results. A persistent scope label must make that distinction
visible. No existing V9 metric, chart, or headline value changes scope.

The deployed GNN path is not an ordinary node-level `model.forward` call. It
encodes people, mean-pools embeddings across each active COTRAVEL component, and
applies the prediction head. Relation types are retained in graph-derived input
features even though the default GraphSAGE message-passing edges are not typed.

Consequently, a stock GNNExplainer edge mask alone cannot explain even the
single-seed Hybrid selection. The design must explain both the seed-0 Hybrid
decision and the seed-0 graph message-passing contribution.

## Prerequisite: Leak-Free HOT-Plate Timing

The current graph builder derives a vehicle's first hot time from the event
timestamp of its first `seizure_flag`. That precedes official
`label_available_time_utc` in the corpus and violates the project's strict as-of
rule. In the checked V9dev corpus, all 159 seizure labels become available after
their event, with delays from 1 to 28 days.

Before generating explanations:

1. load `label_available_time_utc` with plate/seizure inputs;
2. for each vehicle, define `first_observable_seizure_time` as the earliest valid
   `label_available_time_utc` among rows whose `seizure_flag` is true;
3. keep a shared-plate relationship ordinary when its own edge-availability time
   precedes that observable seizure time;
4. mark it `SHARED_PLATE_HOT` only when its edge-availability time is at or after
   the first observable seizure time; and
5. treat missing or malformed seizure-label availability as unavailable, never
   as event-time knowledge.

The graph's existing strict `edge_available_time < scoring_snapshot` filter still
applies. The correction must be exercised on V9dev first, then the three-seed V9
ensemble and seed-0 observability results must be regenerated. Update the current
V9 diagnostic and `Documents/Data/changes_3.md` with the corrected data-driven
values; do not preserve stale headline numbers in explanatory copy.

## Method Decision

### Primary: exact grouped counterfactual attribution

For every explained case, remove one coherent, observable factor group and rerun
the full scoring path:

- a canonical person-pair relationship group;
- an observed prior-caught source/member flag;
- all active ties of one relation type for the affected person or path;
- one derived structural feature group; or
- the relevant COTRAVEL component membership/pooling relationship.

Each ablation must rebuild affected graph-derived features, COTRAVEL components,
and pooling; rescore GraphSAGE seed 0; recompute the seed-0 GNN percentile against
a frozen peer-score reference distribution; and recompute the single-seed Hybrid
rank.
The signed Hybrid rank change is the primary displayed contribution measure.
Removing a factor is allowed to improve a score; the UI must not assume every
effect is positive.

### Secondary: single-seed GNNExplainer message view

Run GNNExplainer against GraphSAGE seed 0's pre-pool message-passing computation
for every member of the selected person's pooled component. Combine the member
explanations using the exact linear-head/component-mean decomposition. Use
multiple deterministic explainer restarts and aggregate normalized masks using:

- median edge and feature influence;
- interquartile range or comparable spread;
- top-edge selection frequency; and
- sign/top-factor agreement across explainer restarts.

These restarts vary only the post-hoc explainer optimization initialization.
They do not train, load, score, or compare any additional GNN model seed.

The mask controls visual edge emphasis and staged message-flow tracing. It does
not represent component-membership effects, graph-derived feature provenance,
or the final Hybrid decision, and it does not replace the counterfactual
Hybrid-rank measurement.

### Rejected for the first version: ACGAN-GNNExplainer

The repository's second paper is **ACGAN-GNNExplainer: Auxiliary Conditional
Generative Explainer for Graph Neural Networks**, not “AGCN Explainer.” Its
amortized generator could reduce per-case latency after training, but the
published method assumes a homogeneous adjacency mask, lacks the required
feature/relation treatment, and requires costly edge-deletion pseudo-labels and
adversarial training. It is not a direct fit for the current pooled GraphSAGE
pipeline.

## Results-Tab Information Architecture

Place the new block after the Results tab's model explanation / three-lens story
and before the aggregate depth-recall charts. The Results hero's graph-evidence
link may navigate directly to the case-evidence section.

### 25/day recovery summary

Label this summary “Single-seed observability · GraphSAGE seed 0.” All six values
come from the seed-0 Hybrid and Baseline under the same 25/day policy. Existing
three-seed ensemble totals elsewhere in V9 Results remain unchanged and must not
be mixed into this block.

Show six data-driven values:

1. Baseline recovered;
2. recovered by both;
3. Hybrid-only recovered;
4. Baseline-only recovered;
5. Hybrid total; and
6. net gain, `hybrid_total - baseline_total`.

The overlap values must be calculated from person-ID sets, never inferred by
subtracting aggregate totals. A zero Baseline-only value may support an explicit
containment statement. A nonzero value is shown honestly in amber, and the UI
must not claim that the Hybrid preserved every Baseline success.

### Split case explorer

Use the approved two-column layout:

- **Left rail:** representative Hybrid-only people, sortable by GNN/Hybrid rank
  uplift and filterable by stable-factor status or relationship category.
- **Right detail:** selected person's score/rank decomposition, top measured
  factors, complete explanation-community graph, and as-of evidence boundary.

The detail header shows Baseline rank, seed-0 GNN rank, seed-0 Hybrid rank,
scoring snapshot, selection status at 25/day, and a persistent single-seed scope
badge.

## Complete Community And Influence Flow

The graph must not sample or silently omit members of the selected case's exact
message-and-pooling explanation community. It includes:

1. every person in the target's active COTRAVEL pooling component;
2. every person in the two-hop GraphSAGE receptive field of every pooled member;
   and
3. every active, model-available relationship among included people that is
   relevant to message passing or derived features.

If a selected graph-derived feature depends on relationships outside this
message-and-pooling community, its factor detail expands those provenance nodes
and edges explicitly. The UI must not imply that an aggregate degree/component
feature was produced only by the currently visible message paths.

For large communities, preserve all nodes and edges while reducing label density
and providing zoom, pan, search, and fit-to-community controls.

The graph supports two coordinated views:

- **All connections:** every included node and relationship remains visible.
- **Influence flow:** the same complete graph remains present, while edge
  thickness/opacity shows seed-0, restart-aggregated explainer influence and
  arrows trace messages toward the pooled component and selected person.

Stage controls progressively emphasize:

1. first-hop neighbor aggregation;
2. second-hop propagation;
3. COTRAVEL component mean pooling; and
4. GNN-percentile and Hybrid-rank fusion.

Relation colors provide observable context such as co-travel, shared plate, or
residence. They must not imply that the default GraphSAGE arm learned a distinct
message-passing parameter per relation. Selecting a path or factor synchronizes
the graph highlight with its counterfactual GNN- and Hybrid-rank changes.

## Representative Explanation Coverage

The single-seed observability recovery summary covers every person recovered by
the seed-0 Hybrid or Baseline. The first version generates full explanations for
at most 40 representative seed-0 Hybrid-only people.

Selection is deterministic:

1. anchor each Hybrid-only person to their first simulated Hybrid recovery day;
2. compute lightweight Baseline/GNN/Hybrid rank decomposition and as-of
   relationship categories for all candidates;
3. order primarily by daily `baseline_rank - hybrid_rank`, then by
   `gnn_percentile - baseline_percentile`, with synthetic person ID as the stable
   tie-breaker;
4. round-robin across available relationship categories and scoring periods so
   the set is not dominated by one graph pattern or day; and
5. attempt candidates in that order until 40 valid explanations are produced or
   the candidate set is exhausted.

Explanation failures are counted and reported. They are not silently replaced
with heuristic factors. The UI states coverage explicitly, for example “40
explained cases out of N Hybrid-only recoveries.”

## Components And Data Flow

### 1. Recovery-set capture

Extend the stateful simulated-catch evaluation to retain unique recovered-person
ID sets for the Baseline and seed-0 Hybrid at 25/day. Compute the six summary
fields and the exact single-seed Hybrid-only candidate cohort from those sets.
Do not replace or reinterpret the existing three-seed ensemble result artifact.

### 2. Case anchor and decision trace

For every Hybrid-only candidate, retain the first-recovery event/person/day
anchor and a lightweight decision trace:

- Baseline raw score and comparison-pool percentile;
- seed 0's GNN probability;
- seed-0 GNN comparison-pool percentile;
- weighted Baseline and GNN rank terms;
- final Hybrid score and daily rank; and
- the exact reference-pool identity and inspection budget.

Hybrid attribution is expressed as rank effects, not probability addition.

### 3. Explanation generator

Run the representative-case explanation pass while the trained seed-0 model is
still available. Cache day snapshots, derived features, components, and
deduplicated `(person_id, scoring_day)` requests. Build the complete explanation
community, run multiple seed-0 GNNExplainer restarts, execute grouped
counterfactuals, and record faithfulness/restart-stability metadata.

### 4. Explanation artifact

Write a separate generated diagnostic artifact under `gnn/diagnostics/`, keeping
the existing aggregate comparison JSON focused. The artifact contains:

```text
schema_version
policy
summary
coverage
hybrid_only_cases[]          # lightweight record for the full cohort
explanations[]               # complete payload for up to 40 cases
generation_diagnostics
```

`policy` records `observability_seed: 0`, `gnn_arm: sage`, the Hybrid blend
weight, the 25/day budget, and the frozen percentile-reference identity. The
artifact also records that the surrounding headline V9 Results use ensemble
seeds `[0, 1, 2]`; this is display provenance only and never enters the
single-seed observability calculations.

Each complete explanation contains:

```text
case_id, person_id, event_id, scoring_day
decision_trace
factors[]
community.nodes[]
community.edges[]
flow_stages[]
stability
faithfulness
evidence_boundary
llm_narrative.source          # llm or deterministic_template
llm_narrative.model           # gemma4:12b when source is llm
llm_narrative.prompt_version
llm_narrative.summary
llm_narrative.claims[]        # text plus source-field references
llm_narrative.validated
```

Node and edge payloads may contain synthetic IDs, observable as-of status,
relation type, availability time, and explainer/counterfactual values. Hidden
organization/community labels, lifetime outcomes, future edges, and future
catch information are prohibited.

### 5. Grounded Gemma narrative

Use the locally installed Ollama model `gemma4:12b` at dashboard-build time to
convert each validated structured explanation into a short plain-language “Why
this person was surfaced” narrative. Gemma is a narrator, not an attribution
method. Do not call an external LLM provider or expose the Ollama service to the
browser.

The input is a minimal fact packet containing only:

- the single-seed scope and scoring snapshot;
- Baseline, seed-0 GNN, and seed-0 Hybrid ranks;
- validated counterfactual factor effects;
- visible as-of path/relation labels;
- GNNExplainer restart-aggregated influence values; and
- approved interpretation caveats.

Require structured output with a short summary, ordered factor sentences, and
source-field references for every claim. A validator rejects any narrative that:

- introduces an ID, relationship, number, causal claim, or model fact absent
  from the fact packet;
- describes influence values as learned parameters transferred across edges;
- omits the single-seed scope when comparing ranks; or
- uses hidden, lifetime, future, or ground-truth community information.

Use deterministic generation settings supported by the local Ollama runtime and
store the accepted narrative, model tag, and prompt version in the static
artifact. The browser never calls Ollama or receives service credentials. If the
Ollama daemon or `gemma4:12b` is unavailable, generation fails, or validation
rejects the result, generate the same section from a deterministic evidence
template. Do not automatically download a replacement model. Label accepted
Gemma text “AI-generated summary · Gemma 4 12B” and keep the measured factor
panel and graph authoritative.

### 6. Dashboard builder and UI

The V9 dashboard builder embeds the new artifact and renders the summary and
split explorer. It must not reuse the generic dashboard Explorer's current
handcrafted “GNNExplainer-style” lifetime factors. A secondary navigation link
to the generic Explorer is optional context only and cannot serve as model
evidence.

## Leakage And Faithfulness Requirements

- Use the production UTC day-start scoring snapshot.
- Require `edge_available_time < snapshot_time`.
- Require `label_available_time_utc < snapshot_time` for caught-state evidence.
- Exclude hidden labels, hidden organization membership, ground-truth community
  propensity, lifetime outcome aggregates, and future relationships from all
  explanatory inputs.
- Retrospective hidden truth may label the case as a simulated recovery, but it
  must be visually and structurally separated from model-available evidence.
- Require explanation-wrapper prediction parity with the production seed-0
  score, pooled seed-0 GNN score, and single-seed Hybrid rank before emitting an
  explanation.
- Calculate ablated ranks against the frozen unablated peer-score distribution.
- Compare top-edge removal curves with relation/degree-matched random removals.
- Report explainer-restart stability; do not promote unstable factors as strong
  explanations.

## Failure And Empty States

- If the record-level artifact is absent, show the existing aggregate Results
  content and an explicit “case evidence unavailable” state.
- If overlap IDs are unavailable, do not infer or display overlap numbers.
- If one representative explanation fails parity or leakage checks,
  mark the attempt failed and continue deterministic candidate selection.
- If fewer than 40 valid explanations exist, show the actual explained count.
- If no stable factor exists for a valid case, preserve the score/rank trace and
  complete explanation community, but state that no stable factor met the display
  threshold.
- Never substitute the generic lifetime heuristic explanation.

## Verification

### HOT-plate timing tests

- Verify a seizure does not create `SHARED_PLATE_HOT` edges before its
  `label_available_time_utc`.
- Verify a shared-plate encounter exactly at the label-availability timestamp is
  typed HOT but remains unavailable to a scoring snapshot at that exact time.
- Verify missing/malformed label availability never creates a HOT relation.
- Verify future seizure labels do not relabel earlier shared-plate encounters.
- Regenerate V9dev and confirm strict as-of invariance before the full V9 run.

### Evaluation tests

- Prove exact set algebra for Baseline, overlap, Hybrid-only, Baseline-only,
  Hybrid total, and net gain for seed 0 at the same 25/day budget.
- After the HOT-timing correction, verify every headline and aggregate V9 result
  remains sourced from the three-seed ensemble and is not further changed by
  observability generation.
- Prove person deduplication and first-recovery anchoring.
- Verify deterministic representative selection and explicit coverage counts.

### As-of and leakage tests

- Verify strict-before edge and caught-label inclusion.
- Verify exact-at-snapshot and future edges/catches do not affect explanations.
- Scan serialized fields to reject hidden organization/community and lifetime
  outcome inputs.

### Model and attribution tests

- Verify explanation-wrapper parity for seed 0, component pooling, seed-0 GNN
  percentile, and single-seed Hybrid rank.
- Verify counterfactual recomputation rebuilds affected derived features and
  pooling components.
- Verify frozen-peer percentile and rank recalculation.
- Verify restart aggregation and stability labels.

### Gemma narrative tests

- Verify every generated claim references existing fact-packet fields.
- Reject invented IDs, relationships, numbers, causal claims, and unsupported
  model descriptions.
- Verify the narrative labels its single-seed scope and AI-generated status.
- Verify the artifact records `gemma4:12b` and the prompt version for accepted
  model output.
- Stub the Ollama client in automated tests; do not require a running local model
  for the source test suite.
- Verify deterministic template fallback when Ollama or `gemma4:12b` is
  unavailable or returns invalid output.

### Community tests

- Verify the serialized node/edge set equals the exact pooled-component plus
  two-hop message-and-pooling explanation community.
- Verify selected graph-derived factors expose any additional provenance nodes
  and edges required to support their displayed aggregate values.
- Verify no sampling or truncation occurs for large communities.
- Verify graph stages change emphasis without changing membership.

### Dashboard tests

- Verify all six summary values are artifact-driven.
- Verify nonzero Baseline-only results suppress containment claims.
- Verify missing-artifact, failed-case, unstable-factor, and large-community
  states render correctly.
- Run focused V9dev tests before a full V9 artifact generation and dashboard
  inspection.

## Non-Goals

- Do not force Baseline containment by using outcome labels, post-hoc selection,
  a larger Hybrid budget, or hidden corpus truth.
- Do not tune the corpus or model merely to make Baseline-only equal zero.
- Do not preserve old V9 metric values if the leak-free HOT-timing correction
  changes them.
- Do not implement ACGAN-GNNExplainer in the first version.
- Do not generate full explanations for every Hybrid-only recovery in the first
  version.
- Do not use the LLM to discover factors, assign influence, recalculate scores,
  or replace measured evidence.
- Do not call an external LLM provider or automatically pull an Ollama model.
- Do not change existing three-seed V9 Results to single-seed results.
- Do not replace or redesign unrelated Results charts.

## Success Criteria

The feature is complete when:

1. HOT-plate relation timing uses official label availability and corrected
   V9dev/full-V9 artifacts have been regenerated;
2. the observability block reports exact seed-0, same-budget unique-person
   overlap and gain while all existing V9 results remain three-seed ensemble
   results;
3. it explains up to 40 deterministic representative seed-0 Hybrid-only
   recoveries;
4. each explained case shows the complete as-of explanation community, staged
   message influence, score/rank decomposition, measured counterfactual effects,
   restart stability, and a grounded LLM or deterministic narrative;
5. no future, lifetime, hidden-organization, or ground-truth community input can
   enter an explanation;
6. failure states never fabricate or substitute explanations; and
7. focused V9dev verification and a full V9 artifact/dashboard check pass.
