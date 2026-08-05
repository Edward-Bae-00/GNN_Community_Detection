from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from types import SimpleNamespace

from test_recovery_observability import _artifact_fixture

from gnn.observability_artifact import (
    _explain_case_with_narrative,
    _validate_schema3_evidence_boundary,
    build_observability_artifact,
    explain_case,
    validate_artifact_invariants,
)


REQUIRED_SCORE_FIELDS = {
    "baseline_raw",
    "baseline_percentile",
    "baseline_rank",
    "seed0_gnn_probability",
    "seed0_gnn_percentile",
    "seed0_gnn_rank",
    "seed0_hybrid_score",
    "seed0_hybrid_rank",
    "detail_status",
    "provenance",
    "run_identity",
}


def _schema3_fixture(**overrides):
    values = _artifact_fixture()
    engine = values["explanation_engine"]
    engine.schema3_test_adapter = True
    engine.schema3_preflight_adapter = lambda _person_id, _scoring_day: {
        "eligible": True,
        "status": "eligible",
        "node_count": 128,
        "edge_count": 256,
        "max_nodes": 128,
        "max_edges": 256,
        "reason_code": "test_adapter",
    }
    values.update(
        {
            "schema_version": "3.0",
            "hybrid_detail_limit": 20,
            "baseline_control_limit": 10,
            "corpus_identity": "fixture-corpus-v9",
            "recovery_run_identity": {
                "checkpoint_id": "fixture-checkpoint",
                "score_run_id": "fixture-score-run",
            },
        }
    )
    values.update(overrides)
    engine = values["explanation_engine"]
    engine.schema3_test_adapter = True
    engine.schema3_preflight_adapter = lambda _person_id, _scoring_day: {
        "eligible": True,
        "status": "eligible",
        "node_count": 128,
        "edge_count": 256,
        "max_nodes": 128,
        "max_edges": 256,
        "reason_code": "test_adapter",
    }
    return values


def test_schema3_emits_exact_three_cohort_algebra_and_score_semantics():
    artifact = build_observability_artifact(**_schema3_fixture())

    assert artifact["schema_version"] == "3.0"
    assert set(artifact["cohorts"]) == {
        "hybrid_only",
        "baseline_only",
        "recovered_by_both",
    }
    summary = artifact["summary"]
    assert summary["baseline_recovered"] == (
        summary["recovered_by_both"] + summary["baseline_only_recovered"]
    )
    assert summary["hybrid_total"] == (
        summary["recovered_by_both"] + summary["hybrid_only_recovered"]
    )
    assert summary["net_gain"] == (
        summary["hybrid_total"] - summary["baseline_recovered"]
    )
    assert {
        record["recovery_anchor_arm"]
        for record in artifact["cohorts"]["hybrid_only"]
    } <= {"hybrid_seed0"}

    records = [record for cohort in artifact["cohorts"].values() for record in cohort]
    assert records
    assert all(REQUIRED_SCORE_FIELDS <= record.keys() for record in records)
    assert artifact["policy"]["hybrid_score_semantics"] == "percentile_fusion_not_probability"
    assert all(record["seed0_hybrid_score"] != record["seed0_gnn_probability"]
               or record["seed0_hybrid_score"] == 0.0
               for record in records)
    assert all(record["run_identity"] == artifact["run_identity"] for record in records)
    assert all(record["provenance"]["corpus_identity"] == "fixture-corpus-v9"
               for record in records)
    assert validate_artifact_invariants(artifact) is artifact
    json.dumps(artifact, sort_keys=True, allow_nan=False)


def test_schema3_builds_both_summary_when_arm_anchors_are_on_different_days():
    values = _schema3_fixture(
        pool=pd.DataFrame(
            {
                "event_id": ["e1", "e2", "e3", "e4", "e5", "e6", "e7"],
                "primary_person_id": ["p1", "p2", "p3", "p4", "p5", "p6", "p1"],
                "t": [
                    "2025-01-01T01:00:00Z",
                    "2025-01-01T02:00:00Z",
                    "2025-01-01T03:00:00Z",
                    "2025-01-01T04:00:00Z",
                    "2025-01-01T05:00:00Z",
                    "2025-01-01T06:00:00Z",
                    "2025-01-02T01:00:00Z",
                ],
                "hidden": [True] * 7,
            }
        ),
        baseline_raw=np.array([1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.1]),
        seed0_gnn_raw=np.array([0.0, 1.0, 0.9, 0.8, 0.7, 0.6, 0.2]),
        hybrid_detail_limit=0,
        baseline_control_limit=0,
        seed_level_unique_person_recovery={
            "inspections_per_day": 5,
            "common_validation_tuned_fusion_weight": 0.75,
            "seeds": {
                str(seed): {
                    "baseline_unique_people_recovered": 5,
                    "hybrid_unique_people_recovered": 6,
                    "net_unique_people_gain": 1,
                }
                for seed in (0, 1, 2)
            },
            "mean": {
                "baseline_unique_people_recovered": 5.0,
                "hybrid_unique_people_recovered": 6.0,
                "net_unique_people_gain": 1.0,
            },
            "population_sd": {
                "baseline_unique_people_recovered": 0.0,
                "hybrid_unique_people_recovered": 0.0,
                "net_unique_people_gain": 0.0,
            },
            "score_averaged_ensemble": {
                "baseline_unique_people_recovered": 5,
                "hybrid_unique_people_recovered": 6,
                "net_unique_people_gain": 1,
            },
        },
    )

    artifact = build_observability_artifact(**values)

    assert artifact["summary"]["recovered_by_both"] == 5
    assert len(artifact["cohorts"]["recovered_by_both"]) == 5
    assert validate_artifact_invariants(artifact) is artifact


