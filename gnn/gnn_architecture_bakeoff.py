"""Standalone, GNN-only comparison of all registered V9 architectures.

The module deliberately shares only the leak-safe preparation and GNN scoring
primitives with :mod:`gnn.run_demo`.  It does not run the demo entry point or
construct any tabular, hybrid, checkpoint, bootstrap, or observability output.
"""

from __future__ import annotations

import argparse
import math
import numbers
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import pandas as pd

from gnn import config as FC
import gnn.run_demo as _rd
from gnn.graphmodel_rgcn import (
    REL_PLATE,
    NUM_REL_PLATE,
    build_person_graph_typed,
    caught_feature_names,
)
from gnn.learned_cell import build_caught_times, validate_pool_identities


# These aliases are intentional: tests and downstream callers can replace a
# preparation primitive without importing or executing the full demo workflow.
GNN_ARMS = _rd.GNN_ARMS
STRATA = _rd.STRATA
KS = _rd.KS
DAILY_KS = _rd.DAILY_KS
SUBSTRATE = _rd.SUBSTRATE
_atomic_json_write = _rd._atomic_json_write
_split_label_cutoffs = _rd._split_label_cutoffs
_build_oracle = _rd._build_oracle
load_pool = _rd.load_pool
stratum_for_pool = _rd.stratum_for_pool
_train_pool_and_labels = _rd._train_pool_and_labels
_gnn_scores = _rd._gnn_scores


DEFAULT_SEEDS = (0, 1, 2)
DEFAULT_EPOCHS = 18
DEFAULT_TRAIN_BUCKET = "Q"
DEFAULT_CORPUS = FC.DEFAULT_CORPUS_DIR
DEFAULT_OUTPUT = FC.RESULTS / "gnn_architecture_comparison_v9.json"


def _unique_ints(values, name: str, *, minimum: int) -> tuple[int, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a sequence of integers")
    try:
        items = tuple(values)
    except TypeError as exc:
        raise ValueError(f"{name} must be a sequence of integers") from exc
    if not items:
        raise ValueError(f"{name} must not be empty")
    if any(isinstance(value, bool) or not isinstance(value, numbers.Integral)
           for value in items):
        raise ValueError(f"{name} must contain integers")
    items = tuple(int(value) for value in items)
    if any(value < minimum for value in items):
        qualifier = "non-negative" if minimum == 0 else "positive"
        raise ValueError(f"{name} must contain {qualifier} integers")
    if len(set(items)) != len(items):
        raise ValueError(f"{name} must not contain duplicate integers")
    return items


def _positive_unique(values, name: str) -> tuple[int, ...]:
    return _unique_ints(values, name, minimum=1)


def _nonnegative_unique(values, name: str) -> tuple[int, ...]:
    return _unique_ints(values, name, minimum=0)


def _positive_int_arg(value: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


class _PositiveUniqueAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        try:
            checked = _positive_unique(values, self.dest)
        except ValueError as exc:
            raise argparse.ArgumentError(self, str(exc)) from exc
        setattr(namespace, self.dest, list(checked))


class _NonnegativeUniqueAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        try:
            checked = _nonnegative_unique(values, self.dest)
        except ValueError as exc:
            raise argparse.ArgumentError(self, str(exc)) from exc
        setattr(namespace, self.dest, list(checked))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the GNN-only architecture bake-off."
    )
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--seeds", nargs="+", type=int, action=_NonnegativeUniqueAction,
        default=list(DEFAULT_SEEDS),
    )
    parser.add_argument("--epochs", type=_positive_int_arg, default=DEFAULT_EPOCHS)
    parser.add_argument("--train-bucket", default=DEFAULT_TRAIN_BUCKET)
    parser.add_argument(
        "--ks", nargs="+", type=int, action=_PositiveUniqueAction,
        default=list(KS),
    )
    parser.add_argument(
        "--daily-ks", nargs="+", type=int, action=_PositiveUniqueAction,
        default=list(DAILY_KS),
    )
    return parser


