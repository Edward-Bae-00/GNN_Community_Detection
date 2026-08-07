# Published LLM Narrative and Counterfactual Factor Cleanup Implementation Plan

> **For agentic workers:** Use test-driven development and preserve unrelated
> uncommitted work. Leave changes uncommitted unless explicitly requested.

**Goal:** Make published v4 LLM narratives visible and omit counterfactual factors whose removal does not change the published Hybrid rank.

**Architecture:** Keep the published schema-3 artifact and producer contract unchanged. Update only the client-side narrative source-reference allowlist, then filter the existing validated factor records at render time using their published original and ablated ranks. Add focused JavaScript-contract tests through the existing Python/Node test harness.

**Tech Stack:** Python, embedded JavaScript, pytest, Node.js.

---

### Task 1: Add regression tests for producer-generated v4 narrative references

**Files:**
- Modify: `tests/test_v9_recovery_explainer_ui.py`

- [x] Extend the valid LLM narrative fixture/test with producer-style claim references under `attributions`, `component_pooling`, and `rank_fusion`.
- [x] Run the focused validator test and confirm it fails with `visible == False` because the UI allowlist rejects those references.

### Task 2: Synchronize the UI narrative allowlist

**Files:**
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py:266-273`

- [x] Add narrowly scoped patterns for the exact v4 producer paths: ranked attribution values/IDs, top pooled-member values/IDs, and rank-fusion numeric fields.
- [x] Preserve rejection of unknown paths and invalid provenance metadata.
- [x] Run the new validator test and confirm the published-style narrative is visible.

### Task 3: Add regression coverage for zero-rank-change factors

**Files:**
- Modify: `tests/test_v9_recovery_explainer_ui.py`

- [x] Add a focused factor-view test containing one zero-effect connection and one non-zero-effect factor, asserting only the non-zero factor is selected for display.
- [x] Add coverage that an empty factor set does not emit the restart-consistency warning.
- [x] Run these tests before implementation and confirm the expected failures.

### Task 4: Filter and clarify the counterfactual factor panel

**Files:**
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py:2870-2890`

- [x] Filter visible factors to `ablated_hybrid_rank !== original_hybrid_rank`; retain both positive and countervailing non-zero effects.
- [x] Emit the restart-consistency message only when at least one displayed factor exists and none is stable.
- [x] Clarify that zero-rank-movement factors are omitted, and keep the no-measured-factors state for an empty filtered list.
- [x] Run the focused tests, affected dashboard tests, JavaScript syntax checks, and `git diff --check`.

### Verification

- [x] Run `.venv/bin/python -m pytest -q tests/test_v9_recovery_explainer_ui.py` (210 passed).
- [x] Run the affected dashboard/source tests that import this UI module (154 passed).
- [x] Inspect the published bundle’s 19 narratives with the UI validator and confirm they are visible.
- [x] Review the final diff and confirm no generated recovery objects or unrelated dirty files were changed.
