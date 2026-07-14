# V9 Metric Story Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an always-visible three-lens narrative to the V9 results tab that explains the scope, denominator, and budget differences behind the displayed metrics.

**Architecture:** Keep all model and metric calculations unchanged. Add presentation copy and a small narrative strip in the existing `V9_RESULTS_JS` template, update the existing source-level dashboard test to lock the explanation in place, then verify the focused test suite and generated dashboard source.

**Tech Stack:** Python source templates, embedded HTML/CSS/JavaScript, pytest.

---

### Task 1: Lock the explanatory contract with tests

**Files:**
- Modify: `tests/test_v9_dashboard_builder.py`
- Test: `tests/test_v9_dashboard_builder.py`

- [ ] **Step 1: Write failing assertions**

Extend the existing V9 UI source test so it requires:

```python
assert "Read the V9 result through three lenses" in ui
assert "Whole-pool model comparison" in ui
assert "Global Found@K by selected population" in ui
assert "25 inspections/day means 6,825 total inspections" in ui
assert "Hybrid finds 310 vs 186 for the baseline at K=2,000" in ui
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```bash
rtk pytest tests/test_v9_dashboard_builder.py -q
```

Expected: FAIL because the approved narrative and scope labels are not yet in `v9_dashboard_ui.py`.

### Task 2: Add the three-lens story and clarify panel scopes

**Files:**
- Modify: `Documents/Data/scripts/v9_dashboard_ui.py:153-172`

- [ ] **Step 1: Add the explainer block**

Insert an always-visible `v9-story` block after the model notes and before the metric panels. It must contain three short lens items:

```text
Global ranking: one top-K list over the entire test pool.
Findable depth: the selected observable slice, where relational signal can work.
Daily operations: a separate quota for each test day.
```

Include a concise explanation of low whole-pool F1 and these auditable examples:

```text
At K=2,000 across the whole pool, Hybrid finds 310 hidden carriers versus 186 for the baseline.
At 25 inspections/day, the daily budget is 6,825 inspections and Hybrid finds 953 versus 536.
```

- [ ] **Step 2: Rename the three panel headings**

Change the existing headings to:

```text
Whole-pool model comparison
Global Found@K by selected population
Daily capacity view
```

Update the nearby hints so they explicitly describe whole-pool, selected-population, and per-day scopes.

- [ ] **Step 3: Add scoped styling**

Use the existing V9 card tokens and responsive breakpoints. Give each lens a subtle left accent and keep the block readable at mobile widths without adding new dependencies or animations.

- [ ] **Step 4: Run the focused test to verify it passes**

Run:

```bash
rtk pytest tests/test_v9_dashboard_builder.py -q
```

Expected: PASS.

### Task 3: Verify no metric behavior changed

**Files:**
- Inspect: `gnn/run_demo.py`
- Inspect: `gnn/diagnostics/demo_comparison_v9.json`
- Test: `tests/test_v9_dashboard_builder.py`, `tests/test_run_demo_smoke.py`

- [ ] **Step 1: Confirm the diff is presentation-only**

Run:

```bash
rtk git diff -- Documents/Data/scripts/v9_dashboard_ui.py tests/test_v9_dashboard_builder.py
```

Expected: only narrative markup, labels, scoped CSS, and source assertions change; no result-generation code changes.

- [ ] **Step 2: Run the relevant tests**

Run:

```bash
rtk pytest tests/test_v9_dashboard_builder.py tests/test_run_demo_smoke.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Confirm the concrete values remain sourced from the current artifact**

Run:

```bash
rtk jq '.overall.hybrid["found@2000"], .overall.baseline["found@2000"], .overall_daily.hybrid["daily_found@25"], .overall_daily.baseline["daily_found@25"]' gnn/diagnostics/demo_comparison_v9.json
```

Expected: `310`, `186`, `953`, `536`.
