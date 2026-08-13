# Project Memory

## 2026-08-06: dashboard and data utility packaging

- Dashboard builders, UI modules, assets, and recovery sidecar helpers live in
  the importable `scripts.dashboard` package; corpus validation lives in
  `scripts.data.validate_corpus`.
- V9 dashboard code uses the canonical `gnn.paths` contracts and publishes to
  `artifacts/v9/dashboard`; serve that directory over HTTP for sidecar-backed
  pages. `v9_dashboard_ui.py` was moved without behavior changes.

## V9 K=5 observability architecture

- The graph node universe is the complete sorted canonical oracle universe, including disconnected people. Train, validation, and test identities are validated against it before any baseline or GNN fitting. Missing, blank, non-string, or outside-universe mappings fail closed; scoring never substitutes `0.0`.
- Expensive scoring is persisted under `gnn/diagnostics/checkpoints/<checkpoint_id>/`. The checkpoint ID is derived from logical tensor/array content and run compatibility metadata. Physical model and score files retain SHA-256 closure, array shape/dtype/content manifests, model tensor shape/dtype/content manifests, corpus fingerprints, schemas, fusion weights, and exact validation/test event order.
- Checkpoint reuse verifies the complete existing payload before acceptance. Models are reconstructed only from the registered architecture and `weights_only=True` state dictionaries; tensor dtypes and shapes must match the target model before `load_state_dict`.
- `gnn.run_demo.resume_observability` rebuilds cheap corpus/graph inputs and generates observability without fitting. Recovery staging identity includes the verified checkpoint ID plus the fixed observability policy, so interrupted generation resumes the correct stage.
- Production observability requires local `gemma4:12b`. A live Ollama tag and selector-generation contract preflight runs before fitting. `narrative=False` and deterministic-template production fallback are rejected; each Gemma generation retains four attempts.

## Explanation, evidence, retry, and publication decisions

- GNNExplainer remains target-local with exactly three deterministic restarts. Diagnostic counterfactuals are bounded to salient pair-relation, target relation-star, caught-node, pooling-changing COTRAVEL, and structural-provenance factors. Complete graph evidence remains available lazily and is not represented as an all-factor rescore set.
- Recovery evidence uses the normalized SQLite-backed catalog in `gnn/recovery_evidence_store.py`: immutable canonical nodes, edges/pairs, and provenance are stored once by content; day-specific community membership and caught/status state remain separate. `community_key` remains a hash of scoring day and component ID to preserve as-of differences.
- Case generation is deterministic and per-person. Failures are recorded without aborting the first pass, retried after the cohort pass, and cleared only on successful retry. Finalization requires exact Hybrid-only/Baseline-only ID coverage, zero failures, complete communities, and validated `gemma4:12b` metadata for every Hybrid-only case.
- Recovery publication uses same-filesystem atomic promotion and removes obsolete successful staging data. Dashboard publication prefers independent copy-on-write cloning, never hardlinks; physical copies require a free-space preflight and post-copy hash verification, with the recovery pointer written last.

## 2026-07-20 measured results and fixes

- Fresh full-V9 K=5 scoring checkpoint: `gnn/diagnostics/checkpoints/17d5ee9fe23234ab33b0ba33e36800ab21bd25101b32ff51bb787b259e4f3c52` (seeds [0,1,2], epochs 18, quarterly buckets, valid_sample 20000, daily budget 5). Canonical comparison rewritten at `gnn/diagnostics/demo_comparison_v9.json`. Full affected suite: 683 passed / 1 skipped. Live `gemma4:12b` integration test passed. V9dev end-to-end completed with complete coverage (0 cohort cases in the tiny corpus; hybrid≡baseline there).
- Measured K=5 seed-level unique-person recovery (5 inspections/day): baseline mean 113, hybrid mean 321 (population SD 3.74), net +208; score-averaged ensemble hybrid 328 vs baseline 113 (+215). Hybrid ≈ 2.8× baseline. pool_size 40578, hidden_total 2691, fusion w_gnn 0.7.
- Giant benchmark (checkpoint 17d5ee9f): 120,000 nodes / 2,639,472 typed edges; largest Hybrid-only community 6,952 nodes (person P00032161, 191 days scanned); 3-restart GNNExplainer + real gemma narrative succeeded; **bounded peak RSS ~5.2 GiB with per-day snapshot release (prior OOM/exit-137 is resolved)**. KNOWN LIMITATION: the benchmark's publication-*sizing* projection is architecturally fragile on heterogeneous real communities and does not finalize; the authoritative disk/memory number comes from the real recovery bundle produced by `resume_observability` instead.
- Four real correctness bugs found and fixed (all TDD-tested), because this pipeline had never run end-to-end on the full V9 corpus:
  1. `observability_artifact._community_stream_source` did not normalize truncated-edge `source_row_count` (bounded dense edges). Fix normalizes to `len(source_row_ids)` and preserves the true total under `complete_source_row_count` (mirrors the overlay stream). Test: `test_recovery_bundle.py::test_community_stream_source_normalizes_truncated_edge_source_row_count`. **Also required by the real publication path.**
  2. `giant_observability_benchmark._estimate_full_publication` treated a lazy `CommunityScope` as a dict. Added `_case_community` to materialize the target-local dict view. Test: `test_giant_observability_benchmark.py::test_case_community_materializes_communityscope_target_local_view`.
  3. `sage_explainer.build_provenance_expansion` assigned per-expansion ring coordinates, so an outside person in ≥2 expansions got conflicting x/y. Fix: `_outside_ring_position(node_id)` deterministic per node_id. Test: `test_sage_explainer.py::test_outside_ring_position_is_stable_per_node_id_and_independent_of_cohort`.
  4. **Primary observability blocker:** a node that is both a ranked attribution node and a structural-provenance node was emitted twice with disjoint fields; `recovery_bundle._stream_overlay_evidence.add_node` rejected it. Fix: buffer the bounded overlay node set and MERGE complementary views by node_id (union of fields; still fail closed on a genuine shared-field conflict). Tests: `test_recovery_bundle.py::test_overlay_merges_complementary_views_of_the_same_node` and `::test_overlay_still_rejects_genuine_shared_field_conflict`. Validated on the real failing cases P00060034 and P00061000 (both now write cleanly).
