# V9 Results order Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorder the V9 Results tab into a concise live-demo narrative without changing metrics, model behavior, data contracts, or existing interactions.

**Architecture:** Keep the static HTML and vanilla JavaScript injection architecture. Reorder the existing `sec.innerHTML` sections in `V9_RESULTS_JS`, split the daily chart block so cumulative unique-person recovery is read before event-volume context, and place model notes, architecture comparison, and run metrics in a supporting methods tail. Add source-order assertions to the existing dashboard contract tests.

**Tech Stack:** Python string templates, vanilla JavaScript, CSS tokens, pytest, Node syntax checks, generated static HTML.

---

### Task 1: Lock the approved source order with a failing test

**Files:**
- Modify: `tests/test_v9_dashboard_builder.py:31-61,620-664`

- [ ] **Step 1: Update the frozen IDs to the approved visual order**

Use this sequence in `FROZEN_V9_RESULT_IDS`:

```python
FROZEN_V9_RESULT_IDS = (
    "v9-summary",
    "v9-story-title",
    "v9-pop",
    "v9-bars",
    "v9-daily",
    "v9-simulated-catches",
    "v9-simulated-title",
    "v9-simulated-mode",
    "v9-simulated-k",
    "v9-simulated-summary",
    "v9-simulated-volume",
    "v9-daily-found-k",
    "v9-volume",
    "v9-case-evidence",
    "v9-sig",
    "v9-model-notes",
    "v9-metrics",
)
```

- [ ] **Step 2: Change the architecture-order assertions to the new boundary**

Replace the old additive-order assertions with checks that the story precedes operational results, operational results precede recovery, recovery precedes bootstrap, and bootstrap precedes methods:

```python
def test_v9_results_uses_live_demo_order():
    js = V9_UI.V9_RESULTS_JS
    architecture_mount = (
        '<section id="v9-gnn-architecture-comparison" '
        'aria-labelledby="v9-gnn-architecture-title"></section>'
    )

    assert js.index('class="v9-story"') < js.index('id="v9-pop"')
    assert js.index('id="v9-pop"') < js.index('id="v9-case-evidence"')
    assert js.index('id="v9-case-evidence"') < js.index("Bootstrap verdicts")
    assert js.index("Bootstrap verdicts") < js.index('id="v9-model-notes"')
    assert js.index('id="v9-model-notes"') < js.index(architecture_mount)
    assert js.index(architecture_mount) < js.index('id="v9-metrics"')
    assert js.index("'Base Models': [], 'Hybrid Models': [], 'GNN Models': []") < js.index(
        "Object.entries(groups)"
    )
```

Keep the existing exactly-once mount and accessibility assertions.

- [ ] **Step 3: Run the focused order test and confirm it fails before implementation**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_v9_dashboard_builder.py -k "live_demo_order or architecture_mount"
```

Expected: FAIL because the current renderer places architecture before the story and metrics before the methods tail.

### Task 2: Reorder the V9 renderer for the live demo

**Files:**
- Modify: `Documents/Data/scripts/v9_dashboard_ui.py:257-324`

- [ ] **Step 1: Move the three-lens story directly below the headline summary**

Keep its current copy and IDs. Place the story immediately after the `v9-summary` block and before `v9-pop`. Do not add a new paragraph.

- [ ] **Step 2: Group the operational result panels in this order**

Render the existing controls and mounts in this sequence:

```text
Baseline vs Hybrid vs GNN
  population toggle
  Depth event recall / v9-bars
  Daily capacity view / v9-daily
  Simulated catches / v9-simulated-catches
  Daily Crossing Volume / v9-volume
```

Keep `v9-simulated-mode` defaulted to cumulative and keep its accessibility table contract unchanged. Make the simulated-catches card a sibling of the daily crossing card so the live demo can show unique-person recovery before event-volume context. Preserve all existing selectors, chart controls, and subtitles; only shorten or reuse copy where the current sentence is redundant.

- [ ] **Step 3: Place recovery evidence after operational results**

Keep the existing `v9-case-evidence` mount exactly once, after the operational group and before the bootstrap card. Preserve the recovery renderer invocation and `DATA.v9RecoveryExplainer` input.

- [ ] **Step 4: Place bootstrap confidence after recovery evidence**

Keep both bootstrap tables, explanatory terms, and population semantics unchanged. The card remains headed `Bootstrap verdicts` and retains `v9-sig` exactly once.

- [ ] **Step 5: Move model notes, architecture comparison, and metrics to the methods tail**

Render a compact methods tail after bootstrap:

```html
<section class="v9-methods" aria-labelledby="v9-methods-title">
  <h3 id="v9-methods-title">How the models work</h3>
  <div id="v9-model-notes"></div>
  <section id="v9-gnn-architecture-comparison" aria-labelledby="v9-gnn-architecture-title"></section>
  <div id="v9-metrics"></div>
</section>
```

Use the existing model-note copy and architecture renderer. Change only the group order in `drawModelNotes` to `Base Models`, `Hybrid Models`, `GNN Models`, so every lineup follows Baseline, Deployable Hybrid, GNN.

- [ ] **Step 6: Add only the layout CSS needed by the new methods wrapper**

Add a small `.v9-methods` spacing rule using existing borders and surface tokens. Do not introduce a new color, font, dependency, animation, or card family.

### Task 3: Verify source contracts and generated output

**Files:**
- Modify: `Documents/Data/changes_3.md`
- Modify: `PROJECT_MEMORY.md`
- Regenerate: `Documents/Data/v9_dashboard/index.html` and `Documents/Data/v9_dashboard/data_v9.json` only if the builder writes them

- [ ] **Step 1: Run the focused tests**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_v9_dashboard_builder.py tests/test_v9_recovery_explainer_ui.py
```

Expected: all tests pass.

- [ ] **Step 2: Validate the injected JavaScript syntax**

Run the existing builder test path plus:

```bash
rtk .venv/bin/python -m py_compile Documents/Data/scripts/v9_dashboard_ui.py Documents/Data/scripts/build_v9_dashboard.py
```

Expected: no syntax errors.

- [ ] **Step 3: Rebuild the dashboard**

```bash
rtk .venv/bin/python Documents/Data/scripts/build_v9_dashboard.py
```

Expected: the builder writes the dashboard without errors and the generated HTML contains each preserved V9 mount exactly once.

- [ ] **Step 4: Run a visual smoke check**

Serve the generated dashboard with the repository's documented local server and inspect `#tab-v9Results` at desktop and mobile widths. Confirm the first viewport shows the headline, three lenses, and the beginning of operational results, with no architecture panel before the results.

- [ ] **Step 5: Record the durable ordering decision**

Append a short dated note to `Documents/Data/changes_3.md` and `PROJECT_MEMORY.md` stating that V9 Results is now ordered as readout, operations, evidence, confidence, methods, with concise live-demo copy. Do not report new metrics.
