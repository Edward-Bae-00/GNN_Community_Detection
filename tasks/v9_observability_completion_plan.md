# V9 K=5 Observability Completion Plan

**Goal:** Complete a reliable full-V9, 5-inspections/day comparison and observability run. The final artifact must use the complete 120,000-person graph universe, a three-seed GraphSAGE comparison, genuine three-restart seed-0 GNNExplainer output, validated local `gemma4:12b` narratives, complete day-correct lazy evidence, and atomic fail-closed publication.

**Status as of 2026-07-20 (K=5 release pass):**

- Fresh full-V9 K=5 scoring produced checkpoint `17d5ee9f...` and rewrote
  `gnn/diagnostics/demo_comparison_v9.json` (seeds [0,1,2], 18 epochs, quarterly
  buckets, valid 20000, daily budget 5). Measured seed-level unique-person
  recovery at 5/day: baseline 113, hybrid 321 (SD 3.74), net +208; ensemble +215.
- Full affected suite: 683 passed / 1 skipped. Live `gemma4:12b` test passed.
  V9dev end-to-end completed with complete coverage (dev corpus has zero cohort
  cases). Real giant benchmark ran from the verified checkpoint: 120k nodes /
  2.64M typed edges, largest Hybrid-only community 6,952 nodes, three-restart
  explainer + real gemma succeeded, **peak RSS bounded ~5.2 GiB with per-day
  release (prior OOM resolved)**.
- Four correctness bugs fixed and TDD-tested (truncated source_row_count;
  CommunityScope materialization; deterministic outside ring coordinates;
  merging complementary overlay-node views). The observability blocker is
  validated on real cases P00060034/P00061000. See `changes_3.md` Part
  "Full-V9 K=5 release, benchmark, and observability fixes (2026-07-20)".
- **Blocked on hardware:** the full 268-case `resume_observability` generation is
  OS-killed on the 16 GiB dev machine (engine + ~8 GiB resident gemma + giant
  community). It is checkpoint-resumable and must complete on a larger machine or
  with the model offloaded. The K=5 observability artifact and the dashboard's
  recovery-explainer panel are therefore not yet regenerated; the dashboard's
  main K=5 panels are fresh.
- The benchmark publication-*sizing* projection is architecturally fragile on
  heterogeneous real communities and does not finalize; take the authoritative
  published-bundle size from the real observability run instead.

## Non-negotiable contract

- Operational depth is exactly 5 inspections/day.
- The surrounding comparison is GraphSAGE seeds `[0, 1, 2]` with one common validation-tuned fusion weight, per-seed unique-person recovery, mean, population SD, and a separate score-averaged ensemble.
- Observability is seed 0 only.
- Every Hybrid-only case must run target-local GNNExplainer with exactly three deterministic restarts.
- Every Hybrid-only case must have a validated local `gemma4:12b` narrative. Production has no deterministic-template fallback.
- Baseline-only cases have no GNN narrative but retain a complete as-of community.
- Edges, catches, labels, and community state must be available strictly before the scoring day.
- Whole communities are day-specific. Never reuse a community across days solely because its component ID matches.
- Every canonical node, connection, and provenance record remains lazily accessible even when diagnostic counterfactuals are bounded.
- Publication is exact, atomic, and fail-closed.

## Task 1: Complete model and explainer node universe

**Status:** Complete and reviewed.

**Files:** `gnn/graphmodel_rgcn.py`, `gnn/learned_cell.py`, `gnn/run_demo.py`, `tests/test_df_graphmodel_rgcn.py`, `tests/test_run_demo_smoke.py`, `tests/test_v9_corpus_snapshot.py`.

- [x] Build `node_ids` from every nonblank canonical oracle identity, including disconnected people.
- [x] Keep constant singleton base features without inventing edges.
- [x] Assert every typed edge endpoint belongs to the canonical universe.
- [x] Validate all train, validation, and test identities before baseline or GNN fitting.
- [x] Reject unmapped, non-string, blank, or outside-universe identities with counts and examples.
- [x] Remove zero-risk fallback for missing graph identities.
- [x] Preserve disconnected training rows and require finite singleton model scores.
- [x] Assert the V9 snapshot has 120,000 canonical nodes and unchanged typed-edge counts.

