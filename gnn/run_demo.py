"""V9 positive-control demo: a realistic tabular baseline versus a three-seed
GraphSAGE caught-propagation arm over {COTRAVEL, RESIDENCE, SHARED_PLATE,
SHARED_PLATE_HOT}. Same
pool, same substrate (oracle identity — ER is NOT the question here and both arms
share it, so the comparison is fair), leak-free; paired-event bootstrap for
significance. The default is a three-seed GraphSAGE run with seeds ``(0, 1, 2)``
on the Git-LFS-backed canonical V9 corpus. Hybrid scores are rank-normalized and
combined with baseline scores by validation-tuned convex late rank fusion. The
deployable fusion weight is tuned only on caught labels available to deployment;
hidden labels tune only the explicitly non-deployable oracle ceiling:

    python -m gnn.run_demo

Set CBP_CORPUS_DIR to override the default corpus path.
"""
from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass
from functools import partial
import json
from pathlib import Path
import re
from types import MappingProxyType

import numpy as np
import pandas as pd

from gnn import config as FC

STRATA = ("observable", "dark", "lone")

def evaluate(df, score_col, ks):
    """Evaluate ranked scores at configured operational depths.

    ``df`` must contain aligned ``hidden`` targets and the named ``score_col``;
    ``ks`` supplies positive ranking depths.  The return value maps each depth
    to integer found counts and rounded precision/recall, using stable
    descending score order.  This is a pure retrospective metric helper with no
    writes; callers must pass frozen deployable scores and keep the synthetic
    hidden target outside feature, threshold, and weight selection.
    """
    hidden = df["hidden"].values
    scores = df[score_col].values
    order = np.argsort(-scores, kind="mergesort")
    denom = int(hidden.sum())
    out = {}
    for k in ks:
        f = int(hidden[order[:k]].sum())
        out[f"found@{k}"] = f
        out[f"precision@{k}"] = round(f / k, 4)
        out[f"recall@{k}"] = round(f / denom, 4) if denom else 0.0
    return out


def evaluate_daily(pool, scores, daily_ks):
    """Capacity-aware view: instead of one global budget over the whole test
    window, give each calendar day its own top-`k` inspection budget, rank that
    day's crossings by score, and sum the missed carriers caught across all days.
    `daily_found@k` = carriers surfaced with k inspections/day; `total_budget@k`
    = k * n_days total inspections spent (so precision = found / budget)."""
    df = pool[["t", "hidden"]].copy()
    df["_s"] = np.asarray(scores)
    df["_day"] = pd.to_datetime(df["t"], utc=True, errors="coerce").dt.floor("D")
    denom = int(df["hidden"].sum())
    n_days = int(df["_day"].nunique())
    ranked = df.sort_values(["_day", "_s"], ascending=[True, False], kind="mergesort")
    ranked["_day_rank"] = ranked.groupby("_day", sort=False).cumcount()
    out = {"n_days": n_days}
    for k in daily_ks:
        topk = ranked[ranked["_day_rank"] < k]
        f = int(topk["hidden"].sum())
        budget = int(topk.shape[0])
        found_by_day = topk.groupby("_day", sort=True)["hidden"].sum()
        precision = f / budget if budget else 0.0
        recall = f / denom if denom else 0.0
        out[f"daily_found@{k}"] = f
        out[f"daily_found_by_day@{k}"] = [
            {"date": pd.Timestamp(day).date().isoformat(),
             "found": int(found_by_day.get(day, 0))}
            for day in sorted(ranked["_day"].dropna().unique())
        ]
        out[f"daily_recall@{k}"] = round(recall, 4)
        out[f"daily_precision@{k}"] = round(precision, 4)
        out[f"daily_f1@{k}"] = round(
            2 * precision * recall / (precision + recall), 4
        ) if precision + recall else 0.0
        out[f"daily_budget@{k}"] = budget  # actual inspections (< k*days on thin days)
    return out


def evaluate_daily_simulated_catches(
    pool, scores_by_arm, daily_ks, official_caught_times
):
    """Evaluate daily quotas after successful hidden-person inspections.

    Official catches remove rows only when their label was available before the
    UTC scoring-day start. Simulated catches are maintained independently for
    each arm/budget and remove that person's rows beginning on the next day.
    Scores remain fixed; simulated catches never feed back into graph features.
    """
    required = {"t", "hidden", "primary_person_id"}
    missing = required.difference(pool.columns)
    if missing:
        raise ValueError(f"pool is missing required columns: {sorted(missing)}")

    df = pool[["t", "hidden", "primary_person_id"]].copy().reset_index(drop=True)
    df["_day"] = pd.to_datetime(df["t"], utc=True, errors="coerce").dt.floor("D")
    if df["_day"].isna().any():
        raise ValueError("pool.t must contain valid timestamps")
    if df["primary_person_id"].isna().any():
        raise ValueError("pool.primary_person_id must contain canonical identities")
    df["hidden"] = df["hidden"].fillna(False).astype(bool)
    df["_row_order"] = np.arange(len(df))
    df["_official_caught_time"] = pd.to_datetime(
        df["primary_person_id"].map(official_caught_times),
        utc=True,
        errors="coerce",
    )
    df["_official_eligible"] = (
        df["_official_caught_time"].isna()
        | (df["_official_caught_time"] >= df["_day"])
    )

    eligible = df["_official_eligible"]
    excluded = ~eligible
    initial_hidden = eligible & df["hidden"]
    excluded_hidden = excluded & df["hidden"]
    initial_pool = {
        "candidate_events": int(eligible.sum()),
        "hidden_events": int(initial_hidden.sum()),
        "hidden_people": int(df.loc[initial_hidden, "primary_person_id"].nunique()),
        "excluded_events": int(excluded.sum()),
        "excluded_people": int(df.loc[excluded, "primary_person_id"].nunique()),
        "excluded_hidden_events": int(excluded_hidden.sum()),
        "excluded_hidden_people": int(
            df.loc[excluded_hidden, "primary_person_id"].nunique()
        ),
    }
    hidden_people_denom = initial_pool["hidden_people"]
    days = sorted(df["_day"].unique())
    arms = {}

    for arm_name, scores in scores_by_arm.items():
        scores = np.asarray(scores, dtype=float)
        if len(scores) != len(df):
            raise ValueError(
                f"scores for {arm_name!r} have length {len(scores)}; expected {len(df)}"
            )
        arm_df = df.assign(_score=scores)
        arm_metrics = {}

        for k in daily_ks:
            k = int(k)
            if k <= 0:
                raise ValueError("daily inspection budgets must be positive")
            simulated_caught = set()
            inspected_events = 0
            later_candidate_events_removed = 0
            later_hidden_events_removed = 0
            found_by_day = []

            for day in days:
                day_rows = arm_df[
                    (arm_df["_day"] == day) & arm_df["_official_eligible"]
                ]
                removed = day_rows["primary_person_id"].isin(simulated_caught)
                later_candidate_events_removed += int(removed.sum())
                later_hidden_events_removed += int(
                    (removed & day_rows["hidden"]).sum()
                )
                ranked = day_rows.loc[~removed].sort_values(
                    ["_score", "_row_order"],
                    ascending=[False, True],
                    kind="mergesort",
                    na_position="last",
                )
                inspected = ranked.head(k)
                inspected_events += int(len(inspected))
                found_today = set(
                    inspected.loc[inspected["hidden"], "primary_person_id"]
                )
                found_by_day.append({
                    "date": pd.Timestamp(day).date().isoformat(),
                    "found": int(len(found_today)),
                })
                simulated_caught.update(found_today)

            people_found = len(simulated_caught)
            precision = people_found / inspected_events if inspected_events else 0.0
            recall = people_found / hidden_people_denom if hidden_people_denom else 0.0
            f1 = (
                2 * precision * recall / (precision + recall)
                if precision + recall else 0.0
            )
            arm_metrics.update({
                f"daily_people_found@{k}": int(people_found),
                f"daily_found_by_day@{k}": found_by_day,
                f"daily_budget@{k}": int(inspected_events),
                f"daily_precision@{k}": round(precision, 4),
                f"daily_recall@{k}": round(recall, 4),
                f"daily_f1@{k}": round(f1, 4),
                f"later_candidate_events_removed@{k}": int(
                    later_candidate_events_removed
                ),
                f"later_hidden_events_removed@{k}": int(later_hidden_events_removed),
            })
        arms[arm_name] = arm_metrics

    return {
        "policy": {
            "official_catch_time_field": "label_available_time_utc",
            "official_boundary": "strictly_before_utc_day_start",
            "simulated_feedback": "candidate_removal_only",
        },
        "initial_pool": initial_pool,
        "arms": arms,
    }


