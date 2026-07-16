"""Learned cell scores: structural as-of feature builder + GBM and cell-pooled
RGCN trainers. All features/labels obey the leakage rails in the plan:
{COTRAVEL,RESIDENCE} edges only, as-of (avail_time < T), no family_id/outcome/future.
"""
from __future__ import annotations

import os
from collections import Counter

import numpy as np
import pandas as pd







import torch
from gnn.graphmodel_rgcn import REL, NUM_REL, _RGCN, _asof_x, _edge_index_typed

class UF:
    def __init__(self, n):
        self.parent = np.arange(n)
        self.rank = np.zeros(n)
    def find(self, i):
        if self.parent[i] == i: return i
        self.parent[i] = self.find(self.parent[i])
        return self.parent[i]
    def union(self, i, j):
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i != root_j:
            if self.rank[root_i] < self.rank[root_j]:
                self.parent[root_i] = root_j
            elif self.rank[root_i] > self.rank[root_j]:
                self.parent[root_j] = root_i
            else:
                self.parent[root_j] = root_i
                self.rank[root_i] += 1


def _component_roots(node_ids, active_typed_edges, t):
    """Union-find COTRAVEL-component root per node using only edges with
    avail_time < t. Returns an int array of length len(node_ids). Pure membership
    computation (no gradient), shared by numpy and torch pooling below."""
    index = {p: i for i, p in enumerate(node_ids)}
    uf = UF(len(node_ids))
    cot = active_typed_edges[(active_typed_edges["rel"] == REL["COTRAVEL"]) &
                             (active_typed_edges["avail_time"] < t)]
    for u, v in zip(cot["u"], cot["v"]):
        if u in index and v in index:
            uf.union(index[u], index[v])
    return np.array([uf.find(i) for i in range(len(node_ids))])


def _asof_cell_pool(z, node_ids, active_typed_edges, t):
    """Numpy mean-pool of z over as-of COTRAVEL components (inference / tests).
    Singletons keep their own embedding."""
    roots = _component_roots(node_ids, active_typed_edges, t)
    pooled = z.copy()
    for r in np.unique(roots):
        members = np.where(roots == r)[0]
        if len(members) > 1:
            pooled[members] = z[members].mean(axis=0)
    return pooled


def _pool_by_roots_torch(z, roots):
    """Differentiable mean-pool of a torch tensor z by integer component roots.
    Keeps the gradient path to the encoder (unlike a numpy detour)."""
    roots_t = torch.as_tensor(roots, dtype=torch.long)
    uniq, inv = torch.unique(roots_t, return_inverse=True)
    sums = torch.zeros(len(uniq), z.shape[1], dtype=z.dtype).index_add_(0, inv, z)
    counts = torch.zeros(len(uniq), 1, dtype=z.dtype).index_add_(
        0, inv, torch.ones(len(z), 1, dtype=z.dtype))
    return (sums / counts)[inv]


def build_caught_times(corpus_dir, obs_to_identity) -> dict:
    """identity -> earliest official DETECTED-label availability (tz-aware).
    This is the persistent 'ever caught' boundary; a scoring time T uses
    caught_time[id] < T, so only officially available catches strictly before T
    ever raise risk (as-of, no future peek)."""
    egt = pd.read_csv(corpus_dir / "event_ground_truth.csv",
                      usecols=["event_id", "detected_flag"])
    ev = pd.read_csv(corpus_dir / "crossing_events.csv",
                     usecols=["event_id", "observed_person_record_id",
                              "label_available_time_utc"])
    det = egt[egt.detected_flag.fillna(False).astype(bool)].merge(ev, on="event_id")
    det["identity"] = det["observed_person_record_id"].map(obs_to_identity)
    det["_t"] = pd.to_datetime(det["label_available_time_utc"], utc=True, errors="coerce")
    det = det.dropna(subset=["identity", "_t"])
    return det.groupby("identity")["_t"].min().to_dict()


def _eligible_training_supervision(train_pool, train_labels, train_cutoff):
    """Return event/label pairs available strictly before train_cutoff."""
    rows = train_pool.reset_index(drop=True).copy()
    labels = np.asarray(train_labels)
    if len(rows) != len(labels):
        raise ValueError("train_pool and train_labels must have equal length")
    if "label_available_time" not in rows.columns:
        raise ValueError("train_pool must include label_available_time")

    cutoff = pd.Timestamp(train_cutoff)
    cutoff = (
        cutoff.tz_localize("UTC")
        if cutoff.tzinfo is None
        else cutoff.tz_convert("UTC")
    )
    event_time = pd.to_datetime(rows["t"], utc=True, errors="coerce")
    label_time = pd.to_datetime(
        rows["label_available_time"], utc=True, errors="coerce"
    )
    eligible = (
        event_time.notna()
        & (event_time < cutoff)
        & label_time.notna()
        & (label_time < cutoff)
    ).to_numpy()
    return rows.loc[eligible].reset_index(drop=True), labels[eligible]