Focused command:

```bash
rtk env PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/test_df_graphmodel_rgcn.py \
  tests/test_run_demo_smoke.py \
  tests/test_v9_corpus_snapshot.py
```

## Task 2: Preflight expensive-run dependencies

**Status:** Complete and reviewed.

**Files:** `gnn/run_demo.py`, `gnn/explanation_narrative.py`, `tests/test_run_demo_smoke.py`, `tests/test_explanation_narrative.py`.

- [x] When production observability is requested, verify Ollama, the exact `gemma4:12b` tag, and a live selector-generation contract before fitting.
- [x] Reject `observability=True, narrative=False` before model work.
- [x] Preserve injectable runners for tests and prove failed preflight prevents fitting.
- [x] Retain four attempts per Gemma generation with no production template fallback.

## Task 3: Durable scoring checkpoint and no-training resume

**Status:** Complete and reviewed.

**Files:** `gnn/demo_checkpoint.py`, `gnn/run_demo.py`, `tests/test_demo_checkpoint.py`, `tests/test_run_demo_smoke.py`.

Checkpoint layout:

```text
gnn/diagnostics/checkpoints/<checkpoint_id>/
  metadata.json
  models/seed_0.pt
  models/seed_1.pt
  models/seed_2.pt
  scores.npz
```

- [x] Persist baseline validation/test raw scores and every seed's validation/test GNN raw scores.
- [x] Record corpus identity and fingerprints, seeds, epochs, train bucket, validation sample, feature schema, ordered node-universe hash, relation schema, fusion weights, exact event order, model-file SHA-256 values, and score-file SHA-256.
- [x] Derive checkpoint identity from logical tensor/array content and compatible run metadata.
- [x] Verify file closure, content hashes, shapes, dtypes, tensor manifests, seeds, run parameters, and event ordering before returning data or reusing an existing destination.
- [x] Reconstruct registered models only from `weights_only=True` state dictionaries; reject shape or dtype casts before `load_state_dict`.
- [x] Publish the checkpoint atomically after scoring/fusion and before observability.
- [x] Provide `resume_observability(...)` that rebuilds cheap corpus inputs and never fits.
- [x] Include the verified checkpoint ID in the recovery run identity.
- [x] Prove fresh-process resume score parity and no-fitting behavior.

Focused command:

```bash
rtk env PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/test_demo_checkpoint.py \
  tests/test_run_demo_smoke.py
```

## Task 4: Bound explanation work without hiding evidence

**Status:** Mostly implemented; selector finalization and real benchmark pending.

**Files:** `gnn/sage_explainer.py`, `gnn/giant_observability_benchmark.py`, `tests/test_sage_explainer.py`, `tests/test_explanation_narrative.py`, `tests/test_giant_observability_benchmark.py`.

The final deterministic salient-factor selector must contain at most:

- 10 unique canonical pair-relation factors ranked by GNNExplainer attribution;
- one target-incident relation-star factor per relation type;
- 5 caught-node factors ranked by absolute pooled-logit contribution;
- 5 pooling-changing COTRAVEL factors intersecting attributed edges;
- one structural-provenance group;
- the existing bounded edge-removal faithfulness points.

- [x] Preserve complete community construction and exactly three target-local GNNExplainer restarts.
- [x] Preserve exact provenance expansion for selected factors.
- [x] Keep unselected nodes, edges, and observations in lazy evidence.
- [x] Add instrumentation for factor, faithfulness, GNNExplainer, cache-hit, and unclassified encoder forwards.
- [ ] Finalize and independently review the selector against every exact deterministic category and bound above.
- [ ] Prove a synthetic community with more than 100,000 potential pair factors has constant-bounded diagnostic forwards.
- [ ] Run the real largest-case benchmark from a verified production checkpoint.
- [ ] Record wall runtime, local node/edge counts, salient-factor count, actual encoder-forward counts, peak RSS, and recovery-bundle dry-run disk estimate.

