import json
from types import MappingProxyType, SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import torch

from gnn import graphmodel_rgcn as gm
from gnn.graphmodel_rgcn import _RGCN
from gnn.learned_cell import _asof_x_caught, _score_pool
from gnn.recovery_observability import build_rank_reference
from gnn.sage_explainer import (
    AblationSpec,
    CounterfactualContext,
    build_ablation_specs,
    classify_factor_stability,
    frozen_peer_rank,
    structural_provenance_rows,
    validate_explanation_payload,
)


SCORING_DAY = pd.Timestamp("2025-01-02T00:00:00Z")


def _explanation_fixture(*, return_components=False, rank_reference=None):
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
        rank_reference=rank_reference,
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
    if return_components:
        return (
            engine,
            production,
            (model, edges, node_ids, node_feat, caught_times),
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


def test_snapshot_cache_returns_pristine_defensive_copies():
    engine, _ = _explanation_fixture()
    first = engine.snapshot(SCORING_DAY)
    expected_edges = first.active_edges.copy(deep=True)
    expected_x = first.x.clone()
    expected_edge_index = first.edge_index.clone()
    expected_prepool_logits = first.prepool_logits.clone()
    expected_pooled_logits = first.pooled_logits.clone()
    expected_probabilities = first.probabilities.copy()

    first.active_edges.loc[:, "source_row_id"] = "poisoned"
    first.x.fill_(99.0)
    first.edge_index.fill_(0)
    first.prepool_logits.fill_(99.0)
    first.pooled_logits.fill_(99.0)
    first.probabilities.setflags(write=True)
    first.probabilities.fill(99.0)

    second = engine.snapshot(SCORING_DAY)

    pd.testing.assert_frame_equal(second.active_edges, expected_edges)
    torch.testing.assert_close(second.x, expected_x)
    torch.testing.assert_close(second.edge_index, expected_edge_index)
    torch.testing.assert_close(second.prepool_logits, expected_prepool_logits)
    torch.testing.assert_close(second.pooled_logits, expected_pooled_logits)
    np.testing.assert_array_equal(second.probabilities, expected_probabilities)
    assert second is not first


def test_engine_snapshots_keep_construction_time_model_weights():
    engine, _, components = _explanation_fixture(return_components=True)
    original_model = components[0]
    before_mutation = engine.snapshot(pd.Timestamp("2025-01-03T00:00:00Z"))

    with torch.no_grad():
        for parameter in original_model.parameters():
            parameter.zero_()
        original_model.head.bias.fill_(20.0)

    uncached_day = engine.snapshot(pd.Timestamp("2025-01-04T00:00:00Z"))

    np.testing.assert_allclose(
        uncached_day.probabilities, before_mutation.probabilities, rtol=0, atol=0
    )


def test_score_pool_prepares_snapshot_source_once_for_multiple_days(monkeypatch):
    import gnn.learned_cell as learned_cell

    _, _, components = _explanation_fixture(return_components=True)
    model, edges, node_ids, node_feat, caught_times = components
    original_prepare = learned_cell.prepare_snapshot_source
    prepare_calls = []

    def recording_prepare(*args, **kwargs):
        prepare_calls.append(1)
        return original_prepare(*args, **kwargs)

    monkeypatch.setattr(learned_cell, "prepare_snapshot_source", recording_prepare)
    pool = pd.DataFrame(
        {
            "primary_obs_id": ["obs-target-1", "obs-target-2"],
            "t": pd.to_datetime(
                ["2025-01-02T06:00:00Z", "2025-01-03T06:00:00Z"]
            ),
        }
    )
    scores = _score_pool(
        model,
        pool,
        {"obs-target-1": "target", "obs-target-2": "target"},
        edges,
        node_ids,
        node_feat,
        caught_times,
        {person_id: i for i, person_id in enumerate(node_ids)},
        num_rel=4,
    )

    assert len(scores) == 2
    assert len(prepare_calls) == 1


def test_engine_prepares_snapshot_source_once(monkeypatch):
    import gnn.learned_cell as learned_cell
    from gnn.sage_explainer import Seed0ExplanationEngine

    _, _, components = _explanation_fixture(return_components=True)
    model, edges, node_ids, node_feat, caught_times = components
    original_prepare = learned_cell.prepare_snapshot_source
    prepare_calls = []

    def recording_prepare(*args, **kwargs):
        prepare_calls.append(1)
        return original_prepare(*args, **kwargs)

    monkeypatch.setattr(learned_cell, "prepare_snapshot_source", recording_prepare)
    engine = Seed0ExplanationEngine(
        model=model,
        edges_typed=edges,
        node_ids=node_ids,
        node_feat=node_feat,
        caught_time=caught_times,
        num_rel=4,
    )
    engine.snapshot(SCORING_DAY)
    engine.snapshot(SCORING_DAY + pd.Timedelta(days=1))

    assert len(prepare_calls) == 1


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


def test_community_is_json_serializable():
    engine, _ = _explanation_fixture()

    serialized = json.dumps(engine.community("target", SCORING_DAY))

    assert '"complete": true' in serialized


def test_engine_exposes_counterfactual_scoring_without_mutable_source_state():
    engine, _ = _explanation_fixture()

    assert not hasattr(engine, "_counterfactual_cache")
    assert hasattr(engine, "score_counterfactual")
    assert not hasattr(engine, "edges_typed")
    assert not hasattr(engine, "node_feat")
    assert not hasattr(engine, "model")


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


def _counterfactual_reference(*, blend_weight=0.75):
    return build_rank_reference(
        pd.DataFrame({"event_id": ["target-a", "target-b", "peer-a", "peer-b"]}),
        np.array([0.40, 0.40, 0.60, 0.20]),
        np.array([0.80, 0.80, 0.50, 0.10]),
        blend_weight,
    )


def _counterfactual_context(*, candidates=(0, 1, 2, 3), original_rank=1):
    return CounterfactualContext(
        person_id="target",
        row_index=0,
        scoring_day=SCORING_DAY + pd.Timedelta(hours=12),
        same_day_person_row_indices=(0, 1),
        candidate_row_indices=candidates,
        original_hybrid_rank=original_rank,
    )


def test_ablation_spec_is_frozen_and_canonicalizes_unique_evidence():
    spec = AblationSpec(
        factor_id="pair:g1:rel:0",
        kind="pair_relation",
        edge_source_row_ids=("row-b", "row-a"),
    )

    assert spec.edge_source_row_ids == ("row-a", "row-b")
    with pytest.raises(AttributeError):
        spec.kind = "caught_flag"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"factor_id": " ", "kind": "caught_flag", "caught_person_ids": ("p",)}, "factor_id"),
        ({"factor_id": "x", "kind": "unknown", "edge_source_row_ids": ("row",)}, "unsupported"),
        ({"factor_id": "x", "kind": "pair_relation"}, "edge_source_row_ids"),
        ({"factor_id": "x", "kind": "caught_flag"}, "caught_person_ids"),
        (
            {
                "factor_id": "x",
                "kind": "structural_provenance",
                "edge_source_row_ids": ("row",),
            },
            "provenance_node_ids",
        ),
        (
            {
                "factor_id": "x",
                "kind": "cotravel_pool",
                "edge_source_row_ids": ("row", "row"),
            },
            "duplicate",
        ),
        (
            {
                "factor_id": "x",
                "kind": "caught_flag",
                "caught_person_ids": (1,),
            },
            "strings",
        ),
        (
            {
                "factor_id": "caught:not-a-pair",
                "kind": "pair_relation",
                "edge_source_row_ids": ("row",),
            },
            "factor_id.*pair_relation",
        ),
        (
            {
                "factor_id": "caught:hop1",
                "kind": "caught_flag",
                "edge_source_row_ids": ("row",),
                "caught_person_ids": ("hop1",),
                "provenance_node_ids": ("outside",),
            },
            "exclusive evidence",
        ),
    ],
)
def test_ablation_spec_rejects_invalid_or_incomplete_evidence(kwargs, message):
    with pytest.raises(ValueError, match=message):
        AblationSpec(**kwargs)


