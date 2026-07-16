from __future__ import annotations

import json
from dataclasses import replace
from types import MappingProxyType

import numpy as np
import pandas as pd
import pytest

from gnn.recovery_observability import (
    HybridOnlyCase,
    RecoveryAnchor,
    RecoveryOverlap,
    build_decision_trace,
    build_rank_reference,
    recovery_overlap,
    representative_attempt_order,
    simulate_recovery_run,
)
from gnn.run_demo import _rank_fuse


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


@pytest.mark.parametrize("column", ["event_id", "primary_person_id"])
@pytest.mark.parametrize("bad_value", [None, np.nan, pd.NA, "", "   "])
def test_null_or_blank_identifiers_are_rejected(
    column: str, bad_value: object
) -> None:
    pool = _pool(["e1"], ["p1"], ["2025-01-01T01:00:00Z"])
    pool.loc[0, column] = bad_value

    with pytest.raises(
        ValueError, match=rf"{column} must contain non-null, non-blank values"
    ):
        simulate_recovery_run(
            pool,
            [0.5],
            arm="baseline",
            daily_budget=1,
            official_caught_times={},
        )


@pytest.mark.parametrize(
    ("hidden_value", "is_hidden"),
    [
        (True, True),
        (False, False),
        (np.bool_(True), True),
        (np.bool_(False), False),
        (1, True),
        (0, False),
        ("true", True),
        (" TRUE ", True),
        ("false", False),
        ("False", False),
        ("1", True),
        ("0", False),
    ],
)
def test_hidden_values_are_parsed_from_explicit_boolean_tokens(
    hidden_value: object, is_hidden: bool
) -> None:
    pool = _pool(
        ["e1"],
        ["p1"],
        ["2025-01-01T01:00:00Z"],
        hidden=[hidden_value],  # type: ignore[list-item]
    )

    run = simulate_recovery_run(
        pool,
        [0.5],
        arm="baseline",
        daily_budget=1,
        official_caught_times={},
    )

    expected = frozenset({"p1"}) if is_hidden else frozenset()
    assert run.recovered_ids == expected


@pytest.mark.parametrize("hidden_value", [None, np.nan, pd.NA, "", "yes", 2, -1, 0.5])
def test_null_or_unknown_hidden_values_are_rejected(hidden_value: object) -> None:
    pool = _pool(
        ["e1"],
        ["p1"],
        ["2025-01-01T01:00:00Z"],
        hidden=[hidden_value],  # type: ignore[list-item]
    )

    with pytest.raises(ValueError, match="hidden contains invalid boolean values"):
        simulate_recovery_run(
            pool,
            [0.5],
            arm="baseline",
            daily_budget=1,
            official_caught_times={},
        )


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


def test_rank_reference_matches_rank_fuse_and_freezes_arrays() -> None:
    pool = pd.DataFrame({"event_id": ["e1", "e2", "e3", "e4"]})
    baseline = np.array([0.1, 0.8, 0.4, 0.4])
    gnn = np.array([0.9, 0.2, 0.5, 0.5])

    reference = build_rank_reference(pool, baseline, gnn, blend_weight=0.75)

    np.testing.assert_allclose(
        reference.baseline_percentile,
        np.array([0.25, 1.0, 0.625, 0.625]),
    )
    np.testing.assert_allclose(
        reference.seed0_hybrid_score,
        _rank_fuse(baseline, gnn, 0.75),
    )
    expected_noise = np.random.default_rng(42).uniform(0.0, 1e-9, size=4)
    np.testing.assert_allclose(
        reference.baseline_selection_score,
        baseline + expected_noise,
        rtol=0.0,
        atol=0.0,
    )
    assert reference.percentile_reference_id.startswith("sha256:")
    assert reference.event_ids == ("e1", "e2", "e3", "e4")

    baseline[0] = 99.0
    assert reference.baseline_raw[0] == pytest.approx(0.1)
    for values in (
        reference.baseline_raw,
        reference.seed0_gnn_raw,
        reference.baseline_percentile,
        reference.seed0_gnn_percentile,
        reference.seed0_hybrid_score,
        reference.baseline_selection_score,
        reference.seed0_gnn_selection_score,
        reference.seed0_hybrid_selection_score,
    ):
        assert not values.flags.writeable
        with pytest.raises(ValueError, match="read-only"):
            values[0] = -1.0
        with pytest.raises(ValueError, match="cannot set WRITEABLE flag"):
            values.setflags(write=True)


