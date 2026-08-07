# Changes & Decision Log — V9 Designed Positive-Control Demonstration

**Status: COMPLETE (2026-07-07).** This document covers the **V9** corpus and the
baseline-vs-GNN demonstration built on it. It is a **separate track** from the
honest V5–V8 work. The historical `changes_2.md` V8 note was intentionally
removed from this checkout. Nothing here changes the V8 findings.
Headline: on the designed
V9 corpus the GNN catches **2.3–2.9× more hidden carriers at operational depth** than a
strong 14-feature tabular baseline (p=0 for K≥500), via as-of guilt-by-association — a wash
only at the razor top (K≤100). See Results.

## 2026-08-06: evidence-first explanation graph

The V9 explanation graph now defaults to an evidence-first first-hop view,
separates unsigned model evidence weight from observable relationship type with
dual-channel edges, groups graph controls by purpose, and labels the strongest
published connections directly. When the strict narrative validator rejects or
lacks prose and ranked attribution is available, the Grounded narrative section
shows deterministic highest-attribution evidence instead of empty prose;
otherwise the inline panel shows an explicit attribution-unavailable state.
Model outputs, sidecars, strict as-of rules, graph limits, and complete tables
are unchanged.
Browser visual QA was unavailable in this environment, so verification used
executable DOM/canvas contracts and generated-dashboard inspection; no manual
visual pass is claimed.

## 2026-08-06: guided Overview and bootstrap explanation

The V9 Overview now leads with the operational result, then explains the
relational mechanism and limits before the dataset/model inventory. The daily
bootstrap panel now explains event-level paired re-sampling: event rows are
sampled with replacement, then ranked within each day under the same inspection
quota. It defines the Hybrid-minus-baseline event-hit gap, the 95% interval as
resampling variability, zero-crossing verdicts, and the event-vs-person
distinction. Artifacts, calculations, and as-of contracts are unchanged.

## 2026-08-06: published narrative and factor cleanup

The schema-3 UI source-reference validator now accepts the producer-generated
v4 attribution, component-pooling, and rank-fusion claim paths. The published
bundle contains validated local Gemma narratives for all 19 explanation cases;
the dashboard had been rejecting their valid claim references client-side.
Counterfactual cards now omit factors whose ablation leaves Hybrid rank
unchanged, while retaining both positive and countervailing rank effects.
Restart-selection stability remains separate from measured rank movement.

## 2026-08-05: explanation dashboard readability pass

The schema-3 explanation explorer now leads with a grounded narrative and an
explicit Baseline / Seed-0 GNN / Seed-0 Hybrid rank comparison, including a
plain-language baseline-to-Hybrid movement. Visible numeric text is capped at
three decimal places with trailing zeroes omitted across scores, faithfulness,
attribution, graph tables, progress labels, and legacy JSON panels. Artifact
precision, model semantics, lazy sidecar loading, and strict as-of evidence
contracts are unchanged.

## 2026-08-05: Graph-first GNN explanation workspace

- Reorganized the schema-3 explanation explorer around the selected case: full-width case/rank context, bounded explanation rail, large graph workspace, then readable narrative and measured factors.
- Moved stability, faithfulness, attribution, complete graph tables, and cohort metrics into accessible state-preserving disclosures.
- Added responsive case-picker behavior plus composed loading, empty, and retryable error states.
- Preserved explained-only eligibility, SHA-256 sidecar verification, strict as-of fail-closed behavior, graph semantics, artifacts, and evaluation logic.

## 2026-08-05: schema-3 explanation graph loading fix

Schema-3 overlay sidecars intentionally combine weighted attribution rows with
neutral structural-provenance rows. The dashboard now classifies rows before
attribution membership checks: rows with neither `explainer_median` nor `rank`
remain neutral context, while any row carrying either evidence field must pass
the complete weight, rank, identity, and base-community contract. This restores
graph loading across all 19 published GNN-explanation cases without weakening
fail-closed validation for malformed attribution evidence.

## What V9 is (and is not)