def test_counterfactual_context_normalizes_utc_day_and_membership():
    context = _counterfactual_context()

    assert context.scoring_day == SCORING_DAY
    assert context.same_day_person_row_indices == (0, 1)
    assert context.candidate_row_indices == (0, 1, 2, 3)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"row_index": -1}, "row_index"),
        ({"same_day_person_row_indices": (1,)}, "anchor"),
        ({"same_day_person_row_indices": (0, 0)}, "duplicate"),
        ({"candidate_row_indices": (0, 2, 2)}, "duplicate"),
        ({"candidate_row_indices": (0, 2, 3)}, "same-day"),
        ({"original_hybrid_rank": 0}, "positive"),
        ({"original_hybrid_rank": 5}, "candidate"),
    ],
)
def test_counterfactual_context_rejects_invalid_indices(overrides, message):
    values = {
        "person_id": "target",
        "row_index": 0,
        "scoring_day": SCORING_DAY,
        "same_day_person_row_indices": (0, 1),
        "candidate_row_indices": (0, 1, 2, 3),
        "original_hybrid_rank": 1,
    }
    values.update(overrides)

    with pytest.raises(ValueError, match=message):
        CounterfactualContext(**values)


def test_counterfactual_context_rejects_non_scalar_scoring_day():
    with pytest.raises(ValueError, match="scalar timestamp"):
        CounterfactualContext(
            person_id="target",
            row_index=0,
            scoring_day=[SCORING_DAY, SCORING_DAY],
            same_day_person_row_indices=(0,),
            candidate_row_indices=(0,),
            original_hybrid_rank=1,
        )