@pytest.mark.parametrize(
    ("pool", "baseline", "gnn", "blend_weight", "error"),
    [
        (pd.DataFrame({"event_id": []}), [], [], 0.5, "non-empty and aligned"),
        (
            pd.DataFrame({"event_id": ["e1"]}),
            [0.1, 0.2],
            [0.3],
            0.5,
            "non-empty and aligned",
        ),
        (
            pd.DataFrame({"event_id": ["e1"]}),
            [np.nan],
            [0.3],
            0.5,
            "finite",
        ),
        (
            pd.DataFrame({"not_event_id": ["e1"]}),
            [0.1],
            [0.3],
            0.5,
            "event_id",
        ),
        (
            pd.DataFrame({"event_id": ["   "]}),
            [0.1],
            [0.3],
            0.5,
            "non-null, non-blank",
        ),
        (
            pd.DataFrame({"event_id": ["e1"]}),
            [0.1],
            [0.3],
            1.1,
            "blend_weight",
        ),
    ],
)
def test_rank_reference_rejects_invalid_inputs(
    pool: pd.DataFrame,
    baseline: list[float],
    gnn: list[float],
    blend_weight: float,
    error: str,
) -> None:
    with pytest.raises(ValueError, match=error):
        build_rank_reference(pool, baseline, gnn, blend_weight)


@pytest.mark.parametrize(
    "invalid_reference_id",
    ["sha256:not-a-digest", f"sha256:{'0' * 64}"],
)
def test_percentile_reference_id_must_match_ordered_event_ids(
    invalid_reference_id: str,
) -> None:
    reference = build_rank_reference(
        pd.DataFrame({"event_id": ["e1", "e2"]}),
        [0.8, 0.2],
        [0.7, 0.3],
        0.5,
    )

    with pytest.raises(ValueError, match="must match ordered event_ids"):
        replace(reference, percentile_reference_id=invalid_reference_id)


def test_rank_reference_rejects_duplicate_event_ids_in_build_and_direct_use() -> None:
    pool = pd.DataFrame({"event_id": ["duplicate", "duplicate"]})
    with pytest.raises(ValueError, match="event_id values must be unique"):
        build_rank_reference(pool, [0.8, 0.2], [0.7, 0.3], 0.5)

    reference = build_rank_reference(
        pd.DataFrame({"event_id": ["e1", "e2"]}),
        [0.8, 0.2],
        [0.7, 0.3],
        0.5,
    )
    with pytest.raises(ValueError, match="event_id values must be unique"):
        replace(
            reference,
            event_ids=("duplicate", "duplicate"),
            percentile_reference_id=f"sha256:{'0' * 64}",
        )


def test_decision_trace_hashes_ordered_candidate_sets_and_uses_arm_ranks() -> None:
    pool = pd.DataFrame({"event_id": ["anchor", "b-high", "h-high", "low"]})
    reference = build_rank_reference(
        pool,
        baseline_raw=[0.8, 0.9, 0.1, 0.2],
        seed0_gnn_raw=[0.8, 0.1, 0.9, 0.2],
        blend_weight=0.5,
    )

    trace = build_decision_trace(
        reference,
        row_index=0,
        baseline_candidate_row_indices=(1, 0, 3),
        hybrid_candidate_row_indices=(2, 0, 3),
        daily_budget=2,
    )
    reordered = build_decision_trace(
        reference,
        row_index=0,
        baseline_candidate_row_indices=(0, 1, 3),
        hybrid_candidate_row_indices=(2, 0, 3),
        daily_budget=2,
    )
    changed_hybrid = build_decision_trace(
        reference,
        row_index=0,
        baseline_candidate_row_indices=(1, 0, 3),
        hybrid_candidate_row_indices=(0, 2, 3),
        daily_budget=2,
    )

    assert trace["percentile_reference_id"] == reference.percentile_reference_id
    assert trace["baseline_daily_reference_id"] != reordered[
        "baseline_daily_reference_id"
    ]
    assert trace["hybrid_daily_reference_id"] == reordered[
        "hybrid_daily_reference_id"
    ]
    assert trace["baseline_daily_reference_id"] == changed_hybrid[
        "baseline_daily_reference_id"
    ]
    assert trace["hybrid_daily_reference_id"] != changed_hybrid[
        "hybrid_daily_reference_id"
    ]
    assert trace["baseline_rank"] == 2
    assert trace["seed0_gnn_rank"] == 2
    assert trace["seed0_hybrid_rank"] == 1
    assert trace["daily_budget"] == 2
    assert trace["baseline_raw"] == pytest.approx(0.8)
    assert trace["baseline_weighted_term"] == pytest.approx(
        0.5 * reference.baseline_percentile[0]
    )
    assert trace["seed0_gnn_probability"] == pytest.approx(0.8)
    assert trace["seed0_gnn_weighted_term"] == pytest.approx(
        0.5 * reference.seed0_gnn_percentile[0]
    )
    assert trace["seed0_hybrid_score"] == pytest.approx(
        reference.seed0_hybrid_score[0]
    )
    assert all(
        isinstance(value, (str, int, float)) for value in trace.values()
    )


