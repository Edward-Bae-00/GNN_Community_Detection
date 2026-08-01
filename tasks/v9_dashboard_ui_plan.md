# V9 Dashboard UI Improvements Implementation Plan

**Goal:** Make the V9 dashboard work equally well as a GNN demo readout and as a corpus exploration tool while preserving the existing data and model behavior.

**Architecture:** Keep the static HTML/D3 architecture and make the template plus injected V9 UI the source of truth. Add a lightweight two-level navigation shell, URL/hash state for tabs, a V9 headline summary derived from the existing diagnostic JSON, and semantic/accessibility improvements without introducing a framework or new runtime dependency.

**Tech Stack:** Python dashboard builder, generated static HTML, vanilla CSS/JavaScript, D3, pytest.

---

### Task 1: Add regression coverage for the new UI contract

**Files:**
- Modify: `tests/test_v9_dashboard_builder.py`
- Test: generated dashboard source strings and builder helpers

- [ ] Add tests that assert the V9 UI source includes the readout/explorer navigation groups, tab accessibility attributes, hash-state helpers, and the headline summary container.
- [ ] Add a test that the generated HTML removes all legacy `entityResolution` nav/section entries and retains only the intended 11 visible tabs.
- [ ] Run the focused test file and confirm the new assertions fail before implementation.

### Task 2: Implement navigation and V9 readout hierarchy

**Files:**
- Modify: `Documents/Data/synthetic_cbp_graph_corpus_v9/dashboard_standalone.html`
- Modify: `Documents/Data/scripts/v9_dashboard_ui.py`
- Modify: `Documents/Data/scripts/build_v9_dashboard.py`

- [ ] Replace the flat tab strip with grouped navigation while keeping every current exploration destination available.
- [ ] Add ARIA tab semantics, focus-visible styling, a skip link, and a compact mobile section selector.
- [ ] Add hash-based tab persistence and browser back/forward handling.
- [ ] Add a V9 readout hero with a concise deployable-hybrid verdict computed from the existing `v9Demo` data and a link into the exploratory tabs.
- [ ] Normalize injected V9 and unsupervised UI typography to the dashboard font tokens.

### Task 3: Improve explorer interaction and responsive behavior

**Files:**
- Modify: `Documents/Data/synthetic_cbp_graph_corpus_v9/dashboard_standalone.html`

- [ ] Convert clickable filter chips and legends to semantic buttons with keyboard support and active-filter summaries.
- [ ] Add responsive table wrappers and resize-safe chart sizing rules.
- [ ] Preserve existing cross-tab drill hooks and make the navigation state update when they are used.

### Task 4: Remove generated/template duplication

**Files:**
- Modify: `Documents/Data/scripts/build_v9_dashboard.py`
- Modify: `Documents/Data/synthetic_cbp_graph_corpus_v9/dashboard_standalone.html`

- [ ] Remove duplicate Community Explorer style blocks and duplicate legacy Entity Resolution renderer blocks from the source template or builder normalization path.
- [ ] Keep the builder idempotent so rerunning it does not duplicate injected tabs, sections, or CSS.

### Task 5: Regenerate and verify

**Files:**
- Regenerate: `Documents/Data/v9_dashboard/index.html`
- Regenerate: `Documents/Data/v9_dashboard/data_v9.json` only if the builder changes require it

- [ ] Run `pytest -q tests/test_v9_dashboard_builder.py`.
- [ ] Run the affected dashboard and smoke tests.
- [ ] Parse the generated JavaScript with Node syntax checking.
- [ ] Rebuild the dashboard and verify tab counts, ARIA hooks, hash navigation, and the V9 summary are present exactly once.
- [ ] Review the final diff and confirm unrelated worktree changes remain untouched.
