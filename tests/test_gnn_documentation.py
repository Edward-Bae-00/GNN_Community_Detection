"""Contract tests for the active and reproducibility GNN package documentation."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOTS = (
    pytest.param(REPOSITORY_ROOT / "gnn", id="active"),
    pytest.param(
        REPOSITORY_ROOT / "reproducibility" / "v9_observability_colab_schema3" / "gnn",
        id="schema3",
    ),
)
REQUIRED_ACTIVE_MODULE_SENTENCES = {
    "__init__.py": "Active leak-safe GNN anomaly-detection research package.",
    "config.py": "Runtime configuration for corpus selection and generated diagnostics.",
    "detector.py": "Scikit-learn fitting helpers shared by tabular detector experiments.",
    "graphmodel_alt.py": "Alternative GraphSAGE, GAT, GIN, and KPI-AA encoder definitions.",
    "graphmodel_rgcn.py": "Typed as-of person-graph construction and relational GNN scoring.",
    "unsupervised_ad.py": "Leak-safe unsupervised and caught-supervised anomaly evaluation.",
}


def _python_files(package_root: Path) -> list[Path]:
    return sorted(package_root.glob("*.py"))


def _public_definitions(tree: ast.Module):
    return (
        node
        for node in tree.body
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef))
        and not node.name.startswith("_")
    )


@pytest.mark.parametrize("package_root", PACKAGE_ROOTS)
def test_gnn_modules_and_public_top_level_apis_are_documented(package_root: Path):
    for path in _python_files(package_root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assert ast.get_docstring(tree), f"{path}: missing module docstring"
        for node in _public_definitions(tree):
            assert ast.get_docstring(node), (
                f"{path}:{node.lineno}: missing docstring for public {node.name}"
            )


def test_active_required_module_docstring_first_sentences_are_stable():
    for filename, sentence in REQUIRED_ACTIVE_MODULE_SENTENCES.items():
        path = REPOSITORY_ROOT / "gnn" / filename
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        docstring = ast.get_docstring(tree, clean=False)
        assert docstring is not None
        assert docstring.strip().splitlines()[0] == sentence, path
