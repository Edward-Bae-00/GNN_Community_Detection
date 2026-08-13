import json
import copy
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch


def _context():
    from gnn.giant_observability_benchmark import BenchmarkContext

    day = "2025-01-02T00:00:00+00:00"
    cases = (
        SimpleNamespace(
            person_id="small",
            anchor=SimpleNamespace(scoring_day=day),
        ),
        SimpleNamespace(
            person_id="giant",
            anchor=SimpleNamespace(scoring_day=day),
        ),
    )
    return BenchmarkContext(
        checkpoint_id="checkpoint-verified",
        engine=object(),
        cases=cases,
        publication_cases=cases,
    )


def _recovery_case(case_id, cohort):
    from gnn.recovery_observability import RecoveryAnchor, build_recovery_case

    person_id = case_id.split(":", 1)[1]
    trace = {
        "baseline_raw": 0.4,
        "baseline_percentile": 0.4,
        "baseline_rank": 2,
        "seed0_gnn_probability": 0.6,
        "seed0_gnn_percentile": 0.6,
        "seed0_gnn_rank": 3,
        "seed0_hybrid_score": 0.55,
        "seed0_hybrid_rank": 2,
    }
    return build_recovery_case(
        case_id=case_id,
        recovery_cohort=cohort,
        anchor_event=RecoveryAnchor(
            person_id=person_id,
            event_id=f"event:{person_id}",
            row_index=0,
            scoring_day="2025-01-02T00:00:00+00:00",
            inspected_rank=1,
        ),
        subject_id=person_id,
        subject_display={},
        decision_trace=trace,
        recovery_anchor_arm="hybrid" if cohort == "hybrid_only" else "baseline",
        hybrid_blend_weight=0.75,
        relationship_categories=("COTRAVEL",),
        scoring_period="2025-01",
    )


def test_canonical_benchmark_balances_cohorts_and_accounts_structural_controls():
    from gnn.giant_observability_benchmark import (
        BenchmarkContext,
        _benchmark_balanced_controls,
    )

    hybrid = tuple(
        _recovery_case(f"case:h{index:02d}", "hybrid_only")
        for index in range(25)
    )
    baseline = tuple(
        _recovery_case(f"case:b{index:02d}", "baseline_only")
        for index in range(12)
    )
    structural_calls = []
    instrumentation = []
    context = BenchmarkContext(
        checkpoint_id="fixture-checkpoint",
        engine=SimpleNamespace(),
        cases=(),
        publication_cases=(),
        hybrid_recovery_cases=hybrid,
        baseline_recovery_cases=baseline,
    )

    def preflight(_engine, case):
        oversized = case.case_id in {"case:h00", "case:h01"}
        return {
            "eligible": not oversized,
            "status": "community_only" if oversized else "eligible",
            "node_count": 129 if oversized else 128,
            "edge_count": 256,
            "max_nodes": 128,
            "max_edges": 256,
            "reason_code": "node_limit_exceeded" if oversized else "eligible",
        }

    result = _benchmark_balanced_controls(
        context,
        preflight_runner=preflight,
        structural_runner=lambda _engine, case: structural_calls.append(case.case_id),
        instrumentation=lambda stage, fields: instrumentation.append((stage, fields)),
        started_at=0.0,
    )
    assert len(result["selection"].selected_ids["hybrid_only"]) == 20
    assert len(result["selection"].selected_ids["baseline_only"]) == 10
    assert len(result["eligible_hybrid_ids"]) == 23
    assert len(result["baseline_structural_case_ids"]) == 10
    assert len(structural_calls) == 10
    assert result["baseline_gnnexplainer_encoder_forward_count"] == 0
    assert result["counts"]["hybrid_requested"] == 20
    assert result["counts"]["baseline_requested"] == 10
    assert result["counts"]["hybrid_eligible"] == 23
    assert result["counts"]["hybrid_oversized"] == 2
    assert result["counts"]["baseline_attempted"] == 10
    assert result["counts"]["baseline_generated"] == 10
    elapsed = [fields["elapsed_seconds"] for _stage, fields in instrumentation]
    assert elapsed == sorted(elapsed)
    assert all(fields["peak_rss_bytes"] > 0 for _stage, fields in instrumentation)


def test_benchmark_canonical_path_processes_all_selected_hybrid_cases(tmp_path):
    from gnn.giant_observability_benchmark import BenchmarkContext, run_benchmark

    day = "2025-01-02T00:00:00+00:00"
    hybrid_technical = tuple(
        SimpleNamespace(
            person_id=f"h{index:02d}",
            anchor=SimpleNamespace(scoring_day=day),
        )
        for index in range(22)
    )
    baseline_technical = tuple(
        SimpleNamespace(
            person_id=f"b{index:02d}",
            anchor=SimpleNamespace(scoring_day=day),
        )
        for index in range(11)
    )
    context = BenchmarkContext(
        checkpoint_id="checkpoint-verified",
        engine=object(),
        cases=hybrid_technical,
        publication_cases=tuple(("hybrid_only", case) for case in hybrid_technical)
        + tuple(("baseline_only", case) for case in baseline_technical),
        hybrid_recovery_cases=tuple(
            _recovery_case(f"case:{case.person_id}", "hybrid_only")
            for case in hybrid_technical
        ),
        baseline_recovery_cases=tuple(
            _recovery_case(f"case:{case.person_id}", "baseline_only")
            for case in baseline_technical
        ),
    )
    calls = []

    def runner(_engine, case, restart_seeds):
        calls.append(case.person_id)
        return {
            "restart_seeds": list(restart_seeds),
            "local_node_count": 3,
            "local_edge_count": 4,
            "salient_factor_count": 0,
            "factor_scoring_call_count": 0,
            "factor_scoring_cache_hit_count": 0,
            "factor_actual_encoder_forward_count": 0,
            "faithfulness_scoring_call_count": 0,
            "faithfulness_scoring_cache_hit_count": 0,
            "faithfulness_actual_encoder_forward_count": 0,
            "gnnexplainer_encoder_forward_count": 1,
            "other_encoder_forward_count": 0,
            "explanation": {"case_id": f"case:{case.person_id}"},
        }

    result = run_benchmark(
        tmp_path,
        tmp_path,
        tmp_path / "benchmark.json",
        context_loader=lambda *_: context,
        component_size=lambda _engine, case: int(case.person_id[1:]) + 1,
        explanation_runner=runner,
        preflight_runner=lambda _engine, _case: {
            "eligible": True,
            "status": "eligible",
            "node_count": 128,
            "edge_count": 256,
            "max_nodes": 128,
            "max_edges": 256,
            "reason_code": "eligible",
        },
        structural_runner=lambda *_: None,
        publication_estimator=lambda *_: {
            "estimated_publication_bytes": 1,
            "estimated_required_free_bytes": 2,
            "publication_estimate_basis": "recovery_bundle_dry_run_test",
            "publication_copy_policy": "test",
        },
    )
    assert len(calls) == 20
    assert result["balanced_selection"]["baseline_gnnexplainer_encoder_forward_count"] == 0
    assert result["balanced_selection"]["selected_ids"]["baseline_only"]
    counts = result["balanced_selection"]["counts"]
    assert counts["hybrid_selected"] == 20
    assert counts["hybrid_attempted"] == 20
    assert counts["baseline_selected"] == 10
    assert counts["baseline_attempted"] == 10
    assert counts["baseline_generated"] == 10
    assert counts["baseline_failed"] == 0
    assert counts["hybrid_gnnexplainer_encoder_forward_count"] == 20
    assert counts["hybrid_explanations_wall_seconds"] > 0.0
    assert counts["baseline_controls_wall_seconds"] >= 0.0


