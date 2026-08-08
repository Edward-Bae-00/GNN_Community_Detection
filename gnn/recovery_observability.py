"""Pure recovery-set accounting for daily operational inspections."""

from __future__ import annotations

import hashlib
from collections import defaultdict, deque
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Callable, Mapping

import numpy as np
import pandas as pd
from scipy.stats import rankdata


_SAFE_SUBJECT_DISPLAY_FIELDS = frozenset(
    {
        "display_name",
        "region",
        "age_band",
        "vehicle_type",
        "document_type",
        "residence_region",
    }
)


@dataclass(frozen=True)
class RecoveryAnchor:
    """One baseline-missed person selected for recovery analysis."""

    person_id: str
    event_id: str
    row_index: int
    scoring_day: pd.Timestamp
    inspected_rank: int


@dataclass(frozen=True)
class DailyPoolTrace:
    """Frozen daily candidate-pool and ranking provenance."""

    scoring_day: pd.Timestamp
    candidate_row_indices: tuple[int, ...]
    inspected_row_indices: tuple[int, ...]


@dataclass(frozen=True)
class RecoveryRun:
    """Complete baseline-versus-hybrid recovery output for one evaluation run."""

    arm: str
    daily_budget: int
    recovered_ids: frozenset[str]
    first_recovery: Mapping[str, RecoveryAnchor]
    days: Mapping[pd.Timestamp, DailyPoolTrace]
    run_identity: str | None = None
    as_of_identity: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.daily_budget, (int, np.integer))
            or isinstance(self.daily_budget, (bool, np.bool_))
            or self.daily_budget <= 0
        ):
            raise ValueError("daily_budget must be positive")
        object.__setattr__(self, "daily_budget", int(self.daily_budget))
        object.__setattr__(self, "recovered_ids", frozenset(self.recovered_ids))
        object.__setattr__(
            self, "first_recovery", MappingProxyType(dict(self.first_recovery))
        )
        object.__setattr__(self, "days", MappingProxyType(dict(self.days)))
        if self.run_identity is not None:
            _validate_nonblank_text(self.run_identity, "run_identity")
        if self.as_of_identity is not None:
            _validate_nonblank_text(self.as_of_identity, "as_of_identity")


@dataclass(frozen=True)
class RecoveryOverlap:
    """Overlap counts between baseline and hybrid recovery sets."""

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
    """Immutable rank and score reference for one candidate."""

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
    """A hidden carrier recovered by Hybrid but missed by the baseline."""

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


@dataclass(frozen=True)
class RecoveryCase:
    """Immutable artifact metadata for one recovered subject.

    This is intentionally not a ``HybridOnlyCase`` replacement for
    ``compose_case_explanation``. The producer must retain the legacy
    ``HybridOnlyCase`` with its candidate-row and decision-trace fields for
    the technical GNNExplainer path; this record is for selection and output
    metadata.
    """

    case_id: str
    recovery_cohort: str
    anchor_event: RecoveryAnchor
    subject_id: str
    subject_display: Mapping[str, object]
    baseline_raw: float
    baseline_percentile: float
    baseline_rank: int
    seed0_gnn_probability: float
    seed0_gnn_percentile: float
    seed0_gnn_rank: int
    seed0_hybrid_score: float
    seed0_hybrid_rank: int
    recovery_anchor_arm: str | None = None
    hybrid_blend_weight: float | None = None
    hybrid_score_kind: str = "percentile_fusion"
    relationship_categories: tuple[str, ...] = ()
    scoring_period: str = ""

    def __post_init__(self) -> None:
        _validate_nonblank_text(self.case_id, "case_id")
        _validate_nonblank_text(self.subject_id, "subject_id")
        if self.recovery_cohort not in {
            "hybrid_only",
            "baseline_only",
            "recovered_by_both",
        }:
            raise ValueError("recovery_cohort is invalid")
        if not isinstance(self.anchor_event, RecoveryAnchor):
            raise ValueError("anchor_event must be a RecoveryAnchor")
        if self.anchor_event.person_id != self.subject_id:
            raise ValueError("anchor_event person_id must match subject_id")

        expected_arm = {
            "hybrid_only": "hybrid",
            "baseline_only": "baseline",
        }.get(self.recovery_cohort)
        if self.recovery_anchor_arm is None:
            if expected_arm is not None:
                object.__setattr__(self, "recovery_anchor_arm", expected_arm)
            elif self.recovery_cohort == "recovered_by_both":
                raise ValueError(
                    "recovered_by_both requires recovery_anchor_arm"
                )
        elif self.recovery_anchor_arm not in {
            "baseline",
            "hybrid",
            "hybrid_seed0",
        }:
            raise ValueError("recovery_anchor_arm is invalid")
        if expected_arm is not None and not self.recovery_anchor_arm.startswith(
            expected_arm
        ):
            raise ValueError("recovery_anchor_arm does not match recovery_cohort")

        if not isinstance(self.subject_display, Mapping):
            raise ValueError("subject_display must be a mapping")
        display_keys = tuple(self.subject_display)
        invalid_display_keys = [
            key
            for key in display_keys
            if not isinstance(key, str) or key not in _SAFE_SUBJECT_DISPLAY_FIELDS
        ]
        if invalid_display_keys:
            raise ValueError(
                "subject_display field is not allowlisted: "
                f"{invalid_display_keys[0]!r}"
            )
        invalid_display_values = [
            key
            for key, value in self.subject_display.items()
            if value is not None
            and not isinstance(value, (str, int, float, bool))
        ]
        if invalid_display_values:
            raise ValueError(
                "subject_display values must be scalar: "
                f"{invalid_display_values[0]!r}"
            )
        object.__setattr__(
            self, "subject_display", _freeze_json_like(self.subject_display)
        )
        _validate_finite_score(self.baseline_raw, "baseline_raw")
        _validate_percentile(self.baseline_percentile, "baseline_percentile")
        _validate_positive_rank(self.baseline_rank, "baseline_rank")
        _validate_probability(
            self.seed0_gnn_probability, "seed0_gnn_probability"
        )
        _validate_percentile(self.seed0_gnn_percentile, "seed0_gnn_percentile")
        _validate_positive_rank(self.seed0_gnn_rank, "seed0_gnn_rank")
        _validate_percentile(self.seed0_hybrid_score, "seed0_hybrid_score")
        _validate_positive_rank(self.seed0_hybrid_rank, "seed0_hybrid_rank")

        for field_name in (
            "baseline_raw",
            "baseline_percentile",
            "seed0_gnn_probability",
            "seed0_gnn_percentile",
            "seed0_hybrid_score",
        ):
            object.__setattr__(self, field_name, float(getattr(self, field_name)))
        for field_name in (
            "baseline_rank",
            "seed0_gnn_rank",
            "seed0_hybrid_rank",
        ):
            object.__setattr__(self, field_name, int(getattr(self, field_name)))

        if self.hybrid_score_kind != "percentile_fusion":
            raise ValueError("hybrid_score_kind must be percentile_fusion")
        if self.hybrid_blend_weight is None:
            raise ValueError(
                "percentile_fusion requires hybrid_blend_weight"
            )
        weight = _validated_blend_weight(self.hybrid_blend_weight)
        expected_hybrid_score = (
            (1.0 - weight) * float(self.baseline_percentile)
            + weight * float(self.seed0_gnn_percentile)
        )
        if not np.isclose(
            float(self.seed0_hybrid_score),
            expected_hybrid_score,
            rtol=0.0,
            atol=1e-12,
        ):
            raise ValueError("seed0_hybrid_score does not match percentile fusion")
        object.__setattr__(self, "hybrid_blend_weight", weight)

        if isinstance(self.relationship_categories, str):
            raise ValueError("relationship_categories must be a collection")
        categories = tuple(self.relationship_categories)
        if any(
            not isinstance(category, str) or not category.strip()
            for category in categories
        ):
            raise ValueError(
                "relationship_categories must contain non-blank strings"
            )
        object.__setattr__(
            self,
            "relationship_categories",
            tuple(sorted(set(category.strip() for category in categories))),
        )
        if not isinstance(self.scoring_period, str):
            raise ValueError("scoring_period must be a string")
        object.__setattr__(self, "scoring_period", self.scoring_period.strip())

    @property
    def cohort(self) -> str:
        """Compatibility alias for callers that use the shorter cohort name."""
        return self.recovery_cohort

    @property
    def arm(self) -> str | None:
        """Compatibility alias for the arm that supplied the recovery anchor."""
        return self.recovery_anchor_arm

    @property
    def recovery_arm(self) -> str | None:
        return self.recovery_anchor_arm

    @property
    def anchor(self) -> RecoveryAnchor:
        """Compatibility alias matching the existing recovery case types."""
        return self.anchor_event

    @property
    def person_id(self) -> str:
        return self.subject_id

    @property
    def subject_display_fields(self) -> Mapping[str, object]:
        return self.subject_display

    @property
    def baseline_raw_score(self) -> float:
        return self.baseline_raw

    @property
    def gnn_probability(self) -> float:
        return self.seed0_gnn_probability

    @property
    def gnn_percentile(self) -> float:
        return self.seed0_gnn_percentile

    @property
    def gnn_rank(self) -> int:
        return self.seed0_gnn_rank

    @property
    def hybrid_score(self) -> float:
        return self.seed0_hybrid_score

    @property
    def hybrid_rank(self) -> int:
        return self.seed0_hybrid_rank

    @property
    def hybrid_rank_uplift(self) -> int:
        return self.baseline_rank - self.seed0_hybrid_rank

    @property
    def gnn_percentile_uplift(self) -> float:
        return self.seed0_gnn_percentile - self.baseline_percentile

    @property
    def normalized_relationship_signature(self) -> tuple[str, ...]:
        return self.relationship_categories or ("NONE",)