- Environment risk: this is a 16 GiB machine. Long background runs that use Gemma (8.1 GiB on GPU) are killed intermittently (OOM/harness). `resume_observability` (268 Hybrid-only cases, each with a real gemma narrative, ~hours) must be run detached and is checkpoint-resumable; monitor `gnn/diagnostics/.hybrid_recovery_explanations_v9.recovery-stage/<id>/checkpoint.json` for `cases`/`failures` progress. As of this writing the resume is running detached and processing cases cleanly (previously-failing cases resolved).

## 2026-07-20 follow-ups: dashboard nav fix + Colab handoff

- Dashboard build was broadly broken (pre-existing): the base v8 template lost its
  `<!-- V9_NAV_TABS -->` / `<!-- V9_TAB_SECTIONS -->` markers, so `build_v9_dashboard.py`
  silently injected neither the V9 nav buttons nor the `tab-v9Results`/`tab-unsupervisedAD`
  section wrappers (V9 tabs were unreachable), and there was no grouped/ARIA/hash-routed
  nav. Fixed in `scripts/dashboard/build_v9_dashboard.py` with marker-independent
  injection (`_inject_v9_nav_and_sections`) plus `_apply_grouped_accessible_nav` /
  `_rewrite_nav_js` (data-nav-group readout/explore, role/aria-controls/aria-selected,
  data-navigate-tab delegated clicks, location.hash + hashchange routing). 74/74 dashboard
  tests pass; dashboard serves with fresh K=5 data.
- Colab handoff package for the blocked observability generation lives at
  `~/Desktop/v9_observability_colab/` (outside the repo, 1.4 GB): fixed `gnn/` source, the
  fresh checkpoint, the FULL corpus (all 30 CSVs — the checkpoint fingerprints every CSV
  and pins the absolute corpus path, so a subset/symlink will not verify), a notebook,
  `run_observability.py`, and a README covering run + result-return + post-run steps. The
  notebook copies the corpus to the recorded absolute path (symlink fails: the loader
  resolves it) and installs ollama + `gemma4:12b`. Validated locally end-to-end up to case
  generation (checkpoint verification + engine build pass with the packaged code).

## 2026-07-28: demo-tab readability pass

- **Simulated-catch budgets are now a separate sweep from `daily_ks`.** `gnn/run_demo.py`
  has `SIMULATED_DAILY_KS = (5, 10, 25)`, passed to `evaluate_daily_simulated_catches`
  via `main(simulated_daily_ks=...)` and published as `simulated_catch_daily_ks`.
  `daily_ks` still owns the capacity table, the daily crossing chart, and the daily
  bootstrap, so the K=5 release numbers are untouched. Do not re-couple them: the demo
  needs several staffing levels on the recovery curve without restating the headline at
  budgets the run never bootstrapped.
- **The artifact was updated from the frozen checkpoint, not a re-fit.** Scores from
  `checkpoints/17d5ee9f…` were re-fused at the recorded `w_gnn=0.7` and every previously
  published `@5` value (all 273 daily entries, `initial_pool`) reproduced exactly before
  writing; only `simulated_catch_daily`/`simulated_catch_daily_ks` changed. This is the
  cheap, safe pattern for adding post-hoc evaluation budgets — retraining risks moving
  every published number for a presentation change.
- Measured: 5/day 328 vs 113 (2.9x), 10/day 488 vs 217, 25/day 818 vs 502 (1.6x). The
  Hybrid advantage is largest at the tightest budget.
- **Fixed a real defect:** the "3. Daily event operations" lens hardcoded
  `daily_found@25` and rendered `0 vs 0` on the K=5 release. It now quotes whichever
  budget `daily_ks` publishes.
- **Anomaly-ranking tab is no longer tables-only.** `v9_dashboard_ui.UNSUP_AD_CHART_JS`
  holds the chart helpers (`buildUnsupervisedADChartModel`, `uadAxis`, `uadColumnChart`,
  `uadScatterChart`, `uadStrataBars`), injected alongside `UNSUP_AD_VIEW_MODEL_JS`. Arms
  are pinned to fixed palette slots (`#3987e5` / `#d95926` / `#199e70` / `#c98500`) —
  colour follows arm identity, never lineup position — validated for CVD separation and
  >=3:1 contrast against the dashboard's dark `--surface` (#131316).
- **Constraint on that tab's renderer:** `tests/..::_render_unsupervised_html` executes
  `UNSUP_AD_JS` in node against a stub `document` whose `getElementById` returns a bare
  `{innerHTML}` object. Any post-render DOM work must be capability-guarded the way
  `wireUnsupervisedADTooltips` is, or that test breaks.
- Verification pattern for dashboard visuals on this machine: build, then screenshot the
  generated `index.html` with headless Chrome. Old headless paints from the document
  origin and ignores `scrollTo`, so hide earlier sections with injected CSS and crop with
  Pillow rather than trying to scroll.

## Remaining release gates

- Run the complete affected source suite from the merged tree.
- Run V9dev end to end with disconnected cohort fixtures and a transient Gemma failure.
- Benchmark a real giant V9 component and record runtime, local explainer sizes, bounded factor/forward counts, peak memory, and disk estimate.
- Check available disk against the measured publication requirement.
- Run the full three-seed V9 K=5 comparison/observability generation and verify exact coverage, zero failures, validated narratives, complete as-of communities, hashes/pointers, and staging cleanup.
- Build and serve the dashboard; verify cohort switching, narratives/fusion, lazy complete evidence, pagination, responsive behavior, and browser console cleanliness.
- Update `docs/research/changes_3.md` only with newly measured K=5 results. Its existing daily-25 observability record is historical and must not be reused as the K=5 result.

## 2026-08-06: guided Overview and bootstrap interpretation

- The V9 Overview now leads with the operational result, then the relational
  mechanism and limits, followed by dataset/model inventory. Keep the V9
  positive-control framing distinct from the V8 honest track.
