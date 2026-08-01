"""Compose the separate seed-0 recovery-observability diagnostic artifact."""
from __future__ import annotations

import json
import hashlib
from itertools import groupby
from pathlib import Path
from collections.abc import Mapping

import numpy as np
import pandas as pd

from gnn.explanation_narrative import (
    MODEL_TAG,
    PROMPT_VERSION,
    build_fact_packet,
    generate_narrative,
    preflight_local_model,
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
from gnn.recovery_bundle import RecoveryBundleWriter
from gnn.sage_explainer import (
    CommunityScope,
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
_DEMO_INSPECTIONS_PER_DAY = 5
_RECOVERY_METRICS = (
    "baseline_unique_people_recovered",
    "hybrid_unique_people_recovered",
    "net_unique_people_gain",
)


def _positive_integer(value, *, field_name):
    if (
        not isinstance(value, (int, np.integer))
        or isinstance(value, (bool, np.bool_))
        or value <= 0
    ):
        raise ValueError(f"{field_name} must be a positive integer")
    return int(value)


def _explanation_limit(value):
    if value is None:
        return None
    if (
        not isinstance(value, (int, np.integer))
        or isinstance(value, (bool, np.bool_))
        or value < 0
    ):
        raise ValueError("explanation_limit must be a non-negative integer or None")
    return int(value)


def _validated_scope(gnn_arm, surrounding_seeds):
    try:
        seeds = tuple(surrounding_seeds)
    except TypeError as exc:
        raise ValueError(_SCOPE_ERROR) from exc
    if gnn_arm != "sage" or seeds != (0, 1, 2):
        raise ValueError(_SCOPE_ERROR)
    return seeds


def _validate_seed_level_unique_person_recovery(value, *, blend_weight):
    payload = _detached_json_object(
        value, field_name="seed_level_unique_person_recovery"
    )
    if payload.get("inspections_per_day") != _DEMO_INSPECTIONS_PER_DAY:
        raise ValueError("seed-level recovery must use exactly 5 inspections per day")
    try:
        reported_weight = float(
            payload["common_validation_tuned_fusion_weight"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("seed-level recovery fusion weight is invalid") from exc
    if not np.isfinite(reported_weight) or not np.isclose(
        reported_weight, float(blend_weight), rtol=0.0, atol=1e-12
    ):
        raise ValueError("seed-level recovery fusion weight does not match policy")

    seeds = payload.get("seeds")
    if not isinstance(seeds, Mapping) or tuple(seeds) != ("0", "1", "2"):
        raise ValueError("seed-level recovery requires ordered seeds 0, 1, and 2")

    def validate_counts(record, *, field_name):
        if not isinstance(record, Mapping) or set(record) != set(_RECOVERY_METRICS):
            raise ValueError(f"{field_name} has invalid recovery metrics")
        for metric in _RECOVERY_METRICS:
            if not isinstance(record[metric], int) or isinstance(record[metric], bool):
                raise ValueError(f"{field_name} recovery counts must be integers")
        if record["baseline_unique_people_recovered"] < 0 or record[
            "hybrid_unique_people_recovered"
        ] < 0:
            raise ValueError(f"{field_name} recovery counts must be non-negative")
        if record["net_unique_people_gain"] != (
            record["hybrid_unique_people_recovered"]
            - record["baseline_unique_people_recovered"]
        ):
            raise ValueError(f"{field_name} recovery gain is inconsistent")

    for seed, record in seeds.items():
        validate_counts(record, field_name=f"seed {seed}")
    baseline_counts = {
        record["baseline_unique_people_recovered"] for record in seeds.values()
    }
    if len(baseline_counts) != 1:
        raise ValueError("seed-level recovery must share one baseline result")

    for statistic, reducer in (("mean", np.mean), ("population_sd", np.std)):
        reported = payload.get(statistic)
        if not isinstance(reported, Mapping) or set(reported) != set(
            _RECOVERY_METRICS
        ):
            raise ValueError(f"seed-level recovery {statistic} is invalid")
        for metric in _RECOVERY_METRICS:
            try:
                reported_value = float(reported[metric])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"seed-level recovery {statistic} is invalid"
                ) from exc
            expected = float(reducer([record[metric] for record in seeds.values()]))
            if not np.isfinite(reported_value) or not np.isclose(
                reported_value, expected, rtol=0.0, atol=1e-12
            ):
                raise ValueError(
                    f"seed-level recovery {statistic} does not match seed values"
                )
    validate_counts(
        payload.get("score_averaged_ensemble"),
        field_name="score-averaged ensemble",
    )
    return payload


def _validate_seed0_recovery_overlap(seed_recovery, overlap):
    seed_zero = seed_recovery["seeds"]["0"]
    summary = overlap.summary
    if (
        seed_zero["baseline_unique_people_recovered"]
        != summary["baseline_recovered"]
        or seed_zero["hybrid_unique_people_recovered"] != summary["hybrid_total"]
        or seed_zero["net_unique_people_gain"] != summary["net_gain"]
    ):
        raise ValueError(
            "seed-level recovery seed 0 does not match exact overlap cohorts"
        )


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


def _build_exclusive_cases(
    pool,
    person_ids,
    anchor_run,
    baseline_run,
    hybrid_run,
    reference,
    explanation_engine,
):
    """Build exact case records for one exclusive recovery cohort."""
    rows, scoring_days = _prepared_pool(pool)
    people = rows["primary_person_id"].to_numpy(dtype=str)
    return [
        _build_exclusive_case(
            rows,
            scoring_days,
            people,
            person_id,
            anchor_run,
            baseline_run,
            hybrid_run,
            reference,
            explanation_engine,
        )
        for person_id in sorted(person_ids)
    ]


def _build_exclusive_case(
    rows,
    scoring_days,
    people,
    person_id,
    anchor_run,
    baseline_run,
    hybrid_run,
    reference,
    explanation_engine,
):
    """Build one recovery case so construction failures can be retried."""
    anchor = anchor_run.first_recovery[person_id]
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
    return HybridOnlyCase(
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


def build_hybrid_only_cases(
    pool,
    overlap,
    baseline_run,
    hybrid_run,
    reference,
    explanation_engine,
):
    """Build the complete lightweight Hybrid-only cohort."""
    return _build_exclusive_cases(
        pool,
        overlap.hybrid_only_ids,
        hybrid_run,
        baseline_run,
        hybrid_run,
        reference,
        explanation_engine,
    )


def build_baseline_only_cases(
    pool,
    overlap,
    baseline_run,
    hybrid_run,
    reference,
    explanation_engine,
):
    """Build the complete lightweight Baseline-only cohort."""
    return _build_exclusive_cases(
        pool,
        overlap.baseline_only_ids,
        baseline_run,
        baseline_run,
        hybrid_run,
        reference,
        explanation_engine,
    )


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


def _validate_complete_community(community, snapshot):
    if isinstance(community, CommunityScope):
        if community.complete is not True:
            raise ValueError("incomplete explanation community")
        if community.scoring_day != snapshot:
            raise ValueError("community scoring day does not match its case")
        for value, field_name in (
            (community.component_id, "component_id"),
            (community.community_key, "community_key"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"complete community requires {field_name}")
        for node in community.iter_nodes():
            caught_before = node.get("caught_before_snapshot", False)
            if not isinstance(caught_before, bool):
                raise ValueError("caught-before-snapshot evidence must be boolean")
            caught_time = node.get("caught_label_available_time")
            if caught_before:
                if not _as_utc_timestamp(
                    caught_time, field_name="caught label available time"
                ) < snapshot:
                    raise ValueError("caught evidence is not strictly as-of")
            elif caught_time is not None:
                raise ValueError(
                    "caught label time is exposed without strictly as-of caught evidence"
                )
        provenance = iter(community.iter_provenance())
        for edge in community.iter_edges():
            source_row_ids = edge.get("source_row_ids")
            if (
                not isinstance(source_row_ids, list)
                or not source_row_ids
                or len(set(source_row_ids)) != len(source_row_ids)
            ):
                raise ValueError(
                    "edge strictly as-of provenance requires unique source_row_ids"
                )
            for source_row_id in source_row_ids:
                try:
                    observation = next(provenance)
                except StopIteration as exc:
                    raise ValueError(
                        "edge evidence lacks strictly as-of provenance"
                    ) from exc
                if (
                    observation.get("edge_id") != edge["edge_id"]
                    or observation.get("source_row_id") != source_row_id
                ):
                    raise ValueError(
                        "edge strictly as-of observations disagree with source_row_ids"
                    )
                if not _as_utc_timestamp(
                    observation.get("available_time"),
                    field_name="edge available_time",
                ) < snapshot:
                    raise ValueError("edge evidence is not strictly as-of")
        try:
            next(provenance)
        except StopIteration:
            return community
        raise ValueError("provenance observations reference an unknown edge")
    if not isinstance(community, Mapping) or community.get("complete") is not True:
        raise ValueError("incomplete explanation community")
    community_snapshot = _as_utc_timestamp(
        community.get("scoring_day"), field_name="community scoring_day"
    )
    if community_snapshot != snapshot:
        raise ValueError("community scoring day does not match its case")
    for key_name in ("component_id", "community_key"):
        key = community.get(key_name)
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"complete community requires {key_name}")

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
    return community


def _validate_complete_explanation(explanation):
    validate_explanation_payload(explanation)
    parity = explanation.get("parity")
    if not isinstance(parity, Mapping) or any(
        parity.get(key) is not True for key in _REQUIRED_PARITY
    ):
        raise ValueError("explanation parity validation failed")
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
    community = explanation.get("community")
    overlay_expansions = explanation.get("provenance_expansions", [])
    if overlay_expansions:
        community = dict(community)
        community["provenance_expansions"] = overlay_expansions
    _validate_complete_community(community, snapshot)
    return explanation


def _published_community(community, scoring_day):
    """Detach one complete view and key its exact serialized content."""
    snapshot = _as_utc_timestamp(scoring_day, field_name="case scoring_day")
    detached = _detached_json_object(community, field_name="community")
    _validate_complete_community(detached, snapshot)
    source_key = detached["community_key"]

    # These are producer-only lookup accelerators or duplicated provenance.
    # Nodes and canonical edges remain complete in the published community.
    detached.pop("nodes_by_id", None)
    detached.pop("base_source_row_ids", None)
    for node in detached.get("nodes", []):
        if isinstance(node, dict):
            node.pop("target", None)
    for expansion in detached.get("provenance_expansions", []):
        if not isinstance(expansion, dict):
            continue
        for node in expansion.get("nodes", []):
            if isinstance(node, dict):
                node.pop("target", None)

    detached.pop("community_key", None)
    encoded = json.dumps(
        detached,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    community_key = f"community:sha256:{hashlib.sha256(encoded).hexdigest()}"
    detached["community_key"] = community_key
    return source_key, community_key, detached


def _store_community(communities, source_communities, community, scoring_day):
    if not isinstance(community, Mapping):
        raise ValueError("community must be an object")
    materialized_records = sum(
        len(community.get(field, ()))
        for field in ("nodes", "edges", "provenance_expansions")
    )
    if materialized_records > 10_000:
        raise ValueError(
            "legacy materialization limit exceeded; use the streaming bundle path"
        )
    source_key, key, detached = _published_community(community, scoring_day)
    prior_source = source_communities.get(source_key)
    if prior_source is not None and prior_source != detached:
        raise ValueError(
            f"community key {source_key!r} maps to conflicting payloads"
        )
    source_communities[source_key] = detached
    prior = communities.get(key)
    if prior is not None and prior != detached:
        raise ValueError(f"community key {key!r} maps to conflicting payloads")
    communities[key] = detached
    return key


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
            explanations.append(
                _explain_case_with_narrative(
                    case, explanation_engine, narrative_builder
                )
            )
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


def _explain_case_with_narrative(case, explanation_engine, narrative_builder):
    raw_explanation = explain_case(explanation_engine, case)
    community_scope = getattr(raw_explanation, "community_scope", None)
    explanation = _detached_json_object(
        raw_explanation,
        field_name="explanation",
    )
    if (
        explanation.get("case_id") != f"case:{case.person_id}"
        or explanation.get("person_id") != case.person_id
        or explanation.get("event_id") != case.anchor.event_id
        or explanation.get("decision_trace") != case.decision_trace_jsonable()
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
    if community_scope is not None:
        explanation["_community_scope"] = community_scope
    return explanation


def serialize_artifact(
    reference,
    overlap,
    hybrid_only_cases,
    baseline_only_cases,
    explanations,
    failures,
    communities,
    community_keys_by_case,
    seed_level_unique_person_recovery,
    *,
    seeds,
    blend_weight,
    inspections_per_day,
    explanation_limit,
):
    explanation_by_person = {
        explanation["person_id"]: explanation for explanation in explanations
    }

    def lightweight(case, cohort):
        explanation = explanation_by_person.get(case.person_id)
        case_id = f"case:{case.person_id}"
        return {
            "cohort": cohort,
            "case_id": case_id,
            "community_key": community_keys_by_case[case_id],
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

    hybrid_lightweight = [
        lightweight(case, "hybrid_only") for case in hybrid_only_cases
    ]
    baseline_lightweight = [
        lightweight(case, "baseline_only") for case in baseline_only_cases
    ]
    llm_validated_count = sum(
        explanation.get("llm_narrative", {}).get("source") == "llm"
        and explanation.get("llm_narrative", {}).get("validated") is True
        for explanation in explanations
    )
    complete = (
        len(explanations) == len(hybrid_only_cases)
        and llm_validated_count == len(hybrid_only_cases)
        and not failures
    )
    summary = dict(overlap.summary)
    summary["seed_level_unique_person_recovery"] = (
        seed_level_unique_person_recovery
    )
    return {
        "schema_version": "2.0",
        "policy": {
            "observability_seed": 0,
            "gnn_arm": "sage",
            "surrounding_results_seeds": list(seeds),
            "inspections_per_day": int(inspections_per_day),
            "hybrid_blend_weight": float(blend_weight),
            "percentile_reference_id": reference.percentile_reference_id,
        },
        "summary": summary,
        "coverage": {
            "hybrid_only_count": len(hybrid_only_cases),
            "baseline_only_count": len(baseline_only_cases),
            "attempted_count": len(explanations) + len(failures),
            "explained_count": len(explanations),
            "llm_validated_count": int(llm_validated_count),
            "failed_count": len(failures),
            "complete": complete,
        },
        "cohorts": {
            "hybrid_only": hybrid_lightweight,
            "baseline_only": baseline_lightweight,
        },
        "explanations": explanations,
        "communities": communities,
        "generation_diagnostics": {"failed_attempts": failures},
    }


def validate_artifact_invariants(artifact):
    if artifact.get("schema_version") != "2.0":
        raise ValueError("invalid observability artifact schema version")
    policy = artifact.get("policy", {})
    if policy.get("observability_seed") != 0 or policy.get("gnn_arm") != "sage":
        raise ValueError("invalid observability scope")
    if policy.get("surrounding_results_seeds") != [0, 1, 2]:
        raise ValueError("invalid surrounding ensemble provenance")
    if policy.get("inspections_per_day") != _DEMO_INSPECTIONS_PER_DAY:
        raise ValueError("observability policy must use exactly 5 inspections per day")

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
    _validate_seed_level_unique_person_recovery(
        summary.get("seed_level_unique_person_recovery"),
        blend_weight=policy.get("hybrid_blend_weight"),
    )

    cohorts = artifact.get("cohorts", {})
    if not isinstance(cohorts, Mapping):
        raise ValueError("artifact cohorts must be an object")
    cases = cohorts.get("hybrid_only", [])
    baseline_cases = cohorts.get("baseline_only", [])
    explanations = artifact.get("explanations", [])
    communities = artifact.get("communities", {})
    diagnostics = artifact.get("generation_diagnostics", {})
    failures = diagnostics.get("failed_attempts", [])
    coverage = artifact.get("coverage", {})
    if not isinstance(communities, Mapping) or not all(
        isinstance(items, list)
        for items in (cases, baseline_cases, explanations, failures)
    ):
        raise ValueError("artifact cohort and attempt payloads must be lists")
    if coverage.get("hybrid_only_count") != len(cases) or len(cases) != summary[
        "hybrid_only_recovered"
    ]:
        raise ValueError("hybrid-only coverage does not match exact overlap")
    if coverage.get("baseline_only_count") != len(baseline_cases) or len(
        baseline_cases
    ) != summary["baseline_only_recovered"]:
        raise ValueError("baseline-only coverage does not match exact overlap")
    if coverage.get("explained_count") != len(explanations) or coverage.get(
        "failed_count"
    ) != len(failures):
        raise ValueError("detailed explanation coverage counts are inconsistent")
    if coverage.get("attempted_count") != len(explanations) + len(failures):
        raise ValueError("attempted explanation coverage count is inconsistent")
    if coverage.get("attempted_count", 0) > len(cases):
        raise ValueError("attempted explanation count exceeds the cohort")
    llm_validated_count = sum(
        explanation.get("llm_narrative", {}).get("source") == "llm"
        and explanation.get("llm_narrative", {}).get("validated") is True
        for explanation in explanations
    )
    if coverage.get("llm_validated_count") != llm_validated_count:
        raise ValueError("LLM-validated explanation coverage is inconsistent")
    if (
        coverage.get("complete") is not True
        or len(explanations) != len(cases)
        or llm_validated_count != len(cases)
        or failures
    ):
        raise ValueError("complete Hybrid-only explanation coverage is required")

    case_ids = [case.get("person_id") for case in cases]
    if any(not isinstance(person_id, str) or not person_id for person_id in case_ids):
        raise ValueError("hybrid-only cases require person IDs")
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("hybrid-only case person IDs must be unique")
    baseline_case_ids = [case.get("person_id") for case in baseline_cases]
    if len(set(baseline_case_ids)) != len(baseline_case_ids) or set(
        baseline_case_ids
    ).intersection(case_ids):
        raise ValueError("exclusive recovery cohort person IDs must be disjoint")
    for case in [*cases, *baseline_cases]:
        community_key = case.get("community_key")
        if not isinstance(community_key, str) or community_key not in communities:
            raise ValueError("every exclusive recovery case requires a complete community")
        _validate_complete_community(
            communities[community_key],
            _as_utc_timestamp(case.get("scoring_day"), field_name="case scoring_day"),
        )
        if communities[community_key].get("community_key") != community_key:
            raise ValueError("top-level community key disagrees with its payload")
    attempted_ids = [item.get("person_id") for item in [*explanations, *failures]]
    if len(set(attempted_ids)) != len(attempted_ids) or not set(
        attempted_ids
    ).issubset(case_ids):
        raise ValueError("explanation attempts do not match the lightweight cohort")

    explanation_case_keys = {
        case["case_id"]: case["community_key"] for case in cases
    }
    for explanation in explanations:
        if "community" in explanation:
            raise ValueError("serialized explanations must reference communities")
        community_key = explanation.get("community_key")
        if (
            not isinstance(community_key, str)
            or community_key not in communities
            or explanation_case_keys.get(explanation.get("case_id")) != community_key
        ):
            raise ValueError("explanation community reference is invalid")
        hydrated = dict(explanation)
        hydrated.pop("community_key", None)
        hydrated["community"] = communities[community_key]
        _validate_complete_explanation(hydrated)
        narrative = explanation.get("llm_narrative")
        if not isinstance(narrative, Mapping):
            raise ValueError("explanation narrative is absent or invalid")
        _validate_grounded_narrative(build_fact_packet(hydrated), narrative)

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
    seed_level_unique_person_recovery,
    explanation_limit=None,
    inspections_per_day=5,
    narrative_builder=generate_narrative,
):
    """Build the legacy in-memory artifact for small fixtures and adapters only."""
    seeds = _validated_scope(gnn_arm, surrounding_seeds)
    limit = _explanation_limit(explanation_limit)
    daily_budget = _positive_integer(
        inspections_per_day, field_name="inspections_per_day"
    )
    if daily_budget != _DEMO_INSPECTIONS_PER_DAY:
        raise ValueError("observability inspections_per_day must be exactly 5")
    seed_recovery = _validate_seed_level_unique_person_recovery(
        seed_level_unique_person_recovery,
        blend_weight=blend_weight,
    )
    if not callable(narrative_builder):
        raise ValueError("narrative_builder must be callable")
    bind_rank_reference = getattr(explanation_engine, "bind_rank_reference", None)
    if not callable(bind_rank_reference):
        raise ValueError("explanation_engine must support bind_rank_reference")
    for capability in ("relationship_categories", "community"):
        if not callable(getattr(explanation_engine, capability, None)):
            raise ValueError(
                f"explanation_engine must support {capability}"
            )
    if not callable(getattr(explanation_engine, "explain_case", None)) and not (
        callable(getattr(explanation_engine, "snapshot", None))
        and hasattr(explanation_engine, "rank_reference")
    ):
        raise ValueError("explanation_engine lacks case explanation capability")
    if narrative_builder is generate_narrative:
        preflight_local_model()

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
    _validate_seed0_recovery_overlap(seed_recovery, overlap)
    cases = build_hybrid_only_cases(
        rows,
        overlap,
        baseline_run,
        hybrid_run,
        reference,
        explanation_engine,
    )
    baseline_cases = build_baseline_only_cases(
        rows,
        overlap,
        baseline_run,
        hybrid_run,
        reference,
        explanation_engine,
    )
    ordered_cases = representative_attempt_order(cases)
    if limit is not None and limit < len(ordered_cases):
        raise ValueError(
            "explanation_limit must cover the complete Hybrid-only cohort"
        )
    explanations, failures = explain_representatives(
        ordered_cases,
        explanation_engine,
        narrative_builder=narrative_builder,
        limit=len(ordered_cases),
    )
    if failures or len(explanations) != len(ordered_cases):
        raise ValueError("complete Hybrid-only explanation coverage is required")
    communities = {}
    source_communities = {}
    community_keys_by_case = {}
    for explanation in explanations:
        community = explanation.pop("community", None)
        overlay_expansions = explanation.pop("provenance_expansions", [])
        if overlay_expansions:
            community = dict(community)
            community["provenance_expansions"] = overlay_expansions
        community_key = _store_community(
            communities,
            source_communities,
            community,
            explanation.get("scoring_day"),
        )
        explanation["community_key"] = community_key
        community_keys_by_case[explanation["case_id"]] = community_key
    for case in baseline_cases:
        case_id = f"case:{case.person_id}"
        community = explanation_engine.community(
            case.person_id, case.anchor.scoring_day
        )
        community_keys_by_case[case_id] = _store_community(
            communities,
            source_communities,
            community,
            case.anchor.scoring_day,
        )
    artifact = serialize_artifact(
        reference,
        overlap,
        ordered_cases,
        baseline_cases,
        explanations,
        failures,
        communities,
        community_keys_by_case,
        seed_recovery,
        seeds=seeds,
        blend_weight=reference.blend_weight,
        inspections_per_day=daily_budget,
        explanation_limit=len(ordered_cases),
    )
    safe_artifact = _detached_json_object(artifact, field_name="artifact")
    return validate_artifact_invariants(safe_artifact)


def _bundle_case_record(case, cohort, community_key, explanation=None):
    return {
        "cohort": cohort,
        "case_id": f"case:{case.person_id}",
        "person_id": case.person_id,
        "event_id": case.anchor.event_id,
        "scoring_day": case.anchor.scoring_day.isoformat(),
        "community_key": community_key,
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


def _community_stream_source(community):
    """Split canonical records from raw observations using one-shot iterators."""
    if isinstance(community, CommunityScope):
        return {
            "complete": True,
            "scoring_day": community.scoring_day.isoformat(),
            "component_id": community.component_id,
            "community_key": community.community_key,
            "nodes": community.iter_nodes(),
            "edges": community.iter_edges(),
            "provenance_observations": community.iter_provenance(),
            "provenance_expansions": iter(()),
        }
    key = community["community_key"]

    def nodes():
        for node in community.get("nodes", ()):
            record = dict(node)
            record.pop("target", None)
            yield record

    def edges():
        for edge in community.get("edges", ()):
            record = dict(edge)
            record.pop("observations", None)
            source_row_ids = record.get("source_row_ids")
            if isinstance(source_row_ids, list):
                # A giant/dense community edge may be bounded to
                # MAX_LOCAL_SOURCE_ROWS_PER_EDGE, leaving source_row_count as the
                # full untruncated total while source_row_ids (and the matching
                # observations) hold only the bounded subset. The recovery bundle
                # requires day-membership source_row_count == len(source_row_ids),
                # so normalize to the bounded count here and preserve the true
                # total under complete_source_row_count, exactly as the overlay
                # stream does for attribution edges.
                record["complete_source_row_count"] = int(
                    record.get(
                        "complete_source_row_count",
                        record.get("source_row_count", len(source_row_ids)),
                    )
                )
                record["source_row_count"] = len(source_row_ids)
            yield record

    def provenance():
        for edge in community.get("edges", ()):
            edge_id = edge["edge_id"]
            for observation in edge.get("observations", ()):
                yield {**dict(observation), "edge_id": edge_id}

    return {
        "complete": True,
        "scoring_day": community["scoring_day"],
        "component_id": community["component_id"],
        "community_key": key,
        "nodes": nodes(),
        "edges": edges(),
        "provenance_observations": provenance(),
        "provenance_expansions": iter(()),
    }


def _overlay_stream_source(explanation, community, expansions):
    canonical_edges = {
        edge["edge_id"]: edge for edge in community.get("edges", ())
    }

    def edges():
        for attribution in explanation.get("attributions", {}).get(
            "top_edges", ()
        ):
            edge_id = attribution["edge_id"]
            canonical = canonical_edges.get(edge_id)
            if canonical is None:
                raise ValueError(
                    f"attribution edge {edge_id!r} is absent from its community"
                )
            projected_source_row_ids = list(canonical["source_row_ids"])
            yield {
                **dict(attribution),
                "source_row_ids": projected_source_row_ids,
                "source_row_count": len(projected_source_row_ids),
                "complete_source_row_count": int(
                    attribution.get(
                        "complete_source_row_count",
                        canonical.get(
                            "source_row_count", len(projected_source_row_ids)
                        ),
                    )
                ),
                "source_rows_truncated": (
                    attribution.get(
                        "source_rows_truncated",
                        canonical.get("source_rows_truncated", False),
                    )
                    is True
                ),
                "observations": [
                    dict(observation)
                    for observation in canonical.get("observations", ())
                ],
            }

    return {
        "nodes": iter(
            explanation.get("attributions", {}).get("top_local_nodes", ())
        ),
        "edges": edges(),
        "provenance_expansions": iter(expansions),
    }


def _recovery_run_fingerprint(
    explanation_engine,
    *,
    corpus_identity,
    seeds,
    recovery_run_identity=None,
):
    material_builder = getattr(
        explanation_engine, "observability_fingerprint_material", None
    )
    if not callable(material_builder):
        raise ValueError(
            "explanation_engine must support observability_fingerprint_material"
        )
    material = _detached_json_object(
        material_builder(), field_name="engine fingerprint material"
    )
    run_identity = (
        {"corpus_identity": str(corpus_identity)}
        if recovery_run_identity is None
        else _detached_json_object(
            recovery_run_identity, field_name="recovery run identity"
        )
    )
    return {
        "schema_version": "1.0",
        "corpus_identity": str(corpus_identity),
        "run_identity": run_identity,
        "engine": material,
        "policy": {
            "observability_seed": 0,
            "gnn_arm": "sage",
            "surrounding_seeds": list(seeds),
            "inspections_per_day": _DEMO_INSPECTIONS_PER_DAY,
            "gnnexplainer_restart_seeds": [0, 1, 2],
            "gnnexplainer_epochs": 150,
            "narrative_model": MODEL_TAG,
            "narrative_prompt_version": PROMPT_VERSION,
        },
    }


def build_observability_bundle(
    *,
    pool,
    baseline_raw,
    seed0_gnn_raw,
    blend_weight,
    caught_times,
    gnn_arm,
    surrounding_seeds,
    explanation_engine,
    seed_level_unique_person_recovery,
    staging_root,
    final_root,
    corpus_identity,
    recovery_run_identity=None,
    explanation_limit=None,
    inspections_per_day=5,
    narrative_builder=generate_narrative,
    writer_factory=RecoveryBundleWriter,
):
    """Incrementally build and publish the production recovery bundle."""
    seeds = _validated_scope(gnn_arm, surrounding_seeds)
    limit = _explanation_limit(explanation_limit)
    daily_budget = _positive_integer(
        inspections_per_day, field_name="inspections_per_day"
    )
    if daily_budget != _DEMO_INSPECTIONS_PER_DAY:
        raise ValueError("observability inspections_per_day must be exactly 5")
    seed_recovery = _validate_seed_level_unique_person_recovery(
        seed_level_unique_person_recovery, blend_weight=blend_weight
    )
    if not callable(narrative_builder):
        raise ValueError("narrative_builder must be callable")
    for capability in (
        "bind_rank_reference",
        "relationship_categories",
        "community",
        "release_snapshot",
    ):
        if not callable(getattr(explanation_engine, capability, None)):
            raise ValueError(f"explanation_engine must support {capability}")
    if narrative_builder is generate_narrative:
        preflight_local_model()

    rows, scoring_days = _prepared_pool(pool)
    reference = build_rank_reference(
        rows, baseline_raw, seed0_gnn_raw, blend_weight
    )
    explanation_engine.bind_rank_reference(
        reference, _rank_row_bindings(rows, scoring_days)
    )
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
    _validate_seed0_recovery_overlap(seed_recovery, overlap)
    expected_hybrid_case_ids = {
        f"case:{person_id}" for person_id in overlap.hybrid_only_ids
    }
    expected_baseline_case_ids = {
        f"case:{person_id}" for person_id in overlap.baseline_only_ids
    }
    if limit is not None and limit < len(expected_hybrid_case_ids):
        raise ValueError("explanation_limit must cover the complete Hybrid-only cohort")

    run_fingerprint = _recovery_run_fingerprint(
        explanation_engine,
        corpus_identity=corpus_identity,
        seeds=seeds,
        recovery_run_identity=recovery_run_identity,
    )
    fingerprint_bytes = json.dumps(
        run_fingerprint, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    fingerprint_id = hashlib.sha256(fingerprint_bytes).hexdigest()[:24]
    writer = writer_factory(
        Path(staging_root) / fingerprint_id,
        final_root,
        run_fingerprint=run_fingerprint,
        sidecar_prefix="recovery",
    )

    people = rows["primary_person_id"].to_numpy(dtype=str)
    scheduled = [
        (person_id, "hybrid_only", hybrid_run)
        for person_id in overlap.hybrid_only_ids
    ] + [
        (person_id, "baseline_only", baseline_run)
        for person_id in overlap.baseline_only_ids
    ]
    scheduled.sort(
        key=lambda item: (
            item[2].first_recovery[item[0]].scoring_day,
            0 if item[1] == "hybrid_only" else 1,
            item[0],
        )
    )

    def process_descriptor(descriptor, phase):
        person_id, cohort, anchor_run = descriptor
        anchor = anchor_run.first_recovery[person_id]
        case_id = f"case:{person_id}"
        if writer.has_completed_case(case_id, cohort):
            return True
        if writer.case_attempt_state(case_id)[phase] != "pending":
            return False
        writer.begin_case_attempt(case_id, phase)
        try:
            case = _build_exclusive_case(
                rows,
                scoring_days,
                people,
                person_id,
                anchor_run,
                baseline_run,
                hybrid_run,
                reference,
                explanation_engine,
            )
            if cohort == "hybrid_only":
                explanation = _explain_case_with_narrative(
                    case, explanation_engine, narrative_builder
                )
                local_community = explanation.pop("community")
                community = explanation.pop("_community_scope", local_community)
                expansions = explanation.pop("provenance_expansions", [])
                _validate_complete_community(community, case.anchor.scoring_day)
                community_key = (
                    community.community_key
                    if isinstance(community, CommunityScope)
                    else community["community_key"]
                )
                if community_key not in writer.community_index:
                    writer.write_community(_community_stream_source(community))
                explanation["community_key"] = community_key
                explanation["provenance_expansion_ids"] = [
                    expansion["expansion_id"] for expansion in expansions
                ]
                writer.write_case(
                    cohort,
                    _bundle_case_record(case, cohort, community_key, explanation),
                    explanation=explanation,
                    validation_metadata=explanation["llm_narrative"],
                    overlay_evidence=_overlay_stream_source(
                        explanation, local_community, expansions
                    ),
                )
            else:
                community = explanation_engine.community(
                    case.person_id, case.anchor.scoring_day
                )
                _validate_complete_community(community, case.anchor.scoring_day)
                community_key = (
                    community.community_key
                    if isinstance(community, CommunityScope)
                    else community["community_key"]
                )
                if community_key not in writer.community_index:
                    writer.write_community(_community_stream_source(community))
                writer.write_case(
                    cohort, _bundle_case_record(case, cohort, community_key)
                )
            return True
        except Exception as error:
            writer.record_failure(
                {
                    "case_id": case_id,
                    "cohort": cohort,
                    "person_id": person_id,
                    "event_id": anchor.event_id,
                    "reason_code": type(error).__name__,
                    "message": str(error),
                }
            )
            return False

    def run_pass(descriptors, phase):
        failures = []
        for scoring_day, day_items in groupby(
            descriptors,
            key=lambda item: item[2].first_recovery[item[0]].scoring_day,
        ):
            try:
                for descriptor in day_items:
                    if not process_descriptor(descriptor, phase):
                        failures.append(descriptor)
            finally:
                explanation_engine.release_snapshot(scoring_day)
        return failures

    retry_descriptors = run_pass(scheduled, "first_pass")
    if retry_descriptors:
        run_pass(retry_descriptors, "deferred_retry")

    policy = {
        "observability_seed": 0,
        "gnn_arm": "sage",
        "surrounding_results_seeds": list(seeds),
        "inspections_per_day": daily_budget,
        "hybrid_blend_weight": float(reference.blend_weight),
        "percentile_reference_id": reference.percentile_reference_id,
    }
    summary = dict(overlap.summary)
    summary["seed_level_unique_person_recovery"] = seed_recovery
    manifest = writer.finalize(
        expected_hybrid_case_ids=expected_hybrid_case_ids,
        expected_baseline_case_ids=expected_baseline_case_ids,
        policy=policy,
        summary=summary,
    )
    compact = _detached_json_object(manifest, field_name="bundle manifest")
    if "communities" in compact or "explanations" in compact:
        raise ValueError("production observability manifest must remain compact")
    return compact
