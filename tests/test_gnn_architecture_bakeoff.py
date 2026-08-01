"""Tests for the standalone GNN architecture bake-off artifact contract."""

from pathlib import Path
import copy
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import gnn.gnn_architecture_bakeoff as bakeoff


def _pool():
    return pd.DataFrame(
        {
            "event_id": ["e0", "e1", "e2", "e3"],
            "primary_person_id": ["p0", "p1", "p2", "p3"],
            "primary_obs_id": ["o0", "o1", "o2", "o3"],
            "t": pd.to_datetime(
                [
                    "2025-01-01T01:00:00Z",
                    "2025-01-01T02:00:00Z",
                    "2025-01-02T01:00:00Z",
                    "2025-01-02T02:00:00Z",
                ]
            ),
            "hidden": [True, False, True, False],
        }
    )


def _fake_score_bundle(seeds, n):
    return SimpleNamespace(
        scores_by_seed={
            int(seed): (np.arange(n, dtype=float) + float(seed),)
            for seed in seeds
        }
    )


def _fake_prep(monkeypatch):
    pool = _pool()
    strata = pd.Series(["observable", "dark", "lone", "observable"])
    calls = {"split": 0, "oracle": 0, "pool": 0, "strata": 0, "train": 0,
             "graph": 0, "caught": 0, "identity": 0}
    loaded_pool = {"value": None}

    def split(_):
        calls["split"] += 1
        return pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2025-01-01", tz="UTC")

    def oracle(_):
        calls["oracle"] += 1
        return {f"o{i}": f"p{i}" for i in range(4)}

    def load(_, split="test"):
        calls["pool"] += 1
        loaded_pool["value"] = pool.copy()
        return loaded_pool["value"]

    def strata_for_pool(*_):
        calls["strata"] += 1
        return strata.copy()

    def train(*_):
        calls["train"] += 1
        return pool.iloc[:1].copy(), np.array([1])

    def graph(*_, **__):
        calls["graph"] += 1
        return pd.DataFrame(columns=["u", "v", "avail_time", "rel"]), [f"p{i}" for i in range(4)], {
            f"p{i}": np.array([1.0]) for i in range(4)
        }

    def caught(*_):
        calls["caught"] += 1
        return {}

    def identities(*_, **__):
        calls["identity"] += 1

    monkeypatch.setattr(bakeoff, "_split_label_cutoffs", split)
    monkeypatch.setattr(bakeoff, "_build_oracle", oracle)
    monkeypatch.setattr(bakeoff, "load_pool", load)
    monkeypatch.setattr(bakeoff, "stratum_for_pool", strata_for_pool)
    monkeypatch.setattr(bakeoff, "_train_pool_and_labels", train)
    monkeypatch.setattr(bakeoff, "build_person_graph_typed", graph)
    monkeypatch.setattr(bakeoff, "build_caught_times", caught)
    monkeypatch.setattr(bakeoff, "validate_pool_identities", identities)
    return calls, pool, loaded_pool


def _valid_artifact(monkeypatch, tmp_path):
    _fake_prep(monkeypatch)
    sentinel = type("Sentinel_sage", (), {})
    monkeypatch.setattr(
        bakeoff,
        "GNN_ARMS",
        {"sage": {"cls": sentinel, "num_rel": 4, "label": "SAGE", "looks_for": "x"}},
    )
    monkeypatch.setattr(
        bakeoff,
        "_gnn_scores",
        lambda *args, **kwargs: _fake_score_bundle(kwargs["seeds"], 4),
    )
    return bakeoff.run_bakeoff(
        corpus_dir=tmp_path, output=tmp_path / "artifact.json", ks=(1,), daily_ks=(1,)
    )


