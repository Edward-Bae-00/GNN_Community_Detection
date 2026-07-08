# Agent Instructions - GNN Community Detection

## Project Context

This is a GNN-based anomaly detection research project on fully synthetic
CBP-style border crossing data. No row represents a real person, vehicle,
document, officer, case, event, seizure, arrest, address, phone number, email,
license plate, or name. Aggregate real-world CSVs under
`Documents/Data/RealWorld_Data/` are calibration/context inputs only.

The active research track is `gnn/`: a leak-free baseline-vs-GNN
demonstration over V8/V9 synthetic corpora.

## Current Goals

- Preserve the distinction between the V8 honest track and the V9 positive
  control. V8 is the realistic thin-graph-signal regime; V9 is deliberately
  engineered to contain relational signal.
- Use V9 to demonstrate the intended positive control: when hidden-carrier risk
  is propagable through co-travel/shared-plate/residence structure, the as-of
  caught-propagation RGCN should recover more hidden carriers at operational
  depth than a strong tabular baseline.
- Keep the comparison leak-free. Future outcomes, lifetime catches, hidden org
  labels, and outcome aggregates must not become model features.
- Keep the baseline strong and fair: own-history, observed demographics, and
  event context are allowed; graph/neighbor-label features are not.
- Keep docs synchronized with the filesystem. The historical
  `Documents/Data/changes_2.md` and `gnn/FINDINGS.md` notes were intentionally
  removed; verify detailed V8 claims from current artifacts before relying on
  them.

## Environment

- Python 3.14, venv at `.venv/`
- Activate with `source .venv/bin/activate`
- Key packages in the working environment: PyTorch, PyTorch Geometric,
  scikit-learn, networkx, pandas, numpy
- Local shell convention from `@/Users/edward/.codex/RTK.md`: prefix shell
  commands with `rtk`

## Current File Navigation

### Active Package

- `gnn/config.py` - repository paths, corpus override, result path
- `gnn/run_demo.py` - main V9 baseline-vs-GNN evaluation harness
- `gnn/demo_baseline.py` - leak-safe 14-feature tabular baseline
- `gnn/graphmodel_rgcn.py` - typed graph construction and RGCN
- `gnn/learned_cell.py` - as-of caught-propagation scoring
- `gnn/detector.py` - sklearn model fitting helper
- `gnn/diagnostics/` - run outputs such as `demo_comparison_v9.json`

### Data And Scripts

- `Documents/Data/synthetic_cbp_graph_corpus_v8/` - V8 honest-track corpus
- `Documents/Data/synthetic_cbp_graph_corpus_v9/` - full V9 positive-control
  corpus
- `Documents/Data/synthetic_cbp_graph_corpus_v9dev/` - small V9 dev/test corpus
- `Documents/Data/scripts/validate_corpus.py` - corpus validation harness
- `Documents/Data/scripts/build_dashboard.py` and `build_v9_dashboard.py` -
  dashboard builders
- `Documents/Data/v9_dashboard/` - generated V9 dashboard output
- `Documents/Data/changes_3.md` - canonical V9 design/results log in this
  checkout
- `Documents/Data/DATA_GUIDE.md` - older broad data guide; currently contains
  V7-era material and should not override V8/V9-specific docs

### Tests

The current source test suite is small and focused on the V9 demo stack:

- `tests/test_df_detector.py`
- `tests/test_df_graphmodel_rgcn.py`
- `tests/test_demo_baseline.py`
- `tests/test_run_demo_smoke.py`
- `tests/test_v9_corpus_snapshot.py`

## Before Changing Model Or Evaluation Logic

1. Read `Documents/Data/changes_3.md`.
2. Read the relevant source files in `gnn/`.
3. The historical `Documents/Data/changes_2.md` and `gnn/FINDINGS.md` notes were
   intentionally removed; verify V8/honest-track claims from current artifacts
   before changing that logic.
4. Verify strict as-of semantics: graph edges and caught labels must be available
   before the row time `T`.
5. Re-run targeted tests, at minimum the affected `tests/test_*.py` files.

## Organization Constraints

- Do not move corpus directories casually. Several scripts and configs assume
  the current `Documents/Data/...` layout.
- Do not delete or restore legacy research artifacts based only on stale docs or
  `__pycache__` names.
- Keep generated diagnostics under `gnn/diagnostics/`.
- Prefer small, targeted documentation updates over large rewrites unless the
  user explicitly asks for a data-guide or architecture cleanup pass.
