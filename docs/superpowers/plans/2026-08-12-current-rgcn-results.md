# Current RGCN Results Publication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Version and publish the newer 40,578-row RGCN architecture artifact as the current RGCN result while preserving the older 38,948-row table as explicitly historical evidence.

**Architecture:** Keep GraphSAGE as the active runtime and keep both result producers independent. Pin the existing architecture JSON byte-for-byte, add a SHA-bound compatibility exception for its legacy corpus path, make documentation state the cross-artifact Baseline/RGCN boundary, and regenerate the dashboard from the committed inputs. Add fail-closed release, baseline-feature, documentation, dashboard, and active-versus-bundled parity contracts.

**Tech Stack:** Python 3.14, JSON, SHA-256, pytest, Git/Git LFS, Markdown, the existing V9 dashboard builder.

---

## Execution constraints

- Work only in `/Users/edward/.config/superpowers/worktrees/GNN_Community_Detection/reorganize-repo` on `feature/repository-reorganization`.
- Read the source artifact only from `/Users/edward/Desktop/GNN_Community_Detection/gnn/diagnostics/gnn_architecture_comparison_v9.json`; do not modify the dirty `main` worktree.
- Do not retrain or refit any model. The selected RGCN result is frozen-artifact verifiable, not checkpoint replayable.
- Do not modify corpora, checkpoints, the GraphSAGE diagnostic, the explanation ZIP, model/evaluation logic, or strict as-of behavior.
- Do not commit, merge, or push. The user's no-commit instruction overrides the workflow's normal commit checkpoints; use `git diff --check`, focused tests, and independent review checkpoints instead.
- Prefix every shell command with `rtk`.

## File map

- Add `gnn/diagnostics/gnn_architecture_comparison_v9.json`: exact 549,896-byte RGCN/architecture evidence copied from dirty main.
- Modify `.gitignore`: unignore only the selected architecture JSON alongside the frozen demo JSON.
- Modify `.gitattributes`: force LF checkout bytes for the SHA-256-pinned JSON.
- Add `tests/test_v9_release_provenance.py`: exact release hash/config/metric and cross-artifact compatibility contracts.
- Modify `scripts/dashboard/build_v9_dashboard.py`: SHA-bound acceptance of the exact release artifact's legacy corpus identity.
- Modify `tests/test_v9_dashboard_builder.py`: pinned-legacy identity, mutation rejection, and real committed-dashboard embedding tests.
- Modify `tests/test_demo_baseline.py`: independent exact 14-feature baseline allowlist.
- Add `tests/test_gnn_cross_tree_parity.py`: fail-closed active-versus-bundled module and executable-AST contract.
- Modify `tests/test_gnn_documentation.py`: current-versus-historical RGCN publication contract.
- Modify `docs/research/changes_3.md`: current RGCN table, cross-artifact caveat, and historical appendix label.
- Modify `README.md`: onboarding evidence status and committed-diagnostics inventory.
- Modify `docs/data/DATA_GUIDE.md`: current RGCN evidence, historical status, and artifact-generation guidance.
- Modify `artifacts/v9/dashboard/index.html`: builder-generated snapshot containing the committed architecture artifact.
- Modify `PROJECT_MEMORY.md`: durable evidence boundary and remaining exact-retraining limitation.
- Remove `tasks/plan.md` and the empty `tasks/` directory only after its audit findings are reflected in active docs and memory.

### Task 1: Pin the exact RGCN artifact and its release contract

**Files:**
- Create: `tests/test_v9_release_provenance.py`
- Create: `gnn/diagnostics/gnn_architecture_comparison_v9.json`
- Modify: `.gitignore:41-43`
- Modify: `.gitattributes:1-14`

- [x] **Step 1: Add the failing exact-release tests**

Create `tests/test_v9_release_provenance.py` with this content:

```python
"""Pinned current V9 result artifacts and their cross-artifact boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from gnn import gnn_architecture_bakeoff as bakeoff


ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE = ROOT / "gnn/diagnostics/gnn_architecture_comparison_v9.json"
DEMO = ROOT / "gnn/diagnostics/demo_comparison_v9.json"
EXPECTED_ARCHITECTURE_SHA256 = (
    "d4b5d349532ca949f11a3c1df59f27b4323189e06ae6099d7310dac3fc7ad35a"
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_current_rgcn_artifact_has_expected_bytes_config_and_metrics():
    raw = ARCHITECTURE.read_bytes()
    assert len(raw) == 549_896
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_ARCHITECTURE_SHA256

    artifact = json.loads(raw)
    bakeoff.validate_artifact(artifact)
    assert {
        "schema_version": artifact["schema_version"],
        "artifact_kind": artifact["artifact_kind"],
        "corpus": artifact["corpus"],
        "substrate": artifact["substrate"],
        "seeds": artifact["seeds"],
        "epochs": artifact["epochs"],
        "train_bucket": artifact["train_bucket"],
        "ks": artifact["ks"],
        "daily_ks": artifact["daily_ks"],
        "pool_size": artifact["pool_size"],
        "hidden_total": artifact["hidden_total"],
        "stratum_hidden": artifact["stratum_hidden"],
        "architecture_order": artifact["architecture_order"],
    } == {
        "schema_version": 1,
        "artifact_kind": "gnn_architecture_comparison",
        "corpus": "synthetic_cbp_graph_corpus_v9",
        "substrate": "oracle",
        "seeds": [0, 1, 2],
        "epochs": 18,
        "train_bucket": "Q",
        "ks": [50, 100, 200, 500, 1000, 2000, 5000],
        "daily_ks": [5, 10, 25, 50],
        "pool_size": 40_578,
        "hidden_total": 2_691,
        "stratum_hidden": {"observable": 708, "dark": 234, "lone": 1749},
        "architecture_order": ["sage", "rgcn", "gat", "gin", "kpiaa"],
    }

    rgcn = artifact["architectures"]["rgcn"]["ensemble"]
    assert {
        key: rgcn["overall"][key]
        for key in (
            "found@500", "recall@500", "found@2000", "recall@2000",
            "found@5000", "recall@5000",
        )
    } == {
        "found@500": 144,
        "recall@500": 0.0535,
        "found@2000": 538,
        "recall@2000": 0.1999,
        "found@5000": 1030,
        "recall@5000": 0.3828,
    }
    assert {
        key: rgcn["stratified"]["observable"][key]
        for key in (
            "hidden", "found@500", "recall@500", "found@2000",
            "recall@2000", "found@5000", "recall@5000",
        )
    } == {
        "hidden": 708,
        "found@500": 111,
        "recall@500": 0.1568,
        "found@2000": 407,
        "recall@2000": 0.5749,
        "found@5000": 700,
        "recall@5000": 0.9887,
    }
    assert {
        key: rgcn["daily"][key]
        for key in (
            "daily_found@25", "daily_precision@25", "daily_recall@25",
            "daily_f1@25", "daily_budget@25",
        )
    } == {
        "daily_found@25": 1129,
        "daily_precision@25": 0.1654,
        "daily_recall@25": 0.4195,
        "daily_f1@25": 0.2373,
        "daily_budget@25": 6825,
    }


def test_current_rgcn_and_baseline_artifacts_share_only_declared_substrate_fields():
    architecture = _read_json(ARCHITECTURE)
    demo = _read_json(DEMO)
    assert {
        "corpus": architecture["corpus"],
        "pool_size": architecture["pool_size"],
        "hidden_total": architecture["hidden_total"],
        "seeds": architecture["seeds"],
        "epochs": architecture["epochs"],
        "train_bucket": architecture["train_bucket"],
    } == {
        "corpus": demo["corpus"],
        "pool_size": demo["pool_size"],
        "hidden_total": demo["hidden_total"],
        "seeds": demo["gnn_seeds"],
        "epochs": demo["epochs"],
        "train_bucket": demo["train_bucket"],
    }
    assert {
        key: demo["overall"]["baseline"][key]
        for key in ("recall@500", "recall@2000", "recall@5000")
    } == {
        "recall@500": 0.0149,
        "recall@2000": 0.071,
        "recall@5000": 0.1557,
    }


def test_current_rgcn_artifact_is_explicitly_unignored():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "!gnn/diagnostics/gnn_architecture_comparison_v9.json" in ignore
```

