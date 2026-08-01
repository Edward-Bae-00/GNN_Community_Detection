"""End-to-end smoke of the V9 baseline-vs-GNN demo on the tiny v9dev corpus.
See tasks/v9_demo_corpus_plan.md (Task 10)."""
from dataclasses import FrozenInstanceError
import json
import os
from pathlib import Path
import subprocess
import sys
import pathlib
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import gnn.run_demo as rd
from gnn import learned_cell as lc

CD = pathlib.Path(__file__).resolve().parents[1] / \
    "Documents/Data/synthetic_cbp_graph_corpus_v9dev"


def _write_cutoff_corpus(corpus):
    cutoff_spec = (
        "train<2024-01-01; validation<2025-01-01; test>=2025-01-01"
    )
    rows = [
        ("train-before", "train", "2023-12-01T00:00:00Z",
         "2023-12-31T23:59:59Z", True),
        ("train-equal", "train", "2023-12-02T00:00:00Z",
         "2024-01-01T00:00:00Z", True),
        ("train-after", "train", "2023-12-03T00:00:00Z",
         "2024-01-02T00:00:00Z", False),
        ("valid-before", "validation", "2024-12-01T00:00:00Z",
         "2024-12-31T23:59:59Z", True),
        ("valid-equal", "validation", "2024-12-02T00:00:00Z",
         "2025-01-01T00:00:00Z", True),
        ("valid-after", "validation", "2024-12-03T00:00:00Z",
         "2025-01-02T00:00:00Z", False),
    ]
    pd.DataFrame([
        {
            "event_id": event_id,
            "primary_person_id": f"person-{event_id}",
            "detected_flag": detected,
            "false_negative_flag": False,
        }
        for event_id, _, _, _, detected in rows
    ]).to_csv(corpus / "event_ground_truth.csv", index=False)
    pd.DataFrame([
        {
            "entity_id": event_id,
            "split": split,
            "temporal_cutoff": cutoff_spec,
        }
        for event_id, split, _, _, _ in rows
    ]).to_csv(corpus / "train_valid_test_splits.csv", index=False)
    pd.DataFrame([
        {
            "event_id": event_id,
            "event_timestamp_utc": event_time,
            "observed_person_record_id": f"obs-{event_id}",
            "label_available_time_utc": label_time,
        }
        for event_id, _, event_time, label_time, _ in rows
    ]).to_csv(corpus / "crossing_events.csv", index=False)


def test_training_labels_are_available_strictly_before_declared_cutoff(tmp_path):
    _write_cutoff_corpus(tmp_path)

    train_cutoff, test_cutoff = rd._split_label_cutoffs(tmp_path)
    pool, labels = rd._train_pool_and_labels(tmp_path, train_cutoff)

    assert train_cutoff == pd.Timestamp("2024-01-01T00:00:00Z")
    assert test_cutoff == pd.Timestamp("2025-01-01T00:00:00Z")
    assert pool["event_id"].tolist() == ["train-before"]
    assert labels.tolist() == [1]


def test_validation_labels_are_available_strictly_before_test_start(tmp_path):
    _write_cutoff_corpus(tmp_path)

    _, test_cutoff = rd._split_label_cutoffs(tmp_path)
    valid_pool = rd.load_pool(tmp_path, split="validation")
    eligible = rd._label_available_before(valid_pool, test_cutoff)

    assert valid_pool.loc[eligible, "event_id"].tolist() == ["valid-before"]


def test_gnn_training_defense_excludes_label_at_cutoff():
    pool = pd.DataFrame({
        "event_id": ["before", "equal", "after"],
        "primary_obs_id": ["o1", "o2", "o3"],
        "t": pd.to_datetime([
            "2023-12-01T00:00:00Z",
            "2023-12-02T00:00:00Z",
            "2023-12-03T00:00:00Z",
        ]),
        "label_available_time": pd.to_datetime([
            "2023-12-31T23:59:59Z",
            "2024-01-01T00:00:00Z",
            "2024-01-02T00:00:00Z",
        ]),
    })

    eligible_pool, eligible_labels = lc._eligible_training_supervision(
        pool,
        np.array([1, 1, 0]),
        pd.Timestamp("2024-01-01T00:00:00Z"),
    )

    assert eligible_pool["event_id"].tolist() == ["before"]
    assert eligible_labels.tolist() == [1]