@dataclass(frozen=True)
class FrozenRecoverySelection:
    """Frozen selection and explainability coverage for recovery cases."""

    selected_ids: Mapping[str, tuple[str, ...]]
    selected_cases: Mapping[str, tuple[RecoveryCase, ...]]
    published_ids: Mapping[str, tuple[str, ...]]
    counts: Mapping[str, int]
    status: Mapping[str, str]
    aggregate_ids: tuple[str, ...] = ()
    aggregate_cases: tuple[RecoveryCase, ...] = ()
    attempted_ids: tuple[str, ...] = ()
    explained_ids: tuple[str, ...] = ()
    failed_ids: tuple[str, ...] = ()
    failures: tuple[Mapping[str, object], ...] = ()
    detail_status: Mapping[str, str] = field(default_factory=dict)
    policy_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("selected_ids", "selected_cases", "published_ids"):
            value = getattr(self, field_name)
            if not isinstance(value, Mapping):
                raise ValueError(f"{field_name} must be a mapping")
            object.__setattr__(
                self,
                field_name,
                MappingProxyType({key: tuple(items) for key, items in value.items()}),
            )
        for field_name in ("counts", "status"):
            value = getattr(self, field_name)
            if not isinstance(value, Mapping):
                raise ValueError(f"{field_name} must be a mapping")
            object.__setattr__(self, field_name, MappingProxyType(dict(value)))
        for field_name in ("attempted_ids", "explained_ids", "failed_ids"):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        object.__setattr__(self, "aggregate_ids", tuple(self.aggregate_ids))
        object.__setattr__(self, "aggregate_cases", tuple(self.aggregate_cases))
        for field_name in ("detail_status",):
            value = getattr(self, field_name)
            if not isinstance(value, Mapping):
                raise ValueError(f"{field_name} must be a mapping")
            object.__setattr__(self, field_name, MappingProxyType(dict(value)))
        object.__setattr__(
            self,
            "policy_metadata",
            _freeze_json_like(self.policy_metadata),
        )
        object.__setattr__(
            self,
            "failures",
            tuple(_freeze_json_like(failure) for failure in self.failures),
        )

        cohorts = ("hybrid_only", "baseline_only", "recovered_by_both")
        for field_name in ("selected_ids", "selected_cases", "published_ids"):
            keys = set(getattr(self, field_name))
            if keys != set(cohorts):
                raise ValueError(f"{field_name} must contain exactly the recovery cohorts")

        selected_case_ids: set[str] = set()
        selected_ids_by_cohort: dict[str, set[str]] = {}
        for cohort in cohorts:
            cases = self.selected_cases[cohort]
            case_ids = tuple(case.case_id for case in cases)
            if any(
                not isinstance(case, RecoveryCase) or case.recovery_cohort != cohort
                for case in cases
            ):
                raise ValueError("selected_cases cases must map to their cohort")
            if self.selected_ids[cohort] != case_ids:
                raise ValueError("selected_ids do not match selected_cases")
            if len(set(case_ids)) != len(case_ids):
                raise ValueError("selected_cases contains duplicate case IDs")
            selected_ids_by_cohort[cohort] = set(case_ids)
            selected_case_ids.update(case_ids)
        if selected_ids_by_cohort["recovered_by_both"]:
            raise ValueError("selected recovered_by_both cases must be summary-only")

        aggregate_case_ids = tuple(case.case_id for case in self.aggregate_cases)
        if self.aggregate_ids != aggregate_case_ids:
            raise ValueError("aggregate_ids do not match aggregate_cases")
        if any(
            not isinstance(case, RecoveryCase)
            or case.recovery_cohort != "recovered_by_both"
            for case in self.aggregate_cases
        ):
            raise ValueError("aggregate cases must have recovered_by_both cohort")
        if len(set(aggregate_case_ids)) != len(aggregate_case_ids):
            raise ValueError("aggregate_cases contains duplicate case IDs")
        aggregate_ids_set = set(aggregate_case_ids)
        all_cases = [
            case
            for cohort in cohorts
            for case in self.selected_cases[cohort]
        ] + list(self.aggregate_cases)
        all_case_ids = [case.case_id for case in all_cases]
        if len(set(all_case_ids)) != len(all_case_ids):
            raise ValueError("case IDs must be globally unique across selection")
        if aggregate_ids_set & selected_case_ids:
            raise ValueError("case IDs must be globally unique across selection")
        subjects_by_id: dict[str, str] = {}
        for case in all_cases:
            prior_case_id = subjects_by_id.get(case.subject_id)
            if prior_case_id is not None:
                raise ValueError(
                    "subject IDs must be globally disjoint across selection: "
                    f"{case.subject_id!r} appears in {prior_case_id!r} and {case.case_id!r}"
                )
            subjects_by_id[case.subject_id] = case.case_id

        published_ids_set: set[str] = set()
        for cohort in cohorts:
            ids = self.published_ids[cohort]
            if len(set(ids)) != len(ids):
                raise ValueError("published_ids contains duplicate case IDs")
            if not set(ids).issubset(selected_ids_by_cohort[cohort]):
                raise ValueError("published IDs must be selected IDs in their cohort")
            if cohort == "recovered_by_both" and ids:
                raise ValueError("recovered_by_both cannot have published detail IDs")
            published_ids_set.update(ids)
        if published_ids_set & aggregate_ids_set:
            raise ValueError("published IDs must not include aggregate IDs")

        selected_fields = {
            "attempted_ids": self.attempted_ids,
            "explained_ids": self.explained_ids,
            "failed_ids": self.failed_ids,
            "detail_status": tuple(self.detail_status),
        }
        for field_name, ids in selected_fields.items():
            if len(set(ids)) != len(ids):
                raise ValueError(f"{field_name} contains duplicate IDs")
            if not set(ids).issubset(selected_case_ids):
                raise ValueError(f"{field_name} must contain selected IDs only")
            if set(ids) & aggregate_ids_set:
                raise ValueError(f"{field_name} must not contain aggregate IDs")
        if set(self.explained_ids) & set(self.failed_ids):
            raise ValueError("explained_ids and failed_ids must be disjoint")
        if set(self.detail_status) != selected_case_ids:
            raise ValueError("detail_status must cover selected IDs only")
        allowed_detail_states = {
            "selected",
            "not_confirmed",
            "generated",
            "failed",
            "community_only",
            "technical_available",
        }
        if any(state not in allowed_detail_states for state in self.detail_status.values()):
            raise ValueError("detail_status contains an invalid publication state")
        published_hybrid_ids = set(self.published_ids["hybrid_only"])
        published_baseline_ids = set(self.published_ids["baseline_only"])
        failed_id_set = set(self.failed_ids)
        for case_id, state in self.detail_status.items():
            if state == "technical_available" and case_id not in published_hybrid_ids:
                raise ValueError(
                    "technical_available detail status requires a published hybrid ID"
                )
            if state == "community_only" and case_id not in published_baseline_ids:
                raise ValueError(
                    "community_only detail status requires a published baseline ID"
                )
            if state == "failed" and case_id not in failed_id_set:
                raise ValueError("failed detail status requires a failed ID")
        for case_id in self.published_ids["hybrid_only"]:
            if self.detail_status[case_id] != "technical_available":
                raise ValueError(
                    "published hybrid IDs require technical_available detail status"
                )
        for case_id in self.published_ids["baseline_only"]:
            if self.detail_status[case_id] != "community_only":
                raise ValueError(
                    "published baseline IDs require community_only detail status"
                )
        for case_id in self.failed_ids:
            if self.detail_status[case_id] != "failed":
                raise ValueError("failed IDs require failed detail status")

        failure_ids: list[str] = []
        for failure in self.failures:
            if not isinstance(failure, Mapping) or "case_id" not in failure:
                raise ValueError("failure records require case_id")
            failure_ids.append(str(failure["case_id"]))
        if len(set(failure_ids)) != len(failure_ids):
            raise ValueError("duplicate failure records are not allowed")
        if set(failure_ids) != set(self.failed_ids):
            raise ValueError("failed_ids must match failure record IDs")
        if not set(failure_ids).issubset(selected_case_ids):
            raise ValueError("failure records must contain selected IDs only")
        if published_ids_set & set(failure_ids):
            raise ValueError("published IDs must not include failed IDs")

        expected_counts = {
            "selected_hybrid_only": len(self.selected_ids["hybrid_only"]),
            "selected_baseline_only": len(self.selected_ids["baseline_only"]),
            "selected_recovered_by_both": 0,
            "attempted": len(self.attempted_ids),
            "explained": len(self.explained_ids),
            "failed": len(self.failed_ids),
            "published_hybrid_only": len(self.published_ids["hybrid_only"]),
            "published_baseline_only": len(self.published_ids["baseline_only"]),
            "published_recovered_by_both": 0,
            "published_count": len(published_ids_set),
        }
        if "aggregate_recovered_by_both" in self.counts:
            expected_counts["aggregate_recovered_by_both"] = len(aggregate_case_ids)
        if "publication_failures" in self.counts:
            expected_counts["publication_failures"] = len(self.failures)
        for field_name, expected in expected_counts.items():
            if self.counts.get(field_name) != expected:
                raise ValueError(f"counts[{field_name!r}] is inconsistent")

    def policy_jsonable(self) -> dict[str, object]:
        """Return detached JSON-safe policy metadata."""
        return _thaw_json_like(self.policy_metadata)

    @property
    def policy(self) -> dict[str, object]:
        """Compatibility alias returning JSON-safe policy metadata."""
        return self.policy_jsonable()