def add_tiebreak(scores, pool):
    """Add deterministic row-order jitter without changing rank meaningfully.

    ``scores`` is the one-dimensional score vector and ``pool`` is an unused
    compatibility context; the return value is a new floating array with a fixed
    seed's sub-nanounit jitter added in row order.  This breaks exact ties for
    stable ranking without materially changing score meaning or metrics, and it
    writes no artifact.  Callers must preserve score order and must not
    use the jitter as a feature or as a replacement for an explicit cutoff.
    """
    rng = np.random.default_rng(42)
    return np.array(scores, dtype=float) + rng.uniform(0, 1e-9, size=len(scores))

def load_pool(corpus_dir, split="test"):
    """Load a split-aligned event pool with oracle fields reserved for retrospective evaluation.

    ``corpus_dir`` selects the synthetic corpus and ``split`` selects one
    declared train/validation/test partition.  The returned DataFrame is in
    source row order with normalized UTC ``t`` and label-availability columns,
    canonical oracle identity/hidden fields for later metrics, and observed
    record IDs for deployable feature construction.  Ground-truth rows may be
    loaded early to align event IDs, but hidden outcomes and organization
    labels cannot affect feature construction, score generation, caught-label
    fusion, threshold selection, or blend-weight selection.  The function reads
    CSVs only.  Missing files or required columns propagate their file/pandas
    exceptions, while malformed event and label-availability timestamps are
    coerced to ``NaT``.
    """
    egt = pd.read_csv(corpus_dir / "event_ground_truth.csv", usecols=["event_id", "primary_person_id", "false_negative_flag"])
    splits = pd.read_csv(corpus_dir / "train_valid_test_splits.csv", usecols=["entity_id", "split"])
    ev = pd.read_csv(
        corpus_dir / "crossing_events.csv",
        usecols=[
            "event_id",
            "event_timestamp_utc",
            "observed_person_record_id",
            "label_available_time_utc",
        ],
    )
    df = egt.merge(splits, left_on="event_id", right_on="entity_id", how="inner").merge(ev, on="event_id", how="inner")
    te = df[df.split == split].copy()
    te["t"] = pd.to_datetime(te.event_timestamp_utc, utc=True, errors="coerce")
    te["label_available_time"] = pd.to_datetime(
        te.label_available_time_utc, utc=True, errors="coerce"
    )
    te = te.rename(columns={"observed_person_record_id": "primary_obs_id"})
    te["hidden"] = te["false_negative_flag"].fillna(False).astype(bool)
    return te.reset_index(drop=True)


def _label_available_before(pool, cutoff):
    """Mask rows whose official label exists strictly before cutoff."""
    cutoff = pd.Timestamp(cutoff)
    cutoff = (
        cutoff.tz_localize("UTC")
        if cutoff.tzinfo is None
        else cutoff.tz_convert("UTC")
    )
    available = pd.to_datetime(
        pool["label_available_time"], utc=True, errors="coerce"
    )
    return available.notna() & (available < cutoff)


def _split_label_cutoffs(corpus_dir):
    """Read train/test-start label cutoffs from the corpus split contract."""
    specs = pd.read_csv(
        corpus_dir / "train_valid_test_splits.csv",
        usecols=["temporal_cutoff"],
    )["temporal_cutoff"].dropna().astype(str).unique()
    if len(specs) != 1:
        raise ValueError("corpus must declare one temporal_cutoff contract")
    match = re.fullmatch(
        r"\s*train<([^;]+);\s*validation<([^;]+);\s*test>=([^;]+)\s*",
        specs[0],
    )
    if match is None:
        raise ValueError(f"unsupported temporal_cutoff contract: {specs[0]!r}")

    def as_utc(value):
        timestamp = pd.Timestamp(value.strip())
        return (
            timestamp.tz_localize("UTC")
            if timestamp.tzinfo is None
            else timestamp.tz_convert("UTC")
        )

    train_cutoff = as_utc(match.group(1))
    validation_cutoff = as_utc(match.group(2))
    test_cutoff = as_utc(match.group(3))
    if validation_cutoff != test_cutoff:
        raise ValueError("validation cutoff must equal the test deployment start")
    return train_cutoff, test_cutoff

def _build_oracle(corpus_dir):
    obs = pd.read_csv(corpus_dir / "observed_person_records.csv", usecols=["observed_person_record_id", "canonical_person_id"])
    return dict(zip(obs["observed_person_record_id"], obs["canonical_person_id"]))

def stratum_for_pool(pool, corpus_dir):
    """Assign retrospective graph-observability strata from synthetic ground truth.

    ``pool`` supplies event rows and may omit ``primary_person_id``; ``corpus_dir``
    supplies the synthetic event and organization truth used to label each row
    ``observable``, ``dark``, or ``lone``.  The return value is a Series aligned
    to the pool index.  These strata are evaluation annotations, not deployable
    features: oracle organization values may be materialized early for alignment,
    but are retained exclusively for retrospective metrics and never flow into
    deployable features, scores, caught-label fusion, threshold selection, or
    blend-weight selection.  Missing identity columns are recovered by event
    alignment; malformed joins surface as pandas errors, and no files are written.
    """
    if "primary_person_id" not in pool.columns:
        egt = pd.read_csv(corpus_dir / "event_ground_truth.csv", usecols=["event_id", "primary_person_id"])
        pool = pool.merge(egt, on="event_id", how="left")
    org = pd.read_csv(corpus_dir / "org_membership_ground_truth.csv", usecols=["person_id", "is_observable"])
    org["is_observable"] = org["is_observable"].astype(str).str.lower().eq("true")
    org_obs = org.groupby("person_id")["is_observable"].max().reset_index()
    pool = pool.merge(org_obs, left_on="primary_person_id", right_on="person_id", how="left")
    def get_stratum(row):
        if pd.isna(row["is_observable"]): return "lone"
        return "observable" if row["is_observable"] else "dark"
    return pool.apply(get_stratum, axis=1)


