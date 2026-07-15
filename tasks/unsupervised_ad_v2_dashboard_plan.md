# Unsupervised AD V2 Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the schema-v3 relational-strict metrics, drift diagnostics, capacity curves, and bounded rarity/sensitivity explanations in the existing V9 dashboard without changing unrelated tabs.

**Architecture:** Make artifact selection explicit in `build_v9_dashboard.py`, isolate schema normalization in a testable JavaScript view-model function, and extend only the Unsupervised AD CSS/renderer in `v9_dashboard_ui.py`. Charts use bounded inline SVG and existing design tokens so the generated dashboard remains self-contained.

**Tech Stack:** Python dashboard builder, vanilla JavaScript, inline SVG, existing V9 CSS tokens, pytest, Node-based view-model tests, browser visual QA.

---

## File Map

- Modify `Documents/Data/scripts/build_v9_dashboard.py`: prefer the V9-qualified unsupervised artifact and validate its corpus identity.
- Modify `Documents/Data/scripts/v9_dashboard_ui.py`: schema-v3 view model, relational comparison, charts, drift, recovery, and explainability.
- Modify `tests/test_v9_dashboard_builder.py`: builder selection, view-model behavior, UI contract, and generated-dashboard tests.
- Regenerate `Documents/Data/v9_dashboard/data_v9.json` and `Documents/Data/v9_dashboard/index.html` after source tests pass.

### Task 1: Prefer And Validate The Corpus-qualified Artifact

**Files:**
- Modify: `Documents/Data/scripts/build_v9_dashboard.py:81-106`
- Modify: `tests/test_v9_dashboard_builder.py`

- [ ] **Step 1: Write failing artifact-selection tests**

```python
def test_unsupervised_artifact_path_prefers_v9_qualified_file(tmp_path):
    diagnostics = tmp_path / "gnn" / "diagnostics"
    diagnostics.mkdir(parents=True)
    legacy = diagnostics / "unsupervised_ad_results.json"
    qualified = diagnostics / "unsupervised_ad_results_v9.json"
    legacy.write_text('{"provenance":{"corpus_name":"synthetic_cbp_graph_corpus_v8"}}')
    qualified.write_text('{"provenance":{"corpus_name":"synthetic_cbp_graph_corpus_v9"}}')

    assert BUILDER._unsupervised_artifact_path(tmp_path).name == qualified.name


def test_unsupervised_artifact_rejects_wrong_corpus(tmp_path):
    diagnostics = tmp_path / "gnn" / "diagnostics"
    diagnostics.mkdir(parents=True)
    path = diagnostics / "unsupervised_ad_results_v9.json"
    path.write_text('{"provenance":{"corpus_name":"synthetic_cbp_graph_corpus_v8"}}')

    with pytest.raises(ValueError, match="expected a V9 corpus"):
        BUILDER._load_unsupervised_artifact(tmp_path)
```

Add `import pytest` at the top of the test file.

- [ ] **Step 2: Run tests and verify RED**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_v9_dashboard_builder.py -k unsupervised_artifact
```

Expected: helper attribute errors.

- [ ] **Step 3: Implement explicit artifact selection**

```python
def _unsupervised_artifact_path(repo_root):
    diagnostics = Path(repo_root) / "gnn" / "diagnostics"
    qualified = diagnostics / "unsupervised_ad_results_v9.json"
    legacy = diagnostics / "unsupervised_ad_results.json"
    return qualified if qualified.exists() else legacy


def _load_unsupervised_artifact(repo_root):
    path = _unsupervised_artifact_path(repo_root)
    if not path.exists():
        return None, path
    payload = json.loads(path.read_text())
    corpus_name = payload.get("provenance", {}).get("corpus_name")
    if corpus_name and not corpus_name.endswith("v9"):
        raise ValueError(
            f"expected a V9 corpus in {path}, found {corpus_name!r}"
        )
    return payload, path
```

Import `Path` from `pathlib`, replace the unconditional legacy load with this
helper, and preserve the existing sparse-tab warning when no artifact exists.

- [ ] **Step 4: Run builder tests**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_v9_dashboard_builder.py -k "unsupervised_artifact or load_v9_data"
```

Expected: selected tests pass.

### Task 2: Add A Testable Schema-v3 View Model

**Files:**
- Modify: `Documents/Data/scripts/v9_dashboard_ui.py:586-667`
- Modify: `tests/test_v9_dashboard_builder.py`

- [ ] **Step 1: Add the Node view-model test helper**

```python
def _run_unsupervised_view_model(payload):
    script = (
        V9_UI.UNSUP_AD_VIEW_MODEL_JS
        + "\nprocess.stdout.write(JSON.stringify(buildUnsupervisedViewModel("
        + json.dumps(payload)
        + ")));"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True,
    )
    return json.loads(completed.stdout)
```