def recovery_case_explainer_boundary() -> dict[str, str]:
    """Document the metadata/technical-explainer boundary for producers."""
    return {
        "artifact_case": "RecoveryCase",
        "technical_explainer_case": "HybridOnlyCase",
        "producer_requirement": (
            "retain HybridOnlyCase candidate-row and decision-trace fields "
            "for compose_case_explanation"
        ),
    }


def _validate_nonblank_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-blank")


def _validate_finite_score(value: object, field_name: str) -> None:
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{field_name} must be finite")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be finite") from exc
    if not np.isfinite(numeric):
        raise ValueError(f"{field_name} must be finite")


def _validate_probability(value: object, field_name: str) -> None:
    _validate_percentile(value, field_name)


def _validate_percentile(value: object, field_name: str) -> None:
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{field_name} must be between 0 and 1")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be between 0 and 1") from exc
    if not np.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1")


def _validate_positive_rank(value: object, field_name: str) -> None:
    if (
        not isinstance(value, (int, np.integer))
        or isinstance(value, (bool, np.bool_))
        or value <= 0
    ):
        raise ValueError(f"{field_name} must be a positive integer")


def build_recovery_case(
    *,
    case_id: str,
    recovery_cohort: str,
    anchor_event: RecoveryAnchor,
    subject_id: str,
    subject_display: Mapping[str, object],
    decision_trace: Mapping[str, object],
    recovery_anchor_arm: str | None = None,
    hybrid_blend_weight: float | None = None,
    hybrid_score_kind: str = "percentile_fusion",
    relationship_categories: tuple[str, ...] = (),
    scoring_period: str = "",
) -> RecoveryCase:
    """Build a display case from the already-frozen decision trace."""
    if not isinstance(decision_trace, Mapping):
        raise ValueError("decision_trace must be a mapping")
    fields = (
        "baseline_raw",
        "baseline_percentile",
        "baseline_rank",
        "seed0_gnn_probability",
        "seed0_gnn_percentile",
        "seed0_gnn_rank",
        "seed0_hybrid_score",
        "seed0_hybrid_rank",
    )
    missing = [field_name for field_name in fields if field_name not in decision_trace]
    if missing:
        raise ValueError(f"decision_trace missing fields: {', '.join(missing)}")
    return RecoveryCase(
        case_id=case_id,
        recovery_cohort=recovery_cohort,
        recovery_anchor_arm=recovery_anchor_arm,
        hybrid_blend_weight=hybrid_blend_weight,
        hybrid_score_kind=hybrid_score_kind,
        relationship_categories=relationship_categories,
        scoring_period=scoring_period,
        anchor_event=anchor_event,
        subject_id=subject_id,
        subject_display=subject_display,
        baseline_raw=decision_trace["baseline_raw"],
        baseline_percentile=decision_trace["baseline_percentile"],
        baseline_rank=decision_trace["baseline_rank"],
        seed0_gnn_probability=decision_trace["seed0_gnn_probability"],
        seed0_gnn_percentile=decision_trace["seed0_gnn_percentile"],
        seed0_gnn_rank=decision_trace["seed0_gnn_rank"],
        seed0_hybrid_score=decision_trace["seed0_hybrid_score"],
        seed0_hybrid_rank=decision_trace["seed0_hybrid_rank"],
    )


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
    run_identity: str | None = None,
    as_of_identity: str | None = None,
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
        run_identity=run_identity,
        as_of_identity=as_of_identity,
    )


