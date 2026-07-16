import numpy as np
import pandas as pd
import torch

from gnn import graphmodel_rgcn as gm
from gnn.graphmodel_rgcn import _RGCN
from gnn.learned_cell import _asof_x_caught, _score_pool


SCORING_DAY = pd.Timestamp("2025-01-02T00:00:00Z")


def _explanation_fixture():
    from gnn.sage_explainer import Seed0ExplanationEngine

    torch.manual_seed(0)
    node_ids = ["target", "poolmate", "hop1", "hop2", "future"]
    node_feat = {person_id: np.array([1.0]) for person_id in node_ids}
    edges = pd.DataFrame(
        {
            "source_row_id": [
                "before",
                "cot",
                "cot-duplicate",
                "res",
                "plate",
                "at-boundary",
                "after-boundary",
            ],
            "canonical_pair_group_id": [
                "g0",
                "g1",
                "g1",
                "g2",
                "g3",
                "g4",
                "g5",
            ],
            "u": [
                "future",
                "target",
                "poolmate",
                "poolmate",
                "hop1",
                "target",
                "hop2",
            ],
            "v": [
                "hop1",
                "poolmate",
                "target",
                "hop1",
                "hop2",
                "future",
                "future",
            ],
            "avail_time": pd.to_datetime(
                [
                    "2025-01-01T20:00:00Z",
                    "2025-01-01T01:00:00Z",
                    "2025-01-01T01:30:00Z",
                    "2025-01-01T02:00:00Z",
                    "2025-01-01T03:00:00Z",
                    "2025-01-02T00:00:00Z",
                    "2025-01-02T00:00:01Z",
                ]
            ),
            "rel": [3, 0, 0, 1, 2, 0, 2],
            "edge_type": [
                "SHARED_PLATE_HOT",
                "COTRAVEL",
                "COTRAVEL",
                "RESIDENCE",
                "SHARED_PLATE",
                "COTRAVEL",
                "SHARED_PLATE",
            ],
        }
    )
    caught_times = {
        "hop1": pd.Timestamp("2025-01-01T23:59:59Z"),
        "future": SCORING_DAY,
        "hop2": SCORING_DAY + pd.Timedelta(seconds=1),
    }
    model = _RGCN(in_dim=8, hidden=4, out=4, num_relations=4)
    engine = Seed0ExplanationEngine(
        model=model,
        edges_typed=edges,
        node_ids=node_ids,
        node_feat=node_feat,
        caught_time=caught_times,
        num_rel=4,
    )
    pool = pd.DataFrame(
        {
            "event_id": ["event-target"],
            "primary_obs_id": ["obs-target"],
            "t": [SCORING_DAY + pd.Timedelta(hours=6)],
        }
    )
    production = _score_pool(
        model,
        pool,
        {"obs-target": "target"},
        edges,
        node_ids,
        node_feat,
        caught_times,
        {person_id: i for i, person_id in enumerate(node_ids)},
        num_rel=4,
    )
    return engine, production


def test_snapshot_excludes_edges_and_catches_at_or_after_day_start():
    engine, _ = _explanation_fixture()

    snapshot = engine.snapshot(SCORING_DAY + pd.Timedelta(hours=12))

    active_source_rows = set(snapshot.active_edges.source_row_id)
    assert "at-boundary" not in active_source_rows
    assert "after-boundary" not in active_source_rows
    assert "before" in active_source_rows
    assert snapshot.scoring_day == SCORING_DAY
    assert snapshot.caught_before_snapshot == frozenset({"hop1"})
    assert engine.relationship_categories("target", SCORING_DAY) == ("COTRAVEL",)


def test_snapshot_inputs_do_not_alias_mutable_caller_values():
    from gnn.learned_cell import build_day_snapshot_inputs

    edges = pd.DataFrame(
        {
            "source_row_id": ["row-a"],
            "canonical_pair_group_id": ["group-a"],
            "u": ["p1"],
            "v": ["p2"],
            "avail_time": [pd.Timestamp("2025-01-01T00:00:00Z")],
            "rel": [0],
            "edge_type": ["COTRAVEL"],
        }
    )
    node_ids = ["p1", "p2"]
    node_feat = {person_id: np.array([1.0]) for person_id in node_ids}
    inputs = build_day_snapshot_inputs(
        SCORING_DAY,
        edges,
        node_ids,
        node_feat,
        {},
        {"p1": 0, "p2": 1},
        num_rel=2,
    )

    edges.loc[0, "source_row_id"] = "mutated"
    node_feat["p1"][0] = 99.0

    assert inputs.active_edges.loc[0, "source_row_id"] == "row-a"
    assert inputs.tensor_edge_source_row_ids.tolist() == ["row-a", "row-a"]
    assert inputs.x[0, 0].item() == 1.0


