# V9 Dashboard Demo Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the V9 dashboard demo-ready: fresh build, no dead-end evidence clicks, persuasive charts (cumulative catches, no dual axis, smoothing), narrative-ordered V9 tab, a visual summary for the anomaly tab, one-click explorer presets, and label polish.

**Architecture:** All V9-tab UI lives as Python string constants in `Documents/Data/scripts/v9_dashboard_ui.py` and `v9_recovery_explainer_ui.py`, spliced into the corpus template by `build_v9_dashboard.py`. The Community Explorer lives in `explorer_ui.py`, spliced by `build_dashboard.py`. Pure JS view-model helpers are unit-tested by executing them under `node` from pytest (existing pattern). Rendering changes are verified by string-contract tests plus a final headless-Chrome screenshot pass.

**Tech Stack:** Python 3.14 (`.venv`), pytest, Node v26 (for JS view-model tests), headless Google Chrome for screenshots.

## Global Constraints

- Run tests with: `source .venv/bin/activate && PYTHONPATH=. pytest -q tests`
- Rebuild dashboard with: `.venv/bin/python Documents/Data/scripts/build_v9_dashboard.py` (requires `Documents/Data/synthetic_cbp_graph_corpus_v9/dashboard_standalone.html` and `dashboard_data.json` to exist locally).
- Serve for viewing: `python3 -m http.server 8000 --directory Documents/Data/v9_dashboard`
- Do NOT touch scoring/eval logic (`gnn/learned_cell.py`, `gnn/demo_baseline.py`, `gnn/graphmodel_rgcn.py`). Leak-free as-of semantics must stay untouched.
- Do NOT reorganize `Documents/Data/` paths.
- Injection markers must survive every edit: `const Tabs={`, `explorer:{rendered:false,render(){`, `<!-- V9_NAV_TABS -->`, `<!-- V9_TAB_SECTIONS -->`, and the tooltip bootstrap block replaced by `_make_d3_optional`.
- `_validate_recovery_explorer_mount` (build_v9_dashboard.py:343) requires each of `href="#v9-case-evidence"`, `id="v9-case-evidence"`, `DATA.v9RecoveryExplainer` to appear **exactly once** in the built HTML. Never add a second `href="#v9-case-evidence"`.
- Tests pin the label string `Deployable Hybrid` (test_v9_dashboard_builder.py:129,260,1694). Keep that label.
- Screenshot method (for visual verification): copy `Documents/Data/v9_dashboard/` into the session scratchpad, serve it on a port, then
  `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars --window-size=1440,9500 --virtual-time-budget=15000 --screenshot=<out.png> "http://localhost:<port>/index.html#tab-<name>"`
  Tab names: `v9Results`, `unsupervisedAD`, `explorer`, `overview`.

---

### Task 1: Rebuild the stale dashboard

The published `Documents/Data/v9_dashboard/index.html` predates the current `v9_dashboard_ui.py` (it still says "more hidden carriers at K=", the current code says "hidden-positive event hits"). Rebuild before anything else so the demo baseline is current.

**Files:**
- No source changes. Regenerates `Documents/Data/v9_dashboard/index.html` and `data_v9.json`.

- [ ] **Step 1: Confirm staleness**

Run: `grep -c 'hidden-positive event hits' Documents/Data/v9_dashboard/index.html`
Expected: `0`

- [ ] **Step 2: Rebuild**

Run: `.venv/bin/python Documents/Data/scripts/build_v9_dashboard.py`
Expected: `[v9-dashboard] wrote .../index.html` with no traceback. WARNINGs about generic unsupervised artifacts are acceptable; ERRORs are not.

- [ ] **Step 3: Verify freshness**

Run: `grep -c 'hidden-positive event hits' Documents/Data/v9_dashboard/index.html && grep -c 'more hidden carriers at K=' Documents/Data/v9_dashboard/index.html`
Expected: first count ≥ 1, second count `0`.

- [ ] **Step 4: Run the test suite to establish a green baseline**

Run: `PYTHONPATH=. pytest -q tests`
Expected: all pass (record any pre-existing failures before continuing).

*(No commit — generated artifacts; check `git check-ignore Documents/Data/v9_dashboard/index.html` and only commit if the repo already tracks it.)*

---

### Task 2: Recovery case list — explained-first ordering, evidence badges, no dead-end default

Today only 1 of 593 hybrid-only cases has a validated explanation, and the default-selected case renders "No validated explanation is available for this case." Make explained cases sort first (so the default selection always lands on one), badge them, and add an evidence filter.

**Files:**
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py` (function `filterAndSortRecoveryCases` ~line 300; case-list renderer ~line 1556; filter controls near the existing sort/stable/relationship selects ~line 1540; CSS block near line 28)
- Test: `tests/test_v9_recovery_explainer_ui.py` (node harness `_run_ui` at line 634)

**Interfaces:**
- Produces: `filterAndSortRecoveryCases(cases, options)` gains two optional keys: `options.explainedIds` (array of case_id strings) and `options.evidence` (`'all'` | `'explained'`). With `explainedIds` present, explained cases sort before unexplained ones; within each group the existing sort keys apply unchanged. With `evidence:'explained'`, unexplained cases are filtered out. Omitting both keys reproduces today's behavior exactly.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_v9_recovery_explainer_ui.py` (reuse `_run_ui` and the case-shape helpers already in the file; build two valid cases `case:p1` explained, `case:p2` unexplained where `p2` has the higher `hybrid_rank_uplift`):

```python
def test_filter_sorts_explained_cases_first_when_ids_supplied():
    low_uplift_explained = _case("case:p1", "p1", hybrid_rank_uplift=10)
    high_uplift_unexplained = _case("case:p2", "p2", hybrid_rank_uplift=90)
    result = _run_ui(
        "filterAndSortRecoveryCases",
        [high_uplift_unexplained, low_uplift_explained],
        {"explainedIds": ["case:p1"]},
    )
    assert [item["case_id"] for item in result] == ["case:p1", "case:p2"]


def test_filter_evidence_only_drops_unexplained_cases():
    result = _run_ui(
        "filterAndSortRecoveryCases",
        [_case("case:p1", "p1"), _case("case:p2", "p2")],
        {"explainedIds": ["case:p1"], "evidence": "explained"},
    )
    assert [item["case_id"] for item in result] == ["case:p1"]


def test_filter_without_new_options_keeps_legacy_order():
    low = _case("case:p1", "p1", hybrid_rank_uplift=10)
    high = _case("case:p2", "p2", hybrid_rank_uplift=90)
    result = _run_ui("filterAndSortRecoveryCases", [high, low], {})
    assert [item["case_id"] for item in result] == ["case:p2", "case:p1"]
```