def test_gnn_score_bundle_retains_seed_models_and_scores(monkeypatch):
    events = []
    train_cutoffs = []
    train_cutoff = object()
    pools = [SimpleNamespace(pool_index=0), SimpleNamespace(pool_index=1)]

    def fake_train(*args, **kwargs):
        events.append(("train", kwargs["seed"]))
        train_cutoffs.append(kwargs["train_cutoff"])
        return SimpleNamespace(seed=kwargs["seed"])

    def fake_score(model, pool, *args, **kwargs):
        events.append(("score", model.seed, pool.pool_index))
        return np.array([model.seed + pool.pool_index,
                         model.seed + pool.pool_index + 3.0])

    monkeypatch.setattr(rd, "_train_caught_rgcn", fake_train)
    monkeypatch.setattr(rd, "_score_pool", fake_score)
    monkeypatch.setattr(rd, "validate_pool_identities", lambda *args, **kwargs: None)

    bundle = rd._gnn_scores(
        [], ["person"], np.zeros((1, 1)), {}, SimpleNamespace(), np.array([1]),
        pools, {}, seeds=(0, 1, 2), epochs=1, train_bucket="M",
        train_cutoff=train_cutoff, model_cls=object, num_rel=4,
    )

    assert bundle.seed_order == (0, 1, 2)
    assert tuple(bundle.models_by_seed) == bundle.seed_order
    assert [bundle.models_by_seed[seed].seed for seed in bundle.seed_order] == [0, 1, 2]
    assert tuple(bundle.scores_by_seed) == bundle.seed_order
    np.testing.assert_array_equal(bundle.ensemble(0), np.array([1.0, 4.0]))
    assert all(cutoff is train_cutoff for cutoff in train_cutoffs)
    assert events == [
        ("train", 0), ("train", 1), ("train", 2),
        ("score", 0, 0), ("score", 1, 0), ("score", 2, 0),
        ("score", 0, 1), ("score", 1, 1), ("score", 2, 1),
    ]


def test_gnn_scores_rejects_empty_or_duplicate_seed_order():
    args = ([], [], np.empty((0, 0)), {}, SimpleNamespace(), np.array([]), [], {})
    kwargs = {
        "epochs": 1,
        "train_bucket": "M",
        "train_cutoff": object(),
        "model_cls": object,
        "num_rel": 4,
    }

    with pytest.raises(ValueError, match="at least one"):
        rd._gnn_scores(*args, seeds=(), **kwargs)
    with pytest.raises(ValueError, match="duplicate"):
        rd._gnn_scores(*args, seeds=(1, "1"), **kwargs)


def test_gnn_score_bundle_rejects_invalid_pool_index():
    bundle = rd.GNNScoreBundle(
        seed_order=(0, 1),
        models_by_seed={0: object(), 1: object()},
        scores_by_seed={
            0: (np.array([0.1, 0.2]),),
            1: (np.array([0.3, 0.4]),),
        },
    )

    with pytest.raises(IndexError, match="pool_index"):
        bundle.ensemble(-1)
    with pytest.raises(IndexError, match="pool_index"):
        bundle.ensemble(1)


def test_gnn_score_bundle_rejects_identical_shaped_2d_scores():
    with pytest.raises(ValueError, match="exactly 1-D"):
        rd.GNNScoreBundle(
            seed_order=(0, 1),
            models_by_seed={0: object(), 1: object()},
            scores_by_seed={
                0: (np.array([[0.1, 0.2], [0.3, 0.4]]),),
                1: (np.array([[0.5, 0.6], [0.7, 0.8]]),),
            },
        )


@pytest.mark.parametrize("nonfinite", [np.nan, np.inf, -np.inf])
def test_gnn_score_bundle_rejects_nonfinite_scores(nonfinite):
    with pytest.raises(ValueError, match="finite"):
        rd.GNNScoreBundle(
            seed_order=(0,),
            models_by_seed={0: object()},
            scores_by_seed={0: (np.array([0.1, nonfinite]),)},
        )


def test_gnn_score_bundle_rejects_inconsistent_pool_counts():
    with pytest.raises(ValueError, match="same number of pool entries"):
        rd.GNNScoreBundle(
            seed_order=(0, 1),
            models_by_seed={0: object(), 1: object()},
            scores_by_seed={
                0: (np.array([0.1]), np.array([0.2])),
                1: (np.array([0.3]),),
            },
        )