Do not mark this task complete from the existence of benchmark code or tests alone.

## Task 5: Defer, retry, and exactly finalize case failures

**Status:** Complete and reviewed.

**Files:** `gnn/observability_artifact.py`, `gnn/recovery_bundle.py`, `tests/test_recovery_observability.py`, `tests/test_recovery_bundle.py`.

- [x] Construct cases one person at a time in deterministic day/cohort/person order.
- [x] Create the writer from expected overlap IDs before case construction.
- [x] Record per-case construction, explanation, narrative, or streaming failures and continue the first pass.
- [x] Retry failed cases after all other cases; Gemma retains four attempts within each pass.
- [x] Clear only the matching failure after a successful retry.
- [x] Reject partial publication.
- [x] Require exact Hybrid-only/Baseline-only ID sets, zero failures, complete communities, and validated `gemma4:12b` metadata for every Hybrid-only case.

## Task 6: Normalize day-correct evidence and control disk

**Status:** SQLite/catalog/publication implementation complete and reviewed; giant streaming/memory proof pending.

**Files:** `gnn/recovery_evidence_store.py`, `gnn/recovery_bundle.py`, `gnn/observability_artifact.py`, `Documents/Data/scripts/v9_recovery_sidecars.py`, `Documents/Data/scripts/v9_recovery_explainer_ui.py`, and associated recovery/dashboard tests.

- [x] Store immutable canonical nodes, canonical pair/edge records, and raw provenance once in content-addressed SQLite catalogs.
- [x] Store day-specific membership, caught state, and status separately.
- [x] Keep `community_key = hash(scoring_day, component_id)`.
- [x] Reuse same-day/same-component communities without reusing cross-day state.
- [x] Stream normalized records into sidecars and expose complete Baseline-only and Hybrid-only evidence lazily.
- [x] Publish verified recovery bundles with same-filesystem atomic promotion and remove obsolete successful staging data.
- [x] Prefer independent copy-on-write dashboard clones, never hardlinks; preflight free space before physical copying, verify hashes, and write the recovery pointer last.
- [x] Cover day separation, deduplication, mutation isolation, pointer ordering, copy-space failure, and staging cleanup in focused tests.
- [ ] Demonstrate true streaming on a real giant community without first retaining an equivalent giant nested structure in memory.
- [ ] Record peak memory and physical disk behavior for the real giant/full-publication path.
- [ ] Confirm successful production publication does not leave three durable physical trees.

## Task 7: Verify the checkpoint → benchmark → resume sequence

**Status:** Pending. A prior live Gemma integration passed, but rerun it from the final merged tree before production.

### 7.1 Score and checkpoint without observability

```bash
rtk env \
  CBP_CORPUS_DIR=Documents/Data/synthetic_cbp_graph_corpus_v9 \
  PYTHONPATH=. \
  PYTHONUNBUFFERED=1 \
  .venv/bin/python -c '
from gnn.run_demo import main
main(
    seeds=(0, 1, 2),
    n_boot=1500,
    epochs=18,
    train_bucket="Q",
    valid_sample=20000,
    daily_ks=(5,),
    observability=False,
    out_name="demo_comparison_v9.json",
)
'
```

This still writes the durable checkpoint. Retain the exact line:

```text
scoring checkpoint = .../gnn/diagnostics/checkpoints/<checkpoint_id>
```

Do not guess the newest directory when multiple checkpoints exist. The checkpoint is resumable only after that line appears.

### 7.2 Benchmark the verified real checkpoint

```bash
rtk env PYTHONPATH=. PYTHONUNBUFFERED=1 \
  .venv/bin/python -m gnn.giant_observability_benchmark \
  --corpus Documents/Data/synthetic_cbp_graph_corpus_v9 \
  --checkpoint gnn/diagnostics/checkpoints/<CHECKPOINT_ID> \
  --output gnn/diagnostics/giant_observability_benchmark_v9.json
```