- The Daily bootstrap explanation must match `gnn.run_demo.paired_daily_bootstrap`:
  event rows are sampled with replacement, then ranked within each day under the
  same daily quota. Each replicate produces a Hybrid-minus-baseline event-hit
  gap; the 95% interval is the middle 95% of those gaps and is not a probability
  that the true gap lies inside it.
- Bootstrap verdicts count event hits, not unique-person recovery. The recovery
  explorer remains the unique-person readout. Dashboard source-contract tests
  cover the copy, pills, quota note, and preserved table behavior; no live
  browser visual pass was available in this environment.

## 2026-07-30: additive-only GNN architecture dashboard work

- The standalone multi-architecture GNN comparison must be added without
  removing, replacing, reordering, renaming, or changing any existing dashboard
  section, navigation entry, chart, table, interaction, accessibility behavior,
  artifact, or published result. Use independent artifact loading, element IDs,
  and rendering state, and regression-test preservation of the existing
  dashboard structure and order.

## 2026-07-30: recovery attribution presentation

- Recovery-case explanations expose a deterministic dashboard panel titled
  `Highest-attribution evidence`, derived directly from
  `explanation.attributions` rather than LLM prose. It shows at most three
  nodes and three connections with ranked unsigned median attribution weights,
  endpoint/type/edge identity, accessible proportional bars, and a non-causal
  salience caveat. The shared renderer supports schema-1 and schema-2 Hybrid-only
  cases; Baseline-only cases retain their explicit no-explanation policy.
- Producer ranks are used only when every valid record in a collection has a
  unique positive rank. Mixed or duplicate ranks fall back collection-wide to
  weight-descending, ID-stable ordering with sequential display ranks.
- The currently checked recovery artifact is older schema-1 data without raw
  attribution arrays. It intentionally renders the unavailable state until the
  completed Colab schema-2 artifact replaces
  `gnn/diagnostics/hybrid_recovery_explanations_v9.json` and the dashboard is
  rebuilt.

## 2026-08-01: additive GNN architecture bakeoff dashboard

- Standalone `.venv/bin/python -m gnn.gnn_architecture_bakeoff` resolved full-V9
  seeds `0/1/2`, 18 epochs, quarterly training bucket, global K
  `50/100/200/500/1000/2000/5000`, and daily K `5/10/25/50`. It produced
  `gnn/diagnostics/gnn_architecture_comparison_v9.json`; Baseline/Hybrid were not
  executed or output by this command.
- The validated artifact has five arms: GraphSAGE, full-graph RGCN, GAT attention,
  GIN, and KPI-AA approximation. At K=500, whole-pool / observable found-recall
  were respectively sage `143/0.0531`, `114/0.1610`; rgcn `144/0.0535`,
  `111/0.1568`; gat `80/0.0297`, `49/0.0692`; gin `23/0.0085`, `0/0.0000`;
  kpiaa `139/0.0517`, `106/0.1497`. At daily K=25, whole-pool
  found/precision/recall/F1 were sage `1124/0.1647/0.4177/0.2362`, rgcn
  `1129/0.1654/0.4195/0.2373`, gat `1106/0.1621/0.4110/0.2325`, gin
  `1077/0.1578/0.4002/0.2264`, and kpiaa `1104/0.1618/0.4103/0.2320`.
- Dashboard output independently validates/embeds the artifact under
  `v9GNNArchitectureComparison` and adds a GNN-only V9 Results section without
  changing existing sections/nav/data. Rebuilt outputs:
  `artifacts/v9/dashboard/data_v9.json` and `index.html`.
- Approximate observed runtime risk: on a 16GB Mac, the sequential run used about
  12 active CPU-hours; sleep/contention lengthened wall time. Future optimization
  should cache snapshots/checkpoints and use at most about two workers. The affected
  suite (`tests/test_gnn_architecture_bakeoff.py`, `tests/test_run_demo_smoke.py`,
  `tests/test_df_graphmodel_rgcn.py`, `tests/test_v9_dashboard_builder.py`)
  completed **203 passed, 327 warnings in 436.46s (0:07:16)**; warnings are existing
  Python 3.14/PyTorch/PyG/timezone/joblib warnings. `git diff --check` and
  `py_compile` for the four affected Python modules passed. Dashboard rebuild,
  generated-JavaScript syntax, and desktop/narrow headless Chrome checks passed.
  In-app browser was unavailable and direct console capture timed out, so console
  cleanliness is unclaimed.

## 2026-08-01: V9 Results live-demo order

- The V9 Results surface is ordered as readout, operations, evidence, confidence,
  then methods. The three-lens orientation follows the headline; depth recall,
  daily capacity, cumulative simulated unique-person catches, and daily crossing
  context stay together; recovery evidence and bootstrap follow; model notes,
  the GNN architecture comparison, and run metrics form the methods tail.
- Model notes use the stable `Base Models`, `Hybrid Models`, `GNN Models` order.
  This is presentation-only. Published values, as-of semantics, data contracts,
  and interactions remain unchanged. The affected suite completed 307 passed and
  the rebuilt dashboard was visually checked with headless Chrome.

## 2026-08-01: daily-only GNN dashboard metrics

- The release dashboard now exposes daily operating budgets only: K=5, 10, and
  25 inspections per day. Global K/depth and population controls were removed
  from the V9 Results and GNN architecture surfaces; legacy K=50 values in the
  architecture artifact are filtered out of the rendered view.
- Daily capacity tables now show Found, Precision, Recall, and F1 for each
  published budget. `gnn.run_demo.DAILY_KS` is `(5, 10, 25)`, so future demo
  and architecture-bakeoff outputs use the same contract.
- The refreshed V9 demo reused frozen checkpoint
  `17d5ee9fe23234ab33b0ba33e36800ab21bd25101b32ff51bb787b259e4f3c52`; no GNN
  retraining was needed. Existing K=5 values were preserved while K=10/K=25
  daily metrics and paired-bootstrap summaries were added to the published
  artifact. The rebuilt dashboard lives under `artifacts/v9/dashboard/`.
- The architecture comparison now leads with three aligned F1 bar-chart panels
  for K=5/10/25. Bar length uses one shared scale; the tabular baseline is gray,
  GNN architectures are blue, and an off-screen accessible table preserves
  Found, Budget, Precision, Recall, and F1 details for each panel.