def test_frozen_peer_rank_updates_all_identity_rows_and_freezes_candidates():
    result = frozen_peer_rank(
        _counterfactual_reference(),
        anchor_row_index=0,
        affected_row_indices=(1, 0),
        ablated_seed0_probability=0.20,
        candidate_row_indices=(0, 1, 2, 3),
        original_hybrid_rank=1,
    )

    assert result["ablated_gnn_percentile"] == pytest.approx(0.625)
    assert result["updated_row_indices"] == [0, 1]
    assert result["unchanged_peer_row_indices"] == [2, 3]
    assert result["ablated_hybrid_rank"] == 2
    assert result["hybrid_rank_delta"] == 1
    assert result["hybrid_rank_delta"] == (
        result["ablated_hybrid_rank"] - result["original_hybrid_rank"]
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"ablated_seed0_probability": np.nan}, "finite"),
        ({"ablated_seed0_probability": 1.1}, r"\[0, 1\]"),
        ({"anchor_row_index": 9}, "out of range"),
        ({"affected_row_indices": (1,)}, "anchor"),
        ({"affected_row_indices": (0, 0)}, "duplicate"),
        ({"candidate_row_indices": (0, 2, 2)}, "duplicate"),
        ({"candidate_row_indices": (1, 2, 3)}, "anchor"),
        ({"candidate_row_indices": (0, 2, 3)}, "affected"),
        ({"original_hybrid_rank": 4, "candidate_row_indices": (0, 1)}, "candidate"),
    ],
)
def test_frozen_peer_rank_rejects_misaligned_inputs(overrides, message):
    values = {
        "reference": _counterfactual_reference(),
        "anchor_row_index": 0,
        "affected_row_indices": (0, 1),
        "ablated_seed0_probability": 0.2,
        "candidate_row_indices": (0, 1, 2, 3),
        "original_hybrid_rank": 1,
    }
    values.update(overrides)

    with pytest.raises(ValueError, match=message):
        frozen_peer_rank(**values)


def test_structural_provenance_expands_components_without_dropping_observations():
    active_edges = pd.DataFrame(
        {
            "source_row_id": ["cot-b", "cot-a", "cot-c", "cot-other", "res-b", "res-a", "res-other"],
            "u": ["a", "a", "b", "x", "c", "f", "x"],
            "v": ["b", "b", "c", "y", "f", "g", "z"],
            "edge_type": ["COTRAVEL"] * 4 + ["RESIDENCE"] * 3,
        }
    )

    rows = structural_provenance_rows(active_edges, {"a"})

    assert rows["source_row_id"].tolist() == [
        "cot-a",
        "cot-b",
        "cot-c",
        "res-a",
        "res-b",
    ]
    assert len(rows.loc[(rows["u"] == "a") & (rows["v"] == "b")]) == 2


