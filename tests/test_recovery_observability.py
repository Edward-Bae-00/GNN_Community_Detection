from __future__ import annotations

import json
from dataclasses import replace
from types import MappingProxyType

import numpy as np
import pandas as pd
import pytest

from gnn.explanation_narrative import MODEL_TAG, PROMPT_VERSION, render_template
from gnn.observability_artifact import (
    build_observability_artifact,
    build_observability_bundle,
    explain_representatives,
)
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
from gnn.recovery_bundle import RecoveryBundleError, RecoveryBundleWriter
from gnn.run_demo import _rank_fuse


class FakeExplanationEngine:
    def __init__(self, *, explanation_overrides=None):
        self.bind_calls = []
        self.blend_weight = 0.75
        self.explained_cases = []
        self.explanation_overrides = explanation_overrides or {}
        self.release_calls = []

    def bind_rank_reference(self, reference, row_bindings):
        self.bind_calls.append((reference, tuple(row_bindings)))
        self.blend_weight = float(reference.blend_weight)

    def observability_fingerprint_material(self):
        return {
            "graph_sha256": "fixture-graph",
            "model_state_sha256": "fixture-model",
            "rank_reference_fingerprint": "fixture-rank",
        }

    def release_snapshot(self, scoring_day):
        self.release_calls.append(pd.Timestamp(scoring_day))
        return True

    def relationship_categories(self, person_id, scoring_day):
        return ("COTRAVEL",)

    def community(self, person_id, scoring_day):
        day = pd.Timestamp(scoring_day).isoformat()
        edge_id = f"edge:{person_id}"
        return {
            "complete": True,
            "scoring_day": day,
            "component_id": f"component:{person_id}",
            "community_key": f"community:{day}:{person_id}",
            "nodes": [
                {
                    "node_id": person_id,
                    "target": True,
                    "caught_before_snapshot": False,
                    "caught_label_available_time": None,
                },
                {
                    "node_id": f"support:{person_id}",
                    "target": False,
                    "caught_before_snapshot": False,
                    "caught_label_available_time": None,
                },
            ],
            "nodes_by_id": {
                person_id: {
                    "node_id": person_id,
                    "target": True,
                    "caught_before_snapshot": False,
                    "caught_label_available_time": None,
                },
                f"support:{person_id}": {
                    "node_id": f"support:{person_id}",
                    "target": False,
                    "caught_before_snapshot": False,
                    "caught_label_available_time": None,
                },
            },
            "edges": [
                {
                    "edge_id": edge_id,
                    "u": person_id,
                    "v": f"support:{person_id}",
                    "edge_type": "COTRAVEL",
                    "source_row_ids": [f"row:{person_id}"],
                    "observations": [
                        {
                            "source_row_id": f"row:{person_id}",
                            "available_time": (
                                pd.Timestamp(scoring_day)
                                - pd.Timedelta(seconds=1)
                            ).isoformat(),
                        }
                    ],
                }
            ],
            "base_source_row_ids": [f"row:{person_id}"],
            "provenance_expansions": [],
        }

    def explain_case(self, case):
        self.explained_cases.append(case)
        community = self.community(case.person_id, case.anchor.scoring_day)
        edge = community["edges"][0]
        trace = case.decision_trace
        baseline_percentile = float(
            trace.get("baseline_percentile", case.baseline_percentile)
        )
        seed0_gnn_percentile = float(
            trace.get("seed0_gnn_percentile", case.gnn_percentile)
        )
        baseline_term = float(
            trace.get(
                "baseline_weighted_term",
                (1.0 - self.blend_weight) * baseline_percentile,
            )
        )
        gnn_term = float(
            trace.get(
                "seed0_gnn_weighted_term",
                self.blend_weight * seed0_gnn_percentile,
            )
        )
        explanation = {
            "case_id": f"case:{case.person_id}",
            "person_id": case.person_id,
            "event_id": case.anchor.event_id,
            "scoring_day": case.anchor.scoring_day.isoformat(),
            "decision_trace": case.decision_trace_jsonable(),
            "attributions": {
                "top_local_nodes": [
                    {
                        "node_id": case.person_id,
                        "explainer_median": 0.75,
                    }
                ],
                "top_edges": [
                    {
                        "edge_id": edge["edge_id"],
                        "u": edge["u"],
                        "v": edge["v"],
                        "edge_type": edge["edge_type"],
                        "source_row_ids": list(edge["source_row_ids"]),
                        "explainer_median": 0.5,
                        "explainer_q1": 0.4,
                        "explainer_q3": 0.6,
                        "selection_frequency": 1.0,
                    }
                ],
                "top_features": [],
            },
            "decision_ledger": {
                "component_pooling": {
                    "top_members_by_absolute_contribution": [
                        {
                            "person_id": case.person_id,
                            "pooled_logit_contribution": 0.25,
                        }
                    ],
                },
                "rank_fusion": {
                    "daily_budget": int(trace.get("daily_budget", 5)),
                    "blend_weight": self.blend_weight,
                    "baseline_percentile": baseline_percentile,
                    "seed0_gnn_percentile": seed0_gnn_percentile,
                    "baseline_weighted_term": baseline_term,
                    "seed0_gnn_weighted_term": gnn_term,
                    "hybrid_score": float(
                        trace.get("seed0_hybrid_score", baseline_term + gnn_term)
                    ),
                },
            },
            "factors": [],
            "community": community,
            "flow_stages": [
                {"stage_id": "first_hop", "emphasized_edge_ids": []},
                {"stage_id": "second_hop", "emphasized_edge_ids": []},
                {"stage_id": "component_pool", "emphasized_edge_ids": []},
                {"stage_id": "rank_fusion", "emphasized_edge_ids": []},
            ],
            "stable_factor_status": "unstable",
            "stability": {"stable_factor_count": 0},
            "faithfulness": {"points": []},
            "parity": {
                "production_seed0_probability": True,
                "pooled_logit_decomposition": True,
                "frozen_percentile": True,
                "frozen_daily_hybrid_rank": True,
            },
            "evidence_boundary": {
                "snapshot": case.anchor.scoring_day.isoformat(),
                "edge_rule": "available_time < snapshot",
                "caught_rule": "label_available_time_utc < snapshot",
            },
        }
        explanation.update(self.explanation_overrides)
        return explanation


