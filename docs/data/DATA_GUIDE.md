# Synthetic CBP Graph Corpus - Data Guide

> Current-status note (2026-08-06): The active `gnn/` runtime is the V9
> designed positive control. The canonical full V9 corpus is Git-LFS versioned
> in `reproducibility/v9_observability_colab_schema3/corpus/`; V9dev is at
> `tests/fixtures/v9dev/`. V8 is historical honest-track context only and its
> corpus is absent from this checkout. Detailed V9 design and result claims
> live in `docs/research/changes_3.md`.

## What This Dataset Is

This is a fully synthetic, privacy-safe graph corpus that models CBP-style
border crossing events and observable social/logistic structure around those
events. It is for research on graph learning, entity resolution, and anomaly
scoring. It is not operational data.

No row represents a real person, vehicle, document, officer, case, event,
seizure, arrest, address, phone number, email, license plate, or name.
Aggregate real-world CSVs are calibration/context inputs only.

The active corpus inputs in this checkout are:

| Corpus | Path | Role |
| --- | --- | --- |
| V9 | `reproducibility/v9_observability_colab_schema3/corpus/synthetic_cbp_graph_corpus_v9/` | Active designed positive-control corpus with propagable relational signal |
| V9dev | `tests/fixtures/v9dev/` | Small V9-profile corpus used by tests and smoke runs |
| V8 | *(historical; corpus absent)* | Honest-track context with thin relational signal |

`gnn/config.py` defaults to the canonical full V9 corpus. Set
`CBP_CORPUS_DIR` only when intentionally evaluating another compatible corpus:

```bash
CBP_CORPUS_DIR=/path/to/compatible/corpus python -m gnn.run_demo
```

Validate the tracked development corpus and rebuild the current dashboard with
the organized package modules:

```bash
python -m scripts.data.validate_corpus tests/fixtures/v9dev
python -m scripts.dashboard.build_v9_dashboard
```

## Current Research Track

The active `gnn/` track compares a strong leak-free tabular baseline, the
default three-seed GraphSAGE caught-propagation arm, and a hybrid method that
combines their scores with validation-tuned convex late rank fusion.

| File | Current role |
| --- | --- |
| `gnn/config.py` | Repository paths, default corpus, diagnostics path |
| `gnn/run_demo.py` | Main baseline-vs-GNN evaluation harness |
| `gnn/demo_baseline.py` | 14-feature leak-safe tabular baseline |
| `gnn/graphmodel_alt.py` | Alternative encoders, including the default GraphSAGE arm |
| `gnn/graphmodel_rgcn.py` | Typed graph construction and optional RGCN model |
| `gnn/learned_cell.py` | As-of caught-propagation scoring |
| `gnn/detector.py` | sklearn model fitting helper |
| `gnn/unsupervised_ad.py` | Unsupervised anomaly detection per border (region) |

The comparison is intentionally narrow:

- Train labels are `detected_flag`: observed catches available to the model.
- Evaluation targets are `false_negative_flag`: hidden carriers in the test
  pool.
- The baseline uses own prior history, observed demographics, and current event
  context.
- The baseline does not use graph edges, neighbor labels, future outcomes,
  lifetime catches, hidden org labels, or outcome aggregates.
- The GNN uses as-of graph structure and caught propagation over
  `COTRAVEL`, `RESIDENCE`, `SHARED_PLATE`, and `SHARED_PLATE_HOT`.
- Edges and caught labels are only used when available strictly before the
  scoring time.
- The hybrid arm rank-normalizes baseline and GNN scores, then applies a
  validation-tuned convex late rank fusion. Its deployable fusion weight is
  tuned only on caught labels available to deployment; hidden labels tune only
  the explicitly non-deployable oracle ceiling.

The current 14 baseline features are:

```text
prior_crossings, prior_secondary, prior_seizure, prior_arrests,
hour, age_bucket, sex, citizenship_country, residence_country,
region, mode_of_transportation, travel_category,
declared_trip_purpose, day_of_week
```

## V8 And V9

V8 and V9 answer different questions.

### V8: Honest Track

V8 is the realistic thin-graph-signal regime. Smuggling communities include many
lone actors and dark members who leave little or no observable enforcement
trail. In this setting, the working result is that the GNN edge over a strong
per-person tabular baseline is bounded and marginal.

V8 remains important because it is the honest, realistic track. V9 does not
replace it.

### V9: Positive Control

V9 is deliberately engineered so that hidden-carrier risk is propagable through
observable relational structure. It asks a method-validation question: when the
generative process contains relational signal, does a GNN exploit it better than
a per-person tabular model?

Key V9 design points:

- Dense co-offender co-travel: 3-5 anchors-first cell-mates per org event.
- Larger and more observable cells: `org_size` 4-12, dark rate reduced from
  0.30 to 0.10, observability increased.