V9 is a **designed positive-control / demonstration corpus**: the generative process is
deliberately engineered so the signal lives in the **graph** (co-offender co-travel,
shared plates, propagable catches). Its purpose is to show that **a GNN recovers more
hidden smugglers than a strong tabular baseline when the relational signal is present** —
a method-validation / positive control.

- **It does NOT supersede the honest V8 result.** The V8 working summary is that in the
  realistic regime the graph signal is thin (many lone actors and dark members) and
  the GNN edge is bounded. That remains the honest finding.
- **V9 answers a different question:** *when the generative process contains relational
  signal, does a GNN exploit it better than a per-person tabular model?* Expected: yes.
- **Leak-free by construction.** The GNN wins via **as-of guilt-by-association** (a
  co-offender caught before time `T` illuminates still-uncaught cell-mates after `T`),
  never via the retired legacy leak (lifetime/future catches, outcome aggregates).

## The mechanism

Inside a co-offender cell, members co-travel and share plates. Over time some are
**caught** (`detected_flag`, the train label) while connected members **carry but pass**
(`false_negative_flag`, the hidden eval target). A per-person baseline sees only the
escapee's own features and misses them; a GNN message-passes the earlier catch across
co-travel + shared-plate edges (strictly `caught_time < T`) and flags them. The
population also keeps a **lone-smuggler tail** (carriers in no cell) findable by neither
arm — so the GNN's advantage is *specific to the connected subpopulation*, which is the
honest, realistic shape of the win.

## Design

The design is captured in this log and the current checked-in corpus snapshots.
The generator has been retired from this checkout after the V8/V9/V9dev snapshots
were produced. Older notes referenced `tasks/v9_demo_corpus_design.md` and
`tasks/v9_demo_corpus_plan.md`, but the `tasks/` directory is not present in this
checkout.

**Corpus knobs** (V9 snapshot: 120K persons / 200K events; `v9dev` snapshot:
2K/4K for tests):
- Denser co-offender co-travel (3–5 anchors-first cell-mates per org event).
- **Catch rate ≈ 4%** (measured 0.0401 = 8,013/200,000), NOT the ~10% first targeted.
  Higher rates require catching lone/benign carriers, whose catches then propagate along
  the graph to *benign* co-travelers and destroy the GNN's advantage. Catches are instead
  **concentrated in cells** (org-member crossing seizure rate 31.9% vs 1.8% non-org), which
  is what creates a clean as-of guilt-by-association signal. See test rationale in
  `tests/test_v9_corpus_snapshot.py::test_v9dev_catch_rate_and_fn_pool`.
- More connectivity: more/larger cells (`org_size` 4–12), dark rate 0.30 → 0.10, higher
  observability (0.80–0.99).
- **Role split:** each non-dark cell member is either an
  **anchor** (`V9_ANCHOR_FRAC≈0.55`, caught with high probability → the graph signal) or a
  **clean carrier** (carries but is forced to leave no enforcement trail → the hidden FN
  eval target). This split is what lets a caught anchor illuminate an uncaught cell-mate.
- Shared plates: cells reuse a small plate pool → high co-use counts.
- Preserved lone-smuggler tail (66.9% of hidden carriers are in no cell).

**Detection changes:**
- New weighted, as-of `SHARED_PLATE` / `SHARED_PLATE_HOT` edge rail (the HOT relation
  activates only for shared-plate edges at or after the first seizure observed on
  that plate, so later seizures do not hot-label earlier plate edges).
- GNN arm: as-of caught-propagation RGCN over
  `{COTRAVEL, RESIDENCE, SHARED_PLATE, SHARED_PLATE_HOT}`.
- Baseline arm: realistic **14-feature** observable tabular model (`gnn/
  demo_baseline.py`): as-of own history (`prior_crossings, prior_secondary, prior_seizure,
  prior_arrests`) + observed demographics (`age_bucket, sex`) + per-event context
  (`citizenship_country, residence_country, region, mode_of_transportation,
  travel_category, declared_trip_purpose, day_of_week, hour`), NO graph info. This is a
  **strong** baseline — it includes the person's own prior seizures and arrests — so the
  GNN is not winning against a demographics-only strawman; its only edge is relational.