def recovery_overlap(
    baseline: RecoveryRun,
    hybrid: RecoveryRun,
    *,
    strict: bool = False,
) -> RecoveryOverlap:
    """Return exact recovery sets.

    The default preserves legacy equal-budget-only callers. ``strict=True``
    additionally validates normalized arm names and shared run/as-of
    provenance identities for producer-facing comparisons.
    """
    if not isinstance(strict, bool):
        raise ValueError("strict must be a boolean")
    if baseline.daily_budget != hybrid.daily_budget:
        raise ValueError("recovery overlap requires equal daily_budget values")
    if strict:
        _validate_strict_recovery_pair(baseline, hybrid)

    baseline_ids = frozenset(baseline.recovered_ids)
    hybrid_ids = frozenset(hybrid.recovered_ids)
    return RecoveryOverlap(
        baseline_ids=baseline_ids,
        hybrid_ids=hybrid_ids,
        both_ids=baseline_ids & hybrid_ids,
        hybrid_only_ids=hybrid_ids - baseline_ids,
        baseline_only_ids=baseline_ids - hybrid_ids,
    )


def partition_recovery_cohorts(
    baseline_ids, hybrid_ids
) -> RecoveryOverlap:
    """Partition two recovery ID sets into the three disjoint cohorts."""
    baseline = frozenset(baseline_ids)
    hybrid = frozenset(hybrid_ids)
    return RecoveryOverlap(
        baseline_ids=baseline,
        hybrid_ids=hybrid,
        both_ids=baseline & hybrid,
        hybrid_only_ids=hybrid - baseline,
        baseline_only_ids=baseline - hybrid,
    )


def recovery_cohort_counts(overlap: RecoveryOverlap) -> dict[str, int]:
    """Return pure count algebra for an exact recovery partition."""
    if not isinstance(overlap, RecoveryOverlap):
        raise ValueError("overlap must be a RecoveryOverlap")
    return {
        "baseline_recovered": len(overlap.baseline_ids),
        "recovered_by_both": len(overlap.both_ids),
        "hybrid_only_recovered": len(overlap.hybrid_only_ids),
        "baseline_only_recovered": len(overlap.baseline_only_ids),
        "hybrid_total": len(overlap.hybrid_ids),
        "net_gain": len(overlap.hybrid_ids) - len(overlap.baseline_ids),
    }


def _normalized_recovery_arm(arm: str) -> str:
    if arm == "baseline":
        return "baseline"
    if arm in {"hybrid", "hybrid_seed0"}:
        return "hybrid"
    raise ValueError(f"unsupported recovery arm: {arm!r}")