- The redundant V9 Results metrics/settings card (pool counts, outcome rate,
  fusion weight, and GNN run settings) was removed from the presentation layer;
  those values remain in the published JSON for provenance.

## 2026-08-02: schema-3 balanced explainability producer review and repair

- The schema-3 producer and downstream bundle/dashboard work live uncommitted
  on `feature/v9-balanced-explainability` (superpowers worktree). Tasks 1-7 are
  implemented; Task 8 (full regeneration and result-specific docs) remains
  pending because no full V9 generation has been run. Per-case resume state is
  still deferred.
- Durable decisions made while repairing the producer:
  - The Hybrid detail budget is a single frozen budget of `hybrid_detail_limit`.
    Eligible candidates fill it with GNNExplainer evidence; any remaining slots
    are filled deterministically with community-only structural fallbacks for
    preflight-ineligible (oversized) candidates. Both selections are frozen
    before any explanation work, so this is not post-failure replacement.
    Candidates beyond the budget stay `not_selected` with
    `selection_reason="ineligible_preflight"` and claim no evidence.
  - `community_index` may therefore contain `hybrid_only` case IDs. The
    deferred schema-3 sidecar validator must not assume it is baseline-only.
  - Coverage shortfall is measured against the requested limits, never against
    the clamped candidate pool, and a nonzero shortfall must carry a reason.
  - The run fingerprint is cross-checked against the published selection,
    preflight, policy, and limits. Recomputing the token alone only proves the
    material is self-consistent.
  - The structural-community compatibility shim is gated on
    `explanation_engine.schema3_test_adapter is True`; production extraction
    errors surface as failed cases instead of degraded evidence.
  - Baseline controls must measure zero explainer work in the benchmark rather
    than assert it. `_baseline_explainer_monitor` hooks the model encoder and
    the explainer entry points and raises on any nonzero count.
- Known, unaddressed: the fingerprint material stores the full selection policy
  twice in addition to `artifact["selection"]`, so the per-candidate preflight
  map is triplicated in the artifact. This remains a fingerprint-contract
  compatibility tradeoff, not a correctness failure.
- The schema-3 sidecar validator accepts Hybrid structural-fallback case IDs,
  schema-3 sidecars are packaged atomically with lazy case/community refs, and
  the dashboard has a schema-specific view model/mount that keeps technical
  Hybrid detail separate from structural-only controls. Explicit schema-3
  bundle refs are verified before publication, and explainer limits are sourced
  from `sage_explainer` constants.
- Verified green in the focused environment: 771 tests across schema-3,
  recovery-observability, recovery-bundle, benchmark, sage-explainer, dashboard
  builder, and recovery UI suites. No full V9 generation has been run, so no
  coverage numbers are published yet.
  No full V9 generation has been run, so no coverage numbers are published yet.

## 2026-08-02: schema-3 producer audit — snapshot lifecycle, staging, resume

Independent review of the schema-3 work above. The five repairs it claims
(fingerprint cross-binding, oversized-Hybrid structural fallback, test-only
adapter gating, shortfall-vs-requested, measured Baseline explainer counts)
were verified present and correct in the code, not just asserted.

Three defects remained, all in the producer-to-bundle seam:

- **Unbounded day snapshots (the reason no full V9 run finished).**
  `_build_schema3_artifact` never called `release_snapshot`, unlike the
  schema-2 `run_pass`. Preflight measures the exact two-hop input for every
  Hybrid candidate, so the engine cached one `DaySnapshot` per candidate
  scoring day with no eviction — reintroducing the exit-137 OOM that per-day
  release had already resolved at ~5.2 GiB peak. Preflight now walks candidates
  in scoring-day order and releases each day after its group; the detail
  phases release per case. `generation_diagnostics.snapshot_cache_peak_days`
  records the high-water mark, and `release_snapshot` is now a required
  engine capability for schema 3 exactly as it is for schema 2.
- **`finalize_schema3` was dead code.** `build_observability_bundle`'s schema-3
  branch ignored `staging_root`, `final_root`, and `writer_factory` and
  returned a monolithic in-memory artifact. That path also routes communities
  through `_store_community`, whose legacy 10,000-record bound is smaller than
  real V9 communities (the giant benchmark measured a 6,952-node Hybrid
  community), so large cases would have failed. `_build_schema3_bundle` now
  stages through `RecoveryBundleWriter`, streams communities, and publishes via
  `finalize_schema3`. The published manifest is verified end to end against the
  real `publish_prepackaged_schema3_manifest`, not a stub.
- **Per-case resume state was never persisted.** Selected cases now claim a
  checkpointed attempt slot before any work (`first_pass`, then
  `deferred_retry` on resume) and completed cases are served from their staged
  sidecar, so an interrupted run never re-runs GNNExplainer or Gemma for
  evidence it already published. Staged narrative outcomes are replayed into
  the coverage counters so a resumed run does not report zero narratives.

Durable decisions:

- `build_observability_artifact(schema_version="3.0")` stays the in-memory
  fixture path (no writer, inline communities). `build_observability_bundle`
  is the production path and always stages. Do not merge them.
- The staging identity folds in the schema version and the 20/10 limits, so a
  run with different limits can never resume into another run's bundle.
- Resume applies only to an interrupted run. A successful `finalize_schema3`
  moves staging into the published bundle and deletes it; re-running then
  reproduces the same bundle ID idempotently.
- `python -m gnn.run_demo observability <checkpoint>` is the entry point for
  schema-3 generation and defaults to `3.0` with 20/10. The library defaults
  stay at `2.0` for legacy callers.

Still open: Task 8 (full regeneration, dashboard rebuild, and the
`changes_3.md` coverage entry) has not been run.

## 2026-08-02: clean schema-3 Colab handoff

- The runnable handoff is `/Users/edward/Desktop/v9_observability_colab_schema3/`,
  separate from the legacy `/Users/edward/Desktop/v9_observability_colab/`
  schema-2 package. It contains the fixed source, full V9 corpus, verified
  three-seed checkpoint `17d5ee9f…`, a local-scratch runner, and a Colab
  notebook that exports only after final schema-3 validation.