def test_benchmark_aggregates_forward_counts_from_failed_hybrid_attempts(tmp_path):
    from gnn.giant_observability_benchmark import BenchmarkContext, run_benchmark

    day = "2025-01-02T00:00:00+00:00"
    hybrid_technical = tuple(
        SimpleNamespace(
            person_id=f"h{index:02d}",
            anchor=SimpleNamespace(scoring_day=day),
        )
        for index in range(21)
    )
    baseline_technical = tuple(
        SimpleNamespace(
            person_id=f"b{index:02d}",
            anchor=SimpleNamespace(scoring_day=day),
        )
        for index in range(11)
    )
    context = BenchmarkContext(
        checkpoint_id="checkpoint-verified",
        engine=object(),
        cases=hybrid_technical,
        publication_cases=tuple(("hybrid_only", case) for case in hybrid_technical)
        + tuple(("baseline_only", case) for case in baseline_technical),
        hybrid_recovery_cases=tuple(
            _recovery_case(f"case:{case.person_id}", "hybrid_only")
            for case in hybrid_technical
        ),
        baseline_recovery_cases=tuple(
            _recovery_case(f"case:{case.person_id}", "baseline_only")
            for case in baseline_technical
        ),
    )

    def measured(case_id, *, include_explanation):
        payload = {
            "restart_seeds": [0, 1, 2],
            "local_node_count": 3,
            "local_edge_count": 4,
            "salient_factor_count": 0,
            "factor_scoring_call_count": 0,
            "factor_scoring_cache_hit_count": 0,
            "factor_actual_encoder_forward_count": 0,
            "faithfulness_scoring_call_count": 0,
            "faithfulness_scoring_cache_hit_count": 0,
            "faithfulness_actual_encoder_forward_count": 0,
            "gnnexplainer_encoder_forward_count": 1,
            "other_encoder_forward_count": 0,
        }
        if include_explanation:
            payload["explanation"] = {"case_id": case_id}
        return payload

    calls = []

    def runner(_engine, case, restart_seeds):
        calls.append(case.person_id)
        if len(calls) == 1:
            error = RuntimeError("narrative failed after explainer work")
            error.measurement = measured(f"case:{case.person_id}", include_explanation=False)
            raise error
        payload = measured(f"case:{case.person_id}", include_explanation=True)
        if len(calls) == 2:
            payload["salient_factor_count"] = -1
        return payload

    result = run_benchmark(
        tmp_path,
        tmp_path,
        tmp_path / "benchmark.json",
        context_loader=lambda *_: context,
        component_size=lambda _engine, case: int(case.person_id[1:]) + 1,
        explanation_runner=runner,
        preflight_runner=lambda _engine, _case: _eligible_preflight(),
        structural_runner=lambda *_: None,
        publication_estimator=lambda *_: {
            "estimated_publication_bytes": 1,
            "estimated_required_free_bytes": 2,
            "publication_estimate_basis": "recovery_bundle_dry_run_test",
            "publication_copy_policy": "test",
        },
    )

    counts = result["balanced_selection"]["counts"]
    assert len(calls) == 20
    assert counts["hybrid_failed"] == 2
    assert counts["hybrid_gnnexplainer_encoder_forward_count"] == 20


def _eligible_preflight(*_args, **_kwargs):
    return {
        "eligible": True,
        "status": "eligible",
        "node_count": 4,
        "edge_count": 6,
        "max_nodes": 128,
        "max_edges": 256,
        "reason_code": "eligible",
    }


def test_benchmark_measures_baseline_explainer_calls_instead_of_assuming_zero():
    import gnn.giant_observability_benchmark as benchmark_module
    from gnn.giant_observability_benchmark import (
        BenchmarkContext,
        _benchmark_balanced_controls,
    )

    context = BenchmarkContext(
        checkpoint_id="fixture-checkpoint",
        engine=SimpleNamespace(),
        cases=(),
        publication_cases=(),
        hybrid_recovery_cases=tuple(
            _recovery_case(f"case:h{index:02d}", "hybrid_only") for index in range(2)
        ),
        baseline_recovery_cases=tuple(
            _recovery_case(f"case:b{index:02d}", "baseline_only") for index in range(2)
        ),
    )

    def leaking_structural_runner(_engine, _case):
        benchmark_module.run_member_explanation()

    with pytest.raises(ValueError, match="must not invoke GNNExplainer"):
        _benchmark_balanced_controls(
            context,
            preflight_runner=_eligible_preflight,
            structural_runner=leaking_structural_runner,
        )

    result = _benchmark_balanced_controls(
        context,
        preflight_runner=_eligible_preflight,
        structural_runner=lambda *_: None,
    )
    assert result["baseline_explainer_call_count"] == 0
    assert result["baseline_gnnexplainer_encoder_forward_count"] == 0
    assert result["baseline_explainer_measurement"] == "explainer_entrypoints_only"
    assert benchmark_module.run_member_explanation.__name__ == "run_member_explanation"


def test_benchmark_counts_baseline_structural_failures():
    from gnn.giant_observability_benchmark import (
        BenchmarkContext,
        _benchmark_balanced_controls,
    )

    context = BenchmarkContext(
        checkpoint_id="fixture-checkpoint",
        engine=SimpleNamespace(),
        cases=(),
        publication_cases=(),
        hybrid_recovery_cases=(_recovery_case("case:h00", "hybrid_only"),),
        baseline_recovery_cases=tuple(
            _recovery_case(f"case:b{index:02d}", "baseline_only") for index in range(2)
        ),
    )

    def failing_structural_runner(_engine, case):
        if case.case_id == "case:b00":
            raise RuntimeError("community extraction failed")

    result = _benchmark_balanced_controls(
        context,
        preflight_runner=_eligible_preflight,
        structural_runner=failing_structural_runner,
    )
    assert result["counts"]["baseline_attempted"] == 2
    assert result["counts"]["baseline_generated"] == 1
    assert result["counts"]["baseline_failed"] == 1
    assert result["baseline_failures"][0]["case_id"] == "case:b00"