def test_schema3_freezes_20_10_selection_and_keeps_failed_id_without_replacement():
    engine = _artifact_fixture()["explanation_engine"]
    original = engine.explain_case

    def fail_hybrid(case):
        if case.person_id == "p6":
            raise RuntimeError("fixture explainer failure")
        return original(case)

    engine.explain_case = fail_hybrid
    artifact = build_observability_artifact(**_schema3_fixture(
        explanation_engine=engine,
        hybrid_detail_limit=1,
        baseline_control_limit=1,
    ))

    hybrid = artifact["cohorts"]["hybrid_only"]
    selected = artifact["selection"]["selected_ids"]["hybrid_only"]
    assert selected == ["case:p6"]
    assert hybrid[0]["case_id"] == "case:p6"
    assert hybrid[0]["detail_status"] == "failed"
    assert artifact["coverage"]["hybrid_requested"] == 1
    assert artifact["coverage"]["hybrid_selected"] == 1
    assert artifact["coverage"]["hybrid_explained"] == 0
    assert artifact["coverage"]["shortfall"] == 1
    assert artifact["generation_diagnostics"]["failed_attempts"][0]["case_id"] == "case:p6"


def test_schema3_baseline_controls_are_community_only_and_target_local():
    engine = _artifact_fixture()["explanation_engine"]
    artifact = build_observability_artifact(**_schema3_fixture(
        explanation_engine=engine,
        hybrid_detail_limit=0,
        baseline_control_limit=1,
    ))

    baseline = artifact["cohorts"]["baseline_only"]
    assert baseline[0]["detail_kind"] == "community_control"
    assert baseline[0]["detail_status"] == "community_only"
    assert baseline[0]["target_person_id"] == baseline[0]["person_id"]
    assert engine.explained_cases == []
    for community in artifact["communities"].values():
        assert all("target" not in node for node in community["nodes"])
        assert "target_person_id" not in community


def test_schema3_uses_strict_shared_run_and_as_of_identity(monkeypatch):
    import gnn.observability_artifact as artifact_module

    observed = {}
    original = artifact_module.recovery_overlap

    def capture(baseline, hybrid, *, strict=False):
        observed["strict"] = strict
        observed["run_identity"] = (baseline.run_identity, hybrid.run_identity)
        observed["as_of_identity"] = (baseline.as_of_identity, hybrid.as_of_identity)
        return original(baseline, hybrid, strict=strict)

    monkeypatch.setattr(artifact_module, "recovery_overlap", capture)
    build_observability_artifact(**_schema3_fixture(hybrid_detail_limit=0))

    assert observed["strict"] is True
    assert observed["run_identity"][0] == observed["run_identity"][1]
    assert observed["as_of_identity"][0] == observed["as_of_identity"][1]


def test_schema2_default_remains_legacy_contract():
    artifact = build_observability_artifact(**_artifact_fixture())
    assert artifact["schema_version"] == "2.0"
    assert "recovered_by_both" not in artifact["cohorts"]


def test_schema3_rejects_conflicting_legacy_limit():
    with pytest.raises(ValueError, match="conflicting"):
        build_observability_artifact(**_schema3_fixture(
            explanation_limit=3,
            hybrid_detail_limit=2,
        ))


@pytest.mark.parametrize(
    "field,value",
    [
        ("snapshot", "2025-01-03T00:00:00+00:00"),
        ("edge_rule", "available_time <= snapshot"),
        ("caught_rule", "label_available_time_utc <= snapshot"),
    ],
)
def test_schema3_staged_evidence_boundary_is_revalidated(field, value):
    payload = {
        "scoring_day": "2025-01-02T00:00:00+00:00",
        "evidence_boundary": {
            "snapshot": "2025-01-02T00:00:00+00:00",
            "edge_rule": "available_time < snapshot",
            "caught_rule": "label_available_time_utc < snapshot",
        },
    }
    payload["evidence_boundary"][field] = value

    with pytest.raises(ValueError, match="evidence boundary"):
        _validate_schema3_evidence_boundary(
            payload,
            "2025-01-02T00:00:00+00:00",
            field_name="staged explanation",
        )