If the file has no `_case` helper, add one that copies the case dict shape from `_valid_recovery_artifact` (line ~49) with overridable `case_id`, `person_id`, `hybrid_rank_uplift`.

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `PYTHONPATH=. pytest -q tests/test_v9_recovery_explainer_ui.py -k "explained or legacy_order"`
Expected: first two FAIL (ordering/filtering not implemented), third PASSES.

- [ ] **Step 3: Implement in `filterAndSortRecoveryCases`**

```js
function filterAndSortRecoveryCases(cases,options){
  if(!Array.isArray(cases)) return [];
  const settings=recoveryIsRecord(options)?options:{};
  const stable=recoveryNonBlankString(settings.stableStatus)
    ?settings.stableStatus:'all';
  const relation=recoveryNonBlankString(settings.relationshipCategory)
    ?settings.relationshipCategory:'all';
  const allowedSorts=['hybrid_rank_uplift','gnn_percentile_uplift'];
  const sortBy=allowedSorts.includes(settings.sortBy)
    ?settings.sortBy:'hybrid_rank_uplift';
  const explainedIds=Array.isArray(settings.explainedIds)
    ?new Set(settings.explainedIds.filter(recoveryNonBlankString)):null;
  const evidence=settings.evidence==='explained'&&explainedIds?'explained':'all';
  return cases.filter(item=>recoveryValidCase(item)
      &&(stable==='all'||item.stable_factor_status===stable)
      &&(relation==='all'||item.relationship_categories.includes(relation))
      &&(evidence==='all'||explainedIds.has(item.case_id)))
    .slice()
    .sort((left,right)=>
      (explainedIds?Number(explainedIds.has(right.case_id))
        -Number(explainedIds.has(left.case_id)):0)
      ||right[sortBy]-left[sortBy]
      ||right.hybrid_rank_uplift-left.hybrid_rank_uplift
      ||recoveryCompareId(left.person_id,right.person_id)
      ||recoveryCompareId(left.case_id,right.case_id));
}
```

- [ ] **Step 4: Wire the renderer**

In the schema-1 renderer (state init ~line 1436, case-list build ~line 1556):
1. Wherever the case list is computed, pass `explainedIds:Array.from(view.explanations.keys())` and `evidence:state.evidence` in the options object.
2. Add `evidence:'all'` to the `state` literal at line ~1437.
3. Add an "Evidence" select alongside the existing sort/stable/relationship selects (copy the existing select-building pattern in that section) with options `{value:'all',label:'All cases'}` and `{value:'explained',label:'Validated evidence only'}`, writing `state.evidence` and re-rendering on change.
4. In the case-button builder (~line 1560), after the `v9-recovery-case-meta` element, append a badge when explained:

```js
if(view.explanations.has(item.case_id)){
  button.appendChild(recoveryElement(
    doc,'div','v9-recovery-case-evidence','✓ evidence'
  ));
}
```

5. Add CSS next to the other `.v9-recovery-case-*` rules:

```css
#tab-v9Results .v9-recovery-case-evidence { margin-top: 4px; color: var(--accent-hover); font-size: 10px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
```

- [ ] **Step 5: Run the full recovery UI test file**

Run: `PYTHONPATH=. pytest -q tests/test_v9_recovery_explainer_ui.py`
Expected: PASS (if an existing test snapshots select markup or case-button DOM, update it to include the new control/badge — that is the only acceptable change to existing assertions).

- [ ] **Step 6: Rebuild + eyeball**

Rebuild, screenshot `#tab-v9Results`, confirm: default-selected case shows measured factors (not the empty message), explained case is at the top of the list with a `✓ evidence` badge.

- [ ] **Step 7: Commit**

```bash
git add Documents/Data/scripts/v9_recovery_explainer_ui.py tests/test_v9_recovery_explainer_ui.py
git commit -m "feat: surface validated recovery evidence first in case explorer"
```

---

### Task 3: Regenerate the recovery artifact with more explained cases

Coverage today: `explanation_limit=1`, 10 attempts, 9 failures ("pooled component size N exceeds maximum explainable component size 6" — most top-uplift cases live in the giant co-travel component). Raising the limit walks further down the case list and collects more small-component successes. **This task is compute-heavy and requires the local Gemma narrative runner; it can run in the background while Tasks 4–9 proceed. If the narrative preflight fails, stop this task and report — Task 2 already guarantees the demo never shows a dead end.**

**Files:**
- Regenerates: `gnn/diagnostics/hybrid_recovery_explanations_v9.json`

- [ ] **Step 1: Identify a compatible checkpoint**

Run: `grep -n "read_demo_checkpoint_metadata" gnn/run_demo.py | head -3` to find the import source, then:

```bash
PYTHONPATH=. .venv/bin/python - <<'EOF'
from pathlib import Path
from gnn.run_demo import read_demo_checkpoint_metadata
for p in sorted(Path('gnn/diagnostics/checkpoints').iterdir()):
    try:
        m = read_demo_checkpoint_metadata(p)
        print(p.name, m['run']['gnn_arm'], m['run']['seeds'])
    except Exception as e:
        print(p.name, 'unreadable:', e)
EOF
```

Expected: at least one checkpoint with `sage [0, 1, 2]`. (Adjust the import if `read_demo_checkpoint_metadata` lives in another module — copy whatever import `gnn/run_demo.py` itself uses.)

- [ ] **Step 2: Regenerate with a higher limit**

```bash
PYTHONPATH=. CBP_CORPUS_DIR=$PWD/Documents/Data/synthetic_cbp_graph_corpus_v9 \
.venv/bin/python -c "
from gnn.run_demo import resume_observability
resume_observability('gnn/diagnostics/checkpoints/<CHECKPOINT_ID>', explanation_limit=None)"
```

**Execution correction (2026-07-19):** the plan originally said `explanation_limit=6`, but current `gnn/observability_artifact.py` raises `ValueError("explanation_limit must cover the complete Hybrid-only cohort")` for any limit below the full cohort size (593). The production mode is complete-cohort coverage; `None` selects it. Component-size failures are cheap ValueErrors, so the walk over 593 cases is dominated by the successful explanations' narrative validation.

Expected: completes without traceback. If `preflight_narrative_contract` fails (no local Gemma), STOP this task and report the blocker.

- [ ] **Step 3: Verify coverage improved**

```bash
python3 -c "
import json
d = json.load(open('gnn/diagnostics/hybrid_recovery_explanations_v9.json'))
print(d['coverage'])"
```

Expected: `explained_count >= 2` (target 6; every explained case is one more demo story).

