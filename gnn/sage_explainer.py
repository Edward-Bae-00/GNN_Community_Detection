"""Exact seed-0 GraphSAGE day snapshots and complete message communities."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass

import networkx as nx
import numpy as np
import pandas as pd
import torch
from scipy.stats import rankdata
from torch_geometric.explain import Explainer, GNNExplainer, ModelConfig
from torch_geometric.utils import k_hop_subgraph

from gnn import learned_cell
from gnn.graphmodel_rgcn import caught_feature_names
from gnn.recovery_observability import (
    FrozenRankReference,
    HybridOnlyCase,
    _selection_tiebreak,
    build_decision_trace,
)


_ABLATION_KINDS = frozenset(
    {
        "pair_relation",
        "caught_flag",
        "relation_star",
        "structural_provenance",
        "cotravel_pool",
    }
)

FORBIDDEN_EXPLANATION_FIELDS = frozenset(
    {
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
    }
)


def _canonical_string_ids(values, *, field_name):
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{field_name} must contain strings")
    try:
        normalized = tuple(values)
    except TypeError as exc:
        raise ValueError(f"{field_name} must contain strings") from exc
    if any(not isinstance(value, str) for value in normalized):
        raise ValueError(f"{field_name} must contain strings")
    if any(not value.strip() for value in normalized):
        raise ValueError(f"{field_name} must contain non-blank strings")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} must not contain duplicate IDs")
    return tuple(sorted(normalized))


@dataclass(frozen=True)
class AblationSpec:
    factor_id: str
    kind: str
    edge_source_row_ids: tuple[str, ...] = ()
    caught_person_ids: tuple[str, ...] = ()
    provenance_node_ids: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.factor_id, str) or not self.factor_id.strip():
            raise ValueError("factor_id must be a non-blank string")
        object.__setattr__(self, "factor_id", self.factor_id.strip())
        if self.kind not in _ABLATION_KINDS:
            raise ValueError(f"unsupported ablation kind: {self.kind}")
        for field_name in (
            "edge_source_row_ids",
            "caught_person_ids",
            "provenance_node_ids",
        ):
            object.__setattr__(
                self,
                field_name,
                _canonical_string_ids(
                    getattr(self, field_name), field_name=field_name
                ),
            )

        if self.kind in {
            "pair_relation",
            "relation_star",
            "cotravel_pool",
            "structural_provenance",
        } and not self.edge_source_row_ids:
            raise ValueError(
                f"{self.kind} requires nonempty edge_source_row_ids"
            )
        if self.kind == "caught_flag" and not self.caught_person_ids:
            raise ValueError("caught_flag requires nonempty caught_person_ids")
        if self.kind == "structural_provenance" and not self.provenance_node_ids:
            raise ValueError(
                "structural_provenance requires nonempty provenance_node_ids"
            )

        edge_only_kinds = {
            "pair_relation",
            "relation_star",
            "cotravel_pool",
        }
        if self.kind in edge_only_kinds and (
            self.caught_person_ids or self.provenance_node_ids
        ):
            raise ValueError(
                f"{self.kind} requires exclusive evidence in edge_source_row_ids"
            )
        if self.kind == "caught_flag" and (
            len(self.caught_person_ids) != 1
            or self.edge_source_row_ids
            or self.provenance_node_ids
        ):
            raise ValueError(
                "caught_flag requires exclusive evidence for exactly one caught person"
            )
        if self.kind == "structural_provenance" and self.caught_person_ids:
            raise ValueError(
                "structural_provenance requires exclusive edge and provenance evidence"
            )

        factor_id_patterns = {
            "pair_relation": r"pair:.+:rel:[0-9]+",
            "relation_star": r"relation-star:.+:rel:[0-9]+",
            "caught_flag": r"caught:.+",
            "structural_provenance": r"structural:.+",
            "cotravel_pool": r"cotravel-pool:.+:rel:[0-9]+",
        }
        if re.fullmatch(factor_id_patterns[self.kind], self.factor_id) is None:
            raise ValueError(
                f"factor_id does not match {self.kind} generated ID syntax"
            )
        if self.kind == "caught_flag" and self.factor_id != (
            f"caught:{self.caught_person_ids[0]}"
        ):
            raise ValueError(
                "caught_flag factor_id must match its caught person evidence"
            )


def _nonnegative_unique_indices(values, *, field_name):
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{field_name} must contain row indices")
    try:
        indices = tuple(values)
    except TypeError as exc:
        raise ValueError(f"{field_name} must contain row indices") from exc
    if not indices:
        raise ValueError(f"{field_name} must not be empty")
    if any(
        not isinstance(index, (int, np.integer))
        or isinstance(index, (bool, np.bool_))
        or index < 0
        for index in indices
    ):
        raise ValueError(f"{field_name} must contain nonnegative row indices")
    normalized = tuple(int(index) for index in indices)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} must not contain duplicate row indices")
    return normalized


@dataclass(frozen=True)
class CounterfactualContext:
    person_id: str
    row_index: int
    scoring_day: pd.Timestamp
    same_day_person_row_indices: tuple[int, ...]
    candidate_row_indices: tuple[int, ...]
    original_hybrid_rank: int

    def __post_init__(self):
        if not isinstance(self.person_id, str) or not self.person_id.strip():
            raise ValueError("person_id must be a non-blank string")
        object.__setattr__(self, "person_id", self.person_id.strip())
        if (
            not isinstance(self.row_index, (int, np.integer))
            or isinstance(self.row_index, (bool, np.bool_))
            or self.row_index < 0
        ):
            raise ValueError("row_index must be a nonnegative integer")
        object.__setattr__(self, "row_index", int(self.row_index))
        object.__setattr__(self, "scoring_day", _scoring_day(self.scoring_day))
        same_day = _nonnegative_unique_indices(
            self.same_day_person_row_indices,
            field_name="same_day_person_row_indices",
        )
        candidates = _nonnegative_unique_indices(
            self.candidate_row_indices,
            field_name="candidate_row_indices",
        )
        if self.row_index not in same_day:
            raise ValueError("anchor row_index must be a same-day person row")
        if not set(same_day).issubset(candidates):
            raise ValueError(
                "every same-day person row must belong to candidate_row_indices"
            )
        object.__setattr__(self, "same_day_person_row_indices", same_day)
        object.__setattr__(self, "candidate_row_indices", candidates)
        if (
            not isinstance(self.original_hybrid_rank, (int, np.integer))
            or isinstance(self.original_hybrid_rank, (bool, np.bool_))
            or self.original_hybrid_rank <= 0
        ):
            raise ValueError("original_hybrid_rank must be a positive integer")
        original_rank = int(self.original_hybrid_rank)
        if original_rank > len(candidates):
            raise ValueError(
                "original_hybrid_rank exceeds the candidate reference"
            )
        object.__setattr__(self, "original_hybrid_rank", original_rank)


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


class PrePoolSAGELogitWrapper(torch.nn.Module):
    """Expose the homogeneous GraphSAGE member logits before component pooling."""

    def __init__(self, model: torch.nn.Module):
        super().__init__()
        self.model = model

    def forward(self, x, edge_index):
        embeddings = self.model.enc(x, edge_index)
        return self.model.head(embeddings).squeeze(-1)


@dataclass(frozen=True, init=False)
class MemberSubgraph:
    """Immutable two-hop inputs with detached tensor-edge provenance."""

    _x: torch.Tensor
    _edge_index: torch.Tensor
    target_index: int
    _original_node_indices: np.ndarray
    _tensor_edge_source_row_ids: np.ndarray

    def __init__(
        self,
        *,
        x,
        edge_index,
        target_index,
        original_node_indices,
        tensor_edge_source_row_ids,
    ):
        if not torch.is_tensor(x) or x.ndim != 2:
            raise ValueError("member subgraph x must be a two-dimensional tensor")
        if (
            not torch.is_tensor(edge_index)
            or edge_index.ndim != 2
            or edge_index.shape[0] != 2
        ):
            raise ValueError("member subgraph edge_index must have shape [2, E]")
        nodes = np.array(original_node_indices, dtype=np.int64, copy=True)
        provenance = np.array(
            tensor_edge_source_row_ids, dtype=object, copy=True
        )
        if nodes.ndim != 1 or nodes.shape[0] != x.shape[0]:
            raise ValueError(
                "member subgraph nodes must align with node features"
            )
        if provenance.ndim != 1 or provenance.shape[0] != edge_index.shape[1]:
            raise ValueError(
                "member subgraph tensor edges and provenance must align"
            )
        if any(
            not isinstance(source_row_id, str) or not source_row_id
            for source_row_id in provenance
        ):
            raise ValueError(
                "member subgraph provenance must contain nonempty strings"
            )
        if (
            not isinstance(target_index, (int, np.integer))
            or isinstance(target_index, (bool, np.bool_))
            or not 0 <= int(target_index) < x.shape[0]
        ):
            raise ValueError("member subgraph target_index is out of range")
        if edge_index.numel() and (
            int(edge_index.min()) < 0 or int(edge_index.max()) >= x.shape[0]
        ):
            raise ValueError("member subgraph edge_index is out of range")
        object.__setattr__(self, "_x", x.detach().clone())
        object.__setattr__(
            self, "_edge_index", edge_index.detach().clone()
        )
        object.__setattr__(self, "target_index", int(target_index))
        nodes.setflags(write=False)
        provenance.setflags(write=False)
        object.__setattr__(self, "_original_node_indices", nodes)
        object.__setattr__(self, "_tensor_edge_source_row_ids", provenance)

    @property
    def x(self):
        return self._x.detach().clone()

    @property
    def edge_index(self):
        return self._edge_index.detach().clone()

    @property
    def original_node_indices(self):
        result = np.array(self._original_node_indices, copy=True)
        result.setflags(write=False)
        return result

    @property
    def tensor_edge_source_row_ids(self):
        result = np.array(
            self._tensor_edge_source_row_ids, dtype=object, copy=True
        )
        result.setflags(write=False)
        return result


@dataclass(frozen=True)
class _BoundRankReference:
    reference: FrozenRankReference
    row_bindings: tuple[tuple[str, pd.Timestamp], ...]
    fingerprint: str


def _detached_rank_reference(reference):
    if not isinstance(reference, FrozenRankReference):
        raise ValueError("reference must be a FrozenRankReference")
    return FrozenRankReference(
        percentile_reference_id=reference.percentile_reference_id,
        event_ids=reference.event_ids,
        baseline_raw=reference.baseline_raw,
        seed0_gnn_raw=reference.seed0_gnn_raw,
        baseline_percentile=reference.baseline_percentile,
        seed0_gnn_percentile=reference.seed0_gnn_percentile,
        seed0_hybrid_score=reference.seed0_hybrid_score,
        baseline_selection_score=reference.baseline_selection_score,
        seed0_gnn_selection_score=reference.seed0_gnn_selection_score,
        seed0_hybrid_selection_score=reference.seed0_hybrid_selection_score,
        blend_weight=reference.blend_weight,
    )


def _canonical_rank_row_bindings(row_bindings, *, n_rows):
    if isinstance(row_bindings, Mapping):
        items = tuple(row_bindings.items())
    else:
        if isinstance(row_bindings, (str, bytes)):
            raise ValueError("row_bindings must map row indices to metadata")
        try:
            records = tuple(row_bindings)
        except TypeError as exc:
            raise ValueError(
                "row_bindings must map row indices to metadata"
            ) from exc
        items = []
        for record in records:
            if isinstance(record, (str, bytes)):
                raise ValueError(
                    "row_bindings records must contain row_index, person_id, and scoring_day"
                )
            try:
                row_index, person_id, scoring_day = tuple(record)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "row_bindings records must contain row_index, person_id, and scoring_day"
                ) from exc
            items.append((row_index, (person_id, scoring_day)))
        items = tuple(items)

    normalized = {}
    for row_index, metadata in items:
        if (
            not isinstance(row_index, (int, np.integer))
            or isinstance(row_index, (bool, np.bool_))
            or not 0 <= row_index < n_rows
        ):
            raise ValueError(
                "row_bindings must cover exactly row indices 0..n-1"
            )
        row_index = int(row_index)
        if row_index in normalized:
            raise ValueError("row_bindings must not contain duplicate rows")
        if isinstance(metadata, (str, bytes)):
            raise ValueError(
                "row binding metadata must contain person_id and scoring_day"
            )
        try:
            person_id, scoring_day = tuple(metadata)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "row binding metadata must contain person_id and scoring_day"
            ) from exc
        if not isinstance(person_id, str) or not person_id.strip():
            raise ValueError(
                "row binding person_id must be a non-blank string"
            )
        normalized[row_index] = (
            person_id.strip(),
            _scoring_day(scoring_day),
        )

    expected_rows = set(range(n_rows))
    if set(normalized) != expected_rows:
        raise ValueError("row_bindings must cover exactly row indices 0..n-1")
    return tuple(normalized[index] for index in range(n_rows))


def _rank_reference_fingerprint(reference, row_bindings):
    metadata = {
        "percentile_reference_id": reference.percentile_reference_id,
        "event_ids": reference.event_ids,
        "blend_weight": reference.blend_weight,
        "row_bindings": tuple(
            (person_id, scoring_day.isoformat())
            for person_id, scoring_day in row_bindings
        ),
    }
    digest = hashlib.sha256(
        json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    )
    for field_name in (
        "baseline_raw",
        "seed0_gnn_raw",
        "baseline_percentile",
        "seed0_gnn_percentile",
        "seed0_hybrid_score",
        "baseline_selection_score",
        "seed0_gnn_selection_score",
        "seed0_hybrid_selection_score",
    ):
        values = np.asarray(getattr(reference, field_name), dtype=np.float64)
        digest.update(field_name.encode("utf-8"))
        digest.update(values.tobytes(order="C"))
    return f"sha256:{digest.hexdigest()}"


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
        rank_row_bindings=None,
    ):
        self.__model = copy.deepcopy(model).eval()
        self.__model.requires_grad_(False)
        prepared_node_ids = tuple(node_ids)
        self.__prepared_source = learned_cell.prepare_snapshot_source(
            edges_typed,
            prepared_node_ids,
            node_feat,
            caught_time,
            {
                person_id: index
                for index, person_id in enumerate(prepared_node_ids)
            },
            num_rel=num_rel,
        )
        self.node_ids = self.__prepared_source.node_ids
        self.num_rel = self.__prepared_source.num_rel
        self.person_index = self.__prepared_source.index
        self.__rank_state = None
        self.__snapshot_cache: dict[pd.Timestamp, DaySnapshot] = {}
        self.__community_cache: dict[tuple[pd.Timestamp, object], dict] = {}
        self.__counterfactual_cache: dict[str, dict[str, object]] = {}
        self.__faithfulness_cache: dict[str, float] = {}
        self.__factor_specs_cache: dict[
            tuple[str, pd.Timestamp, str], tuple[AblationSpec, ...]
        ] = {}
        if (rank_reference is None) != (rank_row_bindings is None):
            raise ValueError(
                "rank_reference and rank_row_bindings must be provided together"
            )
        if rank_reference is not None:
            self.bind_rank_reference(rank_reference, rank_row_bindings)

    @property
    def rank_reference(self):
        if self.__rank_state is None:
            return None
        return self.__rank_state.reference

    def bind_rank_reference(self, reference, row_bindings):
        detached_reference = _detached_rank_reference(reference)
        detached_bindings = _canonical_rank_row_bindings(
            row_bindings,
            n_rows=len(detached_reference.event_ids),
        )
        new_state = _BoundRankReference(
            reference=detached_reference,
            row_bindings=detached_bindings,
            fingerprint=_rank_reference_fingerprint(
                detached_reference, detached_bindings
            ),
        )
        self.__rank_state = new_state
        self.__counterfactual_cache.clear()
        self.__faithfulness_cache.clear()
        self.__factor_specs_cache.clear()

    def snapshot(self, scoring_day) -> DaySnapshot:
        day = _scoring_day(scoring_day)
        cached = self.__snapshot_cache.get(day)
        if cached is not None:
            return _materialize_snapshot(cached)

        inputs = learned_cell.build_day_snapshot_inputs(
            day,
            prepared_source=self.__prepared_source,
        )
        self.__model.eval()
        with torch.no_grad():
            embeddings = self.__model.enc(
                inputs.x, inputs.edge_index, edge_type=inputs.edge_type
            )
            prepool_logits = self.__model.head(embeddings).squeeze(-1)
            pooled_embeddings = learned_cell._pool_by_roots_torch(
                embeddings, inputs.component_roots
            )
            pooled_logits = self.__model.head(pooled_embeddings).squeeze(-1)
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
            active_edges=inputs.active_edges,
            x=inputs.x,
            edge_index=inputs.edge_index,
            edge_type=inputs.edge_type,
            tensor_edge_source_row_ids=tensor_provenance,
            component_roots=component_roots,
            prepool_embeddings=embeddings.detach(),
            prepool_logits=prepool_logits.detach(),
            pooled_logits=pooled_logits.detach(),
            probabilities=probabilities,
            caught_before_snapshot=inputs.caught_before_snapshot,
        )
        self.__snapshot_cache[day] = result
        return _materialize_snapshot(result)

    @property
    def cached_snapshot_days(self):
        return tuple(sorted(self.__snapshot_cache))

    def release_snapshot(self, scoring_day):
        """Release day-bound tensors and derived diagnostic caches."""
        day = _scoring_day(scoring_day)
        removed = self.__snapshot_cache.pop(day, None) is not None
        community_keys = [
            key for key in self.__community_cache if key[0] == day
        ]
        for key in community_keys:
            self.__community_cache.pop(key, None)
        removed = removed or bool(community_keys)
        if removed:
            self.__counterfactual_cache.clear()
            self.__faithfulness_cache.clear()
            self.__factor_specs_cache = {
                key: value
                for key, value in self.__factor_specs_cache.items()
                if key[1] != day
            }
        return removed

    def observability_fingerprint_material(self):
        """Return compact content fingerprints for resumable diagnostics."""
        if self.__rank_state is None:
            raise ValueError("observability fingerprint requires a rank reference")

        graph_digest = hashlib.sha256()
        for person_id in self.node_ids:
            payload = person_id.encode("utf-8")
            graph_digest.update(len(payload).to_bytes(8, "big"))
            graph_digest.update(payload)
            feature = np.asarray(
                self.__prepared_source.node_feat[person_id], dtype=np.float64
            )
            graph_digest.update(feature.shape.__repr__().encode("ascii"))
            graph_digest.update(feature.tobytes(order="C"))
            caught = self.__prepared_source.caught_time.get(person_id)
            graph_digest.update(
                ("" if caught is None else pd.Timestamp(caught).isoformat()).encode(
                    "utf-8"
                )
            )
        edges = self.__prepared_source._edges_typed
        graph_digest.update(
            json.dumps(list(edges.columns), separators=(",", ":")).encode("utf-8")
        )
        graph_digest.update(
            pd.util.hash_pandas_object(edges, index=False).to_numpy().tobytes()
        )
        graph_digest.update(str(self.num_rel).encode("ascii"))

        model_digest = hashlib.sha256()
        for name, tensor in sorted(self.__model.state_dict().items()):
            encoded_name = name.encode("utf-8")
            model_digest.update(len(encoded_name).to_bytes(8, "big"))
            model_digest.update(encoded_name)
            values = tensor.detach().cpu().contiguous().numpy()
            model_digest.update(str(values.dtype).encode("ascii"))
            model_digest.update(repr(values.shape).encode("ascii"))
            model_digest.update(values.tobytes(order="C"))
        return {
            "graph_sha256": graph_digest.hexdigest(),
            "model_state_sha256": model_digest.hexdigest(),
            "rank_reference_fingerprint": self.__rank_state.fingerprint,
        }

    def relationship_categories(self, person_id, scoring_day):
        if person_id not in self.person_index:
            raise KeyError(f"unknown person_id: {person_id}")
        day = _scoring_day(scoring_day)
        edges = self.__prepared_source._edges_typed
        incident = edges.loc[
            (
                (edges["u"] == person_id)
                | (edges["v"] == person_id)
            )
            & (edges["avail_time"] < day)
        ]
        return tuple(sorted(set(incident["edge_type"].astype(str))))

    def community(self, person_id, scoring_day):
        if person_id not in self.person_index:
            raise KeyError(f"unknown person_id: {person_id}")
        day = _scoring_day(scoring_day)
        snapshot = self.snapshot(day)
        component_root = snapshot.component_roots[self.person_index[person_id]]
        normalized_root = (
            component_root.item()
            if isinstance(component_root, np.generic)
            else component_root
        )
        cache_key = (day, normalized_root)
        cached = self.__community_cache.get(cache_key)
        if cached is None:
            cached = build_complete_community(self, person_id, day)
            self.__community_cache[cache_key] = cached
        return cached

    def score_counterfactual(self, context, factor):
        return score_grouped_counterfactual(self, context, factor)

    def explanation_model_copy(self):
        """Return an isolated eval-mode model for post-hoc explanation only."""
        return copy.deepcopy(self.__model).eval()

    def caught_available_time(self, person_id):
        """Return one immutable observed-catch availability scalar, if known."""
        if person_id not in self.person_index:
            raise KeyError(f"unknown person_id: {person_id}")
        value = self.__prepared_source.caught_time.get(person_id)
        return None if value is None else pd.Timestamp(value)

    def __validate_candidate_rows_for_day(
        self, scoring_day, row_indices, *, field_name
    ):
        rank_state = self.__rank_state
        if rank_state is None:
            raise ValueError(
                "candidate validation requires a frozen rank reference"
            )
        day = _scoring_day(scoring_day)
        indices = _reference_indices(
            row_indices,
            field_name=field_name,
            n_rows=len(rank_state.reference.event_ids),
        )
        for row_index in indices:
            _, bound_day = rank_state.row_bindings[row_index]
            if bound_day != day:
                raise ValueError(
                    f"{field_name} row binding does not match scoring_day"
                )

    def __caught_available_time(self, person_id):
        return self.__prepared_source.caught_time[person_id]

    def __diagnostic_edge_source_set_probability(
        self, context, edge_source_row_ids
    ):
        if not isinstance(context, CounterfactualContext):
            raise ValueError("context must be a CounterfactualContext")
        rank_state = self.__rank_state
        if rank_state is None:
            raise ValueError(
                "diagnostic edge scoring requires a frozen rank reference"
            )
        if context.person_id not in self.person_index:
            raise KeyError(f"unknown person_id: {context.person_id}")
        _validate_bound_counterfactual_context(rank_state, context)
        source_ids = _canonical_string_ids(
            edge_source_row_ids, field_name="edge_source_row_ids"
        )
        original = self.snapshot(context.scoring_day)
        active_source_ids = set(
            original.active_edges["source_row_id"].astype(str)
        )
        inactive = sorted(set(source_ids).difference(active_source_ids))
        if inactive:
            raise ValueError(
                "every diagnostic edge source_row_id must be active at the "
                f"scoring snapshot: {inactive}"
            )

        cache_key = _length_framed_hash(
            (
                "faithfulness-edge-source-set",
                rank_state.fingerprint,
                context.person_id,
                context.scoring_day.isoformat(),
                str(context.row_index),
                *(str(index) for index in context.same_day_person_row_indices),
                "candidate-boundary",
                *(str(index) for index in context.candidate_row_indices),
                "source-boundary",
                *source_ids,
            )
        )
        cached = self.__faithfulness_cache.get(cache_key)
        if cached is not None:
            return float(cached)

        target_index = self.person_index[context.person_id]
        if not source_ids:
            probability = float(original.probabilities[target_index])
        else:
            source = self.__prepared_source
            modified_edges = source._edges_typed.loc[
                ~source._edges_typed["source_row_id"]
                .astype(str)
                .isin(source_ids)
            ].copy(deep=True)
            modified_source = learned_cell.prepare_snapshot_source(
                modified_edges,
                source.node_ids,
                source.node_feat,
                source.caught_time,
                source.index,
                num_rel=source.num_rel,
            )
            inputs = learned_cell.build_day_snapshot_inputs(
                context.scoring_day, prepared_source=modified_source
            )
            self.__model.eval()
            with torch.no_grad():
                embeddings = self.__model.enc(
                    inputs.x,
                    inputs.edge_index,
                    edge_type=inputs.edge_type,
                )
                pooled_embeddings = learned_cell._pool_by_roots_torch(
                    embeddings, inputs.component_roots
                )
                probabilities = (
                    torch.sigmoid(
                        self.__model.head(pooled_embeddings).squeeze(-1)
                    )
                    .detach()
                    .cpu()
                    .numpy()
                )
            probability = float(probabilities[target_index])
        if not np.isfinite(probability) or not 0.0 <= probability <= 1.0:
            raise ValueError(
                "diagnostic edge-set probability must be finite in [0, 1]"
            )
        self.__faithfulness_cache[cache_key] = probability
        return float(probability)

    def __score_grouped_counterfactual(self, context, factor):
        if not isinstance(context, CounterfactualContext):
            raise ValueError("context must be a CounterfactualContext")
        if not isinstance(factor, AblationSpec):
            raise ValueError("factor must be an AblationSpec")
        rank_state = self.__rank_state
        if rank_state is None:
            raise ValueError(
                "counterfactual scoring requires a frozen rank reference"
            )
        reference = rank_state.reference
        if context.person_id not in self.person_index:
            raise KeyError(f"unknown person_id: {context.person_id}")
        _validate_bound_counterfactual_context(rank_state, context)
        cache_key = _counterfactual_fingerprint(
            context, factor, rank_state.fingerprint
        )
        cached = self.__counterfactual_cache.get(cache_key)
        if cached is not None:
            return copy.deepcopy(cached)

        original = self.snapshot(context.scoring_day)
        target_index = self.person_index[context.person_id]
        original_probability = float(original.probabilities[target_index])
        frozen_probabilities = reference.seed0_gnn_raw[
            list(context.same_day_person_row_indices)
        ]
        if not np.allclose(
            frozen_probabilities,
            original_probability,
            rtol=1e-7,
            atol=1e-8,
        ):
            raise ValueError(
                "affected frozen seed0 probabilities do not match the strict "
                "as-of snapshot probability"
            )
        no_op_rank = frozen_peer_rank(
            reference,
            anchor_row_index=context.row_index,
            affected_row_indices=context.same_day_person_row_indices,
            ablated_seed0_probability=original_probability,
            candidate_row_indices=context.candidate_row_indices,
            original_hybrid_rank=context.original_hybrid_rank,
        )
        if no_op_rank["hybrid_rank_delta"] != 0:
            raise ValueError(
                "original probability no-op must preserve the frozen hybrid rank"
            )
        specs_cache_key = (
            rank_state.fingerprint,
            context.scoring_day,
            context.person_id,
        )
        generated_specs = self.__factor_specs_cache.get(specs_cache_key)
        if generated_specs is None:
            community = build_complete_community(
                self, context.person_id, context.scoring_day
            )
            generated_specs = tuple(
                build_ablation_specs(
                    original, context.person_id, community
                )
            )
            self.__factor_specs_cache[specs_cache_key] = generated_specs
        allowed_specs = {
            spec.factor_id: spec
            for spec in generated_specs
        }
        expected_factor = allowed_specs.get(factor.factor_id)
        if expected_factor is None or factor != expected_factor:
            raise ValueError(
                "incomplete or invalid factor for the strict as-of snapshot: "
                f"{factor.factor_id}"
            )

        source = self.__prepared_source
        known_edge_source_ids = (
            set(source._edges_typed["source_row_id"].astype(str))
            if "source_row_id" in source._edges_typed.columns
            else set()
        )
        unknown_edge_source_ids = sorted(
            set(factor.edge_source_row_ids).difference(known_edge_source_ids)
        )
        if unknown_edge_source_ids:
            raise ValueError(
                "unknown edge source_row_id requested for ablation: "
                f"{unknown_edge_source_ids}"
            )
        known_caught_people = set(source.caught_time).intersection(source.index)
        unknown_caught_people = sorted(
            set(factor.caught_person_ids).difference(known_caught_people)
        )
        if unknown_caught_people:
            raise ValueError(
                "unknown caught person_id requested for ablation: "
                f"{unknown_caught_people}"
            )
        unknown_provenance_nodes = sorted(
            set(factor.provenance_node_ids).difference(source.index)
        )
        if unknown_provenance_nodes:
            raise ValueError(
                "unknown provenance node_id requested for ablation: "
                f"{unknown_provenance_nodes}"
            )

        modified_edges = source._edges_typed.copy(deep=True)
        if factor.edge_source_row_ids:
            modified_edges = modified_edges.loc[
                ~modified_edges["source_row_id"]
                .astype(str)
                .isin(factor.edge_source_row_ids)
            ].copy(deep=True)
        modified_caught = {
            person_id: available_time
            for person_id, available_time in source.caught_time.items()
            if person_id not in factor.caught_person_ids
        }
        modified_source = learned_cell.prepare_snapshot_source(
            modified_edges,
            source.node_ids,
            source.node_feat,
            modified_caught,
            source.index,
            num_rel=source.num_rel,
        )
        inputs = learned_cell.build_day_snapshot_inputs(
            context.scoring_day,
            prepared_source=modified_source,
        )
        self.__model.eval()
        with torch.no_grad():
            embeddings = self.__model.enc(
                inputs.x, inputs.edge_index, edge_type=inputs.edge_type
            )
            pooled_embeddings = learned_cell._pool_by_roots_torch(
                embeddings, inputs.component_roots
            )
            probabilities = (
                torch.sigmoid(
                    self.__model.head(pooled_embeddings).squeeze(-1)
                )
                .detach()
                .cpu()
                .numpy()
                .copy()
            )

        ablated_probability = float(probabilities[target_index])
        if not (
            np.isfinite(original_probability)
            and np.isfinite(ablated_probability)
            and 0.0 <= original_probability <= 1.0
            and 0.0 <= ablated_probability <= 1.0
        ):
            raise ValueError("counterfactual probabilities must be finite in [0, 1]")
        rank_effect = frozen_peer_rank(
            reference,
            anchor_row_index=context.row_index,
            affected_row_indices=context.same_day_person_row_indices,
            ablated_seed0_probability=ablated_probability,
            candidate_row_indices=context.candidate_row_indices,
            original_hybrid_rank=context.original_hybrid_rank,
        )
        original_root = original.component_roots[target_index]
        ablated_root = inputs.component_roots[target_index]
        caught_feature_changes = [
            {
                "person_id": person_id,
                "original_caught_before_snapshot": (
                    person_id in original.caught_before_snapshot
                ),
                "ablated_caught_before_snapshot": (
                    person_id in inputs.caught_before_snapshot
                ),
            }
            for person_id in factor.caught_person_ids
        ]
        result = {
            **rank_effect,
            "factor_id": factor.factor_id,
            "kind": factor.kind,
            "original_seed0_probability": original_probability,
            "ablated_seed0_probability": ablated_probability,
            "seed0_probability_delta": (
                ablated_probability - original_probability
            ),
            "original_component_size": int(
                np.count_nonzero(
                    original.component_roots == original_root
                )
            ),
            "ablated_component_size": int(
                np.count_nonzero(inputs.component_roots == ablated_root)
            ),
            "caught_feature_changes": caught_feature_changes,
            "features_rebuilt": True,
            "pooling_rebuilt": True,
        }
        validate_explanation_payload(result)
        pristine = copy.deepcopy(result)
        self.__counterfactual_cache[cache_key] = pristine
        return copy.deepcopy(pristine)


def score_grouped_counterfactual(engine, context, factor):
    if not isinstance(engine, Seed0ExplanationEngine):
        raise ValueError("engine must be a Seed0ExplanationEngine")
    return engine._Seed0ExplanationEngine__score_grouped_counterfactual(
        context, factor
    )


def diagnostic_edge_source_set_probability(
    engine, context, edge_source_row_ids
):
    """Rescore an exact active source-row set without relaxing Task 6 factors."""
    if not isinstance(engine, Seed0ExplanationEngine):
        raise ValueError("engine must be a Seed0ExplanationEngine")
    return engine._Seed0ExplanationEngine__diagnostic_edge_source_set_probability(
        context, edge_source_row_ids
    )


def _length_framed_hash(parts):
    """Hash ordered strings without separator or concatenation collisions."""
    if isinstance(parts, (str, bytes)):
        raise ValueError("hash parts must be a sequence of strings")
    digest = hashlib.sha256()
    for part in parts:
        if not isinstance(part, str):
            raise ValueError("hash parts must be strings")
        payload = part.encode("utf-8")
        digest.update(len(payload).to_bytes(8, byteorder="big", signed=False))
        digest.update(payload)
    return f"sha256:{digest.hexdigest()}"


def member_subgraph(engine, person_id, scoring_day):
    if not isinstance(engine, Seed0ExplanationEngine):
        raise ValueError("engine must be a Seed0ExplanationEngine")
    if person_id not in engine.person_index:
        raise KeyError(f"unknown person_id: {person_id}")
    snapshot = engine.snapshot(scoring_day)
    target_index = engine.person_index[person_id]
    subset, edge_index, mapping, edge_mask = k_hop_subgraph(
        target_index,
        2,
        snapshot.edge_index,
        relabel_nodes=True,
        num_nodes=len(engine.node_ids),
    )
    provenance = snapshot.tensor_edge_source_row_ids[
        edge_mask.detach().cpu().numpy()
    ]
    return MemberSubgraph(
        x=snapshot.x[subset],
        edge_index=edge_index,
        target_index=int(mapping.item()),
        original_node_indices=subset.detach().cpu().numpy(),
        tensor_edge_source_row_ids=provenance,
    )


def make_gnn_explainer(wrapper, epochs=150):
    if not isinstance(wrapper, PrePoolSAGELogitWrapper):
        raise ValueError("wrapper must be a PrePoolSAGELogitWrapper")
    if (
        not isinstance(epochs, (int, np.integer))
        or isinstance(epochs, (bool, np.bool_))
        or epochs <= 0
    ):
        raise ValueError("epochs must be a positive integer")
    return Explainer(
        model=wrapper,
        algorithm=GNNExplainer(epochs=int(epochs)),
        explanation_type="model",
        node_mask_type="attributes",
        edge_mask_type="object",
        model_config=ModelConfig(
            mode="binary_classification",
            task_level="node",
            return_type="raw",
        ),
    )


def _validated_restart_seeds(restart_seeds):
    if isinstance(restart_seeds, (str, bytes)):
        raise ValueError("restart_seeds must contain nonnegative integers")
    try:
        values = tuple(restart_seeds)
    except TypeError as exc:
        raise ValueError(
            "restart_seeds must contain nonnegative integers"
        ) from exc
    if not values:
        raise ValueError("restart_seeds must not be empty")
    if any(
        not isinstance(value, (int, np.integer))
        or isinstance(value, (bool, np.bool_))
        or value < 0
        for value in values
    ):
        raise ValueError("restart_seeds must contain nonnegative integers")
    normalized = tuple(int(value) for value in values)
    if len(set(normalized)) != len(normalized):
        raise ValueError("restart_seeds must not contain duplicates")
    if normalized != (0, 1, 2):
        raise ValueError("restart_seeds must be exactly (0, 1, 2)")
    return normalized


def _readonly_float_mask(value, *, expected_length, field_name):
    mask = np.asarray(value, dtype=float)
    if mask.ndim != 1 or mask.shape[0] != expected_length:
        raise ValueError(f"{field_name} is not aligned with explanation inputs")
    if not np.isfinite(mask).all() or (mask < 0.0).any():
        raise ValueError(f"{field_name} must be finite and nonnegative")
    result = np.array(mask, dtype=float, copy=True)
    result.setflags(write=False)
    return result


def _readonly_node_feature_mask(
    value, *, expected_shape, field_name="node_feature_mask"
):
    mask = np.asarray(value, dtype=float)
    if mask.ndim != 2 or tuple(mask.shape) != tuple(expected_shape):
        raise ValueError(f"{field_name} is not aligned with explanation inputs")
    if not np.isfinite(mask).all() or (mask < 0.0).any():
        raise ValueError(f"{field_name} must be finite and nonnegative")
    result = np.array(mask, dtype=float, copy=True)
    result.setflags(write=False)
    return result


def run_member_explanation(
    engine,
    person_id,
    scoring_day,
    *,
    restart_seeds=(0, 1, 2),
    epochs=150,
    explainer_factory=make_gnn_explainer,
):
    """Explain one pooled member's exact two-hop pre-pool GraphSAGE logit."""
    seeds = _validated_restart_seeds(restart_seeds)
    local = member_subgraph(engine, person_id, scoring_day)
    wrapper = PrePoolSAGELogitWrapper(engine.explanation_model_copy())
    local_x = local.x
    local_edge_index = local.edge_index
    snapshot = engine.snapshot(scoring_day)
    with torch.no_grad():
        local_logit = wrapper(local_x, local_edge_index)[local.target_index]
        full_logit = snapshot.prepool_logits[engine.person_index[person_id]]
    torch.testing.assert_close(
        local_logit, full_logit, rtol=1e-6, atol=1e-6
    )

    edge_count = local_edge_index.shape[1]
    edge_masks = []
    node_feature_masks = []
    for restart_seed in seeds:
        with torch.random.fork_rng():
            torch.manual_seed(restart_seed)
            explanation = explainer_factory(wrapper, epochs=epochs)(
                x=local_x,
                edge_index=local_edge_index,
                index=local.target_index,
            )
        if explanation.edge_mask is None:
            if edge_count:
                raise ValueError("edge_mask is required when message edges exist")
            edge_mask = np.zeros(0, dtype=float)
        else:
            edge_mask = explanation.edge_mask.detach().cpu().numpy()
        edge_masks.append(
            _readonly_float_mask(
                edge_mask,
                expected_length=edge_count,
                field_name="edge_mask",
            )
        )
        if explanation.node_mask is None:
            raise ValueError("node_mask is required for member explanations")
        node_feature_masks.append(
            _readonly_node_feature_mask(
                explanation.node_mask.detach().cpu().numpy(),
                expected_shape=tuple(local_x.shape),
            )
        )
    return {
        "edge_masks": tuple(edge_masks),
        "node_feature_masks": tuple(node_feature_masks),
        "restart_seeds": seeds,
        "local_prepool_logit": float(local_logit),
        "full_prepool_logit": float(full_logit),
        "status": "no-message-edges" if edge_count == 0 else "ok",
    }