def _fake_narrative(packet):
    narrative = render_template(packet)
    narrative["source"] = "llm"
    narrative["model"] = MODEL_TAG
    return narrative


def _artifact_fixture(**overrides):
    values = {
        "pool": pd.DataFrame(
            {
                "event_id": ["e1", "e2", "e3", "e4", "e5", "e6", "e7", "e8"],
                "primary_person_id": ["p1", "p1", "p2", "p3", "p4", "p5", "p6", "p7"],
                "t": pd.to_datetime(
                    [
                        "2025-01-01T01:00:00Z",
                        "2025-01-01T02:00:00Z",
                        "2025-01-01T03:00:00Z",
                        "2025-01-01T04:00:00Z",
                        "2025-01-01T05:00:00Z",
                        "2025-01-01T06:00:00Z",
                        "2025-01-01T07:00:00Z",
                        "2025-01-02T01:00:00Z",
                    ]
                ),
                "hidden": [True] * 8,
            },
            index=[10, 20, 30, 40, 50, 60, 70, 80],
        ),
        "baseline_raw": np.array([0.99, 0.01, 0.9, 0.8, 0.7, 0.6, 0.1, 0.5]),
        "seed0_gnn_raw": np.array([0.0, 0.01, 0.5, 0.6, 0.7, 0.8, 1.0, 0.5]),
        "blend_weight": 0.75,
        "caught_times": {},
        "gnn_arm": "sage",
        "surrounding_seeds": (0, 1, 2),
        "explanation_engine": FakeExplanationEngine(),
        "explanation_limit": None,
        "inspections_per_day": 5,
        "seed_level_unique_person_recovery": {
            "inspections_per_day": 5,
            "common_validation_tuned_fusion_weight": 0.75,
            "seeds": {
                str(seed): {
                    "baseline_unique_people_recovered": 6,
                    "hybrid_unique_people_recovered": 6,
                    "net_unique_people_gain": 0,
                }
                for seed in (0, 1, 2)
            },
            "mean": {
                "baseline_unique_people_recovered": 6.0,
                "hybrid_unique_people_recovered": 6.0,
                "net_unique_people_gain": 0.0,
            },
            "population_sd": {
                "baseline_unique_people_recovered": 0.0,
                "hybrid_unique_people_recovered": 0.0,
                "net_unique_people_gain": 0.0,
            },
            "score_averaged_ensemble": {
                "baseline_unique_people_recovered": 6,
                "hybrid_unique_people_recovered": 6,
                "net_unique_people_gain": 0,
            },
        },
        "narrative_builder": _fake_narrative,
    }
    values.update(overrides)
    return values


