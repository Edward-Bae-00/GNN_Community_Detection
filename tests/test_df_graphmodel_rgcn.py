import numpy as np
import pandas as pd
import pytest
import torch
from gnn import graphmodel_rgcn as gm
from gnn.learned_cell import build_caught_times

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


def _write_plate_corpus(corpus_dir, rows):
    frame = pd.DataFrame(rows)
    observed = frame[
        [
            "observed_person_record_id",
            "event_id",
            "event_timestamp_utc",
        ]
    ].copy()
    observed["observed_residence_location_id"] = pd.NA
    observed.to_csv(corpus_dir / "observed_person_records.csv", index=False)

    crossing = frame[
        [
            "event_id",
            "observed_person_record_id",
            "vehicle_id",
            "event_timestamp_utc",
            "seizure_flag",
            "label_available_time_utc",
        ]
    ]
    crossing.to_csv(corpus_dir / "crossing_events.csv", index=False)

    return dict(
        zip(frame["observed_person_record_id"], frame["canonical_person_id"])
    )

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


def test_source_provenance_is_deterministic_unique_and_collision_safe():
    collision_separator = "\x1f"
    edges = pd.DataFrame(
        {
            "u": [
                "duplicate|left",
                "duplicate|left",
                f"a{collision_separator}b",
                "a",
                "pair-left",
                "pair-right",
            ],
            "v": [
                "duplicate|right",
                "duplicate|right",
                "c",
                f"b{collision_separator}c",
                "pair-right",
                "pair-left",
            ],
            "avail_time": [
                "2025-01-01T00:00:00Z",
                pd.Timestamp("2024-12-31T19:00:00-05:00"),
                "2025-01-01T00:00:00Z",
                "2025-01-01T00:00:00Z",
                "2025-01-01T00:00:00Z",
                "2025-01-01T00:00:00Z",
            ],
            "edge_type": ["COTRAVEL"] * 6,
            "rel": [0] * 6,
        }
    )

    first = gm._add_edge_provenance(edges)
    second = gm._add_edge_provenance(edges)

    assert first["source_row_id"].tolist() == second["source_row_id"].tolist()
    assert first["source_row_id"].notna().all()
    assert first["source_row_id"].is_unique
    assert first.loc[2, "source_row_id"] != first.loc[3, "source_row_id"]
    assert first.loc[2, "canonical_pair_group_id"] != first.loc[
        3, "canonical_pair_group_id"
    ]
    assert first.loc[4, "canonical_pair_group_id"] == first.loc[
        5, "canonical_pair_group_id"
    ]


def test_source_provenance_rejects_non_string_person_ids():
    edges = pd.DataFrame(
        {
            "u": [1],
            "v": ["1"],
            "avail_time": ["2025-01-01T00:00:00Z"],
            "edge_type": ["COTRAVEL"],
            "rel": [0],
        }
    )

    with pytest.raises(ValueError, match="string"):
        gm._add_edge_provenance(edges)


@pytest.mark.parametrize(
    ("edges", "message"),
    [
        (
            pd.DataFrame({"u": ["p1"], "v": ["p2"], "rel": [0]}),
            "source_row_id",
        ),
        (
            pd.DataFrame(
                {
                    "source_row_id": [None],
                    "u": ["p1"],
                    "v": ["p2"],
                    "rel": [0],
                }
            ),
            "source_row_id",
        ),
        (
            pd.DataFrame(
                {
                    "source_row_id": ["row-a"],
                    "u": ["p1"],
                    "v": ["unknown"],
                    "rel": [0],
                }
            ),
            "unknown",
        ),
    ],
)
def test_tensor_provenance_rejects_missing_null_or_unknown_values(edges, message):
    with pytest.raises(ValueError, match=message):
        gm._edge_index_typed_with_provenance(edges, {"p1": 0, "p2": 1})


def test_empty_tensor_provenance_is_aligned():
    edge_index, edge_type, source_rows = gm._edge_index_typed_with_provenance(
        pd.DataFrame(), {"p1": 0}
    )

    assert edge_index.shape == (2, 0)
    assert edge_type.shape == (0,)
    assert source_rows.shape == (0,)


def test_build_caught_times_uses_earliest_label_availability(tmp_path):
    pd.DataFrame(
        {
            "event_id": ["e1", "e2", "e3", "e4"],
            "detected_flag": [True, True, True, True],
        }
    ).to_csv(tmp_path / "event_ground_truth.csv", index=False)
    pd.DataFrame(
        {
            "event_id": ["e1", "e2", "e3", "e4"],
            "observed_person_record_id": ["r1", "r1", "r2", "unmapped"],
            "event_timestamp_utc": [
                "2024-01-01T00:00:00Z",
                "2024-01-02T00:00:00Z",
                "2024-01-03T00:00:00Z",
                "2024-01-04T00:00:00Z",
            ],
            "label_available_time_utc": [
                "2024-01-03T00:00:00Z",
                "2024-01-04T00:00:00Z",
                pd.NA,
                "2024-01-05T00:00:00Z",
            ],
        }
    ).to_csv(tmp_path / "crossing_events.csv", index=False)

    caught_times = build_caught_times(tmp_path, {"r1": "p1", "r2": "p2"})

    assert caught_times == {"p1": pd.Timestamp("2024-01-03T00:00:00Z")}