- [ ] **Step 2: Write a failing schema-normalization test**

```python
def test_unsupervised_view_model_preserves_legacy_and_relational_results():
    payload = {
        "schema_version": 3,
        "modes": {
            "strict": {"North": {"test_precision": 0.2}},
            "assisted": {"North": {"test_precision": 0.3}},
        },
        "arms": {
            "relational_strict": {
                "North": {
                    "test_precision": 0.4,
                    "diagnostics": {
                        "threshold_curve": [{"recall": 0.5, "precision": 0.4}],
                        "capacity": {"ks": [10], "precision@10": 0.4},
                        "monthly": [{"month": "2025-01", "alert_rate": 0.1}],
                    },
                    "explainability": {
                        "alerts": [{"event_id": "E1", "features": []}],
                        "global_influence": [{"feature": "party_size",
                                              "mean_absolute_sensitivity": 0.2}],
                    },
                }
            }
        },
    }
    view = _run_unsupervised_view_model(payload)
    assert view["regions"] == ["North"]
    assert view["rows"][0]["strict"]["test_precision"] == 0.2
    assert view["rows"][0]["relational"]["test_precision"] == 0.4
    assert view["rows"][0]["alerts"][0]["event_id"] == "E1"
```

- [ ] **Step 3: Run the test and verify RED**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_v9_dashboard_builder.py -k unsupervised_view_model
```

Expected: `UNSUP_AD_VIEW_MODEL_JS` is missing.

- [ ] **Step 4: Implement the pure JavaScript view model**

Place this exported string before `UNSUP_AD_JS`:

```javascript
function buildUnsupervisedViewModel(ad){
  const modes=(ad&&ad.modes)||{};
  const relational=((ad&&ad.arms)||{}).relational_strict||{};
  const regionSet=new Set([
    ...Object.keys(modes.strict||{}),
    ...Object.keys(modes.assisted||{}),
    ...Object.keys(relational),
  ]);
  const regions=[...regionSet].sort();
  const rows=regions.map(region=>{
    const arm=relational[region]||{};
    const diagnostics=arm.diagnostics||{};
    const explanations=arm.explainability||{};
    return {
      region,
      strict:(modes.strict||{})[region]||null,
      assisted:(modes.assisted||{})[region]||null,
      relational:arm.status==='skipped'?null:arm,
      skipped:arm.status==='skipped'?arm.reason:null,
      thresholdCurve:diagnostics.threshold_curve||[],
      capacity:diagnostics.capacity||{},
      dailyCapacity:diagnostics.daily_capacity||{},
      monthly:diagnostics.monthly||[],
      histogram:diagnostics.score_histogram||{},
      alerts:explanations.alerts||[],
      influence:explanations.global_influence||[],
    };
  });
  return {schemaVersion:Number(ad&&ad.schema_version||2),regions,rows,
          provenance:(ad&&ad.provenance)||{},
          armMetadata:(ad&&ad.arm_metadata)||{}};
}
```

Assign the complete function body from Step 4 to the
`UNSUP_AD_VIEW_MODEL_JS` raw-string constant. Define `UNSUP_AD_JS` by
concatenating that constant with the existing raw-string renderer body, so the
generated dashboard and Node tests execute the identical implementation.

- [ ] **Step 5: Run the view-model tests**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_v9_dashboard_builder.py -k unsupervised_view_model
```

Expected: view-model tests pass for schema v3 and a separate schema-v2 fixture
with no `arms` key.

### Task 3: Relational-arm Summary And Comparison

**Files:**
- Modify: `Documents/Data/scripts/v9_dashboard_ui.py:452-667`
- Modify: `tests/test_v9_dashboard_builder.py`

- [ ] **Step 1: Write failing UI contract assertions**

```python
def test_unsupervised_dashboard_has_relational_comparison_contract():
    ui = UI_MODULE_PATH.read_text()
    for token in (
        "Relational strict", "relational proxies", "label-free threshold",
        "uad-arm-comparison", "uad-score-shift", "uad-capacity",
        "uad-drift", "uad-explanations",
    ):
        assert token in ui
    assert "not an unsupervised GNN" in ui
    assert "not probabilities" in ui
```

