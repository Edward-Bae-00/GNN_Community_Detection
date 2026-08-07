# GNN Explanation Graph Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the schema-3 GNN explanation explorer into the approved graph-first workspace while preserving every published evidence, as-of, loading, graph, and artifact contract.

**Architecture:** Keep the implementation inside the existing vanilla JavaScript/CSS generator in `v9_recovery_explainer_ui.py`. Refactor only the mount's presentation functions: selected-case header and ranks lead, case navigation becomes a bounded rail/native picker, graph rendering precedes prose, and dense evidence moves into state-preserving disclosures. Existing schema-3 view models, SHA-256 sidecar loading, request-token cancellation, graph command builders, canvas bindings, and table data remain unchanged.

**Tech Stack:** Python 3.14 string-based asset generator, vanilla JavaScript and CSS, Node-backed fake DOM tests, pytest, existing HTML dashboard builder.

---

## Execution guardrails

- Work in the current Merget workspace. A clean worktree cannot reproduce the large uncommitted schema-3 cleanup that this redesign must build on.
- Do not restore schema-1/schema-2 renderer code removed by the active diff.
- Do not edit `build_v9_dashboard.py`, source artifacts, ZIP payloads, corpus files, model code, or evaluation logic.
- Use TDD for each behavior slice: failing focused test, minimal implementation, focused passing test.
- This repository uses Merget Historian. Do not run `git commit` or `merget commit` unless the user explicitly requests it. Each task ends with a scoped diff checkpoint for Historian instead.
- Prefix every shell command with `rtk`.

## File map

- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py`
  - Owns all recovery explorer CSS, schema-3 render composition, event delegation, lazy loading, graph/table presentation, and UI states.
- Modify: `tests/test_v9_recovery_explainer_ui.py`
  - Owns view-model contracts, fake-DOM mount tests, render order, CSS contracts, loading/error behavior, graph semantics, and lifecycle checks.
- Modify: `tests/test_v9_dashboard_builder.py`
  - Owns the integration contract between the V9 Results mount and injected recovery assets.
- Modify: `Documents/Data/changes_3.md`
  - Records the completed presentation-only dashboard change and verification evidence.
- Modify: `PROJECT_MEMORY.md`
  - Records the durable graph-first hierarchy and the artifact-preservation boundary for later sessions.
- Generated only during verification: `Documents/Data/v9_dashboard/index.html` and `Documents/Data/v9_dashboard/data_v9.json`
  - Rebuilt output; not source implementation files.

## Task 1: Lock the graph-first DOM contract in the fake-DOM harness

**Files:**
- Modify: `tests/test_v9_recovery_explainer_ui.py:3082-3175`
- Modify: `tests/test_v9_recovery_explainer_ui.py:3200-3290`

- [ ] **Step 1: Extend the fake-DOM snapshot with structural fields**

Replace the current `emitSnapshot()` payload in `_mount_schema3` with a reusable structural snapshot. Keep the existing `text`, `labels`, `fetches`, `details`, `tables`, and `rows` keys so existing tests do not lose coverage.

```javascript
function snapshotRoot(root){
  const nodes=allNodes(root).map(node=>({
    tag:node.tag,
    className:node.className,
    id:node.id,
    attrs:node.attrs,
    dataset:node.dataset,
    open:node.open===true
  }));
  return {
    text:visibleText(root),
    labels:ariaLabels(root),
    nodes,
    tables:nodes.filter(node=>node.tag==='table').length,
    rows:nodes.filter(node=>node.tag==='tr').length
  };
}
```

In `_mount_schema3`, capture the synchronous loading render immediately after mount. Add the final line shown here after the existing mount interpolation:

```python
+ "\nconst root=makeRoot();"
+ "\nconst cleanup=mountRecoveryExplorerV3(root,"
+ json.dumps(artifact)
+ ",{});"
+ "\nconst initial=snapshotRoot(root);"
```

Then replace the current `emitSnapshot` string fragments with:

```python
+ "function emitSnapshot(){return {"
+ "...snapshotRoot(root),initial,fetches:FETCHED,details:DETAILS};}"
```

- [ ] **Step 2: Replace narrative-first assertions with the approved graph-first assertions**

Rename the existing readability/order tests and assert the selected header, valid heading ID, eligible count, ranks, graph, narrative, and disclosures in approved order.

```python
def test_schema3_mount_uses_graph_first_case_workspace_and_three_decimals():
    artifact, files = _schema3_served_bundle()
    record = artifact["cohorts"]["hybrid_only"][0]
    record["baseline_raw"] = 0.8427
    record["seed0_gnn_probability"] = 0.3184
    record["seed0_hybrid_score"] = 0.6719

    rendered = _mount_schema3("h1", (artifact, files))
    text = " | ".join(rendered["text"])

    assert "1 published GNN explanation" in text
    assert "Why case p1 surfaced" in text
    assert "Baseline rank" in text
    assert "Seed-0 GNN rank" in text
    assert "Seed-0 Hybrid rank" in text
    assert "12 places higher than Baseline" in text
    assert text.index("Why case p1 surfaced") < text.index("Baseline rank")
    assert text.index("Baseline rank") < text.index(
        "As-of community context + explanation evidence"
    )
    assert text.index("As-of community context + explanation evidence") < text.index(
        "Grounded narrative"
    )
    assert "0.843" in text
    assert "0.318" in text
    assert "0.672" in text
    assert "0.8427" not in text
    assert "0.3184" not in text
    assert "0.6719" not in text


def test_schema3_mount_supplies_the_v9_results_accessible_heading():
    rendered = _mount_schema3("h1")
    titles = [
        node for node in rendered["nodes"]
        if node["id"] == "v9-recovery-title"
    ]

    assert len(titles) == 1
    assert titles[0]["tag"] == "h3"
```

- [ ] **Step 3: Add failing tests for the new rail, picker, and removed status strip**

```python
def test_schema3_mount_renders_published_case_navigation_without_status_strip():
    rendered = _mount_schema3("h1")
    text = " | ".join(rendered["text"])
    classes = {node["className"] for node in rendered["nodes"]}

    assert "v9-recovery-v3-list" in classes
    assert "v9-recovery-v3-picker" in classes
    assert "Showing GNN explanations only" not in text
    assert "+12 places vs baseline" not in text
    assert "Hybrid rank 8" in text
    assert "12 places higher than Baseline" in text
