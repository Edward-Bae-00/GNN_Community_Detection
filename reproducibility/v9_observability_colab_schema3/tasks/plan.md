# 20 exact Hybrid explanations for the demo

## Status

Design approved 2026-08-03. Parts 1-5 implemented; `pytest tests/` is 62 passed.

**Ceiling set to 512 / 1024 on 2026-08-03** without a `--preflight-only` run.
Chosen from the display side rather than measured candidate sizes: the demo's
canvas becomes unreadable past roughly 1024 nodes, so 512/1024 is the largest
value worth admitting, and taking the largest affordable ceiling is safe here
only because selection freezes 20 candidates with no post-failure replacement.

Next action: full Colab run. `preflight_complete` fires ~45 min in carrying
`eligible_hybrid` and the whole `ceiling_grid`; if 512/1024 does not clear 20
eligible, stop there and read the grid rather than letting the run finish.
The exact-20 gate cannot pass with fewer than 20 eligible.

The layout that publishes `x`/`y` also changed -- see "Display layout" below.

## Run of 2026-08-04: measured, and why it could not pass

`preflight_complete` finally delivered the measurement step 3 asked for, and it
says the 512/1024 guess was wrong on the axis that mattered.

**The node ceiling never binds on this corpus.** From the reported
`ceiling_grid`, 1024 edges admits 19 candidates at 128, 256 *and* 512 nodes;
1536 edges admits 25 at both 192 and 384. Eligibility is a pure function of the
edge ceiling here. The 128 -> 512 node raise bought exactly zero candidates.
Cross-checking `smallest_by_nodes`, the 19 eligible cases are the ones with
`edge_count <= 1024`, and every one of them has <= 24 nodes against a 512-node
bound -- the corpus is dense, not wide (`node_count` p50 71, `edge_count` p50
9384).

So the run was already unpassable at `selection_frozen`, 69 minutes in, on
three independent gate clauses:

- `hybrid_eligible=19 < 20` -- the exact-20 budget cannot be filled.
- `hybrid_structural_fallback=1` -- any fallback fails the gate by design.
- `failed_count>=7` -- every attempted `gnn_explanation` case failed.

The remaining ~3.6 hours could not have changed the verdict. `--allow-shortfall`
in the notebook means the producer still exits 0, so a green cell is not a
healthy run; `result.json` carries the real one.

**Ceiling reset to 192/1536** (25 eligible), the smallest measured step that
clears 20. This is now set from the grid rather than from the display side.
Headroom still does not buy failure tolerance: selection freezes 20 and
`no_post_failure_replacement` is True, so all 20 selected cases must succeed.

### The explanation failures are not yet root-caused

All 7 attempted cases failed, and the reason is *not* in the pasted log: the
`case_published` stage event carried `status` but no reason, so a 4.75-hour run
reported that everything failed and nothing about why. Fixed -- both
`case_published` sites now emit a bounded `failure_reason`, guarded by an AST
test in tests/test_diagnostics_hardening.py so the live stream cannot silently
regress to a reason-free `failed` again.

What the timing already rules out: the failures land *after* the explainer
(63s for the smallest case, up to 2556s for the largest, scaling with graph
size), and all 19 eligible cases are tiny (4-24 nodes, 24-956 edges). This is
not a size, memory or ceiling problem -- it is in the post-explainer compose /
validate / narrative path, and it is deterministic across every case.

**The exact change-set is now known.** `~/Desktop/GNN_Community_Detection`
(git) carries the last copy of `gnn/sage_explainer.py` from before this round.
Diffing its `HEAD` against this package isolates everything that changed
between the run that produced explanations and the run where every case fails:

1. `MAX_LOCAL_EXPLANATION_NODES/EDGES` 128/256 -> tied to the explainer ceiling.
2. `display_hop_ring_layout` added, applied to the display projection.
3. `CommunityScope.iter_nodes` now emits a `target` field.
4. `candidate_edges` dropped `source_limit=MAX_LOCAL_SOURCE_ROWS_PER_EDGE` and
   truncates itself, recording complete membership under
   `COMPLETE_SOURCE_ROW_INDEX` plus `source_rows_truncated`.
