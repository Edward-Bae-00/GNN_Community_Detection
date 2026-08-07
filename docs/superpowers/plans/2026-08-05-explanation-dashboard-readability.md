# Explanation Dashboard Readability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the V9 schema-3 explanation explorer around a narrative-first case readout plus a compact ranking comparison, while formatting every displayed number to at most three decimal places.

**Architecture:** Keep all artifact validation, sidecar loading, graph commands, and as-of semantics unchanged. Add a shared presentation formatter and JSON numeric replacer inside the existing recovery UI module, then update only V2/V3 render strings and scoped CSS. Add a Stitch-ready `DESIGN.md` that documents the implemented visual tokens and anti-patterns.

**Tech Stack:** Python string constants, browser JavaScript, CSS, pytest, Node-based DOM harnesses, generated standalone HTML dashboard.

---

## File map

- Create: `DESIGN.md` — Stitch-ready semantic design system for the explanation dashboard.
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py` — shared numeric formatting, V3 hierarchy, V2 fallback formatting, scoped visual styles.
- Modify: `tests/test_v9_recovery_explainer_ui.py` — formatter, DOM order, three-decimal, and CSS contract coverage.
- Modify: `Documents/Data/changes_3.md` — short implementation note after verification, keeping research semantics explicit.
- Regenerate: `Documents/Data/v9_dashboard/index.html` and `Documents/Data/v9_dashboard/data_v9.json` only through the existing builder if the build changes them.

The generated dashboard is not edited by hand. Existing unrelated worktree changes must remain untouched.

### Task 1: Lock the numeric presentation contract with failing tests

**Files:**
- Test: `tests/test_v9_recovery_explainer_ui.py`
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py`

- [x] **Step 1: Add a Node formatter harness test.**

Append a Python helper/test near the existing `_run_ui` helpers:

```python
def _run_display_formatter(expression):
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\\nprocess.stdout.write(JSON.stringify("
        + expression
        + "));"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def test_recovery_display_formatter_caps_precision_and_handles_signs():
    result = _run_display_formatter(
        "[recoveryFormatNumber(0.8427),recoveryFormatNumber(0.5),"
        "recoveryFormatNumber(1),recoveryFormatSigned(-4),"
        "recoveryFormatSigned(32),recoveryFormatNumber(NaN)]"
    )
    assert result == ["0.843", "0.5", "1", "-4", "+32", "not available"]


def test_recovery_debug_json_formatter_caps_nested_numbers():
    result = _run_display_formatter(
        "recoveryFormatJson({a:0.123456,b:[1.2,0.5000],nested:{c:9.9999}})"
    )
    assert result == '{\\n  "a": 0.123,\\n  "b": [\\n    1.2,\\n    0.5\\n  ],\\n  "nested": {\\n    "c": 10\\n  }\\n}'
```

- [x] **Step 2: Run the new tests and confirm they fail.**

Run:

```bash
rtk .venv/bin/python -m pytest tests/test_v9_recovery_explainer_ui.py -k 'display_formatter or debug_json_formatter' -q
```

Expected: FAIL because `recoveryFormatNumber`, `recoveryFormatSigned`, and `recoveryFormatJson` do not yet exist.

- [x] **Step 3: Implement the shared formatter at the top of `V9_RECOVERY_EXPLAINER_JS`.**

Use one presentation seam for every renderer:

```javascript
function recoveryFormatNumber(value){
  if(value===null||value===undefined||value==='')return 'not available';
  const number=Number(value);
  if(!Number.isFinite(number))return 'not available';
  if(Object.is(number,-0))return '0';
  return new Intl.NumberFormat('en-US',{
    maximumFractionDigits:3,
    useGrouping:true
  }).format(number);
}

function recoveryFormatSigned(value){
  if(value===null||value===undefined||value==='')return 'not available';
  const number=Number(value);
  if(!Number.isFinite(number))return 'not available';
  return (number>0?'+':'')+recoveryFormatNumber(number);
}

function recoveryFormatJson(value){
  return JSON.stringify(value,(_,entry)=>{
    if(typeof entry==='number'&&Number.isFinite(entry)){
      return Number(entry.toFixed(3));
    }
    return entry;
  },2);
}
```