def _bundle_fixture(tmp_path, **overrides):
    values = _artifact_fixture()
    values.update(
        {
            "staging_root": tmp_path / ".recovery-stage",
            "final_root": tmp_path / "recovery",
            "corpus_identity": "fixture-v9",
        }
    )
    values.update(overrides)
    return values


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


def test_observability_artifact_v2_has_both_exclusive_cohorts_and_complete_coverage() -> None:
    engine = FakeExplanationEngine()

    artifact = build_observability_artifact(
        **_artifact_fixture(explanation_engine=engine)
    )

    assert artifact["schema_version"] == "2.0"
    assert artifact["policy"] == {
        "observability_seed": 0,
        "gnn_arm": "sage",
        "surrounding_results_seeds": [0, 1, 2],
        "inspections_per_day": 5,
        "hybrid_blend_weight": 0.75,
        "percentile_reference_id": artifact["policy"][
            "percentile_reference_id"
        ],
    }
    assert artifact["summary"] == {
        "overlap_ids_available": True,
        "baseline_recovered": 6,
        "recovered_by_both": 5,
        "hybrid_only_recovered": 1,
        "baseline_only_recovered": 1,
        "hybrid_total": 6,
        "net_gain": 0,
        "seed_level_unique_person_recovery": _artifact_fixture()[
            "seed_level_unique_person_recovery"
        ],
    }
    assert artifact["coverage"] == {
        "hybrid_only_count": 1,
        "baseline_only_count": 1,
        "attempted_count": 1,
        "explained_count": 1,
        "llm_validated_count": 1,
        "failed_count": 0,
        "complete": True,
    }
    assert [case["person_id"] for case in artifact["cohorts"]["hybrid_only"]] == [
        "p6"
    ]
    assert [case["person_id"] for case in artifact["cohorts"]["baseline_only"]] == [
        "p1"
    ]
    baseline_case = artifact["cohorts"]["baseline_only"][0]
    assert baseline_case["cohort"] == "baseline_only"
    assert baseline_case["event_id"] == "e1"
    assert baseline_case["baseline_rank"] == 1
    assert baseline_case["seed0_hybrid_rank"] > 5
    assert "explanation" not in baseline_case
    assert [case["person_id"] for case in artifact["explanations"]] == ["p6"]
    assert all("community" not in item for item in artifact["explanations"])
    assert set(artifact["communities"]) == {
        artifact["cohorts"]["hybrid_only"][0]["community_key"],
        artifact["cohorts"]["baseline_only"][0]["community_key"],
    }
    for cohort in ("hybrid_only", "baseline_only"):
        case = artifact["cohorts"][cohort][0]
        assert artifact["communities"][case["community_key"]]["complete"] is True
    assert artifact["explanations"][0]["community_key"] == artifact["cohorts"][
        "hybrid_only"
    ][0]["community_key"]
    assert artifact["generation_diagnostics"] == {"failed_attempts": []}
    json.dumps(artifact, sort_keys=True, allow_nan=False)