def test_registry_only_schema_and_shared_preparation(monkeypatch, tmp_path):
    calls, pool, loaded_pool = _fake_prep(monkeypatch)
    score_calls = []
    score_context = []
    sentinel_classes = {
        name: type(f"Sentinel_{name}", (), {})
        for name in bakeoff.GNN_ARMS
    }

    def score(*args, **kwargs):
        score_calls.append(kwargs["model_cls"])
        score_context.append(
            (args[0], args[6], kwargs["seeds"], kwargs["epochs"], kwargs["train_bucket"])
        )
        return _fake_score_bundle(kwargs["seeds"], len(pool))

    monkeypatch.setattr(bakeoff, "_gnn_scores", score)
    monkeypatch.setattr(
        bakeoff,
        "GNN_ARMS",
        {name: {**spec, "cls": sentinel_classes[name]} for name, spec in bakeoff.GNN_ARMS.items()},
    )
    payload = bakeoff.run_bakeoff(
        corpus_dir=tmp_path,
        output=tmp_path / "artifact.json",
        ks=(1, 2),
        daily_ks=(1,),
    )

    assert payload["architecture_order"] == list(bakeoff.GNN_ARMS)
    assert list(payload["architectures"]) == list(bakeoff.GNN_ARMS)
    assert not any("baseline" in key.lower() or "hybrid" in key.lower()
                   for key in payload)
    assert calls == {"split": 1, "oracle": 1, "pool": 1, "strata": 1, "train": 1,
                     "graph": 1, "caught": 1, "identity": 2}
    assert score_calls == [sentinel_classes[name] for name in bakeoff.GNN_ARMS]
    assert all(context[0] is score_context[0][0] for context in score_context)
    assert all(len(context[1]) == 1 and context[1][0] is loaded_pool["value"]
               for context in score_context)
    assert all(context[2] == (0, 1, 2) and context[3] == 18 and context[4] == "Q"
               for context in score_context)
    bakeoff.validate_artifact(payload)


def test_ensemble_and_per_seed_metrics_are_aggregated(monkeypatch, tmp_path):
    _fake_prep(monkeypatch)
    monkeypatch.setattr(
        bakeoff,
        "GNN_ARMS",
        {"sage": {"cls": object, "num_rel": 4, "label": "SAGE", "looks_for": "x"}},
    )
    original_tiebreak = bakeoff._rd.add_tiebreak
    tiebreak_inputs = []
    tiebreak_outputs = []

    def record_tiebreak(scores, pool):
        tiebreak_inputs.append(np.array(scores, copy=True))
        output = original_tiebreak(scores, pool)
        tiebreak_outputs.append(np.array(output, copy=True))
        return output

    monkeypatch.setattr(bakeoff._rd, "add_tiebreak", record_tiebreak)
    monkeypatch.setattr(
        bakeoff,
        "_gnn_scores",
        lambda *args, **kwargs: SimpleNamespace(
            scores_by_seed={0: (np.array([.1, .2, .3, .4]),),
                            1: (np.array([.9, .2, .3, .4]),),
                            2: (np.array([.1, .2, .8, .4]),)}
        ),
    )
    payload = bakeoff.run_bakeoff(
        corpus_dir=tmp_path, output=tmp_path / "artifact.json", ks=(1,), daily_ks=(1,)
    )
    row = payload["architectures"]["sage"]
    expected_raw = np.mean(np.column_stack([
        np.array([.1, .2, .3, .4]), np.array([.9, .2, .3, .4]),
        np.array([.1, .2, .8, .4]),
    ]), axis=1)
    np.testing.assert_allclose(tiebreak_inputs[0], expected_raw)
    np.testing.assert_allclose(
        tiebreak_outputs[0], original_tiebreak(expected_raw, _pool())
    )
    assert set(row["per_seed"]) == {"0", "1", "2"}
    assert "daily" in row["ensemble"]
    assert "daily" not in row["per_seed"]["0"]
    assert row["ensemble"]["overall"]["found@1"] == 1