Keep raw numbers for geometry, bar widths, sorting, validation, and `aria-valuenow`; only text and JSON serialization use these helpers.

- [x] **Step 4: Route every existing display path through the formatter.**

Make these exact substitutions without changing validation:

```javascript
// recoveryV2Panel
panel.appendChild(recoveryElement(doc,'pre','',recoveryFormatJson(value||null)));

// mountRecoveryExplorerV2 and mountRecoveryExplorerV3
const fmt=value=>recoveryFormatNumber(value);

// renderHighestAttributionPanel
recoveryFormatNumber(row.weight)

// renderRanks
recoveryFormatNumber(record.baseline_raw)
recoveryFormatNumber(record.baseline_percentile)
recoveryFormatNumber(record.seed0_gnn_percentile)
recoveryFormatNumber(record.seed0_gnn_probability)
recoveryFormatNumber(record.seed0_hybrid_score)

// renderStabilityAndFaithfulness
recoveryFormatNumber(faithfulness.original_probability)
recoveryFormatNumber(point.fraction)
recoveryFormatNumber(point.top_edge_probability_drop)
recoveryFormatNumber(point.matched_random_probability_drop)
recoveryFormatNumber(point.unmatched_control_count)

// graph data tables
recoveryFormatNumber(node.importance)
recoveryFormatNumber(edge.importance)
```

Use `recoveryFormatSigned(effect)` for counterfactual rank movement, route visible graph aria counts through `fmt(...)`, and keep missing matched controls as `not measured`.

- [x] **Step 5: Run the formatter tests again.**

Run the same command from Step 2. Expected: PASS.

### Task 2: Add the combined narrative-first case hierarchy

**Files:**
- Test: `tests/test_v9_recovery_explainer_ui.py`
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py:2398-2905`

- [x] **Step 1: Add a V3 DOM-order test with over-precision fixture values.**

Extend `_schema3_served_bundle()` fixture values so the selected record includes `0.8427`, `0.3184`, and `0.6719` display values, then add:

```python
def test_schema3_mount_uses_narrative_first_ranking_strip_and_three_decimals():
    rendered = _mount_schema3("h1")
    text = " | ".join(rendered["text"])

    assert "Why this case surfaced" in text
    assert "Baseline" in text and "Seed-0 GNN" in text and "Seed-0 Hybrid" in text
    assert "places higher than Baseline" in text
    assert text.index("Grounded narrative") < text.index(
        "As-of community context + explanation evidence"
    )
    assert "0.843" in text
    assert "0.8427" not in text
    assert "0.3184" not in text
    assert "0.6719" not in text
```

- [x] **Step 2: Run the new DOM test and confirm it fails.**

Run:

```bash
rtk .venv/bin/python -m pytest tests/test_v9_recovery_explainer_ui.py -k 'narrative_first_ranking_strip' -q
```

Expected: FAIL because the current header has no narrative-first title and no plain-language ranking movement.

- [x] **Step 3: Implement the ranking strip view model and render order.**

In `mountRecoveryExplorerV3`, add a small pure helper before `renderRanks`:

```javascript
function recoveryRankDelta(record){
  const baseline=Number(record.baseline_rank);
  const hybrid=Number(record.seed0_hybrid_rank);
  return Number.isSafeInteger(baseline)&&Number.isSafeInteger(hybrid)
    ?baseline-hybrid:null;
}
```

Update `renderHeader` to group the eyebrow/title/intro into a copy block and add the selected-case status only when a record is available. Update `renderRanks` to render three `.v9-recovery-rank` cells and a `.v9-recovery-rank-delta` sentence using `recoveryRankDelta`. Keep labels explicit and keep the score semantics copy below the rank values.

In `renderSelectedEvidence`, call `renderNarrative` before `renderFactors`, then render stability/faithfulness, attribution, and graph. Keep controls and data tables in the same lazy-loaded path.

- [x] **Step 4: Update the case rail text without changing filters.**

Replace the `B ... / H ...` string in the V3 case button with a formatted delta line:

```javascript
const delta=recoveryRankDelta(record);
addText(button,'div','v9-recovery-case-meta',
  record.cohort+' · '+(record.detailStatus||'not_selected'));