def test_prepool_component_mean_matches_production_probability():
    engine, production = _explanation_fixture()
    snapshot = engine.snapshot(SCORING_DAY)
    target_index = engine.person_index["target"]

    np.testing.assert_allclose(
        snapshot.probabilities[target_index], production[0], rtol=1e-6
    )
    members = np.flatnonzero(
        snapshot.component_roots == snapshot.component_roots[target_index]
    )
    torch.testing.assert_close(
        snapshot.pooled_logits[target_index],
        snapshot.prepool_logits[members].mean(),
    )


def test_duplicate_tensor_edges_have_complete_mirrored_provenance():
    edges = pd.DataFrame(
        {
            "source_row_id": ["row-a", "row-b"],
            "u": ["p1", "p1"],
            "v": ["p2", "p2"],
            "rel": [0, 1],
        }
    )

    edge_index, edge_type, source_rows = gm._edge_index_typed_with_provenance(
        edges, {"p1": 0, "p2": 1}
    )

    assert edge_index.shape[1] == edge_type.shape[0] == source_rows.shape[0]
    assert sorted(source_rows.tolist()) == ["row-a", "row-a", "row-b", "row-b"]
    assert edge_index.tolist() == [[0, 0, 1, 1], [1, 1, 0, 0]]
    assert edge_type.tolist() == [0, 1, 0, 1]


def test_community_contains_complete_pool_and_two_hop_provenance():
    engine, _ = _explanation_fixture()

    community = engine.community("target", SCORING_DAY)

    assert community["complete"] is True
    assert set(community["nodes_by_id"]) == {
        "target",
        "poolmate",
        "hop1",
        "hop2",
        "future",
    }
    assert set(community["base_source_row_ids"]) == {
        "before",
        "cot",
        "cot-duplicate",
        "res",
        "plate",
    }
    assert "at-boundary" not in community["base_source_row_ids"]
    assert "after-boundary" not in community["base_source_row_ids"]
    assert community["provenance_expansions"] == []

    pooled = {
        node["node_id"] for node in community["nodes"] if node["pooled_member"]
    }
    assert pooled == {"target", "poolmate"}
    assert community["nodes_by_id"]["target"]["target"] is True
    assert community["nodes_by_id"]["hop1"]["caught_label_available_time"] == (
        "2025-01-01T23:59:59+00:00"
    )
    assert community["nodes_by_id"]["future"]["caught_label_available_time"] is None

    duplicate_edge = next(edge for edge in community["edges"] if edge["edge_id"].startswith("g1:"))
    assert duplicate_edge["source_row_ids"] == ["cot", "cot-duplicate"]
    assert duplicate_edge["observations"] == [
        {
            "source_row_id": "cot",
            "available_time": "2025-01-01T01:00:00+00:00",
        },
        {
            "source_row_id": "cot-duplicate",
            "available_time": "2025-01-01T01:30:00+00:00",
        },
    ]
    assert duplicate_edge["message_hop"] == 0


def test_community_layout_is_deterministic_and_normalized():
    engine, _ = _explanation_fixture()

    first = engine.community("target", SCORING_DAY)
    second = engine.community("target", SCORING_DAY)

    first_positions = {
        node["node_id"]: (node["x"], node["y"]) for node in first["nodes"]
    }
    second_positions = {
        node["node_id"]: (node["x"], node["y"]) for node in second["nodes"]
    }
    assert first_positions == second_positions
    assert all(
        0.0 <= coordinate <= 1.0
        for position in first_positions.values()
        for coordinate in position
    )


def test_task5_engine_has_no_counterfactual_scaffolding():
    engine, _ = _explanation_fixture()

    assert not hasattr(engine, "_counterfactual_cache")
    assert not hasattr(engine, "score_counterfactual")


def test_caught_feature_names_exactly_align_with_feature_width():
    node_ids = ["p1", "p2"]
    node_feat = {person_id: np.array([1.0]) for person_id in node_ids}
    empty_edges = pd.DataFrame(columns=["u", "v", "avail_time", "rel"])

    x = _asof_x_caught(
        node_ids, node_feat, empty_edges, {}, SCORING_DAY, num_rel=4
    )

    assert gm.caught_feature_names(4) == (
        "bias",
        "degree_cotravel",
        "degree_residence",
        "degree_shared_plate",
        "degree_shared_plate_hot",
        "log1p_cotravel_component_size",
        "log1p_households_spanned",
        "caught_before_snapshot",
    )
    assert len(gm.caught_feature_names(4)) == x.shape[1]
