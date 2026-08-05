# Schema-3 explanation graph presentation implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the schema-3 recovery explorer show only published GNN explanations and render the complete as-of community context with readable, weight-driven explanation emphasis.

**Architecture:** Keep the existing self-contained Python-generated JavaScript and canvas renderer. The schema-3 mount will lazily fetch the case's verified attribution overlay, validate overlay IDs against the loaded community, and pass a presentation-only overlay into the graph command builder. The builder will produce complete table rows plus a deterministic bounded canvas slice that preserves the target and every attributed node/edge.

**Tech Stack:** Python 3.14, pytest, Node JavaScript syntax/view-model tests, native Canvas 2D, existing dashboard CSS variables, generated static HTML.

---

## Context and invariants

- Work only in `/Users/edward/.config/superpowers/worktrees/GNN_Community_Detection/v9-balanced-explainability`.
- The source of truth is `Documents/Data/scripts/v9_recovery_explainer_ui.py`; `build_v9_dashboard.py` injects its CSS and JavaScript into the generated dashboard.
- Schema-3 base community chunks resolve compact `catalog_id`/identity rows and day-view coordinates. Explanation weights live in `caseData.overlay_evidence.node_chunks` and `edge_chunks`.
- `gnn_explanation` is the only selectable detail kind for this explorer. Baseline/community-control data remains validated in the manifest but is not shown by the schema-3 case selector.
- Existing schema-2 UI, structural controls, as-of boundary checks, sidecar hashes, complete tables, pointer controls, and accessibility contracts must remain intact.

### Task 1: Add failing pure-JavaScript contracts for explained-only selection and overlay validation

**Files:**
- Modify: `tests/test_v9_recovery_explainer_ui.py` near the schema-3 view-model tests and `_schema3_served_bundle`
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py` near `filterRecoverySchema3Cases` and `buildRecoverySchema3Detail`

- [ ] **Step 1: Add a failing explained-only selector test.**

Add a test that builds `_schema3_ui_artifact()`, adds an unselected Hybrid summary record and a baseline control, executes the schema-3 visible-row contract, and asserts only the GNN explanation remains:

```python
def test_schema3_explorer_defaults_to_published_explanations_only():
    artifact = _schema3_ui_artifact()
    extra = dict(artifact["cohorts"]["hybrid_only"][0])
    extra.update(case_id="h2", person_id="person:h2", detail_status="not_selected", detail_kind=None)
    artifact["cohorts"]["hybrid_only"].append(extra)

    result = _node_json(
        "const view=buildRecoverySchema3ViewModel(" + json.dumps(artifact) + ");"
        "process.stdout.write(JSON.stringify(filterRecoverySchema3Cases(view,'gnn_explanation')));"
    )

    assert [row["caseId"] for row in result] == ["h1"]
    assert all(row["detailKind"] == "gnn_explanation" for row in result)
```

- [ ] **Step 2: Add failing overlay merge/validation tests.**

Add tests for a valid overlay, an unknown node/edge ID, duplicate overlay IDs, and endpoint mismatch. The desired pure helper contract is:

```javascript
mergeRecoverySchema3Overlay(community, overlayNodes, overlayEdges)
// => {available:true, nodes:[...], edges:[...]}
// or {available:false, reason:'invalid-overlay-membership'|'invalid-overlay-identity'}
```

The valid case must assert `nodes[0].importance === 0.9`, `nodes[0].attributed === true`, `edges[0].importance === 0.8`, and `edges[0].attributed === true`. The invalid cases must assert `available === false` and never silently add an overlay member outside the base community.

- [ ] **Step 3: Add a failing bounded-slice test.**

Create a community with `RECOVERY_GRAPH_NODE_LIMIT + 5` nodes, one target, two attributed nodes, one attributed edge, and more than `RECOVERY_GRAPH_EDGE_LIMIT` context edges. Execute the desired helper:

```javascript
buildRecoveryGraphSlice(fullNodes, fullEdges, personId)
```

Assert that it is deterministic, reports `sampled === true`, keeps the target, keeps both attributed endpoints, keeps the attributed edge, and returns no more than the node/edge limits. This test must also assert that `tableNodes` and `tableEdges` still contain the complete input lengths.

- [ ] **Step 4: Run the focused tests and confirm RED.**

Run:

```bash
rtk .venv/bin/pytest -q tests/test_v9_recovery_explainer_ui.py -k "explainer_only or overlay or bounded"
```

Expected result: the new tests fail because the helper contracts and explained-only mount behavior do not yet exist. Fix test typos before continuing if the failure is a collection or syntax error.

### Task 2: Implement strict overlay loading and presentation-model helpers

**Files:**
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py` near `recoveryValidatedChunkRows`, `assembleRecoverySchema3Community`, and `buildRecoverySchema3Detail`
- Test: `tests/test_v9_recovery_explainer_ui.py`