def test_gnn_score_bundle_rejects_misaligned_pool_rows():
    with pytest.raises(ValueError, match="aligned row shapes"):
        rd.GNNScoreBundle(
            seed_order=(0, 1),
            models_by_seed={0: object(), 1: object()},
            scores_by_seed={
                0: (np.array([0.1, 0.2]),),
                1: (np.array([0.3]),),
            },
        )


def test_gnn_score_bundle_is_defensively_immutable():
    seed_order = [0, 1]
    models = {0: SimpleNamespace(seed=0), 1: SimpleNamespace(seed=1)}
    seed_zero_scores = np.array([0.1, 0.2], dtype=np.float32)
    scores = {
        0: [seed_zero_scores],
        1: [np.array([0.3, 0.4], dtype=np.float32)],
    }
    bundle = rd.GNNScoreBundle(seed_order, models, scores)

    seed_order.append(2)
    models[2] = SimpleNamespace(seed=2)
    scores[0].append(np.array([9.0, 9.0]))
    seed_zero_scores[0] = 9.0

    assert bundle.seed_order == (0, 1)
    np.testing.assert_array_equal(
        bundle.scores_by_seed[0][0], np.array([0.1, 0.2], dtype=np.float32)
    )
    ensemble_before = bundle.ensemble(0).copy()
    retained = bundle.scores_by_seed[0][0]
    with pytest.raises(TypeError):
        bundle.models_by_seed[0] = object()
    with pytest.raises(TypeError):
        bundle.scores_by_seed[0] = ()
    with pytest.raises(ValueError, match="WRITEABLE"):
        retained.setflags(write=True)
    with pytest.raises(ValueError, match="read-only"):
        retained[0] = 7.0
    np.testing.assert_array_equal(bundle.ensemble(0), ensemble_before)
    with pytest.raises(FrozenInstanceError):
        bundle.seed_order = (1, 0)


def test_gnn_score_bundle_ensemble_matches_old_mean_for_multiple_pools():
    scores_by_seed = {
        7: (
            np.array([0.15, 0.25, 0.35], dtype=np.float32),
            np.array([1, 5], dtype=np.int16),
        ),
        3: (
            np.array([0.45, 0.55, 0.65], dtype=np.float32),
            np.array([3, 7], dtype=np.int16),
        ),
        11: (
            np.array([0.75, 0.85, 0.95], dtype=np.float32),
            np.array([5, 9], dtype=np.int16),
        ),
    }
    bundle = rd.GNNScoreBundle(
        seed_order=(7, 3, 11),
        models_by_seed={seed: object() for seed in scores_by_seed},
        scores_by_seed=scores_by_seed,
    )

    for pool_index in range(2):
        expected = np.mean(np.column_stack([
            scores_by_seed[seed][pool_index] for seed in bundle.seed_order
        ]), axis=1)
        actual = bundle.ensemble(pool_index)
        np.testing.assert_array_equal(actual, expected)
        assert actual.dtype == expected.dtype


def test_daily_found_mask_stays_aligned_when_scores_reorder_rows():
    days = pd.to_datetime(["2025-01-01", "2025-01-01"], utc=True)

    found = rd._daily_found_by_k(
        days,
        scores=np.array([0.1, 0.9]),
        hidden=np.array([False, True]),
        daily_ks=(1,),
        mask=np.array([False, True]),
    )

    assert found == {1: 1}


def test_evaluate_daily_reports_precision_recall_and_f1():
    pool = pd.DataFrame({
        "t": pd.to_datetime([
            "2025-01-01T01:00:00Z", "2025-01-01T02:00:00Z",
            "2025-01-01T03:00:00Z", "2025-01-02T01:00:00Z",
            "2025-01-02T02:00:00Z", "2025-01-02T03:00:00Z",
        ]),
        "hidden": [True, False, True, False, True, False],
    })
    out = rd.evaluate_daily(pool, np.array([.9, .8, .1, .7, .6, .5]), (2,))

    assert out["daily_budget@2"] == 4
    assert out["daily_found@2"] == 2
    assert out["daily_precision@2"] == 0.5
    assert out["daily_recall@2"] == 0.6667
    assert out["daily_f1@2"] == 0.5714
    assert out["daily_found_by_day@2"] == [
        {"date": "2025-01-01", "found": 1},
        {"date": "2025-01-02", "found": 1},
    ]


