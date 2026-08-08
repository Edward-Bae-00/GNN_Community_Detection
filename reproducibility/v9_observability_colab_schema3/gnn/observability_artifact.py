"""Compose the separate seed-0 recovery-observability diagnostic artifact."""
from __future__ import annotations

import json
import hashlib
import os
import time
import traceback
from itertools import groupby
from pathlib import Path
from collections.abc import Mapping

import numpy as np
import pandas as pd

from gnn.explanation_narrative import (
    MODEL_TAG,
    PROMPT_VERSION,
    bounded_diagnostic_text,
    build_fact_packet,
    generate_narrative,
    preflight_local_model,
    render_template,
    validate_candidate,
)
from gnn.recovery_observability import (
    HybridOnlyCase,
    build_decision_trace,
    build_rank_reference,
    build_recovery_case,
    _round_robin_balanced_cases,
    finalize_recovery_publication,
    materialize_recovered_by_both_case,
    recovery_overlap,
    representative_attempt_order,
    select_balanced_detail_cases,
    simulate_recovery_run,
)
from gnn.recovery_bundle import RecoveryBundleWriter
from gnn.sage_explainer import (
    CommunityScope,
    MAX_EXPLAINER_INPUT_EDGES,
    MAX_EXPLAINER_INPUT_NODES,
    MAX_LOCAL_EXPLANATION_EDGES,
    MAX_LOCAL_EXPLANATION_NODES,
    MAX_LOCAL_SOURCE_ROWS_PER_EDGE,
    MAX_NODE_ATTRIBUTION_SOURCE_ROWS,
    MAX_NODE_FEATURE_MASK_STATS,
    build_flow_stages,
    build_structural_community_control,
    compose_case_explanation,
    explainability_eligibility as exact_explainability_eligibility,
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
SCHEMA2 = "2.0"
SCHEMA3 = "3.0"
DEFAULT_HYBRID_DETAIL_LIMIT = 20
DEFAULT_BASELINE_CONTROL_LIMIT = 10
EXPLAINER_RESTART_SEEDS = (0, 1, 2)
EXPLAINER_EPOCHS = 150
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


def _detail_limit(value, *, field_name):
    if value is None:
        return None
    if (
        not isinstance(value, (int, np.integer))
        or isinstance(value, (bool, np.bool_))
        or value < 0
    ):
        raise ValueError(f"{field_name} must be a non-negative integer or None")
    return int(value)


def _resolve_schema3_limits(
    explanation_limit, hybrid_detail_limit, baseline_control_limit
):
    legacy_limit = _detail_limit(explanation_limit, field_name="explanation_limit")
    hybrid_limit = _detail_limit(
        hybrid_detail_limit, field_name="hybrid_detail_limit"
    )
    baseline_limit = _detail_limit(
        baseline_control_limit, field_name="baseline_control_limit"
    )
    if legacy_limit is not None and hybrid_limit is not None and legacy_limit != hybrid_limit:
        raise ValueError(
            "explanation_limit and hybrid_detail_limit have conflicting values"
        )
    if hybrid_limit is None:
        hybrid_limit = (
            legacy_limit
            if legacy_limit is not None
            else DEFAULT_HYBRID_DETAIL_LIMIT
        )
    if baseline_limit is None:
        baseline_limit = DEFAULT_BASELINE_CONTROL_LIMIT
    return hybrid_limit, baseline_limit


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


def _validate_schema3_evidence_boundary(payload, scoring_day, *, field_name):
    """Re-check the immutable as-of contract before reusing staged evidence."""
    expected_snapshot = _as_utc_timestamp(
        scoring_day, field_name=f"{field_name} scoring_day"
    )
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} is invalid")
    payload_snapshot = _as_utc_timestamp(
        payload.get("scoring_day"), field_name=f"{field_name} scoring_day"
    )
    boundary = payload.get("evidence_boundary")
    if (
        not isinstance(boundary, Mapping)
        or boundary.get("edge_rule") != "available_time < snapshot"
        or boundary.get("caught_rule") != "label_available_time_utc < snapshot"
    ):
        raise ValueError(f"invalid {field_name} evidence boundary")
    boundary_snapshot = _as_utc_timestamp(
        boundary.get("snapshot"), field_name=f"{field_name} boundary snapshot"
    )
    if payload_snapshot != expected_snapshot or boundary_snapshot != expected_snapshot:
        raise ValueError(f"{field_name} evidence boundary is not strictly as-of")
    return payload


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


def _schema3_identity(value, *, corpus_identity):
    supplied = (
        {"corpus_identity": str(corpus_identity)}
        if value is None
        else _detached_json_object(value, field_name="recovery run identity")
    )
    supplied_corpus = supplied.get("corpus_identity")
    if supplied_corpus is not None and str(supplied_corpus) != str(corpus_identity):
        raise ValueError("conflicting corpus identity in recovery run identity")
    supplied["corpus_identity"] = str(corpus_identity)
    checkpoint_id = supplied.get("checkpoint_id")
    if not isinstance(checkpoint_id, str) or not checkpoint_id.strip():
        raise ValueError("schema-3 recovery run identity requires checkpoint_id")
    run_id = supplied.get("run_id", supplied.get("score_run_id"))
    if not isinstance(run_id, str) or not run_id.strip():
        supplied["run_id"] = f"{checkpoint_id}:observability"
    else:
        supplied["run_id"] = run_id
    return supplied


def _schema3_identity_token(value, *, label):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return f"{label}:sha256:{hashlib.sha256(encoded).hexdigest()}"


def _schema3_provenance(
    *, corpus_identity, run_identity, as_of_identity, reference, recovery_arm
):
    return {
        "corpus_identity": str(corpus_identity),
        "run_identity": run_identity,
        "as_of_identity": as_of_identity,
        "percentile_reference_id": reference.percentile_reference_id,
        "recovery_arm": recovery_arm,
        "observability_seed": 0,
        "gnn_arm": "sage",
    }


def _schema3_recovery_case(technical_case, *, cohort, recovery_anchor_arm, reference):
    return build_recovery_case(
        case_id=f"case:{technical_case.person_id}",
        recovery_cohort=cohort,
        anchor_event=technical_case.anchor,
        subject_id=technical_case.person_id,
        subject_display={},
        decision_trace=technical_case.decision_trace_jsonable(),
        recovery_anchor_arm=recovery_anchor_arm,
        hybrid_blend_weight=reference.blend_weight,
        relationship_categories=technical_case.relationship_categories,
        scoring_period=technical_case.scoring_period,
    )


def _schema3_preflight(explanation_engine, technical_case):
    adapter = getattr(explanation_engine, "schema3_preflight_adapter", None)
    if callable(adapter) and getattr(explanation_engine, "schema3_test_adapter", False) is True:
        result = adapter(
            technical_case.person_id, technical_case.anchor.scoring_day
        )
    else:
        result = exact_explainability_eligibility(
            explanation_engine,
            technical_case.person_id,
            technical_case.anchor.scoring_day,
        )
    result = _detached_json_object(result, field_name="explainer preflight")
    required = {
        "eligible", "status", "node_count", "edge_count", "max_nodes",
        "max_edges", "reason_code",
    }
    if (
        set(result) != required
        or not isinstance(result["eligible"], bool)
        or result["status"] not in {"eligible", "community_only"}
        or result["reason_code"] not in {
            "eligible", "test_adapter", "node_limit_exceeded",
            "edge_limit_exceeded", "node_and_edge_limits_exceeded",
        }
        or any(
            not isinstance(result[field], int) or isinstance(result[field], bool)
            or result[field] < 0
            for field in ("node_count", "edge_count", "max_nodes", "max_edges")
        )
        or result["max_nodes"] != MAX_EXPLAINER_INPUT_NODES
        or result["max_edges"] != MAX_EXPLAINER_INPUT_EDGES
        or result["eligible"]
        != (
            result["node_count"] <= MAX_EXPLAINER_INPUT_NODES
            and result["edge_count"] <= MAX_EXPLAINER_INPUT_EDGES
        )
        or (result["eligible"] and result["status"] != "eligible")
        or (not result["eligible"] and result["status"] != "community_only")
    ):
        raise ValueError("explainer preflight result is invalid")
    return result


_PREFLIGHT_CEILING_GRID_NODES = (
    128, 192, 256, 384, 512, 768, 1024, 1536, 2048, 3072, 4096, 8192,
)
_PREFLIGHT_CEILING_GRID_EDGE_FACTORS = (2, 4, 8)


def _preflight_size_summary(preflight):
    """Summarize measured candidate sizes so a ceiling can be chosen from data.

    The per-case counts already reach the artifact, but only after a full run.
    Choosing an eligibility ceiling needs them at the moment preflight finishes,
    and it needs them in a form that answers one question directly: which
    ceiling admits how many candidates.  Eligibility requires a candidate to be
    under *both* limits, so the grid counts pairs rather than each dimension on
    its own.
    """
    sizes = sorted(
        (int(result["node_count"]), int(result["edge_count"]))
        for result in preflight.values()
    )
    if not sizes:
        return {"candidates": 0, "percentiles": {}, "ceiling_grid": [],
                "smallest_by_nodes": []}

    def percentiles(values):
        ordered = sorted(values)
        last = len(ordered) - 1
        return {
            f"p{int(fraction * 100)}": ordered[min(last, int(fraction * last))]
            for fraction in (0.0, 0.5, 0.75, 0.9, 0.95, 0.99, 1.0)
        }

    grid = []
    for max_nodes in _PREFLIGHT_CEILING_GRID_NODES:
        for factor in _PREFLIGHT_CEILING_GRID_EDGE_FACTORS:
            max_edges = max_nodes * factor
            grid.append(
                {
                    "max_nodes": max_nodes,
                    "max_edges": max_edges,
                    "eligible": sum(
                        1
                        for node_count, edge_count in sizes
                        if node_count <= max_nodes and edge_count <= max_edges
                    ),
                }
            )
    return {
        "candidates": len(sizes),
        "percentiles": {
            "node_count": percentiles(node for node, _ in sizes),
            "edge_count": percentiles(edge for _, edge in sizes),
        },
        "ceiling_grid": grid,
        "smallest_by_nodes": [
            {"node_count": node_count, "edge_count": edge_count}
            for node_count, edge_count in sizes[:40]
        ],
    }