def test_schema3_accepts_engine_without_explain_case_when_no_hybrid_detail_is_requested():
    values = _schema3_fixture(hybrid_detail_limit=0)
    engine = values["explanation_engine"]

    class NoMethodEngine:
        bind_rank_reference = engine.bind_rank_reference
        relationship_categories = engine.relationship_categories
        community = engine.community
        release_snapshot = engine.release_snapshot
        observability_fingerprint_material = engine.observability_fingerprint_material
        schema3_preflight_adapter = staticmethod(engine.schema3_preflight_adapter)
        schema3_test_adapter = True

    values["explanation_engine"] = NoMethodEngine()
    artifact = build_observability_artifact(**values)
    assert artifact["coverage"]["hybrid_requested"] == 0


def test_seed0_engine_reaches_compose_case_explanation_adapter(monkeypatch):
    from test_sage_explainer import _explanation_fixture

    engine, _ = _explanation_fixture()
    observed = {}

    def compose(real_engine, case):
        observed["engine"] = real_engine
        observed["case"] = case
        return {"adapter": "reached"}

    import gnn.observability_artifact as artifact_module

    monkeypatch.setattr(artifact_module, "compose_case_explanation", compose)
    case = SimpleNamespace(person_id="target")
    result = explain_case(engine, case)
    assert result == {"adapter": "reached"}
    assert observed["engine"] is engine
    assert observed["case"] is case


def test_schema3_falls_back_to_deterministic_narrative_after_builder_failure():
    calls = []

    def failing_builder(_packet):
        calls.append("builder")
        raise RuntimeError("narrative service unavailable")

    instrumentation = []
    artifact = build_observability_artifact(
        **_schema3_fixture(
            narrative_builder=failing_builder,
            hybrid_detail_limit=1,
            baseline_control_limit=0,
            instrumentation=lambda stage, fields: instrumentation.append(
                (stage, fields)
            ),
        )
    )
    assert calls == ["builder"]
    detail = next(iter(artifact["detail_index"].values()))
    assert detail["explanation"]["llm_narrative"]["source"] == "deterministic_template"
    assert artifact["coverage"]["narrative_fallback"] == 1
    assert artifact["coverage"]["narrative_failed"] == 0
    stages = [stage for stage, _fields in instrumentation]
    assert stages.index("selection_frozen") < stages.index("hybrid_explanations_start")


def test_schema3_fingerprint_contains_engine_and_frozen_selection_material():
    artifact = build_observability_artifact(**_schema3_fixture(hybrid_detail_limit=1))
    material = artifact["run_fingerprint"]["material"]
    assert material["checkpoint_id"] == "fixture-checkpoint"
    assert material["corpus_identity"] == "fixture-corpus-v9"
    assert material["graph_fingerprint"] == "fixture-graph"
    assert material["model_state_fingerprint"] == "fixture-model"
    assert material["rank_reference_identity"] == artifact["policy"]["percentile_reference_id"]
    assert material["eligible_ordered_prefix"]
    assert material["selected_ids"] == artifact["selection"]["selected_ids"]
    with pytest.raises(ValueError, match="conflicting corpus identity"):
        build_observability_artifact(
            **_schema3_fixture(
                recovery_run_identity={
                    "corpus_identity": "different-corpus",
                    "checkpoint_id": "fixture-checkpoint",
                }
            )
        )


def test_schema3_validator_rejects_score_status_and_baseline_detail_mutations():
    artifact = build_observability_artifact(**_schema3_fixture(hybrid_detail_limit=1))

    mutated = json.loads(json.dumps(artifact))
    mutated["cohorts"]["hybrid_only"][0]["baseline_percentile"] = 1.5
    with pytest.raises(ValueError, match="percentile"):
        validate_artifact_invariants(mutated)

    mutated = json.loads(json.dumps(artifact))
    mutated["cohorts"]["hybrid_only"][0]["detail_status"] = "available"
    mutated["detail_index"] = {}
    with pytest.raises(ValueError, match="detail_status"):
        validate_artifact_invariants(mutated)

    mutated = json.loads(json.dumps(artifact))
    baseline_id = artifact["selection"]["selected_ids"]["baseline_only"][0]
    mutated["community_index"][baseline_id]["explanation"] = {"forbidden": True}
    with pytest.raises(ValueError, match="Baseline"):
        validate_artifact_invariants(mutated)