def test_paired_daily_bootstrap_reports_daily_hybrid_comparison():
    pool = pd.DataFrame({
        "t": pd.to_datetime([
            "2025-01-01T01:00:00Z", "2025-01-01T02:00:00Z",
            "2025-01-02T01:00:00Z", "2025-01-02T02:00:00Z",
        ]),
    })
    hidden = np.array([True, False, False, True])
    out = rd.paired_daily_bootstrap(
        np.array([.9, .8, .7, .1]),
        np.array([.8, .7, .9, .1]),
        pool,
        hidden,
        (1, 2),
        n_boot=10,
        seed=0,
    )

    assert set(out) == {
        "hybrid_vs_baseline_daily@1",
        "hybrid_vs_baseline_daily@2",
    }
    assert all({"mean_diff", "ci", "p_enh_le_base", "significant"} <= set(v)
               for v in out.values())


def test_simulated_catches_applies_strict_day_start_boundary_before_ranking():
    pool = pd.DataFrame({
        "t": pd.to_datetime([
            "2025-01-02T01:00:00Z", "2025-01-02T02:00:00Z",
            "2025-01-02T03:00:00Z", "2025-01-02T04:00:00Z",
        ]),
        "hidden": [False, True, True, False],
        "primary_person_id": [
            "caught-before", "caught-at-start", "caught-same-day", "never-caught",
        ],
    })
    scores = {
        "baseline": np.array([.99, .90, .80, .70]),
        "hybrid": np.array([.99, .90, .80, .70]),
    }
    caught_times = {
        "caught-before": pd.Timestamp("2025-01-01T23:59:59Z"),
        "caught-at-start": pd.Timestamp("2025-01-02T00:00:00Z"),
        "caught-same-day": pd.Timestamp("2025-01-02T12:00:00Z"),
    }

    out = rd.evaluate_daily_simulated_catches(pool, scores, (2,), caught_times)

    assert out["policy"] == {
        "official_catch_time_field": "label_available_time_utc",
        "official_boundary": "strictly_before_utc_day_start",
        "simulated_feedback": "candidate_removal_only",
    }
    assert out["initial_pool"] == {
        "candidate_events": 3,
        "hidden_events": 2,
        "hidden_people": 2,
        "excluded_events": 1,
        "excluded_people": 1,
        "excluded_hidden_events": 0,
        "excluded_hidden_people": 0,
    }
    assert out["arms"]["baseline"] == {
        "daily_people_found@2": 2,
        "daily_found_by_day@2": [{"date": "2025-01-02", "found": 2}],
        "daily_budget@2": 2,
        "daily_precision@2": 1.0,
        "daily_recall@2": 1.0,
        "daily_f1@2": 1.0,
        "later_candidate_events_removed@2": 0,
        "later_hidden_events_removed@2": 0,
    }


def test_simulated_catches_removes_people_only_after_the_scoring_day():
    pool = pd.DataFrame({
        "t": pd.to_datetime([
            "2025-01-01T01:00:00Z", "2025-01-01T02:00:00Z",
            "2025-01-02T01:00:00Z", "2025-01-02T02:00:00Z",
            "2025-01-03T01:00:00Z", "2025-01-03T02:00:00Z",
            "2025-01-03T03:00:00Z",
        ]),
        "hidden": [True, True, True, True, False, True, False],
        "primary_person_id": ["a", "a", "a", "c", "a", "a", "d"],
    })
    scores = {
        "baseline": np.array([.90, .80, .99, .80, .99, .98, .70]),
        "hybrid": np.array([.90, .80, .99, .80, .99, .98, .70]),
    }

    out = rd.evaluate_daily_simulated_catches(pool, scores, (2,), {})
    metrics = out["arms"]["baseline"]

    assert out["initial_pool"] == {
        "candidate_events": 7,
        "hidden_events": 5,
        "hidden_people": 2,
        "excluded_events": 0,
        "excluded_people": 0,
        "excluded_hidden_events": 0,
        "excluded_hidden_people": 0,
    }
    assert metrics == {
        "daily_people_found@2": 2,
        "daily_found_by_day@2": [
            {"date": "2025-01-01", "found": 1},
            {"date": "2025-01-02", "found": 1},
            {"date": "2025-01-03", "found": 0},
        ],
        "daily_budget@2": 4,
        "daily_precision@2": 0.5,
        "daily_recall@2": 1.0,
        "daily_f1@2": 0.6667,
        "later_candidate_events_removed@2": 3,
        "later_hidden_events_removed@2": 2,
    }


