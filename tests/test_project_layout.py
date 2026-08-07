"""Repository metadata and canonical path contracts."""
from pathlib import Path
import tomllib

from gnn import paths


ROOT = Path(__file__).resolve().parents[1]


def test_project_metadata_declares_runtime_and_test_dependencies():
    payload = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project = payload["project"]
    assert project["requires-python"] == ">=3.11"
    dependencies = "\n".join(project["dependencies"]).lower()
    for name in (
        "torch", "torch-geometric", "pandas", "numpy", "scikit-learn",
        "scipy", "networkx",
    ):
        assert name in dependencies
    assert "pytest" in "\n".join(project["optional-dependencies"]["dev"]).lower()
    package_data = payload["tool"]["setuptools"]["package-data"]
    assert package_data["scripts.dashboard"] == ["assets/fonts/*.woff2"]


def test_canonical_v9_paths_are_repo_relative():
    assert paths.REPO_ROOT == ROOT
    assert paths.V9_CORPUS_DIR == (
        ROOT
        / "reproducibility/v9_observability_colab_schema3/corpus/"
          "synthetic_cbp_graph_corpus_v9"
    )
    assert paths.V9DEV_CORPUS_DIR == ROOT / "tests/fixtures/v9dev"
    assert paths.V9_EXPLANATION_ARCHIVE == (
        ROOT / "artifacts/v9/explanations/v9_schema3_results.zip"
    )
    assert paths.V9_DASHBOARD_DIR == ROOT / "artifacts/v9/dashboard"
    assert "synthetic_cbp_graph_corpus_v8" not in str(paths.V9_CORPUS_DIR)