def _validate_strict_recovery_pair(
    baseline: RecoveryRun, hybrid: RecoveryRun
) -> None:
    if not isinstance(baseline, RecoveryRun) or not isinstance(hybrid, RecoveryRun):
        raise ValueError("strict recovery overlap requires RecoveryRun values")
    if _normalized_recovery_arm(baseline.arm) != "baseline":
        raise ValueError("baseline arm must normalize to baseline")
    if _normalized_recovery_arm(hybrid.arm) != "hybrid":
        raise ValueError("hybrid arm must normalize to hybrid or hybrid_seed0")
    if baseline.daily_budget != hybrid.daily_budget:
        raise ValueError("recovery overlap requires equal daily_budget values")
    if not baseline.run_identity or not hybrid.run_identity:
        raise ValueError("strict recovery overlap requires run_identity")
    if baseline.run_identity != hybrid.run_identity:
        raise ValueError("strict recovery overlap requires equal run_identity")
    if not baseline.as_of_identity or not hybrid.as_of_identity:
        raise ValueError("strict recovery overlap requires as_of_identity")
    if baseline.as_of_identity != hybrid.as_of_identity:
        raise ValueError("strict recovery overlap requires equal as_of_identity")


def _anchor_order_key(anchor: RecoveryAnchor, arm: str):
    return (
        pd.Timestamp(anchor.scoring_day).value,
        int(anchor.inspected_rank),
        anchor.event_id,
        int(anchor.row_index),
        arm,
    )


def choose_earliest_recovery_anchor(
    baseline_anchor: RecoveryAnchor | None,
    hybrid_anchor: RecoveryAnchor | None,
) -> tuple[RecoveryAnchor, str]:
    """Choose one subject's earliest arm anchor with deterministic tie-breaks."""
    candidates: list[tuple[RecoveryAnchor, str]] = []
    if baseline_anchor is not None:
        candidates.append((baseline_anchor, "baseline"))
    if hybrid_anchor is not None:
        candidates.append((hybrid_anchor, "hybrid"))
    if not candidates:
        raise ValueError("at least one recovery anchor is required")
    subject_ids = {anchor.person_id for anchor, _ in candidates}
    if len(subject_ids) != 1:
        raise ValueError("baseline and hybrid anchors must belong to one subject")
    return min(candidates, key=lambda item: _anchor_order_key(*item))


def materialize_recovered_by_both_case(
    baseline_case: RecoveryCase,
    hybrid_case: RecoveryCase,
    *,
    case_id: str | None = None,
) -> RecoveryCase:
    """Materialize one overlap case from the subject's two arm cases."""
    if not isinstance(baseline_case, RecoveryCase) or not isinstance(
        hybrid_case, RecoveryCase
    ):
        raise ValueError("both materialization requires two RecoveryCase values")
    if baseline_case.subject_id != hybrid_case.subject_id:
        raise ValueError("both materialization requires one subject")
    if baseline_case.recovery_cohort != "baseline_only":
        raise ValueError("baseline_case must be baseline_only")
    if hybrid_case.recovery_cohort != "hybrid_only":
        raise ValueError("hybrid_case must be hybrid_only")
    anchor, anchor_arm = choose_earliest_recovery_anchor(
        baseline_case.anchor_event,
        hybrid_case.anchor_event,
    )
    source_case = baseline_case if anchor_arm == "baseline" else hybrid_case
    return replace(
        source_case,
        case_id=case_id or f"case:{source_case.subject_id}",
        recovery_cohort="recovered_by_both",
        recovery_anchor_arm=anchor_arm,
        anchor_event=anchor,
    )


def _validate_selection_limit(value: object, field_name: str) -> int:
    if (
        not isinstance(value, (int, np.integer))
        or isinstance(value, (bool, np.bool_))
        or value < 0
    ):
        raise ValueError(f"{field_name} must be a non-negative integer")
    return int(value)


def _balanced_bucket(case: RecoveryCase) -> tuple[tuple[str, ...], str]:
    return (case.normalized_relationship_signature, case.scoring_period)


def _round_robin_balanced_cases(
    cases: list[RecoveryCase], *, hybrid: bool
) -> list[RecoveryCase]:
    if hybrid:
        ranked = sorted(
            cases,
            key=lambda case: (
                -case.hybrid_rank_uplift,
                -case.gnn_percentile_uplift,
                case.normalized_relationship_signature,
                case.scoring_period,
                case.subject_id,
            ),
        )
    else:
        ranked = sorted(
            cases,
            key=lambda case: (
                -(case.seed0_hybrid_rank - case.baseline_rank),
                case.normalized_relationship_signature,
                case.scoring_period,
                case.subject_id,
            ),
        )
    queues: defaultdict[tuple[tuple[str, ...], str], deque[RecoveryCase]] = (
        defaultdict(deque)
    )
    for case in ranked:
        queues[_balanced_bucket(case)].append(case)

    def bucket_order_key(bucket):
        best = queues[bucket][0]
        if hybrid:
            priority = (
                -best.hybrid_rank_uplift,
                -best.gnn_percentile_uplift,
            )
        else:
            priority = (-(best.seed0_hybrid_rank - best.baseline_rank),)
        return priority + (bucket[0], bucket[1])

    bucket_order = sorted(queues, key=bucket_order_key)
    ordered: list[RecoveryCase] = []
    while any(queues.values()):
        progressed = False
        for bucket in bucket_order:
            if queues[bucket]:
                ordered.append(queues[bucket].popleft())
                progressed = True
        if not progressed:
            break
    return ordered


def _validate_balanced_inputs(
    hybrid_cases, baseline_cases
) -> tuple[list[RecoveryCase], list[RecoveryCase]]:
    seen_case_ids: set[str] = set()
    seen_subjects: dict[str, str] = {}
    normalized: list[list[RecoveryCase]] = []
    for expected_cohort, values in (
        ("hybrid_only", hybrid_cases),
        ("baseline_only", baseline_cases),
    ):
        cohort_cases: list[RecoveryCase] = []
        for case in values:
            if not isinstance(case, RecoveryCase):
                raise ValueError("balanced selector inputs must be RecoveryCase values")
            if case.recovery_cohort != expected_cohort:
                raise ValueError(
                    f"balanced selector requires {expected_cohort} cases"
                )
            if case.case_id in seen_case_ids:
                raise ValueError(f"duplicate recovery case ID: {case.case_id}")
            prior_case_id = seen_subjects.get(case.subject_id)
            if prior_case_id is not None:
                raise ValueError(
                    "balanced selector input must be subject-disjoint: "
                    f"subject {case.subject_id!r} appears in {prior_case_id!r} "
                    f"and {case.case_id!r}"
                )
            seen_case_ids.add(case.case_id)
            seen_subjects[case.subject_id] = case.case_id
            cohort_cases.append(case)
        normalized.append(cohort_cases)
    return normalized[0], normalized[1]