- [x] **Step 2: Run the tests and verify the expected red state**

Run:

```bash
rtk env PYTHONDONTWRITEBYTECODE=1 /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_v9_release_provenance.py
```

Expected: FAIL because the architecture artifact does not exist in the feature worktree and its unignore rule is absent.

- [x] **Step 3: Copy and verify the exact artifact bytes**

Run these as separate commands:

```bash
rtk shasum -a 256 /Users/edward/Desktop/GNN_Community_Detection/gnn/diagnostics/gnn_architecture_comparison_v9.json
rtk cp /Users/edward/Desktop/GNN_Community_Detection/gnn/diagnostics/gnn_architecture_comparison_v9.json /Users/edward/.config/superpowers/worktrees/GNN_Community_Detection/reorganize-repo/gnn/diagnostics/gnn_architecture_comparison_v9.json
rtk shasum -a 256 gnn/diagnostics/gnn_architecture_comparison_v9.json
rtk stat -f '%z' gnn/diagnostics/gnn_architecture_comparison_v9.json
```

Expected: both SHA-256 outputs equal `d4b5d349532ca949f11a3c1df59f27b4323189e06ae6099d7310dac3fc7ad35a`; target size is `549896`.

- [x] **Step 4: Unignore only the selected artifact**

Change the diagnostics block in `.gitignore` to:

```gitignore
gnn/diagnostics/*
!gnn/diagnostics/demo_comparison_v9.json
!gnn/diagnostics/gnn_architecture_comparison_v9.json
```

- [x] **Step 5: Run the release tests to green**

Run the Task 1 pytest command again.

Expected: `3 passed`.

- [x] **Step 6: Record a no-commit review checkpoint**

Run:

```bash
rtk git status --short --untracked-files=all
rtk git diff --check
```

Expected: the JSON and test are visible as untracked, `.gitignore` is modified, and no whitespace errors are reported.

### Task 2: Make the dashboard accept only the exact pinned legacy identity

**Files:**
- Modify: `tests/test_v9_dashboard_builder.py:1-25,1470-1660`
- Modify: `scripts/dashboard/build_v9_dashboard.py:1-55,430-575`

- [x] **Step 1: Add failing loader tests**

Add these tests beside the existing architecture loader tests:

```python
def test_loader_accepts_exact_pinned_architecture_with_legacy_corpus_identity():
    path = ROOT / "gnn/diagnostics/gnn_architecture_comparison_v9.json"
    artifact = json.loads(path.read_text(encoding="utf-8"))
    assert Path(artifact["corpus_identity"]).resolve() != Path(BUILDER.V9_CORPUS).resolve()

    loaded = BUILDER._load_v9_gnn_architecture_artifact(str(path))

    assert loaded == artifact


def test_loader_rejects_semantically_unchanged_reencoding_of_legacy_artifact(
    tmp_path, capsys
):
    source = ROOT / "gnn/diagnostics/gnn_architecture_comparison_v9.json"
    artifact = json.loads(source.read_text(encoding="utf-8"))
    rewritten = tmp_path / source.name
    rewritten.write_text(
        json.dumps(artifact, separators=(",", ":")), encoding="utf-8"
    )
    assert rewritten.read_bytes() != source.read_bytes()

    loaded = BUILDER._load_v9_gnn_architecture_artifact(str(rewritten))

    assert loaded is None
    assert "corpus_identity does not match V9 corpus" in capsys.readouterr().out
```

- [x] **Step 2: Run both tests and verify the expected red state**

Run:

```bash
rtk env PYTHONDONTWRITEBYTECODE=1 /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_v9_dashboard_builder.py::test_loader_accepts_exact_pinned_architecture_with_legacy_corpus_identity tests/test_v9_dashboard_builder.py::test_loader_rejects_semantically_unchanged_reencoding_of_legacy_artifact
```

Expected: the exact pinned artifact test FAILS because the current validator requires the organized corpus path; the re-encoded artifact remains rejected.

- [x] **Step 3: Add the SHA-bound compatibility path**

In `scripts/dashboard/build_v9_dashboard.py`, import `hashlib`, define:

```python
V9_GNN_ARCHITECTURE_RELEASE_SHA256 = (
    "d4b5d349532ca949f11a3c1df59f27b4323189e06ae6099d7310dac3fc7ad35a"
)
```

Change the validator signature and corpus identity check to:

```python
def _validate_v9_gnn_architecture_artifact(
    artifact, *, allow_pinned_legacy_corpus_identity=False
):
    """Validate the producer schema and an explicitly bounded corpus identity."""
    # Keep every existing validation statement unchanged above this check.
    identity = artifact["corpus_identity"]
    if not Path(identity).is_absolute() or str(Path(identity).resolve()) != identity:
        raise ValueError("corpus_identity must be an absolute normalized resolved path")
    if (
        os.path.realpath(identity) != os.path.realpath(V9_CORPUS)
        and not allow_pinned_legacy_corpus_identity
    ):
        raise ValueError("artifact corpus_identity does not match V9 corpus")
    # Keep the remaining schema/metric validation unchanged.
```

Load bytes once and bind the exception to their digest:

```python
def _load_v9_gnn_architecture_artifact(path):
    """Load the optional architecture artifact, warning and failing closed."""
    if not os.path.exists(path):
        p(f"[v9-dashboard] WARNING: GNN architecture comparison {path} not found.")
        return None
    try:
        raw = Path(path).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        artifact = json.loads(raw, object_pairs_hook=_reject_duplicate_json_keys)
        _validate_v9_gnn_architecture_artifact(
            artifact,
            allow_pinned_legacy_corpus_identity=(
                digest == V9_GNN_ARCHITECTURE_RELEASE_SHA256
            ),
        )
    except (
        OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError,
        TypeError, ValueError,
    ) as error:
        p(f"[v9-dashboard] WARNING: invalid GNN architecture comparison: {error}")
        return None
    return artifact
```

- [x] **Step 4: Run the loader tests to green, then the full builder contract**

Run:

```bash
rtk env PYTHONDONTWRITEBYTECODE=1 /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_v9_dashboard_builder.py
```

Expected: all builder tests pass; canonical-path synthetic artifacts remain accepted, incompatible artifacts remain rejected, and the two new tests pass.

- [x] **Step 5: Record a no-commit review checkpoint**

Run `rtk git diff --check` and inspect `rtk git diff -- scripts/dashboard/build_v9_dashboard.py tests/test_v9_dashboard_builder.py`.

### Task 3: Add independent leak-safe and cross-tree parity guards

**Files:**
- Modify: `tests/test_demo_baseline.py:1-24`
- Create: `tests/test_gnn_cross_tree_parity.py`

- [x] **Step 1: Add the independent baseline allowlist**

Add this test-owned constant and test to `tests/test_demo_baseline.py`:

```python
EXPECTED_GRAPH_FREE_BASELINE_FEATURES = [
    "prior_crossings", "prior_secondary", "prior_seizure", "prior_arrests",
    "hour", "age_bucket", "sex", "citizenship_country", "residence_country",
    "region", "mode_of_transportation", "travel_category",
    "declared_trip_purpose", "day_of_week",
]


def test_graph_free_baseline_has_an_independent_exact_feature_allowlist():
    assert FEATURE_NAMES == EXPECTED_GRAPH_FREE_BASELINE_FEATURES
```