- The handoff was validated from its own package import path: 268 focused
  schema-3/recovery tests passed, Python compilation passed, runner `--help`
  passed, and notebook JSON parsed. The package is about 1.4 GB and includes
  40 corpus files plus the three model weights.
- A full local generation was started after the anchor-day fix but stopped
  before publication when this 16 GiB Mac reached roughly 7 GiB resident plus
  2.8 GiB swap. The Colab run should use high-RAM GPU, local `/content`
  scratch, one Ollama model instance, and Drive only for the final export.

## 2026-08-02: Task 6 schema-3 dashboard evidence renderers

The schema-3 mount previously rendered ranks, a status line, narrative text, a
factor count, and a 25-item node list. It now reuses the real evidence
renderers and drives the lazy sidecar pipeline end to end.

- `mountRecoveryExplorerV3` loads the community's node and edge chunks,
  resolves them through the normalized catalog, and merges the day-view status
  and membership chunks, so `x`/`y`, `pooled_member`, `caught_before_snapshot`,
  and `message_hop` reach the renderer. The catalog/day-view resolution was
  extracted from the schema-2 mount into `recoveryResolveCatalogRows` and
  `recoveryApplyDayView` and is now shared by both.
- Hybrid detail renders counterfactual factors, restart stability, edge-removal
  faithfulness, the grounded narrative, the highest-attribution panel, and the
  staged community graph, behind the strict as-of evidence-boundary gate.
- Baseline controls render the same graph-stage controls with neutral emphasis
  and no attribution or factor panels.
- Filters cover `all`, the three cohorts, `gnn_explanation`,
  `community_control`, and `all_detail`; unselected and failed cases stay in
  the list.

Durable decisions and deviations from the written plan:

- **The plan's "exact copy" for a control uses an em dash, which the repo
  bans.** `tests/test_v9_recovery_explainer_ui.py` asserts no em/en dash exists
  anywhere in the explainer JS or CSS, and `recoveryVisibleText` strips them at
  render time. The copy is therefore
  `Community context only: GNNExplainer was not run for this baseline control.`
- **Baseline controls carry `structural_stages`, not `flow_stages`.**
  `build_structural_community_control` is guarded by a test that forbids the
  substring `rank` anywhere in a control payload, and the Hybrid `rank_fusion`
  stage has no meaning for a control. Controls therefore expose three
  structural stages and `buildStructuralDrawCommands` rejects `rank_fusion`.
- **A stability/faithfulness panel had to be written, not reused.** The plan
  said to reuse existing panels, but no renderer had ever surfaced
  `explanation.stability` or `explanation.faithfulness`, even though the
  producer has always emitted both. The panel reports the top-edge probability
  drop against its matched random control and reports an unmatched control as
  `not measured` rather than imputing one.
- **Per-factor provenance expansion is not overlaid on the schema-3 graph.**
  Schema 3 publishes attribution overlay as a separate chunked sidecar owner,
  so the community's `provenance_expansions` is empty. The factor panel says so
  instead of silently drawing nothing.
- **Canvas is bounded at 1500 nodes / 4000 edges.** Above that the paged data
  table is the only representation, and it states why. The table renders in
  every case as the non-canvas accessibility fallback.

## 2026-08-02: schema-3 integrity follow-up

- Schema-3 detail construction rejects any evidence boundary whose snapshot or
  strict-before rules do not match the case scoring day, before evidence
  panels render. Summary records must carry the published baseline, GNN, and
  percentile-fusion score fields with their declared semantics.
- Catalog resolution and day-view joins fail closed on missing, mismatched, or
  duplicate identities. Both the staged writer and prepackaged publisher
  verify day-view identity alignment; the browser cache key includes the
  expected chunk hash.
- Hybrid structural-fallback copy and canvas aria labels identify the case as
  Hybrid fallback rather than calling it a baseline control.

## 2026-08-02: final Colab handoff verification

- `/Users/edward/Desktop/v9_observability_colab_schema3/` now matches the
  current feature-worktree `gnn/` source exactly, including resume-path as-of
  re-validation and cached-community chunk offset/count/identity checks.
- Verified locally: checkpoint closure plus all 30 corpus CSV fingerprints;
  484 producer/recovery/bundle/explainer tests; 303 downstream dashboard/UI
  tests; Python compilation; valid nbformat 4.5 with 11 uniquely identified
  cells; and a real manifest-plus-sidecar export accepted by
  `publish_prepackaged_schema3_manifest`.
- The notebook's exact Ollama acquisition, list-verification, and HTTP
  generation-smoke cells were executed locally with `gemma4:12b`; the model
  returned `ready`. The acquisition cell skips a registry pull when an exact
  imported/private tag is already present, while later verification remains
  mandatory.
- The live Colab run remains the only environment-specific check: use
  high-RAM local `/content` scratch and Drive only for the final export pair.
  Do not publish the JSON without its sibling `recovery/` tree.

## 2026-08-03: Colab Ollama bootstrap and cold-start behavior

- Stock Colab can lack `zstd`, which causes the Ollama installer to fail
  before installing the CLI. The notebook bootstrap now installs `zstd` with
  `apt-get` when absent and verifies the resulting CLI is usable.
- A 12B CPU model may take longer than two minutes to produce its first visible
  response even when `ollama list` shows the exact tag. The smoke request uses
  deterministic settings, a small 64-token output cap, `keep_alive`, and a
  10-minute socket timeout. Do not interpret a two-minute timeout as proof the
  model tag is broken.

## 2026-08-03: Colab Drive path with spaces

- The user uploaded the package under `MyDrive/Colab Notebooks/`. The old
  notebook used unquoted shell `cp` arguments, so the space split the source
  path and left `/content/v9_observability_colab_schema3` absent; later cells
  still ran because shell-magics did not raise. The notebook now auto-detects
  both `MyDrive/` and `MyDrive/Colab Notebooks/`, copies with `shutil.copytree`,
  installs requirements with `check=True`, and runs the producer with
  `check=True`. A missing package now fails at setup instead of spending time
  on Ollama and failing only at the producer cell.