def test_observability_binds_complete_positional_identity_day_reference_once() -> None:
    engine = FakeExplanationEngine()

    artifact = build_observability_artifact(
        **_artifact_fixture(explanation_engine=engine)
    )

    assert artifact["coverage"]["explained_count"] == 1
    assert len(engine.bind_calls) == 1
    reference, row_bindings = engine.bind_calls[0]
    assert reference.event_ids == ("e1", "e2", "e3", "e4", "e5", "e6", "e7", "e8")
    assert row_bindings == (
        (0, "p1", pd.Timestamp("2025-01-01T00:00:00Z")),
        (1, "p1", pd.Timestamp("2025-01-01T00:00:00Z")),
        (2, "p2", pd.Timestamp("2025-01-01T00:00:00Z")),
        (3, "p3", pd.Timestamp("2025-01-01T00:00:00Z")),
        (4, "p4", pd.Timestamp("2025-01-01T00:00:00Z")),
        (5, "p5", pd.Timestamp("2025-01-01T00:00:00Z")),
        (6, "p6", pd.Timestamp("2025-01-01T00:00:00Z")),
        (7, "p7", pd.Timestamp("2025-01-02T00:00:00Z")),
    )
    case = engine.explained_cases[0]
    assert case.same_day_person_row_indices == (6,)
    assert set(case.baseline_candidate_row_indices) == set(range(7))
    assert set(case.hybrid_candidate_row_indices) == set(range(7))


def test_observability_rejects_any_budget_other_than_fixed_demo_k5() -> None:
    with pytest.raises(ValueError, match="exactly 5"):
        build_observability_artifact(
            **_artifact_fixture(inspections_per_day=25)
        )


def test_observability_fails_before_explaining_without_community_capability() -> None:
    engine = FakeExplanationEngine()
    engine.community = None

    with pytest.raises(ValueError, match="community"):
        build_observability_artifact(
            **_artifact_fixture(explanation_engine=engine)
        )

    assert engine.explained_cases == []


def test_schema2_cases_resolve_to_deduplicated_top_level_communities() -> None:
    artifact = build_observability_artifact(**_artifact_fixture())

    all_cases = [
        *artifact["cohorts"]["hybrid_only"],
        *artifact["cohorts"]["baseline_only"],
    ]
    assert all(case["community_key"] in artifact["communities"] for case in all_cases)
    assert all(
        explanation["community_key"] in artifact["communities"]
        and "community" not in explanation
        for explanation in artifact["explanations"]
    )


def test_streaming_bundle_returns_only_compact_prepackaged_manifest(tmp_path) -> None:
    artifact = build_observability_bundle(
        **_bundle_fixture(
            tmp_path,
            recovery_run_identity={"checkpoint_id": "checkpoint-abc"},
        )
    )

    assert artifact["schema_version"] == "2.0"
    assert artifact["bundle_id"]
    assert artifact["sidecar_base"].startswith("recovery/bundles/")
    assert set(artifact["case_index"]) == {"case:p1", "case:p6"}
    assert set(artifact["community_index"])
    assert "communities" not in artifact
    assert "explanations" not in artifact
    assert not (tmp_path / ".recovery-stage").exists()
    fingerprint = artifact["run_identity"]
    assert fingerprint == {"checkpoint_id": "checkpoint-abc"}
    assert artifact["recovery_policy"] == {
        "observability_seed": 0,
        "gnn_arm": "sage",
        "surrounding_seeds": [0, 1, 2],
        "inspections_per_day": 5,
        "gnnexplainer_restart_seeds": [0, 1, 2],
        "gnnexplainer_epochs": 150,
        "narrative_model": MODEL_TAG,
        "narrative_prompt_version": PROMPT_VERSION,
    }
    json.dumps(artifact, sort_keys=True, allow_nan=False)


def test_streaming_bundle_defers_case_construction_failure_and_retries_last(
    tmp_path,
) -> None:
    events = []

    class TransientConstructionEngine(FakeExplanationEngine):
        def __init__(self):
            super().__init__()
            self.failed = False

        def relationship_categories(self, person_id, scoring_day):
            events.append(("categories", person_id))
            if person_id == "p6" and not self.failed:
                self.failed = True
                raise RuntimeError("transient category lookup")
            return super().relationship_categories(person_id, scoring_day)

        def community(self, person_id, scoring_day):
            events.append(("community", person_id))
            return super().community(person_id, scoring_day)

    artifact = build_observability_bundle(
        **_bundle_fixture(
            tmp_path,
            explanation_engine=TransientConstructionEngine(),
        )
    )

    assert artifact["coverage"]["complete"] is True
    assert events.count(("categories", "p6")) == 2
    assert events.index(("community", "p1")) < len(events) - 1


