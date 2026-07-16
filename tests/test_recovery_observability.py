from __future__ import annotations

from types import MappingProxyType

import numpy as np
import pandas as pd
import pytest

from gnn.recovery_observability import (
    RecoveryAnchor,
    recovery_overlap,
    simulate_recovery_run,
)


def _pool(
    event_ids: list[str],
    person_ids: list[str],
    timestamps: list[str],
    hidden: list[bool] | None = None,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "event_id": event_ids,
            "primary_person_id": person_ids,
            "t": timestamps,
            "hidden": hidden if hidden is not None else [True] * len(event_ids),
        }
    )


def test_exact_recovery_overlap_and_summary() -> None:
    pool = _pool(
        ["e1", "e2", "e3", "e4"],
        ["p1", "p1", "p2", "p3"],
        [
            "2025-01-01T01:00:00Z",
            "2025-01-01T02:00:00Z",
            "2025-01-01T03:00:00Z",
            "2025-01-02T01:00:00Z",
        ],
    )

    baseline = simulate_recovery_run(
        pool,
        [0.9, 0.8, 0.7, 0.6],
        arm="baseline",
        daily_budget=1,
        official_caught_times={},
    )
    hybrid = simulate_recovery_run(
        pool,
        [0.8, 0.7, 0.9, 0.95],
        arm="hybrid",
        daily_budget=1,
        official_caught_times={},
    )
    overlap = recovery_overlap(baseline, hybrid)

    assert baseline.recovered_ids == frozenset({"p1", "p3"})
    assert hybrid.recovered_ids == frozenset({"p2", "p3"})
    assert overlap.baseline_ids == frozenset({"p1", "p3"})
    assert overlap.hybrid_ids == frozenset({"p2", "p3"})
    assert overlap.both_ids == frozenset({"p3"})
    assert overlap.hybrid_only_ids == frozenset({"p2"})
    assert overlap.baseline_only_ids == frozenset({"p1"})
    assert overlap.summary == {
        "overlap_ids_available": True,
        "baseline_recovered": 2,
        "recovered_by_both": 1,
        "hybrid_only_recovered": 1,
        "baseline_only_recovered": 1,
        "hybrid_total": 2,
        "net_gain": 0,
    }


def test_same_day_repeat_consumes_budget_and_uses_first_hidden_anchor() -> None:
    pool = _pool(
        ["e-highest", "e-repeat", "e-other"],
        ["p1", "p1", "p2"],
        [
            "2025-01-01T01:00:00Z",
            "2025-01-01T02:00:00Z",
            "2025-01-01T03:00:00Z",
        ],
    )

    run = simulate_recovery_run(
        pool,
        [0.9, 0.8, 0.7],
        arm="baseline",
        daily_budget=2,
        official_caught_times={},
    )
    day = pd.Timestamp("2025-01-01", tz="UTC")

    assert run.recovered_ids == frozenset({"p1"})
    assert run.first_recovery["p1"] == RecoveryAnchor(
        person_id="p1",
        event_id="e-highest",
        row_index=0,
        scoring_day=day,
        inspected_rank=1,
    )
    assert run.days[day].candidate_row_indices == (0, 1, 2)
    assert run.days[day].inspected_row_indices == (0, 1)


def test_official_catch_boundary_is_strictly_before_day_start() -> None:
    pool = _pool(
        ["e-before", "e-boundary"],
        ["p-before", "p-boundary"],
        ["2025-01-02T01:00:00Z", "2025-01-02T02:00:00Z"],
    )

    run = simulate_recovery_run(
        pool,
        [1.0, 0.5],
        arm="hybrid",
        daily_budget=2,
        official_caught_times={
            "p-before": "2025-01-01T23:59:59Z",
            "p-boundary": "2025-01-02T00:00:00Z",
        },
    )
    day = pd.Timestamp("2025-01-02", tz="UTC")

    assert run.days[day].candidate_row_indices == (1,)
    assert run.days[day].inspected_row_indices == (1,)
    assert run.recovered_ids == frozenset({"p-boundary"})


def test_recovered_identity_is_removed_on_later_days_without_shared_arm_state() -> None:
    pool = _pool(
        ["e-p1-day1", "e-px-day1", "e-p1-day2", "e-p2-day2"],
        ["p1", "px", "p1", "p2"],
        [
            "2025-01-01T01:00:00Z",
            "2025-01-01T02:00:00Z",
            "2025-01-02T01:00:00Z",
            "2025-01-02T02:00:00Z",
        ],
    )

    baseline = simulate_recovery_run(
        pool,
        [0.9, 0.1, 1.0, 0.5],
        arm="baseline",
        daily_budget=1,
        official_caught_times={},
    )
    hybrid = simulate_recovery_run(
        pool,
        [0.1, 0.9, 1.0, 0.5],
        arm="hybrid",
        daily_budget=1,
        official_caught_times={},
    )
    day_two = pd.Timestamp("2025-01-02", tz="UTC")

    assert baseline.days[day_two].candidate_row_indices == (3,)
    assert baseline.recovered_ids == frozenset({"p1", "p2"})
    assert hybrid.days[day_two].candidate_row_indices == (2, 3)
    assert hybrid.recovered_ids == frozenset({"px", "p1"})
    assert baseline.arm == "baseline"
    assert hybrid.arm == "hybrid"