def test_simulated_catch_state_is_isolated_per_arm_and_budget():
    pool = pd.DataFrame({
        "t": pd.to_datetime([
            "2025-01-01T01:00:00Z", "2025-01-01T02:00:00Z",
            "2025-01-02T01:00:00Z", "2025-01-02T02:00:00Z",
        ]),
        "hidden": [True, True, True, False],
        "primary_person_id": ["a", "b", "b", "c"],
    })
    scores = {
        "baseline": np.array([.90, .80, .90, .10]),
        "hybrid": np.array([.10, .90, .80, .95]),
    }

    out = rd.evaluate_daily_simulated_catches(pool, scores, (1, 2), {})

    baseline = out["arms"]["baseline"]
    assert baseline["daily_found_by_day@1"] == [
        {"date": "2025-01-01", "found": 1},
        {"date": "2025-01-02", "found": 1},
    ]
    assert baseline["later_candidate_events_removed@1"] == 0
    assert baseline["daily_found_by_day@2"] == [
        {"date": "2025-01-01", "found": 2},
        {"date": "2025-01-02", "found": 0},
    ]
    assert baseline["later_candidate_events_removed@2"] == 1
    hybrid = out["arms"]["hybrid"]
    assert hybrid["daily_found_by_day@1"] == [
        {"date": "2025-01-01", "found": 1},
        {"date": "2025-01-02", "found": 0},
    ]
    assert hybrid["later_candidate_events_removed@1"] == 1


def test_seed_level_unique_person_recovery_uses_common_weight_and_population_sd():
    pool = pd.DataFrame(
        {
            "t": pd.to_datetime(
                [
                    "2025-01-01T01:00:00Z",
                    "2025-01-01T02:00:00Z",
                    "2025-01-01T03:00:00Z",
                    "2025-01-02T01:00:00Z",
                    "2025-01-02T02:00:00Z",
                    "2025-01-02T03:00:00Z",
                ]
            ),
            "primary_person_id": ["p1", "px", "p2", "p1", "p3", "py"],
            "hidden": [True, False, True, True, True, False],
        }
    )
    baseline = np.array([0.9, 0.2, 0.1, 0.95, 0.8, 0.1])
    gnn_scores = {
        0: np.array([0.1, 0.9, 0.2, 0.9, 0.1, 0.2]),
        1: np.array([0.1, 0.2, 0.9, 0.1, 0.9, 0.2]),
        2: np.array([0.9, 0.2, 0.1, 0.95, 0.8, 0.1]),
    }

    result = rd._seed_level_unique_person_recovery(
        pool,
        baseline,
        gnn_scores,
        blend_weight=1.0,
        official_caught_times={},
        inspections_per_day=1,
    )

    assert result["inspections_per_day"] == 1
    assert result["common_validation_tuned_fusion_weight"] == 1.0
    assert result["seeds"] == {
        "0": {
            "baseline_unique_people_recovered": 2,
            "hybrid_unique_people_recovered": 1,
            "net_unique_people_gain": -1,
        },
        "1": {
            "baseline_unique_people_recovered": 2,
            "hybrid_unique_people_recovered": 2,
            "net_unique_people_gain": 0,
        },
        "2": {
            "baseline_unique_people_recovered": 2,
            "hybrid_unique_people_recovered": 2,
            "net_unique_people_gain": 0,
        },
    }
    assert result["mean"] == pytest.approx(
        {
            "baseline_unique_people_recovered": 2.0,
            "hybrid_unique_people_recovered": 5 / 3,
            "net_unique_people_gain": -1 / 3,
        }
    )
    assert result["population_sd"] == pytest.approx(
        {
            "baseline_unique_people_recovered": 0.0,
            "hybrid_unique_people_recovered": np.sqrt(2 / 9),
            "net_unique_people_gain": np.sqrt(2 / 9),
        }
    )
    assert result["score_averaged_ensemble"] == {
        "baseline_unique_people_recovered": 2,
        "hybrid_unique_people_recovered": 1,
        "net_unique_people_gain": -1,
    }