- [ ] **Step 1: Add `mergeRecoverySchema3Overlay`.**

Validate both arrays, unique nonblank `node_id`/`edge_id`, finite unit `explainer_median`, and matching base identities. For edges, also require overlay `u`/`v` to match the base edge endpoints. Return normalized presentation rows with `importance` clamped to `[0,1]`, `attributed: true`, stable rank, and relation/type fields. Return `recoveryUnavailable('invalid-overlay-membership')` or `recoveryUnavailable('invalid-overlay-identity')` on any mismatch.

- [ ] **Step 2: Add the schema-3 overlay row loader.**

Add `loadRecoverySchema3OverlayRows(owner, normalized, token)` beside `loadCommunityRows`. It must:

1. read only `node_chunks` or `edge_chunks` from `payload.overlay_evidence`;
2. fetch every reference through `recoveryFetchJson`, preserving SHA-256 verification;
3. validate offset/count/row-field contracts with `recoveryValidatedChunkRows`;
4. enforce `recoveryValidateChunkOwner` before fetching; and
5. abort on stale `token`/disposed state exactly as `loadCommunityRows` does.

Do not resolve overlay rows through the base catalog or day view: overlay rows already carry attribution fields and stable graph IDs.

- [ ] **Step 3: Extend schema-3 detail state without changing published rows.**

Add `overlayNodes` and `overlayEdges` to the explanation presentation object returned by `buildRecoverySchema3Detail`. Keep `community.nodes` and `community.edges` unchanged for complete table rendering. Set `canvasAvailable` true for a valid GNN explanation even when its full community exceeds the old limit; retain the old size-bound behavior for structural controls.

- [ ] **Step 4: Run the Task 1 tests and the schema-3 contract tests.**

Run:

```bash
rtk .venv/bin/pytest -q tests/test_v9_recovery_explainer_ui.py -k "explainer_only or overlay or bounded or schema3_detail"
```

Expected result: overlay validation and presentation-state contracts pass; the bounded-slice tests remain RED until Task 4 implements `buildRecoveryGraphSlice`, and mount integration tests may still fail until Task 3 loads the rows.

### Task 3: Load and merge explanation overlays in the schema-3 mount

**Files:**
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py` inside `mountRecoveryExplorerV3`
- Modify: `tests/test_v9_recovery_explainer_ui.py` in `_schema3_served_bundle` and schema-3 end-to-end tests

- [ ] **Step 1: Extend V3 state.**

Initialize and clear `state.overlayNodeRows` and `state.overlayEdgeRows` beside `state.nodeRows` and `state.edgeRows`. For a selected `gnn_explanation`, require `caseData.overlay_evidence` to satisfy `recoveryValidateChunkOwner`; load the two overlay row collections after the complete base community rows. Do not fetch overlay chunks for controls.

- [ ] **Step 2: Pass overlay rows through the render path.**

Pass the loaded overlay rows into `buildRecoverySchema3Detail`, call `mergeRecoverySchema3Overlay`, and attach the resulting presentation overlay to `detailView.explanation`. If overlay validation or fetch/hash verification fails, use the existing `state.error` and `recoveryServerHelp` path instead of rendering unverified evidence.

- [ ] **Step 3: Extend the served-bundle fixture.**

Publish one overlay node chunk and one overlay edge chunk in `_schema3_served_bundle`, add their references to the Hybrid case payload, and assert the end-to-end mount fetches them. The fixture’s overlay edge must match `e1` and have `explainer_median: 0.8`; the overlay node must match `p2` and have `explainer_median: 0.9`.

- [ ] **Step 4: Run the mount tests and verify GREEN.**

Run:

```bash
rtk .venv/bin/pytest -q tests/test_v9_recovery_explainer_ui.py -k "schema3_mount or overlay or served_bundle"
```

Expected result: the Hybrid end-to-end test observes overlay rows and the baseline-control tests still assert no attribution fetch/rendering.

### Task 4: Implement deterministic full-context slicing and weighted graph commands

**Files:**
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py` in `buildCommunityDrawCommands`, `recoveryEdgeStyle`, and the canvas draw loop
- Test: `tests/test_v9_recovery_explainer_ui.py`