def build_flow_stages(community):
    if not isinstance(community, Mapping):
        raise ValueError("community must be a mapping")
    nodes_by_id = community.get("nodes_by_id")
    edges = community.get("edges")
    if not isinstance(nodes_by_id, Mapping) or not isinstance(edges, Sequence):
        raise ValueError("community must contain nodes_by_id and edges")
    node_ids = tuple(sorted(str(node_id) for node_id in nodes_by_id))
    edge_ids = tuple(sorted(str(edge["edge_id"]) for edge in edges))
    first_hop = sorted(
        edge["edge_id"] for edge in edges if edge["message_hop"] <= 1
    )
    second_hop = sorted(
        edge["edge_id"] for edge in edges if edge["message_hop"] <= 2
    )
    pooling = sorted(
        edge["edge_id"]
        for edge in edges
        if str(edge["edge_type"]).upper() == "COTRAVEL"
        and nodes_by_id[edge["u"]]["pooled_member"]
        and nodes_by_id[edge["v"]]["pooled_member"]
    )
    emphasized = (first_hop, second_hop, pooling, [])
    return [
        {
            "stage_id": stage_id,
            "node_ids": list(node_ids),
            "edge_ids": list(edge_ids),
            "emphasized_edge_ids": values,
        }
        for stage_id, values in zip(
            ("first_hop", "second_hop", "component_pool", "rank_fusion"),
            emphasized,
        )
    ]