def test_ablation_specs_are_deterministic_complete_and_relation_qualified():
    engine, _ = _explanation_fixture()
    snapshot = engine.snapshot(SCORING_DAY)
    community = engine.community("target", SCORING_DAY)
    snapshot.active_edges.loc[len(snapshot.active_edges)] = {
        "source_row_id": "outside-cot",
        "canonical_pair_group_id": "outside-group",
        "u": "poolmate",
        "v": "outside",
        "avail_time": SCORING_DAY - pd.Timedelta(hours=1),
        "rel": 0,
        "edge_type": "COTRAVEL",
    }
    snapshot.active_edges.loc[len(snapshot.active_edges)] = {
        "source_row_id": "outside-res",
        "canonical_pair_group_id": "outside-res-group",
        "u": "outside",
        "v": "res-outside",
        "avail_time": SCORING_DAY - pd.Timedelta(hours=1),
        "rel": 1,
        "edge_type": "RESIDENCE",
    }

    first = build_ablation_specs(snapshot, "target", community)
    second = build_ablation_specs(snapshot, "target", community)

    assert first == second
    assert tuple(spec.factor_id for spec in first) == tuple(
        sorted(spec.factor_id for spec in first)
    )
    pair = next(
        spec
        for spec in first
        if spec.kind == "pair_relation" and spec.factor_id == "pair:g1:rel:0"
    )
    assert pair.edge_source_row_ids == ("cot", "cot-duplicate")
    star = next(spec for spec in first if spec.kind == "relation_star")
    assert star.edge_source_row_ids == ("cot", "cot-duplicate")
    assert any(
        spec.kind == "caught_flag" and spec.caught_person_ids == ("hop1",)
        for spec in first
    )
    structural = next(spec for spec in first if spec.kind == "structural_provenance")
    assert {"outside-cot", "outside-res"}.issubset(
        structural.edge_source_row_ids
    )
    assert structural.provenance_node_ids == ("outside", "res-outside")
    pooling = next(
        spec
        for spec in first
        if spec.kind == "cotravel_pool" and spec.factor_id == "cotravel-pool:g1:rel:0"
    )
    assert pooling.edge_source_row_ids == ("cot", "cot-duplicate")


def test_cotravel_pool_factors_exclude_groups_with_redundant_pair_connectivity():
    active_edges = pd.DataFrame(
        {
            "source_row_id": ["row-a", "row-b"],
            "canonical_pair_group_id": ["group-a", "group-b"],
            "u": ["p1", "p1"],
            "v": ["p2", "p2"],
            "rel": [0, 0],
            "edge_type": ["COTRAVEL", "COTRAVEL"],
        }
    )
    snapshot = SimpleNamespace(
        active_edges=active_edges,
        caught_before_snapshot=frozenset(),
    )
    community = {
        "base_source_row_ids": ["row-a", "row-b"],
        "nodes_by_id": {"p1": {}, "p2": {}},
    }

    specs = build_ablation_specs(snapshot, "p1", community)

    assert not any(spec.kind == "cotravel_pool" for spec in specs)


def test_cotravel_counterfactual_rebuilds_features_pooling_and_component():
    reference = _counterfactual_reference()
    engine, _ = _explanation_fixture(rank_reference=reference)
    community = engine.community("target", SCORING_DAY)
    factor = next(
        spec
        for spec in build_ablation_specs(
            engine.snapshot(SCORING_DAY), "target", community
        )
        if spec.kind == "cotravel_pool"
        and spec.factor_id == "cotravel-pool:g1:rel:0"
    )

    result = engine.score_counterfactual(_counterfactual_context(), factor)

    assert result["factor_id"] == factor.factor_id
    assert result["kind"] == "cotravel_pool"
    assert result["original_component_size"] == 2
    assert result["ablated_component_size"] == 1
    assert result["features_rebuilt"] is True
    assert result["pooling_rebuilt"] is True
    assert result["seed0_probability_delta"] == pytest.approx(
        result["ablated_seed0_probability"]
        - result["original_seed0_probability"]
    )
    assert result["updated_row_indices"] == [0, 1]
    assert result["unchanged_peer_row_indices"] == [2, 3]


