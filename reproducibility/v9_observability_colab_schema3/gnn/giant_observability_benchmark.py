"""Benchmark one real giant-component observability explanation."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from contextlib import contextmanager
import copy
from dataclasses import dataclass, replace
import gc
from itertools import groupby
import json
import os
from pathlib import Path
import resource
import sys
import tempfile
import time
from typing import Callable

import numpy as np

from gnn.demo_checkpoint import (
    checkpoint_node_universe_hash,
    corpus_fingerprints,
    load_demo_checkpoint,
    read_demo_checkpoint_metadata,
)
from gnn.demo_baseline import FEATURE_NAMES
from gnn.explanation_narrative import build_fact_packet, generate_narrative
from gnn.graphmodel_rgcn import (
    REL_PLATE,
    build_person_graph_typed,
    caught_feature_names,
)
from gnn.learned_cell import build_caught_times
from gnn.observability_artifact import (
    _bundle_case_record,
    _community_stream_source,
    _overlay_stream_source,
    _prepared_pool,
    _rank_row_bindings,
    build_baseline_only_cases,
    build_hybrid_only_cases,
)
from gnn.recovery_bundle import RecoveryBundleWriter
from gnn.recovery_observability import (
    build_recovery_case,
    build_rank_reference,
    recovery_overlap,
    select_balanced_detail_cases,
    simulate_recovery_run,
)
from gnn.run_demo import GNN_ARMS, _build_oracle, load_pool
from gnn.sage_explainer import (
    CommunityScope,
    MAX_EXPLAINER_INPUT_EDGES,
    MAX_EXPLAINER_INPUT_NODES,
    Seed0ExplanationEngine,
    compose_case_explanation,
    diagnostic_edge_source_set_probability,
    member_subgraph,
    run_member_explanation,
)


RESTART_SEEDS = (0, 1, 2)
INSPECTIONS_PER_DAY = 5
EXPECTED_NODE_COUNT = 120_000
MAX_FACTOR_ENCODER_FORWARDS = 25
MAX_FAITHFULNESS_ENCODER_FORWARDS = 6
MAX_DIAGNOSTIC_ENCODER_FORWARDS = (
    MAX_FACTOR_ENCODER_FORWARDS + MAX_FAITHFULNESS_ENCODER_FORWARDS
)
EXPECTED_TYPED_EDGE_COUNTS = {
    0: 504_358,
    1: 2_016_084,
    2: 107_856,
    3: 11_174,
}
EXPECTED_CORPUS_NAME = "synthetic_cbp_graph_corpus_v9"


@dataclass(frozen=True)
class BenchmarkContext:
    """Verified scoring state and real Hybrid-only benchmark candidates."""

    checkpoint_id: str
    engine: object
    cases: tuple
    publication_cases: tuple
    hybrid_recovery_cases: tuple = ()
    baseline_recovery_cases: tuple = ()


def _stage_log(stage, *, instrumentation=None, started_at=None, **fields):
    elapsed_seconds = (
        max(0.0, time.perf_counter() - started_at)
        if started_at is not None
        else float(fields.pop("elapsed_seconds", 0.0))
    )
    details = " ".join(f"{key}={value}" for key, value in sorted(fields.items()))
    suffix = f" {details}" if details else ""
    print(
        f"[v9-giant-benchmark] stage={stage} "
        f"peak_rss_bytes={_process_peak_rss_bytes()}{suffix}",
        flush=True,
    )
    callback = instrumentation
    if isinstance(instrumentation, Mapping):
        callback = instrumentation.get("on_stage")
    if callable(callback):
        callback(
            stage,
            {
                "stage": stage,
                "elapsed_seconds": elapsed_seconds,
                "peak_rss_bytes": _process_peak_rss_bytes(),
                **fields,
            },
        )


def _validate_production_metadata(metadata):
    run = metadata.get("run", {})
    requirements = (
        (tuple(run.get("seeds", ())) == RESTART_SEEDS, "seeds=[0,1,2]"),
        (run.get("epochs") == 18, "epochs=18"),
        (run.get("train_bucket") == "Q", "train_bucket=Q"),
        (run.get("valid_sample") == 20_000, "valid_sample=20000"),
        (run.get("gnn_arm") == "sage", "gnn_arm=sage"),
        (run.get("substrate") == "oracle", "substrate=oracle"),
        (
            metadata.get("node_universe", {}).get("count")
            == EXPECTED_NODE_COUNT,
            "node_universe.count=120000",
        ),
        (
            metadata.get("model", {}).get("name") == run.get("gnn_arm"),
            "model.name matching run.gnn_arm",
        ),
        (
            metadata.get("model", {}).get("kwargs")
            == {
                "in_dim": len(caught_feature_names(GNN_ARMS["sage"]["num_rel"])),
                "num_relations": GNN_ARMS["sage"]["num_rel"],
            },
            "production model kwargs",
        ),
    )
    failed = [description for valid, description in requirements if not valid]
    if failed:
        raise ValueError(
            "benchmark requires the full V9 production checkpoint: "
            + ", ".join(failed)
        )


def _validate_graph_contract(node_ids, edges_typed):
    if len(node_ids) != EXPECTED_NODE_COUNT:
        raise ValueError("full V9 graph must contain exactly 120000 canonical nodes")
    counts = {
        int(key): int(value)
        for key, value in edges_typed["rel"].value_counts().to_dict().items()
    }
    if counts != EXPECTED_TYPED_EDGE_COUNTS:
        raise ValueError(
            "full V9 typed-edge counts are incompatible: "
            f"expected {EXPECTED_TYPED_EDGE_COUNTS}, got {counts}"
        )


def _canonical_json(value) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _load_verified_context(corpus_dir, checkpoint_path) -> BenchmarkContext:
    _stage_log("context_start")
    corpus_dir = Path(corpus_dir).resolve()
    if corpus_dir.name != EXPECTED_CORPUS_NAME:
        raise ValueError(
            f"benchmark corpus must be the canonical {EXPECTED_CORPUS_NAME} directory"
        )
    checkpoint_path = Path(checkpoint_path)
    metadata = read_demo_checkpoint_metadata(checkpoint_path)
    _validate_production_metadata(metadata)
    run = metadata["run"]
    if checkpoint_path.name != metadata["checkpoint_id"]:
        raise ValueError(
            "checkpoint path identity does not match checkpoint metadata"
        )
    recorded_corpus = Path(metadata.get("corpus", {}).get("identity", ""))
    if recorded_corpus.resolve() != corpus_dir:
        raise ValueError("corpus path identity does not match checkpoint metadata")
    actual_fingerprints = corpus_fingerprints(corpus_dir)
    if metadata.get("corpus", {}).get("fingerprints") != actual_fingerprints:
        raise ValueError("corpus fingerprints do not match checkpoint metadata")
    _stage_log("checkpoint_metadata_verified")

    pool = load_pool(corpus_dir)
    observed_to_person = _build_oracle(corpus_dir)
    edges_typed, node_ids, node_feat = build_person_graph_typed(
        corpus_dir,
        substrate=run["substrate"],
        include_plate=True,
    )
    _validate_graph_contract(node_ids, edges_typed)
    _stage_log(
        "graph_rebuilt",
        nodes=len(node_ids),
        typed_edges=len(edges_typed),
    )
    arm = GNN_ARMS[run["gnn_arm"]]
    loaded = load_demo_checkpoint(
        checkpoint_path,
        model_registry={name: spec["cls"] for name, spec in GNN_ARMS.items()},
        expected={
            "seeds": run["seeds"],
            "epochs": run["epochs"],
            "train_bucket": run["train_bucket"],
            "valid_sample": run["valid_sample"],
            "gnn_arm": run["gnn_arm"],
            "substrate": run["substrate"],
            "corpus_identity": str(corpus_dir),
            "corpus_fingerprints": actual_fingerprints,
            "feature_schema": {
                "baseline": list(FEATURE_NAMES),
                "gnn": list(caught_feature_names(arm["num_rel"])),
            },
            "node_universe_hash": checkpoint_node_universe_hash(node_ids),
            "relation_schema": {
                key: int(value) for key, value in sorted(REL_PLATE.items())
            },
        },
    )
    expected_event_ids = pool["event_id"].astype(str).to_numpy()
    if not np.array_equal(loaded.test_event_ids, expected_event_ids):
        raise ValueError("checkpoint test event order is incompatible")
    valid_pool = load_pool(corpus_dir, split="validation")
    if run["valid_sample"] and len(valid_pool) > run["valid_sample"]:
        from gnn import config as FC

        valid_pool = valid_pool.sample(
            run["valid_sample"], random_state=FC.SEED
        ).reset_index(drop=True)
    expected_valid_ids = valid_pool["event_id"].astype(str).to_numpy()
    if not np.array_equal(loaded.validation_event_ids, expected_valid_ids):
        raise ValueError("checkpoint validation event order is incompatible")
    _stage_log("checkpoint_payload_verified")

    caught_times = build_caught_times(corpus_dir, observed_to_person)
    rows, scoring_days = _prepared_pool(pool)
    blend_weight = loaded.metadata["fusion_weights"]["deployable"]
    reference = build_rank_reference(
        rows,
        loaded.baseline_test,
        loaded.gnn_test_by_seed[0],
        blend_weight,
    )
    engine = Seed0ExplanationEngine(
        model=loaded.models_by_seed[0],
        edges_typed=edges_typed,
        node_ids=node_ids,
        node_feat=node_feat,
        caught_time=caught_times,
        num_rel=arm["num_rel"],
    )
    engine.bind_rank_reference(
        reference,
        _rank_row_bindings(rows, scoring_days),
    )
    baseline_run = simulate_recovery_run(
        rows,
        reference.baseline_selection_score,
        arm="baseline",
        daily_budget=INSPECTIONS_PER_DAY,
        official_caught_times=caught_times,
    )
    hybrid_run = simulate_recovery_run(
        rows,
        reference.seed0_hybrid_selection_score,
        arm="hybrid_seed0",
        daily_budget=INSPECTIONS_PER_DAY,
        official_caught_times=caught_times,
    )
    overlap = recovery_overlap(baseline_run, hybrid_run)
    cases = tuple(
        build_hybrid_only_cases(
            rows,
            overlap,
            baseline_run,
            hybrid_run,
            reference,
            engine,
        )
    )
    if not cases:
        raise ValueError("checkpoint has no real Hybrid-only benchmark candidates")
    baseline_cases = tuple(
        build_baseline_only_cases(
            rows,
            overlap,
            baseline_run,
            hybrid_run,
            reference,
            engine,
        )
    )
    checkpoint_id = loaded.checkpoint_id
    context = BenchmarkContext(
        checkpoint_id=checkpoint_id,
        engine=engine,
        cases=cases,
        publication_cases=(
            tuple(("hybrid_only", case) for case in cases)
            + tuple(("baseline_only", case) for case in baseline_cases)
        ),
        hybrid_recovery_cases=tuple(
            build_recovery_case(
                case_id=f"case:{case.person_id}",
                recovery_cohort="hybrid_only",
                anchor_event=case.anchor,
                subject_id=case.person_id,
                subject_display={},
                decision_trace=case.decision_trace_jsonable(),
                recovery_anchor_arm="hybrid",
                hybrid_blend_weight=reference.blend_weight,
                relationship_categories=case.relationship_categories,
                scoring_period=case.scoring_period,
            )
            for case in cases
        ),
        baseline_recovery_cases=tuple(
            build_recovery_case(
                case_id=f"case:{case.person_id}",
                recovery_cohort="baseline_only",
                anchor_event=case.anchor,
                subject_id=case.person_id,
                subject_display={},
                decision_trace=case.decision_trace_jsonable(),
                recovery_anchor_arm="baseline",
                hybrid_blend_weight=reference.blend_weight,
                relationship_categories=case.relationship_categories,
                scoring_period=case.scoring_period,
            )
            for case in baseline_cases
        ),
    )
    del loaded, edges_typed, node_ids, node_feat, pool, valid_pool, rows
    gc.collect()
    _stage_log(
        "context_ready",
        hybrid_cases=len(cases),
        publication_cases=len(context.publication_cases),
    )
    return context


def _component_node_count(engine, case) -> int:
    snapshot = engine.snapshot(case.anchor.scoring_day)
    target_index = engine.person_index[case.person_id]
    root = snapshot.component_roots[target_index]
    return int(np.count_nonzero(snapshot.component_roots == root))


def _select_largest_case_bounded(
    context, component_size, *, instrumentation=None, started_at=None
):
    ordered = sorted(
        context.cases,
        key=lambda case: (str(case.anchor.scoring_day), case.person_id),
    )
    if not ordered:
        raise ValueError("benchmark requires at least one real candidate case")
    release = getattr(context.engine, "release_snapshot", None)
    best_order_key = None
    best_identity = None
    best_size = None
    day_count = 0
    for scoring_day, day_cases in groupby(
        ordered, key=lambda case: str(case.anchor.scoring_day)
    ):
        day_count += 1
        materialized_cases = tuple(day_cases)
        try:
            for case in materialized_cases:
                size = int(component_size(context.engine, case))
                order_key = (-size, scoring_day, case.person_id)
                if best_order_key is None or order_key < best_order_key:
                    best_order_key = order_key
                    best_identity = (scoring_day, case.person_id)
                    best_size = size
        finally:
            if callable(release):
                release(materialized_cases[0].anchor.scoring_day)
            del materialized_cases
            gc.collect()
        if day_count == 1 or day_count % 10 == 0:
            _stage_log(
                "selection_day_released",
                instrumentation=instrumentation,
                started_at=started_at,
                days_processed=day_count,
            )
    selected = next(
        case
        for case in ordered
        if (str(case.anchor.scoring_day), case.person_id) == best_identity
    )
    _stage_log(
        "selection_complete",
        instrumentation=instrumentation,
        started_at=started_at,
        community_nodes=best_size,
        days_processed=day_count,
        person_id=selected.person_id,
    )
    return best_size, selected


def _generate_case_narrative(explanation):
    return generate_narrative(build_fact_packet(explanation))


def _run_case_explanation(
    engine,
    case,
    restart_seeds,
    *,
    narrative_builder=_generate_case_narrative,
):
    local = member_subgraph(engine, case.person_id, case.anchor.scoring_day)
    original_factor = engine.score_counterfactual
    original_faithfulness = diagnostic_edge_source_set_probability
    model = getattr(engine, "_Seed0ExplanationEngine__model")
    active_path = ["other"]
    encoder_forwards = {"factor": 0, "faithfulness": 0, "explainer": 0, "other": 0}
    factor_calls = 0
    factor_cache_hits = 0
    faithfulness_calls = 0
    faithfulness_cache_hits = 0

    def count_encoder_forward(_module, _inputs):
        encoder_forwards[active_path[-1]] += 1

    hook = model.enc.register_forward_pre_hook(count_encoder_forward)

    def counted_counterfactual(context, factor):
        nonlocal factor_calls, factor_cache_hits
        factor_calls += 1
        before = encoder_forwards["factor"]
        cache = getattr(
            engine, "_Seed0ExplanationEngine__counterfactual_cache", None
        )
        before_cache_keys = None if cache is None else frozenset(cache)
        active_path.append("factor")
        try:
            result = original_factor(context, factor)
        finally:
            active_path.pop()
        after_cache_keys = None if cache is None else frozenset(cache)
        if (
            before_cache_keys == after_cache_keys
            if cache is not None
            else encoder_forwards["factor"] == before
        ):
            factor_cache_hits += 1
        return result

    def counted_faithfulness(target_engine, context, source_ids):
        nonlocal faithfulness_calls, faithfulness_cache_hits
        faithfulness_calls += 1
        before = encoder_forwards["faithfulness"]
        cache = getattr(
            engine, "_Seed0ExplanationEngine__faithfulness_cache", None
        )
        before_cache_keys = None if cache is None else frozenset(cache)
        active_path.append("faithfulness")
        try:
            result = original_faithfulness(target_engine, context, source_ids)
        finally:
            active_path.pop()
        after_cache_keys = None if cache is None else frozenset(cache)
        if (
            before_cache_keys == after_cache_keys
            if cache is not None
            else encoder_forwards["faithfulness"] == before
        ):
            faithfulness_cache_hits += 1
        return result

    def counted_member_explanation(*args, **kwargs):
        active_path.append("explainer")
        try:
            return run_member_explanation(*args, **kwargs)
        finally:
            active_path.pop()

    engine.score_counterfactual = counted_counterfactual
    globals()["diagnostic_edge_source_set_probability"] = counted_faithfulness
    composer_globals = compose_case_explanation.__globals__
    composer_had_diagnostic = (
        "diagnostic_edge_source_set_probability" in composer_globals
    )
    composer_original_diagnostic = composer_globals.get(
        "diagnostic_edge_source_set_probability"
    )
    if composer_had_diagnostic:
        composer_globals["diagnostic_edge_source_set_probability"] = (
            counted_faithfulness
        )
    try:
        try:
            explanation = compose_case_explanation(
                engine,
                case,
                member_explainer=counted_member_explanation,
                restart_seeds=restart_seeds,
            )
            explanation["llm_narrative"] = narrative_builder(explanation)
        except Exception as error:
            # Preserve measurements when narrative validation or an explainer
            # restart fails after encoder work. The outer benchmark can then
            # account for every attempted case instead of summing successes.
            error.measurement = {
                "restart_seeds": list(restart_seeds),
                "local_node_count": int(local.x.shape[0]),
                "local_edge_count": int(local.edge_index.shape[1]),
                "salient_factor_count": 0,
                "factor_scoring_call_count": factor_calls,
                "factor_scoring_cache_hit_count": factor_cache_hits,
                "factor_actual_encoder_forward_count": encoder_forwards[
                    "factor"
                ],
                "faithfulness_scoring_call_count": faithfulness_calls,
                "faithfulness_scoring_cache_hit_count": faithfulness_cache_hits,
                "faithfulness_actual_encoder_forward_count": encoder_forwards[
                    "faithfulness"
                ],
                "gnnexplainer_encoder_forward_count": encoder_forwards[
                    "explainer"
                ],
                "other_encoder_forward_count": encoder_forwards["other"],
            }
            raise
    finally:
        engine.score_counterfactual = original_factor
        globals()["diagnostic_edge_source_set_probability"] = original_faithfulness
        if composer_had_diagnostic:
            composer_globals["diagnostic_edge_source_set_probability"] = (
                composer_original_diagnostic
            )
        hook.remove()

    scope = explanation.get("attributions", {}).get("scope", {})
    return {
        "restart_seeds": scope.get("restart_seeds"),
        "local_node_count": int(local.x.shape[0]),
        "local_edge_count": int(local.edge_index.shape[1]),
        "salient_factor_count": len(explanation.get("factors", ())),
        "factor_scoring_call_count": factor_calls,
        "factor_scoring_cache_hit_count": factor_cache_hits,
        "factor_actual_encoder_forward_count": encoder_forwards["factor"],
        "faithfulness_scoring_call_count": faithfulness_calls,
        "faithfulness_scoring_cache_hit_count": faithfulness_cache_hits,
        "faithfulness_actual_encoder_forward_count": encoder_forwards[
            "faithfulness"
        ],
        "gnnexplainer_encoder_forward_count": encoder_forwards["explainer"],
        "other_encoder_forward_count": encoder_forwards["other"],
        "explanation": explanation,
    }


def _failed_explanation_measurement(error):
    measurement = getattr(error, "measurement", None)
    if not isinstance(measurement, Mapping):
        return None
    try:
        _validate_benchmark_measurement(measurement)
    except (TypeError, ValueError):
        return None
    return measurement


def _failed_explanation_forward_count(error):
    measurement = getattr(error, "measurement", None)
    if not isinstance(measurement, Mapping):
        return None
    value = measurement.get("gnnexplainer_encoder_forward_count")
    if (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
    ):
        return value
    return None


def _benchmark_exact_preflight(engine, case):
    from gnn.sage_explainer import explainability_eligibility

    result = explainability_eligibility(
        engine, case.subject_id, case.anchor_event.scoring_day
    )
    return _validate_benchmark_preflight(result)


def _validate_benchmark_preflight(result):
    if not isinstance(result, Mapping):
        raise ValueError("benchmark preflight result must be an object")
    required = {
        "eligible", "status", "node_count", "edge_count", "max_nodes",
        "max_edges", "reason_code",
    }
    if set(result) != required:
        raise ValueError("benchmark preflight result shape is invalid")
    if not isinstance(result["eligible"], bool):
        raise ValueError("benchmark preflight eligibility must be boolean")
    if (
        result["max_nodes"] != MAX_EXPLAINER_INPUT_NODES
        or result["max_edges"] != MAX_EXPLAINER_INPUT_EDGES
    ):
        raise ValueError(
            "benchmark preflight limits must match the explainer constants"
        )
    if any(
        not isinstance(result[field], int)
        or isinstance(result[field], bool)
        or result[field] < 0
        for field in ("node_count", "edge_count", "max_nodes", "max_edges")
    ):
        raise ValueError("benchmark preflight counts must be non-negative integers")
    if result["status"] not in {"eligible", "community_only"}:
        raise ValueError("benchmark preflight status is invalid")
    if not isinstance(result["reason_code"], str) or not result["reason_code"].strip():
        raise ValueError("benchmark preflight reason_code is invalid")
    if result["eligible"] != (
        result["node_count"] <= MAX_EXPLAINER_INPUT_NODES
        and result["edge_count"] <= MAX_EXPLAINER_INPUT_EDGES
    ) or (result["eligible"] and result["status"] != "eligible") or (
        not result["eligible"] and result["status"] != "community_only"
    ):
        raise ValueError("benchmark preflight eligibility is inconsistent")
    return dict(result)


@contextmanager
def _baseline_explainer_monitor(engine):
    """Measure any explainer work performed while building Baseline controls.

    The count must be measured rather than assumed, otherwise a Baseline
    control path that silently starts calling GNNExplainer keeps reporting a
    hard-coded zero.
    """
    counts = {"encoder_forwards": 0, "explainer_calls": 0}
    module = globals()
    original_member = module["run_member_explanation"]
    original_compose = module["compose_case_explanation"]

    def counted_member(*args, **kwargs):
        counts["explainer_calls"] += 1
        return original_member(*args, **kwargs)

    def counted_compose(*args, **kwargs):
        counts["explainer_calls"] += 1
        return original_compose(*args, **kwargs)

    encoder = getattr(
        getattr(engine, "_Seed0ExplanationEngine__model", None), "enc", None
    )
    hook = None
    if hasattr(encoder, "register_forward_pre_hook"):
        def count_encoder_forward(_module, _inputs):
            counts["encoder_forwards"] += 1

        hook = encoder.register_forward_pre_hook(count_encoder_forward)
    counts["measurement"] = (
        "model_encoder_forward_hook_and_explainer_entrypoints"
        if hook is not None
        else "explainer_entrypoints_only"
    )
    module["run_member_explanation"] = counted_member
    module["compose_case_explanation"] = counted_compose
    try:
        yield counts
    finally:
        module["run_member_explanation"] = original_member
        module["compose_case_explanation"] = original_compose
        if hook is not None:
            hook.remove()


def _benchmark_balanced_controls(
    context, *, preflight_runner=None, structural_runner=None, instrumentation=None,
    started_at=None,
):
    hybrid_cases = tuple(getattr(context, "hybrid_recovery_cases", ()))
    baseline_cases = tuple(getattr(context, "baseline_recovery_cases", ()))
    if not hybrid_cases or not baseline_cases:
        return None
    preflight_runner = preflight_runner or _benchmark_exact_preflight
    preflight = {}
    eligible = []
    for case in hybrid_cases:
        result = _validate_benchmark_preflight(
            preflight_runner(context.engine, case)
        )
        preflight[case.case_id] = result
        if result["eligible"]:
            eligible.append(case.case_id)
    _stage_log(
        "preflight_complete",
        instrumentation=instrumentation,
        started_at=started_at,
        hybrid_candidates=len(hybrid_cases),
        eligible_hybrid=len(eligible),
        ineligible_hybrid=len(hybrid_cases) - len(eligible),
    )
    selection = select_balanced_detail_cases(
        hybrid_cases,
        baseline_cases,
        hybrid_limit=20,
        baseline_limit=10,
        eligible_hybrid_ids=eligible,
    )
    _stage_log(
        "balanced_selection_frozen",
        instrumentation=instrumentation,
        started_at=started_at,
        hybrid_selected=len(selection.selected_ids["hybrid_only"]),
        baseline_selected=len(selection.selected_ids["baseline_only"]),
    )
    structural_runner = structural_runner or (
        lambda engine, case: engine.community(
            case.subject_id, case.anchor_event.scoring_day
        )
    )
    baseline_selected = selection.selected_cases["baseline_only"]
    baseline_structural = []
    baseline_failures = []
    baseline_started = time.perf_counter()
    with _baseline_explainer_monitor(context.engine) as baseline_counts:
        for case in baseline_selected:
            try:
                structural_runner(context.engine, case)
            except Exception as error:
                baseline_failures.append(
                    {
                        "case_id": case.case_id,
                        "reason_code": type(error).__name__,
                        "message": str(error),
                    }
                )
                continue
            baseline_structural.append(case.case_id)
    baseline_wall_seconds = max(0.0, time.perf_counter() - baseline_started)
    baseline_forwards = int(baseline_counts["encoder_forwards"])
    baseline_calls = int(baseline_counts["explainer_calls"])
    if baseline_forwards or baseline_calls:
        raise ValueError(
            "Baseline structural controls must not invoke GNNExplainer: measured "
            f"{baseline_calls} explainer calls and {baseline_forwards} encoder forwards"
        )
    _stage_log(
        "baseline_controls_complete",
        instrumentation=instrumentation,
        started_at=started_at,
        attempted=len(baseline_selected),
        generated=len(baseline_structural),
        failed=len(baseline_failures),
        gnnexplainer_forwards=baseline_forwards,
    )
    return {
        "selection": selection,
        "preflight": preflight,
        "eligible_hybrid_ids": eligible,
        "baseline_structural_case_ids": baseline_structural,
        "baseline_failures": baseline_failures,
        "baseline_gnnexplainer_encoder_forward_count": baseline_forwards,
        "baseline_explainer_call_count": baseline_calls,
        "baseline_explainer_measurement": baseline_counts["measurement"],
        "counts": {
            "hybrid_requested": 20,
            "baseline_requested": 10,
            "hybrid_eligible": len(eligible),
            "hybrid_oversized": sum(
                result["reason_code"] != "eligible" for result in preflight.values()
            ),
            "hybrid_selected": len(selection.selected_ids["hybrid_only"]),
            "baseline_selected": len(baseline_selected),
            "hybrid_attempted": 0,
            "hybrid_generated": 0,
            "hybrid_fallback": 0,
            "hybrid_failed": 0,
            "hybrid_gnnexplainer_encoder_forward_count": 0,
            "baseline_attempted": len(baseline_selected),
            "baseline_generated": len(baseline_structural),
            "baseline_failed": len(baseline_failures),
            "baseline_controls_wall_seconds": baseline_wall_seconds,
            "hybrid_explanations_wall_seconds": 0.0,
        },
    }


def _validate_benchmark_measurement(measured):
    restart_seeds = measured.get("restart_seeds")
    if tuple(restart_seeds or ()) != RESTART_SEEDS:
        raise ValueError("benchmark restart seeds must be exactly [0, 1, 2]")
    factor_forward_count = measured.get("factor_actual_encoder_forward_count")
    if (
        not isinstance(factor_forward_count, int)
        or isinstance(factor_forward_count, bool)
        or not 0 <= factor_forward_count <= MAX_FACTOR_ENCODER_FORWARDS
    ):
        raise ValueError("benchmark counterfactual forward count exceeds the actual encoder bound of 25")
    factor_count = measured.get("salient_factor_count")
    if not isinstance(factor_count, int) or not 0 <= factor_count <= 25:
        raise ValueError("salient factor count exceeds the constant bound of 25")
    faithfulness_forward_count = measured.get("faithfulness_actual_encoder_forward_count")
    if (
        not isinstance(faithfulness_forward_count, int)
        or isinstance(faithfulness_forward_count, bool)
        or not 0 <= faithfulness_forward_count <= MAX_FAITHFULNESS_ENCODER_FORWARDS
    ):
        raise ValueError("faithfulness actual encoder forwards exceed bound of 6")
    diagnostic_forward_count = factor_forward_count + faithfulness_forward_count
    if diagnostic_forward_count > MAX_DIAGNOSTIC_ENCODER_FORWARDS:
        raise ValueError("total diagnostic actual encoder forwards exceed bound of 31")
    if measured.get("other_encoder_forward_count") != 0:
        raise ValueError("benchmark observed unclassified other encoder forwards")
    explainer_forward_count = measured.get("gnnexplainer_encoder_forward_count")
    if (
        not isinstance(explainer_forward_count, int)
        or isinstance(explainer_forward_count, bool)
        or explainer_forward_count <= 0
    ):
        raise ValueError("benchmark requires positive GNNExplainer encoder forwards")
    return {
        "factor_forward_count": factor_forward_count,
        "factor_count": factor_count,
        "faithfulness_forward_count": faithfulness_forward_count,
        "diagnostic_forward_count": diagnostic_forward_count,
        "other_forward_count": 0,
        "explainer_forward_count": explainer_forward_count,
    }


def _tree_size(root):
    return sum(path.stat().st_size for path in Path(root).rglob("*") if path.is_file())


def _rewrite_projection_values(value, replacements):
    if isinstance(value, dict):
        return {
            key: _rewrite_projection_values(item, replacements)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_rewrite_projection_values(item, replacements) for item in value]
    if isinstance(value, tuple):
        return tuple(
            _rewrite_projection_values(item, replacements) for item in value
        )
    if isinstance(value, str):
        rewritten = value
        for old, new in replacements:
            if old:
                rewritten = rewritten.replace(old, new)
        return rewritten
    return value


def _canonicalize_projected_overlay_nodes(projected, expansions):
    top_nodes = projected.setdefault("attributions", {}).setdefault(
        "top_local_nodes", []
    )
    merged_by_id = {}
    ordered_records = list(top_nodes) + [
        node
        for expansion in expansions
        for node in expansion.get("nodes", ())
    ]
    for record in ordered_records:
        if not isinstance(record, dict):
            raise ValueError("projected overlay node must be an object")
        node_id = record.get("node_id")
        if not isinstance(node_id, str) or not node_id:
            raise ValueError("projected overlay node requires node_id")
        merged = merged_by_id.setdefault(node_id, {})
        for key, value in record.items():
            if key in merged and _canonical_json(merged[key]) != _canonical_json(value):
                raise ValueError(
                    "projected overlay node semantic conflict for "
                    f"{node_id!r} field {key!r}"
                )
            merged[key] = copy.deepcopy(value)
    projected["attributions"]["top_local_nodes"] = [
        copy.deepcopy(merged_by_id[record["node_id"]])
        for record in top_nodes
    ]
    for expansion in expansions:
        expansion["nodes"] = [
            copy.deepcopy(merged_by_id[record["node_id"]])
            for record in expansion.get("nodes", ())
        ]
    return projected, expansions


def _project_hybrid_explanation(case, community, selected_case, explanation):
    narrative = copy.deepcopy(explanation.get("llm_narrative"))
    if not isinstance(narrative, dict) or narrative.get("validated") is not True:
        raise ValueError(
            "publication sizing requires the selected validated Gemma narrative"
        )
    explanation_template = {
        key: value for key, value in explanation.items() if key != "community"
    }
    if case.person_id == selected_case.person_id:
        projected = copy.deepcopy(explanation_template)
        expansions = projected.pop("provenance_expansions", [])
    else:
        selected_day = selected_case.anchor.scoring_day.isoformat()
        target_day = case.anchor.scoring_day.isoformat()
        selected_community = explanation.get("community")
        selected_community_key = (
            selected_community.get("community_key", "")
            if isinstance(selected_community, dict)
            else explanation.get("community_key", "")
        )
        replacements = [
            (f"case:{selected_case.person_id}", f"case:{case.person_id}"),
            (selected_case.anchor.event_id, case.anchor.event_id),
            (selected_case.person_id, case.person_id),
            (selected_day, target_day),
            (selected_community_key, community["community_key"]),
        ]
        selected_top_edges = explanation.get("attributions", {}).get(
            "top_edges", ()
        )
        target_edges = list(community.get("edges", ()))
        if target_edges:
            for selected_edge, target_edge in zip(
                selected_top_edges, target_edges
            ):
                replacements.append(
                    (str(selected_edge.get("edge_id", "")), target_edge["edge_id"])
                )
        projected = _rewrite_projection_values(
            copy.deepcopy(explanation_template), replacements
        )
        expansions = projected.pop("provenance_expansions", [])
        projected.pop("community", None)
        projected["case_id"] = f"case:{case.person_id}"
        projected["person_id"] = case.person_id
        projected["event_id"] = case.anchor.event_id
        projected["scoring_day"] = target_day
        projected["sizing_projection"] = "selected_validated_gemma_full_shape"

        target_nodes = list(community.get("nodes", ()))
        if not target_nodes:
            raise ValueError("Hybrid sizing projection requires a target community node")
        target_person_node = next(
            (
                node
                for node in target_nodes
                if node.get("node_id") == case.person_id
            ),
            target_nodes[0],
        )
        top_nodes = projected.setdefault("attributions", {}).get(
            "top_local_nodes", ()
        )
        remapped_nodes = []
        for index, attribution in enumerate(top_nodes):
            target_node = (
                target_person_node
                if index == 0
                else target_nodes[index % len(target_nodes)]
            )
            record = dict(attribution)
            record["node_id"] = target_node["node_id"]
            if "source_id" in record:
                record["source_id"] = target_node["node_id"]
            remapped_nodes.append(record)
        if not remapped_nodes:
            remapped_nodes = [{"node_id": target_person_node["node_id"]}]
        projected["attributions"]["top_local_nodes"] = remapped_nodes

        remapped_edges = []
        if target_edges:
            for attribution, canonical in zip(selected_top_edges, target_edges):
                record = _rewrite_projection_values(
                    copy.deepcopy(attribution), replacements
                )
                for field in (
                    "edge_id",
                    "u",
                    "v",
                    "edge_type",
                    "source_row_ids",
                ):
                    if field in canonical:
                        record[field] = copy.deepcopy(canonical[field])
                source_row_ids = list(canonical["source_row_ids"])
                record["source_row_count"] = len(source_row_ids)
                record["complete_source_row_count"] = int(
                    canonical.get(
                        "complete_source_row_count",
                        canonical.get("source_row_count", len(source_row_ids)),
                    )
                )
                record["source_rows_truncated"] = (
                    canonical.get("source_rows_truncated", False) is True
                )
                remapped_edges.append(record)
        projected["attributions"]["top_edges"] = remapped_edges

        remapped_expansions = []
        for index, expansion in enumerate(expansions):
            record = dict(expansion)
            record["expansion_id"] = (
                f"sizing:{case.person_id}:expansion:{index}"
            )
            original_nodes = list(record.get("nodes", ()))
            record["nodes"] = [
                {
                    **dict(original_node),
                    "node_id": target_nodes[node_index % len(target_nodes)][
                        "node_id"
                    ],
                    "source_id": target_nodes[node_index % len(target_nodes)][
                        "node_id"
                    ],
                }
                for node_index, original_node in enumerate(original_nodes)
            ] or [{"node_id": target_person_node["node_id"]}]
            expansion_edges = []
            if remapped_edges:
                # Reuse the exact top-edge attribution payload so the writer sees
                # one canonical overlay edge plus an expansion membership, not a
                # conflicting duplicate edge ID.
                canonical = target_edges[min(index, len(remapped_edges) - 1)]
                expansion_edge = copy.deepcopy(
                    remapped_edges[min(index, len(remapped_edges) - 1)]
                )
                expansion_edge["observations"] = copy.deepcopy(
                    canonical.get("observations", ())
                )
                expansion_edges.append(expansion_edge)
            record["edges"] = expansion_edges
            remapped_expansions.append(record)
        expansions = remapped_expansions

        selected_projection = copy.deepcopy(explanation_template)
        selected_projection.pop("provenance_expansions", None)
        selected_projection["community_key"] = selected_community_key
        deficit = len(_canonical_json(selected_projection)) - len(
            _canonical_json(projected)
        )
        if deficit > 0:
            projected["sizing_conservative_padding"] = "x" * deficit
    projected["community_key"] = community["community_key"]
    return _canonicalize_projected_overlay_nodes(projected, expansions)


def _enriched_overlay_stats(explanation, community, expansions):
    source = _overlay_stream_source(explanation, community, expansions)
    enriched = {key: list(value) for key, value in source.items()}
    observations = sum(
        len(edge.get("observations", ())) for edge in enriched["edges"]
    ) + sum(
        len(edge.get("observations", ()))
        for expansion in enriched["provenance_expansions"]
        for edge in expansion.get("edges", ())
    )
    expansion_nodes = sum(
        len(expansion.get("nodes", ()))
        for expansion in enriched["provenance_expansions"]
    )
    expansion_edges = sum(
        len(expansion.get("edges", ()))
        for expansion in enriched["provenance_expansions"]
    )
    record_count = (
        len(enriched["nodes"])
        + len(enriched["edges"])
        + observations
        + len(enriched["provenance_expansions"])
        + expansion_nodes
        + expansion_edges
    )
    return {
        "bytes": len(_canonical_json(enriched)),
        "record_count": record_count,
        "provenance_observation_count": observations,
    }


def _case_community(engine, case):
    """Resolve a case's community as a target-local dict.

    ``engine.community(...)`` returns a lazy ``CommunityScope`` for real runs; the
    publication-sizing loop needs the bounded target-local mapping (community_key,
    nodes, edges) rather than the streaming handle. Materialize exactly as the
    explanation runner does — via ``member_subgraph`` local node indices — so the
    dict is the same bounded shape, never the full giant community. Mappings
    (already-materialized communities, e.g. from a test double or an explanation)
    pass through unchanged.
    """
    community = engine.community(case.person_id, case.anchor.scoring_day)
    if isinstance(community, CommunityScope):
        local = member_subgraph(engine, case.person_id, case.anchor.scoring_day)
        local_original_indices = np.asarray(
            local.original_node_indices, dtype=np.int64
        )
        return community.materialize_local(
            (engine.node_ids[int(index)] for index in local_original_indices),
            target_person_id=case.person_id,
        )
    if isinstance(community, Mapping):
        return community
    raise ValueError("case community must be a CommunityScope or mapping")


def _estimate_full_publication(
    context,
    selected_case,
    explanation,
    *,
    temporary_parent=None,
):
    _stage_log("publication_sizing_start")
    raw_cases = tuple(context.publication_cases)
    publication_cases = sorted(
        (
        item if isinstance(item, tuple) and len(item) == 2 else ("hybrid_only", item)
        for item in raw_cases
        ),
        key=lambda item: (
            0 if item[1].person_id == selected_case.person_id else 1,
            str(item[1].anchor.scoring_day),
            item[0],
            item[1].person_id,
        ),
    )
    with tempfile.TemporaryDirectory(
        prefix="v9-benchmark-sizing-", dir=temporary_parent
    ) as temporary:
        temporary = Path(temporary)
        writer = RecoveryBundleWriter(
            temporary / "stage",
            temporary / "final",
            run_fingerprint={
                "checkpoint_id": context.checkpoint_id,
                "inspections_per_day": INSPECTIONS_PER_DAY,
                "purpose": "giant_observability_publication_dry_run",
            },
            chunk_size=250,
            sidecar_prefix="recovery",
        )
        seen_communities = set()
        hybrid_count = 0
        expected_hybrid_ids = set()
        expected_baseline_ids = set()
        selected_community = explanation.get("community")
        release = getattr(context.engine, "release_snapshot", None)
        try:
            if not isinstance(selected_community, dict):
                selected_community = _case_community(context.engine, selected_case)
            selected_expansions = explanation.get("provenance_expansions", ())
            selected_overlay_stats = _enriched_overlay_stats(
                explanation, selected_community, selected_expansions
            )
        except Exception:
            writer.catalog_store.close()
            raise
        finally:
            if callable(release):
                release(selected_case.anchor.scoring_day)
            gc.collect()
        projected_overlay_accounted_bytes = []
        projected_overlay_observation_counts = []
        try:
            for case_index, (cohort, case) in enumerate(publication_cases, start=1):
                is_selected = case.person_id == selected_case.person_id
                community = None
                try:
                    community = (
                        selected_community
                        if is_selected
                        else _case_community(context.engine, case)
                    )
                    community_key = community["community_key"]
                    if community_key not in seen_communities:
                        writer.write_community(_community_stream_source(community))
                        seen_communities.add(community_key)
                    case_id = f"case:{case.person_id}"
                    if cohort == "hybrid_only":
                        projected, expansions = _project_hybrid_explanation(
                            case, community, selected_case, explanation
                        )
                        enriched_stats = _enriched_overlay_stats(
                            projected, community, expansions
                        )
                        omitted_records = max(
                            0,
                            selected_overlay_stats["record_count"]
                            - enriched_stats["record_count"],
                        )
                        conservative_padding = max(
                            0,
                            selected_overlay_stats["bytes"]
                            - enriched_stats["bytes"],
                        ) + omitted_records * 512
                        projected["sizing_conservative_overlay_padding_bytes"] = (
                            conservative_padding
                        )
                        if conservative_padding:
                            projected["sizing_conservative_overlay_padding"] = (
                                "x" * conservative_padding
                            )
                        projected_overlay_accounted_bytes.append(
                            enriched_stats["bytes"] + conservative_padding
                        )
                        projected_overlay_observation_counts.append(
                            enriched_stats["provenance_observation_count"]
                        )
                        record = _bundle_case_record(
                            case, cohort, community_key, explanation=projected
                        )
                        writer.write_case(
                            cohort,
                            record,
                            explanation=projected,
                            validation_metadata=projected["llm_narrative"],
                            overlay_evidence=_overlay_stream_source(
                                projected, community, expansions
                            ),
                        )
                        expected_hybrid_ids.add(case_id)
                        hybrid_count += 1
                    else:
                        writer.write_case(
                            cohort,
                            _bundle_case_record(case, cohort, community_key),
                        )
                        expected_baseline_ids.add(case_id)
                finally:
                    if callable(release):
                        release(case.anchor.scoring_day)
                    if is_selected:
                        explanation.pop("community", None)
                        selected_community = None
                    if community is not None:
                        del community
                    gc.collect()
                if case_index == 1 or case_index % 10 == 0:
                    _stage_log(
                        "publication_case_released",
                        cases_processed=case_index,
                        cases_total=len(publication_cases),
                    )
            manifest = writer.finalize(
                expected_hybrid_case_ids=expected_hybrid_ids,
                expected_baseline_case_ids=expected_baseline_ids,
                policy={
                    "observability_seed": 0,
                    "gnn_arm": "sage",
                    "surrounding_results_seeds": list(RESTART_SEEDS),
                    "inspections_per_day": INSPECTIONS_PER_DAY,
                },
                summary={
                    "sizing_dry_run": True,
                    "hybrid_only_count": len(expected_hybrid_ids),
                    "baseline_only_count": len(expected_baseline_ids),
                },
            )
            published_root = temporary / "final"
            published_bytes = _tree_size(published_root)
            published_files = sum(
                path.is_file() for path in published_root.rglob("*")
            )
            _stage_log(
                "publication_sizing_finalized",
                bytes=published_bytes,
                files=published_files,
            )
        finally:
            if not writer.catalog_store.closed:
                writer.catalog_store.close()
    return {
        "estimated_publication_bytes": int(published_bytes),
        "estimated_required_free_bytes": int(published_bytes * 2),
        "publication_estimate_basis": (
            "recovery_bundle_dry_run_finalized_exact_cohorts_complete_"
            "communities_overlays_provenance_catalog_day_state_indexes_"
            "manifests_pointer_chunks_250_with_selected_validated_gemma_"
            "projection"
        ),
        "publication_copy_policy": (
            "same_filesystem_atomic_bundle_then_copy_on_write_clone_when_"
            "available_else_hash_verified_physical_copy"
        ),
        "publication_community_count": len(seen_communities),
        "publication_case_count": len(publication_cases),
        "publication_hybrid_explanation_projection_count": hybrid_count,
        "publication_chunk_size": 250,
        "published_bundle_file_count": int(published_files),
        "published_bundle_id": manifest["bundle_id"],
        "selected_representative_overlay_bytes": int(
            selected_overlay_stats["bytes"]
        ),
        "projected_min_overlay_accounted_bytes": int(
            min(projected_overlay_accounted_bytes)
            if projected_overlay_accounted_bytes
            else 0
        ),
        "selected_representative_overlay_provenance_observation_count": int(
            selected_overlay_stats["provenance_observation_count"]
        ),
        "projected_min_overlay_provenance_observation_count": int(
            min(projected_overlay_observation_counts)
            if projected_overlay_observation_counts
            else 0
        ),
    }


def _process_peak_rss_bytes():
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _atomic_write(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.tmp-", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_canonical_json(payload))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)


def _run_benchmark_unprotected(
    corpus_dir,
    checkpoint_path,
    output_path,
    *,
    context_loader: Callable = _load_verified_context,
    component_size: Callable = _component_node_count,
    explanation_runner: Callable = _run_case_explanation,
    publication_estimator: Callable = _estimate_full_publication,
    instrumentation=None,
    preflight_runner: Callable | None = None,
    structural_runner: Callable | None = None,
):
    """Verify a checkpoint and benchmark its largest Hybrid-only component."""
    started = time.perf_counter()
    _stage_log("benchmark_start", instrumentation=instrumentation, started_at=started)
    context = context_loader(corpus_dir, checkpoint_path)
    balanced = _benchmark_balanced_controls(
        context,
        preflight_runner=preflight_runner,
        structural_runner=structural_runner,
        instrumentation=instrumentation,
        started_at=started,
    )
    selection_context = context
    if balanced is not None:
        selected_ids = set(balanced["selection"].selected_ids["hybrid_only"])
        selected_cases = tuple(
            case for case in context.cases if f"case:{case.person_id}" in selected_ids
        )
        if not selected_cases:
            raise ValueError("balanced selection produced no Hybrid benchmark case")
        missing_ids = sorted(
            selected_ids - {f"case:{case.person_id}" for case in context.cases}
        )
        if missing_ids:
            raise ValueError(
                "balanced selection references Hybrid benchmark cases missing from "
                f"the verified context: {', '.join(missing_ids)}"
            )
        selection_context = replace(context, cases=selected_cases)
    _stage_log(
        "selection_start", instrumentation=instrumentation, started_at=started, candidates=len(selection_context.cases)
    )
    community_node_count, case = _select_largest_case_bounded(
        selection_context, component_size, instrumentation=instrumentation, started_at=started
    )
    balanced_measurements = {}
    if balanced is not None:
        counts = balanced["counts"]
        hybrid_forward_counts = []
        hybrid_started = time.perf_counter()
        for candidate in selection_context.cases:
            _stage_log(
                "explanation_start",
                instrumentation=instrumentation,
                started_at=started,
                person_id=candidate.person_id,
            )
            candidate_measured = None
            try:
                candidate_measured = explanation_runner(
                    context.engine, candidate, RESTART_SEEDS
                )
                try:
                    _validate_benchmark_measurement(candidate_measured)
                except Exception as validation_error:
                    if isinstance(candidate_measured, Mapping):
                        validation_error.measurement = candidate_measured
                    raise
                balanced_measurements[candidate.person_id] = candidate_measured
                hybrid_forward_counts.append(
                    int(candidate_measured["gnnexplainer_encoder_forward_count"])
                )
                counts["hybrid_attempted"] += 1
                source = (
                    candidate_measured.get("explanation", {})
                    .get("llm_narrative", {})
                    .get("source")
                )
                if source == "deterministic_template":
                    counts["hybrid_fallback"] += 1
                else:
                    counts["hybrid_generated"] += 1
            except Exception as error:
                failed_measurement = _failed_explanation_measurement(error)
                if failed_measurement is not None:
                    hybrid_forward_counts.append(
                        int(
                            failed_measurement[
                                "gnnexplainer_encoder_forward_count"
                            ]
                        )
                    )
                else:
                    forward_count = _failed_explanation_forward_count(error)
                    if forward_count is not None:
                        hybrid_forward_counts.append(forward_count)
                counts["hybrid_attempted"] += 1
                counts["hybrid_failed"] += 1
            _stage_log(
                "explanation_complete",
                instrumentation=instrumentation,
                started_at=started,
                person_id=candidate.person_id,
            )
        counts["hybrid_explanations_wall_seconds"] = max(
            0.0, time.perf_counter() - hybrid_started
        )
        if not balanced_measurements:
            raise ValueError("all selected Hybrid benchmark explanations failed")
        if counts["hybrid_attempted"] != counts["hybrid_selected"]:
            raise ValueError(
                "benchmark did not process every selected Hybrid case: attempted "
                f"{counts['hybrid_attempted']} of {counts['hybrid_selected']}"
            )
        if counts["baseline_attempted"] != counts["baseline_selected"]:
            raise ValueError(
                "benchmark did not process every selected Baseline control: attempted "
                f"{counts['baseline_attempted']} of {counts['baseline_selected']}"
            )
        counts["hybrid_gnnexplainer_encoder_forward_count"] = sum(
            hybrid_forward_counts
        )
        if case.person_id not in balanced_measurements:
            case = max(
                (candidate for candidate in selection_context.cases if candidate.person_id in balanced_measurements),
                key=lambda candidate: int(component_size(context.engine, candidate)),
            )
            community_node_count = int(component_size(context.engine, case))
        measured = balanced_measurements[case.person_id]
        _stage_log(
            "hybrid_explanations_complete",
            instrumentation=instrumentation,
            started_at=started,
            requested=counts["hybrid_requested"],
            attempted=counts["hybrid_attempted"],
            generated=counts["hybrid_generated"],
            fallback=counts["hybrid_fallback"],
            failed=counts["hybrid_failed"],
        )
    else:
        _stage_log(
            "explanation_start", instrumentation=instrumentation, started_at=started, person_id=case.person_id
        )
        measured = explanation_runner(context.engine, case, RESTART_SEEDS)
        _stage_log(
            "explanation_complete", instrumentation=instrumentation, started_at=started, person_id=case.person_id
        )

    restart_seeds = measured.get("restart_seeds")
    if tuple(restart_seeds or ()) != RESTART_SEEDS:
        raise ValueError("benchmark restart seeds must be exactly [0, 1, 2]")
    factor_forward_count = measured.get("factor_actual_encoder_forward_count")
    if (
        not isinstance(factor_forward_count, int)
        or isinstance(factor_forward_count, bool)
        or not 0 <= factor_forward_count <= MAX_FACTOR_ENCODER_FORWARDS
    ):
        raise ValueError(
            "benchmark counterfactual forward count exceeds the actual encoder bound of 25"
        )
    factor_count = measured.get("salient_factor_count")
    if not isinstance(factor_count, int) or not 0 <= factor_count <= 25:
        raise ValueError(
            "salient factor count exceeds the constant bound of 25"
        )
    faithfulness_forward_count = measured.get(
        "faithfulness_actual_encoder_forward_count"
    )
    if (
        not isinstance(faithfulness_forward_count, int)
        or isinstance(faithfulness_forward_count, bool)
        or not 0
        <= faithfulness_forward_count
        <= MAX_FAITHFULNESS_ENCODER_FORWARDS
    ):
        raise ValueError("faithfulness actual encoder forwards exceed bound of 6")
    diagnostic_forward_count = factor_forward_count + faithfulness_forward_count
    if diagnostic_forward_count > MAX_DIAGNOSTIC_ENCODER_FORWARDS:
        raise ValueError("total diagnostic actual encoder forwards exceed bound of 31")
    other_forward_count = measured.get("other_encoder_forward_count")
    if other_forward_count != 0:
        raise ValueError("benchmark observed unclassified other encoder forwards")
    explainer_forward_count = measured.get("gnnexplainer_encoder_forward_count")
    if (
        not isinstance(explainer_forward_count, int)
        or isinstance(explainer_forward_count, bool)
        or explainer_forward_count <= 0
    ):
        raise ValueError("benchmark requires positive GNNExplainer encoder forwards")
    explanation = measured.get("explanation")
    publication = publication_estimator(context, case, explanation)
    if not str(publication.get("publication_estimate_basis", "")).startswith(
        "recovery_bundle_dry_run"
    ):
        raise ValueError("publication estimate must use recovery bundle dry-run sizing")
    result = {
        "schema_version": "1.0",
        "checkpoint_id": context.checkpoint_id,
        "checkpoint_verification": "hash_and_tensor_manifest_verified",
        "production_contract": {
            "node_count": EXPECTED_NODE_COUNT,
            "seeds": list(RESTART_SEEDS),
            "epochs": 18,
            "train_bucket": "Q",
            "valid_sample": 20_000,
            "inspections_per_day": INSPECTIONS_PER_DAY,
        },
        "target_person_id": case.person_id,
        "scoring_day": str(case.anchor.scoring_day),
        "community_node_count": int(community_node_count),
        "local_explainer_node_count": int(measured["local_node_count"]),
        "local_explainer_edge_count": int(measured["local_edge_count"]),
        "salient_factor_count": int(factor_count),
        "factor_scoring_call_count": int(measured["factor_scoring_call_count"]),
        "factor_scoring_cache_hit_count": int(
            measured["factor_scoring_cache_hit_count"]
        ),
        "factor_actual_encoder_forward_count": int(factor_forward_count),
        "factor_actual_encoder_forward_bound": MAX_FACTOR_ENCODER_FORWARDS,
        "faithfulness_scoring_call_count": int(
            measured["faithfulness_scoring_call_count"]
        ),
        "faithfulness_scoring_cache_hit_count": int(
            measured["faithfulness_scoring_cache_hit_count"]
        ),
        "faithfulness_actual_encoder_forward_count": int(
            faithfulness_forward_count
        ),
        "faithfulness_actual_encoder_forward_bound": (
            MAX_FAITHFULNESS_ENCODER_FORWARDS
        ),
        "diagnostic_actual_encoder_forward_count": int(
            diagnostic_forward_count
        ),
        "diagnostic_actual_encoder_forward_bound": (
            MAX_DIAGNOSTIC_ENCODER_FORWARDS
        ),
        "gnnexplainer_encoder_forward_count": int(
            explainer_forward_count
        ),
        "other_encoder_forward_count": int(other_forward_count),
        "restart_seeds": list(RESTART_SEEDS),
        "wall_runtime_seconds": max(0.0, time.perf_counter() - started),
        "process_peak_rss_bytes": _process_peak_rss_bytes(),
        "process_peak_rss_scope": "process_lifetime_high_water_mark",
        "process_peak_rss_source": "resource.getrusage(RUSAGE_SELF).ru_maxrss",
        "counts": None if balanced is None else dict(balanced["counts"]),
        "balanced_selection": None
        if balanced is None
        else {
            "hybrid_limit": 20,
            "baseline_limit": 10,
            "eligible_hybrid_ids": list(balanced["eligible_hybrid_ids"]),
            "selected_ids": {
                cohort: list(ids)
                for cohort, ids in balanced["selection"].selected_ids.items()
            },
            "preflight": balanced["preflight"],
            "baseline_structural_case_ids": balanced["baseline_structural_case_ids"],
            "baseline_failures": list(balanced["baseline_failures"]),
            "baseline_gnnexplainer_encoder_forward_count": balanced[
                "baseline_gnnexplainer_encoder_forward_count"
            ],
            "baseline_explainer_call_count": balanced["baseline_explainer_call_count"],
            "baseline_explainer_measurement": balanced[
                "baseline_explainer_measurement"
            ],
            "counts": dict(balanced["counts"]),
        },
        **publication,
    }
    _atomic_write(output_path, result)
    _stage_log(
        "benchmark_complete", instrumentation=instrumentation, started_at=started, output=Path(output_path)
    )
    return result


def run_benchmark(
    corpus_dir,
    checkpoint_path,
    output_path,
    *,
    context_loader: Callable = _load_verified_context,
    component_size: Callable = _component_node_count,
    explanation_runner: Callable = _run_case_explanation,
    publication_estimator: Callable = _estimate_full_publication,
    instrumentation=None,
    preflight_runner: Callable | None = None,
    structural_runner: Callable | None = None,
):
    holder = {}

    def capturing_loader(*args):
        context = context_loader(*args)
        holder["context"] = context
        return context

    try:
        return _run_benchmark_unprotected(
            corpus_dir,
            checkpoint_path,
            output_path,
            context_loader=capturing_loader,
            component_size=component_size,
            explanation_runner=explanation_runner,
            publication_estimator=publication_estimator,
            instrumentation=instrumentation,
            preflight_runner=preflight_runner,
            structural_runner=structural_runner,
        )
    finally:
        context = holder.get("context")
        release = (
            None
            if context is None
            else getattr(context.engine, "release_snapshot", None)
        )
        if callable(release):
            days = {
                case.anchor.scoring_day
                for case in tuple(context.cases)
                + tuple(
                    item[1]
                    if isinstance(item, tuple) and len(item) == 2
                    else item
                    for item in context.publication_cases
                )
            }
            for day in days:
                release(day)
        gc.collect()
        if context is not None:
            _stage_log("benchmark_cache_cleanup_complete")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark the largest real Hybrid-only V9 explanation from a "
            "verified scoring checkpoint."
        )
    )
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    result = run_benchmark(args.corpus, args.checkpoint, args.output)
    print(json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