def test_benchmark_rejects_selected_hybrid_cases_missing_from_context(tmp_path):
    from gnn.giant_observability_benchmark import BenchmarkContext, run_benchmark

    day = "2025-01-02T00:00:00+00:00"
    technical = tuple(
        SimpleNamespace(
            person_id=f"h{index:02d}", anchor=SimpleNamespace(scoring_day=day)
        )
        for index in range(3)
    )
    context = BenchmarkContext(
        checkpoint_id="checkpoint-verified",
        engine=object(),
        cases=technical[:2],
        publication_cases=tuple(("hybrid_only", case) for case in technical[:2]),
        hybrid_recovery_cases=tuple(
            _recovery_case(f"case:{case.person_id}", "hybrid_only")
            for case in technical
        ),
        baseline_recovery_cases=(_recovery_case("case:b00", "baseline_only"),),
    )

    with pytest.raises(ValueError, match="missing from the verified context"):
        run_benchmark(
            tmp_path,
            tmp_path,
            tmp_path / "benchmark.json",
            context_loader=lambda *_: context,
            component_size=lambda _engine, case: 1,
            explanation_runner=lambda *_: {},
            preflight_runner=_eligible_preflight,
            structural_runner=lambda *_: None,
            publication_estimator=lambda *_: {},
        )


def test_benchmark_writes_largest_real_case_measurements_atomically(tmp_path):
    from gnn.giant_observability_benchmark import run_benchmark

    checkpoint = tmp_path / "checkpoint"
    corpus = tmp_path / "corpus"
    output = tmp_path / "benchmark.json"
    checkpoint.mkdir()
    corpus.mkdir()
    calls = []
    instrumentation = []

    def loader(corpus_dir, checkpoint_path):
        calls.append((Path(corpus_dir), Path(checkpoint_path)))
        return _context()

    def component_size(_engine, case):
        return {"small": 4, "giant": 120_000}[case.person_id]

    def runner(_engine, case, restart_seeds):
        assert case.person_id == "giant"
        assert restart_seeds == (0, 1, 2)
        return {
            "restart_seeds": [0, 1, 2],
            "local_node_count": 913,
            "local_edge_count": 4_812,
            "salient_factor_count": 25,
            "factor_scoring_call_count": 25,
            "factor_scoring_cache_hit_count": 0,
            "factor_actual_encoder_forward_count": 25,
            "faithfulness_scoring_call_count": 7,
            "faithfulness_scoring_cache_hit_count": 1,
            "faithfulness_actual_encoder_forward_count": 6,
            "gnnexplainer_encoder_forward_count": 453,
            "other_encoder_forward_count": 0,
            "explanation": {"case_id": "case:giant", "factors": [0] * 25},
        }

    def estimator(_context, _case, _explanation):
        return {
            "estimated_publication_bytes": 9_000_000,
            "estimated_required_free_bytes": 18_000_000,
            "publication_estimate_basis": (
                "recovery_bundle_dry_run_complete_cohort_communities"
            ),
            "publication_copy_policy": "atomic_bundle_then_cow_or_verified_copy",
        }

    result = run_benchmark(
        corpus,
        checkpoint,
        output,
        context_loader=loader,
        component_size=component_size,
        explanation_runner=runner,
        publication_estimator=estimator,
        instrumentation=lambda stage, fields: instrumentation.append(
            (stage, fields)
        ),
    )

    assert calls == [(corpus, checkpoint)]
    assert result["checkpoint_id"] == "checkpoint-verified"
    assert result["target_person_id"] == "giant"
    assert result["community_node_count"] == 120_000
    assert result["local_explainer_node_count"] == 913
    assert result["local_explainer_edge_count"] == 4_812
    assert result["salient_factor_count"] == 25
    assert result["factor_actual_encoder_forward_count"] == 25
    assert result["faithfulness_actual_encoder_forward_count"] == 6
    assert result["diagnostic_actual_encoder_forward_count"] == 31
    assert result["gnnexplainer_encoder_forward_count"] == 453
    assert result["other_encoder_forward_count"] == 0
    assert result["restart_seeds"] == [0, 1, 2]
    assert result["wall_runtime_seconds"] >= 0.0
    assert result["process_peak_rss_bytes"] > 0
    assert result["process_peak_rss_scope"] == "process_lifetime_high_water_mark"
    assert result["estimated_publication_bytes"] == 9_000_000
    assert result["estimated_required_free_bytes"] == 18_000_000
    assert result["publication_estimate_basis"].startswith("recovery_bundle_dry_run")
    assert json.loads(output.read_text()) == result
    assert not output.with_suffix(".json.tmp").exists()
    assert [stage for stage, _ in instrumentation] == [
        "benchmark_start",
        "selection_start",
        "selection_day_released",
        "selection_complete",
        "explanation_start",
        "explanation_complete",
        "benchmark_complete",
    ]
    assert all("elapsed_seconds" in fields for _, fields in instrumentation)
    assert all(fields["elapsed_seconds"] > 0.0 for _, fields in instrumentation)
    assert all(fields["peak_rss_bytes"] > 0 for _, fields in instrumentation)


@pytest.mark.parametrize(
    ("restart_seeds", "forward_count", "message"),
    [
        ((0, 1), 20, "restart seeds"),
        ((0, 1, 2), 26, "counterfactual forward"),
    ],
)
def test_benchmark_rejects_contract_violations_without_publishing(
    tmp_path, restart_seeds, forward_count, message
):
    from gnn.giant_observability_benchmark import run_benchmark

    output = tmp_path / "benchmark.json"

    def runner(_engine, _case, _restart_seeds):
        return {
            "restart_seeds": list(restart_seeds),
            "local_node_count": 3,
            "local_edge_count": 4,
            "salient_factor_count": min(forward_count, 25),
            "factor_scoring_call_count": forward_count,
            "factor_scoring_cache_hit_count": 0,
            "factor_actual_encoder_forward_count": forward_count,
            "faithfulness_scoring_call_count": 1,
            "faithfulness_scoring_cache_hit_count": 1,
            "faithfulness_actual_encoder_forward_count": 0,
            "gnnexplainer_encoder_forward_count": 3,
            "other_encoder_forward_count": 0,
            "explanation": {"case_id": "case:giant"},
        }

    with pytest.raises(ValueError, match=message):
        run_benchmark(
            tmp_path,
            tmp_path,
            output,
            context_loader=lambda *_: _context(),
            component_size=lambda _engine, case: (
                100 if case.person_id == "giant" else 1
            ),
            explanation_runner=runner,
            publication_estimator=lambda *_: {
                "estimated_publication_bytes": 1,
                "estimated_required_free_bytes": 2,
                "publication_estimate_basis": "recovery_bundle_dry_run_test",
                "publication_copy_policy": "test",
            },
        )

    assert not output.exists()