5. `projection_policy` gained `node_layout` and `attribution_source_rows`.
6. `compose_case_explanation` gained the eligibility re-check, epoch
   validation, completeness accounting and the `attribution_completeness` block.

Checked and cleared as failure mechanisms: (3) `target` is already in
`RecoveryEvidenceStore._DAY_NODE_FIELDS`, so it splits into per-day status and
the canonical node record stays `{node_id}`; the `_community_stream_source`
CommunityScope/Mapping asymmetry is identical in the pre-change copy. (5)/(6)
add keys, and neither `write_case` nor `validate_explanation_payload`
allowlists explanation fields. (4) cannot collide in `source_to_edge`:
`source_row_id` hashes `(u, v, avail_time, edge_type, occurrence)` while the
group hashes `(sorted(u, v), edge_type)`, so a row belongs to exactly one
group, and `_edge_record` is byte-identical across the two copies.

(4) does carry a real cost, though: `_edge_record` now builds the complete
source-row list for *every* group in the community rather than 16 rows, and
`heapq.nsmallest` drains the whole generator. Against the documented shape
(RESIDENCE 24466 groups, max 1144 rows) that is a large constant-factor
slowdown of `materialize_local` on every case. It explains cost, not failure.

No change in the set has a mechanism that provably raises, so none of it should
be reverted on suspicion. Get the traceback first.

