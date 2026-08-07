# GNN Community Detection

Research project for graph-based anomaly detection on fully synthetic
CBP-style border crossing data. The current active track is `gnn/`,
which compares a strong leak-safe tabular baseline with an as-of
caught-propagation RGCN.

The data is synthetic. No row represents a real person, vehicle, document,
officer, case, event, seizure, arrest, address, phone number, email, license
plate, or name. Aggregate real-world CSVs under `Documents/Data/RealWorld_Data/`
are calibration/context inputs only.

## Current Goals

- Maintain an honest V8 track where relational signal is naturally thin and the
  graph advantage is expected to be bounded.
- Maintain a V9 positive-control demo where co-travel, shared plates, residence,
  and prior caught cell-mates create a real relational signal.
- Demonstrate that the RGCN catches more hidden carriers than a strong per-person
  tabular baseline when the graph signal is actually present.
- Preserve strict as-of semantics: no future outcomes, lifetime labels, hidden
  org labels, or outcome aggregates in model features.

## Repository Layout

```text
gnn/
  config.py              Corpus/result paths; `CBP_CORPUS_DIR` override
  run_demo.py            Main V9 baseline-vs-GNN evaluation harness
  demo_baseline.py       Strong 14-feature tabular baseline, no graph features
  graphmodel_rgcn.py     Typed graph builder and RGCN components
  learned_cell.py        As-of caught-propagation scoring
  detector.py            sklearn fitting helper
  diagnostics/           Generated evaluation outputs

scripts/
  data/validate_corpus.py            Corpus validator
  dashboard/build_dashboard.py      Corpus dashboard builder
  dashboard/build_v9_dashboard.py   V9 dashboard packager

reproducibility/v9_observability_colab_schema3/corpus/
  synthetic_cbp_graph_corpus_v9/     Canonical full V9 positive-control corpus

tests/fixtures/v9dev/                Tracked small V9 dev/test corpus
artifacts/v9/dashboard/              Generated V9 dashboard output
Documents/Data/
  changes_3.md                       Canonical V9 design/results log
  DATA_GUIDE.md                      Older broad data guide with V7-era sections

tests/
  test_demo_baseline.py
  test_df_detector.py
  test_df_graphmodel_rgcn.py
  test_run_demo_smoke.py
  test_v9_corpus_snapshot.py
```

## Environment

This checkout assumes the existing virtual environment:

```bash
source .venv/bin/activate
```

The working environment is Python 3.14 with PyTorch, PyTorch Geometric,
scikit-learn, networkx, pandas, and numpy installed. Runtime and development
dependencies are declared in the root `pyproject.toml`.

## Data Availability

The canonical full V9 corpus and tracked V9dev fixture live at the paths shown
above. Historical V8 data is not tracked here; preserve its honest-track
interpretation and verify any local V8 artifacts before using them.

## Run The V9 Demo

```bash
source .venv/bin/activate
python -m gnn.run_demo
```

Results are written under `gnn/diagnostics/`.

By default, `gnn/config.py` uses the canonical V9 corpus from `gnn.paths`.
Set `CBP_CORPUS_DIR` only when intentionally evaluating another compatible
corpus.

## Run Tests

```bash
source .venv/bin/activate
PYTHONPATH=. pytest -q tests
```

The V9 corpus snapshot test validates the tracked `tests/fixtures/v9dev/`
fixture directly.

## Data Utilities

```bash
# Validate a corpus
python -m scripts.data.validate_corpus tests/fixtures/v9dev

# Build the V9 dashboard
python -m scripts.dashboard.build_dashboard reproducibility/v9_observability_colab_schema3/corpus/synthetic_cbp_graph_corpus_v9
python -m scripts.dashboard.build_v9_dashboard
```

To view the dashboard, serve `artifacts/v9/dashboard/` through a local HTTP
server so `index.html` can fetch `data_v9.json`.

## Current Result Summary

`Documents/Data/changes_3.md` is the canonical V9 result log in this checkout.
It records the positive-control conclusion: on V9, the caught-propagation RGCN
recovers substantially more hidden carriers than the strong tabular baseline at
operational depth because co-travel is now present in the graph the model sees.

The V8 honest-track note historically referenced as `Documents/Data/changes_2.md`
and the older `gnn/FINDINGS.md` notes were intentionally removed from this
checkout. Treat detailed V8 claims as needing verification from current
artifacts before relying on them.

## Organization Notes

- `Documents/Data/DATA_GUIDE.md` still contains V7-era broad documentation. Use
  the V8/V9 corpus READMEs and `Documents/Data/changes_3.md` for current-track
  specifics.
- `scripts/data/` and `scripts/dashboard/` contain validation, dashboard, and ER helper
  utilities. Corpus generation has been retired from this checkout; local
  V8/V9/V9dev snapshots are the source artifacts.
- `__pycache__/`, `.pytest_cache/`, and `.DS_Store` files are local/generated
  noise and should not be treated as source-of-truth structure.
