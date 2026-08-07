# Agent Instructions - GNN Community Detection

## Project context

This is a research project on fully synthetic CBP-style border-crossing data.
No row represents a real person, vehicle, document, officer, case, event,
seizure, arrest, address, phone number, email, license plate, or name.
Aggregate real-world CSVs are calibration/context inputs only.

The active runtime is the V9-first, leak-free baseline-vs-GNN demonstration in
the flat root `gnn/` package. V9 is the designed positive control. V8 is
historical honest-track context only; its corpus is absent and must not be
treated as the current default or data path.

## Current research constraints

- Preserve strict as-of semantics: graph edges and caught labels must be
  available before row time `T`.
- Keep future outcomes, lifetime catches, hidden organization labels, and
  outcome aggregates out of features.
- Keep the strong graph-free baseline fair: own history, observed demographics,
  and event context are allowed; graph and neighbor-label features are not.
- Keep V9 positive-control conclusions separate from the historical V8
  thin-graph-signal interpretation.
- Treat every record as synthetic; real-world aggregates are calibration/context
  inputs only.

## Active paths

- `gnn/` - active flat implementation and generated diagnostics.
- `docs/research/changes_3.md` - canonical V9 design/results log.
- `docs/data/DATA_GUIDE.md` - active data guide and historical interpretation.
- `scripts/data/validate_corpus.py` - corpus validation harness.
- `scripts/dashboard/build_v9_dashboard.py` - V9 dashboard builder.
- `tests/fixtures/v9dev/` - tracked small V9 development/test corpus.
- `reproducibility/v9_observability_colab_schema3/` - full V9 Colab/checkpoint
  handoff and canonical corpus.
- `artifacts/v9/explanations/v9_schema3_results.zip` - committed schema-3
  explanation archive.
- `artifacts/v9/dashboard/` - generated dashboard output.
- `references/papers/` - seven Git LFS-backed research papers.

`pyproject.toml` is authoritative for install metadata and dependencies.
`gnn/config.py` defaults to the canonical full V9 corpus and accepts the
`CBP_CORPUS_DIR` override for intentional compatible-corpus evaluation.

## Before changing model or evaluation logic

1. Read `docs/research/changes_3.md`.
2. Read the relevant source files in `gnn/` and verify the current path
   contracts.
3. Confirm strict as-of availability of graph edges and caught labels before
   row time `T`.
4. Re-run the affected `tests/test_*.py` files.

The historical V8 interpretation must be verified from current artifacts before
being extended. Do not restore removed historical notes based on stale paths.

## Organization constraints

- Do not move corpus directories casually; the canonical full V9 corpus lives
  inside the schema-3 reproducibility handoff and V9dev lives under the test
  fixtures path.
- Do not change code/model behavior, data, artifacts, or tests during
  documentation-only reorganizations except for explicitly requested path
  assertions.
- Keep generated diagnostics under `gnn/diagnostics/` and generated dashboard
  output under `artifacts/v9/dashboard/`.
- Keep active docs synchronized with the filesystem. Root `README.md` is
  authoritative for onboarding; `tasks/README.md` and
  `docs/superpowers/README.md` explain the status of historical task records.
- Prefix shell commands with `rtk` in this environment.