The benchmark must be read-only with respect to the corpus and checkpoint.

### 7.3 Re-prove live Gemma from the final tree

```bash
rtk ollama list
rtk env RUN_OLLAMA_INTEGRATION=1 PYTHONPATH=. \
  .venv/bin/python -m pytest -q tests/test_explanation_narrative.py -k live_gemma
```

Require the exact `gemma4:12b` tag and a validated `llm` result.

### 7.4 Resume observability without retraining

```bash
rtk env PYTHONPATH=. PYTHONUNBUFFERED=1 \
  .venv/bin/python -c '
from pathlib import Path
from gnn.run_demo import resume_observability
resume_observability(
    Path("gnn/diagnostics/checkpoints/<CHECKPOINT_ID>"),
    corpus_dir=Path("Documents/Data/synthetic_cbp_graph_corpus_v9"),
    observability_out_name="hybrid_recovery_explanations_v9.json",
    explanation_limit=None,
    narrative=True,
)
'
```

- [ ] Verify no baseline or GNN fitting helper is called during resume.
- [ ] Verify persisted baseline/seed-0 scores and event order match exactly.
- [ ] Verify recovery staging uses the checkpoint ID and fixed observability policy.
- [ ] Verify interruption resumes the matching stage rather than restarting completed cases.
- [ ] Verify final exact cohort coverage, zero failures, complete communities, validated narratives, and staging cleanup.

## Task 8: Release verification and artifact generation

**Status:** Pending.

### 8.1 Complete affected source suite

```bash
rtk env PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/test_df_detector.py \
  tests/test_df_graphmodel_rgcn.py \
  tests/test_demo_baseline.py \
  tests/test_run_demo_smoke.py \
  tests/test_v9_corpus_snapshot.py \
  tests/test_recovery_observability.py \
  tests/test_sage_explainer.py \
  tests/test_explanation_narrative.py \
  tests/test_recovery_bundle.py \
  tests/test_demo_checkpoint.py \
  tests/test_giant_observability_benchmark.py \
  tests/test_v9_dashboard_builder.py \
  tests/test_v9_recovery_explainer_ui.py
```

- [ ] Run the suite above from the final merged tree.
- [ ] Run V9dev end to end with forced disconnected Hybrid-only/Baseline-only fixtures and a transient Gemma failure.
- [ ] Complete Task 4's real giant benchmark and Task 6's streaming/memory proof.
- [ ] Check free disk against the measured publication requirement.
- [ ] Run the Task 7 sequence and retain its logs.
- [ ] Verify the comparison records 120,000 nodes, seeds `[0, 1, 2]`, 18 epochs, quarterly buckets, validation sample 20,000, and daily budget 5.
- [ ] Verify exact cohort coverage, zero failures, three explainer restarts per Hybrid-only case, validated `gemma4:12b` narratives, complete day-correct communities, valid hashes/pointers, and no stale staging tree.
- [ ] Rebuild the dashboard only after verified artifacts exist.
- [ ] Serve the dashboard over HTTP and verify cohort switching, narrative/fusion panels, complete lazy evidence, pagination, responsive behavior, and no browser console errors.
- [ ] Update `Documents/Data/changes_3.md` only with newly measured K=5 results. Do not reuse historical daily-25 values.

## Definition of done

- The complete affected suite passes from the final merged tree.
- A terminated observability run resumes from its verified checkpoint without fitting again.
- Disconnected people have finite singleton model scores and explanation parity.
- Real giant-case diagnostic forwards are bounded and measured.
- Real giant-community evidence generation is demonstrably streamed within measured memory/disk bounds.
- Every Hybrid-only case has three-restart GNNExplainer output and a validated local Gemma narrative.
- Every Baseline-only case has complete day-correct community evidence without a GNN narrative.
- Exact coverage, hashes, pointers, cleanup, and atomic publication validate.
- The full V9 K=5 artifact and dashboard are generated and manually verified.

