# Dashboard visual refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the generated V9 dashboard easier to read on a laptop and in projected or screenshot form while preserving its dark technical identity, data semantics, and interaction behavior.

**Architecture:** Keep the generated `dashboard_standalone.html` untouched as the base template. Put global palette, typography, surface, focus, responsive, and print changes in the tracked CSS layer emitted by `v9_design_system.py`; put V9 results and anomaly-ranking layout refinements in `v9_dashboard_ui.py`. Use the existing builder tests as the contract for generated markup and JavaScript behavior, and add only visual-contract assertions needed to lock the new direction.

**Tech Stack:** Python string-based HTML/CSS/JavaScript emitters, embedded WOFF2 fonts, pytest, existing generated-dashboard builder.

---

## Scope guardrails

- Work in the current workspace because the dashboard seam already contains active uncommitted changes; do not reset, stash, or isolate those changes.
- Do not modify model calculations, artifact selection, data contracts, tab routing, chart data, or as-of semantics.
- Do not add a theme toggle, framework, icon library, or new runtime dependency.
- Do not edit the generated dashboard directly; the builder will overwrite it.
- Follow the repository handoff rule: leave commits to the Historian unless the user explicitly asks for a commit.

## Files and responsibilities

- Modify `Documents/Data/scripts/v9_design_system.py`: deep-slate tokens, contrast-safe text ramp, series colors, shared spacing/shape/surface rules, chart legibility, focus states, and print inversion.
- Modify `Documents/Data/scripts/v9_dashboard_ui.py`: V9 results-specific hierarchy, story/summary surfaces, cards, tables, charts, legends, segmented controls, anomaly-ranking figures, and responsive presentation rules.
- Modify `tests/test_v9_design_system.py`: regression contracts for the new palette, readable type floor, surface hierarchy, series encoding, and focus/print behavior.
- Modify `tests/test_v9_dashboard_builder.py`: regression contracts ensuring the visual refresh does not change V9 results DOM ordering, ARIA relationships, generated tab behavior, or mobile wrapping/shrink assumptions.
- Do not modify `Documents/Data/scripts/build_v9_dashboard.py` unless a test proves a narrowly scoped markup hook is required; its role remains composition and publication.

### Task 1: Lock the new deep-slate visual tokens with tests

**Files:**
- Modify: `tests/test_v9_design_system.py`
- Modify: `Documents/Data/scripts/v9_design_system.py`

- [ ] **Step 1: Add failing token-contract tests**

Extend the existing `build_design_system_css()` tests with contracts for the approved direction:

```python
def test_dashboard_uses_readable_deep_slate_palette():
    css = build_design_system_css()
    expected = (
        "--bg:#0c1117",
        "--surface:#141c24",
        "--elevated:#1d2832",
        "--sunk:#070b10",
        "--text1:#f4f7fa",
        "--text2:#c0cbd5",
        "--text3:#93a1ad",
        "--accent:#5eead4",
        "--data-baseline:#e2e8f0",
        "--data-hybrid:#5eead4",
        "--data-gnn:#60a5fa",
    )
    assert all(token in css for token in expected)


def test_dashboard_visual_tokens_keep_essential_text_above_type_floor():
    css = build_design_system_css()
    assert "--fs-micro:11px" in css
    assert "--fs-xs:12px" in css
    assert "--fs-sm:13px" in css
    assert "--fs-base:14px" in css
```

Also update the existing `SURFACES` tuple to `("#0c1117", "#141c24", "#1d2832", "#070b10")`, update the dim-token surface assertion to `#141c24`, and update `test_type_scale_is_bounded()` to expect `11`. Keep the existing visible `--shadow-1:0 1px 2px rgba(0,0,0,.45)` contract; the new palette does not require a new shadow token.

Run: `rtk .venv/bin/python -m pytest tests/test_v9_design_system.py -q`

Expected: the new tests fail because the current token values and micro-type floor do not match the approved deep-slate/readability direction.

- [ ] **Step 2: Replace only the shared token values**

In `_TOKENS`, update the neutral palette to the exact values asserted above. Keep the existing token names and add semantic values without changing consumer selectors:

```css
:root{
  --bg:#0c1117;--surface:#141c24;--elevated:#1d2832;--sunk:#070b10;
  --text1:#f4f7fa;--text2:#c0cbd5;--text3:#93a1ad;--text-dim:#71808c;
  --accent:#5eead4;--accent-hover:#99f6e4;
  --accent-soft:rgba(94,234,212,.12);--accent-glow:rgba(94,234,212,.18);
  --positive:#5eead4;--warning:#fbbf24;
  --negative:#fb7185;--negative-soft:rgba(251,113,133,.14);
  --data-baseline:#e2e8f0;--data-hybrid:#5eead4;--data-gnn:#60a5fa;
  --data-context:#93a1ad;
  --fs-micro:11px;--fs-xs:12px;--fs-sm:13px;--fs-base:14px;
  --fs-md:15px;--fs-lg:19px;--fs-xl:26px;
}
```

