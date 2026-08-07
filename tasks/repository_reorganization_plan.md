# Repository Reorganization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a clean, documented, V9-first repository whose current GNN behavior is preserved, whose canonical V9 data and explanation evidence are uploaded through Git LFS, and whose original main worktree remains untouched.

**Architecture:** Keep the active `gnn/` package and `tests/` flat, centralize repository paths in `gnn.paths`, move peripheral utilities into importable `scripts/` packages, and retain the schema-3 handoff as an atomic reproducibility snapshot. Store one canonical full V9 corpus, one V9dev fixture, and one verified explanation ZIP; regenerate the extracted dashboard rather than versioning a second multi-gigabyte tree.

**Tech Stack:** Python 3.14, PyTorch, PyTorch Geometric, pandas, NumPy, scikit-learn, SciPy, NetworkX, pytest, Git, Git worktrees, Git LFS, Markdown, Jupyter notebook JSON.

---

## File Map

### New files

- `pyproject.toml` — root package/dependency and pytest metadata.
- `.gitattributes` — Git LFS rules for V9 payloads, checkpoints, ZIP evidence, and papers.
- `gnn/paths.py` — canonical paths shared by model and utility code.
- `scripts/__init__.py`, `scripts/data/__init__.py`, `scripts/dashboard/__init__.py` — importable utility packages.
- `scripts/data/v9_assets.py` — hydration, hash, corpus-comparison, ZIP validation, and safe extraction CLI.
- `scripts/data/compare_comment_only.py` — AST comparison against `HEAD`, ignoring docstrings.
- `tests/test_project_layout.py` — project metadata and canonical path contracts.
- `tests/test_v9_assets.py` — asset verifier and extractor tests.
- `tests/test_gnn_documentation.py` — module/public API documentation contract.
- `tests/fixtures/v9dev/` — LFS-backed V9dev corpus.
- `reproducibility/v9_observability_colab_schema3/` — complete Colab handoff and canonical full V9 corpus.
- `artifacts/v9/explanations/v9_schema3_results.zip` — LFS-backed schema-3 evidence archive.
- `artifacts/v9/explanations/MANIFEST.sha256` — archive digest.
- `references/papers/*.pdf` — seven byte-preserved research papers.
- `docs/data/DATA_GUIDE.md`, `docs/research/changes_3.md` — active documentation moved out of the data tree.
- `docs/research/ideas.html` — preserved research-ideas artifact moved out of the repository root.
- `tasks/README.md`, `docs/superpowers/README.md` — active-versus-historical path guidance.

### Moved files

- `Documents/Data/scripts/*` → `scripts/dashboard/*`, except `validate_corpus.py` → `scripts/data/validate_corpus.py`.
- `Documents/Data/DATA_GUIDE.md` → `docs/data/DATA_GUIDE.md`.
- `Documents/Data/changes_3.md` → `docs/research/changes_3.md`.
- `ideas.html` → `docs/research/ideas.html`.
- `v9_observability_colab_schema3/` → `reproducibility/v9_observability_colab_schema3/`.
- `v9_schema3_results.zip` → `artifacts/v9/explanations/v9_schema3_results.zip`.
- `Documents/GNN/*.pdf` → `references/papers/*.pdf` by verified copy; the main-worktree originals remain untouched.

### Modified active files

- `gnn/config.py`, `gnn/gnn_architecture_bakeoff.py`, `gnn/run_demo.py` — V9-first paths and commands.
- All active `gnn/*.py` and bundled `reproducibility/.../gnn/*.py` — focused module/API documentation without logic changes.
- `scripts/dashboard/build_dashboard.py`, `scripts/dashboard/build_v9_dashboard.py` — package imports and canonical paths.
- Data-dependent and dashboard tests under `tests/` — canonical fixtures and generated-output independence.
- `README.md`, `AGENTS.md`, `CLAUDE.md`, `PROJECT_MEMORY.md`, active data/research docs, and schema-3 README — synchronized layout and commands.
- `.gitignore` — generated dashboard/extraction paths and local data policy.

---

### Task 1: Commit the Seeded User-Owned Baseline

**Files:**

- Commit existing modifications in `Documents/Data/changes_3.md`, `Documents/Data/scripts/*.py`, `PROJECT_MEMORY.md`, `gnn/sage_explainer.py`, and the 10 modified `tests/test_*.py` files.
- Commit the 19 explicitly copied untracked design/plan files shown by `git status`.
- Exclude: `tasks/repository_reorganization_design.md` and this plan, which already have their own documentation commits.

- [ ] **Step 1: Verify the seeded diff is internally clean**

Run:

```bash
rtk git diff --check
rtk proxy git status --short
```

Expected: no whitespace errors; only the 16 seeded tracked changes and 19 seeded untracked source/design files are listed in addition to this already committed plan history.

- [ ] **Step 2: Run the seeded code-focused baseline**

Run:

```bash
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_recovery_bundle.py \
  tests/test_recovery_layout_parity.py \
  tests/test_sage_explainer.py \
  tests/test_v9_design_system.py \
  tests/test_v9_recovery_explainer_ui.py \
  tests/test_v9_summary_page.py \
  tests/test_v9_dashboard_builder.py \
  -k 'not generated_dashboard'
```

Expected: PASS with no failures. The six generated-dashboard tests are excluded only until canonical V9 assets are present.

- [ ] **Step 3: Stage exactly the seeded baseline**

Run:

```bash
rtk git add -u
rtk git add -- \
  DESIGN.md \
  docs/superpowers/plans/2026-08-05-dashboard-visual-refresh.md \
  docs/superpowers/plans/2026-08-05-explanation-dashboard-readability.md \
  docs/superpowers/plans/2026-08-06-clean-connection-labels-and-dates.md \
  docs/superpowers/plans/2026-08-06-guided-overview-ci.md \
  docs/superpowers/plans/2026-08-06-overview-dataset-model-snapshot.md \
  docs/superpowers/plans/2026-08-06-v9-evidence-first-graph.md \
  docs/superpowers/specs/2026-08-05-dashboard-visual-refresh-design.md \
  docs/superpowers/specs/2026-08-05-explanation-dashboard-readability-design.md \
  docs/superpowers/specs/2026-08-05-gnn-explanation-graph-workspace-design.md \
  docs/superpowers/specs/2026-08-05-v9-results-readability-design.md \
  docs/superpowers/specs/2026-08-06-guided-overview-ci-design.md \
  docs/superpowers/specs/2026-08-06-overview-dataset-model-snapshot-design.md \
  docs/superpowers/specs/2026-08-06-v9-evidence-first-graph-design.md \
  tasks/gnn_explanation_graph_workspace_plan.md \
  tasks/llm_explanation_factor_cleanup_plan.md \
  tasks/recovery_explanation_stack_plan.md \
  tasks/v9_schema3_dashboard_cleanup_design.md \
  tasks/v9_schema3_dashboard_cleanup_plan.md
rtk proxy git diff --cached --name-only
```

Expected: exactly 35 seeded paths; no corpus, ZIP, staging directory, cache, design spec, or reorganization plan is staged.

- [ ] **Step 4: Commit the baseline**

Run:

```bash
rtk git commit -m "chore: checkpoint current dashboard and explanation work"
```

Expected: one commit containing only the seeded user-owned state.

---

### Task 2: Add Project Metadata and Canonical Path Contracts

**Files:**

- Create: `pyproject.toml`
- Create: `gnn/paths.py`
- Create: `tests/test_project_layout.py`
- Modify: `gnn/config.py`
- Modify: `gnn/gnn_architecture_bakeoff.py`

- [ ] **Step 1: Write failing project-layout tests**

Create `tests/test_project_layout.py` with:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest tests/test_project_layout.py -q
```

Expected: FAIL because `pyproject.toml` and `gnn.paths` do not exist.

- [ ] **Step 3: Add exact package metadata**

Create `pyproject.toml` with:

```toml
[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[project]
name = "gnn-community-detection"
version = "0.1.0"
description = "Leak-safe GNN anomaly detection on fully synthetic border-crossing data"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "torch>=2.4",
  "torch-geometric>=2.5",
  "pandas>=2.0",
  "numpy>=1.26",
  "scikit-learn>=1.3",
  "scipy>=1.10",
  "networkx>=3.0",
]

[project.optional-dependencies]
dev = ["pytest>=8"]

[tool.setuptools.packages.find]
include = ["gnn*", "scripts*"]