def _as_score_array(scores, expected: int, *, context: str) -> np.ndarray:
    try:
        array = np.asarray(scores, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} scores must be numeric") from exc
    if array.ndim != 1 or len(array) != expected:
        raise ValueError(
            f"{context} scores must be a 1-D array of length {expected}"
        )
    if not np.isfinite(array).all():
        raise ValueError(f"{context} scores must be finite")
    return array


def _bundle_seed_scores(bundle, seeds: tuple[int, ...], pool_size: int):
    """Extract the test-pool score (pool index zero) for each seed."""
    scores_by_seed = getattr(bundle, "scores_by_seed", None)
    if not isinstance(scores_by_seed, Mapping):
        raise ValueError("_gnn_scores must return a score bundle with scores_by_seed")
    result = {}
    for seed in seeds:
        if seed not in scores_by_seed:
            raise ValueError(f"GNN score bundle is missing seed {seed}")
        seed_scores = scores_by_seed[seed]
        try:
            scores = seed_scores[0]
        except (IndexError, KeyError, TypeError) as exc:
            raise ValueError(f"GNN score bundle has no test scores for seed {seed}") from exc
        result[seed] = _as_score_array(scores, pool_size, context=f"seed {seed}")
    return result


def _metric_bundle(pool, scores, hidden, strata, ks, daily_ks):
    tied = _rd.add_tiebreak(scores, pool)
    frame = pool.copy()
    frame["_bakeoff_score"] = tied
    overall = _rd._add_f1_at_k(
        _rd.evaluate(frame, "_bakeoff_score", ks=ks), ks=ks
    )
    stratified = _rd.stratum_metrics(tied, pool, hidden, strata, ks=ks)
    daily = _rd.evaluate_daily(pool, tied, daily_ks=daily_ks)
    return {"overall": overall, "stratified": stratified, "daily": daily}, tied


def _build_architecture_row(spec, pool, hidden, strata, seed_scores, ks, daily_ks):
    seeds = tuple(seed_scores)
    arrays = [seed_scores[seed] for seed in seeds]
    ensemble_raw = np.mean(np.column_stack(arrays), axis=1)
    ensemble, _ = _metric_bundle(
        pool, ensemble_raw, hidden, strata, ks, daily_ks
    )
    per_seed = {}
    for seed in seeds:
        metrics, _ = _metric_bundle(
            pool, seed_scores[seed], hidden, strata, ks, ()
        )
        # Per-seed records intentionally contain global-depth metrics only.
        per_seed[str(seed)] = {
            "overall": metrics["overall"],
            "stratified": metrics["stratified"],
        }
    return {
        "label": str(spec["label"]),
        "looks_for": str(spec["looks_for"]),
        "num_relations": int(spec["num_rel"]),
        "ensemble": ensemble,
        "per_seed": per_seed,
    }


