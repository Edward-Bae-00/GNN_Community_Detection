# Project Memory

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
  nav. Fixed in `Documents/Data/scripts/build_v9_dashboard.py` with marker-independent
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
- Update `Documents/Data/changes_3.md` only with newly measured K=5 results. Its existing daily-25 observability record is historical and must not be reused as the K=5 result.

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
  `Documents/Data/v9_dashboard/data_v9.json` and `index.html`.
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
  artifact. The rebuilt dashboard lives under `Documents/Data/v9_dashboard/`.
- The architecture comparison now leads with three aligned F1 bar-chart panels
  for K=5/10/25. Bar length uses one shared scale; the tabular baseline is gray,
  GNN architectures are blue, and an off-screen accessible table preserves
  Found, Budget, Precision, Recall, and F1 details for each panel.
- The redundant V9 Results metrics/settings card (pool counts, outcome rate,
  fusion weight, and GNN run settings) was removed from the presentation layer;
  those values remain in the published JSON for provenance.

## 2026-08-03: explainer ceiling raised to 512/1024 and the graph got a real layout

- `MAX_LOCAL_EXPLANATION_NODES` / `_EDGES` moved from 128/256 to **512/1024** here
  and in the schema-3 producer package at
  `~/Desktop/v9_observability_colab_schema3` (`MAX_EXPLAINER_INPUT_NODES/EDGES`,
  which the display bounds are defined from). The two copies must move together:
  the producer writes the display projection at its ceiling and this repo reads
  it back, so a lower bound here would silently mean "top among displayed
  records" rather than top in the explanation. The driver was the exact-20
  coverage gate, which needs >= 20 candidates to pass explainer preflight; at
  128/256 only 10 of 268 did.
- 512/1024 was chosen from the **display** side, not from measured candidate
  sizes. Past roughly 1024 nodes the community canvas stops being interpretable,
  and because selection freezes 20 cases with no post-failure replacement, a
  bigger ceiling admits large graphs that can then be *selected* and time out.
- **`CommunityScope.iter_nodes` never had a layout.** It placed nodes on a
  `sqrt(N)` grid in sorted `node_id` order -- position encoded alphabetical rank,
  so every edge was a line between two unrelated cells -- and the grid was sized
  from the whole community while only the bounded projection is drawn.
  `display_hop_ring_layout` replaces it for the projection: target centred, one
  ring per `message_distance`, each ring ordered so a node sits in the arc of its
  lowest-id neighbour one ring in. Rings over 120 nodes spread across up to 4
  concentric sub-rings; 480 hop-2 nodes on a single circle render as a solid
  band. `iter_nodes` keeps its grid because it must stay a whole-community stream
  for the chunked sidecars.
- The layout exists **three** times: Python in `gnn/sage_explainer.py`, a
  byte-identical copy in the producer package, and a JS port
  (`recoveryHopRingLayout`) in `Documents/Data/scripts/v9_recovery_explainer_ui.py`.
  The UI recomputes rather than trusting payload `x`/`y` so artifacts published
  before this change still render structurally, falling back to payload
  coordinates only when `message_distance` is missing.
  `tests/test_recovery_layout_parity.py` fails if they drift -- verified by
  unlinking the JS radius constant and watching 5 tests fail, then reverting.
- Recovery graph panel additions, all in the UI script: importance-ordered edge
  drawing, viewport culling, density-scaled ink and node radii, a strided auto
  label budget (taking the first N crowded every label onto one arc), hover
  tooltip, click-to-focus neighbourhood dimming, a node/relation legend, a
  "N nodes / M edges drawn" readout that flags when the display bound was hit,
  and a responsive `clamp()` canvas height replacing the fixed 410px.
- Verified with the headless-Chrome pattern above against a synthetic 513-node /
  1024-edge community. Suites: this repo 978 passed / 1 skipped; producer package
  62 passed. NOTE: run this repo's tests as `.venv/bin/python -m pytest`;
  `.venv/bin/pytest` leaves the repo off `sys.path` and 16 dashboard-builder
  tests fail with `ModuleNotFoundError: No module named 'gnn'`.

## 2026-08-03: Overview tab was rendering twice on every load

- `_rewrite_nav_js` (build_v9_dashboard.py) swaps the template's flat tab binding
  for delegated hash routing ending in
  `(function(){const n=_tabFromHash();_navigateTo(n||'overview');})();`. The
  template's own trailing `Tabs.overview.render();Tabs.overview.rendered=true;`
  was left in place one line below. `switchTab` guards on `Tabs[name].rendered`,
  that trailing call does not, and the tab renderers (`makeMetrics`,
  `makeSection`) APPEND to the tab element rather than replacing its contents.
  Net effect: every visitor landed on an Overview carrying two metric rows, two
  Outcome Funnels, and two of each bar chart. `_rewrite_nav_js` now strips the
  redundant bootstrap; the routed IIFE owns the initial render for every entry
  point including deep links like `#seizures`.