def test_validate_artifact_rejects_strict_contract_failures():
    payload = {
        "schema_version": 1,
        "artifact_kind": "gnn_architecture_comparison",
        "corpus": "toy",
        "corpus_identity": str(Path("/tmp/toy").resolve()),
        "substrate": "oracle",
        "seeds": [0, 1, 2],
        "epochs": 18,
        "train_bucket": "Q",
        "ks": [1],
        "daily_ks": [1],
        "pool_size": 1,
        "hidden_total": 1,
        "stratum_hidden": {"observable": 1, "dark": 0, "lone": 0},
        "feature_schema": list(bakeoff.caught_feature_names(bakeoff.NUM_REL_PLATE)),
        "relation_schema": {str(name): int(value) for name, value in bakeoff.REL_PLATE.items()},
        "architecture_order": ["sage"],
        "architectures": {},
    }
    with pytest.raises(ValueError, match="registry"):
        bakeoff.validate_artifact(payload)

    bad = dict(payload)
    bad["architecture_order"] = list(bakeoff.GNN_ARMS)
    bad["architectures"] = {name: {} for name in bakeoff.GNN_ARMS}
    bad["seeds"] = [0, 0, 1]
    with pytest.raises(ValueError, match="duplicate"):
        bakeoff.validate_artifact(bad)

    bad = dict(payload)
    bad["forbidden_baseline"] = {"nested": {"hybrid": 1}}
    with pytest.raises(ValueError, match="forbidden"):
        bakeoff.validate_artifact(bad)


def test_validate_artifact_rejects_numeric_schema_and_metric_corruption(monkeypatch, tmp_path):
    payload = _valid_artifact(monkeypatch, tmp_path)

    bad = copy.deepcopy(payload)
    bad["architectures"]["sage"]["ensemble"]["overall"]["precision@1"] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        bakeoff.validate_artifact(bad)

    bad = copy.deepcopy(payload)
    bad["architectures"]["sage"]["ensemble"]["overall"]["found@1"] = True
    with pytest.raises(ValueError, match="boolean"):
        bakeoff.validate_artifact(bad)

    bad = copy.deepcopy(payload)
    bad["stratum_hidden"]["dark"] += 1
    with pytest.raises(ValueError, match="sum"):
        bakeoff.validate_artifact(bad)

    bad = copy.deepcopy(payload)
    bad["architectures"]["sage"]["label"] = "wrong"
    with pytest.raises(ValueError, match="registry"):
        bakeoff.validate_artifact(bad)

    bad = copy.deepcopy(payload)
    bad["architectures"]["sage"]["per_seed"].pop("0")
    with pytest.raises(ValueError, match="keys"):
        bakeoff.validate_artifact(bad)

    bad = copy.deepcopy(payload)
    bad["architectures"]["sage"]["unexpected"] = 1
    with pytest.raises(ValueError, match="unexpected"):
        bakeoff.validate_artifact(bad)

    bad = copy.deepcopy(payload)
    bad["architectures"]["sage"]["ensemble"]["event_scores"] = {}
    with pytest.raises(ValueError, match="forbidden"):
        bakeoff.validate_artifact(bad)

    bad = copy.deepcopy(payload)
    bad["architectures"]["sage"]["ensemble"]["overall"].pop("f1@1")
    with pytest.raises(ValueError, match="missing|required|invalid"):
        bakeoff.validate_artifact(bad)

    bad = copy.deepcopy(payload)
    bad["architectures"]["sage"]["ensemble"]["daily"]["daily_found_by_day@1"][0]["found"] += 1
    with pytest.raises(ValueError, match="sum"):
        bakeoff.validate_artifact(bad)

    bad = copy.deepcopy(payload)
    bad["architectures"]["sage"]["ensemble"]["daily"]["daily_budget@1"] = 100
    with pytest.raises(ValueError, match="daily denominator"):
        bakeoff.validate_artifact(bad)

    bad = copy.deepcopy(payload)
    bad["architectures"]["sage"]["ensemble"]["daily"]["daily_found_by_day@1"][0]["found"] = 2
    with pytest.raises(ValueError, match="quota"):
        bakeoff.validate_artifact(bad)

    bad = copy.deepcopy(payload)
    rows = bad["architectures"]["sage"]["ensemble"]["daily"]["daily_found_by_day@1"]
    rows[1]["date"] = rows[0]["date"]
    with pytest.raises(ValueError, match="duplicate"):
        bakeoff.validate_artifact(bad)

    bad = copy.deepcopy(payload)
    bad["substrate"] = "er"
    with pytest.raises(ValueError, match="substrate"):
        bakeoff.validate_artifact(bad)

    bad = copy.deepcopy(payload)
    bad["corpus_identity"] = "relative/path"
    with pytest.raises(ValueError, match="corpus_identity"):
        bakeoff.validate_artifact(bad)

    bad = copy.deepcopy(payload)
    bad["corpus_identity"] = "/tmp/../tmp/toy"
    with pytest.raises(ValueError, match="corpus_identity"):
        bakeoff.validate_artifact(bad)