- [ ] **Step 4: Rebuild dashboard and confirm the explorer shows the new cases**

Rebuild, screenshot, confirm multiple `✓ evidence` badges.

*(No commit — diagnostics artifacts are generated data; commit only if the repo tracks this file: check `git ls-files gnn/diagnostics/`.)*

---

### Task 4: Cumulative view for the simulated-catches chart

Two jagged daily lines (0–7/day over 273 days) hide the 912-vs-502 story. Add cumulative series to the view model and a Cumulative/Daily toggle defaulting to **Cumulative**.

**Files:**
- Modify: `Documents/Data/scripts/v9_dashboard_ui.py` (`SIMULATED_CATCH_VIEW_MODEL_JS` line ~143; `drawSimulatedCatches` line ~381; `V9_RESULTS_CSS`)
- Test: `tests/test_v9_dashboard_builder.py` (harness `_run_simulated_view_model` line 55)

**Interfaces:**
- Produces: `buildSimulatedCatchViewModel(sim, requestedBudget)` return value gains `cumulativeByArm` (per-arm running sums of `valuesByArm`), `cumulativeMaxY` (≥1 integer ceiling), `cumulativeTicks` (deduped 4-step ticks). Existing keys unchanged.

- [ ] **Step 1: Write failing test**

```python
def test_simulated_view_model_reports_cumulative_series():
    baseline = _simulated_arm({5: [
        {"date": "2025-01-01", "found": 1},
        {"date": "2025-01-02", "found": 0},
        {"date": "2025-01-03", "found": 2},
    ]})
    hybrid = _simulated_arm({5: [
        {"date": "2025-01-01", "found": 2},
        {"date": "2025-01-02", "found": 3},
        {"date": "2025-01-03", "found": 1},
    ]})
    view = _run_simulated_view_model(
        {"arms": {"baseline": baseline, "hybrid": hybrid}}, 5
    )
    assert view["cumulativeByArm"] == {
        "baseline": [1, 1, 3],
        "hybrid": [2, 5, 6],
    }
    assert view["cumulativeMaxY"] == 6
    assert view["cumulativeTicks"] == [0, 2, 4, 6]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=. pytest -q tests/test_v9_dashboard_builder.py -k cumulative`
Expected: FAIL (`KeyError: 'cumulativeByArm'`).

- [ ] **Step 3: Implement in the view model**

In `SIMULATED_CATCH_VIEW_MODEL_JS`, after `valuesByArm` is built and before the `return`:

```js
const cumulativeByArm=Object.fromEntries(arms.map(a=>{
  let total=0;
  return [a,valuesByArm[a].map(value=>(total+=value))];
}));
const cumulativeMax=Math.max(1,...arms.map(a=>cumulativeByArm[a][cumulativeByArm[a].length-1]||0));
const cumulativeMaxY=Math.max(1,Math.ceil(cumulativeMax));
const cumulativeTicks=Array.from(new Set(Array.from({length:4},(_,i)=>Math.round(cumulativeMaxY*i/3))));
```

and add `cumulativeByArm,cumulativeMaxY,cumulativeTicks` to the returned object.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest -q tests/test_v9_dashboard_builder.py -k simulated`
Expected: PASS (all simulated view-model tests, old and new).

- [ ] **Step 5: Add the toggle to `drawSimulatedCatches`**

1. Next to the other per-tab state (`let pop='observable';` line ~229) add `let simMode='cumulative';`.
2. In the simulated section header (inside the big `sec.innerHTML` template, `id="v9-simulated-catches"` block), add before the select:
   `'<div class="v9-seg v9-seg-small" id="v9-simulated-mode" role="group" aria-label="Simulated chart mode"><button data-v="cumulative" class="on" aria-pressed="true">Cumulative</button><button data-v="daily" aria-pressed="false">Daily</button></div>'`
3. At the top of `drawSimulatedCatches`, wire it once (guard with a `dataset.wired` flag):

```js
const modeSeg=document.getElementById('v9-simulated-mode');
if(modeSeg&&!modeSeg.dataset.wired){
  modeSeg.dataset.wired='1';
  modeSeg.addEventListener('click',e=>{
    const b=e.target.closest('button'); if(!b) return;
    simMode=b.dataset.v;
    modeSeg.querySelectorAll('button').forEach(x=>{const on=x===b;x.classList.toggle('on',on);x.setAttribute('aria-pressed',String(on));});
    drawSimulatedCatches();
  });
}
```

4. Select series by mode where the chart is drawn:

```js
const plotByArm=simMode==='cumulative'?view.cumulativeByArm:view.valuesByArm;
const plotMaxY=simMode==='cumulative'?view.cumulativeMaxY:view.foundMaxY;
const plotTicks=simMode==='cumulative'?view.cumulativeTicks:view.yTicks;
const yAxisTitle=simMode==='cumulative'?'total unique people caught':'new unique people / day';
```

Replace uses of `valuesByArm`/`foundMaxY`/`view.yTicks` in the line/point/rule/table construction with `plotByArm`/`plotMaxY`/`plotTicks`, and the `<text x=... y="12">` axis title with `yAxisTitle`. The accessible table and tooltip must show the plotted values (cumulative in cumulative mode).
5. CSS: `#tab-v9Results .v9-seg-small { margin: 0; padding: 3px; } #tab-v9Results .v9-seg-small button { padding: 4px 10px; font-size: 12px; }`

- [ ] **Step 6: Full test run + rebuild + eyeball**

Run: `PYTHONPATH=. pytest -q tests/test_v9_dashboard_builder.py`
Expected: PASS. If `test_v9_ui_adds_independent_simulated_catch_contract` or the sr-table test pins the old header markup, update only the pinned strings to include the new toggle. Rebuild + screenshot: cumulative default shows two diverging curves ending at the arm totals.

- [ ] **Step 7: Commit**

```bash
git add Documents/Data/scripts/v9_dashboard_ui.py tests/test_v9_dashboard_builder.py
git commit -m "feat: cumulative simulated-catch chart with daily toggle"
```

---

### Task 5: Replace the dual-axis daily chart with stacked panels + 7-day smoothing

`drawCombined` (v9_dashboard_ui.py line ~341) overlays crossings (left axis) and model hits (right axis) as raw daily lines. Split into two stacked panels sharing the x-axis, and plot 7-day trailing means bold with raw lines faint.

**Files:**
- Modify: `Documents/Data/scripts/v9_dashboard_ui.py` (`drawCombined`, `V9_RESULTS_CSS`; add `rollingMean` helper next to `SIMULATED_CATCH_VIEW_MODEL_JS` so it is injected before the Tabs registry via the existing `_inject_dashboard_tab_scripts` helper argument)
- Test: `tests/test_v9_dashboard_builder.py`

