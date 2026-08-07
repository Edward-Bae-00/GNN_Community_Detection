# Guided Overview and Confidence-Interval Explanation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the V9 Overview and bootstrap confidence-interval explanation easier to understand without changing any artifact, metric, model, or evaluation behavior.

**Architecture:** Keep the existing DOM-rendering and source-contract architecture. Reorder the Overview's existing evidence blocks so the reader sees the operational result, mechanism, and limits before the dataset/model inventory; rewrite only the explanatory strings in the existing bootstrap panel. No new runtime fields, controls, charts, or statistical calculations are needed.

**Tech Stack:** Python string modules, browser JavaScript rendered by the dashboard builder, pytest, Node syntax checks.

---

## File map

- `Documents/Data/scripts/v9_summary_page.py`: Overview runtime validation, CSS, and DOM renderer. It owns the guided result/mechanism/limits ordering.
- `Documents/Data/scripts/v9_dashboard_ui.py`: V9 results tab markup and bootstrap explanation copy. It owns the CI glossary next to the existing verdict table.
- `tests/test_v9_summary_page.py`: Node-backed runtime and renderer contract tests for Overview.
- `tests/test_v9_dashboard_builder.py`: source-contract tests for CI language and V9 result-section ordering.
- `Documents/Data/changes_3.md`: short user-facing changelog entry.
- `docs/superpowers/specs/2026-08-06-guided-overview-ci-design.md`: approved design; do not alter unless the user requests a design change.

## Task 1: Add failing source-contract tests

**Files:**

- Modify: `tests/test_v9_summary_page.py`
- Modify: `tests/test_v9_dashboard_builder.py`

- [x] **Step 1: Add the Overview ordering contract.** Append a test to `tests/test_v9_summary_page.py` that checks the renderer contains the exact guided headings and that the order is result → mechanism → limits → dataset:

```python
def test_summary_renderer_uses_guided_evidence_order_and_plain_language_headings():
    renderer = SUMMARY.SUMMARY_PAGE_RENDERER_JS

    for marker in (
        "What the result means",
        "Why the graph can help",
        "Limits and provenance",
        "Dataset and models",
        "V9 is a designed positive control",
    ):
        assert marker in renderer
    assert renderer.index("What the result means") < renderer.index("Why the graph can help")
    assert renderer.index("Why the graph can help") < renderer.index("Limits and provenance")
    assert renderer.index("Limits and provenance") < renderer.index("Dataset and models")
```

- [x] **Step 2: Add the CI explanation contract.** Add a test to `tests/test_v9_dashboard_builder.py` that checks the four reader questions and the event/person distinction:

```python
def test_v9_ui_explains_bootstrap_intervals_as_paired_gap_variability():
    ui = UI_MODULE_PATH.read_text()
    for marker in (
        "What is re-sampled?",
        "What is measured?",
        "What does 95% CI mean here?",
        "How should it be read?",
        "same re-drawn events",
        "Hybrid minus baseline",
        "not the probability that the true gap is inside the interval",
        "interval crossing zero is inconclusive",
        "event hits, not unique people",
    ):
        assert marker in ui
```

- [x] **Step 3: Run only the new tests and confirm they fail** because the current source does not contain the new headings/copy.

Run:

```bash
rtk pytest -q tests/test_v9_summary_page.py::test_summary_renderer_uses_guided_evidence_order_and_plain_language_headings tests/test_v9_dashboard_builder.py::test_v9_ui_explains_bootstrap_intervals_as_paired_gap_variability
```

Expected: both tests fail with an assertion showing the old headings/copy.

## Task 2: Implement the guided Overview ordering and copy

**Files:**

- Modify: `Documents/Data/scripts/v9_summary_page.py`

- [x] **Step 1: Change the left brief to the approved result-first framing.** Keep the existing kicker and DOM helpers, but use this headline and paragraph:

```javascript
heading(brief,'h2','A graph helps recover more people at operational depth.');
para(brief,'V9 is a deliberately connected synthetic positive control. It asks whether an as-of graph signal can help a deployable Hybrid recover people that a strong tabular baseline misses. This does not replace the V8 honest track, where graph signal is intentionally thin.');
```

- [x] **Step 2: Move the existing dataset/model block after the result, mechanism, and limits blocks.** Keep `summaryBuildDatasetSnapshot`, all existing malformed/unavailable handling, and all model metadata unchanged. The renderer must create blocks in this order:

```javascript
const operational=block(console,'operational-evidence','What the result means');
const mechanism=block(console,'mechanism-evidence','Why the graph can help');
const limits=block(console,'limits-evidence','Limits and provenance');
const dataset=block(console,'dataset-model-evidence','Dataset and models');
```

Use these surrounding paragraphs while keeping the existing metrics and values:

```javascript
para(operational,'Canonical three-seed operational comparison. At the stated daily inspection depth, the values below count unique people recovered—not event hits.');
para(mechanism,'The positive-control signal propagates through co-travel, shared plate, and residence links. The model may use only graph edges and caught labels available strictly before each event time T.');
```