def test_run_demo_smoke():
    out = rd.main(
        corpus_dir=CD,
        seeds=(0,),
        n_boot=50,
        out_name="demo_smoke.json",
        epochs=1,
        ks=(50, 100),
    )
    assert {"baseline", "hybrid", "gnn"}.issubset(out["overall"])
    assert set(out["model_arms"]) == set(out["overall"])
    for arm in ("baseline", "hybrid", "gnn"):
        assert "precision@50" in out["overall"][arm]
        assert "recall@50" in out["overall"][arm]
        assert "f1@50" in out["overall"][arm]
    assert out["model_arms"]["baseline"]["kind"] == "baseline"
    assert out["model_arms"]["hybrid"]["kind"] == "hybrid"
    assert out["model_arms"]["gnn"]["kind"] == "gnn"
    assert out["hidden_total"] >= 0
    assert "observability" not in out
    assert out["seed_level_unique_person_recovery"][
        "common_validation_tuned_fusion_weight"
    ] == out["hybrid_fusion_w_gnn"]
    # Hybrid bootstrap comparisons exist
    assert len(out.get("win_hybrid_whole_pool", {})) > 0
    assert len(out.get("win_hybrid_daily", {})) > 0
    assert "daily_precision@25" in out["overall_daily"]["hybrid"]
    assert "daily_f1@25" in out["overall_daily"]["hybrid"]
    daily_series = out["overall_daily"]["hybrid"]["daily_found_by_day@25"]
    assert len(daily_series) == out["overall_daily"]["hybrid"]["n_days"]
    assert sum(day["found"] for day in daily_series) == out["overall_daily"]["hybrid"]["daily_found@25"]
    simulated = out["simulated_catch_daily"]
    assert set(simulated["arms"]) == {"baseline", "hybrid"}
    initial = simulated["initial_pool"]
    assert initial["candidate_events"] + initial["excluded_events"] == out["pool_size"]
    assert initial["hidden_events"] + initial["excluded_hidden_events"] == out["hidden_total"]
    assert initial["hidden_people"] <= initial["hidden_events"]
    assert initial["excluded_hidden_people"] <= initial["excluded_hidden_events"]
    # Simulated catches and operational capacity share the daily-only budget
    # contract so every dashboard surface reads K=5, 10, and 25 per day.
    assert out["daily_ks"] == list(rd.DAILY_KS)
    assert out["simulated_catch_daily_ks"] == list(rd.SIMULATED_DAILY_KS)
    assert set(rd.SIMULATED_DAILY_KS) == set(rd.DAILY_KS)
    for arm in simulated["arms"].values():
        assert {
            int(key.split("@")[1])
            for key in arm
            if key.startswith("daily_people_found@")
        } == set(out["simulated_catch_daily_ks"])
        for k in out["simulated_catch_daily_ks"]:
            found = arm[f"daily_people_found@{k}"]
            budget = arm[f"daily_budget@{k}"]
            series = arm[f"daily_found_by_day@{k}"]
            assert len(series) == out["overall_daily"]["baseline"]["n_days"]
            assert sum(day["found"] for day in series) == found
            assert arm[f"daily_precision@{k}"] == (
                round(found / budget, 4) if budget else 0.0
            )
            assert arm[f"daily_recall@{k}"] == (
                round(found / initial["hidden_people"], 4)
                if initial["hidden_people"] else 0.0
            )
            assert (arm[f"later_hidden_events_removed@{k}"]
                    <= arm[f"later_candidate_events_removed@{k}"])


def test_atomic_json_write_replaces_target_without_leaving_temporary_file(
    tmp_path,
):
    target = tmp_path / "nested" / "result.json"
    target.parent.mkdir(parents=True)
    target.write_text("stale")

    rd._atomic_json_write(target, {"value": 3})

    assert json.loads(target.read_text()) == {"value": 3}
    assert not target.with_suffix(".json.tmp").exists()


def test_observability_output_failure_preserves_prior_valid_artifact(
    tmp_path,
):
    comparison = tmp_path / "comparison.json"
    comparison.write_text('{"comparison": "valid"}')
    target = tmp_path / "observability.json"
    temporary = target.with_suffix(".json.tmp")
    target.write_text('{"prior": "valid"}')
    temporary.write_text("partial")

    def fail_generation():
        temporary.write_text("new partial")
        raise RuntimeError("artifact failed")

    with pytest.raises(RuntimeError, match="artifact failed"):
        rd._write_observability_output(target, fail_generation)

    assert comparison.read_text() == '{"comparison": "valid"}'
    assert target.read_text() == '{"prior": "valid"}'
    assert not temporary.exists()


