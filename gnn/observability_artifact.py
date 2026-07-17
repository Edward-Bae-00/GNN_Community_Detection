"""Compose the separate seed-0 recovery-observability diagnostic artifact."""
from __future__ import annotations

import json
from collections.abc import Mapping

import numpy as np
import pandas as pd

from gnn.explanation_narrative import (
    MODEL_TAG,
    PROMPT_VERSION,
    build_fact_packet,
    generate_narrative,
    validate_candidate,
)
from gnn.recovery_observability import (
    HybridOnlyCase,
    build_decision_trace,
    build_rank_reference,
    recovery_overlap,
    representative_attempt_order,
    simulate_recovery_run,
)
from gnn.sage_explainer import (
    compose_case_explanation,
    json_safe,
    validate_explanation_payload,
)


_REQUIRED_PARITY = (
    "production_seed0_probability",
    "pooled_logit_decomposition",
    "frozen_percentile",
    "frozen_daily_hybrid_rank",
)
_SCOPE_ERROR = "observability requires the surrounding three-seed GraphSAGE run"


def _positive_integer(value, *, field_name):
    if (
        not isinstance(value, (int, np.integer))
        or isinstance(value, (bool, np.bool_))
        or value <= 0
    ):
        raise ValueError(f"{field_name} must be a positive integer")
    return int(value)


def _explanation_limit(value):
    if (
        not isinstance(value, (int, np.integer))
        or isinstance(value, (bool, np.bool_))
        or not 0 <= value <= 40
    ):
        raise ValueError("explanation_limit must be an integer between 0 and 40")
    return int(value)


def _validated_scope(gnn_arm, surrounding_seeds):
    try:
        seeds = tuple(surrounding_seeds)
    except TypeError as exc:
        raise ValueError(_SCOPE_ERROR) from exc
    if gnn_arm != "sage" or seeds != (0, 1, 2):
        raise ValueError(_SCOPE_ERROR)
    return seeds


def _prepared_pool(pool):
    if not isinstance(pool, pd.DataFrame):
        raise ValueError("pool must be a pandas DataFrame")
    required = {"event_id", "primary_person_id", "t", "hidden"}
    missing = sorted(required.difference(pool.columns))
    if missing:
        raise ValueError(f"pool missing required columns: {', '.join(missing)}")
    rows = pool.reset_index(drop=True).copy(deep=True)
    people = rows["primary_person_id"]
    if people.isna().any() or people.map(str).str.strip().eq("").any():
        raise ValueError(
            "primary_person_id must contain non-null, non-blank values"
        )
    rows["primary_person_id"] = people.map(str)
    scoring_days = pd.to_datetime(rows["t"], utc=True, errors="coerce").dt.floor(
        "D"
    )
    if scoring_days.isna().any():
        raise ValueError("pool contains invalid timestamps")
    return rows, scoring_days


def _rank_row_bindings(rows, scoring_days):
    return tuple(
        (
            int(row_index),
            str(rows.at[row_index, "primary_person_id"]),
            pd.Timestamp(scoring_days.iloc[row_index]),
        )
        for row_index in range(len(rows))
    )


def build_hybrid_only_cases(
    pool,
    overlap,
    baseline_run,
    hybrid_run,
    reference,
    explanation_engine,
):
    """Build the complete lightweight Hybrid-only cohort."""
    rows, scoring_days = _prepared_pool(pool)
    cases = []
    people = rows["primary_person_id"].to_numpy(dtype=str)
    for person_id in sorted(overlap.hybrid_only_ids):
        anchor = hybrid_run.first_recovery[person_id]
        same_day_rows = tuple(
            int(index)
            for index in np.flatnonzero(
                (people == person_id)
                & scoring_days.eq(anchor.scoring_day).to_numpy()
            )
        )
        baseline_day = baseline_run.days.get(anchor.scoring_day)
        hybrid_day = hybrid_run.days.get(anchor.scoring_day)
        if baseline_day is None or hybrid_day is None:
            raise ValueError("recovery anchor day is missing from a recovery run")
        baseline_candidates = baseline_day.candidate_row_indices
        hybrid_candidates = hybrid_day.candidate_row_indices
        trace = build_decision_trace(
            reference,
            row_index=anchor.row_index,
            baseline_candidate_row_indices=baseline_candidates,
            hybrid_candidate_row_indices=hybrid_candidates,
            daily_budget=hybrid_run.daily_budget,
        )
        categories = tuple(
            sorted(
                set(
                    explanation_engine.relationship_categories(
                        person_id, anchor.scoring_day
                    )
                )
            )
        )
        cases.append(
            HybridOnlyCase(
                person_id=person_id,
                anchor=anchor,
                baseline_rank=int(trace["baseline_rank"]),
                gnn_rank=int(trace["seed0_gnn_rank"]),
                hybrid_rank=int(trace["seed0_hybrid_rank"]),
                baseline_percentile=float(trace["baseline_percentile"]),
                gnn_percentile=float(trace["seed0_gnn_percentile"]),
                relationship_categories=categories,
                scoring_period=anchor.scoring_day.strftime("%Y-%m"),
                same_day_person_row_indices=same_day_rows,
                baseline_candidate_row_indices=baseline_candidates,
                hybrid_candidate_row_indices=hybrid_candidates,
                decision_trace=trace,
            )
        )
    return cases


