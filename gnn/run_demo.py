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

def add_tiebreak(scores, pool):
    rng = np.random.default_rng(42)
    return np.array(scores, dtype=float) + rng.uniform(0, 1e-9, size=len(scores))

def load_pool(corpus_dir):
    egt = pd.read_csv(corpus_dir / "event_ground_truth.csv", usecols=["event_id", "primary_person_id", "false_negative_flag"])
    splits = pd.read_csv(corpus_dir / "train_valid_test_splits.csv", usecols=["entity_id", "split"])
    ev = pd.read_csv(corpus_dir / "crossing_events.csv", usecols=["event_id", "event_timestamp_utc", "observed_person_record_id"])
    df = egt.merge(splits, left_on="event_id", right_on="entity_id", how="inner").merge(ev, on="event_id", how="inner")
    te = df[df.split == "test"].copy()
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
)
from gnn.learned_cell import build_caught_times, rgcn_cell_score
from gnn.detector import fit_predict
from gnn.demo_baseline import build_baseline_features, FEATURE_NAMES

KS = (50, 100, 200, 500, 1000, 2000, 5000)
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
    "gnn": {
        "label": "RGCN full graph",
        "kind": "gnn",
        "looks_for": (
            "As-of caught-propagation over COTRAVEL, RESIDENCE, SHARED_PLATE, "
            "and SHARED_PLATE_HOT relations. This is the canonical V9 GNN arm."
        ),
    },
}


def _add_f1_at_k(metrics: dict, ks=KS) -> dict:
    out = dict(metrics)
    for k in ks:
        p = float(out.get(f"precision@{k}", 0.0) or 0.0)
        r = float(out.get(f"recall@{k}", 0.0) or 0.0)
        out[f"f1@{k}"] = round(0.0 if p + r == 0.0 else (2 * p * r / (p + r)), 4)
    return out


def _mean_rgcn_score(
    edges_typed,
    node_ids,
    node_feat,
    caught_time,
    train_pool,
    pool,
    obs2id,
    train_labels,
    *,
    seeds,
    num_rel,
    epochs,
    train_bucket,
) -> np.ndarray:
    per_seed = [
        rgcn_cell_score(
            edges_typed,
            node_ids,
            node_feat,
            caught_time,
            train_pool,
            pool,
            obs2id,
            train_labels,
            seed=s,
            num_rel=num_rel,
            epochs=epochs,
            train_bucket=train_bucket,
        )
        for s in seeds
    ]
    return np.mean(np.column_stack(per_seed), axis=1)


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
         epochs=30, train_bucket="M", ks=KS):
    cd = corpus_dir or FC.CORPUS_DIR
    obs2id = _build_oracle(cd)
    pool = load_pool(cd)
    hidden = pool["hidden"].values.astype(bool)
    strata = stratum_for_pool(pool, cd)
    obs_mask = (strata == "observable").values
    train_pool, train_labels = _train_pool_and_labels(cd)

    # --- baseline (realistic tabular, NO graph) ---
    Xtr, names = build_baseline_features(
        train_pool[["event_id", "primary_obs_id", "t"]], cd, obs2id)
    Xte, _ = build_baseline_features(
        pool[["event_id", "primary_obs_id", "t"]], cd, obs2id)
    base = add_tiebreak(fit_predict(Xtr, train_labels, Xte, model="hgb", seed=FC.SEED), pool)

    # --- GNN (as-of caught-propagation RGCN incl. shared-plate relations) ---
    edges_typed, node_ids, node_feat = build_person_graph_typed(
        cd, substrate=SUBSTRATE, include_plate=True)
    caught_time = build_caught_times(cd, obs2id)
    gnn = add_tiebreak(
        _mean_rgcn_score(
            edges_typed, node_ids, node_feat, caught_time, train_pool, pool,
            obs2id, train_labels, seeds=seeds, num_rel=NUM_REL_PLATE, epochs=epochs,
            train_bucket=train_bucket,
        ),
        pool,
    )

    arms = {
        "baseline": base,
        "gnn": gnn,
    }
    overall = {
        k: _add_f1_at_k(evaluate(pool.assign(_s=v), "_s", ks=ks), ks=ks)
        for k, v in arms.items()
    }
    strat = {k: stratum_metrics(v, pool, hidden, strata, ks=ks) for k, v in arms.items()}
    win = {f"gnn_vs_baseline@{k}": paired_event_bootstrap(
               gnn, base, hidden, ks=(k,), mask=None, n_boot=n_boot)[f"found@{k}"] for k in ks}
    win_obs = {f"gnn_vs_baseline_obs@{k}": paired_event_bootstrap(
               gnn, base, hidden, ks=(k,), mask=obs_mask, n_boot=n_boot)[f"found@{k}"] for k in ks}

    out = {"corpus": str(cd.name), "substrate": SUBSTRATE, "pool_size": int(len(pool)),
           "hidden_total": int(hidden.sum()), "features": FEATURE_NAMES,
           "model_arms": MODEL_ARMS,
           "gnn_seeds": list(seeds), "epochs": int(epochs),
           "train_bucket": train_bucket,
           "stratum_hidden": {st: strat["baseline"][st]["hidden"] for st in STRATA},
           "overall": overall, "stratified": strat,
           "win_whole_pool": win, "win_observable": win_obs}
    FC.RESULTS.mkdir(parents=True, exist_ok=True)
    (FC.RESULTS / out_name).write_text(json.dumps(out, indent=2, default=str))

    display_k = 500 if 500 in ks else max(ks)
    for k in arms:
        o, s = overall[k], strat[k]["observable"]
        print(f"{k:18s} P@50={o.get('precision@50', 'n/a')} "
              f"R@{display_k}={o[f'recall@{display_k}']} "
              f"F1@{display_k}={o[f'f1@{display_k}']} "
              f"| OBS f@50={s.get('found@50', 'n/a')} "
              f"f@{display_k}={s[f'found@{display_k}']}/{s['hidden']}")
    print("OBS found@K [base,gnn] /", strat["baseline"]["observable"]["hidden"], ":",
          {k: [strat["baseline"]["observable"][f"found@{k}"],
               strat["gnn"]["observable"][f"found@{k}"]] for k in ks})
    for name, w in {**win, **win_obs}.items():
        print(name, "diff", w["mean_diff"], "ci", w["ci"], "p", w["p_enh_le_base"])
    return out


if __name__ == "__main__":
    main()