def test_legacy_materialization_rejects_unbounded_community_evidence() -> None:
    engine = FakeExplanationEngine()

    def giant_community(person_id, scoring_day):
        community = FakeExplanationEngine.community(engine, person_id, scoring_day)
        community["nodes"] = [
            {"node_id": f"node:{index}"} for index in range(10_001)
        ]
        return community

    engine.community = giant_community

    with pytest.raises(ValueError, match="legacy materialization limit"):
        build_observability_artifact(
            **_artifact_fixture(explanation_engine=engine)
        )


def test_streaming_resume_skips_completed_explain_and_narrate_work(tmp_path) -> None:
    class InterruptOnceEngine(FakeExplanationEngine):
        def __init__(self):
            super().__init__()
            self.fail_baseline_once = True

        def community(self, person_id, scoring_day):
            if person_id == "p1" and self.fail_baseline_once:
                self.fail_baseline_once = False
                raise RuntimeError("planned interruption")
            return super().community(person_id, scoring_day)

    engine = InterruptOnceEngine()
    narrative_calls = []

    def recording_narrative(packet):
        narrative_calls.append(packet["snapshot"])
        return _fake_narrative(packet)

    kwargs = _bundle_fixture(
        tmp_path,
        explanation_engine=engine,
        narrative_builder=recording_narrative,
    )
    artifact = build_observability_bundle(**kwargs)

    assert artifact["coverage"]["complete"] is True
    assert [case.person_id for case in engine.explained_cases] == ["p6"]
    assert len(narrative_calls) == 1
    assert engine.release_calls


def test_streaming_two_targets_reuse_one_immutable_base_community(tmp_path) -> None:
    pool = _artifact_fixture()["pool"].copy()
    pool["t"] = pd.Timestamp("2025-01-01T01:00:00Z")

    class SharedCommunityEngine(FakeExplanationEngine):
        def community(self, person_id, scoring_day):
            day = pd.Timestamp(scoring_day).isoformat()
            return {
                "complete": True,
                "scoring_day": day,
                "component_id": "component:shared",
                "community_key": "community:shared",
                "nodes": [
                    {
                        "node_id": "shared",
                        "caught_before_snapshot": False,
                        "caught_label_available_time": None,
                    },
                    {
                        "node_id": "support:shared",
                        "caught_before_snapshot": False,
                        "caught_label_available_time": None,
                    }
                ],
                "nodes_by_id": {},
                "edges": [
                    {
                        "edge_id": "edge:shared",
                        "u": "shared",
                        "v": "support:shared",
                        "edge_type": "COTRAVEL",
                        "source_row_ids": ["row:shared"],
                        "observations": [
                            {
                                "source_row_id": "row:shared",
                                "available_time": (
                                    pd.Timestamp(scoring_day)
                                    - pd.Timedelta(seconds=1)
                                ).isoformat(),
                            }
                        ],
                    }
                ],
                "base_source_row_ids": ["row:shared"],
                "provenance_expansions": [],
            }

    class CountingWriter(RecoveryBundleWriter):
        community_writes = 0

        def write_community(self, community):
            type(self).community_writes += 1
            return super().write_community(community)

    recovery = _artifact_fixture()["seed_level_unique_person_recovery"]
    for record in recovery["seeds"].values():
        record["baseline_unique_people_recovered"] = 5
        record["hybrid_unique_people_recovered"] = 5
    recovery["mean"]["baseline_unique_people_recovered"] = 5.0
    recovery["mean"]["hybrid_unique_people_recovered"] = 5.0
    recovery["score_averaged_ensemble"][
        "baseline_unique_people_recovered"
    ] = 5
    recovery["score_averaged_ensemble"][
        "hybrid_unique_people_recovered"
    ] = 5

    artifact = build_observability_bundle(
        **_bundle_fixture(
            tmp_path,
            pool=pool,
            baseline_raw=np.array([1.0, 0.01, 0.9, 0.8, 0.7, 0.6, 0.1, 0.05]),
            seed0_gnn_raw=np.array([0.0, 0.01, 0.1, 0.6, 0.7, 0.8, 1.0, 0.9]),
            explanation_engine=SharedCommunityEngine(),
            writer_factory=CountingWriter,
            seed_level_unique_person_recovery=recovery,
        )
    )

    assert artifact["coverage"]["hybrid_only_count"] == 2
    assert CountingWriter.community_writes == 1
    assert set(artifact["community_index"]) == {"community:shared"}