**Interfaces:**
- Produces: `rollingMean(values, windowSize)` — trailing mean over up to `windowSize` points ending at each index; returns `[]` for invalid input (non-array, window < 1, non-finite entries).

- [ ] **Step 1: Write failing tests**

Add a node harness mirroring `_run_simulated_view_model` (line 55) that evaluates `UI.SIMULATED_CATCH_VIEW_MODEL_JS + UI.ROLLING_MEAN_JS` — define `ROLLING_MEAN_JS` as its own module constant so tests can target it:

```python
def _run_rolling_mean(values, window):
    script = (
        UI.ROLLING_MEAN_JS
        + f"\nprocess.stdout.write(JSON.stringify(rollingMean({json.dumps(values)},{window})));"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def test_rolling_mean_trailing_window():
    assert _run_rolling_mean([2, 4, 6, 8], 2) == [2, 3, 5, 7]
    assert _run_rolling_mean([1, 2, 3], 7) == [1, 1.5, 2]


def test_rolling_mean_rejects_invalid_input():
    assert _run_rolling_mean([1, "x", 3], 2) == []
    assert _run_rolling_mean([1, 2], 0) == []
```

(`UI` here is the imported `v9_dashboard_ui` module — follow the file's existing import at the top.)

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=. pytest -q tests/test_v9_dashboard_builder.py -k rolling`
Expected: FAIL (`AttributeError: ROLLING_MEAN_JS`).

- [ ] **Step 3: Implement `ROLLING_MEAN_JS`**

```python
ROLLING_MEAN_JS = r"""
  function rollingMean(values,windowSize){
    if(!Array.isArray(values)||!Number.isInteger(windowSize)||windowSize<1) return [];
    if(!values.every(v=>Number.isFinite(v))) return [];
    let sum=0;
    return values.map((value,i)=>{
      sum+=value;
      if(i>=windowSize) sum-=values[i-windowSize];
      return sum/Math.min(i+1,windowSize);
    });
  }
"""
```

Concatenate it where `SIMULATED_CATCH_VIEW_MODEL_JS` is already spliced into `V9_RESULTS_JS` (line ~380: `""" + SIMULATED_CATCH_VIEW_MODEL_JS + r"""` → also `+ ROLLING_MEAN_JS +`).

- [ ] **Step 4: Run to verify pass**

Run: `PYTHONPATH=. pytest -q tests/test_v9_dashboard_builder.py -k rolling`
Expected: PASS.

- [ ] **Step 5: Rewrite `drawCombined` as stacked panels**

Keep: data assembly (`points`, budget select wiring, `byArm`, `valuesByArm`, toggles, `modelVisibility`/`layerVisibility`, hover index math, tooltip, summary stat tiles). Replace the single-plot geometry with two panels in one SVG:

```js
const dates=points.map(d=>d.date), width=720, left=58, right=20, top=20;
const crossH=72, gap=34, modelH=170, bottom=42;
const height=top+crossH+gap+modelH+bottom, chartW=width-left-right;
const crossings=points.map(d=>d.value);
const crossingsSmooth=rollingMean(crossings,7);
const smoothByArm=Object.fromEntries(arms.map(a=>[a,rollingMean(valuesByArm[a],7)]));
const crossingMaxY=Math.max(1,Math.ceil(Math.max.apply(null,crossings)/10)*10);
const foundMaxY=Math.max(1,Math.ceil(Math.max(1,...arms.flatMap(a=>valuesByArm[a]))));
const x=i=>left+(dates.length===1?chartW/2:i*chartW/(dates.length-1));
const yCross=v=>top+crossH-(v/crossingMaxY)*crossH;
const yModel=v=>top+crossH+gap+modelH-(v/foundMaxY)*modelH;
```

- Top panel: crossings raw as `v9-volume-area` fill + raw line at `opacity:.35`, smoothed line bold (`v9-volume-line`), panel title `<text>` "crossing events / day (7-day average, faint = daily)". Two y-ticks (0 and `crossingMaxY`).
- Bottom panel: per arm, raw daily polyline with class `v9-found-chart-line <arm> is-raw` (CSS `opacity:.22;stroke-width:1.5`) plus smoothed polyline `v9-found-chart-line <arm>` (existing bold style). Panel title "hidden-positive event hits / day (7-day average)". Ticks from `foundMaxY` as today.
- One hover guide line spanning `y1=top` to `y2=top+crossH+gap+modelH`; hover dots sit on the **smoothed** lines; tooltip shows date, daily crossings, budget, and each visible arm's daily value (raw, since that's the operational number).
- `updateVisibility` keeps working: crossings toggle hides the whole top-panel group `<g class="v9-crossings-layer">`; arm toggles hide both raw and smooth polylines for that arm (both carry the arm class, so the existing `querySelectorAll('.v9-found-chart-line.'+a)` selector still matches).
- x-axis date ticks once, under the bottom panel.

- [ ] **Step 6: Full test run; update layout-pinned assertions only**

Run: `PYTHONPATH=. pytest -q tests/test_v9_dashboard_builder.py`
`test_v9_ui_includes_model_daily_catch_chart` (line 123) and `test_v9_ui_keeps_daily_volume_and_simulated_catches_independent` (line 293) may pin markup from the old single-plot layout — update only geometry/markup assertions; semantic assertions (series present, budget select, toggles) must pass unmodified.

- [ ] **Step 7: Rebuild + eyeball**

Screenshot `#tab-v9Results`: two clean panels, smoothed hybrid line visibly above baseline, no right-hand second axis.

- [ ] **Step 8: Commit**

```bash
git add Documents/Data/scripts/v9_dashboard_ui.py tests/test_v9_dashboard_builder.py
git commit -m "feat: split daily volume chart into stacked panels with 7-day smoothing"
```

---

### Task 6: Reorder the V9 tab, fix the evidence-link hash bug, add jump nav, collapse the appendix

Two changes to `sec.innerHTML` in `V9_RESULTS_JS` (line ~232) plus one bug fix.

**The hash bug (fix first):** the headline link `<a class="v9-summary-link" href="#v9-case-evidence">` sets `location.hash`; the template's `hashchange` listener runs `switchTab(tabFromHash())`, and since `v9-case-evidence` is not a tab it falls back to **switching to the Overview tab**. Clicking the headline link mid-demo yanks the presenter off the results tab.

**New section order:** title/sub → jump nav → headline summary → metrics row → three lenses → "Baseline vs Hybrid vs GNN" (pop toggle + depth recall + daily capacity) → case evidence → charts card → model notes card → bootstrap appendix in `<details>`.

**Files:**
- Modify: `Documents/Data/scripts/v9_dashboard_ui.py` (`V9_RESULTS_JS`, `V9_RESULTS_CSS`)
- Test: `tests/test_v9_dashboard_builder.py` (`test_v9_results_mounts_recovery_explorer_in_the_approved_story_position` line 493 pins the OLD order — update it to pin the NEW order; that is a deliberate, approved change)

- [ ] **Step 1: Fix the hash bug**

After `sec.innerHTML=...` is assigned (near the `mountV9RecoveryExplainer` call, line ~251), add:

```js
const evidenceLink=sec.querySelector('.v9-summary-link');
if(evidenceLink) evidenceLink.addEventListener('click',e=>{
  e.preventDefault();
  const target=document.getElementById('v9-case-evidence');
  if(target) target.scrollIntoView({behavior:'smooth',block:'start'});
});
```

The `href="#v9-case-evidence"` attribute stays (the build validator requires exactly one).

- [ ] **Step 2: Reorder `sec.innerHTML`**

Rearrange the existing concatenated blocks into the order above. Wrap the bootstrap card:

```js
+'<details class="v9-appendix" id="v9-appendix"><summary>Appendix — bootstrap verdicts (statistical evidence)</summary>'
+'<div class="v9-card" style="margin-top:12px"><h3>Bootstrap verdicts</h3>...(existing content unchanged)...</div></details>'
```

Insert the jump nav right after the `.v9-sub` div:

```js
+'<nav class="v9-jumpnav" aria-label="Section shortcuts">'
+'<button data-jump="v9-summary">Headline</button>'
+'<button data-jump="v9-lenses">Three lenses</button>'
+'<button data-jump="v9-compare">Rankings</button>'
+'<button data-jump="v9-case-evidence">Case evidence</button>'
+'<button data-jump="v9-trends">Trends</button>'
+'<button data-jump="v9-appendix">Appendix</button>'
+'</nav>'
```

Add the matching ids: `id="v9-lenses"` on the `.v9-story` section, `id="v9-compare"` on the `<h3>Baseline vs Hybrid vs GNN</h3>` heading, `id="v9-trends"` on the Daily Crossing Volume card. Wire after innerHTML assignment:

```js
sec.querySelector('.v9-jumpnav').addEventListener('click',e=>{
  const b=e.target.closest('button[data-jump]'); if(!b) return;
  const target=document.getElementById(b.dataset.jump);
  if(target){
    if(target.tagName==='DETAILS') target.open=true;
    target.scrollIntoView({behavior:'smooth',block:'start'});
  }
});
```

CSS:

```css
#tab-v9Results .v9-jumpnav { position: sticky; top: 0; z-index: 5; display: flex; flex-wrap: wrap; gap: 6px; padding: 10px 0; margin: 0 0 14px; background: var(--bg); }
#tab-v9Results .v9-jumpnav button { background: var(--elevated); color: var(--text2); border: 1px solid var(--border); border-radius: 999px; padding: 5px 12px; font: inherit; font-size: 12px; cursor: pointer; }
#tab-v9Results .v9-jumpnav button:hover { color: var(--text1); border-color: var(--border-strong); }
#tab-v9Results .v9-appendix > summary { cursor: pointer; color: var(--text2); font-size: 13px; font-weight: 600; padding: 12px 0; }
```

- [ ] **Step 3: Update the position test, run the suite**

Rewrite `test_v9_results_mounts_recovery_explorer_in_the_approved_story_position` to assert the new order: summary index < story index < `v9-compare` index < `v9-case-evidence` index < `v9-trends` index < `v9-appendix` index (use `V9_RESULTS_JS.index(...)` on the distinctive id strings). Run `PYTHONPATH=. pytest -q tests/test_v9_dashboard_builder.py` — all pass. The build-time mount validator is unaffected (ids unchanged, single href).

- [ ] **Step 4: Rebuild + eyeball**

Screenshot; confirm order, sticky nav, closed appendix, and that clicking the headline evidence link scrolls instead of switching tabs (manual check in a real browser: `python3 -m http.server 8000 --directory Documents/Data/v9_dashboard`).

- [ ] **Step 5: Commit**

```bash
git add Documents/Data/scripts/v9_dashboard_ui.py tests/test_v9_dashboard_builder.py
git commit -m "feat: demo-ordered V9 tab with jump nav and collapsed appendix"
```

---

### Task 7: Label & copy polish batch

All in `Documents/Data/scripts/v9_dashboard_ui.py` unless noted.

- [ ] **Step 1: Depth card K label**

The bars use `k=ks.includes(5000)?5000:ks[ks.length-1]` (`drawBars`, line ~307) while the headline uses K=2,000 — label it. Move the `k` computation so the card heading can use it, and change the card to:
`'<div class="v9-card"><h3>Depth event recall <span class="v9-k-note">top '+fmt(k)+' reviewed</span></h3>...'`
CSS: `#tab-v9Results .v9-k-note { color: var(--text3); font-size: 11px; font-weight: 500; margin-left: 6px; }`

- [ ] **Step 2: Arm labels**

`armLabel` (line ~213) → `a==='baseline'?'Tabular baseline':(a==='hybrid'?'Deployable Hybrid':'GNN (ceiling)')`. Also update the bar row literal `[['baseline',...]]` in `drawBars` which hardcodes lowercase `'baseline'` as its display label — route it through `armLabel('baseline')`. Do NOT change `'Deployable Hybrid'` (pinned by tests).

- [ ] **Step 3: Plain-language bootstrap sentences**

In `drawSig` (line ~429), before each table, derive a sentence from the data instead of hardcoding:

```js
const verdictOf=s=>{if(!s)return 'na';const lo=Number(s.ci[0]),hi=Number(s.ci[1]);return lo>0?'win':(hi<0?'loss':'wash');};
function plainReading(entries){
  const wins=entries.filter(e=>e.v==='win').map(e=>e.k);
  const washes=entries.filter(e=>e.v==='wash').map(e=>e.k);
  if(!entries.length) return '';
  let text='Plain reading: ';
  if(wins.length) text+='the Hybrid lead is statistically solid at '+wins.map(fmt).join(', ')+'. ';
  if(washes.length) text+='At '+washes.map(fmt).join(', ')+' the comparison is a wash.';
  if(!wins.length&&!washes.length) text+='the baseline leads at every tested budget.';
  return '<div class="v9-hint" style="margin:0 0 10px">'+text+'</div>';
}
```

Build `entries` as `{k, v: verdictOf(s)}` while iterating `ks` (whole-window table) and `daily_ks` (daily table), and prepend `plainReading(entries)` above each `<table>`. Reuse `verdictOf` inside `pill()` to avoid duplicated CI logic.

- [ ] **Step 4: Derive lens/summary daily budgets from the artifact (bug found during execution)**

The current `demo_comparison_v9.json` has `daily_ks: [5]`, but the three-lens panel hardcodes `daily_found@25` / `daily_budget@25` (lines ~224–227), rendering "0 vs 0" and "25/day equals 0 inspections". Replace the hardcoded 25 with a derived budget:

```js
const dailyKs=(demo.daily_ks||[]).map(Number).sort((a,b)=>a-b);
const lensDailyK=dailyKs.includes(25)?25:(dailyKs[dailyKs.length-1]||null);
const dailyBaselineLens=lensDailyK==null?null:Number((demo.overall_daily.baseline||{})['daily_found@'+lensDailyK]||0);
const dailyHybridLens=lensDailyK==null?null:Number((demo.overall_daily.hybrid||{})['daily_found@'+lensDailyK]||0);
const dailyBudgetLens=lensDailyK==null?null:Number((demo.overall_daily.baseline||{})['daily_budget@'+lensDailyK]||0);
```

Use these in lens 3's copy (`'…'+fmt(lensDailyK)+'/day equals '+fmt(dailyBudgetLens)+' inspections'`, stat `fmt(dailyHybridLens)+' vs '+fmt(dailyBaselineLens)`, label `'…at '+fmt(lensDailyK)+' inspections/day'`); when `lensDailyK==null` render 'n/a'. Delete the old `dailyBaseline25/dailyHybrid25/dailyBudget25` constants. Add a string-contract test asserting `V9_RESULTS_JS` contains no `daily_found@25` / `daily_budget@25` literals.

- [ ] **Step 5: GNN-run metric tile**

`runLabel` (line ~214) → `` (demo.gnn_seeds?demo.gnn_seeds.length:0)+' seeds · '+(demo.epochs||'-')+' epochs · '+(demo.gnn_arm||'-') `` (drop `(s)` and the trailing "arm" so the tile fits its metric styling).

- [ ] **Step 6: Test, rebuild, commit**

Run: `PYTHONPATH=. pytest -q tests/test_v9_dashboard_builder.py` (update `test_v9_ui_labels_overall_found_counts_as_event_hits_not_people` only if it pins `runLabel`/lowercase `baseline` strings). Rebuild + screenshot.

```bash
git add Documents/Data/scripts/v9_dashboard_ui.py tests/test_v9_dashboard_builder.py
git commit -m "polish: V9 tab labels, K note, and plain-language verdicts"
```

---

### Task 8: Anomaly ranking tab — headline comparison chart + collapsible tables

The tab is 12 cards × 13-row tables with no visual encoding. Add a grouped-bar headline ("missed-at-event recall by arm and region") built from the existing view model, and collapse each arm's tables into `<details>`.

**Files:**
- Modify: `Documents/Data/scripts/v9_dashboard_ui.py` (`UNSUP_AD_VIEW_MODEL_JS` line ~648, `UNSUP_AD_JS` line ~730, `UNSUP_AD_CSS` line ~461)
- Test: `tests/test_v9_dashboard_builder.py`

**Interfaces:**
- Produces: `buildUnsupervisedADHeadlineRows(view)` → array of `{armId, region, missedRecall, lifetimeRecall}` for completed regions of primary arms, in `view.primary` order; skipped regions omitted; metric value `null` when absent.

- [ ] **Step 1: Write failing test**

Add a node harness that concatenates `UI.UNSUP_AD_VIEW_MODEL_JS` and calls both functions:

```python
def _run_uad_headline(artifact):
    script = (
        UI.UNSUP_AD_VIEW_MODEL_JS
        + "\nconst view=buildUnsupervisedADViewModel("
        + json.dumps(artifact)
        + ");process.stdout.write(JSON.stringify(buildUnsupervisedADHeadlineRows(view)));"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def test_uad_headline_rows_cover_primary_arms_and_skip_skipped_regions():
    artifact = {
        "schema_version": 3,
        "primary_arm_order": ["tabular_unlabeled", "relational_unlabeled"],
        "ablation_arm_order": [],
        "arm_metadata": {},
        "arms": {
            "tabular_unlabeled": {
                "North": {"status": "completed",
                          "evaluation_only": {
                              "missed_at_event": {"recall": 0.21},
                              "lifetime_never_caught_people": {"recall": 0.14}}},
                "South": {"status": "skipped", "skip_reason": "no data"},
            },
            "relational_unlabeled": {
                "North": {"status": "completed",
                          "evaluation_only": {
                              "missed_at_event": {"recall": 0.27},
                              "lifetime_never_caught_people": {"recall": 0.18}}},
            },
        },
    }
    rows = _run_uad_headline(artifact)
    assert rows == [
        {"armId": "tabular_unlabeled", "region": "North",
         "missedRecall": 0.21, "lifetimeRecall": 0.14},
        {"armId": "relational_unlabeled", "region": "North",
         "missedRecall": 0.27, "lifetimeRecall": 0.18},
    ]
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=. pytest -q tests/test_v9_dashboard_builder.py -k uad_headline`
Expected: FAIL (`buildUnsupervisedADHeadlineRows is not defined`).

- [ ] **Step 3: Implement the helper**

Append inside `UNSUP_AD_VIEW_MODEL_JS`:

```js
function buildUnsupervisedADHeadlineRows(view){
  const rows=[];
  for(const arm of (view&&Array.isArray(view.primary)?view.primary:[])){
    for(const region of arm.regions){
      if(region.status==='skipped') continue;
      rows.push({
        armId:arm.id,
        region:region.region,
        missedRecall:region.metrics.missedRecall,
        lifetimeRecall:region.metrics.lifetimeNeverCaughtRecall
      });
    }
  }
  return rows;
}
```

- [ ] **Step 4: Run to verify pass, then render**

In the schema-v3 branch of `UNSUP_AD_JS` (after `const view=buildUnsupervisedADViewModel(ad);`):

```js
const ARM_COLORS={tabular_unlabeled:'#94a3b8',relational_unlabeled:'#3b82f6',relational_caught_supervised:'#16a34a'};
const ARM_SHORT={tabular_unlabeled:'Tabular (unlabeled)',relational_unlabeled:'Relational (unlabeled)',relational_caught_supervised:'Relational + caught labels'};
const headlineRows=buildUnsupervisedADHeadlineRows(view);
if(headlineRows.length){
  const regions=Array.from(new Set(headlineRows.map(r=>r.region)));
  h+='<div class="uad-card" style="margin-bottom:28px"><h3 class="uad-headline-title">Missed-at-event recall by arm and region</h3>'
    +'<div class="uad-headline-hint">Share of hidden-positive events each arm’s frozen alert threshold recovers. Higher is better; the progression tabular → relational → relational+caught is the story.</div>'
    +'<div class="uad-headline-legend">'+Object.entries(ARM_SHORT)
      .filter(([id])=>headlineRows.some(r=>r.armId===id))
      .map(([id,label])=>'<span><i style="background:'+ARM_COLORS[id]+'"></i>'+esc(label)+'</span>').join('')+'</div>'
    +regions.map(region=>'<div class="uad-headline-group"><b>'+esc(region)+'</b>'
      +headlineRows.filter(r=>r.region===region).map(r=>{
        const value=r.missedRecall==null?0:Number(r.missedRecall);
        return '<div class="uad-headline-row"><div class="uad-headline-track"><div class="uad-headline-fill" style="width:'+Math.max(2,Math.round(value*100))+'%;background:'+ARM_COLORS[r.armId]+'"></div></div><span>'+pct(r.missedRecall)+'</span></div>';
      }).join('')+'</div>').join('')
    +'</div>';
}
```

Insert this block right after the `.uad-header` div and before "Primary deployability progression". Then wrap each arm render in a collapsible: change `renderArm` to emit `'<details class="uad-details"><summary>'+esc(meta.label||arm.id)+' · '+fmt(meta.feature_count)+' features — full regional tables</summary>'+ ...existing arm body... +'</details>'`.

CSS:

```css
.uad-headline-title { margin: 0 0 6px; font-size: 14px; font-weight: 600; color: var(--text1); }
.uad-headline-hint { color: var(--text3); font-size: 12px; margin-bottom: 14px; max-width: 720px; line-height: 1.5; }
.uad-headline-legend { display: flex; flex-wrap: wrap; gap: 14px; margin-bottom: 14px; color: var(--text2); font-size: 12px; }
.uad-headline-legend i { display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 6px; }
.uad-headline-group { margin-bottom: 14px; }
.uad-headline-group > b { display: block; margin-bottom: 6px; color: var(--text1); font-size: 12px; }
.uad-headline-group .uad-headline-row { margin-bottom: 4px; }
.uad-headline-row { display: grid; grid-template-columns: 1fr 52px; gap: 10px; align-items: center; font-size: 11px; color: var(--text2); font-variant-numeric: tabular-nums; }
.uad-headline-track { height: 8px; background: var(--elevated); border-radius: 999px; overflow: hidden; }
.uad-headline-fill { height: 100%; border-radius: 999px; }
.uad-details > summary { cursor: pointer; color: var(--text1); font-size: 14px; font-weight: 600; padding: 10px 0; }
.uad-details { border-bottom: 1px solid var(--border); margin-bottom: 8px; }
```

(`.uad-card` already exists — reuse it for the chart container. If `uad-card h3` styling collides, scope with the classes above.)

- [ ] **Step 5: Full test run + rebuild + eyeball**

Run: `PYTHONPATH=. pytest -q tests/test_v9_dashboard_builder.py`; rebuild; screenshot `#tab-unsupervisedAD` — chart on top tells the arm progression, tables collapsed beneath.

- [ ] **Step 6: Commit**

```bash
git add Documents/Data/scripts/v9_dashboard_ui.py tests/test_v9_dashboard_builder.py
git commit -m "feat: anomaly tab headline recall chart with collapsible tables"
```

---

### Task 9: Community Explorer demo presets

Default view is a 19k-node hairball. Add one-click presets that land on a story.

**Files:**
- Modify: `Documents/Data/scripts/explorer_ui.py` (controls section around lines 90–135; reset handler line ~349; `EXPLORER_CSS`)
- Test: create `tests/test_explorer_ui.py`

**Interfaces:**
- Consumes existing in-scope variables: `catChips` (keys `carried`, `seized`, `arrested`, `interdict`, `nbsmug`, `nbarr`), `commSel`, `drillCommId`, `mode`, `modeSeg`, `colorBy`, `colorSeg`, `clearFilters()` (hoisted function declaration), `apply()`, `E.communities` (`{id,size,carried,arrested}`), `renderSide`, `selectedNode`.

- [ ] **Step 1: Write failing contract test**

```python
import importlib.util
from pathlib import Path

UI_PATH = (
    Path(__file__).resolve().parents[1] / "Documents/Data/scripts/explorer_ui.py"
)
spec = importlib.util.spec_from_file_location("explorer_ui", UI_PATH)
UI = importlib.util.module_from_spec(spec)
spec.loader.exec_module(UI)


def test_explorer_ships_demo_presets():
    js = UI.EXPLORER_JS
    assert "Demo presets" in js
    assert "Contraband carriers" in js
    assert "Most-flagged cell" in js
    assert js.count("function resetExplorerState()") == 1
    assert "resetExplorerState();" in js


def test_explorer_preset_css_present():
    assert ".xp-preset" in UI.EXPLORER_CSS
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=. pytest -q tests/test_explorer_ui.py`
Expected: FAIL.

- [ ] **Step 3: Implement**

1. Refactor: extract the body of the current `resetBtn` click handler (line ~349) into `function resetExplorerState(){ clearFilters(); commSel.value=''; drillCommId=''; selectedNode=null; mode='highlight'; modeSeg.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x.dataset.v==='highlight')); colorBy='type'; colorSeg.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x.dataset.v==='type')); }` and make the handler `()=>{resetExplorerState();apply();renderSide(null);}`. (Place the function next to `clearFilters` so both live together; function declarations hoist, so the earlier preset wiring can call it.)
2. Immediately before `const resetBtn=...` (line ~133), add:

```js
  // demo presets — canned filter states for live walkthroughs
  const presetG=group('Demo presets');const presetWrap=document.createElement('div');presetWrap.className='xp-chips';presetG.appendChild(presetWrap);
  function focusMode(){mode='focus';modeSeg.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x.dataset.v==='focus'));}
  function presetButton(label,configure){const b=document.createElement('button');b.type='button';b.className='xp-preset';b.textContent=label;b.addEventListener('click',()=>{resetExplorerState();configure();apply();});presetWrap.appendChild(b);}
  presetButton('Contraband carriers',()=>{catChips.carried.classList.add('on');catChips.seized.classList.add('on');focusMode();});
  presetButton('Most-flagged cell',()=>{
    const best=E.communities.slice().sort((a,b)=>(b.carried||0)-(a.carried||0)||(b.size||0)-(a.size||0))[0];
    if(!best) return;
    commSel.value=best.id;drillCommId=best.id;focusMode();
  });
```

3. CSS in `EXPLORER_CSS`:

```css
.xp-preset{background:var(--accent-soft);border:1px solid var(--accent);color:var(--accent-hover);border-radius:8px;padding:5px 11px;font-size:12px;font-weight:600;cursor:pointer}
.xp-preset:hover{background:var(--accent-glow)}
```

- [ ] **Step 4: Run tests, rebuild the template chain, eyeball**

Run: `PYTHONPATH=. pytest -q tests/test_explorer_ui.py tests/test_v9_dashboard_builder.py`
Explorer JS enters via `build_dashboard.py`, so the chain is:
`.venv/bin/python Documents/Data/scripts/build_dashboard.py Documents/Data/synthetic_cbp_graph_corpus_v9` then `.venv/bin/python Documents/Data/scripts/build_v9_dashboard.py`.
Screenshot `#tab-explorer`, click nothing — then manually verify presets in a real browser: "Most-flagged cell" should drill into a small readable subgraph.

- [ ] **Step 5: Commit**

```bash
git add Documents/Data/scripts/explorer_ui.py tests/test_explorer_ui.py
git commit -m "feat: one-click demo presets for the community explorer"
```

---

### Task 10 (optional, larger): Light "projector" theme toggle

Dark-only dashboards wash out on projectors. Injected entirely by `build_v9_dashboard.py` so the corpus template stays untouched. Skip if time-boxed; nothing later depends on it.

**Files:**
- Modify: `Documents/Data/scripts/build_v9_dashboard.py`
- Test: `tests/test_v9_dashboard_builder.py`

- [ ] **Step 1: Write failing test**

```python
def test_v9_dashboard_injects_light_theme_toggle():
    from build_v9_dashboard import LIGHT_THEME_CSS, THEME_TOGGLE_JS
    assert '[data-theme="light"]' in LIGHT_THEME_CSS
    assert "--bg:" in LIGHT_THEME_CSS
    assert "localStorage" in THEME_TOGGLE_JS
    assert "v9-theme" in THEME_TOGGLE_JS
```

(Match the import style the test file already uses for `build_v9_dashboard`.)

- [ ] **Step 2: Run to verify failure, then implement**

Add to `build_v9_dashboard.py`:

```python
LIGHT_THEME_CSS = r"""
:root[data-theme="light"]{
  --bg:#f5f6f7; --sunk:#ebedef; --surface:#ffffff; --elevated:#f0f1f3;
  --muted:#e2e4e8; --border:#d8dade; --border-strong:#bfc3ca;
  --text1:#191b1f; --text2:#4a4f58; --text3:#767b85;
  --accent:#059669; --accent-hover:#047857;
  --accent-soft:rgba(5,150,105,0.10); --accent-glow:rgba(5,150,105,0.16);
  --negative:#dc2626; --negative-soft:rgba(220,38,38,0.08);
}
:root[data-theme="light"] body{background:var(--bg);color:var(--text1);}
#v9-theme-toggle{position:fixed;right:14px;bottom:14px;z-index:50;background:var(--surface);color:var(--text2);border:1px solid var(--border-strong);border-radius:999px;padding:7px 14px;font:600 12px var(--font-body);cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.18)}
"""

THEME_TOGGLE_JS = r"""
<script>
(function(){
  const saved=localStorage.getItem('v9-theme');
  if(saved==='light')document.documentElement.dataset.theme='light';
  const btn=document.createElement('button');
  btn.id='v9-theme-toggle';btn.type='button';
  function label(){btn.textContent=document.documentElement.dataset.theme==='light'?'Dark theme':'Projector theme';}
  btn.addEventListener('click',()=>{
    const light=document.documentElement.dataset.theme==='light';
    if(light)delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme='light';
    localStorage.setItem('v9-theme',light?'dark':'light');label();
  });
  label();document.body.appendChild(btn);
})();
</script>
"""
```

In `_build_staged_dashboard`, after the existing `html.replace("</style>", V9_RESULTS_CSS + ...)` line: `html = html.replace("</style>", LIGHT_THEME_CSS + "\n</style>", 1)` and before `</body>`: `html = html.replace("</body>", THEME_TOGGLE_JS + "\n</body>", 1)`.

- [ ] **Step 3: Test, rebuild, screenshot both themes**

Run pytest; rebuild; screenshot dark, then screenshot with a query to force light (`localStorage` won't apply headlessly — temporarily verify by screenshotting after loading `index.html` with `document.documentElement.dataset.theme='light'` via a scratch copy, or just verify manually in a real browser). Known limitation to eyeball: hard-coded chart hexes (#16a34a, #3b82f6, #64748b, #94a3b8) stay as-is — verify they read on white; they are mid-tone and should. If any chart text is invisible in light mode, fix with a `[data-theme="light"]`-scoped override, not by editing chart code.

- [ ] **Step 4: Commit**

```bash
git add Documents/Data/scripts/build_v9_dashboard.py tests/test_v9_dashboard_builder.py
git commit -m "feat: optional projector (light) theme toggle for V9 dashboard"
```

---

### Task 11: Final verification pass

- [ ] **Step 1: Full rebuild chain**

```bash
.venv/bin/python Documents/Data/scripts/build_dashboard.py Documents/Data/synthetic_cbp_graph_corpus_v9
.venv/bin/python Documents/Data/scripts/build_v9_dashboard.py
```

- [ ] **Step 2: Full test suite**

Run: `PYTHONPATH=. pytest -q tests`
Expected: all pass.

- [ ] **Step 3: Screenshot every changed tab and eyeball**

`v9Results` (order, jump nav, cumulative default, stacked panels, K note, plain-language verdicts, evidence badges), `unsupervisedAD` (headline chart, collapsed tables), `explorer` (preset buttons), plus light theme if Task 10 ran. Check for label collisions, overflow, and that the demo walk-through (Overview → V9 results → case evidence → explorer preset) flows without dead ends.

- [ ] **Step 4: Update `Documents/Data/changes_3.md`**

Add a short entry describing the dashboard changes (UI only — no metric changes; artifact regeneration coverage numbers if Task 3 ran).

---

## Out-of-scope notes (for the log, not this plan)

- Most top-uplift recovery cases fail explanation because their pooled component exceeds the max explainable size (6). Raising that cap or attempting small-component candidates first is an evaluation-side change — needs its own plan.
- `switchTab`'s unknown-hash fallback to Overview is template-owned behavior; Task 6 works around it for our link only.
- The `unsupervised_ad_results_v9.json` artifact is 9.2 MB inside a 12.9 MB embedded page; trimming embedded payloads (e.g., dropping legacy schema-v2 blocks from the embed) would cut load time.