```

- [ ] **Step 4: Run the new tests and verify they fail for the intended reasons**

Run:

```bash
rtk .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_mount_uses_graph_first_case_workspace_and_three_decimals \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_mount_supplies_the_v9_results_accessible_heading \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_mount_renders_published_case_navigation_without_status_strip
```

Expected: FAIL because the current mount renders the generic title, standalone GNN-only status, old case-row copy, and narrative before graph.

- [ ] **Step 5: Run the unchanged JavaScript syntax test**

Run:

```bash
rtk .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py::test_ui_javascript_is_valid_and_has_no_rendering_side_effects
```

Expected: PASS. This confirms the harness-only edit did not change generated JavaScript.

- [ ] **Step 6: Leave a Merget checkpoint**

Run:

```bash
rtk git diff --check -- tests/test_v9_recovery_explainer_ui.py
rtk git diff --stat -- tests/test_v9_recovery_explainer_ui.py
```

Expected: no whitespace errors; only the focused harness/order tests are added or changed.

## Task 2: Build the selected-case header, rank strip, and case navigation

**Files:**
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py:1792-1950`
- Test: `tests/test_v9_recovery_explainer_ui.py`

- [ ] **Step 1: Add one test for the narrow native picker contract**

```python
def test_schema3_case_picker_uses_the_same_explained_case_state():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    mount = js.split("function mountRecoveryExplorerV3", 1)[1].split(
        "const recoveryMounts", 1
    )[0]

    assert "data.v3Change==='case'" in mount
    assert "state.caseId=control.value" in mount
    assert "loadSelected();return" in mount
    assert "Published GNN explanations" in mount
```

- [ ] **Step 2: Run the picker test and verify it fails**

Run:

```bash
rtk .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_case_picker_uses_the_same_explained_case_state
```

Expected: FAIL because the mount has no case select or `v3Change='case'` branch.

- [ ] **Step 3: Replace the static header/summary/filter renderers**

Inside `mountRecoveryExplorerV3`, replace `renderHeader`, `renderSummary`, and `renderFilters` with the following focused helpers. Keep `renderRecordStatus` and the schema-3 view model unchanged.

```javascript
function eligibleCountLabel(rows){
  return fmt(rows.length)+' published GNN explanation'
    +(rows.length===1?'':'s');
}

function selectedBoundaryText(){
  if(state.loading)return 'Strict as-of evidence loading';
  if(state.error)return 'Strict as-of evidence unavailable';
  const explanation=state.caseData&&(
    state.caseData.explanation
      ||(state.caseData.detail&&state.caseData.detail.explanation));
  const boundary=explanation&&explanation.evidence_boundary;
  if(!recoveryIsRecord(boundary)
      ||!recoveryNonBlankString(boundary.snapshot)
      ||!recoveryNonBlankString(boundary.edge_rule)
      ||!recoveryNonBlankString(boundary.caught_rule)){
    return 'Strict as-of evidence pending';
  }
  return 'Strict as-of snapshot '+boundary.snapshot
    +'. Edges: '+boundary.edge_rule
    +'. Caught labels: '+boundary.caught_rule+'.';
}

function renderSelectedHeader(fragment,record,rows){
  const header=recoveryElement(doc,'header','v9-recovery-selected-header');
  const copy=recoveryElement(doc,'div','v9-recovery-selected-copy');
  addText(copy,'div','v9-recovery-selected-eyebrow',eligibleCountLabel(rows));
  const title=recoveryElement(doc,'h3','v9-recovery-title',
    record?'Why case '+record.personId+' surfaced':'GNN explanations');
  title.id='v9-recovery-title';copy.appendChild(title);
  addText(copy,'p','v9-recovery-selected-meta',record
    ?'Event '+record.event_id+' / scoring day '+record.scoring_day+'. '
      +selectedBoundaryText()
    :'No published GNN explanation is available.');
  header.appendChild(copy);
  addText(header,'div','v9-recovery-selected-scope',
    'GraphSAGE seed 0 / Hybrid score is percentile fusion, not probability.');
  fragment.appendChild(header);
}

function renderCohortContext(parent,record){
  const grid=recoveryElement(doc,'div','v9-recovery-summary');
  grid.setAttribute('aria-label','Schema-3 recovery overlap summary');
  for(const [key,label] of [
    ['baseline_recovered','Baseline recovered'],
    ['recovered_by_both','Recovered by both'],
    ['hybrid_only_recovered','Hybrid-only recovered'],
    ['baseline_only_recovered','Baseline-only recovered'],
    ['hybrid_total','Hybrid total'],['net_gain','Net gain']]){
    const card=recoveryElement(doc,'article','v9-recovery-stat');
    addText(card,'b','',fmt(view.summary[key]));
    addText(card,'span','',label);grid.appendChild(card);
  }
  parent.appendChild(grid);
  const coverage=recoveryElement(doc,'div','v9-recovery-coverage');
  addText(coverage,'span','',
    'Hybrid technical detail '+fmt(view.coverage.hybrid_explained)
      +' / '+fmt(view.coverage.hybrid_requested));
  addText(coverage,'span','',
    'Baseline community context '+fmt(view.coverage.baseline_community)
      +' / '+fmt(view.coverage.baseline_requested));
  parent.appendChild(coverage);
  if(record){
    for(const [label,value] of [
      ['Baseline score',record.baseline_raw],
      ['Baseline percentile',record.baseline_percentile],
      ['Seed-0 GNN percentile',record.seed0_gnn_percentile],
      ['Seed-0 GNN probability',record.seed0_gnn_probability],
      ['Hybrid percentile-fusion score',record.seed0_hybrid_score]]){
      if(typeof value==='number')addText(parent,'div','v9-recovery-score-context',
        label+': '+recoveryFormatNumber(value));
    }
  }
}
```

- [ ] **Step 4: Make the rank strip a full-width selected-case zone**

