# V9 schema-3 dashboard cleanup design

## Status

Approved for implementation on 2026-08-05 with an explicit
artifact-preservation constraint.

## Goal

Make the active V9 dashboard schema-3-only, remove unused schema-1/schema-2
presentation and packaging compatibility, simplify the V9 Results charts, and
show only successfully published GNN explanations.

## Current-state findings

- The dashboard builder currently prefers
  `gnn/diagnostics/hybrid_recovery_explanations_v9.json`, which is schema 1.0,
  over the available `v9_schema3_results.zip`. Legacy recovery rendering is
  therefore still the default local build path.
- The recovery UI ships schema-1, schema-2, and schema-3 renderers together.
  The schema-1/schema-2 branches have no callers once the builder is made
  schema-3-only.
- The current schema-3 manifest labels 20 Hybrid cases as
  `gnn_explanation`, but only 19 have published entries in `detail_index`.
  The twentieth case failed generation and currently reaches the case list.
- Daily Crossing Volume currently follows Daily capacity and Simulated
  catches, and its independent budget selector defaults to 25/day.
- Daily capacity currently renders Baseline, Deployable Hybrid, and GNN.

## Immutable artifact contract

Implementation must not edit or regenerate source evaluation artifacts. This
includes, at minimum:

- `gnn/diagnostics/demo_comparison_v9.json`;
- `gnn/diagnostics/hybrid_recovery_explanations_v9.json`;
- `gnn/diagnostics/unsupervised_ad_results_v9.json` when present;
- `gnn/diagnostics/gnn_architecture_comparison_v9.json` when present;
- `v9_schema3_results.zip`;
- corpus `dashboard_data.json` inputs; and
- every simulated-catch payload, including `simulated_catch_daily` and
  `simulated_catch_daily_ks`.

Record hashes for existing source artifacts before implementation and compare
them after verification. The generated, gitignored
`Documents/Data/v9_dashboard/data_v9.json` is not a source artifact: rebuilding
it may replace its recovery section with the schema-3 manifest selected from
the unchanged ZIP, but must not alter any upstream JSON or ZIP.

No model, scoring, simulation, bootstrap, corpus, or artifact-production logic
is in scope.

## Approved design

### Schema-3-only active path

The builder will prefer the configured schema-3 artifact, then the existing
repo-root schema-3 ZIP. A plain JSON input remains acceptable only when its
declared schema is `3.0`. Schema 1.0 and 2.0 inputs will fail closed instead of
silently activating compatibility UI.

Remove schema-1/schema-2 recovery loading, rendering, CSS, sidecar publishing,
and their compatibility tests. Preserve helpers used by schema 3, including
graph projection, narrative, attribution, fetch, chunk validation, and error
presentation.

The anomaly-ranking UI will also stop rendering schema-2 fallback content and
the visible legacy-oracle appendix. Existing anomaly JSON is neither rewritten
nor stripped; the schema-3 UI simply ignores quarantined legacy fields.

Historical design notes and source artifact files remain untouched. Active
`build_dashboard.py` and Community Explorer code remain in place.

### V9 Results order and model scope

Keep the V9 headline and short “How to read this tab” introduction first.
Within the operational results, render:

1. Daily Crossing Volume;
2. Daily capacity view; and
3. Simulated catches.

Daily Crossing Volume will default its independent selector to 10/day while
retaining all published budget options and all three model lines. The headline
continues to use its existing 25/day choice; only the graph selector default
changes.

Daily capacity will render Baseline and Deployable Hybrid only. GNN remains in
the headline, Daily Crossing Volume, architecture material, and other views
where it is still meaningful.

The Simulated catches view, cumulative/daily mode, default cumulative mode,
budget data, calculations, accessibility labels, and JSON contract remain
unchanged. Moving its containing section does not modify its renderer.

### Explainability eligibility

The main schema-3 GNN explainability list will include a case only when:

- its detail kind is `gnn_explanation`; and
- its case ID has a published reference in `detail_index`.

This makes the current list contain the 19 published explanations and omits
the failed twentieth case. The default case is selected from that same list.
Full-cohort recovery and coverage summaries remain visible as context; only
the selectable explanation cases and detail views are explanation-only.

If no published explanations exist, preserve the current explicit empty state.
Sidecar integrity, fetch, and validation failures for genuinely published
cases remain visible rather than being hidden.

## Verification

- Add failing source-contract and Node-backed view-model tests before code
  changes.
- Run focused dashboard builder, recovery UI, and sidecar tests in `.venv`.
- Compile the changed Python modules and validate generated JavaScript syntax.
- Rebuild the gitignored dashboard from unchanged inputs.
- Verify source artifact hashes are identical before and after.
- Inspect V9 Results at desktop and narrow widths: crossing volume first and at
  10/day, capacity with two arms, simulated catches unchanged, and only
  published explanation cases selectable.
- Run `git diff --check` and review the final diff for accidental artifact or
  unrelated changes.

## Out of scope

- Deleting historical documentation or research provenance.
- Removing producer-side legacy benchmark data from anomaly artifacts.
- Changing any metric, budget series, model output, or artifact schema.
- Renaming active paths, moving corpus directories, or changing generated-data
  semantics beyond selecting schema 3 for the recovery dashboard.