def test_schema3_validator_scans_expansion_nodes_for_shared_targets():
    artifact = build_observability_artifact(**_schema3_fixture(hybrid_detail_limit=0))
    community = next(iter(artifact["communities"].values()))
    community["provenance_expansions"] = [
        {"nodes": [{"node_id": "leaked", "target": True}]}
    ]
    with pytest.raises(ValueError, match="target markers"):
        validate_artifact_invariants(artifact)


def test_schema3_maps_exact_oversized_preflight_to_community_only_summary(monkeypatch):
    import gnn.observability_artifact as artifact_module

    values = _schema3_fixture(hybrid_detail_limit=1, baseline_control_limit=0)
    engine = values["explanation_engine"]
    del engine.schema3_preflight_adapter
    monkeypatch.setattr(
        artifact_module,
        "exact_explainability_eligibility",
        lambda *_args, **_kwargs: {
            "eligible": False,
            "status": "community_only",
            "node_count": 129,
            "edge_count": 300,
            "max_nodes": 128,
            "max_edges": 256,
            "reason_code": "node_and_edge_limits_exceeded",
        },
    )
    artifact = build_observability_artifact(**values)
    record = artifact["cohorts"]["hybrid_only"][0]
    assert record["detail_status"] == "community_only"
    assert record["detail_kind"] == "community_control"
    assert record["selection_reason"] == "ineligible_preflight_structural_fallback"
    assert artifact["selection"]["preflight"][record["case_id"]]["status"] == "community_only"
    assert artifact["selection"]["preflight"][record["case_id"]]["node_count"] == 129
    assert artifact["coverage"]["oversized_hybrid"] == 1


def _oversized_fixture(monkeypatch, artifact_module, **overrides):
    values = _schema3_fixture(**overrides)
    del values["explanation_engine"].schema3_preflight_adapter
    monkeypatch.setattr(
        artifact_module,
        "exact_explainability_eligibility",
        lambda *_args, **_kwargs: {
            "eligible": False,
            "status": "community_only",
            "node_count": 129,
            "edge_count": 300,
            "max_nodes": 128,
            "max_edges": 256,
            "reason_code": "node_and_edge_limits_exceeded",
        },
    )
    return values


def test_schema3_oversized_hybrid_cases_receive_real_structural_fallback_evidence(
    monkeypatch,
):
    import gnn.observability_artifact as artifact_module

    artifact = build_observability_artifact(
        **_oversized_fixture(
            monkeypatch,
            artifact_module,
            hybrid_detail_limit=1,
            baseline_control_limit=0,
        )
    )

    record = artifact["cohorts"]["hybrid_only"][0]
    case_id = record["case_id"]
    assert record["detail_status"] == "community_only"
    assert record["detail_kind"] == "community_control"
    assert record["selection_reason"] == "ineligible_preflight_structural_fallback"
    assert record["community_key"]
    assert record["community_key"] in artifact["communities"]
    assert record["target_person_id"] == record["person_id"]
    assert record["failure_reason"] is None
    assert record["explanation_unavailable_reason"] == "node_and_edge_limits_exceeded"

    assert artifact["selection"]["hybrid_structural_fallback_ids"] == [case_id]
    detail = artifact["community_index"][case_id]
    assert detail["community_key"] == record["community_key"]
    assert detail["target_person_id"] == record["person_id"]
    assert detail["structural_evidence"]["complete"] is True
    assert "explanation" not in detail["structural_evidence"]
    assert "overlay_evidence" not in detail["structural_evidence"]

    coverage = artifact["coverage"]
    assert coverage["hybrid_structural_fallback"] == 1
    assert coverage["hybrid_explained"] == 0
    assert coverage["baseline_community"] == 0
    assert case_id in artifact["generation_diagnostics"]["attempted_ids"]
    assert validate_artifact_invariants(artifact) is artifact


def test_schema3_unselected_oversized_hybrid_cases_claim_no_evidence(monkeypatch):
    import gnn.observability_artifact as artifact_module

    artifact = build_observability_artifact(
        **_oversized_fixture(
            monkeypatch,
            artifact_module,
            hybrid_detail_limit=0,
            baseline_control_limit=0,
        )
    )

    record = artifact["cohorts"]["hybrid_only"][0]
    assert record["detail_status"] == "not_selected"
    assert record["detail_kind"] is None
    assert record["selection_reason"] == "ineligible_preflight"
    assert record["community_key"] is None
    assert artifact["community_index"] == {}
    assert artifact["selection"]["hybrid_structural_fallback_ids"] == []