- [x] **Step 3: Keep secondary diagnostics and semantics after the guided brief.** Retain the existing single-seed observability block and Metric semantics disclosure after the limits/dataset sections. Do not reintroduce the removed event-depth section or alter runtime validation.

- [x] **Step 4: Run the Overview tests.**

Run:

```bash
rtk pytest -q tests/test_v9_summary_page.py
```

Expected: all Summary page tests pass, including the new ordering contract and Node syntax check.

## Task 3: Implement the guided confidence-interval explanation

**Files:**

- Modify: `Documents/Data/scripts/v9_dashboard_ui.py`

- [x] **Step 1: Replace the bootstrap hint and lead with the paired-resampling explanation.** Use this copy in the existing card:

```javascript
+'<div class="v9-card v9-card-spaced"><h3>Daily bootstrap verdicts</h3><div class="v9-hint">Does the Hybrid event-hit lead persist when we re-draw the test events many times and keep the same daily inspection quota?</div>'
+'<div class="v9-explain"><p class="v9-explain-lead">Each bootstrap replicate re-draws test events with replacement. Both rankers score the <b>same re-drawn event pool</b>, rank events within each day, and keep the same per-day inspection quota. We record the Hybrid minus baseline hidden-positive event-hit gap for that replicate, so the table shows how the gap varies across re-draws—not just in one run.</p>'
```

- [x] **Step 2: Replace the existing four glossary entries while keeping the same `dt`/`dd` structure and verdict pills.** Use these reader-question labels and definitions:

```javascript
+'<div><dt>What is re-sampled?</dt><dd>Test events are re-drawn with replacement; daily ranking and quotas are then applied to the sampled events.</dd></div>'
+'<div><dt>What is measured?</dt><dd>Each replicate measures the Hybrid minus baseline gap in hidden-positive event hits.</dd></div>'
+'<div><dt>What does 95% CI mean here?</dt><dd>The middle 95% of the re-drawn gaps. It describes resampling variability, not the probability that the true gap is inside the interval.</dd></div>'
+'<div><dt>How should it be read?</dt><dd><span class="v9-pill win">Hybrid win</span> interval entirely above zero <span class="v9-explain-sep">/</span> <span class="v9-pill tie">wash</span> interval crossing zero is inconclusive <span class="v9-explain-sep">/</span> <span class="v9-pill loss">baseline win</span> interval entirely below zero</dd></div>'
```

- [x] **Step 3: Replace the footnote with the event/person distinction.** Use:

```javascript
+'<p class="v9-explain-foot">Each row gives every test day a fixed quota and scores the whole event pool. These bootstrap rows count event hits, not unique people; use the recovery explorer for the unique-person question.</p></div>'
```

Keep `pill(summary)` and all table calculations untouched.

- [x] **Step 4: Run the V9 dashboard contract tests.**

Run:

```bash
rtk pytest -q tests/test_v9_dashboard_builder.py
```

Expected: all dashboard-builder tests pass, including the new CI explanation contract and existing section-order/accessibility contracts.

## Task 4: Update the decision log

**Files:**

- Modify: `Documents/Data/changes_3.md`

- [x] **Step 1: Add a dated entry near the top under the existing 2026-08-06 entries.** Record that the Overview now uses a result → mechanism → limits reading order and that the bootstrap explanation now defines paired re-sampling, the meaning of the 95% CI, zero-crossing verdicts, and event-vs-person semantics. State explicitly that artifacts and calculations are unchanged.

Example:

```markdown
## 2026-08-06: guided Overview and bootstrap explanation

The V9 Overview now leads with the operational result, then explains the
relational mechanism and limits before the dataset/model inventory. The daily
bootstrap panel now explains event-level paired re-sampling, the Hybrid-minus-baseline
event-hit gap, the 95% interval as resampling variability, and how to
read zero-crossing verdicts. It explicitly distinguishes event hits from
unique-person recovery. Artifacts, calculations, and as-of contracts are
unchanged.
```

## Task 5: Final verification

- [x] **Step 1: Run the focused source suite.**

```bash
rtk pytest -q tests/test_v9_dashboard_builder.py tests/test_v9_summary_page.py
```

Expected: all tests pass.

- [x] **Step 2: Check the patch for whitespace and scope.**

```bash
rtk git diff --check
rtk git diff --stat -- Documents/Data/scripts/v9_summary_page.py Documents/Data/scripts/v9_dashboard_ui.py tests/test_v9_summary_page.py tests/test_v9_dashboard_builder.py Documents/Data/changes_3.md
```

Expected: no whitespace errors; only the approved source-contract, UI-copy,
and changelog files are named in the task-specific diff. Existing unrelated
worktree changes remain untouched.

- [x] **Step 3: Inspect the generated dashboard if the focused tests rebuild it.** Confirm the Overview and V9 results sections are each mounted once and that no new runtime data fields or controls were introduced.

No commit is included in this plan because the checkout is Merget-managed and
contains extensive unrelated in-progress changes; the implementation should
leave those changes unstaged for the Historian workflow.