This is a characterization guard for already-correct behavior, so its first run is expected to PASS rather than manufacture an artificial failure.

- [x] **Step 2: Add the fail-closed cross-tree parity contract**

Create `tests/test_gnn_cross_tree_parity.py`:

```python
"""Explicit active-versus-schema3 GNN executable parity boundary."""

from pathlib import Path

from scripts.data.compare_comment_only import _syntax_dump


ROOT = Path(__file__).resolve().parents[1]
ACTIVE = ROOT / "gnn"
BUNDLED = ROOT / "reproducibility/v9_observability_colab_schema3/gnn"
COMMON = {
    "__init__.py", "config.py", "demo_baseline.py", "demo_checkpoint.py",
    "detector.py", "explanation_narrative.py", "giant_observability_benchmark.py",
    "gnn_architecture_bakeoff.py", "graphmodel_alt.py", "graphmodel_rgcn.py",
    "learned_cell.py", "observability_artifact.py", "pu_learning.py",
    "recovery_bundle.py", "recovery_evidence_store.py",
    "recovery_observability.py", "run_demo.py", "sage_explainer.py",
    "unsupervised_ad.py", "unsupervised_features.py",
}
ACTIVE_ONLY = {"paths.py"}
INTENTIONAL_DIVERGENCES = {
    "config.py", "explanation_narrative.py", "giant_observability_benchmark.py",
    "gnn_architecture_bakeoff.py", "observability_artifact.py",
    "recovery_bundle.py", "recovery_evidence_store.py", "sage_explainer.py",
    "unsupervised_ad.py",
}


def _paths(package: Path) -> set[str]:
    return {path.relative_to(package).as_posix() for path in package.rglob("*.py")}


def test_active_and_bundled_gnn_module_inventory_is_explicit():
    active = _paths(ACTIVE)
    bundled = _paths(BUNDLED)
    assert active == COMMON | ACTIVE_ONLY
    assert bundled == COMMON
    assert active - bundled == ACTIVE_ONLY
    assert bundled - active == set()


def test_active_and_bundled_executable_divergences_are_explicit():
    differences = set()
    for relative in sorted(COMMON):
        active = ACTIVE / relative
        bundled = BUNDLED / relative
        active_dump = _syntax_dump(active.read_text(encoding="utf-8"), f"active/{relative}")
        bundled_dump = _syntax_dump(
            bundled.read_text(encoding="utf-8"), f"bundled/{relative}"
        )
        if active_dump != bundled_dump:
            differences.add(relative)
    assert differences == INTENTIONAL_DIVERGENCES
    assert COMMON - differences == COMMON - INTENTIONAL_DIVERGENCES
```

- [x] **Step 3: Run both guard files**

Run:

```bash
rtk env PYTHONDONTWRITEBYTECODE=1 /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_demo_baseline.py tests/test_gnn_cross_tree_parity.py
```

Expected: all tests pass. If parity differs, stop and classify the exact additional module rather than widening the allowlist reflexively.

- [x] **Step 4: Record a no-commit review checkpoint**

Run `rtk git diff --check` and inspect both test changes.

### Task 4: Publish current RGCN evidence and quarantine the historical run

**Files:**
- Modify: `tests/test_gnn_documentation.py:1-30,230-290`
- Modify: `docs/research/changes_3.md:1-275,491-545`
- Modify: `README.md:1-115,200-220`
- Modify: `docs/data/DATA_GUIDE.md:120-175,235-260`

- [x] **Step 1: Add the failing documentation contract**

Add this test to `tests/test_gnn_documentation.py`:

```python
def test_results_docs_publish_current_rgcn_and_preserve_historical_table():
    changes = (REPOSITORY_ROOT / "docs/research/changes_3.md").read_text(
        encoding="utf-8"
    )
    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
    guide = (REPOSITORY_ROOT / "docs/data/DATA_GUIDE.md").read_text(
        encoding="utf-8"
    )
    current_marker = "### Current artifact-backed RGCN result (40,578-row release)"
    historical_marker = (
        "### Historical RGCN-era result (38,948-row run; artifact unavailable)"
    )
    assert current_marker in changes
    assert historical_marker in changes
    assert changes.index(current_marker) < changes.index(historical_marker)
    current = changes.split(current_marker, 1)[1].split(historical_marker, 1)[0]
    for row in (
        "| 500 | 0.0149 | 144 | 0.0535 |",
        "| 2,000 | 0.0710 | 538 | 0.1999 |",
        "| 5,000 | 0.1557 | 1,030 | 0.3828 |",
    ):
        assert row in current
    assert "p=0" not in current
    for old_row in (
        "| 500  | 0.039 | 0.056 | +49  (p=0) |",
        "| 2000 | 0.091 | **0.261** | +455 (p=0) |",
        "| 5000 | 0.175 | **0.403** | +609 (p=0) |",
    ):
        assert old_row in changes
    for document in (readme, guide):
        assert "GraphSAGE remains the active runtime default" in document
        assert "frozen-artifact verifiable, not exactly retrainable" in document
        assert "38,948-row" in document and "historical" in document.lower()
```

- [x] **Step 2: Run the documentation test and verify the expected red state**

Run:

```bash
rtk env PYTHONDONTWRITEBYTECODE=1 /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_gnn_documentation.py::test_results_docs_publish_current_rgcn_and_preserve_historical_table
```

Expected: FAIL because the current/historical headings and onboarding evidence language are absent.

- [x] **Step 3: Update the research result log**

Immediately before the old full-scale result block, add:

```markdown
### Current artifact-backed RGCN result (40,578-row release)

GraphSAGE remains the active runtime default. The current RGCN measurements
come from the committed architecture-only artifact
`gnn/diagnostics/gnn_architecture_comparison_v9.json` (SHA-256
`d4b5d349532ca949f11a3c1df59f27b4323189e06ae6099d7310dac3fc7ad35a`).
It records the logical V9 corpus, 40,578 test events, 2,691 hidden events,
seeds 0/1/2, 18 epochs, quarterly training buckets, and oracle identity.

The Baseline reference below is read separately from the frozen
`demo_comparison_v9.json`; the two artifacts agree on those declared substrate
fields, but the architecture command did not execute or serialize a Baseline
arm. This is a cross-artifact comparison. The RGCN JSON contains no checkpoint,
score arrays, or paired bootstrap, so it is frozen-artifact verifiable, not
exactly retrainable, and no historical p-value is assigned to these rows.

| K | Baseline recall | RGCN found | RGCN recall |
| ---: | ---: | ---: | ---: |
| 500 | 0.0149 | 144 | 0.0535 |
| 2,000 | 0.0710 | 538 | 0.1999 |
| 5,000 | 0.1557 | 1,030 | 0.3828 |

On the 708-person observable slice, RGCN found 111, 407, and 700 at those
depths (recall 0.1568, 0.5749, and 0.9887). At 25 inspections/day it recorded
1,129 found, precision 0.1654, recall 0.4195, and F1 0.2373.

### Historical RGCN-era result (38,948-row run; artifact unavailable)

The following table and interpretation are preserved verbatim as historical
research evidence. No matching corpus fingerprint, result JSON, checkpoint,
score arrays, or complete invocation survived, so the values are not a current
reproducibility claim and must not be combined with the 40,578-row release.
```

Keep every old numeric row unchanged below the historical heading. Update the document's opening headline and the later architecture-bakeoff section to use the current RGCN artifact and remove the claim that it is ignored. Do not attach `p=0` or old paired-bootstrap conclusions to the new table.

- [x] **Step 4: Update onboarding and data-guide evidence status**

In both `README.md` and `docs/data/DATA_GUIDE.md`, include this exact sentence:

```markdown
GraphSAGE remains the active runtime default; the committed 40,578-row RGCN
architecture artifact is frozen-artifact verifiable, not exactly retrainable.
```

