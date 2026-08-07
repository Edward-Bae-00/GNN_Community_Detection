import os
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[1]
# CBP_CORPUS_DIR env var repoints the harness (e.g. at V9); unset -> V8 default.
CORPUS_DIR = Path(os.environ.get(
    "CBP_CORPUS_DIR", REPO_ROOT / "Documents" / "Data" / "synthetic_cbp_graph_corpus_v8"))
RESULTS = REPO_ROOT / "gnn" / "diagnostics"
KS = (50, 100, 500)
GNN_SEEDS = (20260701, 20260702, 20260703, 20260704, 20260705)
SEED = 42
