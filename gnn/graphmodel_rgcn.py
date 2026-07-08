from __future__ import annotations
import numpy as np
import pandas as pd
import torch
from torch_geometric.nn import RGCNConv
import torch.nn.functional as F

from . import config as C

REL = {"COTRAVEL": 0, "RESIDENCE": 1}
NUM_REL = 2
REL_PLATE = {"COTRAVEL": 0, "RESIDENCE": 1,
             "SHARED_PLATE": 2, "SHARED_PLATE_HOT": 3}
NUM_REL_PLATE = 4

class RelationSAGEEncoder(torch.nn.Module):
    def __init__(self, in_dim, hidden=32, out=32, num_relations=4):
        super().__init__()
        self.conv1 = RGCNConv(in_dim, hidden, num_relations=num_relations)
        self.conv2 = RGCNConv(hidden, out, num_relations=num_relations)

    def forward(self, x, edge_index, edge_type):
        x = self.conv1(x, edge_index, edge_type)
        x = F.relu(x)
        x = self.conv2(x, edge_index, edge_type)
        return x

def build_anchor_graph(obs_to_person, corpus_dir, include_assoc=False, include_plate=False):
    obs = pd.read_csv(corpus_dir / "observed_person_records.csv", usecols=["observed_person_record_id", "event_id", "event_timestamp_utc", "observed_residence_location_id"])
    obs["identity"] = obs["observed_person_record_id"].map(obs_to_person)
    obs = obs.dropna(subset=["identity"])
    obs["avail_time"] = pd.to_datetime(obs["event_timestamp_utc"], utc=True, errors="coerce")
    edges = []
    
    merged = obs.merge(obs, on="event_id")
    merged = merged[merged["identity_x"] != merged["identity_y"]]
    merged["edge_type"] = "COTRAVEL"
    merged["avail_time"] = merged[["avail_time_x", "avail_time_y"]].max(axis=1)
    edges.append(merged[["identity_x", "identity_y", "avail_time", "edge_type"]].rename(columns={"identity_x": "u", "identity_y": "v"}))
    
    obs_res = obs.dropna(subset=["observed_residence_location_id"])
    merged_res = obs_res.merge(obs_res, on="observed_residence_location_id")
    merged_res = merged_res[merged_res["identity_x"] != merged_res["identity_y"]]
    merged_res["edge_type"] = "RESIDENCE"
    merged_res["avail_time"] = merged_res[["avail_time_x", "avail_time_y"]].max(axis=1)
    edges.append(merged_res[["identity_x", "identity_y", "avail_time", "edge_type"]].rename(columns={"identity_x": "u", "identity_y": "v"}))

    if include_plate:
        ce = pd.read_csv(corpus_dir / "crossing_events.csv", usecols=["observed_person_record_id", "vehicle_id", "event_timestamp_utc", "seizure_flag"])
        ce["identity"] = ce["observed_person_record_id"].map(obs_to_person)
        ce = ce.dropna(subset=["identity", "vehicle_id"])
        ce["avail_time"] = pd.to_datetime(ce["event_timestamp_utc"], utc=True, errors="coerce")
        ce["seizure_flag"] = ce["seizure_flag"].astype(str).str.lower().eq("true")
        first_seizure_time = (
            ce.loc[ce["seizure_flag"]]
              .groupby("vehicle_id")["avail_time"]
              .min()
        )
        
        merged_ce = ce.merge(ce, on="vehicle_id")
        merged_ce = merged_ce[merged_ce["identity_x"] != merged_ce["identity_y"]]
        merged_ce["avail_time"] = merged_ce[["avail_time_x", "avail_time_y"]].max(axis=1)
        merged_ce["edge_type"] = "SHARED_PLATE"
        merged_ce["first_seizure_time"] = merged_ce["vehicle_id"].map(first_seizure_time)
        hot_mask = (
            merged_ce["first_seizure_time"].notna()
            & (merged_ce["avail_time"] >= merged_ce["first_seizure_time"])
        )
        merged_ce.loc[hot_mask, "edge_type"] = "SHARED_PLATE_HOT"
        edges.append(merged_ce[["identity_x", "identity_y", "avail_time", "edge_type"]].rename(columns={"identity_x": "u", "identity_y": "v"}))
        
    return pd.concat(edges, ignore_index=True) if edges else pd.DataFrame(columns=["u", "v", "avail_time", "edge_type"])