def aggregate_restart_masks(masks, top_fraction=0.1):
    try:
        fraction = float(top_fraction)
    except (TypeError, ValueError) as exc:
        raise ValueError("top_fraction must be finite and in (0, 1]") from exc
    if not np.isfinite(fraction) or not 0.0 < fraction <= 1.0:
        raise ValueError("top_fraction must be finite and in (0, 1]")
    if isinstance(masks, (str, bytes)):
        raise ValueError("at least one aligned explainer mask is required")
    try:
        rows = tuple(np.asarray(mask, dtype=float) for mask in masks)
    except (TypeError, ValueError) as exc:
        raise ValueError("explainer masks must be numeric") from exc
    if not rows:
        raise ValueError("at least one aligned explainer mask is required")
    if any(row.ndim != 1 for row in rows):
        raise ValueError("each explainer mask must be one-dimensional")
    if len({row.shape for row in rows}) != 1:
        raise ValueError("explainer masks must be aligned")
    matrix = np.vstack(rows)
    if not np.isfinite(matrix).all():
        raise ValueError("explainer masks must be finite")
    if (matrix < 0.0).any():
        raise ValueError("explainer masks must be nonnegative")
    if matrix.shape[1] == 0:
        empty = np.zeros(0, dtype=float)
        return {
            "median": empty,
            "q1": empty,
            "q3": empty,
            "selection_frequency": empty,
            "restart_count": matrix.shape[0],
            "top_factor_agreement": 0.0,
            "status": "no-message-edges",
        }

    normalized = matrix / np.maximum(
        matrix.max(axis=1, keepdims=True), 1e-12
    )
    top_count = max(1, int(np.ceil(normalized.shape[1] * fraction)))
    selected = np.zeros_like(normalized, dtype=bool)
    for row_index, row in enumerate(normalized):
        top = np.argsort(-row, kind="stable")[:top_count]
        positive_top = top[row[top] > 0.0]
        selected[row_index, positive_top] = True
    selection_frequency = selected.mean(axis=0)
    return {
        "median": np.median(normalized, axis=0),
        "q1": np.quantile(normalized, 0.25, axis=0),
        "q3": np.quantile(normalized, 0.75, axis=0),
        "selection_frequency": selection_frequency,
        "restart_count": normalized.shape[0],
        "top_factor_agreement": float(selection_frequency.max()),
        "status": "ok" if selected.any() else "no-positive-influence",
    }


