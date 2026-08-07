"""Runtime configuration for corpus selection and generated diagnostics."""
import os
from pathlib import Path

from gnn.paths import REPO_ROOT, V9_CORPUS_DIR


DEFAULT_CORPUS_DIR = V9_CORPUS_DIR
CORPUS_DIR = Path(os.environ.get("CBP_CORPUS_DIR", DEFAULT_CORPUS_DIR))
RESULTS = REPO_ROOT / "gnn" / "diagnostics"
KS = (50, 100, 500)
GNN_SEEDS = (20260701, 20260702, 20260703, 20260704, 20260705)
SEED = 42
