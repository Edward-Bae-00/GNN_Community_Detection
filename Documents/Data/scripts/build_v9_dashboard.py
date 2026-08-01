#!/usr/bin/env python3
"""Build a V9-only dashboard from the V9 standalone shell.

Run after `build_dashboard.py Documents/Data/synthetic_cbp_graph_corpus_v9`
has produced `dashboard_data.json`.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import sys
import csv
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path


HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(os.path.dirname(DATA_DIR))
V9_CORPUS = os.path.join(DATA_DIR, "synthetic_cbp_graph_corpus_v9")
V9_DATA = os.path.join(V9_CORPUS, "dashboard_data.json")
V9_DEMO = os.path.join(REPO_ROOT, "gnn", "diagnostics", "demo_comparison_v9.json")
DIAGNOSTICS_DIR = os.path.join(REPO_ROOT, "gnn", "diagnostics")
V9_GNN_ARCHITECTURE_COMPARISON = os.path.join(
    DIAGNOSTICS_DIR, "gnn_architecture_comparison_v9.json"
)
V9_RECOVERY_EXPLANATIONS = os.path.join(
    REPO_ROOT,
    "gnn",
    "diagnostics",
    "hybrid_recovery_explanations_v9.json",
)
V9_UNSUPERVISED_ARTIFACT = "unsupervised_ad_results_v9.json"
GENERIC_UNSUPERVISED_ARTIFACT = "unsupervised_ad_results.json"
V9_CORPUS_NAME = "synthetic_cbp_graph_corpus_v9"
V9_GNN_ARCHITECTURE_IDS = ("sage", "rgcn", "gat", "gin", "kpiaa")
OUT_DIR = os.path.join(DATA_DIR, "v9_dashboard")


def p(*args):
    print(*args, flush=True)


def _normalize_v9_template(html: str) -> str:
    """Remove stale V7 renderers and duplicate Explorer CSS from the template."""
    html = re.sub(
        r"(?ms)^[ \t]*entityResolution:\{rendered:false,render\(\)\{.*?^\}\},[ \t]*\n",
        "",
        html,
    )

    style_start = html.find("<style")
    style_end = html.find("</style>", style_start)
    marker = "/* ---- Community Explorer ---- */"
    if style_start < 0 or style_end < 0:
        return html

    style = html[style_start:style_end]
    markers = list(re.finditer(re.escape(marker), style))
    if len(markers) > 1:
        style = style[:markers[0].start()] + style[markers[-1].start():]
        html = html[:style_start] + style + html[style_end:]
    return html


def _daily_crossing_series(corpus_dir):
    """Return actual crossing-event volume for each V9 test-window day."""
    split_path = os.path.join(corpus_dir, "train_valid_test_splits.csv")
    events_path = os.path.join(corpus_dir, "crossing_events.csv")
    test_ids = set()
    with open(split_path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("split") == "test":
                test_ids.add(row.get("entity_id"))

    counts = Counter()
    with open(events_path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("event_id") not in test_ids:
                continue
            timestamp = row.get("event_timestamp_utc", "")
            if not timestamp:
                continue
            try:
                day = datetime.fromisoformat(
                    timestamp.replace("Z", "+00:00")
                ).date().isoformat()
            except ValueError:
                day = timestamp[:10]
            counts[day] += 1
    return [
        {"date": day, "crossings": counts[day]}
        for day in sorted(counts)
    ]


def _is_compatible_v9_demo(demo):
    """Return whether demo satisfies the fields dereferenced by V9 Results."""
    if not isinstance(demo, dict):
        return False
    for section in ("overall", "overall_daily", "stratified"):
        value = demo.get(section)
        if not isinstance(value, dict):
            return False
        for arm in ("baseline", "hybrid"):
            if not isinstance(value.get(arm), dict):
                return False
    for arm in ("baseline", "hybrid"):
        if not isinstance(demo["stratified"][arm].get("observable"), dict):
            return False
    return (
        isinstance(demo.get("stratum_hidden"), dict)
        and "hidden_total" in demo
    )


def _load_recovery_artifact(path, output_dir=None):
    if not os.path.exists(path):
        p(f"[v9-dashboard] WARNING: {path} not found; case evidence unavailable.")
        return None
    try:
        with open(path) as handle:
            artifact = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        p(f"[v9-dashboard] WARNING: invalid recovery artifact: {error}")
        return None
    if not isinstance(artifact, dict):
        p("[v9-dashboard] WARNING: unsupported recovery artifact schema.")
        return None
    if artifact.get("schema_version") == "2.0":
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        from v9_recovery_sidecars import publish_prepackaged_manifest

        try:
            dashboard_output = OUT_DIR if output_dir is None else output_dir
            if (
                isinstance(artifact.get("case_index"), dict)
                and isinstance(artifact.get("community_index"), dict)
                and isinstance(artifact.get("bundle_id"), str)
            ):
                return publish_prepackaged_manifest(
                    artifact,
                    path,
                    os.path.join(dashboard_output, "recovery"),
                )
            raise ValueError(
                "schema-2 recovery requires a prepackaged producer bundle"
            )
        except ValueError as error:
            raise ValueError(
                f"invalid schema-2 recovery artifact: {error}"
            ) from error
    if artifact.get("schema_version") != "1.0":
        p("[v9-dashboard] WARNING: unsupported recovery artifact schema.")
        return None
    return artifact


def _load_v9_unsupervised_artifact(diagnostics_dir):
    """Load the safest available anomaly artifact for the V9-only dashboard."""
    diagnostics_dir = os.fspath(diagnostics_dir)
    qualified = os.path.join(diagnostics_dir, V9_UNSUPERVISED_ARTIFACT)
    generic = os.path.join(diagnostics_dir, GENERIC_UNSUPERVISED_ARTIFACT)
    selected = qualified if os.path.exists(qualified) else generic
    if not os.path.exists(selected):
        return None

    with open(selected) as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"unsupervised AD artifact must be an object: {selected}")

    try:
        schema_version = int(payload.get("schema_version", 2))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"unsupervised AD artifact has invalid schema_version: {selected}"
        ) from exc

    if schema_version >= 3:
        provenance = payload.get("provenance")
        corpus_name = (
            provenance.get("corpus_name")
            if isinstance(provenance, dict)
            else None
        )
        if corpus_name != V9_CORPUS_NAME:
            raise ValueError(
                "V9 dashboard refused schema-v3 artifact for wrong corpus "
                f"{corpus_name!r}: {selected}"
            )
        if selected == generic:
            p(
                "[v9-dashboard] WARNING: using generic schema-v3 compatibility "
                f"fallback {generic}; regenerate {qualified}."
            )
    elif selected == generic:
        p(
            "[v9-dashboard] WARNING: using legacy schema-v2 generic fallback "
            f"{generic}; provenance cannot verify the V9 corpus."
        )
    else:
        p(
            "[v9-dashboard] WARNING: using legacy schema-v2 corpus-qualified "
            f"artifact {qualified}; provenance cannot verify the V9 corpus."
        )
    return payload


V9_STRATA = ("observable", "dark", "lone")
V9_FEATURE_SCHEMA = (
    "bias", "degree_cotravel", "degree_residence", "degree_shared_plate",
    "degree_shared_plate_hot", "log1p_cotravel_component_size",
    "log1p_households_spanned", "caught_before_snapshot",
)
V9_RELATION_SCHEMA = {
    "COTRAVEL": 0, "RESIDENCE": 1, "SHARED_PLATE": 2, "SHARED_PLATE_HOT": 3,
}
V9_ARM_METADATA = {
    "sage": {
        "label": "GraphSAGE",
        "looks_for": "As-of caught-propagation over the person graph, ignoring edge types. Best/representative GNN arm; the one the hybrid fuses.",
        "num_relations": 4,
    },
    "rgcn": {
        "label": "RGCN full graph",
        "looks_for": "As-of caught-propagation over typed COTRAVEL, RESIDENCE, SHARED_PLATE, SHARED_PLATE_HOT relations.",
        "num_relations": 4,
    },
    "gat": {
        "label": "GAT (attention)",
        "looks_for": "As-of caught-propagation with attention over neighbors.",
        "num_relations": 4,
    },
    "gin": {
        "label": "GIN",
        "looks_for": "As-of caught-propagation with a high-expressivity GIN.",
        "num_relations": 4,
    },
    "kpiaa": {
        "label": "KPI-AA (approx)",
        "looks_for": "As-of caught-propagation mimicking key-person ID.",
        "num_relations": 4,
    },
}


def _walk_finite_numeric_values(value, path="artifact"):
    """Iteratively reject booleans and non-finite numeric values."""
    pending = [(path, value)]
    while pending:
        current_path, current = pending.pop()
        if isinstance(current, bool):
            raise ValueError(f"{current_path} must not be boolean")
        if isinstance(current, (int, float)):
            try:
                finite = math.isfinite(float(current))
            except (OverflowError, ValueError):
                finite = False
            if not finite:
                raise ValueError(f"{current_path} must be finite")
        elif isinstance(current, dict):
            pending.extend(
                (f"{current_path}.{key}", child)
                for key, child in current.items()
            )
        elif isinstance(current, list):
            pending.extend(
                (f"{current_path}[{index}]", child)
                for index, child in enumerate(current)
            )


def _strict_integer(value, path, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{path} must be an integer >= {minimum}")
    return value


def _strict_metric_number(metrics, key, path):
    if key not in metrics:
        raise ValueError(f"missing required metric {path}.{key}")
    value = metrics[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path}.{key} must be numeric")
    try:
        finite = math.isfinite(float(value))
    except (OverflowError, ValueError):
        finite = False
    if not finite:
        raise ValueError(f"{path}.{key} must be finite")
    return float(value)


def _exact_keys(mapping, expected, path):
    if not isinstance(mapping, dict):
        raise ValueError(f"{path} must be an object")
    if set(mapping) != set(expected):
        raise ValueError(f"{path} has unexpected or missing keys")


def _validate_global_metrics(metrics, ks, hidden_total, pool_size, path):
    _exact_keys(
        metrics,
        {
            metric for k in ks
            for metric in (f"found@{k}", f"precision@{k}", f"recall@{k}", f"f1@{k}")
        },
        path,
    )
    found_by_k = {}
    for k in ks:
        found = _strict_integer(metrics[f"found@{k}"], f"{path}.found@{k}")
        if found > min(k, pool_size, hidden_total):
            raise ValueError(f"{path}.found@{k} exceeds pool capacity")
        precision = _strict_metric_number(metrics, f"precision@{k}", path)
        recall = _strict_metric_number(metrics, f"recall@{k}", path)
        f1 = _strict_metric_number(metrics, f"f1@{k}", path)
        expected_precision = round(found / k, 4)
        expected_recall = round(found / hidden_total, 4) if hidden_total else 0.0
        expected_f1 = round(
            2 * expected_precision * expected_recall
            / (expected_precision + expected_recall), 4
        ) if expected_precision + expected_recall else 0.0
        if (precision, recall, f1) != (expected_precision, expected_recall, expected_f1):
            raise ValueError(f"inconsistent global metrics at {path} for K={k}")
        found_by_k[k] = found
    return found_by_k


def _validate_stratified_metrics(metrics, ks, stratum_hidden, path):
    _exact_keys(metrics, V9_STRATA, path)
    expected = {"hidden", *(metric for k in ks for metric in (f"found@{k}", f"recall@{k}"))}
    found_by_k = {k: 0 for k in ks}
    for stratum in V9_STRATA:
        row = metrics[stratum]
        _exact_keys(row, expected, f"{path}.{stratum}")
        denominator = _strict_integer(row["hidden"], f"{path}.{stratum}.hidden")
        if denominator != stratum_hidden[stratum]:
            raise ValueError(f"{path}.{stratum}.hidden disagrees with stratum_hidden")
        for k in ks:
            found = _strict_integer(row[f"found@{k}"], f"{path}.{stratum}.found@{k}")
            if found > denominator:
                raise ValueError(f"{path}.{stratum}.found@{k} exceeds denominator")
            recall = _strict_metric_number(row, f"recall@{k}", f"{path}.{stratum}")
            expected_recall = round(found / denominator, 4) if denominator else 0.0
            if recall != expected_recall:
                raise ValueError(f"inconsistent stratified recall at {path}.{stratum} for K={k}")
            found_by_k[k] += found
    return found_by_k


def _validate_daily_metrics(metrics, daily_ks, hidden_total, pool_size, path):
    expected = {"n_days"}
    expected.update(
        metric for k in daily_ks
        for metric in (
            f"daily_found@{k}", f"daily_found_by_day@{k}",
            f"daily_recall@{k}", f"daily_precision@{k}",
            f"daily_f1@{k}", f"daily_budget@{k}",
        )
    )
    _exact_keys(metrics, expected, path)
    n_days = _strict_integer(metrics["n_days"], f"{path}.n_days")
    if n_days > pool_size:
        raise ValueError(f"{path}.n_days exceeds pool_size")
    for k in daily_ks:
        found = _strict_integer(metrics[f"daily_found@{k}"], f"{path}.daily_found@{k}")
        budget = _strict_integer(metrics[f"daily_budget@{k}"], f"{path}.daily_budget@{k}")
        if found > budget or found > hidden_total or budget > pool_size or budget > k * n_days:
            raise ValueError(f"invalid daily denominator at {path} for K={k}")
        precision = _strict_metric_number(metrics, f"daily_precision@{k}", path)
        recall = _strict_metric_number(metrics, f"daily_recall@{k}", path)
        f1 = _strict_metric_number(metrics, f"daily_f1@{k}", path)
        exact_precision = found / budget if budget else 0.0
        exact_recall = found / hidden_total if hidden_total else 0.0
        expected_f1 = round(
            2 * exact_precision * exact_recall / (exact_precision + exact_recall), 4
        ) if exact_precision + exact_recall else 0.0
        if (precision, recall, f1) != (
            round(exact_precision, 4), round(exact_recall, 4), expected_f1
        ):
            raise ValueError(f"inconsistent daily metrics at {path} for K={k}")
        rows = metrics[f"daily_found_by_day@{k}"]
        if not isinstance(rows, list) or len(rows) != n_days:
            raise ValueError(f"{path}.daily_found_by_day@{k} must list one row per day")
        dates = set()
        by_day_total = 0
        for index, row in enumerate(rows):
            row_path = f"{path}.daily_found_by_day@{k}[{index}]"
            _exact_keys(row, {"date", "found"}, row_path)
            if not isinstance(row["date"], str) or not row["date"] or row["date"] in dates:
                raise ValueError(f"{row_path}.date must be a unique non-empty string")
            dates.add(row["date"])
            day_found = _strict_integer(row["found"], f"{row_path}.found")
            if day_found > k:
                raise ValueError(f"{row_path}.found exceeds daily quota")
            by_day_total += day_found
        if by_day_total != found:
            raise ValueError(f"{path}.daily_found_by_day@{k} does not sum to daily_found@{k}")


def _validate_v9_gnn_architecture_artifact(artifact):
    """Validate the producer's schema locally without importing model code."""
    if not isinstance(artifact, dict):
        raise ValueError("artifact must be an object")
    _walk_finite_numeric_values(artifact)
    required = {
        "schema_version", "artifact_kind", "corpus", "corpus_identity", "substrate",
        "seeds", "epochs", "train_bucket", "ks", "daily_ks", "pool_size",
        "hidden_total", "stratum_hidden", "feature_schema", "relation_schema",
        "architecture_order", "architectures",
    }
    _exact_keys(artifact, required, "artifact")
    if artifact["schema_version"] != 1:
        raise ValueError("schema_version must be 1")
    if artifact["artifact_kind"] != "gnn_architecture_comparison":
        raise ValueError("artifact_kind must be gnn_architecture_comparison")
    for field in ("corpus", "corpus_identity", "substrate", "train_bucket"):
        if not isinstance(artifact[field], str) or not artifact[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if artifact["corpus"] != V9_CORPUS_NAME or artifact["substrate"] != "oracle":
        raise ValueError("artifact provenance does not match V9")
    identity = artifact["corpus_identity"]
    if not Path(identity).is_absolute() or str(Path(identity).resolve()) != identity:
        raise ValueError("corpus_identity must be an absolute normalized resolved path")
    if os.path.realpath(identity) != os.path.realpath(V9_CORPUS):
        raise ValueError("artifact corpus_identity does not match V9 corpus")
    if artifact["seeds"] != [0, 1, 2]:
        raise ValueError("artifact seeds must be exactly [0, 1, 2]")
    _strict_integer(artifact["epochs"], "epochs", minimum=1)
    for field in ("ks", "daily_ks"):
        values = artifact[field]
        if not isinstance(values, list) or not values:
            raise ValueError(f"{field} must not be empty")
        checked = [_strict_integer(value, f"{field}[{i}]", minimum=1) for i, value in enumerate(values)]
        if len(set(checked)) != len(checked):
            raise ValueError(f"{field} must not contain duplicates")
    pool_size = _strict_integer(artifact["pool_size"], "pool_size")
    hidden_total = _strict_integer(artifact["hidden_total"], "hidden_total")
    if hidden_total > pool_size:
        raise ValueError("hidden_total cannot exceed pool_size")
    _exact_keys(artifact["stratum_hidden"], V9_STRATA, "stratum_hidden")
    stratum_hidden = {
        key: _strict_integer(artifact["stratum_hidden"][key], f"stratum_hidden.{key}")
        for key in V9_STRATA
    }
    if sum(stratum_hidden.values()) != hidden_total:
        raise ValueError("stratum_hidden denominators must sum to hidden_total")
    if artifact["feature_schema"] != list(V9_FEATURE_SCHEMA):
        raise ValueError("feature_schema does not match producer schema")
    if artifact["relation_schema"] != V9_RELATION_SCHEMA:
        raise ValueError("relation_schema does not match producer schema")
    if artifact["architecture_order"] != list(V9_GNN_ARCHITECTURE_IDS):
        raise ValueError("architecture_order does not match registry")
    architectures = artifact["architectures"]
    if not isinstance(architectures, dict) or list(architectures) != list(V9_GNN_ARCHITECTURE_IDS):
        raise ValueError("architectures must contain the complete registry in order")
    ks = artifact["ks"]
    daily_ks = artifact["daily_ks"]
    for architecture_id in V9_GNN_ARCHITECTURE_IDS:
        row = architectures[architecture_id]
        _exact_keys(row, {"label", "looks_for", "num_relations", "ensemble", "per_seed"}, f"architectures.{architecture_id}")
        metadata = V9_ARM_METADATA[architecture_id]
        if row["label"] != metadata["label"] or row["looks_for"] != metadata["looks_for"]:
            raise ValueError(f"architectures.{architecture_id} metadata does not match registry")
        if _strict_integer(row["num_relations"], f"architectures.{architecture_id}.num_relations", minimum=1) != 4:
            raise ValueError(f"architectures.{architecture_id}.num_relations does not match registry")
        ensemble = row["ensemble"]
        _exact_keys(ensemble, {"overall", "stratified", "daily"}, f"architectures.{architecture_id}.ensemble")
        overall_found = _validate_global_metrics(ensemble["overall"], ks, hidden_total, pool_size, f"architectures.{architecture_id}.ensemble.overall")
        stratified_found = _validate_stratified_metrics(ensemble["stratified"], ks, stratum_hidden, f"architectures.{architecture_id}.ensemble.stratified")
        if overall_found != stratified_found:
            raise ValueError(f"architectures.{architecture_id}.ensemble metrics do not partition")
        _validate_daily_metrics(ensemble["daily"], daily_ks, hidden_total, pool_size, f"architectures.{architecture_id}.ensemble.daily")
        per_seed = row["per_seed"]
        if not isinstance(per_seed, dict) or set(per_seed) != {"0", "1", "2"}:
            raise ValueError(f"architectures.{architecture_id}.per_seed keys must match seeds")
        for seed in ("0", "1", "2"):
            seed_row = per_seed[seed]
            _exact_keys(seed_row, {"overall", "stratified"}, f"architectures.{architecture_id}.per_seed.{seed}")
            seed_overall_found = _validate_global_metrics(seed_row["overall"], ks, hidden_total, pool_size, f"architectures.{architecture_id}.per_seed.{seed}.overall")
            seed_stratified_found = _validate_stratified_metrics(seed_row["stratified"], ks, stratum_hidden, f"architectures.{architecture_id}.per_seed.{seed}.stratified")
            if seed_overall_found != seed_stratified_found:
                raise ValueError(f"architectures.{architecture_id}.per_seed.{seed} metrics do not partition")
    return artifact


def _is_compatible_v9_gnn_architecture(artifact):
    """Return whether ``artifact`` satisfies the optional V9 artifact contract."""
    try:
        _validate_v9_gnn_architecture_artifact(artifact)
    except (TypeError, ValueError):
        return False
    return True


def _reject_duplicate_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _load_v9_gnn_architecture_artifact(path):
    """Load the optional architecture artifact, warning and failing closed."""
    if not os.path.exists(path):
        p(f"[v9-dashboard] WARNING: GNN architecture comparison {path} not found.")
        return None
    try:
        with open(path) as handle:
            artifact = json.load(handle, object_pairs_hook=_reject_duplicate_json_keys)
        _validate_v9_gnn_architecture_artifact(artifact)
    except (OSError, json.JSONDecodeError, RecursionError, TypeError, ValueError) as error:
        p(f"[v9-dashboard] WARNING: invalid GNN architecture comparison: {error}")
        return None
    return artifact


def _load_v9_data(output_dir=None) -> dict:
    if not os.path.exists(V9_DATA):
        p(f"[v9-dashboard] ERROR: {V9_DATA} not found.")
        p("[v9-dashboard] Run: .venv/bin/python Documents/Data/scripts/build_dashboard.py "
          "Documents/Data/synthetic_cbp_graph_corpus_v9")
        sys.exit(1)
    with open(V9_DATA) as f:
        data = json.load(f)
    data["v9DailyCrossings"] = _daily_crossing_series(V9_CORPUS)
    candidate_demo = data.get("v9Demo")
    if os.path.exists(V9_DEMO):
        with open(V9_DEMO) as f:
            candidate_demo = json.load(f)
    else:
        p(f"[v9-dashboard] WARNING: {V9_DEMO} not found; V9 Results tab will be sparse.")
    if _is_compatible_v9_demo(candidate_demo):
        data["v9Demo"] = candidate_demo
    else:
        data.pop("v9Demo", None)
        if candidate_demo is not None:
            p("[v9-dashboard] WARNING: discarded incompatible V9 demo payload.")

    data.pop("v9RecoveryExplainer", None)
    recovery_artifact = _load_recovery_artifact(
        V9_RECOVERY_EXPLANATIONS, output_dir=output_dir
    )
    if recovery_artifact is not None:
        data["v9RecoveryExplainer"] = recovery_artifact

    v9_unsup = _load_v9_unsupervised_artifact(DIAGNOSTICS_DIR)
    if v9_unsup is not None:
        data["unsupervisedAD"] = v9_unsup
    else:
        p(
            "[v9-dashboard] WARNING: no corpus-qualified or generic "
            "unsupervised AD artifact found; anomaly-ranking tab will be sparse."
        )

    data.pop("v9GNNArchitectureComparison", None)
    gnn_architecture = _load_v9_gnn_architecture_artifact(
        V9_GNN_ARCHITECTURE_COMPARISON
    )
    if gnn_architecture is not None:
        data["v9GNNArchitectureComparison"] = gnn_architecture

    return data


def _embed_dashboard_data(html: str, data: dict) -> str:
    """Replace the template data blob with a self-contained V9 data blob."""
    data_start = html.find("const DATA = ")
    iife_start = html.find("\n(async function(){", data_start)
    if data_start < 0 or iife_start < 0:
        raise ValueError("dashboard template is missing its DATA/IIFE boundary")
    blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    # Prevent a data string from prematurely closing the surrounding script.
    blob = blob.replace("<", "\\u003c")
    return (
        html[:data_start]
        + "\nlet DATA = " + blob + ";\nlet D = DATA;\n"
        + html[iife_start:]
    )


def _make_d3_optional(html: str) -> str:
    """Keep V9 tab bootstrapping alive when the optional D3 CDN is unavailable."""
    old = """const tip=d3.select('body').append('div').attr('class','tooltip');
function showTip(e,html){
  tip.html(html).style('opacity',1);
  const b=tip.node().getBoundingClientRect();
  let x=e.clientX+14,y=e.clientY-12;
  if(x+b.width>window.innerWidth-10)x=e.clientX-b.width-14;
  if(y+b.height>window.innerHeight-10)y=e.clientY-b.height-10;
  if(y<6)y=6;
  tip.style('left',x+'px').style('top',y+'px');
}
function hideTip(){tip.style('opacity',0)}"""
    new = """const tip=document.createElement('div');
tip.className='tooltip';
document.body.appendChild(tip);
function showTip(e,html){
  tip.innerHTML=html;
  tip.style.opacity='1';
  const b=tip.getBoundingClientRect();
  let x=e.clientX+14,y=e.clientY-12;
  if(x+b.width>window.innerWidth-10)x=e.clientX-b.width-14;
  if(y+b.height>window.innerHeight-10)y=e.clientY-b.height-10;
  if(y<6)y=6;
  tip.style.left=x+'px';
  tip.style.top=y+'px';
}
function hideTip(){tip.style.opacity='0'}"""
    if old not in html:
        raise ValueError("dashboard template is missing its tooltip bootstrap")
    return html.replace(old, new, 1)


def _inject_dashboard_tab_scripts(html, helper_js, renderer_js):
    """Place helpers before ``Tabs`` and renderers inside its object literal."""
    tabs_marker = "const Tabs={"
    explorer_marker = "explorer:{rendered:false,render(){"
    if tabs_marker not in html or explorer_marker not in html:
        raise ValueError("dashboard template is missing its tab registry markers")
    html = html.replace(tabs_marker, helper_js + "\n" + tabs_marker, 1)
    return html.replace(explorer_marker, renderer_js + explorer_marker, 1)


def _inject_recovery_assets(html, css, js):
    """Idempotently place recovery explorer behavior and styles in the shell."""
    if not isinstance(css, str) or not css or not isinstance(js, str) or not js:
        raise ValueError("recovery assets must be non-empty strings")
    if html.count(css) > 1 or html.count(js) > 1:
        raise ValueError("dashboard contains duplicate recovery assets")

    style_start = html.find("<style")
    style_end = html.find("</style>", style_start)
    if style_start < 0 or style_end < 0:
        raise ValueError("dashboard template is missing its style boundary")
    css_index = html.find(css)
    if css_index >= 0 and not (
        style_start < css_index and css_index + len(css) <= style_end
    ):
        raise ValueError("recovery asset CSS is outside the style boundary")

    tabs_marker = "const Tabs={"
    tabs_index = html.find(tabs_marker)
    if tabs_index < 0:
        raise ValueError("dashboard template is missing its tab registry marker")
    js_index = html.find(js)
    if js_index >= tabs_index:
        raise ValueError("recovery asset JavaScript must precede the tab registry")

    if css not in html:
        html = html.replace("</style>", css + "\n</style>", 1)
    if js not in html:
        html = html.replace(tabs_marker, js + "\n" + tabs_marker, 1)
    return html


# Tabs that live in the interactive "explore" group; everything else is a readout.
_NAV_EXPLORE_TABS = ("map", "explorer")
_NAV_GROUP_LABELS = {
    "readout": "Readouts",
    "explore": "Explore & drill in",
}


def _inject_v9_nav_and_sections(html, nav_buttons, sections):
    """Inject the V9 nav buttons and tab sections.

    The base v8 template historically carried ``<!-- V9_NAV_TABS -->`` and
    ``<!-- V9_TAB_SECTIONS -->`` markers, but current base builds omit them, which
    silently dropped the V9 tabs. Fall back to appending before the closing
    ``</nav>``/``</main>`` so the V9 tabs are always present and reachable.
    """
    nav_marker = "    <!-- V9_NAV_TABS -->\n"
    if nav_marker in html:
        html = html.replace(nav_marker, "    " + nav_buttons, 1)
    elif nav_buttons.strip() not in html:
        html = html.replace("</nav>", "  " + nav_buttons + "</nav>", 1)
    section_marker = "  <!-- V9_TAB_SECTIONS -->\n"
    if section_marker in html:
        html = html.replace(section_marker, sections, 1)
    elif sections.strip() not in html:
        html = html.replace("</main>", sections + "</main>", 1)
    return html


def _rewrite_nav_js(html):
    """Replace flat tab click-binding with delegated, hash-routed navigation."""
    old_bind = (
        "document.querySelectorAll('nav.tabs button')"
        ".forEach(b=>b.addEventListener('click',()=>switchTab(b.dataset.tab)));"
    )
    if old_bind not in html:
        raise ValueError("dashboard template is missing its nav click binding")
    new_js = (
        "function _navTabButtons(){return Array.from("
        "document.querySelectorAll('nav.tabs [data-navigate-tab]'));}\n"
        "function _syncNavSelection(name){_navTabButtons().forEach(b=>{"
        "const on=b.dataset.navigateTab===name;b.classList.toggle('active',on);"
        "b.setAttribute('aria-selected',on?'true':'false');});}\n"
        "function _tabFromHash(){const n=(location.hash||'').replace(/^#/,'');"
        "return (n&&document.getElementById('tab-'+n))?n:null;}\n"
        "function _navigateTo(name){if(!document.getElementById('tab-'+name))return;"
        "switchTab(name);_syncNavSelection(name);}\n"
        "document.querySelector('nav.tabs').addEventListener('click',e=>{"
        "const b=e.target.closest('[data-navigate-tab]');if(!b)return;"
        "e.preventDefault();const name=b.dataset.navigateTab;"
        "if(('#'+name)===location.hash){_navigateTo(name);}else{location.hash='#'+name;}});\n"
        "window.addEventListener('hashchange',()=>{const n=_tabFromHash();"
        "if(n)_navigateTo(n);});\n"
        "(function(){const n=_tabFromHash();_navigateTo(n||'overview');})();"
    )
    return html.replace(old_bind, new_js, 1)


def _apply_grouped_accessible_nav(html):
    """Group the flat tab bar into accessible, hash-routed navigation groups.

    Produces ``data-nav-group`` sections (readout/explore), ARIA tab semantics
    (``role``, ``aria-controls``, ``aria-selected``), ``data-navigate-tab`` hooks
    for delegated clicks, and hash-state routing. Contract asserted by
    tests/test_v9_dashboard_builder.py::test_generated_dashboard_has_grouped_accessible_navigation_and_hash_state.
    """
    match = re.search(r'<nav class="tabs">(.*?)</nav>', html, re.S)
    if not match:
        raise ValueError("dashboard template is missing its <nav class=\"tabs\"> bar")
    buttons = re.findall(
        r'<button\s+data-tab="([a-zA-Z0-9]+)"([^>]*)>(.*?)</button>',
        match.group(1),
        re.S,
    )
    if not buttons:
        raise ValueError("dashboard nav bar has no tab buttons to group")
    grouped = {"readout": [], "explore": []}
    for name, attrs, label in buttons:
        active = "active" in attrs or name == "overview"
        cls = ' class="active"' if active else ""
        selected = "true" if active else "false"
        grouped["explore" if name in _NAV_EXPLORE_TABS else "readout"].append(
            f'<button role="tab" data-tab="{name}" data-navigate-tab="{name}" '
            f'aria-controls="tab-{name}" aria-selected="{selected}"{cls}>'
            f'{label.strip()}</button>'
        )
    parts = []
    for gid in ("readout", "explore"):
        if not grouped[gid]:
            continue
        parts.append(
            f'<div class="nav-group" data-nav-group="{gid}" role="tablist" '
            f'aria-label="{_NAV_GROUP_LABELS[gid]}">' + "".join(grouped[gid]) + "</div>"
        )
    new_nav = (
        '<nav class="tabs" aria-label="Dashboard sections">' + "".join(parts) + "</nav>"
    )
    html = html[: match.start()] + new_nav + html[match.end():]
    return _rewrite_nav_js(html)


def _validate_recovery_explorer_mount(html):
    """Fail closed if the local artifact explorer mount is missing or ambiguous."""
    exact_once = (
        'href="#v9-case-evidence"',
        'id="v9-case-evidence"',
        "DATA.v9RecoveryExplainer",
    )
    if any(html.count(token) != 1 for token in exact_once):
        raise ValueError("dashboard recovery explorer mount is invalid")
    return html


def _publish_staged_dashboard(staged_dir, destination_dir):
    """Swap a complete staged dashboard into place, restoring the prior tree on failure."""
    staged = Path(staged_dir)
    destination = Path(destination_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(
        prefix=f".{destination.name}.backup-", dir=destination.parent
    ))
    backup.rmdir()
    prior_moved = False
    try:
        if destination.exists():
            os.replace(destination, backup)
            prior_moved = True
        os.replace(staged, destination)
    except Exception:
        if prior_moved and not destination.exists() and backup.exists():
            os.replace(backup, destination)
        raise
    if prior_moved:
        shutil.rmtree(backup)


def _build_staged_dashboard(staged_output, destination, tmpl_path):
    data = _load_v9_data(output_dir=staged_output)
    out_data = staged_output / "data_v9.json"
    with open(out_data, "w") as f:
        json.dump(data, f, separators=(",", ":"))

    with open(tmpl_path) as f:
        html = f.read()
    html = _normalize_v9_template(html)

    # 1. Embed the data while retaining data_v9.json for inspection. Schema-2
    # sidecars still require HTTP because browsers block file:// fetches.
    html = _embed_dashboard_data(html, data)

    # 2. Replace the fetch block in IIFE
    iife_cleanup = re.search(
        r'\(async function\(\)\{.*?if\(!D\)\s*return;\s*\n',
        html, re.DOTALL
    )
    if iife_cleanup:
        html = html[:iife_cleanup.start()] + "(async function(){\n" + html[iife_cleanup.end():]
    else:
        # Fallback
        old_iife_body = re.search(
            r'\(async function\(\)\{.*?const D = DATA \|\| await fetch.*?\n',
            html, re.DOTALL
        )
        if old_iife_body:
            html = html.replace(old_iife_body.group(0), "(async function(){\n")

    # 3. Inject the V9 Results tab
    sys.path.insert(0, HERE)
    from v9_dashboard_ui import (
        V9_RESULTS_CSS,
        V9_RESULTS_JS,
        V9_RESULTS_NAV_BTN,
        V9_RESULTS_SECTION,
        UNSUP_AD_NAV_BTN,
        UNSUP_AD_SECTION,
        UNSUP_AD_JS,
        UNSUP_AD_CSS,
        UNSUP_AD_VIEW_MODEL_JS,
        UNSUP_AD_CHART_JS,
    )
    from v9_recovery_explainer_ui import (
        V9_RECOVERY_EXPLAINER_CSS,
        V9_RECOVERY_EXPLAINER_JS,
    )
    from v9_gnn_architecture_ui import (
        GNN_ARCHITECTURE_VIEW_MODEL_JS,
        GNN_ARCHITECTURE_UI_JS,
        GNN_ARCHITECTURE_CSS,
    )

    html = _inject_v9_nav_and_sections(
        html,
        V9_RESULTS_NAV_BTN + '    ' + UNSUP_AD_NAV_BTN,
        V9_RESULTS_SECTION + UNSUP_AD_SECTION,
    )
    html = _inject_recovery_assets(
        html,
        V9_RECOVERY_EXPLAINER_CSS,
        V9_RECOVERY_EXPLAINER_JS,
    )
    html = _inject_dashboard_tab_scripts(
        html,
        GNN_ARCHITECTURE_VIEW_MODEL_JS + GNN_ARCHITECTURE_UI_JS + "\n"
        + UNSUP_AD_VIEW_MODEL_JS + UNSUP_AD_CHART_JS,
        V9_RESULTS_JS + UNSUP_AD_JS,
    )
    html = _validate_recovery_explorer_mount(html)
    html = html.replace(
        "</style>",
        V9_RESULTS_CSS + "\n" + GNN_ARCHITECTURE_CSS + "\n"
        + UNSUP_AD_CSS + "\n</style>",
        1,
    )

    # 3b. Design system layer. Appended after every other stylesheet so it wins
    # the cascade, which is the only durable seam: the base sheet lives in the
    # generated, gitignored template and is rewritten on each build.
    from v9_design_system import (
        build_design_system_css,
        inject_provenance,
        provenance_from_meta,
        strip_google_fonts_import,
    )

    html = strip_google_fonts_import(html)
    html = html.replace("</style>", build_design_system_css() + "\n</style>", 1)
    html = inject_provenance(html, provenance_from_meta(data.get("meta")))

    html = _make_d3_optional(html)

    # 4. Remove Entity Resolution if present
    html = html.replace('  <button data-tab="entityResolution">Entity Resolution</button>\n', '')
    html = html.replace('  <section id="tab-entityResolution" class="tab-content"></section>\n', '')

    # 4b. Group the tab bar into accessible, hash-routed navigation.
    html = _apply_grouped_accessible_nav(html)

    # 5. Update titles
    html = re.sub(r"<title>[^<]*</title>", "<title>CBP Graph Corpus Explorer - V9</title>", html, count=1)
    html = re.sub(r"<h1>[^<]*</h1>", "<h1>CBP Graph Corpus Explorer &middot; V9</h1>", html, count=1)

    # 5. DATA is already embedded above; no local fetch is needed.
    out_html = staged_output / "index.html"
    with open(out_html, "w") as f:
        f.write(html)
    _publish_staged_dashboard(staged_output, destination)
    final_data = destination / "data_v9.json"
    final_html = destination / "index.html"
    p(f"[v9-dashboard] wrote {final_data} ({os.path.getsize(final_data)/1e6:.2f} MB)")
    p(f"[v9-dashboard] wrote {final_html} ({os.path.getsize(final_html)/1e6:.2f} MB)")
    p("[v9-dashboard] run: python -m http.server 8000 --directory Documents/Data/v9_dashboard")
    p("[v9-dashboard] then open http://localhost:8000/index.html")


def main():
    tmpl_path = os.path.join(V9_CORPUS, "dashboard_standalone.html")
    if not os.path.exists(tmpl_path):
        p(f"[v9-dashboard] ERROR: {tmpl_path} not found.")
        sys.exit(1)

    destination = Path(OUT_DIR)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged_output = Path(tempfile.mkdtemp(
        prefix=f".{destination.name}.stage-", dir=destination.parent
    ))
    try:
        _build_staged_dashboard(staged_output, destination, tmpl_path)
    except Exception:
        if staged_output.exists():
            shutil.rmtree(staged_output)
        raise


if __name__ == "__main__":
    main()
