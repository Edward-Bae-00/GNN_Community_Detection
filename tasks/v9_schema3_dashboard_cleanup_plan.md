# V9 schema-3 dashboard cleanup implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` to implement this plan task by task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the V9 dashboard schema-3-only, remove unused compatibility UI,
reorder and simplify operational charts, and list only published GNN
explanations without changing any source data artifact.

**Architecture:** Retain the existing Python-string/vanilla-JavaScript dashboard
architecture. Narrow artifact acceptance and UI dispatch to schema 3, delete
unreachable schema-1/schema-2 branches while preserving shared evidence
helpers, and make presentation-only changes in `v9_dashboard_ui.py`. Guard the
immutable input boundary with before/after hashes.

**Tech Stack:** Python 3.14, pytest, Node-backed JavaScript harnesses, vanilla
JavaScript/CSS, static dashboard builder, headless Chrome.

---

## Global constraints

- Do not modify model, scoring, simulation, bootstrap, or producer logic.
- Do not edit source JSON/ZIP artifacts or simulated-catch payloads.
- Preserve all current uncommitted readability and accessibility work.
- Use `.venv/bin/python` or `.venv/bin/pytest`; the system interpreter does not
  provide PyTorch.
- Do not manually commit. Let Merget's Historian record changes unless the user
  explicitly requests a commit.

### Task 1: Freeze source artifacts and add failing cleanup contracts

**Files:**

- Modify: `tests/test_v9_dashboard_builder.py`
- Modify: `tests/test_v9_recovery_explainer_ui.py`
- Modify: `tests/test_recovery_bundle.py` only for removed schema-2 packager
  contracts
- Record transient hashes under `/private/tmp`, not in the repository

- [x] **Step 1: Record immutable input hashes**

Run a guarded loop over each existing source artifact and write the SHA-256
manifest to `/private/tmp/v9-dashboard-cleanup-before.sha256`.

Recorded in session state before production edits. The manifest includes every
existing diagnostic JSON, the schema-3 ZIP, and the V9 corpus
`dashboard_data.json`; it is outside the repository.

- [x] **Step 2: Add a failing builder contract**

Add tests asserting that:

```python
assert BUILDER._recovery_artifact_path() == BUILDER.V9_RECOVERY_ARCHIVE
```

when both the current schema-1 diagnostic JSON and schema-3 archive exist, and
that `_load_recovery_artifact()` rejects schema `1.0` and `2.0` fixtures rather
than returning/publishing them.

- [x] **Step 3: Add failing active-source absence contracts**

Assert the shipped recovery/anomaly UI no longer contains dispatcher or
renderer markers such as:

```python
for dead in (
    "mountRecoveryExplorerV2",
    "buildRecoveryManifestViewModel",
    "renderLegacySchemaV2",
    "Legacy schema-v2 anomaly diagnostics",
):
    assert dead not in ui_source
```

Avoid assertions against shared schema-3 evidence helpers.

- [x] **Step 4: Add a failing schema-3 explanation eligibility test**

Construct one available explanation with a `detail_index` reference and one
failed row with `detail_kind="gnn_explanation"` but no reference. Execute
`filterRecoverySchema3Cases` in the existing Node harness and assert only the
available case is returned.

- [x] **Step 5: Add failing V9 Results contracts**

Assert:

```python
assert js.index("Daily Crossing Volume") < js.index("Daily capacity view")
assert "dks.includes(10)?10:dks[0]" in draw_combined_source
assert "['baseline','hybrid']" in draw_daily_source
assert "['baseline','hybrid','gnn']" in draw_combined_source
```

Also retain the existing cumulative simulated-mode, simulated-budget,
accessibility, and combined-chart GNN assertions.

- [x] **Step 6: Run the focused tests and confirm the new assertions fail**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_v9_dashboard_builder.py \
  tests/test_v9_recovery_explainer_ui.py \
  tests/test_recovery_bundle.py
