"""Grounded local narratives for validated seed-0 explanation evidence."""
from __future__ import annotations

import json
import hashlib
import math
import re
import subprocess
from collections.abc import Mapping

from gnn.sage_explainer import validate_explanation_payload


MODEL_TAG = "gemma4:12b"
PROMPT_VERSION = "v4"
_PREFLIGHT_CACHE = set()
_CONTRACT_PREFLIGHT_CACHE = set()

APPROVED_CAVEATS = (
    "This is seed-0 observability, not the three-seed headline result.",
    "GNNExplainer masks are unsigned; direction comes from counterfactual rank effects.",
    "The evidence is associative and does not establish causation.",
)
FACT_PACKET_FIELDS = frozenset(
    {
        "scope", "snapshot", "ranks", "attributions", "component_pooling",
        "rank_fusion", "factors_by_id", "visible_paths", "community_summary", "caveats",
    }
)
FACTOR_FIELDS = frozenset(
    {"label", "kind", "counterfactual", "restart", "stability"}
)
COUNTERFACTUAL_FIELDS = frozenset(
    {
        "percentile_reference_id",
        "ablated_gnn_percentile",
        "original_hybrid_rank",
        "ablated_hybrid_rank",
        "hybrid_rank_delta",
        "original_seed0_probability",
        "ablated_seed0_probability",
        "seed0_probability_delta",
        "original_component_size",
        "ablated_component_size",
    }
)
REQUIRED_COUNTERFACTUAL_FIELDS = frozenset(
    {"original_hybrid_rank", "ablated_hybrid_rank", "hybrid_rank_delta"}
)
RESTART_FIELDS = frozenset({"selection_frequency", "iqr"})
VISIBLE_PATH_FIELDS = frozenset(
    {"edge_id", "relation", "u", "v", "explainer_median", "source_row_ids"}
)
FACTOR_KINDS = frozenset(
    {
        "pair_relation",
        "caught_flag",
        "relation_star",
        "structural_provenance",
        "cotravel_pool",
    }
)
FACTOR_STATES = frozenset({"stable", "unstable", "countervailing"})
RELATION_TYPES = frozenset(
    {"COTRAVEL", "RESIDENCE", "SHARED_PLATE", "SHARED_PLATE_HOT"}
)

CAUSAL_PHRASES = re.compile(
    r"\b(?:caused|causes|proved|proves|guaranteed|guarantees|determined|"
    r"drove|drives|triggered|triggers|led to|resulted in|because of|"
    r"contributed|contributes|responsible for|transferred weights?|"
    r"weights? transferred|learned weights?|learned parameters?)\b",
    re.IGNORECASE,
)
MULTI_SEED_FRAMING = re.compile(
    r"\b(?:three[- ]seed|multi[- ]seed|ensemble|headline)\b", re.IGNORECASE
)
ID_TOKEN = re.compile(r"\b(?:P|E|edge|pair)-[A-Za-z0-9_-]+\b")
NUMBER_TOKEN = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?")

_DIAGNOSTIC_TEXT_LIMIT = 512


def _process_output_text(value):
    """Decode subprocess output for parsing without changing its payload."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if value is None:
        return ""
    return str(value)


def bounded_diagnostic_text(value, *, limit=_DIAGNOSTIC_TEXT_LIMIT):
    """Return a short, bytes-safe diagnostic excerpt."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    else:
        value = str(value)
    value = value.strip()
    if len(value) > limit:
        if limit <= 0:
            return ""
        ellipsis = "...<truncated>"[:limit]
        # Nested wrappers may bound an already formatted diagnostic. Keep the
        # stderr segment (normally the most actionable part) visible even when
        # stdout is much larger than the diagnostic budget.
        stderr_start = value.rfind("; stderr=")
        if stderr_start < 0:
            stderr_start = value.rfind("stderr=")
        if stderr_start >= 0:
            stderr = value[stderr_start:]
            if len(stderr) >= limit:
                prefix_limit = min(160, max(0, limit - len(ellipsis) - 1))
                stderr_limit = max(0, limit - prefix_limit - len(ellipsis))
                prefix = value[:stderr_start]
                return f"{prefix[:prefix_limit]}{ellipsis}{stderr[:stderr_limit]}"
            prefix_limit = max(0, limit - len(stderr) - len(ellipsis))
            return f"{value[:prefix_limit]}{ellipsis}{stderr}"
        return f"{value[:max(0, limit - len(ellipsis))]}{ellipsis}"
    return value


def _format_process_diagnostic(operation, *, returncode=None, stdout=None, stderr=None, error=None):
    """Format bounded subprocess details for errors surfaced to the artifact."""
    parts = [operation]
    if returncode is not None:
        parts.append(f"return code {returncode}")
    if error is not None:
        parts.append(f"error={bounded_diagnostic_text(error)}")
    stdout_text = bounded_diagnostic_text(stdout)
    stderr_text = bounded_diagnostic_text(stderr)
    if stdout_text:
        parts.append(f"stdout={stdout_text!r}")
    if stderr_text:
        parts.append(f"stderr={stderr_text!r}")
    return "; ".join(parts)


def _require_fields(value, *, allowed, required=None, path):
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) for key in value
    ):
        raise ValueError(f"fact packet fields at {path} must form an object")
    keys = set(value)
    required = allowed if required is None else required
    if keys - allowed or required - keys:
        raise ValueError(f"fact packet fields at {path} do not match the allowlist")


