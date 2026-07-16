"""Grounded local narratives for validated seed-0 explanation evidence."""
from __future__ import annotations

import json
import math
import re
import subprocess
from collections.abc import Mapping

from gnn.sage_explainer import validate_explanation_payload


MODEL_TAG = "gemma4:12b"
PROMPT_VERSION = "v1"

APPROVED_CAVEATS = (
    "This is seed-0 observability, not the three-seed headline result.",
    "GNNExplainer masks are unsigned; direction comes from counterfactual rank effects.",
    "The evidence is associative and does not establish causation.",
)
FACT_PACKET_FIELDS = frozenset(
    {"scope", "snapshot", "ranks", "factors_by_id", "visible_paths", "caveats"}
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
    {"edge_id", "relation", "u", "v", "explainer_median"}
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
        "factors_by_id": {},
        "visible_paths": [],
        "caveats": list(APPROVED_CAVEATS),
    }
    return _validated_fact_packet(safe_packet)


def _installed_model_names(stdout):
    lines = [line.split() for line in str(stdout).splitlines() if line.split()]
    return {columns[0] for columns in lines[1:] if columns}


def _run_local_gemma(prompt, *, runner, timeout_seconds):
    listed = runner(
        ["ollama", "list"],
        capture_output=True,
        text=True,
        timeout=min(timeout_seconds, 10),
        check=False,
    )
    if listed.returncode != 0 or MODEL_TAG not in _installed_model_names(listed.stdout):
        raise RuntimeError(f"local {MODEL_TAG} is unavailable")

    completed = runner(
        [
            "ollama",
            "run",
            MODEL_TAG,
            "--format",
            "json",
            "--think=false",
            "--keepalive",
            "10m",
        ],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("local Gemma generation failed")
    return json.loads(completed.stdout)


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
        "factors_by_id": {},
        "visible_paths": [
            {
                "edge_id": edge["edge_id"],
                "relation": edge["edge_type"],
                "u": edge["u"],
                "v": edge["v"],
                "explainer_median": edge.get("explainer_median", 0.0),
            }
            for edge in explanation["community"]["edges"]
        ],
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
    schema = {
        "summary": {"text": "string", "source_refs": ["dot.path"]},
        "claims": [{"text": "string", "source_refs": ["dot.path"]}],
    }
    return (
        "Return JSON only. Explain this seed-0 observability result using only the "
        "fact packet. Every sentence needs source_refs. Copy one allowed summary "
        "and zero or more allowed claims exactly, including their source_refs. Do "
        "not mention ensemble, multi-seed, or headline results. Required schema: "
        + json.dumps(schema, sort_keys=True)
        + "\nALLOWED_SUMMARIES\n"
        + json.dumps(_supported_records_json(_supported_summaries(packet)), sort_keys=True)
        + "\nALLOWED_CLAIMS\n"
        + json.dumps(_supported_records_json(_supported_claims(packet)), sort_keys=True)
        + "\nFACT_PACKET\n"
        + json.dumps(packet, sort_keys=True)
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


def generate_narrative(packet, *, runner=subprocess.run, timeout_seconds=180):
    try:
        packet = _validated_fact_packet(packet)
    except ValueError:
        return render_template(_rank_only_packet(packet))
    try:
        candidate = _run_local_gemma(
            build_prompt(packet), runner=runner, timeout_seconds=timeout_seconds
        )
        validated = validate_candidate(packet, candidate)
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
    ):
        return render_template(packet)