def test_instrumentation_counts_cache_hits_and_actual_factor_and_faithfulness_forwards(
    monkeypatch,
):
    from gnn import giant_observability_benchmark as benchmark

    class Encoder(torch.nn.Module):
        def forward(self, value):
            return value

    class Engine:
        def __init__(self):
            setattr(
                self,
                "_Seed0ExplanationEngine__model",
                SimpleNamespace(enc=Encoder()),
            )
            self.factor_cache = set()
            setattr(self, "_Seed0ExplanationEngine__counterfactual_cache", {})
            setattr(self, "_Seed0ExplanationEngine__faithfulness_cache", {})

        def score_counterfactual(self, _context, factor):
            if factor not in self.factor_cache:
                self.factor_cache.add(factor)
                if factor != "factor-noop":
                    getattr(self, "_Seed0ExplanationEngine__model").enc(
                        torch.ones(1)
                    )
                getattr(
                    self, "_Seed0ExplanationEngine__counterfactual_cache"
                )[factor] = True
            return {"factor": factor}

    engine = Engine()
    faithfulness_cache = set()

    def diagnostic(target, _context, source_ids):
        key = tuple(source_ids)
        if key not in faithfulness_cache:
            faithfulness_cache.add(key)
            if key:
                getattr(target, "_Seed0ExplanationEngine__model").enc(torch.ones(1))
            getattr(target, "_Seed0ExplanationEngine__faithfulness_cache")[key] = True
        return 0.5

    def lightweight_member(target, *_args, **_kwargs):
        copied_model = copy.deepcopy(
            getattr(target, "_Seed0ExplanationEngine__model")
        )
        copied_model.enc(torch.ones(1))
        return {"restart_seeds": (0, 1, 2)}

    def compose(target, _case, *, restart_seeds, member_explainer):
        member_explainer(target, "giant", "2025-01-02")
        target.score_counterfactual(None, "factor-noop")
        target.score_counterfactual(None, "factor-noop")
        target.score_counterfactual(None, "factor-a")
        benchmark.diagnostic_edge_source_set_probability(target, None, ())
        benchmark.diagnostic_edge_source_set_probability(target, None, ())
        benchmark.diagnostic_edge_source_set_probability(target, None, ("e1",))
        return {
            "attributions": {"scope": {"restart_seeds": list(restart_seeds)}},
            "factors": [
                {"factor_id": "factor-noop"},
                {"factor_id": "factor-a"},
            ],
        }

    monkeypatch.setattr(
        benchmark,
        "member_subgraph",
        lambda *_: SimpleNamespace(
            x=torch.zeros((3, 2)), edge_index=torch.zeros((2, 4))
        ),
    )
    monkeypatch.setattr(benchmark, "compose_case_explanation", compose)
    monkeypatch.setattr(benchmark, "run_member_explanation", lightweight_member)
    monkeypatch.setattr(
        benchmark, "diagnostic_edge_source_set_probability", diagnostic
    )

    measured = benchmark._run_case_explanation(
        engine,
        SimpleNamespace(
            person_id="giant",
            anchor=SimpleNamespace(scoring_day="2025-01-02"),
        ),
        (0, 1, 2),
        narrative_builder=lambda _explanation: {
            "source": "llm",
            "model": "gemma4:12b",
            "validated": True,
            "prompt_version": "test",
            "summary": "Grounded summary.",
            "summary_source_refs": ["node:giant"],
            "claims": [{"text": "Grounded.", "source_refs": ["node:giant"]}],
        },
    )

    assert measured["factor_scoring_call_count"] == 3
    assert measured["factor_scoring_cache_hit_count"] == 1
    assert measured["factor_actual_encoder_forward_count"] == 1
    assert measured["faithfulness_scoring_call_count"] == 3
    assert measured["faithfulness_scoring_cache_hit_count"] == 1
    assert measured["faithfulness_actual_encoder_forward_count"] == 1
    assert measured["gnnexplainer_encoder_forward_count"] == 1
    assert measured["other_encoder_forward_count"] == 0


def test_production_metadata_gate_rejects_nonproduction_configuration():
    from gnn.giant_observability_benchmark import _validate_production_metadata

    metadata = {
        "checkpoint_id": "id",
        "run": {
            "seeds": [0, 1, 2],
            "epochs": 17,
            "train_bucket": "Q",
            "valid_sample": 20_000,
            "gnn_arm": "sage",
        },
        "model": {"name": "sage"},
        "node_universe": {"count": 120_000},
    }
    with pytest.raises(ValueError, match="epochs=18"):
        _validate_production_metadata(metadata)


def test_real_checkpoint_closure_rejects_corruption(tmp_path):
    from gnn.demo_checkpoint import load_demo_checkpoint, write_demo_checkpoint

    class TinyModel(torch.nn.Module):
        def __init__(self, in_dim=1, num_relations=1):
            super().__init__()
            self.layer = torch.nn.Linear(in_dim, 1)

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "input.csv").write_text("id\n1\n")
    model = TinyModel()
    written = write_demo_checkpoint(
        checkpoints_root=tmp_path / "checkpoints",
        corpus_dir=corpus,
        seeds=(0,),
        epochs=1,
        train_bucket="D",
        valid_sample=None,
        gnn_arm="tiny",
        substrate="oracle",
        feature_schema={"baseline": ["x"], "gnn": ["x"]},
        node_ids=["p1"],
        relation_schema={"REL": 0},
        fusion_weights={"deployable": 0.5},
        model_name="tiny",
        model_kwargs={"in_dim": 1, "num_relations": 1},
        models_by_seed={0: model},
        baseline_valid=np.array([0.1]),
        baseline_test=np.array([0.2]),
        gnn_valid_by_seed={0: np.array([0.3])},
        gnn_test_by_seed={0: np.array([0.4])},
        validation_event_ids=["v1"],
        test_event_ids=["t1"],
    )
    (written.path / "scores.npz").write_bytes(b"corrupt")

    with pytest.raises(ValueError, match="scores SHA-256"):
        load_demo_checkpoint(written.path, model_registry={"tiny": TinyModel})


def test_deterministic_largest_component_tie_uses_day_then_person(tmp_path):
    from gnn.giant_observability_benchmark import run_benchmark

    cases = (
        SimpleNamespace(person_id="z", anchor=SimpleNamespace(scoring_day="2025-01-01")),
        SimpleNamespace(person_id="a", anchor=SimpleNamespace(scoring_day="2025-01-01")),
    )
    context = SimpleNamespace(
        checkpoint_id="id", engine=object(), cases=cases, publication_cases=cases
    )
    selected = []

    def runner(_engine, case, _seeds):
        selected.append(case.person_id)
        return {
            "restart_seeds": [0, 1, 2],
            "local_node_count": 1,
            "local_edge_count": 0,
            "salient_factor_count": 0,
            "factor_scoring_call_count": 0,
            "factor_scoring_cache_hit_count": 0,
            "factor_actual_encoder_forward_count": 0,
            "faithfulness_scoring_call_count": 1,
            "faithfulness_scoring_cache_hit_count": 1,
            "faithfulness_actual_encoder_forward_count": 0,
            "gnnexplainer_encoder_forward_count": 3,
            "other_encoder_forward_count": 0,
            "explanation": {},
        }

    run_benchmark(
        tmp_path,
        tmp_path,
        tmp_path / "out.json",
        context_loader=lambda *_: context,
        component_size=lambda *_: 10,
        explanation_runner=runner,
        publication_estimator=lambda *_: {
            "estimated_publication_bytes": 1,
            "estimated_required_free_bytes": 2,
            "publication_estimate_basis": "recovery_bundle_dry_run_test",
            "publication_copy_policy": "test",
        },
    )
    assert selected == ["a"]