def _is_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_finite_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _validate_fact_packet_shape(packet):
    _require_fields(packet, allowed=FACT_PACKET_FIELDS, path="root")
    _require_fields(
        packet["scope"],
        allowed=frozenset({"observability_seed", "gnn_arm"}),
        path="scope",
    )
    if packet["scope"] != {"observability_seed": 0, "gnn_arm": "sage"}:
        raise ValueError("fact packet scope must be seed-0 GraphSAGE observability")
    if not isinstance(packet["snapshot"], str) or not packet["snapshot"].strip():
        raise ValueError("fact packet snapshot must be a non-blank string")

    rank_fields = frozenset({"baseline", "seed0_gnn", "seed0_hybrid"})
    _require_fields(packet["ranks"], allowed=rank_fields, path="ranks")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value <= 0
        for value in packet["ranks"].values()
    ):
        raise ValueError("fact packet ranks must be positive integers")

    attributions = packet["attributions"]
    _require_fields(
        attributions,
        allowed=frozenset(
            {"top_local_nodes", "top_edges", "top_features", "unsigned_masks"}
        ),
        path="attributions",
    )
    if attributions["unsigned_masks"] is not True:
        raise ValueError("fact packet attribution masks must be unsigned")
    attribution_specs = (
        ("top_local_nodes", ("node_id",)),
        ("top_edges", ("edge_id",)),
        ("top_features", ("feature_name", "node_id")),
    )
    for collection_name, id_fields in attribution_specs:
        records = attributions[collection_name]
        if not isinstance(records, list):
            raise ValueError("fact packet attribution records must be lists")
        for record in records:
            allowed = frozenset((*id_fields, "explainer_median"))
            _require_fields(
                record,
                allowed=allowed,
                path=f"attributions.{collection_name}",
            )
            if any(
                not isinstance(record[field], str) or not record[field].strip()
                for field in id_fields
            ):
                raise ValueError("fact packet attribution IDs must be strings")
            if (
                not _is_finite_number(record["explainer_median"])
                or not 0.0 <= float(record["explainer_median"]) <= 1.0
            ):
                raise ValueError("fact packet attribution weights must be in [0, 1]")

    _require_fields(
        packet["component_pooling"],
        allowed=frozenset({"top_members_by_absolute_contribution"}),
        path="component_pooling",
    )
    members = packet["component_pooling"]["top_members_by_absolute_contribution"]
    if not isinstance(members, list):
        raise ValueError("fact packet component members must be a list")
    for member in members:
        _require_fields(
            member,
            allowed=frozenset({"person_id", "pooled_logit_contribution"}),
            path="component_pooling.top_members_by_absolute_contribution",
        )
        if not isinstance(member["person_id"], str) or not member["person_id"].strip():
            raise ValueError("fact packet component member IDs must be strings")
        if not _is_finite_number(member["pooled_logit_contribution"]):
            raise ValueError("fact packet component contributions must be finite")

    fusion_fields = frozenset(
        {
            "daily_budget", "blend_weight", "baseline_percentile",
            "seed0_gnn_percentile", "baseline_weighted_term",
            "seed0_gnn_weighted_term", "hybrid_score",
        }
    )
    _require_fields(packet["rank_fusion"], allowed=fusion_fields, path="rank_fusion")
    fusion = packet["rank_fusion"]
    if fusion["daily_budget"] != 5:
        raise ValueError("fact packet rank fusion must use the 5/day policy")
    if any(not _is_finite_number(fusion[field]) for field in fusion_fields - {"daily_budget"}):
        raise ValueError("fact packet rank-fusion values must be finite")
    if not 0.0 <= fusion["blend_weight"] <= 1.0:
        raise ValueError("fact packet rank-fusion blend weight must be in [0, 1]")
    if not 0.0 <= fusion["baseline_percentile"] <= 1.0 or not 0.0 <= fusion["seed0_gnn_percentile"] <= 1.0:
        raise ValueError("fact packet rank-fusion percentiles must be in [0, 1]")
    if not math.isclose(
        (1.0 - fusion["blend_weight"]) * fusion["baseline_percentile"],
        fusion["baseline_weighted_term"],
        rel_tol=1e-9,
        abs_tol=1e-12,
    ) or not math.isclose(
        fusion["blend_weight"] * fusion["seed0_gnn_percentile"],
        fusion["seed0_gnn_weighted_term"],
        rel_tol=1e-9,
        abs_tol=1e-12,
    ):
        raise ValueError("fact packet rank-fusion weighted terms are inconsistent")
    if not math.isclose(
        fusion["baseline_weighted_term"] + fusion["seed0_gnn_weighted_term"],
        fusion["hybrid_score"],
        rel_tol=1e-9,
        abs_tol=1e-12,
    ):
        raise ValueError("fact packet rank-fusion ledger is inconsistent")
    community_summary_fields = frozenset(
        {
            "complete", "community_key", "component_id", "scoring_day",
            "node_count", "edge_count", "target_person_id",
        }
    )
    _require_fields(
        packet["community_summary"],
        allowed=community_summary_fields,
        path="community_summary",
    )
    community_summary = packet["community_summary"]
    if community_summary["complete"] is not True:
        raise ValueError("fact packet requires a complete community summary")
    if any(
        not isinstance(community_summary[field], str)
        or not community_summary[field].strip()
        for field in (
            "community_key", "component_id", "scoring_day", "target_person_id"
        )
    ):
        raise ValueError("fact packet community identity fields must be strings")
    if any(
        not _is_integer(community_summary[field]) or community_summary[field] < 0
        for field in ("node_count", "edge_count")
    ):
        raise ValueError("fact packet community counts must be nonnegative integers")

    factors = packet["factors_by_id"]
    if not isinstance(factors, dict):
        raise ValueError("fact packet factors_by_id must be an object")
    for factor_id, factor in factors.items():
        if (
            not isinstance(factor_id, str)
            or not factor_id.strip()
            or "." in factor_id
        ):
            raise ValueError("fact packet factor IDs must be non-blank dot-free strings")
        _require_fields(factor, allowed=FACTOR_FIELDS, path=f"factors_by_id.{factor_id}")
        _require_fields(
            factor["counterfactual"],
            allowed=COUNTERFACTUAL_FIELDS,
            required=REQUIRED_COUNTERFACTUAL_FIELDS,
            path=f"factors_by_id.{factor_id}.counterfactual",
        )
        _require_fields(
            factor["restart"],
            allowed=RESTART_FIELDS,
            path=f"factors_by_id.{factor_id}.restart",
        )
        if not isinstance(factor["label"], str) or not factor["label"].strip():
            raise ValueError("fact packet factor labels and states must be strings")
        if (
            not isinstance(factor["kind"], str)
            or factor["kind"] not in FACTOR_KINDS
        ):
            raise ValueError("fact packet factor kind is not allowlisted")
        if (
            not isinstance(factor["stability"], str)
            or factor["stability"] not in FACTOR_STATES
        ):
            raise ValueError("fact packet factor stability is not allowlisted")

        counterfactual = factor["counterfactual"]
        for field in (
            "original_hybrid_rank",
            "ablated_hybrid_rank",
            "hybrid_rank_delta",
        ):
            if not _is_integer(counterfactual[field]):
                raise ValueError(
                    f"fact packet counterfactual {field} must be an integer"
                )
        if (
            counterfactual["original_hybrid_rank"] <= 0
            or counterfactual["ablated_hybrid_rank"] <= 0
        ):
            raise ValueError("fact packet counterfactual ranks must be positive")
        if counterfactual["hybrid_rank_delta"] != (
            counterfactual["ablated_hybrid_rank"]
            - counterfactual["original_hybrid_rank"]
        ):
            raise ValueError("fact packet counterfactual rank delta is inconsistent")
        if (
            counterfactual["original_hybrid_rank"]
            != packet["ranks"]["seed0_hybrid"]
        ):
            raise ValueError(
                "fact packet counterfactual original rank is inconsistent"
            )

        if "percentile_reference_id" in counterfactual and (
            not isinstance(counterfactual["percentile_reference_id"], str)
            or not counterfactual["percentile_reference_id"].strip()
        ):
            raise ValueError("fact packet percentile reference must be a string")
        for field in (
            "ablated_gnn_percentile",
            "original_seed0_probability",
            "ablated_seed0_probability",
        ):
            if field in counterfactual and (
                not _is_finite_number(counterfactual[field])
                or not 0.0 <= float(counterfactual[field]) <= 1.0
            ):
                raise ValueError(f"fact packet {field} must be finite in [0, 1]")
        if "seed0_probability_delta" in counterfactual and (
            not _is_finite_number(counterfactual["seed0_probability_delta"])
            or not -1.0 <= float(counterfactual["seed0_probability_delta"]) <= 1.0
        ):
            raise ValueError(
                "fact packet seed0_probability_delta must be finite in [-1, 1]"
            )
        probability_fields = {
            "original_seed0_probability",
            "ablated_seed0_probability",
            "seed0_probability_delta",
        }
        present_probability_fields = probability_fields & counterfactual.keys()
        if present_probability_fields and present_probability_fields != probability_fields:
            raise ValueError(
                "fact packet counterfactual probability evidence is incomplete"
            )
        if present_probability_fields and not math.isclose(
            float(counterfactual["seed0_probability_delta"]),
            float(counterfactual["ablated_seed0_probability"])
            - float(counterfactual["original_seed0_probability"]),
            rel_tol=1e-9,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "fact packet counterfactual probability delta is inconsistent"
            )
        for field in ("original_component_size", "ablated_component_size"):
            if field in counterfactual and (
                not _is_integer(counterfactual[field]) or counterfactual[field] <= 0
            ):
                raise ValueError(f"fact packet {field} must be a positive integer")

        restart = factor["restart"]
        if (
            not _is_finite_number(restart["selection_frequency"])
            or not 0.0 <= float(restart["selection_frequency"]) <= 1.0
        ):
            raise ValueError(
                "fact packet restart selection_frequency must be finite in [0, 1]"
            )
        if not _is_finite_number(restart["iqr"]) or float(restart["iqr"]) < 0.0:
            raise ValueError("fact packet restart iqr must be finite and nonnegative")

    paths = packet["visible_paths"]
    if not isinstance(paths, list):
        raise ValueError("fact packet visible_paths must be a list")
    for index, path in enumerate(paths):
        _require_fields(
            path, allowed=VISIBLE_PATH_FIELDS, path=f"visible_paths.{index}"
        )
        if any(
            not isinstance(path[field], str) or not path[field].strip()
            for field in ("edge_id", "u", "v")
        ):
            raise ValueError("fact packet visible path IDs must be non-blank strings")
        if (
            not isinstance(path["relation"], str)
            or path["relation"] not in RELATION_TYPES
        ):
            raise ValueError("fact packet visible path relation is not allowlisted")
        if (
            not _is_finite_number(path["explainer_median"])
            or not 0.0 <= float(path["explainer_median"]) <= 1.0
        ):
            raise ValueError(
                "fact packet explainer_median must be finite in [0, 1]"
            )
        source_row_ids = path["source_row_ids"]
        if (
            not isinstance(source_row_ids, list)
            or not source_row_ids
            or any(
                not isinstance(source_id, str) or not source_id.strip()
                for source_id in source_row_ids
            )
        ):
            raise ValueError("fact packet visible path source IDs must be strings")
    if packet["caveats"] != list(APPROVED_CAVEATS):
        raise ValueError("fact packet caveats must match the approved evidence boundary")


