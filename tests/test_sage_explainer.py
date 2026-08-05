import json
import hashlib
import multiprocessing
import resource
import sys
import tracemalloc
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import torch

from gnn import graphmodel_rgcn as gm
from gnn import learned_cell
from gnn import observability_artifact as oa
from gnn import sage_explainer as se
from gnn.explanation_narrative import MODEL_TAG, render_template
from gnn.graphmodel_alt import _SAGE
from gnn.graphmodel_rgcn import _RGCN
from gnn.learned_cell import _asof_x_caught, _score_pool
from gnn.recovery_observability import (
    HybridOnlyCase,
    RecoveryAnchor,
    build_decision_trace,
    build_rank_reference,
)
from gnn.recovery_bundle import RecoveryBundleWriter
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


def _explanation_fixture(*, return_components=False, bind_rank_reference=False):
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
    constructor_kwargs = {}
    if bind_rank_reference:
        constructor_kwargs = {
            "rank_reference": _counterfactual_reference(
                target_probability=float(production[0])
            ),
            "rank_row_bindings": _counterfactual_row_bindings(),
        }
    engine = Seed0ExplanationEngine(
        model=model,
        edges_typed=edges,
        node_ids=node_ids,
        node_feat=node_feat,
        caught_time=caught_times,
        num_rel=4,
        **constructor_kwargs,
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


def test_relationship_categories_filters_prepared_edges_without_snapshot(
    monkeypatch,
):
    engine, _ = _explanation_fixture()

    def forbidden_snapshot(scoring_day):
        raise AssertionError("relationship categories must not build a snapshot")

    monkeypatch.setattr(engine, "snapshot", forbidden_snapshot)

    assert engine.relationship_categories(
        "target", SCORING_DAY + pd.Timedelta(hours=12)
    ) == ("COTRAVEL",)
    assert engine.relationship_categories("future", SCORING_DAY) == (
        "SHARED_PLATE_HOT",
    )
    assert engine.relationship_categories(
        "target", SCORING_DAY - pd.Timedelta(days=1)
    ) == ()
    with pytest.raises(KeyError, match="unknown person_id: missing"):
        engine.relationship_categories("missing", SCORING_DAY)


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
    nodes = list(community.iter_nodes())
    edges = list(community.iter_edges())
    provenance = list(community.iter_provenance())
    nodes_by_id = {node["node_id"]: node for node in nodes}

    assert community.complete is True
    assert community.scoring_day.isoformat() == "2025-01-02T00:00:00+00:00"
    assert community.component_id.startswith("component:sha256:")
    assert community.community_key.startswith("community:sha256:")
    poolmate_view = engine.community("poolmate", SCORING_DAY)
    assert poolmate_view.component_id == community.component_id
    assert poolmate_view.community_key == community.community_key
    assert poolmate_view is not community
    poolmate_nodes_by_id = {
        node["node_id"]: node for node in poolmate_view.iter_nodes()
    }
    assert poolmate_nodes_by_id["target"]["target"] is False
    assert poolmate_nodes_by_id["poolmate"]["target"] is True
    assert set(nodes_by_id) == {
        "target",
        "poolmate",
        "hop1",
        "hop2",
        "future",
    }
    assert {row["source_row_id"] for row in provenance} == {
        "before",
        "cot",
        "cot-duplicate",
        "res",
        "plate",
    }
    assert "at-boundary" not in {row["source_row_id"] for row in provenance}
    assert "after-boundary" not in {row["source_row_id"] for row in provenance}

    pooled = {
        node["node_id"] for node in nodes if node["pooled_member"]
    }
    assert pooled == {"target", "poolmate"}
    assert nodes_by_id["target"]["target"] is True
    assert all(
        node["target"] is (node["node_id"] == "target") for node in nodes
    )
    assert nodes_by_id["hop1"]["caught_label_available_time"] == (
        "2025-01-01T23:59:59+00:00"
    )
    assert nodes_by_id["future"]["caught_label_available_time"] is None

    duplicate_edge = next(edge for edge in edges if edge["edge_id"].startswith("g1:"))
    assert duplicate_edge["source_row_ids"] == ["cot", "cot-duplicate"]
    assert [
        {key: row[key] for key in ("source_row_id", "available_time")}
        for row in provenance
        if row["edge_id"] == duplicate_edge["edge_id"]
    ] == [
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
        node["node_id"]: (node["x"], node["y"]) for node in first.iter_nodes()
    }
    second_positions = {
        node["node_id"]: (node["x"], node["y"]) for node in second.iter_nodes()
    }
    assert first_positions == second_positions
    assert all(
        0.0 <= coordinate <= 1.0
        for position in first_positions.values()
        for coordinate in position
    )


def test_same_component_cache_switches_target_flags_per_requested_subject():
    engine, _ = _explanation_fixture()

    target_scope = engine.community("target", SCORING_DAY)
    poolmate_scope = engine.community("poolmate", SCORING_DAY)
    target_nodes = {
        node["node_id"]: node["target"]
        for node in target_scope.iter_nodes()
    }
    poolmate_nodes = {
        node["node_id"]: node["target"]
        for node in poolmate_scope.iter_nodes()
    }

    assert target_scope is not poolmate_scope
    assert target_scope.community_key == poolmate_scope.community_key
    assert target_nodes["target"] is True
    assert target_nodes["poolmate"] is False
    assert poolmate_nodes["target"] is False
    assert poolmate_nodes["poolmate"] is True


def test_same_component_caches_request_specific_scopes_until_day_release(
    monkeypatch,
):
    engine, _ = _explanation_fixture()
    original_builder = se.build_complete_community
    calls = []

    def counted_builder(*args, **kwargs):
        calls.append((args[1], pd.Timestamp(args[2])))
        return original_builder(*args, **kwargs)

    monkeypatch.setattr(se, "build_complete_community", counted_builder)

    target = engine.community("target", SCORING_DAY)
    before = (
        list(target.iter_nodes()),
        list(target.iter_edges()),
        list(target.iter_provenance()),
    )
    poolmate = engine.community("poolmate", SCORING_DAY)

    assert target is not poolmate
    assert len(calls) == 2

    assert engine.release_snapshot(SCORING_DAY) is True
    rebuilt = engine.community("target", SCORING_DAY)
    assert rebuilt is not target
    assert (
        list(rebuilt.iter_nodes()),
        list(rebuilt.iter_edges()),
        list(rebuilt.iter_provenance()),
    ) == before
    assert len(calls) == 3


def test_community_layout_never_uses_networkx_spring_layout(monkeypatch):
    engine, _ = _explanation_fixture()

    monkeypatch.setattr(
        se.nx,
        "spring_layout",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("spring layout must not run")
        ),
    )

    community = engine.community("target", SCORING_DAY)

    assert list(community.iter_nodes())


def test_release_snapshot_evicts_day_bound_heavy_caches():
    engine, _ = _explanation_fixture()
    first_day = pd.Timestamp("2025-01-01T00:00:00Z")

    engine.snapshot(first_day)
    engine.snapshot(SCORING_DAY)
    assert engine.cached_snapshot_days == (first_day, SCORING_DAY)

    assert engine.release_snapshot(first_day) is True
    assert engine.cached_snapshot_days == (SCORING_DAY,)
    assert engine.release_snapshot(first_day) is False


def test_observability_fingerprint_material_is_compact_and_deterministic():
    engine, _ = _explanation_fixture(bind_rank_reference=True)

    first = engine.observability_fingerprint_material()
    second = engine.observability_fingerprint_material()

    assert first == second
    assert set(first) == {
        "graph_sha256",
        "model_state_sha256",
        "rank_reference_fingerprint",
    }
    assert all(value for value in first.values())


def test_community_scope_does_not_materialize_as_nested_json():
    engine, _ = _explanation_fixture()

    with pytest.raises(TypeError, match="CommunityScope"):
        json.dumps(engine.community("target", SCORING_DAY))


def test_community_scope_replays_fresh_deterministic_streams():
    engine, _ = _explanation_fixture()

    scope = engine.community("target", SCORING_DAY)
    first_nodes = list(scope.iter_nodes())
    second_nodes = list(scope.iter_nodes())
    first_edges = list(scope.iter_edges())
    second_edges = list(scope.iter_edges())
    first_provenance = list(scope.iter_provenance())
    second_provenance = list(scope.iter_provenance())

    assert isinstance(scope, se.CommunityScope)
    assert first_nodes == second_nodes
    assert first_edges == second_edges
    assert first_provenance == second_provenance
    assert scope.iter_nodes() is not scope.iter_nodes()
    assert scope.iter_edges() is not scope.iter_edges()
    assert scope.iter_provenance() is not scope.iter_provenance()
    assert [node["node_id"] for node in first_nodes] == sorted(
        node["node_id"] for node in first_nodes
    )
    assert [edge["edge_id"] for edge in first_edges] == sorted(
        edge["edge_id"] for edge in first_edges
    )
    assert {row["source_row_id"] for row in first_provenance} == {
        source_row_id
        for edge in first_edges
        for source_row_id in edge["source_row_ids"]
    }


def test_community_scope_retains_compact_state_for_more_than_100k_display_edges():
    edge_count = 100_001
    active_edges = pd.DataFrame(
        {
            "source_row_id": [f"row:{index:06d}" for index in range(edge_count)],
            "u": ["p1"] * edge_count,
            "v": ["p2"] * edge_count,
            "rel": np.zeros(edge_count, dtype=np.int8),
            "edge_type": ["COTRAVEL"] * edge_count,
            "canonical_pair_group_id": [
                f"group:{index:06d}" for index in range(edge_count)
            ],
            "avail_time": pd.Timestamp("2025-01-01T00:00:00Z"),
        }
    )
    snapshot = SimpleNamespace(
        active_edges=active_edges,
        caught_before_snapshot=frozenset(),
    )
    engine = SimpleNamespace(
        person_index={"p1": 0, "p2": 1},
        community_snapshot=lambda scoring_day: snapshot,
        caught_available_time=lambda person_id: None,
    )
    scope = se.CommunityScope(
        engine=engine,
        scoring_day=pd.Timestamp("2025-01-02T00:00:00Z"),
        component_id="component:large",
        community_key="community:large",
        node_ids=("p1", "p2"),
        node_indices=np.array([0, 1], dtype=np.int64),
        message_distances=np.array([0, 0], dtype=np.int8),
        pooled_members=np.array([True, True]),
        edge_row_indices=np.arange(edge_count, dtype=np.int64),
        edge_group_starts=np.arange(edge_count, dtype=np.int64),
    )

    retained_arrays = (
        scope.node_indices,
        scope.message_distances,
        scope.pooled_members,
        scope.edge_row_indices,
        scope.edge_group_starts,
    )
    assert sum(array.nbytes for array in retained_arrays) < 2_000_000
    assert not any(isinstance(value, (dict, list, set)) for value in vars(scope).values())
    assert sum(1 for _ in scope.iter_edges()) == edge_count
    assert sum(1 for _ in scope.iter_edges()) == edge_count
    assert sys.getsizeof(scope) < 1_024

    local = scope.materialize_local(
        ("p1", "p2"), (), target_person_id="p1"
    )
    assert len(local["nodes"]) <= se.MAX_LOCAL_EXPLANATION_NODES
    assert len(local["edges"]) == se.MAX_LOCAL_EXPLANATION_EDGES
    assert all(
        len(edge["source_row_ids"]) <= se.MAX_LOCAL_SOURCE_ROWS_PER_EDGE
        for edge in local["edges"]
    )
    assert local["projection_policy"] == {
        "max_nodes": se.MAX_LOCAL_EXPLANATION_NODES,
        "max_edges": se.MAX_LOCAL_EXPLANATION_EDGES,
        "max_source_rows_per_edge": se.MAX_LOCAL_SOURCE_ROWS_PER_EDGE,
        "node_order": "target_then_pooled_caught_salience_then_hop_then_id",
        "edge_order": "target_incident_then_hop_then_id",
    }


def test_flow_stages_use_compact_rules_instead_of_membership_copies():
    community = {
        "nodes_by_id": {
            "target": {"pooled_member": True},
            "neighbor": {"pooled_member": True},
        },
        "edges": [
            {
                "edge_id": "edge:1",
                "u": "target",
                "v": "neighbor",
                "edge_type": "COTRAVEL",
                "message_hop": 1,
            }
        ],
    }

    stages = se.build_flow_stages(community)

    assert [stage["stage_id"] for stage in stages] == [
        "first_hop",
        "second_hop",
        "component_pool",
        "rank_fusion",
    ]
    assert all("node_ids" not in stage and "edge_ids" not in stage for stage in stages)
    assert stages[0]["edge_rule"] == {"max_message_hop": 1}
    assert stages[2]["edge_rule"] == {
        "edge_type": "COTRAVEL",
        "both_pooled_members": True,
    }