Change `renderRanks` so it appends the existing three rank cells directly to the supplied parent and labels every value as a rank. Remove loose raw-score lines; `renderCohortContext` now owns those secondary values.

```javascript
function renderRanks(parent,record){
  const ranks=recoveryElement(doc,'section','v9-recovery-ranks');
  ranks.setAttribute('aria-label','Selected case rank comparison');
  for(const [label,value,primary] of [
    ['Baseline rank',record.baseline_rank,false],
    ['Seed-0 GNN rank',record.seed0_gnn_rank,false],
    ['Seed-0 Hybrid rank',record.seed0_hybrid_rank,true]]){
    const cell=recoveryElement(doc,'div','v9-recovery-rank'
      +(primary?' is-primary':''));
    addText(cell,'b','',fmt(value));addText(cell,'span','',label);
    ranks.appendChild(cell);
  }
  const delta=recoveryRankDelta(record);
  addText(ranks,'div','v9-recovery-rank-delta',
    delta===null?'Rank movement unavailable'
      :delta>0?fmt(delta)+' places higher than Baseline'
      :delta<0?fmt(Math.abs(delta))+' places lower than Baseline'
      :'No rank movement recorded');
  parent.appendChild(ranks);
}
```

- [ ] **Step 5: Render the desktop rail and narrow picker from the same rows**

```javascript
function renderCaseNavigation(grid,rows){
  const list=recoveryElement(doc,'aside','v9-recovery-v3-list');
  list.setAttribute('aria-label','Published GNN explanations');
  addText(list,'div','v9-recovery-v3-list-head',eligibleCountLabel(rows));
  for(const record of rows){
    const button=recoveryElement(doc,'button','v9-recovery-case');
    button.type='button';button.dataset.v3Case=record.caseId;
    button.setAttribute('aria-current',String(record.caseId===state.caseId));
    button.setAttribute('aria-label','Inspect GNN explanation for '+record.personId);
    addText(button,'strong','',record.personId);
    addText(button,'div','v9-recovery-case-meta',
      'Hybrid rank '+fmt(record.seed0_hybrid_rank));
    const delta=recoveryRankDelta(record);
    addText(button,'div','v9-recovery-case-evidence',
      delta===null?'Rank movement unavailable'
        :delta>0?fmt(delta)+' places higher than Baseline'
        :delta<0?fmt(Math.abs(delta))+' places lower than Baseline'
        :'No rank movement recorded');
    list.appendChild(button);
  }
  grid.appendChild(list);

  const picker=recoveryElement(doc,'select','v9-recovery-v3-picker');
  picker.dataset.v3Change='case';
  picker.setAttribute('aria-label','Choose a published GNN explanation');
  for(const record of rows){
    const option=recoveryElement(doc,'option','',record.personId
      +' / Hybrid rank '+fmt(record.seed0_hybrid_rank));
    option.value=record.caseId;picker.appendChild(option);
  }
  picker.value=state.caseId||'';grid.appendChild(picker);
}
```

Add the case branch before the existing density branch in `onV3Change`:

```javascript
const control=event.target;
if(control.dataset.v3Change==='case'){
  state.caseId=control.value;loadSelected();return;
}
if(control.dataset.v3Change==='density'){
  state.labelDensity=control.value;render();
  restoreV3Focus('data-v3-change','v3Change','density');
}
```

- [ ] **Step 6: Recompose the top-level render order**

In `render()`, compute `rows` and `record` before the header, render the selected header and rank strip before the two-column workspace, and remove calls to the old summary/filter renderers.

```javascript
const fragment=doc.createDocumentFragment();
if(!view.available){
  renderSelectedHeader(fragment,null,[]);
  addText(fragment,'div','v9-recovery-empty',
    'Case evidence unavailable. '+view.reason+'.');
  root.replaceChildren(fragment);return;
}
const rows=visibleRows();
const record=currentRecord();
renderSelectedHeader(fragment,record,rows);
if(record)renderRanks(fragment,record);
const grid=recoveryElement(doc,'div','v9-recovery-v3-grid');
renderCaseNavigation(grid,rows);
const detail=recoveryElement(doc,'section','v9-recovery-v3-detail');
detail.setAttribute('aria-label','Selected GNN explanation');
```

Keep the existing selected-evidence call and canvas bind after `root.replaceChildren`.

- [ ] **Step 7: Run focused structure tests**

Run:

```bash
rtk .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_mount_uses_graph_first_case_workspace_and_three_decimals \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_mount_supplies_the_v9_results_accessible_heading \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_mount_renders_published_case_navigation_without_status_strip \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_case_picker_uses_the_same_explained_case_state
```

Expected: the accessible heading and navigation tests PASS; the graph-first order assertion may remain FAIL until Task 4 moves the graph.

- [ ] **Step 8: Leave a Merget checkpoint**

Run:

```bash
rtk git diff --check -- \
  Documents/Data/scripts/v9_recovery_explainer_ui.py \
  tests/test_v9_recovery_explainer_ui.py
rtk git diff --stat -- \
  Documents/Data/scripts/v9_recovery_explainer_ui.py \
  tests/test_v9_recovery_explainer_ui.py
```

Expected: no whitespace errors; only presentation functions and their tests change.

## Task 3: Apply the graph-first layout and responsive CSS

**Files:**
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py:5-149`
- Test: `tests/test_v9_recovery_explainer_ui.py:1001-1105`

- [ ] **Step 1: Replace old nested-grid CSS assertions with the approved layout contract**

```python
def test_schema3_graph_workspace_css_uses_bounded_rail_and_graph_first_tracks():
    css = UI.V9_RECOVERY_EXPLAINER_CSS

    for token in (
        "grid-template-columns: 214px minmax(0, 1fr)",
        "max-height: min(70vh, 720px)",
        "position: sticky",
        "top: 16px",
        "overflow-y: auto",
        "height: clamp(420px, 52vh, 560px)",
        ".v9-recovery-explanation-row",
        "grid-template-columns: minmax(0, 1.28fr) minmax(220px, .72fr)",
    ):
        assert token in css
    assert "radial-gradient" not in css