- After the path fix, the producer itself returned exit code 1 while the
  notebook only surfaced a generic `CalledProcessError`. The run cell now
  streams producer output, writes `/content/v9_schema3_run/producer.log`, and
  copies that log to the Drive export directory on both success and failure.
  A future producer failure must be diagnosed from that log rather than from
  the notebook wrapper traceback.

## 2026-08-04: schema-3 ZIP-backed dashboard build

- `build_v9_dashboard.py` accepts `V9_SCHEMA3_RESULTS_ZIP` and falls back to a
  repo-root `v9_schema3_results.zip` when the JSON diagnostic is absent. The
  ZIP publisher requires the exact `v9_schema3_results/` prefix, rejects unsafe,
  duplicate, and symlink members, verifies the canonical nested bundle
  manifest and every referenced hash/byte count, then streams verified members
  into the staged dashboard output.
- The supplied bundle `3df66ce7d0e5a791345797e7` built successfully with
  schema-3 partial coverage: 19/20 Hybrid technical explanations and 10/10
  Baseline community controls, with one recorded shortfall. The generated
  recovery tree is large (about 4.7 GB) because it preserves the lazy graph,
  catalog, provenance, and attribution sidecars; do not replace it with the
  summary manifest alone.

## 2026-08-04: schema-3 explanation graph presentation

- The schema-3 recovery explorer intentionally exposes only published
  `gnn_explanation` records in its visible case list. Baseline/community-control
  records remain in the validated manifest for provenance and summary algebra,
  but are not selectable in this view.
- Explanation attribution is loaded from verified overlay sidecars and merged
  into a presentation-only model. The complete as-of community remains the
  authoritative table; the canvas uses a deterministic 1500-node/4000-edge
  slice that retains the target and evidence endpoints, and fails closed if
  mandatory evidence itself cannot fit the bound.
- Context relations are muted while attributed edges use a single accent whose
  width/brightness follows unsigned explainer median. This is presentation
  salience, not a causal claim. The generated dashboard was rebuilt from the
  supplied schema-3 ZIP and verified over HTTP for the index, data, recovery
  pointer, manifest, case, community, and both overlay sidecars.
- Overlay chunks intentionally mix weighted attribution rows with neutral
  structural-provenance rows. The renderer must skip rows containing neither
  `explainer_median` nor `rank` before attribution membership checks; a row
  containing either field remains an attribution candidate and must pass the
  complete weight, rank, identity, and base-community contract.

## 2026-08-05: explanation dashboard readability pass

- The tracked recovery UI now uses one presentation-only numeric formatter with
  a maximum of three fractional digits, including nested legacy JSON panels;
  artifact values remain full precision.
- Both the schema-3 and legacy recovery paths use a narrative-first selected
  case view, explicit Baseline / Seed-0 GNN / Seed-0 Hybrid ranks, and a plain-
  language baseline-to-Hybrid movement. This is display hierarchy only; filters,
  lazy sidecars, graph bounds, evidence contracts, and as-of semantics remain
  unchanged.
- `DESIGN.md` is the Stitch-ready visual source of truth: Outfit prose,
  JetBrains Mono technical values, zinc/charcoal neutrals, green interaction
  accent, semantic evidence colors, and no decorative glow/precision sprawl.

## 2026-08-05: GNN explanation workspace hierarchy

- The schema-3 explanation view is graph-first: selected case and ranks lead, the graph is the primary surface, narrative/factors follow, and dense technical evidence is closed by default.
- The published-artifact, strict as-of, explained-only eligibility, and graph/table contracts remain unchanged; future UI work should preserve this boundary.

## 2026-08-05: schema-3 recovery and V9 Results contract

- The active recovery dashboard contract is schema-3-only. Top-level schema-1/2
  UI and packaging compatibility is removed; shared schema-3 evidence helpers
  remain.
- The main GNN explainability case list/default contains only canonical,
  available `gnn_explanation` records with validated `detail_index` membership.
  The full cohort summary remains available.
- V9 Results order is Daily Crossing Volume, Daily capacity, then Simulated
  catches. The crossing selector defaults to 10/day; capacity shows Baseline and
  Deployable Hybrid only. GNN remains in the combined chart/headline and other
  relevant views.
- Simulated-catch view/model/accessibility behavior and every source JSON/ZIP
  artifact, data schema, and metric remain unchanged. Legacy anomaly fields may
  remain in source artifacts but are no longer rendered. No new measured results.

## 2026-08-06: evidence-first explanation graph

- Keep the explanation graph evidence-first at the first hop: relationship
  identity is encoded by stroke color/pattern while unsigned model evidence
  weight is a separate gold underlay; grouped controls and direct labels must
  preserve those distinct semantics.
- If strict narrative validation rejects or lacks prose and ranked attribution
  is available, render the deterministic highest-attribution evidence in the
  Grounded narrative panel once, omitting only the duplicate attribution
  disclosure; otherwise the inline panel shows an explicit
  attribution-unavailable state. Preserve model outputs, sidecars, strict
  as-of behavior, graph limits, and complete tables.

## 2026-08-06: Overview dataset and model snapshot

- The V9 Overview now reads the existing embedded `meta`, `overview`, and
  `v9Demo` payloads through a validated client-side snapshot view model.
- It exposes corpus-wide totals (nodes, heterogeneous edges, events, and
  communities), compact typed node/edge counts, and the deployable HGB
  tabular baseline versus Baseline + GraphSAGE rank-fusion Hybrid setup.
- Total heterogeneous edges must remain labeled as corpus edges, not as the
  person-graph edge count. Malformed or missing metadata renders unavailable
  states and never invents values; model evaluation artifacts and metrics are
  unchanged.
- Do not surface legacy whole-pool `found@K` ranking depth in Overview. V9's
  operational comparison is the daily inspection-budget view rendered in V9
  Results (`overall_daily`); global `found@K` values are not interchangeable
  with inspections per day.

## 2026-08-06: explanation graph render seam and canvas legibility

- Graph control changes (view, stage, relationship, labels, search, zoom) must
  NOT re-render the whole recovery section. `renderGraphOnly` rebuilds just the
  `.v9-recovery-graph-panel` (plus the tables disclosure body, whose Emphasized
  column is stage-dependent); zoom/label-density repaint the live canvas via
  `canvasCleanup.draw`, and search swaps draw commands via
  `canvasCleanup.setCommands` so the input keeps focus and caret. Measured:
  ~1078 ms per stage click before, 13-67 ms after; "Full community" previously
  blocked the renderer for tens of seconds.