def _legacy_large_structural_bundle_helper_is_bounded_and_complete(
    tmp_path, monkeypatch
):
    edge_count = 100_001
    scoring_day = pd.Timestamp("2025-01-02T00:00:00Z")
    edges = pd.DataFrame(
        {
            "source_row_id": [f"row:{index:06d}" for index in range(edge_count)],
            "canonical_pair_group_id": [
                f"group:{index:06d}" for index in range(edge_count)
            ],
            "u": ["target"] * edge_count,
            "v": ["poolmate"] * edge_count,
            "avail_time": scoring_day - pd.Timedelta(hours=1),
            "rel": np.zeros(edge_count, dtype=np.int8),
            "edge_type": ["COTRAVEL"] * edge_count,
        }
    )
    engine = se.Seed0ExplanationEngine(
        model=_SAGE(in_dim=8, hidden=4, out=4, num_relations=4),
        edges_typed=edges,
        node_ids=["target", "poolmate"],
        node_feat={
            "target": np.array([1.0]),
            "poolmate": np.array([0.5]),
        },
        caught_time={"poolmate": scoring_day - pd.Timedelta(hours=2)},
        num_rel=4,
    )
    snapshot = engine.snapshot(scoring_day)
    probability = float(snapshot.probabilities[engine.person_index["target"]])
    reference = _counterfactual_reference(target_probability=probability)
    engine.bind_rank_reference(reference, _counterfactual_row_bindings())
    trace = build_decision_trace(
        reference,
        row_index=0,
        baseline_candidate_row_indices=(0, 1, 2, 3),
        hybrid_candidate_row_indices=(0, 1, 2, 3),
        daily_budget=5,
    )
    case = HybridOnlyCase(
        person_id="target",
        anchor=RecoveryAnchor(
            person_id="target",
            event_id="target-a",
            row_index=0,
            scoring_day=scoring_day,
            inspected_rank=1,
        ),
        baseline_rank=trace["baseline_rank"],
        gnn_rank=trace["seed0_gnn_rank"],
        hybrid_rank=trace["seed0_hybrid_rank"],
        baseline_percentile=trace["baseline_percentile"],
        gnn_percentile=trace["seed0_gnn_percentile"],
        relationship_categories=("COTRAVEL",),
        scoring_period="2025-01",
        same_day_person_row_indices=(0, 1),
        baseline_candidate_row_indices=(0, 1, 2, 3),
        hybrid_candidate_row_indices=(0, 1, 2, 3),
        decision_trace=trace,
    )

    def bounded_member_explainer(
        bound_engine, person_id, day, *, restart_seeds, epochs
    ):
        local = se.member_subgraph(bound_engine, person_id, day)
        logit = float(
            bound_engine.snapshot(day).prepool_logits[
                bound_engine.person_index[person_id]
            ]
        )
        return {
            "edge_masks": tuple(
                np.zeros(len(local.tensor_edge_source_row_ids), dtype=float)
                for _ in restart_seeds
            ),
            "node_feature_masks": tuple(
                np.ones(tuple(local.x.shape), dtype=float) for _ in restart_seeds
            ),
            "restart_seeds": tuple(restart_seeds),
            "local_prepool_logit": logit,
            "full_prepool_logit": logit,
            "status": "ok",
        }

    monkeypatch.setattr(
        se,
        "diagnostic_edge_source_set_probability",
        lambda *args, **kwargs: probability,
    )
    monkeypatch.setattr(
        engine,
        "score_counterfactual",
        lambda context, factor: {
            "factor_id": factor.factor_id,
            "kind": factor.kind,
            "original_hybrid_rank": context.original_hybrid_rank,
            "ablated_hybrid_rank": context.original_hybrid_rank,
            "hybrid_rank_delta": 0,
        },
    )

    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    tracemalloc.start()
    scope = engine.community("target", scoring_day)
    explanation = se.compose_case_explanation(
        engine, case, member_explainer=bounded_member_explainer
    )
    writer = RecoveryBundleWriter(
        tmp_path / "stage",
        tmp_path / "published",
        run_fingerprint="large-structural-bundle-helper",
        chunk_size=1_000,
    )
    community_ref = writer.write_community(
        {
            "complete": True,
            "scoring_day": scope.scoring_day.isoformat(),
            "component_id": scope.component_id,
            "community_key": scope.community_key,
            "nodes": scope.iter_nodes(),
            "edges": scope.iter_edges(),
            "provenance_observations": scope.iter_provenance(),
            "provenance_expansions": iter(()),
        }
    )
    writer.write_case(
        "baseline_only",
        {
            "case_id": "case:target",
            "person_id": "target",
            "event_id": "target-a",
            "scoring_day": scoring_day.isoformat(),
            "community_key": scope.community_key,
        },
    )
    manifest = writer.finalize(
        expected_hybrid_case_ids=set(),
        expected_baseline_case_ids={"case:target"},
        policy={"inspections_per_day": 5},
        summary={},
    )
    _, peak_tracemalloc = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    bundle_root = tmp_path / "published" / manifest["bundle_path"]
    files = [path for path in bundle_root.rglob("*") if path.is_file()]
    physical_bytes = sum(path.stat().st_size for path in files)
    community_manifest = json.loads(
        (bundle_root / community_ref["path"]).read_text(encoding="utf-8")
    )

    assert isinstance(scope, se.CommunityScope)
    assert len(explanation["community"]["nodes"]) <= se.MAX_LOCAL_EXPLANATION_NODES
    assert len(explanation["community"]["edges"]) <= se.MAX_LOCAL_EXPLANATION_EDGES
    assert len(explanation["attributions"]["node_feature_mask_stats"]) <= (
        se.MAX_NODE_FEATURE_MASK_STATS
    )
    assert len(explanation["stability"]["edge_restart_aggregate"]["median"]) <= (
        se.MAX_LOCAL_EXPLANATION_EDGES
    )
    assert community_manifest["node_count"] == 2
    assert community_manifest["edge_count"] == edge_count
    assert community_manifest["provenance_observation_count"] == edge_count
    assert manifest["coverage"]["complete"] is True
    assert peak_tracemalloc < 512 * 1024 * 1024
    assert physical_bytes < 512 * 1024 * 1024
    assert len(files) < 2_000
    assert rss_after >= rss_before
    assert {
        "peak_tracemalloc_bytes": peak_tracemalloc,
        "peak_rss_before": rss_before,
        "peak_rss_after": rss_after,
        "physical_bytes": physical_bytes,
        "file_count": len(files),
    }


def _rss_bytes():
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _walk_reference_closure(pointer_path, bundle_root):
    pointer_path = Path(pointer_path)
    bundle_root = Path(bundle_root)
    published_root = pointer_path.parent
    visited = set()
    verified_references = 0

    def load(path, expected=None):
        nonlocal verified_references
        path = path.resolve()
        content = path.read_bytes()
        if expected is not None:
            assert len(content) == expected["bytes"]
            assert hashlib.sha256(content).hexdigest() == expected["sha256"]
            verified_references += 1
        if path in visited:
            return None
        visited.add(path)
        if path.suffix != ".json":
            return None
        payload = json.loads(content)
        return payload

    def resolve(reference):
        relative = Path(reference["path"])
        for base in (bundle_root, published_root, pointer_path.parent):
            candidate = base / relative
            if candidate.is_file():
                return candidate
        raise AssertionError(f"unresolved reference {relative}")

    def walk(value):
        if isinstance(value, dict):
            if {
                "path",
                "sha256",
                "bytes",
            }.issubset(value) and isinstance(value["path"], str):
                payload = load(resolve(value), value)
                if payload is not None:
                    walk(payload)
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    pointer = load(pointer_path)
    manifest_path = bundle_root / "manifest.json"
    manifest = load(manifest_path)
    manifest_digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert pointer["manifest_sha256"] == manifest_digest
    walk(pointer)
    walk(manifest)
    bundle_json = {
        path.resolve() for path in bundle_root.rglob("*.json") if path.is_file()
    }
    assert bundle_json.issubset(visited)
    assert verified_references > 0
    return {
        "verified_reference_count": verified_references,
        "verified_file_count": len(visited),
        "pointer_sha256": hashlib.sha256(pointer_path.read_bytes()).hexdigest(),
        "manifest_sha256": manifest_digest,
    }