def test_caught_counterfactual_removes_caught_feature_and_matches_full_rescore():
    reference = _counterfactual_reference()
    engine, _, components = _explanation_fixture(
        rank_reference=reference, return_components=True
    )
    model, edges, node_ids, node_feat, caught_times = components
    factor = AblationSpec(
        factor_id="caught:hop1",
        kind="caught_flag",
        caught_person_ids=("hop1",),
    )

    result = engine.score_counterfactual(_counterfactual_context(), factor)

    expected = _score_pool(
        model,
        pd.DataFrame(
            {
                "primary_obs_id": ["obs-target"],
                "t": [SCORING_DAY + pd.Timedelta(hours=6)],
            }
        ),
        {"obs-target": "target"},
        edges,
        node_ids,
        node_feat,
        {key: value for key, value in caught_times.items() if key != "hop1"},
        {person_id: index for index, person_id in enumerate(node_ids)},
        num_rel=4,
    )[0]
    assert result["ablated_seed0_probability"] == pytest.approx(expected, rel=1e-6)
    assert result["caught_feature_changes"] == [
        {
            "person_id": "hop1",
            "original_caught_before_snapshot": True,
            "ablated_caught_before_snapshot": False,
        }
    ]


def test_counterfactual_requires_reference_and_rejects_unknown_evidence_ids():
    engine, _ = _explanation_fixture()
    context = _counterfactual_context()

    with pytest.raises(ValueError, match="frozen rank reference"):
        engine.score_counterfactual(
            context,
            AblationSpec(
                factor_id="pair:unknown:rel:0",
                kind="pair_relation",
                edge_source_row_ids=("unknown-row",),
            ),
        )

    engine, _ = _explanation_fixture(rank_reference=_counterfactual_reference())
    with pytest.raises(ValueError, match="incomplete or invalid factor"):
        engine.score_counterfactual(
            context,
            AblationSpec(
                factor_id="pair:unknown:rel:0",
                kind="pair_relation",
                edge_source_row_ids=("unknown-row",),
            ),
        )
    with pytest.raises(ValueError, match="incomplete or invalid factor"):
        engine.score_counterfactual(
            context,
            AblationSpec(
                factor_id="caught:unknown-person",
                kind="caught_flag",
                caught_person_ids=("unknown-person",),
            ),
        )


def test_counterfactual_rejects_caught_ids_that_are_not_graph_nodes():
    from gnn.sage_explainer import Seed0ExplanationEngine

    _, _, components = _explanation_fixture(return_components=True)
    model, edges, node_ids, node_feat, caught_times = components
    caught_times = {**caught_times, "ghost": SCORING_DAY - pd.Timedelta(days=1)}
    engine = Seed0ExplanationEngine(
        model=model,
        edges_typed=edges,
        node_ids=node_ids,
        node_feat=node_feat,
        caught_time=caught_times,
        num_rel=4,
        rank_reference=_counterfactual_reference(),
    )

    with pytest.raises(ValueError, match="incomplete or invalid factor"):
        engine.score_counterfactual(
            _counterfactual_context(),
            AblationSpec(
                factor_id="caught:ghost",
                kind="caught_flag",
                caught_person_ids=("ghost",),
            ),
        )


def test_caught_counterfactual_supports_an_empty_lifetime_graph():
    from gnn.sage_explainer import Seed0ExplanationEngine

    torch.manual_seed(0)
    engine = Seed0ExplanationEngine(
        model=_RGCN(in_dim=8, hidden=4, out=4, num_relations=4),
        edges_typed=pd.DataFrame(
            columns=[
                "source_row_id",
                "canonical_pair_group_id",
                "u",
                "v",
                "avail_time",
                "rel",
                "edge_type",
            ]
        ),
        node_ids=["target"],
        node_feat={"target": np.array([1.0])},
        caught_time={"target": SCORING_DAY - pd.Timedelta(hours=1)},
        num_rel=4,
        rank_reference=build_rank_reference(
            pd.DataFrame({"event_id": ["target-event"]}),
            np.array([0.5]),
            np.array([0.5]),
            0.75,
        ),
    )
    context = CounterfactualContext(
        person_id="target",
        row_index=0,
        scoring_day=SCORING_DAY,
        same_day_person_row_indices=(0,),
        candidate_row_indices=(0,),
        original_hybrid_rank=1,
    )

    result = engine.score_counterfactual(
        context,
        AblationSpec(
            factor_id="caught:target",
            kind="caught_flag",
            caught_person_ids=("target",),
        ),
    )

    assert result["caught_feature_changes"] == [
        {
            "person_id": "target",
            "original_caught_before_snapshot": True,
            "ablated_caught_before_snapshot": False,
        }
    ]