def select_balanced_detail_cases(
    hybrid_cases,
    baseline_cases,
    *,
    hybrid_limit: int = 20,
    baseline_limit: int = 10,
    eligible_hybrid_ids=None,
) -> FrozenRecoverySelection:
    """Select frozen balanced detail prefixes before technical explanation.

    ``eligible_hybrid_ids`` is a pre-explanation candidate filter. It does not
    refill a quota after publication or explanation failures; publication is
    performed by the later Hybrid callback path.
    """
    hybrid_limit = _validate_selection_limit(hybrid_limit, "hybrid_limit")
    baseline_limit = _validate_selection_limit(baseline_limit, "baseline_limit")
    hybrid_values, baseline_values = _validate_balanced_inputs(
        hybrid_cases, baseline_cases
    )
    if eligible_hybrid_ids is None:
        eligible_ids = {case.case_id for case in hybrid_values}
    else:
        if isinstance(eligible_hybrid_ids, str):
            raise ValueError("eligible_hybrid_ids must be a collection")
        try:
            raw_eligible_ids = tuple(eligible_hybrid_ids)
        except TypeError as exc:
            raise ValueError("eligible_hybrid_ids must be a collection") from exc
        if any(
            not isinstance(case_id, str) or not case_id.strip()
            for case_id in raw_eligible_ids
        ):
            raise ValueError(
                "eligible_hybrid_ids must contain unique non-blank strings"
            )
        if len(set(raw_eligible_ids)) != len(raw_eligible_ids):
            raise ValueError("eligible_hybrid_ids must contain unique IDs")
        candidate_ids = {case.case_id for case in hybrid_values}
        unknown_ids = set(raw_eligible_ids) - candidate_ids
        if unknown_ids:
            raise ValueError(
                "eligible_hybrid_ids contains IDs absent from hybrid candidates"
            )
        eligible_ids = set(raw_eligible_ids)
    eligible_hybrid = [
        case for case in hybrid_values if case.case_id in eligible_ids
    ]
    ordered_hybrid = _round_robin_balanced_cases(eligible_hybrid, hybrid=True)
    ordered_baseline = _round_robin_balanced_cases(baseline_values, hybrid=False)
    selected_cases = {
        "hybrid_only": tuple(ordered_hybrid[:hybrid_limit]),
        "baseline_only": tuple(ordered_baseline[:baseline_limit]),
        "recovered_by_both": (),
    }
    selected_ids = {
        cohort: tuple(case.case_id for case in cases)
        for cohort, cases in selected_cases.items()
    }
    detail_status = {
        case.case_id: "selected"
        for case in selected_cases["hybrid_only"]
    }
    detail_status.update(
        {
            case.case_id: "selected"
            for case in selected_cases["baseline_only"]
        }
    )
    policy_metadata = {
        "policy_version": "balanced_detail_v1",
        "quotas": {
            "hybrid_only": hybrid_limit,
            "baseline_only": baseline_limit,
        },
        "eligible_hybrid_ids": sorted(eligible_ids),
        "eligible_ordered_prefix": [case.case_id for case in ordered_hybrid],
        "selected_ids": {
            cohort: list(ids) for cohort, ids in selected_ids.items()
        },
        "hybrid_priority": [
            "hybrid_rank_uplift",
            "gnn_percentile_uplift",
            "relationship_signature",
            "scoring_period",
            "subject_id",
        ],
        "baseline_priority": [
            "baseline_vs_hybrid_rank_gap",
            "relationship_signature",
            "scoring_period",
            "subject_id",
        ],
        "round_robin_buckets": True,
    }
    return FrozenRecoverySelection(
        selected_ids=selected_ids,
        selected_cases=selected_cases,
        published_ids={
            "hybrid_only": (),
            "baseline_only": (),
            "recovered_by_both": (),
        },
        counts={
            "hybrid_only": len(hybrid_values),
            "eligible_hybrid": len(eligible_hybrid),
            "baseline_only": len(baseline_values),
            "selected_hybrid_only": len(selected_cases["hybrid_only"]),
            "selected_baseline_only": len(selected_cases["baseline_only"]),
            "selected_recovered_by_both": 0,
            "attempted": 0,
            "explained": 0,
            "failed": 0,
            "published_hybrid_only": 0,
            "published_baseline_only": 0,
            "published_recovered_by_both": 0,
            "published_count": 0,
        },
        status={
            "selection": "frozen",
            "explainability": "not_requested",
            "recovered_by_both": "aggregate_only",
        },
        detail_status=detail_status,
        policy_metadata=policy_metadata,
    )


def select_frozen_recovery_prefix(
    cases,
    *,
    max_hybrid: int = 20,
    max_baseline: int = 10,
    hybrid_explain_case: Callable[[RecoveryCase], object] | None = None,
) -> FrozenRecoverySelection:
    """Compatibility wrapper delegating to the balanced selector.

    This wrapper is deliberately pure: the retained ``hybrid_explain_case``
    argument is accepted for import/call compatibility but is never called.
    Technical explanation remains a producer operation over retained
    ``HybridOnlyCase`` values, followed by explicit publication finalization.
    The wrapper has no independent chronological selection policy.
    """
    if hybrid_explain_case is not None and not callable(hybrid_explain_case):
        raise ValueError("hybrid_explain_case must be callable or None")

    by_cohort: dict[str, list[RecoveryCase]] = {
        "hybrid_only": [],
        "baseline_only": [],
        "recovered_by_both": [],
    }
    seen_ids: set[str] = set()
    seen_subjects: dict[str, str] = {}
    for case in cases:
        if not isinstance(case, RecoveryCase):
            raise ValueError("cases must contain RecoveryCase values")
        if case.case_id in seen_ids:
            raise ValueError(f"duplicate recovery case ID: {case.case_id}")
        prior_case_id = seen_subjects.get(case.subject_id)
        if prior_case_id is not None:
            raise ValueError(
                "selector input must be subject-disjoint: "
                f"subject {case.subject_id!r} appears in {prior_case_id!r} "
                f"and {case.case_id!r}"
            )
        seen_ids.add(case.case_id)
        seen_subjects[case.subject_id] = case.case_id
        by_cohort[case.recovery_cohort].append(case)

    selection = select_balanced_detail_cases(
        by_cohort["hybrid_only"],
        by_cohort["baseline_only"],
        hybrid_limit=max_hybrid,
        baseline_limit=max_baseline,
    )
    aggregate_cases = tuple(by_cohort["recovered_by_both"])
    counts = dict(selection.counts)
    counts.update(
        {
            "recovered_by_both": len(aggregate_cases),
            "aggregate_recovered_by_both": len(aggregate_cases),
        }
    )
    policy_metadata = selection.policy_jsonable()
    policy_metadata["compatibility_wrapper"] = "select_frozen_recovery_prefix"
    return replace(
        selection,
        aggregate_ids=tuple(case.case_id for case in aggregate_cases),
        aggregate_cases=aggregate_cases,
        counts=counts,
        policy_metadata=policy_metadata,
    )