def paired_event_bootstrap(a, b, hidden, ks, mask=None, n_boot=2000, seed=0):
    """Bootstrap paired baseline and hybrid metrics over shared sampled events.

    ``a`` and ``b`` are aligned score vectors, ``hidden`` is the retrospective
    target vector, ``ks`` contains ranking depths, ``mask`` optionally restricts
    the target to one stratum, and ``n_boot``/``seed`` control resampling.  The
    return value maps ``found@k`` to mean, confidence interval, and one-sided
    comparison summaries.  Sampling is paired by shared row index and sized from
    ``hidden``, not from a pool object, and writes no artifacts; callers must pass
    frozen deployable scores and must keep hidden labels in this post-freeze
    evaluation path.
    """
    rng = np.random.default_rng(seed)
    n = len(hidden)
    diffs = {k: np.empty(n_boot) for k in ks}
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        ha = hidden[idx]
        ma = mask[idx] if mask is not None else None
        sa, sb = a[idx], b[idx]
        oa = np.argsort(-sa, kind="mergesort")
        ob = np.argsort(-sb, kind="mergesort")
        for k in ks:
            fa = (ha[oa[:k]] & ma[oa[:k]]).sum() if ma is not None else ha[oa[:k]].sum()
            fb = (ha[ob[:k]] & ma[ob[:k]]).sum() if ma is not None else ha[ob[:k]].sum()
            diffs[k][i] = fa - fb
    return {f"found@{k}": _diff_summary(diffs[k]) for k in ks}


def _daily_found_by_k(days, scores, hidden, daily_ks, mask=None):
    """Return daily-capacity found counts for one sampled event set."""
    data = {
        "_day": days,
        "_s": np.asarray(scores),
        "_hidden": np.asarray(hidden, dtype=bool),
    }
    if mask is not None:
        data["_mask"] = np.asarray(mask, dtype=bool)
    ranked = pd.DataFrame(data).sort_values(
        ["_day", "_s"], ascending=[True, False], kind="mergesort"
    )
    ranked["_day_rank"] = ranked.groupby("_day", sort=False).cumcount()
    selected_mask = np.ones(len(ranked), dtype=bool)
    if mask is not None:
        selected_mask &= ranked["_mask"].to_numpy()
    hidden_values = ranked["_hidden"].to_numpy()
    ranks = ranked["_day_rank"].to_numpy()
    return {
        k: int((hidden_values & selected_mask & (ranks < k)).sum())
        for k in daily_ks
    }


def paired_daily_bootstrap(a, b, pool, hidden, daily_ks, mask=None,
                           n_boot=2000, seed=0):
    """Paired bootstrap of hybrid-minus-baseline found counts at daily quotas."""
    rng = np.random.default_rng(seed)
    days = pd.to_datetime(pool["t"], utc=True, errors="coerce").dt.floor("D").to_numpy()
    hidden = np.asarray(hidden, dtype=bool)
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    mask = np.asarray(mask, dtype=bool) if mask is not None else None
    n = len(hidden)
    diffs = {k: np.empty(n_boot) for k in daily_ks}
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        sample_mask = mask[idx] if mask is not None else None
        fa = _daily_found_by_k(days[idx], a[idx], hidden[idx], daily_ks, sample_mask)
        fb = _daily_found_by_k(days[idx], b[idx], hidden[idx], daily_ks, sample_mask)
        for k in daily_ks:
            diffs[k][i] = fa[k] - fb[k]
    return {
        f"hybrid_vs_baseline_daily@{k}": _diff_summary(diffs[k])
        for k in daily_ks
    }

def _diff_summary(d):
    lo, hi = np.percentile(d, [2.5, 97.5])
    return {"mean_diff": round(float(np.mean(d)), 3),
            "ci": [round(float(lo), 2), round(float(hi), 2)],
            "p_enh_le_base": round(float(np.mean(d <= 0)), 4),
            "significant": bool(lo > 0)}

def stratum_metrics(scores, pool, hidden, strata_labels, ks):
    """Compute per-stratum ranking metrics for one score vector.

    ``scores`` and ``hidden`` are aligned arrays, ``pool`` is an unused
    compatibility parameter, ``strata_labels`` assigns each row to the three
    known strata, and ``ks`` supplies operational depths.  The return value maps
    each stratum to hidden denominators and found/recall counts at every depth.
    Computation is pure and writes no artifacts; hidden labels and synthetic
    strata are retrospective evaluation inputs and must never be fed back into
    score or threshold selection.
    """
    order = np.argsort(-scores, kind="mergesort")
    out = {}
    for st in STRATA:
        m = (strata_labels == st).values & hidden
        denom = int(m.sum())
        out[st] = {"hidden": denom}
        for k in ks:
            f = int((hidden[order[:k]] & m[order[:k]]).sum())
            out[st][f"found@{k}"] = f
            out[st][f"recall@{k}"] = round(f / denom, 4) if denom else 0.0
    return out

from gnn.graphmodel_rgcn import (
    build_person_graph_typed,
    NUM_REL_PLATE,
    _RGCN,
    REL_PLATE,
    caught_feature_names,
)
from gnn.graphmodel_alt import _SAGE, _GAT, _GIN, _KPIAA
from gnn.learned_cell import (
    build_caught_times,
    _eligible_training_supervision,
    _train_caught_rgcn,
    _score_pool,
    validate_pool_identities,
)
from scipy.stats import rankdata
from gnn.detector import fit_predict
from gnn.demo_baseline import build_baseline_features, FEATURE_NAMES
from gnn.explanation_narrative import (
    generate_narrative,
    preflight_narrative_contract,
)
from gnn.demo_checkpoint import (
    checkpoint_node_universe_hash,
    corpus_fingerprints,
    load_demo_checkpoint,
    read_demo_checkpoint_metadata,
    write_demo_checkpoint,
)
from gnn.observability_artifact import build_observability_bundle
from gnn.sage_explainer import Seed0ExplanationEngine

KS = (50, 100, 200, 500, 1000, 2000, 5000)
DAILY_KS = (5, 10, 25)   # per-day inspection budgets for the capacity-aware view
# The simulated-catch view sweeps its own budgets so the operational recovery
# curve can be read at several staffing levels without changing the capacity
# table, the daily crossing chart, or the daily bootstrap, which stay on the
# budgets the run publishes in DAILY_KS.
SIMULATED_DAILY_KS = (5, 10, 25)
SUBSTRATE = "oracle"   # detection demo: perfect ER, shared by both arms (fair)


def _result_path(name_or_path):
    path = Path(name_or_path)
    return path if path.is_absolute() else FC.RESULTS / path


def _atomic_json_write(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2, default=str))
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_observability_output(path, build_payload):
    """Atomically replace observability only after a full new payload succeeds."""
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        payload = build_payload()
        _atomic_json_write(path, payload)
        return payload
    finally:
        temporary.unlink(missing_ok=True)

MODEL_ARMS = {
    "baseline": {
        "label": "HGB tabular baseline",
        "kind": "baseline",
        "looks_for": (
            "Leak-safe per-person own history, observed demographics, and "
            "per-event context. It does not use neighbor labels or graph edges."
        ),
    },
    "hybrid": {
        "label": "Baseline + GNN rank fusion (deployable)",
        "kind": "hybrid",
        "looks_for": (
            "Late score-level fusion: a rank blend of the tabular baseline and "
            "the as-of GraphSAGE risk score. The blend weight is tuned on the "
            "held-out validation split against the CAUGHT label (detected_flag) "
            "only -- the signal available in real deployment, where the true "
            "carrier label is unknown. Leans on the GNN where relational signal "
            "is real and falls back to the baseline where it is not."
        ),
    },
    "hybrid_oracle": {
        "label": "Baseline + GNN rank fusion (oracle ceiling)",
        "kind": "hybrid",
        "looks_for": (
            "Same rank fusion as `hybrid`, but the blend weight is tuned against "
            "the MISSED-carrier label (false_negative_flag), a synthetic-only "
            "oracle. Not deployable; it measures the ceiling and exposes how much "
            "the deployable arm loses from only having caught labels."
        ),
    },
}