def matched_random_controls(
    edge_records, *, selected_edge_ids, seed
):
    pairs, _ = _matched_control_details(
        edge_records, selected_edge_ids=selected_edge_ids, seed=seed
    )
    return tuple(pair["control_edge_id"] for pair in pairs)


def _matched_control_details(
    edge_records, *, selected_edge_ids, seed
):
    records = tuple(edge_records)
    edge_ids = tuple(record["edge_id"] for record in records)
    if len(set(edge_ids)) != len(edge_ids):
        raise ValueError("control edge_id values must be unique")
    by_id = {record["edge_id"]: record for record in records}
    selected_ids = tuple(selected_edge_ids)
    if len(set(selected_ids)) != len(selected_ids):
        raise ValueError("selected_edge_ids must not contain duplicates")
    unknown = sorted(set(selected_ids).difference(by_id))
    if unknown:
        raise ValueError(f"unknown selected edge IDs: {unknown}")
    selected = set(selected_ids)
    rng = np.random.default_rng(seed)
    pairs = []
    unmatched = []
    used_controls = set()
    for edge_id in selected_ids:
        source = by_id[edge_id]
        candidates = sorted(
            record["edge_id"]
            for record in records
            if record["edge_id"] not in selected
            and record["edge_id"] not in used_controls
            and record["relation"] == source["relation"]
            and record["degree_bin"] == source["degree_bin"]
        )
        if candidates:
            control_edge_id = candidates[
                int(rng.integers(0, len(candidates)))
            ]
            used_controls.add(control_edge_id)
            pairs.append(
                {
                    "selected_edge_id": edge_id,
                    "control_edge_id": control_edge_id,
                }
            )
        else:
            unmatched.append(edge_id)
    return pairs, unmatched


def _validated_probability(value, *, field_name):
    try:
        probability = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be finite in [0, 1]") from exc
    if not np.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError(f"{field_name} must be finite in [0, 1]")
    return probability


def edge_removal_faithfulness(
    edge_records, importance_by_id, *, rescore, seed=0
):
    records = tuple(edge_records)
    edge_ids = tuple(record["edge_id"] for record in records)
    if len(set(edge_ids)) != len(edge_ids):
        raise ValueError("faithfulness edge_id values must be unique")
    if not isinstance(importance_by_id, Mapping):
        raise ValueError("importance_by_id must be a mapping")
    importance = {}
    for edge_id in edge_ids:
        try:
            value = float(importance_by_id.get(edge_id, 0.0))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "faithfulness importance values must be finite and nonnegative"
            ) from exc
        if not np.isfinite(value) or value < 0.0:
            raise ValueError(
                "faithfulness importance values must be finite and nonnegative"
            )
        importance[edge_id] = value
    ordered = sorted(
        records,
        key=lambda record: (
            -importance[record["edge_id"]],
            record["edge_id"],
        ),
    )
    original = _validated_probability(
        rescore(()), field_name="original_probability"
    )
    points = []
    for fraction in (0.10, 0.25, 0.50):
        count = (
            max(1, int(np.ceil(len(ordered) * fraction)))
            if ordered
            else 0
        )
        selected = tuple(
            record["edge_id"] for record in ordered[:count]
        )
        control_pairs, unmatched = _matched_control_details(
            records,
            selected_edge_ids=selected,
            seed=int(seed) + count,
        )
        controls = tuple(
            pair["control_edge_id"] for pair in control_pairs
        )
        top_probability = _validated_probability(
            rescore(selected), field_name="top_edge_probability"
        )
        matched_drop = None
        if len(controls) == len(selected):
            matched_probability = _validated_probability(
                rescore(controls), field_name="matched_random_probability"
            )
            matched_drop = original - matched_probability
        points.append(
            {
                "fraction": fraction,
                "selected_edge_ids": list(selected),
                "matched_control_edge_ids": list(controls),
                "matched_control_pairs": control_pairs,
                "unmatched_selected_edge_ids": unmatched,
                "top_edge_probability_drop": original - top_probability,
                "matched_random_probability_drop": matched_drop,
                "unmatched_control_count": len(unmatched),
            }
        )
    return {"original_probability": original, "points": points}


def _counterfactual_fingerprint(context, factor, rank_reference_fingerprint):
    payload = {
        "context": asdict(context),
        "factor": asdict(factor),
        "rank_reference_fingerprint": rank_reference_fingerprint,
    }
    payload["context"]["scoring_day"] = context.scoring_day.isoformat()
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    )
    return f"sha256:{digest.hexdigest()}"


def _materialize_snapshot(snapshot):
    """Return a detached public snapshot without exposing pristine cache state."""
    return DaySnapshot(
        scoring_day=snapshot.scoring_day,
        active_edges=snapshot.active_edges.copy(deep=True),
        x=snapshot.x.detach().clone(),
        edge_index=snapshot.edge_index.detach().clone(),
        edge_type=snapshot.edge_type.detach().clone(),
        tensor_edge_source_row_ids=np.array(
            snapshot.tensor_edge_source_row_ids, dtype=object, copy=True
        ),
        component_roots=np.array(snapshot.component_roots, copy=True),
        prepool_embeddings=snapshot.prepool_embeddings.detach().clone(),
        prepool_logits=snapshot.prepool_logits.detach().clone(),
        pooled_logits=snapshot.pooled_logits.detach().clone(),
        probabilities=np.array(snapshot.probabilities, copy=True),
        caught_before_snapshot=snapshot.caught_before_snapshot,
    )