- Role split: anchors are caught with high probability and seed the graph;
  clean carriers carry but are forced to leave no enforcement trail and become
  hidden evaluation targets.
- Shared plates: cells reuse a small plate pool, creating `SHARED_PLATE` and
  `SHARED_PLATE_HOT` rails.
- Lone-smuggler tail preserved: many hidden carriers remain outside any cell,
  bounding the GNN's possible win.

The intended mechanism is as-of guilt-by-association: a caught anchor before
time `T` illuminates still-uncaught connected cell-mates after `T`. The GNN is
not allowed to see future catches, hidden org labels, or lifetime outcomes.

## Current Results

The canonical V9 result log is `docs/research/changes_3.md`.
GraphSAGE remains the active runtime default; the committed 40,578-row RGCN architecture artifact is frozen-artifact verifiable, not exactly retrainable.
The current demo diagnostic is the committed
`gnn/diagnostics/demo_comparison_v9.json`. The committed
`gnn/diagnostics/gnn_architecture_comparison_v9.json` is the current
architecture comparison artifact; no RGCN checkpoint or score arrays survive.

The current cross-artifact RGCN reference is:

| K | Baseline recall | RGCN found | RGCN recall |
| ---: | ---: | ---: | ---: |
| 500 | 0.0149 | 144 | 0.0535 |
| 2,000 | 0.0710 | 538 | 0.1999 |
| 5,000 | 0.1557 | 1,030 | 0.3828 |

The Baseline values come from the demo artifact and the RGCN values from the
architecture artifact; old bootstrap significance is not transferred. The
38,948-row RGCN-era table in `changes_3.md` is explicitly historical evidence
with its artifact unavailable. Other files under `gnn/diagnostics/` remain
generated and ignored, including `demo_smoke.json`, `unsupervised_ad_results.json`,
and the preferred `unsupervised_ad_results_v9.json`. The unsupervised producer
emits both unsupervised filenames, while the dashboard prefers the
corpus-qualified file; both are generated and ignored.

Regenerate local diagnostics when needed:

```bash
python -m gnn.run_demo
python -m gnn.unsupervised_ad
python -m gnn.gnn_architecture_bakeoff  # optional; expensive separate run
```

`python -m gnn.run_demo` uses the current experimental defaults (30 epochs,
monthly buckets). The committed artifacts were produced with seeds `0/1/2`,
18 epochs, and quarterly buckets; replay that exact configuration with
`python -m gnn.run_demo release`.

Full-scale V9 result summary from `docs/research/changes_3.md`:

- Corpus: 120K persons / 200K events; current test pool: 40,578 events.
- The historical 38,948-row RGCN-era run remains available only as labeled
  historical evidence in `docs/research/changes_3.md`.
- Hidden carriers: 2,691 total, including 708 observable, 234 dark, and 1,749
  lone.
- Demo graph relations: 113,293 `COTRAVEL`, 169,315 `RESIDENCE`, 14,385
  `SHARED_PLATE`, and 5,355 `SHARED_PLATE_HOT`.
- Current RGCN whole-pool recalls are 0.0535, 0.1999, and 0.3828 at K=500,
  2,000, and 5,000; these are frozen artifact fields, not a retraining claim.

Important caveats:

- The current cross-artifact RGCN comparison has no paired-bootstrap inference;
  the historical K<=100 wash statement is not transferred to the current release.
- The GNN win is concentrated in the connected subpopulation. Lone and dark
  carriers have little or no relational signal.
- Co-travel is the load-bearing rail. Tests now assert that co-travel reaches
  the built demo graph, not just `edges.csv`.
- V9 is a designed positive control. It does not change the V8 honest-track
  finding.

## Data Realism And Interdiction Rates

The corpora model a setting where most smuggling is undetected. `event_ground_truth.csv`
contains latent ground truth such as true contraband presence and false negatives;
the model-facing labels use observed detections.

In V9, the catch rate is deliberately around 4% rather than the initially
targeted ~10%. Catches are concentrated in co-offender cells, which creates a
clean as-of caught-propagation signal without spreading risk to benign
co-travelers. V8 interdiction remains in the approximate 7-8% range.

The low observed catch-rate assumption is consistent with the project rationale:
real-world total flow is uncertain, seizure rates vary by drug and vector, and
observed seizures are only a partial view of latent trafficking.

## Evaluation Splits

The corpora use strict temporal splits combined with group-level leakage prevention, recorded in `train_valid_test_splits.csv`. In the full V9 corpus (200,000 events), the temporal breakdown is:

- **Train:** Events before `2024-01-01` (103,917 events).
- **Validation:** Events between `2024-01-01` and `2024-12-31` (55,505 events).
- **Test:** Events on or after `2025-01-01` (40,578 events).