### Bug caught & fixed: the co-travel rail was structurally empty (2026-07-07)

An external review (codex) flagged that the co-travel signal was **not reaching the GNN**.
Root cause: the demo graph builder (`gnn/graphmodel_rgcn.py`,
`build_anchor_graph`) derives
`COTRAVEL` edges from **≥2 observed records sharing an `event_id`**, but the generator only
emitted co-traveler `observed_person_records` for `scale_key=='v8'` — V9 wrote exactly one
record per event. So the dense co-travel V9 created lived only in `edges.csv` (which
`build_anchor_graph` never reads), and the RGCN's actual graph had **zero COTRAVEL edges**:
`{RESIDENCE:121033, SHARED_PLATE:877, SHARED_PLATE_HOT:211}`. The apparent win was really
caught-propagation over the **household-residence + a thin plate rail**, not co-travel.

The prior test (`test_v9dev_cotravel_is_dense`) gave false confidence because it checked
`edges.csv`, not the graph the model sees.

**Fix:** V9 emits a co-traveler observed record per event (via an independent
deterministic stream, strictly additive). After regeneration, the demo graph has real co-travel:
`{COTRAVEL:113293, RESIDENCE:169315, SHARED_PLATE:14385, SHARED_PLATE_HOT:5355}` (records
200K→333K, 36% of events multi-record). Catch rate (0.0401) and FN pool (13,456) are
per-event and unchanged. New guard `test_v9dev_cotravel_reaches_demo_graph` asserts rel-0
(COTRAVEL) edges exist in the **built graph**, not just `edges.csv`.

**Leak-free cleanup (2026-07-08):** Shared-plate HOT relation assignment was
changed so a future vehicle seizure cannot mark earlier shared-plate encounters
as `SHARED_PLATE_HOT`. The checked-in V8/V9/V9dev `PERSON_ASSOCIATED_WITH_PERSON`
edges were also retimestamped to the pair's first actual shared crossing instead
of the source person's first-ever crossing. This keeps `edges.csv` as-of consumers
from seeing co-travel relationships before they existed.

**Evaluation:** the existing leak-free harness — train on `detected_flag`, rank
`false_negative_flag` in the test pool; found@K / precision@K / recall@K on the whole
pool and the observable (findable) slice; paired-event bootstrap for significance.

## Results

### Corrected V9 observability regeneration (2026-07-17)

The full V9 comparison and seed-0 observability cohort were regenerated after
correcting `SHARED_PLATE_HOT` activation to use the earliest official
`label_available_time_utc` for each vehicle. The V9dev boundary/invariant smoke
and the focused source suite passed before the full run.

- The surrounding headline comparison remains a three-seed GraphSAGE ensemble
  (`[0, 1, 2]`) with deployable Hybrid fusion weight `0.75`.
- At the operational 25-inspections/day depth, Baseline recovered `560` hidden
  carriers and Hybrid recovered `981`.
- The separate seed-0 observability simulation recovered `502` people with
  Baseline and `884` with Hybrid: `291` were recovered by both, `211` were
  Baseline-only, and `593` were Hybrid-only, for a net gain of `382`.
- The lightweight artifact includes all `593` Hybrid-only cases. Detailed
  post-hoc explanation was deliberately bounded because transitive COTRAVEL
  pooling creates components as large as 6,952 people. The checked artifact
  attempted 10 representatives, recorded nine oversized-component failures,
  and retained one fully validated deterministic-template explanation. The
  explainer now fails closed before community/counterfactual expansion or
  GNNExplainer work when a pooled component exceeds the measured full-V9
  component-size p99 of six. Lightweight relationship-category enumeration also
  avoids model snapshots entirely.

This observability block is explicitly single-seed diagnostics. It does not
replace or alter any three-seed V9 headline metric.