addText(button,'div','v9-recovery-case-evidence',
  delta===null?'Rank movement unavailable':
    recoveryFormatSigned(delta)+' places vs baseline');
```

Preserve the existing accessible case label and evidence/detail status values.

- [x] **Step 5: Run focused V3 tests.**

Run:

```bash
rtk .venv/bin/python -m pytest tests/test_v9_recovery_explainer_ui.py -k 'schema3_mount or graph_copy or highest_attribution' -q
```

Expected: PASS, with any existing assertions updated only where the intentionally changed presentation strings are covered.

### Task 3: Apply the premium readability system and create the Stitch source of truth

**Files:**
- Create: `DESIGN.md`
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py` CSS constant
- Test: `tests/test_v9_recovery_explainer_ui.py`

- [x] **Step 1: Add CSS contract assertions before changing styles.**

Add assertions for the new scoped selectors and responsive rules:

```python
def test_schema3_readability_system_uses_clear_zones_and_touch_targets():
    css = UI.V9_RECOVERY_EXPLAINER_CSS
    for token in (
        ".v9-recovery-header-copy",
        ".v9-recovery-rank-delta",
        ".v9-recovery-rank.is-primary",
        "min-height: 44px",
        "font-family: Outfit",
        "font-family: 'JetBrains Mono'",
        "@media(max-width:900px)",
        "@media(max-width:700px)",
    ):
        assert token in css
```

- [x] **Step 2: Run the CSS test and confirm it fails.**

Run:

```bash
rtk .venv/bin/python -m pytest tests/test_v9_recovery_explainer_ui.py -k 'readability_system' -q
```

Expected: FAIL until the new selectors/tokens exist.

- [x] **Step 3: Update only the recovery-scoped CSS.**

Add the following style intent to `V9_RECOVERY_EXPLAINER_CSS`:

```css
#tab-v9Results .v9-recovery-header-copy{min-width:0;max-width:760px}
#tab-v9Results .v9-recovery-case-header{display:grid;gap:12px}
#tab-v9Results .v9-recovery-ranks{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
#tab-v9Results .v9-recovery-rank{min-height:72px;padding:12px;border-top:2px solid var(--border-strong);border-left:0}
#tab-v9Results .v9-recovery-rank.is-primary{border-top-color:var(--accent);background:var(--accent-soft)}
#tab-v9Results .v9-recovery-rank-delta{margin-top:4px;color:var(--accent-hover);font-size:12px;line-height:1.4}
#tab-v9Results .v9-recovery-narrative{padding:18px;border-radius:10px}
#tab-v9Results .v9-recovery-narrative p{font-size:13px;line-height:1.6}
#tab-v9Results .v9-recovery-button,
#tab-v9Results .v9-recovery-case,
#tab-v9Results .v9-recovery-factor{min-height:44px}
#tab-v9Results .v9-recovery-v3 .v9-recovery-canvas-wrap{background:var(--sunk)}
@media(max-width:700px){
  #tab-v9Results .v9-recovery-ranks{grid-template-columns:1fr}
  #tab-v9Results .v9-recovery-rank{min-height:0}
}
```

Use the existing embedded Outfit/JetBrains Mono dashboard fonts via the existing design-system layer. Do not add a new network font import, gradient text, glow, or animation.