def _validated_fact_packet(packet):
    if not isinstance(packet, Mapping):
        raise ValueError("fact packet must be a JSON object")
    validate_explanation_payload(packet)
    try:
        encoded = json.dumps(packet, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("fact packet must be JSON-safe") from exc
    decoded = json.loads(encoded)
    if not isinstance(decoded, dict):
        raise ValueError("fact packet must be a JSON object")
    _validate_fact_packet_shape(decoded)
    return decoded


def _rank_only_packet(packet):
    """Salvage only independently validated rank evidence from a bad packet."""
    if not isinstance(packet, Mapping):
        raise ValueError("fact packet must be a JSON object")
    try:
        scope = packet["scope"]
        snapshot = packet["snapshot"]
        ranks = packet["ranks"]
    except KeyError as exc:
        raise ValueError("fact packet lacks rank-only fallback evidence") from exc
    safe_packet = {
        "scope": scope,
        "snapshot": snapshot,
        "ranks": ranks,
        "attributions": packet["attributions"],
        "component_pooling": packet["component_pooling"],
        "rank_fusion": packet["rank_fusion"],
        "factors_by_id": {},
        "visible_paths": [],
        "community_summary": packet["community_summary"],
        "caveats": list(APPROVED_CAVEATS),
    }
    return _validated_fact_packet(safe_packet)


def _installed_model_names(stdout):
    text = _process_output_text(stdout)
    lines = [line.split() for line in text.splitlines() if line.split()]
    return {columns[0] for columns in lines[1:] if columns}


def preflight_local_model(*, runner=subprocess.run, timeout_seconds=180):
    """Verify the required local model once per injected runner/model pair."""
    cache_key = (MODEL_TAG, runner)
    if cache_key in _PREFLIGHT_CACHE:
        return MODEL_TAG
    command = ["ollama", "list"]
    try:
        listed = runner(
            command,
            capture_output=True,
            text=True,
            timeout=min(timeout_seconds, 10),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            _format_process_diagnostic(
                "ollama list timed out",
                error=f"timeout after {exc.timeout}s",
                stdout=getattr(exc, "stdout", None) or getattr(exc, "output", None),
                stderr=getattr(exc, "stderr", None),
            )
        ) from exc
    except OSError as exc:
        raise RuntimeError(_format_process_diagnostic("ollama list failed", error=exc)) from exc
    if listed.returncode != 0:
        raise RuntimeError(
            _format_process_diagnostic(
                "ollama list failed",
                returncode=listed.returncode,
                stdout=getattr(listed, "stdout", None),
                stderr=getattr(listed, "stderr", None),
            )
        )
    if MODEL_TAG not in _installed_model_names(getattr(listed, "stdout", None)):
        raise RuntimeError(
            _format_process_diagnostic(
                f"local {MODEL_TAG} is unavailable",
                returncode=listed.returncode,
                stdout=getattr(listed, "stdout", None),
                stderr=getattr(listed, "stderr", None),
            )
        )
    _PREFLIGHT_CACHE.add(cache_key)
    return MODEL_TAG


def _selector_preflight_packet():
    return {
        "scope": {"observability_seed": 0, "gnn_arm": "sage"},
        "snapshot": "2025-01-01T00:00:00Z",
        "ranks": {"baseline": 10, "seed0_gnn": 2, "seed0_hybrid": 4},
        "attributions": {
            "top_local_nodes": [],
            "top_edges": [],
            "top_features": [],
            "unsigned_masks": True,
        },
        "component_pooling": {"top_members_by_absolute_contribution": []},
        "rank_fusion": {
            "daily_budget": 5,
            "blend_weight": 0.75,
            "baseline_percentile": 0.8,
            "seed0_gnn_percentile": 0.6,
            "baseline_weighted_term": 0.2,
            "seed0_gnn_weighted_term": 0.45,
            "hybrid_score": 0.65,
        },
        "factors_by_id": {},
        "visible_paths": [],
        "community_summary": {
            "complete": True,
            "community_key": "community:sha256:preflight",
            "component_id": "component:sha256:preflight",
            "scoring_day": "2025-01-01T00:00:00Z",
            "node_count": 1,
            "edge_count": 0,
            "target_person_id": "P-PREFLIGHT",
        },
        "caveats": list(APPROVED_CAVEATS),
    }


def preflight_narrative_contract(
    *, runner=subprocess.run, timeout_seconds=180, packet=None
):
    """Verify Ollama, the exact model tag, and selector resolution live."""
    packet = _validated_fact_packet(
        _selector_preflight_packet() if packet is None else packet
    )
    prompt = build_prompt(packet)
    cache_key = (MODEL_TAG, PROMPT_VERSION, hashlib.sha256(prompt.encode()).hexdigest(), runner)
    if cache_key in _CONTRACT_PREFLIGHT_CACHE:
        return MODEL_TAG
    preflight_local_model(runner=runner, timeout_seconds=timeout_seconds)
    last_error = None
    for _attempt in range(4):
        try:
            selector = _run_local_gemma(
                prompt,
                runner=runner,
                timeout_seconds=timeout_seconds,
                preflight=False,
            )
            resolve_narrative_selector(packet, selector)
            _CONTRACT_PREFLIGHT_CACHE.add(cache_key)
            return MODEL_TAG
        except (
            OSError,
            RuntimeError,
            TimeoutError,
            subprocess.TimeoutExpired,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            last_error = exc
    detail = bounded_diagnostic_text(last_error) if last_error is not None else "unknown error"
    raise RuntimeError(
        f"local Gemma selector-generation contract failed: {detail}"
    ) from last_error


def _run_local_gemma(prompt, *, runner, timeout_seconds, preflight=True):
    if preflight:
        preflight_local_model(runner=runner, timeout_seconds=timeout_seconds)

    command = [
        "ollama",
        "run",
        MODEL_TAG,
        "--format",
        "json",
        "--think=false",
        "--keepalive",
        "10m",
        "--nowordwrap",
    ]
    try:
        completed = runner(
            command,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            _format_process_diagnostic(
                "ollama run timed out",
                error=f"timeout after {exc.timeout}s",
                stdout=getattr(exc, "stdout", None) or getattr(exc, "output", None),
                stderr=getattr(exc, "stderr", None),
            )
        ) from exc
    except OSError as exc:
        raise RuntimeError(_format_process_diagnostic("ollama run failed", error=exc)) from exc
    if completed.returncode != 0:
        raise RuntimeError(
            _format_process_diagnostic(
                "ollama run failed",
                returncode=completed.returncode,
                stdout=getattr(completed, "stdout", None),
                stderr=getattr(completed, "stderr", None),
            )
        )
    output = _process_output_text(getattr(completed, "stdout", None))
    try:
        return json.loads(output)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            _format_process_diagnostic(
                "ollama run returned invalid JSON",
                stdout=getattr(completed, "stdout", None),
                stderr=getattr(completed, "stderr", None),
                error=exc,
            )
        ) from exc


def build_fact_packet(explanation):
    """Return the allowlisted model-available evidence used by the narrator."""
    trace = explanation["decision_trace"]
    packet = {
        "scope": {"observability_seed": 0, "gnn_arm": "sage"},
        "snapshot": explanation["scoring_day"],
        "ranks": {
            "baseline": int(trace["baseline_rank"]),
            "seed0_gnn": int(trace["seed0_gnn_rank"]),
            "seed0_hybrid": int(trace["seed0_hybrid_rank"]),
        },
        "attributions": {
            "top_local_nodes": [
                {
                    "node_id": record["node_id"],
                    "explainer_median": record["explainer_median"],
                }
                for record in explanation["attributions"]["top_local_nodes"]
            ],
            "top_edges": [
                {
                    "edge_id": record["edge_id"],
                    "explainer_median": record["explainer_median"],
                }
                for record in explanation["attributions"]["top_edges"]
            ],
            "top_features": [
                {
                    "feature_name": record["feature_name"],
                    "node_id": record["node_id"],
                    "explainer_median": record["explainer_median"],
                }
                for record in explanation["attributions"]["top_features"]
            ],
            "unsigned_masks": True,
        },
        "component_pooling": {
            "top_members_by_absolute_contribution": [
                {
                    "person_id": record["person_id"],
                    "pooled_logit_contribution": record[
                        "pooled_logit_contribution"
                    ],
                }
                for record in explanation["decision_ledger"][
                    "component_pooling"
                ]["top_members_by_absolute_contribution"]
            ]
        },
        "rank_fusion": {
            key: explanation["decision_ledger"]["rank_fusion"][key]
            for key in (
                "daily_budget",
                "blend_weight",
                "baseline_percentile",
                "seed0_gnn_percentile",
                "baseline_weighted_term",
                "seed0_gnn_weighted_term",
                "hybrid_score",
            )
        },
        "factors_by_id": {},
        "visible_paths": [
            {
                "edge_id": record["edge_id"],
                "relation": record["edge_type"],
                "u": record["u"],
                "v": record["v"],
                "explainer_median": record["explainer_median"],
                "source_row_ids": list(record["source_row_ids"]),
            }
            for record in explanation["attributions"]["top_edges"][:10]
        ],
        "community_summary": {
            "complete": explanation["community"]["complete"],
            "community_key": explanation["community"]["community_key"],
            "component_id": explanation["community"]["component_id"],
            "scoring_day": explanation["community"]["scoring_day"],
            "node_count": len(explanation["community"]["nodes"]),
            "edge_count": len(explanation["community"]["edges"]),
            "target_person_id": explanation["person_id"],
        },
        "caveats": list(APPROVED_CAVEATS),
    }
    for factor in explanation["factors"]:
        validate_explanation_payload(factor["counterfactual"])
        validate_explanation_payload(factor["restart"])
        packet["factors_by_id"][factor["factor_id"]] = {
            "label": factor["label"],
            "kind": factor["kind"],
            "counterfactual": {
                key: factor["counterfactual"][key]
                for key in sorted(COUNTERFACTUAL_FIELDS)
                if key in factor["counterfactual"]
            },
            "restart": {
                key: factor["restart"][key]
                for key in sorted(RESTART_FIELDS)
                if key in factor["restart"]
            },
            "stability": factor["stability"],
        }
    return _validated_fact_packet(packet)


def build_prompt(packet):
    packet = _validated_fact_packet(packet)
    catalog = build_selector_catalog(packet)
    selector = {
        "selected_summary_id": catalog["default_summary_id"],
        "selected_claim_ids": catalog["required_claim_ids"],
    }
    context = {
        "prompt_version": PROMPT_VERSION,
        "snapshot": packet["snapshot"],
        "ranks": packet["ranks"],
        "community_key": packet["community_summary"]["community_key"],
        "unsigned_masks": packet["attributions"]["unsigned_masks"],
    }
    return (
        "Return JSON only. Return exactly this compact selector object with no "
        "additional keys, prose, source references, or rewritten claims: "
        + json.dumps(selector, sort_keys=True, separators=(",", ":"))
        + "\nCONTEXT\n"
        + json.dumps(context, sort_keys=True, separators=(",", ":"))
    )


def _resolve_source_ref(packet, source_ref):
    value = packet
    for part in source_ref.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
            continue
        if isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
            continue
        if isinstance(value, list) and part.isdigit() and int(part) >= len(value):
            raise ValueError(f"unknown source_ref: {source_ref}")
        raise ValueError(f"unknown source_ref: {source_ref}")
    return value


def _add_supported(records, text, refs):
    records.setdefault(text, []).append(frozenset(refs))


def _supported_summaries(packet):
    ranks = packet["ranks"]
    records = {}
    _add_supported(
        records,
        f"In seed 0, the recorded Hybrid rank was {ranks['seed0_hybrid']}.",
        ("scope.observability_seed", "ranks.seed0_hybrid"),
    )
    _add_supported(
        records,
        (
            f"In seed 0, Baseline rank was {ranks['baseline']}, GNN rank was "
            f"{ranks['seed0_gnn']}, and Hybrid rank was {ranks['seed0_hybrid']}."
        ),
        (
            "scope.observability_seed",
            "ranks.baseline",
            "ranks.seed0_gnn",
            "ranks.seed0_hybrid",
        ),
    )
    return records


def _supported_claims(packet):
    records = {}
    if packet["attributions"]["top_local_nodes"]:
        node = packet["attributions"]["top_local_nodes"][0]
        _add_supported(
            records,
            f"The top unsigned local-node attribution was {node['node_id']} with median weight {node['explainer_median']}.",
            (
                "attributions.top_local_nodes.0.node_id",
                "attributions.top_local_nodes.0.explainer_median",
            ),
        )
    if packet["attributions"]["top_edges"]:
        edge = packet["attributions"]["top_edges"][0]
        _add_supported(
            records,
            f"The top unsigned edge attribution was {edge['edge_id']} with median weight {edge['explainer_median']}.",
            (
                "attributions.top_edges.0.edge_id",
                "attributions.top_edges.0.explainer_median",
            ),
        )
    if packet["attributions"]["top_features"]:
        feature = packet["attributions"]["top_features"][0]
        _add_supported(
            records,
            f"For {feature['node_id']}, the top unsigned feature attribution was {feature['feature_name']} with median weight {feature['explainer_median']}.",
            (
                "attributions.top_features.0.node_id",
                "attributions.top_features.0.feature_name",
                "attributions.top_features.0.explainer_median",
            ),
        )
    members = packet["component_pooling"][
        "top_members_by_absolute_contribution"
    ]
    if members:
        member = members[0]
        _add_supported(
            records,
            f"The exact pooled-logit term for {member['person_id']} was {member['pooled_logit_contribution']}.",
            (
                "component_pooling.top_members_by_absolute_contribution.0.person_id",
                "component_pooling.top_members_by_absolute_contribution.0.pooled_logit_contribution",
            ),
        )
    fusion = packet["rank_fusion"]
    _add_supported(
        records,
        (
            f"With GNN blend weight {fusion['blend_weight']}, baseline term "
            f"{fusion['baseline_weighted_term']} plus GNN term "
            f"{fusion['seed0_gnn_weighted_term']} equaled Hybrid score "
            f"{fusion['hybrid_score']} under daily budget {fusion['daily_budget']}."
        ),
        (
            "rank_fusion.blend_weight",
            "rank_fusion.baseline_weighted_term",
            "rank_fusion.seed0_gnn_weighted_term",
            "rank_fusion.hybrid_score",
            "rank_fusion.daily_budget",
        ),
    )
    for factor_id, factor in packet["factors_by_id"].items():
        counterfactual = factor["counterfactual"]
        _add_supported(
            records,
            (
                f"Removing {factor['label']} moved Hybrid rank from "
                f"{counterfactual['original_hybrid_rank']} to "
                f"{counterfactual['ablated_hybrid_rank']}."
            ),
            (
                f"factors_by_id.{factor_id}.label",
                f"factors_by_id.{factor_id}.counterfactual.original_hybrid_rank",
                f"factors_by_id.{factor_id}.counterfactual.ablated_hybrid_rank",
            ),
        )
        _add_supported(
            records,
            f"The recorded factor stability is {factor['stability']}.",
            (f"factors_by_id.{factor_id}.stability",),
        )
    for index, path in enumerate(packet["visible_paths"]):
        _add_supported(
            records,
            f"The visible relation is {path['relation']}.",
            (f"visible_paths.{index}.relation",),
        )
        _add_supported(
            records,
            (
                f"The visible {path['relation']} path connects "
                f"{path['u']} and {path['v']}."
            ),
            (
                f"visible_paths.{index}.relation",
                f"visible_paths.{index}.u",
                f"visible_paths.{index}.v",
            ),
        )
    for index in (1, 2):
        _add_supported(records, packet["caveats"][index], (f"caveats.{index}",))
    return records


def _supported_records_json(records):
    return [
        {"text": text, "source_refs": sorted(refs)}
        for text in sorted(records)
        for refs in sorted(records[text], key=lambda values: tuple(sorted(values)))
    ]


def _stable_record_catalog(records, *, prefix):
    catalog = {}
    for text in sorted(records):
        for refs in sorted(
            records[text], key=lambda values: tuple(sorted(values))
        ):
            record = {"text": text, "source_refs": sorted(refs)}
            encoded = json.dumps(
                record, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            record_id = f"{prefix}:sha256:{hashlib.sha256(encoded).hexdigest()[:16]}"
            existing = catalog.get(record_id)
            if existing is not None and existing != record:
                raise RuntimeError("narrative selector ID collision")
            catalog[record_id] = record
    return catalog


def build_selector_catalog(packet):
    """Build stable server-side records and the exact required selector IDs."""
    packet = _validated_fact_packet(packet)
    summaries = _stable_record_catalog(
        _supported_summaries(packet), prefix="summary"
    )
    claims = _stable_record_catalog(_supported_claims(packet), prefix="claim")
    default_summary_id = next(
        record_id
        for record_id, record in summaries.items()
        if "the recorded Hybrid rank" in record["text"]
    )

    required_claim_ids = []
    category_prefixes = (
        "attributions.top_local_nodes.",
        "attributions.top_edges.",
        "attributions.top_features.",
        "component_pooling.top_members_by_absolute_contribution.",
        "rank_fusion.",
    )
    for category_prefix in category_prefixes:
        matches = [
            record_id
            for record_id, record in claims.items()
            if any(
                source_ref.startswith(category_prefix)
                for source_ref in record["source_refs"]
            )
        ]
        if matches:
            required_claim_ids.append(sorted(matches)[0])
    if packet["factors_by_id"]:
        top_factor_id = max(
            packet["factors_by_id"],
            key=lambda factor_id: (
                abs(
                    packet["factors_by_id"][factor_id]["counterfactual"][
                        "hybrid_rank_delta"
                    ]
                ),
                factor_id,
            ),
        )
        factor_prefix = f"factors_by_id.{top_factor_id}.counterfactual."
        factor_matches = [
            record_id
            for record_id, record in claims.items()
            if any(
                source_ref == factor_prefix + "ablated_hybrid_rank"
                for source_ref in record["source_refs"]
            )
        ]
        if not factor_matches:
            raise RuntimeError("required factor selector record is unavailable")
        required_claim_ids.append(sorted(factor_matches)[0])
    return {
        "default_summary_id": default_summary_id,
        "required_claim_ids": required_claim_ids,
        "summaries_by_id": summaries,
        "claims_by_id": claims,
    }


def _validate_text(packet, record, *, supported):
    if not isinstance(record, Mapping):
        raise ValueError("unsupported narrative claim: record must be an object")
    text = str(record.get("text", "")).strip()
    refs = record.get("source_refs")
    if not text or not isinstance(refs, list) or not refs:
        raise ValueError("unsupported narrative claim: text and source_refs are required")

    if any(not isinstance(source_ref, str) or not source_ref for source_ref in refs):
        raise ValueError(
            "unsupported narrative claim: source_refs must be non-blank strings"
        )
    if len(set(refs)) != len(refs):
        raise ValueError(
            "unsupported narrative claim: source_refs must not contain duplicates"
        )
    normalized_refs = list(refs)
    values = [_resolve_source_ref(packet, source_ref) for source_ref in normalized_refs]
    evidence_text = json.dumps(values, sort_keys=True, allow_nan=False)
    if CAUSAL_PHRASES.search(text):
        raise ValueError("unsupported narrative claim: causal language")
    if MULTI_SEED_FRAMING.search(text):
        raise ValueError("unsupported narrative claim: multi-seed framing")
    if any(token not in evidence_text for token in ID_TOKEN.findall(text)):
        raise ValueError("unsupported narrative claim: unknown identifier")

    referenced_numbers = set(NUMBER_TOKEN.findall(evidence_text))
    allowed_scope_numbers = (
        {"0"} if packet.get("scope", {}).get("observability_seed") == 0 else set()
    )
    if any(
        number not in referenced_numbers | allowed_scope_numbers
        for number in NUMBER_TOKEN.findall(text)
    ):
        raise ValueError("unsupported narrative claim: unknown number")
    supported_refsets = supported.get(text, [])
    if frozenset(normalized_refs) not in supported_refsets:
        raise ValueError("unsupported narrative claim: text is not grounded by refs")
    return {"text": text, "source_refs": normalized_refs}


def validate_candidate(packet, candidate):
    packet = _validated_fact_packet(packet)
    if not isinstance(candidate, Mapping):
        raise ValueError("unsupported narrative claim: candidate must be an object")
    summary = _validate_text(
        packet,
        candidate.get("summary", {}),
        supported=_supported_summaries(packet),
    )
    if "seed 0" not in summary["text"].casefold():
        raise ValueError("unsupported narrative claim: missing single-seed scope")

    claims_value = candidate.get("claims", [])
    if not isinstance(claims_value, list):
        raise ValueError("unsupported narrative claim: claims must be a list")
    supported_claims = _supported_claims(packet)
    claims = [
        _validate_text(packet, item, supported=supported_claims)
        for item in claims_value
    ]
    return {"summary": summary, "claims": claims}


def _require_production_coverage(packet, validated):
    required_prefixes = []
    for field in ("top_local_nodes", "top_edges", "top_features"):
        if packet["attributions"][field]:
            required_prefixes.append(f"attributions.{field}.")
    if packet["component_pooling"]["top_members_by_absolute_contribution"]:
        required_prefixes.append(
            "component_pooling.top_members_by_absolute_contribution."
        )
    required_prefixes.append("rank_fusion.")
    if packet["factors_by_id"]:
        required_prefixes.append("factors_by_id.")
    all_refs = [
        source_ref
        for claim in validated["claims"]
        for source_ref in claim["source_refs"]
    ]
    missing = [
        prefix
        for prefix in required_prefixes
        if not any(source_ref.startswith(prefix) for source_ref in all_refs)
    ]
    if missing:
        raise ValueError(
            "unsupported narrative claim: required v4 evidence is missing"
        )


def resolve_narrative_selector(packet, selector):
    """Resolve compact model-selected IDs to exact prevalidated records."""
    packet = _validated_fact_packet(packet)
    if not isinstance(selector, Mapping) or set(selector) != {
        "selected_summary_id",
        "selected_claim_ids",
    }:
        raise ValueError("narrative selector has invalid fields")
    summary_id = selector["selected_summary_id"]
    claim_ids = selector["selected_claim_ids"]
    if not isinstance(summary_id, str) or not isinstance(claim_ids, list):
        raise ValueError("narrative selector IDs have invalid types")
    if any(not isinstance(claim_id, str) for claim_id in claim_ids):
        raise ValueError("narrative selector claim IDs must be strings")
    if len(set(claim_ids)) != len(claim_ids):
        raise ValueError("narrative selector claim IDs must not be duplicates")

    catalog = build_selector_catalog(packet)
    if summary_id not in catalog["summaries_by_id"]:
        raise ValueError("narrative selector contains an unknown summary ID")
    unknown = set(claim_ids).difference(catalog["claims_by_id"])
    if unknown:
        raise ValueError("narrative selector contains an unknown claim ID")
    if set(claim_ids) != set(catalog["required_claim_ids"]):
        raise ValueError("narrative selector is missing required claim IDs")

    candidate = {
        "summary": catalog["summaries_by_id"][summary_id],
        "claims": [
            catalog["claims_by_id"][claim_id]
            for claim_id in catalog["required_claim_ids"]
        ],
    }
    validated = validate_candidate(packet, candidate)
    _require_production_coverage(packet, validated)
    return validated


def render_template(packet):
    packet = _validated_fact_packet(packet)
    factors = list(packet["factors_by_id"].items())
    factors.sort(
        key=lambda item: (
            -abs(item[1]["counterfactual"]["hybrid_rank_delta"]),
            item[0],
        )
    )
    candidate = {
        "summary": {
            "text": (
                f"In seed 0, Baseline rank was {packet['ranks']['baseline']}, "
                f"GNN rank was {packet['ranks']['seed0_gnn']}, and Hybrid rank was "
                f"{packet['ranks']['seed0_hybrid']}."
            ),
            "source_refs": [
                "scope.observability_seed",
                "ranks.baseline",
                "ranks.seed0_gnn",
                "ranks.seed0_hybrid",
            ],
        },
        "claims": [],
    }
    if factors:
        factor_id, factor = factors[0]
        candidate["claims"].append(
            {
                "text": (
                    f"Removing {factor['label']} moved Hybrid rank from "
                    f"{factor['counterfactual']['original_hybrid_rank']} to "
                    f"{factor['counterfactual']['ablated_hybrid_rank']}."
                ),
                "source_refs": [
                    f"factors_by_id.{factor_id}.label",
                    (
                        f"factors_by_id.{factor_id}.counterfactual."
                        "original_hybrid_rank"
                    ),
                    (
                        f"factors_by_id.{factor_id}.counterfactual."
                        "ablated_hybrid_rank"
                    ),
                ],
            }
        )
    supported = _supported_claims(packet)
    required_prefixes = (
        "attributions.top_local_nodes.",
        "attributions.top_edges.",
        "attributions.top_features.",
        "component_pooling.top_members_by_absolute_contribution.",
        "rank_fusion.",
    )
    for text in sorted(supported):
        for refs in sorted(supported[text], key=lambda item: tuple(sorted(item))):
            if any(
                any(source_ref.startswith(prefix) for source_ref in refs)
                for prefix in required_prefixes
            ):
                candidate["claims"].append(
                    {"text": text, "source_refs": sorted(refs)}
                )
    validated = validate_candidate(packet, candidate)
    return {
        "source": "deterministic_template",
        "model": None,
        "prompt_version": PROMPT_VERSION,
        "summary": validated["summary"]["text"],
        "summary_source_refs": validated["summary"]["source_refs"],
        "claims": validated["claims"],
        "validated": True,
    }


def generate_narrative(
    packet,
    *,
    runner=subprocess.run,
    timeout_seconds=180,
    mode="production",
    max_retries=3,
):
    if mode == "template":
        try:
            return render_template(_validated_fact_packet(packet))
        except ValueError:
            return render_template(_rank_only_packet(packet))
    if mode != "production":
        raise ValueError("mode must be 'production' or 'template'")
    packet = _validated_fact_packet(packet)
    preflight_local_model(runner=runner, timeout_seconds=timeout_seconds)
    prompt = build_prompt(packet)
    last_error = None
    attempt_count = int(max_retries) + 1
    for _attempt in range(attempt_count):
        try:
            selector = _run_local_gemma(
                prompt,
                runner=runner,
                timeout_seconds=timeout_seconds,
                preflight=False,
            )
            validated = resolve_narrative_selector(packet, selector)
            return {
                "source": "llm",
                "model": MODEL_TAG,
                "prompt_version": PROMPT_VERSION,
                "summary": validated["summary"]["text"],
                "summary_source_refs": validated["summary"]["source_refs"],
                "claims": validated["claims"],
                "validated": True,
            }
        except (
            OSError,
            RuntimeError,
            TimeoutError,
            subprocess.TimeoutExpired,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            last_error = exc
    detail = bounded_diagnostic_text(last_error) if last_error is not None else "unknown error"
    raise RuntimeError(
        f"local narrative failed after {attempt_count} attempts: {detail}"
    ) from last_error