- [ ] **Step 2: Run the contract test and verify RED**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_v9_dashboard_builder.py::test_unsupervised_dashboard_has_relational_comparison_contract
```

Expected: missing relational-strict tokens.

- [ ] **Step 3: Add comparison markup and styles**

Add these class contracts to `UNSUP_AD_CSS`:

```css
.uad-arm-comparison{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:18px 0 28px}
.uad-arm-card{padding:16px;border:1px solid var(--border);border-radius:10px;background:var(--surface)}
.uad-arm-card.is-relational{border-color:rgba(16,185,129,.45);background:rgba(16,185,129,.05)}
.uad-arm-card b{display:block;color:var(--text1);font-size:13px;margin-bottom:6px}
.uad-arm-card p{margin:0;color:var(--text2);font-size:12px;line-height:1.5}
.uad-panel{margin-top:18px;padding:20px;border:1px solid var(--border);border-radius:12px;background:var(--surface)}
.uad-panel h3{margin:0 0 6px;color:var(--text1);font-size:14px}
.uad-panel-note{margin:0 0 16px;color:var(--text3);font-size:11px;line-height:1.5}
@media(max-width:800px){.uad-arm-comparison{grid-template-columns:1fr}}
```

In `UNSUP_AD_JS`, build the view model once and render three arm-contract cards.
Use the exact disclosures: legacy strict uses a training-score threshold,
assisted uses validation labels, and relational strict uses recent unlabeled
validation scores plus relational proxies and is not an unsupervised GNN.

- [ ] **Step 4: Add one comparison table per region**

Render precision, recall, F1, alert rate, average precision, hidden people
found, and threshold source for all available arms. Use `n/a` for missing
schema-v2 fields, never numeric zero. Add a skipped-arm note when the view model
contains a skip reason.

- [ ] **Step 5: Run UI contract tests**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_v9_dashboard_builder.py -k "unsupervised_dashboard"
```

Expected: legacy disclosure tests and new relational comparison tests pass.

### Task 4: Inline Score, PR, Capacity, And Drift Charts

**Files:**
- Modify: `Documents/Data/scripts/v9_dashboard_ui.py`
- Modify: `tests/test_v9_dashboard_builder.py`

- [ ] **Step 1: Write failing chart contract tests**

```python
def test_unsupervised_dashboard_charts_are_bounded_inline_svg():
    ui = UI_MODULE_PATH.read_text()
    assert "function uadLinePath" in ui
    assert "function uadScoreHistogram" in ui
    assert "function uadThresholdCurve" in ui
    assert "function uadCapacityChart" in ui
    assert "function uadDriftChart" in ui
    assert "<svg" in ui
    assert "higher = more anomalous" in ui
    assert "retrospective evaluation only" in ui
```

- [ ] **Step 2: Run the chart test and verify RED**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_v9_dashboard_builder.py::test_unsupervised_dashboard_charts_are_bounded_inline_svg
```

Expected: chart helper tokens are absent.

- [ ] **Step 3: Add shared bounded SVG helpers**

Implement finite-value filtering, empty-state text, and coordinate mapping:

```javascript
function uadLinePath(points,xValue,yValue,w=560,h=180,p=24){
  const clean=points.filter(d=>Number.isFinite(xValue(d))&&Number.isFinite(yValue(d)));
  if(!clean.length)return '';
  const xs=clean.map(xValue),ys=clean.map(yValue);
  const xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);
  const sx=x=>p+(x-xmin)/Math.max(xmax-xmin,1e-12)*(w-2*p);
  const sy=y=>h-p-(y-ymin)/Math.max(ymax-ymin,1e-12)*(h-2*p);
  return clean.map((d,i)=>(i?'L':'M')+sx(xValue(d)).toFixed(1)+','+sy(yValue(d)).toFixed(1)).join(' ');
}

function uadEmptyChart(message){
  return '<div class="uad-chart-empty">'+esc(message)+'</div>';
}
```

Add `.uad-chart`, `.uad-chart-legend`, `.uad-chart-empty`, and accessible
`svg[role="img"]` styles. Every chart consumes already-bounded artifact arrays;
do not embed raw event scores.

- [ ] **Step 4: Implement the four chart renderers**

- `uadScoreHistogram(histogram, threshold)` overlays train/validation/test bins
  and draws a threshold guide, labeling the score direction.
- `uadThresholdCurve(points, frozenThreshold)` draws precision, recall, and F1,
  marks the frozen point, and labels the curve retrospective-only.
- `uadCapacityChart(capacity, dailyCapacity)` draws precision@k, recall@k, and
  cumulative lift against the global `ks` array, followed by found people and
  total inspections at each recorded per-day quota.
- `uadDriftChart(monthly)` draws monthly median score and alert rate, with
  separate scales and a legend.

Each function must return `uadEmptyChart` when required arrays are absent so
schema-v2 artifacts remain readable.

- [ ] **Step 5: Attach charts to relational regional panels**

Create containers with IDs derived from a stable sanitized region token:
`uad-score-shift-*`, `uad-pr-*`, `uad-capacity-*`, and `uad-drift-*`. Populate
them after assigning `sec.innerHTML`, avoiding script execution inside strings.

- [ ] **Step 6: Run dashboard source tests**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_v9_dashboard_builder.py
```