def test_hot_plate_waits_for_official_label_availability(tmp_path):
    rows = [
        {
            "event_id": "e1",
            "observed_person_record_id": "r1",
            "canonical_person_id": "p1",
            "vehicle_id": "veh-1",
            "event_timestamp_utc": "2024-01-01T00:00:00Z",
            "seizure_flag": "false",
            "label_available_time_utc": None,
        },
        {
            "event_id": "e2",
            "observed_person_record_id": "r2",
            "canonical_person_id": "p2",
            "vehicle_id": "veh-1",
            "event_timestamp_utc": "2024-01-03T00:00:00Z",
            "seizure_flag": "true",
            "label_available_time_utc": "2024-01-10T00:00:00Z",
        },
        {
            "event_id": "e3",
            "observed_person_record_id": "r3",
            "canonical_person_id": "p3",
            "vehicle_id": "veh-1",
            "event_timestamp_utc": "2024-01-08T00:00:00Z",
            "seizure_flag": "false",
            "label_available_time_utc": None,
        },
        {
            "event_id": "e4",
            "observed_person_record_id": "r4",
            "canonical_person_id": "p4",
            "vehicle_id": "veh-1",
            "event_timestamp_utc": "2024-01-11T00:00:00Z",
            "seizure_flag": "false",
            "label_available_time_utc": None,
        },
    ]
    obs_to_person = _write_plate_corpus(tmp_path, rows)

    edges = gm.build_anchor_graph(obs_to_person, tmp_path, include_plate=True)

    before_label = edges[
        (edges["u"] == "p2")
        & (edges["v"] == "p3")
        & (edges["avail_time"] == pd.Timestamp("2024-01-08T00:00:00Z"))
    ]
    after_label = edges[
        (edges["u"] == "p2")
        & (edges["v"] == "p4")
        & (edges["avail_time"] == pd.Timestamp("2024-01-11T00:00:00Z"))
    ]
    assert len(before_label) == 1
    assert len(after_label) == 1
    assert before_label.iloc[0]["edge_type"] == "SHARED_PLATE"
    assert after_label.iloc[0]["edge_type"] == "SHARED_PLATE_HOT"


def test_hot_plate_at_label_timestamp_is_typed_but_not_active(tmp_path):
    label_time = pd.Timestamp("2024-01-10T00:00:00Z")
    rows = [
        {
            "event_id": "e1",
            "observed_person_record_id": "r1",
            "canonical_person_id": "p1",
            "vehicle_id": "veh-1",
            "event_timestamp_utc": "2024-01-03T00:00:00Z",
            "seizure_flag": "true",
            "label_available_time_utc": label_time.isoformat(),
        },
        {
            "event_id": "e2",
            "observed_person_record_id": "r2",
            "canonical_person_id": "p2",
            "vehicle_id": "veh-1",
            "event_timestamp_utc": label_time.isoformat(),
            "seizure_flag": "false",
            "label_available_time_utc": None,
        },
    ]
    obs_to_person = _write_plate_corpus(tmp_path, rows)

    edges = gm.build_anchor_graph(obs_to_person, tmp_path, include_plate=True)

    follow_up = edges[
        (edges["u"] == "p1")
        & (edges["v"] == "p2")
        & (edges["avail_time"] == label_time)
    ]
    assert len(follow_up) == 1
    assert follow_up.iloc[0]["edge_type"] == "SHARED_PLATE_HOT"

    typed_edges = edges[edges["edge_type"].isin(gm.REL_PLATE)].copy()
    typed_edges["rel"] = typed_edges["edge_type"].map(gm.REL_PLATE)
    node_ids = sorted(set(typed_edges["u"]) | set(typed_edges["v"]))
    node_feat = {person_id: np.array([1.0]) for person_id in node_ids}

    class RecordingModel:
        def __init__(self):
            self.edge_counts = []

        def eval(self):
            return self

        def __call__(self, x, edge_index, edge_type):
            self.edge_counts.append(edge_index.shape[1])
            return torch.zeros(x.shape[0])

    model = RecordingModel()
    gm.asof_risk_rgcn(
        model,
        typed_edges[["u", "v", "avail_time", "rel"]],
        node_ids,
        node_feat,
        pd.DataFrame({"person_id": ["p2"], "t": [label_time]}),
    )
    assert model.edge_counts == [0]


@pytest.mark.parametrize("label_available_time", [None, "not-a-time"])
def test_unavailable_hot_plate_label_never_creates_hot_state(
    tmp_path, label_available_time
):
    rows = [
        {
            "event_id": "e1",
            "observed_person_record_id": "r1",
            "canonical_person_id": "p1",
            "vehicle_id": "veh-1",
            "event_timestamp_utc": "2024-01-03T00:00:00Z",
            "seizure_flag": "true",
            "label_available_time_utc": label_available_time,
        },
        {
            "event_id": "e2",
            "observed_person_record_id": "r2",
            "canonical_person_id": "p2",
            "vehicle_id": "veh-1",
            "event_timestamp_utc": "2024-01-11T00:00:00Z",
            "seizure_flag": "false",
            "label_available_time_utc": None,
        },
    ]
    obs_to_person = _write_plate_corpus(tmp_path, rows)

    edges = gm.build_anchor_graph(obs_to_person, tmp_path, include_plate=True)

    shared_plate = edges[
        (edges["u"] == "p1")
        & (edges["v"] == "p2")
        & (edges["avail_time"] == pd.Timestamp("2024-01-11T00:00:00Z"))
    ]
    assert len(shared_plate) == 1
    assert shared_plate.iloc[0]["edge_type"] == "SHARED_PLATE"