def test_counterfactual_rejects_partial_duplicate_pair_group():
    engine, _ = _explanation_fixture(
        rank_reference=_counterfactual_reference()
    )
    partial = AblationSpec(
        factor_id="pair:g1:rel:0",
        kind="pair_relation",
        edge_source_row_ids=("cot",),
    )

    with pytest.raises(ValueError, match="incomplete or invalid factor"):
        engine.score_counterfactual(_counterfactual_context(), partial)


def test_generated_pair_caught_and_cotravel_factors_are_scoreable():
    engine, _ = _explanation_fixture(
        rank_reference=_counterfactual_reference()
    )
    snapshot = engine.snapshot(SCORING_DAY)
    community = engine.community("target", SCORING_DAY)
    specs_by_kind = {
        spec.kind: spec
        for spec in build_ablation_specs(snapshot, "target", community)
        if spec.kind in {"pair_relation", "caught_flag", "cotravel_pool"}
        and (
            spec.kind == "caught_flag"
            or spec.factor_id.endswith("g1:rel:0")
        )
    }

    assert set(specs_by_kind) == {
        "pair_relation",
        "caught_flag",
        "cotravel_pool",
    }
    for kind in ("pair_relation", "caught_flag", "cotravel_pool"):
        result = engine.score_counterfactual(
            _counterfactual_context(), specs_by_kind[kind]
        )
        assert result["factor_id"] == specs_by_kind[kind].factor_id
        assert result["kind"] == kind


def test_counterfactual_cache_returns_copies_and_separates_candidate_contexts():
    engine, _ = _explanation_fixture(rank_reference=_counterfactual_reference())
    factor = AblationSpec(
        factor_id="caught:hop1",
        kind="caught_flag",
        caught_person_ids=("hop1",),
    )
    full_context = _counterfactual_context()
    first = engine.score_counterfactual(full_context, factor)
    expected = json.loads(json.dumps(first))

    first["factor_id"] = "poisoned"
    first["updated_row_indices"].append(99)
    second = engine.score_counterfactual(full_context, factor)
    shorter = engine.score_counterfactual(
        _counterfactual_context(candidates=(0, 1)), factor
    )

    assert second == expected
    assert shorter["unchanged_peer_row_indices"] == []
    assert second["unchanged_peer_row_indices"] == [2, 3]


@pytest.mark.parametrize(
    "forbidden",
    [
        "hidden",
        "false_negative_flag",
        "organization_id",
        "org_id",
        "ground_truth_community",
        "community_propensity",
        "lifetime_seizures",
        "lifetime_arrests",
        "future_caught",
        "future_edges",
    ],
)
def test_serialization_rejects_every_forbidden_field_case_insensitively(forbidden):
    payload = MappingProxyType(
        {"outer": ({forbidden.swapcase(): [True]},)}
    )

    with pytest.raises(
        ValueError,
        match=rf"forbidden explanation field at root\.outer\[0\]\.{forbidden.swapcase()}",
    ):
        validate_explanation_payload(payload)


def test_serialization_allows_nested_leak_safe_mappings_and_sequences():
    payload = MappingProxyType(
        {"case": ({"factor": "caught:hop1", "values": [1, 2, None]},)}
    )

    assert validate_explanation_payload(payload) is payload


@pytest.mark.parametrize(
    ("delta", "frequency", "iqr", "expected"),
    [
        (-1, 1.0, 0.0, "countervailing"),
        (1, 2 / 3, 0.25, "stable"),
        (1, (2 / 3) - 1e-12, 0.25, "unstable"),
        (1, 2 / 3, 0.2500001, "unstable"),
        (0, 1.0, 0.0, "unstable"),
    ],
)
def test_factor_stability_boundaries(delta, frequency, iqr, expected):
    assert classify_factor_stability(
        {"hybrid_rank_delta": delta}, frequency, iqr
    ) == expected


@pytest.mark.parametrize(
    ("frequency", "iqr", "message"),
    [
        (np.nan, 0.0, "finite"),
        (-0.1, 0.0, r"\[0, 1\]"),
        (1.1, 0.0, r"\[0, 1\]"),
        (0.8, np.inf, "finite"),
        (0.8, -0.1, "nonnegative"),
    ],
)
def test_factor_stability_rejects_invalid_restart_metrics(frequency, iqr, message):
    with pytest.raises(ValueError, match=message):
        classify_factor_stability({"hybrid_rank_delta": 1}, frequency, iqr)