def test_global_and_daily_f1_rounding_rules_are_distinct():
    global_metrics = {
        "found@6": 1,
        "precision@6": 0.1667,
        "recall@6": 0.1429,
        "f1@6": 0.1539,
    }
    assert bakeoff._validate_global_metrics(
        global_metrics, (6,), hidden_total=7, pool_size=7, path="global"
    ) == {6: 1}

    daily_metrics = {
        "n_days": 1,
        "daily_found@6": 1,
        "daily_found_by_day@6": [{"date": "2025-01-01", "found": 1}],
        "daily_recall@6": 0.1429,
        "daily_precision@6": 0.1667,
        "daily_f1@6": 0.1538,
        "daily_budget@6": 6,
    }
    bakeoff._validate_daily_metrics(
        daily_metrics, (6,), hidden_total=7, pool_size=7, path="daily"
    )
    bad_daily = dict(daily_metrics)
    bad_daily["daily_f1@6"] = 0.1539
    with pytest.raises(ValueError, match="inconsistent daily"):
        bakeoff._validate_daily_metrics(
            bad_daily, (6,), hidden_total=7, pool_size=7, path="daily"
        )


def test_exact_keys_rejects_heterogeneous_programmatic_keys():
    with pytest.raises(ValueError, match="invalid fields"):
        bakeoff._exact_keys({"expected": 1, 2: "unexpected"}, {"expected"}, "mixed")


def test_architecture_failure_does_not_publish_partial_output(monkeypatch, tmp_path):
    _fake_prep(monkeypatch)
    sage_cls = type("Sentinel_sage", (), {})
    rgcn_cls = type("Sentinel_rgcn", (), {})
    monkeypatch.setattr(
        bakeoff,
        "GNN_ARMS",
        {"sage": {"cls": sage_cls, "num_rel": 4, "label": "SAGE", "looks_for": "x"},
         "rgcn": {"cls": rgcn_cls, "num_rel": 4, "label": "RGCN", "looks_for": "x"}},
    )
    output = tmp_path / "artifact.json"
    output.write_text("prior")

    def fail(*args, **kwargs):
        if kwargs["model_cls"] is bakeoff.GNN_ARMS["rgcn"]["cls"]:
            raise ValueError("boom")
        return _fake_score_bundle(kwargs["seeds"], 4)

    monkeypatch.setattr(bakeoff, "_gnn_scores", fail)
    with pytest.raises(RuntimeError, match="rgcn"):
        bakeoff.run_bakeoff(corpus_dir=tmp_path, output=output, ks=(1,), daily_ks=(1,))
    assert output.read_text() == "prior"


