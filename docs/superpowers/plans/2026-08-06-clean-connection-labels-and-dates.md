# Clean connection labels and date-only evidence copy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make published GNN explanation connections readable while preserving full identifiers for traceability, remove visible strict as-of copy, and show scoring dates without times.

**Architecture:** Keep evidence-boundary validation unchanged in `v9_recovery_explainer_ui.py`, but stop rendering its verbose rule/status strings. Add small presentation helpers for date-only formatting and compact IDs. Render relationship names as the primary connection label, shortened endpoints as secondary context, and full IDs in `title`/ARIA text.

**Tech Stack:** Vanilla JavaScript embedded in Python string constants, Python DOM-contract tests executed through Node, pytest.

---

### Task 1: Add failing contracts for readable connection labels and date-only copy

**Files:**
- Modify: `tests/test_v9_recovery_explainer_ui.py`

- [ ] **Step 1: Add a renderer contract for relationship-first labels.** Assert the rendered connection text contains the relation and shortened endpoints, while the progressbar ARIA label retains the full endpoint IDs and edge ID.

- [ ] **Step 2: Add a date-only helper contract.** Assert an ISO scoring timestamp renders as `2025-01-31` and the rendered schema-3 header contains no `T00:00:00` time suffix.

- [ ] **Step 3: Add absence assertions for visible strict as-of copy.** Assert the mounted schema-3 detail does not render `Strict as-of evidence boundary` or `Strict as-of status:` while the underlying boundary validation tests continue to exercise valid and invalid payloads.

- [ ] **Step 4: Run the focused tests and confirm the new assertions fail against the current UI.**

Run: `rtk pytest -q tests/test_v9_recovery_explainer_ui.py -k 'highest_attribution or schema3_mount_renders_hybrid_technical_evidence_end_to_end or schema3_header_validates or schema3_header_rejects'`

Expected: the new label/date/absence assertions fail before implementation.

### Task 2: Implement the presentation helpers and UI copy changes

**Files:**
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py`

- [ ] **Step 1: Add `recoveryFormatDateOnly(value)`** that returns the first ten characters of a valid ISO date-time string and leaves a plain date unchanged; use it for event/scoring-day display.

- [ ] **Step 2: Add a compact identifier helper** that preserves a short readable prefix and suffix while retaining the original ID for `title` and accessible labels.

- [ ] **Step 3: Update highest-attribution connection rendering** to show the relationship name first, then compact endpoint context, and keep the full endpoint/edge identifiers in the progressbar `aria-label` and `title` attributes.

- [ ] **Step 4: Remove visible strict as-of status rendering** from the selected header and evidence-boundary technical detail, without removing `validateRecoveryEvidenceBoundary` or changing fail-closed behavior.

- [ ] **Step 5: Normalize the published explanation count/event copy** so it reads `19 published GNN explanations in this evidence bundle.` and `Event E00017786 / scoring day 2025-01-31.` when the source timestamp includes a time.

### Task 3: Verify regression coverage

**Files:**
- Test: `tests/test_v9_recovery_explainer_ui.py`
- Test: `tests/test_v9_dashboard_builder.py`

- [ ] **Step 1: Run the focused recovery explainer and dashboard-builder tests.**

Run: `rtk pytest -q tests/test_v9_recovery_explainer_ui.py tests/test_v9_dashboard_builder.py`

Expected: all tests pass.

- [ ] **Step 2: Search the rendered UI source for the removed visible strings and timestamp concatenations.**

Run: `rtk rg -n "Strict as-of evidence boundary:|Strict as-of status:|scoring day '\+record\.scoring_day|snapshot '\+boundary\.snapshot" Documents/Data/scripts/v9_recovery_explainer_ui.py`

Expected: no visible-rendering matches for the removed copy; validation field names may remain in validation logic.

- [ ] **Step 3: Review the final diff and preserve all unrelated pre-existing worktree changes.**

Run: `rtk git diff -- Documents/Data/scripts/v9_recovery_explainer_ui.py tests/test_v9_recovery_explainer_ui.py`

Expected: only the approved label, date, copy, and test-contract changes are present.
