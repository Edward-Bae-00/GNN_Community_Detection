"""End-to-end smoke of the V9 baseline-vs-GNN demo on the tiny v9dev corpus.
See tasks/v9_demo_corpus_plan.md (Task 10)."""
import pathlib

import numpy as np
import pandas as pd

import gnn.run_demo as rd

CD = pathlib.Path(__file__).resolve().parents[1] / \
    "Documents/Data/synthetic_cbp_graph_corpus_v9dev"


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
    for arm in simulated["arms"].values():
        for k in out["daily_ks"]:
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