def test_schema3_structural_adapter_is_gated_and_surfaces_extraction_errors(
    monkeypatch,
):
    import gnn.observability_artifact as artifact_module

    values = _schema3_fixture(hybrid_detail_limit=0, baseline_control_limit=1)
    engine = values["explanation_engine"]
    del engine.schema3_test_adapter
    monkeypatch.setattr(
        artifact_module,
        "exact_explainability_eligibility",
        lambda *_args, **_kwargs: {
            "eligible": True,
            "status": "eligible",
            "node_count": 4,
            "edge_count": 6,
            "max_nodes": 128,
            "max_edges": 256,
            "reason_code": "eligible",
        },
    )

    artifact = build_observability_artifact(**values)

    selected = artifact["selection"]["selected_ids"]["baseline_only"]
    assert len(selected) == 1
    record = next(
        item
        for item in artifact["cohorts"]["baseline_only"]
        if item["case_id"] == selected[0]
    )
    assert record["detail_status"] == "failed"
    assert record["failure_reason"]
    assert record["community_key"] is None
    assert artifact["community_index"] == {}
    assert artifact["coverage"]["baseline_community"] == 0
    assert artifact["generation_diagnostics"]["failed_attempts"][0]["case_id"] == (
        selected[0]
    )


def test_schema3_shortfall_totals_measure_against_requested_limits():
    artifact = build_observability_artifact(
        **_schema3_fixture(hybrid_detail_limit=20, baseline_control_limit=10)
    )

    coverage = artifact["coverage"]
    assert coverage["hybrid_requested"] == 20
    assert coverage["baseline_requested"] == 10
    assert coverage["hybrid_candidates"] < 20
    assert coverage["baseline_candidates"] < 10
    assert coverage["hybrid_shortfall"] == 20 - coverage["hybrid_explained"]
    assert coverage["baseline_shortfall"] == 10 - coverage["baseline_community"]
    assert coverage["shortfall"] == (
        coverage["hybrid_shortfall"] + coverage["baseline_shortfall"]
    )
    assert coverage["shortfall"] > 0
    assert "insufficient_hybrid_candidates" in coverage["shortfall_reasons"]
    assert "insufficient_baseline_candidates" in coverage["shortfall_reasons"]

    mutated = json.loads(json.dumps(artifact))
    mutated["coverage"]["shortfall"] = 0
    with pytest.raises(ValueError, match="shortfall"):
        validate_artifact_invariants(mutated)


def test_schema3_fingerprint_is_bound_to_published_selection_and_limits():
    artifact = build_observability_artifact(**_schema3_fixture(hybrid_detail_limit=1))

    mutated = json.loads(json.dumps(artifact))
    case_id = next(iter(mutated["selection"]["preflight"]))
    assert mutated["selection"]["preflight"][case_id]["node_count"] != 7
    mutated["selection"]["preflight"][case_id]["node_count"] = 7
    with pytest.raises(ValueError, match="fingerprint"):
        validate_artifact_invariants(mutated)

    mutated = json.loads(json.dumps(artifact))
    mutated["coverage"]["hybrid_requested"] = 99
    mutated["coverage"]["hybrid_shortfall"] = 99 - mutated["coverage"]["hybrid_explained"]
    mutated["coverage"]["shortfall"] = (
        mutated["coverage"]["hybrid_shortfall"]
        + mutated["coverage"]["baseline_shortfall"]
    )
    with pytest.raises(ValueError, match="fingerprint"):
        validate_artifact_invariants(mutated)

    mutated = json.loads(json.dumps(artifact))
    mutated["selection"]["explainer_input_policy"]["max_nodes"] = 9999
    with pytest.raises(ValueError, match="fingerprint does not bind"):
        validate_artifact_invariants(mutated)


@pytest.mark.parametrize(
    "field",
    ["hybrid_selected", "baseline_selected", "failed_count"],
)
def test_schema3_validator_reconciles_published_coverage_counters(field):
    artifact = build_observability_artifact(**_schema3_fixture(hybrid_detail_limit=1))
    artifact["coverage"][field] = 999

    with pytest.raises(ValueError, match="coverage|counter"):
        validate_artifact_invariants(artifact)


def test_schema3_test_adapter_is_rejected_without_explicit_test_flag(monkeypatch):
    import gnn.observability_artifact as artifact_module

    values = _schema3_fixture(hybrid_detail_limit=0)
    engine = values["explanation_engine"]
    del engine.schema3_test_adapter
    called = []

    def exact(*_args, **_kwargs):
        called.append(True)
        return {
            "eligible": True,
            "status": "eligible",
            "node_count": 128,
            "edge_count": 256,
            "max_nodes": 128,
            "max_edges": 256,
            "reason_code": "eligible",
        }

    monkeypatch.setattr(artifact_module, "exact_explainability_eligibility", exact)
    build_observability_artifact(**values)
    assert called