def _bounded_stage_failure_reason(reason):
    """Return a stage-log-safe failure reason, or None for a healthy case.

    Stage payloads are printed one JSON object per line and are the only live
    view an operator has of a multi-hour run, so an unbounded exception string
    would make that stream unreadable. ``bounded_diagnostic_text`` applies the
    same limit already used for narrative diagnostics.
    """
    if reason is None:
        return None
    return bounded_diagnostic_text(reason)


_STAGE_TRACEBACK_LIMIT = 4000


def _bounded_stage_traceback(error):
    """Return a bounded traceback for a failed case, or None when it succeeded.

    ``failure_reason`` keeps only ``type: message``, which for a deterministic
    library-internal failure names neither the failing line nor the call path
    that reached it. A schema-3 case costs 20-40 minutes of GNNExplainer and
    counterfactual work before it can fail, and the artifact holding that
    reason is written only after the whole multi-hour run -- so if the
    traceback does not survive the first occurrence, recovering it costs
    another Colab session.
    """
    if error is None:
        return None
    formatted = traceback.format_exception(type(error), error, error.__traceback__)
    # The frames and the exception line have to be bounded separately and from
    # opposite ends. Several raises on this path interpolate whole ID lists into
    # the message, so bounding the two together would let one long message push
    # out every frame -- and then even the exception type. Bound the message
    # from the front (keeping "ValueError: ...") and the frames from the back
    # (keeping the innermost frame, which names the failing statement).
    exception_line = bounded_diagnostic_text(formatted[-1].strip())
    frames = "".join(formatted[:-1]).strip()
    budget = max(0, _STAGE_TRACEBACK_LIMIT - len(exception_line))
    if len(frames) > budget:
        frames = f"...<truncated>{frames[len(frames) - budget:]}"
    return f"{frames}\n{exception_line}".strip()


def _schema3_attribution_complete(explanation):
    """Return True when a payload's ranked attribution covers its whole input.

    Absent or malformed blocks count as incomplete: an explanation that cannot
    demonstrate coverage must not be certified as exact.
    """
    if not isinstance(explanation, Mapping):
        return False
    completeness = explanation.get("attribution_completeness")
    if not isinstance(completeness, Mapping):
        return False
    return completeness.get("complete") is True


def _schema3_structural_detail(explanation_engine, technical_case, community):
    try:
        structural = build_structural_community_control(community)
    except (KeyError, TypeError, ValueError):
        if getattr(explanation_engine, "schema3_test_adapter", False) is not True:
            # Production engines must yield extractable structural evidence. A
            # silent shim here would publish degraded community-only evidence
            # while hiding a real extraction defect, so surface the error and
            # let the caller record the case as failed.
            raise
        # Test-only compatibility shim for fake engines that expose the already
        # validated community shape but not the streaming structural adapter.
        # It still removes shared target markers and retains as-of rows.
        structural = _detached_json_object(
            community, field_name="baseline community"
        )
        structural["detail_kind"] = "community_only"
        structural["kind"] = "community_only"
        structural["evidence_kind"] = "structural_provenance"
        structural["complete"] = True
        structural["flow_stages"] = build_flow_stages(community)
    structural["target_person_id"] = technical_case.person_id
    structural["score_evidence"] = "baseline_vs_hybrid_risk_values_and_ranks"
    return structural


def _schema3_materialize_community(community):
    if not isinstance(community, CommunityScope):
        return community
    edges = []
    provenance = list(community.iter_provenance())
    observations_by_edge = {}
    for observation in provenance:
        observations_by_edge.setdefault(observation["edge_id"], []).append(
            {
                "source_row_id": observation["source_row_id"],
                "available_time": observation["available_time"],
            }
        )
    for edge in community.iter_edges():
        record = dict(edge)
        record["observations"] = observations_by_edge.get(record["edge_id"], [])
        edges.append(record)
    return {
        "complete": True,
        "scoring_day": community.scoring_day.isoformat(),
        "component_id": community.component_id,
        "community_key": community.community_key,
        "nodes": list(community.iter_nodes()),
        "edges": edges,
        "provenance_expansions": [],
    }


def _schema3_summary_record(
    case,
    *,
    cohort,
    reference,
    provenance,
    detail_status="not_selected",
    detail_kind=None,
    selection_reason="not_selected",
    failure_reason=None,
):
    return {
        "cohort": cohort,
        "case_id": case.case_id,
        "person_id": case.subject_id,
        "event_id": case.anchor_event.event_id,
        "scoring_day": case.anchor_event.scoring_day.isoformat(),
        "baseline_raw": case.baseline_raw,
        "baseline_percentile": case.baseline_percentile,
        "baseline_rank": case.baseline_rank,
        "seed0_gnn_probability": case.seed0_gnn_probability,
        "seed0_gnn_percentile": case.seed0_gnn_percentile,
        "seed0_gnn_rank": case.seed0_gnn_rank,
        "seed0_hybrid_score": case.seed0_hybrid_score,
        "seed0_hybrid_rank": case.seed0_hybrid_rank,
        "hybrid_score_semantics": "percentile_fusion_not_probability",
        "hybrid_rank_uplift": case.hybrid_rank_uplift,
        "gnn_percentile_uplift": case.gnn_percentile_uplift,
        "relationship_categories": list(case.relationship_categories),
        "detail_status": detail_status,
        "detail_kind": detail_kind,
        "selection_reason": selection_reason,
        "failure_reason": failure_reason,
        "community_key": None,
        "target_person_id": None,
        "provenance": provenance,
        "run_identity": provenance["run_identity"],
        "recovery_anchor_arm": case.recovery_anchor_arm,
        "recovery_anchor_event_id": case.anchor_event.event_id,
        "recovery_anchor_inspected_rank": case.anchor_event.inspected_rank,
        "percentile_reference_id": reference.percentile_reference_id,
    }


def _process_peak_rss_bytes():
    try:
        import resource

        value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return value * (1024 if os.uname().sysname == "Darwin" else 1)
    except (AttributeError, OSError, ImportError, ValueError):
        return None


def _schema3_stage_recorder(instrumentation):
    started = time.perf_counter()
    stages = []

    def record(stage, **fields):
        item = {
            "stage": stage,
            "elapsed_seconds": max(0.0, time.perf_counter() - started),
            "process_peak_rss_bytes": _process_peak_rss_bytes(),
            **fields,
        }
        stages.append(item)
        callback = instrumentation
        if isinstance(instrumentation, Mapping):
            callback = instrumentation.get("on_stage")
        if callable(callback):
            callback(stage, dict(item))

    return started, stages, record