# GNN architecture registry. The full 5-way architecture bake-off lives in the
# archived comparison; the demo now runs ONE GNN arm (the best/representative one,
# default GraphSAGE -- also the arm the hybrid fuses) side-by-side with baseline
# and hybrid. Pick another via `main(gnn_arm=...)` to re-run the comparison.
GNN_ARMS = {
    "sage": {"cls": _SAGE, "num_rel": NUM_REL_PLATE, "label": "GraphSAGE",
             "looks_for": "As-of caught-propagation over the person graph, "
                          "ignoring edge types. Best/representative GNN arm; the "
                          "one the hybrid fuses."},
    "rgcn": {"cls": _RGCN, "num_rel": NUM_REL_PLATE, "label": "RGCN full graph",
             "looks_for": "As-of caught-propagation over typed COTRAVEL, "
                          "RESIDENCE, SHARED_PLATE, SHARED_PLATE_HOT relations."},
    "gat": {"cls": _GAT, "num_rel": NUM_REL_PLATE, "label": "GAT (attention)",
            "looks_for": "As-of caught-propagation with attention over neighbors."},
    "gin": {"cls": _GIN, "num_rel": NUM_REL_PLATE, "label": "GIN",
            "looks_for": "As-of caught-propagation with a high-expressivity GIN."},
    "kpiaa": {"cls": _KPIAA, "num_rel": NUM_REL_PLATE, "label": "KPI-AA (approx)",
              "looks_for": "As-of caught-propagation mimicking key-person ID."},
}


def _add_f1_at_k(metrics: dict, ks=KS) -> dict:
    out = dict(metrics)
    for k in ks:
        p = float(out.get(f"precision@{k}", 0.0) or 0.0)
        r = float(out.get(f"recall@{k}", 0.0) or 0.0)
        out[f"f1@{k}"] = round(0.0 if p + r == 0.0 else (2 * p * r / (p + r)), 4)
    return out


def _rank_fuse(base_score, gnn_score, w):
    """Late score-level fusion. Rank-normalize each ranker to [0, 1] within the
    pool and take a convex blend: w on the GNN, (1 - w) on the baseline. Ranks
    (not raw probabilities) so the two very differently-calibrated scores combine
    on a common scale and only their ordering matters."""
    br = rankdata(base_score) / len(base_score)
    gr = rankdata(gnn_score) / len(gnn_score)
    return w * gr + (1.0 - w) * br


def _seed_level_unique_person_recovery(
    pool,
    baseline_raw,
    gnn_scores_by_seed,
    *,
    blend_weight,
    official_caught_times,
    inspections_per_day=5,
):
    """Report seed-level and score-ensemble unique-person recovery at one K.

    Every seed reuses the single validation-tuned fusion weight. Recovery uses
    the production candidate-removal simulation, so later events for a person
    found on an earlier day are excluded independently within each arm.
    """
    seed_order = tuple(int(seed) for seed in gnn_scores_by_seed)
    if not seed_order:
        raise ValueError("gnn_scores_by_seed must contain at least one seed")
    if len(set(seed_order)) != len(seed_order):
        raise ValueError("gnn_scores_by_seed must not contain duplicate seeds")
    daily_budget = int(inspections_per_day)
    if daily_budget <= 0:
        raise ValueError("inspections_per_day must be positive")
    baseline_raw = np.asarray(baseline_raw, dtype=float)
    baseline = add_tiebreak(baseline_raw, pool)
    scores_by_arm = {"baseline": baseline}
    gnn_arrays = []
    for seed in seed_order:
        gnn_raw = np.asarray(gnn_scores_by_seed[seed], dtype=float)
        gnn_arrays.append(gnn_raw)
        scores_by_arm[f"hybrid_seed_{seed}"] = add_tiebreak(
            _rank_fuse(baseline_raw, gnn_raw, blend_weight), pool
        )
    ensemble_gnn = np.mean(np.column_stack(gnn_arrays), axis=1)
    scores_by_arm["hybrid_score_averaged_ensemble"] = add_tiebreak(
        _rank_fuse(baseline_raw, ensemble_gnn, blend_weight), pool
    )
    simulated = evaluate_daily_simulated_catches(
        pool,
        scores_by_arm,
        (daily_budget,),
        official_caught_times,
    )
    found_key = f"daily_people_found@{daily_budget}"
    baseline_count = int(simulated["arms"]["baseline"][found_key])

    def record(hybrid_count):
        hybrid_count = int(hybrid_count)
        return {
            "baseline_unique_people_recovered": baseline_count,
            "hybrid_unique_people_recovered": hybrid_count,
            "net_unique_people_gain": hybrid_count - baseline_count,
        }

    seed_records = {
        str(seed): record(simulated["arms"][f"hybrid_seed_{seed}"][found_key])
        for seed in seed_order
    }
    metric_names = tuple(next(iter(seed_records.values())))
    return {
        "inspections_per_day": daily_budget,
        "common_validation_tuned_fusion_weight": float(blend_weight),
        "seeds": seed_records,
        "mean": {
            metric: float(np.mean([row[metric] for row in seed_records.values()]))
            for metric in metric_names
        },
        "population_sd": {
            metric: float(np.std([row[metric] for row in seed_records.values()]))
            for metric in metric_names
        },
        "score_averaged_ensemble": record(
            simulated["arms"]["hybrid_score_averaged_ensemble"][found_key]
        ),
    }


def _pick_fusion_weight(base_valid, gnn_valid, hidden_valid, ks,
                        grid=tuple(np.round(np.linspace(0.0, 1.0, 21), 3))):
    """Choose a convex late-rank-fusion weight from validation tuning targets.

    The third argument, ``hidden_valid``, is caller-supplied tuning targets:
    callers pass caught labels available to deployment for deployable fusion and
    hidden labels only for the explicitly non-deployable oracle ceiling. The
    objective is mean recall across ``ks`` on those supplied targets.
    """
    hv = np.asarray(hidden_valid, dtype=bool)
    denom = int(hv.sum())
    if denom == 0:
        return 1.0
    valid_ks = [k for k in ks if k <= len(hv)] or [len(hv)]
    best_w, best_val = 1.0, -1.0
    for w in grid:
        order = np.argsort(-_rank_fuse(base_valid, gnn_valid, w), kind="mergesort")
        val = float(np.mean([hv[order[:k]].sum() / denom for k in valid_ks]))
        if val > best_val:
            best_val, best_w = val, float(w)
    return best_w


