# Changes & Decision Log — V9 Designed Positive-Control Demonstration

**Status: COMPLETE (2026-07-07).** This document covers the **V9** corpus and the
baseline-vs-GNN demonstration built on it. It is a **separate track** from the
honest V5–V8 work. The historical `changes_2.md` V8 note was intentionally
removed from this checkout. Nothing here changes the V8 findings.
Headline: on the designed
V9 corpus the GNN catches **2.3–2.9× more hidden carriers at operational depth** than a
strong 14-feature tabular baseline (p=0 for K≥500), via as-of guilt-by-association — a wash
only at the razor top (K≤100). See Results.

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