def _build_schema3_artifact(
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
    explanation_limit,
    hybrid_detail_limit,
    baseline_control_limit,
    inspections_per_day,
    narrative_builder,
    corpus_identity,
    recovery_run_identity,
    instrumentation,
    narrative_preflight,
    bundle_writer=None,
):
    seeds = _validated_scope(gnn_arm, surrounding_seeds)
    hybrid_limit, baseline_limit = _resolve_schema3_limits(
        explanation_limit, hybrid_detail_limit, baseline_control_limit
    )
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
    started, stages, stage = _schema3_stage_recorder(instrumentation)
    snapshot_peak_days = 0

    def release_day(scoring_day):
        """Drop day-bound tensors as soon as the producer is finished with them.

        Every snapshot the engine materializes stays cached until it is
        released, and a full V9 run touches one scoring day per recovery
        candidate.  Without this the cache holds every day's node features,
        edge index, and pooled activations at once, which is the exact
        unbounded growth that per-day release was introduced to fix.
        """
        nonlocal snapshot_peak_days
        cached = getattr(explanation_engine, "cached_snapshot_days", ())
        try:
            snapshot_peak_days = max(snapshot_peak_days, len(cached))
        except TypeError:
            pass
        explanation_engine.release_snapshot(scoring_day)
    stage("preparation_start")
    rows, scoring_days = _prepared_pool(pool)
    reference = build_rank_reference(
        rows, baseline_raw, seed0_gnn_raw, blend_weight
    )
    explanation_engine.bind_rank_reference(
        reference, _rank_row_bindings(rows, scoring_days)
    )
    run_identity_payload = _schema3_identity(
        recovery_run_identity, corpus_identity=corpus_identity
    )
    run_identity_token = _schema3_identity_token(
        run_identity_payload, label="recovery-run"
    )
    as_of_identity = _schema3_identity_token(
        {
            "corpus_identity": str(corpus_identity),
            "percentile_reference_id": reference.percentile_reference_id,
            "inspections_per_day": daily_budget,
        },
        label="as-of",
    )
    baseline_run = simulate_recovery_run(
        rows,
        reference.baseline_selection_score,
        arm="baseline",
        daily_budget=daily_budget,
        official_caught_times=caught_times,
        run_identity=run_identity_token,
        as_of_identity=as_of_identity,
    )
    hybrid_run = simulate_recovery_run(
        rows,
        reference.seed0_hybrid_selection_score,
        arm="hybrid_seed0",
        daily_budget=daily_budget,
        official_caught_times=caught_times,
        run_identity=run_identity_token,
        as_of_identity=as_of_identity,
    )
    overlap = recovery_overlap(baseline_run, hybrid_run, strict=True)
    _validate_seed0_recovery_overlap(seed_recovery, overlap)
    stage(
        "recovery_overlap_complete",
        baseline_recovered=len(overlap.baseline_ids),
        hybrid_recovered=len(overlap.hybrid_ids),
        recovered_by_both=len(overlap.both_ids),
    )

    hybrid_technical = {
        case.person_id: case
        for case in build_hybrid_only_cases(
            rows, overlap, baseline_run, hybrid_run, reference, explanation_engine
        )
    }
    baseline_technical = {
        case.person_id: case
        for case in build_baseline_only_cases(
            rows, overlap, baseline_run, hybrid_run, reference, explanation_engine
        )
    }
    both_baseline_technical = {}
    both_hybrid_technical = {}
    for person_id in sorted(overlap.both_ids):
        # Recovered-by-both records are aggregate summaries.  Build each
        # source trace against its own arm's daily candidate reference before
        # materializing the earlier anchor.  The other arm may have recovered
        # the person on an earlier day, in which case its row is correctly
        # absent from the candidate pool on this anchor day.
        both_baseline_technical[person_id] = _build_exclusive_case(
            rows,
            scoring_days,
            rows["primary_person_id"].to_numpy(dtype=str),
            person_id,
            baseline_run,
            baseline_run,
            baseline_run,
            reference,
            explanation_engine,
        )
        both_hybrid_technical[person_id] = _build_exclusive_case(
            rows,
            scoring_days,
            rows["primary_person_id"].to_numpy(dtype=str),
            person_id,
            hybrid_run,
            hybrid_run,
            hybrid_run,
            reference,
            explanation_engine,
        )

    hybrid_cases = {
        f"case:{person_id}": _schema3_recovery_case(
            technical,
            cohort="hybrid_only",
            recovery_anchor_arm="hybrid_seed0",
            reference=reference,
        )
        for person_id, technical in hybrid_technical.items()
    }
    baseline_cases = {
        f"case:{person_id}": _schema3_recovery_case(
            technical,
            cohort="baseline_only",
            recovery_anchor_arm="baseline",
            reference=reference,
        )
        for person_id, technical in baseline_technical.items()
    }
    both_cases = {}
    for person_id in sorted(overlap.both_ids):
        both_cases[f"case:{person_id}"] = materialize_recovered_by_both_case(
            _schema3_recovery_case(
                both_baseline_technical[person_id],
                cohort="baseline_only",
                recovery_anchor_arm="baseline",
                reference=reference,
            ),
            _schema3_recovery_case(
                both_hybrid_technical[person_id],
                cohort="hybrid_only",
                recovery_anchor_arm="hybrid_seed0",
                reference=reference,
            ),
        )

    stage("preflight_start", hybrid_candidates=len(hybrid_cases))
    # Preflight measures the exact two-hop input for every Hybrid candidate, so
    # it materializes one day snapshot per candidate scoring day.  Walk the
    # candidates in day order and release each day as soon as its group is
    # measured; the results are re-keyed in case-ID order below so the frozen
    # selection and its fingerprint stay independent of this traversal.
    measured_preflight = {}
    day_ordered_candidates = sorted(
        hybrid_cases.items(),
        key=lambda item: (item[1].anchor_event.scoring_day, item[0]),
    )
    for scoring_day, day_candidates in groupby(
        day_ordered_candidates, key=lambda item: item[1].anchor_event.scoring_day
    ):
        try:
            for case_id, case in day_candidates:
                measured_preflight[case_id] = _schema3_preflight(
                    explanation_engine, hybrid_technical[case.person_id]
                )
        finally:
            release_day(scoring_day)
    preflight = {
        case_id: measured_preflight[case_id] for case_id in sorted(hybrid_cases)
    }
    eligible_ids = [
        case_id for case_id, result in preflight.items() if result["eligible"]
    ]
    stage(
        "preflight_complete",
        hybrid_candidates=len(hybrid_cases),
        eligible_hybrid=len(eligible_ids),
        ineligible_hybrid=len(hybrid_cases) - len(eligible_ids),
        max_nodes=MAX_EXPLAINER_INPUT_NODES,
        max_edges=MAX_EXPLAINER_INPUT_EDGES,
        size_summary=_preflight_size_summary(preflight),
    )
    selection = select_balanced_detail_cases(
        list(hybrid_cases.values()),
        list(baseline_cases.values()),
        hybrid_limit=hybrid_limit,
        baseline_limit=baseline_limit,
        eligible_hybrid_ids=eligible_ids,
    )
    selected_ids = selection.selected_ids
    # Oversized Hybrid candidates cannot receive GNNExplainer evidence, so the
    # unused remainder of the frozen Hybrid budget is filled deterministically
    # with community-only structural fallbacks. This happens before any
    # explanation work, so it never replaces a case after a failure.
    fallback_slots = max(0, hybrid_limit - len(selected_ids["hybrid_only"]))
    eligible_id_set = set(eligible_ids)
    ineligible_cases = [
        case
        for case_id, case in sorted(hybrid_cases.items())
        if case_id not in eligible_id_set
    ]
    structural_fallback_ids = tuple(
        case.case_id
        for case in _round_robin_balanced_cases(ineligible_cases, hybrid=True)[
            :fallback_slots
        ]
    )
    stage(
        "selection_frozen",
        hybrid_selected=len(selected_ids["hybrid_only"]),
        baseline_selected=len(selected_ids["baseline_only"]),
        hybrid_structural_fallback=len(structural_fallback_ids),
    )
    narrative_stats = {
        "narrative_attempted": 0,
        "narrative_generated": 0,
        "narrative_fallback": 0,
        "narrative_failed": 0,
        "narrative_preflight_failed": 0,
        "narrative_last_error": None,
    }
    if callable(narrative_preflight):
        try:
            narrative_preflight()
        except Exception as error:
            narrative_stats["narrative_preflight_failed"] += 1
            narrative_stats["narrative_preflight_error"] = (
                f"{type(error).__name__}: {bounded_diagnostic_text(error)}"
            )
    elif narrative_builder is generate_narrative:
        try:
            preflight_local_model()
        except Exception as error:
            narrative_stats["narrative_preflight_failed"] += 1
            narrative_stats["narrative_preflight_error"] = (
                f"{type(error).__name__}: {bounded_diagnostic_text(error)}"
            )

    provenance_by_cohort = {
        "hybrid_only": _schema3_provenance(
            corpus_identity=corpus_identity,
            run_identity=run_identity_payload,
            as_of_identity=as_of_identity,
            reference=reference,
            recovery_arm="hybrid_seed0",
        ),
        "baseline_only": _schema3_provenance(
            corpus_identity=corpus_identity,
            run_identity=run_identity_payload,
            as_of_identity=as_of_identity,
            reference=reference,
            recovery_arm="baseline",
        ),
        "recovered_by_both": _schema3_provenance(
            corpus_identity=corpus_identity,
            run_identity=run_identity_payload,
            as_of_identity=as_of_identity,
            reference=reference,
            recovery_arm="both_summary_only",
        ),
    }
    records = {
        cohort: {}
        for cohort in ("hybrid_only", "baseline_only", "recovered_by_both")
    }
    for cohort, cases in (
        ("hybrid_only", hybrid_cases),
        ("baseline_only", baseline_cases),
        ("recovered_by_both", both_cases),
    ):
        for case_id, case in cases.items():
            records[cohort][case_id] = _schema3_summary_record(
                case,
                cohort=cohort,
                reference=reference,
                provenance=provenance_by_cohort[cohort],
            )
    for case_id, result in preflight.items():
        if not result["eligible"]:
            # Ineligible candidates stay unselected unless they win a frozen
            # structural-fallback slot below, which is what actually publishes
            # their community evidence.
            records["hybrid_only"][case_id].update(
                {
                    "detail_status": "not_selected",
                    "detail_kind": None,
                    "selection_reason": "ineligible_preflight",
                    "failure_reason": result["reason_code"],
                    "preflight_status": result["status"],
                    "preflight_node_count": result["node_count"],
                    "preflight_edge_count": result["edge_count"],
                }
            )

    communities = {}
    source_communities = {}
    detail_index = {}
    community_index = {}
    failures = []
    attempted_ids = []
    succeeded_ids = []
    failed_ids = []
    published_ids = {"hybrid_only": [], "baseline_only": [], "recovered_by_both": []}

    structural_fallback_published = []
    structural_fallback_failures = []

    def staged_payload(case_id, cohort):
        """Return evidence a previous run already published for this case."""
        if bundle_writer is None or not bundle_writer.has_completed_case(
            case_id, cohort
        ):
            return None
        return bundle_writer.read_case_payload(case_id)

    def open_attempt(case_id):
        """Claim the next persisted attempt slot, or None when both are spent.

        The attempt is checkpointed before the work starts, so a run killed
        mid-case resumes into the deferred-retry slot instead of silently
        repeating an attempt or replacing the frozen selection.
        """
        if bundle_writer is None:
            return "first_pass"
        state = bundle_writer.case_attempt_state(case_id)
        for phase in ("first_pass", "deferred_retry"):
            if state[phase] == "pending":
                bundle_writer.begin_case_attempt(case_id, phase)
                return phase
        return None

    def store_case_community(community, scoring_day):
        """Key one community, streaming it into the bundle when one is staged.

        The in-memory store materializes every record and refuses communities
        over its legacy 10,000-record bound, which real V9 communities exceed;
        the staged path streams the same evidence in bounded chunks instead.
        """
        if bundle_writer is None:
            return _store_community(
                communities,
                source_communities,
                _schema3_materialize_community(community),
                scoring_day,
            )
        community_key = (
            community.community_key
            if isinstance(community, CommunityScope)
            else community["community_key"]
        )
        if community_key not in bundle_writer.community_index:
            bundle_writer.write_community(_community_stream_source(community))
        return community_key

    def publish_community_control(
        case_id,
        *,
        cohort,
        case,
        technical,
        selection_reason,
        published_bucket,
        failure_bucket,
        unavailable_reason=None,
    ):
        """Publish community-only structural evidence for one selected case."""
        attempted_ids.append(case_id)
        record = records[cohort][case_id]
        failure_traceback = None
        try:
            staged = staged_payload(case_id, cohort)
            if staged is not None:
                community_key = staged["community_key"]
                structural = staged["detail"]
                _validate_schema3_evidence_boundary(
                    structural,
                    technical.anchor.scoring_day,
                    field_name="staged structural detail",
                )
            else:
                if open_attempt(case_id) is None:
                    raise RuntimeError(
                        "selected case exhausted its persisted publication attempts"
                    )
                community = explanation_engine.community(
                    technical.person_id, technical.anchor.scoring_day
                )
                community_key = store_case_community(
                    community, technical.anchor.scoring_day
                )
                structural = _schema3_structural_detail(
                    explanation_engine, technical, community
                )
                if bundle_writer is not None:
                    bundle_writer.write_case(
                        cohort,
                        _bundle_case_record(technical, cohort, community_key),
                        structural_detail=structural,
                    )
            record.update(
                {
                    "detail_status": "community_only",
                    "detail_kind": "community_control",
                    "selection_reason": selection_reason,
                    "community_key": community_key,
                    "target_person_id": case.person_id,
                    # This case has evidence, so failure_reason stays empty and
                    # the missing GNN explanation is explained separately.
                    "failure_reason": None,
                    "explanation_unavailable_reason": unavailable_reason,
                    # Community-only evidence carries the score ledger for both
                    # Baseline controls and oversized-Hybrid fallbacks.
                    "score_ledger": {
                        "baseline_rank": case.baseline_rank,
                        "hybrid_rank": case.seed0_hybrid_rank,
                        "baseline_percentile": case.baseline_percentile,
                        "hybrid_score": case.seed0_hybrid_score,
                        "hybrid_score_semantics": "percentile_fusion_not_probability",
                    },
                }
            )
            community_index[case_id] = {
                "community_key": community_key,
                "target_person_id": case.person_id,
                # Staged runs publish the structural payload as a verified
                # sidecar, so it is referenced rather than carried inline.
                **(
                    {}
                    if bundle_writer is not None
                    else {"structural_evidence": structural}
                ),
            }
            published_bucket.append(case_id)
            succeeded_ids.append(case_id)
        except Exception as error:
            failed_ids.append(case_id)
            failure_traceback = _bounded_stage_traceback(error)
            record.update(
                {
                    "detail_status": "failed",
                    "detail_kind": "community_control",
                    "selection_reason": selection_reason,
                    "community_key": None,
                    "failure_reason": f"{type(error).__name__}: {error}",
                }
            )
            failure = {
                "case_id": case_id,
                "cohort": cohort,
                "reason_code": type(error).__name__,
                "message": str(error),
            }
            failure_bucket.append(failure)
            if bundle_writer is not None:
                bundle_writer.record_failure(failure)
        finally:
            # The community payload is fully detached by now, so the day's
            # tensors can go even though later selected cases may share it.
            release_day(technical.anchor.scoring_day)
            # Publication stages run for minutes per case on real V9
            # communities, so without a per-case event an operator watching the
            # stage log cannot tell a working run from a stalled one.
            stage(
                "case_published",
                cohort=cohort,
                case_id=case_id,
                detail_kind="community_control",
                status=record["detail_status"],
                # Without this the stage log reports *that* a case failed but
                # never why, and the reason is only readable from the artifact
                # -- which is written after the whole multi-hour run. An
                # operator watching the log has to be able to diagnose a
                # failing run while it is still running.
                failure_reason=_bounded_stage_failure_reason(
                    record.get("failure_reason")
                ),
                failure_traceback=failure_traceback,
            )

    for case_id in selected_ids["baseline_only"]:
        publish_community_control(
            case_id,
            cohort="baseline_only",
            case=baseline_cases[case_id],
            technical=baseline_technical[baseline_cases[case_id].person_id],
            selection_reason="balanced_frozen_prefix",
            published_bucket=published_ids["baseline_only"],
            failure_bucket=failures,
        )

    stage("baseline_controls_complete", attempted=len(selected_ids["baseline_only"]))
    stage(
        "hybrid_structural_fallback_start", attempted=len(structural_fallback_ids)
    )
    for case_id in structural_fallback_ids:
        publish_community_control(
            case_id,
            cohort="hybrid_only",
            case=hybrid_cases[case_id],
            technical=hybrid_technical[hybrid_cases[case_id].person_id],
            selection_reason="ineligible_preflight_structural_fallback",
            published_bucket=structural_fallback_published,
            failure_bucket=structural_fallback_failures,
            unavailable_reason=preflight[case_id]["reason_code"],
        )
    stage(
        "hybrid_structural_fallback_complete",
        attempted=len(structural_fallback_ids),
        succeeded=len(structural_fallback_published),
    )
    attribution_complete_count = 0
    stage("hybrid_explanations_start", attempted=len(selected_ids["hybrid_only"]))
    for case_id in selected_ids["hybrid_only"]:
        case = hybrid_cases[case_id]
        technical = hybrid_technical[case.person_id]
        attempted_ids.append(case_id)
        failure_traceback = None
        try:
            staged = staged_payload(case_id, "hybrid_only")
            if staged is not None:
                # A resumed run must never re-run GNNExplainer or the narrative
                # for a case whose evidence is already published.
                explanation = staged["explanation"]
                community_key = staged["community_key"]
                # Replay the staged narrative outcome so a resumed run reports
                # true coverage instead of "no narratives generated".
                _validate_schema3_evidence_boundary(
                    explanation,
                    technical.anchor.scoring_day,
                    field_name="staged explanation",
                )
                narrative_stats["narrative_attempted"] += 1
                if explanation.get("llm_narrative", {}).get("source") == (
                    "deterministic_template"
                ):
                    narrative_stats["narrative_fallback"] += 1
                else:
                    narrative_stats["narrative_generated"] += 1
            else:
                if open_attempt(case_id) is None:
                    raise RuntimeError(
                        "selected case exhausted its persisted explanation attempts"
                    )
                explanation = _explain_case_with_narrative(
                    technical,
                    explanation_engine,
                    narrative_builder,
                    narrative_stats=narrative_stats,
                    narrative_preflight_failed=bool(
                        narrative_stats["narrative_preflight_failed"]
                    ),
                )
                local_community = explanation.pop("community")
                community = explanation.pop("_community_scope", local_community)
                expansions = explanation.pop("provenance_expansions", [])
                _validate_complete_community(
                    community, technical.anchor.scoring_day
                )
                if bundle_writer is None:
                    community_key = _store_community(
                        communities,
                        source_communities,
                        local_community,
                        technical.anchor.scoring_day,
                    )
                else:
                    community_key = store_case_community(
                        community, technical.anchor.scoring_day
                    )
                explanation["community_key"] = community_key
                explanation["provenance_expansion_ids"] = [
                    expansion["expansion_id"] for expansion in expansions
                ]
                if bundle_writer is not None:
                    bundle_writer.write_case(
                        "hybrid_only",
                        _bundle_case_record(
                            technical, "hybrid_only", community_key, explanation
                        ),
                        explanation=explanation,
                        validation_metadata=explanation["llm_narrative"],
                        overlay_evidence=_overlay_stream_source(
                            explanation, local_community, expansions
                        ),
                    )
            record = records["hybrid_only"][case_id]
            record.update(
                {
                    "detail_status": "available",
                    "detail_kind": "gnn_explanation",
                    "selection_reason": "balanced_frozen_prefix",
                    "community_key": community_key,
                    "target_person_id": case.person_id,
                }
            )
            detail_index[case_id] = {
                **record,
                "target_person_id": case.person_id,
                "explanation": explanation,
            }
            published_ids["hybrid_only"].append(case_id)
            succeeded_ids.append(case_id)
            # Counted rather than raised: a case whose ranked attribution is
            # partial is still valid evidence, but it must not be reported as an
            # exact explanation, so the coverage gate rejects the run instead of
            # this loop failing the case and burning its retry slot.
            if _schema3_attribution_complete(explanation):
                attribution_complete_count += 1
        except Exception as error:
            failed_ids.append(case_id)
            failure_traceback = _bounded_stage_traceback(error)
            records["hybrid_only"][case_id].update(
                {
                    "detail_status": "failed",
                    "detail_kind": "gnn_explanation",
                    "selection_reason": "balanced_frozen_prefix",
                    "failure_reason": f"{type(error).__name__}: {error}",
                }
            )
            failure = {
                "case_id": case_id,
                "cohort": "hybrid_only",
                "reason_code": type(error).__name__,
                "message": str(error),
            }
            failures.append(failure)
            if bundle_writer is not None:
                bundle_writer.record_failure(failure)
        finally:
            release_day(technical.anchor.scoring_day)
            stage(
                "case_published",
                cohort="hybrid_only",
                case_id=case_id,
                detail_kind="gnn_explanation",
                status=records["hybrid_only"][case_id]["detail_status"],
                # Surfaced per case so a run proves its published attribution
                # covered the whole exact input, instead of that being assumed
                # from the ceilings being configured equal.
                attribution_complete=(
                    detail_index.get(case_id, {})
                    .get("explanation", {})
                    .get("attribution_completeness", {})
                    .get("complete")
                ),
                # A failed explanation costs 20-40 minutes of GNNExplainer and
                # counterfactual work before it raises, so the reason has to
                # reach the live stage log. Recording it only in the artifact
                # means a run that fails every case reports nothing diagnosable
                # until it finishes hours later.
                failure_reason=_bounded_stage_failure_reason(
                    records["hybrid_only"][case_id].get("failure_reason")
                ),
                failure_traceback=failure_traceback,
            )
    stage(
        "hybrid_explanations_complete",
        attempted=len(selected_ids["hybrid_only"]),
        succeeded=len(published_ids["hybrid_only"]),
        failed=len([item for item in failures if item["cohort"] == "hybrid_only"]),
    )

    # Structural-fallback cases are not part of the frozen publication
    # selection, so their failures are reported in the artifact but not fed
    # back into the selection finalizer.
    all_failures = list(failures) + list(structural_fallback_failures)
    # Selection finalization receives the complete frozen failure set so published
    # cohort records and diagnostics cannot drift after selection.
    selection_final = finalize_recovery_publication(
        selection,
        published_ids=published_ids,
        failures=failures,
    )
    selection_policy = selection_final.policy_jsonable()
    selection_policy.update(
        {
            "eligible_hybrid_ids": list(eligible_ids),
            "eligible_ordered_prefix": list(
                selection_policy["eligible_ordered_prefix"]
            ),
            "preflight": preflight,
            "selected_ids": {
                cohort: list(ids) for cohort, ids in selected_ids.items()
            },
            "hybrid_structural_fallback_ids": list(structural_fallback_ids),
            "no_post_failure_replacement": True,
            "explainer_input_policy": {
                "max_nodes": MAX_EXPLAINER_INPUT_NODES,
                "max_directed_edges": MAX_EXPLAINER_INPUT_EDGES,
                "pruning": "none",
            },
        }
    )
    fingerprint_material = {
        "schema_version": SCHEMA3,
        "corpus_identity": str(corpus_identity),
        "run_identity": run_identity_payload,
        "as_of_identity": as_of_identity,
        "percentile_reference_id": reference.percentile_reference_id,
        "selection": selection_policy,
        "restart_seeds": list(EXPLAINER_RESTART_SEEDS),
        "epochs": EXPLAINER_EPOCHS,
    }
    engine_fingerprint = getattr(
        explanation_engine, "observability_fingerprint_material", None
    )
    if not callable(engine_fingerprint):
        raise ValueError(
            "explanation_engine must support observability_fingerprint_material"
        )
    engine_material = _detached_json_object(
        engine_fingerprint(), field_name="engine fingerprint material"
    )
    for field in ("graph_sha256", "model_state_sha256", "rank_reference_fingerprint"):
        value = engine_material.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"engine fingerprint material requires {field}")
    fingerprint_material.update(
        {
            "checkpoint_id": run_identity_payload.get("checkpoint_id"),
            "graph_fingerprint": engine_material.get("graph_sha256"),
            "model_state_fingerprint": engine_material.get("model_state_sha256"),
            "rank_reference_identity": reference.percentile_reference_id,
            "eligible_ordered_prefix": list(
                selection_policy["eligible_ordered_prefix"]
            ),
            "selected_ids": {
                cohort: list(ids) for cohort, ids in selected_ids.items()
            },
            "policy": selection_policy,
            "engine_fingerprint": engine_material,
            "limits": {
                "hybrid_detail": hybrid_limit,
                "baseline_control": baseline_limit,
            },
        }
    )
    fingerprint = _schema3_identity_token(fingerprint_material, label="schema3")
    summary = dict(overlap.summary)
    summary["seed_level_unique_person_recovery"] = seed_recovery
    coverage = {
        "hybrid_requested": hybrid_limit,
        "baseline_requested": baseline_limit,
        "hybrid_available": len(hybrid_cases),
        "baseline_available": len(baseline_cases),
        "hybrid_candidates": len(hybrid_cases),
        "baseline_candidates": len(baseline_cases),
        "hybrid_eligible": len(eligible_ids),
        "hybrid_selected": len(selected_ids["hybrid_only"]),
        "baseline_selected": len(selected_ids["baseline_only"]),
        "hybrid_explained": len(published_ids["hybrid_only"]),
        # Explained cases whose ranked attribution covered the whole exact
        # input. Published separately from hybrid_explained so a run cannot
        # certify partial attributions as exact explanations.
        "hybrid_attribution_complete": attribution_complete_count,
        "baseline_community": len(published_ids["baseline_only"]),
        "hybrid_structural_fallback_selected": len(structural_fallback_ids),
        "hybrid_structural_fallback": len(structural_fallback_published),
        "attempted": len(attempted_ids),
        "succeeded": len(succeeded_ids),
        "failed": len(failed_ids),
        "failed_count": len(all_failures),
        # Shortfall is measured against the requested limits, so a small
        # candidate pool is reported as a real shortfall rather than being
        # silently absorbed by clamping the request to what was available.
        "shortfall": (
            max(0, hybrid_limit - len(published_ids["hybrid_only"]))
            + max(0, baseline_limit - len(published_ids["baseline_only"]))
        ),
        "hybrid_shortfall": max(
            0, hybrid_limit - len(published_ids["hybrid_only"])
        ),
        "baseline_shortfall": max(
            0, baseline_limit - len(published_ids["baseline_only"])
        ),
        "shortfall_reasons": [
            failure["reason_code"] for failure in all_failures
        ]
        + (["ineligible_hybrid_candidates"] if len(eligible_ids) < len(hybrid_cases) else []),
        "narrative_attempted": narrative_stats["narrative_attempted"],
        "narrative_generated": narrative_stats["narrative_generated"],
        "narrative_fallback": narrative_stats["narrative_fallback"],
        "narrative_failed": narrative_stats["narrative_failed"],
        "narrative_preflight_failed": narrative_stats["narrative_preflight_failed"],
        "oversized_hybrid": sum(
            result["reason_code"] in {
                "node_limit_exceeded",
                "edge_limit_exceeded",
                "node_and_edge_limits_exceeded",
            }
            for result in preflight.values()
        ),
    }
    if len(hybrid_cases) < hybrid_limit:
        coverage["shortfall_reasons"].append("insufficient_hybrid_candidates")
    if len(baseline_cases) < baseline_limit:
        coverage["shortfall_reasons"].append("insufficient_baseline_candidates")
    if coverage["shortfall"] and not coverage["shortfall_reasons"]:
        raise ValueError("schema-3 shortfall must record an explicit reason")
    artifact = {
        "schema_version": SCHEMA3,
        "policy": {
            "observability_seed": 0,
            "gnn_arm": "sage",
            "surrounding_results_seeds": list(seeds),
            "inspections_per_day": daily_budget,
            "hybrid_blend_weight": float(reference.blend_weight),
            "percentile_reference_id": reference.percentile_reference_id,
            "hybrid_score_semantics": "percentile_fusion_not_probability",
            "gnnexplainer_restart_seeds": list(EXPLAINER_RESTART_SEEDS),
            "gnnexplainer_epochs": EXPLAINER_EPOCHS,
            "selection_policy_version": selection_policy["policy_version"],
            "recovery_overlap_provenance": "strict_shared_run_and_as_of_identity",
        },
        "summary": summary,
        "coverage": coverage,
        "cohorts": {
            cohort: list(records[cohort].values())
            for cohort in ("hybrid_only", "baseline_only", "recovered_by_both")
        },
        "selection": selection_policy,
        "detail_index": detail_index,
        "community_index": community_index,
        "catalog_index": {
            case_id: {"cohort": record["cohort"], "detail_status": record["detail_status"]}
            for cohort in records.values()
            for case_id, record in cohort.items()
        },
        "communities": communities,
        "run_identity": run_identity_payload,
        "run_fingerprint": {
            "fingerprint": fingerprint,
            "material": fingerprint_material,
        },
        "generation_diagnostics": {
            "failed_attempts": all_failures,
            "preflight": preflight,
            "stage_transitions": stages,
            "elapsed_seconds": max(0.0, time.perf_counter() - started),
            "process_peak_rss_bytes": _process_peak_rss_bytes(),
            # Highest number of day snapshots the engine held at once. Per-day
            # release keeps this bounded; unbounded growth here is the OOM
            # signature that killed earlier full-corpus generation.
            "snapshot_cache_peak_days": snapshot_peak_days,
            "snapshot_cache_residual_days": len(
                getattr(explanation_engine, "cached_snapshot_days", ())
            ),
            "counts": {
                "selected": len(selected_ids["hybrid_only"])
                + len(selected_ids["baseline_only"]),
                "attempted": len(attempted_ids),
                "succeeded": len(succeeded_ids),
                "failed": len(failed_ids),
            },
            "attempted_ids": list(attempted_ids),
            "succeeded_ids": list(succeeded_ids),
            "failed_ids": list(failed_ids),
            "restart_seeds": list(EXPLAINER_RESTART_SEEDS),
            "epochs": EXPLAINER_EPOCHS,
            "narrative": dict(narrative_stats),
        },
    }
    stage("artifact_validated")
    return validate_schema3_artifact(_detached_json_object(artifact, field_name="artifact"))