def test_atomic_failure_cleans_unique_temp_and_preserves_destination(
    tmp_path, monkeypatch
):
    from gnn import giant_observability_benchmark as benchmark

    destination = tmp_path / "result.json"
    destination.write_text("old")
    monkeypatch.setattr(benchmark.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("boom")))

    with pytest.raises(OSError, match="boom"):
        benchmark._atomic_write(destination, {"new": True})

    assert destination.read_text() == "old"
    assert not list(tmp_path.glob(".result.json.tmp-*"))


def test_true_publication_estimator_finalizes_all_cases_and_cleans_temp(tmp_path):
    from gnn.giant_observability_benchmark import _estimate_full_publication

    def case(person_id, day):
        return SimpleNamespace(
            person_id=person_id,
            anchor=SimpleNamespace(
                event_id=f"event-{person_id}",
                scoring_day=pd.Timestamp(day),
            ),
            baseline_rank=2,
            gnn_rank=1,
            hybrid_rank=1,
            hybrid_rank_uplift=1,
            gnn_percentile_uplift=0.2,
            relationship_categories=("COTRAVEL",),
        )

    import pandas as pd

    hybrid = case("hybrid", "2025-01-02T00:00:00Z")
    baseline = case("baseline", "2025-01-03T00:00:00Z")
    communities = {
        "hybrid": {
            "complete": True,
            "scoring_day": "2025-01-02T00:00:00+00:00",
            "component_id": "component-h",
            "community_key": "community-h",
            "nodes": [{"node_id": "hybrid", "target": True}],
            "edges": [],
        },
        "baseline": {
            "complete": True,
            "scoring_day": "2025-01-03T00:00:00+00:00",
            "component_id": "component-b",
            "community_key": "community-b",
            "nodes": [{"node_id": "baseline", "target": True}],
            "edges": [],
        },
    }
    engine = SimpleNamespace(
        community=lambda person_id, _day: communities[person_id]
    )
    context = SimpleNamespace(
        checkpoint_id="checkpoint-id",
        engine=engine,
        publication_cases=(("hybrid_only", hybrid), ("baseline_only", baseline)),
    )
    explanation = {
        "case_id": "case:hybrid",
        "person_id": "hybrid",
        "event_id": "event-hybrid",
        "scoring_day": "2025-01-02T00:00:00+00:00",
        "attributions": {
            "top_local_nodes": [{"node_id": "hybrid"}],
            "top_edges": [],
        },
        "provenance_expansions": [],
        "llm_narrative": {
            "source": "llm",
            "model": "gemma4:12b",
            "validated": True,
            "prompt_version": "test-v1",
            "summary": "Grounded summary.",
            "summary_source_refs": ["node:hybrid"],
            "claims": [
                {"text": "Grounded claim.", "source_refs": ["node:hybrid"]}
            ],
        },
    }

    result = _estimate_full_publication(
        context, hybrid, explanation, temporary_parent=tmp_path
    )

    assert result["publication_case_count"] == 2
    assert result["publication_community_count"] == 2
    assert result["published_bundle_file_count"] > 1
    assert result["estimated_publication_bytes"] > 0
    assert result["published_bundle_id"]
    assert not list(tmp_path.iterdir())


