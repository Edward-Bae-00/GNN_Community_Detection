"""Pure recovery-set accounting for daily operational inspections."""

from __future__ import annotations

import hashlib
from collections import defaultdict, deque
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

import numpy as np
import pandas as pd
from scipy.stats import rankdata


@dataclass(frozen=True)
class RecoveryAnchor:
    person_id: str
    event_id: str
    row_index: int
    scoring_day: pd.Timestamp
    inspected_rank: int


@dataclass(frozen=True)
class DailyPoolTrace:
    scoring_day: pd.Timestamp
    candidate_row_indices: tuple[int, ...]
    inspected_row_indices: tuple[int, ...]


@dataclass(frozen=True)
class RecoveryRun:
    arm: str
    daily_budget: int
    recovered_ids: frozenset[str]
    first_recovery: Mapping[str, RecoveryAnchor]
    days: Mapping[pd.Timestamp, DailyPoolTrace]

    def __post_init__(self) -> None:
        object.__setattr__(self, "recovered_ids", frozenset(self.recovered_ids))
        object.__setattr__(
            self, "first_recovery", MappingProxyType(dict(self.first_recovery))
        )
        object.__setattr__(self, "days", MappingProxyType(dict(self.days)))


@dataclass(frozen=True)
class RecoveryOverlap:
    baseline_ids: frozenset[str]
    hybrid_ids: frozenset[str]
    both_ids: frozenset[str]
    hybrid_only_ids: frozenset[str]
    baseline_only_ids: frozenset[str]

    def __post_init__(self) -> None:
        field_names = (
            "baseline_ids",
            "hybrid_ids",
            "both_ids",
            "hybrid_only_ids",
            "baseline_only_ids",
        )
        for field_name in field_names:
            object.__setattr__(self, field_name, frozenset(getattr(self, field_name)))

        expected_sets = {
            "both_ids": self.baseline_ids & self.hybrid_ids,
            "hybrid_only_ids": self.hybrid_ids - self.baseline_ids,
            "baseline_only_ids": self.baseline_ids - self.hybrid_ids,
        }
        for field_name, expected in expected_sets.items():
            if getattr(self, field_name) != expected:
                raise ValueError(f"{field_name} is inconsistent with recovery ID sets")

    @property
    def summary(self) -> dict[str, bool | int]:
        baseline_total = len(self.baseline_ids)
        hybrid_total = len(self.hybrid_ids)
        return {
            "overlap_ids_available": True,
            "baseline_recovered": baseline_total,
            "recovered_by_both": len(self.both_ids),
            "hybrid_only_recovered": len(self.hybrid_only_ids),
            "baseline_only_recovered": len(self.baseline_only_ids),
            "hybrid_total": hybrid_total,
            "net_gain": hybrid_total - baseline_total,
        }


@dataclass(frozen=True)
class FrozenRankReference:
    percentile_reference_id: str
    event_ids: tuple[str, ...]
    baseline_raw: np.ndarray
    seed0_gnn_raw: np.ndarray
    baseline_percentile: np.ndarray
    seed0_gnn_percentile: np.ndarray
    seed0_hybrid_score: np.ndarray
    baseline_selection_score: np.ndarray
    seed0_gnn_selection_score: np.ndarray
    seed0_hybrid_selection_score: np.ndarray
    blend_weight: float

    def __post_init__(self) -> None:
        event_ids = tuple(self.event_ids)
        if not event_ids:
            raise ValueError("rank reference must contain event IDs")
        if any(
            value is None or pd.isna(value) or not str(value).strip()
            for value in event_ids
        ):
            raise ValueError("event_id must contain non-null, non-blank values")
        event_ids = tuple(str(value) for value in event_ids)
        if len(set(event_ids)) != len(event_ids):
            raise ValueError("event_id values must be unique")
        object.__setattr__(self, "event_ids", event_ids)

        array_fields = (
            "baseline_raw",
            "seed0_gnn_raw",
            "baseline_percentile",
            "seed0_gnn_percentile",
            "seed0_hybrid_score",
            "baseline_selection_score",
            "seed0_gnn_selection_score",
            "seed0_hybrid_selection_score",
        )
        for field_name in array_fields:
            copied = np.array(getattr(self, field_name), dtype=float, copy=True)
            if copied.ndim != 1 or len(copied) != len(event_ids):
                raise ValueError(
                    f"{field_name} must be one-dimensional and aligned to event_ids"
                )
            if not np.isfinite(copied).all():
                raise ValueError(f"{field_name} must be finite")
            values = np.frombuffer(copied.tobytes(), dtype=copied.dtype)
            object.__setattr__(self, field_name, values)

        blend_weight = _validated_blend_weight(self.blend_weight)
        object.__setattr__(self, "blend_weight", blend_weight)
        if self.percentile_reference_id != _ordered_id_hash(event_ids):
            raise ValueError(
                "percentile_reference_id must match ordered event_ids"
            )