def test_daily_candidate_hashes_use_unambiguous_length_framing() -> None:
    reference = build_rank_reference(
        pd.DataFrame(
            {"event_id": ["anchor", "a\nb", "c", "a", "b\nc"]}
        ),
        [0.9, 0.8, 0.7, 0.6, 0.5],
        [0.9, 0.8, 0.7, 0.6, 0.5],
        0.5,
    )
    first = build_decision_trace(
        reference,
        row_index=0,
        baseline_candidate_row_indices=(0, 1, 2),
        hybrid_candidate_row_indices=(0, 1, 2),
        daily_budget=1,
    )
    second = build_decision_trace(
        reference,
        row_index=0,
        baseline_candidate_row_indices=(0, 3, 4),
        hybrid_candidate_row_indices=(0, 3, 4),
        daily_budget=1,
    )

    assert first["baseline_daily_reference_id"] != second[
        "baseline_daily_reference_id"
    ]
    assert first["hybrid_daily_reference_id"] != second[
        "hybrid_daily_reference_id"
    ]

    left_global = build_rank_reference(
        pd.DataFrame({"event_id": ["a\nb", "c"]}),
        [0.8, 0.2],
        [0.7, 0.3],
        0.5,
    )
    right_global = build_rank_reference(
        pd.DataFrame({"event_id": ["a", "b\nc"]}),
        [0.8, 0.2],
        [0.7, 0.3],
        0.5,
    )
    assert (
        left_global.percentile_reference_id
        != right_global.percentile_reference_id
    )


def test_decision_trace_rejects_duplicate_candidate_rows() -> None:
    reference = build_rank_reference(
        pd.DataFrame({"event_id": ["e1", "e2"]}),
        [0.8, 0.2],
        [0.7, 0.3],
        0.5,
    )

    with pytest.raises(ValueError, match="must not contain duplicate row indices"):
        build_decision_trace(
            reference,
            row_index=0,
            baseline_candidate_row_indices=(0, 0),
            hybrid_candidate_row_indices=(0, 1),
            daily_budget=1,
        )


@pytest.mark.parametrize(
    ("row_index", "baseline_candidates", "hybrid_candidates", "budget", "error"),
    [
        (3, (0, 1), (0, 1), 1, "row_index"),
        (0, (1,), (0, 1), 1, "absent"),
        (0, (0, 1), (1,), 1, "absent"),
        (0, (0, 2), (0, 1), 1, "out of range"),
        (0, (0, 1), (0, -1), 1, "out of range"),
        (0, (0, 1), (0, 1), 0, "daily_budget"),
    ],
)
def test_decision_trace_rejects_invalid_references(
    row_index: int,
    baseline_candidates: tuple[int, ...],
    hybrid_candidates: tuple[int, ...],
    budget: int,
    error: str,
) -> None:
    reference = build_rank_reference(
        pd.DataFrame({"event_id": ["e1", "e2"]}),
        [0.8, 0.2],
        [0.7, 0.3],
        0.5,
    )

    with pytest.raises(ValueError, match=error):
        build_decision_trace(
            reference,
            row_index=row_index,
            baseline_candidate_row_indices=baseline_candidates,
            hybrid_candidate_row_indices=hybrid_candidates,
            daily_budget=budget,
        )


