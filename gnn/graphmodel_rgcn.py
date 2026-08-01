from __future__ import annotations
import hashlib

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


def _stable_digest(*parts) -> str:
    """Hash values with explicit byte lengths so embedded delimiters are safe."""
    digest = hashlib.sha256()
    for part in parts:
        payload = str(part).encode("utf-8")
        digest.update(len(payload).to_bytes(8, byteorder="big", signed=False))
        digest.update(payload)
    return digest.hexdigest()


def _add_edge_provenance(edges: pd.DataFrame) -> pd.DataFrame:
    """Attach stable source-row and unordered typed-pair identifiers."""
    required = {"u", "v", "avail_time", "edge_type"}
    missing = sorted(required.difference(edges.columns))
    if missing:
        raise ValueError(f"edge provenance requires columns: {', '.join(missing)}")

    work = edges.reset_index(drop=True).copy(deep=True)
    work["avail_time"] = pd.to_datetime(
        work["avail_time"], utc=True, errors="raise"
    )
    if work[["u", "v", "avail_time", "edge_type"]].isna().any().any():
        raise ValueError("edge provenance cannot be generated from null values")
    if not work["u"].map(lambda value: isinstance(value, str)).all() or not work[
        "v"
    ].map(lambda value: isinstance(value, str)).all():
        raise ValueError("edge provenance person IDs must be strings")
    work["edge_type"] = work["edge_type"].astype(str)

    occurrence_keys = ["u", "v", "avail_time", "edge_type"]
    work["_source_occurrence"] = work.groupby(
        occurrence_keys, sort=False, dropna=False
    ).cumcount()
    work["source_row_id"] = [
        "edge:"
        + _stable_digest(
            u,
            v,
            pd.Timestamp(available_time).tz_convert("UTC").isoformat(),
            edge_type,
            int(occurrence),
        )
        for u, v, available_time, edge_type, occurrence in work[
            [*occurrence_keys, "_source_occurrence"]
        ].itertuples(index=False, name=None)
    ]
    work["canonical_pair_group_id"] = [
        "pair:" + _stable_digest(*sorted((str(u), str(v))), edge_type)
        for u, v, edge_type in work[["u", "v", "edge_type"]].itertuples(
            index=False, name=None
        )
    ]
    if work["source_row_id"].isna().any():
        raise RuntimeError("generated source_row_id provenance contains null values")
    if work["source_row_id"].duplicated().any():
        raise RuntimeError("generated source_row_id provenance is not unique")
    return work.drop(columns="_source_occurrence")