@pytest.mark.parametrize(
    ("seeds", "gnn_arm"),
    [((1, 2), "sage"), ((0, 1, 2), "rgcn")],
)
def test_observability_main_fails_before_work_without_exact_sage_scope(
    seeds, gnn_arm
):
    with pytest.raises(
        ValueError,
        match="requires the surrounding three-seed GraphSAGE run",
    ):
        rd.main(
            corpus_dir=CD,
            seeds=seeds,
            gnn_arm=gnn_arm,
            observability=True,
        )


def test_observability_without_narrative_fails_before_training(monkeypatch):
    monkeypatch.setattr(
        rd,
        "_gnn_scores",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("training must not start")
        ),
    )

    with pytest.raises(ValueError, match="requires validated Gemma narratives"):
        rd.main(
            corpus_dir=CD,
            seeds=(0, 1, 2),
            observability=True,
            narrative=False,
        )


def test_observability_preflight_failure_precedes_training(monkeypatch):
    monkeypatch.setattr(
        rd,
        "preflight_narrative_contract",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("preflight failed")),
    )
    monkeypatch.setattr(
        rd,
        "_gnn_scores",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("training must not start")
        ),
    )

    with pytest.raises(RuntimeError, match="preflight failed"):
        rd.main(
            corpus_dir=CD,
            seeds=(0, 1, 2),
            observability=True,
        )


def test_gnn_identity_validation_failure_precedes_seed_zero_training(monkeypatch):
    monkeypatch.setattr(
        rd,
        "validate_pool_identities",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("outside universe")),
    )
    monkeypatch.setattr(
        rd,
        "_train_caught_rgcn",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("seed-zero training must not start")
        ),
    )
    pool = pd.DataFrame({"primary_obs_id": ["obs-1"]})

    with pytest.raises(ValueError, match="outside universe"):
        rd._gnn_scores(
            [], ["P-1"], np.ones((1, 1)), {}, pool, np.array([0]), [pool],
            {"obs-1": "P-2"}, seeds=(0,), epochs=1, train_bucket="M",
            train_cutoff=pd.Timestamp("2024-01-01", tz="UTC"),
            model_cls=object, num_rel=4,
        )


def test_main_identity_validation_failure_precedes_baseline_fitting(monkeypatch):
    monkeypatch.setattr(
        rd,
        "validate_pool_identities",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("outside universe")),
    )
    monkeypatch.setattr(
        rd,
        "fit_predict",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("baseline fitting must not start")
        ),
    )

    with pytest.raises(ValueError, match="outside universe"):
        rd.main(
            corpus_dir=CD,
            seeds=(0,),
            n_boot=1,
            epochs=1,
            ks=(50,),
            daily_ks=(5,),
            valid_sample=10,
        )