def validate_schema3_artifact(artifact):
    """Validate in-memory schema-3 coverage, index, and fingerprint invariants.

    ``artifact`` is the complete in-memory diagnostic object; validation checks
    schema-3 evidence before any durable ``RecoveryBundleWriter`` publication.
    This function is pure and returns the validated detached artifact.
    """

    # Schema-3 validation is an in-memory contract; durable publication belongs
    # to RecoveryBundleWriter after the verified evidence tree is complete.
    if not isinstance(artifact, Mapping) or artifact.get("schema_version") != SCHEMA3:
        raise ValueError("invalid schema-3 observability artifact version")
    policy = artifact.get("policy")
    if not isinstance(policy, Mapping) or policy.get("observability_seed") != 0:
        raise ValueError("invalid schema-3 observability scope")
    if policy.get("gnn_arm") != "sage" or policy.get("surrounding_results_seeds") != [0, 1, 2]:
        raise ValueError("invalid schema-3 ensemble provenance")
    if policy.get("hybrid_score_semantics") != "percentile_fusion_not_probability":
        raise ValueError("Hybrid score semantics must identify percentile fusion")
    if policy.get("gnnexplainer_restart_seeds") != [0, 1, 2] or policy.get("gnnexplainer_epochs") != 150:
        raise ValueError("invalid GNNExplainer policy")

    summary = artifact.get("summary")
    if not isinstance(summary, Mapping):
        raise ValueError("schema-3 summary is required")
    algebra = (
        ("baseline_recovered", "recovered_by_both", "baseline_only_recovered"),
        ("hybrid_total", "recovered_by_both", "hybrid_only_recovered"),
    )
    if any(
        not isinstance(summary.get(total), int)
        or summary[total] != summary[both] + summary[exclusive]
        for total, both, exclusive in algebra
    ):
        raise ValueError("invalid schema-3 overlap algebra")
    if summary.get("net_gain") != summary["hybrid_total"] - summary["baseline_recovered"]:
        raise ValueError("invalid schema-3 net gain algebra")

    cohorts = artifact.get("cohorts")
    cohort_names = {"hybrid_only", "baseline_only", "recovered_by_both"}
    if not isinstance(cohorts, Mapping) or set(cohorts) != cohort_names:
        raise ValueError("schema-3 artifact requires exactly three cohorts")
    expected_lengths = {
        "hybrid_only": summary["hybrid_only_recovered"],
        "baseline_only": summary["baseline_only_recovered"],
        "recovered_by_both": summary["recovered_by_both"],
    }
    if any(
        not isinstance(cohorts[cohort], list)
        or len(cohorts[cohort]) != expected_lengths[cohort]
        for cohort in cohort_names
    ):
        raise ValueError("schema-3 cohort counts do not match summary")

    run_identity = artifact.get("run_identity")
    if not isinstance(run_identity, Mapping):
        raise ValueError("schema-3 run identity is required")
    corpus_identity = run_identity.get("corpus_identity")
    if not isinstance(corpus_identity, str) or not corpus_identity:
        raise ValueError("schema-3 corpus identity is required")
    checkpoint_id = run_identity.get("checkpoint_id")
    run_id = run_identity.get("run_id")
    if (
        not isinstance(checkpoint_id, str)
        or not checkpoint_id.strip()
        or not isinstance(run_id, str)
        or not run_id.strip()
    ):
        raise ValueError("schema-3 checkpoint and run identity are required")
    reference_id = policy.get("percentile_reference_id")
    as_of_id = None
    required = {
        "baseline_raw", "baseline_percentile", "baseline_rank",
        "seed0_gnn_probability", "seed0_gnn_percentile", "seed0_gnn_rank",
        "seed0_hybrid_score", "seed0_hybrid_rank", "detail_status",
        "provenance", "run_identity",
    }
    records_by_id = {}
    for cohort, records in cohorts.items():
        for record in records:
            if not isinstance(record, Mapping) or not required.issubset(record):
                raise ValueError(f"{cohort} record is missing required score/provenance fields")
            case_id = record.get("case_id")
            if not isinstance(case_id, str) or case_id in records_by_id:
                raise ValueError("schema-3 case IDs must be globally unique")
            if record.get("cohort") != cohort or record.get("hybrid_score_semantics") != policy["hybrid_score_semantics"]:
                raise ValueError("schema-3 record cohort or score semantics is invalid")
            provenance = record.get("provenance")
            if not isinstance(provenance, Mapping) or record["run_identity"] != run_identity:
                raise ValueError("schema-3 record provenance identity is invalid")
            if (
                provenance.get("corpus_identity") != corpus_identity
                or provenance.get("run_identity") != run_identity
                or provenance.get("percentile_reference_id") != reference_id
                or provenance.get("as_of_identity") is None
            ):
                raise ValueError("schema-3 record provenance identity is invalid")
            if as_of_id is None:
                as_of_id = provenance["as_of_identity"]
            elif provenance["as_of_identity"] != as_of_id:
                raise ValueError("schema-3 as-of provenance identity is inconsistent")
            for field in (
                "baseline_raw", "baseline_percentile", "seed0_gnn_probability",
                "seed0_gnn_percentile", "seed0_hybrid_score",
            ):
                value = record[field]
                if (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not np.isfinite(float(value))
                    or not 0.0 <= float(value) <= 1.0
                ):
                    raise ValueError(f"schema-3 {field} must be in [0, 1]")
            for field in ("baseline_rank", "seed0_gnn_rank", "seed0_hybrid_rank"):
                if not isinstance(record[field], int) or isinstance(record[field], bool) or record[field] <= 0:
                    raise ValueError(f"schema-3 {field} must be a positive rank")
            expected_score = (1.0 - float(policy["hybrid_blend_weight"])) * float(record["baseline_percentile"]) + float(policy["hybrid_blend_weight"]) * float(record["seed0_gnn_percentile"])
            if not np.isclose(record["seed0_hybrid_score"], expected_score, rtol=1e-9, atol=1e-9):
                raise ValueError("schema-3 hybrid fusion arithmetic is invalid")
            if record.get("hybrid_rank_uplift") != record["baseline_rank"] - record["seed0_hybrid_rank"]:
                raise ValueError("schema-3 hybrid rank arithmetic is invalid")
            if not np.isclose(record.get("gnn_percentile_uplift"), record["seed0_gnn_percentile"] - record["baseline_percentile"], rtol=1e-9, atol=1e-9):
                raise ValueError("schema-3 percentile uplift arithmetic is invalid")
            records_by_id[case_id] = record

    selection = artifact.get("selection")
    if not isinstance(selection, Mapping) or selection.get("no_post_failure_replacement") is not True:
        raise ValueError("schema-3 frozen selection is required")
    selected = selection.get("selected_ids")
    if not isinstance(selected, Mapping) or set(selected) != cohort_names:
        raise ValueError("schema-3 selected IDs are required")
    selected_sets = {}
    for cohort in cohort_names:
        ids = selected[cohort]
        if not isinstance(ids, list) or len(ids) != len(set(ids)) or any(case_id not in records_by_id for case_id in ids):
            raise ValueError("schema-3 selection IDs do not match cohort summaries")
        if cohort == "recovered_by_both" and ids:
            raise ValueError("recovered_by_both is summary-only")
        selected_sets[cohort] = set(ids)
    preflight = selection.get("preflight")
    hybrid_ids = {record["case_id"] for record in cohorts["hybrid_only"]}
    if not isinstance(preflight, Mapping) or set(preflight) != hybrid_ids:
        raise ValueError("schema-3 preflight coverage is incomplete")
    eligible_ids = selection.get("eligible_hybrid_ids")
    if not isinstance(eligible_ids, list) or len(eligible_ids) != len(set(eligible_ids)) or not set(eligible_ids) <= hybrid_ids:
        raise ValueError("schema-3 eligible Hybrid prefix is invalid")
    eligible_ordered_prefix = selection.get("eligible_ordered_prefix")
    if (
        not isinstance(eligible_ordered_prefix, list)
        or len(eligible_ordered_prefix) != len(set(eligible_ordered_prefix))
        or set(eligible_ordered_prefix) != set(eligible_ids)
    ):
        raise ValueError("schema-3 eligible ordered prefix is invalid")
    for result in preflight.values():
        if not isinstance(result, Mapping) or set(result) != {"eligible", "status", "node_count", "edge_count", "max_nodes", "max_edges", "reason_code"}:
            raise ValueError("schema-3 preflight result shape is invalid")
        if (
            result["max_nodes"] != MAX_EXPLAINER_INPUT_NODES
            or result["max_edges"] != MAX_EXPLAINER_INPUT_EDGES
        ):
            raise ValueError("schema-3 preflight limits must be exact")
        if any(not isinstance(result[field], int) or isinstance(result[field], bool) or result[field] < 0 for field in ("node_count", "edge_count")):
            raise ValueError("schema-3 preflight counts are invalid")
        if result["eligible"] != (
            result["node_count"] <= MAX_EXPLAINER_INPUT_NODES
            and result["edge_count"] <= MAX_EXPLAINER_INPUT_EDGES
        ):
            raise ValueError("schema-3 preflight eligibility is invalid")
    if not set(selected["hybrid_only"]) <= set(eligible_ids):
        raise ValueError("schema-3 selected Hybrid cases must be preflight eligible")
    fallback_ids = selection.get("hybrid_structural_fallback_ids")
    if (
        not isinstance(fallback_ids, list)
        or len(fallback_ids) != len(set(fallback_ids))
        or not set(fallback_ids) <= hybrid_ids
        or set(fallback_ids) & selected_sets["hybrid_only"]
        or set(fallback_ids) & set(eligible_ids)
    ):
        raise ValueError("schema-3 Hybrid structural fallback selection is invalid")
    fallback_set = set(fallback_ids)
    coverage = artifact.get("coverage")
    if not isinstance(coverage, Mapping):
        raise ValueError("schema-3 coverage diagnostics are required")
    hybrid_requested = coverage.get("hybrid_requested")
    baseline_requested = coverage.get("baseline_requested")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in (hybrid_requested, baseline_requested)
    ):
        raise ValueError("schema-3 coverage limits are invalid")
    coverage_counts = (
        "hybrid_available", "baseline_available", "hybrid_candidates",
        "baseline_candidates", "hybrid_eligible", "hybrid_selected",
        "baseline_selected", "hybrid_explained", "baseline_community",
        "hybrid_structural_fallback_selected", "hybrid_structural_fallback",
        "attempted", "succeeded", "failed", "failed_count",
    )
    if any(
        not isinstance(coverage.get(field), int)
        or isinstance(coverage.get(field), bool)
        or coverage[field] < 0
        for field in coverage_counts
    ):
        raise ValueError("schema-3 coverage counters are invalid")
    if (
        coverage["hybrid_available"] != len(cohorts["hybrid_only"])
        or coverage["baseline_available"] != len(cohorts["baseline_only"])
        or coverage["hybrid_candidates"] != len(cohorts["hybrid_only"])
        or coverage["baseline_candidates"] != len(cohorts["baseline_only"])
        or coverage["hybrid_eligible"] != len(eligible_ids)
        or coverage["hybrid_selected"] != len(selected["hybrid_only"])
        or coverage["baseline_selected"] != len(selected["baseline_only"])
    ):
        raise ValueError("schema-3 selection coverage counters do not reconcile")
    if len(selected["hybrid_only"]) + len(fallback_ids) > hybrid_requested:
        raise ValueError("schema-3 Hybrid detail budget is exceeded")
    if len(selected["baseline_only"]) > baseline_requested:
        raise ValueError("schema-3 Baseline detail budget is exceeded")

    detail_index = artifact.get("detail_index", {})
    community_index = artifact.get("community_index", {})
    if not isinstance(detail_index, Mapping) or not isinstance(community_index, Mapping):
        raise ValueError("schema-3 detail indexes must be objects")
    if not set(detail_index) <= selected_sets["hybrid_only"] or not set(community_index) <= (
        selected_sets["baseline_only"] | fallback_set
    ):
        raise ValueError("schema-3 detail indexes are not frozen cohort subsets")
    forbidden_baseline = {
        "explanation", "llm_narrative", "overlay", "overlay_evidence",
        "attributions", "factors", "stability", "faithfulness", "mask",
        "masks", "node_masks", "edge_masks",
    }

    def _contains_forbidden_fields(value):
        if isinstance(value, Mapping):
            if forbidden_baseline.intersection(value):
                return True
            return any(_contains_forbidden_fields(child) for child in value.values())
        if isinstance(value, list):
            return any(_contains_forbidden_fields(child) for child in value)
        return False

    for case_id, record in records_by_id.items():
        selected_status = record["detail_status"]
        if case_id in selected_sets["hybrid_only"]:
            if selected_status not in {"available", "failed"} or record.get("detail_kind") != "gnn_explanation":
                raise ValueError("schema-3 Hybrid detail_status is inconsistent with selection")
            if selected_status == "available" and case_id not in detail_index:
                raise ValueError("schema-3 detail_status=available Hybrid detail is missing")
        elif case_id in selected_sets["baseline_only"]:
            if selected_status not in {"community_only", "failed"} or record.get("detail_kind") != "community_control":
                raise ValueError("schema-3 Baseline detail_status is inconsistent with selection")
            if selected_status == "community_only" and case_id not in community_index:
                raise ValueError("schema-3 available Baseline control is missing")
            if _contains_forbidden_fields(record):
                raise ValueError("Baseline records must not contain explanation fields")
        elif case_id in fallback_set:
            if selected_status not in {"community_only", "failed"} or record.get("detail_kind") != "community_control":
                raise ValueError("schema-3 Hybrid structural fallback detail_status is inconsistent with selection")
            if record.get("selection_reason") != "ineligible_preflight_structural_fallback":
                raise ValueError("schema-3 Hybrid structural fallback selection reason is invalid")
            if selected_status == "community_only" and case_id not in community_index:
                raise ValueError("schema-3 Hybrid structural fallback evidence is missing")
            if _contains_forbidden_fields(record):
                raise ValueError(
                    "Hybrid structural fallback records must not contain explanation fields"
                )
        else:
            if (
                record["detail_status"] != "not_selected"
                or record.get("detail_kind") is not None
            ):
                raise ValueError("schema-3 unselected detail_status is invalid")
    for case_id, detail in detail_index.items():
        if (
            detail.get("cohort") != "hybrid_only"
            or detail.get("detail_status") != "available"
            or case_id not in selected_sets["hybrid_only"]
            or "explanation" not in detail
            or case_id in set(
                item.get("case_id")
                for item in artifact.get("generation_diagnostics", {}).get(
                    "failed_attempts", []
                )
                if isinstance(item, Mapping)
            )
        ):
            raise ValueError("schema-3 Hybrid detail is invalid")
    for case_id, detail in community_index.items():
        expected_cohort = (
            "hybrid_only" if case_id in fallback_set else "baseline_only"
        )
        if (
            records_by_id[case_id].get("cohort") != expected_cohort
            or records_by_id[case_id].get("detail_status") != "community_only"
            or records_by_id[case_id].get("community_key") != detail.get("community_key")
            or detail.get("target_person_id") != records_by_id[case_id]["person_id"]
        ):
            raise ValueError("community control target identity must be case-local")
        if _contains_forbidden_fields(detail):
            raise ValueError("Baseline controls must not contain explanation fields")

    communities = artifact.get("communities", {})
    if not isinstance(communities, Mapping):
        raise ValueError("schema-3 communities must be an object")

    def _reject_nested_target_markers(value):
        if isinstance(value, Mapping):
            if "target" in value or "target_person_id" in value:
                raise ValueError("target markers must remain case-local")
            for child in value.values():
                _reject_nested_target_markers(child)
        elif isinstance(value, list):
            for child in value:
                _reject_nested_target_markers(child)

    for community in communities.values():
        if not isinstance(community, Mapping):
            raise ValueError("schema-3 community payload must be an object")
        _reject_nested_target_markers(community)

    catalog = artifact.get("catalog_index")
    if not isinstance(catalog, Mapping) or set(catalog) != set(records_by_id):
        raise ValueError("schema-3 catalog index does not reconcile")
    for case_id, record in records_by_id.items():
        catalog_record = catalog.get(case_id)
        if not isinstance(catalog_record, Mapping) or catalog_record != {
            "cohort": record["cohort"],
            "detail_status": record["detail_status"],
        }:
            raise ValueError("schema-3 catalog index does not reconcile")

    diagnostics = artifact.get("generation_diagnostics")
    if not isinstance(diagnostics, Mapping):
        raise ValueError("schema-3 coverage diagnostics are required")
    expected_attempted_ids = diagnostics.get("attempted_ids")
    expected_succeeded_ids = diagnostics.get("succeeded_ids")
    expected_failed_ids = diagnostics.get("failed_ids")
    if any(
        not isinstance(ids, list) or len(ids) != len(set(ids))
        for ids in (expected_attempted_ids, expected_succeeded_ids, expected_failed_ids)
    ):
        raise ValueError("schema-3 generation ID counters are invalid")
    if set(expected_attempted_ids) != set(selected["hybrid_only"]) | set(selected["baseline_only"]) | fallback_set:
        raise ValueError("schema-3 attempted counter does not reconcile")
    if set(expected_succeeded_ids) & set(expected_failed_ids):
        raise ValueError("schema-3 succeeded and failed counters overlap")
    if set(expected_succeeded_ids) | set(expected_failed_ids) != set(expected_attempted_ids):
        raise ValueError("schema-3 generation counters do not reconcile")
    published_fallback = fallback_set & set(community_index)
    if coverage.get("hybrid_explained") != len(detail_index) or coverage.get(
        "baseline_community"
    ) != len(community_index) - len(published_fallback):
        raise ValueError("schema-3 coverage counters do not reconcile")
    if coverage.get("hybrid_structural_fallback_selected") != len(fallback_ids) or coverage.get(
        "hybrid_structural_fallback"
    ) != len(published_fallback):
        raise ValueError("schema-3 structural fallback counters do not reconcile")
    if coverage.get("attempted") != len(expected_attempted_ids) or coverage.get("succeeded") != len(expected_succeeded_ids) or coverage.get("failed") != len(expected_failed_ids):
        raise ValueError("schema-3 coverage counters do not reconcile")
    if coverage.get("failed_count") != len(expected_failed_ids):
        raise ValueError("schema-3 failure counter does not reconcile")
    hybrid_shortfall = max(0, hybrid_requested - len(detail_index))
    baseline_shortfall = max(
        0, baseline_requested - (len(community_index) - len(published_fallback))
    )
    if (
        coverage.get("hybrid_shortfall") != hybrid_shortfall
        or coverage.get("baseline_shortfall") != baseline_shortfall
        or coverage.get("shortfall") != hybrid_shortfall + baseline_shortfall
    ):
        raise ValueError("schema-3 shortfall totals do not reconcile")
    shortfall_reasons = coverage.get("shortfall_reasons")
    if not isinstance(shortfall_reasons, list) or (
        coverage["shortfall"] and not shortfall_reasons
    ):
        raise ValueError("schema-3 shortfall must record an explicit reason")
    narrative = diagnostics.get("narrative", {})
    if not isinstance(narrative, Mapping) or (
        narrative.get("narrative_attempted")
        != narrative.get("narrative_generated", 0)
        + narrative.get("narrative_fallback", 0)
    ):
        raise ValueError("schema-3 narrative counters do not reconcile")
    fingerprint = artifact.get("run_fingerprint")
    material = fingerprint.get("material") if isinstance(fingerprint, Mapping) else None
    if not isinstance(fingerprint, Mapping) or not isinstance(material, Mapping):
        raise ValueError("schema-3 fingerprint material is required")
    for field in ("schema_version", "checkpoint_id", "corpus_identity", "run_identity", "as_of_identity", "percentile_reference_id", "graph_fingerprint", "model_state_fingerprint", "rank_reference_identity", "eligible_ordered_prefix", "selected_ids", "selection", "policy", "engine_fingerprint", "restart_seeds", "epochs", "limits"):
        if field not in material:
            raise ValueError(f"schema-3 fingerprint is missing {field}")
    if (
        material["corpus_identity"] != corpus_identity
        or material["checkpoint_id"] != checkpoint_id
        or material["selected_ids"] != {cohort: list(ids) for cohort, ids in selected.items()}
        or material["rank_reference_identity"] != reference_id
        or any(
            material.get(field) in (None, "")
            for field in (
                "graph_fingerprint",
                "model_state_fingerprint",
                "rank_reference_identity",
            )
        )
    ):
        raise ValueError("schema-3 fingerprint identity is inconsistent")
    # The fingerprint hashes its own material, so authenticating the token only
    # proves the material is self-consistent. Bind the material to what the
    # artifact actually published, otherwise selection, preflight, policy, and
    # limit tampering all survive an authentic-looking fingerprint.
    engine_material = material["engine_fingerprint"]
    if (
        material["schema_version"] != SCHEMA3
        or material["run_identity"] != run_identity
        or (as_of_id is not None and material["as_of_identity"] != as_of_id)
        or material["percentile_reference_id"] != reference_id
        or material["eligible_ordered_prefix"] != eligible_ordered_prefix
        or material["selection"] != selection
        or material["policy"] != selection
        or material["restart_seeds"] != policy["gnnexplainer_restart_seeds"]
        or material["epochs"] != policy["gnnexplainer_epochs"]
        or material["limits"] != {
            "hybrid_detail": hybrid_requested,
            "baseline_control": baseline_requested,
        }
        or not isinstance(engine_material, Mapping)
        or engine_material.get("graph_sha256") != material["graph_fingerprint"]
        or engine_material.get("model_state_sha256") != material["model_state_fingerprint"]
    ):
        raise ValueError("schema-3 fingerprint does not bind the published artifact")
    expected_fingerprint = _schema3_identity_token(material, label="schema3")
    if fingerprint.get("fingerprint") != expected_fingerprint:
        raise ValueError("schema-3 fingerprint authentication failed")
    json.dumps(artifact, sort_keys=True, allow_nan=False)
    return artifact


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