Do not reintroduce Google-font loading or change the existing Outfit/JetBrains Mono face list.

- [ ] **Step 3: Run the token and existing design-system tests**

Run: `rtk .venv/bin/python -m pytest tests/test_v9_design_system.py -q`

Expected: PASS, including existing contrast, retired-color, type-floor, series-dash, focus, reduced-motion, print, and embedded-font contracts. If an existing test encodes a stale literal that contradicts the approved palette, update that test to assert the token contract rather than weakening the accessibility check.

### Task 2: Rebalance the global shell for scanability

**Files:**
- Modify: `Documents/Data/scripts/v9_design_system.py`
- Test: `tests/test_v9_design_system.py`

- [ ] **Step 1: Add a failing shell-hierarchy contract**

Add a test that checks the generated design-system layer contains the shared shell rules needed for readable projection:

```python
def test_dashboard_shell_uses_readable_shell_rhythm():
    css = build_design_system_css()
    assert ".metric-label,.metric-sub{color:var(--text2)" in css
    assert ".section-head{font-size:var(--fs-md);color:var(--text1)" in css
    assert ".chart-title{color:var(--text2)" in css
    assert ".axis .tick text{fill:var(--text2);font-size:12px" in css
```

Run: `rtk .venv/bin/python -m pytest tests/test_v9_design_system.py::test_dashboard_shell_uses_readable_shell_rhythm -q`

Expected: FAIL until the shared rhythm rules are updated.

- [ ] **Step 2: Update shared shell, surface, and chart rules**

Update `_SHAPE_AND_ELEVATION`, `_INTERACTION`, `_PROVENANCE`, and `_RHYTHM` so that:

```css
header{background:var(--surface);border-bottom-color:var(--border-strong)}
nav.tabs{background:var(--sunk);border-bottom-color:var(--border-strong)}
nav.tabs button{font-size:13px;color:var(--text2);padding:15px 18px}
nav.tabs button.active{color:var(--accent-hover);border-bottom-color:var(--accent)}
.metric-label,.metric-sub{color:var(--text2)}
.section-head{font-size:var(--fs-md);color:var(--text1)}
.section-note,.chart-title{color:var(--text2)}
.axis .tick text{fill:var(--text2);font-size:12px}
.grid line{stroke:var(--border-strong);opacity:.72}
.chart-panel,.map-container,.filter-panel,.network-canvas,.network-side,
.xp-canvas,.xp-side,.xp-tools,.uad-card,.uad-figure,
#tab-v9Results .v9-card,#tab-v9Results .v9-recovery-workspace{
  background:var(--surface);border-color:var(--border-strong)
}
```

Keep the existing focus-visible selector, reduced-motion block, shrink rules, and print inversion. Use existing tokenized shadow/radius rules; do not add generic black shadows or a new radius scale.

- [ ] **Step 3: Run focused shell tests**

Run: `rtk .venv/bin/python -m pytest tests/test_v9_design_system.py -q`

Expected: PASS with the updated shell hierarchy, no regressions in focus, motion, print, or series-encoding contracts.

### Task 3: Refine the V9 results readout without changing markup contracts

**Files:**
- Modify: `Documents/Data/scripts/v9_dashboard_ui.py`
- Modify: `tests/test_v9_dashboard_builder.py`

- [ ] **Step 1: Add presentation-contract assertions**

Extend the existing V9 builder tests to assert the stylesheet still contains the agreed visual hooks. Keep the existing builder tests for results ordering, IDs, ARIA relationships, and hidden accessible tables as the DOM regression contract; do not add a new fixture just for this visual pass:

```python
def test_v9_results_style_keeps_headline_and_supporting_groups_distinct():
    assert ".v9-summary-lead" in V9_RESULTS_CSS
    assert ".v9-summary-stat" in V9_RESULTS_CSS
    assert ".v9-story" in V9_RESULTS_CSS
    assert ".v9-chart-block" in V9_RESULTS_CSS
    assert ".v9-seg button.on" in V9_RESULTS_CSS
```

The test imports the existing `V9_UI` module already used by the layout tests and verifies `V9_UI.V9_RESULTS_CSS`; the surrounding existing tests continue to verify results ordering, IDs, ARIA relationships, and hidden accessible data tables.

- [ ] **Step 2: Update V9 result CSS in place**

Keep `V9_RESULTS_CSS` as the single V9-specific stylesheet and update these selector groups:

1. **Readout lead:** use a deep-slate surface with a stronger teal edge/gradient, make `.v9-summary-title` and `.v9-summary-stat b` the most prominent values, and set supporting copy to `var(--text2)`.
2. **Story block:** reduce competing decorative colors, use `var(--data-gnn)`, `var(--warning)`, and `var(--positive)` only where they encode meaning, and make the story title/body readable at `var(--fs-lg)` / `var(--fs-base)`.
3. **Cards and tables:** use `var(--surface)`/`var(--elevated)` with `var(--border-strong)`, `var(--text1)` headings, `var(--text2)` body text, and `var(--text3)` only for non-essential metadata. Increase table cell padding and keep horizontal scrolling only as a narrow-screen fallback.
4. **Charts:** use 12px axis/legend labels, brighter rules, more visible hover targets, and the existing dash/marker redundancy. Keep the simulated chart's intentional minimum width but add a visible scroll affordance through the existing focus style.
5. **Controls:** make selected segmented buttons use `var(--accent-soft)` plus `var(--accent-hover)` text and a quiet inset highlight; keep `aria-pressed` and `aria-label` behavior unchanged.
6. **Responsive layout:** retain the current breakpoint behavior, but ensure summary stats, capacity rows, simulated metric grids, and chart headers wrap without clipped text.

Do not change `SIMULATED_CATCH_VIEW_MODEL_JS`, `DAILY_CROSSING_SELECTION_JS`, or `V9_RESULTS_JS` unless a class hook is strictly necessary for styling. If a hook is needed, add only a semantic class and preserve all data and accessibility attributes.

- [ ] **Step 3: Run V9 builder tests**

Run: `rtk .venv/bin/python -m pytest tests/test_v9_dashboard_builder.py -q`

Expected: PASS for DOM order, ARIA relationships, selectors, mobile wrapping, shrink behavior, JavaScript injection/syntax, recovery artifact contracts, and simulated-view-model behavior.

### Task 4: Rebuild and verify the generated dashboard at representative widths

**Files:**
- Generate/inspect only: `Documents/Data/v9_dashboard/index.html`
- Generate/inspect only: `Documents/Data/v9_dashboard/data_v9.json`

- [ ] **Step 1: Run the source and builder smoke suite before rebuilding**

Run:

```bash
rtk .venv/bin/python -m pytest \
  tests/test_v9_design_system.py \
  tests/test_v9_dashboard_builder.py \
  tests/test_v9_summary_page.py \
  tests/test_v9_recovery_explainer_ui.py -q
```

Expected: PASS before manual inspection. If a failure comes from the active uncommitted schema-3/recovery work, isolate whether it is pre-existing before changing visual code.

- [ ] **Step 2: Build the V9 dashboard through the tracked builder**

Run: `rtk .venv/bin/python Documents/Data/scripts/build_v9_dashboard.py`

Expected: the builder publishes `Documents/Data/v9_dashboard/index.html` and `data_v9.json` without changing any corpus source files, and reports the local HTTP-server command.

- [ ] **Step 3: Inspect generated output structurally**

Run:

```bash
rtk rg -n --glob 'index.html' \
  'v9-summary|v9-story|v9-chart-block|v9-simulated-chart|aria-label|--bg:#0c1117|--text3:#93a1ad' \
  Documents/Data/v9_dashboard
rtk .venv/bin/python -m pytest tests/test_run_demo_smoke.py tests/test_v9_corpus_snapshot.py -q
```

Expected: the generated HTML contains the new token layer and existing V9 visual/accessibility hooks; unrelated demo/corpus smoke tests remain green.

- [ ] **Step 4: Perform visual QA at desktop and narrow widths**

Serve the generated dashboard with the existing local command:

```bash
rtk .venv/bin/python -m http.server 8000 --directory Documents/Data/v9_dashboard
```

Inspect the Overview and V9 results readout at approximately 1440px and 900px widths. Verify:

- the headline finding is visible first;
- primary and supporting text are readable without zooming;
- Baseline / Hybrid / GNN remain distinct in charts and legends;
- tables and charts do not clip or create unexplained horizontal overflow;
- tabs, segmented controls, legends, and chart scroll regions have visible focus states;
- narrative, charts, recovery/explanation panels, and anomaly-ranking panels share the same surface/token language.

If the browser companion remains unavailable, record visual QA using generated HTML inspection plus the existing test suite and report that limitation rather than claiming interactive screenshot verification.

- [ ] **Step 5: Final regression check and diff review**

Run:

```bash
rtk git diff --check
rtk git status --short
rtk .venv/bin/python -m pytest tests/test_v9_design_system.py tests/test_v9_dashboard_builder.py -q
```

Expected: no whitespace errors, only the intended source/spec/plan changes are attributable to this task, and focused tests pass. Do not include or alter the pre-existing large artifact/uncommitted research changes.

## Plan self-review

- Spec coverage: palette, type scale, hierarchy, chart encoding, responsive behavior, accessibility, print styling, non-goals, and verification are covered in Tasks 1–4.
- No placeholder steps: every task names files, commands, expected outcomes, and the selectors/contracts to change.
- Type consistency: the existing token names (`--bg`, `--surface`, `--text1`, `--text2`, `--text3`, `--data-baseline`, `--data-hybrid`, `--data-gnn`) are reused across both CSS layers and tests.
- Scope check: no model, artifact, renderer, data, or navigation behavior is included.