def _hybrid_only_case(
    person_id: str,
    row_index: int,
    baseline_rank: int,
    gnn_rank: int,
    hybrid_rank: int,
    baseline_percentile: float,
    gnn_percentile: float,
    categories: tuple[str, ...],
    period: str,
    *,
    decision_trace: dict[str, object] | None = None,
) -> HybridOnlyCase:
    day = pd.Timestamp("2025-01-02T00:00:00Z")
    return HybridOnlyCase(
        person_id=person_id,
        anchor=RecoveryAnchor(
            person_id, f"e-{person_id}", row_index, day, inspected_rank=1
        ),
        baseline_rank=baseline_rank,
        gnn_rank=gnn_rank,
        hybrid_rank=hybrid_rank,
        baseline_percentile=baseline_percentile,
        gnn_percentile=gnn_percentile,
        relationship_categories=categories,
        scoring_period=period,
        same_day_person_row_indices=[row_index],  # type: ignore[arg-type]
        baseline_candidate_row_indices=[row_index],  # type: ignore[arg-type]
        hybrid_candidate_row_indices=[row_index],  # type: ignore[arg-type]
        decision_trace={} if decision_trace is None else decision_trace,
    )


def test_representative_attempt_order_is_deterministic_and_round_robin() -> None:
    cases = [
        _hybrid_only_case("p1", 0, 21, 2, 1, 0.40, 0.90, ("COTRAVEL",), "2025-01"),
        _hybrid_only_case("p2", 1, 20, 3, 1, 0.41, 0.88, ("RESIDENCE",), "2025-01"),
        _hybrid_only_case(
            "p3", 2, 19, 4, 1, 0.42, 0.87, ("SHARED_PLATE",), "2025-02"
        ),
        _hybrid_only_case(
            "p4",
            3,
            18,
            5,
            1,
            0.43,
            0.86,
            ("COTRAVEL", "RESIDENCE"),
            "2025-01",
        ),
    ]

    first = representative_attempt_order(cases)
    second = representative_attempt_order(list(reversed(cases)))

    assert [case.person_id for case in first] == [case.person_id for case in second]
    assert len({case.person_id for case in first}) == len(cases)
    assert {case.relationship_categories[0] for case in first[:3]} == {
        "COTRAVEL",
        "RESIDENCE",
        "SHARED_PLATE",
    }


def test_representative_round_robin_interleaves_exact_queue_sequence() -> None:
    cases = [
        _hybrid_only_case("p1", 0, 101, 2, 1, 0.1, 0.9, ("COTRAVEL",), "2025-01"),
        _hybrid_only_case("p2", 1, 92, 3, 2, 0.2, 0.9, ("COTRAVEL",), "2025-01"),
        _hybrid_only_case("p3", 2, 83, 4, 3, 0.3, 0.9, ("COTRAVEL",), "2025-01"),
        _hybrid_only_case("p4", 3, 74, 5, 4, 0.4, 0.9, ("RESIDENCE",), "2025-01"),
        _hybrid_only_case(
            "p5", 4, 65, 6, 5, 0.5, 0.9, ("SHARED_PLATE",), "2025-02"
        ),
        _hybrid_only_case(
            "p6", 5, 56, 7, 6, 0.6, 0.9, ("SHARED_PLATE",), "2025-02"
        ),
    ]

    ordered = representative_attempt_order(list(reversed(cases)))

    assert [case.person_id for case in ordered] == [
        "p1",
        "p4",
        "p5",
        "p2",
        "p6",
        "p3",
    ]


def test_hybrid_only_case_copies_inputs_and_freezes_decision_trace() -> None:
    decision_trace: dict[str, object] = {"baseline_rank": 3}
    case = _hybrid_only_case(
        "p1", 0, 3, 2, 1, 0.25, 0.75, ("COTRAVEL",), "2025-01",
        decision_trace=decision_trace,
    )
    decision_trace["baseline_rank"] = 99

    assert case.hybrid_rank_uplift == 2
    assert case.gnn_percentile_uplift == pytest.approx(0.5)
    assert case.same_day_person_row_indices == (0,)
    assert case.baseline_candidate_row_indices == (0,)
    assert case.hybrid_candidate_row_indices == (0,)
    assert isinstance(case.decision_trace, MappingProxyType)
    assert case.decision_trace["baseline_rank"] == 3
    with pytest.raises(TypeError):
        case.decision_trace["baseline_rank"] = 4  # type: ignore[index]