[tool.setuptools.package-data]
"scripts.dashboard" = ["assets/fonts/*.woff2"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 4: Add exact canonical paths**

Create `gnn/paths.py` with:

```python
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
```

Replace `gnn/config.py` with:

```python
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
```

In `gnn/gnn_architecture_bakeoff.py`, replace the hard-coded default with:

```python
DEFAULT_CORPUS = FC.DEFAULT_CORPUS_DIR
```

- [ ] **Step 5: Run path and config tests**

Run:

```bash
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest -q \
  tests/test_project_layout.py \
  tests/test_gnn_architecture_bakeoff.py \
  tests/test_df_graphmodel_rgcn.py
```

Expected: PASS; the corpus-reading graph test may skip until Task 4 hydrates the canonical V9 corpus.

- [ ] **Step 6: Commit**

Run:

```bash
rtk git add pyproject.toml gnn/paths.py gnn/config.py \
  gnn/gnn_architecture_bakeoff.py tests/test_project_layout.py
rtk git commit -m "build: add project metadata and canonical paths"
```

---

### Task 3: Build V9 Asset Verification and Safe Extraction

**Files:**

- Create: `scripts/__init__.py`
- Create: `scripts/data/__init__.py`
- Create: `scripts/data/v9_assets.py`
- Create: `tests/test_v9_assets.py`

- [ ] **Step 1: Write failing asset tests**

Create `tests/test_v9_assets.py` with:

```python
"""Hash, hydration, comparison, and extraction tests for V9 assets."""
import hashlib
import zipfile
from pathlib import Path

import pytest

from scripts.data.v9_assets import (
    AssetError,
    assert_hydrated,
    compare_trees,
    extract_explanations,
    verify_explanation_archive,
)


def _write_zip(path: Path, members: dict[str, bytes]) -> str:
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_lfs_pointer_is_not_treated_as_hydrated_data(tmp_path):
    pointer = tmp_path / "payload.zip"
    pointer.write_text(
        "version https://git-lfs.github.com/spec/v1\n"
        "oid sha256:" + "0" * 64 + "\nsize 10\n"
    )
    with pytest.raises(AssetError, match="git lfs pull"):
        assert_hydrated(pointer)


def test_archive_verification_and_atomic_extraction(tmp_path):
    archive = tmp_path / "result.zip"
    digest = _write_zip(
        archive,
        {
            "v9_schema3_results/result.json": b"{}",
            "v9_schema3_results/recovery/current.json": b"{}",
            "v9_schema3_results/recovery/bundles/x/manifest.json": b"{}",
        },
    )
    assert verify_explanation_archive(archive, digest) == 3
    destination = tmp_path / "published"
    extract_explanations(archive, destination, digest)
    assert (destination / "result.json").read_bytes() == b"{}"
    assert (destination / "recovery/current.json").is_file()


def test_archive_rejects_traversal(tmp_path):
    archive = tmp_path / "bad.zip"
    digest = _write_zip(
        archive,
        {
            "v9_schema3_results/result.json": b"{}",
            "v9_schema3_results/../../escape.txt": b"bad",
        },
    )
    with pytest.raises(AssetError, match="unsafe ZIP member"):
        verify_explanation_archive(archive, digest)


def test_tree_comparison_reports_missing_and_changed_files(tmp_path):
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "same.csv").write_text("same")
    (right / "same.csv").write_text("same")
    (left / "changed.csv").write_text("left")
    (right / "changed.csv").write_text("right")
    (left / "left-only.csv").write_text("left")
    report = compare_trees(left, right)
    assert report == {
        "changed": ["changed.csv"],
        "left_only": ["left-only.csv"],
        "right_only": [],
    }
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest tests/test_v9_assets.py -q
```

Expected: FAIL because `scripts.data.v9_assets` does not exist.

- [ ] **Step 3: Implement the verifier and extractor**

Create empty package docstrings in `scripts/__init__.py` and `scripts/data/__init__.py`:

```python
"""Repository utility entry points."""
```

```python
"""Data validation and reproducibility utilities."""
```

Create `scripts/data/v9_assets.py` with:

```python
#!/usr/bin/env python3
"""Verify, compare, and safely extract canonical V9 repository assets."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from gnn.paths import V9_EXPLANATION_ARCHIVE


EXPLANATION_SHA256 = (
    "54064788c0cd92893296d1db926aaa902604e30db16fdc3151545413a30008fd"
)
LFS_HEADER = b"version https://git-lfs.github.com/spec/v1"
ARCHIVE_PREFIX = "v9_schema3_results"


class AssetError(RuntimeError):
    """Raised when a versioned V9 asset is absent, unsafe, or corrupted."""


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest for one file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_hydrated(path: Path) -> Path:
    """Require a real file rather than a missing or unhydrated LFS pointer."""
    path = Path(path)
    if not path.is_file():
        raise AssetError(f"asset is missing: {path}; run git lfs pull")
    with path.open("rb") as handle:
        if handle.read(len(LFS_HEADER)) == LFS_HEADER:
            raise AssetError(f"asset is an LFS pointer: {path}; run git lfs pull")
    return path


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if not members:
        raise AssetError("explanation ZIP is empty")
    for member in members:
        name = member.filename
        relative = PurePosixPath(name)
        mode = (member.external_attr >> 16) & 0o170000
        if (
            not name
            or "\\" in name
            or relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[0] != ARCHIVE_PREFIX
            or mode == stat.S_IFLNK
        ):
            raise AssetError(f"unsafe ZIP member: {name!r}")
    required = {
        f"{ARCHIVE_PREFIX}/result.json",
        f"{ARCHIVE_PREFIX}/recovery/current.json",
    }
    names = {member.filename.rstrip("/") for member in members}
    missing = sorted(required - names)
    if missing:
        raise AssetError(f"explanation ZIP is missing: {', '.join(missing)}")
    return members


def verify_explanation_archive(
    path: Path = V9_EXPLANATION_ARCHIVE,
    expected_sha256: str = EXPLANATION_SHA256,
) -> int:
    """Verify hydration, digest, safe member paths, and required evidence files."""
    path = assert_hydrated(path)
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise AssetError(
            f"explanation ZIP SHA-256 mismatch: expected {expected_sha256}, got {actual}"
        )
    with zipfile.ZipFile(path) as archive:
        return len(_safe_members(archive))


def extract_explanations(
    archive_path: Path,
    destination: Path,
    expected_sha256: str = EXPLANATION_SHA256,
) -> Path:
    """Verify and atomically publish the archive's single canonical root."""
    archive_path = Path(archive_path)
    destination = Path(destination)
    verify_explanation_archive(archive_path, expected_sha256)
    if destination.exists():
        raise AssetError(f"extraction destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".v9-extract-", dir=destination.parent))
    try:
        with zipfile.ZipFile(archive_path) as archive:
            _safe_members(archive)
            archive.extractall(stage)
        source = stage / ARCHIVE_PREFIX
        if not source.is_dir():
            raise AssetError("explanation ZIP canonical root is missing")
        os.replace(source, destination)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return destination


def _file_map(root: Path) -> dict[str, Path]:
    root = Path(root)
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and "__pycache__" not in path.parts
        and ".pytest_cache" not in path.parts
    }


def compare_trees(left: Path, right: Path) -> dict[str, list[str]]:
    """Compare two trees by relative file set and SHA-256 content."""
    left_files, right_files = _file_map(left), _file_map(right)
    common = sorted(left_files.keys() & right_files.keys())
    return {
        "changed": [
            name
            for name in common
            if sha256_file(left_files[name]) != sha256_file(right_files[name])
        ],
        "left_only": sorted(left_files.keys() - right_files.keys()),
        "right_only": sorted(right_files.keys() - left_files.keys()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser("verify-explanations")
    verify.add_argument("--archive", type=Path, default=V9_EXPLANATION_ARCHIVE)
    extract = subparsers.add_parser("extract-explanations")
    extract.add_argument("destination", type=Path)
    extract.add_argument("--archive", type=Path, default=V9_EXPLANATION_ARCHIVE)
    compare = subparsers.add_parser("compare-corpora")
    compare.add_argument("left", type=Path)
    compare.add_argument("right", type=Path)
    args = parser.parse_args(argv)
    if args.command == "verify-explanations":
        print(json.dumps({"members": verify_explanation_archive(args.archive)}))
        return 0
    if args.command == "extract-explanations":
        print(extract_explanations(args.archive, args.destination))
        return 0
    report = compare_trees(args.left, args.right)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not any(report.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run asset tests**

Run:

```bash
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest tests/test_v9_assets.py -q
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

Run:

```bash
rtk git add scripts/__init__.py scripts/data/__init__.py \
  scripts/data/v9_assets.py tests/test_v9_assets.py
rtk git commit -m "feat: add verified V9 asset tooling"
```

---

### Task 4: Configure Git LFS and Import Canonical Assets

**Files:**

- Create: `.gitattributes`
- Modify: `.gitignore`
- Create: `reproducibility/v9_observability_colab_schema3/**`
- Create: `tests/fixtures/v9dev/**`
- Create: `artifacts/v9/explanations/v9_schema3_results.zip`
- Create: `artifacts/v9/explanations/MANIFEST.sha256`
- Create: `references/papers/*.pdf`

- [ ] **Step 1: Install and initialize Git LFS for this repository**

Run:

```bash
rtk brew install git-lfs
rtk git lfs install --local
rtk git lfs version
```

Expected: `git-lfs` prints an installed version and local hooks are configured.

- [ ] **Step 2: Add exact LFS rules**

Create `.gitattributes` with:

```gitattributes
/reproducibility/v9_observability_colab_schema3/corpus/**/*.csv filter=lfs diff=lfs merge=lfs -text
/reproducibility/v9_observability_colab_schema3/corpus/**/*.jsonl filter=lfs diff=lfs merge=lfs -text
/reproducibility/v9_observability_colab_schema3/corpus/**/dashboard_data.json filter=lfs diff=lfs merge=lfs -text
/reproducibility/v9_observability_colab_schema3/corpus/**/dashboard_standalone.html filter=lfs diff=lfs merge=lfs -text
/reproducibility/v9_observability_colab_schema3/checkpoint/**/*.pt filter=lfs diff=lfs merge=lfs -text
/reproducibility/v9_observability_colab_schema3/checkpoint/**/*.npz filter=lfs diff=lfs merge=lfs -text
/tests/fixtures/v9dev/**/*.csv filter=lfs diff=lfs merge=lfs -text
/tests/fixtures/v9dev/**/*.jsonl filter=lfs diff=lfs merge=lfs -text
/tests/fixtures/v9dev/**/dashboard_data.json filter=lfs diff=lfs merge=lfs -text
/tests/fixtures/v9dev/**/dashboard_standalone.html filter=lfs diff=lfs merge=lfs -text
/artifacts/v9/explanations/*.zip filter=lfs diff=lfs merge=lfs -text
/references/papers/*.pdf filter=lfs diff=lfs merge=lfs -text
```

Append to `.gitignore`:

```gitignore

# Reorganized generated outputs
/artifacts/v9/dashboard/
/artifacts/v9/explanations/extracted/
/reproducibility/v9_observability_colab_schema3/**/__pycache__/
/reproducibility/v9_observability_colab_schema3/**/.pytest_cache/
/reproducibility/v9_observability_colab_schema3/gnn/diagnostics/
```

- [ ] **Step 3: Copy the canonical schema-3 package without generated caches**

Run from the isolated worktree:

```bash
rtk mkdir -p reproducibility artifacts/v9/explanations references/papers \
  tests/fixtures
rtk proxy rsync -a \
  --exclude '.pytest_cache/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'gnn/diagnostics/' \
  /Users/edward/Desktop/GNN_Community_Detection/v9_observability_colab_schema3/ \
  reproducibility/v9_observability_colab_schema3/
```

Expected: notebook, runner, requirements, top-level checkpoint, full V9 corpus, bundled `gnn/`, and seven tests are copied; generated nested diagnostics and caches are absent.

- [ ] **Step 4: Prove the root and bundled full V9 corpora are identical**

Run:

```bash
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python \
  scripts/data/v9_assets.py compare-corpora \
  /Users/edward/Desktop/GNN_Community_Detection/Documents/Data/synthetic_cbp_graph_corpus_v9 \
  reproducibility/v9_observability_colab_schema3/corpus/synthetic_cbp_graph_corpus_v9
```

Expected: JSON with empty `changed`, `left_only`, and `right_only` lists, exit 0. If the command exits 2, stop this task and preserve both versions; do not delete or overwrite either tree.

- [ ] **Step 5: Copy V9dev, explanation evidence, and papers**

Run:

```bash
rtk proxy rsync -a \
  --exclude '.pytest_cache/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  /Users/edward/Desktop/GNN_Community_Detection/Documents/Data/synthetic_cbp_graph_corpus_v9dev/ \
  tests/fixtures/v9dev/
rtk proxy rsync -a \
  /Users/edward/Desktop/GNN_Community_Detection/v9_schema3_results.zip \
  artifacts/v9/explanations/v9_schema3_results.zip
rtk proxy rsync -a \
  /Users/edward/Desktop/GNN_Community_Detection/Documents/GNN/ \
  references/papers/
```

Expected: V9dev, one ZIP, and exactly seven PDFs are present.

- [ ] **Step 6: Add the exact explanation manifest**

Create `artifacts/v9/explanations/MANIFEST.sha256` with:

```text
54064788c0cd92893296d1db926aaa902604e30db16fdc3151545413a30008fd  v9_schema3_results.zip
```

- [ ] **Step 7: Verify source/destination hashes and archive structure**

Run:

```bash
rtk shasum -a 256 \
  /Users/edward/Desktop/GNN_Community_Detection/v9_schema3_results.zip \
  artifacts/v9/explanations/v9_schema3_results.zip
rtk shasum -a 256 \
  /Users/edward/Desktop/GNN_Community_Detection/Documents/GNN/*.pdf \
  references/papers/*.pdf
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python \
  scripts/data/v9_assets.py verify-explanations
```

Expected: ZIP hashes are identical and equal the manifest; each paper has a matching source/destination hash; verifier reports 64,964 members.

- [ ] **Step 8: Stage assets and verify LFS pointers**

Run:

```bash
rtk git add .gitattributes .gitignore reproducibility tests/fixtures \
  artifacts/v9/explanations references/papers
rtk git lfs ls-files
rtk git check-attr filter -- \
  reproducibility/v9_observability_colab_schema3/corpus/synthetic_cbp_graph_corpus_v9/edges.csv \
  tests/fixtures/v9dev/crossing_events.csv \
  artifacts/v9/explanations/v9_schema3_results.zip \
  references/papers/RGCN.pdf
```

Expected: every listed path reports `filter: lfs`; source code and Markdown do not appear in `git lfs ls-files`.

- [ ] **Step 9: Commit canonical assets**

Run:

```bash
rtk git commit -m "data: add LFS-backed V9 reproducibility assets"
```

---

### Task 5: Move Dashboard and Data Utilities into Packages

**Files:**

- Move: `Documents/Data/scripts/` → `scripts/dashboard/`
- Move: `scripts/dashboard/validate_corpus.py` → `scripts/data/validate_corpus.py`
- Create: `scripts/dashboard/__init__.py`
- Modify: `scripts/dashboard/build_dashboard.py`
- Modify: `scripts/dashboard/build_v9_dashboard.py`
- Modify: `scripts/dashboard/v9_recovery_explainer_ui.py`
- Modify: `tests/test_observability_artifact_schema3.py`
- Modify: `tests/test_recovery_bundle.py`
- Modify: `tests/test_recovery_layout_parity.py`
- Modify: `tests/test_v9_dashboard_builder.py`
- Modify: `tests/test_v9_design_system.py`
- Modify: `tests/test_v9_recovery_explainer_ui.py`
- Modify: `tests/test_v9_summary_page.py`

- [ ] **Step 1: Add failing layout/import assertions**

Append to `tests/test_project_layout.py`:

```python
def test_utility_packages_have_single_responsibilities():
    assert (ROOT / "scripts/dashboard/build_dashboard.py").is_file()
    assert (ROOT / "scripts/dashboard/build_v9_dashboard.py").is_file()
    assert (ROOT / "scripts/data/validate_corpus.py").is_file()
    assert not (ROOT / "Documents/Data/scripts").exists()


def test_dashboard_modules_import_from_their_package():
    from scripts.dashboard import build_v9_dashboard
    from scripts.dashboard import v9_recovery_sidecars

    assert build_v9_dashboard.V9_CORPUS_NAME == "synthetic_cbp_graph_corpus_v9"
    assert callable(v9_recovery_sidecars.publish_prepackaged_schema3_zip)
```

- [ ] **Step 2: Run the assertions to verify they fail**

Run:

```bash
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest \
  tests/test_project_layout.py -q
```

Expected: FAIL because utilities still live under `Documents/Data/scripts`.

- [ ] **Step 3: Move the utility tree atomically**

Run:

```bash
rtk git mv Documents/Data/scripts scripts/dashboard
rtk git mv scripts/dashboard/validate_corpus.py scripts/data/validate_corpus.py
```

Create `scripts/dashboard/__init__.py` with:

```python
"""V9 dashboard builders, renderers, and sidecar publication helpers."""
```

- [ ] **Step 4: Replace bare sibling imports**

In `scripts/dashboard/build_dashboard.py`, replace the final import with:

```python
from scripts.dashboard.explorer_ui import EXPLORER_CSS, EXPLORER_JS  # noqa: E402
```

In `scripts/dashboard/build_v9_dashboard.py`, replace dynamic imports with the
fully qualified forms:

```python
from scripts.dashboard.v9_recovery_sidecars import (
    package_schema3_sidecars,
    publish_prepackaged_schema3_manifest,
    publish_prepackaged_schema3_zip,
)
from scripts.dashboard.v9_dashboard_ui import (
    V9_RESULTS_CSS,
    V9_RESULTS_JS,
    V9_RESULTS_NAV_BTN,
    V9_RESULTS_SECTION,
    UNSUP_AD_NAV_BTN,
    UNSUP_AD_SECTION,
    UNSUP_AD_JS,
    UNSUP_AD_CSS,
    UNSUP_AD_VIEW_MODEL_JS,
    UNSUP_AD_CHART_JS,
)
from scripts.dashboard.v9_summary_page import (
    SUMMARY_PAGE_CSS,
    SUMMARY_PAGE_RENDERER_JS,
    SUMMARY_PAGE_RUNTIME_JS,
)
from scripts.dashboard.v9_recovery_explainer_ui import (
    V9_RECOVERY_EXPLAINER_CSS,
    V9_RECOVERY_EXPLAINER_JS,
)
from scripts.dashboard.v9_gnn_architecture_ui import (
    GNN_ARCHITECTURE_VIEW_MODEL_JS,
    GNN_ARCHITECTURE_UI_JS,
    GNN_ARCHITECTURE_CSS,
)
from scripts.dashboard.v9_design_system import (
    build_design_system_css,
    inject_provenance,
    provenance_from_meta,
    strip_google_fonts_import,
)
```

Remove `sys.path.insert(0, HERE)` branches made unnecessary by these imports.

- [ ] **Step 5: Replace builder path constants**

At the top of `scripts/dashboard/build_v9_dashboard.py`, import canonical paths
and define string constants for the existing `os.path` call sites:

```python
from gnn.paths import (
    REPO_ROOT as REPO_ROOT_PATH,
    V9_CORPUS_DIR as V9_CORPUS_PATH,
    V9_DASHBOARD_DIR as V9_DASHBOARD_PATH,
    V9_EXPLANATION_ARCHIVE as V9_EXPLANATION_PATH,
)


REPO_ROOT = os.fspath(REPO_ROOT_PATH)
V9_CORPUS = os.fspath(V9_CORPUS_PATH)
V9_DATA = os.path.join(V9_CORPUS, "dashboard_data.json")
V9_RECOVERY_ARCHIVE = os.fspath(V9_EXPLANATION_PATH)
OUT_DIR = os.fspath(V9_DASHBOARD_PATH)
```

Keep diagnostics under `REPO_ROOT/gnn/diagnostics`.

Update the module usage text and emitted serving command to the package paths:

```text
python -m scripts.dashboard.build_dashboard \
  reproducibility/v9_observability_colab_schema3/corpus/synthetic_cbp_graph_corpus_v9
python -m scripts.dashboard.build_v9_dashboard
python -m http.server 8000 --directory artifacts/v9/dashboard
```

Apply the same serving-path correction to the user-facing message embedded in
`scripts/dashboard/v9_recovery_explainer_ui.py`.

- [ ] **Step 6: Remove the V8 template dependency from the generic builder**

Change the call and function signature in `scripts/dashboard/build_dashboard.py`:

```python
out_html = render_html(DATA, name, corpus_dir)


def render_html(DATA, name, corpus_dir):
    """Splice data and the explorer into the corpus's standalone template."""
    tmpl_path = os.path.join(corpus_dir, "dashboard_standalone.html")
    with open(tmpl_path) as template:
        html = template.read()
```

This retains the existing fresh/already-transformed handling and removes the
hard-coded V8 corpus read.

- [ ] **Step 7: Update tests to import the package**

Replace imports such as:

```python
from Documents.Data.scripts import v9_recovery_sidecars
```

with:

```python
from scripts.dashboard import v9_recovery_sidecars
```

Replace `importlib` paths under `Documents/Data/scripts` with direct imports
from `scripts.dashboard` in:

- `tests/test_observability_artifact_schema3.py`
- `tests/test_recovery_bundle.py`
- `tests/test_recovery_layout_parity.py`
- `tests/test_v9_dashboard_builder.py`
- `tests/test_v9_design_system.py`
- `tests/test_v9_recovery_explainer_ui.py`
- `tests/test_v9_summary_page.py`

Where a test deliberately reads module source rather than importing it, define
the source path from the new package root:

```python
DASHBOARD_SCRIPTS = ROOT / "scripts" / "dashboard"
UI_MODULE_PATH = DASHBOARD_SCRIPTS / "v9_dashboard_ui.py"
RECOVERY_UI_PATH = DASHBOARD_SCRIPTS / "v9_recovery_explainer_ui.py"
```

Update the serving-command assertion to
`python -m http.server 8000 --directory artifacts/v9/dashboard`. Leave the six
tests that read a generated dashboard for Task 7; all source/import paths move
in this task.

- [ ] **Step 8: Run utility tests**

Run:

```bash
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest -q \
  tests/test_project_layout.py \
  tests/test_observability_artifact_schema3.py \
  tests/test_recovery_bundle.py \
  tests/test_recovery_layout_parity.py \
  tests/test_v9_dashboard_builder.py \
  tests/test_v9_design_system.py \
  tests/test_v9_recovery_explainer_ui.py \
  tests/test_v9_summary_page.py \
  -k 'not generated_dashboard and not v9_research_log'
```

Expected: PASS.

- [ ] **Step 9: Commit**

Run:

```bash
rtk git add scripts tests/test_project_layout.py tests/test_v9_dashboard_builder.py \
  tests/test_observability_artifact_schema3.py tests/test_recovery_bundle.py \
  tests/test_recovery_layout_parity.py \
  tests/test_v9_design_system.py tests/test_v9_recovery_explainer_ui.py \
  tests/test_v9_summary_page.py
rtk git commit -m "refactor: organize dashboard and data utilities"
```

---

### Task 6: Point Runtime and Data Tests at Canonical V9 Assets

**Files:**

- Modify: `gnn/run_demo.py`
- Modify: `tests/test_demo_baseline.py`
- Modify: `tests/test_run_demo_smoke.py`
- Modify: `tests/test_unsupervised_ad.py`
- Modify: `tests/test_v9_corpus_snapshot.py`
- Modify: path assertions in `tests/test_gnn_architecture_bakeoff.py`

- [ ] **Step 1: Replace test-local data constants**

Use these exact imports and aliases:

```python
from gnn.paths import V9_CORPUS_DIR, V9DEV_CORPUS_DIR

CD = V9DEV_CORPUS_DIR
V9 = V9_CORPUS_DIR
V9DEV = V9DEV_CORPUS_DIR
```

Apply `CD` in `tests/test_demo_baseline.py` and `tests/test_run_demo_smoke.py`;
apply `V9`/`V9DEV` in `tests/test_v9_corpus_snapshot.py`; replace both explicit
V9dev constructions in `tests/test_unsupervised_ad.py` with
`V9DEV_CORPUS_DIR`.

- [ ] **Step 2: Update the runnable example in `gnn/run_demo.py`**

Use:

```text
python -m gnn.run_demo
```

and explain in the module docstring that the default is the LFS-backed canonical
V9 corpus and `CBP_CORPUS_DIR` overrides it.

- [ ] **Step 3: Run all corpus-dependent tests**

Run:

```bash
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest -q \
  tests/test_demo_baseline.py \
  tests/test_run_demo_smoke.py \
  tests/test_unsupervised_ad.py \
  tests/test_v9_corpus_snapshot.py \
  tests/test_df_graphmodel_rgcn.py \
  tests/test_gnn_architecture_bakeoff.py
```

Expected: PASS with no missing-corpus failures.

- [ ] **Step 4: Commit**

Run:

```bash
rtk git add gnn/run_demo.py tests/test_demo_baseline.py \
  tests/test_run_demo_smoke.py tests/test_unsupervised_ad.py \
  tests/test_v9_corpus_snapshot.py tests/test_gnn_architecture_bakeoff.py
rtk git commit -m "test: use canonical V9 fixtures"
```

---

### Task 7: Make Generated-Dashboard Tests Self-Contained

**Files:**

- Modify: `tests/test_v9_dashboard_builder.py`
- Modify: `scripts/dashboard/build_v9_dashboard.py` only if the fixture exposes a path-injection defect

- [ ] **Step 1: Replace the static generated index with a fixture**

Remove `GENERATED_INDEX` and add:

```python
@pytest.fixture
def generated_dashboard_html(tmp_path, monkeypatch):
    """Run the complete compositor on a deterministic in-memory data fixture."""
    data = {
        "v9Demo": _compatible_v9_demo(),
        "v9RecoveryExplainer": {"schema_version": "1.0", "fixture": True},
        "unsupervisedAD": {"schema_version": 3, "modes": {}},
        "nav": {"keep": True},
        "unrelated": {"keep": "unchanged"},
    }
    monkeypatch.setattr(BUILDER, "_load_v9_data", lambda **_: data)
    monkeypatch.setattr(BUILDER, "_publish_staged_dashboard", lambda *_: None)
    template_path = tmp_path / "template.html"
    template_path.write_text(_minimal_dashboard_template())
    staged = tmp_path / "staged"
    staged.mkdir()
    BUILDER._build_staged_dashboard(staged, staged, template_path)
    return (staged / "index.html").read_text()
```

- [ ] **Step 2: Inject the fixture into the six generated-output tests**

Change each test signature to accept `generated_dashboard_html` and start with:

```python
html = generated_dashboard_html
```

Keep the existing assertions unchanged for D3 independence, grouped navigation,
single initial render, V9 headline/table contract, no coverage-warning banner,
and no legacy duplicate sections/styles.

- [ ] **Step 3: Run the full dashboard-builder test module**

Run:

```bash
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest \
  tests/test_v9_dashboard_builder.py -q
```

Expected: PASS without reading `artifacts/v9/dashboard/index.html`.

- [ ] **Step 4: Commit**

Run:

```bash
rtk git add tests/test_v9_dashboard_builder.py scripts/dashboard/build_v9_dashboard.py
rtk git commit -m "test: build dashboard fixtures in isolation"
```

---

### Task 8: Move Active Documentation and Rewrite Onboarding

**Files:**

- Move: `Documents/Data/DATA_GUIDE.md` → `docs/data/DATA_GUIDE.md`
- Move: `Documents/Data/changes_3.md` → `docs/research/changes_3.md`
- Move: `ideas.html` → `docs/research/ideas.html`
- Modify: `README.md`, `AGENTS.md`, `CLAUDE.md`, `PROJECT_MEMORY.md`
- Modify: `reproducibility/v9_observability_colab_schema3/README.md`
- Create: `tasks/README.md`, `docs/superpowers/README.md`
- Modify: `tests/test_v9_dashboard_builder.py` research-log path

- [ ] **Step 1: Move the active documentation**

Run:

```bash
rtk mkdir -p docs/data docs/research
rtk git mv Documents/Data/DATA_GUIDE.md docs/data/DATA_GUIDE.md
rtk git mv Documents/Data/changes_3.md docs/research/changes_3.md
rtk git mv ideas.html docs/research/ideas.html
```

- [ ] **Step 2: Add historical-record notices**

Create `tasks/README.md` with:

```markdown
# Task Records

`repository_reorganization_design.md` and `repository_reorganization_plan.md`
describe the current layout change. Other files are historical implementation
records and intentionally preserve the paths and commands that existed when the
work was performed. Use the root README for current commands.
```

Create `docs/superpowers/README.md` with:

```markdown
# Historical Design and Plan Records

Files below `plans/` and `specs/` are immutable historical records. Their paths
describe the repository at the time of implementation and are not current
onboarding instructions. Use the root README and `tasks/` reorganization files
for the active filesystem.
```

- [ ] **Step 3: Rewrite the root README around the current filesystem**

Use these sections in this order:

```markdown
# GNN Community Detection
## Safety and synthetic-data scope
## What the V9 positive control demonstrates
## Repository layout
## Clone and hydrate Git LFS assets
## Environment setup
## Run the V9 demo
## Run tests
## Validate corpora
## Run schema-3 observability in Colab
## Verify and extract explanation evidence
## Build and serve the dashboard
## Research papers
## Generated and local-only files
## Known schema-3 result limitation
```

Include these exact runnable command blocks:

```bash
git lfs install
git lfs pull
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m gnn.run_demo
pytest -q
python -m scripts.data.validate_corpus tests/fixtures/v9dev
python -m scripts.data.v9_assets verify-explanations
python -m scripts.data.v9_assets extract-explanations \
  artifacts/v9/explanations/extracted
python -m scripts.dashboard.build_v9_dashboard
python -m http.server 8000 --directory artifacts/v9/dashboard
```

State explicitly that the ZIP has a failed coverage gate, 19 exact Hybrid
explanations, and one failed case.

- [ ] **Step 4: Synchronize active contributor instructions**

Update `AGENTS.md` and `CLAUDE.md` to name:

```text
docs/research/changes_3.md
docs/data/DATA_GUIDE.md
scripts/data/validate_corpus.py
scripts/dashboard/build_v9_dashboard.py
tests/fixtures/v9dev/
reproducibility/v9_observability_colab_schema3/
artifacts/v9/explanations/v9_schema3_results.zip
artifacts/v9/dashboard/
```

Remove V8 as a current goal/default/data path while retaining the historical
honest-track interpretation. Require `docs/research/changes_3.md` before model
or evaluation changes.

- [ ] **Step 5: Make the data guide and research log describe the new layout**

Replace the current-status block and corpus table at the top of
`docs/data/DATA_GUIDE.md` with V9-first text that names the canonical paths:

```markdown
> Current-status note (2026-08-06): The active runtime is the V9 designed
> positive control. The canonical full corpus is versioned through Git LFS
> inside `reproducibility/v9_observability_colab_schema3/corpus/`; the V9dev
> fixture is `tests/fixtures/v9dev/`. V8 remains historical context, but its
> corpus is not part of this organized branch.
```

Update its command examples and dashboard section to the same module commands
used by the root README. Preserve the V8-versus-V9 research interpretation, but
remove claims that V8 is an active checked-in/default corpus. Change the two
historical dashboard-output lines in `docs/research/changes_3.md` to state that
the current rebuild target is `artifacts/v9/dashboard/`; do not rewrite measured
results or historical decisions.

- [ ] **Step 6: Correct the schema-3 handoff README**

Replace the stale statement that schema-3 dashboard support is absent from
`main` with a current handoff section that says:

```markdown
## Downstream dashboard

The repository's schema-3 reader lives under `scripts/dashboard/`. From the
repository root, verify the archive with
`python -m scripts.data.v9_assets verify-explanations`, then run
`python -m scripts.dashboard.build_v9_dashboard`. The archived result is a
degraded 19-of-20 run with one failed case and must not be described as a fully
passing coverage-gated artifact.
```

- [ ] **Step 7: Update the active research-log test and memory**

Change the test path to:

```python
log = (ROOT / "docs/research/changes_3.md").read_text()
```

Append to `PROJECT_MEMORY.md`:

```markdown
## 2026-08-06: repository organization and artifact policy

- The active runtime is V9-first. Canonical full V9 data lives inside the
  schema-3 reproducibility handoff; V9dev lives under `tests/fixtures/`.
- Schema-3 explanation evidence is versioned as one SHA-256-verified Git LFS
  ZIP. Extracted dashboard/recovery trees are generated and ignored.
- `gnn/` remains flat and is the active implementation; the handoff's bundled
  `gnn/` is an intentional reproducibility snapshot.
- GNN documentation changes must preserve as-of and leakage semantics and be
  verified separately from functional changes.
```

- [ ] **Step 8: Run active-document checks**

Run:

```bash
rtk rg -n 'Documents/Data/(scripts|changes_3.md|DATA_GUIDE.md|v9_dashboard)' \
  README.md AGENTS.md CLAUDE.md gnn scripts tests docs/data docs/research
rtk rg -n 'defaults? to V8|active (V8|V8, V9)|checked-in.*V8' \
  README.md AGENTS.md CLAUDE.md docs/data/DATA_GUIDE.md
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest -q \
  tests/test_project_layout.py tests/test_v9_dashboard_builder.py
```

Expected: the search returns no stale active path; tests pass. Historical
`tasks/` and `docs/superpowers/{plans,specs}/` are excluded by design.

- [ ] **Step 9: Commit**

Run:

```bash
rtk git add README.md AGENTS.md CLAUDE.md PROJECT_MEMORY.md docs tasks/README.md \
  reproducibility/v9_observability_colab_schema3/README.md \
  tests/test_v9_dashboard_builder.py
rtk git commit -m "docs: synchronize the V9-first repository layout"
```

---

### Task 9: Document the Active GNN Package Without Logic Changes

**Files:**

- Create: `scripts/data/compare_comment_only.py`
- Create: `tests/test_gnn_documentation.py`
- Modify: all `gnn/*.py`

- [ ] **Step 1: Add the documentation contract test**

Create `tests/test_gnn_documentation.py` with:

```python
"""Documentation contracts for active and reproducibility GNN modules."""
import ast
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_ROOTS = {
    "active": ROOT / "gnn",
    "schema3": ROOT / "reproducibility/v9_observability_colab_schema3/gnn",
}


def _python_files(root):
    return sorted(path for path in root.glob("*.py") if path.is_file())


@pytest.mark.parametrize("package", MODULE_ROOTS)
def test_every_gnn_module_has_a_docstring(package):
    missing = []
    for path in _python_files(MODULE_ROOTS[package]):
        if ast.get_docstring(ast.parse(path.read_text())) is None:
            missing.append(path.name)
    assert missing == []


@pytest.mark.parametrize("package", MODULE_ROOTS)
def test_public_top_level_gnn_apis_have_docstrings(package):
    missing = []
    for path in _python_files(MODULE_ROOTS[package]):
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not node.name.startswith("_") and ast.get_docstring(node) is None:
                    missing.append(f"{path.name}:{node.name}")
    assert missing == []
```

- [ ] **Step 2: Add a comment-only AST comparator**

Create `scripts/data/compare_comment_only.py` with:

```python
#!/usr/bin/env python3
"""Compare working-tree Python with HEAD after removing all docstrings."""
from __future__ import annotations

import argparse
import ast
import subprocess
from pathlib import Path


DOCSTRING_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


class StripDocstrings(ast.NodeTransformer):
    """Remove leading string expressions that Python treats as docstrings."""

    def generic_visit(self, node):
        node = super().generic_visit(node)
        if isinstance(node, DOCSTRING_OWNERS) and node.body:
            first = node.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                node.body = node.body[1:]
        return node


def normalized(source: str) -> str:
    """Return an attribute-free AST dump after stripping docstrings."""
    tree = StripDocstrings().visit(ast.parse(source))
    ast.fix_missing_locations(tree)
    return ast.dump(tree, include_attributes=False)


def compare(path: Path) -> bool:
    """Return whether one working-tree file differs from its HEAD logic."""
    relative = path.as_posix()
    baseline = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return normalized(baseline) != normalized(path.read_text())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args(argv)
    changed = []
    for supplied in args.paths:
        candidates = supplied.glob("*.py") if supplied.is_dir() else (supplied,)
        changed.extend(path.as_posix() for path in candidates if compare(path))
    if changed:
        print("logic changed:\n" + "\n".join(sorted(changed)))
        return 1
    print("comment/docstring-only AST comparison passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run the active documentation contract to verify it fails**

Run:

```bash
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest \
  tests/test_gnn_documentation.py -q -k active
```

Expected: FAIL listing missing active module and public API docstrings.

- [ ] **Step 4: Add exact missing module docstrings**

Use these module docstrings at the top of the named active files:

```text
gnn/__init__.py: "Active leak-safe GNN anomaly-detection research package."
gnn/config.py: "Runtime configuration for corpus selection and generated diagnostics."
gnn/detector.py: "Scikit-learn fitting helpers shared by tabular detector experiments."
gnn/graphmodel_alt.py: "Alternative GraphSAGE, GAT, GIN, and KPI-AA encoder definitions."
gnn/graphmodel_rgcn.py: "Typed as-of person-graph construction and relational GNN scoring."
gnn/unsupervised_ad.py: "Leak-safe unsupervised and caught-supervised anomaly evaluation."
```

- [ ] **Step 5: Add exact public API docstring intent**

Insert docstrings with these exact first sentences into each currently
undocumented public symbol:

```text
demo_baseline.build_baseline_features — "Build leak-safe as-of tabular features for requested crossing events."
demo_checkpoint.WrittenDemoCheckpoint — "Paths and identity metadata for a newly written checkpoint."
demo_checkpoint.LoadedDemoCheckpoint — "Validated models, scores, and metadata loaded from a checkpoint."
demo_checkpoint.read_demo_checkpoint_metadata — "Read checkpoint metadata without loading model tensors or score arrays."
detector.fit_predict — "Fit the tabular detector and return positive-class scores for validation and test rows."
explanation_narrative.build_prompt — "Build the bounded evidence prompt used for one recovery narrative."
explanation_narrative.validate_candidate — "Validate a generated narrative against its structured evidence contract."
explanation_narrative.render_template — "Render the deterministic narrative fallback from validated evidence."
explanation_narrative.generate_narrative — "Generate and validate one narrative, recording deterministic fallback diagnostics."
giant_observability_benchmark.run_benchmark — "Measure schema-3 observability memory and publication behavior on the full graph."
giant_observability_benchmark.main — "Parse CLI arguments and run the giant observability benchmark."
gnn_architecture_bakeoff.build_parser — "Build the architecture-bakeoff command-line parser."
gnn_architecture_bakeoff.main — "Train and compare configured GNN encoders on one corpus snapshot."
graphmodel_alt.SAGEEncoder — "Encode person nodes with two GraphSAGE message-passing layers."
graphmodel_alt.GATEncoder — "Encode person nodes with relation-collapsed graph attention layers."
graphmodel_alt.GINEncoder — "Encode person nodes with graph isomorphism network layers."
graphmodel_alt.KPIAAEncoder — "Encode person nodes with KPI-AA-inspired gated relation aggregation."
graphmodel_rgcn.RelationSAGEEncoder — "Encode typed person relations with relation-specific GraphSAGE convolutions."
graphmodel_rgcn.build_anchor_graph — "Build the legacy anchor graph retained for compatibility experiments."
graphmodel_rgcn.build_person_graph_typed — "Build the typed person graph using only observable as-of relations."
graphmodel_rgcn.train_rgcn — "Fit the relational encoder on labels available by the training cutoff."
graphmodel_rgcn.asof_risk_rgcn — "Score rows from graph state and caught labels available strictly as of each row time."
learned_cell.UF — "Maintain disjoint co-travel components while replaying events in time order."
learned_cell.DaySnapshotInputs — "Frozen daily graph inputs used by relational training and scoring."
observability_artifact.validate_schema3_artifact — "Validate schema-3 pointer, coverage, and evidence invariants."
observability_artifact.serialize_artifact — "Serialize a validated observability artifact without inlining sidecar evidence."
observability_artifact.validate_artifact_invariants — "Reject observability artifacts that violate leakage or schema contracts."
recovery_observability.RecoveryAnchor — "One baseline-missed person selected for recovery analysis."
recovery_observability.DailyPoolTrace — "Frozen daily candidate-pool and ranking provenance."
recovery_observability.RecoveryRun — "Complete baseline-versus-hybrid recovery output for one evaluation run."
recovery_observability.RecoveryOverlap — "Overlap counts between baseline and hybrid recovery sets."
recovery_observability.FrozenRankReference — "Immutable rank and score reference for one candidate."
recovery_observability.HybridOnlyCase — "A hidden carrier recovered by Hybrid but missed by the baseline."
run_demo.evaluate — "Evaluate ranked scores at configured operational depths."
run_demo.add_tiebreak — "Add deterministic event-ID jitter without changing rank meaningfully."
run_demo.load_pool — "Load the observable event pool and normalize timestamps and split labels."
run_demo.stratum_for_pool — "Assign graph-observability strata from leak-safe structural features."
run_demo.paired_event_bootstrap — "Bootstrap paired baseline and hybrid metrics over shared sampled events."
run_demo.stratum_metrics — "Compute per-stratum ranking metrics for one score vector."
run_demo.main — "Run the leak-safe baseline-versus-GNN V9 comparison."
sage_explainer.AblationSpec — "Describe one evidence factor removed for a counterfactual score."
sage_explainer.CounterfactualContext — "Reusable graph state for grouped counterfactual scoring."
sage_explainer.DaySnapshot — "As-of graph, features, and scores frozen for one evaluation day."
sage_explainer.Seed0ExplanationEngine — "Generate deterministic seed-0 GNNExplainer evidence for selected cases."
sage_explainer.score_grouped_counterfactual — "Score grouped evidence ablations without rebuilding unchanged graph state."
sage_explainer.member_subgraph — "Materialize the exact member-induced subgraph used by one explanation."
sage_explainer.make_gnn_explainer — "Construct the configured PyG GNNExplainer wrapper."
sage_explainer.build_flow_stages — "Describe how observable evidence flows through the two-hop scoring pipeline."
sage_explainer.aggregate_restart_masks — "Aggregate restart attribution masks with completeness diagnostics."
sage_explainer.matched_random_controls — "Select deterministic matched controls for faithfulness comparisons."
sage_explainer.edge_removal_faithfulness — "Measure score change after removing attributed versus control edges."
sage_explainer.classify_factor_stability — "Classify whether an evidence factor is stable across explanation restarts."
sage_explainer.build_ablation_specs — "Build deterministic node, edge, and relation ablation specifications."
sage_explainer.build_complete_community — "Stream the complete community while bounding the display projection."
unsupervised_ad.corpus_output_path — "Return a corpus-qualified diagnostics path for anomaly results."
unsupervised_ad.main — "Run deployable anomaly arms, freeze scores, then attach oracle-only evaluation."
unsupervised_features.FeatureBundle — "Leak-safe tabular and relational feature frames plus provenance."
unsupervised_features.EncodedSplits — "Encoded train, validation, and test matrices with frozen schemas."
```

Keep existing longer docstrings and expand these first sentences with parameter,
return, and invariant details visible in each function signature.

- [ ] **Step 6: Add focused invariant comments**

Place these comments at the corresponding boundaries if an equivalent comment
is not already present:

```python
# Relation timestamps are availability times: an edge at or after the scored
# row is excluded even when its underlying real-world event happened earlier.
```

in `graphmodel_rgcn.build_person_graph_typed` before temporal edge filtering;

```python
# Caught state is replayed forward and frozen before scoring the current row, so
# the row's own outcome and all future outcomes remain unavailable features.
```

in `learned_cell` at caught-history snapshot construction;

```python
# Oracle files are opened only after every deployable score and threshold has
# frozen; data below this boundary is evaluation-only.
```

in `run_demo.main` and `unsupervised_ad.main` at oracle loading;

```python
# Sidecar references carry hashes and byte counts; publishing the pointer JSON
# before the verified evidence tree would create a corrupt but plausible run.
```

in `observability_artifact`/`recovery_bundle` at final publication.

In `gnn/sage_explainer.py`, update the snapshot-reference comment to
`reproducibility/v9_observability_colab_schema3/gnn/sage_explainer.py`; do not
change the parity contract it documents.

- [ ] **Step 7: Prove active changes are documentation-only**

Run before committing:

```bash
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python \
  scripts/data/compare_comment_only.py gnn
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest -q \
  tests/test_gnn_documentation.py -k active \
  tests/test_demo_baseline.py \
  tests/test_df_graphmodel_rgcn.py \
  tests/test_run_demo_smoke.py \
  tests/test_observability_artifact_schema3.py \
  tests/test_recovery_observability.py \
  tests/test_sage_explainer.py \
  tests/test_unsupervised_ad.py
```

Expected: AST comparison passes and all selected tests pass.

- [ ] **Step 8: Commit**

Run:

```bash
rtk git add gnn scripts/data/compare_comment_only.py \
  tests/test_gnn_documentation.py
rtk git commit -m "docs: document active GNN invariants and APIs"
```

---

### Task 10: Document the Schema-3 GNN Snapshot Without Deduplicating It

**Files:**

- Modify: `reproducibility/v9_observability_colab_schema3/gnn/*.py`
- Test: `tests/test_gnn_documentation.py`
- Test: `reproducibility/v9_observability_colab_schema3/tests/*.py`

- [ ] **Step 1: Run the schema-3 documentation contract to verify it fails**

Run:

```bash
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest \
  tests/test_gnn_documentation.py -q -k schema3
```

Expected: FAIL listing the bundled module/public API gaps.

- [ ] **Step 2: Add the exact bundled module and API documentation**

Use these module docstrings at the top of the bundled files:

```text
gnn/__init__.py: "Active leak-safe GNN anomaly-detection research package."
gnn/config.py: "Runtime configuration for corpus selection and generated diagnostics."
gnn/detector.py: "Scikit-learn fitting helpers shared by tabular detector experiments."
gnn/graphmodel_alt.py: "Alternative GraphSAGE, GAT, GIN, and KPI-AA encoder definitions."
gnn/graphmodel_rgcn.py: "Typed as-of person-graph construction and relational GNN scoring."
gnn/unsupervised_ad.py: "Leak-safe unsupervised and caught-supervised anomaly evaluation."
```

Use these exact first sentences for every currently undocumented public symbol
in the bundled snapshot:

```text
demo_baseline.build_baseline_features — "Build leak-safe as-of tabular features for requested crossing events."
demo_checkpoint.WrittenDemoCheckpoint — "Paths and identity metadata for a newly written checkpoint."
demo_checkpoint.LoadedDemoCheckpoint — "Validated models, scores, and metadata loaded from a checkpoint."
demo_checkpoint.read_demo_checkpoint_metadata — "Read checkpoint metadata without loading model tensors or score arrays."
detector.fit_predict — "Fit the tabular detector and return positive-class scores for validation and test rows."
explanation_narrative.build_prompt — "Build the bounded evidence prompt used for one recovery narrative."
explanation_narrative.validate_candidate — "Validate a generated narrative against its structured evidence contract."
explanation_narrative.render_template — "Render the deterministic narrative fallback from validated evidence."
explanation_narrative.generate_narrative — "Generate and validate one narrative, recording deterministic fallback diagnostics."
giant_observability_benchmark.run_benchmark — "Measure schema-3 observability memory and publication behavior on the full graph."
giant_observability_benchmark.main — "Parse CLI arguments and run the giant observability benchmark."
gnn_architecture_bakeoff.build_parser — "Build the architecture-bakeoff command-line parser."
gnn_architecture_bakeoff.main — "Train and compare configured GNN encoders on one corpus snapshot."
graphmodel_alt.SAGEEncoder — "Encode person nodes with two GraphSAGE message-passing layers."
graphmodel_alt.GATEncoder — "Encode person nodes with relation-collapsed graph attention layers."
graphmodel_alt.GINEncoder — "Encode person nodes with graph isomorphism network layers."
graphmodel_alt.KPIAAEncoder — "Encode person nodes with KPI-AA-inspired gated relation aggregation."
graphmodel_rgcn.RelationSAGEEncoder — "Encode typed person relations with relation-specific GraphSAGE convolutions."
graphmodel_rgcn.build_anchor_graph — "Build the legacy anchor graph retained for compatibility experiments."
graphmodel_rgcn.build_person_graph_typed — "Build the typed person graph using only observable as-of relations."
graphmodel_rgcn.train_rgcn — "Fit the relational encoder on labels available by the training cutoff."
graphmodel_rgcn.asof_risk_rgcn — "Score rows from graph state and caught labels available strictly as of each row time."
learned_cell.UF — "Maintain disjoint co-travel components while replaying events in time order."
learned_cell.DaySnapshotInputs — "Frozen daily graph inputs used by relational training and scoring."
observability_artifact.validate_schema3_artifact — "Validate schema-3 pointer, coverage, and evidence invariants."
observability_artifact.serialize_artifact — "Serialize a validated observability artifact without inlining sidecar evidence."
observability_artifact.validate_artifact_invariants — "Reject observability artifacts that violate leakage or schema contracts."
recovery_observability.RecoveryAnchor — "One baseline-missed person selected for recovery analysis."
recovery_observability.DailyPoolTrace — "Frozen daily candidate-pool and ranking provenance."
recovery_observability.RecoveryRun — "Complete baseline-versus-hybrid recovery output for one evaluation run."
recovery_observability.RecoveryOverlap — "Overlap counts between baseline and hybrid recovery sets."
recovery_observability.FrozenRankReference — "Immutable rank and score reference for one candidate."
recovery_observability.HybridOnlyCase — "A hidden carrier recovered by Hybrid but missed by the baseline."
run_demo.evaluate — "Evaluate ranked scores at configured operational depths."
run_demo.add_tiebreak — "Add deterministic event-ID jitter without changing rank meaningfully."
run_demo.load_pool — "Load the observable event pool and normalize timestamps and split labels."
run_demo.stratum_for_pool — "Assign graph-observability strata from leak-safe structural features."
run_demo.paired_event_bootstrap — "Bootstrap paired baseline and hybrid metrics over shared sampled events."
run_demo.stratum_metrics — "Compute per-stratum ranking metrics for one score vector."
run_demo.main — "Run the leak-safe baseline-versus-GNN V9 comparison."
sage_explainer.AblationSpec — "Describe one evidence factor removed for a counterfactual score."
sage_explainer.CounterfactualContext — "Reusable graph state for grouped counterfactual scoring."
sage_explainer.DaySnapshot — "As-of graph, features, and scores frozen for one evaluation day."
sage_explainer.Seed0ExplanationEngine — "Generate deterministic seed-0 GNNExplainer evidence for selected cases."
sage_explainer.score_grouped_counterfactual — "Score grouped evidence ablations without rebuilding unchanged graph state."
sage_explainer.member_subgraph — "Materialize the exact member-induced subgraph used by one explanation."
sage_explainer.make_gnn_explainer — "Construct the configured PyG GNNExplainer wrapper."
sage_explainer.build_flow_stages — "Describe how observable evidence flows through the two-hop scoring pipeline."
sage_explainer.aggregate_restart_masks — "Aggregate restart attribution masks with completeness diagnostics."
sage_explainer.matched_random_controls — "Select deterministic matched controls for faithfulness comparisons."
sage_explainer.edge_removal_faithfulness — "Measure score change after removing attributed versus control edges."
sage_explainer.classify_factor_stability — "Classify whether an evidence factor is stable across explanation restarts."
sage_explainer.build_ablation_specs — "Build deterministic node, edge, and relation ablation specifications."
sage_explainer.build_complete_community — "Stream the complete community while bounding the display projection."
unsupervised_ad.corpus_output_path — "Return a corpus-qualified diagnostics path for anomaly results."
unsupervised_ad.main — "Run deployable anomaly arms, freeze scores, then attach oracle-only evaluation."
unsupervised_features.FeatureBundle — "Leak-safe tabular and relational feature frames plus provenance."
unsupervised_features.EncodedSplits — "Encoded train, validation, and test matrices with frozen schemas."
```

Expand each first sentence with parameter, return, and invariant details visible
from that bundled function's own signature. Preserve every function body,
constant, import, path, checkpoint contract, and intentionally divergent
schema-3 behavior.

Add these comments only at equivalent bundled boundaries:

```python
# Relation timestamps are availability times: an edge at or after the scored
# row is excluded even when its underlying real-world event happened earlier.

# Caught state is replayed forward and frozen before scoring the current row, so
# the row's own outcome and all future outcomes remain unavailable features.

# Oracle files are opened only after every deployable score and threshold has
# frozen; data below this boundary is evaluation-only.

# Sidecar references carry hashes and byte counts; publishing the pointer JSON
# before the verified evidence tree would create a corrupt but plausible run.
```

- [ ] **Step 3: Prove snapshot changes are documentation-only**

Run:

```bash
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python \
  scripts/data/compare_comment_only.py \
  reproducibility/v9_observability_colab_schema3/gnn
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest \
  tests/test_gnn_documentation.py -q
```

Expected: AST comparison passes and all four documentation-contract parameters pass.

- [ ] **Step 4: Run the bundled package tests in package context**

From `reproducibility/v9_observability_colab_schema3/`, run:

```bash
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest tests -q
```

Expected: 7 bundled test modules pass with no import from the root `gnn/` package.

- [ ] **Step 5: Commit**

Run from the repository root:

```bash
rtk git add reproducibility/v9_observability_colab_schema3/gnn \
  tests/test_gnn_documentation.py
rtk git commit -m "docs: document schema3 GNN snapshot"
```

---

### Task 11: Clean Active Paths and Run Full Verification

**Files:**

- Modify only files identified by failing verification.
- Generated/ignored: `artifacts/v9/dashboard/`

- [ ] **Step 1: Verify no V8 data or generated staging tree entered the branch**

Run:

```bash
rtk git ls-files | rtk rg 'synthetic_cbp_graph_corpus_v8|\.v9_dashboard\.stage|__pycache__|\.pytest_cache|\.DS_Store'
```

Expected: no output. Historical text references to V8 are allowed; V8 data files are not.

- [ ] **Step 2: Verify LFS integrity and regular-blob limits**

Run:

```bash
rtk git lfs fsck
rtk git lfs ls-files
rtk git lfs migrate info --include-ref=HEAD --above=100MB
```

Expected: LFS fsck passes; corpus, V9dev, ZIP, checkpoint arrays, and seven PDFs
are listed; no regular blob at `HEAD` exceeds 100 MiB.

- [ ] **Step 3: Validate both corpora**

Run:

```bash
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m \
  scripts.data.validate_corpus \
  reproducibility/v9_observability_colab_schema3/corpus/synthetic_cbp_graph_corpus_v9
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m \
  scripts.data.validate_corpus tests/fixtures/v9dev
```

Expected: both validators succeed.

- [ ] **Step 4: Verify the notebook and runner wiring**

Run:

```bash
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m json.tool \
  reproducibility/v9_observability_colab_schema3/v9_schema3_observability.ipynb
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python \
  reproducibility/v9_observability_colab_schema3/run_schema3_observability.py --help
```

Expected: valid JSON and successful CLI help without starting a full run.

- [ ] **Step 5: Verify explanation evidence and build the dashboard**

Run:

```bash
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m \
  scripts.data.v9_assets verify-explanations
rtk proxy env \
  V9_SCHEMA3_RESULTS_ZIP=artifacts/v9/explanations/v9_schema3_results.zip \
  /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m \
  scripts.dashboard.build_v9_dashboard
```

Expected: archive verifies, dashboard writes
`artifacts/v9/dashboard/index.html` and `data_v9.json`, and the ignored recovery
tree is published below that directory.

- [ ] **Step 6: Run the complete root suite**

Run:

```bash
rtk /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest -q
```

Expected: 0 failures. Existing environment-dependent skips are acceptable only
when pytest reports their explicit skip reason.

- [ ] **Step 7: Scan active source and docs for stale layout claims**

Run:

```bash
rtk rg -n 'Documents/Data/(scripts|changes_3.md|DATA_GUIDE.md|v9_dashboard)|unset -> V8 default' \
  README.md AGENTS.md CLAUDE.md gnn scripts tests docs/data docs/research \
  reproducibility/v9_observability_colab_schema3/README.md
```

Expected: no stale active path/default claims.

- [ ] **Step 8: Request independent review**

Dispatch a `reviewer` agent with this exact scope:

```text
Review feature/repository-reorganization against
tasks/repository_reorganization_design.md. Check no feature loss, strict as-of
and leakage semantics, path safety, LFS coverage, ZIP extraction safety,
root-versus-schema3 separation, paper preservation, V8-data exclusion,
documentation accuracy, test quality, and accidental inclusion of generated
files. Report findings by severity with exact file paths.
```

Expected: no unresolved critical or high-severity findings. Fix accepted
findings with focused tests and a dedicated commit.

- [ ] **Step 9: Record final verification in project memory**

Append measured test counts, LFS object count/bytes, remote branch name, known
schema-3 degraded coverage, and any residual operational caveat to the existing
2026-08-06 reorganization section in `PROJECT_MEMORY.md`.

- [ ] **Step 10: Commit verification documentation**

Run:

```bash
rtk git add PROJECT_MEMORY.md
rtk git commit -m "docs: record repository verification"
```

Expected: commit contains only measured verification notes.

---

### Task 12: Upload the Feature Branch and LFS Objects

**Files:** No source changes expected.

- [ ] **Step 1: Confirm the main fallback remains untouched**

Run:

```bash
rtk proxy git -C /Users/edward/Desktop/GNN_Community_Detection status --short --branch
rtk git status --short --branch
```

Expected: the main worktree still shows its original user-owned dirty state;
the isolated feature worktree is clean.

- [ ] **Step 2: Confirm SSH reachability**

Run:

```bash
rtk git ls-remote --heads origin
```

Expected: `refs/heads/main` is returned.

- [ ] **Step 3: Upload all LFS objects for the feature branch**

Run:

```bash
rtk git lfs push --all origin feature/repository-reorganization
```

Expected: all referenced LFS objects upload successfully with no missing-object error.

- [ ] **Step 4: Push the Git branch**

Run:

```bash
rtk git push -u origin feature/repository-reorganization
```

Expected: the remote feature branch is created and upstream tracking is configured.

- [ ] **Step 5: Verify the remote branch and local LFS state**

Run:

```bash
rtk git ls-remote --heads origin feature/repository-reorganization
rtk git lfs fsck
rtk git status --short --branch
```

Expected: remote SHA equals local `HEAD`, LFS fsck passes, and the worktree is clean.

- [ ] **Step 6: Report handoff without changing main**

Report:

```text
Worktree path
Feature branch and remote SHA
Commit list
Root and schema3 test counts
LFS object count and uploaded bytes
Canonical V9 and explanation paths
Known 19-of-20 schema3 coverage limitation
Confirmation that main was not merged, reset, cleaned, or pushed
```

Do not merge or delete either worktree unless the user explicitly requests it.