- Every re-render path must pair `focus({preventScroll:true})` with the
  `measureAnchor`/`restoreAnchor` pin. GOTCHA: do not feature-detect
  preventScroll via `control.focus.length` - Chrome's native `focus.length` is
  0, so that guard silently takes the scrolling path and the page still jumps.
  Always pass the options object; engines without support ignore it.
- Canvas legibility rules that the published sidecar layout forces:
  x/y coordinates frequently put three or more members on one line, so edges
  are drawn as deterministic quadratic arcs (`recoveryEdgeCurveOffset`, keyed
  by a stable hash of edge id) rather than straight lines. Do not relayout
  published coordinates to fix this.
- Evidence weight is normalized against the strongest attributed edge that is
  actually on screen (`recoveryEvidenceScale`); absolute-only scaling saturates
  every edge in gold whenever a case attributes most of its edges at high
  weight. The evidence channel is a gold halo (shadowBlur), not a flat band
  under the relationship stroke - a band shows through dashed strokes and
  collapses both channels into one muddy colour.
- Node labels are placed by priority with collision rejection
  (`recoveryNodeLabelPriority`); sampled communities otherwise emit hundreds of
  overlapping labels. GOTCHA: the label box must clear the node's own marker
  box (`recoveryNodeLabelBox` starts at radius+7, marker box ends at radius+5)
  or every collision-checked label rejects itself and only the target is
  labeled.
- Pre-existing, untouched: `tests/test_recovery_layout_parity.py` fails to
  import (`DISPLAY_LAYOUT_RADIUS` missing from `gnn.sage_explainer`), and the
  screen-reader-only `.gnn-chart-data` tables overflow the page horizontally.

## 2026-08-06: hop-ring layout restored (was lost in merge 8f00e43)

- Published community `x`/`y` in the chunked schema-3 sidecars come from
  `iter_nodes`, which indexes members into a sqrt(N) grid in **sorted node_id
  order**. Position therefore encoded alphabetical rank and nothing else, and
  every edge was a line between two unrelated cells. Measured on the 35,791-node
  community for `P00031774`: x spacing exactly 1/190, y spacing exactly 1/189.
- `buildRecoveryGraphSlice` fills its context quota in the *same* sorted-id
  order, so the drawn context was an alphabetical prefix that landed in the
  first 8 of 189 grid rows — the horizontal band at the top of the canvas. Its
  hop mix matched the whole community's, i.e. it carried no structure.
- `display_hop_ring_layout` / `recoveryHopRingLayout` already existed with a
  bit-exact parity test and were dropped by merge `8f00e43`, which kept
  `tests/test_recovery_layout_parity.py` while taking the other parent's copy of
  both implementation files. Restored from `fec6b5d`; that suite now passes
  (19 tests) for the first time.
- The UI recomputes the rings client-side, so **already-published bundles read
  structurally with no regeneration**. This depends on `message_distance` being
  present in the day-view node rows and on `assembleRecoverySchema3Community`
  passing `nodes: nodeRows` through untouched.
- GOTCHA: lay out over the bounded drawable projection (`slice.nodes`), not
  `community.nodes` and not `slice.tableNodes` (the complete row set). Ring
  radius is `DISPLAY_LAYOUT_RADIUS*ring/(maxRing+0.5)`, so a wrongly scoped
  layout sizes the rings for members that are never drawn and squeezes the drawn
  ones into an inner sliver. Pinned by
  `test_layout_is_scoped_to_the_drawn_projection_not_the_whole_community`.
- Result on the real drawn projection (1,500 nodes of 35,791): vertical spread
  26.5% -> 87.4% of the canvas, radius now encodes hop (hop 1 at 0.184-0.253,
  hop 2 at 0.368-0.437), target dead centre, all 1,500 positions distinct.
- Not re-verified in a browser: the Chrome extension stopped responding after
  the rebuild. Rendering correctness is covered by tests and by numeric checks
  against the published bundle, but the on-screen result is unconfirmed, as is
  whether the hashed edge arcs are still worth keeping now that positions carry
  structure.

## 2026-08-06: recovery explainer factor readability

- `canonical_pair_group_id` may already begin with `pair:`. Factor generation
  must preserve that prefix rather than emitting `pair:pair:...`.
- Recovery factor rows should resolve technical pair IDs to relation plus
  endpoints when the community edge is available; schema-3 published edge
  catalog records expose the pair ID through `edge_id`, not necessarily through
  `canonical_pair_group_id`. Retain the full factor ID only as technical
  metadata/title text.
- Explain `unstable` as variation across deterministic explainer restarts. A
  stable factor requires positive rank effect, selection frequency at least
  2/3, and restart IQR at most 0.25. The absence of a stable factor does not
  mean the measured effect is zero.
- Highest-attribution evidence displays up to the top five nodes and top five
  connections. The displayed weights are normalized unsigned median salience
  weights across restarts, not probabilities or causal effects; direction comes
  from the separate counterfactual rank effect.
- The published 19-case bundle contains factors and attribution rows for all
  19 hybrid explanations. Its narrative payloads use prompt version `v4`,
  while the old UI narrative validator only accepted `v1`, so the narrative
  fallback appeared even though explanation evidence existed. The visible
  GNN explanation path now shows highest-attribution evidence directly and
  does not render the narrative panel.
- Factor cards keep measured counterfactual rank effect separate from restart
  support. The effect is `ablated_hybrid_rank - original_hybrid_rank`; restart
  support describes whether the explainer selected the factor consistently
  across deterministic restarts. A case can therefore show a large measured
  effect even when no factor is consistently selected.
- Published recovery narratives are LLM outputs from local Gemma
  `gemma4:12b` with prompt version `v4`; the schema-3 UI now accepts that
  provenance and renders the validated summary and claims in an `LLM
  explanation` panel above attribution and factor evidence. Keep the
  deterministic-template `v1` path for fixtures/fallback artifacts.