def test_estimator_projects_full_selected_shape_to_other_hybrid_case(
    tmp_path, monkeypatch
):
    import pandas as pd
    from gnn import giant_observability_benchmark as benchmark

    def case(person_id, day):
        return SimpleNamespace(
            person_id=person_id,
            anchor=SimpleNamespace(
                event_id=f"event-{person_id}", scoring_day=pd.Timestamp(day)
            ),
            baseline_rank=3,
            gnn_rank=1,
            hybrid_rank=1,
            hybrid_rank_uplift=2,
            gnn_percentile_uplift=0.3,
            relationship_categories=("COTRAVEL",),
        )

    selected = case("selected", "2025-01-02T00:00:00Z")
    projected = case("projected", "2025-01-03T00:00:00Z")
    communities = {
        "selected": {
            "complete": True,
            "scoring_day": "2025-01-02T00:00:00+00:00",
            "component_id": "component-selected",
            "community_key": "community-selected",
            "nodes": [
                {"node_id": "selected", "target": True},
                {"node_id": "selected-peer-a"},
                {"node_id": "selected-peer-b"},
            ],
            "edges": [
                {
                    "edge_id": "edge-selected-a",
                    "u": "selected",
                    "v": "selected-peer-a",
                    "edge_type": "COTRAVEL",
                    "source_row_ids": ["row-selected-a1", "row-selected-a2"],
                    "source_row_count": 2,
                    "observations": [
                        {"source_row_id": "row-selected-a1"},
                        {"source_row_id": "row-selected-a2"},
                    ],
                },
                {
                    "edge_id": "edge-selected-b",
                    "u": "selected",
                    "v": "selected-peer-b",
                    "edge_type": "RESIDENCE",
                    "source_row_ids": ["row-selected-b"],
                    "source_row_count": 1,
                    "observations": [{"source_row_id": "row-selected-b"}],
                },
                {
                    "edge_id": "edge-selected-c",
                    "u": "selected-peer-a",
                    "v": "selected-peer-b",
                    "edge_type": "SHARED_PLATE",
                    "source_row_ids": ["row-selected-c"],
                    "source_row_count": 1,
                    "observations": [{"source_row_id": "row-selected-c"}],
                },
            ],
        },
        "projected": {
            "complete": True,
            "scoring_day": "2025-01-03T00:00:00+00:00",
            "component_id": "component-projected",
            "community_key": "community-projected",
            "nodes": [
                {"node_id": "projected", "target": True},
                {"node_id": "projected-peer"},
            ],
            "edges": [
                {
                    "edge_id": "edge-projected-only",
                    "u": "projected",
                    "v": "projected-peer",
                    "edge_type": "COTRAVEL",
                    "source_row_ids": ["row-projected-only"],
                    "source_row_count": 1,
                    "complete_source_row_count": 4,
                    "source_rows_truncated": True,
                    "observations": [{"source_row_id": "row-projected-only"}],
                }
            ],
        },
    }
    explanation = {
        "case_id": "case:selected",
        "person_id": "selected",
        "event_id": "event-selected",
        "scoring_day": "2025-01-02T00:00:00+00:00",
        "decision_trace": {"seed0_hybrid_rank": 1},
        "decision_ledger": {"component_pooling": {"component_size": 1}},
        "attributions": {
            "scope": {"restart_seeds": [0, 1, 2]},
            "top_local_nodes": [
                {
                    "node_id": "selected",
                    "source_id": "selected",
                    "rank": 1,
                    "explainer_median": 0.75,
                }
            ],
            "top_edges": [
                {
                    "edge_id": "edge-selected-a",
                    "u": "selected",
                        "v": "selected-peer-a",
                        "edge_type": "COTRAVEL",
                        "source_row_ids": ["row-selected-a1", "row-selected-a2"],
                    "explainer_median": 0.9,
                },
                {
                    "edge_id": "edge-selected-b",
                    "u": "selected",
                    "v": "selected-peer-b",
                    "edge_type": "RESIDENCE",
                    "source_row_ids": ["row-selected-b"],
                    "explainer_median": 0.8,
                },
            ],
            "top_features": [{"node_id": "selected", "feature_name": "caught"}],
            "node_feature_mask_stats": [
                {"node_id": "selected", "feature_name": "caught", "explainer_median": 0.5}
            ],
        },
        "factors": [
            {
                "factor_id": "caught:selected",
                "kind": "caught_flag",
                "counterfactual": {"hybrid_rank_delta": 1},
            }
        ],
        "stability": {"stable_factor_count": 1},
        "faithfulness": {"original_probability": 0.8, "points": []},
        "flow_stages": [{"stage": "target", "node_ids": ["selected"]}],
        "parity": {"production_seed0_probability": True},
        "evidence_boundary": {"snapshot": "2025-01-02T00:00:00+00:00"},
        "provenance_expansions": [
            {
                "expansion_id": "expansion:selected",
                "label": "Representative provenance",
                "nodes": [
                    {
                        "node_id": "selected",
                        "source_id": "selected",
                        "layout_x": 10.0,
                        "caught_before_snapshot": False,
                    }
                ],
                "edges": [
                    {
                        "edge_id": "edge-selected-c",
                        "u": "selected-peer-a",
                        "v": "selected-peer-b",
                        "edge_type": "SHARED_PLATE",
                        "source_row_ids": ["row-selected-c"],
                        "source_row_count": 1,
                        "observations": [
                            {"source_row_id": "row-selected-c"}
                        ],
                    },
                ],
            }
        ],
        "llm_narrative": {
            "source": "llm",
            "model": "gemma4:12b",
            "validated": True,
            "prompt_version": "test-v1",
            "summary": "Selected representative.",
            "summary_source_refs": ["node:selected"],
            "claims": [
                {"text": "Selected claim.", "source_refs": ["node:selected"]}
            ],
        },
    }
    context = SimpleNamespace(
        checkpoint_id="checkpoint-id",
        engine=SimpleNamespace(
            community=lambda person_id, _day: communities[person_id]
        ),
        publication_cases=(
            ("hybrid_only", selected),
            ("hybrid_only", projected),
        ),
    )
    captured = {}
    original_write_case = benchmark.RecoveryBundleWriter.write_case

    def capture_write_case(self, cohort, case_record, **kwargs):
        explanation_record = copy.deepcopy(kwargs.get("explanation"))
        overlay = kwargs.get("overlay_evidence")
        materialized_overlay = None
        if overlay is not None:
            materialized_overlay = {
                key: list(value) for key, value in overlay.items()
            }
            kwargs["overlay_evidence"] = {
                key: iter(value) for key, value in materialized_overlay.items()
            }
        captured[case_record["person_id"]] = (
            explanation_record,
            materialized_overlay,
        )
        return original_write_case(self, cohort, case_record, **kwargs)

    monkeypatch.setattr(
        benchmark.RecoveryBundleWriter, "write_case", capture_write_case
    )

    result = benchmark._estimate_full_publication(
        context, selected, explanation, temporary_parent=tmp_path
    )

    selected_projection, _ = captured["selected"]
    other_projection, other_overlay = captured["projected"]
    for key in (
        "factors",
        "decision_ledger",
        "attributions",
        "stability",
        "faithfulness",
        "flow_stages",
        "parity",
        "evidence_boundary",
    ):
        assert key in other_projection
    assert len(other_projection["factors"]) == len(selected_projection["factors"])
    assert len(other_projection["attributions"]["node_feature_mask_stats"]) == 1
    assert other_overlay["nodes"]
    assert other_overlay["provenance_expansions"]
    projected_top_node = other_overlay["nodes"][0]
    projected_expansion_node = other_overlay[
        "provenance_expansions"
    ][0]["nodes"][0]
    assert projected_top_node == projected_expansion_node
    assert projected_top_node["explainer_median"] == 0.75
    assert projected_top_node["layout_x"] == 10.0
    projected_edge_ids = [edge["edge_id"] for edge in other_overlay["edges"]]
    assert projected_edge_ids == ["edge-projected-only"]
    expansion_edges = other_overlay["provenance_expansions"][0]["edges"]
    assert expansion_edges
    assert expansion_edges[0]["edge_id"] == "edge-projected-only"
    assert expansion_edges[0] == other_overlay["edges"][0]
    assert expansion_edges[0]["source_row_count"] == 1
    assert expansion_edges[0]["complete_source_row_count"] == 4
    assert expansion_edges[0]["source_rows_truncated"] is True
    assert expansion_edges[0]["observations"] == [
        {"source_row_id": "row-projected-only"}
    ]
    assert other_projection["sizing_conservative_overlay_padding_bytes"] > 0
    assert len(benchmark._canonical_json(other_projection)) >= len(
        benchmark._canonical_json(selected_projection)
    )
    assert result["publication_hybrid_explanation_projection_count"] == 2
    assert result["projected_min_overlay_accounted_bytes"] >= result[
        "selected_representative_overlay_bytes"
    ]
    assert result[
        "selected_representative_overlay_provenance_observation_count"
    ] >= 3
    assert result["projected_min_overlay_provenance_observation_count"] < result[
        "selected_representative_overlay_provenance_observation_count"
    ]
    assert not list(tmp_path.iterdir())


def test_overlay_node_canonicalization_fails_closed_on_semantic_conflict():
    from gnn.giant_observability_benchmark import (
        _canonicalize_projected_overlay_nodes,
    )

    projected = {
        "attributions": {
            "top_local_nodes": [{"node_id": "P1", "rank": 1}]
        }
    }
    expansions = [
        {
            "expansion_id": "expansion:P1",
            "nodes": [{"node_id": "P1", "rank": 2}],
            "edges": [],
        }
    ]

    with pytest.raises(ValueError, match="semantic conflict.*P1.*rank"):
        _canonicalize_projected_overlay_nodes(projected, expansions)