def _exact_limit_structural_control_worker(root_value, metrics_path_value):
    """Exercise over-limit compose rejection and structural-control helpers."""
    root = Path(root_value)
    metrics_path = Path(metrics_path_value)
    tracemalloc.start()
    rss_before = _rss_bytes()
    scoring_day = pd.Timestamp("2025-01-02T00:00:00Z")
    display_edge_count = 1_001
    duplicate_observations = 20
    group_ids = ["group:000000"] * duplicate_observations + [
        f"group:{index:06d}" for index in range(1, display_edge_count)
    ]
    raw_row_count = len(group_ids)
    edges = pd.DataFrame(
        {
            "source_row_id": [f"row:{index:06d}" for index in range(raw_row_count)],
            "canonical_pair_group_id": group_ids,
            "u": ["target"] * raw_row_count,
            "v": ["poolmate"] * raw_row_count,
            "avail_time": scoring_day - pd.Timedelta(hours=1),
            "rel": np.zeros(raw_row_count, dtype=np.int8),
            "edge_type": ["COTRAVEL"] * raw_row_count,
        }
    )
    engine = se.Seed0ExplanationEngine(
        model=_SAGE(in_dim=8, hidden=4, out=4, num_relations=4),
        edges_typed=edges,
        node_ids=["target", "poolmate"],
        node_feat={"target": np.array([1.0]), "poolmate": np.array([0.5])},
        caught_time={"poolmate": scoring_day - pd.Timedelta(hours=2)},
        num_rel=4,
    )
    snapshot = engine.snapshot(scoring_day)
    probability = float(snapshot.probabilities[engine.person_index["target"]])
    reference = _counterfactual_reference(target_probability=probability)
    engine.bind_rank_reference(reference, _counterfactual_row_bindings())
    trace = build_decision_trace(
        reference,
        row_index=0,
        baseline_candidate_row_indices=(0, 1, 2, 3),
        hybrid_candidate_row_indices=(0, 1, 2, 3),
        daily_budget=5,
    )
    case = HybridOnlyCase(
        person_id="target",
        anchor=RecoveryAnchor(
            person_id="target",
            event_id="target-a",
            row_index=0,
            scoring_day=scoring_day,
            inspected_rank=1,
        ),
        baseline_rank=trace["baseline_rank"],
        gnn_rank=trace["seed0_gnn_rank"],
        hybrid_rank=trace["seed0_hybrid_rank"],
        baseline_percentile=trace["baseline_percentile"],
        gnn_percentile=trace["seed0_gnn_percentile"],
        relationship_categories=("COTRAVEL",),
        scoring_period="2025-01",
        same_day_person_row_indices=(0, 1),
        baseline_candidate_row_indices=(0, 1, 2, 3),
        hybrid_candidate_row_indices=(0, 1, 2, 3),
        decision_trace=trace,
    )

    def bounded_member_explainer(
        bound_engine, person_id, day, *, restart_seeds, epochs
    ):
        local = se.member_subgraph(bound_engine, person_id, day)
        logit = float(
            bound_engine.snapshot(day).prepool_logits[
                bound_engine.person_index[person_id]
            ]
        )
        return {
            "edge_masks": tuple(
                np.zeros(len(local.tensor_edge_source_row_ids), dtype=float)
                for _ in restart_seeds
            ),
            "node_feature_masks": tuple(
                np.ones(tuple(local.x.shape), dtype=float) for _ in restart_seeds
            ),
            "restart_seeds": tuple(restart_seeds),
            "local_prepool_logit": logit,
            "full_prepool_logit": logit,
            "status": "ok",
        }

    se.diagnostic_edge_source_set_probability = lambda *args, **kwargs: probability
    engine.score_counterfactual = lambda context, factor: {
        "factor_id": factor.factor_id,
        "kind": factor.kind,
        "original_hybrid_rank": context.original_hybrid_rank,
        "ablated_hybrid_rank": context.original_hybrid_rank,
        "hybrid_rank_delta": 0,
    }
    engine.explain_case = lambda selected_case: se.compose_case_explanation(
        engine, selected_case, member_explainer=bounded_member_explainer
    )

    sentinel_calls = []

    def sentinel_explainer(*args, **kwargs):
        sentinel_calls.append((args, kwargs))
        raise AssertionError(
            "over-limit compose must reject before the explainer"
        )

    try:
        se.compose_case_explanation(
            engine,
            case,
            member_explainer=sentinel_explainer,
        )
    except se.ExplainerEligibilityError as error:
        eligibility = error.eligibility
    else:
        raise AssertionError("over-limit compose did not fail closed")

    if sentinel_calls:
        raise AssertionError("over-limit compose ran the sentinel explainer")

    scope = engine.community("target", scoring_day)
    control = se.build_structural_community_control(scope)
    if control["detail_kind"] != "community_only":
        raise AssertionError(
            "exact-limit structural control has the wrong detail kind"
        )
    if control["evidence_kind"] != "structural_provenance":
        raise AssertionError(
            "exact-limit structural control has the wrong evidence kind"
        )
    control_sha256 = hashlib.sha256(
        json.dumps(
            control,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    metrics_path.write_text(
        json.dumps(
            {
                "eligibility": eligibility,
                "sentinel_calls": len(sentinel_calls),
                "control_detail_kind": control["detail_kind"],
                "control_evidence_kind": control["evidence_kind"],
                "control_complete": control["complete"],
                "control_node_count": control["node_count"],
                "control_edge_count": control["edge_count"],
                "control_edges_with_provenance": sum(
                    bool(edge["available_times"]) for edge in control["edges"]
                ),
                "control_sha256": control_sha256,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return


def test_exact_limit_structural_control_rejects_over_limit_compose_and_hashes_complete_result(
    tmp_path,
):
    """Cover helper-level exact-limit rejection and complete structural output."""
    metrics_path = tmp_path / "structural-control-metrics.json"
    process = multiprocessing.get_context("spawn").Process(
        target=_exact_limit_structural_control_worker,
        args=(str(tmp_path / "structural-control-child"), str(metrics_path)),
    )
    process.start()
    process.join(timeout=240)
    if process.is_alive():
        process.terminate()
        process.join()
        pytest.fail(
            "exact-limit structural-control helper exceeded 240 seconds"
        )
    assert process.exitcode == 0
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    print(
        "EXACT_LIMIT_STRUCTURAL_CONTROL_METRICS="
        + json.dumps(metrics, sort_keys=True)
    )
    assert metrics["eligibility"]["status"] == "community_only"
    assert metrics["eligibility"]["reason_code"] == "edge_limit_exceeded"
    assert metrics["eligibility"]["node_count"] == 2
    assert metrics["eligibility"]["edge_count"] > se.MAX_LOCAL_EXPLANATION_EDGES
    assert metrics["sentinel_calls"] == 0
    assert metrics["control_detail_kind"] == "community_only"
    assert metrics["control_evidence_kind"] == "structural_provenance"
    assert metrics["control_complete"] is True
    assert metrics["control_node_count"] == 2
    assert metrics["control_edge_count"] == 1_001
    assert metrics["control_edges_with_provenance"] == 1_001
    assert metrics["control_complete"] is True
    assert len(metrics["control_sha256"]) == hashlib.sha256().digest_size * 2


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


def _counterfactual_reference(*, blend_weight=0.75, target_probability=0.80):
    return build_rank_reference(
        pd.DataFrame({"event_id": ["target-a", "target-b", "peer-a", "peer-b"]}),
        np.array([0.40, 0.40, 0.60, 0.20]),
        np.array(
            [target_probability, target_probability, 0.50, 0.10]
        ),
        blend_weight,
    )


def _counterfactual_row_bindings():
    return {
        0: ("target", SCORING_DAY + pd.Timedelta(hours=6)),
        1: ("target", SCORING_DAY + pd.Timedelta(hours=18)),
        2: ("peer-a", SCORING_DAY),
        3: ("peer-b", SCORING_DAY),
    }


def _counterfactual_context(*, candidates=(0, 1, 2, 3), original_rank=1):
    return CounterfactualContext(
        person_id="target",
        row_index=0,
        scoring_day=SCORING_DAY + pd.Timedelta(hours=12),
        same_day_person_row_indices=(0, 1),
        candidate_row_indices=candidates,
        original_hybrid_rank=original_rank,
    )


def _caught_factor(engine):
    return next(
        spec
        for spec in build_ablation_specs(
            engine.snapshot(SCORING_DAY),
            "target",
            engine.community("target", SCORING_DAY),
        )
        if spec.kind == "caught_flag" and spec.caught_person_ids == ("hop1",)
    )


def _bind_matching_reference(engine, *, row_bindings=None):
    probability = float(
        engine.snapshot(SCORING_DAY).probabilities[
            engine.person_index["target"]
        ]
    )
    reference = _counterfactual_reference(target_probability=probability)
    engine.bind_rank_reference(
        reference,
        _counterfactual_row_bindings()
        if row_bindings is None
        else row_bindings,
    )
    return reference


def test_counterfactual_rejects_stale_original_rank():
    engine, _ = _explanation_fixture()
    _bind_matching_reference(engine)

    with pytest.raises(ValueError, match="original_hybrid_rank.*frozen"):
        engine.score_counterfactual(
            _counterfactual_context(original_rank=2),
            _caught_factor(engine),
        )


def test_counterfactual_rejects_wrong_person_row_binding():
    engine, _ = _explanation_fixture()
    bindings = _counterfactual_row_bindings()
    bindings[1] = ("peer-a", SCORING_DAY)
    _bind_matching_reference(engine, row_bindings=bindings)

    with pytest.raises(ValueError, match="same-day person row.*person_id"):
        engine.score_counterfactual(
            _counterfactual_context(), _caught_factor(engine)
        )


def test_counterfactual_rejects_wrong_day_row_binding():
    engine, _ = _explanation_fixture()
    bindings = _counterfactual_row_bindings()
    bindings[1] = ("target", SCORING_DAY + pd.Timedelta(days=1))
    _bind_matching_reference(engine, row_bindings=bindings)

    with pytest.raises(ValueError, match="same-day person row.*scoring_day"):
        engine.score_counterfactual(
            _counterfactual_context(), _caught_factor(engine)
        )


def test_counterfactual_rejects_candidate_bound_to_a_different_day():
    engine, _ = _explanation_fixture()
    bindings = _counterfactual_row_bindings()
    bindings[2] = ("peer-a", SCORING_DAY + pd.Timedelta(days=1))
    _bind_matching_reference(engine, row_bindings=bindings)

    with pytest.raises(ValueError, match="candidate row.*scoring_day"):
        engine.score_counterfactual(
            _counterfactual_context(), _caught_factor(engine)
        )


def test_counterfactual_rejects_mismatched_frozen_probability():
    engine, _ = _explanation_fixture()
    engine.bind_rank_reference(
        _counterfactual_reference(target_probability=0.80),
        _counterfactual_row_bindings(),
    )

    with pytest.raises(ValueError, match="frozen seed0.*snapshot probability"):
        engine.score_counterfactual(
            _counterfactual_context(), _caught_factor(engine)
        )


def test_rank_reference_binding_is_defensive_and_not_publicly_assignable():
    engine, _ = _explanation_fixture()
    bindings = _counterfactual_row_bindings()
    reference = _bind_matching_reference(engine, row_bindings=bindings)
    expected = np.array(engine.rank_reference.seed0_gnn_raw, copy=True)

    bindings[0] = ("poisoned", SCORING_DAY + pd.Timedelta(days=20))
    object.__setattr__(
        reference,
        "seed0_gnn_raw",
        np.full(len(reference.event_ids), 0.01),
    )

    np.testing.assert_array_equal(
        engine.rank_reference.seed0_gnn_raw, expected
    )
    with pytest.raises(AttributeError):
        engine.rank_reference = reference


@pytest.mark.parametrize(
    ("row_bindings", "message"),
    [
        (
            {0: ("target", SCORING_DAY)},
            "exactly row indices",
        ),
        (
            {
                **_counterfactual_row_bindings(),
                4: ("extra", SCORING_DAY),
            },
            "exactly row indices",
        ),
        (
            [
                (0, "target", SCORING_DAY),
                (0, "target", SCORING_DAY),
                (2, "peer-a", SCORING_DAY),
                (3, "peer-b", SCORING_DAY),
            ],
            "duplicate rows",
        ),
        (
            {
                **_counterfactual_row_bindings(),
                0: (7, SCORING_DAY),
            },
            "person_id.*string",
        ),
        (
            {
                **_counterfactual_row_bindings(),
                0: ("target", [SCORING_DAY]),
            },
            "scalar timestamp",
        ),
    ],
)
def test_rank_reference_binding_rejects_incomplete_or_invalid_metadata(
    row_bindings, message
):
    engine, _ = _explanation_fixture()

    with pytest.raises(ValueError, match=message):
        engine.bind_rank_reference(_counterfactual_reference(), row_bindings)


def test_failed_rank_reference_binding_preserves_previous_state_atomically():
    engine, _ = _explanation_fixture()
    reference = _bind_matching_reference(engine)
    expected_id = engine.rank_reference.percentile_reference_id
    expected_raw = np.array(engine.rank_reference.seed0_gnn_raw, copy=True)

    with pytest.raises(ValueError, match="exactly row indices"):
        engine.bind_rank_reference(reference, {0: ("target", SCORING_DAY)})

    assert engine.rank_reference.percentile_reference_id == expected_id
    np.testing.assert_array_equal(
        engine.rank_reference.seed0_gnn_raw, expected_raw
    )


def test_counterfactual_requires_complete_bound_identity_day_group():
    engine, _ = _explanation_fixture()
    _bind_matching_reference(engine)
    incomplete = CounterfactualContext(
        person_id="target",
        row_index=0,
        scoring_day=SCORING_DAY,
        same_day_person_row_indices=(0,),
        candidate_row_indices=(0, 1, 2, 3),
        original_hybrid_rank=1,
    )

    with pytest.raises(ValueError, match="complete bound identity-day group"):
        engine.score_counterfactual(incomplete, _caught_factor(engine))


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


def test_frozen_peer_rank_no_op_preserves_exact_original_rank():
    result = frozen_peer_rank(
        _counterfactual_reference(),
        anchor_row_index=0,
        affected_row_indices=(0, 1),
        ablated_seed0_probability=0.80,
        candidate_row_indices=(0, 1, 2, 3),
        original_hybrid_rank=1,
    )

    assert result["ablated_hybrid_rank"] == 1
    assert result["hybrid_rank_delta"] == 0


def test_frozen_peer_rank_rejects_stale_original_rank():
    with pytest.raises(ValueError, match="original_hybrid_rank.*frozen"):
        frozen_peer_rank(
            _counterfactual_reference(),
            anchor_row_index=0,
            affected_row_indices=(0, 1),
            ablated_seed0_probability=0.80,
            candidate_row_indices=(0, 1, 2, 3),
            original_hybrid_rank=2,
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


def test_structural_provenance_never_materializes_networkx_components(monkeypatch):
    active_edges = pd.DataFrame(
        {
            "source_row_id": ["cot-a", "cot-b", "res-a", "res-b"],
            "u": ["a", "b", "c", "d"],
            "v": ["b", "c", "d", "e"],
            "edge_type": ["COTRAVEL", "COTRAVEL", "RESIDENCE", "RESIDENCE"],
        }
    )
    calls = {"connected_components": 0}
    original = se.nx.connected_components

    def counted_components(graph):
        calls["connected_components"] += 1
        return original(graph)

    monkeypatch.setattr(se.nx, "connected_components", counted_components)

    structural_provenance_rows(active_edges, {"a", "b", "c"})

    assert calls == {"connected_components": 0}


def test_structural_provenance_revisits_both_relations_to_fixed_point():
    active_edges = pd.DataFrame(
        {
            "source_row_id": ["res-a-b", "cot-b-c"],
            "u": ["a", "b"],
            "v": ["b", "c"],
            "edge_type": ["RESIDENCE", "COTRAVEL"],
        }
    )

    rows = structural_provenance_rows(active_edges, {"a"})

    assert rows["source_row_id"].tolist() == ["cot-b-c", "res-a-b"]


def test_structural_provenance_cap_is_deterministic_across_input_order():
    count = se.MAX_STRUCTURAL_PROVENANCE_ROWS + 44
    records = pd.DataFrame(
        {
            "source_row_id": [f"row:{index:04d}" for index in range(count)],
            "u": ["target"] * count,
            "v": [f"person:{index:04d}" for index in range(count)],
            "edge_type": ["COTRAVEL"] * count,
        }
    )

    forward = structural_provenance_rows(records, {"target"})
    reverse = structural_provenance_rows(
        records.iloc[::-1].reset_index(drop=True), {"target"}
    )

    expected = [
        f"row:{index:04d}" for index in range(se.MAX_STRUCTURAL_PROVENANCE_ROWS)
    ]
    assert forward["source_row_id"].tolist() == expected
    assert reverse["source_row_id"].tolist() == expected


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


def test_cotravel_factor_construction_builds_one_graph_for_many_groups(monkeypatch):
    active_edges = pd.DataFrame(
        {
            "source_row_id": ["row-a", "row-b", "row-c", "row-d"],
            "canonical_pair_group_id": ["g-a", "g-b", "g-c", "g-d"],
            "u": ["p0", "p1", "p2", "p3"],
            "v": ["p1", "p2", "p3", "p4"],
            "rel": [0, 0, 0, 0],
            "edge_type": ["COTRAVEL"] * 4,
        }
    )
    snapshot = SimpleNamespace(
        active_edges=active_edges,
        caught_before_snapshot=frozenset(),
    )
    community = {
        "base_source_row_ids": list(active_edges["source_row_id"]),
        "nodes_by_id": {f"p{index}": {} for index in range(5)},
    }
    calls = {"graph": 0}
    original_graph = se.nx.Graph

    def counted_graph(*args, **kwargs):
        calls["graph"] += 1
        return original_graph(*args, **kwargs)

    monkeypatch.setattr(
        se,
        "structural_provenance_rows",
        lambda active, visible: active.iloc[0:0].copy(deep=True),
    )
    monkeypatch.setattr(se.nx, "Graph", counted_graph)

    specs = build_ablation_specs(snapshot, "p0", community)

    assert len([spec for spec in specs if spec.kind == "cotravel_pool"]) == 4
    assert calls == {"graph": 1}


def test_giant_community_salient_counterfactual_factors_are_constant_bounded(
    monkeypatch,
):
    pair_count = 100_001
    source_ids = [f"row-{index:06d}" for index in range(pair_count)]
    active_edges = pd.DataFrame(
        {
            "source_row_id": source_ids,
            "canonical_pair_group_id": [
                f"group-{index:06d}" for index in range(pair_count)
            ],
            "u": ["target"] * pair_count,
            "v": [f"person-{index:06d}" for index in range(pair_count)],
            "rel": [1] * pair_count,
            "edge_type": ["RESIDENCE"] * pair_count,
        }
    )
    caught_people = {f"person-{index:06d}" for index in range(20)}
    snapshot = SimpleNamespace(
        active_edges=active_edges,
        caught_before_snapshot=frozenset(caught_people),
    )
    community = {
        "base_source_row_ids": source_ids,
        "nodes_by_id": {
            "target": {},
            **{person_id: {} for person_id in caught_people},
        },
    }
    monkeypatch.setattr(
        se,
        "structural_provenance_rows",
        lambda active, visible: active.iloc[0:0].copy(deep=True),
    )

    specs = build_ablation_specs(
        snapshot,
        "target",
        community,
        ranked_edge_source_row_ids=reversed(source_ids[-10:]),
        pooled_logit_contributions={
            person_id: float(index)
            for index, person_id in enumerate(sorted(caught_people))
        },
    )

    assert len([spec for spec in specs if spec.kind == "pair_relation"]) == 10
    assert len([spec for spec in specs if spec.kind == "relation_star"]) == 1
    assert len([spec for spec in specs if spec.kind == "caught_flag"]) == 5
    assert len(specs) == 16

    model = _SAGE(in_dim=8, hidden=4, out=4, num_relations=4)
    engine = se.Seed0ExplanationEngine(
        model=model,
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
        caught_time={},
        num_rel=4,
    )
    local = se.MemberSubgraph(
        x=torch.ones((1, 8), dtype=torch.float32),
        edge_index=torch.empty((2, 0), dtype=torch.long),
        target_index=0,
        original_node_indices=np.array([0]),
        tensor_edge_source_row_ids=np.array([], dtype=object),
    )
    with torch.no_grad():
        local_logit = float(
            se.PrePoolSAGELogitWrapper(engine.explanation_model_copy())(
                local.x, local.edge_index
            )[0]
        )
    real_snapshot = se.DaySnapshot(
        scoring_day=SCORING_DAY,
        active_edges=active_edges.assign(
            avail_time=pd.Timestamp("2025-01-01T00:00:00Z")
        ),
        x=local.x,
        edge_index=local.edge_index,
        edge_type=torch.empty(0, dtype=torch.long),
        tensor_edge_source_row_ids=np.array([], dtype=object),
        component_roots=np.array([0]),
        prepool_embeddings=torch.zeros((1, 4)),
        prepool_logits=torch.tensor([local_logit]),
        pooled_logits=torch.tensor([local_logit]),
        probabilities=np.array([0.80]),
        caught_before_snapshot=frozenset(caught_people),
    )
    display_source_ids = source_ids[-10:]
    giant_community = {
        "community_key": "community:giant",
        "complete": True,
        "base_source_row_ids": source_ids,
        "nodes_by_id": {
            "target": {},
            **{person_id: {} for person_id in caught_people},
        },
        "nodes": [{"node_id": "target"}],
        "edges": [
            {
                "edge_id": f"edge:{index}",
                "u": "target",
                "v": sorted(caught_people)[index % len(caught_people)],
                "edge_type": "RESIDENCE",
                "message_hop": 0,
                "source_row_ids": [source_row_id],
            }
            for index, source_row_id in enumerate(display_source_ids)
        ],
        "provenance_expansions": [],
    }
    reference = _counterfactual_reference(target_probability=0.80)
    engine.bind_rank_reference(reference, _counterfactual_row_bindings())
    trace = build_decision_trace(
        reference,
        row_index=0,
        baseline_candidate_row_indices=(0, 1, 2, 3),
        hybrid_candidate_row_indices=(0, 1, 2, 3),
        daily_budget=5,
    )
    case = HybridOnlyCase(
        person_id="target",
        anchor=RecoveryAnchor(
            person_id="target",
            event_id="target-a",
            row_index=0,
            scoring_day=SCORING_DAY,
            inspected_rank=1,
        ),
        baseline_rank=trace["baseline_rank"],
        gnn_rank=trace["seed0_gnn_rank"],
        hybrid_rank=trace["seed0_hybrid_rank"],
        baseline_percentile=trace["baseline_percentile"],
        gnn_percentile=trace["seed0_gnn_percentile"],
        relationship_categories=("RESIDENCE",),
        scoring_period="2025-01",
        same_day_person_row_indices=(0, 1),
        baseline_candidate_row_indices=(0, 1, 2, 3),
        hybrid_candidate_row_indices=(0, 1, 2, 3),
        decision_trace=trace,
    )

    restart_runs = []
    counterfactual_forwards = []
    original_member_explainer = se.run_member_explanation
    original_score_counterfactual = engine.score_counterfactual

    class LightweightExplainer:
        def __call__(self, *, x, edge_index, index):
            restart_runs.append(torch.initial_seed())
            return SimpleNamespace(
                edge_mask=torch.zeros(edge_index.shape[1]),
                node_mask=torch.ones_like(x),
            )

    def lightweight_member_explainer(*args, **kwargs):
        return original_member_explainer(
            *args,
            **kwargs,
            explainer_factory=lambda *factory_args, **factory_kwargs: (
                LightweightExplainer()
            ),
        )

    def lightweight_grouped_counterfactual(_engine, context, factor):
        return {
            "factor_id": factor.factor_id,
            "kind": factor.kind,
            "original_hybrid_rank": context.original_hybrid_rank,
            "ablated_hybrid_rank": context.original_hybrid_rank,
            "hybrid_rank_delta": 0,
        }

    def recording_score_counterfactual(context, factor):
        counterfactual_forwards.append(factor.factor_id)
        return original_score_counterfactual(context, factor)

    monkeypatch.setattr(engine, "snapshot", lambda scoring_day: real_snapshot)
    monkeypatch.setattr(engine, "community", lambda person_id, scoring_day: giant_community)
    monkeypatch.setattr(se, "member_subgraph", lambda *args, **kwargs: local)
    monkeypatch.setattr(se, "run_member_explanation", lightweight_member_explainer)
    monkeypatch.setattr(se, "score_grouped_counterfactual", lightweight_grouped_counterfactual)
    monkeypatch.setattr(
        se,
        "diagnostic_edge_source_set_probability",
        lambda *args, **kwargs: 0.80,
    )
    monkeypatch.setattr(engine, "score_counterfactual", recording_score_counterfactual)

    explanation = se.compose_case_explanation(engine, case)

    assert restart_runs == [0, 1, 2]
    assert len(counterfactual_forwards) == len(explanation["factors"])
    assert len(counterfactual_forwards) <= 25
    assert explanation["factor_scope"] == "salient_counterfactual_factors"


def test_composed_salient_factors_run_three_restarts_and_bounded_forwards(
    monkeypatch,
):
    engine, case = _sage_case_fixture()
    restart_runs = []
    counterfactual_forwards = []
    original_counterfactual = engine.score_counterfactual

    def recording_explainer(*args, **kwargs):
        restart_runs.extend(kwargs["restart_seeds"])
        return _deterministic_member_explainer(*args, **kwargs)

    def recording_counterfactual(context, factor):
        counterfactual_forwards.append(factor.factor_id)
        return original_counterfactual(context, factor)

    monkeypatch.setattr(engine, "score_counterfactual", recording_counterfactual)

    explanation = se.compose_case_explanation(
        engine, case, member_explainer=recording_explainer
    )

    assert restart_runs == [0, 1, 2]
    assert len(counterfactual_forwards) == len(explanation["factors"])
    assert len(counterfactual_forwards) <= 25
    assert explanation["factor_scope"] == "salient_counterfactual_factors"


def test_cotravel_counterfactual_rebuilds_features_pooling_and_component():
    engine, _ = _explanation_fixture(bind_rank_reference=True)
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
    engine, _, components = _explanation_fixture(
        bind_rank_reference=True, return_components=True
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

    engine, _ = _explanation_fixture(bind_rank_reference=True)
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
    )
    _bind_matching_reference(engine)

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
    )
    original_probability = float(engine.snapshot(SCORING_DAY).probabilities[0])
    engine.bind_rank_reference(
        build_rank_reference(
            pd.DataFrame({"event_id": ["target-event"]}),
            np.array([0.5]),
            np.array([original_probability]),
            0.75,
        ),
        {0: ("target", SCORING_DAY)},
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
    engine, _ = _explanation_fixture(bind_rank_reference=True)
    partial = AblationSpec(
        factor_id="pair:g1:rel:0",
        kind="pair_relation",
        edge_source_row_ids=("cot",),
    )

    with pytest.raises(ValueError, match="incomplete or invalid factor"):
        engine.score_counterfactual(_counterfactual_context(), partial)


def test_generated_pair_caught_relation_star_and_cotravel_factors_are_scoreable():
    engine, _ = _explanation_fixture(bind_rank_reference=True)
    snapshot = engine.snapshot(SCORING_DAY)
    community = engine.community("target", SCORING_DAY)
    specs_by_kind = {
        spec.kind: spec
        for spec in build_ablation_specs(snapshot, "target", community)
        if spec.kind
        in {
            "pair_relation",
            "caught_flag",
            "relation_star",
            "cotravel_pool",
        }
        and (
            spec.kind in {"caught_flag", "relation_star"}
            or spec.factor_id.endswith("g1:rel:0")
        )
    }

    assert set(specs_by_kind) == {
        "pair_relation",
        "caught_flag",
        "relation_star",
        "cotravel_pool",
    }
    for kind in (
        "pair_relation",
        "caught_flag",
        "relation_star",
        "cotravel_pool",
    ):
        result = engine.score_counterfactual(
            _counterfactual_context(), specs_by_kind[kind]
        )
        assert result["factor_id"] == specs_by_kind[kind].factor_id
        assert result["kind"] == kind


def test_generated_structural_provenance_factor_is_scoreable():
    from gnn.sage_explainer import Seed0ExplanationEngine

    torch.manual_seed(0)
    node_ids = ["target", "a", "b", "c"]
    edges = pd.DataFrame(
        {
            "source_row_id": ["target-res", "a-b-cot", "b-c-cot"],
            "canonical_pair_group_id": ["g-res", "g-ab", "g-bc"],
            "u": ["target", "a", "b"],
            "v": ["a", "b", "c"],
            "avail_time": [SCORING_DAY - pd.Timedelta(hours=1)] * 3,
            "rel": [1, 0, 0],
            "edge_type": ["RESIDENCE", "COTRAVEL", "COTRAVEL"],
        }
    )
    engine = Seed0ExplanationEngine(
        model=_RGCN(in_dim=8, hidden=4, out=4, num_relations=4),
        edges_typed=edges,
        node_ids=node_ids,
        node_feat={person_id: np.array([1.0]) for person_id in node_ids},
        caught_time={},
        num_rel=4,
    )
    original_probability = float(
        engine.snapshot(SCORING_DAY).probabilities[
            engine.person_index["target"]
        ]
    )
    engine.bind_rank_reference(
        build_rank_reference(
            pd.DataFrame({"event_id": ["target-event"]}),
            np.array([0.5]),
            np.array([original_probability]),
            0.75,
        ),
        {0: ("target", SCORING_DAY)},
    )
    context = CounterfactualContext(
        person_id="target",
        row_index=0,
        scoring_day=SCORING_DAY,
        same_day_person_row_indices=(0,),
        candidate_row_indices=(0,),
        original_hybrid_rank=1,
    )
    community = engine.community("target", SCORING_DAY)
    factor = next(
        spec
        for spec in build_ablation_specs(
            engine.snapshot(SCORING_DAY), "target", community
        )
        if spec.kind == "structural_provenance"
    )

    result = engine.score_counterfactual(context, factor)

    assert factor.provenance_node_ids == ("c",)
    assert result["factor_id"] == factor.factor_id
    assert result["kind"] == "structural_provenance"
    assert result["features_rebuilt"] is True
    assert result["pooling_rebuilt"] is True


def test_counterfactual_cache_returns_copies_and_separates_candidate_contexts():
    engine, _ = _explanation_fixture(bind_rank_reference=True)
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


def test_identical_counterfactual_cache_skips_all_expensive_work(monkeypatch):
    engine, _ = _explanation_fixture(bind_rank_reference=True)
    factor = _caught_factor(engine)
    counters = {
        "snapshot": 0,
        "community": 0,
        "specs": 0,
        "prepare": 0,
        "day_inputs": 0,
        "rescore": 0,
    }

    original_snapshot = engine.snapshot
    original_community = se.build_complete_community
    original_specs = se.build_ablation_specs
    original_prepare = learned_cell.prepare_snapshot_source
    original_day_inputs = learned_cell.build_day_snapshot_inputs
    encoder = engine._Seed0ExplanationEngine__model.enc
    original_forward = encoder.forward

    def counted_snapshot(*args, **kwargs):
        counters["snapshot"] += 1
        return original_snapshot(*args, **kwargs)

    def counted_community(*args, **kwargs):
        counters["community"] += 1
        return original_community(*args, **kwargs)

    def counted_specs(*args, **kwargs):
        counters["specs"] += 1
        return original_specs(*args, **kwargs)

    def counted_prepare(*args, **kwargs):
        counters["prepare"] += 1
        return original_prepare(*args, **kwargs)

    def counted_day_inputs(*args, **kwargs):
        counters["day_inputs"] += 1
        return original_day_inputs(*args, **kwargs)

    def counted_forward(*args, **kwargs):
        counters["rescore"] += 1
        return original_forward(*args, **kwargs)

    monkeypatch.setattr(engine, "snapshot", counted_snapshot)
    monkeypatch.setattr(se, "build_complete_community", counted_community)
    monkeypatch.setattr(se, "build_ablation_specs", counted_specs)
    monkeypatch.setattr(
        learned_cell, "prepare_snapshot_source", counted_prepare
    )
    monkeypatch.setattr(
        learned_cell, "build_day_snapshot_inputs", counted_day_inputs
    )
    monkeypatch.setattr(encoder, "forward", counted_forward)

    first = engine.score_counterfactual(_counterfactual_context(), factor)
    after_first = counters.copy()
    second = engine.score_counterfactual(_counterfactual_context(), factor)

    assert after_first == {
        "snapshot": 3,
        "community": 1,
        "specs": 1,
        "prepare": 1,
        "day_inputs": 1,
        "rescore": 1,
    }
    assert second == first
    assert counters == after_first


def test_generated_factor_specs_are_cached_across_different_factors(monkeypatch):
    engine, _ = _explanation_fixture(bind_rank_reference=True)
    snapshot = engine.snapshot(SCORING_DAY)
    community = engine.community("target", SCORING_DAY)
    factors = {
        spec.kind: spec
        for spec in build_ablation_specs(snapshot, "target", community)
        if spec.kind in {"relation_star", "caught_flag"}
    }
    counters = {"community": 0, "specs": 0}
    original_community = se.build_complete_community
    original_specs = se.build_ablation_specs

    def counted_community(*args, **kwargs):
        counters["community"] += 1
        return original_community(*args, **kwargs)

    def counted_specs(*args, **kwargs):
        counters["specs"] += 1
        return original_specs(*args, **kwargs)

    monkeypatch.setattr(se, "build_complete_community", counted_community)
    monkeypatch.setattr(se, "build_ablation_specs", counted_specs)

    engine.score_counterfactual(
        _counterfactual_context(), factors["relation_star"]
    )
    engine.score_counterfactual(
        _counterfactual_context(), factors["caught_flag"]
    )

    assert counters == {"community": 1, "specs": 1}


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


def _sage_explanation_fixture(*, caught_time=None):
    torch.manual_seed(0)
    node_ids = ["target", "poolmate", "hop1", "hop2"]
    edges = pd.DataFrame(
        {
            "source_row_id": ["cot", "res", "plate"],
            "canonical_pair_group_id": ["g-cot", "g-res", "g-plate"],
            "u": ["target", "poolmate", "hop1"],
            "v": ["poolmate", "hop1", "hop2"],
            "avail_time": [SCORING_DAY - pd.Timedelta(hours=1)] * 3,
            "rel": [0, 1, 2],
            "edge_type": ["COTRAVEL", "RESIDENCE", "SHARED_PLATE"],
        }
    )
    return se.Seed0ExplanationEngine(
        model=_SAGE(in_dim=8, hidden=4, out=4, num_relations=4),
        edges_typed=edges,
        node_ids=node_ids,
        node_feat={person_id: np.array([1.0]) for person_id in node_ids},
        caught_time={} if caught_time is None else caught_time,
        num_rel=4,
    )


def test_two_hop_wrapper_matches_full_graph_member_prepool_logit():
    engine = _sage_explanation_fixture()
    snapshot = engine.snapshot(SCORING_DAY)
    local = se.member_subgraph(engine, "target", SCORING_DAY)

    actual = se.PrePoolSAGELogitWrapper(
        engine.explanation_model_copy()
    )(local.x, local.edge_index)[local.target_index]
    expected = snapshot.prepool_logits[engine.person_index["target"]]

    torch.testing.assert_close(actual, expected, rtol=1e-6, atol=1e-6)
    assert local.tensor_edge_source_row_ids.tolist() == [
        "cot",
        "res",
        "cot",
        "res",
    ]


def test_restart_aggregation_normalizes_and_reports_median_iqr_frequency():
    aggregate = se.aggregate_restart_masks(
        [
            np.array([0.9, 0.2, 0.1]),
            np.array([0.8, 0.3, 0.1]),
            np.array([0.7, 0.4, 0.1]),
        ],
        top_fraction=1 / 3,
    )

    np.testing.assert_allclose(aggregate["median"], [1.0, 0.375, 0.125])
    np.testing.assert_allclose(
        aggregate["q1"], [1.0, 0.2986111111111111, 0.11805555555555555]
    )
    np.testing.assert_allclose(
        aggregate["q3"], [1.0, 0.4732142857142857, 0.13392857142857142]
    )
    np.testing.assert_allclose(
        aggregate["selection_frequency"], [1.0, 0.0, 0.0]
    )
    assert aggregate["restart_count"] == 3
    assert aggregate["top_factor_agreement"] == 1.0
    assert aggregate["status"] == "ok"


def test_restart_aggregation_reports_explicit_empty_edge_status():
    aggregate = se.aggregate_restart_masks(
        [np.zeros(0), np.zeros(0), np.zeros(0)]
    )

    assert aggregate["median"].size == 0
    assert aggregate["q1"].size == 0
    assert aggregate["q3"].size == 0
    assert aggregate["selection_frequency"].size == 0
    assert aggregate["restart_count"] == 3
    assert aggregate["top_factor_agreement"] == 0.0
    assert aggregate["status"] == "no-message-edges"


@pytest.mark.parametrize(
    ("masks", "top_fraction", "message"),
    [
        ([], 0.1, "at least one"),
        ([np.array([1.0]), np.array([1.0, 2.0])], 0.1, "aligned"),
        ([np.array([[1.0]])], 0.1, "one-dimensional"),
        ([np.array([-0.1])], 0.1, "nonnegative"),
        ([np.array([np.inf])], 0.1, "finite"),
        ([np.array([1.0])], 0.0, "top_fraction"),
        ([np.array([1.0])], 1.1, "top_fraction"),
        ([np.array([1.0])], np.nan, "top_fraction"),
    ],
)
def test_restart_aggregation_rejects_invalid_masks_and_fraction(
    masks, top_fraction, message
):
    with pytest.raises(ValueError, match=message):
        se.aggregate_restart_masks(masks, top_fraction=top_fraction)


def test_restart_aggregation_reports_top_factor_agreement():
    aggregate = se.aggregate_restart_masks(
        [
            np.array([1.0, 0.0, 0.0]),
            np.array([0.0, 1.0, 0.0]),
            np.array([1.0, 0.0, 0.0]),
        ],
        top_fraction=1 / 3,
    )

    np.testing.assert_allclose(
        aggregate["selection_frequency"], [2 / 3, 1 / 3, 0.0]
    )
    assert aggregate["top_factor_agreement"] == pytest.approx(2 / 3)


def test_restart_aggregation_does_not_select_arbitrary_zero_masks():
    aggregate = se.aggregate_restart_masks(
        [np.zeros(3), np.zeros(3), np.zeros(3)], top_fraction=1 / 3
    )

    np.testing.assert_array_equal(
        aggregate["selection_frequency"], np.zeros(3)
    )
    assert aggregate["top_factor_agreement"] == 0.0
    assert aggregate["status"] == "no-positive-influence"


def test_faithfulness_controls_require_exact_relation_and_degree_bin():
    edge_records = [
        {"edge_id": "e1", "relation": "COTRAVEL", "degree_bin": "2-4"},
        {"edge_id": "e2", "relation": "COTRAVEL", "degree_bin": "2-4"},
        {"edge_id": "e3", "relation": "RESIDENCE", "degree_bin": "5-8"},
        {"edge_id": "e4", "relation": "RESIDENCE", "degree_bin": "5-8"},
        {"edge_id": "loose-relation", "relation": "RESIDENCE", "degree_bin": "2-4"},
        {"edge_id": "loose-degree", "relation": "COTRAVEL", "degree_bin": "5-8"},
    ]

    assert se.matched_random_controls(
        edge_records, selected_edge_ids=("e1", "e3"), seed=0
    ) == ("e2", "e4")
    assert se.matched_random_controls(
        edge_records, selected_edge_ids=("e1", "e2"), seed=0
    ) == ()


def test_member_subgraph_is_immutable_and_defensively_copied():
    local = se.member_subgraph(_sage_explanation_fixture(), "target", SCORING_DAY)
    expected_x = local.x.clone()
    expected_edge_index = local.edge_index.clone()
    expected_nodes = local.original_node_indices.copy()
    expected_provenance = local.tensor_edge_source_row_ids.copy()

    local.x.fill_(99.0)
    local.edge_index.fill_(0)
    with pytest.raises(ValueError, match="read-only"):
        local.original_node_indices[:] = -1
    with pytest.raises(ValueError, match="read-only"):
        local.tensor_edge_source_row_ids[:] = "poisoned"

    torch.testing.assert_close(local.x, expected_x)
    torch.testing.assert_close(local.edge_index, expected_edge_index)
    np.testing.assert_array_equal(local.original_node_indices, expected_nodes)
    np.testing.assert_array_equal(
        local.tensor_edge_source_row_ids, expected_provenance
    )
    with pytest.raises(AttributeError):
        local.target_index = 99


def test_member_subgraph_rejects_misaligned_tensor_edge_provenance():
    with pytest.raises(ValueError, match="tensor edges.*provenance"):
        se.MemberSubgraph(
            x=torch.ones((2, 3)),
            edge_index=torch.tensor([[0], [1]], dtype=torch.long),
            target_index=0,
            original_node_indices=np.array([0, 1]),
            tensor_edge_source_row_ids=np.array([], dtype=object),
        )


def test_make_gnn_explainer_uses_binary_node_raw_configuration():
    wrapper = se.PrePoolSAGELogitWrapper(
        _sage_explanation_fixture().explanation_model_copy()
    )

    explainer = se.make_gnn_explainer(wrapper, epochs=150)

    assert explainer.model is wrapper
    assert explainer.model_config.mode.value == "binary_classification"
    assert explainer.model_config.task_level.value == "node"
    assert explainer.model_config.return_type.value == "raw"
    assert explainer.node_mask_type.value == "attributes"
    assert explainer.edge_mask_type.value == "object"
    assert explainer.algorithm.epochs == 150


def test_production_explainer_epoch_policy_is_fixed():
    wrapper = se.PrePoolSAGELogitWrapper(
        _sage_explanation_fixture().explanation_model_copy()
    )

    with pytest.raises(ValueError, match="epochs must be exactly 150"):
        se.make_gnn_explainer(wrapper, epochs=149)

    with pytest.raises(ValueError, match="epochs must be exactly 150"):
        se.run_member_explanation(
            _sage_explanation_fixture(),
            "target",
            SCORING_DAY,
            epochs=149,
            explainer_factory=lambda *args, **kwargs: pytest.fail(
                "invalid epoch policy must reject before the injected explainer"
            ),
        )

    engine, case = _sage_case_fixture()
    with pytest.raises(ValueError, match="epochs must be exactly 150"):
        se.compose_case_explanation(
            engine,
            case,
            explainer_epochs=149,
            member_explainer=lambda *args, **kwargs: pytest.fail(
                "invalid epoch policy must reject before the injected explainer"
            ),
        )


def test_member_explanation_uses_exact_restarts_and_isolated_model_copy():
    engine = _sage_explanation_fixture()
    expected_later_day = engine.snapshot(
        SCORING_DAY + pd.Timedelta(days=1)
    ).probabilities.copy()
    canonical_model = engine._Seed0ExplanationEngine__model
    expected_parameters = [
        parameter.detach().clone() for parameter in canonical_model.parameters()
    ]
    calls = []

    class FakeExplainer:
        def __init__(self, wrapper):
            self.wrapper = wrapper

        def __call__(self, *, x, edge_index, index):
            calls.append((x.shape, edge_index.shape, index))
            with torch.no_grad():
                next(self.wrapper.parameters()).fill_(99.0)
            return SimpleNamespace(
                edge_mask=torch.rand(edge_index.shape[1]),
                node_mask=torch.rand(x.shape),
            )

    def explainer_factory(wrapper, *, epochs):
        assert epochs == 150
        return FakeExplainer(wrapper)

    first = se.run_member_explanation(
        engine,
        "target",
        SCORING_DAY,
        restart_seeds=(0, 1, 2),
        epochs=150,
        explainer_factory=explainer_factory,
    )
    second = se.run_member_explanation(
        engine,
        "target",
        SCORING_DAY,
        restart_seeds=(0, 1, 2),
        epochs=150,
        explainer_factory=explainer_factory,
    )

    assert first["status"] == "ok"
    assert first["restart_seeds"] == (0, 1, 2)
    assert len(first["edge_masks"]) == len(first["node_feature_masks"]) == 3
    for actual, expected in zip(first["edge_masks"], second["edge_masks"]):
        np.testing.assert_array_equal(actual, expected)
    for actual, expected in zip(
        first["node_feature_masks"], second["node_feature_masks"]
    ):
        np.testing.assert_array_equal(actual, expected)
        assert actual.shape == se.member_subgraph(
            engine, "target", SCORING_DAY
        ).x.shape
    assert len(calls) == 6
    np.testing.assert_array_equal(
        engine.snapshot(SCORING_DAY + pd.Timedelta(days=2)).probabilities,
        expected_later_day,
    )
    assert canonical_model.training is False
    assert all(not parameter.requires_grad for parameter in canonical_model.parameters())
    for actual, expected in zip(canonical_model.parameters(), expected_parameters):
        torch.testing.assert_close(actual, expected)


def test_member_explanation_runs_all_restarts_for_isolated_target_node_masks():
    engine = se.Seed0ExplanationEngine(
        model=_SAGE(in_dim=8, hidden=4, out=4, num_relations=4),
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
        caught_time={},
        num_rel=4,
    )

    calls = []

    class IsolatedExplainer:
        def __call__(self, *, x, edge_index, index):
            calls.append((tuple(x.shape), tuple(edge_index.shape), index))
            return SimpleNamespace(
                edge_mask=torch.zeros(0),
                node_mask=torch.rand(x.shape),
            )

    def isolated_factory(*args, **kwargs):
        return IsolatedExplainer()

    result = se.run_member_explanation(
        engine,
        "target",
        SCORING_DAY,
        explainer_factory=isolated_factory,
    )

    assert result["status"] == "no-message-edges"
    assert result["restart_seeds"] == (0, 1, 2)
    assert len(result["edge_masks"]) == 3
    assert all(mask.size == 0 for mask in result["edge_masks"])
    assert len(result["node_feature_masks"]) == 3
    assert all(mask.shape == (1, 8) for mask in result["node_feature_masks"])
    assert all(mask.any() for mask in result["node_feature_masks"])
    assert calls == [((1, 8), (2, 0), 0)] * 3
    assert result["local_prepool_logit"] == pytest.approx(
        result["full_prepool_logit"]
    )


def test_real_gnnexplainer_returns_isolated_target_node_masks():
    engine = se.Seed0ExplanationEngine(
        model=_SAGE(in_dim=8, hidden=4, out=4, num_relations=4),
        edges_typed=pd.DataFrame(
            columns=[
                "source_row_id", "canonical_pair_group_id", "u", "v",
                "avail_time", "rel", "edge_type",
            ]
        ),
        node_ids=["target"],
        node_feat={"target": np.array([1.0])},
        caught_time={},
        num_rel=4,
    )

    result = se.run_member_explanation(engine, "target", SCORING_DAY, epochs=150)

    assert len(result["node_feature_masks"]) == 3
    assert all(mask.shape == (1, 8) for mask in result["node_feature_masks"])
    assert all(np.isfinite(mask).all() for mask in result["node_feature_masks"])


@pytest.mark.parametrize(
    "restart_seeds",
    [(7,), (0, 1), (0, 1, 2, 3), (2, 1, 0)],
)
def test_restart_seed_validation_requires_canonical_seed_zero_restarts(
    restart_seeds,
):
    with pytest.raises(ValueError, match=r"exactly \(0, 1, 2\)"):
        se._validated_restart_seeds(restart_seeds)


def test_member_and_case_entrypoints_reject_noncanonical_restarts():
    engine = _sage_explanation_fixture()

    class ZeroExplainer:
        def __call__(self, *, x, edge_index, index):
            return SimpleNamespace(
                edge_mask=torch.zeros(edge_index.shape[1]),
                node_mask=torch.zeros(x.shape),
            )

    with pytest.raises(ValueError, match=r"exactly \(0, 1, 2\)"):
        se.run_member_explanation(
            engine,
            "target",
            SCORING_DAY,
            restart_seeds=(7,),
            epochs=150,
            explainer_factory=lambda wrapper, epochs: ZeroExplainer(),
        )

    bound_engine, case = _sage_case_fixture()
    with pytest.raises(ValueError, match=r"exactly \(0, 1, 2\)"):
        se.compose_case_explanation(
            bound_engine,
            case,
            restart_seeds=(7,),
            member_explainer=_deterministic_member_explainer,
        )


def test_flow_stages_use_constant_size_rules_without_membership_copies():
    community = _sage_explanation_fixture().community("target", SCORING_DAY)

    stages = se.build_flow_stages(community)

    assert [stage["stage_id"] for stage in stages] == [
        "first_hop",
        "second_hop",
        "component_pool",
        "rank_fusion",
    ]
    assert all(set(stage) == {"stage_id", "edge_rule"} for stage in stages)
    assert stages[0]["edge_rule"] == {"max_message_hop": 1}
    assert stages[1]["edge_rule"] == {"max_message_hop": 2}
    assert stages[2]["edge_rule"] == {
        "edge_type": "COTRAVEL",
        "both_pooled_members": True,
    }
    assert stages[3]["edge_rule"] == {"match_none": True}


def test_edge_removal_faithfulness_uses_exact_fractions_and_matched_controls():
    records = [
        {"edge_id": f"e{index}", "relation": "COTRAVEL", "degree_bin": "2-4"}
        for index in range(1, 7)
    ]
    importance = {f"e{index}": 7.0 - index for index in range(1, 7)}

    def rescore(removed):
        return 0.9 - 0.05 * len(removed)

    result = se.edge_removal_faithfulness(
        records, importance, rescore=rescore, seed=0
    )

    assert result["original_probability"] == pytest.approx(0.9)
    assert [point["fraction"] for point in result["points"]] == [0.1, 0.25, 0.5]
    assert [len(point["selected_edge_ids"]) for point in result["points"]] == [1, 2, 3]
    assert all(point["unmatched_control_count"] == 0 for point in result["points"])
    assert all(
        point["matched_random_probability_drop"]
        == pytest.approx(point["top_edge_probability_drop"])
        for point in result["points"]
    )


def test_edge_removal_faithfulness_records_unmatched_controls_without_fallback():
    records = [
        {"edge_id": "e1", "relation": "COTRAVEL", "degree_bin": "1"},
        {"edge_id": "e2", "relation": "RESIDENCE", "degree_bin": "9+"},
    ]

    result = se.edge_removal_faithfulness(
        records,
        {"e1": 1.0, "e2": 0.5},
        rescore=lambda removed: 0.8 - 0.1 * len(removed),
    )

    assert all(point["unmatched_control_count"] > 0 for point in result["points"])
    assert all(
        point["matched_random_probability_drop"] is None
        for point in result["points"]
    )


def test_faithfulness_records_exact_unmatched_ids_and_control_pairing():
    records = [
        {"edge_id": "e1", "relation": "COTRAVEL", "degree_bin": "1"},
        {"edge_id": "e2", "relation": "RESIDENCE", "degree_bin": "2-4"},
        {"edge_id": "e3", "relation": "RESIDENCE", "degree_bin": "2-4"},
    ]

    result = se.edge_removal_faithfulness(
        records,
        {"e1": 3.0, "e2": 2.0, "e3": 1.0},
        rescore=lambda removed: 0.9 - 0.1 * len(removed),
        seed=0,
    )

    half = result["points"][2]
    assert half["selected_edge_ids"] == ["e1", "e2"]
    assert half["matched_control_pairs"] == [
        {"selected_edge_id": "e2", "control_edge_id": "e3"}
    ]
    assert half["unmatched_selected_edge_ids"] == ["e1"]
    assert half["unmatched_control_count"] == 1


def test_diagnostic_edge_set_rescore_is_exact_strict_asof_and_separate():
    engine, _, components = _explanation_fixture(
        return_components=True, bind_rank_reference=True
    )
    model, edges, node_ids, node_feat, caught_times = components
    context = _counterfactual_context()

    actual = se.diagnostic_edge_source_set_probability(
        engine, context, ("cot", "cot-duplicate")
    )
    expected = _score_pool(
        model,
        pd.DataFrame(
            {
                "primary_obs_id": ["obs-target"],
                "t": [SCORING_DAY + pd.Timedelta(hours=6)],
            }
        ),
        {"obs-target": "target"},
        edges.loc[
            ~edges["source_row_id"].isin(("cot", "cot-duplicate"))
        ],
        node_ids,
        node_feat,
        caught_times,
        {person_id: index for index, person_id in enumerate(node_ids)},
        num_rel=4,
    )[0]

    assert actual == pytest.approx(expected, rel=1e-6)
    with pytest.raises(ValueError, match="active at the scoring snapshot"):
        se.diagnostic_edge_source_set_probability(
            engine, context, ("at-boundary",)
        )
    with pytest.raises(ValueError, match="incomplete or invalid factor"):
        engine.score_counterfactual(
            context,
            AblationSpec(
                factor_id="pair:g1:rel:0",
                kind="pair_relation",
                edge_source_row_ids=("cot",),
            ),
        )


def test_length_framed_hash_prevents_edge_set_boundary_collisions():
    assert se._length_framed_hash(("a", "bc")) != se._length_framed_hash(
        ("ab", "c")
    )


def _sage_case_fixture():
    engine = _sage_explanation_fixture()
    probability = float(
        engine.snapshot(SCORING_DAY).probabilities[
            engine.person_index["target"]
        ]
    )
    reference = _counterfactual_reference(target_probability=probability)
    engine.bind_rank_reference(reference, _counterfactual_row_bindings())
    trace = build_decision_trace(
        reference,
        row_index=0,
        baseline_candidate_row_indices=(0, 1, 2, 3),
        hybrid_candidate_row_indices=(0, 1, 2, 3),
        daily_budget=5,
    )
    case = HybridOnlyCase(
        person_id="target",
        anchor=RecoveryAnchor(
            person_id="target",
            event_id="target-a",
            row_index=0,
            scoring_day=SCORING_DAY,
            inspected_rank=1,
        ),
        baseline_rank=trace["baseline_rank"],
        gnn_rank=trace["seed0_gnn_rank"],
        hybrid_rank=trace["seed0_hybrid_rank"],
        baseline_percentile=trace["baseline_percentile"],
        gnn_percentile=trace["seed0_gnn_percentile"],
        relationship_categories=("COTRAVEL",),
        scoring_period="2025-01",
        same_day_person_row_indices=(0, 1),
        baseline_candidate_row_indices=(0, 1, 2, 3),
        hybrid_candidate_row_indices=(0, 1, 2, 3),
        decision_trace=trace,
    )
    return engine, case


def _deterministic_member_explainer(
    engine, person_id, scoring_day, *, restart_seeds=(0, 1, 2), **kwargs
):
    local = se.member_subgraph(engine, person_id, scoring_day)
    edge_values = {
        "cot": 1.0,
        "res": 0.5,
        "plate": 0.25,
    }
    edge_mask = np.array(
        [
            edge_values.get(str(source_id), 1.0)
            for source_id in local.tensor_edge_source_row_ids
        ],
        dtype=float,
    )
    feature_mask = np.arange(1, local.x.shape[1] + 1, dtype=float)
    snapshot = engine.snapshot(scoring_day)
    logit = float(snapshot.prepool_logits[engine.person_index[person_id]])
    return {
        "edge_masks": tuple(edge_mask.copy() for _ in restart_seeds),
        "node_feature_masks": tuple(
            np.vstack(
                [feature_mask * (node_index + 1) for node_index in range(local.x.shape[0])]
            )
            for _ in restart_seeds
        ),
        "restart_seeds": tuple(restart_seeds),
        "local_prepool_logit": logit,
        "full_prepool_logit": logit,
        "status": "ok",
    }


def _copy_case(case, *, decision_trace=None, **overrides):
    values = {
        "person_id": case.person_id,
        "anchor": case.anchor,
        "baseline_rank": case.baseline_rank,
        "gnn_rank": case.gnn_rank,
        "hybrid_rank": case.hybrid_rank,
        "baseline_percentile": case.baseline_percentile,
        "gnn_percentile": case.gnn_percentile,
        "relationship_categories": case.relationship_categories,
        "scoring_period": case.scoring_period,
        "same_day_person_row_indices": case.same_day_person_row_indices,
        "baseline_candidate_row_indices": case.baseline_candidate_row_indices,
        "hybrid_candidate_row_indices": case.hybrid_candidate_row_indices,
        "decision_trace": (
            case.decision_trace_jsonable()
            if decision_trace is None
            else decision_trace
        ),
    }
    values.update(overrides)
    return HybridOnlyCase(**values)


def test_json_safe_handles_mapping_proxy_numpy_timestamp_and_tuples():
    payload = MappingProxyType(
        {
            "array": np.array([1, 2]),
            "scalar": np.float32(0.5),
            "when": SCORING_DAY,
            "nested": (MappingProxyType({"flag": np.bool_(True)}),),
        }
    )

    safe = se.json_safe(payload)

    assert safe == {
        "array": [1, 2],
        "scalar": pytest.approx(0.5),
        "when": "2025-01-02T00:00:00+00:00",
        "nested": [{"flag": True}],
    }
    json.dumps(safe, allow_nan=False, sort_keys=True)


def test_provenance_expansion_is_strict_asof_and_uses_source_row_ids():
    node_ids = ["target", "a", "b", "outside"]
    edges = pd.DataFrame(
        {
            "source_row_id": ["target-res", "a-b-cot", "b-outside-cot", "future"],
            "canonical_pair_group_id": ["g-res", "g-ab", "g-bo", "g-future"],
            "u": ["target", "a", "b", "outside"],
            "v": ["a", "b", "outside", "target"],
            "avail_time": [
                SCORING_DAY - pd.Timedelta(hours=4),
                SCORING_DAY - pd.Timedelta(hours=3),
                SCORING_DAY - pd.Timedelta(hours=2),
                SCORING_DAY,
            ],
            "rel": [1, 0, 0, 2],
            "edge_type": ["RESIDENCE", "COTRAVEL", "COTRAVEL", "SHARED_PLATE"],
        }
    )
    engine = se.Seed0ExplanationEngine(
        model=_SAGE(in_dim=8, hidden=4, out=4, num_relations=4),
        edges_typed=edges,
        node_ids=node_ids,
        node_feat={person_id: np.array([1.0]) for person_id in node_ids},
        caught_time={"outside": SCORING_DAY - pd.Timedelta(hours=1)},
        num_rel=4,
    )
    snapshot = engine.snapshot(SCORING_DAY)
    community = engine.community("target", SCORING_DAY)
    spec = next(
        factor
        for factor in build_ablation_specs(snapshot, "target", community)
        if factor.kind == "structural_provenance"
    )

    expansion = se.build_provenance_expansion(
        engine, snapshot, spec, community
    )

    assert expansion["label"] == "outside message community"
    assert [edge["source_row_ids"] for edge in expansion["edges"]] == [
        ["b-outside-cot"]
    ]
    assert "future" not in json.dumps(expansion)
    outside = next(
        node for node in expansion["nodes"] if node["node_id"] == "outside"
    )
    assert outside["caught_before_snapshot"] is True
    assert outside["caught_label_available_time"] == (
        "2025-01-01T23:00:00+00:00"
    )
    json.dumps(se.json_safe(expansion), allow_nan=False, sort_keys=True)


def test_outside_ring_position_is_stable_per_node_id_and_independent_of_cohort():
    """An outside person's layout coordinate must depend only on its node_id, not
    on which other outside people share the expansion. Both the recovery bundle
    (add_node conflict guard) and the dashboard reconcile outside nodes by
    node_id and reject the same node recurring with different x/y, so a node that
    appears in two provenance expansions must land on identical coordinates."""
    a = se._outside_ring_position("P00008628")
    again = se._outside_ring_position("P00008628")
    assert a == again  # pure function of node_id
    x, y = a
    assert 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0
    # A different node generally maps elsewhere on the ring.
    assert se._outside_ring_position("P00030957") != a
    # Cohort membership must not shift a node's coordinate: the same id resolves
    # identically regardless of any surrounding set.
    assert se._outside_ring_position("P00008628") == a


def test_compose_case_explanation_ranks_target_local_attributions_and_proves_ledger():
    engine, case = _sage_case_fixture()
    calls = []
    canonical_community = engine.community("target", SCORING_DAY)

    def recording_explainer(*args, **kwargs):
        calls.append((args[1], kwargs["restart_seeds"], kwargs["epochs"]))
        return _deterministic_member_explainer(*args, **kwargs)

    explanation = se.compose_case_explanation(
        engine, case, member_explainer=recording_explainer
    )

    assert calls == [("target", (0, 1, 2), 150)]
    assert explanation.community_scope is canonical_community
    assert explanation["community"]["display_scope"] == "target_local"
    assert all(
        not {
            "explainer_median",
            "explainer_q1",
            "explainer_q3",
            "selection_frequency",
        }.intersection(edge)
        for edge in explanation["community"]["edges"]
    )
    assert isinstance(explanation["provenance_expansions"], list)
    assert explanation["case_id"] == "case:target"
    assert set(explanation["snapshot"]) == {"scoring_day"}
    assert explanation["parity"] == {
        "production_seed0_probability": True,
        "pooled_logit_decomposition": True,
        "frozen_percentile": True,
        "frozen_daily_hybrid_rank": True,
        "anchor_event": True,
    }
    assert explanation["decision_trace"]["daily_budget"] == 5
    attributions = explanation["attributions"]
    assert attributions["scope"] == {
        "target_person_id": "target",
        "hops": 2,
        "restart_seeds": [0, 1, 2],
        "epochs": 150,
        "unsigned_masks": True,
    }
    assert 0 < len(attributions["top_local_nodes"]) <= 10
    assert 0 < len(attributions["top_edges"]) <= 10
    assert 0 < len(attributions["top_features"]) <= 5
    assert all(
        {"explainer_median", "explainer_q1", "explainer_q3", "selection_frequency"}
        <= set(record)
        for key in ("top_local_nodes", "top_edges", "top_features")
        for record in attributions[key]
    )
    assert all("source_row_ids" in edge for edge in attributions["top_edges"])
    local = se.member_subgraph(engine, "target", SCORING_DAY)
    assert len(attributions["node_feature_mask_stats"]) == (
        local.x.shape[0] * local.x.shape[1]
    )
    assert {
        (record["node_id"], record["feature_name"])
        for record in attributions["node_feature_mask_stats"]
    } == {
        (engine.node_ids[int(node_index)], feature_name)
        for node_index in local.original_node_indices
        for feature_name in se.caught_feature_names(engine.num_rel)
    }
    pooling = explanation["decision_ledger"]["component_pooling"]
    assert "members" not in pooling
    assert pooling["component_size"] == 2
    assert sum(
        member["pooled_logit_contribution"]
        for member in pooling["top_members_by_absolute_contribution"]
    ) == pytest.approx(pooling["contribution_sum"])
    assert pooling["contribution_sum"] == pytest.approx(pooling["pooled_logit"])
    assert len(pooling["top_members_by_absolute_contribution"]) <= 10
    fusion = explanation["decision_ledger"]["rank_fusion"]
    assert fusion["daily_budget"] == 5
    assert fusion["hybrid_score"] == pytest.approx(
        fusion["baseline_weighted_term"] + fusion["seed0_gnn_weighted_term"]
    )
    assert explanation["stability"]["signed_effect_source"] == (
        "counterfactual_only"
    )
    assert explanation["stability"]["edge_restart_aggregate"][
        "top_factor_agreement"
    ] == 1.0
    assert explanation["factors"]
    assert all("counterfactual" in factor for factor in explanation["factors"])
    assert [point["fraction"] for point in explanation["faithfulness"]["points"]] == [
        0.1,
        0.25,
        0.5,
    ]
    assert all(
        set(stage) == {"stage_id", "edge_rule"}
        for stage in explanation["flow_stages"]
    )
    assert explanation["evidence_boundary"] == {
        "snapshot": "2025-01-02T00:00:00+00:00",
        "edge_rule": "available_time < snapshot",
        "caught_rule": "label_available_time_utc < snapshot",
    }
    json.dumps(explanation, allow_nan=False, sort_keys=True)


def _sage_pooled_component_case_fixture(component_size):
    node_ids = ["target"] + [
        f"poolmate-{index:02d}" for index in range(1, component_size)
    ]
    edges = pd.DataFrame(
        {
            "source_row_id": [
                f"cot-{index:02d}" for index in range(1, component_size)
            ],
            "canonical_pair_group_id": [
                f"g-cot-{index:02d}" for index in range(1, component_size)
            ],
            "u": ["target"] * (component_size - 1),
            "v": node_ids[1:],
            "avail_time": [
                SCORING_DAY - pd.Timedelta(hours=1)
            ] * (component_size - 1),
            "rel": [0] * (component_size - 1),
            "edge_type": ["COTRAVEL"] * (component_size - 1),
        }
    )
    engine = se.Seed0ExplanationEngine(
        model=_SAGE(in_dim=8, hidden=4, out=4, num_relations=4),
        edges_typed=edges,
        node_ids=node_ids,
        node_feat={person_id: np.array([1.0]) for person_id in node_ids},
        caught_time={},
        num_rel=4,
    )
    probability = float(
        engine.snapshot(SCORING_DAY).probabilities[
            engine.person_index["target"]
        ]
    )
    reference = _counterfactual_reference(target_probability=probability)
    engine.bind_rank_reference(reference, _counterfactual_row_bindings())
    trace = build_decision_trace(
        reference,
        row_index=0,
        baseline_candidate_row_indices=(0, 1, 2, 3),
        hybrid_candidate_row_indices=(0, 1, 2, 3),
        daily_budget=5,
    )
    case = HybridOnlyCase(
        person_id="target",
        anchor=RecoveryAnchor(
            person_id="target",
            event_id="target-a",
            row_index=0,
            scoring_day=SCORING_DAY,
            inspected_rank=trace["seed0_hybrid_rank"],
        ),
        baseline_rank=trace["baseline_rank"],
        gnn_rank=trace["seed0_gnn_rank"],
        hybrid_rank=trace["seed0_hybrid_rank"],
        baseline_percentile=trace["baseline_percentile"],
        gnn_percentile=trace["seed0_gnn_percentile"],
        relationship_categories=("COTRAVEL",),
        scoring_period="2025-01",
        same_day_person_row_indices=(0, 1),
        baseline_candidate_row_indices=(0, 1, 2, 3),
        hybrid_candidate_row_indices=(0, 1, 2, 3),
        decision_trace=trace,
    )
    return engine, case


def test_compose_case_explanation_handles_large_pool_with_target_only_explainer():
    engine, case = _sage_pooled_component_case_fixture(7)
    calls = []

    def recording_explainer(*args, **kwargs):
        calls.append(args[1])
        return _deterministic_member_explainer(*args, **kwargs)

    explanation = se.compose_case_explanation(
        engine,
        case,
        member_explainer=recording_explainer,
    )

    assert calls == ["target"]
    pooling = explanation["decision_ledger"]["component_pooling"]
    assert pooling["component_size"] == 7
    assert "members" not in pooling


def test_compose_case_explanation_admits_size_six_into_diagnostic(monkeypatch):
    engine, case = _sage_pooled_component_case_fixture(6)

    def diagnostic_sentinel(*args, **kwargs):
        raise AssertionError("size-six component entered diagnostic work")

    monkeypatch.setattr(
        se, "diagnostic_edge_source_set_probability", diagnostic_sentinel
    )

    with pytest.raises(
        AssertionError,
        match="size-six component entered diagnostic work",
    ):
        se.compose_case_explanation(engine, case)


@pytest.mark.parametrize(
    "limit",
    [0, -1, True, 1.5, "6"],
)
def test_compose_case_explanation_rejects_invalid_component_limit(limit):
    engine, case = _sage_case_fixture()

    with pytest.raises(ValueError, match="positive integer"):
        se.compose_case_explanation(
            engine,
            case,
            member_explainer=_deterministic_member_explainer,
            max_explainable_component_size=limit,
        )


def test_compose_case_explanation_is_deterministic_and_cache_safe():
    engine, case = _sage_case_fixture()

    first = se.compose_case_explanation(
        engine, case, member_explainer=_deterministic_member_explainer
    )
    expected = json.dumps(first, allow_nan=False, sort_keys=True)
    first["community"]["edges"][0]["source_row_ids"].append("poisoned")
    second = se.compose_case_explanation(
        engine, case, member_explainer=_deterministic_member_explainer
    )

    assert json.dumps(second, allow_nan=False, sort_keys=True) == expected


def test_compose_case_explanation_rejects_stale_probability_parity():
    engine, case = _sage_case_fixture()
    stale_reference = _counterfactual_reference(target_probability=0.99)
    engine.bind_rank_reference(stale_reference, _counterfactual_row_bindings())

    with pytest.raises(ValueError, match="production parity"):
        se.compose_case_explanation(
            engine, case, member_explainer=_deterministic_member_explainer
        )


@pytest.mark.parametrize(
    ("field_name", "mutate"),
    [
        ("percentile_reference_id", lambda value: value + "-stale"),
        ("baseline_daily_reference_id", lambda value: value + "-stale"),
        ("hybrid_daily_reference_id", lambda value: value + "-stale"),
        ("baseline_raw", lambda value: value + 0.01),
        ("baseline_percentile", lambda value: value + 0.01),
        ("baseline_weighted_term", lambda value: value + 0.01),
        ("baseline_rank", lambda value: value + 1),
        ("seed0_gnn_probability", lambda value: min(1.0, value + 0.01)),
        ("seed0_gnn_percentile", lambda value: value - 0.01),
        ("seed0_gnn_weighted_term", lambda value: value - 0.01),
        ("seed0_gnn_rank", lambda value: value + 1),
        ("seed0_hybrid_score", lambda value: value - 0.01),
        ("seed0_hybrid_rank", lambda value: value + 1),
    ],
)
def test_compose_case_explanation_rejects_any_stale_decision_trace_field(
    field_name, mutate
):
    engine, case = _sage_case_fixture()
    trace = case.decision_trace_jsonable()
    trace[field_name] = mutate(trace[field_name])

    with pytest.raises(ValueError, match="decision trace.*frozen"):
        se.compose_case_explanation(
            engine,
            _copy_case(case, decision_trace=trace),
            member_explainer=_deterministic_member_explainer,
        )


@pytest.mark.parametrize(
    ("field_name", "mutate"),
    [
        ("baseline_rank", lambda value: value + 1),
        ("gnn_rank", lambda value: value + 1),
        ("baseline_percentile", lambda value: value + 0.01),
        ("gnn_percentile", lambda value: value - 0.01),
    ],
)
def test_compose_case_explanation_rejects_stale_outer_case_rank_fields(
    field_name, mutate
):
    engine, case = _sage_case_fixture()

    with pytest.raises(ValueError, match="case rank fields.*frozen"):
        se.compose_case_explanation(
            engine,
            _copy_case(case, **{field_name: mutate(getattr(case, field_name))}),
            member_explainer=_deterministic_member_explainer,
        )


def test_compose_case_explanation_rejects_cross_day_baseline_candidate_pool():
    engine, case = _sage_case_fixture()
    reference = engine.rank_reference
    bindings = _counterfactual_row_bindings()
    bindings[3] = ("peer-b", SCORING_DAY + pd.Timedelta(days=1))
    engine.bind_rank_reference(reference, bindings)
    baseline_candidates = (0, 1, 2, 3)
    hybrid_candidates = (0, 1, 2)
    trace = build_decision_trace(
        reference,
        row_index=0,
        baseline_candidate_row_indices=baseline_candidates,
        hybrid_candidate_row_indices=hybrid_candidates,
        daily_budget=5,
    )
    poisoned = _copy_case(
        case,
        baseline_rank=trace["baseline_rank"],
        gnn_rank=trace["seed0_gnn_rank"],
        hybrid_rank=trace["seed0_hybrid_rank"],
        baseline_percentile=trace["baseline_percentile"],
        gnn_percentile=trace["seed0_gnn_percentile"],
        baseline_candidate_row_indices=baseline_candidates,
        hybrid_candidate_row_indices=hybrid_candidates,
        decision_trace=trace,
    )

    with pytest.raises(ValueError, match="baseline_candidate.*scoring_day"):
        se.compose_case_explanation(
            engine,
            poisoned,
            member_explainer=_deterministic_member_explainer,
        )


def test_structural_factor_restart_stability_uses_feature_masks_not_edge_masks():
    spec = AblationSpec(
        factor_id="structural:target",
        kind="structural_provenance",
        edge_source_row_ids=("outside-row",),
        provenance_node_ids=("outside",),
    )
    feature_names = list(gm.caught_feature_names(4))
    frequency = np.zeros(len(feature_names), dtype=float)
    q1 = np.zeros(len(feature_names), dtype=float)
    q3 = np.zeros(len(feature_names), dtype=float)
    for name in (
        "log1p_cotravel_component_size",
        "log1p_households_spanned",
    ):
        index = feature_names.index(name)
        frequency[index] = 0.75
        q1[index] = 0.2
        q3[index] = 0.3

    actual = se._factor_restart_metrics(
        spec,
        [
            {
                "source_row_ids": ["outside-row"],
                "selection_frequency": 1.0,
                "explainer_q1": 0.0,
                "explainer_q3": 0.9,
            }
        ],
        feature_names,
        {
            "selection_frequency": frequency,
            "q1": q1,
            "q3": q3,
            "restart_count": 3,
        },
    )

    assert actual[:2] == pytest.approx((0.75, 0.1))
    assert actual[2] == "feature_mask"


def _synthetic_member_subgraph(node_count, edge_count):
    sources = np.arange(edge_count, dtype=np.int64) % max(node_count, 1)
    targets = (sources + 1) % max(node_count, 1)
    edge_index = torch.tensor(
        np.vstack((sources, targets)), dtype=torch.long
    )
    return se.MemberSubgraph(
        x=torch.ones((node_count, 8), dtype=torch.float32),
        edge_index=edge_index,
        target_index=0,
        original_node_indices=np.arange(node_count, dtype=np.int64),
        tensor_edge_source_row_ids=np.array(
            [f"source:{index}" for index in range(edge_count)],
            dtype=object,
        ),
    )


def _real_two_hop_boundary_engine(neighbor_count, extra_edges):
    node_ids = ["target"] + [
        f"neighbor:{index:03d}" for index in range(neighbor_count)
    ]
    rows = []
    for index, neighbor_id in enumerate(node_ids[1:]):
        rows.append((f"row:star:{index:03d}", "target", neighbor_id))
    for index, (u, v) in enumerate(extra_edges):
        rows.append((f"row:extra:{index:03d}", u, v))
    edges = pd.DataFrame(
        {
            "source_row_id": [row[0] for row in rows],
            "canonical_pair_group_id": [
                f"group:{index:03d}" for index in range(len(rows))
            ],
            "u": [row[1] for row in rows],
            "v": [row[2] for row in rows],
            "avail_time": [SCORING_DAY - pd.Timedelta(hours=1)] * len(rows),
            "rel": [0] * len(rows),
            "edge_type": ["COTRAVEL"] * len(rows),
        }
    )
    engine = se.Seed0ExplanationEngine(
        model=_SAGE(in_dim=8, hidden=4, out=4, num_relations=4),
        edges_typed=edges,
        node_ids=node_ids,
        node_feat={person_id: np.array([1.0]) for person_id in node_ids},
        caught_time={},
        num_rel=4,
    )
    return engine, set(node_ids), {row[0] for row in rows}


def test_real_two_hop_extractor_preserves_exact_boundary_nodes_and_provenance():
    engine, expected_nodes, expected_source_rows = (
        _real_two_hop_boundary_engine(
            127,
            [("neighbor:000", "neighbor:001")],
        )
    )

    local = se.member_subgraph(engine, "target", SCORING_DAY)
    returned_nodes = {
        engine.node_ids[int(index)] for index in local.original_node_indices
    }
    source_rows, source_counts = np.unique(
        local.tensor_edge_source_row_ids, return_counts=True
    )

    assert returned_nodes == expected_nodes
    assert local.x.shape[0] == se.MAX_LOCAL_EXPLANATION_NODES
    assert local.edge_index.shape[1] == se.MAX_LOCAL_EXPLANATION_EDGES
    assert set(source_rows) == expected_source_rows
    assert set(source_counts) == {2}
    assert se.explainability_eligibility(
        engine, "target", SCORING_DAY
    ) == {
        "eligible": True,
        "status": "eligible",
        "node_count": 128,
        "edge_count": 256,
        "max_nodes": 128,
        "max_edges": 256,
        "reason_code": "eligible",
    }


@pytest.mark.parametrize(
    ("neighbor_count", "extra_edges", "reason_code"),
    [
        (128, [], "node_limit_exceeded"),
        (
            127,
            [("neighbor:000", "neighbor:001"), ("neighbor:002", "neighbor:003")],
            "edge_limit_exceeded",
        ),
        (128, [("neighbor:000", "neighbor:001")], "node_and_edge_limits_exceeded"),
    ],
)
def test_real_two_hop_extractor_fails_closed_over_exact_limits(
    neighbor_count, extra_edges, reason_code
):
    engine, expected_nodes, expected_source_rows = (
        _real_two_hop_boundary_engine(neighbor_count, extra_edges)
    )
    local = se.member_subgraph(engine, "target", SCORING_DAY)
    returned_nodes = {
        engine.node_ids[int(index)] for index in local.original_node_indices
    }
    source_rows, source_counts = np.unique(
        local.tensor_edge_source_row_ids, return_counts=True
    )
    eligibility = se.explainability_eligibility(
        engine, "target", SCORING_DAY
    )
    sentinel_calls = []

    def sentinel(*args, **kwargs):
        sentinel_calls.append((args, kwargs))
        raise AssertionError("over-limit real subgraph reached GNNExplainer")

    with pytest.raises(se.ExplainerEligibilityError) as error:
        se.run_member_explanation(
            engine,
            "target",
            SCORING_DAY,
            explainer_factory=sentinel,
        )

    assert returned_nodes == expected_nodes
    assert set(source_rows) == expected_source_rows
    assert set(source_counts) == {2}
    assert eligibility["eligible"] is False
    assert eligibility["status"] == "community_only"
    assert eligibility["reason_code"] == reason_code
    assert error.value.eligibility == eligibility
    assert sentinel_calls == []


def test_explainer_policy_defaults_are_explicit_and_stable():
    assert se.EXPLAINER_RESTART_SEEDS == (0, 1, 2)
    assert se.EXPLAINER_EPOCHS == 150
    assert se.MAX_LOCAL_EXPLANATION_NODES == 128
    assert se.MAX_LOCAL_EXPLANATION_EDGES == 256


@pytest.mark.parametrize(
    ("field_name", "value"),
    [("max_nodes", 127), ("max_nodes", 129), ("max_edges", 255), ("max_edges", 257)],
)
def test_explainability_eligibility_rejects_policy_limit_overrides(
    field_name, value
):
    engine = _sage_explanation_fixture()

    with pytest.raises(ValueError, match=f"{field_name} must be exactly"):
        se.explainability_eligibility(
            engine,
            "target",
            SCORING_DAY,
            **{field_name: value},
        )


def test_explainability_eligibility_accepts_under_limit_exact_subgraph(
    monkeypatch,
):
    engine = _sage_explanation_fixture()
    local = _synthetic_member_subgraph(3, 4)
    monkeypatch.setattr(se, "member_subgraph", lambda *args: local)

    result = se.explainability_eligibility(
        engine, "target", SCORING_DAY
    )

    assert result == {
        "eligible": True,
        "status": "eligible",
        "node_count": 3,
        "edge_count": 4,
        "max_nodes": 128,
        "max_edges": 256,
        "reason_code": "eligible",
    }
    json.dumps(result, allow_nan=False)


def test_explainability_eligibility_accepts_exact_boundary_without_pruning(
    monkeypatch,
):
    engine = _sage_explanation_fixture()
    local = _synthetic_member_subgraph(128, 256)
    returned = []

    def return_local(*args):
        returned.append(local)
        return local

    monkeypatch.setattr(se, "member_subgraph", return_local)

    result = se.explainability_eligibility(
        engine, "target", SCORING_DAY
    )

    assert result["eligible"] is True
    assert result["reason_code"] == "eligible"
    assert result["node_count"] == 128
    assert result["edge_count"] == 256
    assert returned == [local]
    assert local.x.shape == (128, 8)
    assert local.edge_index.shape == (2, 256)
    assert len(local.tensor_edge_source_row_ids) == 256


@pytest.mark.parametrize(
    ("node_count", "edge_count", "reason_code"),
    [
        (129, 0, "node_limit_exceeded"),
        (2, 257, "edge_limit_exceeded"),
        (129, 257, "node_and_edge_limits_exceeded"),
    ],
)
def test_explainability_eligibility_fails_closed_without_pruning(
    monkeypatch, node_count, edge_count, reason_code
):
    engine = _sage_explanation_fixture()
    local = _synthetic_member_subgraph(node_count, edge_count)
    monkeypatch.setattr(se, "member_subgraph", lambda *args: local)

    result = se.explainability_eligibility(
        engine, "target", SCORING_DAY
    )

    assert result == {
        "eligible": False,
        "status": "community_only",
        "node_count": node_count,
        "edge_count": edge_count,
        "max_nodes": 128,
        "max_edges": 256,
        "reason_code": reason_code,
    }
    assert local.x.shape[0] == node_count
    assert local.edge_index.shape[1] == edge_count
    assert len(local.tensor_edge_source_row_ids) == edge_count


def test_compose_rejects_oversized_member_before_gnnexplainer_or_expansion(
    monkeypatch,
):
    engine, case = _sage_case_fixture()
    local = _synthetic_member_subgraph(129, 0)
    monkeypatch.setattr(se, "member_subgraph", lambda *args: local)
    monkeypatch.setattr(
        se,
        "diagnostic_edge_source_set_probability",
        lambda *args, **kwargs: pytest.fail(
            "oversized explanation must not run counterfactual scoring"
        ),
    )

    def should_not_explain(*args, **kwargs):
        pytest.fail("oversized explanation must not run GNNExplainer")

    with pytest.raises(se.ExplainerEligibilityError) as error:
        se.compose_case_explanation(
            engine,
            case,
            member_explainer=should_not_explain,
        )

    assert error.value.status == "community_only"
    assert error.value.reason_code == "node_limit_exceeded"
    assert error.value.eligibility["node_count"] == 129
    assert str(error.value) == (
        "community_only explanation is ineligible: node_limit_exceeded"
    )


def test_run_member_explanation_rejects_oversized_member_before_gnnexplainer(
    monkeypatch,
):
    engine = _sage_explanation_fixture()
    local = _synthetic_member_subgraph(129, 0)
    monkeypatch.setattr(se, "member_subgraph", lambda *args: local)

    def should_not_explain(*args, **kwargs):
        pytest.fail("oversized member must not reach GNNExplainer")

    with pytest.raises(se.ExplainerEligibilityError) as error:
        se.run_member_explanation(
            engine,
            "target",
            SCORING_DAY,
            explainer_factory=should_not_explain,
        )

    assert error.value.status == "community_only"
    assert error.value.reason_code == "node_limit_exceeded"


def _complete_structural_mapping(scope):
    return {
        "complete": True,
        "scoring_day": scope.scoring_day.isoformat(),
        "component_id": scope.component_id,
        "community_key": scope.community_key,
        "nodes": [
            {
                "node_id": node["node_id"],
                "target": node["target"],
                "message_distance": node["message_distance"],
                "pooled_member": node["pooled_member"],
                "caught_before_snapshot": node["caught_before_snapshot"],
                "caught_label_available_time": node[
                    "caught_label_available_time"
                ],
            }
            for node in scope.iter_nodes()
        ],
        "edges": [
            {
                key: edge[key]
                for key in (
                    "edge_id",
                    "u",
                    "v",
                    "rel",
                    "edge_type",
                    "source_row_ids",
                    "source_row_count",
                )
                if key in edge
            }
            for edge in scope.iter_edges()
        ],
        "provenance_observations": list(scope.iter_provenance()),
    }


def test_structural_community_control_is_json_safe_and_attribution_free():
    engine = _sage_explanation_fixture(
        caught_time={"hop1": SCORING_DAY - pd.Timedelta(seconds=1)}
    )
    scope = engine.community("target", SCORING_DAY)

    control = se.build_structural_community_control(scope)

    assert control["detail_kind"] == "community_only"
    assert control["kind"] == "community_only"
    assert control["evidence_kind"] == "structural_provenance"
    assert control["community_key"] == scope.community_key
    assert control["component_id"] == scope.component_id
    assert control["scoring_day"] == SCORING_DAY.isoformat()
    assert control["node_count"] == len(scope.node_ids)
    assert control["edge_count"] == sum(1 for _ in scope.iter_edges())
    assert set(control["communities"]) == {
        scope.community_key,
    }
    assert {node["node_id"] for node in control["nodes"]} == set(
        scope.node_ids
    )
    assert all(
        set(node)
        <= {
            "node_id",
            "target",
            "message_distance",
            "pooled_member",
            "caught_before_snapshot",
            "caught_label_available_time",
        }
        for node in control["nodes"]
    )
    nodes_by_id = {node["node_id"]: node for node in control["nodes"]}
    assert nodes_by_id["target"]["target"] is True
    assert all(
        node["target"] is (node["node_id"] == "target")
        for node in control["nodes"]
    )
    assert nodes_by_id["target"]["caught_before_snapshot"] is False
    assert nodes_by_id["target"]["caught_label_available_time"] is None
    assert nodes_by_id["hop1"]["caught_before_snapshot"] is True
    assert (
        nodes_by_id["hop1"]["caught_label_available_time"]
        == "2025-01-01T23:59:59+00:00"
    )
    assert all(
        node["caught_label_available_time"] is None
        or pd.Timestamp(node["caught_label_available_time"]) < SCORING_DAY
        for node in control["nodes"]
    )
    assert all(
        set(edge)
        <= {
            "edge_id",
            "u",
            "v",
            "rel",
            "edge_type",
            "source_row_ids",
            "source_row_count",
            "message_hop",
            "available_times",
        }
        for edge in control["edges"]
    )
    serialized = json.dumps(control, sort_keys=True, allow_nan=False)
    for forbidden in (
        "attributions",
        "explanation",
        "narrative",
        "hidden",
        "rank",
        "mask",
        "false_negative_flag",
    ):
        assert forbidden not in serialized.casefold()
    assert control["evidence_boundary"] == {
        "edge_rule": "available_time < snapshot",
        "caught_rule": "label_available_time_utc < snapshot",
        "snapshot": SCORING_DAY.isoformat(),
    }

    mapping_control = se.build_structural_community_control(
        _complete_structural_mapping(scope)
    )
    projected_control = mapping_control
    assert projected_control["detail_kind"] == "community_only"
    assert projected_control["node_count"] == len(scope.node_ids)
    assert projected_control["edge_count"] == sum(1 for _ in scope.iter_edges())
    assert any(
        edge["available_times"] for edge in projected_control["edges"]
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["provenance_observations"].clear(),
        lambda payload: payload["provenance_observations"].pop(),
        lambda payload: payload["provenance_observations"][0].update(
            available_time=SCORING_DAY.isoformat()
        ),
        lambda payload: payload["provenance_observations"].append(
            {
                "edge_id": "edge:not-emitted",
                "source_row_id": "row:extra",
                "available_time": (
                    SCORING_DAY - pd.Timedelta(hours=1)
                ).isoformat(),
            }
        ),
        lambda payload: payload["edges"][0].update(
            source_row_count=len(payload["edges"][0]["source_row_ids"]) + 1
        ),
    ],
)
def test_structural_mapping_requires_complete_as_of_provenance(mutate):
    scope = _sage_explanation_fixture().community("target", SCORING_DAY)
    payload = _complete_structural_mapping(scope)
    mutate(payload)

    with pytest.raises(ValueError, match="provenance|source row|strictly"):
        se.build_structural_community_control(payload)


def test_structural_mapping_rejects_source_row_reused_across_edges():
    scope = _sage_explanation_fixture().community("target", SCORING_DAY)
    payload = _complete_structural_mapping(scope)
    first_edge = payload["edges"][0]
    second_edge = payload["edges"][1]
    source_row_id = first_edge["source_row_ids"][0]
    second_edge["source_row_ids"] = [source_row_id]
    second_edge["source_row_count"] = 1
    payload["provenance_observations"] = [
        observation
        for observation in payload["provenance_observations"]
        if observation["edge_id"] != second_edge["edge_id"]
    ]
    payload["provenance_observations"].append(
        {
            "edge_id": second_edge["edge_id"],
            "source_row_id": source_row_id,
            "available_time": (
                SCORING_DAY - pd.Timedelta(hours=1)
            ).isoformat(),
        }
    )

    with pytest.raises(ValueError, match="source_row_id.*multiple edges"):
        se.build_structural_community_control(payload)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["nodes"][0].update(metadata={"hidden": True}),
        lambda payload: payload["nodes"][0].update(target={"status": "selected"}),
        lambda payload: payload["nodes"][0].update(target=1),
        lambda payload: payload["nodes"][0].update(message_distance=True),
        lambda payload: payload["nodes"][0].update(message_distance=-1),
        lambda payload: payload["nodes"][0].update(pooled_member=1),
        lambda payload: payload["edges"][0].update(edge_type="future_outcome"),
        lambda payload: payload["edges"][0].update(
            source_row_ids=[" "]
        ),
        lambda payload: payload["provenance_observations"][0].update(
            metadata={"rank": 1}
        ),
    ],
)
def test_structural_mapping_rejects_unsafe_nested_or_invalid_members(mutate):
    scope = _sage_explanation_fixture().community("target", SCORING_DAY)
    payload = _complete_structural_mapping(scope)
    mutate(payload)

    with pytest.raises(ValueError, match="structural|forbidden|nonnegative|boolean|source"):
        se.build_structural_community_control(payload)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: next(
            node for node in payload["nodes"] if node["node_id"] == "hop1"
        ).update(caught_label_available_time=SCORING_DAY.isoformat()),
        lambda payload: next(
            node for node in payload["nodes"] if node["node_id"] == "target"
        ).update(caught_before_snapshot=True),
        lambda payload: next(
            node for node in payload["nodes"] if node["node_id"] == "target"
        ).update(
            caught_label_available_time=(
                SCORING_DAY - pd.Timedelta(hours=1)
            ).isoformat()
        ),
    ],
)
def test_structural_mapping_requires_as_of_consistent_catch_fields(mutate):
    scope = _sage_explanation_fixture().community("target", SCORING_DAY)
    payload = _complete_structural_mapping(scope)
    mutate(payload)

    with pytest.raises(ValueError, match="caught|snapshot|strictly"):
        se.build_structural_community_control(payload)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["edges"][0].update(
            edge_type="futureOutcome_rankMaskNarrative"
        ),
        lambda payload: payload["nodes"][0].update(
            **{"futureOutcome_rankMaskNarrative": True}
        ),
    ],
)
def test_structural_mapping_rejects_compound_forbidden_keys_and_values(mutate):
    scope = _sage_explanation_fixture().community("target", SCORING_DAY)
    payload = _complete_structural_mapping(scope)
    mutate(payload)

    with pytest.raises(ValueError, match="forbidden structural token"):
        se.build_structural_community_control(payload)