def finalize_recovery_publication(
    selection: FrozenRecoverySelection,
    *,
    published_ids: Mapping[str, object],
    failures=(),
) -> FrozenRecoverySelection:
    """Record explicit publication confirmation without changing selection.

    ``select_*`` functions freeze the detail prefix and do not infer
    publication from selection or from a callback that merely returned.  A
    producer calls this helper later with IDs it has explicitly confirmed as
    published.  IDs outside the frozen detail prefix, and aggregate overlap
    IDs, are rejected; no failure can trigger replacement selection.
    """
    if not isinstance(selection, FrozenRecoverySelection):
        raise ValueError("selection must be a FrozenRecoverySelection")
    if not isinstance(published_ids, Mapping):
        raise ValueError("published_ids must be a cohort mapping")

    cohorts = ("hybrid_only", "baseline_only", "recovered_by_both")
    unknown_cohorts = set(published_ids) - set(cohorts)
    if unknown_cohorts:
        raise ValueError(f"published_ids has unknown cohorts: {sorted(unknown_cohorts)!r}")

    selected_by_id: dict[str, str] = {}
    selected_order: list[str] = []
    for cohort in cohorts:
        for case_id in selection.selected_ids.get(cohort, ()):
            if case_id in selected_by_id:
                raise ValueError(f"selection contains duplicate case ID: {case_id}")
            selected_by_id[case_id] = cohort
            selected_order.append(case_id)

    prior_published = {
        cohort: set(selection.published_ids.get(cohort, ()))
        for cohort in cohorts
    }
    prior_published_ids = set().union(*prior_published.values())
    prior_failure_ids = set(selection.failed_ids)
    requested: dict[str, tuple[str, ...]] = {}
    requested_ids: set[str] = set()
    for cohort in cohorts:
        values = published_ids.get(cohort, ())
        if isinstance(values, str):
            raise ValueError("published IDs must be collections of case IDs")
        ids = tuple(str(case_id) for case_id in values)
        if len(set(ids)) != len(ids):
            raise ValueError(f"published_ids[{cohort!r}] contains duplicates")
        for case_id in ids:
            actual_cohort = selected_by_id.get(case_id)
            if actual_cohort != cohort:
                raise ValueError(
                    f"published case ID {case_id!r} is not selected in {cohort!r}"
                )
            if (
                case_id not in prior_published_ids
                and selection.detail_status.get(case_id)
                not in {"selected", "generated"}
            ):
                raise ValueError(
                    f"published case ID {case_id!r} must be selected or generated"
                )
            if case_id in prior_failure_ids:
                raise ValueError(f"failed case ID cannot be published: {case_id}")
            requested_ids.add(case_id)
        requested[cohort] = ids

    failure_records: list[Mapping[str, object]] = []
    failure_ids: set[str] = set()
    existing_failure_ids = {
        str(record["case_id"])
        for record in selection.failures
        if isinstance(record, Mapping) and "case_id" in record
    }
    for failure in failures:
        if not isinstance(failure, Mapping):
            raise ValueError("publication failures must be mappings")
        if "case_id" not in failure:
            raise ValueError("publication failure requires case_id")
        case_id = str(failure["case_id"])
        if case_id not in selected_by_id:
            raise ValueError(f"publication failure ID is not selected: {case_id}")
        if case_id in requested_ids or case_id in prior_published_ids:
            raise ValueError(f"case ID cannot be both published and failed: {case_id}")
        if case_id in failure_ids or case_id in existing_failure_ids:
            raise ValueError(f"duplicate failure record for case ID: {case_id}")
        failure_ids.add(case_id)
        failure_records.append(failure)

    published = {
        cohort: tuple(
            case_id
            for case_id in selected_order
            if case_id in prior_published[cohort]
            or case_id in requested.get(cohort, ())
        )
        for cohort in cohorts
    }
    detail_status = dict(selection.detail_status)
    for case_id in set().union(*[set(ids) for ids in published.values()]):
        detail_status[case_id] = (
            "community_only"
            if selected_by_id[case_id] == "baseline_only"
            else "technical_available"
        )
    for case_id in failure_ids:
        detail_status[case_id] = "failed"

    failed_ids = prior_failure_ids | failure_ids
    ordered_failed_ids = tuple(case_id for case_id in selected_order if case_id in failed_ids)
    counts = dict(selection.counts)
    counts.update(
        {
            "failed": len(ordered_failed_ids),
            "published_hybrid_only": len(published["hybrid_only"]),
            "published_baseline_only": len(published["baseline_only"]),
            "published_recovered_by_both": 0,
            "published_count": sum(len(ids) for ids in published.values()),
            "publication_failures": len(selection.failures) + len(failure_records),
        }
    )
    status = dict(selection.status)
    cohort_states: dict[str, str] = {}
    for cohort, confirmed_state in (
        ("baseline_only", "community_only"),
        ("hybrid_only", "technical_available"),
    ):
        selected = set(selection.selected_ids[cohort])
        confirmed = set(published[cohort])
        failed = selected & failed_ids
        if not selected:
            state = "not_confirmed"
        elif confirmed == selected:
            state = confirmed_state
        elif confirmed:
            state = "partial"
        elif failed == selected:
            state = "failed"
        else:
            state = "not_confirmed"
        cohort_states[cohort] = state
        status[f"publication_{cohort}"] = state
    states = [
        cohort_states[cohort]
        for cohort in ("hybrid_only", "baseline_only")
        if selection.selected_ids[cohort]
    ]
    if any(state == "partial" for state in states):
        status["publication"] = "partial"
    elif states and all(state in {"technical_available", "community_only"} for state in states):
        status["publication"] = "confirmed"
    elif states and any(state in {"technical_available", "community_only"} for state in states):
        status["publication"] = "partial"
    elif states and all(state == "failed" for state in states):
        status["publication"] = "failed"
    elif states:
        status["publication"] = "not_confirmed"
    else:
        status["publication"] = "not_confirmed"
    status["publication_recovered_by_both"] = "summary_only"

    return FrozenRecoverySelection(
        selected_ids=selection.selected_ids,
        selected_cases=selection.selected_cases,
        published_ids=published,
        counts=counts,
        status=status,
        aggregate_ids=selection.aggregate_ids,
        aggregate_cases=selection.aggregate_cases,
        attempted_ids=selection.attempted_ids,
        explained_ids=selection.explained_ids,
        failed_ids=ordered_failed_ids,
        failures=selection.failures + tuple(failure_records),
        detail_status=detail_status,
        policy_metadata=selection.policy_metadata,
    )


