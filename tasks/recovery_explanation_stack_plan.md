# Recovery explanation stack implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stack the schema-3 GNN explanation panels at full width in the order attribution evidence, counterfactual factors, then LLM explanation.

**Architecture:** Keep the existing explanation panel renderers and data unchanged. Change the shared explanation-row CSS from two columns to one column, and reorder the three existing render calls so DOM order, visual order, and keyboard order agree.

**Tech Stack:** Python-generated vanilla CSS/JavaScript dashboard bundle, pytest static UI contracts, V9 dashboard builder.

---

### Task 1: Update the UI regression contracts first

**Files:**
- Modify: `tests/test_v9_recovery_explainer_ui.py:1250-1270`
- Modify: `tests/test_v9_recovery_explainer_ui.py:2900-2930`

- [x] **Step 1: Change the CSS contract to require one full-width column**

In `test_schema3_graph_workspace_css_uses_bounded_rail_and_graph_first_tracks`, replace the old two-column token:

```python
"grid-template-columns: minmax(0, 1.28fr) minmax(220px, .72fr)",
```

with:

```python
"grid-template-columns: minmax(0, 1fr)",
```

- [x] **Step 2: Change the renderer-order contract to attribution → factors → narrative**

In `test_schema3_detail_renderer_reuses_the_technical_evidence_panels`, keep the existing index lookups and replace:

```python
assert boundary_index < graph_index < narrative_index < attribution_index < factors_index
```

with:

```python
assert boundary_index < graph_index < attribution_index < factors_index < narrative_index
```

This asserts the requested DOM order without changing any panel implementation.

- [x] **Step 3: Run the focused tests and verify they fail for the old implementation**

Run:

```bash
rtk .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_graph_workspace_css_uses_bounded_rail_and_graph_first_tracks \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_detail_renderer_reuses_the_technical_evidence_panels
```

Expected: both tests fail because the current CSS still contains the two-column track and the current render order is narrative → attribution → factors.

### Task 2: Implement the approved stacked layout

**Files:**
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py:139-140`
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py:3305-3309`

- [x] **Step 1: Make the explanation row a single-column grid**

Change the shared rule from:

```css
#tab-v9Results .v9-recovery-explanation-row { display: grid; grid-template-columns: minmax(0, 1.28fr) minmax(220px, .72fr); gap: 14px; margin-top: 14px; }
```

to:

```css
#tab-v9Results .v9-recovery-explanation-row { display: grid; grid-template-columns: minmax(0, 1fr); gap: 14px; margin-top: 14px; }
```

Leave the child `min-width` rule and existing mobile override in place.

- [x] **Step 2: Match the render/DOM order to the approved reading order**

Replace the GNN branch in `mountRecoveryExplorerV3` with:

```javascript
    if(detailView.kind==='gnn_explanation'){
      explanationRow.appendChild(renderHighestAttributionPanel(doc,detailView.explanation));
      renderFactors(explanationRow,detailView.explanation);
      renderNarrative(explanationRow,detailView.explanation);
    }else{
```

Do not alter the structural fallback branch or any explanation content logic.

- [x] **Step 3: Run the focused regression tests**

Run:

```bash
rtk .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py \
  tests/test_v9_dashboard_builder.py
```

Expected: all focused tests pass.

### Task 3: Rebuild and verify the shipped dashboard bundle

**Files:**
- Generated: `Documents/Data/v9_dashboard/data_v9.json`
- Generated: `Documents/Data/v9_dashboard/index.html`

- [x] **Step 1: Rebuild the V9 dashboard**

Run:

```bash
rtk .venv/bin/python Documents/Data/scripts/build_v9_dashboard.py
```

Expected: the builder reports updated `data_v9.json` and `index.html` paths without errors.

- [x] **Step 2: Verify the generated bundle contains the new layout contract**

Run:

```bash
rtk rg -n -C 1 \
  "v9-recovery-explanation-row|renderHighestAttributionPanel\(doc,detailView.explanation\)|renderFactors\(explanationRow,detailView.explanation\)|renderNarrative\(explanationRow,detailView.explanation\)" \
  Documents/Data/v9_dashboard/index.html
```

Expected: `index.html` contains the one-column explanation-row rule and the render-call sequence attribution → factors → narrative.

- [x] **Step 3: Run final hygiene checks**

Run:

```bash
rtk git diff --check
```

Expected: no whitespace errors.
