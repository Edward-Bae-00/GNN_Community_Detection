# GNN Community Detection - Project Guide

## What This Project Is

This repository is a research sandbox for graph-based anomaly detection on fully
synthetic CBP-style border crossing data. The active work is a controlled
comparison between a strong tabular baseline and a relational GNN on synthetic
corpora.

No modeled row is real operational or PII data. Aggregate CSVs under
`Documents/Data/RealWorld_Data/` are used only for calibration/context.

## Current Research State

### V8 Honest Track

V8 represents the realistic regime where relational signal is thin. Many hidden
carriers are lone actors or dark cell members, so graph structure alone has a
bounded ceiling. The current working summary is that learned graph arms do not
decisively beat strong label-free or tabular signals in this regime.

Detailed V8 logs previously referenced as `Documents/Data/changes_2.md` and the
older `gnn/FINDINGS.md` notes were intentionally removed from this checkout.
Treat any detailed V8 claim as needing verification from current artifacts.

### V9 Positive-Control Demo

V9 is deliberately engineered so the signal lives in observable relationships:
co-travel, shared plates, residence, and prior caught cell-mates. The goal is to
show that a caught-propagation RGCN catches more hidden carriers than a strong
per-person tabular baseline when relational signal is truly present.

Canonical V9 notes and current headline results are in
`Documents/Data/changes_3.md`. The current demo output is written to
`gnn/diagnostics/demo_comparison_v9.json`.

## Environment

- Python: 3.14
- Virtualenv: `.venv/`
- Activate: `source .venv/bin/activate`
- Common libraries in this environment: torch, torch-geometric, scikit-learn,
  networkx, pandas, numpy

The root `pyproject.toml` declares runtime and development dependencies; use the
existing `.venv` for this checkout.

## Project Structure

```text
.
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── gnn/
│   ├── __init__.py
│   ├── config.py              # Corpus/result paths and defaults
│   ├── demo_baseline.py       # Leak-safe 14-feature tabular baseline
│   ├── detector.py            # sklearn model helper
│   ├── graphmodel_rgcn.py     # Typed graph builder and RGCN pieces
│   ├── learned_cell.py        # As-of caught-propagation scoring
│   ├── run_demo.py            # Main V9 baseline-vs-GNN harness
│   └── diagnostics/           # Generated comparison/smoke outputs
├── Documents/
│   ├── Data/
│   │   ├── DATA_GUIDE.md      # Legacy broad guide; V7-era sections remain
│   │   ├── changes_3.md       # V9 design and result log
│   │   └── RealWorld_Data/    # Aggregate calibration/reference CSVs
│   └── GNN/                   # Reference papers/materials
├── reproducibility/v9_observability_colab_schema3/corpus/
│   └── synthetic_cbp_graph_corpus_v9/  # Canonical full V9 corpus
├── scripts/
│   ├── data/validate_corpus.py
│   └── dashboard/             # Generic and V9 dashboard utilities
├── tests/fixtures/v9dev/      # Tracked small V9 fixture
└── artifacts/v9/dashboard/    # Generated dashboard output
└── tests/
    ├── test_demo_baseline.py
    ├── test_df_detector.py
    ├── test_df_graphmodel_rgcn.py
    ├── test_run_demo_smoke.py
    └── test_v9_corpus_snapshot.py
```

## Running The Demo

```bash
source .venv/bin/activate
python -m gnn.run_demo
```

`gnn/config.py` defaults to the canonical V9 corpus from `gnn.paths`. Set
`CBP_CORPUS_DIR` only when intentionally evaluating another compatible corpus.

Outputs go to `gnn/diagnostics/`.

## Running Tests

```bash
source .venv/bin/activate
PYTHONPATH=. pytest -q tests
```

`tests/test_v9_corpus_snapshot.py` validates the tracked `tests/fixtures/v9dev/`
snapshot directly.

## Data And Dashboard Utilities

```bash
# Validate a corpus
python -m scripts.data.validate_corpus tests/fixtures/v9dev

# Build V9 dashboard data and shell
python -m scripts.dashboard.build_dashboard reproducibility/v9_observability_colab_schema3/corpus/synthetic_cbp_graph_corpus_v9
python -m scripts.dashboard.build_v9_dashboard
```

Serve `artifacts/v9/dashboard/` through a local HTTP server before opening
the dashboard, because it fetches `data_v9.json`.

## Working Conventions

- Preserve leak-free as-of evaluation. Current outcomes and future events must
  not leak into features.
- Keep the baseline graph-free. Party size, shared assets, neighbor labels, and
  graph shadows should not be added to the tabular baseline without explicitly
  changing the experimental question.
- Keep V8 and V9 claims separate. V9 validates the method under engineered
  relational signal; it does not supersede the V8 honest-track caveat.
- Before changing generation or evaluation logic, read `Documents/Data/changes_3.md`.
- Do not reorganize `Documents/Data/` without a specific migration plan; paths are
  assumed by config and dashboard scripts.