- [ ] **Step 1: Add `buildRecoveryGraphSlice`.**

Convert the complete community rows once into `tableNodes` and `tableEdges`. If the counts are within bounds, use all rows for the canvas. Otherwise, retain the target, all attributed nodes, and every attributed edge endpoint, then add remaining context nodes in stable `node_id` order and context edges in stable `edge_id` order until the limits are reached. Return `sampled`, `fullNodeCount`, `fullEdgeCount`, `nodes`, `edges`, `tableNodes`, and `tableEdges`.

- [ ] **Step 2: Add weighted presentation fields to draw commands.**

Use the validated overlay maps when mapping base rows. Every edge receives `importance`, `attributed`, `rank`, and `emphasized`; every node receives `importance`, `attributed`, and `rank`. In `flow` mode, stage rules still determine arrows, but an attributed edge must retain its evidence emphasis even when the selected stage does not match it. Return `sampled` and complete counts on the command object for the renderer and accessible copy.

- [ ] **Step 3: Update `recoveryEdgeStyle` and node drawing.**

Use relation colors only for context edges. Use the single evidence accent for attributed edges, mapping median weight to a visibly wider/brighter stroke. Draw an evidence halo/ring around attributed nodes, use the target marker as the highest-priority visual, and keep caught/pooled/search markers legible. Guard every endpoint lookup so a malformed command cannot throw during drawing.

- [ ] **Step 4: Update the graph table to remain complete.**

Change `renderGraphTable(panel, commands, record)` to page `commands.tableNodes` and `commands.tableEdges` while the canvas uses `commands.nodes` and `commands.edges`. Add columns for `Evidence weight` and `Evidence rank` so the table explains the visual encoding without changing the underlying rows.

- [ ] **Step 5: Run the pure command and accessibility tests.**

Run:

```bash
rtk .venv/bin/pytest -q tests/test_v9_recovery_explainer_ui.py -k "draw or graph or accessibility or bounded"
```

Expected result: full-context commands preserve every table row, sampled commands preserve all evidence rows, and weighted style fields are asserted.

### Task 5: Apply the visual hierarchy and explained-only interaction