def _asof_struct_feats(node_ids, active_edges, T):
    """Per-node as-of structural bridging features, so the RGCN can SEE and
    message-pass the finding-5 signal (not just degree):
      - cell_size: size of the node's COTRAVEL component (as-of T)
      - distinct_hh: # distinct RESIDENCE households spanned by that component
    Returns (cell_size, distinct_hh) float arrays aligned to node_ids."""
    index = {p: i for i, p in enumerate(node_ids)}
    n = len(node_ids)
    res_uf = UF(n)
    res = active_edges[(active_edges["rel"] == REL["RESIDENCE"]) &
                       (active_edges["avail_time"] < T)]
    for u, v in zip(res["u"], res["v"]):
        if u in index and v in index:
            res_uf.union(index[u], index[v])
    roots = _component_roots(node_ids, active_edges, T)  # COTRAVEL cell roots
    cell_size = np.ones(n, dtype=float)
    distinct_hh = np.ones(n, dtype=float)
    members: dict = {}
    for i, r in enumerate(roots):
        members.setdefault(r, []).append(i)
    for r, mem in members.items():
        if len(mem) > 1:
            hhs = {res_uf.find(m) for m in mem}
            for m in mem:
                cell_size[m] = len(mem)
                distinct_hh[m] = len(hhs)
    return cell_size, distinct_hh


def _asof_x_caught(node_ids, node_feat, active_edges, caught_time, T, num_rel=NUM_REL):
    """As-of node features for the caught-propagation RGCN, in column order:
    [base + per-relation degree (_asof_x)] + [log1p(cell_size), log1p(distinct_hh)]
    (finding-5 structural bridging) + [caught_before_T]. `caught_before_T` is kept
    as the LAST column (1.0 iff caught_time[p] < T, persistent, strictly as-of)."""
    x = _asof_x(node_ids, node_feat, active_edges, num_rel=num_rel)
    cell_size, distinct_hh = _asof_struct_feats(node_ids, active_edges, T)
    struct = torch.tensor(
        np.column_stack([np.log1p(cell_size), np.log1p(distinct_hh)]), dtype=torch.float)
    caught = torch.tensor(
        [[1.0] if (caught_time.get(p) is not None and caught_time[p] < T) else [0.0]
         for p in node_ids], dtype=torch.float)
    return torch.cat([x, struct, caught], dim=1)


def _train_caught_rgcn(edges_typed, node_ids, node_feat, caught_time, train_pool,
                       obs_to_identity, train_labels, *, seed, epochs, lr,
                       train_cutoff, train_bucket, num_rel=NUM_REL, model_cls=_RGCN):
    """Per-event supervision, time-bucketed for speed. Each train crossing keeps its
    OWN detected label; features/edges are as-of the bucket start (strictly < bucket).
    Gradients flow enc -> torch cell-pool -> head (no numpy detour)."""
    torch.manual_seed(seed)
    cutoff = pd.Timestamp(train_cutoff)
    cutoff = (
        cutoff.tz_localize("UTC")
        if cutoff.tzinfo is None
        else cutoff.tz_convert("UTC")
    )
    index = {p: i for i, p in enumerate(node_ids)}
    tr, eligible_labels = _eligible_training_supervision(
        train_pool, train_labels, cutoff
    )
    tr["identity"] = tr["primary_obs_id"].map(obs_to_identity)
    tr["_t"] = pd.to_datetime(tr["t"], utc=True, errors="coerce")
    tr["_lab"] = np.asarray(eligible_labels, dtype=float)
    tr = tr[tr["identity"].isin(index)].copy()
    if len(tr) == 0:
        return model_cls(_asof_x_caught(node_ids, node_feat, edges_typed.iloc[0:0],
                                    caught_time, cutoff, num_rel=num_rel).shape[1],
                     num_relations=num_rel)
    tr["_bucket"] = (tr["_t"].dt.to_period(train_bucket).dt.start_time
                     .dt.tz_localize("UTC"))

    in_dim = _asof_x_caught(node_ids, node_feat, edges_typed.iloc[0:0],
                            caught_time, cutoff, num_rel=num_rel).shape[1]
    model = model_cls(in_dim, num_relations=num_rel)
    npos = float(tr["_lab"].sum()); nneg = float(len(tr)) - npos
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor([nneg / max(npos, 1.0)]))
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    groups = list(tr.groupby("_bucket", sort=True))
    model.train()
    for _ in range(epochs):
        for Tb, grp in groups:
            sub = edges_typed[edges_typed["avail_time"] < Tb]
            x = _asof_x_caught(node_ids, node_feat, sub, caught_time, Tb, num_rel=num_rel)
            ei, et = _edge_index_typed(sub, index)
            z = model.enc(x, ei, edge_type=et)
            zp = _pool_by_roots_torch(z, _component_roots(node_ids, sub, Tb))
            logit = model.head(zp).squeeze(-1)
            idxs = [index[i] for i in grp["identity"]]
            labs = torch.tensor(grp["_lab"].values, dtype=torch.float)
            loss = loss_fn(logit[idxs], labs)
            opt.zero_grad(); loss.backward(); opt.step()
    model.eval()
    return model


