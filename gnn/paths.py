"""Canonical repository paths shared by model and utility entry points."""
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA3_HANDOFF_ROOT = (
    REPO_ROOT / "reproducibility" / "v9_observability_colab_schema3"
)
V9_CORPUS_DIR = (
    SCHEMA3_HANDOFF_ROOT / "corpus" / "synthetic_cbp_graph_corpus_v9"
)
V9DEV_CORPUS_DIR = REPO_ROOT / "tests" / "fixtures" / "v9dev"
V9_EXPLANATION_ARCHIVE = (
    REPO_ROOT / "artifacts" / "v9" / "explanations" / "v9_schema3_results.zip"
)
V9_DASHBOARD_DIR = REPO_ROOT / "artifacts" / "v9" / "dashboard"
V9_RESEARCH_LOG = REPO_ROOT / "docs" / "research" / "changes_3.md"