def test_schema3_fingerprint_is_authenticated_and_nested_targets_are_rejected():
    artifact = build_observability_artifact(**_schema3_fixture(hybrid_detail_limit=0))
    mutated = json.loads(json.dumps(artifact))
    mutated["run_fingerprint"]["fingerprint"] = "schema3:sha256:forged"
    with pytest.raises(ValueError, match="fingerprint"):
        validate_artifact_invariants(mutated)

    mutated = json.loads(json.dumps(artifact))
    community = next(iter(mutated["communities"].values()))
    community["nested"] = {"nodes": [{"node_id": "nested", "target": True}]}
    with pytest.raises(ValueError, match="target markers"):
        validate_artifact_invariants(mutated)


def test_schema3_coverage_and_catalog_counters_must_reconcile():
    artifact = build_observability_artifact(**_schema3_fixture(hybrid_detail_limit=1))
    mutated = json.loads(json.dumps(artifact))
    mutated["coverage"]["hybrid_explained"] += 1
    with pytest.raises(ValueError, match="coverage"):
        validate_artifact_invariants(mutated)

    mutated = json.loads(json.dumps(artifact))
    case_id = next(
        record["case_id"] for record in mutated["cohorts"]["hybrid_only"]
    )
    mutated["catalog_index"][case_id]["cohort"] = "baseline_only"
    with pytest.raises(ValueError, match="catalog"):
        validate_artifact_invariants(mutated)


class _SnapshotCacheProbe:
    """Fixture engine wrapper that simulates the engine's day snapshot cache.

    ``Seed0ExplanationEngine`` caches one ``DaySnapshot`` per scoring day and
    only evicts it in ``release_snapshot``.  A full V9 run preflights one day
    per Hybrid candidate, so a producer that never releases holds every day's
    tensors at once.  This probe records the high-water mark so that leak is a
    test failure rather than an out-of-memory kill during generation.
    """

    def __init__(self, engine):
        self._engine = engine
        self._cached = {}
        self.peak_cached_days = 0
        self.materialized_days = []
        self.schema3_test_adapter = True

    def __getattr__(self, name):
        return getattr(self._engine, name)

    def _materialize(self, scoring_day):
        day = pd.Timestamp(scoring_day)
        self._cached[day] = object()
        self.materialized_days.append(day)
        self.peak_cached_days = max(self.peak_cached_days, len(self._cached))

    @property
    def cached_snapshot_days(self):
        return tuple(sorted(self._cached))

    def schema3_preflight_adapter(self, _person_id, scoring_day):
        self._materialize(scoring_day)
        return {
            "eligible": True,
            "status": "eligible",
            "node_count": 128,
            "edge_count": 256,
            "max_nodes": 128,
            "max_edges": 256,
            "reason_code": "test_adapter",
        }

    def community(self, person_id, scoring_day):
        self._materialize(scoring_day)
        return self._engine.community(person_id, scoring_day)

    def release_snapshot(self, scoring_day):
        return self._cached.pop(pd.Timestamp(scoring_day), None) is not None


def _multi_day_schema3_fixture():
    """A schema-3 fixture whose recovery cohorts span two scoring days."""
    values = _schema3_fixture()
    values["pool"] = pd.DataFrame(
        {
            "event_id": [f"e{index}" for index in range(1, 13)],
            "primary_person_id": [f"p{index}" for index in range(1, 13)],
            "t": pd.to_datetime(
                [
                    "2025-01-01T01:00:00Z", "2025-01-01T02:00:00Z",
                    "2025-01-01T03:00:00Z", "2025-01-01T04:00:00Z",
                    "2025-01-01T05:00:00Z", "2025-01-01T06:00:00Z",
                    "2025-01-02T01:00:00Z", "2025-01-02T02:00:00Z",
                    "2025-01-02T03:00:00Z", "2025-01-02T04:00:00Z",
                    "2025-01-02T05:00:00Z", "2025-01-02T06:00:00Z",
                ]
            ),
            "hidden": [True] * 12,
        },
        index=list(range(10, 130, 10)),
    )
    values["baseline_raw"] = np.array(
        [0.99, 0.9, 0.8, 0.7, 0.2, 0.1, 0.99, 0.9, 0.8, 0.7, 0.2, 0.1]
    )
    values["seed0_gnn_raw"] = np.array(
        [0.0, 0.1, 0.2, 0.3, 0.95, 0.99, 0.0, 0.1, 0.2, 0.3, 0.95, 0.99]
    )
    recovered = {
        "baseline_unique_people_recovered": 10,
        "hybrid_unique_people_recovered": 10,
        "net_unique_people_gain": 0,
    }
    seed_recovery = values["seed_level_unique_person_recovery"]
    seed_recovery["seeds"] = {
        str(seed): dict(recovered) for seed in (0, 1, 2)
    }
    seed_recovery["mean"] = {key: float(value) for key, value in recovered.items()}
    seed_recovery["score_averaged_ensemble"] = dict(recovered)
    return values