class _RGCN(torch.nn.Module):
    def __init__(self, in_dim, hidden=32, out=32, num_relations=NUM_REL):
        super().__init__()
        self.enc = RelationSAGEEncoder(in_dim, hidden=hidden, out=out, num_relations=num_relations)
        self.head = torch.nn.Linear(out, 1)
    def forward(self, x, edge_index, edge_type):
        z = self.enc(x, edge_index, edge_type=edge_type)
        return self.head(z).squeeze(-1)

def build_person_graph_typed(corpus_dir=None, substrate="oracle", include_plate=False):
    from gnn.run_demo import _build_oracle
    corpus_dir = corpus_dir or C.CORPUS_DIR
    obs_to_person = _build_oracle(corpus_dir)
    e = build_anchor_graph(obs_to_person, corpus_dir, include_assoc=False,
                           include_plate=include_plate)  # +SHARED_PLATE(_HOT) if include_plate
    rel_map = REL_PLATE if include_plate else REL
    e = e[e["edge_type"].isin(rel_map.keys())].copy()
    e["avail_time"] = pd.to_datetime(e["avail_time"], utc=True, errors="coerce")
    e = e[e["avail_time"].notna()].copy()
    e["rel"] = e["edge_type"].map(rel_map).astype(int)
    node_ids = sorted(set(e["u"]) | set(e["v"]))
    node_feat = {p: np.array([1.0]) for p in node_ids}
    return e[["u", "v", "avail_time", "rel"]].copy(), node_ids, node_feat

def _asof_x(node_ids, node_feat, active_edges, num_rel=NUM_REL):
    index = {p: i for i, p in enumerate(node_ids)}
    base = np.stack([node_feat[p] for p in node_ids])
    deg = np.zeros((len(node_ids), num_rel))
    if len(active_edges):
        for r in range(num_rel):
            sub = active_edges[active_edges["rel"] == r]
            if len(sub):
                vc = pd.concat([sub["u"], sub["v"]]).value_counts()
                for p, c in vc.items():
                    if p in index:
                        deg[index[p], r] = float(c)
    return torch.tensor(np.hstack([base, deg]), dtype=torch.float)

def _edge_index_typed(edges, index):
    if len(edges) == 0:
        return torch.zeros((2,0), dtype=torch.long), torch.zeros((0,), dtype=torch.long)
    u = edges["u"].map(index).values; v = edges["v"].map(index).values
    r = edges["rel"].values
    ei = np.stack([np.concatenate([u, v]), np.concatenate([v, u])])
    et = np.concatenate([r, r])
    return torch.tensor(ei, dtype=torch.long), torch.tensor(et, dtype=torch.long)

def train_rgcn(edges, node_ids, node_feat, labels, train_mask,
               *, seed=0, epochs=30, lr=1e-2, device="cpu"):
    torch.manual_seed(seed)
    index = {p: i for i, p in enumerate(node_ids)}
    x = _asof_x(node_ids, node_feat, edges)
    ei, et = _edge_index_typed(edges, index)
    y = torch.tensor([float(labels.get(p, 0)) for p in node_ids])
    m = torch.tensor([bool(train_mask.get(p, False)) for p in node_ids])
    model = _RGCN(x.shape[1])
    npos = float(y[m].sum()); nneg = float(m.sum()) - npos
    pw = torch.tensor([nneg / max(npos, 1.0)])
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=pw)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    model.train()
    for _ in range(epochs):
        opt.zero_grad()
        logit = model(x, ei, et)
        loss = loss_fn(logit[m], y[m])
        loss.backward(); opt.step()
    model.eval()
    return model

def asof_risk_rgcn(model, edges, node_ids, node_feat, rows):
    index = {p: i for i, p in enumerate(node_ids)}
    out = np.zeros(len(rows))
    rows = rows.reset_index(drop=True)
    rows["_t"] = pd.to_datetime(rows["t"], utc=True, errors="coerce")
    model.eval()
    with torch.no_grad():
        for t, grp in rows.groupby("_t", sort=True):
            sub = edges[edges["avail_time"] < t]
            x = _asof_x(node_ids, node_feat, sub)
            ei, et = _edge_index_typed(sub, index)
            logit = model(x, ei, et)
            prob = torch.sigmoid(logit).numpy()
            for ridx, pid in zip(grp.index, grp["person_id"]):
                out[ridx] = prob[index[pid]] if pid in index else 0.0
    return out