def _explain_case_with_narrative(
    case,
    explanation_engine,
    narrative_builder,
    *,
    narrative_stats=None,
    narrative_preflight_failed=False,
):
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
    if narrative_stats is not None:
        narrative_stats["narrative_attempted"] += 1
    try:
        if narrative_preflight_failed:
            raise RuntimeError("narrative preflight failed")
        narrative = _detached_json_object(
            narrative_builder(builder_packet), field_name="narrative"
        )
        _validate_grounded_narrative(fact_packet, narrative)
        if narrative_stats is not None:
            narrative_stats["narrative_generated"] += 1
    except Exception as error:
        if narrative_stats is not None:
            narrative_stats["narrative_fallback"] += 1
            if not narrative_preflight_failed:
                narrative_stats["narrative_last_error"] = (
                    f"{type(error).__name__}: {bounded_diagnostic_text(error)}"
                )
        try:
            narrative = _detached_json_object(
                render_template(builder_packet), field_name="narrative fallback"
            )
            narrative["source"] = "deterministic_template"
            narrative["model"] = None
            narrative["prompt_version"] = PROMPT_VERSION
            narrative["validated"] = True
            _validate_grounded_narrative(fact_packet, narrative)
        except Exception:
            if narrative_stats is not None:
                narrative_stats["narrative_failed"] += 1
            raise
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
    """Serialize the legacy schema-2 artifact with inline explanation and community payloads.

    The supplied frozen recovery reference, cohorts, explanations, failures,
    and publication controls are converted into the legacy JSON-compatible
    mapping; schema-3 publication uses ``RecoveryBundleWriter`` instead.
    """

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
    """Reject observability artifacts that violate leakage or schema contracts.

    Schema-3 values use the in-memory validator, while legacy schema-2 values
    retain their inline payload and provenance checks.  Validation performs no
    publication or mutation and returns ``True`` on success.
    """

    if isinstance(artifact, Mapping) and artifact.get("schema_version") == SCHEMA3:
        return validate_schema3_artifact(artifact)
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
    schema_version=SCHEMA2,
    hybrid_detail_limit=None,
    baseline_control_limit=None,
    corpus_identity="in_memory_fixture",
    recovery_run_identity=None,
    instrumentation=None,
    narrative_preflight=None,
):
    """Build the legacy in-memory artifact for small fixtures and adapters only."""
    if str(schema_version) == SCHEMA3:
        return _build_schema3_artifact(
            pool=pool,
            baseline_raw=baseline_raw,
            seed0_gnn_raw=seed0_gnn_raw,
            blend_weight=blend_weight,
            caught_times=caught_times,
            gnn_arm=gnn_arm,
            surrounding_seeds=surrounding_seeds,
            explanation_engine=explanation_engine,
            seed_level_unique_person_recovery=seed_level_unique_person_recovery,
            explanation_limit=explanation_limit,
            hybrid_detail_limit=hybrid_detail_limit,
            baseline_control_limit=baseline_control_limit,
            inspections_per_day=inspections_per_day,
            narrative_builder=narrative_builder,
            corpus_identity=corpus_identity,
            recovery_run_identity=recovery_run_identity,
            instrumentation=instrumentation,
            narrative_preflight=narrative_preflight,
        )
    if str(schema_version) != SCHEMA2:
        raise ValueError("unsupported observability artifact schema version")
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
            # The eligibility ceiling decides which candidates are explained and
            # which are downgraded to community-only evidence, so it has to be
            # part of the staging identity.  Without it a run under a new
            # ceiling would resume into a bundle staged under the old one and
            # replay a community-only payload as if it were an explanation.
            "explainer_max_nodes": MAX_EXPLAINER_INPUT_NODES,
            "explainer_max_edges": MAX_EXPLAINER_INPUT_EDGES,
            # The display bound decides what evidence is actually staged and how
            # much attribution survives into it, so it belongs in the staging
            # identity too -- not just the input ceiling.
            "display_max_nodes": MAX_LOCAL_EXPLANATION_NODES,
            "display_max_edges": MAX_LOCAL_EXPLANATION_EDGES,
            # Every cap that shapes published attribution belongs here as well,
            # or a run under a new truncation policy would resume into and reuse
            # explanations staged under the old one.
            "max_source_rows_per_edge": MAX_LOCAL_SOURCE_ROWS_PER_EDGE,
            "max_node_attribution_source_rows": MAX_NODE_ATTRIBUTION_SOURCE_ROWS,
            "max_node_feature_mask_stats": MAX_NODE_FEATURE_MASK_STATS,
            "narrative_model": MODEL_TAG,
            "narrative_prompt_version": PROMPT_VERSION,
        },
    }