Name both committed diagnostics as exceptions to the generated/ignored tree. Replace the Data Guide's old current-result summary with the current three-row RGCN table, and state that the 38,948-row table remains under a historical heading in `changes_3.md`. Update the dashboard sparsity text so architecture data is no longer described as absent until locally regenerated.

- [x] **Step 5: Run documentation contracts to green**

Run:

```bash
rtk env PYTHONDONTWRITEBYTECODE=1 /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_gnn_documentation.py tests/test_v9_release_provenance.py
```

Expected: all tests pass.

- [x] **Step 6: Record a no-commit review checkpoint**

Run `rtk git diff --check`; inspect the three documentation diffs; explicitly verify the three old table rows are unchanged with `rtk rg -n '0\.039|0\.091|0\.175|0\.056|0\.261|0\.403' docs/research/changes_3.md`.

### Task 5: Rebuild and pin the architecture-backed dashboard

**Files:**
- Modify: `tests/test_v9_dashboard_builder.py:31-57`
- Modify: `artifacts/v9/dashboard/index.html` through the builder only

- [x] **Step 1: Add the failing committed-dashboard test**

Add beside `_committed_dashboard_data()`:

```python
def test_committed_dashboard_embeds_real_rgcn_architecture_artifact():
    artifact = json.loads(
        (ROOT / "gnn/diagnostics/gnn_architecture_comparison_v9.json").read_text(
            encoding="utf-8"
        )
    )
    embedded = _committed_dashboard_data()["v9GNNArchitectureComparison"]
    assert embedded == artifact
    rgcn = embedded["architectures"]["rgcn"]["ensemble"]
    assert rgcn["overall"]["found@500"] == 144
    assert rgcn["overall"]["recall@2000"] == 0.1999
    assert rgcn["daily"]["daily_found@25"] == 1129
```

- [x] **Step 2: Run the test and verify the expected red state**

Run:

```bash
rtk env PYTHONDONTWRITEBYTECODE=1 /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_v9_dashboard_builder.py::test_committed_dashboard_embeds_real_rgcn_architecture_artifact
```

Expected: FAIL because the committed dashboard predates the architecture payload.

- [x] **Step 3: Rebuild only through the dashboard builder**

Run:

```bash
rtk env PYTHONDONTWRITEBYTECODE=1 /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m scripts.dashboard.build_v9_dashboard
```

Expected: the builder loads the pinned architecture artifact without an architecture warning and rewrites `artifacts/v9/dashboard/index.html`; sidecars remain ignored.

- [x] **Step 4: Run the complete dashboard contract**

Run:

```bash
rtk env PYTHONDONTWRITEBYTECODE=1 /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_v9_dashboard_builder.py tests/test_v9_design_system.py tests/test_v9_summary_page.py
```

Expected: all tests pass, including the real committed artifact assertion.

- [x] **Step 5: Verify a temporary rebuild is byte-identical**

Use a `/private/tmp` `TemporaryDirectory`, call `scripts.dashboard.build_v9_dashboard._build_staged_dashboard`, assert its generated `index.html` bytes equal the committed index, assert generated `data_v9.json["v9GNNArchitectureComparison"]` equals the committed JSON artifact, then allow the context manager to remove the entire generated tree. Record the generated file count/bytes and SHA-256 in `tasks/plan.md` before final audit-plan removal.

- [x] **Step 6: Record a no-commit review checkpoint**

Run `rtk git diff --check` and `rtk git status --short --untracked-files=all`. Confirm only intended tracked/untracked paths appear and generated sidecars are ignored.

### Task 6: Finalize durable handoff, remove the temporary audit record, and verify

**Files:**
- Modify: `PROJECT_MEMORY.md`
- Delete: `tasks/plan.md`
- Remove empty directory: `tasks/`

- [x] **Step 1: Record the durable decision in project memory**

Append a concise dated entry recording:

```markdown
- GraphSAGE remains the active V9 runtime default.
- Current RGCN measurements are sourced from the committed 40,578-row
  `gnn_architecture_comparison_v9.json`, pinned by SHA-256; they are
  frozen-artifact verifiable but not exactly retrainable because no RGCN
  checkpoint/score arrays survive.
- Baseline/RGCN comparisons are cross-artifact and share only the explicitly
  tested logical corpus, pool/hidden denominators, seeds, epochs, and bucket.
- The older 38,948-row RGCN-era table remains historical and unrecoverable; do
  not transfer its bootstrap significance to the current release.
- The dashboard accepts the artifact's legacy absolute corpus identity only
  when the full file matches the pinned release digest.
- Active and bundled GNN trees have 11 executable-AST-identical core modules,
  nine explicitly classified divergences, and active-only `paths.py`; the old
  project-memory phrase "documentation-only proof" referred to within-tree
  code preservation and must not be read as cross-tree equivalence.
```

- [x] **Step 2: Run focused scientific and provenance verification**

Run:

```bash
rtk env PYTHONDONTWRITEBYTECODE=1 /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_v9_release_provenance.py tests/test_demo_baseline.py tests/test_gnn_cross_tree_parity.py tests/test_gnn_architecture_bakeoff.py tests/test_gnn_documentation.py tests/test_v9_dashboard_builder.py
rtk env PYTHONDONTWRITEBYTECODE=1 /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m scripts.data.validate_corpus tests/fixtures/v9dev
rtk env PYTHONDONTWRITEBYTECODE=1 /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m scripts.data.validate_corpus reproducibility/v9_observability_colab_schema3/corpus/synthetic_cbp_graph_corpus_v9
rtk git lfs fsck
rtk env PYTHONDONTWRITEBYTECODE=1 /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m scripts.data.v9_assets verify-explanations
```

Expected: all focused tests and validators pass, LFS fsck is clean, and the
explanation archive verifies with its existing degraded 19-of-20 coverage
limitation unchanged. The project-layout suite is intentionally deferred until
Step 5 because the audit still owns `tasks/plan.md` at this point.

- [x] **Step 3: Verify the bundled schema-3 package**

From `reproducibility/v9_observability_colab_schema3`, run:

```bash
rtk env PYTHONDONTWRITEBYTECODE=1 /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest tests -q -p no:cacheprovider
```

Expected: the bundled suite passes and imports its local bundled `gnn` package.

- [x] **Step 4: Remove the temporary audit plan before the layout/full-suite gate**

After confirming every durable finding is represented in the spec, implementation plan, active docs, tests, and project memory, delete `tasks/plan.md` with `apply_patch` and remove the now-empty `tasks/` directory with `rtk rmdir tasks`. Do not remove any user-owned file.

- [x] **Step 5: Run the complete root suite fresh**

Run:

```bash
rtk env PYTHONDONTWRITEBYTECODE=1 /Users/edward/Desktop/GNN_Community_Detection/.venv/bin/python -m pytest -q -p no:cacheprovider
```

Expected: zero failures. Treat the previously observed 180-second observability child-process test as a performance risk; if it times out only under suite load, capture the full evidence and rerun that exact node in isolation before classifying it.

- [x] **Step 6: Run final integrity and scope checks**

Run as separate commands:

```bash
rtk shasum -a 256 gnn/diagnostics/gnn_architecture_comparison_v9.json
rtk git diff --check
rtk git status --short --untracked-files=all
rtk git diff --stat
```

Expected: the artifact digest is the pinned `d4b5d349...ad35a`, no whitespace errors exist, `tasks/` is absent, and only intended feature-worktree changes are present.

- [x] **Step 7: Request independent specification and quality review**

Ask a reviewer to verify: exact artifact bytes/metrics, hash-bound identity exception, no significance transfer, preservation of all historical rows, GraphSAGE default, dashboard equality, baseline allowlist independence, cross-tree allowlist exactness, test evidence, and no changes to main/model/corpus/checkpoint/explanation assets. Resolve every Critical or Important finding and rerun affected verification before reporting completion.
