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

Documents/Data/
  synthetic_cbp_graph_corpus_v8/     Local V8 honest-track corpus, not in Git
  synthetic_cbp_graph_corpus_v9/     Local full V9 positive-control corpus, not in Git
  synthetic_cbp_graph_corpus_v9dev/  Local small V9 dev/test corpus, not in Git
  scripts/validate_corpus.py         Corpus validator
  scripts/build_dashboard.py         Corpus dashboard builder
  scripts/build_v9_dashboard.py      V9 dashboard packager
  v9_dashboard/                      Generated V9 dashboard output
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
scikit-learn, networkx, pandas, and numpy installed. There is no root
`requirements.txt` or `pyproject.toml` in this checkout yet.

## Data Availability

Large data corpora, aggregate calibration CSVs, reference PDFs, generated
dashboards, and run diagnostics are intentionally excluded from Git. Keep local
copies under the paths shown above, or set `CBP_CORPUS_DIR` to point at another
compatible corpus checkout.

## Run The V9 Demo

```bash
source .venv/bin/activate
PYTHONPATH=. CBP_CORPUS_DIR=$PWD/Documents/Data/synthetic_cbp_graph_corpus_v9 \
  python -m gnn.run_demo
```

Results are written under `gnn/diagnostics/`.

By default, `gnn/config.py` points at the V8 corpus. Set
`CBP_CORPUS_DIR` explicitly when running the V9 positive-control demo.

## Run Tests

```bash
source .venv/bin/activate
PYTHONPATH=. pytest -q tests
```

The V9 corpus snapshot test validates the local
`Documents/Data/synthetic_cbp_graph_corpus_v9dev/` files directly, so it requires
that corpus to be present outside Git.

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

`docs/research/changes_3.md` is the canonical V9 result log in this checkout.
It records the positive-control conclusion: on V9, the caught-propagation RGCN
recovers substantially more hidden carriers than the strong tabular baseline at
operational depth because co-travel is now present in the graph the model sees.

The V8 honest-track note historically referenced as `Documents/Data/changes_2.md`
and the older `gnn/FINDINGS.md` notes were intentionally removed from this
checkout. Treat detailed V8 claims as needing verification from current
artifacts before relying on them.

## Organization Notes

- `Documents/Data/DATA_GUIDE.md` still contains V7-era broad documentation. Use
  the V8/V9 corpus READMEs and `changes_3.md` for current-track specifics.
- `scripts/data/` and `scripts/dashboard/` contain validation, dashboard, and ER helper
  utilities. Corpus generation has been retired from this checkout; local
  V8/V9/V9dev snapshots are the source artifacts.
- `__pycache__/`, `.pytest_cache/`, and `.DS_Store` files are local/generated
  noise and should not be treated as source-of-truth structure.
