"""Exact seed-0 GraphSAGE day snapshots and complete message communities."""
from __future__ import annotations

import copy
from dataclasses import dataclass

import networkx as nx
import numpy as np
import pandas as pd
import torch

from gnn.learned_cell import build_day_snapshot_inputs, _pool_by_roots_torch


@dataclass(frozen=True)
class DaySnapshot:
    scoring_day: pd.Timestamp
    active_edges: pd.DataFrame
    x: torch.Tensor
    edge_index: torch.Tensor
    edge_type: torch.Tensor
    tensor_edge_source_row_ids: np.ndarray
    component_roots: np.ndarray
    prepool_embeddings: torch.Tensor
    prepool_logits: torch.Tensor
    pooled_logits: torch.Tensor
    probabilities: np.ndarray
    caught_before_snapshot: frozenset[str]


class Seed0ExplanationEngine:
    def __init__(
        self,
        *,
        model,
        edges_typed,
        node_ids,
        node_feat,
        caught_time,
        num_rel,
        rank_reference=None,
    ):
        self.model = model.eval()
        self.edges_typed = edges_typed.copy(deep=True)
        self.node_ids = tuple(node_ids)
        if len(self.node_ids) != len(set(self.node_ids)):
            raise ValueError("node_ids must be unique")
        self.node_feat = {
            person_id: _detached_feature(node_feat[person_id])
            for person_id in self.node_ids
        }
        self.caught_time = _detached_caught_times(caught_time)
        self.num_rel = int(num_rel)
        self.person_index = {
            person_id: index for index, person_id in enumerate(self.node_ids)
        }
        self.rank_reference = copy.deepcopy(rank_reference)
        self._snapshot_cache: dict[pd.Timestamp, DaySnapshot] = {}

    def snapshot(self, scoring_day) -> DaySnapshot:
        day = _scoring_day(scoring_day)
        cached = self._snapshot_cache.get(day)
        if cached is not None:
            return cached

        inputs = build_day_snapshot_inputs(
            day,
            self.edges_typed,
            self.node_ids,
            self.node_feat,
            self.caught_time,
            self.person_index,
            num_rel=self.num_rel,
        )
        self.model.eval()
        with torch.no_grad():
            embeddings = self.model.enc(
                inputs.x, inputs.edge_index, edge_type=inputs.edge_type
            )
            prepool_logits = self.model.head(embeddings).squeeze(-1)
            pooled_embeddings = _pool_by_roots_torch(
                embeddings, inputs.component_roots
            )
            pooled_logits = self.model.head(pooled_embeddings).squeeze(-1)
            probabilities = (
                torch.sigmoid(pooled_logits).detach().cpu().numpy().copy()
            )

        component_roots = np.array(inputs.component_roots, copy=True)
        component_roots.setflags(write=False)
        tensor_provenance = np.array(
            inputs.tensor_edge_source_row_ids, dtype=object, copy=True
        )
        tensor_provenance.setflags(write=False)
        probabilities.setflags(write=False)
        result = DaySnapshot(
            scoring_day=inputs.scoring_day,
            active_edges=inputs.active_edges.copy(deep=True),
            x=inputs.x.detach().clone(),
            edge_index=inputs.edge_index.detach().clone(),
            edge_type=inputs.edge_type.detach().clone(),
            tensor_edge_source_row_ids=tensor_provenance,
            component_roots=component_roots,
            prepool_embeddings=embeddings.detach().clone(),
            prepool_logits=prepool_logits.detach().clone(),
            pooled_logits=pooled_logits.detach().clone(),
            probabilities=probabilities,
            caught_before_snapshot=inputs.caught_before_snapshot,
        )
        self._snapshot_cache[day] = result
        return result

    def relationship_categories(self, person_id, scoring_day):
        if person_id not in self.person_index:
            raise KeyError(f"unknown person_id: {person_id}")
        snapshot = self.snapshot(scoring_day)
        incident = snapshot.active_edges.loc[
            (snapshot.active_edges["u"] == person_id)
            | (snapshot.active_edges["v"] == person_id)
        ]
        return tuple(sorted(set(incident["edge_type"].astype(str))))

    def community(self, person_id, scoring_day):
        return build_complete_community(self, person_id, scoring_day)


def _detached_feature(value):
    if torch.is_tensor(value):
        return value.detach().cpu().numpy().copy()
    return np.array(value, copy=True)


def _detached_caught_times(caught_time):
    detached = {}
    for person_id, value in dict(caught_time).items():
        timestamp = pd.to_datetime(value, utc=True, errors="raise")
        if timestamp is None or pd.isna(timestamp):
            continue
        if not isinstance(timestamp, pd.Timestamp):
            raise ValueError(f"caught_time[{person_id!r}] must be a scalar timestamp")
        detached[person_id] = timestamp
    return detached