def test_schema3_graph_workspace_css_switches_to_picker_and_touch_grid():
    css = UI.V9_RECOVERY_EXPLAINER_CSS

    assert "@media(max-width:900px)" in css
    assert ".v9-recovery-v3-list { display: none; }" in css
    assert ".v9-recovery-v3-picker { display: block;" in css
    assert "height: clamp(360px, 48vh, 470px)" in css
    assert "@media(max-width:700px)" in css
    assert "height: 340px; min-height: 300px" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in css
    assert "min-height: 44px" in css
    assert "@media(max-width:360px)" in css
```

- [ ] **Step 2: Run the CSS tests and verify they fail**

Run:

```bash
rtk .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_graph_workspace_css_uses_bounded_rail_and_graph_first_tracks \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_graph_workspace_css_switches_to_picker_and_touch_grid
```

Expected: FAIL because the current rail is unbounded, the evidence grid squeezes the graph, and the canvas uses a decorative radial gradient.

- [ ] **Step 3: Replace the top-level recovery layout rules**

Preserve graph legend, node/edge semantic color, focus, table, and canvas interaction rules. Replace only header, summary, case navigation, nested evidence-grid, and responsive sizing rules with this contract:

```css
#tab-v9Results .v9-recovery { margin: 30px 0; padding: 24px 0 32px; border-top: 1px solid var(--border-strong); border-bottom: 1px solid var(--border-strong); }
#tab-v9Results .v9-recovery-selected-header { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 24px; align-items: start; padding: 22px 24px; border: 1px solid var(--border); border-radius: 12px 12px 0 0; background: var(--surface); }
#tab-v9Results .v9-recovery-selected-copy { min-width: 0; font-family: Outfit, var(--font-sans), sans-serif; }
#tab-v9Results .v9-recovery-selected-eyebrow { color: var(--accent-hover); font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
#tab-v9Results .v9-recovery-title { margin: 7px 0 0; color: var(--text1); font-size: clamp(22px, 2.5vw, 30px); line-height: 1.08; letter-spacing: -.035em; text-wrap: balance; }
#tab-v9Results .v9-recovery-selected-meta { max-width: 68ch; margin: 9px 0 0; color: var(--text2); font-size: 13px; line-height: 1.6; text-wrap: pretty; }
#tab-v9Results .v9-recovery-selected-scope { max-width: 280px; padding: 9px 11px; border: 1px solid rgba(52,211,153,.3); border-radius: 7px; background: var(--accent-soft); color: var(--accent-hover); font-family: 'JetBrains Mono', var(--font-mono), monospace; font-size: 10px; line-height: 1.5; text-align: right; }
#tab-v9Results .v9-recovery-ranks { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; border: 1px solid var(--border); border-top: 0; background: var(--border); }
#tab-v9Results .v9-recovery-rank { min-width: 0; min-height: 78px; padding: 14px 18px; border: 0; border-top: 3px solid var(--border-strong); background: var(--elevated); }
#tab-v9Results .v9-recovery-rank.is-primary { border-top-color: var(--accent); background: var(--accent-soft); }
#tab-v9Results .v9-recovery-rank b { display: block; color: var(--text1); font-family: 'JetBrains Mono', var(--font-mono), monospace; font-size: 21px; font-variant-numeric: tabular-nums; }
#tab-v9Results .v9-recovery-rank span { display: block; margin-top: 5px; color: var(--text2); font-size: 10px; letter-spacing: .055em; text-transform: uppercase; }
#tab-v9Results .v9-recovery-rank-delta { grid-column: 1 / -1; padding: 9px 18px 12px; background: var(--surface); color: var(--accent-hover); font-size: 12px; }
#tab-v9Results .v9-recovery-v3-grid { display: grid; grid-template-columns: 214px minmax(0, 1fr); gap: 16px; align-items: start; margin-top: 16px; }
#tab-v9Results .v9-recovery-v3-list { position: sticky; top: 16px; max-height: min(70vh, 720px); overflow-y: auto; display: grid; gap: 8px; align-content: start; min-width: 0; padding: 12px; border: 1px solid var(--border); border-radius: 9px; background: var(--sunk); scrollbar-gutter: stable; }
#tab-v9Results .v9-recovery-v3-list-head { color: var(--text2); font-size: 10px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
#tab-v9Results .v9-recovery-v3-picker { display: none; width: 100%; min-height: 44px; border: 1px solid var(--border-strong); border-radius: 7px; background: var(--surface); color: var(--text1); padding: 8px 10px; font: inherit; }
#tab-v9Results .v9-recovery-v3-detail { min-width: 0; }
#tab-v9Results .v9-recovery-graph-panel { min-width: 0; overflow: hidden; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); }
#tab-v9Results .v9-recovery-v3 .v9-recovery-canvas-wrap { height: clamp(420px, 52vh, 560px); min-height: 420px; background: var(--sunk); box-shadow: inset 0 1px 0 rgba(255,255,255,.025); }
#tab-v9Results .v9-recovery-explanation-row { display: grid; grid-template-columns: minmax(0, 1.28fr) minmax(220px, .72fr); gap: 14px; margin-top: 14px; }
#tab-v9Results .v9-recovery-explanation-row > * { min-width: 0; }
#tab-v9Results .v9-recovery-disclosures { display: grid; gap: 8px; margin-top: 14px; }
```

- [ ] **Step 4: Add exact responsive rules**

```css
@media(max-width:900px){
  #tab-v9Results .v9-recovery-selected-header { grid-template-columns: 1fr; }
  #tab-v9Results .v9-recovery-selected-scope { max-width: none; text-align: left; }
  #tab-v9Results .v9-recovery-v3-grid { grid-template-columns: 1fr; }
  #tab-v9Results .v9-recovery-v3-list { display: none; }
  #tab-v9Results .v9-recovery-v3-picker { display: block; margin-bottom: 12px; }
  #tab-v9Results .v9-recovery-v3 .v9-recovery-canvas-wrap { height: clamp(360px, 48vh, 470px); min-height: 360px; }
}
@media(max-width:700px){
  #tab-v9Results .v9-recovery { margin: 24px 0; padding: 20px 0 28px; }
  #tab-v9Results .v9-recovery-selected-header { padding: 18px; }
  #tab-v9Results .v9-recovery-rank { min-height: 68px; padding: 11px 12px; }
  #tab-v9Results .v9-recovery-explanation-row { grid-template-columns: 1fr; }
  #tab-v9Results .v9-recovery-toolbar { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px; }
  #tab-v9Results .v9-recovery-toolgroup { display: grid; grid-column: 1 / -1; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  #tab-v9Results .v9-recovery-toolgroup > *,
  #tab-v9Results .v9-recovery-toolbar > .v9-recovery-search,
  #tab-v9Results .v9-recovery-toolbar > .v9-recovery-select { width: 100%; min-width: 0; min-height: 44px; }
  #tab-v9Results .v9-recovery-v3 .v9-recovery-canvas-wrap { height: 340px; min-height: 300px; }
}
@media(max-width:360px){
  #tab-v9Results .v9-recovery-ranks { grid-template-columns: 1fr; }
  #tab-v9Results .v9-recovery-rank-delta { grid-column: 1; }
}
```

Keep the existing `prefers-reduced-motion` block and focus-visible rules.

- [ ] **Step 5: Run CSS and syntax tests**

Run:

```bash
rtk .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_graph_workspace_css_uses_bounded_rail_and_graph_first_tracks \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_graph_workspace_css_switches_to_picker_and_touch_grid \
  tests/test_v9_recovery_explainer_ui.py::test_recovery_mobile_toolbar_wraps_with_full_width_touch_controls \
  tests/test_v9_recovery_explainer_ui.py::test_ui_javascript_is_valid_and_has_no_rendering_side_effects
