"""Pure recovery-set accounting for daily operational inspections."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

import numpy as np
import pandas as pd


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
