"""Repository metadata and canonical path contracts."""
import os
import re
import subprocess
import sys
from pathlib import Path
import tomllib

from gnn import paths


ROOT = Path(__file__).resolve().parents[1]


def _normalized_distribution_name(requirement: str) -> str:
    name = re.split(r"[<>=!~;\[\s]", requirement, maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", name).lower()


def test_project_metadata_declares_runtime_and_test_dependencies():
    payload = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project = payload["project"]
    assert project["requires-python"] == ">=3.11"
    dependencies = {
        _normalized_distribution_name(requirement)
        for requirement in project["dependencies"]
    }
    assert dependencies >= {
        "torch", "torch-geometric", "pandas", "numpy", "scikit-learn",
        "scipy", "networkx",
    }
    dev_dependencies = {
        _normalized_distribution_name(requirement)
        for requirement in project["optional-dependencies"]["dev"]
    }
    assert "pytest" in dev_dependencies
    package_data = payload["tool"]["setuptools"]["package-data"]
    assert package_data["scripts.dashboard"] == ["assets/fonts/*.woff2"]


def test_canonical_v9_paths_are_repo_relative():
    assert paths.REPO_ROOT == ROOT
    assert paths.SCHEMA3_HANDOFF_ROOT == (
        ROOT / "reproducibility" / "v9_observability_colab_schema3"
    )
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
    assert paths.V9_RESEARCH_LOG == ROOT / "docs/research/changes_3.md"
    assert "synthetic_cbp_graph_corpus_v8" not in str(paths.V9_CORPUS_DIR)


def test_corpus_override_isolated_subprocess(tmp_path):
    expected = tmp_path / "override-corpus"
    parent_value = os.environ.get("CBP_CORPUS_DIR")
    environment = os.environ.copy()
    environment["CBP_CORPUS_DIR"] = str(expected)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from gnn.config import CORPUS_DIR; print(CORPUS_DIR)",
        ],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == str(expected)
    assert os.environ.get("CBP_CORPUS_DIR") == parent_value