```

Expected: PASS after updating the old mobile/nested-grid assertions to the new class names and exact breakpoints.

- [ ] **Step 6: Leave a Merget checkpoint**

Run:

```bash
rtk git diff --check -- \
  Documents/Data/scripts/v9_recovery_explainer_ui.py \
  tests/test_v9_recovery_explainer_ui.py
```

Expected: no whitespace errors.

## Task 4: Move graph before prose and add state-preserving technical disclosures

**Files:**
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py:2000-2340`
- Test: `tests/test_v9_recovery_explainer_ui.py:2220-2285`
- Test: `tests/test_v9_recovery_explainer_ui.py:3200-3310`

- [ ] **Step 1: Add failing DOM tests for graph-first order and disclosures**

```python
def test_schema3_mount_puts_graph_before_open_prose_and_closed_technical_evidence():
    rendered = _mount_schema3("h1")
    text = " | ".join(rendered["text"])
    details = [node for node in rendered["nodes"] if node["tag"] == "details"]

    assert text.index("As-of community context + explanation evidence") < text.index(
        "Grounded narrative"
    )
    assert text.index("Grounded narrative") < text.index(
        "Restart stability and removal faithfulness"
    )
    assert [
        node["dataset"].get("v3Disclosure") for node in details
    ] == ["stability", "attribution", "tables", "cohort"]
    assert all(node["open"] is False for node in details)


def test_schema3_disclosure_state_is_preserved_on_render_and_reset_on_case_load():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    mount = js.split("function mountRecoveryExplorerV3", 1)[1].split(
        "const recoveryMounts", 1
    )[0]

    assert "openDisclosures:new Set()" in mount
    assert "state.openDisclosures.add(key)" in mount
    assert "state.openDisclosures.delete(key)" in mount
    assert "state.openDisclosures.clear()" in mount
    assert "root.addEventListener('toggle',onV3Toggle,true)" in mount
    assert "root.removeEventListener('toggle',onV3Toggle,true)" in mount
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
rtk .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_mount_puts_graph_before_open_prose_and_closed_technical_evidence \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_disclosure_state_is_preserved_on_render_and_reset_on_case_load
```

Expected: FAIL because the graph currently follows narrative/factors and all technical panels are always expanded.

- [ ] **Step 3: Add disclosure state and one renderer helper**

Add `openDisclosures:new Set()` to the mount state.

```javascript
function renderDisclosure(parent,key,label,renderBody){
  const details=recoveryElement(doc,'details','v9-recovery-disclosure');
  details.dataset.v3Disclosure=key;
  details.open=state.openDisclosures.has(key);
  const summary=recoveryElement(doc,'summary','v9-recovery-disclosure-summary',label);
  summary.setAttribute('aria-label',label);
  details.appendChild(summary);
  const body=recoveryElement(doc,'div','v9-recovery-disclosure-body');
  renderBody(body);details.appendChild(body);parent.appendChild(details);
}
```

Add the non-bubbling `toggle` listener in capture mode:

```javascript
function onV3Toggle(event){
  const details=event.target;
  const key=details&&details.dataset&&details.dataset.v3Disclosure;
  if(!key||!root.contains(details))return;
  if(details.open)state.openDisclosures.add(key);
  else state.openDisclosures.delete(key);
}
```

Register with `root.addEventListener('toggle',onV3Toggle,true)` and remove it with the same capture argument during cleanup.

- [ ] **Step 4: Separate graph rendering from table rendering**

Change `renderGraph` with these exact edits; every toolbar, legend, command, sampled-context, canvas, and accessible-description line between them remains byte-for-byte unchanged:

```diff
-    const panel=recoveryElement(doc,'section','v9-recovery-panel');
+    const panel=recoveryElement(doc,'section','v9-recovery-graph-panel');
@@
     if(!commands.available){
       addText(panel,'div','v9-recovery-empty',
         'Strict-bound unavailable: complete community unavailable ('
           +commands.reason+'). The complete data table is not rendered because the graph command failed closed.');
-      column.appendChild(panel);return;
+      column.appendChild(panel);return null;
     }
@@
-    renderGraphTable(panel,commands,record);
-    column.appendChild(panel);
+    column.appendChild(panel);return commands;
   }
```

Do not change `buildCommunityDrawCommands`, `buildStructuralDrawCommands`, `bindRecoveryCanvas`, or `renderGraphTable` internals.