def test_failed_new_streaming_run_preserves_prior_published_bundle(tmp_path) -> None:
    first = build_observability_bundle(**_bundle_fixture(tmp_path))
    current = tmp_path / "recovery" / "current.json"
    prior_pointer = current.read_bytes()
    prior_manifest = (
        tmp_path / "recovery" / first["bundle_path"] / "manifest.json"
    ).read_bytes()

    def fail_narrative(packet):
        raise RuntimeError("planned narrative failure")

    with pytest.raises(RecoveryBundleError, match="failures prevent publication"):
        build_observability_bundle(
            **_bundle_fixture(
                tmp_path,
                corpus_identity="fixture-v9-new-run",
                narrative_builder=fail_narrative,
            )
        )

    assert current.read_bytes() == prior_pointer
    assert (
        tmp_path / "recovery" / first["bundle_path"] / "manifest.json"
    ).read_bytes() == prior_manifest


def test_conflicting_complete_payloads_for_one_engine_community_key_fail() -> None:
    class ConflictingCommunityEngine(FakeExplanationEngine):
        def community(self, person_id, scoring_day):
            community = super().community(person_id, scoring_day)
            community["community_key"] = "community:conflict"
            return community

    with pytest.raises(ValueError, match="conflicting payloads"):
        build_observability_artifact(
            **_artifact_fixture(explanation_engine=ConflictingCommunityEngine())
        )


def test_seed_level_unique_person_summary_must_match_fixed_policy_and_exact_math() -> None:
    bad = _artifact_fixture()["seed_level_unique_person_recovery"] | {
        "common_validation_tuned_fusion_weight": 0.5
    }

    with pytest.raises(ValueError, match="fusion weight"):
        build_observability_artifact(
            **_artifact_fixture(seed_level_unique_person_recovery=bad)
        )


@pytest.mark.parametrize(
    ("surrounding_seeds", "gnn_arm"),
    [((1, 2), "sage"), ((0, 1, 2), "rgcn")],
)
def test_observability_fails_closed_without_exact_seed_zero_sage_scope(
    surrounding_seeds: tuple[int, ...], gnn_arm: str
) -> None:
    with pytest.raises(
        ValueError,
        match="requires the surrounding three-seed GraphSAGE run",
    ):
        build_observability_artifact(
            **_artifact_fixture(
                surrounding_seeds=surrounding_seeds,
                gnn_arm=gnn_arm,
            )
        )


@pytest.mark.parametrize(
    "explanation_overrides",
    [
        {
            "parity": {
                "production_seed0_probability": True,
                "pooled_logit_decomposition": True,
                "frozen_percentile": True,
                "frozen_daily_hybrid_rank": False,
            }
        },
        {
            "community": {
                "complete": False,
                "nodes": [],
                "edges": [],
                "provenance_expansions": [],
            }
        },
        {
            "community": {
                "complete": True,
                "nodes": None,
                "edges": [],
                "provenance_expansions": [],
            }
        },
        {"person_id": "wrong-person"},
        {"false_negative_flag": True},
    ],
)
def test_invalid_detailed_explanations_prevent_artifact_publication(
    explanation_overrides: dict[str, object],
) -> None:
    engine = FakeExplanationEngine(
        explanation_overrides=explanation_overrides
    )

    with pytest.raises(ValueError, match="complete Hybrid-only explanation coverage"):
        build_observability_artifact(
            **_artifact_fixture(explanation_engine=engine)
        )