@dataclass(frozen=True)
class GNNScoreBundle:
    """Runtime GNN models and their per-pool scores in deterministic seed order.

    The mapping/tuple structure and detached, bytes-backed score arrays are
    immutable snapshots. Retained PyTorch model objects remain mutable because
    they are live runtime objects rather than serialized model state.
    """

    seed_order: tuple[int, ...]
    models_by_seed: Mapping[int, object]
    scores_by_seed: Mapping[int, tuple[np.ndarray, ...]]

    def __post_init__(self):
        seed_order = tuple(int(seed) for seed in self.seed_order)
        if not seed_order:
            raise ValueError("seed_order must contain at least one seed")
        if len(set(seed_order)) != len(seed_order):
            raise ValueError("seed_order must not contain duplicate seeds")

        models = {int(seed): model for seed, model in self.models_by_seed.items()}
        raw_scores = {
            int(seed): tuple(seed_scores)
            for seed, seed_scores in self.scores_by_seed.items()
        }
        missing_models = [seed for seed in seed_order if seed not in models]
        missing_scores = [seed for seed in seed_order if seed not in raw_scores]
        if missing_models:
            raise ValueError(f"models_by_seed is missing seeds: {missing_models}")
        if missing_scores:
            raise ValueError(f"scores_by_seed is missing seeds: {missing_scores}")

        pool_counts = {seed: len(raw_scores[seed]) for seed in seed_order}
        if len(set(pool_counts.values())) != 1:
            raise ValueError(
                "scores_by_seed must provide the same number of pool entries "
                f"for every seed: {pool_counts}"
            )

        retained_scores = {}
        for seed in seed_order:
            seed_scores = []
            for pool_index, scores in enumerate(raw_scores[seed]):
                detached = np.array(
                    scores, copy=True, order="C", subok=False
                )
                if detached.ndim != 1:
                    raise ValueError(
                        f"score array for seed {seed}, pool_index {pool_index} "
                        f"must be exactly 1-D; got shape {detached.shape}"
                    )
                try:
                    finite = bool(np.isfinite(detached).all())
                except TypeError as exc:
                    raise ValueError(
                        f"score array for seed {seed}, pool_index {pool_index} "
                        "must contain finite numeric values"
                    ) from exc
                if not finite:
                    raise ValueError(
                        f"score array for seed {seed}, pool_index {pool_index} "
                        "must contain only finite values"
                    )
                immutable = np.frombuffer(
                    detached.tobytes(order="C"), dtype=detached.dtype
                ).reshape(detached.shape)
                seed_scores.append(immutable)
            retained_scores[seed] = tuple(seed_scores)

        for pool_index in range(next(iter(pool_counts.values()))):
            shapes = {
                seed: retained_scores[seed][pool_index].shape
                for seed in seed_order
            }
            if len(set(shapes.values())) != 1:
                raise ValueError(
                    f"score arrays for pool_index {pool_index} must have "
                    f"aligned row shapes across seeds: {shapes}"
                )

        object.__setattr__(self, "seed_order", seed_order)
        object.__setattr__(
            self,
            "models_by_seed",
            MappingProxyType({seed: models[seed] for seed in seed_order}),
        )
        object.__setattr__(
            self,
            "scores_by_seed",
            MappingProxyType(retained_scores),
        )

    def ensemble(self, pool_index):
        """Return the legacy seed mean for one requested pool."""
        if not isinstance(pool_index, (int, np.integer)):
            raise TypeError("pool_index must be an integer")
        pool_index = int(pool_index)
        first_pool_count = len(self.scores_by_seed[self.seed_order[0]])
        if pool_index < 0 or pool_index >= first_pool_count:
            raise IndexError(
                f"pool_index {pool_index} is out of range for "
                f"{first_pool_count} scored pools"
            )

        scores = []
        for seed in self.seed_order:
            seed_scores = self.scores_by_seed[seed]
            if pool_index >= len(seed_scores):
                raise IndexError(
                    f"pool_index {pool_index} is unavailable for seed {seed}"
                )
            scores.append(seed_scores[pool_index])
        shapes = [score.shape for score in scores]
        if any(shape != shapes[0] for shape in shapes[1:]):
            raise ValueError(
                f"inconsistent shapes for pool_index {pool_index}: {shapes}"
            )
        return np.mean(np.column_stack(scores), axis=1)


def _gnn_scores(edges_typed, node_ids, node_feat, caught_time, train_pool,
                train_labels, pools, obs2id, *, seeds, epochs, train_bucket,
                train_cutoff, model_cls, num_rel):
    """Train the caught-propagation GNN once per seed and score each pool in
    `pools` once per model, retaining both for later per-seed observability."""
    seed_order = tuple(int(seed) for seed in seeds)
    if not seed_order:
        raise ValueError("seeds must contain at least one seed")
    if len(set(seed_order)) != len(seed_order):
        raise ValueError("seeds must not contain duplicate seeds")

    pools = tuple(pools)
    index = {p: i for i, p in enumerate(node_ids)}
    validate_pool_identities(
        train_pool, obs2id, index, pool_name="training pool"
    )
    for pool_index, pool in enumerate(pools):
        validate_pool_identities(
            pool,
            obs2id,
            index,
            pool_name=f"scoring pool {pool_index}",
        )
    models_by_seed = {}
    for seed in seed_order:
        models_by_seed[seed] = _train_caught_rgcn(
            edges_typed, node_ids, node_feat, caught_time, train_pool, obs2id,
            train_labels, seed=seed, epochs=epochs, lr=1e-2,
            train_cutoff=train_cutoff, train_bucket=train_bucket,
            num_rel=num_rel, model_cls=model_cls,
        )

    scores_by_seed = {seed: [] for seed in seed_order}
    for pool in pools:
        for seed in seed_order:
            scores_by_seed[seed].append(_score_pool(
                models_by_seed[seed], pool, obs2id, edges_typed, node_ids, node_feat,
                caught_time, index, num_rel=num_rel,
            ))
    return GNNScoreBundle(seed_order, models_by_seed, scores_by_seed)


def _train_pool_and_labels(corpus_dir, train_cutoff):
    """Return train-split supervision available before train_cutoff."""
    egt = pd.read_csv(
        corpus_dir / "event_ground_truth.csv",
        usecols=["event_id", "primary_person_id", "detected_flag"],
    )
    splits = pd.read_csv(
        corpus_dir / "train_valid_test_splits.csv",
        usecols=["entity_id", "split"],
    )
    ev = pd.read_csv(
        corpus_dir / "crossing_events.csv",
        usecols=[
            "event_id",
            "event_timestamp_utc",
            "observed_person_record_id",
            "label_available_time_utc",
        ],
    )
    df = egt.merge(splits, left_on="event_id", right_on="entity_id", how="left").merge(
        ev, on="event_id", how="left"
    )
    tr = df[df.split == "train"].copy()
    tr["t"] = pd.to_datetime(tr.event_timestamp_utc, utc=True, errors="coerce")
    tr["label_available_time"] = pd.to_datetime(
        tr.label_available_time_utc, utc=True, errors="coerce"
    )
    tr = tr.rename(columns={"observed_person_record_id": "primary_obs_id"})
    labels = tr.detected_flag.fillna(False).astype(int).values
    return _eligible_training_supervision(
        tr[
            [
                "event_id",
                "primary_obs_id",
                "primary_person_id",
                "t",
                "label_available_time",
            ]
        ],
        labels,
        train_cutoff,
    )


# Settings that produced the published V9 release artifacts.  ``main`` keeps
# its own experimental defaults (30 epochs, monthly buckets) so ordinary runs
# are unaffected; the ``release`` subcommand replays exactly the configuration
# recorded in the frozen ``demo_comparison_v9.json``, the architecture
# comparison, and the published checkpoint metadata.
PUBLISHED_RELEASE = {
    "seeds": (0, 1, 2),
    "epochs": 18,
    "train_bucket": "Q",
    "gnn_arm": "sage",
    "valid_sample": 20000,
}

# Where `release` writes by default.  Deliberately NOT demo_comparison_v9.json:
# that file is tracked and pinned by the provenance tests, so a verification
# run must not overwrite it.  This name stays on an ignored diagnostics path.
RELEASE_OUT_NAME = "demo_comparison_v9_release.json"