def test_observability_generation_is_separate_and_comparison_is_byte_identical(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(rd.FC, "RESULTS", tmp_path)
    captured = {}
    score_bundles = []
    artifact = {"schema_version": "2.0", "kind": "observability-only"}
    original_gnn_scores = rd._gnn_scores

    def recording_gnn_scores(*args, **kwargs):
        bundle = original_gnn_scores(*args, **kwargs)
        score_bundles.append(bundle)
        return bundle

    def fake_build_observability_bundle(**kwargs):
        captured.update(kwargs)
        return artifact

    monkeypatch.setattr(rd, "_gnn_scores", recording_gnn_scores)
    monkeypatch.setattr(
        rd, "build_observability_bundle", fake_build_observability_bundle
    )
    monkeypatch.setattr(rd, "preflight_narrative_contract", lambda **kwargs: "gemma4:12b")
    arguments = {
        "corpus_dir": CD,
        "seeds": (0, 1, 2),
        "n_boot": 5,
        "epochs": 1,
        "ks": (50,),
        "daily_ks": (25,),
        "valid_sample": 100,
    }

    without = rd.main(
        **arguments,
        out_name="without.json",
        observability=False,
    )
    with_observability = rd.main(
        **arguments,
        out_name="with.json",
        observability=True,
        observability_out_name="observability.json",
        narrative=True,
    )

    assert without == with_observability
    assert (tmp_path / "without.json").read_bytes() == (
        tmp_path / "with.json"
    ).read_bytes()
    assert json.loads((tmp_path / "observability.json").read_text()) == artifact
    assert "observability" not in with_observability
    assert captured["gnn_arm"] == "sage"
    assert captured["surrounding_seeds"] == (0, 1, 2)
    assert captured["inspections_per_day"] == 5
    assert captured["staging_root"] == tmp_path / ".observability.recovery-stage"
    assert captured["final_root"] == tmp_path / "recovery"
    assert captured["corpus_identity"] == str(CD.resolve())
    assert set(captured["recovery_run_identity"]) == {"checkpoint_id"}
    assert len(captured["recovery_run_identity"]["checkpoint_id"]) == 64
    assert captured["seed_level_unique_person_recovery"] == with_observability[
        "seed_level_unique_person_recovery"
    ]
    assert len(captured["seed0_gnn_raw"]) == with_observability["pool_size"]
    np.testing.assert_array_equal(
        captured["seed0_gnn_raw"], score_bundles[-1].scores_by_seed[0][1]
    )
    assert captured["narrative_builder"] is rd.generate_narrative


def test_fresh_process_observability_resume_uses_checkpoint_without_training(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(rd.FC, "RESULTS", tmp_path)
    result = rd.main(
        corpus_dir=CD,
        seeds=(0, 1, 2),
        n_boot=5,
        out_name="comparison.json",
        epochs=1,
        ks=(50,),
        daily_ks=(5,),
        valid_sample=100,
    )
    checkpoint_path = next((tmp_path / "checkpoints").iterdir())
    scores_path = checkpoint_path / "scores.npz"
    with np.load(scores_path, allow_pickle=False) as persisted:
        expected_baseline = persisted["baseline_test"].tolist()
        expected_seed0 = persisted["gnn_test_seed_0"].tolist()
    script = f"""
from pathlib import Path
import gnn.run_demo as rd
rd.FC.RESULTS = Path({str(tmp_path)!r})
rd.preflight_narrative_contract = lambda **kwargs: "gemma4:12b"
def fail_fit(*args, **kwargs):
    raise AssertionError("resume must not fit any model")
rd._gnn_scores = fail_fit
rd._train_caught_rgcn = fail_fit
rd.fit_predict = fail_fit
def capture(**kwargs):
    return {{
        "schema_version": "2.0",
        "baseline_raw": kwargs["baseline_raw"].tolist(),
        "seed0_gnn_raw": kwargs["seed0_gnn_raw"].tolist(),
        "recovery_run_identity": kwargs["recovery_run_identity"],
    }}
rd.build_observability_bundle = capture
rd.resume_observability(
    Path({str(checkpoint_path)!r}),
    corpus_dir=Path({str(CD)!r}),
    observability_out_name="resumed.json",
)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parents[1],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])},
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    resumed = json.loads((tmp_path / "resumed.json").read_text())
    assert resumed == {
        "schema_version": "2.0",
        "baseline_raw": expected_baseline,
        "seed0_gnn_raw": expected_seed0,
        "recovery_run_identity": {"checkpoint_id": checkpoint_path.name},
    }

    mismatch_script = f"""
from pathlib import Path
import gnn.run_demo as rd
rd.FC.RESULTS = Path({str(tmp_path)!r})
rd.preflight_narrative_contract = lambda **kwargs: "gemma4:12b"
real_load_pool = rd.load_pool
def reordered(corpus_dir, split="test"):
    value = real_load_pool(corpus_dir, split=split)
    if split == "test":
        return value.iloc[::-1].reset_index(drop=True)
    return value
rd.load_pool = reordered
rd._gnn_scores = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not train"))
try:
    rd.resume_observability(
        Path({str(checkpoint_path)!r}),
        corpus_dir=Path({str(CD)!r}),
        observability_out_name="must-not-publish.json",
    )
except ValueError as exc:
    if "test event order is incompatible" not in str(exc):
        raise
else:
    raise AssertionError("reordered events were accepted")
"""
    mismatch = subprocess.run(
        [sys.executable, "-c", mismatch_script],
        cwd=Path(__file__).parents[1],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])},
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert mismatch.returncode == 0, mismatch.stderr
    assert not (tmp_path / "must-not-publish.json").exists()