- [ ] **Step 5: Recompose selected evidence in the approved order**

After the existing strict-bound gate succeeds, render the graph first, prose/factors second, and disclosures third:

```javascript
const commands=renderGraph(detail,detailView,record);
if(!commands)return;
const explanationRow=recoveryElement(doc,'div','v9-recovery-explanation-row');
if(detailView.kind==='gnn_explanation'){
  renderNarrative(explanationRow,detailView.explanation);
  renderFactors(explanationRow,detailView.explanation);
}else{
  const note=recoveryElement(doc,'section','v9-recovery-panel');
  addText(note,'h5','','Structural evidence only');
  addText(note,'p','',
    'Community membership is observable context, not an attribution claim.');
  explanationRow.appendChild(note);
}
detail.appendChild(explanationRow);

const disclosures=recoveryElement(doc,'div','v9-recovery-disclosures');
if(detailView.kind==='gnn_explanation'){
  renderDisclosure(disclosures,'stability',
    'Restart stability and removal faithfulness',body=>
      renderStabilityAndFaithfulness(body,detailView.explanation));
  renderDisclosure(disclosures,'attribution',
    'Highest-attribution nodes and relationships',body=>
      body.appendChild(renderHighestAttributionPanel(doc,detailView.explanation)));
}
renderDisclosure(disclosures,'tables','Complete community data tables',body=>
  renderGraphTable(body,commands,record));
renderDisclosure(disclosures,'cohort','Recovery cohort context',body=>
  renderCohortContext(body,record));
detail.appendChild(disclosures);
```

Keep `renderRecordStatus(detail,record)` after the disclosures.

- [ ] **Step 6: Reset disclosure state only when the selected case changes**

At the start of `loadSelected`, after resetting selected factor/table pages, add:

```javascript
state.openDisclosures.clear();
```

Do not clear it in graph mode, stage, zoom, search, density, or table pagination branches.

- [ ] **Step 7: Add disclosure CSS**

```css
#tab-v9Results .v9-recovery-disclosure { overflow: hidden; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); }
#tab-v9Results .v9-recovery-disclosure-summary { min-height: 44px; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 11px 14px; color: var(--text1); font-size: 11px; font-weight: 600; cursor: pointer; list-style: none; transition: background .2s ease, color .2s ease, transform .2s ease; }
#tab-v9Results .v9-recovery-disclosure-summary::-webkit-details-marker { display: none; }
#tab-v9Results .v9-recovery-disclosure-summary::after { content: '+'; color: var(--accent-hover); font-family: 'JetBrains Mono', var(--font-mono), monospace; }
#tab-v9Results .v9-recovery-disclosure[open] .v9-recovery-disclosure-summary::after { content: '-'; }
#tab-v9Results .v9-recovery-disclosure-summary:hover { background: var(--elevated); }
#tab-v9Results .v9-recovery-disclosure-summary:active { transform: translateY(1px); }
#tab-v9Results .v9-recovery-disclosure-summary:focus-visible { outline: 2px solid var(--accent-hover); outline-offset: -2px; }
#tab-v9Results .v9-recovery-disclosure-body { padding: 0 14px 14px; }
```

- [ ] **Step 8: Run graph/disclosure and existing evidence tests**

Run:

```bash
rtk .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_mount_uses_graph_first_case_workspace_and_three_decimals \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_mount_puts_graph_before_open_prose_and_closed_technical_evidence \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_disclosure_state_is_preserved_on_render_and_reset_on_case_load \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_mount_renders_hybrid_technical_evidence_end_to_end \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_graph_exposes_accessible_names_and_a_table_fallback
```

Expected: PASS. The end-to-end test still sees all three tables in the DOM, now inside closed disclosures.

- [ ] **Step 9: Leave a Merget checkpoint**

Run:

```bash
rtk git diff --check -- \
  Documents/Data/scripts/v9_recovery_explainer_ui.py \
  tests/test_v9_recovery_explainer_ui.py
```

Expected: no whitespace errors.

## Task 5: Add composed loading, empty, error, and retry states

**Files:**
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py:2250-2580`
- Test: `tests/test_v9_recovery_explainer_ui.py:3082-3535`

- [ ] **Step 1: Add failing tests for the synchronous loading snapshot**

```python
def test_schema3_mount_uses_layout_skeletons_and_aria_busy_while_loading():
    rendered = _mount_schema3("h1", fetch_latency_ms=50)
    initial = rendered["initial"]
    classes = {node["className"] for node in initial["nodes"]}
    busy_regions = [
        node for node in initial["nodes"]
        if node["attrs"].get("aria-busy") == "true"
    ]

    assert "v9-recovery-loading" in classes
    assert "v9-recovery-skeleton is-graph" in classes
    assert "v9-recovery-skeleton is-copy" in classes
    assert len(busy_regions) == 1
    assert "Loading selected evidence" in " | ".join(initial["text"])
```

- [ ] **Step 2: Add failing tests for empty and error/retry states**

```python
def test_schema3_mount_renders_composed_empty_state_without_published_cases():
    artifact = _schema3_ui_artifact()
    artifact["detail_index"] = {}
    artifact["cohorts"]["hybrid_only"][0]["detail_status"] = "failed"
    rendered = _mount_schema3(None, (artifact, {}), expected_text="No published GNN explanations")
    text = " | ".join(rendered["text"])

    assert "No published GNN explanations are available in this artifact." in text
    assert "Recovery cohort context" in text


def test_schema3_mount_keeps_case_navigation_and_offers_retry_after_fetch_error():
    artifact, files = _schema3_served_bundle()
    missing_url = artifact["sidecar_base"] + artifact["detail_index"]["h1"]["path"]
    del files[missing_url]
    rendered = _mount_schema3(
        "h1", (artifact, files), expected_text="Retry evidence"
    )
    text = " | ".join(rendered["text"])
    classes = {node["className"] for node in rendered["nodes"]}

    assert "v9-recovery-v3-list" in classes
    assert "v9-recovery-error" in classes
    assert "Retry evidence" in text
    assert "As-of community context + explanation evidence" not in text