def _validate_anchor_in_run(
    run: RecoveryRun,
    subject_id: str,
    expected_anchor: RecoveryAnchor,
) -> int:
    actual_anchor = run.first_recovery.get(subject_id)
    if actual_anchor != expected_anchor:
        raise ValueError("case anchor does not match the arm first_recovery anchor")
    day_trace = run.days.get(expected_anchor.scoring_day)
    if day_trace is None:
        raise ValueError("case anchor day is absent from the arm day trace")
    if expected_anchor.row_index not in day_trace.candidate_row_indices:
        raise ValueError("case anchor is absent from the arm candidate rows")
    if expected_anchor.row_index not in day_trace.inspected_row_indices:
        raise ValueError("case anchor is absent from the arm inspected rows")
    inspected_rank = day_trace.inspected_row_indices.index(expected_anchor.row_index) + 1
    if expected_anchor.inspected_rank != inspected_rank:
        raise ValueError("case anchor inspected_rank disagrees with the arm trace")
    return inspected_rank


def _same_anchor_identity(left: RecoveryAnchor, right: RecoveryAnchor) -> bool:
    return (
        left.person_id == right.person_id
        and left.event_id == right.event_id
        and left.row_index == right.row_index
        and pd.Timestamp(left.scoring_day) == pd.Timestamp(right.scoring_day)
    )


def validate_recovery_case_anchor(
    run: RecoveryRun,
    case: RecoveryCase,
    *,
    baseline_run: RecoveryRun | None = None,
    hybrid_run: RecoveryRun | None = None,
) -> None:
    """Validate a case anchor against immutable as-of recovery-run evidence."""
    if not isinstance(run, RecoveryRun) or not isinstance(case, RecoveryCase):
        raise ValueError("run and case must be RecoveryRun and RecoveryCase values")

    if case.recovery_cohort == "recovered_by_both":
        if case.recovery_anchor_arm is None:
            raise ValueError(
                "materialized recovered_by_both case requires "
                "recovery_anchor_arm"
            )
        run_arm = _normalized_recovery_arm(run.arm)
        if run_arm == "baseline" and baseline_run is None:
            baseline_run = run
        if run_arm == "hybrid" and hybrid_run is None:
            hybrid_run = run
        if not isinstance(baseline_run, RecoveryRun) or not isinstance(
            hybrid_run, RecoveryRun
        ):
            raise ValueError(
                "both anchor validation requires baseline_run and hybrid_run"
            )
        if _normalized_recovery_arm(baseline_run.arm) != "baseline":
            raise ValueError("baseline_run must normalize to baseline")
        if _normalized_recovery_arm(hybrid_run.arm) != "hybrid":
            raise ValueError(
                "hybrid_run must normalize to hybrid or hybrid_seed0"
            )
        if baseline_run.daily_budget != hybrid_run.daily_budget:
            raise ValueError("both recovery runs must use equal daily budgets")
        if not baseline_run.run_identity or not hybrid_run.run_identity:
            raise ValueError(
                "both recovery runs require non-blank run_identity values"
            )
        if baseline_run.run_identity != hybrid_run.run_identity:
            raise ValueError("both recovery runs must share run_identity")
        if not baseline_run.as_of_identity or not hybrid_run.as_of_identity:
            raise ValueError(
                "both recovery runs require non-blank as_of_identity values"
            )
        if baseline_run.as_of_identity != hybrid_run.as_of_identity:
            raise ValueError("both recovery runs must share as_of_identity")
        baseline_anchor = baseline_run.first_recovery.get(case.subject_id)
        hybrid_anchor = hybrid_run.first_recovery.get(case.subject_id)
        if baseline_anchor is None or hybrid_anchor is None:
            raise ValueError("both case subject is absent from one recovery arm")
        expected_anchor, expected_arm = choose_earliest_recovery_anchor(
            baseline_anchor, hybrid_anchor
        )
        if not _same_anchor_identity(case.anchor_event, expected_anchor) or (
            _normalized_recovery_arm(case.recovery_anchor_arm) != expected_arm
        ):
            raise ValueError("case anchor does not match the earlier recovery arm")
        baseline_rank = _validate_anchor_in_run(
            baseline_run, case.subject_id, baseline_anchor
        )
        hybrid_rank = _validate_anchor_in_run(
            hybrid_run, case.subject_id, hybrid_anchor
        )
        expected_rank = baseline_rank if expected_arm == "baseline" else hybrid_rank
        if case.anchor_event.inspected_rank != expected_rank:
            raise ValueError("case anchor inspected_rank disagrees with the arm trace")
        return

    expected_arm = _normalized_recovery_arm(case.recovery_anchor_arm or "")
    if _normalized_recovery_arm(run.arm) != expected_arm:
        raise ValueError("recovery run arm does not match case recovery_anchor_arm")
    expected_anchor = run.first_recovery.get(case.subject_id)
    if expected_anchor is None:
        raise ValueError("case subject is absent from recovery run")
    if not _same_anchor_identity(case.anchor_event, expected_anchor):
        raise ValueError("case anchor does not match the arm first_recovery anchor")
    inspected_rank = _validate_anchor_in_run(run, case.subject_id, expected_anchor)
    if case.anchor_event.inspected_rank != inspected_rank:
        raise ValueError("case anchor inspected_rank disagrees with the arm trace")