def main(corpus_dir=None, seeds=(0, 1, 2), n_boot=2000, out_name="demo_comparison_v9.json",
         epochs=30, train_bucket="M", ks=KS, daily_ks=DAILY_KS,
         simulated_daily_ks=SIMULATED_DAILY_KS, gnn_arm="sage",
         valid_sample=20000, observability=False,
         observability_out_name="hybrid_recovery_explanations_v9.json",
         explanation_limit=None, narrative=True, narrative_runner=None,
         checkpoint_root=None, schema_version="2.0", hybrid_detail_limit=20,
         baseline_control_limit=10, observability_instrumentation=None):
    """Run the leak-safe baseline-versus-GNN V9 comparison.

    ``corpus_dir`` and output names select the synthetic inputs/artifacts;
    ``seeds``, ``epochs``, ``train_bucket``, ``gnn_arm``, and ``valid_sample``
    configure the graph training; ``ks``, ``daily_ks``, ``simulated_daily_ks``,
    ``n_boot``, and ``observability_instrumentation`` configure evaluation;
    ``observability``, narrative/checkpoint options, and the two detail limits
    control optional evidence publication.  The return value is the comparison
    result mapping.  Checkpoint, comparison JSON, and optional observability
    outputs are each published atomically at their own stage; a later
    observability failure can leave the earlier checkpoint and comparison JSON
    in place.

    Oracle rows may load early for event/split alignment, but hidden and
    organization oracle values cannot affect deployable feature construction,
    score generation, caught-label fusion, threshold selection, or weight
    selection.  Hidden labels first affect oracle fusion and retrospective
    evaluation after deployable outputs freeze; caught-state replay remains
    strictly as-of each scoring time.
    """
    if observability and (
        gnn_arm != "sage" or tuple(seeds) != (0, 1, 2)
    ):
        raise ValueError(
            "observability requires the surrounding three-seed GraphSAGE run"
        )
    if observability and not narrative:
        raise ValueError(
            "production observability requires validated Gemma narratives"
        )
    if observability and str(schema_version) != "3.0":
        preflight_kwargs = {}
        if narrative_runner is not None:
            preflight_kwargs["runner"] = narrative_runner
        preflight_narrative_contract(**preflight_kwargs)
    comparison_path = _result_path(out_name)
    observability_path = _result_path(observability_out_name)
    if observability and comparison_path.absolute() == observability_path.absolute():
        raise ValueError("comparison and observability outputs must be separate files")
    cd = corpus_dir or FC.CORPUS_DIR
    train_cutoff, test_deployment_cutoff = _split_label_cutoffs(cd)
    obs2id = _build_oracle(cd)
    # Oracle rows may load early for alignment. Hidden/org values remain outside
    # deployable features, score generation, caught-label fusion, and selection.
    pool = load_pool(cd)
    valid_pool = load_pool(cd, split="validation")   # held-out slice for fusion tuning
    # Scoring the full validation split is expensive; a random subsample is ample
    # for tuning a single scalar fusion weight on a coarse grid.
    if valid_sample and len(valid_pool) > valid_sample:
        valid_pool = valid_pool.sample(valid_sample, random_state=FC.SEED).reset_index(drop=True)
    # CAUGHT label on validation (the only label available in real deployment);
    # the MISSED label (`hidden`) is a synthetic-only oracle used for the ceiling.
    # event_ground_truth is loaded early to align the caught validation label.
    # Hidden/outcome fields remain outside features and deployable threshold
    # selection; oracle fusion/evaluation happens after deployable outputs freeze.
    _egt_det = pd.read_csv(cd / "event_ground_truth.csv", usecols=["event_id", "detected_flag"])
    valid_detected = (valid_pool.merge(_egt_det, on="event_id", how="left")["detected_flag"]
                      .fillna(False).astype(bool).values)
    valid_label_eligible = _label_available_before(
        valid_pool, test_deployment_cutoff
    ).to_numpy()
    hidden = pool["hidden"].values.astype(bool)
    strata = stratum_for_pool(pool, cd)
    obs_mask = (strata == "observable").values
    train_pool, train_labels = _train_pool_and_labels(cd, train_cutoff)

    # Establish and validate the complete graph identity universe before either
    # tabular or graph model fitting begins.
    spec = GNN_ARMS[gnn_arm]
    edges_typed, node_ids, node_feat = build_person_graph_typed(
        cd, substrate=SUBSTRATE, include_plate=True)
    caught_time = build_caught_times(cd, obs2id)
    node_index = {person_id: index for index, person_id in enumerate(node_ids)}
    validate_pool_identities(
        train_pool, obs2id, node_index, pool_name="training pool"
    )
    validate_pool_identities(
        valid_pool, obs2id, node_index, pool_name="validation pool"
    )
    validate_pool_identities(
        pool, obs2id, node_index, pool_name="test pool"
    )

    # --- baseline (realistic tabular, NO graph) ---
    Xtr, names = build_baseline_features(
        train_pool[["event_id", "primary_obs_id", "t"]], cd, obs2id)
    Xte, _ = build_baseline_features(
        pool[["event_id", "primary_obs_id", "t"]], cd, obs2id)
    Xva, _ = build_baseline_features(
        valid_pool[["event_id", "primary_obs_id", "t"]], cd, obs2id)
    base_raw = fit_predict(Xtr, train_labels, Xte, model="hgb", seed=FC.SEED)
    base_valid = fit_predict(Xtr, train_labels, Xva, model="hgb", seed=FC.SEED)
    base = add_tiebreak(base_raw, pool)

    # --- GNN: one caught-propagation arm (default GraphSAGE), the best/
    # representative architecture from the archived bake-off and the one the
    # hybrid fuses. Train once per seed; score validation (for tuning) + test. ---
    score_bundle = _gnn_scores(
        edges_typed, node_ids, node_feat, caught_time, train_pool, train_labels,
        [valid_pool, pool], obs2id, seeds=seeds, epochs=epochs,
        train_bucket=train_bucket, train_cutoff=train_cutoff,
        model_cls=spec["cls"], num_rel=spec["num_rel"],
    )
    gnn_valid_raw = score_bundle.ensemble(0)
    gnn_test_raw = score_bundle.ensemble(1)
    gnn = add_tiebreak(gnn_test_raw, pool)

    # --- Hybrid: late rank fusion of baseline + GNN, weight tuned on the held-out
    # validation split. Feature-stacking the GNN score into an HGB trained on
    # detected_flag re-ranks the clean structural signal by the biased supervised
    # objective and dilutes it; score-level fusion preserves each ranker's
    # ordering and adapts to how much relational signal is present. ---
    # Deployable: tune the blend on CAUGHT labels (what a real deployment has).
    w_gnn = _pick_fusion_weight(
        base_valid[valid_label_eligible],
        gnn_valid_raw[valid_label_eligible],
        valid_detected[valid_label_eligible],
        ks,
    )
    hybrid = add_tiebreak(_rank_fuse(base_raw, gnn_test_raw, w_gnn), pool)
    # Deployable scores, caught-label fusion, threshold, and blend weight are
    # frozen above. Hidden labels first affect oracle fusion/evaluation below.
    # Ceiling: tune on the MISSED-carrier oracle label. Not deployable; it shows
    # how much the caught-only tuning costs (the biased-proxy gap).
    w_gnn_oracle = _pick_fusion_weight(
        base_valid[valid_label_eligible],
        gnn_valid_raw[valid_label_eligible],
        valid_pool.loc[valid_label_eligible, "hidden"].values,
        ks,
    )
    hybrid_oracle = add_tiebreak(_rank_fuse(base_raw, gnn_test_raw, w_gnn_oracle), pool)

    checkpoint = write_demo_checkpoint(
        checkpoints_root=(
            Path(checkpoint_root)
            if checkpoint_root is not None
            else FC.RESULTS / "checkpoints"
        ),
        corpus_dir=cd,
        seeds=score_bundle.seed_order,
        epochs=epochs,
        train_bucket=train_bucket,
        valid_sample=valid_sample,
        gnn_arm=gnn_arm,
        substrate=SUBSTRATE,
        feature_schema={
            "baseline": names,
            "gnn": caught_feature_names(spec["num_rel"]),
        },
        node_ids=node_ids,
        relation_schema=REL_PLATE,
        fusion_weights={"deployable": w_gnn, "oracle": w_gnn_oracle},
        model_name=gnn_arm,
        model_kwargs={
            "in_dim": len(caught_feature_names(spec["num_rel"])),
            "num_relations": spec["num_rel"],
        },
        models_by_seed=score_bundle.models_by_seed,
        baseline_valid=base_valid,
        baseline_test=base_raw,
        gnn_valid_by_seed={
            seed: score_bundle.scores_by_seed[seed][0]
            for seed in score_bundle.seed_order
        },
        gnn_test_by_seed={
            seed: score_bundle.scores_by_seed[seed][1]
            for seed in score_bundle.seed_order
        },
        validation_event_ids=valid_pool["event_id"].astype(str).tolist(),
        test_event_ids=pool["event_id"].astype(str).tolist(),
    )

    arms = {
        "baseline": base,
        "hybrid": hybrid,
        "hybrid_oracle": hybrid_oracle,
        "gnn": gnn,
    }
    model_arms = {**MODEL_ARMS, "gnn": {
        "label": f"{spec['label']} (best GNN arm)", "kind": "gnn",
        "looks_for": spec["looks_for"]}}
    overall = {
        k: _add_f1_at_k(evaluate(pool.assign(_s=v), "_s", ks=ks), ks=ks)
        for k, v in arms.items()
    }
    overall_daily = {k: evaluate_daily(pool, v, daily_ks) for k, v in arms.items()}
    simulated_catch_daily = evaluate_daily_simulated_catches(
        pool,
        {"baseline": base, "hybrid": hybrid},
        simulated_daily_ks,
        caught_time,
    )
    seed_level_unique_person_recovery = _seed_level_unique_person_recovery(
        pool,
        base_raw,
        {
            seed: score_bundle.scores_by_seed[seed][1]
            for seed in score_bundle.seed_order
        },
        blend_weight=w_gnn,
        official_caught_times=caught_time,
        inspections_per_day=5,
    )
    strat = {k: stratum_metrics(v, pool, hidden, strata, ks=ks) for k, v in arms.items()}
    win = {f"gnn_vs_baseline@{k}": paired_event_bootstrap(
               gnn, base, hidden, ks=(k,), mask=None, n_boot=n_boot)[f"found@{k}"] for k in ks}
    win_obs = {f"gnn_vs_baseline_obs@{k}": paired_event_bootstrap(
               gnn, base, hidden, ks=(k,), mask=obs_mask, n_boot=n_boot)[f"found@{k}"] for k in ks}
    win_hybrid = {f"hybrid_vs_baseline@{k}": paired_event_bootstrap(
               hybrid, base, hidden, ks=(k,), mask=None, n_boot=n_boot)[f"found@{k}"] for k in ks}
    win_hybrid_obs = {f"hybrid_vs_baseline_obs@{k}": paired_event_bootstrap(
               hybrid, base, hidden, ks=(k,), mask=obs_mask, n_boot=n_boot)[f"found@{k}"] for k in ks}
    win_hybrid_daily = paired_daily_bootstrap(
        hybrid, base, pool, hidden, daily_ks=daily_ks, n_boot=n_boot)

    out = {"corpus": str(cd.name), "substrate": SUBSTRATE, "pool_size": int(len(pool)),
           "hidden_total": int(hidden.sum()), "features": FEATURE_NAMES,
           "model_arms": model_arms, "gnn_arm": gnn_arm,
           "gnn_seeds": list(seeds), "epochs": int(epochs),
           "train_bucket": train_bucket,
           "hybrid_fusion_w_gnn": round(float(w_gnn), 3),
           "hybrid_fusion_w_gnn_oracle": round(float(w_gnn_oracle), 3),
           "daily_ks": list(daily_ks),
           "simulated_catch_daily_ks": list(simulated_daily_ks),
           "stratum_hidden": {st: strat["baseline"][st]["hidden"] for st in STRATA},
           "overall": overall, "overall_daily": overall_daily, "stratified": strat,
           "simulated_catch_daily": simulated_catch_daily,
           "seed_level_unique_person_recovery": seed_level_unique_person_recovery,
           "win_whole_pool": win, "win_observable": win_obs,
           "win_hybrid_whole_pool": win_hybrid, "win_hybrid_observable": win_hybrid_obs,
           "win_hybrid_daily": win_hybrid_daily}
    _atomic_json_write(comparison_path, out)
    print(f"scoring checkpoint = {checkpoint.path}")

    if observability:
        def build_artifact():
            engine = Seed0ExplanationEngine(
                model=score_bundle.models_by_seed[0],
                edges_typed=edges_typed,
                node_ids=node_ids,
                node_feat=node_feat,
                caught_time=caught_time,
                num_rel=spec["num_rel"],
            )
            return build_observability_bundle(
                pool=pool,
                baseline_raw=base_raw,
                seed0_gnn_raw=score_bundle.scores_by_seed[0][1],
                blend_weight=w_gnn,
                caught_times=caught_time,
                gnn_arm=gnn_arm,
                surrounding_seeds=score_bundle.seed_order,
                explanation_engine=engine,
                seed_level_unique_person_recovery=(
                    seed_level_unique_person_recovery
                ),
                explanation_limit=explanation_limit,
                schema_version=schema_version,
                hybrid_detail_limit=hybrid_detail_limit,
                baseline_control_limit=baseline_control_limit,
                instrumentation=observability_instrumentation,
                inspections_per_day=5,
                staging_root=(
                    observability_path.parent
                    / f".{observability_path.stem}.recovery-stage"
                ),
                final_root=observability_path.parent / "recovery",
                corpus_identity=str(Path(cd).resolve()),
                recovery_run_identity={"checkpoint_id": checkpoint.checkpoint_id},
                narrative_builder=(
                    generate_narrative
                    if narrative_runner is None
                    else partial(generate_narrative, runner=narrative_runner)
                ),
                narrative_preflight=(
                    None
                    if str(schema_version) != "3.0"
                    else partial(
                        preflight_narrative_contract,
                        **(
                            {"runner": narrative_runner}
                            if narrative_runner is not None
                            else {}
                        ),
                    )
                ),
            )

        _write_observability_output(observability_path, build_artifact)

    print(f"hybrid fusion weight w_gnn = {w_gnn:.3f} (tuned on CAUGHT, deployable) | "
          f"{w_gnn_oracle:.3f} (tuned on MISSED, oracle ceiling)")
    nd = overall_daily["baseline"]["n_days"]
    print(f"--- daily capacity view ({nd} test days) found/recall @ per-day budget ---")
    for k in daily_ks:
        row = " ".join(f"{a}={overall_daily[a][f'daily_found@{k}']}"
                       f"({overall_daily[a][f'daily_recall@{k}']})"
                       for a in ("baseline", "hybrid", "hybrid_oracle", "gnn"))
        print(f"  budget={k}/day (~{overall_daily['baseline'][f'daily_budget@{k}']} total): {row}")
    display_k = 500 if 500 in ks else max(ks)
    for k in arms:
        o, s = overall[k], strat[k]["observable"]
        print(f"{k:18s} P@50={o.get('precision@50', 'n/a')} "
              f"R@{display_k}={o[f'recall@{display_k}']} "
              f"F1@{display_k}={o[f'f1@{display_k}']} "
              f"| OBS f@50={s.get('found@50', 'n/a')} "
              f"f@{display_k}={s[f'found@{display_k}']}/{s['hidden']}")
    print("OBS found@K [base,hybrid,gnn] /", strat["baseline"]["observable"]["hidden"], ":",
          {k: [strat["baseline"]["observable"][f"found@{k}"],
               strat["hybrid"]["observable"][f"found@{k}"],
               strat["gnn"]["observable"][f"found@{k}"]] for k in ks})
    for name, w in {**win, **win_obs, **win_hybrid, **win_hybrid_obs}.items():
        print(name, "diff", w["mean_diff"], "ci", w["ci"], "p", w["p_enh_le_base"])
    return out