```

- [ ] **Step 3: Run the state tests and verify they fail**

Run:

```bash
rtk .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_mount_uses_layout_skeletons_and_aria_busy_while_loading \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_mount_renders_composed_empty_state_without_published_cases \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_mount_keeps_case_navigation_and_offers_retry_after_fetch_error
```

Expected: FAIL because the current UI uses one text status for loading, a generic filter empty state, and no retry action.

- [ ] **Step 4: Add loading and error render helpers**

```javascript
function renderLoading(detail){
  detail.setAttribute('aria-busy','true');
  const loading=recoveryElement(doc,'section','v9-recovery-loading');
  loading.setAttribute('role','status');
  addText(loading,'span','v9-recovery-sr-only','Loading selected evidence');
  loading.appendChild(recoveryElement(doc,'div','v9-recovery-skeleton is-graph'));
  loading.appendChild(recoveryElement(doc,'div','v9-recovery-skeleton is-copy'));
  loading.appendChild(recoveryElement(doc,'div','v9-recovery-skeleton is-copy is-short'));
  detail.appendChild(loading);
}

function renderError(detail,error){
  detail.setAttribute('aria-busy','false');
  const panel=recoveryElement(doc,'section','v9-recovery-error');
  panel.setAttribute('role','alert');
  addText(panel,'h4','','Selected evidence could not be loaded');
  addText(panel,'p','',recoveryServerHelp(error));
  const retry=recoveryElement(doc,'button','v9-recovery-button v9-recovery-retry',
    'Retry evidence');
  retry.type='button';retry.dataset.v3Retry='true';
  retry.setAttribute('aria-label','Retry selected GNN evidence');
  panel.appendChild(retry);detail.appendChild(panel);
}
```

At the start of `renderSelectedEvidence`:

```javascript
if(state.error){renderError(detail,state.error);return;}
if(state.loading){renderLoading(detail);return;}
detail.setAttribute('aria-busy','false');
```

- [ ] **Step 5: Add retry to existing event delegation**

Extend the delegated selector with `[data-v3-retry]` and handle it before graph actions:

```javascript
if(data.v3Retry){loadSelected();return;}
```

Do not create a second click listener.

- [ ] **Step 6: Render the composed empty state**

When `rows.length===0`, do not render an empty rail/detail pair. Render the valid heading, one empty-state panel, and a closed cohort-context disclosure:

```javascript
if(!rows.length){
  const empty=recoveryElement(doc,'section','v9-recovery-empty-state');
  addText(empty,'h4','','No published GNN explanations are available in this artifact.');
  addText(empty,'p','',
    'The recovery summary remains available, but no case has validated published explanation detail.');
  const disclosures=recoveryElement(doc,'div','v9-recovery-disclosures');
  renderDisclosure(disclosures,'cohort','Recovery cohort context',body=>
    renderCohortContext(body,null));
  empty.appendChild(disclosures);fragment.appendChild(empty);
  root.replaceChildren(fragment);return;
}
```

- [ ] **Step 7: Add state CSS with reduced-motion protection**

```css
#tab-v9Results .v9-recovery-loading { display: grid; gap: 12px; min-height: 520px; padding: 14px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); }
#tab-v9Results .v9-recovery-skeleton { border-radius: 7px; background: var(--elevated); animation: v9-recovery-pulse 1.4s ease-in-out infinite; }
#tab-v9Results .v9-recovery-skeleton.is-graph { min-height: 390px; }
#tab-v9Results .v9-recovery-skeleton.is-copy { min-height: 54px; }
#tab-v9Results .v9-recovery-skeleton.is-short { width: 64%; }
#tab-v9Results .v9-recovery-error, #tab-v9Results .v9-recovery-empty-state { padding: 24px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); color: var(--text2); }
#tab-v9Results .v9-recovery-error h4, #tab-v9Results .v9-recovery-empty-state h4 { margin: 0 0 8px; color: var(--text1); font-size: 15px; }
#tab-v9Results .v9-recovery-retry { margin-top: 12px; }
#tab-v9Results .v9-recovery-sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
@keyframes v9-recovery-pulse { 0%,100% { opacity: 1; } 50% { opacity: .55; } }
@media(prefers-reduced-motion: reduce){
  #tab-v9Results .v9-recovery-skeleton { animation: none; }
}
```

- [ ] **Step 8: Run state, fail-closed, stale-request, and lifecycle tests**

Run:

```bash
rtk .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_mount_uses_layout_skeletons_and_aria_busy_while_loading \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_mount_renders_composed_empty_state_without_published_cases \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_mount_keeps_case_navigation_and_offers_retry_after_fetch_error \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_detail_rejects_invalid_as_of_evidence_boundary \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_mount_discards_stale_responses_and_reports_failures \
  tests/test_v9_recovery_explainer_ui.py::test_ui_javascript_is_valid_and_has_no_rendering_side_effects
```

Expected: PASS.

- [ ] **Step 9: Leave a Merget checkpoint**

Run:

```bash
rtk git diff --check -- \
  Documents/Data/scripts/v9_recovery_explainer_ui.py \
  tests/test_v9_recovery_explainer_ui.py
```

Expected: no whitespace errors.

## Task 6: Integrate, document, rebuild, and prove artifact preservation

**Files:**
- Modify: `tests/test_v9_dashboard_builder.py:1585-1625`
- Modify: `Documents/Data/changes_3.md`
- Modify: `PROJECT_MEMORY.md`
- Verify generated: `Documents/Data/v9_dashboard/index.html`
- Verify generated: `Documents/Data/v9_dashboard/data_v9.json`

- [ ] **Step 1: Strengthen the builder asset contract**

Update `test_recovery_assets_include_readable_explanation_contract`:

```python
def test_recovery_assets_include_graph_first_explanation_contract():
    from Documents.Data.scripts import v9_recovery_explainer_ui as recovery_ui

    template = (
        "<style>base</style><script>const Tabs={\n"
        "explorer:{rendered:false,render(){}}\n};</script>"
    )
    injected = BUILDER._inject_recovery_assets(
        template,
        recovery_ui.V9_RECOVERY_EXPLAINER_CSS,
        recovery_ui.V9_RECOVERY_EXPLAINER_JS,
    )

    assert "recoveryFormatNumber" in injected
    assert "v9-recovery-title" in injected
    assert "v9-recovery-v3-picker" in injected
    assert "v9-recovery-graph-panel" in injected
    assert "Retry evidence" in injected
    assert "Why case " in injected