- [x] **Step 4: Create `DESIGN.md` from the approved Stitch brief.**

Document the implemented atmosphere, exact neutral/accent roles, Outfit/JetBrains Mono typography, layout rules, number formatting rule, component behavior, responsive breakpoints, motion restraint, accessibility targets, and explicit bans (no emojis, Inter, pure black, neon glows, equal three-card rows, filler copy, or overlapping content). State that semantic evidence/warning colors are functional encodings rather than decorative accents.

- [x] **Step 5: Run CSS and DOM tests.**

Run:

```bash
rtk .venv/bin/python -m pytest tests/test_v9_recovery_explainer_ui.py -k 'readability_system or schema3_mount or schema3_css' -q
```

Expected: PASS.

### Task 4: Preserve builder contracts and rebuild the dashboard

**Files:**
- Test: `tests/test_v9_dashboard_builder.py`
- Modify if needed: `Documents/Data/changes_3.md`
- Regenerate: `Documents/Data/v9_dashboard/index.html`, `Documents/Data/v9_dashboard/data_v9.json`

- [x] **Step 1: Add a builder source-contract assertion.**

Extend the existing recovery injection test with:

```python
assert "recoveryFormatNumber" in injected
assert "v9-recovery-rank-delta" in injected
assert "Why this case surfaced" in injected
```

Keep existing injection markers and `DATA.v9RecoveryExplainer` validation unchanged.

- [x] **Step 2: Run the focused builder tests before rebuilding.**

Run:

```bash
rtk .venv/bin/python -m pytest tests/test_v9_dashboard_builder.py -q
```

Expected: PASS after any presentation-only expected-string updates.

- [x] **Step 3: Rebuild using the repository’s supported command.**

Run:

```bash
rtk .venv/bin/python Documents/Data/scripts/build_v9_dashboard.py
```

Expected: the builder completes without changing corpus data or recovery sidecars and emits the updated explanation CSS/JS in `Documents/Data/v9_dashboard/index.html`.

- [x] **Step 4: Record the presentation change in `changes_3.md`.**

Add a short dated note stating that the explanation explorer now leads with grounded narrative plus an explicit Baseline/GNN/Hybrid rank comparison, and that all displayed numeric text is capped at three decimal places. Explicitly state that artifact precision and as-of/model semantics are unchanged.

- [x] **Step 5: Run the complete focused verification set.**

Run:

```bash
rtk .venv/bin/python -m pytest tests/test_v9_recovery_explainer_ui.py tests/test_v9_dashboard_builder.py tests/test_run_demo_smoke.py -q
rtk .venv/bin/python -m py_compile Documents/Data/scripts/v9_recovery_explainer_ui.py Documents/Data/scripts/build_v9_dashboard.py
rtk git diff --check
```

Expected: all focused tests pass, compilation succeeds, and `git diff --check` produces no output.

### Task 5: Visual and scope review

**Files:**
- Inspect: `Documents/Data/v9_dashboard/index.html`
- Inspect: `DESIGN.md`
- Inspect: `git diff`

- [x] **Step 1: Verify desktop and narrow layouts through the available browser workflow.**

Serve the rebuilt dashboard with the existing local HTTP command and inspect the V9 Results explanation section at desktop and narrow widths. Confirm the narrative appears before the graph, the ranking strip is legible, no horizontal overflow is introduced, controls retain 44px targets, and the graph/table fallback remains usable.

- [x] **Step 2: Check the rendered text for precision leaks.**

Search the generated explanation source for raw `String(`/`.toFixed(` display paths and inspect the runtime text for values with four or more fractional digits. Geometry and numeric ARIA values may remain raw; visible text must not.

- [x] **Step 3: Review the final diff for scope.**

Run:

```bash
rtk git diff --stat
rtk git status --short
```

Confirm only the approved UI source, tests, design/docs, and generated dashboard outputs changed; preserve all pre-existing unrelated worktree changes.