def resume_observability(
    checkpoint_path,
    *,
    corpus_dir=None,
    observability_out_name="hybrid_recovery_explanations_v9.json",
    explanation_limit=None,
    narrative=True,
    narrative_runner=None,
    schema_version="2.0",
    hybrid_detail_limit=20,
    baseline_control_limit=10,
    observability_instrumentation=None,
):
    """Generate observability from a verified scoring checkpoint without fitting."""
    if not narrative:
        raise ValueError(
            "production observability requires validated Gemma narratives"
        )
    if str(schema_version) != "3.0":
        preflight_kwargs = {}
        if narrative_runner is not None:
            preflight_kwargs["runner"] = narrative_runner
        preflight_narrative_contract(**preflight_kwargs)

    metadata = read_demo_checkpoint_metadata(checkpoint_path)
    cd = Path(corpus_dir or metadata["corpus"]["identity"])
    run = metadata["run"]
    if run["gnn_arm"] != "sage" or tuple(run["seeds"]) != (0, 1, 2):
        raise ValueError(
            "observability requires the surrounding three-seed GraphSAGE run"
        )
    pool = load_pool(cd)
    valid_pool = load_pool(cd, split="validation")
    valid_sample = run["valid_sample"]
    if valid_sample and len(valid_pool) > valid_sample:
        valid_pool = valid_pool.sample(
            valid_sample, random_state=FC.SEED
        ).reset_index(drop=True)
    obs2id = _build_oracle(cd)
    edges_typed, node_ids, node_feat = build_person_graph_typed(
        cd, substrate=run["substrate"], include_plate=True
    )
    spec = GNN_ARMS[run["gnn_arm"]]
    loaded = load_demo_checkpoint(
        checkpoint_path,
        model_registry={name: arm["cls"] for name, arm in GNN_ARMS.items()},
        expected={
            "seeds": run["seeds"],
            "epochs": run["epochs"],
            "train_bucket": run["train_bucket"],
            "valid_sample": valid_sample,
            "gnn_arm": run["gnn_arm"],
            "substrate": run["substrate"],
            "corpus_identity": str(cd.resolve()),
            "corpus_fingerprints": corpus_fingerprints(cd),
            "feature_schema": {
                "baseline": list(FEATURE_NAMES),
                "gnn": list(caught_feature_names(spec["num_rel"])),
            },
            "node_universe_hash": checkpoint_node_universe_hash(node_ids),
            "relation_schema": {
                key: int(value) for key, value in sorted(REL_PLATE.items())
            },
        },
    )
    expected_valid_ids = valid_pool["event_id"].astype(str).to_numpy()
    expected_test_ids = pool["event_id"].astype(str).to_numpy()
    if not np.array_equal(loaded.validation_event_ids, expected_valid_ids):
        raise ValueError("checkpoint validation event order is incompatible")
    if not np.array_equal(loaded.test_event_ids, expected_test_ids):
        raise ValueError("checkpoint test event order is incompatible")

    caught_time = build_caught_times(cd, obs2id)
    blend_weight = loaded.metadata["fusion_weights"]["deployable"]
    seed_level = _seed_level_unique_person_recovery(
        pool,
        loaded.baseline_test,
        loaded.gnn_test_by_seed,
        blend_weight=blend_weight,
        official_caught_times=caught_time,
        inspections_per_day=5,
    )
    engine = Seed0ExplanationEngine(
        model=loaded.models_by_seed[0],
        edges_typed=edges_typed,
        node_ids=node_ids,
        node_feat=node_feat,
        caught_time=caught_time,
        num_rel=spec["num_rel"],
    )
    observability_path = _result_path(observability_out_name)
    narrative_builder = (
        generate_narrative
        if narrative_runner is None
        else partial(generate_narrative, runner=narrative_runner)
    )
    artifact_holder = {}

    def build_artifact():
        artifact = build_observability_bundle(
            pool=pool,
            baseline_raw=loaded.baseline_test,
            seed0_gnn_raw=loaded.gnn_test_by_seed[0],
            blend_weight=blend_weight,
            caught_times=caught_time,
            gnn_arm=run["gnn_arm"],
            surrounding_seeds=tuple(run["seeds"]),
            explanation_engine=engine,
            seed_level_unique_person_recovery=seed_level,
            explanation_limit=explanation_limit,
            schema_version=schema_version,
            hybrid_detail_limit=hybrid_detail_limit,
            baseline_control_limit=baseline_control_limit,
            instrumentation=observability_instrumentation,
            inspections_per_day=5,
            staging_root=(
                observability_path.parent
                / f".{observability_path.stem}.recovery-stage"
            ),
            final_root=observability_path.parent / "recovery",
            corpus_identity=str(cd.resolve()),
            recovery_run_identity={"checkpoint_id": loaded.checkpoint_id},
            narrative_builder=narrative_builder,
            narrative_preflight=(
                None
                if str(schema_version) != "3.0"
                else partial(
                    preflight_narrative_contract,
                    **(
                        {"runner": narrative_runner}
                        if narrative_runner is not None
                        else {}
                    ),
                )
            ),
        )
        artifact_holder["artifact"] = artifact
        return artifact

    _write_observability_output(observability_path, build_artifact)
    return artifact_holder["artifact"]


