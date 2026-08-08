# Project Guide - GNN Community Detection

This repository studies graph-based anomaly detection over fully synthetic
CBP-style border-crossing data. No modeled row represents a real person,
vehicle, document, officer, case, event, seizure, arrest, address, phone
number, email, license plate, or name. Aggregate real-world CSVs are
calibration/context inputs only.

## Active research state

V9 is the active designed positive control. Observable co-travel, shared-plate,
residence, and prior caught-cell-mate structure make relational signal
propagable. The comparison is leak-free and uses strict as-of semantics: only
graph edges and caught labels available before row time `T` may be used.

The baseline is intentionally strong and graph-free. It may use own history,
observed demographics, and non-relational event context, but not graph edges,
neighbor labels, party size, shared vehicle/document co-use, or other relational
graph shadows. Future outcomes, lifetime catches, hidden organization labels,
and outcome aggregates are not features.

V8 is historical honest-track context only. Its corpus is absent from this
checkout and is not the current default/data path. Preserve the interpretation
that V8 has thin relational signal and does not inherit V9's positive-control
conclusion.

## Repository paths

- `gnn/` - root flat active implementation and diagnostics.
- `docs/research/changes_3.md` - canonical V9 research log.
- `docs/data/DATA_GUIDE.md` - active data guide.
- `scripts/data/validate_corpus.py` - corpus validator.
- `scripts/dashboard/build_v9_dashboard.py` - V9 dashboard builder.
- `tests/fixtures/v9dev/` - small V9 fixture.
- `reproducibility/v9_observability_colab_schema3/` - canonical full V9,
  checkpoint, notebook, and runner handoff.
- `artifacts/v9/explanations/v9_schema3_results.zip` - committed schema-3
  archive.
- `artifacts/v9/dashboard/` - generated dashboard target.
- `references/papers/` - seven Git LFS-backed papers.

`pyproject.toml` is authoritative install metadata. The canonical full V9
corpus is selected by default through `gnn/config.py`; `CBP_CORPUS_DIR` is the
explicit override for another compatible corpus.

## Before model/evaluation changes

Read `docs/research/changes_3.md` and the relevant `gnn/` sources before
changing model or evaluation logic. Verify as-of edge/label availability,
leakage safety, and the strong-baseline contract, then run affected tests.

## Working constraints

- Keep the synthetic-data scope and the V8/V9 distinction explicit.
- Do not move corpus directories casually.
- Do not change code/model behavior, data, artifacts, or tests during a
  documentation-only task except for an explicitly requested path-only test
  update.
- Keep generated diagnostics under `gnn/diagnostics/` and generated dashboard
  output under `artifacts/v9/dashboard/`.
- Root `README.md` is authoritative for onboarding. Historical plans and specs
  are preserved as records; see `docs/superpowers/README.md` for their status.
- Prefix shell commands with `rtk` in this environment.