- **Family/Community Group Leakage Prevention:** Simply splitting by time can lead to "data leakage" if a tight-knit group (like a family or cell) has events crossing the time boundary. If the model learns a hidden trait from one family member in the training set, it might unfairly recognize another family member in the test set. To prevent this, the split strategy uses a `group_leakage_prevention_id` (like a family or community ID) to ensure that strongly-linked individuals are kept together in the same split rather than bleeding across train/test boundaries.

## Snapshot Methodology

The canonical V9 and V9dev inputs are Git-LFS-backed synthetic snapshots. The
active code path for evaluation is `gnn/`, not corpus generation. The V8 corpus
is intentionally absent. Each available corpus directory still includes a
snapshot-local copy of
`generate_synthetic_cbp_graph_corpus_v3.py` and `GENERATION_CONFIG.json` as
provenance artifacts, but generator maintenance is not the current research
track in this checkout.

Foundational design principles inherited from earlier versions include:

1. Observable connectivity only: no synthetic phone-call or social-media graph.
   Person-to-person signal comes from co-travel, shared residences, shared
   vehicles, shared employers, and repeated routes.
2. Families are not addresses: kinship uses hidden family structure that can
   span households.
3. Undetected smuggling: latent contraband and observed detection are distinct,
   producing realistic false negatives.
4. Demographics are not the smuggling mechanism: demographics-only behavior is
   a fairness negative-control concern, not the intended signal.
5. Hidden co-offender cells: `org_id` captures smuggling cells, including dark
   members who may leave no observable trail.
6. Entity-resolution artifacts exist for context, but the current V9 demo uses
   an oracle identity substrate shared by both arms so ER is not the variable.

## Dashboard And Explorer Artifacts

Dashboard artifacts exist for corpus inspection, not as the source of current
model claims.

- The canonical V9 corpus includes `dashboard_data.json` and
  `dashboard_standalone.html`.
- The current V9 dashboard rebuild target is `artifacts/v9/dashboard/`, which
  receives the committed Git LFS-backed `index.html` snapshot and the ignored
  `data_v9.json` from
  `python -m scripts.dashboard.build_v9_dashboard`.
- The builder refreshes `artifacts/v9/dashboard/index.html`; all other files
  under that directory, including recovery sidecars and generated JSON, remain
  generated and ignored.
- The committed demo diagnostic is the release input for the published daily
  budgets 5, 10, and 25; rebuilds must preserve that three-budget contract.
- V9dev intentionally does not include dashboard payloads; it is for tests and
  smoke runs.

After a fresh clone is hydrated with Git LFS, the dashboard can render canonical
corpus content plus the committed schema-3 explanation evidence and the current
architecture comparison release input. Only generated anomaly-ranking and
other local diagnostic sections may be absent or sparse until regenerated with
the commands above. The HTML snapshot is versioned through Git LFS, while its
generated data and recovery sidecars remain ignored.

Rebuild the current dashboard after generating any desired local diagnostics:

```bash
python -m scripts.dashboard.build_v9_dashboard
```

Dashboard tabs summarize corpus structure: overview, temporal/geographic
patterns, communities, outcomes, seizures, graph metrics, entity-resolution
context, and an interactive explorer. Treat ER dashboard material as historical
and diagnostic context for the current demo, not as a changing variable in the
V9 baseline-vs-GNN comparison.

## Current Regression Coverage

The focused test suite covers the active V9 demo stack:

| Test file | Coverage |
| --- | --- |
| `tests/test_df_detector.py` | sklearn detector helper behavior |
| `tests/test_df_graphmodel_rgcn.py` | graph/RGCN dataframe behavior |
| `tests/test_demo_baseline.py` | baseline feature construction and leak-safety expectations |
| `tests/test_run_demo_smoke.py` | V9dev demo smoke output |
| `tests/test_v9_corpus_snapshot.py` | V9dev corpus properties and graph-regression guards |

`tests/test_v9_corpus_snapshot.py` is the main corpus guard. It checks core
files, org-layer presence, dense co-travel, as-of co-travel edge timestamps,
the expected low catch-rate band, the hidden-carrier pool, shared-plate reuse,
the preserved lone-carrier tail, and that `COTRAVEL` reaches the graph built by
`gnn.graphmodel_rgcn.build_person_graph_typed`.

## File Layout

```text
docs/
  data/DATA_GUIDE.md               # active data guide
  research/changes_3.md            # canonical V9 design/results log

reproducibility/v9_observability_colab_schema3/corpus/
  synthetic_cbp_graph_corpus_v9/   # full V9 positive-control corpus

tests/fixtures/v9dev/              # small V9-profile test corpus
artifacts/v9/dashboard/index.html  # committed Git LFS dashboard snapshot
artifacts/v9/dashboard/            # other generated output is ignored

scripts/data/
  validate_corpus.py

scripts/dashboard/
  build_dashboard.py
  build_v9_dashboard.py
  explorer_ui.py
  v9_dashboard_ui.py

Real-world aggregates and historical reference inputs are outside the active
corpus path and remain calibration/context material only.
```