def _score_pool(model, pool, obs_to_identity, edges_typed, node_ids, node_feat,
                caught_time, index, *, num_rel=NUM_REL):
    """Score a pool of crossing events with a trained caught-propagation model."""
    rows = pool.reset_index(drop=True).copy()
    rows["identity"] = rows["primary_obs_id"].map(obs_to_identity)
    rows["_t"] = pd.to_datetime(rows["t"], utc=True, errors="coerce").dt.floor("D")
    out = np.zeros(len(rows))
    with torch.no_grad():
        for t, grp in rows.groupby("_t", sort=True):
            sub = edges_typed[edges_typed["avail_time"] < t]
            x = _asof_x_caught(node_ids, node_feat, sub, caught_time, t, num_rel=num_rel)
            ei, et = _edge_index_typed(sub, index)
            z = model.enc(x, ei, edge_type=et)
            zp = _pool_by_roots_torch(z, _component_roots(node_ids, sub, t))
            prob = torch.sigmoid(model.head(zp).squeeze(-1)).numpy()
            for ridx, ident in zip(grp.index, grp["identity"]):
                out[ridx] = prob[index[ident]] if ident in index else 0.0
    return out


def rgcn_cell_score(edges_typed, node_ids, node_feat, caught_time, train_pool,
                    test_pool, obs_to_identity, train_labels, *, seed=0, epochs=30,
                    lr=1e-2, train_cutoff="2024-01-01", train_bucket="M",
                    num_rel=NUM_REL, model_cls=_RGCN) -> np.ndarray:
    """Train a caught-propagation RGCN and return test-pool risk scores."""
    model = _train_caught_rgcn(edges_typed, node_ids, node_feat, caught_time, train_pool,
                               obs_to_identity, train_labels, seed=seed, epochs=epochs,
                               lr=lr, train_cutoff=train_cutoff, train_bucket=train_bucket,
                               num_rel=num_rel, model_cls=model_cls)
    index = {p: i for i, p in enumerate(node_ids)}
    return _score_pool(model, test_pool, obs_to_identity, edges_typed, node_ids,
                       node_feat, caught_time, index, num_rel=num_rel)


def rgcn_oof_train_scores(edges_typed, node_ids, node_feat, caught_time,
                          train_pool, obs_to_identity, train_labels, *,
                          seed=0, epochs=30, lr=1e-2, train_cutoff="2024-01-01",
                          train_bucket="M", num_rel=NUM_REL, model_cls=_RGCN,
                          n_folds=3) -> np.ndarray:
    """K-fold out-of-fold GNN scores for training rows (leak-free for hybrid).

    Each training row is scored by a model that was NOT trained on that row,
    preventing the in-sample overfitting that would inflate the hybrid arm.
    """
    from sklearn.model_selection import KFold

    oof = np.zeros(len(train_pool))
    kf = KFold(n_splits=n_folds, shuffle=True, random_state=seed)
    labels_arr = np.asarray(train_labels)
    index = {p: i for i, p in enumerate(node_ids)}

    for fold_train_idx, fold_val_idx in kf.split(train_pool):
        fold_tp = train_pool.iloc[fold_train_idx].reset_index(drop=True)
        fold_tl = labels_arr[fold_train_idx]
        fold_vp = train_pool.iloc[fold_val_idx].reset_index(drop=True)

        model = _train_caught_rgcn(
            edges_typed, node_ids, node_feat, caught_time,
            fold_tp, obs_to_identity, fold_tl,
            seed=seed, epochs=epochs, lr=lr,
            train_cutoff=train_cutoff, train_bucket=train_bucket,
            num_rel=num_rel, model_cls=model_cls,
        )

        oof[fold_val_idx] = _score_pool(
            model, fold_vp, obs_to_identity, edges_typed,
            node_ids, node_feat, caught_time, index, num_rel=num_rel,
        )

    return oof