def test_schema3_never_holds_more_than_one_day_snapshot_at_a_time():
    values = _multi_day_schema3_fixture()
    probe = _SnapshotCacheProbe(values["explanation_engine"])
    values["explanation_engine"] = probe

    artifact = build_observability_artifact(**values)

    # More than one distinct scoring day must actually be visited, otherwise a
    # producer that never releases would pass this bound by accident.
    assert len(set(probe.materialized_days)) > 1
    assert probe.peak_cached_days == 1
    assert probe.cached_snapshot_days == ()
    diagnostics = artifact["generation_diagnostics"]
    assert diagnostics["snapshot_cache_peak_days"] == 1
    assert diagnostics["snapshot_cache_residual_days"] == 0


def test_schema3_requires_an_engine_that_can_release_day_snapshots():
    values = _schema3_fixture()

    class NoReleaseEngine:
        schema3_test_adapter = True

        def __init__(self, engine):
            self._engine = engine

        def __getattr__(self, name):
            return getattr(self._engine, name)

        release_snapshot = None

    values["explanation_engine"] = NoReleaseEngine(values["explanation_engine"])
    with pytest.raises(ValueError, match="release_snapshot"):
        build_observability_artifact(**values)


def _schema3_bundle_fixture(tmp_path, **overrides):
    values = _multi_day_schema3_fixture()
    values.update(
        {
            "staging_root": tmp_path / ".recovery-stage",
            "final_root": tmp_path / "recovery",
        }
    )
    values.update(overrides)
    return values


def test_schema3_bundle_publishes_a_compact_prepackaged_manifest(tmp_path):
    from gnn.observability_artifact import build_observability_bundle

    manifest = build_observability_bundle(**_schema3_bundle_fixture(tmp_path))

    assert manifest["schema_version"] == "3.0"
    # The manifest is the published contract: lazy references only, never
    # inline communities or explanations.
    assert "communities" not in manifest
    assert isinstance(manifest["community_sidecar_index"], dict)
    for reference in manifest["detail_index"].values():
        assert {"path", "sha256", "bytes"} <= set(reference)
    for reference in manifest["community_index"].values():
        assert {"path", "sha256", "bytes"} <= set(reference)
    published = tmp_path / "recovery" / manifest["bundle_path"] / "manifest.json"
    assert published.is_file()
    assert json.loads((tmp_path / "recovery" / "current.json").read_text())[
        "bundle_id"
    ] == manifest["bundle_id"]


def test_schema3_bundle_streams_communities_instead_of_materializing_them(tmp_path):
    from gnn.observability_artifact import build_observability_bundle
    import gnn.observability_artifact as artifact_module

    def refuse(*args, **kwargs):
        raise AssertionError("staged runs must not use the in-memory store")

    original = artifact_module._store_community
    artifact_module._store_community = refuse
    try:
        manifest = build_observability_bundle(**_schema3_bundle_fixture(tmp_path))
    finally:
        artifact_module._store_community = original

    assert manifest["community_sidecar_index"]


def _interrupted_writer_factory():
    """A writer whose publication step fails, leaving staged state on disk."""
    from gnn.recovery_bundle import RecoveryBundleWriter

    class InterruptedWriter(RecoveryBundleWriter):
        def finalize_schema3(self, **kwargs):
            raise RuntimeError("simulated interruption before publication")

    return InterruptedWriter


def test_schema3_bundle_resume_reuses_staged_evidence(tmp_path):
    from gnn.observability_artifact import build_observability_bundle

    values = _schema3_bundle_fixture(tmp_path)
    engine = values["explanation_engine"]
    explained = []
    original_explain = engine.explain_case
    engine.explain_case = lambda case: (
        explained.append(case.person_id) or original_explain(case)
    )
    communities = []
    original_community = engine.community
    engine.community = lambda person_id, scoring_day: (
        communities.append(person_id) or original_community(person_id, scoring_day)
    )

    with pytest.raises(RuntimeError, match="simulated interruption"):
        build_observability_bundle(
            **_schema3_bundle_fixture(
                tmp_path,
                explanation_engine=engine,
                writer_factory=_interrupted_writer_factory(),
            )
        )
    assert explained
    assert communities

    # The resumed run must serve every already-staged case from its sidecar
    # rather than re-running GNNExplainer or rebuilding its community.
    explained.clear()
    communities.clear()
    manifest = build_observability_bundle(
        **_schema3_bundle_fixture(tmp_path, explanation_engine=engine)
    )

    assert manifest["schema_version"] == "3.0"
    assert explained == []
    assert communities == []