```

Expected: only the newly introduced cleanup contracts fail; record any
pre-existing failure separately.

### Task 2: Make schema 3 the sole recovery-dashboard contract

**Files:**

- Modify: `Documents/Data/scripts/build_v9_dashboard.py`
- Test: `tests/test_v9_dashboard_builder.py`

- [x] **Step 1: Prefer the schema-3 archive without mutating inputs**

Change `_recovery_artifact_path()` to use this order:

```text
explicit V9_SCHEMA3_RESULTS_ZIP override
existing V9_RECOVERY_ARCHIVE
existing V9_RECOVERY_EXPLANATIONS only if it declares schema 3.0
missing/default path for the existing warning path
```

The helper may inspect only the small JSON header/value needed to confirm its
schema; it must not rewrite the file.

- [x] **Step 2: Remove schema-1/schema-2 loading**

Keep ZIP handling and schema-3 JSON manifest/packaging. For any other declared
schema, fail closed with an explicit unsupported-schema warning or `ValueError`
consistent with the caller's existing error policy.

- [x] **Step 3: Run focused builder loader tests**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_v9_dashboard_builder.py -k "recovery or schema"
```

Expected: schema-3 tests pass and older-schema acceptance tests have been
removed or replaced by rejection tests.

### Task 3: Remove schema-1/schema-2 recovery UI and sidecar code

**Files:**

- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py`
- Modify: `Documents/Data/scripts/v9_recovery_sidecars.py`
- Modify: `tests/test_v9_recovery_explainer_ui.py`
- Modify: `tests/test_recovery_bundle.py`

- [x] **Step 1: Delete recovery UI compatibility branches**

Remove schema-2 CSS, `buildRecoveryManifestViewModel`, `recoveryV2Panel`,
`mountRecoveryExplorerV2`, the schema-2 dispatcher, and schema-1 mount/render
code. Remove helpers proven to be called only by those branches.

Preserve schema-3 and shared helpers including community draw commands,
narrative/attribution rendering, fetch/chunk validation, number formatting,
focus handling used by V3, and current readability changes.

- [x] **Step 2: Narrow the public mount**

`mountV9RecoveryExplainer` should accept schema 3 and render an explicit
unsupported/unavailable state for anything else. It must not silently route to
older UI.

- [x] **Step 3: Delete schema-2-only sidecar publishing**

Remove the schema-2 validator/publisher/packager functions that have no
schema-3 caller. Keep all schema-3 ZIP, manifest, sidecar, catalog, chunk, and
hash validation paths.

- [x] **Step 4: Remove obsolete compatibility tests**

Delete tests whose sole contract is successful schema-1/schema-2 rendering or
publishing. Retain/rebase tests for shared graph, narrative, attribution,
evidence-boundary, accessibility, formatting, and schema-3 sidecar behavior.

- [x] **Step 5: Run recovery UI and sidecar tests**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_v9_recovery_explainer_ui.py \
  tests/test_recovery_bundle.py \
  tests/test_recovery_layout_parity.py
```

Expected: all retained schema-3/shared contracts pass.

Verification note: the recovery UI and bundle slices pass. The unchanged
`tests/test_recovery_layout_parity.py` still fails during collection because
the untouched `gnn.sage_explainer` module does not export
`DISPLAY_LAYOUT_RADIUS`; this is a pre-existing, out-of-scope blocker rather
than a failure in the dashboard cleanup.

### Task 4: Show only published GNN explanations

**Files:**

- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py`
- Test: `tests/test_v9_recovery_explainer_ui.py`

- [x] **Step 1: Strengthen the schema-3 predicate**

Filter `gnn_explanation` rows by both detail kind and published index
membership. Use normalized case IDs and the already validated `detailIndex`;
do not infer availability from prose or failure strings.

- [x] **Step 2: Apply the same predicate to default selection**

Ensure initial and fallback selection cannot target a failed/unpublished row.
Preserve the explicit empty state when the filtered list is empty.

- [x] **Step 3: Run the focused Node-backed tests**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_v9_recovery_explainer_ui.py -k "schema3 or explanation or filter"
```

Expected: available explanations remain selectable; failed/unpublished rows
are absent; sidecar errors for published rows remain visible.

### Task 5: Remove legacy anomaly presentation without touching its JSON

**Files:**

- Modify: `Documents/Data/scripts/v9_dashboard_ui.py`
- Modify: `tests/test_v9_dashboard_builder.py`

- [x] **Step 1: Remove schema-2 anomaly fallback UI**

Delete `renderLegacySchemaV2`, its branch, and schema-2-only CSS. Schema-3
anomaly rendering remains unchanged.

- [x] **Step 2: Remove the visible legacy-oracle appendix**

Stop reading/rendering `legacy_oracle_benchmarks` in the view model. Do not
strip, rewrite, regenerate, or otherwise change the loaded anomaly JSON.

- [x] **Step 3: Update tests**