def _scoring_day(value):
    try:
        timestamp = pd.to_datetime(value, utc=True, errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError("scoring_day must be a non-null scalar timestamp") from exc
    if not isinstance(timestamp, pd.Timestamp):
        raise ValueError("scoring_day must be a non-null scalar timestamp")
    if pd.isna(timestamp):
        raise ValueError("scoring_day must be a non-null scalar timestamp")
    return timestamp.floor("D")


def _reference_indices(values, *, field_name, n_rows):
    indices = _nonnegative_unique_indices(values, field_name=field_name)
    if any(index >= n_rows for index in indices):
        raise ValueError(f"{field_name} contains a row index out of range")
    return indices


def _validate_bound_counterfactual_context(rank_state, context):
    reference = rank_state.reference
    n_rows = len(reference.event_ids)
    same_day_rows = _reference_indices(
        context.same_day_person_row_indices,
        field_name="same_day_person_row_indices",
        n_rows=n_rows,
    )
    candidates = _reference_indices(
        context.candidate_row_indices,
        field_name="candidate_row_indices",
        n_rows=n_rows,
    )
    expected_binding = (context.person_id, context.scoring_day)
    for row_index in same_day_rows:
        person_id, scoring_day = rank_state.row_bindings[row_index]
        if person_id != context.person_id:
            raise ValueError(
                "same-day person row binding does not match context person_id"
            )
        if scoring_day != context.scoring_day:
            raise ValueError(
                "same-day person row binding does not match context scoring_day"
            )
    for row_index in candidates:
        _, scoring_day = rank_state.row_bindings[row_index]
        if scoring_day != context.scoring_day:
            raise ValueError(
                "candidate row binding does not match context scoring_day"
            )
    complete_same_day_rows = tuple(
        row_index
        for row_index, binding in enumerate(rank_state.row_bindings)
        if binding == expected_binding
    )
    if set(same_day_rows) != set(complete_same_day_rows):
        raise ValueError(
            "same_day_person_row_indices must contain the complete bound identity-day group"
        )

    ordered_candidates = sorted(
        candidates,
        key=lambda index: (
            -float(reference.seed0_hybrid_selection_score[index]),
            index,
        ),
    )
    exact_rank = ordered_candidates.index(context.row_index) + 1
    if exact_rank != context.original_hybrid_rank:
        raise ValueError(
            "original_hybrid_rank does not match the frozen hybrid selection score"
        )


def frozen_peer_rank(
    reference: FrozenRankReference,
    *,
    anchor_row_index: int,
    affected_row_indices: tuple[int, ...],
    ablated_seed0_probability: float,
    candidate_row_indices: tuple[int, ...],
    original_hybrid_rank: int,
) -> dict[str, object]:
    """Re-rank one identity while every candidate peer score stays frozen."""
    if not isinstance(reference, FrozenRankReference):
        raise ValueError("reference must be a FrozenRankReference")
    n_rows = len(reference.event_ids)
    if (
        not isinstance(anchor_row_index, (int, np.integer))
        or isinstance(anchor_row_index, (bool, np.bool_))
        or not 0 <= anchor_row_index < n_rows
    ):
        raise ValueError("anchor_row_index is out of range")
    anchor_row_index = int(anchor_row_index)
    affected = _reference_indices(
        affected_row_indices,
        field_name="affected_row_indices",
        n_rows=n_rows,
    )
    candidates = _reference_indices(
        candidate_row_indices,
        field_name="candidate_row_indices",
        n_rows=n_rows,
    )
    if anchor_row_index not in affected:
        raise ValueError("anchor row must be included in affected_row_indices")
    if anchor_row_index not in candidates:
        raise ValueError("anchor row must be included in candidate_row_indices")
    if not set(affected).issubset(candidates):
        raise ValueError("every affected row must be included in candidate rows")
    if (
        not isinstance(original_hybrid_rank, (int, np.integer))
        or isinstance(original_hybrid_rank, (bool, np.bool_))
        or original_hybrid_rank <= 0
        or original_hybrid_rank > len(candidates)
    ):
        raise ValueError(
            "original_hybrid_rank must be positive and within the candidate reference"
        )
    original_ordered_candidates = sorted(
        candidates,
        key=lambda index: (
            -float(reference.seed0_hybrid_selection_score[index]),
            index,
        ),
    )
    exact_original_rank = (
        original_ordered_candidates.index(anchor_row_index) + 1
    )
    if int(original_hybrid_rank) != exact_original_rank:
        raise ValueError(
            "original_hybrid_rank does not match the frozen hybrid selection score"
        )
    try:
        probability = float(ablated_seed0_probability)
    except (TypeError, ValueError) as exc:
        raise ValueError("ablated_seed0_probability must be finite") from exc
    if not np.isfinite(probability):
        raise ValueError("ablated_seed0_probability must be finite")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("ablated_seed0_probability must be in [0, 1]")

    array_fields = (
        reference.seed0_gnn_raw,
        reference.baseline_percentile,
    )
    if any(array.ndim != 1 or len(array) != n_rows for array in array_fields):
        raise ValueError("rank reference arrays are not aligned")
    if any(not np.isfinite(array).all() for array in array_fields):
        raise ValueError("rank reference arrays must be finite")

    gnn_raw = np.array(reference.seed0_gnn_raw, dtype=float, copy=True)
    gnn_raw[list(affected)] = probability
    gnn_percentile = rankdata(gnn_raw, method="average") / n_rows
    hybrid_score = (
        reference.blend_weight * gnn_percentile
        + (1.0 - reference.blend_weight) * reference.baseline_percentile
    )
    if not np.isfinite(gnn_percentile).all() or not np.isfinite(
        hybrid_score
    ).all():
        raise ValueError("ablated rank scores must be finite")
    hybrid_selection = _selection_tiebreak(hybrid_score)
    ordered_candidates = sorted(
        candidates,
        key=lambda index: (-float(hybrid_selection[index]), index),
    )
    ablated_rank = ordered_candidates.index(anchor_row_index) + 1
    original_rank = int(original_hybrid_rank)
    updated = sorted(affected)
    unchanged = sorted(set(candidates).difference(affected))
    return {
        "percentile_reference_id": reference.percentile_reference_id,
        "ablated_gnn_percentile": float(gnn_percentile[anchor_row_index]),
        "original_hybrid_rank": original_rank,
        "ablated_hybrid_rank": ablated_rank,
        "hybrid_rank_delta": ablated_rank - original_rank,
        "updated_row_indices": updated,
        "unchanged_peer_row_indices": unchanged,
    }


def classify_factor_stability(
    counterfactual, restart_selection_frequency, restart_iqr
):
    try:
        frequency = float(restart_selection_frequency)
        iqr = float(restart_iqr)
    except (TypeError, ValueError) as exc:
        raise ValueError("restart metrics must be finite") from exc
    if not np.isfinite(frequency) or not np.isfinite(iqr):
        raise ValueError("restart metrics must be finite")
    if not 0.0 <= frequency <= 1.0:
        raise ValueError("restart_selection_frequency must be in [0, 1]")
    if iqr < 0.0:
        raise ValueError("restart_iqr must be nonnegative")
    if not isinstance(counterfactual, Mapping) or "hybrid_rank_delta" not in counterfactual:
        raise ValueError("counterfactual must contain hybrid_rank_delta")
    try:
        effect = float(counterfactual["hybrid_rank_delta"])
    except (TypeError, ValueError) as exc:
        raise ValueError("hybrid_rank_delta must be finite") from exc
    if not np.isfinite(effect):
        raise ValueError("hybrid_rank_delta must be finite")
    if effect < 0:
        return "countervailing"
    if effect > 0 and frequency >= (2 / 3) and iqr <= 0.25:
        return "stable"
    return "unstable"


def validate_explanation_payload(value, path="root"):
    """Reject leak-prone artifact keys recursively, preserving the input."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() in FORBIDDEN_EXPLANATION_FIELDS:
                raise ValueError(f"forbidden explanation field at {path}.{key}")
            validate_explanation_payload(item, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for index, item in enumerate(value):
            validate_explanation_payload(item, f"{path}[{index}]")
    elif isinstance(value, np.ndarray):
        for index, item in enumerate(value.tolist()):
            validate_explanation_payload(item, f"{path}[{index}]")
    return value


def structural_provenance_rows(active_edges, visible_people):
    """Return complete structural feature provenance for visible people."""
    required_columns = {"source_row_id", "u", "v", "edge_type"}
    missing = sorted(required_columns.difference(active_edges.columns))
    if missing:
        raise ValueError(
            "active_edges missing structural provenance columns: "
            + ", ".join(missing)
        )
    visible = _canonical_string_ids(
        tuple(visible_people), field_name="visible_people"
    )
    visible_set = set(visible)
    relation = active_edges["edge_type"].astype(str).str.upper()
    cotravel = active_edges.loc[relation == "COTRAVEL"]
    residence = active_edges.loc[relation == "RESIDENCE"]

    cotravel_graph = nx.Graph()
    cotravel_graph.add_edges_from(
        cotravel[["u", "v"]].itertuples(index=False, name=None)
    )
    cotravel_components = {}
    for component_values in nx.connected_components(cotravel_graph):
        component = frozenset(component_values)
        cotravel_components.update(
            {person_id: component for person_id in component}
        )
    cotravel_people = set(visible_set)
    for person_id in visible:
        cotravel_people.update(cotravel_components.get(person_id, ()))

    residence_graph = nx.Graph()
    residence_graph.add_edges_from(
        residence[["u", "v"]].itertuples(index=False, name=None)
    )
    residence_components = {}
    for component_values in nx.connected_components(residence_graph):
        component = frozenset(component_values)
        residence_components.update(
            {person_id: component for person_id in component}
        )
    residence_people = set(cotravel_people)
    for person_id in sorted(cotravel_people):
        residence_people.update(residence_components.get(person_id, ()))

    cotravel_rows = cotravel.loc[
        cotravel["u"].isin(cotravel_people)
        & cotravel["v"].isin(cotravel_people)
    ]
    residence_rows = residence.loc[
        residence["u"].isin(residence_people)
        & residence["v"].isin(residence_people)
    ]
    rows = pd.concat(
        [cotravel_rows, residence_rows], ignore_index=False
    ).copy(deep=True)
    if rows.empty:
        return rows.reset_index(drop=True)
    rows["__source_order"] = np.arange(len(rows))
    rows = rows.sort_values(
        ["source_row_id", "__source_order"], kind="stable"
    ).drop(columns="__source_order")
    return rows.reset_index(drop=True)


def _cotravel_groups_changing_pooling(active_edges, groups):
    relation = active_edges["edge_type"].astype(str).str.upper()
    cotravel = active_edges.loc[relation == "COTRAVEL"]
    graph = nx.Graph()
    graph.add_edges_from(
        cotravel[["u", "v"]].itertuples(index=False, name=None)
    )
    bridge_pairs = {
        tuple(sorted((str(u), str(v)))) for u, v in nx.bridges(graph)
    }
    pair_source_ids = {}
    for source_row_id, u, v in cotravel[
        ["source_row_id", "u", "v"]
    ].itertuples(index=False, name=None):
        endpoint_pair = tuple(sorted((str(u), str(v))))
        pair_source_ids.setdefault(endpoint_pair, set()).add(
            str(source_row_id)
        )

    changing = set()
    for group_key, source_row_ids, endpoint_pair in groups:
        if (
            endpoint_pair in bridge_pairs
            and pair_source_ids.get(endpoint_pair, set()).issubset(
                source_row_ids
            )
        ):
            changing.add(group_key)
    return frozenset(changing)


def build_ablation_specs(
    snapshot,
    person_id,
    community,
    *,
    ranked_edge_source_row_ids=(),
    pooled_logit_contributions=None,
):
    if not isinstance(person_id, str) or not person_id.strip():
        raise ValueError("person_id must be a non-blank string")
    required = {
        "source_row_id",
        "canonical_pair_group_id",
        "u",
        "v",
        "rel",
        "edge_type",
    }
    missing = sorted(required.difference(snapshot.active_edges.columns))
    if missing:
        raise ValueError(
            "snapshot active_edges missing ablation columns: "
            + ", ".join(missing)
        )
    if not isinstance(community, Mapping):
        raise ValueError("community must be a mapping")
    base_source_ids = _canonical_string_ids(
        community.get("base_source_row_ids", ()),
        field_name="base_source_row_ids",
    )
    nodes_by_id = community.get("nodes_by_id")
    if not isinstance(nodes_by_id, Mapping):
        raise ValueError("community nodes_by_id must be a mapping")
    visible_people = _canonical_string_ids(
        tuple(nodes_by_id), field_name="visible_people"
    )
    if person_id not in visible_people:
        raise ValueError("person_id must belong to the visible community")

    active = snapshot.active_edges.copy(deep=False)
    internal = active.loc[
        active["source_row_id"].astype(str).isin(base_source_ids)
    ]
    ranked_source_ids = _canonical_string_ids(
        tuple(ranked_edge_source_row_ids),
        field_name="ranked_edge_source_row_ids",
    )
    source_rank = {
        source_row_id: rank
        for rank, source_row_id in enumerate(ranked_source_ids)
    }
    specs = []
    group_columns = ["canonical_pair_group_id", "rel"]
    grouped = internal.groupby(group_columns, sort=True, dropna=False)
    if ranked_source_ids:
        attributed = internal.loc[
            internal["source_row_id"].astype(str).isin(ranked_source_ids)
        ]
        group_ranks = {}
        for group_id, relation_id, source_row_id in attributed[
            [*group_columns, "source_row_id"]
        ].itertuples(index=False, name=None):
            key = (group_id, int(relation_id))
            group_ranks[key] = min(
                group_ranks.get(key, len(source_rank)),
                source_rank[str(source_row_id)],
            )
        ranked_groups = sorted(
            group_ranks,
            key=lambda key: (group_ranks[key], str(key[0]), key[1]),
        )[:10]
    else:
        ranked_groups = [
            (group_id, int(relation_id))
            for group_id, relation_id in list(grouped.groups)[:10]
        ]
    for group_id, relation_id in ranked_groups:
        frame = grouped.get_group((group_id, relation_id))
        source_ids = tuple(sorted(frame["source_row_id"].astype(str)))
        specs.append(
            AblationSpec(
                factor_id=f"pair:{group_id}:rel:{int(relation_id)}",
                kind="pair_relation",
                edge_source_row_ids=source_ids,
            )
        )

    incident = internal.loc[
        (internal["u"] == person_id) | (internal["v"] == person_id)
    ]
    for relation_id, frame in incident.groupby("rel", sort=True):
        specs.append(
            AblationSpec(
                factor_id=f"relation-star:{person_id}:rel:{int(relation_id)}",
                kind="relation_star",
                edge_source_row_ids=tuple(
                    sorted(frame["source_row_id"].astype(str))
                ),
            )
        )

    caught_before = frozenset(snapshot.caught_before_snapshot)
    caught_visible = caught_before.intersection(visible_people)
    if pooled_logit_contributions is None:
        contributions = {}
    elif not isinstance(pooled_logit_contributions, Mapping):
        raise ValueError("pooled_logit_contributions must be a mapping")
    else:
        contributions = {
            str(key): float(value)
            for key, value in pooled_logit_contributions.items()
        }
        if any(not np.isfinite(value) for value in contributions.values()):
            raise ValueError("pooled_logit_contributions must be finite")
    for caught_person_id in sorted(
        caught_visible,
        key=lambda value: (-abs(contributions.get(value, 0.0)), value),
    )[:5]:
        specs.append(
            AblationSpec(
                factor_id=f"caught:{caught_person_id}",
                kind="caught_flag",
                caught_person_ids=(caught_person_id,),
            )
        )

    structural_rows = structural_provenance_rows(active, visible_people)
    if len(structural_rows):
        structural_people = set(structural_rows["u"].astype(str)).union(
            structural_rows["v"].astype(str)
        )
        provenance_people = tuple(
            sorted(structural_people.difference(visible_people))
        )
        if provenance_people:
            specs.append(
                AblationSpec(
                    factor_id=f"structural:{person_id}",
                    kind="structural_provenance",
                    edge_source_row_ids=tuple(
                        sorted(structural_rows["source_row_id"].astype(str))
                    ),
                    provenance_node_ids=provenance_people,
                )
            )

    cotravel = internal.loc[
        internal["edge_type"].astype(str).str.upper() == "COTRAVEL"
    ]
    cotravel_groups = []
    for (group_id, relation_id), frame in cotravel.groupby(
        group_columns, sort=True, dropna=False
    ):
        endpoint_pairs = {
            tuple(sorted((str(u), str(v))))
            for u, v in frame[["u", "v"]].itertuples(
                index=False, name=None
            )
        }
        if len(endpoint_pairs) != 1:
            raise ValueError(
                "canonical COTRAVEL pair group has inconsistent endpoints"
            )
        source_ids = tuple(sorted(frame["source_row_id"].astype(str)))
        endpoint_pair = next(iter(endpoint_pairs))
        if ranked_source_ids and not set(source_ids).intersection(source_rank):
            continue
        cotravel_groups.append(
            (
                (group_id, int(relation_id)),
                frozenset(source_ids),
                endpoint_pair,
            )
        )
    pooling_changes = _cotravel_groups_changing_pooling(
        active, cotravel_groups
    )
    selected_pooling = 0
    for (group_id, relation_id), source_ids, _ in cotravel_groups:
        if (group_id, relation_id) in pooling_changes:
            specs.append(
                AblationSpec(
                    factor_id=(
                        f"cotravel-pool:{group_id}:rel:{int(relation_id)}"
                    ),
                    kind="cotravel_pool",
                    edge_source_row_ids=tuple(source_ids),
                )
            )
            selected_pooling += 1
            if selected_pooling == 5:
                break

    by_factor_id = {}
    for spec in specs:
        existing = by_factor_id.get(spec.factor_id)
        if existing is not None and existing != spec:
            raise ValueError(f"conflicting ablation factor_id: {spec.factor_id}")
        by_factor_id[spec.factor_id] = spec
    return [by_factor_id[factor_id] for factor_id in sorted(by_factor_id)]


def build_complete_community(engine, target_person_id, scoring_day):
    if target_person_id not in engine.person_index:
        raise KeyError(f"unknown person_id: {target_person_id}")
    snapshot = engine.snapshot(scoring_day)
    target_index = engine.person_index[target_person_id]
    target_root = snapshot.component_roots[target_index]
    pooled_indices = set(
        np.flatnonzero(snapshot.component_roots == target_root).tolist()
    )
    pooled_member_ids = tuple(
        sorted(engine.node_ids[index] for index in pooled_indices)
    )
    scoring_day_iso = snapshot.scoring_day.isoformat()
    component_id = f"component:{_length_framed_hash(pooled_member_ids)}"
    community_key = f"community:{_length_framed_hash((scoring_day_iso, component_id))}"

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
            "pooled_member": index in pooled_indices,
            "caught_before_snapshot": (
                person_id in snapshot.caught_before_snapshot
            ),
            "caught_label_available_time": None,
        }
        if person_id in snapshot.caught_before_snapshot:
            record["caught_label_available_time"] = (
                engine._Seed0ExplanationEngine__caught_available_time(
                    person_id
                ).isoformat()
            )
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
        "scoring_day": scoring_day_iso,
        "component_id": component_id,
        "community_key": community_key,
        "nodes": nodes,
        "nodes_by_id": nodes_by_id,
        "edges": edges,
        "base_source_row_ids": sorted(internal["source_row_id"].astype(str)),
        "provenance_expansions": [],
    }


def _normalized_layout(graph):
    """Place deterministic connected clusters in bounded grid cells, O(N+E)."""
    if not graph:
        return {}
    components = sorted(
        (tuple(sorted(component)) for component in nx.connected_components(graph)),
        key=lambda component: component[0],
    )
    cluster_columns = max(1, int(np.ceil(np.sqrt(len(components)))))
    cluster_rows = int(np.ceil(len(components) / cluster_columns))
    positions = {}
    for cluster_index, component in enumerate(components):
        cluster_column = cluster_index % cluster_columns
        cluster_row = cluster_index // cluster_columns
        local_columns = max(1, int(np.ceil(np.sqrt(len(component)))))
        local_rows = int(np.ceil(len(component) / local_columns))
        for local_index, person_id in enumerate(component):
            local_column = local_index % local_columns
            local_row = local_index // local_columns
            local_x = (local_column + 0.5) / local_columns
            local_y = (local_row + 0.5) / local_rows
            positions[person_id] = np.array(
                [
                    (cluster_column + 0.1 + 0.8 * local_x) / cluster_columns,
                    (cluster_row + 0.1 + 0.8 * local_y) / cluster_rows,
                ],
                dtype=float,
            )
    return positions


def json_safe(value):
    """Detach supported scientific values into deterministic JSON primitives."""
    if isinstance(value, Mapping):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if torch.is_tensor(value):
        return json_safe(value.detach().cpu().numpy())
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [json_safe(item) for item in sorted(value, key=str)]
    if isinstance(value, float) and not np.isfinite(value):
        raise ValueError("JSON payload floats must be finite")
    return value


def build_provenance_expansion(engine, snapshot, spec, community):
    """Expand strict-as-of factor provenance outside the message community."""
    if not isinstance(engine, Seed0ExplanationEngine):
        raise ValueError("engine must be a Seed0ExplanationEngine")
    if not isinstance(snapshot, DaySnapshot):
        raise ValueError("snapshot must be a DaySnapshot")
    if not isinstance(spec, AblationSpec):
        raise ValueError("spec must be an AblationSpec")
    if not isinstance(community, Mapping):
        raise ValueError("community must be a mapping")
    base_ids = set(
        _canonical_string_ids(
            community.get("base_source_row_ids", ()),
            field_name="base_source_row_ids",
        )
    )
    active_ids = set(snapshot.active_edges["source_row_id"].astype(str))
    inactive_ids = sorted(
        set(spec.edge_source_row_ids).difference(active_ids)
    )
    if inactive_ids:
        raise ValueError(
            "provenance expansion source IDs must be active strictly before "
            f"the scoring snapshot: {inactive_ids}"
        )
    outside_ids = set(spec.edge_source_row_ids).difference(base_ids)
    if not outside_ids:
        return None
    frame = snapshot.active_edges.loc[
        snapshot.active_edges["source_row_id"].astype(str).isin(outside_ids)
    ].copy(deep=True)
    if frame.empty:
        return None
    if not (
        pd.to_datetime(frame["avail_time"], utc=True, errors="raise")
        < snapshot.scoring_day
    ).all():
        raise ValueError(
            "provenance expansion contains evidence at or after the snapshot"
        )
    nodes_by_id = community.get("nodes_by_id")
    if not isinstance(nodes_by_id, Mapping):
        raise ValueError("community nodes_by_id must be a mapping")
    people = sorted(
        set(frame["u"].astype(str)).union(frame["v"].astype(str))
    )
    outside_people = [
        person_id for person_id in people if person_id not in nodes_by_id
    ]
    ring_position = {
        person_id: (
            0.5
            + 0.46
            * np.cos(
                2 * np.pi * index / max(1, len(outside_people))
            ),
            0.5
            + 0.46
            * np.sin(
                2 * np.pi * index / max(1, len(outside_people))
            ),
        )
        for index, person_id in enumerate(outside_people)
    }
    nodes = []
    for person_id in people:
        if person_id in nodes_by_id:
            nodes.append(copy.deepcopy(dict(nodes_by_id[person_id])))
            continue
        caught_before = person_id in snapshot.caught_before_snapshot
        available_time = engine.caught_available_time(person_id)
        nodes.append(
            {
                "node_id": person_id,
                "x": float(ring_position[person_id][0]),
                "y": float(ring_position[person_id][1]),
                "target": False,
                "pooled_member": False,
                "caught_before_snapshot": caught_before,
                "caught_label_available_time": (
                    available_time.isoformat()
                    if caught_before and available_time is not None
                    else None
                ),
            }
        )

    edges = []
    for (group_id, relation), group in frame.groupby(
        ["canonical_pair_group_id", "rel"], sort=True
    ):
        endpoint_pairs = {
            tuple(sorted((str(row.u), str(row.v))))
            for row in group.itertuples(index=False)
        }
        if len(endpoint_pairs) != 1:
            raise ValueError(
                "provenance pair group has inconsistent endpoints"
            )
        edge_types = set(group["edge_type"].astype(str))
        if len(edge_types) != 1:
            raise ValueError(
                "provenance pair group has inconsistent edge types"
            )
        u, v = next(iter(endpoint_pairs))
        observations = sorted(
            (
                {
                    "source_row_id": str(row.source_row_id),
                    "available_time": pd.Timestamp(row.avail_time).isoformat(),
                }
                for row in group.itertuples(index=False)
            ),
            key=lambda item: (
                item["available_time"],
                item["source_row_id"],
            ),
        )
        edges.append(
            {
                "edge_id": f"provenance:{group_id}:rel:{int(relation)}",
                "u": u,
                "v": v,
                "rel": int(relation),
                "edge_type": next(iter(edge_types)),
                "source_row_ids": sorted(
                    observation["source_row_id"]
                    for observation in observations
                ),
                "observations": observations,
            }
        )
    edges.sort(key=lambda edge: edge["edge_id"])
    return {
        "expansion_id": f"provenance:{spec.factor_id}",
        "label": "outside message community",
        "nodes": nodes,
        "edges": edges,
    }


def _normalize_member_mask(mask, *, expected_length, field_name):
    values = _readonly_float_mask(
        mask, expected_length=expected_length, field_name=field_name
    )
    if values.size == 0:
        return np.zeros(0, dtype=float)
    maximum = float(values.max())
    return (
        np.asarray(values, dtype=float) / maximum
        if maximum > 0.0
        else np.zeros(values.shape, dtype=float)
    )


def _empty_feature_aggregate(feature_count):
    empty = np.zeros(feature_count, dtype=float)
    return {
        "median": empty.copy(),
        "q1": empty.copy(),
        "q3": empty.copy(),
        "selection_frequency": empty.copy(),
        "restart_count": 0,
        "top_factor_agreement": 0.0,
        "status": "no-features",
    }


def _factor_restart_metrics(
    spec,
    community_edges,
    feature_names,
    feature_aggregate,
):
    feature_indices = []
    if spec.kind == "caught_flag" and "caught_before_snapshot" in feature_names:
        feature_indices = [feature_names.index("caught_before_snapshot")]
    elif spec.kind == "structural_provenance":
        feature_indices = [
            feature_names.index(name)
            for name in (
                "log1p_cotravel_component_size",
                "log1p_households_spanned",
            )
            if name in feature_names
        ]
    if feature_indices and feature_aggregate["restart_count"]:
        frequency = max(
            feature_aggregate["selection_frequency"][index]
            for index in feature_indices
        )
        iqr = max(
            feature_aggregate["q3"][index]
            - feature_aggregate["q1"][index]
            for index in feature_indices
        )
        return float(frequency), float(iqr), "feature_mask"

    matching = [
        edge
        for edge in community_edges
        if set(edge["source_row_ids"]).intersection(
            spec.edge_source_row_ids
        )
    ]
    if matching:
        frequency = max(edge["selection_frequency"] for edge in matching)
        iqr = max(
            edge["explainer_q3"] - edge["explainer_q1"]
            for edge in matching
        )
        return float(frequency), float(iqr), "edge_mask"
    return 0.0, 1.0, "not_applicable"


def compose_case_explanation(
    engine,
    case,
    *,
    member_explainer=None,
    restart_seeds=(0, 1, 2),
    explainer_epochs=150,
    max_explainable_component_size=None,
):
    """Compose one deterministic, leak-safe seed-0 explanation payload.

    GNNExplainer runs only for the target person's exact two-hop pre-pool
    computation. Component pooling remains an exact deterministic ledger.
    """
    if not isinstance(engine, Seed0ExplanationEngine):
        raise ValueError("engine must be a Seed0ExplanationEngine")
    if not isinstance(case, HybridOnlyCase):
        raise ValueError("case must be a HybridOnlyCase")
    if max_explainable_component_size is not None:
        if (
            not isinstance(max_explainable_component_size, (int, np.integer))
            or isinstance(max_explainable_component_size, (bool, np.bool_))
            or max_explainable_component_size <= 0
        ):
            raise ValueError(
                "max_explainable_component_size must be a positive integer"
            )
        max_explainable_component_size = int(max_explainable_component_size)
    seeds = _validated_restart_seeds(restart_seeds)
    reference = engine.rank_reference
    if reference is None:
        raise ValueError("case explanation requires a frozen rank reference")
    if not 0 <= case.anchor.row_index < len(reference.event_ids):
        raise ValueError("case anchor row is outside the rank reference")

    snapshot = engine.snapshot(case.anchor.scoring_day)
    target_index = engine.person_index[case.person_id]
    decision_trace = case.decision_trace_jsonable()
    snapshot_probability_parity = bool(
        np.isclose(
            snapshot.probabilities[target_index],
            reference.seed0_gnn_raw[case.anchor.row_index],
            rtol=1e-6,
            atol=1e-7,
        )
    )
    anchor_event_parity = bool(
        reference.event_ids[case.anchor.row_index] == case.anchor.event_id
    )
    if not snapshot_probability_parity or not anchor_event_parity:
        raise ValueError("case explanation failed production parity")
    daily_budget = decision_trace.get("daily_budget")
    if (
        not isinstance(daily_budget, (int, np.integer))
        or isinstance(daily_budget, (bool, np.bool_))
        or daily_budget <= 0
    ):
        raise ValueError("case decision trace daily_budget must be positive")
    daily_budget = int(daily_budget)
    engine._Seed0ExplanationEngine__validate_candidate_rows_for_day(
        case.anchor.scoring_day,
        case.baseline_candidate_row_indices,
        field_name="baseline_candidate_row_indices",
    )
    engine._Seed0ExplanationEngine__validate_candidate_rows_for_day(
        case.anchor.scoring_day,
        case.hybrid_candidate_row_indices,
        field_name="hybrid_candidate_row_indices",
    )
    try:
        expected_trace = build_decision_trace(
            reference,
            row_index=case.anchor.row_index,
            baseline_candidate_row_indices=(
                case.baseline_candidate_row_indices
            ),
            hybrid_candidate_row_indices=case.hybrid_candidate_row_indices,
            daily_budget=daily_budget,
        )
    except ValueError as exc:
        raise ValueError(
            "case decision trace does not match the frozen references"
        ) from exc
    if decision_trace != expected_trace:
        raise ValueError(
            "case decision trace does not match the frozen references"
        )
    outer_case_parity = bool(
        case.baseline_rank == expected_trace["baseline_rank"]
        and case.gnn_rank == expected_trace["seed0_gnn_rank"]
        and case.hybrid_rank == expected_trace["seed0_hybrid_rank"]
        and np.isclose(
            case.baseline_percentile,
            expected_trace["baseline_percentile"],
            rtol=1e-7,
            atol=1e-8,
        )
        and np.isclose(
            case.gnn_percentile,
            expected_trace["seed0_gnn_percentile"],
            rtol=1e-7,
            atol=1e-8,
        )
    )
    if not outer_case_parity:
        raise ValueError(
            "case rank fields do not match the frozen references"
        )
    component_root = snapshot.component_roots[target_index]
    member_indices = np.flatnonzero(
        snapshot.component_roots == component_root
    ).tolist()
    member_ids = sorted(engine.node_ids[index] for index in member_indices)
    if (
        max_explainable_component_size is not None
        and len(member_ids) > max_explainable_component_size
    ):
        raise ValueError(
            f"pooled component size {len(member_ids)} exceeds maximum "
            "explainable component size "
            f"{max_explainable_component_size}"
        )
    member_indices = [engine.person_index[person_id] for person_id in member_ids]
    member_logits = snapshot.prepool_logits[member_indices]
    pooled_logit = snapshot.pooled_logits[target_index]
    pooled_parity = bool(
        torch.isclose(
            pooled_logit,
            member_logits.mean(),
            rtol=1e-6,
            atol=1e-6,
        ).item()
    )
    if not pooled_parity:
        raise ValueError("component member logits failed pooled-logit parity")

    probability_parity = snapshot_probability_parity
    percentile_parity = True
    rank_parity = True

    context = CounterfactualContext(
        person_id=case.person_id,
        row_index=case.anchor.row_index,
        scoring_day=case.anchor.scoring_day,
        same_day_person_row_indices=case.same_day_person_row_indices,
        candidate_row_indices=case.hybrid_candidate_row_indices,
        original_hybrid_rank=case.hybrid_rank,
    )
    diagnostic_edge_source_set_probability(engine, context, ())
    community = engine.community(case.person_id, case.anchor.scoring_day)

    # Attribution values are a target-specific overlay. Never annotate the
    # canonical day/component community shared by multiple cases.
    edges = [
        {
            key: copy.deepcopy(value)
            for key, value in canonical_edge.items()
            if key != "observations"
        }
        for canonical_edge in community["edges"]
    ]
    edge_ids = [edge["edge_id"] for edge in edges]
    source_to_edge = {}
    for edge in edges:
        for source_row_id in edge["source_row_ids"]:
            existing = source_to_edge.get(source_row_id)
            if existing is not None and existing != edge["edge_id"]:
                raise ValueError(
                    "immutable source provenance maps to multiple display edges"
                )
            source_to_edge[source_row_id] = edge["edge_id"]

    restart_edge_values = [defaultdict(float) for _ in seeds]
    feature_count = snapshot.x.shape[1]
    explainer = run_member_explanation if member_explainer is None else member_explainer
    result = explainer(
        engine,
        case.person_id,
        case.anchor.scoring_day,
        restart_seeds=seeds,
        epochs=explainer_epochs,
    )
    if tuple(result.get("restart_seeds", ())) != seeds:
        raise ValueError("target explanation restart seeds are misaligned")
    expected_logit = float(snapshot.prepool_logits[target_index])
    if not (
        np.isclose(
            result.get("local_prepool_logit", np.nan),
            expected_logit,
            rtol=1e-6,
            atol=1e-6,
        )
        and np.isclose(
            result.get("full_prepool_logit", np.nan),
            expected_logit,
            rtol=1e-6,
            atol=1e-6,
        )
    ):
        raise ValueError("target explanation failed local/full parity")
    local = member_subgraph(engine, case.person_id, case.anchor.scoring_day)
    provenance = local.tensor_edge_source_row_ids
    local_edge_index = local.edge_index.detach().cpu().numpy()
    local_node_ids = [
        engine.node_ids[int(index)] for index in local.original_node_indices
    ]
    edge_masks = tuple(result.get("edge_masks", ()))
    if len(edge_masks) != len(seeds):
        raise ValueError("target edge-mask restarts are misaligned")
    for restart_index, mask in enumerate(edge_masks):
        normalized = _normalize_member_mask(
            mask,
            expected_length=len(provenance),
            field_name="target edge_mask",
        )
        for source_row_id, value in zip(provenance, normalized):
            display_edge_id = source_to_edge.get(str(source_row_id))
            if display_edge_id is None:
                raise ValueError(
                    "local tensor-edge provenance is absent from the "
                    f"complete display community: {source_row_id}"
                )
            restart_edge_values[restart_index][display_edge_id] += float(value)

    node_feature_masks = tuple(result.get("node_feature_masks", ()))
    if len(node_feature_masks) != len(seeds):
        raise ValueError("target node-feature-mask restarts are misaligned")
    normalized_node_feature_masks = []
    for mask in node_feature_masks:
        checked = _readonly_node_feature_mask(
            mask,
            expected_shape=(len(local_node_ids), feature_count),
            field_name="target node_feature_mask",
        )
        maximum = float(checked.max()) if checked.size else 0.0
        normalized_node_feature_masks.append(
            np.asarray(checked, dtype=float) / maximum
            if maximum > 0.0
            else np.zeros(checked.shape, dtype=float)
        )

    aligned_edge_masks = [
        np.array([values[edge_id] for edge_id in edge_ids], dtype=float)
        for values in restart_edge_values
    ]
    edge_aggregate = aggregate_restart_masks(aligned_edge_masks)
    node_feature_aggregate = aggregate_restart_masks(
        [mask.reshape(-1) for mask in normalized_node_feature_masks]
    )
    node_feature_stats = {
        key: np.asarray(value).reshape(len(local_node_ids), feature_count)
        for key, value in node_feature_aggregate.items()
        if key in {"median", "q1", "q3", "selection_frequency"}
    }
    node_aggregate = aggregate_restart_masks(
        [mask.max(axis=1) for mask in normalized_node_feature_masks]
    )
    target_local_index = local_node_ids.index(case.person_id)
    feature_aggregate = aggregate_restart_masks(
        [mask[target_local_index] for mask in normalized_node_feature_masks]
    )
    for index, edge in enumerate(edges):
        edge["explainer_median"] = float(edge_aggregate["median"][index])
        edge["explainer_q1"] = float(edge_aggregate["q1"][index])
        edge["explainer_q3"] = float(edge_aggregate["q3"][index])
        edge["selection_frequency"] = float(
            edge_aggregate["selection_frequency"][index]
        )

    feature_names = list(caught_feature_names(engine.num_rel))
    if len(feature_names) != feature_count:
        raise ValueError("feature names are not aligned with snapshot inputs")
    display_feature_mask_stats = [
        {
            "feature_name": name,
            "explainer_median": float(feature_aggregate["median"][index]),
            "explainer_q1": float(feature_aggregate["q1"][index]),
            "explainer_q3": float(feature_aggregate["q3"][index]),
            "selection_frequency": float(
                feature_aggregate["selection_frequency"][index]
            ),
        }
        for index, name in enumerate(feature_names)
    ]

    incident_source_rows = {node_id: set() for node_id in local_node_ids}
    for tensor_edge_index, source_row_id in enumerate(provenance):
        source = local_node_ids[int(local_edge_index[0, tensor_edge_index])]
        target = local_node_ids[int(local_edge_index[1, tensor_edge_index])]
        incident_source_rows[source].add(str(source_row_id))
        incident_source_rows[target].add(str(source_row_id))

    ranked_node_indices = sorted(
        range(len(local_node_ids)),
        key=lambda index: (
            -float(node_aggregate["median"][index]),
            local_node_ids[index],
        ),
    )[:10]
    top_local_nodes = [
        {
            "rank": rank,
            "node_id": local_node_ids[index],
            "source_id": local_node_ids[index],
            "source_row_ids": sorted(incident_source_rows[local_node_ids[index]]),
            "explainer_median": float(node_aggregate["median"][index]),
            "explainer_q1": float(node_aggregate["q1"][index]),
            "explainer_q3": float(node_aggregate["q3"][index]),
            "selection_frequency": float(
                node_aggregate["selection_frequency"][index]
            ),
        }
        for rank, index in enumerate(ranked_node_indices, start=1)
    ]
    ranked_edge_indices = sorted(
        range(len(edges)),
        key=lambda index: (
            -float(edge_aggregate["median"][index]),
            edges[index]["edge_id"],
        ),
    )[:10]
    top_edges = [
        {
            "rank": rank,
            "edge_id": edges[index]["edge_id"],
            "u": edges[index]["u"],
            "v": edges[index]["v"],
            "edge_type": edges[index]["edge_type"],
            "source_row_ids": list(edges[index]["source_row_ids"]),
            "explainer_median": float(edge_aggregate["median"][index]),
            "explainer_q1": float(edge_aggregate["q1"][index]),
            "explainer_q3": float(edge_aggregate["q3"][index]),
            "selection_frequency": float(
                edge_aggregate["selection_frequency"][index]
            ),
        }
        for rank, index in enumerate(ranked_edge_indices, start=1)
    ]
    ranked_feature_indices = sorted(
        range(feature_count),
        key=lambda index: (
            -float(feature_aggregate["median"][index]),
            feature_names[index],
        ),
    )[:5]
    top_features = [
        {
            "rank": rank,
            "feature_index": index,
            "feature_name": feature_names[index],
            "node_id": case.person_id,
            "source_id": f"{case.person_id}:feature:{index}",
            "feature_value": float(snapshot.x[target_index, index]),
            "explainer_median": float(feature_aggregate["median"][index]),
            "explainer_q1": float(feature_aggregate["q1"][index]),
            "explainer_q3": float(feature_aggregate["q3"][index]),
            "selection_frequency": float(
                feature_aggregate["selection_frequency"][index]
            ),
        }
        for rank, index in enumerate(ranked_feature_indices, start=1)
    ]
    node_feature_mask_stats = [
        {
            "node_id": node_id,
            "feature_index": feature_index,
            "feature_name": feature_names[feature_index],
            "source_id": f"{node_id}:feature:{feature_index}",
            "explainer_median": float(
                node_feature_stats["median"][node_index, feature_index]
            ),
            "explainer_q1": float(
                node_feature_stats["q1"][node_index, feature_index]
            ),
            "explainer_q3": float(
                node_feature_stats["q3"][node_index, feature_index]
            ),
            "selection_frequency": float(
                node_feature_stats["selection_frequency"][
                    node_index, feature_index
                ]
            ),
        }
        for node_index, node_id in enumerate(local_node_ids)
        for feature_index in range(feature_count)
    ]

    pooled_contributions = {
        member_id: float(
            snapshot.prepool_logits[engine.person_index[member_id]]
        )
        / len(member_ids)
        for member_id in member_ids
    }
    ranked_source_row_ids = tuple(
        source_row_id
        for edge in top_edges
        for source_row_id in edge["source_row_ids"]
    )
    salient_specs = build_ablation_specs(
        snapshot,
        case.person_id,
        community,
        ranked_edge_source_row_ids=ranked_source_row_ids,
        pooled_logit_contributions=pooled_contributions,
    )
    rank_state = engine._Seed0ExplanationEngine__rank_state
    engine._Seed0ExplanationEngine__factor_specs_cache[
        (rank_state.fingerprint, context.scoring_day, context.person_id)
    ] = tuple(salient_specs)

    factors = []
    provenance_expansions = []
    for spec in salient_specs:
        counterfactual = engine.score_counterfactual(context, spec)
        frequency, iqr, restart_source = _factor_restart_metrics(
            spec, edges, feature_names, feature_aggregate
        )
        expansion = build_provenance_expansion(
            engine, snapshot, spec, community
        )
        if expansion is not None:
            provenance_expansions.append(expansion)
        factors.append(
            {
                "factor_id": spec.factor_id,
                "label": spec.factor_id.replace(":", " · "),
                "kind": spec.kind,
                "counterfactual": counterfactual,
                "restart": {
                    "selection_frequency": frequency,
                    "iqr": iqr,
                    "source": restart_source,
                },
                "stability": classify_factor_stability(
                    counterfactual, frequency, iqr
                ),
                "provenance_expansion_ids": (
                    [expansion["expansion_id"]]
                    if expansion is not None
                    else []
                ),
            }
        )

    importance_by_id = {
        edge["edge_id"]: edge["explainer_median"] for edge in edges
    }
    degrees = defaultdict(int)
    for edge in edges:
        degrees[edge["u"]] += 1
        degrees[edge["v"]] += 1

    def degree_bin(value):
        if value <= 1:
            return "1"
        if value <= 4:
            return "2-4"
        if value <= 8:
            return "5-8"
        return "9+"

    faithfulness_edges = [
        {
            "edge_id": edge["edge_id"],
            "relation": edge["edge_type"],
            "degree_bin": degree_bin(
                max(degrees[edge["u"]], degrees[edge["v"]])
            ),
        }
        for edge in edges
    ]
    edge_by_id = {edge["edge_id"]: edge for edge in edges}

    def rescore(removed_edge_ids):
        source_ids = tuple(
            sorted(
                {
                    source_row_id
                    for edge_id in removed_edge_ids
                    for source_row_id in edge_by_id[edge_id][
                        "source_row_ids"
                    ]
                }
            )
        )
        return diagnostic_edge_source_set_probability(
            engine, context, source_ids
        )

    faithfulness = edge_removal_faithfulness(
        faithfulness_edges,
        importance_by_id,
        rescore=rescore,
        seed=0,
    )
    stable_count = sum(
        factor["stability"] == "stable" for factor in factors
    )
    component_members = []
    for member_id in member_ids:
        prepool_logit = float(
            snapshot.prepool_logits[engine.person_index[member_id]]
        )
        component_members.append(
            {
                "person_id": member_id,
                "source_id": member_id,
                "prepool_logit": prepool_logit,
                "pooled_logit_contribution": prepool_logit / len(member_ids),
            }
        )
    ranked_component_members = sorted(
        component_members,
        key=lambda member: (
            -abs(member["pooled_logit_contribution"]),
            member["person_id"],
        ),
    )
    top_component_members = [
        {"rank": rank, **member}
        for rank, member in enumerate(ranked_component_members[:10], start=1)
    ]
    component_contribution_sum = sum(
        member["pooled_logit_contribution"] for member in component_members
    )
    if not np.isclose(
        component_contribution_sum,
        float(pooled_logit),
        rtol=1e-6,
        atol=1e-6,
    ):
        raise ValueError("component contribution ledger failed pooled-logit parity")

    baseline_term = float(decision_trace["baseline_weighted_term"])
    gnn_term = float(decision_trace["seed0_gnn_weighted_term"])
    hybrid_score = float(decision_trace["seed0_hybrid_score"])
    if not np.isclose(
        baseline_term + gnn_term,
        hybrid_score,
        rtol=1e-7,
        atol=1e-8,
    ):
        raise ValueError("rank-fusion ledger failed hybrid-score parity")
    decision_ledger = {
        "component_pooling": {
            "pooling": "exact_mean_of_member_prepool_logits",
            "component_size": len(component_members),
            "pooled_logit": float(pooled_logit),
            "contribution_sum": component_contribution_sum,
            "top_members_by_absolute_contribution": top_component_members,
        },
        "rank_fusion": {
            "percentile_reference_id": decision_trace[
                "percentile_reference_id"
            ],
            "baseline_daily_reference_id": decision_trace[
                "baseline_daily_reference_id"
            ],
            "hybrid_daily_reference_id": decision_trace[
                "hybrid_daily_reference_id"
            ],
            "daily_budget": daily_budget,
            "blend_weight": float(reference.blend_weight),
            "baseline_percentile": float(
                decision_trace["baseline_percentile"]
            ),
            "seed0_gnn_probability": float(
                decision_trace["seed0_gnn_probability"]
            ),
            "seed0_gnn_percentile": float(
                decision_trace["seed0_gnn_percentile"]
            ),
            "baseline_weighted_term": baseline_term,
            "seed0_gnn_weighted_term": gnn_term,
            "hybrid_score": hybrid_score,
            "baseline_rank": int(decision_trace["baseline_rank"]),
            "seed0_gnn_rank": int(decision_trace["seed0_gnn_rank"]),
            "seed0_hybrid_rank": int(decision_trace["seed0_hybrid_rank"]),
        },
    }
    payload = {
        "case_id": f"case:{case.person_id}",
        "person_id": case.person_id,
        "event_id": case.anchor.event_id,
        "scoring_day": snapshot.scoring_day,
        "snapshot": {
            "scoring_day": snapshot.scoring_day,
        },
        "decision_trace": decision_trace,
        "decision_ledger": decision_ledger,
        "attributions": {
            "scope": {
                "target_person_id": case.person_id,
                "hops": 2,
                "restart_seeds": list(seeds),
                "epochs": int(explainer_epochs),
                "unsigned_masks": True,
            },
            "unsigned_mask_caveat": (
                "GNNExplainer masks are unsigned; direction is established only "
                "by validated counterfactual rank effects."
            ),
            "top_local_nodes": top_local_nodes,
            "top_edges": top_edges,
            "top_features": top_features,
            "node_feature_mask_stats": node_feature_mask_stats,
        },
        "factors": factors,
        "factor_scope": "salient_counterfactual_factors",
        "community": community,
        "provenance_expansions": provenance_expansions,
        "display_feature_mask_stats": display_feature_mask_stats,
        "flow_stages": build_flow_stages(community),
        "stable_factor_status": "stable" if stable_count else "unstable",
        "stability": {
            "stable_factor_count": stable_count,
            "edge_restart_aggregate": edge_aggregate,
            "feature_restart_aggregate": feature_aggregate,
            "signed_effect_source": "counterfactual_only",
        },
        "faithfulness": faithfulness,
        "parity": {
            "production_seed0_probability": probability_parity,
            "pooled_logit_decomposition": pooled_parity,
            "frozen_percentile": percentile_parity,
            "frozen_daily_hybrid_rank": rank_parity,
            "anchor_event": anchor_event_parity,
        },
        "evidence_boundary": {
            "snapshot": snapshot.scoring_day,
            "edge_rule": "available_time < snapshot",
            "caught_rule": "label_available_time_utc < snapshot",
        },
    }
    safe_payload = json_safe(payload)
    validate_explanation_payload(safe_payload)
    json.dumps(
        safe_payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return safe_payload