def test_gnn_only_workflow_never_calls_demo_other_helpers(monkeypatch, tmp_path):
    _fake_prep(monkeypatch)
    monkeypatch.setattr(
        bakeoff,
        "GNN_ARMS",
        {"sage": {"cls": object, "num_rel": 4, "label": "SAGE", "looks_for": "x"}},
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("non-GNN demo helper was called")

    for helper in (
        "main", "build_baseline_features", "fit_predict", "_pick_fusion_weight",
        "_rank_fuse", "paired_event_bootstrap", "write_demo_checkpoint",
        "build_observability_bundle",
    ):
        if hasattr(bakeoff._rd, helper):
            monkeypatch.setattr(bakeoff._rd, helper, forbidden)
    monkeypatch.setattr(
        bakeoff,
        "_gnn_scores",
        lambda *args, **kwargs: _fake_score_bundle(kwargs["seeds"], 4),
    )
    bakeoff.run_bakeoff(
        corpus_dir=tmp_path, output=tmp_path / "artifact.json", ks=(1,), daily_ks=(1,)
    )


def test_main_invokes_bakeoff_and_reports_configuration(monkeypatch, tmp_path):
    calls = {}
    output = tmp_path / "custom.json"

    def fake_run(**kwargs):
        calls.update(kwargs)
        return {
            "architecture_order": ["sage"],
            "seeds": [0, 1, 2],
            "epochs": 18,
            "train_bucket": "Q",
        }

    printed = []
    monkeypatch.setattr(bakeoff, "run_bakeoff", fake_run)
    monkeypatch.setattr("builtins.print", lambda message: printed.append(message))
    result = bakeoff.main([
        "--corpus", str(tmp_path), "--output", str(output), "--seeds", "0", "1", "2",
    ])
    assert result["architecture_order"] == ["sage"]
    assert calls["corpus_dir"] == str(tmp_path)
    assert calls["output"] == str(output)
    assert calls["seeds"] == [0, 1, 2]
    assert printed and str(output) in printed[0]


def test_runner_uses_repository_v9_corpus_when_omitted(monkeypatch, tmp_path):
    _fake_prep(monkeypatch)
    seen = {}

    def split(path):
        seen["corpus"] = path
        return pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2025-01-01", tz="UTC")

    monkeypatch.setattr(bakeoff, "_split_label_cutoffs", split)
    sentinel = type("Sentinel_sage", (), {})
    monkeypatch.setattr(
        bakeoff,
        "GNN_ARMS",
        {"sage": {"cls": sentinel, "num_rel": 4, "label": "SAGE", "looks_for": "x"}},
    )
    monkeypatch.setattr(
        bakeoff,
        "_gnn_scores",
        lambda *args, **kwargs: _fake_score_bundle(kwargs["seeds"], 4),
    )
    bakeoff.run_bakeoff(output=tmp_path / "artifact.json", ks=(1,), daily_ks=(1,))
    assert seen["corpus"] == bakeoff.DEFAULT_CORPUS


def test_validation_failure_preserves_prior_output(monkeypatch, tmp_path):
    _fake_prep(monkeypatch)
    sentinel = type("Sentinel_sage", (), {})
    monkeypatch.setattr(
        bakeoff,
        "GNN_ARMS",
        {"sage": {"cls": sentinel, "num_rel": 4, "label": "SAGE", "looks_for": "x"}},
    )
    monkeypatch.setattr(
        bakeoff,
        "_gnn_scores",
        lambda *args, **kwargs: _fake_score_bundle(kwargs["seeds"], 4),
    )
    def fail_validation(payload):
        raise ValueError("invalid artifact")

    monkeypatch.setattr(bakeoff, "validate_artifact", fail_validation)
    output = tmp_path / "artifact.json"
    output.write_bytes(b"prior-bytes")
    with pytest.raises(ValueError, match="invalid artifact"):
        bakeoff.run_bakeoff(corpus_dir=tmp_path, output=output, ks=(1,), daily_ks=(1,))
    assert output.read_bytes() == b"prior-bytes"


def test_parser_defaults_and_overrides_and_integer_validation():
    parser = bakeoff.build_parser()
    args = parser.parse_args([])
    assert args.corpus == str(bakeoff.DEFAULT_CORPUS)
    assert args.output == str(bakeoff.DEFAULT_OUTPUT)
    assert tuple(args.seeds) == (0, 1, 2)
    assert args.epochs == 18
    assert args.train_bucket == "Q"
    assert tuple(args.ks) == tuple(bakeoff.KS)
    assert tuple(args.daily_ks) == tuple(bakeoff.DAILY_KS)

    args = parser.parse_args([
        "--corpus", "/tmp/custom-corpus", "--output", "/tmp/custom.json",
        "--seeds", "0", "1", "2", "--epochs", "3", "--train-bucket", "M",
        "--ks", "2", "4", "--daily-ks", "1", "3",
    ])
    assert args.corpus == "/tmp/custom-corpus"
    assert args.output == "/tmp/custom.json"
    assert args.seeds == [0, 1, 2]
    assert args.ks == [2, 4]
    with pytest.raises(SystemExit):
        parser.parse_args(["--seeds", "1", "1"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--seeds", "-1"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--epochs", "0"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--ks", "1", "1"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--daily-ks", "0"])