Replace tests that require the legacy renderer/card with schema-3-only and
absence contracts. Retain leakage-boundary copy for active deployable modes.

### Task 6: Reorder and simplify V9 Results

**Files:**

- Modify: `Documents/Data/scripts/v9_dashboard_ui.py`
- Test: `tests/test_v9_dashboard_builder.py`

- [x] **Step 1: Move Daily Crossing Volume**

Move the existing crossing-volume section intact to the first operational
position after the story block. Render Daily capacity next and Simulated
catches third. Preserve all element IDs exactly once.

- [x] **Step 2: Default only the crossing graph to 10/day**

Change the fallback in `drawCombined()` from 25 to 10. Do not change
`headlineDailyK`, `daily_ks`, simulated budgets, or any metric lookup.

- [x] **Step 3: Limit Daily capacity to two arms**

Use Baseline and Hybrid in `drawDaily()` only. Keep all three arms in
`drawCombined()` and keep the GNN line/legend/toggle styles.

- [x] **Step 4: Prove Simulated catches is unchanged**

Run all existing simulated view-model/default/mode/accessibility tests. Review
the diff to confirm there is no functional change inside
`SIMULATED_CATCH_VIEW_MODEL_JS` or `drawSimulatedCatches()`.

- [x] **Step 5: Run focused V9 Results tests**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_v9_dashboard_builder.py -k \
  "live_demo_order or daily or simulated or model_daily_catch"
```

Expected: crossing is first, defaults to 10/day, capacity has two arms,
combined chart retains GNN, and simulated behavior is unchanged.

### Task 7: Verify generated output and artifact immutability

**Files:**

- Modify: `Documents/Data/changes_3.md` with a concise presentation-only note
- Modify: `PROJECT_MEMORY.md` with the durable schema-3-only decision
- Regenerate gitignored: `Documents/Data/v9_dashboard/index.html`
- Regenerate gitignored: `Documents/Data/v9_dashboard/data_v9.json`

- [x] **Step 1: Compile and run the affected suite**

Run:

```bash
rtk .venv/bin/python -m py_compile \
  Documents/Data/scripts/build_v9_dashboard.py \
  Documents/Data/scripts/v9_dashboard_ui.py \
  Documents/Data/scripts/v9_recovery_explainer_ui.py \
  Documents/Data/scripts/v9_recovery_sidecars.py
rtk env PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_v9_dashboard_builder.py \
  tests/test_v9_recovery_explainer_ui.py \
  tests/test_recovery_bundle.py \
  tests/test_recovery_layout_parity.py
```

Expected: compilation succeeds and all affected tests pass.

Result: changed modules compile and the three cleanup-affected suites pass
with 345 tests. The known layout-parity collection blocker is documented
above and excluded from that passing count.

- [x] **Step 2: Rebuild from unchanged inputs**

Run:

```bash
rtk .venv/bin/python Documents/Data/scripts/build_v9_dashboard.py
```

Expected: schema-3 recovery publication succeeds and generated output contains
no schema-1/schema-2 renderer or legacy anomaly appendix.

Result: the atomic rebuild completed successfully and published a schema-3.0
recovery bundle.

- [x] **Step 3: Compare immutable hashes**

Recompute the same source-artifact manifest and compare it byte-for-byte with
`/private/tmp/v9-dashboard-cleanup-before.sha256`.

Expected: no source JSON, ZIP, corpus dashboard input, or simulated payload
artifact changed.

Result: all seven protected JSON/ZIP inputs exactly matched the in-session
pre-edit SHA-256 manifest, including `v9_schema3_results.zip` and the corpus
`dashboard_data.json`.

- [x] **Step 4: Validate generated JavaScript and inspect the dashboard**

Use the existing Node syntax harness and headless-Chrome workflow. Inspect V9
Results at desktop and narrow widths and verify the approved order, controls,
two-arm capacity view, unchanged simulated catches, and 19 published
explanation cases for the current schema-3 artifact.

Result: the generated-JavaScript syntax harness passed. Desktop and 390px
headless-Chrome renders confirmed the order, 10/day crossing default,
two-arm capacity layout, cumulative simulated default, and explained-only
recovery presentation. The schema-3 payload retains 19 published detail refs.

- [x] **Step 5: Final repository checks**

Run:

```bash
rtk git diff --check
rtk git status --short
rtk merget diff --stat
```

Expected: no whitespace errors, no source artifacts changed, and all edits are
inside the approved dashboard/test/documentation scope.