@dataclass(frozen=True)
class HybridOnlyCase:
    person_id: str
    anchor: RecoveryAnchor
    baseline_rank: int
    gnn_rank: int
    hybrid_rank: int
    baseline_percentile: float
    gnn_percentile: float
    relationship_categories: tuple[str, ...]
    scoring_period: str
    same_day_person_row_indices: tuple[int, ...] = ()
    baseline_candidate_row_indices: tuple[int, ...] = ()
    hybrid_candidate_row_indices: tuple[int, ...] = ()
    decision_trace: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.person_id, str) or not self.person_id.strip():
            raise ValueError("person_id must be non-blank")
        if not isinstance(self.anchor, RecoveryAnchor):
            raise ValueError("anchor must be a RecoveryAnchor")
        if self.anchor.person_id != self.person_id:
            raise ValueError("anchor person_id must match case person_id")

        for field_name in ("baseline_rank", "gnn_rank", "hybrid_rank"):
            value = getattr(self, field_name)
            if (
                not isinstance(value, (int, np.integer))
                or isinstance(value, (bool, np.bool_))
                or value <= 0
            ):
                raise ValueError(f"{field_name} must be a positive integer")
            object.__setattr__(self, field_name, int(value))

        for field_name in ("baseline_percentile", "gnn_percentile"):
            try:
                value = float(getattr(self, field_name))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{field_name} must be between 0 and 1") from exc
            if not np.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must be between 0 and 1")
            object.__setattr__(self, field_name, value)

        if isinstance(self.relationship_categories, str):
            raise ValueError("relationship_categories must be a collection")
        categories = tuple(self.relationship_categories)
        if any(
            not isinstance(category, str) or not category.strip()
            for category in categories
        ):
            raise ValueError("relationship_categories must contain non-blank values")
        object.__setattr__(self, "relationship_categories", categories)
        if not isinstance(self.scoring_period, str) or not self.scoring_period.strip():
            raise ValueError("scoring_period must be non-blank")

        index_fields = (
            "same_day_person_row_indices",
            "baseline_candidate_row_indices",
            "hybrid_candidate_row_indices",
        )
        for field_name in index_fields:
            values = _frozen_row_indices(getattr(self, field_name), field_name)
            object.__setattr__(self, field_name, values)

        if not isinstance(self.decision_trace, Mapping):
            raise ValueError("decision_trace must be a mapping")
        object.__setattr__(
            self, "decision_trace", _freeze_json_like(self.decision_trace)
        )

    @property
    def hybrid_rank_uplift(self) -> int:
        return self.baseline_rank - self.hybrid_rank

    @property
    def gnn_percentile_uplift(self) -> float:
        return self.gnn_percentile - self.baseline_percentile

    def decision_trace_jsonable(self) -> dict[str, object]:
        """Return a detached JSON-compatible copy of the frozen trace."""
        return _thaw_json_like(self.decision_trace)


def _validated_identifier_values(values: pd.Series, column_name: str) -> pd.Series:
    if values.isna().any():
        raise ValueError(
            f"{column_name} must contain non-null, non-blank values"
        )
    text_values = values.map(str)
    if text_values.str.strip().eq("").any():
        raise ValueError(
            f"{column_name} must contain non-null, non-blank values"
        )
    return text_values


def _normalized_hidden_values(values: pd.Series) -> np.ndarray:
    normalized: list[bool] = []
    invalid_indices: list[int] = []
    string_tokens = {"true": True, "1": True, "false": False, "0": False}

    for row_index, value in enumerate(values.tolist()):
        if isinstance(value, (bool, np.bool_)):
            normalized.append(bool(value))
        elif isinstance(value, (int, np.integer)) and value in (0, 1):
            normalized.append(bool(value))
        elif isinstance(value, str) and value.strip().lower() in string_tokens:
            normalized.append(string_tokens[value.strip().lower()])
        else:
            invalid_indices.append(row_index)

    if invalid_indices:
        raise ValueError(
            "hidden contains invalid boolean values at row indices: "
            f"{invalid_indices}"
        )
    return np.asarray(normalized, dtype=bool)