def test_largest_case_selection_releases_day_snapshots_and_bounds_cache():
    import pandas as pd
    from gnn.giant_observability_benchmark import _select_largest_case_bounded

    class Engine:
        def __init__(self):
            self.active_days = set()
            self.max_active_days = 0
            self.released = []

        def release_snapshot(self, day):
            normalized = pd.Timestamp(day)
            self.active_days.discard(normalized)
            self.released.append(normalized)

    engine = Engine()
    cases = tuple(
        SimpleNamespace(
            person_id=f"P{index:05d}",
            anchor=SimpleNamespace(
                scoring_day=pd.Timestamp("2025-01-01", tz="UTC")
                + pd.Timedelta(days=index // 4)
            ),
        )
        for index in range(400)
    )

    def component_size(target_engine, case):
        day = pd.Timestamp(case.anchor.scoring_day)
        target_engine.active_days.add(day)
        target_engine.max_active_days = max(
            target_engine.max_active_days, len(target_engine.active_days)
        )
        return int(case.person_id[1:]) + 1

    size, selected = _select_largest_case_bounded(
        SimpleNamespace(engine=engine, cases=cases), component_size
    )

    assert size == 400
    assert selected.person_id == "P00399"
    assert engine.max_active_days == 1
    assert len(set(engine.released)) == 100
    assert not engine.active_days


def test_projection_does_not_deepcopy_embedded_complete_community():
    import pandas as pd
    from gnn.giant_observability_benchmark import _project_hybrid_explanation

    class GiantCommunitySentinel(dict):
        def __deepcopy__(self, memo):
            raise AssertionError("complete giant community must not be deep-copied")

    case = SimpleNamespace(
        person_id="P1",
        anchor=SimpleNamespace(
            event_id="event-P1",
            scoring_day=pd.Timestamp("2025-01-02", tz="UTC"),
        ),
    )
    community = {
        "community_key": "community-P1",
        "nodes": [{"node_id": "P1"}],
        "edges": [],
    }
    explanation = {
        "case_id": "case:P1",
        "person_id": "P1",
        "event_id": "event-P1",
        "scoring_day": "2025-01-02T00:00:00+00:00",
        "community": GiantCommunitySentinel(community),
        "attributions": {"top_local_nodes": [{"node_id": "P1"}], "top_edges": []},
        "provenance_expansions": [],
        "llm_narrative": {
            "source": "llm",
            "model": "gemma4:12b",
            "validated": True,
            "prompt_version": "test",
            "summary": "summary",
            "summary_source_refs": ["node:P1"],
            "claims": [{"text": "claim", "source_refs": ["node:P1"]}],
        },
    }

    projected, _ = _project_hybrid_explanation(
        case, community, case, explanation
    )

    assert "community" not in projected


@pytest.mark.parametrize("failure_stage", ["component", "explanation", "contract"])
def test_run_benchmark_releases_selected_day_on_every_failure(
    tmp_path, failure_stage
):
    import pandas as pd
    from gnn.giant_observability_benchmark import run_benchmark

    class Engine:
        def __init__(self):
            self.active_days = set()

        def activate(self, day):
            self.active_days.add(pd.Timestamp(day))

        def release_snapshot(self, day):
            self.active_days.discard(pd.Timestamp(day))

    engine = Engine()
    context = _context()
    context = SimpleNamespace(
        checkpoint_id=context.checkpoint_id,
        engine=engine,
        cases=context.cases,
        publication_cases=context.publication_cases,
    )

    def component_size(target, case):
        target.activate(case.anchor.scoring_day)
        if failure_stage == "component":
            raise RuntimeError("component failure")
        return 10 if case.person_id == "giant" else 1

    def explanation_runner(target, case, _seeds):
        target.activate(case.anchor.scoring_day)
        if failure_stage == "explanation":
            raise RuntimeError("explanation failure")
        return {"restart_seeds": [0, 1], "explanation": {}}

    with pytest.raises((RuntimeError, ValueError)):
        run_benchmark(
            tmp_path,
            tmp_path,
            tmp_path / "out.json",
            context_loader=lambda *_: context,
            component_size=component_size,
            explanation_runner=explanation_runner,
            publication_estimator=lambda *_: pytest.fail(
                "failure must occur before publication"
            ),
        )

    assert not engine.active_days


def _publication_failure_fixture():
    import pandas as pd

    def case(person_id, day):
        return SimpleNamespace(
            person_id=person_id,
            anchor=SimpleNamespace(
                event_id=f"event-{person_id}",
                scoring_day=pd.Timestamp(day),
            ),
            baseline_rank=2,
            gnn_rank=1,
            hybrid_rank=1,
            hybrid_rank_uplift=1,
            gnn_percentile_uplift=0.2,
            relationship_categories=("COTRAVEL",),
        )

    selected = case("selected", "2025-01-02T00:00:00Z")
    later = case("later", "2025-01-03T00:00:00Z")
    community = {
        "complete": True,
        "scoring_day": "2025-01-02T00:00:00+00:00",
        "component_id": "component-selected",
        "community_key": "community-selected",
        "nodes": [{"node_id": "selected", "target": True}],
        "edges": [],
    }
    explanation = {
        "case_id": "case:selected",
        "person_id": "selected",
        "event_id": "event-selected",
        "scoring_day": "2025-01-02T00:00:00+00:00",
        "attributions": {
            "top_local_nodes": [{"node_id": "selected"}],
            "top_edges": [],
        },
        "provenance_expansions": [],
        "llm_narrative": {
            "source": "llm",
            "model": "gemma4:12b",
            "validated": True,
            "prompt_version": "test",
            "summary": "summary",
            "summary_source_refs": ["node:selected"],
            "claims": [
                {"text": "claim", "source_refs": ["node:selected"]}
            ],
        },
    }
    return selected, later, community, explanation


@pytest.mark.parametrize("failure_stage", ["selected", "later"])
def test_publication_estimator_releases_cache_and_temp_on_acquisition_failure(
    tmp_path, failure_stage
):
    import pandas as pd
    from gnn.giant_observability_benchmark import _estimate_full_publication

    selected, later, selected_community, explanation = (
        _publication_failure_fixture()
    )

    class Engine:
        def __init__(self):
            self.active_days = set()

        def community(self, person_id, day):
            self.active_days.add(pd.Timestamp(day))
            if person_id == failure_stage:
                raise RuntimeError(f"{failure_stage} community failure")
            return selected_community

        def release_snapshot(self, day):
            self.active_days.discard(pd.Timestamp(day))

    engine = Engine()
    context = SimpleNamespace(
        checkpoint_id="checkpoint-id",
        engine=engine,
        publication_cases=(
            ("hybrid_only", selected),
            ("baseline_only", later),
        ),
    )
    if failure_stage == "later":
        explanation["community"] = selected_community

    with pytest.raises(RuntimeError, match="community failure"):
        _estimate_full_publication(
            context,
            selected,
            explanation,
            temporary_parent=tmp_path,
        )

    assert not engine.active_days
    assert not list(tmp_path.iterdir())


def test_stage_log_is_unbuffered_named_and_reports_positive_rss(
    monkeypatch, capsys
):
    from gnn import giant_observability_benchmark as benchmark

    monkeypatch.setattr(benchmark, "_process_peak_rss_bytes", lambda: 4096)

    benchmark._stage_log("selection_day_released", days_processed=10)

    line = capsys.readouterr().out.strip()
    assert "stage=selection_day_released" in line
    assert "peak_rss_bytes=4096" in line
    assert "days_processed=10" in line


@pytest.mark.parametrize(
    ("node_count", "edge_counts", "message"),
    [
        (119_999, {0: 504_358, 1: 2_016_084, 2: 107_856, 3: 11_174}, "120000"),
        (120_000, {0: 1, 1: 2_016_084, 2: 107_856, 3: 11_174}, "typed-edge"),
    ],
)
def test_graph_contract_rejects_wrong_node_or_edge_counts(
    node_count, edge_counts, message
):
    from gnn.giant_observability_benchmark import _validate_graph_contract

    class Edges:
        def __getitem__(self, key):
            assert key == "rel"
            return SimpleNamespace(
                value_counts=lambda: SimpleNamespace(
                    to_dict=lambda: edge_counts
                )
            )

    edges = Edges()
    with pytest.raises(ValueError, match=message):
        _validate_graph_contract([f"p{i}" for i in range(node_count)], edges)


@pytest.mark.parametrize(
    ("other_forwards", "explainer_forwards", "message"),
    [(1, 3, "other encoder"), (0, 0, "GNNExplainer encoder")],
)
def test_benchmark_rejects_unclassified_or_missing_explainer_execution(
    tmp_path, other_forwards, explainer_forwards, message
):
    from gnn.giant_observability_benchmark import run_benchmark

    measured = {
        "restart_seeds": [0, 1, 2],
        "local_node_count": 1,
        "local_edge_count": 0,
        "salient_factor_count": 0,
        "factor_scoring_call_count": 0,
        "factor_scoring_cache_hit_count": 0,
        "factor_actual_encoder_forward_count": 0,
        "faithfulness_scoring_call_count": 1,
        "faithfulness_scoring_cache_hit_count": 0,
        "faithfulness_actual_encoder_forward_count": 0,
        "gnnexplainer_encoder_forward_count": explainer_forwards,
        "other_encoder_forward_count": other_forwards,
        "explanation": {},
    }
    with pytest.raises(ValueError, match=message):
        run_benchmark(
            tmp_path,
            tmp_path,
            tmp_path / "out.json",
            context_loader=lambda *_: _context(),
            component_size=lambda *_: 1,
            explanation_runner=lambda *_: measured,
            publication_estimator=lambda *_: pytest.fail("must fail before sizing"),
        )


def test_case_community_materializes_communityscope_target_local_view(monkeypatch):
    """engine.community() returns a lazy CommunityScope for every case; the
    publication-sizing loop needs a target-local dict. _case_community must
    materialize the CommunityScope (never subscript it) and pass mappings
    through unchanged, mirroring the explanation runner's own conversion."""
    import pandas as pd
    from gnn import giant_observability_benchmark as benchmark
    from gnn.sage_explainer import CommunityScope

    class _ScopeStub(CommunityScope):
        # Bypass the heavy CommunityScope.__init__ but keep isinstance identity.
        def __init__(self, dict_view):
            self._dict_view = dict_view
            self.captured_target = None
            self.captured_node_ids = None

        def materialize_local(self, node_ids, source_row_ids=(), *, target_person_id=None):
            self.captured_node_ids = list(node_ids)
            self.captured_target = target_person_id
            return self._dict_view

    dict_view = {
        "community_key": "community:mat",
        "complete": True,
        "scoring_day": "2025-01-02T00:00:00+00:00",
        "component_id": "component-mat",
        "nodes": [{"node_id": "P1", "target": True}, {"node_id": "P2"}],
        "edges": [],
    }
    scope = _ScopeStub(dict_view)
    engine = SimpleNamespace(
        node_ids=["P1", "P2", "P3"],
        community=lambda person_id, day: scope,
    )
    monkeypatch.setattr(
        benchmark,
        "member_subgraph",
        lambda _engine, _person, _day: SimpleNamespace(
            original_node_indices=np.array([0, 1], dtype=np.int64)
        ),
    )
    case = SimpleNamespace(
        person_id="P1",
        anchor=SimpleNamespace(
            event_id="event-P1", scoring_day=pd.Timestamp("2025-01-02T00:00:00Z")
        ),
    )

    resolved = benchmark._case_community(engine, case)

    assert resolved is dict_view
    assert resolved["community_key"] == "community:mat"
    assert scope.captured_target == "P1"
    assert scope.captured_node_ids == ["P1", "P2"]

    # A community already materialized to a mapping is returned unchanged.
    passthrough = benchmark._case_community(
        SimpleNamespace(community=lambda person_id, day: dict_view), case
    )
    assert passthrough is dict_view


def _portable_corpus(root):
    """Write a byte-identical canonical corpus tree at an arbitrary location."""
    corpus = Path(root) / "synthetic_cbp_graph_corpus_v9"
    corpus.mkdir(parents=True)
    (corpus / "persons.csv").write_text("person_id\nP-1\n", encoding="utf-8")
    (corpus / "labels.csv").write_text("event_id,label\nE-1,0\n", encoding="utf-8")
    return corpus


def test_corpus_verification_accepts_relocated_corpus_with_identical_bytes(tmp_path):
    from gnn.demo_checkpoint import corpus_fingerprints
    from gnn.giant_observability_benchmark import _verify_corpus_compatibility

    recorded = _portable_corpus(tmp_path / "recorded")
    metadata = {
        "corpus": {
            "identity": str(recorded),
            "fingerprints": corpus_fingerprints(recorded),
        }
    }
    relocated = _portable_corpus(tmp_path / "relocated")

    fingerprints = _verify_corpus_compatibility(metadata, relocated)

    assert fingerprints == metadata["corpus"]["fingerprints"]


def test_corpus_verification_rejects_mutated_csv_at_any_location(tmp_path):
    from gnn.demo_checkpoint import corpus_fingerprints
    from gnn.giant_observability_benchmark import _verify_corpus_compatibility

    recorded = _portable_corpus(tmp_path / "recorded")
    metadata = {
        "corpus": {
            "identity": str(recorded),
            "fingerprints": corpus_fingerprints(recorded),
        }
    }
    relocated = _portable_corpus(tmp_path / "relocated")
    (relocated / "persons.csv").write_text("person_id\nP-2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="corpus fingerprints"):
        _verify_corpus_compatibility(metadata, relocated)