def _scoring_day(value):
    timestamp = pd.to_datetime(value, utc=True, errors="raise")
    if timestamp is None or pd.isna(timestamp) or not isinstance(timestamp, pd.Timestamp):
        raise ValueError("scoring_day must be a non-null scalar timestamp")
    return timestamp.floor("D")


def build_complete_community(engine, target_person_id, scoring_day):
    if target_person_id not in engine.person_index:
        raise KeyError(f"unknown person_id: {target_person_id}")
    snapshot = engine.snapshot(scoring_day)
    target_index = engine.person_index[target_person_id]
    target_root = snapshot.component_roots[target_index]
    pooled_indices = set(
        np.flatnonzero(snapshot.component_roots == target_root).tolist()
    )

    adjacency = {index: set() for index in range(len(engine.node_ids))}
    for source, target in snapshot.edge_index.t().cpu().numpy():
        adjacency[int(source)].add(int(target))
        adjacency[int(target)].add(int(source))
    distances = {index: 0 for index in pooled_indices}
    frontier = set(pooled_indices)
    for hop in (1, 2):
        next_frontier = {
            neighbor
            for index in frontier
            for neighbor in adjacency[index]
            if neighbor not in distances
        }
        distances.update({index: hop for index in next_frontier})
        frontier = next_frontier

    included_people = {engine.node_ids[index] for index in distances}
    internal = snapshot.active_edges.loc[
        snapshot.active_edges["u"].isin(included_people)
        & snapshot.active_edges["v"].isin(included_people)
    ].copy(deep=True)

    graph = nx.Graph()
    graph.add_nodes_from(sorted(included_people))
    canonical_graph_edges = sorted(
        {
            tuple(sorted((str(u), str(v))))
            for u, v in internal[["u", "v"]].itertuples(index=False, name=None)
        }
    )
    graph.add_edges_from(canonical_graph_edges)
    positions = _normalized_layout(graph)

    nodes = []
    for person_id in sorted(included_people):
        index = engine.person_index[person_id]
        record = {
            "node_id": person_id,
            "x": float(positions[person_id][0]),
            "y": float(positions[person_id][1]),
            "target": person_id == target_person_id,
            "pooled_member": index in pooled_indices,
            "caught_before_snapshot": (
                person_id in snapshot.caught_before_snapshot
            ),
            "caught_label_available_time": None,
        }
        if person_id in snapshot.caught_before_snapshot:
            record["caught_label_available_time"] = engine.caught_time[
                person_id
            ].isoformat()
        nodes.append(record)
    nodes_by_id = {node["node_id"]: node for node in nodes}

    edges = []
    for (group_id, relation), frame in internal.groupby(
        ["canonical_pair_group_id", "rel"], sort=True
    ):
        endpoint_pairs = {
            tuple(sorted((str(row.u), str(row.v))))
            for row in frame.itertuples(index=False)
        }
        if len(endpoint_pairs) != 1:
            raise ValueError(
                "canonical_pair_group_id contains inconsistent endpoint pairs"
            )
        edge_types = set(frame["edge_type"].astype(str))
        if len(edge_types) != 1:
            raise ValueError(
                "canonical_pair_group_id contains inconsistent edge types"
            )
        u, v = next(iter(endpoint_pairs))
        observations = sorted(
            (
                {
                    "source_row_id": str(row.source_row_id),
                    "available_time": pd.Timestamp(row.avail_time).isoformat(),
                }
                for row in frame.itertuples(index=False)
            ),
            key=lambda observation: (
                observation["available_time"],
                observation["source_row_id"],
            ),
        )
        source_ids = sorted(
            observation["source_row_id"] for observation in observations
        )
        edges.append(
            {
                "edge_id": f"{group_id}:rel:{int(relation)}",
                "u": u,
                "v": v,
                "rel": int(relation),
                "edge_type": next(iter(edge_types)),
                "source_row_ids": source_ids,
                "message_hop": max(
                    distances[engine.person_index[u]],
                    distances[engine.person_index[v]],
                ),
                "observations": observations,
            }
        )
    edges.sort(key=lambda edge: edge["edge_id"])
    return {
        "complete": True,
        "nodes": nodes,
        "nodes_by_id": nodes_by_id,
        "edges": edges,
        "base_source_row_ids": sorted(internal["source_row_id"].astype(str)),
        "provenance_expansions": [],
    }


def _normalized_layout(graph):
    if len(graph) == 1:
        person_id = next(iter(graph.nodes))
        return {person_id: np.array([0.5, 0.5], dtype=float)}
    raw_positions = nx.spring_layout(graph, seed=0)
    values = np.array([raw_positions[node] for node in sorted(graph.nodes)], dtype=float)
    minimum = values.min(axis=0)
    maximum = values.max(axis=0)
    span = maximum - minimum
    positions = {}
    for person_id, point in raw_positions.items():
        normalized = np.empty(2, dtype=float)
        for axis in (0, 1):
            normalized[axis] = (
                (point[axis] - minimum[axis]) / span[axis]
                if span[axis] > 0
                else 0.5
            )
        positions[person_id] = normalized
    return positions