def run_bakeoff(
    corpus_dir=None,
    *,
    output=DEFAULT_OUTPUT,
    seeds=DEFAULT_SEEDS,
    epochs=DEFAULT_EPOCHS,
    train_bucket=DEFAULT_TRAIN_BUCKET,
    ks=KS,
    daily_ks=DAILY_KS,
):
    """Run every registered GNN architecture and atomically publish one artifact."""
    seeds = _nonnegative_unique(seeds, "seeds")
    ks = _positive_unique(ks, "ks")
    daily_ks = _positive_unique(daily_ks, "daily_ks")
    if isinstance(epochs, bool) or not isinstance(epochs, numbers.Integral) or epochs <= 0:
        raise ValueError("epochs must be a positive integer")
    epochs = int(epochs)
    if not isinstance(train_bucket, str) or not train_bucket.strip():
        raise ValueError("train_bucket must be a non-empty string")

    cd = Path(corpus_dir or DEFAULT_CORPUS)
    train_cutoff, _test_cutoff = _split_label_cutoffs(cd)
    obs2id = _build_oracle(cd)
    pool = load_pool(cd, split="test")
    strata = stratum_for_pool(pool, cd)
    train_pool, train_labels = _train_pool_and_labels(cd, train_cutoff)
    edges_typed, node_ids, node_feat = build_person_graph_typed(
        cd, substrate=SUBSTRATE, include_plate=True
    )
    caught_time = build_caught_times(cd, obs2id)
    node_index = {person_id: index for index, person_id in enumerate(node_ids)}
    validate_pool_identities(
        train_pool, obs2id, node_index, pool_name="training pool"
    )
    validate_pool_identities(pool, obs2id, node_index, pool_name="test pool")

    hidden = pool["hidden"].to_numpy(dtype=bool)
    architecture_order = tuple(GNN_ARMS)
    architecture_rows = {}
    for name in architecture_order:
        spec = GNN_ARMS[name]
        try:
            bundle = _gnn_scores(
                edges_typed,
                node_ids,
                node_feat,
                caught_time,
                train_pool,
                train_labels,
                [pool],
                obs2id,
                seeds=seeds,
                epochs=epochs,
                train_bucket=train_bucket,
                train_cutoff=train_cutoff,
                model_cls=spec["cls"],
                num_rel=spec["num_rel"],
            )
            seed_scores = _bundle_seed_scores(bundle, seeds, len(pool))
            architecture_rows[name] = _build_architecture_row(
                spec, pool, hidden, strata, seed_scores, ks, daily_ks
            )
        except Exception as exc:
            raise RuntimeError(f"architecture {name!r} failed") from exc

    stratum_hidden = {
        stratum: int(((strata == stratum).to_numpy() & hidden).sum())
        for stratum in STRATA
    }
    feature_schema = list(caught_feature_names(NUM_REL_PLATE))
    relation_schema = {str(name): int(value) for name, value in REL_PLATE.items()}
    payload = {
        "schema_version": 1,
        "artifact_kind": "gnn_architecture_comparison",
        "corpus": str(cd.name),
        "corpus_identity": str(cd.resolve()),
        "substrate": SUBSTRATE,
        "seeds": list(seeds),
        "epochs": epochs,
        "train_bucket": train_bucket,
        "ks": list(ks),
        "daily_ks": list(daily_ks),
        "pool_size": int(len(pool)),
        "hidden_total": int(hidden.sum()),
        "stratum_hidden": stratum_hidden,
        "feature_schema": feature_schema,
        "relation_schema": relation_schema,
        "architecture_order": list(architecture_order),
        "architectures": architecture_rows,
    }
    validate_artifact(payload)
    _atomic_json_write(Path(output), payload)
    return payload


_FORBIDDEN_KEY_TOKENS = (
    "baseline", "hybrid", "fusion", "checkpoint", "observability",
    "event_scores", "model_weights", "weights", "model",
)


def _walk_numbers(value, path="artifact"):
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).lower()
            if any(token in key_text for token in _FORBIDDEN_KEY_TOKENS):
                raise ValueError(f"forbidden baseline/hybrid field at {path}.{key}")
            _walk_numbers(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _walk_numbers(item, f"{path}[{index}]")
    elif isinstance(value, numbers.Number):
        if isinstance(value, (bool, np.bool_)):
            raise ValueError(f"boolean is not a numeric metric at {path}")
        try:
            finite = math.isfinite(float(value))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"metric at {path} must be finite numeric") from exc
        if not finite:
            raise ValueError(f"metric at {path} must be finite numeric")


def _mapping(value, path):
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be an object")
    return value


def _exact_keys(mapping, expected, path):
    actual = set(mapping)
    expected = set(expected)
    describe = lambda keys: sorted((type(key).__name__, repr(key)) for key in keys)
    missing = describe(expected.difference(actual))
    unexpected = describe(actual.difference(expected))
    if missing or unexpected:
        raise ValueError(
            f"{path} has invalid fields; missing={missing}, unexpected={unexpected}"
        )


def _integer(value, path, *, minimum=0):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Integral):
        raise ValueError(f"{path} must be an integer")
    value = int(value)
    if value < minimum:
        raise ValueError(f"{path} must be >= {minimum}")
    return value


def _metric_number(metrics, key, path):
    if key not in metrics:
        raise ValueError(f"missing required metric {path}.{key}")
    value = metrics[key]
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Number):
        raise ValueError(f"{path}.{key} must be numeric")
    if not math.isfinite(float(value)):
        raise ValueError(f"{path}.{key} must be finite")
    return float(value)