Ruled out from the saved notebook (`~/Downloads/v9_schema3_observability.ipynb`,
which holds the failed run's outputs): the narrative path was healthy.
`gemma4:12b` pulled (7.6 GB), `ollama list` verified it, and the CLI smoke probe
passed, so `narrative_preflight_failed` was 0 and the LLM narrator was live
during all seven failures. The producer cell is complete at 31 lines with no
stderr and no traceback, so no further evidence exists off-VM.

The reasons already exist on the Colab VM and do not need a re-run to read:
`RecoveryBundleWriter.record_failure` checkpoints on every failure, so

    /content/v9_schema3_run/.hybrid_recovery_explanations_v9.recovery-stage/*/checkpoint.json

holds `failures[]` with `reason_code` and full `message` per case. Read that
before spending another session -- but note it is VM-local, so it is gone once
the runtime is recycled.

**Cheapest way to get the traceback back.** One case is enough, and the
selection/limits are part of the staging fingerprint so this cannot contaminate
a real run:

    python3 -u run_schema3_observability.py \
      --work-root /content/v9_schema3_diag \
      --hybrid-detail-limit 1 --baseline-control-limit 0 --allow-shortfall

Use a *fresh* work root. The ceiling and the limits both moved, so the run
fingerprint differs from the failed run's; reusing `/content/v9_schema3_run`
would hit the mismatch branch (`RecoveryBundleError`) or leave diagnostic
staging in the real run's tree. Preflight still costs ~65 min (it measures all 268 candidates regardless), then
one hybrid case. ~1.5 h instead of ~11 h, and `case_published` now carries
`failure_reason` and `failure_traceback`, so the failing line appears in
producer.log as it happens.

## Problem

`hybrid_detail_limit` is already 20. The shortfall is upstream: only 10 of 268
Hybrid candidates pass preflight, so the remaining 10 budget slots are filled
with community-only structural fallbacks.

The gate is `MAX_LOCAL_EXPLANATION_NODES = 128` / `MAX_LOCAL_EXPLANATION_EDGES =
256` (gnn/sage_explainer.py:32-33). `explainability_eligibility` measures the
target's exact unpruned two-hop pre-pool subgraph and refuses anything larger.
`_fixed_explainer_limit` rejects any per-call override, so the ceiling is a
global invariant.

## Decision

Keep GNNExplainer running on the **exact** computation graph. Raise the ceiling
to admit >= 20 candidates. Do not prune the explainer input: pruning would make
the masks describe a truncated graph rather than the model's real computation.

The candidate pool cannot be re-cut instead -- 268 candidates is already nearly
the entire hybrid-recovered set of 325.

## Changes

1. **Name the two bounds, then tie them together** (gnn/sage_explainer.py)
   - `MAX_EXPLAINER_INPUT_NODES` / `MAX_EXPLAINER_INPUT_EDGES` drive eligibility.
   - `MAX_LOCAL_EXPLANATION_NODES/EDGES` are **defined from** them rather than
     set independently. Raise both together.
   - Preflight validators move to the new constants:
     observability_artifact.py:825-830, :1962-1963,
     giant_observability_benchmark.py:626-645.

   REVISED 2026-08-03 after external review. The original plan let the two
   diverge, arguing that raising the display bound would inflate narrative
   prompts. Both halves of that were wrong:
   - `build_fact_packet` (explanation_narrative.py:701-709) sends bounded top-10
     lists, not the display graph, so prompts barely grow.
   - Divergence is unsafe. `materialize_local` picks displayed nodes by
     target/pooled/caught/salience priority before any attribution exists
     (sage_explainer.py:530-537); `compose_case_explanation` then discards mask
     records whose display edge was pruned (:3542-3549), ranks
     top_local_nodes/top_edges over survivors only (:3628-3656), and builds
     faithfulness from the same projected edges (:3813-3822) -- while the
     narrative asserts "the top unsigned local-node attribution"
     (explanation_narrative.py:867). This is lossless today *because* the
     bounds are equal; splitting them is what would introduce the loss.
   - Guard: a test parses sage_explainer.py and fails if the display bounds stop
     being defined from the ceiling. Verified by unlinking them and watching it
     fail, then reverting.
   - Each explained case now publishes `attribution_completeness` (omitted
     nodes, omitted mask records, omitted/retained mask mass), and the per-case
     stage event carries `attribution_complete`, so completeness is demonstrated
     per case rather than assumed from configuration.

2. **Bind the ceiling into the staging fingerprint**
   (gnn/observability_artifact.py:2919-2928)
   - Staging dir id is `sha256(run_fingerprint)[:24]`. `policy` records restart
     seeds, epochs and narrative model but not the eligibility ceiling, so a
     re-run with a new ceiling would resume into the OLD staging dir. Cases
     already published as community-only fallbacks would then be replayed via
     `staged["explanation"]` (observability_artifact.py:1508), which those
     payloads lack -> KeyError -> failed cases -> gate failure.
   - Add `explainer_max_nodes` / `explainer_max_edges` to the policy block.

3. **Measure before choosing the number**
   - `preflight_complete` carries the measured size distribution (already
     computed today, then discarded).
   - `--preflight-only` in run_schema3_observability.py, implemented entirely in
     the runner's existing `on_stage` callback: write
     `preflight_distribution.json`, raise a sentinel, `main()` catches it and
     exits 0. No library control-flow change.
   - Preflight cost does not depend on the ceiling (`member_subgraph` is
     measured either way), so this stays ~45 min.

4. **Catalog count fix** (gnn/recovery_evidence_store.py:231-250,
   gnn/recovery_bundle.py:869-878)
   - After every community write, `catalog_counts` runs three
     `SELECT DISTINCT ... ORDER BY canonical_id` scans over the whole staged
     catalog and `json.loads` every row only to count it. Cost grows per case;
     this is the observed ~20 min/case wall.
   - Replace with `SELECT COUNT(DISTINCT canonical_id)`. Equivalent because
     `records` is `PRIMARY KEY (record_type, canonical_id)`
     (recovery_evidence_store.py:94-100), so canonical_json cannot vary per id.

5. **Per-case progress events** (gnn/observability_artifact.py)
   - One stage event per published case so multi-hour stages are observable.

## Verification

- `python3 -m pytest tests/ -q` runs locally: the suite stubs
  `gnn.sage_explainer` when torch is absent (tests/test_diagnostics_hardening.py:11-31).
  Baseline before changes: 15 passed.
- The stub name lists in tests/test_diagnostics_hardening.py:25-29 and
  tests/test_schema3_rank_reference_ordering.py:36 must gain any new constant
  that observability_artifact imports, or import fails under the stub path.
- Full explainer behaviour needs Colab (torch + torch_geometric).

## Sequencing

1. Land code changes (this session).
2. Let the in-flight 10+10 run finish as a safety-net artifact.
3. Run `--preflight-only` on Colab (~45 min) -> read distribution.
4. Set the ceiling from the 22nd-smallest candidate's counts, with headroom.
5. Full run. The structural-fallback stage disappears once 20 are eligible
   (`fallback_slots = hybrid_limit - len(selected hybrid)` = 0).

## Attribution completeness (round 2, done 2026-08-03)

External review found the first completeness mechanism was telemetry, not
enforcement, and that equal ceilings alone do not make attribution complete.
Both correct. Fixed:

1. **Masks aggregate over complete source-row membership.**
   `MAX_LOCAL_SOURCE_ROWS_PER_EDGE = 16` truncates a canonical edge's published
   source rows, and `source_to_edge` was built from that truncated list, so mask
   weight on later rows was dropped. `materialize_local` now records complete
   membership per displayed edge under a transient key that
   `compose_case_explanation` consumes and removes before publication; the
   displayed provenance stays bounded and keeps `source_rows_truncated`.
   Reproduced the corpus condition locally: COTRAVEL 5878 pair groups exceed 16
   source rows (max 64), RESIDENCE 24466 (max 1144).
2. **Feature-stat truncation is reported.** `attribution_completeness.scope` is
   `ranked_node_and_edge_attribution`; `node_feature_stats` carries
   published/expected/omitted. Note the layout is 8 features, not 6, so a
   128-node case expects 1024 records against a 512 cap.
3. **Completeness is enforced, not just logged.** `hybrid_attribution_complete`
   is published in coverage, and the gate requires it to equal
   `hybrid_explained`. Enforced at the gate rather than raised in the explainer
   so a bad run finishes and reports instead of failing cases and burning retry
   slots.
4. **All attribution-shaping caps are in the staging fingerprint**, so changing
   a truncation policy cannot reuse explanations staged under the old one.
5. Regression guards: structural tests assert `candidate_edges` reads complete
   rows and that the transient index never reaches a payload. Verified by
   reintroducing the bug and watching them fail.
6. Zero-explained runs now still name the ceiling in the gate failure.

Still needs Colab: no test here has seen a real GNNExplainer mask, so the
end-to-end regression for a >16-source-row edge has to run there.

## Display layout (2026-08-03)

Raising the ceiling to 512/1024 exposed that the published coordinates carried
no structure. `CommunityScope.iter_nodes` placed nodes on a `sqrt(N)` grid in
sorted `node_id` order, so position encoded alphabetical rank and every edge was
a line between two unrelated cells. Worse, the grid was sized from the *whole*
community while only the bounded display projection is drawn, so the drawn nodes
landed in scattered cells of an oversized grid.

- `display_hop_ring_layout` (gnn/sage_explainer.py) replaces it: target at the
  centre, one ring per `message_distance`, each ring ordered so a node sits in
  the arc of its lowest-id neighbour one ring in. A ring over
  `DISPLAY_RING_BAND_CAPACITY` (120) nodes spreads across up to
  `MAX_DISPLAY_RING_BANDS` (4) concentric sub-rings, because 480 hop-2 nodes on
  one circle render as a solid band. Deterministic and O(N log N + E).
- `materialize_local` applies it to the display projection specifically.
  `iter_nodes` keeps its grid because it must stay a whole-community stream for
  the chunked sidecars.
- `projection_policy.node_layout` records it as `hop_rings_around_target`.
- The demo repo carries a byte-identical copy of the function, plus a JS port
  (`recoveryHopRingLayout`) so artifacts published before this change still
  render structurally. `GNN_Community_Detection/tests/test_recovery_layout_parity.py`
  fails if the three drift; verified by unlinking the JS radius and watching 5
  of its tests fail, then reverting.

## Open (raised by external review, not yet done)

- ~~**Exact-20 gate.**~~ DONE 2026-08-03. The Hybrid budget must now be filled
  by `hybrid_explained` alone; any `hybrid_structural_fallback` fails, and the
  failure names `hybrid_eligible` when the ceiling rather than case failures is
  the binding constraint. `hybrid_eligible` joined `_COVERAGE_GATE_FIELDS`.
  Covered by tests/test_coverage_gate_exact_hybrid.py (11 tests: 20+0 passes;
  10+10, 19+1, 19+0 fail; small candidate pools stay a legitimate shortfall but
  still reject fallbacks). `--allow-shortfall` still overrides, unchanged.
- **Ceiling headroom does not buy failure tolerance.** Selection freezes 20 and
  `no_post_failure_replacement` is True (observability_artifact.py:1718,
  enforced :2012), so spare eligible candidates are never used. Within-run
  same-case retry would be the actual fix.
- **`--preflight-only` hygiene.** It constructs the bundle writer (and its
  sqlite staging dir) before stopping, never closes or removes it, leaves any
  prior artifact/`result.json` in the work root untouched, and exits 0. Run it
  in a fresh work root until fixed. `preflight_distribution.json` should also
  carry checkpoint id, corpus identity, model/graph fingerprints, current
  ceilings, per-candidate IDs, a timestamp, and `mode: preflight_only`.
  The notebook (cell 10) hardcodes the full-run command with no toggle.
- **Measurement does not describe the selected cases.** The grid reports how
  many candidates a ceiling admits, but selection is by balancing priority, not
  size. It should simulate selection per candidate ceiling and report selected
  IDs, max/total selected nodes and edges, largest selected case, and expected
  fallback count.
- **Catalog counts still rescan.** Three counts over the whole active catalog
  after every community; total work still grows with community count. The fix is
  incremental maintenance in `register()`, not a benchmark.
- **RSS field is wrong** (observability_artifact.py:1003): `value * (1024 if
  Darwin else 1)` is backward on both platforms -- macOS ru_maxrss is bytes,
  Linux is KB. Do not size anything from `process_peak_rss_bytes` until fixed.
- **`MAX_NODE_FEATURE_MASK_STATS = 512`** is a positional cap filled in node
  order (sage_explainer.py:3708-3736), so at a higher ceiling it covers a
  smaller fraction of nodes. It does not affect the "top" claims, but it should
  either scale or report its coverage.
- **Nothing here has run against real Torch/PyG.** The suite stubs the explainer,
  so no test has seen a real mask, a graph over 128/256, or an end-to-end
  staging/resume. Benchmark the largest selected case before committing to 20.
- ~~Ceiling value: pending step 3.~~ Set to 512/1024 from the display bound, not
  from measurement. `--preflight-only` was never run, so the eligible count at
  this ceiling is still unknown until `preflight_complete` reports it.
- If 512/1024 does not admit 20 eligible candidates, the mixed exact/projected
  option is now the option to revisit rather than raising further: past ~1024
  nodes the community canvas stops being interpretable, so a higher ceiling buys
  explanations nobody can read.
- `MAX_NODE_FEATURE_MASK_STATS = 512` now covers a much smaller fraction: a
  512-node case expects 4096 records against the 512 cap. It does not fail the
  gate (`attribution_completeness.complete` deliberately excludes
  `node_feature_mask_stats`) but the published dump is now ~12% of the input.