```

- [ ] **Step 2: Run focused builder integration tests**

Run:

```bash
rtk .venv/bin/python -m pytest -q \
  tests/test_v9_dashboard_builder.py::test_v9_results_mounts_recovery_explorer_in_the_approved_story_position \
  tests/test_v9_dashboard_builder.py::test_recovery_assets_include_graph_first_explanation_contract \
  tests/test_v9_dashboard_builder.py::test_recovery_assets_precede_renderer_that_mounts_them
```

Expected: PASS. No `v9_dashboard_ui.py` or builder source change is required because the mount already uses `aria-labelledby="v9-recovery-title"`.

- [ ] **Step 3: Run the complete focused source suites**

Run:

```bash
rtk .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py \
  tests/test_v9_dashboard_builder.py \
  tests/test_v9_design_system.py
```

Expected: all tests PASS. If `tests/test_recovery_layout_parity.py` is run separately, treat its existing `DISPLAY_LAYOUT_RADIUS` collection failure as unrelated unless this task changes that result.

- [ ] **Step 4: Compile the changed Python generators and validate generated JavaScript**

Run:

```bash
rtk .venv/bin/python -m py_compile \
  Documents/Data/scripts/v9_recovery_explainer_ui.py \
  Documents/Data/scripts/v9_dashboard_ui.py \
  Documents/Data/scripts/build_v9_dashboard.py
rtk .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py::test_ui_javascript_is_valid_and_has_no_rendering_side_effects
```

Expected: compilation succeeds and the JavaScript syntax test PASSes.

- [ ] **Step 5: Record immutable source-artifact hashes before rebuild**

Run:

```bash
rtk shasum -a 256 \
  v9_schema3_results.zip \
  gnn/diagnostics/demo_comparison_v9.json \
  gnn/diagnostics/unsupervised_ad_results_v9.json
```

Expected: three hashes are printed. Keep the output in the execution transcript for comparison; do not write a new hash file.

- [ ] **Step 6: Rebuild the generated dashboard**

Run:

```bash
rtk .venv/bin/python Documents/Data/scripts/build_v9_dashboard.py
```

Expected: the command reports updated `Documents/Data/v9_dashboard/data_v9.json` and `index.html` and exits successfully.

- [ ] **Step 7: Re-run immutable artifact hashes and compare exactly**

Run the same command from Step 5.

Expected: every hash exactly matches the pre-build value.

- [ ] **Step 8: Serve and visually inspect desktop and narrow layouts**

Run the local dashboard server:

```bash
rtk .venv/bin/python -m http.server 8000 \
  --bind 127.0.0.1 \
  --directory Documents/Data/v9_dashboard
```

Open `http://localhost:8000/index.html#v9Results` with the available local browser workflow. Inspect at 1440px and 390px viewport widths.

Desktop acceptance:

- selected-case header and ranks appear before navigation/detail;
- 214px case rail is bounded, sticky, and independently scrollable;
- graph is the largest surface and precedes narrative;
- narrative/factors are open and readable;
- four technical disclosures are closed by default;
- no standalone “Showing GNN explanations only” strip remains.

Narrow acceptance:

- native case picker replaces the rail;
- graph uses the full content width;
- toolbar controls wrap into touch-sized tracks;
- narrative/factors stack;
- there is no page-level horizontal scrolling;
- rank strip remains three columns at 390px.

Interaction acceptance:

- case selection updates the selected explanation and resets disclosures;
- graph mode/stage/zoom/search/density keep open disclosures open;
- loading skeleton appears without hiding case navigation;
- a forced sidecar failure keeps navigation visible and exposes Retry evidence;
- keyboard focus rings and canvas/table fallback remain usable.

- [ ] **Step 9: Document the completed change**

Append a concise section to `Documents/Data/changes_3.md` containing:

```markdown
## 2026-08-05: Graph-first GNN explanation workspace

- Reorganized the schema-3 explanation explorer around the selected case: full-width case/rank context, bounded explanation rail, large graph workspace, then readable narrative and measured factors.
- Moved stability, faithfulness, attribution, complete graph tables, and cohort metrics into accessible state-preserving disclosures.
- Added responsive case-picker behavior plus composed loading, empty, and retryable error states.
- Preserved explained-only eligibility, SHA-256 sidecar verification, strict as-of fail-closed behavior, graph semantics, artifacts, and evaluation logic.
```

Append a durable note to `PROJECT_MEMORY.md`:

```markdown
## 2026-08-05: GNN explanation workspace hierarchy

- The schema-3 explanation view is graph-first: selected case and ranks lead, the graph is the primary surface, narrative/factors follow, and dense technical evidence is closed by default.
- The published-artifact, strict as-of, explained-only eligibility, and graph/table contracts remain unchanged; future UI work should preserve this boundary.
```

- [ ] **Step 10: Run final verification and scoped diff review**

Run:

```bash
rtk .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py \
  tests/test_v9_dashboard_builder.py \
  tests/test_v9_design_system.py
rtk git diff --check
rtk git status --short
rtk git diff --stat -- \
  Documents/Data/scripts/v9_recovery_explainer_ui.py \
  tests/test_v9_recovery_explainer_ui.py \
  tests/test_v9_dashboard_builder.py \
  Documents/Data/changes_3.md \
  PROJECT_MEMORY.md
```

Expected:

- focused suites PASS;
- `git diff --check` reports no errors;
- no source artifact, ZIP, corpus, model, or evaluation file changed because of this redesign;
- scoped diff contains only the approved UI, tests, and documentation work layered on the existing Merget changes.

- [ ] **Step 11: Leave the final Merget checkpoint for Historian**

Do not run a manual commit. Report the exact test counts, artifact hash comparison, visual inspection results, and changed-file list to the orchestrator so Merget Historian can record the completed prompt.