Full-scale V9 (120K persons / 200K events), oracle-identity substrate (shared by both
arms, so ER is not the variable), 3 seeds, paired-event bootstrap (1,500 resamples),
`train_bucket='Q'`, 18 epochs. Source: `gnn/diagnostics/demo_comparison_v9.json`.

- **Pool:** 38,948 test events; **2,691 hidden carriers** — 708 observable (in a co-offender
  cell with an observable tie), 234 dark, 1,749 lone. The observable 708 is the GNN's
  recoverable ceiling; lone/dark carriers have no relational signal for either arm.
- **Demo graph relations:** `{COTRAVEL: 113,293, RESIDENCE: 169,315, SHARED_PLATE: 14,385,
  SHARED_PLATE_HOT: 5,355}`.

**Whole-pool recall (baseline → GNN):**

| K | baseline R@K | GNN R@K | GNN found − base (p) |
|---|---|---|---|
| 500  | 0.039 | 0.056 | +49  (p=0) |
| 2000 | 0.091 | **0.261** | +455 (p=0) |
| 5000 | 0.175 | **0.403** | +609 (p=0) |

**Observable (findable) slice — found@K `[baseline, GNN]` out of 708:**

| K | baseline | GNN | note |
|---|---|---|---|
| 50   | 3  | 1   | wash (whole-pool p=0.53) |
| 100  | 14 | 11  | wash (p=0.52) |
| 200  | 22 | 34  | borderline (p=0.054) |
| 500  | 50 | **107** | p=0 |
| 1000 | 73 | **237** | p=0 |
| 2000 | 90 | **504** | p=0 |
| 5000 | 140| **703** | GNN recovers ~all findable carriers (5× baseline) |

**Verdict — the GNN decisively catches more smugglers than the tabular baseline at every
operational depth (K ≥ 200), by 2.3–2.9× whole-pool recall at depth and ~5× on the findable
slice.** The mechanism is as-of guilt-by-association: once one cell member is caught, the
RGCN propagates risk across co-travel + shared-plate + residence edges (strictly
`caught_time < T`) and surfaces the still-uncaught cell-mates the per-person baseline cannot
see. This is the intended positive control: **GNNs catch more people than a strong baseline
when relational signal is present.**

**Honest caveats:**
1. **Top-K is a wash, not a GNN win.** At K ≤ 100 the baseline is level or marginally ahead
   — its own-history features (prior seizures/arrests) pick off a few obvious repeat
   offenders first. The GNN's advantage is *recall at depth* (a wider, structure-informed
   net that recovers whole cells), not precision at the razor top. That is the correct,
   expected shape for a guilt-by-association mechanism — not a clean sweep.
2. **The win is on the connected subpopulation.** 66.9% of hidden carriers are lone actors
   with no relational signal; neither arm can find them structurally. The 2.3–2.9× depth
   advantage is real but bounded by how much of the population is actually connected.
3. **Co-travel is the load-bearing rail** (confirmed by the before/after in the bug section:
   with the co-travel rail empty, the GNN *lost* the mid-band @500/@1000; restoring it
   flipped those to decisive wins). Residence and the seizure-weighted plate rail add to it.
4. **Catch rate is ~4%, not the ~10% first targeted** — deliberately, to keep catches
   concentrated in cells (see design note above).

> This is a positive control showing a GNN exploits relational signal when the generative
> process contains it. It does **not** change the honest V8 finding that in
> the realistic regime the real signal is thin and the GNN's edge is marginal.

## Unsupervised Anomaly Detection Improvements

The regional Isolation Forest is a one-class anomaly detector: it learns a region-specific
profile of normal tabular behavior, then flags rows with unusually low decision scores.
The dashboard presents two tracks:

1. **Strict unsupervised:** the forest fits without target labels and does not exclude
   rows using the positive label. This is the deployable unsupervised mode.
2. **Label-assisted benchmark:** known positive training rows are excluded from the fit;
   training labels are used only for that exclusion. This is a diagnostic benchmark, not
   a claim of label-free performance.

