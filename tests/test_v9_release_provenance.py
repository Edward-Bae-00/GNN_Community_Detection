"""Release provenance contracts for the V9 architecture comparison evidence."""

import hashlib
import json
from pathlib import Path
import subprocess

import gnn.gnn_architecture_bakeoff as bakeoff


ROOT = Path(__file__).parents[1]
ARCHITECTURE_ARTIFACT = ROOT / "gnn/diagnostics/gnn_architecture_comparison_v9.json"
DEMO_ARTIFACT = ROOT / "gnn/diagnostics/demo_comparison_v9.json"


def _load_json(path):
    return json.loads(path.read_bytes())


def test_v9_architecture_artifact_is_exact_validated_evidence():
    raw = ARCHITECTURE_ARTIFACT.read_bytes()
    assert len(raw) == 549896
    assert hashlib.sha256(raw).hexdigest() == (
        "d4b5d349532ca949f11a3c1df59f27b4323189e06ae6099d7310dac3fc7ad35a"
    )

    artifact = _load_json(ARCHITECTURE_ARTIFACT)
    bakeoff.validate_artifact(artifact)

    assert artifact["schema_version"] == 1
    assert artifact["artifact_kind"] == "gnn_architecture_comparison"
    assert artifact["corpus"] == "synthetic_cbp_graph_corpus_v9"
    assert artifact["substrate"] == "oracle"
    assert artifact["seeds"] == [0, 1, 2]
    assert artifact["epochs"] == 18
    assert artifact["train_bucket"] == "Q"
    assert artifact["ks"] == [50, 100, 200, 500, 1000, 2000, 5000]
    assert artifact["daily_ks"] == [5, 10, 25, 50]
    assert artifact["pool_size"] == 40578
    assert artifact["hidden_total"] == 2691
    assert artifact["stratum_hidden"] == {
        "observable": 708,
        "dark": 234,
        "lone": 1749,
    }
    assert artifact["architecture_order"] == ["sage", "rgcn", "gat", "gin", "kpiaa"]

    rgcn = artifact["architectures"]["rgcn"]["ensemble"]
    assert {
        k: (rgcn["overall"][f"found@{k}"], rgcn["overall"][f"recall@{k}"])
        for k in (500, 2000, 5000)
    } == {
        500: (144, 0.0535),
        2000: (538, 0.1999),
        5000: (1030, 0.3828),
    }
    assert rgcn["stratified"]["observable"]["hidden"] == 708
    assert {
        k: (
            rgcn["stratified"]["observable"][f"found@{k}"],
            rgcn["stratified"]["observable"][f"recall@{k}"],
        )
        for k in (500, 2000, 5000)
    } == {
        500: (111, 0.1568),
        2000: (407, 0.5749),
        5000: (700, 0.9887),
    }
    assert {
        key: rgcn["daily"][f"daily_{key}@25"]
        for key in ("found", "precision", "recall", "f1", "budget")
    } == {
        "found": 1129,
        "precision": 0.1654,
        "recall": 0.4195,
        "f1": 0.2373,
        "budget": 6825,
    }


def test_v9_architecture_and_demo_artifacts_share_logical_contract():
    architecture = _load_json(ARCHITECTURE_ARTIFACT)
    demo = _load_json(DEMO_ARTIFACT)

    assert architecture["corpus"] == demo["corpus"]
    assert architecture["pool_size"] == demo["pool_size"]
    assert architecture["hidden_total"] == demo["hidden_total"]
    assert architecture["stratum_hidden"] == demo["stratum_hidden"] == {
        "observable": 708,
        "dark": 234,
        "lone": 1749,
    }
    assert architecture["seeds"] == demo["gnn_seeds"]
    assert architecture["substrate"] == demo["substrate"] == "oracle"
    assert architecture["epochs"] == demo["epochs"]
    assert architecture["train_bucket"] == demo["train_bucket"]

    baseline = demo["overall"]["baseline"]
    assert baseline["recall@500"] == 0.0149
    assert baseline["recall@2000"] == 0.071
    assert baseline["recall@5000"] == 0.1557