def test_results_are_immutable_and_pool_index_is_reset_for_score_alignment() -> None:
    pool = _pool(
        ["e-low", "e-high"],
        ["p-low", "p-high"],
        ["2025-01-01T01:00:00Z", "2025-01-01T02:00:00Z"],
    )
    pool.index = [10, 20]

    run = simulate_recovery_run(
        pool,
        [0.1, 0.9],
        arm="baseline",
        daily_budget=1,
        official_caught_times={},
    )
    day = pd.Timestamp("2025-01-01", tz="UTC")

    assert isinstance(run.first_recovery, MappingProxyType)
    assert isinstance(run.days, MappingProxyType)
    assert run.days[day].candidate_row_indices == (1, 0)
    assert run.first_recovery["p-high"].row_index == 1
    with pytest.raises(TypeError):
        run.first_recovery["new"] = run.first_recovery["p-high"]  # type: ignore[index]
    with pytest.raises(TypeError):
        run.days[day] = run.days[day]  # type: ignore[index]
    with pytest.raises((AttributeError, TypeError)):
        run.arm = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("missing", ["event_id", "primary_person_id", "t", "hidden"])
def test_missing_required_columns_fail_clearly(missing: str) -> None:
    pool = _pool(["e1"], ["p1"], ["2025-01-01T01:00:00Z"]).drop(columns=missing)

    with pytest.raises(ValueError, match=rf"missing required columns.*{missing}"):
        simulate_recovery_run(
            pool,
            [0.5],
            arm="baseline",
            daily_budget=1,
            official_caught_times={},
        )


@pytest.mark.parametrize(
    ("scores", "daily_budget", "error"),
    [
        ([0.1], 0, "daily_budget must be positive"),
        ([0.1], -1, "daily_budget must be positive"),
        ([0.1, 0.2], 1, "scores must have length"),
        ([np.nan], 1, "scores must be finite"),
        ([np.inf], 1, "scores must be finite"),
    ],
)
def test_invalid_budget_and_scores_fail_clearly(
    scores: list[float], daily_budget: int, error: str
) -> None:
    pool = _pool(["e1"], ["p1"], ["2025-01-01T01:00:00Z"])

    with pytest.raises(ValueError, match=error):
        simulate_recovery_run(
            pool,
            scores,
            arm="baseline",
            daily_budget=daily_budget,
            official_caught_times={},
        )


def test_invalid_pool_timestamp_fails_closed_but_invalid_official_time_does_not_exclude() -> None:
    bad_pool = _pool(["e1"], ["p1"], ["not-a-time"])
    with pytest.raises(ValueError, match="invalid timestamps"):
        simulate_recovery_run(
            bad_pool,
            [0.5],
            arm="baseline",
            daily_budget=1,
            official_caught_times={},
        )

    pool = _pool(["e1"], ["p1"], ["2025-01-01T01:00:00Z"])
    run = simulate_recovery_run(
        pool,
        [0.5],
        arm="baseline",
        daily_budget=1,
        official_caught_times={"p1": "not-a-time"},
    )
    assert run.recovered_ids == frozenset({"p1"})


def test_equal_scores_use_row_index_as_deterministic_tiebreak() -> None:
    pool = _pool(
        ["e1", "e2", "e3"],
        ["p1", "p2", "p3"],
        [
            "2025-01-01T01:00:00Z",
            "2025-01-01T02:00:00Z",
            "2025-01-01T03:00:00Z",
        ],
    )
    run = simulate_recovery_run(
        pool,
        [0.5, 0.5, 0.5],
        arm="baseline",
        daily_budget=2,
        official_caught_times={},
    )
    day = pd.Timestamp("2025-01-01", tz="UTC")

    assert run.days[day].candidate_row_indices == (0, 1, 2)
    assert run.days[day].inspected_row_indices == (0, 1)


def test_overlap_rejects_unequal_budgets() -> None:
    pool = _pool(["e1"], ["p1"], ["2025-01-01T01:00:00Z"])
    baseline = simulate_recovery_run(
        pool,
        [0.5],
        arm="baseline",
        daily_budget=1,
        official_caught_times={},
    )
    hybrid = simulate_recovery_run(
        pool,
        [0.5],
        arm="hybrid",
        daily_budget=2,
        official_caught_times={},
    )

    with pytest.raises(ValueError, match="equal daily_budget"):
        recovery_overlap(baseline, hybrid)
