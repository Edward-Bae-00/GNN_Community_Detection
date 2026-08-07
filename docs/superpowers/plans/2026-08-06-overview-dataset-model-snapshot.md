# Overview Dataset and Model Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a validated, provenance-backed dataset and model snapshot to the V9 Overview page.

**Architecture:** Extend `v9_summary_page.py` with a small JavaScript view model that validates `D.meta`, `D.overview`, and `D.v9Demo`, then render the result as a new evidence block. Keep all existing result evidence and model artifacts unchanged.

**Tech Stack:** Embedded JavaScript, DOM APIs, CSS, Node syntax/runtime tests, pytest.

---

### Task 1: Lock the snapshot contract with failing tests

**Files:**
- Modify: `tests/test_v9_summary_page.py`
- Test: `tests/test_v9_summary_page.py`

- [x] **Step 1: Add a complete snapshot runtime test**

Exercise `DashboardRuntime.buildDatasetSnapshot` with the checked-in V9 values and assert the four totals, sorted typed counts, Baseline/Hybrid labels, 14-feature count, GraphSAGE arm, three seeds, and `0.7` fusion weight.

- [x] **Step 2: Add malformed-input coverage**

Pass missing metadata and invalid negative/non-integer counts and assert the view model returns `available: false` or unavailable subsections without throwing.

- [x] **Step 3: Add renderer contract assertions**

Require the renderer source to reference the dataset snapshot heading, total labels, node/edge breakdown classes, and both model-card labels. These assertions should fail until the renderer is updated.

- [x] **Step 4: Run the focused tests and verify the expected RED state**

Run:

```bash
rtk .venv/bin/pytest -q tests/test_v9_summary_page.py
```

Expected: the new tests fail because the dataset snapshot runtime and markup do not yet exist; the pre-existing renderer and syntax tests remain diagnosable.

### Task 2: Implement and verify the Overview snapshot

**Files:**
- Modify: `Documents/Data/scripts/v9_summary_page.py`
- Modify: `tests/test_v9_summary_page.py`

- [x] **Step 1: Add validated dataset/model view-model helpers**

Implement safe record/count/text helpers and `summaryBuildDatasetSnapshot(meta, overview, demo)`. Read only existing embedded payloads, sort typed counts by descending count with stable label tie-breaking, and return explicit unavailable states for malformed data.

- [x] **Step 2: Wire the renderer to the snapshot**

Call the view model with `D.meta`, `D.overview`, and `D.v9Demo`. Render the new block after the left-rail intro, with four totals, compact node/edge type lists, and model cards. Include configuration facts only when validated and label the oracle arm as synthetic-only/non-deployable.

- [x] **Step 3: Add focused styling**

Extend the existing summary CSS with responsive grid/list/card styles using current design tokens and the existing mobile breakpoint. Do not alter the current evidence-block styles or dashboard-wide tokens.

- [x] **Step 4: Run focused tests and syntax checks**

Run:

```bash
rtk .venv/bin/pytest -q tests/test_v9_summary_page.py tests/test_v9_dashboard_builder.py
rtk node --check - <(printf '%s\n' "$(rtk python - <<'PY'
from pathlib import Path
from Documents.Data.scripts import v9_summary_page
print(v9_summary_page.SUMMARY_PAGE_RUNTIME_JS)
print(v9_summary_page.SUMMARY_PAGE_RENDERER_JS)
PY
)")
```

The pytest command must pass. If process-substitution syntax is not supported by the active shell, use the repository’s existing Node-backed summary syntax test as the authoritative check.

- [x] **Step 5: Build the dashboard and inspect the generated artifact**

Run:

```bash
rtk .venv/bin/python Documents/Data/scripts/build_v9_dashboard.py
rtk rg -n "Dataset and models|636,606|2,090,447|HGB tabular baseline|GraphSAGE" Documents/Data/v9_dashboard/index.html
```

Confirm the generated HTML contains the new Overview strings and that the build exits successfully.

### Task 3: Final regression verification

**Files:**
- None expected.

- [x] **Step 1: Run the affected source suite**

```bash
rtk .venv/bin/pytest -q tests/test_v9_summary_page.py tests/test_v9_dashboard_builder.py tests/test_v9_design_system.py
```

- [x] **Step 2: Check the diff and generated-state boundaries**

```bash
rtk git diff --check
rtk git status --short
```

Confirm only the requested source/test/docs changes and expected generated dashboard outputs are attributable to this task; preserve unrelated existing changes.