- The client narrative source-reference allowlist must mirror the producer's
  v4 `attributions.*`, `component_pooling.*`, and `rank_fusion.*` claim paths;
  rejecting those paths makes valid published LLM output appear unavailable.
- Visible counterfactual factor cards omit factors whose ablation leaves the
  published Hybrid rank unchanged. Positive and countervailing non-zero rank
  effects remain visible; restart consistency remains a separate signal.

## 2026-08-06: stacked recovery explanation panels

- The schema-3 GNN explanation row now uses a single full-width CSS grid column.
  Its DOM order is Highest-attribution evidence, Key counterfactual factors,
  then the LLM explanation, so visual and keyboard reading order match. The
  structural-only fallback remains unchanged. Focused UI and dashboard-builder
  tests pass (361 total), and the generated V9 dashboard was rebuilt.

## 2026-08-06: repository organization and artifact policy

- The active runtime is V9-first. The full V9 corpus lives inside the
  `reproducibility/v9_observability_colab_schema3/` handoff; V9dev lives under
  `tests/fixtures/v9dev/`.
- Schema-3 evidence is one SHA-256-verified Git LFS ZIP at
  `artifacts/v9/explanations/v9_schema3_results.zip`. Extracted explanation
  trees are generated and ignored.
- The root `gnn/` directory is the flat active implementation. The bundled
  `reproducibility/v9_observability_colab_schema3/gnn/` copy is an intentional
  reproducibility snapshot.
- Documentation changes preserve the as-of and leakage semantics and are
  verified separately from functional model/evaluation changes.
- At final HEAD, the root suite recorded 1,329 passed, 1 skipped, 2,971
  warnings, and 1,079.59 seconds; the skip is the opt-in local Gemma/Ollama
  integration requiring `RUN_OLLAMA_INTEGRATION=1`.
- Active and bundled documentation-only proof found executable AST equivalence
  across 21 active GNN Python files and 20 bundled GNN Python files; semantic
  and comparator tests passed, and final independent review approved with no
  findings.
- Bundled schema-3 package verification recorded 72 passed plus 9 subtests,
  with 2 warnings.
- Both validators passed all hard checks with zero observability mismatches.
  Full V9 has 78,613 person associations, 120,000 household edges, 800 orgs /
  5,043 members / 507 dark, and 21,469 true-smuggling / 8,013 seized /
  13,456 undetected. V9dev has 1,437 associations, 2,000 household edges,
  14 orgs / 83 members / 9 dark, and 421 true-smuggling / 159 seized /
  262 undetected.
- Git LFS verification found 76 hydrated tracked paths, 75 unique objects, and
  2,816,876,814 bytes; `fsck` was OK, no regular HEAD blob exceeded 100 MiB,
  and all seven paper copies were byte-identical to their originals.
- The explanation archive is
  `artifacts/v9/explanations/v9_schema3_results.zip`, SHA-256
  `54064788c0cd92893296d1db926aaa902604e30db16fdc3151545413a30008fd`, with
  64,964 members. Known limitation: 19 exact Hybrid explanations of 20
  selected, one failed case, and coverage gate false.
- Dashboard verification successfully built 64,703 nonempty generated files;
  `index.html` was 11,838,659 bytes, `data_v9.json` was 11,118,116 bytes, the
  schema 3.0 bundle was `3df66ce7d0e5a791345797e7`, and 30 attempts / 29
  succeeded. Results were 113 baseline recovered / 325 Hybrid total / net
  gain 212. The generated dashboard was removed after verification. Optional
  missing diagnostics leave some tabs sparse; this is the residual
  operational caveat.
- No V8 corpus or data is present; seven papers remain. The upload target and
  remote branch name is `feature/repository-reorganization`; origin SSH
  reachability was confirmed, but this is not a claim that it is pushed.
- `tasks/` was intentionally removed at the user's request after implementation;
  current onboarding is in `README.md` and active `docs/`, while immutable
  historical records may retain older `tasks/` references.
- The main fallback remains untouched and is not implied to be merged.

## 2026-08-08: generated dashboard snapshot policy

- `artifacts/v9/dashboard/index.html` is the committed Git LFS-backed HTML
  snapshot and must be refreshed only by
  `python -m scripts.dashboard.build_v9_dashboard` from the organized branch.
- All other files under `artifacts/v9/dashboard/`, including `data_v9.json`,
  recovery sidecars, and generated subdirectories, remain ignored and local-only
  for serving the snapshot.
- The published V9 Results release contract is daily budgets 5/10/25 and
  depends on the committed normal-Git diagnostic
  `gnn/diagnostics/demo_comparison_v9.json` with SHA-256
  `a43d2b63ea43058d503ce0c3043636462b6564b1ee97fa06f3ad2567b5604066`.
  Never rebuild or version release HTML from the canonical-corpus K=5 fallback;
  verify this diagnostic hash and the embedded `[5, 10, 25]` contract first.

## 2026-08-12: current RGCN release evidence boundary

- GraphSAGE remains the active V9 runtime default. Current RGCN measurements
  come from the 40,578-row `gnn_architecture_comparison_v9.json` artifact,
  SHA-256 `d4b5d349532ca949f11a3c1df59f27b4323189e06ae6099d7310dac3fc7ad35a`;
  it is frozen-artifact verifiable, not exactly retrainable, because no RGCN
  checkpoint or score arrays survive.
- Baseline/RGCN is cross-artifact sharing only the tested logical corpus,
  oracle substrate, pool/hidden counts, strata, seeds, epochs, and bucket.
  The older 38,948-row table is historical and unrecoverable; its significance
  must not transfer to the current release.
- Dashboard legacy identity is accepted only for the exact pinned digest;
  re-encoding is rejected. Active and bundled trees have 11 AST-identical core
  modules, nine divergences pinned on both sides by normalized AST SHA, and
  active-only `paths.py`. The old “documentation-only proof” phrase refers
  only to within-tree preservation and is not evidence of cross-tree equality;
  the historical entry remains unchanged.
- The regenerated dashboard index embeds the artifact and has SHA-256
  `bb61a1ddb22f2ed908677ac0c851893167aae67917895707878ba6aa0f46d4b5`.
  The known 19/20 exact Hybrid-explanation limitation remains.