@pytest.mark.parametrize(
    "evidence_kind",
    ["edge", "caught", "empty_edge", "boundary", "provenance"],
)
def test_exact_at_snapshot_evidence_is_rejected_as_not_strictly_asof(
    evidence_kind: str,
) -> None:
    snapshot = "2025-01-01T00:00:00+00:00"
    community = {
        "complete": True,
        "nodes": [],
        "edges": [],
        "provenance_expansions": [],
    }
    overrides = {"community": community}
    if evidence_kind == "edge":
        community["edges"] = [
            {
                "edge_id": "pair-1:rel:0",
                "u": "p2",
                "v": "px",
                "edge_type": "COTRAVEL",
                "source_row_ids": ["r1"],
                "observations": [
                    {"source_row_id": "r1", "available_time": snapshot}
                ],
            }
        ]
    elif evidence_kind == "caught":
        community["nodes"] = [
            {
                "node_id": "px",
                "caught_before_snapshot": True,
                "caught_label_available_time": snapshot,
            }
        ]
    elif evidence_kind == "empty_edge":
        community["edges"] = [
            {
                "edge_id": "pair-1:rel:0",
                "u": "p2",
                "v": "px",
                "edge_type": "COTRAVEL",
                "source_row_ids": [],
                "observations": [],
            }
        ]
    elif evidence_kind == "boundary":
        overrides["evidence_boundary"] = {
            "snapshot": "2024-12-31T00:00:00+00:00",
            "edge_rule": "available_time < snapshot",
            "caught_rule": "label_available_time_utc < snapshot",
        }
    else:
        community["edges"] = [
            {
                "edge_id": "pair-1:rel:0",
                "u": "p2",
                "v": "px",
                "edge_type": "COTRAVEL",
                "source_row_ids": ["different-row"],
                "observations": [
                    {
                        "source_row_id": "r1",
                        "available_time": "2024-12-31T23:59:59+00:00",
                    }
                ],
            }
        ]
    engine = FakeExplanationEngine(
        explanation_overrides=overrides
    )

    with pytest.raises(ValueError, match="complete Hybrid-only explanation coverage"):
        build_observability_artifact(
            **_artifact_fixture(explanation_engine=engine)
        )


def test_ungrounded_narrative_is_rejected_despite_validated_flag() -> None:
    def invented_narrative(packet):
        return {
            "source": "deterministic_template",
            "model": None,
            "prompt_version": "v1",
            "summary": "In seed 0, invented person P-999 had rank 999.",
            "summary_source_refs": ["scope.observability_seed"],
            "claims": [],
            "validated": True,
        }

    with pytest.raises(ValueError, match="complete Hybrid-only explanation coverage"):
        build_observability_artifact(
            **_artifact_fixture(narrative_builder=invented_narrative)
        )


def test_narrative_builder_cannot_mutate_its_grounding_reference() -> None:
    def mutating_narrative(packet):
        packet["ranks"]["seed0_hybrid"] = 999
        return render_template(packet)

    with pytest.raises(ValueError, match="complete Hybrid-only explanation coverage"):
        build_observability_artifact(
            **_artifact_fixture(narrative_builder=mutating_narrative)
        )


def test_explanation_limit_counts_successes_not_failed_attempts() -> None:
    cases = [
        _hybrid_only_case(
            person_id,
            row_index,
            baseline_rank=3,
            gnn_rank=2,
            hybrid_rank=1,
            baseline_percentile=0.25,
            gnn_percentile=0.75,
            categories=("COTRAVEL",),
            period="2025-01",
            decision_trace={
                "baseline_rank": 3,
                "seed0_gnn_rank": 2,
                "seed0_hybrid_rank": 1,
            },
        )
        for row_index, person_id in enumerate(("fail", "success", "unattempted"))
    ]

    class FailThenExplain(FakeExplanationEngine):
        def explain_case(self, case):
            if case.person_id == "fail":
                self.explained_cases.append(case)
                raise ValueError("planned failure")
            return super().explain_case(case)

    engine = FailThenExplain()
    explanations, failures = explain_representatives(
        cases,
        engine,
        narrative_builder=_fake_narrative,
        limit=1,
    )

    assert [item["person_id"] for item in explanations] == ["success"]
    assert [item["person_id"] for item in failures] == ["fail"]
    assert [case.person_id for case in engine.explained_cases] == [
        "fail",
        "success",
    ]