def _validated_blend_weight(blend_weight: object) -> float:
    if isinstance(blend_weight, (bool, np.bool_)):
        raise ValueError("blend_weight must be finite and between 0 and 1")
    try:
        value = float(blend_weight)
    except (TypeError, ValueError) as exc:
        raise ValueError("blend_weight must be finite and between 0 and 1") from exc
    if not np.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("blend_weight must be finite and between 0 and 1")
    return value


def _frozen_row_indices(values, field_name: str) -> tuple[int, ...]:
    try:
        indices = tuple(values)
    except TypeError as exc:
        raise ValueError(f"{field_name} must contain row indices") from exc
    if any(
        not isinstance(index, (int, np.integer))
        or isinstance(index, (bool, np.bool_))
        or index < 0
        for index in indices
    ):
        raise ValueError(f"{field_name} must contain non-negative row indices")
    return tuple(int(index) for index in indices)


def _freeze_json_like(value):
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("decision_trace mapping keys must be strings")
        return MappingProxyType(
            {key: _freeze_json_like(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json_like(item) for item in value)
    if isinstance(value, (set, frozenset)):
        raise ValueError("decision_trace sets are not JSON-compatible")
    if isinstance(value, float) and not np.isfinite(value):
        raise ValueError("decision_trace floats must be finite")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError(
        "decision_trace contains an unsupported value type: "
        f"{type(value).__name__}"
    )


def _thaw_json_like(value):
    if isinstance(value, Mapping):
        return {key: _thaw_json_like(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json_like(item) for item in value]
    return value


def _ordered_id_hash(values) -> str:
    encoded_values = tuple(str(value).encode("utf-8") for value in values)
    digest = hashlib.sha256()
    digest.update(len(encoded_values).to_bytes(8, byteorder="big", signed=False))
    for value in encoded_values:
        digest.update(len(value).to_bytes(8, byteorder="big", signed=False))
        digest.update(value)
    return f"sha256:{digest.hexdigest()}"


def _selection_tiebreak(scores) -> np.ndarray:
    values = np.asarray(scores, dtype=float)
    rng = np.random.default_rng(42)
    return values + rng.uniform(0.0, 1e-9, size=len(values))


def _validated_rank_input(values, field_name: str, n_rows: int) -> np.ndarray:
    try:
        array = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("rank inputs must be numeric and one-dimensional") from exc
    if array.ndim != 1 or len(array) != n_rows:
        raise ValueError("rank inputs must be non-empty and aligned to pool rows")
    if not np.isfinite(array).all():
        raise ValueError(f"{field_name} rank inputs must be finite")
    return array


def build_rank_reference(
    pool: pd.DataFrame,
    baseline_raw,
    seed0_gnn_raw,
    blend_weight,
) -> FrozenRankReference:
    """Freeze global seed-0 percentile and selection references for one pool."""
    if "event_id" not in pool.columns:
        raise ValueError("pool missing required column: event_id")
    n_rows = len(pool)
    if n_rows == 0:
        raise ValueError("rank inputs must be non-empty and aligned to pool rows")
    baseline = _validated_rank_input(baseline_raw, "baseline", n_rows)
    gnn = _validated_rank_input(seed0_gnn_raw, "seed0 GNN", n_rows)
    weight = _validated_blend_weight(blend_weight)
    event_ids = tuple(_validated_identifier_values(pool["event_id"], "event_id"))

    baseline_pct = rankdata(baseline, method="average") / n_rows
    gnn_pct = rankdata(gnn, method="average") / n_rows
    hybrid = weight * gnn_pct + (1.0 - weight) * baseline_pct
    return FrozenRankReference(
        percentile_reference_id=_ordered_id_hash(event_ids),
        event_ids=event_ids,
        baseline_raw=baseline,
        seed0_gnn_raw=gnn,
        baseline_percentile=baseline_pct,
        seed0_gnn_percentile=gnn_pct,
        seed0_hybrid_score=hybrid,
        baseline_selection_score=_selection_tiebreak(baseline),
        seed0_gnn_selection_score=_selection_tiebreak(gnn),
        seed0_hybrid_selection_score=_selection_tiebreak(hybrid),
        blend_weight=weight,
    )


def _validated_candidate_indices(
    values,
    *,
    field_name: str,
    n_rows: int,
) -> tuple[int, ...]:
    try:
        indices = tuple(values)
    except TypeError as exc:
        raise ValueError(f"{field_name} must contain row indices") from exc
    if any(
        not isinstance(index, (int, np.integer))
        or isinstance(index, (bool, np.bool_))
        or not 0 <= index < n_rows
        for index in indices
    ):
        raise ValueError(f"{field_name} contains a row index out of range")
    normalized = tuple(int(index) for index in indices)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} must not contain duplicate row indices")
    return normalized


def _rank_in_candidates(
    scores: np.ndarray,
    row_index: int,
    candidate_row_indices: tuple[int, ...],
) -> int:
    ordered = sorted(
        candidate_row_indices,
        key=lambda index: (-float(scores[index]), index),
    )
    if row_index not in ordered:
        raise ValueError("anchor row is absent from its daily candidate reference")
    return ordered.index(row_index) + 1


def build_decision_trace(
    reference: FrozenRankReference,
    row_index: int,
    baseline_candidate_row_indices: tuple[int, ...],
    hybrid_candidate_row_indices: tuple[int, ...],
    daily_budget: int,
) -> dict[str, object]:
    """Serialize the frozen global scores and arm-specific daily ranks."""
    n_rows = len(reference.event_ids)
    if (
        not isinstance(row_index, (int, np.integer))
        or isinstance(row_index, (bool, np.bool_))
        or not 0 <= row_index < n_rows
    ):
        raise ValueError("row_index is out of range for the rank reference")
    row_index = int(row_index)
    if (
        not isinstance(daily_budget, (int, np.integer))
        or isinstance(daily_budget, (bool, np.bool_))
        or daily_budget <= 0
    ):
        raise ValueError("daily_budget must be positive")
    baseline_candidates = _validated_candidate_indices(
        baseline_candidate_row_indices,
        field_name="baseline_candidate_row_indices",
        n_rows=n_rows,
    )
    hybrid_candidates = _validated_candidate_indices(
        hybrid_candidate_row_indices,
        field_name="hybrid_candidate_row_indices",
        n_rows=n_rows,
    )

    baseline_rank = _rank_in_candidates(
        reference.baseline_selection_score, row_index, baseline_candidates
    )
    gnn_rank = _rank_in_candidates(
        reference.seed0_gnn_selection_score, row_index, hybrid_candidates
    )
    hybrid_rank = _rank_in_candidates(
        reference.seed0_hybrid_selection_score, row_index, hybrid_candidates
    )
    return {
        "percentile_reference_id": reference.percentile_reference_id,
        "baseline_daily_reference_id": _ordered_id_hash(
            reference.event_ids[index] for index in baseline_candidates
        ),
        "hybrid_daily_reference_id": _ordered_id_hash(
            reference.event_ids[index] for index in hybrid_candidates
        ),
        "daily_budget": int(daily_budget),
        "baseline_raw": float(reference.baseline_raw[row_index]),
        "baseline_percentile": float(reference.baseline_percentile[row_index]),
        "baseline_weighted_term": float(
            (1.0 - reference.blend_weight)
            * reference.baseline_percentile[row_index]
        ),
        "baseline_rank": baseline_rank,
        "seed0_gnn_probability": float(reference.seed0_gnn_raw[row_index]),
        "seed0_gnn_percentile": float(reference.seed0_gnn_percentile[row_index]),
        "seed0_gnn_weighted_term": float(
            reference.blend_weight * reference.seed0_gnn_percentile[row_index]
        ),
        "seed0_gnn_rank": gnn_rank,
        "seed0_hybrid_score": float(reference.seed0_hybrid_score[row_index]),
        "seed0_hybrid_rank": hybrid_rank,
    }


def representative_attempt_order(cases) -> list[HybridOnlyCase]:
    """Return deterministic category/period round-robin attempt order."""
    ranked = sorted(
        cases,
        key=lambda case: (
            -case.hybrid_rank_uplift,
            -case.gnn_percentile_uplift,
            case.person_id,
        ),
    )
    queues: defaultdict[tuple[str, str], deque[HybridOnlyCase]] = defaultdict(deque)
    for case in ranked:
        categories = sorted(set(case.relationship_categories) or {"NONE"})
        for category in categories:
            queues[(category, case.scoring_period)].append(case)

    selected: set[str] = set()
    ordered: list[HybridOnlyCase] = []
    while any(queues.values()):
        progressed = False
        for key in sorted(queues):
            queue = queues[key]
            while queue and queue[0].person_id in selected:
                queue.popleft()
            if queue:
                case = queue.popleft()
                selected.add(case.person_id)
                ordered.append(case)
                progressed = True
        if not progressed:
            break
    return ordered


def simulate_recovery_run(
    pool: pd.DataFrame,
    scores,
    *,
    arm: str,
    daily_budget: int,
    official_caught_times: Mapping[str, object],
) -> RecoveryRun:
    """Simulate one arm using strict day-start eligibility semantics."""
    required_columns = ("event_id", "primary_person_id", "t", "hidden")
    missing = [column for column in required_columns if column not in pool.columns]
    if missing:
        raise ValueError(f"pool missing required columns: {', '.join(missing)}")
    if not isinstance(daily_budget, (int, np.integer)) or isinstance(
        daily_budget, (bool, np.bool_)
    ) or daily_budget <= 0:
        raise ValueError("daily_budget must be positive")

    try:
        score_values = np.asarray(scores, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("scores must be numeric and one-dimensional") from exc
    if score_values.ndim != 1 or len(score_values) != len(pool):
        raise ValueError(f"scores must have length {len(pool)} and be one-dimensional")
    if not np.isfinite(score_values).all():
        raise ValueError("scores must be finite")

    rows = pool.reset_index(drop=True).copy()
    rows["_row_index"] = np.arange(len(rows), dtype=int)
    rows["_score"] = score_values
    rows["_event_id"] = _validated_identifier_values(rows["event_id"], "event_id")
    rows["_person_id"] = _validated_identifier_values(
        rows["primary_person_id"], "primary_person_id"
    )
    rows["_hidden"] = _normalized_hidden_values(rows["hidden"])
    parsed_times = pd.to_datetime(rows["t"], utc=True, errors="coerce")
    if parsed_times.isna().any():
        raise ValueError("pool contains invalid timestamps")
    rows["_scoring_day"] = parsed_times.dt.floor("D")

    official_times: dict[str, pd.Timestamp] = {}
    for person_id, caught_time in official_caught_times.items():
        parsed = pd.to_datetime(caught_time, utc=True, errors="coerce")
        if not pd.isna(parsed):
            official_times[str(person_id)] = parsed

    recovered: set[str] = set()
    anchors: dict[str, RecoveryAnchor] = {}
    traces: dict[pd.Timestamp, DailyPoolTrace] = {}

    for scoring_day in sorted(rows["_scoring_day"].unique()):
        scoring_day = pd.Timestamp(scoring_day)
        day_rows = rows.loc[rows["_scoring_day"] == scoring_day]
        eligible = day_rows.loc[
            ~day_rows["_person_id"].isin(recovered)
            & day_rows["_person_id"].map(
                lambda person_id: not (
                    person_id in official_times
                    and official_times[person_id] < scoring_day
                )
            )
        ]
        ranked = eligible.sort_values(
            ["_score", "_row_index"],
            ascending=[False, True],
            kind="mergesort",
        )
        candidate_indices = tuple(int(value) for value in ranked["_row_index"])
        inspected = ranked.iloc[: int(daily_budget)]
        inspected_indices = tuple(int(value) for value in inspected["_row_index"])

        recovered_today: set[str] = set()
        inspected_values = inspected[
            ["_person_id", "_event_id", "_row_index", "_hidden"]
        ].itertuples(index=False, name=None)
        for inspected_rank, row in enumerate(inspected_values, start=1):
            person_id, event_id, row_index, hidden = row
            if not hidden or person_id in recovered_today:
                continue
            anchors[person_id] = RecoveryAnchor(
                person_id=person_id,
                event_id=event_id,
                row_index=int(row_index),
                scoring_day=scoring_day,
                inspected_rank=inspected_rank,
            )
            recovered_today.add(person_id)

        traces[scoring_day] = DailyPoolTrace(
            scoring_day=scoring_day,
            candidate_row_indices=candidate_indices,
            inspected_row_indices=inspected_indices,
        )
        recovered.update(recovered_today)

    return RecoveryRun(
        arm=arm,
        daily_budget=int(daily_budget),
        recovered_ids=frozenset(recovered),
        first_recovery=MappingProxyType(anchors),
        days=MappingProxyType(traces),
    )


def recovery_overlap(baseline: RecoveryRun, hybrid: RecoveryRun) -> RecoveryOverlap:
    """Return exact baseline/hybrid recovery sets for equal-budget runs."""
    if baseline.daily_budget != hybrid.daily_budget:
        raise ValueError("recovery overlap requires equal daily_budget values")

    baseline_ids = frozenset(baseline.recovered_ids)
    hybrid_ids = frozenset(hybrid.recovered_ids)
    return RecoveryOverlap(
        baseline_ids=baseline_ids,
        hybrid_ids=hybrid_ids,
        both_ids=baseline_ids & hybrid_ids,
        hybrid_only_ids=hybrid_ids - baseline_ids,
        baseline_only_ids=baseline_ids - hybrid_ids,
    )