For either track, the validation split supplies threshold-selection metrics; the selected
threshold and its source are frozen before the held-out test split is scored. Test
precision, recall, F1, positive prevalence, and predicted-positive rate therefore describe
the frozen operating point. F1 is **not** maximized on the test set. Train exclusion counts
make the assisted-vs-strict fitting difference explicit.

The benchmark uses oracle identity resolution on synthetic data, so it does not measure
entity-resolution error. That oracle identity is a substrate limitation and must not be
read as deployable identity quality.

## Caught-supervised deployability comparison (2026-07-16)

The V9 anomaly-ranking comparison now uses three primary arms in artifact order, plus
one appendix ablation:

| Role | Arm ID | Fit signal | Feature count |
|---|---|---|---:|
| Primary A | `tabular_unlabeled` | unlabeled feature distribution | 14 |
| Primary B | `relational_unlabeled` | unlabeled feature distribution | 18 (14 + 4 relational proxies) |
| Primary C | `relational_caught_supervised` | as-of caught positives versus unlabeled (naive PU) | 18 (14 + 4 relational proxies) |
| Appendix | `tabular_caught_supervised` | as-of caught positives versus unlabeled (naive PU) | 14 |

The caught-supervised arms do **not** inherit a SCAR ranking guarantee. Retrospective
V9 corpus diagnostics show why: among actual carrier events, the observed catch rate is
**50.9% for organization members versus 27.4% for non-organization members**. Catching
is feature-dependent, so the score can reflect historical enforcement propensity as well
as carrier risk. Recovery of missed carriers is therefore an empirical held-out result,
not a theorem about preserving the true-carrier ranking.

### As-of label maturity

The fit cutoff is January 1, 2024. At that boundary, **229** training outcomes are
immature and **79** of those events eventually become caught. The operational rule is
explicit: **immature -> unlabeled**. Across full V9, all **8,013** caught labels mature
after their crossing, with delays of up to **28 days**. A caught-positive is available to
fit only when the observed catch and its label-availability timestamp are strictly before
the fit cutoff; future maturation is never backfilled into an earlier fit.

### Frozen operating point and evaluation strata

Every primary and ablation arm uses a label-free validation-score quantile as its
**operating point**. This equalizes the alert-volume policy; it is not probability
calibration and does not put scores on a shared probability scale. Scores and thresholds
freeze before synthetic oracle truth is joined for retrospective evaluation.

The retrospective target report separates:

- all carrier events;
- missed-at-this-event carriers;
- no-prior-catch missed events;
- lifetime-never-caught person recovery;
- unique-person first-hit recovery; and
- observed-catch enrichment precision and lift.

This distinction matters empirically: the V9 test split contains **2,691**
missed-at-event carrier events, and **213** are tied to people caught somewhere else in
their lifetime. A missed event is therefore not synonymous with a never-caught person.

The label and threshold semantics are deployable only **conditional on resolved identity**.
This synthetic study still uses oracle canonical identity and does not measure
production entity-resolution error. Oracle carrier evaluation is unavailable in
production; operational monitoring can observe caught enrichment only among adjudicated
alerts.

The former `assisted` result is quarantined under `legacy_oracle_benchmarks` as a legacy
oracle-assisted diagnostic. It is nondeployable and **not a ceiling**, because it both
changes the fit population with oracle labels and selects its threshold with oracle
validation labels. It never belongs in the primary lineup.

These numbers are **retrospective corpus diagnostics and evaluation, not fit inputs**.
They document V9 as the **designed positive control** and do not supersede V8: V9 tests
whether methods exploit deliberately propagable relational signal, while V8 remains the
honest thin-graph-signal track.

## Part: Full-V9 K=5 release, benchmark, and observability fixes (2026-07-20)

This part records a fresh full-V9 run at the non-negotiable operational depth of
**5 inspections/day**, a real giant-component benchmark, four correctness fixes
found by running the observability pipeline end-to-end for the first time on the
full corpus, and the hardware limit that gates full observability generation.

### Fresh K=5 scoring (measured, not fit inputs)