def explain_case(explanation_engine, case):
    """Use a test adapter when supplied, otherwise the production composer."""
    engine_method = getattr(explanation_engine, "explain_case", None)
    if callable(engine_method):
        return engine_method(case)
    return compose_case_explanation(explanation_engine, case)


def _detached_json_object(value, *, field_name):
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a JSON object")
    try:
        encoded = json.dumps(
            json_safe(value),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be deterministic and JSON-safe") from exc
    decoded = json.loads(encoded)
    if not isinstance(decoded, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return decoded


def _as_utc_timestamp(value, *, field_name):
    try:
        timestamp = pd.to_datetime(value, utc=True, errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a valid timestamp") from exc
    if not isinstance(timestamp, pd.Timestamp) or pd.isna(timestamp):
        raise ValueError(f"{field_name} must be a valid timestamp")
    return timestamp


def _community_evidence(community):
    nodes = community.get("nodes", [])
    edges = community.get("edges", [])
    expansions = community.get("provenance_expansions", [])
    if not all(isinstance(items, list) for items in (nodes, edges, expansions)):
        raise ValueError("explanation community evidence must use lists")
    nodes = list(nodes)
    edges = list(edges)
    for expansion in expansions:
        if not isinstance(expansion, Mapping):
            raise ValueError("explanation provenance expansion must be an object")
        expansion_nodes = expansion.get("nodes", [])
        expansion_edges = expansion.get("edges", [])
        if not isinstance(expansion_nodes, list) or not isinstance(
            expansion_edges, list
        ):
            raise ValueError("explanation provenance evidence must use lists")
        nodes.extend(expansion_nodes)
        edges.extend(expansion_edges)
    return nodes, edges


def _validate_complete_explanation(explanation):
    validate_explanation_payload(explanation)
    parity = explanation.get("parity")
    if not isinstance(parity, Mapping) or any(
        parity.get(key) is not True for key in _REQUIRED_PARITY
    ):
        raise ValueError("explanation parity validation failed")
    community = explanation.get("community")
    if not isinstance(community, Mapping) or community.get("complete") is not True:
        raise ValueError("incomplete explanation community")
    snapshot = _as_utc_timestamp(
        explanation.get("scoring_day"), field_name="explanation scoring_day"
    )
    boundary = explanation.get("evidence_boundary")
    if not isinstance(boundary, Mapping) or boundary.get("edge_rule") != (
        "available_time < snapshot"
    ) or boundary.get("caught_rule") != (
        "label_available_time_utc < snapshot"
    ):
        raise ValueError("invalid explanation evidence boundary")
    boundary_snapshot = _as_utc_timestamp(
        boundary.get("snapshot"), field_name="evidence boundary snapshot"
    )
    if boundary_snapshot != snapshot:
        raise ValueError("evidence boundary snapshot is not strictly as-of")

    nodes, edges = _community_evidence(community)
    for edge in edges:
        if not isinstance(edge, Mapping):
            raise ValueError("explanation community edge must be an object")
        source_row_ids = edge.get("source_row_ids")
        if (
            not isinstance(source_row_ids, list)
            or not source_row_ids
            or any(
                not isinstance(source_row_id, str) or not source_row_id.strip()
                for source_row_id in source_row_ids
            )
            or len(set(source_row_ids)) != len(source_row_ids)
        ):
            raise ValueError(
                "edge strictly as-of provenance requires unique source_row_ids"
            )
        observations = edge.get("observations", [])
        if not isinstance(observations, list):
            raise ValueError("explanation edge observations must be a list")
        if not observations:
            raise ValueError("edge evidence lacks strictly as-of provenance")
        observation_source_ids = []
        for observation in observations:
            if not isinstance(observation, Mapping):
                raise ValueError("explanation edge observation must be an object")
            source_row_id = observation.get("source_row_id")
            if not isinstance(source_row_id, str) or not source_row_id.strip():
                raise ValueError(
                    "edge observation lacks strictly as-of source_row_id provenance"
                )
            observation_source_ids.append(source_row_id)
            available_time = _as_utc_timestamp(
                observation.get("available_time"),
                field_name="edge available_time",
            )
            if not available_time < snapshot:
                raise ValueError("edge evidence is not strictly as-of")
        if (
            len(set(observation_source_ids)) != len(observation_source_ids)
            or sorted(observation_source_ids) != sorted(source_row_ids)
        ):
            raise ValueError(
                "edge strictly as-of observations disagree with source_row_ids"
            )
    for node in nodes:
        if not isinstance(node, Mapping):
            raise ValueError("explanation community node must be an object")
        caught_before = node.get("caught_before_snapshot", False)
        if not isinstance(caught_before, bool):
            raise ValueError("caught-before-snapshot evidence must be boolean")
        caught_time = node.get("caught_label_available_time")
        if caught_before is True:
            available_time = _as_utc_timestamp(
                caught_time, field_name="caught label available time"
            )
            if not available_time < snapshot:
                raise ValueError("caught evidence is not strictly as-of")
        elif caught_time is not None:
            raise ValueError(
                "caught label time is exposed without strictly as-of caught evidence"
            )
    return explanation


def _validate_grounded_narrative(packet, narrative):
    required_fields = {
        "source",
        "model",
        "prompt_version",
        "summary",
        "summary_source_refs",
        "claims",
        "validated",
    }
    if set(narrative) != required_fields or narrative.get("validated") is not True:
        raise ValueError("explanation narrative metadata is invalid")
    source = narrative.get("source")
    model = narrative.get("model")
    invalid_source_metadata = (
        source not in {"llm", "deterministic_template"}
        or (source == "llm" and model != MODEL_TAG)
        or (source == "deterministic_template" and model is not None)
        or narrative.get("prompt_version") != PROMPT_VERSION
    )
    if invalid_source_metadata:
        raise ValueError("explanation narrative source metadata is invalid")
    validated = validate_candidate(
        packet,
        {
            "summary": {
                "text": narrative.get("summary"),
                "source_refs": narrative.get("summary_source_refs"),
            },
            "claims": narrative.get("claims"),
        },
    )
    if (
        narrative["summary"] != validated["summary"]["text"]
        or narrative["summary_source_refs"]
        != validated["summary"]["source_refs"]
        or narrative["claims"] != validated["claims"]
    ):
        raise ValueError("explanation narrative is not grounded in its fact packet")
    return narrative


def explain_representatives(
    cases,
    explanation_engine,
    *,
    narrative_builder,
    limit,
):
    """Attempt deterministic representatives until the success limit is met."""
    explanations = []
    failures = []
    for case in cases:
        if len(explanations) >= limit:
            break
        try:
            explanation = _detached_json_object(
                explain_case(explanation_engine, case),
                field_name="explanation",
            )
            if (
                explanation.get("case_id") != f"case:{case.person_id}"
                or explanation.get("person_id") != case.person_id
                or explanation.get("event_id") != case.anchor.event_id
                or explanation.get("decision_trace")
                != case.decision_trace_jsonable()
                or _as_utc_timestamp(
                    explanation.get("scoring_day"),
                    field_name="explanation scoring_day",
                )
                != case.anchor.scoring_day
            ):
                raise ValueError("explanation does not match its recovery case")
            _validate_complete_explanation(explanation)
            fact_packet = _detached_json_object(
                build_fact_packet(explanation), field_name="fact packet"
            )
            builder_packet = _detached_json_object(
                fact_packet, field_name="narrative builder fact packet"
            )
            narrative = _detached_json_object(
                narrative_builder(builder_packet), field_name="narrative"
            )
            _validate_grounded_narrative(fact_packet, narrative)
            explanation["llm_narrative"] = narrative
            _validate_complete_explanation(explanation)
            explanations.append(explanation)
        except (KeyError, RuntimeError, ValueError) as error:
            failures.append(
                {
                    "person_id": case.person_id,
                    "event_id": case.anchor.event_id,
                    "reason_code": type(error).__name__,
                    "message": str(error),
                }
            )
    return explanations, failures


def serialize_artifact(
    reference,
    overlap,
    cases,
    explanations,
    failures,
    *,
    seeds,
    blend_weight,
    inspections_per_day,
    explanation_limit,
):
    explanation_by_person = {
        explanation["person_id"]: explanation for explanation in explanations
    }
    lightweight = []
    for case in cases:
        explanation = explanation_by_person.get(case.person_id)
        lightweight.append(
            {
                "case_id": f"case:{case.person_id}",
                "person_id": case.person_id,
                "event_id": case.anchor.event_id,
                "scoring_day": case.anchor.scoring_day.isoformat(),
                "baseline_rank": case.baseline_rank,
                "seed0_gnn_rank": case.gnn_rank,
                "seed0_hybrid_rank": case.hybrid_rank,
                "hybrid_rank_uplift": case.hybrid_rank_uplift,
                "gnn_percentile_uplift": case.gnn_percentile_uplift,
                "relationship_categories": list(case.relationship_categories),
                "stable_factor_status": (
                    explanation.get("stable_factor_status", "unstable")
                    if explanation is not None
                    else "not_explained"
                ),
            }
        )
    return {
        "schema_version": "1.0",
        "policy": {
            "observability_seed": 0,
            "gnn_arm": "sage",
            "surrounding_results_seeds": list(seeds),
            "inspections_per_day": int(inspections_per_day),
            "hybrid_blend_weight": float(blend_weight),
            "percentile_reference_id": reference.percentile_reference_id,
        },
        "summary": overlap.summary,
        "coverage": {
            "hybrid_only_count": len(cases),
            "explanation_limit": int(explanation_limit),
            "attempted_count": len(explanations) + len(failures),
            "explained_count": len(explanations),
            "failed_count": len(failures),
        },
        "hybrid_only_cases": lightweight,
        "explanations": explanations,
        "generation_diagnostics": {"failed_attempts": failures},
    }


def validate_artifact_invariants(artifact):
    policy = artifact.get("policy", {})
    if policy.get("observability_seed") != 0 or policy.get("gnn_arm") != "sage":
        raise ValueError("invalid observability scope")
    if policy.get("surrounding_results_seeds") != [0, 1, 2]:
        raise ValueError("invalid surrounding ensemble provenance")

    summary = artifact.get("summary", {})
    if summary.get("overlap_ids_available") is not True:
        raise ValueError("recovery overlap IDs are unavailable")
    required_counts = (
        "baseline_recovered",
        "recovered_by_both",
        "hybrid_only_recovered",
        "baseline_only_recovered",
        "hybrid_total",
        "net_gain",
    )
    if any(
        not isinstance(summary.get(key), int)
        or isinstance(summary.get(key), bool)
        for key in required_counts
    ):
        raise ValueError("recovery overlap summary counts must be integers")
    if summary["baseline_recovered"] != (
        summary["recovered_by_both"] + summary["baseline_only_recovered"]
    ):
        raise ValueError("invalid baseline overlap algebra")
    if summary["hybrid_total"] != (
        summary["recovered_by_both"] + summary["hybrid_only_recovered"]
    ) or summary["net_gain"] != (
        summary["hybrid_total"] - summary["baseline_recovered"]
    ):
        raise ValueError("invalid hybrid overlap algebra")

    cases = artifact.get("hybrid_only_cases", [])
    explanations = artifact.get("explanations", [])
    diagnostics = artifact.get("generation_diagnostics", {})
    failures = diagnostics.get("failed_attempts", [])
    coverage = artifact.get("coverage", {})
    if not all(isinstance(items, list) for items in (cases, explanations, failures)):
        raise ValueError("artifact cohort and attempt payloads must be lists")
    if coverage.get("hybrid_only_count") != len(cases) or len(cases) != summary[
        "hybrid_only_recovered"
    ]:
        raise ValueError("hybrid-only coverage does not match exact overlap")
    if coverage.get("explained_count") != len(explanations) or coverage.get(
        "failed_count"
    ) != len(failures):
        raise ValueError("detailed explanation coverage counts are inconsistent")
    if coverage.get("attempted_count") != len(explanations) + len(failures):
        raise ValueError("attempted explanation coverage count is inconsistent")
    if coverage.get("attempted_count", 0) > len(cases):
        raise ValueError("attempted explanation count exceeds the cohort")
    if len(explanations) > coverage.get("explanation_limit", -1):
        raise ValueError("explained count exceeds explanation_limit")

    case_ids = [case.get("person_id") for case in cases]
    if any(not isinstance(person_id, str) or not person_id for person_id in case_ids):
        raise ValueError("hybrid-only cases require person IDs")
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("hybrid-only case person IDs must be unique")
    attempted_ids = [
        item.get("person_id") for item in [*explanations, *failures]
    ]
    if len(set(attempted_ids)) != len(attempted_ids) or not set(
        attempted_ids
    ).issubset(case_ids):
        raise ValueError("explanation attempts do not match the lightweight cohort")

    for explanation in explanations:
        _validate_complete_explanation(explanation)
        narrative = explanation.get("llm_narrative")
        if not isinstance(narrative, Mapping):
            raise ValueError("explanation narrative is absent or invalid")
        _validate_grounded_narrative(build_fact_packet(explanation), narrative)

    validate_explanation_payload(artifact)
    try:
        json.dumps(artifact, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("artifact must be deterministic and JSON-safe") from exc
    return artifact


def build_observability_artifact(
    *,
    pool,
    baseline_raw,
    seed0_gnn_raw,
    blend_weight,
    caught_times,
    gnn_arm,
    surrounding_seeds,
    explanation_engine,
    explanation_limit=40,
    inspections_per_day=25,
    narrative_builder=generate_narrative,
):
    """Build one validated seed-0 artifact without altering ensemble results."""
    seeds = _validated_scope(gnn_arm, surrounding_seeds)
    limit = _explanation_limit(explanation_limit)
    daily_budget = _positive_integer(
        inspections_per_day, field_name="inspections_per_day"
    )
    if not callable(narrative_builder):
        raise ValueError("narrative_builder must be callable")
    bind_rank_reference = getattr(explanation_engine, "bind_rank_reference", None)
    if not callable(bind_rank_reference):
        raise ValueError("explanation_engine must support bind_rank_reference")

    rows, scoring_days = _prepared_pool(pool)
    reference = build_rank_reference(
        rows, baseline_raw, seed0_gnn_raw, blend_weight
    )
    bind_rank_reference(reference, _rank_row_bindings(rows, scoring_days))
    baseline_run = simulate_recovery_run(
        rows,
        reference.baseline_selection_score,
        arm="baseline",
        daily_budget=daily_budget,
        official_caught_times=caught_times,
    )
    hybrid_run = simulate_recovery_run(
        rows,
        reference.seed0_hybrid_selection_score,
        arm="hybrid_seed0",
        daily_budget=daily_budget,
        official_caught_times=caught_times,
    )
    overlap = recovery_overlap(baseline_run, hybrid_run)
    cases = build_hybrid_only_cases(
        rows,
        overlap,
        baseline_run,
        hybrid_run,
        reference,
        explanation_engine,
    )
    ordered_cases = representative_attempt_order(cases)
    explanations, failures = explain_representatives(
        ordered_cases,
        explanation_engine,
        narrative_builder=narrative_builder,
        limit=limit,
    )
    artifact = serialize_artifact(
        reference,
        overlap,
        ordered_cases,
        explanations,
        failures,
        seeds=seeds,
        blend_weight=reference.blend_weight,
        inspections_per_day=daily_budget,
        explanation_limit=limit,
    )
    safe_artifact = _detached_json_object(artifact, field_name="artifact")
    return validate_artifact_invariants(safe_artifact)
