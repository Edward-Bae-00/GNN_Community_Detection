import json
from types import MappingProxyType, SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import torch

from gnn import graphmodel_rgcn as gm
from gnn import learned_cell
from gnn import sage_explainer as se
from gnn.graphmodel_alt import _SAGE
from gnn.graphmodel_rgcn import _RGCN
from gnn.learned_cell import _asof_x_caught, _score_pool
from gnn.recovery_observability import (
    HybridOnlyCase,
    RecoveryAnchor,
    build_decision_trace,
    build_rank_reference,
)
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


def test_structural_provenance_scans_each_relation_graph_once(monkeypatch):
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

    assert calls == {"connected_components": 2}


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
        "snapshot": 2,
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


def _sage_explanation_fixture():
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
        caught_time={},
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

    explainer = se.make_gnn_explainer(wrapper, epochs=2)

    assert explainer.model is wrapper
    assert explainer.model_config.mode.value == "binary_classification"
    assert explainer.model_config.task_level.value == "node"
    assert explainer.model_config.return_type.value == "raw"
    assert explainer.node_mask_type.value == "attributes"
    assert explainer.edge_mask_type.value == "object"
    assert explainer.algorithm.epochs == 2


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
        assert epochs == 2
        return FakeExplainer(wrapper)

    first = se.run_member_explanation(
        engine,
        "target",
        SCORING_DAY,
        restart_seeds=(0, 1, 2),
        epochs=2,
        explainer_factory=explainer_factory,
    )
    second = se.run_member_explanation(
        engine,
        "target",
        SCORING_DAY,
        restart_seeds=(0, 1, 2),
        epochs=2,
        explainer_factory=explainer_factory,
    )

    assert first["status"] == "ok"
    assert first["restart_seeds"] == (0, 1, 2)
    assert len(first["edge_masks"]) == len(first["feature_masks"]) == 3
    for actual, expected in zip(first["edge_masks"], second["edge_masks"]):
        np.testing.assert_array_equal(actual, expected)
    for actual, expected in zip(
        first["feature_masks"], second["feature_masks"]
    ):
        np.testing.assert_array_equal(actual, expected)
    assert len(calls) == 6
    np.testing.assert_array_equal(
        engine.snapshot(SCORING_DAY + pd.Timedelta(days=2)).probabilities,
        expected_later_day,
    )
    assert canonical_model.training is False
    assert all(not parameter.requires_grad for parameter in canonical_model.parameters())
    for actual, expected in zip(canonical_model.parameters(), expected_parameters):
        torch.testing.assert_close(actual, expected)


def test_member_explanation_reports_empty_message_edges_without_optimizer_call():
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

    def forbidden_factory(*args, **kwargs):
        raise AssertionError("empty explanations must not run GNNExplainer")

    result = se.run_member_explanation(
        engine,
        "target",
        SCORING_DAY,
        explainer_factory=forbidden_factory,
    )

    assert result["status"] == "no-message-edges"
    assert result["restart_seeds"] == (0, 1, 2)
    assert len(result["edge_masks"]) == 3
    assert all(mask.size == 0 for mask in result["edge_masks"])
    assert result["feature_masks"] == ()


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
            epochs=1,
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


def test_flow_stages_preserve_complete_membership_and_only_change_emphasis():
    community = _sage_explanation_fixture().community("target", SCORING_DAY)

    stages = se.build_flow_stages(community)

    node_ids = tuple(sorted(community["nodes_by_id"]))
    edge_ids = tuple(sorted(edge["edge_id"] for edge in community["edges"]))
    assert [stage["stage_id"] for stage in stages] == [
        "first_hop",
        "second_hop",
        "component_pool",
        "rank_fusion",
    ]
    assert all(tuple(stage["node_ids"]) == node_ids for stage in stages)
    assert all(tuple(stage["edge_ids"]) == edge_ids for stage in stages)
    assert stages[0]["emphasized_edge_ids"] == ["g-cot:rel:0", "g-res:rel:1"]
    assert stages[1]["emphasized_edge_ids"] == list(edge_ids)
    assert stages[2]["emphasized_edge_ids"] == ["g-cot:rel:0"]
    assert stages[3]["emphasized_edge_ids"] == []


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
        daily_budget=25,
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
        [edge_values[str(source_id)] for source_id in local.tensor_edge_source_row_ids],
        dtype=float,
    )
    feature_mask = np.arange(1, local.x.shape[1] + 1, dtype=float)
    snapshot = engine.snapshot(scoring_day)
    logit = float(snapshot.prepool_logits[engine.person_index[person_id]])
    return {
        "edge_masks": tuple(edge_mask.copy() for _ in restart_seeds),
        "feature_masks": tuple(feature_mask.copy() for _ in restart_seeds),
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


def test_compose_case_explanation_collapses_member_masks_and_proves_parity():
    engine, case = _sage_case_fixture()

    explanation = se.compose_case_explanation(
        engine, case, member_explainer=_deterministic_member_explainer
    )

    assert explanation["case_id"] == "case:target"
    assert explanation["snapshot"]["component_member_ids"] == [
        "poolmate",
        "target",
    ]
    assert explanation["parity"] == {
        "production_seed0_probability": True,
        "pooled_logit_decomposition": True,
        "frozen_percentile": True,
        "frozen_daily_hybrid_rank": True,
        "anchor_event": True,
    }
    edge_stats = {
        edge["edge_id"]: edge for edge in explanation["community"]["edges"]
    }
    assert edge_stats["g-cot:rel:0"]["explainer_median"] == pytest.approx(1.0)
    assert edge_stats["g-res:rel:1"]["explainer_median"] == pytest.approx(0.5)
    assert edge_stats["g-plate:rel:2"]["explainer_median"] == pytest.approx(0.125)
    assert edge_stats["g-cot:rel:0"]["selection_frequency"] == 1.0
    assert edge_stats["g-res:rel:1"]["selection_frequency"] == 0.0
    assert edge_stats["g-plate:rel:2"]["selection_frequency"] == 0.0
    assert explanation["stability"]["signed_effect_source"] == (
        "counterfactual_only"
    )
    assert explanation["stability"]["edge_restart_aggregate"][
        "top_factor_agreement"
    ] == 1.0
    assert explanation["display_feature_mask_stats"][0]["feature_name"] == "bias"
    assert explanation["factors"]
    assert all("counterfactual" in factor for factor in explanation["factors"])
    assert [point["fraction"] for point in explanation["faithfulness"]["points"]] == [
        0.1,
        0.25,
        0.5,
    ]
    assert all(
        set(stage["node_ids"])
        == set(explanation["community"]["nodes_by_id"])
        for stage in explanation["flow_stages"]
    )
    assert explanation["evidence_boundary"] == {
        "snapshot": "2025-01-02T00:00:00+00:00",
        "edge_rule": "available_time < snapshot",
        "caught_rule": "label_available_time_utc < snapshot",
    }
    json.dumps(explanation, allow_nan=False, sort_keys=True)


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
        ("daily_budget", lambda value: value - 1),
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
        daily_budget=25,
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