def _validate_global_metrics(metrics, ks, *, hidden_total, pool_size, path):
    metrics = _mapping(metrics, path)
    expected_keys = {
        metric
        for k in ks
        for metric in (f"found@{k}", f"precision@{k}", f"recall@{k}", f"f1@{k}")
    }
    _exact_keys(metrics, expected_keys, path)
    found_by_k = {}
    for k in ks:
        found = _integer(metrics.get(f"found@{k}"), f"{path}.found@{k}")
        if found > min(k, pool_size, hidden_total):
            raise ValueError(f"{path}.found@{k} exceeds pool capacity")
        precision = _metric_number(metrics, f"precision@{k}", path)
        recall = _metric_number(metrics, f"recall@{k}", path)
        f1 = _metric_number(metrics, f"f1@{k}", path)
        exact_precision = found / k
        exact_recall = found / hidden_total if hidden_total else 0.0
        expected_precision = round(exact_precision, 4)
        expected_recall = round(exact_recall, 4)
        expected_f1 = round(
            2 * expected_precision * expected_recall
            / (expected_precision + expected_recall), 4
        ) if expected_precision + expected_recall else 0.0
        if precision != expected_precision or recall != expected_recall or f1 != expected_f1:
            raise ValueError(f"inconsistent global metrics at {path} for K={k}")
        found_by_k[k] = found
    return found_by_k


def _validate_stratified_metrics(metrics, ks, *, stratum_hidden, path):
    metrics = _mapping(metrics, path)
    _exact_keys(metrics, STRATA, path)
    expected_row_keys = {
        "hidden",
        *(metric for k in ks for metric in (f"found@{k}", f"recall@{k}")),
    }
    found_by_k = {k: 0 for k in ks}
    for stratum in STRATA:
        row = _mapping(metrics[stratum], f"{path}.{stratum}")
        _exact_keys(row, expected_row_keys, f"{path}.{stratum}")
        denominator = _integer(row.get("hidden"), f"{path}.{stratum}.hidden")
        if denominator != stratum_hidden[stratum]:
            raise ValueError(f"{path}.{stratum}.hidden disagrees with stratum_hidden")
        for k in ks:
            found = _integer(row.get(f"found@{k}"), f"{path}.{stratum}.found@{k}")
            if found > denominator:
                raise ValueError(f"{path}.{stratum}.found@{k} exceeds denominator")
            recall = _metric_number(row, f"recall@{k}", f"{path}.{stratum}")
            expected = round(found / denominator, 4) if denominator else 0.0
            if recall != expected:
                raise ValueError(f"inconsistent stratified recall at {path}.{stratum} for K={k}")
            found_by_k[k] += found
    return found_by_k


def _validate_daily_metrics(metrics, daily_ks, *, hidden_total, pool_size, path):
    metrics = _mapping(metrics, path)
    expected_keys = {"n_days"}
    expected_keys.update(
        metric for k in daily_ks for metric in (
            f"daily_found@{k}", f"daily_found_by_day@{k}",
            f"daily_recall@{k}", f"daily_precision@{k}",
            f"daily_f1@{k}", f"daily_budget@{k}",
        )
    )
    _exact_keys(metrics, expected_keys, path)
    n_days = _integer(metrics.get("n_days"), f"{path}.n_days")
    if n_days > pool_size:
        raise ValueError(f"{path}.n_days exceeds pool_size")
    for k in daily_ks:
        found = _integer(metrics.get(f"daily_found@{k}"), f"{path}.daily_found@{k}")
        budget = _integer(metrics.get(f"daily_budget@{k}"), f"{path}.daily_budget@{k}")
        if found > budget or found > hidden_total or budget > pool_size or budget > k * n_days:
            raise ValueError(f"invalid daily denominator at {path} for K={k}")
        precision = _metric_number(metrics, f"daily_precision@{k}", path)
        recall = _metric_number(metrics, f"daily_recall@{k}", path)
        f1 = _metric_number(metrics, f"daily_f1@{k}", path)
        exact_precision = found / budget if budget else 0.0
        exact_recall = found / hidden_total if hidden_total else 0.0
        expected_precision = round(exact_precision, 4)
        expected_recall = round(exact_recall, 4)
        expected_f1 = round(
            2 * exact_precision * exact_recall
            / (exact_precision + exact_recall), 4
        ) if exact_precision + exact_recall else 0.0
        if precision != expected_precision or recall != expected_recall or f1 != expected_f1:
            raise ValueError(f"inconsistent daily metrics at {path} for K={k}")
        key = f"daily_found_by_day@{k}"
        rows = metrics.get(key)
        if not isinstance(rows, list) or len(rows) != n_days:
            raise ValueError(f"{path}.{key} must list one row per day")
        by_day_total = 0
        dates = set()
        for index, row in enumerate(rows):
            row_path = f"{path}.{key}[{index}]"
            row = _mapping(row, row_path)
            _exact_keys(row, {"date", "found"}, row_path)
            if not isinstance(row["date"], str) or not row["date"]:
                raise ValueError(f"{row_path}.date must be a non-empty string")
            if row["date"] in dates:
                raise ValueError(f"{path}.{key} contains duplicate dates")
            dates.add(row["date"])
            day_found = _integer(row["found"], f"{row_path}.found")
            if day_found > k:
                raise ValueError(f"{row_path}.found exceeds daily quota")
            by_day_total += day_found
        if by_day_total != found:
            raise ValueError(f"{path}.{key} found values must sum to daily_found@{k}")