def test_v9_architecture_artifact_is_explicitly_unignored():
    exception = "!gnn/diagnostics/gnn_architecture_comparison_v9.json"
    active_lines = [
        line.strip()
        for line in (ROOT / ".gitignore").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert active_lines.count(exception) == 1

    result = subprocess.run(
        [
            "git",
            "check-ignore",
            "--no-index",
            "-q",
            "gnn/diagnostics/gnn_architecture_comparison_v9.json",
        ],
        cwd=ROOT,
        check=False,
    )
    assert result.returncode == 1


def test_v9_architecture_artifact_has_pinned_lf_attributes():
    rule = "/gnn/diagnostics/gnn_architecture_comparison_v9.json text eol=lf"
    active_lines = [
        line.strip()
        for line in (ROOT / ".gitattributes").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert active_lines.count(rule) == 1

    result = subprocess.run(
        [
            "git",
            "check-attr",
            "text",
            "eol",
            "--",
            "gnn/diagnostics/gnn_architecture_comparison_v9.json",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "text: set" in result.stdout
    assert "eol: lf" in result.stdout


def test_published_release_settings_match_the_frozen_artifacts():
    from gnn.run_demo import PUBLISHED_RELEASE

    demo = _load_json(DEMO_ARTIFACT)
    architecture = _load_json(ARCHITECTURE_ARTIFACT)

    assert PUBLISHED_RELEASE == {
        "seeds": (0, 1, 2),
        "epochs": 18,
        "train_bucket": "Q",
        "gnn_arm": "sage",
        "valid_sample": 20000,
    }
    assert list(PUBLISHED_RELEASE["seeds"]) == demo["gnn_seeds"] == architecture["seeds"]
    assert PUBLISHED_RELEASE["epochs"] == demo["epochs"] == architecture["epochs"]
    assert (
        PUBLISHED_RELEASE["train_bucket"]
        == demo["train_bucket"]
        == architecture["train_bucket"]
    )
    assert PUBLISHED_RELEASE["gnn_arm"] == demo["gnn_arm"]


def test_release_subcommand_runs_the_published_settings_not_the_defaults():
    import inspect

    from gnn import run_demo

    defaults = {
        name: parameter.default
        for name, parameter in inspect.signature(run_demo.main).parameters.items()
    }
    # The experimental defaults must stay where they are.
    assert defaults["epochs"] == 30
    assert defaults["train_bucket"] == "M"

    captured = {}
    original = run_demo.main
    run_demo.main = lambda **kwargs: captured.update(kwargs)
    try:
        run_demo._cli(["release"])
    finally:
        run_demo.main = original

    assert {k: captured[k] for k in run_demo.PUBLISHED_RELEASE} == dict(
        run_demo.PUBLISHED_RELEASE
    )


def test_release_never_overwrites_the_committed_frozen_diagnostic():
    from gnn import run_demo

    captured = {}
    original = run_demo.main
    run_demo.main = lambda **kwargs: captured.update(kwargs)
    try:
        run_demo._cli(["release"])
    finally:
        run_demo.main = original

    # The frozen diagnostic is tracked; a verification run must not clobber it.
    assert captured["out_name"] == run_demo.RELEASE_OUT_NAME
    assert captured["out_name"] != DEMO_ARTIFACT.name
    assert run_demo.RELEASE_OUT_NAME != DEMO_ARTIFACT.name

    # And the default output must not be a tracked file.
    result = subprocess.run(
        ["git", "check-ignore", "-q", f"gnn/diagnostics/{run_demo.RELEASE_OUT_NAME}"],
        cwd=ROOT,
        check=False,
    )
    assert result.returncode == 0, "release output must land on an ignored path"


def test_release_out_name_is_overridable():
    from gnn import run_demo

    captured = {}
    original = run_demo.main
    run_demo.main = lambda **kwargs: captured.update(kwargs)
    try:
        run_demo._cli(["release", "--out-name", "custom_run.json"])
    finally:
        run_demo.main = original

    assert captured["out_name"] == "custom_run.json"