Config: seeds `[0,1,2]`, 18 epochs, quarterly training buckets, validation
sample 20,000, `daily_ks=(5,)`, 1,500 bootstraps. Canonical output rewritten to
`gnn/diagnostics/demo_comparison_v9.json`; durable checkpoint
`gnn/diagnostics/checkpoints/17d5ee9fe23234ab33b0ba33e36800ab21bd25101b32ff51bb787b259e4f3c52`.

Seed-level unique-person recovery at 5 inspections/day:

| Arm | mean unique recovered | population SD | score-averaged ensemble |
|---|---:|---:|---:|
| Baseline | 113 | 0.00 | 113 |
| Hybrid | 321 | 3.74 | 328 |
| Net gain | +208 | 3.74 | +215 |

Hybrid recovers ~2.8x the baseline at K=5. pool_size 40,578; hidden_total 2,691;
validation-tuned fusion weight 0.7. Full affected suite 683 passed / 1 skipped;
live `gemma4:12b` narrative test passed; V9dev end-to-end completed with complete
coverage (the tiny dev corpus has hybrid≡baseline, so zero cohort cases there).

### Real giant-component benchmark

From the verified checkpoint: 120,000 nodes / 2,639,472 typed edges; largest
Hybrid-only community 6,952 nodes (person P00032161, found after scanning 191
days); three-restart GNNExplainer plus a real gemma narrative on that community
succeeded. **Peak RSS was bounded at ~5.2 GiB with per-day snapshot release** —
the earlier giant-benchmark OOM (exit 137) is resolved. The benchmark's
publication-*sizing* projection remains architecturally fragile on heterogeneous
real communities and does not finalize; the authoritative published-bundle size
is to be taken from the real `resume_observability` output instead.

### Four correctness fixes (each TDD-tested)

The observability path had never been run end-to-end on the full corpus, so it
carried latent bugs that only trigger on real, large, heterogeneous communities:

1. **Truncated-edge source_row_count.** `observability_artifact._community_stream_source`
   emitted bounded dense edges with `source_row_count = full row total` but a
   truncated `source_row_ids`, violating the recovery bundle's
   `source_row_count == len(source_row_ids)` invariant. Fix normalizes to the
   bounded count and records the true total under `complete_source_row_count`,
   mirroring the overlay stream. This also fixes the real publication path, not
   only the benchmark.
2. **CommunityScope vs dict.** `giant_observability_benchmark._estimate_full_publication`
   subscripted a lazy `CommunityScope`. Added `_case_community` to materialize the
   bounded target-local dict view (via `member_subgraph` local indices).
3. **Per-expansion ring coordinates.** `sage_explainer.build_provenance_expansion`
   laid outside-community people out by their index within one expansion's set, so
   a person in two expansions got conflicting `x`/`y`. Both the recovery bundle and
   the dashboard require identical coordinates per node_id. Fix: deterministic
   `_outside_ring_position(node_id)`.
4. **Complementary overlay-node views (primary observability blocker).** A node that
   is both a ranked attribution node and a structural-provenance node was emitted
   twice with disjoint fields; `recovery_bundle._stream_overlay_evidence` rejected
   it as a conflict. Fix buffers the bounded overlay node set and merges
   complementary views by node_id (union of fields; still fails closed on a genuine
   shared-field disagreement). Validated on the real cases P00060034 and P00061000,
   which now write cleanly.

### Hardware limit on full observability generation

`resume_observability` generates 268 Hybrid-only cases, each with a real
`gemma4:12b` narrative. On the 16 GiB development machine the resident model
(~8 GiB) plus the engine plus a giant-community explanation exceeds RAM, and the
process is OS-killed within a few cases regardless of how it is launched. The run
is checkpoint-resumable but full generation must be completed on a larger machine
(or with the model offloaded between cases). The K=5 daily-budget observability
artifact is therefore **not yet regenerated**; the V9 dashboard's main panels use
the fresh K=5 comparison above, while its recovery-explainer panel still reflects
the prior observability artifact until this run completes on adequate hardware.