def caught_feature_names(num_rel):
    """Names aligned exactly to ``learned_cell._asof_x_caught`` columns."""
    num_rel = int(num_rel)
    ordered = sorted(REL_PLATE.items(), key=lambda item: item[1])
    relation_names = [name for name, relation in ordered if relation < num_rel]
    relation_ids = [relation for _, relation in ordered if relation < num_rel]
    if relation_ids != list(range(num_rel)):
        raise ValueError(f"no complete relation-name mapping for num_rel={num_rel}")
    return (
        "bias",
        *(f"degree_{name.lower()}" for name in relation_names),
        "log1p_cotravel_component_size",
        "log1p_households_spanned",
        "caught_before_snapshot",
    )

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
        ce = pd.read_csv(corpus_dir / "crossing_events.csv", usecols=["observed_person_record_id", "vehicle_id", "event_timestamp_utc", "seizure_flag", "label_available_time_utc"])
        ce["identity"] = ce["observed_person_record_id"].map(obs_to_person)
        ce = ce.dropna(subset=["identity", "vehicle_id"])
        ce["avail_time"] = pd.to_datetime(ce["event_timestamp_utc"], utc=True, errors="coerce")
        ce["label_available_time"] = pd.to_datetime(ce["label_available_time_utc"], utc=True, errors="coerce")
        ce["seizure_flag"] = ce["seizure_flag"].astype(str).str.lower().eq("true")
        first_observable_seizure_time = (
            ce.loc[ce["seizure_flag"]]
              .groupby("vehicle_id")["label_available_time"]
              .min()
        )
        
        merged_ce = ce.merge(ce, on="vehicle_id")
        merged_ce = merged_ce[merged_ce["identity_x"] != merged_ce["identity_y"]]
        merged_ce["avail_time"] = merged_ce[["avail_time_x", "avail_time_y"]].max(axis=1)
        merged_ce["edge_type"] = "SHARED_PLATE"
        merged_ce["first_observable_seizure_time"] = merged_ce["vehicle_id"].map(first_observable_seizure_time)
        hot_mask = (
            merged_ce["first_observable_seizure_time"].notna()
            & (merged_ce["avail_time"] >= merged_ce["first_observable_seizure_time"])
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
    e = _add_edge_provenance(e)
    canonical_people = set()
    for person_id in obs_to_person.values():
        if pd.isna(person_id):
            continue
        if not isinstance(person_id, str):
            raise ValueError("oracle canonical person IDs must be strings")
        if not person_id.strip():
            continue
        canonical_people.add(person_id)
    node_ids = sorted(canonical_people)
    unknown_endpoints = sorted(
        (set(e["u"]) | set(e["v"])).difference(canonical_people)
    )
    if unknown_endpoints:
        raise ValueError(
            "typed edge endpoints are outside the canonical person node universe: "
            f"{unknown_endpoints}"
        )
    node_feat = {p: np.array([1.0]) for p in node_ids}
    return e[
        [
            "u",
            "v",
            "avail_time",
            "rel",
            "edge_type",
            "source_row_id",
            "canonical_pair_group_id",
        ]
    ].copy(), node_ids, node_feat

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

def _edge_index_typed_with_provenance(edges, index):
    if not all(isinstance(person_id, str) for person_id in index):
        raise ValueError("typed edge index person IDs must be strings")
    if len(edges) == 0:
        return (
            torch.zeros((2, 0), dtype=torch.long),
            torch.zeros((0,), dtype=torch.long),
            np.zeros((0,), dtype=object),
        )

    required = {"source_row_id", "u", "v", "rel"}
    missing = sorted(required.difference(edges.columns))
    if missing:
        raise ValueError(
            f"typed edges require columns including immutable provenance: "
            f"{', '.join(missing)}"
        )
    if edges[["u", "v"]].isna().any().any():
        raise ValueError("typed edge node endpoints cannot be null")
    if not edges["u"].map(lambda value: isinstance(value, str)).all() or not edges[
        "v"
    ].map(lambda value: isinstance(value, str)).all():
        raise ValueError("typed edge person IDs must be strings")
    unknown_nodes = sorted(
        (set(edges["u"]) | set(edges["v"])).difference(index), key=str
    )
    if unknown_nodes:
        raise ValueError(f"typed edges reference unknown nodes: {unknown_nodes}")
    if edges["source_row_id"].isna().any():
        raise ValueError("typed edge source_row_id provenance cannot be null")
    if not edges["source_row_id"].map(
        lambda value: isinstance(value, str)
    ).all():
        raise ValueError("typed edge source_row_id provenance must be strings")
    source_rows = edges["source_row_id"]
    if source_rows.eq("").any():
        raise ValueError("typed edge source_row_id provenance cannot be empty")
    if source_rows.duplicated().any():
        raise ValueError("typed edge source_row_id provenance must be unique")
    if edges["rel"].isna().any():
        raise ValueError("typed edge relation values cannot be null")

    try:
        relation = edges["rel"].to_numpy(dtype=np.int64, copy=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("typed edge relation values must be integers") from exc
    if not np.array_equal(
        relation.astype(object), edges["rel"].to_numpy(dtype=object, copy=True)
    ):
        raise ValueError("typed edge relation values must be integers")

    u = edges["u"].map(index).to_numpy(dtype=np.int64, copy=True)
    v = edges["v"].map(index).to_numpy(dtype=np.int64, copy=True)
    ei = np.stack([np.concatenate([u, v]), np.concatenate([v, u])])
    et = np.concatenate([relation, relation])
    provenance = np.concatenate(
        [
            source_rows.to_numpy(dtype=object, copy=True),
            source_rows.to_numpy(dtype=object, copy=True),
        ]
    )
    return (
        torch.tensor(ei, dtype=torch.long),
        torch.tensor(et, dtype=torch.long),
        provenance,
    )


def _edge_index_typed(edges, index):
    work = edges
    if len(edges) and "source_row_id" not in edges.columns:
        work = edges.copy(deep=True)
        work["source_row_id"] = [f"legacy-edge:{i}" for i in range(len(work))]
    edge_index, edge_type, _ = _edge_index_typed_with_provenance(work, index)
    return edge_index, edge_type

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