def validate_artifact(payload):
    """Strictly validate a completed architecture-only artifact."""
    payload = _mapping(payload, "artifact")
    _walk_numbers(payload)
    required = {
        "schema_version", "artifact_kind", "corpus", "corpus_identity",
        "substrate", "seeds", "epochs", "train_bucket", "ks", "daily_ks",
        "pool_size", "hidden_total", "stratum_hidden", "feature_schema",
        "relation_schema", "architecture_order", "architectures",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"artifact missing required fields: {missing}")
    unexpected = sorted(
        (type(key).__name__, repr(key))
        for key in set(payload).difference(required)
    )
    if unexpected:
        raise ValueError(f"artifact has unexpected top-level fields: {unexpected}")
    if payload["schema_version"] != 1:
        raise ValueError("schema_version must be 1")
    if payload["artifact_kind"] != "gnn_architecture_comparison":
        raise ValueError("artifact_kind must be gnn_architecture_comparison")
    for field in ("corpus", "corpus_identity", "substrate", "train_bucket"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if payload["substrate"] != SUBSTRATE:
        raise ValueError("substrate does not match SUBSTRATE")
    identity = payload["corpus_identity"]
    if not Path(identity).is_absolute() or str(Path(identity).resolve()) != identity:
        raise ValueError("corpus_identity must be an absolute normalized resolved path")
    seeds = _nonnegative_unique(payload["seeds"], "seeds")
    epochs = _integer(payload["epochs"], "epochs", minimum=1)
    del epochs
    ks = _positive_unique(payload["ks"], "ks")
    daily_ks = _positive_unique(payload["daily_ks"], "daily_ks")
    pool_size = _integer(payload["pool_size"], "pool_size")
    hidden_total = _integer(payload["hidden_total"], "hidden_total")
    if hidden_total > pool_size:
        raise ValueError("hidden_total cannot exceed pool_size")

    stratum_hidden = _mapping(payload["stratum_hidden"], "stratum_hidden")
    _exact_keys(stratum_hidden, STRATA, "stratum_hidden")
    stratum_hidden = {
        stratum: _integer(stratum_hidden[stratum], f"stratum_hidden.{stratum}")
        for stratum in STRATA
    }
    if sum(stratum_hidden.values()) != hidden_total:
        raise ValueError("stratum_hidden denominators must sum to hidden_total")
    expected_features = list(caught_feature_names(NUM_REL_PLATE))
    if payload["feature_schema"] != expected_features:
        raise ValueError("feature_schema does not match caught_feature_names")
    if not isinstance(payload["feature_schema"], list) or not all(
        isinstance(name, str) and name for name in payload["feature_schema"]
    ):
        raise ValueError("feature_schema must be a non-empty list of names")
    relation_schema = _mapping(payload["relation_schema"], "relation_schema")
    expected_relations = {str(name): int(value) for name, value in REL_PLATE.items()}
    if dict(relation_schema) != expected_relations:
        raise ValueError("relation_schema does not match REL_PLATE")
    relation_ids = []
    for name, relation in relation_schema.items():
        if not isinstance(name, str) or not name:
            raise ValueError("relation_schema names must be non-empty strings")
        relation_ids.append(_integer(relation, f"relation_schema.{name}"))
    if sorted(relation_ids) != list(range(len(relation_ids))):
        raise ValueError("relation_schema relation IDs must be contiguous from zero")

    expected_order = list(GNN_ARMS)
    if payload["architecture_order"] != expected_order:
        raise ValueError("architecture_order must exactly match the registered architecture registry")
    architectures = _mapping(payload["architectures"], "architectures")
    if list(architectures) != expected_order or set(architectures) != set(expected_order):
        raise ValueError("architectures must contain the complete registry in order")
    for name in expected_order:
        row = _mapping(architectures[name], f"architectures.{name}")
        _exact_keys(
            row,
            {"label", "looks_for", "num_relations", "ensemble", "per_seed"},
            f"architectures.{name}",
        )
        spec = GNN_ARMS[name]
        for field in ("label", "looks_for"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"architectures.{name}.{field} must be a non-empty string")
            if row[field] != str(spec[field]):
                raise ValueError(f"architectures.{name}.{field} does not match registry")
        num_relations = _integer(row.get("num_relations"), f"architectures.{name}.num_relations", minimum=1)
        if num_relations != int(spec["num_rel"]) or num_relations != len(relation_schema):
            raise ValueError(f"architectures.{name}.num_relations does not match registry")
        ensemble = _mapping(row.get("ensemble"), f"architectures.{name}.ensemble")
        _exact_keys(ensemble, {"overall", "stratified", "daily"}, f"architectures.{name}.ensemble")
        overall_found = _validate_global_metrics(
            ensemble.get("overall"), ks, hidden_total=hidden_total,
            pool_size=pool_size, path=f"architectures.{name}.ensemble.overall",
        )
        stratified_found = _validate_stratified_metrics(
            ensemble.get("stratified"), ks, stratum_hidden=stratum_hidden,
            path=f"architectures.{name}.ensemble.stratified",
        )
        if overall_found != stratified_found:
            raise ValueError(f"architectures.{name}.ensemble found counts do not partition by stratum")
        _validate_daily_metrics(
            ensemble.get("daily"), daily_ks, hidden_total=hidden_total,
            pool_size=pool_size, path=f"architectures.{name}.ensemble.daily",
        )
        per_seed = _mapping(row.get("per_seed"), f"architectures.{name}.per_seed")
        if set(per_seed) != {str(seed) for seed in seeds}:
            raise ValueError(f"architectures.{name}.per_seed keys must match seeds exactly")
        for seed in seeds:
            seed_row = _mapping(per_seed[str(seed)], f"architectures.{name}.per_seed.{seed}")
            _exact_keys(seed_row, {"overall", "stratified"}, f"architectures.{name}.per_seed.{seed}")
            seed_overall_found = _validate_global_metrics(
                seed_row.get("overall"), ks, hidden_total=hidden_total,
                pool_size=pool_size, path=f"architectures.{name}.per_seed.{seed}.overall",
            )
            seed_stratified_found = _validate_stratified_metrics(
                seed_row.get("stratified"), ks, stratum_hidden=stratum_hidden,
                path=f"architectures.{name}.per_seed.{seed}.stratified",
            )
            if seed_overall_found != seed_stratified_found:
                raise ValueError(f"architectures.{name}.per_seed.{seed} found counts do not partition by stratum")
    return True


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = run_bakeoff(
            corpus_dir=args.corpus,
            output=args.output,
            seeds=args.seeds,
            epochs=args.epochs,
            train_bucket=args.train_bucket,
            ks=args.ks,
            daily_ks=args.daily_ks,
        )
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    path = Path(args.output)
    print(
        f"wrote {path} | architectures={payload['architecture_order']} "
        f"seeds={payload['seeds']} epochs={payload['epochs']} "
        f"train_bucket={payload['train_bucket']}"
    )
    return payload


if __name__ == "__main__":
    main()