def _build_schema3_bundle(
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
    explanation_limit,
    hybrid_detail_limit,
    baseline_control_limit,
    inspections_per_day,
    narrative_builder,
    corpus_identity,
    recovery_run_identity,
    instrumentation,
    narrative_preflight,
    writer_factory,
):
    """Stage, resume, and atomically publish the balanced schema-3 bundle.

    Selected-case evidence is checkpointed as it is produced, so an
    interrupted run resumes without repeating GNNExplainer or narrative work,
    and communities stream into the bundle instead of being materialized in
    memory.
    """
    seeds = _validated_scope(gnn_arm, surrounding_seeds)
    hybrid_limit, baseline_limit = _resolve_schema3_limits(
        explanation_limit, hybrid_detail_limit, baseline_control_limit
    )
    # The staging identity below is derived from the engine fingerprint, and
    # that material carries the engine's rank_reference_fingerprint, so the
    # reference has to be bound before the fingerprint is taken.
    # _build_schema3_artifact rebinds the identical reference from the same
    # inputs; binding is a pure replacement, so doing it twice is harmless.
    rows, scoring_days = _prepared_pool(pool)
    explanation_engine.bind_rank_reference(
        build_rank_reference(rows, baseline_raw, seed0_gnn_raw, blend_weight),
        _rank_row_bindings(rows, scoring_days),
    )
    run_fingerprint = _recovery_run_fingerprint(
        explanation_engine,
        corpus_identity=corpus_identity,
        seeds=seeds,
        recovery_run_identity=recovery_run_identity,
    )
    # The staging identity has to change with the requested balance, otherwise
    # a 20/10 run could resume into a bundle staged for different limits.
    run_fingerprint["policy"] = {
        **run_fingerprint["policy"],
        "schema_version": SCHEMA3,
        "hybrid_detail_limit": hybrid_limit,
        "baseline_control_limit": baseline_limit,
    }
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
    artifact = _build_schema3_artifact(
        pool=pool,
        baseline_raw=baseline_raw,
        seed0_gnn_raw=seed0_gnn_raw,
        blend_weight=blend_weight,
        caught_times=caught_times,
        gnn_arm=gnn_arm,
        surrounding_seeds=surrounding_seeds,
        explanation_engine=explanation_engine,
        seed_level_unique_person_recovery=seed_level_unique_person_recovery,
        explanation_limit=explanation_limit,
        hybrid_detail_limit=hybrid_detail_limit,
        baseline_control_limit=baseline_control_limit,
        inspections_per_day=inspections_per_day,
        narrative_builder=narrative_builder,
        corpus_identity=corpus_identity,
        recovery_run_identity=recovery_run_identity,
        instrumentation=instrumentation,
        narrative_preflight=narrative_preflight,
        bundle_writer=writer,
    )
    selection = artifact["selection"]
    # The verified tree and catalog are complete before RecoveryBundleWriter
    # publishes the compact schema-3 manifest and current pointer.
    manifest = writer.finalize_schema3(
        selected_hybrid_case_ids=selection["selected_ids"]["hybrid_only"],
        selected_baseline_case_ids=selection["selected_ids"]["baseline_only"],
        hybrid_structural_fallback_case_ids=selection[
            "hybrid_structural_fallback_ids"
        ],
        cohorts=artifact["cohorts"],
        policy=artifact["policy"],
        coverage=artifact["coverage"],
        summary=artifact["summary"],
        run_fingerprint=artifact["run_fingerprint"],
        generation_diagnostics=artifact.get("generation_diagnostics"),
    )
    compact = _detached_json_object(manifest, field_name="bundle manifest")
    if "communities" in compact or "explanations" in compact:
        raise ValueError("production observability manifest must remain compact")
    return compact


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
    schema_version=SCHEMA2,
    hybrid_detail_limit=None,
    baseline_control_limit=None,
    instrumentation=None,
    narrative_preflight=None,
    writer_factory=RecoveryBundleWriter,
):
    """Incrementally build and publish the production recovery bundle."""
    if str(schema_version) == SCHEMA3:
        return _build_schema3_bundle(
            pool=pool,
            baseline_raw=baseline_raw,
            seed0_gnn_raw=seed0_gnn_raw,
            blend_weight=blend_weight,
            caught_times=caught_times,
            gnn_arm=gnn_arm,
            surrounding_seeds=surrounding_seeds,
            explanation_engine=explanation_engine,
            seed_level_unique_person_recovery=seed_level_unique_person_recovery,
            staging_root=staging_root,
            final_root=final_root,
            explanation_limit=explanation_limit,
            hybrid_detail_limit=hybrid_detail_limit,
            baseline_control_limit=baseline_control_limit,
            inspections_per_day=inspections_per_day,
            narrative_builder=narrative_builder,
            corpus_identity=corpus_identity,
            recovery_run_identity=recovery_run_identity,
            instrumentation=instrumentation,
            narrative_preflight=narrative_preflight,
            writer_factory=writer_factory,
        )
    if str(schema_version) != SCHEMA2:
        raise ValueError("unsupported observability bundle schema version")
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