**Files:**
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py` CSS and `mountRecoveryExplorerV3` rendering helpers
- Test: `tests/test_v9_recovery_explainer_ui.py`

- [ ] **Step 1: Default V3 to explanation-only rows.**

Set the V3 state filter to `gnn_explanation`, select the first published `detailIndex` case as the default case, and render a single “GNN explanations” filter status rather than controls for baseline/community-control rows. Keep the existing view-model cohort data intact for summary algebra and provenance.

- [ ] **Step 2: Improve graph copy and legend.**

Change the panel heading to “As-of community context + explanation evidence”. Add a concise note that context is muted, evidence width/brightness follows unsigned explainer median, and large contexts are sampled only for canvas performance. Render legend keys for context, explanation evidence, target, caught-before-snapshot, and the weight range.

- [ ] **Step 3: Add focused CSS.**

Update the existing schema-scoped CSS only: give the canvas a layered dark/radial surface, separate the legend into readable keys, add a small sampled-context badge, increase the canvas minimum height on desktop, preserve the existing mobile horizontal toolbar, and add `prefers-reduced-motion`/focus-safe behavior without adding a library or changing global dashboard tokens.

- [ ] **Step 4: Add source-contract assertions.**

Extend `test_schema3_graph_exposes_accessible_names_and_a_table_fallback` and `test_explorer_source_contract_covers_accessibility_lifecycle_and_states` to require the new graph heading, evidence legend text, sampled-context copy, `tableNodes`/`tableEdges`, and the overlay loader. Update old assertions that expected all schema-3 filters or an always-hidden large Hybrid canvas.

- [ ] **Step 5: Run the entire focused UI suite.**

Run:

```bash
rtk .venv/bin/pytest -q tests/test_v9_recovery_explainer_ui.py
```

Expected result: all schema-2 and schema-3 UI tests pass.

### Task 6: Rebuild and verify the generated dashboard

**Files:**
- Modify: `Documents/Data/v9_dashboard/index.html` and `Documents/Data/v9_dashboard/data_v9.json` only if the build output is tracked/generated in this worktree
- Modify: `PROJECT_MEMORY.md` with the durable UI decision after verification

- [ ] **Step 1: Run Python syntax and focused builder tests.**

Run:

```bash
rtk .venv/bin/python -m py_compile Documents/Data/scripts/v9_recovery_explainer_ui.py Documents/Data/scripts/build_v9_dashboard.py
rtk .venv/bin/pytest -q tests/test_v9_recovery_explainer_ui.py tests/test_v9_dashboard_builder.py
```

- [ ] **Step 2: Rebuild the dashboard from the verified schema-3 ZIP.**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/python Documents/Data/scripts/build_v9_dashboard.py
```

Verify the generated HTML contains exactly one injected schema-3 recovery UI payload and the new graph strings.

- [ ] **Step 3: Run JavaScript and HTTP smoke checks.**

Extract/check the generated recovery JavaScript using the existing test helper, then serve `Documents/Data/v9_dashboard` over HTTP and request `/index.html`, `/recovery/current.json`, and one case/community/overlay sidecar. All responses must be HTTP 200; direct `file://` loading is not an acceptable verification path because sidecars require fetch and WebCrypto.

- [ ] **Step 4: Run a headless screenshot check when available.**

Use the repository’s existing Chrome command from `tasks/v9_demo_polish_plan.md` against the local HTTP server. Inspect the schema-3 recovery panel for readable context/evidence contrast, visible weight differences, no clipped toolbar at desktop/narrow widths, and the sampled-context notice on an oversized explained case. If browser tooling is unavailable, record that limitation and rely on the canvas command/accessibility tests.

- [ ] **Step 5: Update project memory and review the diff.**

Add a dated note to `PROJECT_MEMORY.md` recording that schema-3 recovery now presents explanation-only cases, overlays verified attribution weights on full context, and samples only the canvas for oversized communities. Run:

```bash
rtk git diff --check
rtk git status --short
```

Review that no model/evaluation files or main-worktree files were modified.

### Task 7: Final verification and handoff

- [ ] **Step 1: Run the affected regression suite.**

Run:

```bash
rtk .venv/bin/pytest -q tests/test_v9_recovery_explainer_ui.py tests/test_v9_dashboard_builder.py tests/test_recovery_bundle.py
```

- [ ] **Step 2: Confirm the real bundle behavior.**

Use the generated bundle to confirm the explained-only list contains 19 cases, an explained small community shows all context plus weighted evidence edges, and an oversized explained community shows the bounded context canvas while its complete table count remains unchanged.

- [ ] **Step 3: Commit only the implementation changes in the feature worktree.**

Stage the modified UI source, focused tests, generated dashboard output if tracked, and the project-memory note. Do not stage the ZIP or unrelated pre-existing producer/model changes. Use a focused commit message such as:

```bash
git add Documents/Data/scripts/v9_recovery_explainer_ui.py tests/test_v9_recovery_explainer_ui.py PROJECT_MEMORY.md
git commit -m "feat: focus schema3 graph on explanation evidence"
```

- [ ] **Step 4: Report evidence, not assumptions.**

Hand off the commit, changed files, test counts, dashboard URL, and any browser limitation. Do not claim that the full graph is literally rendered for oversized communities; describe it as a bounded canvas context with complete tables and all explanation evidence retained.
