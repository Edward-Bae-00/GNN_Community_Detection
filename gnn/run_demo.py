"""V9 positive-control demo: a realistic tabular baseline vs an as-of caught-
propagation RGCN over {COTRAVEL, RESIDENCE, SHARED_PLATE, SHARED_PLATE_HOT}. Same
pool, same substrate (oracle identity — ER is NOT the question here and both arms
share it, so the comparison is fair), leak-free; paired-event bootstrap for
significance. Run against V9:

    CBP_CORPUS_DIR=$PWD/Documents/Data/synthetic_cbp_graph_corpus_v9 \
        PYTHONPATH=. python -m gnn.run_demo
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd

from gnn import config as FC

STRATA = ("observable", "dark", "lone")

def evaluate(df, score_col, ks):
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
    rng = np.random.default_rng(42)
    return np.array(scores, dtype=float) + rng.uniform(0, 1e-9, size=len(scores))

def load_pool(corpus_dir, split="test"):
    egt = pd.read_csv(corpus_dir / "event_ground_truth.csv", usecols=["event_id", "primary_person_id", "false_negative_flag"])
    splits = pd.read_csv(corpus_dir / "train_valid_test_splits.csv", usecols=["entity_id", "split"])
    ev = pd.read_csv(corpus_dir / "crossing_events.csv", usecols=["event_id", "event_timestamp_utc", "observed_person_record_id"])
    df = egt.merge(splits, left_on="event_id", right_on="entity_id", how="inner").merge(ev, on="event_id", how="inner")
    te = df[df.split == split].copy()
    te["t"] = pd.to_datetime(te.event_timestamp_utc, utc=True, errors="coerce")
    te = te.rename(columns={"observed_person_record_id": "primary_obs_id"})
    te["hidden"] = te["false_negative_flag"].fillna(False).astype(bool)
    return te.reset_index(drop=True)

def _build_oracle(corpus_dir):
    obs = pd.read_csv(corpus_dir / "observed_person_records.csv", usecols=["observed_person_record_id", "canonical_person_id"])
    return dict(zip(obs["observed_person_record_id"], obs["canonical_person_id"]))

def stratum_for_pool(pool, corpus_dir):
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
    ranked = pd.DataFrame({
        "_day": days,
        "_s": np.asarray(scores),
        "_hidden": np.asarray(hidden, dtype=bool),
    }).sort_values(["_day", "_s"], ascending=[True, False], kind="mergesort")
    ranked["_day_rank"] = ranked.groupby("_day", sort=False).cumcount()
    selected_mask = np.ones(len(ranked), dtype=bool)
    if mask is not None:
        ranked["_mask"] = np.asarray(mask, dtype=bool)
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
)
from gnn.graphmodel_alt import _SAGE, _GAT, _GIN, _KPIAA
from gnn.learned_cell import (build_caught_times, _train_caught_rgcn, _score_pool)
from scipy.stats import rankdata
from gnn.detector import fit_predict
from gnn.demo_baseline import build_baseline_features, FEATURE_NAMES

KS = (50, 100, 200, 500, 1000, 2000, 5000)
DAILY_KS = (5, 10, 25, 50)   # per-day inspection budgets for the capacity-aware view
SUBSTRATE = "oracle"   # detection demo: perfect ER, shared by both arms (fair)

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


def _pick_fusion_weight(base_valid, gnn_valid, hidden_valid, ks,
                        grid=tuple(np.round(np.linspace(0.0, 1.0, 21), 3))):
    """Choose the GNN blend weight on the held-out validation split (leak-free
    w.r.t. test). Objective = mean recall of hidden carriers across `ks`, so the
    weight adapts to how much real relational signal the GNN carries: ~1.0 when
    the graph dominates, ~0.0 when it is noise and the baseline should win."""
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


def _gnn_scores(edges_typed, node_ids, node_feat, caught_time, train_pool,
                train_labels, pools, obs2id, *, seeds, epochs, train_bucket,
                model_cls, num_rel):
    """Train the caught-propagation GNN once per seed and score each pool in
    `pools` with the shared, seed-averaged models. Returns one score array per
    pool (same order as `pools`), so validation and test share identical models."""
    index = {p: i for i, p in enumerate(node_ids)}
    models = [
        _train_caught_rgcn(
            edges_typed, node_ids, node_feat, caught_time, train_pool, obs2id,
            train_labels, seed=s, epochs=epochs, lr=1e-2,
            train_cutoff="2024-01-01", train_bucket=train_bucket,
            num_rel=num_rel, model_cls=model_cls,
        )
        for s in seeds
    ]
    scored = []
    for p in pools:
        scored.append(np.mean(np.column_stack([
            _score_pool(m, p, obs2id, edges_typed, node_ids, node_feat,
                        caught_time, index, num_rel=num_rel)
            for m in models
        ]), axis=1))
    return scored


def _train_pool_and_labels(corpus_dir):
    """Train events = train split, with detected_flag as label."""
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
        usecols=["event_id", "event_timestamp_utc", "observed_person_record_id"],
    )
    df = egt.merge(splits, left_on="event_id", right_on="entity_id", how="left").merge(
        ev, on="event_id", how="left"
    )
    tr = df[df.split == "train"].copy()
    tr["t"] = pd.to_datetime(tr.event_timestamp_utc, utc=True, errors="coerce")
    tr = tr.rename(columns={"observed_person_record_id": "primary_obs_id"})
    labels = tr.detected_flag.fillna(False).astype(int).values
    return (
        tr[["event_id", "primary_obs_id", "primary_person_id", "t"]].reset_index(drop=True),
        labels,
    )


def main(corpus_dir=None, seeds=(0, 1, 2), n_boot=2000, out_name="demo_comparison_v9.json",
         epochs=30, train_bucket="M", ks=KS, daily_ks=DAILY_KS, gnn_arm="sage",
         valid_sample=20000):
    cd = corpus_dir or FC.CORPUS_DIR
    obs2id = _build_oracle(cd)
    pool = load_pool(cd)
    valid_pool = load_pool(cd, split="validation")   # held-out slice for fusion tuning
    # Scoring the full validation split is expensive; a random subsample is ample
    # for tuning a single scalar fusion weight on a coarse grid.
    if valid_sample and len(valid_pool) > valid_sample:
        valid_pool = valid_pool.sample(valid_sample, random_state=FC.SEED).reset_index(drop=True)
    # CAUGHT label on validation (the only label available in real deployment);
    # the MISSED label (`hidden`) is a synthetic-only oracle used for the ceiling.
    _egt_det = pd.read_csv(cd / "event_ground_truth.csv", usecols=["event_id", "detected_flag"])
    valid_detected = (valid_pool.merge(_egt_det, on="event_id", how="left")["detected_flag"]
                      .fillna(False).astype(bool).values)
    hidden = pool["hidden"].values.astype(bool)
    strata = stratum_for_pool(pool, cd)
    obs_mask = (strata == "observable").values
    train_pool, train_labels = _train_pool_and_labels(cd)

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
    spec = GNN_ARMS[gnn_arm]
    edges_typed, node_ids, node_feat = build_person_graph_typed(
        cd, substrate=SUBSTRATE, include_plate=True)
    caught_time = build_caught_times(cd, obs2id)
    gnn_valid_raw, gnn_test_raw = _gnn_scores(
        edges_typed, node_ids, node_feat, caught_time, train_pool, train_labels,
        [valid_pool, pool], obs2id, seeds=seeds, epochs=epochs,
        train_bucket=train_bucket, model_cls=spec["cls"], num_rel=spec["num_rel"],
    )
    gnn = add_tiebreak(gnn_test_raw, pool)

    # --- Hybrid: late rank fusion of baseline + GNN, weight tuned on the held-out
    # validation split. Feature-stacking the GNN score into an HGB trained on
    # detected_flag re-ranks the clean structural signal by the biased supervised
    # objective and dilutes it; score-level fusion preserves each ranker's
    # ordering and adapts to how much relational signal is present. ---
    # Deployable: tune the blend on CAUGHT labels (what a real deployment has).
    w_gnn = _pick_fusion_weight(base_valid, gnn_valid_raw, valid_detected, ks)
    hybrid = add_tiebreak(_rank_fuse(base_raw, gnn_test_raw, w_gnn), pool)
    # Ceiling: tune on the MISSED-carrier oracle label. Not deployable; it shows
    # how much the caught-only tuning costs (the biased-proxy gap).
    w_gnn_oracle = _pick_fusion_weight(
        base_valid, gnn_valid_raw, valid_pool["hidden"].values, ks)
    hybrid_oracle = add_tiebreak(_rank_fuse(base_raw, gnn_test_raw, w_gnn_oracle), pool)

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
        daily_ks,
        caught_time,
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
           "stratum_hidden": {st: strat["baseline"][st]["hidden"] for st in STRATA},
           "overall": overall, "overall_daily": overall_daily, "stratified": strat,
           "simulated_catch_daily": simulated_catch_daily,
           "win_whole_pool": win, "win_observable": win_obs,
           "win_hybrid_whole_pool": win_hybrid, "win_hybrid_observable": win_hybrid_obs,
           "win_hybrid_daily": win_hybrid_daily}
    FC.RESULTS.mkdir(parents=True, exist_ok=True)
    (FC.RESULTS / out_name).write_text(json.dumps(out, indent=2, default=str))

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


if __name__ == "__main__":
    main()