- Removal is tolerant, not strict. The minimal template fixture in
  test_v9_dashboard_builder.py has the nav binding but no overview bootstrap, so
  raising on absence breaks two builder tests. Nothing to de-duplicate is not an
  error.
- Guarded by
  `test_generated_dashboard_renders_the_overview_tab_exactly_once`. That test
  reads the BUILT `Documents/Data/v9_dashboard/index.html`, so
  `build_v9_dashboard.py` must be re-run before it reflects a source change.
- **Do not "fix" the Overview bar-chart palette.** The multi-hue bars look like a
  one-accent-rule violation but `C.node` in the base template is a semantic map
  (person emerald, event blue, document purple, vehicle orange, location sky,
  business rose) shared with the network canvas and Community Explorer.
  Recolouring the bars to a single hue would break the encoding. The
  all-emerald EDGE TYPES chart next to it is correct for the same reason: edge
  types have no per-type colour.
- `—` as a null-value placeholder in explorer data rows is a deliberate data-UI
  convention and stays. Only prose em-dashes were replaced, and those live in
  `explorer_ui.py`, which reaches the page through `build_dashboard.py` (corpus
  template), not `build_v9_dashboard.py`.

## 2026-08-03: seed-0 evidence audit readability pass

- **The design system could not be used to fix this panel, and that was the
  root cause of the small type.** `v9_design_system.py` `_TYPE_SCALE` carried a
  block of `#tab-v9Results .v9-recovery-*` font-size rules. That sheet is
  injected at byte ~410k of the built `index.html`, the panel's own sheet at
  ~19k, and the selectors are equal specificity, so the design system silently
  won every tie and editing the panel at source had no effect. The panel now
  owns its type in `v9_recovery_explainer_ui.py`; `_TYPE_SCALE` keeps only the
  `.xp-*` entries. Two guards enforce this:
  `test_this_panel_owns_its_type_and_holds_the_ten_pixel_floor` (no sub-10px in
  the panel sheet) and `test_this_layer_does_not_restyle_recovery_explorer_type`
  (no `.v9-recovery-*` font-size in the design system). Both were verified to
  fail on an injected regression. Do not reinstate recovery font-size rules in
  the design system layer.
- `var(--text3)` and `var(--text-dim)` are banned in this panel's CSS by
  `test_essential_explorer_labels_use_the_contrast_safe_text_token`. Use
  `var(--text2)` for the dimmest label.
- **Rank direction was the worst comprehension defect and it was not visual.**
  The case list showed `B 37 G 41 H 23` beside a `+14 ranks` badge, so an
  improvement made the number fall while the badge rose, with nothing saying
  which direction was good. Ranks are now labelled chips coloured with the
  existing `--data-baseline` / `--data-gnn` / `--data-hybrid` tokens, and both
  the rail and the case header state that rank 1 is inspected first.
- The evidence area is a vertical stack: graph full width, then a 3-up row of
  factors / narrative / attribution. Side by side, the 780px canvas left a
  matching column of empty background and a 512-node community got about half
  the width it needs. `renderDetail` still CALLS the renderers in the old order
  (factors, narrative, attribution, then graph) and appends the graph container
  first, because `test_detail_stops_before_evidence_renderers_when_boundary_is_invalid`
  and `test_highest_attribution_renderer_contract_is_shared_by_schema_paths`
  assert call ordering. Keep DOM order and call order decoupled here.
- `.v9-recovery-case-list` must keep an explicit `max-height`. An auto grid row
  sizes to its items' max-content, so an unbounded list stretches the whole
  workspace to fit all 593 cases at once; `min-height:0` on the rail does not
  prevent this.
- A single-node community now renders a written empty state instead of a
  full-height black canvas with one dot in it. The currently published artifact
  hits this path for its one explained case.
- **No test exercises this panel's DOM.** `_run_ui` runs pure functions in node
  and the rest is string-token assertions, so render bugs are only caught by
  eye. Verification harnesses live in the session scratchpad pattern: isolate
  `#v9-case-evidence` in the built page for the real-data view, and mount the
  panel standalone against `_valid_recovery_artifact()` with a synthetic
  multi-hop community for the canvas view. When faking a community, rewrite
  `flow_stages` node/edge ids to match or the view model returns
  `invalid-flow-stages`.