## Part: Demo-tab readability pass — simulated-catch budget sweep, bootstrap explainer, anomaly-ranking charts (2026-07-28)

Presentation-only work on the two demo tabs, plus one evaluation-config change
that adds budgets to the simulated-catch view without touching any published
headline number.

### Simulated-catch budgets are now swept independently of `daily_ks`

`gnn/run_demo.py` gained `SIMULATED_DAILY_KS = (5, 10, 25)`, threaded through
`main(simulated_daily_ks=...)` into `evaluate_daily_simulated_catches` and
recorded in the artifact as `simulated_catch_daily_ks`. `daily_ks` still drives
the capacity table, the daily crossing chart, and the daily bootstrap, so the
K=5 release above is unchanged; only the simulated recovery curve gained
staffing levels the operator can compare.

The canonical `demo_comparison_v9.json` was updated **from the frozen
checkpoint** `17d5ee9f…`, not from a re-fit: the stored baseline/GNN test scores
were re-fused at the recorded `w_gnn=0.7`, and every value the artifact already
published at `@5` (including all 273 daily series entries and the `initial_pool`
block) reproduced exactly before anything was written. Only
`simulated_catch_daily` and `simulated_catch_daily_ks` changed.

| Budget | Baseline unique people | Hybrid unique people | Inspections | Hybrid P / R / F1 |
|---:|---:|---:|---:|---|
| 5/day | 113 | 328 | 1,365 | 24.0% / 14.0% / 17.7% |
| 10/day | 217 | 488 | 2,730 | 17.9% / 20.8% / 19.2% |
| 25/day | 502 | 818 | 6,825 | 12.0% / 34.8% / 17.8% |

The Hybrid lead is widest at the tightest budget (2.9x at 5/day, 1.6x at
25/day), which is the operationally relevant direction: relational evidence
matters most when there is least capacity to spend.

### Dashboard presentation

- **Simulated catches.** Heading cut to `Simulated catches` with a one-line
  gloss; the budget selector now lists 5/10/25 and defaults to 5, matching the
  crossing chart and the recovery explorer.
- **Bootstrap verdicts.** Added a "how to read this" panel defining `mean diff`,
  `95% CI`, `p(Hybrid<=base)` and the win/wash/loss rule, plus a per-table note
  recording what each table is scored on. The daily table is whole-pool and does
  **not** follow the population toggle; the copy now says so.
- **Daily-operations lens fix.** The lens hardcoded `daily_found@25` and read
  `0 vs 0` on any run that does not publish a 25/day budget (including the K=5
  release). It now quotes whichever budget `daily_ks` actually contains.
- **Anomaly ranking.** The tab was tables-only. It now leads with three charts
  built from the same frozen artifact — missed-at-event recall by region,
  observed-catch enrichment lift with a 1x reference, and a
  precision-against-recall scatter whose per-region connectors trace the
  progression — plus a shared-scale recall-strata bar strip on every region
  card and a 2-series ablation chart. Arms are pinned to fixed categorical
  palette slots (blue / orange / aqua / yellow) validated for CVD separation and
  contrast against the dashboard's dark surface; every chart ships a legend and
  a screen-reader table.

Suite after the change: 830 passed, 1 skipped.

## Part: Additive GNN architecture bakeoff dashboard (2026-08-01)

The standalone command `.venv/bin/python -m gnn.gnn_architecture_bakeoff` resolved
the full-V9 configuration: seeds `0/1/2`, 18 epochs, `train_bucket='Q'`, global
`K=50/100/200/500/1000/2000/5000`, and daily `K=5/10/25/50`. It wrote
`gnn/diagnostics/gnn_architecture_comparison_v9.json`; no Baseline or Hybrid arm
was executed or written by this command.

The full artifact validated five arms: GraphSAGE, full-graph RGCN, GAT attention,
GIN, and KPI-AA approximation. At global K=500, whole-pool and observable
found/recall were:

| Arm | Whole found / recall | Observable found / recall |
|---|---:|---:|
| sage | 143 / 0.0531 | 114 / 0.1610 |
| rgcn | 144 / 0.0535 | 111 / 0.1568 |
| gat | 80 / 0.0297 | 49 / 0.0692 |
| gin | 23 / 0.0085 | 0 / 0.0000 |
| kpiaa | 139 / 0.0517 | 106 / 0.1497 |

At daily K=25, whole-pool aggregate found/precision/recall/F1 were:

| Arm | Found | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| sage | 1124 | 0.1647 | 0.4177 | 0.2362 |
| rgcn | 1129 | 0.1654 | 0.4195 | 0.2373 |
| gat | 1106 | 0.1621 | 0.4110 | 0.2325 |
| gin | 1077 | 0.1578 | 0.4002 | 0.2264 |
| kpiaa | 1104 | 0.1618 | 0.4103 | 0.2320 |

The dashboard independently validates and embeds this artifact under
`v9GNNArchitectureComparison`, rendering a strictly additive GNN-only section in
V9 Results; existing sections, navigation, and data remain unchanged. Generated
outputs were rebuilt at `artifacts/v9/dashboard/data_v9.json` and
`artifacts/v9/dashboard/index.html`.

This observed run used a 16GB Mac and about 12 active CPU-hours sequentially;
sleep/contention made wall time longer. This is an approximate observation, not a
benchmark guarantee. Future optimization should cache snapshots/checkpoints and
use at most about two workers.

The affected suite (`tests/test_gnn_architecture_bakeoff.py`,
`tests/test_run_demo_smoke.py`, `tests/test_df_graphmodel_rgcn.py`, and
`tests/test_v9_dashboard_builder.py`) completed **203 passed, 327 warnings in
436.46s (0:07:16)**. Warnings are existing Python 3.14/PyTorch/PyG/timezone/
joblib warnings. `git diff --check` and `py_compile` for the four affected
Python modules passed. The dashboard rebuild, generated-JavaScript syntax, and
desktop/narrow headless-Chrome visual checks passed. The in-app browser was
unavailable and direct Chrome console capture timed out, so console cleanliness
is not claimed.

## Part: Live-demo V9 Results order (2026-08-01)

The V9 Results tab now reads as a short live-demo narrative: headline and
three-lens orientation, operational depth and staffing results, cumulative
unique-person recoveries, daily crossing context, recovery evidence, bootstrap
confidence, then model and architecture methods. Model notes render in the
stable Baseline, Deployable Hybrid, GNN order. No metrics, data contracts, or
evaluation behavior changed.

The affected dashboard and recovery UI suite completed **307 passed**. The
rebuilt static dashboard was inspected with headless Chrome at the V9 Results
hash; the in-app browser backend was unavailable in this session.

## Part: Schema-3 dashboard contract and V9 Results presentation (2026-08-05)

The V9 dashboard's active recovery path is schema-3-only: top-level schema-1/2
UI and packaging compatibility was removed, while shared schema-3 evidence
helpers remain. The main GNN explainability case list/default now includes only
canonical, available `gnn_explanation` records whose `detail_index` membership
validates; the full cohort summary remains available. V9 Results now leads with
Daily Crossing Volume, Daily capacity, and Simulated catches. The crossing
selector defaults to 10/day; capacity renders Baseline and Deployable Hybrid
only, while GNN remains in the combined chart/headline and other relevant views.

The simulated-catch view/model/accessibility behavior and every source
JSON/ZIP artifact, data schema, and metric are unchanged. Legacy anomaly fields
may remain in source artifacts but are no longer rendered. No new measured
results were produced.

## Part: Schema-3 explanation panel stack (2026-08-06)

The schema-3 GNN explanation panels now occupy separate full-width rows in the
reading order Highest-attribution evidence, Key counterfactual factors, then
LLM explanation. This is presentation-only: the published evidence, rank
effects, restart-support semantics, narrative validation, and structural
fallback are unchanged. The focused recovery UI/dashboard-builder suite passed
361 tests after rebuilding the dashboard bundle.