def test_schema3_bundle_records_per_case_attempt_state(tmp_path):
    from gnn.recovery_bundle import RecoveryBundleWriter
    from gnn.observability_artifact import build_observability_bundle

    observed = {}

    class RecordingWriter(RecoveryBundleWriter):
        def begin_case_attempt(self, case_id, phase):
            observed.setdefault(case_id, []).append(phase)
            return super().begin_case_attempt(case_id, phase)

    manifest = build_observability_bundle(
        **_schema3_bundle_fixture(tmp_path, writer_factory=RecordingWriter)
    )

    selected = set(manifest["selection"]["selected_ids"]["hybrid_only"]) | set(
        manifest["selection"]["selected_ids"]["baseline_only"]
    ) | set(manifest["selection"]["hybrid_structural_fallback_ids"])
    assert selected
    assert set(observed) == selected
    assert all(phases == ["first_pass"] for phases in observed.values())


def test_schema3_bundle_retries_only_an_interrupted_case_once(tmp_path):
    from gnn.recovery_bundle import RecoveryBundleWriter
    from gnn.observability_artifact import build_observability_bundle

    values = _schema3_bundle_fixture(tmp_path)
    engine = values["explanation_engine"]
    original_explain = engine.explain_case
    interrupted = {}

    def explode_once(case):
        if not interrupted:
            interrupted["person_id"] = case.person_id
            raise RuntimeError("simulated explainer interruption")
        return original_explain(case)

    engine.explain_case = explode_once
    with pytest.raises(RuntimeError, match="simulated interruption"):
        build_observability_bundle(
            **_schema3_bundle_fixture(
                tmp_path,
                explanation_engine=engine,
                writer_factory=_interrupted_writer_factory(),
            )
        )
    assert interrupted
    failed_case = f"case:{interrupted['person_id']}"

    phases = {}

    class RecordingWriter(RecoveryBundleWriter):
        def begin_case_attempt(self, case_id, phase):
            phases.setdefault(case_id, []).append(phase)
            return super().begin_case_attempt(case_id, phase)

    resumed = build_observability_bundle(
        **_schema3_bundle_fixture(
            tmp_path, explanation_engine=engine, writer_factory=RecordingWriter
        )
    )

    # Only the interrupted case is retried, and it uses its second and final
    # persisted slot; everything else is served from staged evidence.
    assert phases == {failed_case: ["deferred_retry"]}
    assert failed_case in resumed["detail_index"]


def test_schema3_bundle_manifest_is_accepted_by_the_dashboard_publisher(tmp_path):
    """The published bundle must survive the real sidecar validator.

    The producer and the dashboard packaging step are the two halves of the
    schema-3 contract; stubbing the publisher in the builder tests cannot show
    that a genuinely produced manifest validates.
    """
    import importlib.util
    from pathlib import Path

    from gnn.observability_artifact import build_observability_bundle

    manifest = build_observability_bundle(**_schema3_bundle_fixture(tmp_path))
    source = tmp_path / "hybrid_recovery_explanations_v9.json"
    source.write_text(json.dumps(manifest))

    sidecar_path = (
        Path(__file__).resolve().parents[1]
        / "Documents/Data/scripts/v9_recovery_sidecars.py"
    )
    spec = importlib.util.spec_from_file_location(
        "v9_recovery_sidecars_e2e", sidecar_path
    )
    sidecars = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sidecars)

    published = sidecars.publish_prepackaged_schema3_manifest(
        manifest, source, str(tmp_path / "dashboard" / "recovery")
    )

    assert published["schema_version"] == "3.0"
    assert set(published["detail_index"]) == set(manifest["detail_index"])
    assert set(published["community_index"]) == set(manifest["community_index"])


def test_schema3_resume_reports_true_narrative_coverage(tmp_path):
    from gnn.observability_artifact import build_observability_bundle

    values = _schema3_bundle_fixture(tmp_path)
    engine = values["explanation_engine"]

    with pytest.raises(RuntimeError, match="simulated interruption"):
        build_observability_bundle(
            **_schema3_bundle_fixture(
                tmp_path,
                explanation_engine=engine,
                writer_factory=_interrupted_writer_factory(),
            )
        )

    manifest = build_observability_bundle(
        **_schema3_bundle_fixture(tmp_path, explanation_engine=engine)
    )

    coverage = manifest["coverage"]
    # Every published Hybrid explanation carries a narrative, whether it was
    # produced in this process or replayed from staged evidence.
    assert coverage["hybrid_explained"] > 0
    assert coverage["narrative_attempted"] == coverage["hybrid_explained"]
    assert coverage["narrative_attempted"] == (
        coverage["narrative_generated"] + coverage["narrative_fallback"]
    )
