"""Exact seed-0 GraphSAGE day snapshots and complete message communities."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass

import networkx as nx
import numpy as np
import pandas as pd
import torch
from scipy.stats import rankdata

from gnn import learned_cell
from gnn.recovery_observability import FrozenRankReference, _selection_tiebreak


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
        self.__counterfactual_cache: dict[str, dict[str, object]] = {}
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

    def score_counterfactual(self, context, factor):
        return score_grouped_counterfactual(self, context, factor)

    def __caught_available_time(self, person_id):
        return self.__prepared_source.caught_time[person_id]

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


def build_ablation_specs(snapshot, person_id, community):
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
    specs = []
    group_columns = ["canonical_pair_group_id", "rel"]
    for (group_id, relation_id), frame in internal.groupby(
        group_columns, sort=True, dropna=False
    ):
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
    for caught_person_id in sorted(caught_before.intersection(visible_people)):
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
