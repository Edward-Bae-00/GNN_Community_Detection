import numpy as np
import pandas as pd
from gnn import graphmodel_rgcn as gm

def _toy():
    # A-B co-travel early; C-D co-travel late; A,C also each have a RESIDENCE edge.
    edges = pd.DataFrame({
        "u":["A","C","A","C"], "v":["B","D","E","F"],
        "avail_time":pd.to_datetime(["2023-01-01","2024-06-01","2023-01-01","2024-06-01"], utc=True),
        "rel":[0,0,1,1],  # 0=COTRAVEL, 1=RESIDENCE
    })
    node_ids = ["A","B","C","D","E","F"]
    node_feat = {p: np.array([1.0]) for p in node_ids}
    return edges, node_ids, node_feat

def test_asof_masks_future_edges():
    edges, node_ids, node_feat = _toy()
    labels = {p:(1 if p in ("A","B") else 0) for p in node_ids}
    mask = {p: True for p in node_ids}
    model = gm.train_rgcn(edges, node_ids, node_feat, labels, mask, seed=0, epochs=5)
    before = pd.DataFrame({"person_id":["C"], "t":pd.to_datetime(["2024-01-01"], utc=True)})
    after = pd.DataFrame({"person_id":["C"], "t":pd.to_datetime(["2024-12-01"], utc=True)})
    rb = gm.asof_risk_rgcn(model, edges, node_ids, node_feat, before)
    ra = gm.asof_risk_rgcn(model, edges, node_ids, node_feat, after)
    assert rb.shape == (1,) and ra.shape == (1,)
    assert np.isfinite(rb).all() and np.isfinite(ra).all()
    assert not np.isclose(rb[0], ra[0])

def test_asof_features_ignore_future_edges():
    edges, node_ids, node_feat = _toy()
    labels = {p:(1 if p in ("A","B") else 0) for p in node_ids}; mask = {p: True for p in node_ids}
    model = gm.train_rgcn(edges, node_ids, node_feat, labels, mask, seed=0, epochs=5)
    rows = pd.DataFrame({"person_id":["C"], "t":pd.to_datetime(["2024-01-01"], utc=True)})
    edges_no_future = edges[~((edges["u"]=="C"))].copy()  # drop C's future edges
    r_full = gm.asof_risk_rgcn(model, edges, node_ids, node_feat, rows)
    r_wo = gm.asof_risk_rgcn(model, edges_no_future, node_ids, node_feat, rows)
    assert np.isclose(r_full[0], r_wo[0])

def test_build_person_graph_typed_smoke():
    from gnn import config as C
    if not (C.CORPUS_DIR / "crossing_events.csv").exists():
        import pytest; pytest.skip("no corpus")
    edges, node_ids, node_feat = gm.build_person_graph_typed(C.CORPUS_DIR)
    assert len(node_ids) > 0 and len(edges) > 0
    assert set(edges["rel"].unique()) <= {0,1}
    assert (edges["rel"]==0).any()  # some COTRAVEL edges exist


def test_build_anchor_graph_shares_plate_only_after_known_seizure(tmp_path):
    corpus_dir = tmp_path
    obs = pd.DataFrame(
        {
            "observed_person_record_id": ["r1", "r2", "r3"],
            "event_id": ["e1", "e2", "e3"],
            "event_timestamp_utc": [
                "2024-01-01T00:00:00Z",
                "2024-01-02T00:00:00Z",
                "2024-01-03T00:00:00Z",
            ],
            "observed_residence_location_id": [pd.NA, pd.NA, pd.NA],
        }
    )
    obs.to_csv(corpus_dir / "observed_person_records.csv", index=False)

    ce = pd.DataFrame(
        {
            "observed_person_record_id": ["r1", "r2", "r3"],
            "vehicle_id": ["veh-1", "veh-1", "veh-1"],
            "event_timestamp_utc": [
                "2024-01-01T00:00:00Z",
                "2024-01-02T00:00:00Z",
                "2024-01-03T00:00:00Z",
            ],
            "seizure_flag": ["false", "false", "true"],
        }
    )
    ce.to_csv(corpus_dir / "crossing_events.csv", index=False)

    obs_to_person = {"r1": "p1", "r2": "p2", "r3": "p3"}
    edges = gm.build_anchor_graph(obs_to_person, corpus_dir, include_plate=True)

    early = edges[
        (edges["u"] == "p1")
        & (edges["v"] == "p2")
        & (edges["avail_time"] == pd.Timestamp("2024-01-02T00:00:00Z"))
    ]
    late = edges[
        (edges["u"] == "p2")
        & (edges["v"] == "p3")
        & (edges["avail_time"] == pd.Timestamp("2024-01-03T00:00:00Z"))
    ]
    assert len(early) == 1
    assert len(late) == 1
    assert early.iloc[0]["edge_type"] == "SHARED_PLATE"
    assert late.iloc[0]["edge_type"] == "SHARED_PLATE_HOT"