def test_hybrid_only_case_decision_trace_is_deeply_immutable_and_detached() -> None:
    source_ids: list[object] = ["e1", {"rank": 1}]
    source_metadata = {"candidate_ids": source_ids, "labels": ["A", "B"]}
    decision_trace: dict[str, object] = {"evidence": source_metadata}
    case = _hybrid_only_case(
        "p1",
        0,
        3,
        2,
        1,
        0.25,
        0.75,
        ("COTRAVEL",),
        "2025-01",
        decision_trace=decision_trace,
    )

    source_ids[0] = "changed"
    source_ids[1]["rank"] = 99  # type: ignore[index]
    source_metadata["labels"].append("C")  # type: ignore[union-attr]
    decision_trace["new"] = True

    evidence = case.decision_trace["evidence"]
    assert isinstance(evidence, MappingProxyType)
    assert evidence["candidate_ids"][0] == "e1"
    assert evidence["candidate_ids"][1]["rank"] == 1
    assert evidence["labels"] == ("A", "B")
    with pytest.raises(TypeError):
        evidence["new"] = True  # type: ignore[index]
    with pytest.raises(TypeError):
        evidence["candidate_ids"][0] = "changed"  # type: ignore[index]
    with pytest.raises(TypeError):
        evidence["candidate_ids"][1]["rank"] = 99  # type: ignore[index]
    with pytest.raises(AttributeError):
        evidence["labels"].append("C")  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "invalid_trace",
    [
        {"bad": {"set-value"}},
        {1: "non-string-key"},
        {"bad": np.nan},
        {"bad": np.inf},
        {"bad": object()},
    ],
)
def test_hybrid_only_case_rejects_non_json_decision_trace_values(
    invalid_trace: dict[object, object],
) -> None:
    with pytest.raises(ValueError, match="decision_trace"):
        _hybrid_only_case(
            "p1",
            0,
            3,
            2,
            1,
            0.25,
            0.75,
            ("COTRAVEL",),
            "2025-01",
            decision_trace=invalid_trace,  # type: ignore[arg-type]
        )


def test_decision_trace_jsonable_round_trips_and_is_detached() -> None:
    case = _hybrid_only_case(
        "p1",
        0,
        3,
        2,
        1,
        0.25,
        0.75,
        ("COTRAVEL",),
        "2025-01",
        decision_trace={
            "evidence": {"candidate_ids": ["e1", "e2"], "weights": (0.25, 0.75)},
            "selected": True,
            "note": None,
        },
    )

    jsonable = case.decision_trace_jsonable()
    round_tripped = json.loads(json.dumps(jsonable, sort_keys=True))

    assert round_tripped == {
        "evidence": {
            "candidate_ids": ["e1", "e2"],
            "weights": [0.25, 0.75],
        },
        "note": None,
        "selected": True,
    }
    jsonable["evidence"]["candidate_ids"][0] = "changed"
    assert case.decision_trace["evidence"]["candidate_ids"][0] == "e1"


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


@pytest.mark.parametrize(
    ("field_name", "bad_ids"),
    [
        ("both_ids", frozenset({"not-shared"})),
        ("hybrid_only_ids", frozenset()),
        ("baseline_only_ids", frozenset()),
    ],
)
def test_direct_overlap_construction_rejects_contradictory_sets(
    field_name: str, bad_ids: frozenset[str]
) -> None:
    values = {
        "baseline_ids": frozenset({"baseline", "both"}),
        "hybrid_ids": frozenset({"hybrid", "both"}),
        "both_ids": frozenset({"both"}),
        "hybrid_only_ids": frozenset({"hybrid"}),
        "baseline_only_ids": frozenset({"baseline"}),
    }
    values[field_name] = bad_ids

    with pytest.raises(ValueError, match=rf"{field_name} is inconsistent"):
        RecoveryOverlap(**values)