def test_structural_community_control_accepts_complete_isolated_community():
    isolated_mapping = {
        "complete": True,
        "scoring_day": SCORING_DAY.isoformat(),
        "component_id": "component:isolated",
        "community_key": "community:isolated",
        "nodes": [
            {
                "node_id": "isolated",
                "target": True,
                "message_distance": 0,
                "pooled_member": True,
                "caught_before_snapshot": False,
                "caught_label_available_time": None,
            }
        ],
        "edges": [],
        "provenance_observations": [],
    }

    mapping_control = se.build_structural_community_control(isolated_mapping)

    assert mapping_control["complete"] is True
    assert mapping_control["node_count"] == 1
    assert mapping_control["edge_count"] == 0
    assert mapping_control["edges"] == []

    empty_edges = pd.DataFrame(
        columns=[
            "source_row_id",
            "canonical_pair_group_id",
            "u",
            "v",
            "avail_time",
            "rel",
            "edge_type",
        ]
    )
    isolated_engine = se.Seed0ExplanationEngine(
        model=_SAGE(in_dim=8, hidden=4, out=4, num_relations=4),
        edges_typed=empty_edges,
        node_ids=["isolated"],
        node_feat={"isolated": np.array([1.0])},
        caught_time={},
        num_rel=4,
    )
    scope_control = se.build_structural_community_control(
        isolated_engine.community("isolated", SCORING_DAY)
    )

    assert scope_control["complete"] is True
    assert scope_control["node_count"] == 1
    assert scope_control["edge_count"] == 0
    assert scope_control["edges"] == []


def test_existing_compose_case_explanation_contract_remains_hybrid_only():
    engine, case = _sage_case_fixture()

    explanation = se.compose_case_explanation(
        engine,
        case,
        member_explainer=_deterministic_member_explainer,
    )

    assert isinstance(case, HybridOnlyCase)
    assert explanation["case_id"] == "case:target"
    assert explanation["person_id"] == "target"
    assert explanation["attributions"]["scope"]["restart_seeds"] == [0, 1, 2]
    assert explanation["attributions"]["scope"]["epochs"] == 150
