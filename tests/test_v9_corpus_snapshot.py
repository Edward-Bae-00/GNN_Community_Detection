"""V9 designed-signal corpus snapshot property tests."""
from collections import defaultdict
from pathlib import Path

import pandas as pd

from gnn.graphmodel_rgcn import build_person_graph_typed


REPO = Path(__file__).resolve().parents[1]
V9 = REPO / "Documents" / "Data" / "synthetic_cbp_graph_corpus_v9"
V9DEV = REPO / "Documents" / "Data" / "synthetic_cbp_graph_corpus_v9dev"


def _truthy(series):
    return series.astype(str).str.lower().eq("true")


def test_v9dev_core_files_and_org_layer():
    for f in ["crossing_events.csv", "event_ground_truth.csv", "edges.csv",
              "observed_person_records.csv", "org_membership_ground_truth.csv",
              "train_valid_test_splits.csv", "seizures.csv", "arrests.csv"]:
        assert (V9DEV / f).exists(), f
    org = pd.read_csv(V9DEV / "org_membership_ground_truth.csv")
    assert len(org) > 0 and {"person_id", "is_observable"} <= set(org.columns)


def test_v9dev_cotravel_is_dense():
    e = pd.read_csv(V9DEV / "edges.csv", usecols=["edge_type", "weight"])
    assoc = e[e.edge_type == "PERSON_ASSOCIATED_WITH_PERSON"]
    assert len(assoc) > 0
    # denser co-travel => a non-trivial share of pairs co-travelled repeatedly
    assert (assoc["weight"] >= 2).mean() > 0.15


def test_v9dev_cotravel_edges_start_at_first_shared_crossing():
    ce = pd.read_csv(
        V9DEV / "crossing_events.csv",
        usecols=["event_timestamp_utc", "primary_person_id", "co_traveler_person_ids"],
    )
    first_seen = {}
    for row in ce.itertuples(index=False):
        if not isinstance(row.co_traveler_person_ids, str) or not row.co_traveler_person_ids:
            continue
        t = pd.Timestamp(row.event_timestamp_utc)
        for co_id in row.co_traveler_person_ids.split(";"):
            pair = tuple(sorted((row.primary_person_id, co_id)))
            first_seen[pair] = min(t, first_seen.get(pair, t))

    assoc = pd.read_csv(
        V9DEV / "edges.csv",
        usecols=[
            "source_node_id",
            "target_node_id",
            "edge_type",
            "edge_timestamp_utc",
            "first_seen_timestamp_utc",
            "temporal_valid_from_utc",
            "feature_available_time_utc",
        ],
    )
    assoc = assoc[assoc["edge_type"] == "PERSON_ASSOCIATED_WITH_PERSON"]
    assert len(assoc) > 0

    observed = defaultdict(list)
    for row in assoc.itertuples(index=False):
        pair = tuple(sorted((row.source_node_id, row.target_node_id)))
        observed[pair].append(row)

    assert not (set(observed) - set(first_seen))
    for pair, rows in observed.items():
        expected = first_seen[pair]
        for row in rows:
            for column in [
                "edge_timestamp_utc",
                "first_seen_timestamp_utc",
                "temporal_valid_from_utc",
                "feature_available_time_utc",
            ]:
                assert pd.Timestamp(getattr(row, column)) == expected


def test_v9dev_catch_rate_and_fn_pool():
    # Catches are deliberately concentrated in cells (anchors). A higher overall rate
    # would require catching lone/benign carriers, which pollutes the RGCN and destroys
    # the GNN win, so the snapshot rate sits around 4%.
    ce = pd.read_csv(V9DEV / "crossing_events.csv", usecols=["seizure_flag"])
    rate = _truthy(ce["seizure_flag"]).mean()
    assert 0.02 <= rate <= 0.07, f"catch rate {rate:.3f} outside expected 2-7%"
    egt = pd.read_csv(V9DEV / "event_ground_truth.csv",
                      usecols=["false_negative_flag"])
    fn = _truthy(egt["false_negative_flag"]).mean()
    assert fn > 0.02, f"hidden-carrier pool too small ({fn:.3f})"


def test_v9dev_cotravel_reaches_demo_graph():
    # REGRESSION GUARD: the demo RGCN derives COTRAVEL from >=2 observed records
    # sharing an event_id, so the co-travel rail must be populated in the built graph.
    e, node_ids, _ = build_person_graph_typed(V9DEV, substrate="oracle", include_plate=True)
    counts = e["rel"].value_counts().to_dict()
    assert counts.get(0, 0) > 0, f"no COTRAVEL (rel 0) edges in demo graph: {counts}"


def test_full_v9_demo_graph_has_complete_person_universe_and_stable_edges():
    edges, node_ids, _ = build_person_graph_typed(
        V9, substrate="oracle", include_plate=True
    )

    assert len(node_ids) == 120_000
    assert edges["rel"].value_counts().to_dict() == {
        0: 504_358,
        1: 2_016_084,
        2: 107_856,
        3: 11_174,
    }


def test_v9dev_shared_plates_and_lone_tail():
    ce = pd.read_csv(V9DEV / "crossing_events.csv",
                     usecols=["primary_person_id", "vehicle_id"])
    ce = ce[ce["vehicle_id"].astype(str) != ""]
    # some vehicles are reused across many crossings by >1 person (shared plates)
    per_veh_people = ce.groupby("vehicle_id")["primary_person_id"].nunique()
    per_veh_uses = ce.groupby("vehicle_id").size()
    shared = ((per_veh_people >= 2) & (per_veh_uses >= 4)).sum()
    assert shared > 0, "no strongly shared plates"

    # lone-smuggler tail preserved: many hidden carriers are NOT in any org
    egt = pd.read_csv(V9DEV / "event_ground_truth.csv",
                      usecols=["primary_person_id", "false_negative_flag"])
    org = pd.read_csv(V9DEV / "org_membership_ground_truth.csv",
                      usecols=["person_id"])
    fn = egt[_truthy(egt["false_negative_flag"])]
    lone_frac = (~fn["primary_person_id"].isin(set(org["person_id"]))).mean()
    assert lone_frac > 0.3, f"lone-carrier fraction too low ({lone_frac:.2f})"