Expected: all source and generated-dashboard contract tests pass.

### Task 5: Explainability Table And Detail Panel

**Files:**
- Modify: `Documents/Data/scripts/v9_dashboard_ui.py`
- Modify: `tests/test_v9_dashboard_builder.py`

- [ ] **Step 1: Write failing explanation disclosure and interaction tests**

```python
def test_unsupervised_explanations_are_bounded_and_noncausal():
    ui = UI_MODULE_PATH.read_text()
    for token in (
        "reference-replacement sensitivity", "regional rarity",
        "not causal", "not additive", "data-uad-alert",
        "uad-explanation-detail", "sensitivity_delta", "reference_value",
    ):
        assert token in ui
```

- [ ] **Step 2: Run the test and verify RED**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_v9_dashboard_builder.py::test_unsupervised_explanations_are_bounded_and_noncausal
```

Expected: explanation interaction tokens are absent.

- [ ] **Step 3: Render global influence and alert rows**

For each relational region, render at most the artifact-provided alerts. The
global table contains feature, mean absolute sensitivity, and mean positive
sensitivity. The alert table contains synthetic event ID, anomaly score,
predicted status, and a unique `data-uad-alert` button index.

- [ ] **Step 4: Add the detail renderer**

```javascript
function uadExplanationDetail(alert){
  if(!alert)return '<div class="uad-chart-empty">Select an alert.</div>';
  const rows=(alert.features||[]).map(feature=>
    '<tr><td>'+esc(feature.feature)+'</td>'+
    '<td>'+esc(String(feature.observed_value??'n/a'))+'</td>'+
    '<td>'+esc(String(feature.reference_value??'n/a'))+'</td>'+
    '<td>'+pct(feature.rarity)+'</td>'+
    '<td>'+Number(feature.sensitivity_delta||0).toFixed(4)+'</td></tr>'
  ).join('');
  return '<h4>Event '+esc(alert.event_id)+'</h4>'+
    '<p class="uad-panel-note">Regional rarity and reference-replacement sensitivity; not causal, not additive, and not SHAP.</p>'+
    '<div class="v9-table-wrap"><table><thead><tr><th>feature</th><th>observed</th><th>reference</th><th>rarity</th><th>sensitivity delta</th></tr></thead><tbody>'+rows+'</tbody></table></div>';
}
```

After rendering, bind one delegated click listener on the unsupervised section.
Read the region and alert indices from `data-*` attributes, retrieve the alert
from the view model, and replace only that region's detail container.

- [ ] **Step 5: Run all dashboard tests**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_v9_dashboard_builder.py
```

Expected: all dashboard tests pass.

### Task 6: Regenerate And Visually Verify The V9 Dashboard

**Files:**
- Regenerate: `Documents/Data/v9_dashboard/data_v9.json`
- Regenerate: `Documents/Data/v9_dashboard/index.html`

- [ ] **Step 1: Rebuild from the schema-v3 V9 artifact**

```bash
rtk env PYTHONPATH=. .venv/bin/python Documents/Data/scripts/build_v9_dashboard.py
```

Expected: builder reports the corpus-qualified V9 unsupervised artifact and
writes both dashboard outputs without warnings about missing unsupervised data.

- [ ] **Step 2: Run generated-output contract tests**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_v9_dashboard_builder.py
```

Expected: all tests pass against the regenerated HTML.

- [ ] **Step 3: Perform browser visual QA**

Use the `browser-use:browser` skill to open the generated V9 dashboard, select
the Unsupervised AD tab, and verify at desktop and narrow widths:

- legacy strict and assisted cards remain readable;
- relational comparison values match the embedded JSON;
- score, PR, capacity, and drift charts have no clipping or overlapping labels;
- empty states appear for absent schema-v2 data;
- alert selection updates only the intended explanation detail;
- the non-causal and non-probability disclosures remain visible;
- keyboard focus and responsive table scrolling work.

- [ ] **Step 4: Fix visual defects and repeat focused verification**

For each defect, add or tighten a source-level contract test before changing
CSS/JS, rebuild, reload the local page, and re-check the affected viewport.

- [ ] **Step 5: Run final repository verification**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q
rtk git diff --check
rtk git status --short
```

Expected: zero test failures, no whitespace errors, and only intended dashboard,
generated artifact, core, documentation, and pre-existing user changes.