def _cli(argv=None):
    """Run the demo, or generate observability from a verified checkpoint.

    Bare invocation keeps the documented `python -m gnn.run_demo` behavior
    with its experimental defaults.  The `release` subcommand instead replays
    `PUBLISHED_RELEASE`, the configuration behind the committed artifacts.
    The `observability` subcommand is the only entry point that can request
    the balanced schema-3 workspace, which is why it defaults to `3.0`.
    """
    import argparse

    parser = argparse.ArgumentParser(prog="gnn.run_demo")
    subparsers = parser.add_subparsers(dest="command")
    release = subparsers.add_parser(
        "release",
        help="replay the exact settings that produced the published artifacts",
    )
    release.add_argument("--out-name", default=RELEASE_OUT_NAME)
    observability = subparsers.add_parser(
        "observability",
        help="generate recovery observability from a verified checkpoint",
    )
    observability.add_argument("checkpoint_path")
    observability.add_argument("--corpus-dir", default=None)
    observability.add_argument(
        "--out-name", default="hybrid_recovery_explanations_v9.json"
    )
    observability.add_argument(
        "--schema-version", choices=("2.0", "3.0"), default="3.0"
    )
    observability.add_argument("--hybrid-detail-limit", type=int, default=20)
    observability.add_argument("--baseline-control-limit", type=int, default=10)
    args = parser.parse_args(argv)
    if args.command == "release":
        return main(out_name=args.out_name, **PUBLISHED_RELEASE)
    if args.command != "observability":
        return main()
    return resume_observability(
        args.checkpoint_path,
        corpus_dir=args.corpus_dir,
        observability_out_name=args.out_name,
        schema_version=args.schema_version,
        hybrid_detail_limit=args.hybrid_detail_limit,
        baseline_control_limit=args.baseline_control_limit,
    )


if __name__ == "__main__":
    _cli()
