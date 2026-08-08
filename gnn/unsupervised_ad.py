"""Leak-safe unsupervised and caught-supervised anomaly evaluation."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score

from gnn import config as FC
from gnn.demo_baseline import FEATURE_NAMES, build_baseline_features
from gnn.pu_learning import (
    apply_score_threshold,
    build_caught_snapshot,
    choose_score_quantile,
    fit_caught_supervised,
    fit_unlabeled_anomaly,
    parse_bool_series,
)
from gnn.run_demo import _build_oracle
from gnn.unsupervised_features import (
    FeatureBundle,
    RELATIONAL_PROXY_FEATURES,
    build_relational_feature_bundle,
    encode_feature_splits,
)


MODE_METADATA = {
    "strict": {
        "label": "Strict unsupervised",
        "description": (
            "Fits on all training rows without target labels and selects the "
            "threshold from the training score distribution."
        ),
        "deployable": True,
    },
    "assisted": {
        "label": "Label-assisted benchmark",
        "description": (
            "Excludes known positive training rows and tunes the threshold "
            "with validation labels; retained as a legacy oracle-assisted "
            "diagnostic that is nondeployable and not a performance ceiling."
        ),
        "deployable": False,
    },
}

PRIMARY_ARM_ORDER = [
    "tabular_unlabeled",
    "relational_unlabeled",
    "relational_caught_supervised",
]
ABLATION_ARM_ORDER = ["tabular_caught_supervised"]
ARM_METADATA = {
    "tabular_unlabeled": {
        "label": "Tabular unlabeled",
        "fit_signal": "unlabeled_feature_distribution",
        "feature_count": 14,
        "feature_scope": "observable tabular features",
        "supervision": "none",
        "role": "primary",
    },
    "relational_unlabeled": {
        "label": "Relational unlabeled",
        "fit_signal": "unlabeled_feature_distribution",
        "feature_count": 18,
        "feature_scope": "14 tabular features plus 4 relational proxies",
        "supervision": "none",
        "role": "primary",
    },
    "relational_caught_supervised": {
        "label": "Relational caught-supervised (naive PU)",
        "fit_signal": "caught_vs_unlabeled_naive_pu",
        "feature_count": 18,
        "feature_scope": "14 tabular features plus 4 relational proxies",
        "supervision": "official caught positives versus unlabeled",
        "role": "primary",
    },
    "tabular_caught_supervised": {
        "label": "Tabular caught-supervised (naive PU) ablation",
        "fit_signal": "caught_vs_unlabeled_naive_pu",
        "feature_count": 14,
        "feature_scope": "observable tabular features",
        "supervision": "official caught positives versus unlabeled",
        "role": "ablation",
    },
}
for _arm_metadata in ARM_METADATA.values():
    _arm_metadata.update({
        "operating_point_policy": "label-free validation score quantile",
        "scar_guarantee": False,
        "deployability": (
            "Label and threshold semantics are deployable conditional on an "
            "available identity-resolution system."
        ),
    })


class _ImmutableDict(dict):
    """JSON-compatible mapping that rejects ordinary mutation."""

    @staticmethod
    def _immutable(*args, **kwargs):
        raise TypeError("frozen payload metadata is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __ior__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable


def _freeze_payload(value):
    if isinstance(value, dict):
        return _ImmutableDict({
            key: _freeze_payload(item) for key, item in value.items()
        })
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_payload(item) for item in value)
    return value


def _thaw_payload(value):
    if isinstance(value, dict):
        return {key: _thaw_payload(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_payload(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


@dataclass(frozen=True)
class FrozenArmRegion:
    """One regional arm frozen before retrospective oracle evaluation."""

    arm_id: str
    region: str
    status: str
    feature_names: tuple
    scored_events: object
    model_metadata: dict
    threshold_metadata: dict
    label_metadata: dict
    sample_counts: dict
    realized_test_alert_rate: object = None
    skip_reason: object = None

    def __post_init__(self):
        if self.arm_id not in ARM_METADATA:
            raise ValueError(f"unknown deployable arm: {self.arm_id!r}")
        if self.status not in {"completed", "skipped"}:
            raise ValueError("status must be completed or skipped")
        if self.status == "completed" and not isinstance(
            self.scored_events, FrozenScoredEvents
        ):
            raise ValueError("completed arm requires FrozenScoredEvents")
        if self.status == "skipped" and not self.skip_reason:
            raise ValueError("skipped arm requires a reason")
        object.__setattr__(self, "feature_names", tuple(self.feature_names))
        for name in (
            "model_metadata",
            "threshold_metadata",
            "label_metadata",
            "sample_counts",
        ):
            object.__setattr__(self, name, _freeze_payload(dict(getattr(self, name))))


@dataclass(frozen=True)
class FrozenDeployableArms:
    """All regional arm scores frozen before an oracle is admitted."""

    arms: dict
    fit_as_of: str
    alert_rate: float
    seed: int
    n_estimators: int

    def __post_init__(self):
        expected = [*PRIMARY_ARM_ORDER, *ABLATION_ARM_ORDER]
        if list(self.arms) != expected:
            raise ValueError(f"arms must follow the declared order: {expected}")
        frozen_arms = _ImmutableDict({
            arm_id: _ImmutableDict(dict(region_results))
            for arm_id, region_results in self.arms.items()
        })
        object.__setattr__(self, "arms", frozen_arms)


def _skipped_arm_region(
    arm_id, region, feature_names, sample_counts, reason, label_metadata=None
):
    return FrozenArmRegion(
        arm_id=arm_id,
        region=region,
        status="skipped",
        feature_names=feature_names,
        scored_events=None,
        model_metadata={},
        threshold_metadata={},
        label_metadata=label_metadata or {},
        sample_counts=sample_counts,
        skip_reason=reason,
    )


def _validate_feature_bundle(observable_rows, feature_bundle):
    if not isinstance(feature_bundle, FeatureBundle):
        raise TypeError("feature_bundle must be a FeatureBundle")
    event_ids = list(observable_rows["event_id"])
    bundle_ids = list(feature_bundle.event_ids)
    if len(bundle_ids) != len(set(bundle_ids)):
        raise ValueError("feature_bundle event IDs must be unique")
    if len(event_ids) != len(set(event_ids)):
        raise ValueError("observable_rows event IDs must be unique")
    if set(bundle_ids) != set(event_ids) or len(bundle_ids) != len(event_ids):
        raise ValueError("feature_bundle event IDs must exactly align observable_rows")
    expected_names = list(FEATURE_NAMES) + list(RELATIONAL_PROXY_FEATURES)
    if list(feature_bundle.names) != expected_names:
        raise ValueError(
            "feature_bundle must contain the declared 14 tabular and 4 relational "
            "features in contract order"
        )
    matrix = np.asarray(feature_bundle.matrix)
    if matrix.shape != (len(bundle_ids), len(expected_names)):
        raise ValueError("feature_bundle matrix shape is not aligned")
    if len(feature_bundle.display) != len(bundle_ids):
        raise ValueError("feature_bundle display rows are not aligned")
    missing_display = set(expected_names) - set(feature_bundle.display.columns)
    if missing_display:
        raise ValueError(
            f"feature_bundle display is missing columns: {sorted(missing_display)}"
        )
    display = feature_bundle.display[expected_names].copy()
    display.insert(0, "event_id", bundle_ids)
    display = display.set_index("event_id", drop=True).loc[event_ids]
    return display


def run_deployable_arms(
    observable_rows,
    feature_bundle,
    *,
    fit_as_of,
    alert_rate=0.1,
    seed=42,
    n_estimators=100,
):
    """Fit and freeze all four observable-only arms before oracle evaluation."""
    if not isinstance(observable_rows, pd.DataFrame):
        raise TypeError("observable_rows must be a pandas DataFrame")
    forbidden = _ORACLE_TARGET_COLUMNS.intersection(observable_rows.columns)
    if forbidden:
        raise ValueError(
            f"observable_rows contains oracle columns: {sorted(forbidden)}"
        )
    missing = set(_OBSERVABLE_COLUMNS) - set(observable_rows.columns)
    if missing:
        raise ValueError(f"observable_rows is missing columns: {sorted(missing)}")
    rows = observable_rows.reset_index(drop=True).copy()
    _require_nonempty_identifiers(
        rows, ["event_id", "split", "primary_person_id", "region"]
    )
    rows["t"] = _parse_aware_utc_series(rows["t"], name="t")
    rows["label_available_time_utc"] = _parse_aware_utc_series(
        rows["label_available_time_utc"], name="label_available_time_utc"
    )
    if (rows["label_available_time_utc"] < rows["t"]).any():
        raise ValueError("label_available_time_utc cannot be before event time")
    rows["seizure_flag"] = parse_bool_series(rows["seizure_flag"])
    required_splits = {"train", "validation", "test"}
    actual_splits = set(rows["split"])
    if actual_splits != required_splits:
        raise ValueError(
            "observable_rows must contain exactly train/validation/test splits"
        )
    split_times = {
        split: rows.loc[rows["split"].eq(split), "t"]
        for split in ("train", "validation", "test")
    }
    validation_start = split_times["validation"].min()
    temporal_order_valid = (
        split_times["train"].max() < validation_start
        and validation_start <= split_times["validation"].max()
        and split_times["validation"].max() < split_times["test"].min()
    )
    if not temporal_order_valid:
        raise ValueError(
            "temporal split order must satisfy max(train) < min(validation) "
            "<= max(validation) < min(test)"
        )
    parsed_fit_as_of = _parse_aware_utc_series(
        pd.Series([fit_as_of]), name="fit_as_of"
    ).iloc[0]
    if not (
        split_times["train"].max()
        < parsed_fit_as_of
        <= validation_start
    ):
        raise ValueError(
            "fit_as_of must satisfy max(train event time) < fit_as_of "
            "<= observable validation start "
            f"{validation_start.isoformat()}"
        )
    display = _validate_feature_bundle(rows, feature_bundle)

    tabular_names = list(FEATURE_NAMES)
    relational_names = tabular_names + list(RELATIONAL_PROXY_FEATURES)
    categorical = frozenset(feature_bundle.categorical_names)
    arm_results = {
        arm_id: {} for arm_id in (*PRIMARY_ARM_ORDER, *ABLATION_ARM_ORDER)
    }
    for region in rows["region"].drop_duplicates():
        region_rows = rows.loc[rows["region"].eq(region)].copy()
        split_rows = {
            split: region_rows.loc[region_rows["split"].eq(split)].copy()
            for split in ("train", "validation", "test")
        }
        sample_counts = {
            split: int(len(frame)) for split, frame in split_rows.items()
        }
        if any(count < 50 for count in sample_counts.values()):
            reason = "fewer than 50 rows in a required split"
            for arm_id in arm_results:
                names = (
                    tabular_names if arm_id.startswith("tabular")
                    else relational_names
                )
                arm_results[arm_id][region] = _skipped_arm_region(
                    arm_id, region, names, sample_counts, reason
                )
            continue

        caught_snapshot = build_caught_snapshot(
            split_rows["train"][
                ["seizure_flag", "label_available_time_utc"]
            ],
            parsed_fit_as_of,
        )
        aligned_display = {
            split: display.loc[frame["event_id"]].reset_index(drop=True)
            for split, frame in split_rows.items()
        }
        tabular = encode_feature_splits(
            aligned_display["train"],
            aligned_display["validation"],
            aligned_display["test"],
            tabular_names,
            categorical.intersection(tabular_names),
        )
        relational = encode_feature_splits(
            aligned_display["train"],
            aligned_display["validation"],
            aligned_display["test"],
            relational_names,
            categorical.intersection(relational_names),
        )
        arm_inputs = {
            "tabular_unlabeled": (tabular, False),
            "relational_unlabeled": (relational, False),
            "relational_caught_supervised": (relational, True),
            "tabular_caught_supervised": (tabular, True),
        }
        for arm_id in (*PRIMARY_ARM_ORDER, *ABLATION_ARM_ORDER):
            encoded, supervised = arm_inputs[arm_id]
            names = tabular_names if arm_id.startswith("tabular") else relational_names
            label_metadata = {
                "label_source": "observable seizure_flag as of fit cutoff",
                "fit_as_of": caught_snapshot.fit_as_of,
                "caught_positive_count": caught_snapshot.positive_rows,
                "immature_label_count": caught_snapshot.immature_rows,
                "labels_used_for_fit": supervised,
                "labels_used_for_threshold": False,
                "fit_signal": (
                    "caught_vs_unlabeled_naive_pu"
                    if supervised
                    else "unlabeled_feature_distribution"
                ),
                "scar_guarantee": False,
            }
            if supervised and np.unique(caught_snapshot.labels).size != 2:
                arm_results[arm_id][region] = _skipped_arm_region(
                    arm_id,
                    region,
                    names,
                    sample_counts,
                    "caught-supervised fit requires both caught and unlabeled classes",
                    label_metadata,
                )
                continue
            if supervised:
                frozen_scores = fit_caught_supervised(
                    encoded.train,
                    caught_snapshot.labels,
                    encoded.validation,
                    encoded.test,
                    seed=seed,
                )
            else:
                frozen_scores = fit_unlabeled_anomaly(
                    encoded.train,
                    encoded.validation,
                    encoded.test,
                    seed=seed,
                    n_estimators=n_estimators,
                )
            threshold, threshold_metadata = choose_score_quantile(
                frozen_scores.validation_scores, alert_rate=alert_rate
            )
            scored_events = freeze_scored_events(
                split_rows["test"],
                frozen_scores.test_scores,
                threshold,
                comparator=threshold_metadata["threshold_comparator"],
            )
            realized_test_alert_rate = float(scored_events.selected_mask.mean())
            threshold_metadata = {
                **threshold_metadata,
                "realized_test_alert_rate": realized_test_alert_rate,
            }
            arm_results[arm_id][region] = FrozenArmRegion(
                arm_id=arm_id,
                region=region,
                status="completed",
                feature_names=names,
                scored_events=scored_events,
                model_metadata=frozen_scores.model_metadata,
                threshold_metadata=threshold_metadata,
                label_metadata=label_metadata,
                sample_counts=sample_counts,
                realized_test_alert_rate=realized_test_alert_rate,
            )
    return FrozenDeployableArms(
        arms=arm_results,
        fit_as_of=parsed_fit_as_of.isoformat(),
        alert_rate=float(alert_rate),
        seed=int(seed),
        n_estimators=int(n_estimators),
    )


def _arm_region_payload(result, evaluation_only=None):
    payload = {
        "status": result.status,
        "arm_id": result.arm_id,
        "region": result.region,
        "feature_names": list(result.feature_names),
        "feature_count": len(result.feature_names),
        "model_metadata": _thaw_payload(result.model_metadata),
        "threshold_metadata": _thaw_payload(result.threshold_metadata),
        "label_metadata": _thaw_payload(result.label_metadata),
        "sample_counts": _thaw_payload(result.sample_counts),
    }
    if result.status == "skipped":
        payload["skip_reason"] = result.skip_reason
        return payload
    payload.update({
        "realized_test_alert_rate": result.realized_test_alert_rate,
        "scored_test": {
            "event_ids": list(result.scored_events.event_ids),
            "scores": result.scored_events.scores.tolist(),
            "threshold": result.scored_events.threshold,
            "comparator": result.scored_events.comparator,
            "selected_count": int(result.scored_events.selected_mask.sum()),
        },
    })
    if evaluation_only is not None:
        payload["evaluation_only"] = evaluation_only
    return payload


def evaluate_frozen_arms(frozen_arms, oracle_rows, catch_history):
    """Attach oracle-only metrics after every deployable arm has been frozen."""
    if not isinstance(frozen_arms, FrozenDeployableArms):
        raise TypeError("frozen_arms must be a FrozenDeployableArms instance")
    if not isinstance(oracle_rows, pd.DataFrame):
        raise TypeError("oracle_rows must be a pandas DataFrame")
    evaluated = {}
    for arm_id in (*PRIMARY_ARM_ORDER, *ABLATION_ARM_ORDER):
        evaluated[arm_id] = {}
        for region, result in frozen_arms.arms[arm_id].items():
            if result.status == "skipped":
                evaluated[arm_id][region] = _arm_region_payload(result)
                continue
            event_ids = set(result.scored_events.event_ids)
            regional_oracle = oracle_rows.loc[
                oracle_rows["event_id"].isin(event_ids), _ORACLE_COLUMNS
            ].copy()
            evaluation_only = evaluate_frozen_scores(
                result.scored_events, regional_oracle, catch_history
            )
            evaluated[arm_id][region] = _arm_region_payload(
                result, evaluation_only=evaluation_only
            )
    return evaluated


_OBSERVABLE_COLUMNS = [
    "event_id",
    "split",
    "t",
    "primary_obs_id",
    "primary_person_id",
    "region",
    "seizure_flag",
    "label_available_time_utc",
]
_ORACLE_COLUMNS = [
    "event_id",
    "primary_person_id",
    "true_contraband_present",
    "false_negative_flag",
]
_ORACLE_TARGET_COLUMNS = frozenset({
    "true_contraband_present",
    "false_negative_flag",
    "detected_flag",
})


def _require_nonempty_identifiers(rows, columns):
    """Reject null or blank identifiers without coercing them to strings."""
    for column in columns:
        values = rows[column]
        invalid = values.isna() | values.map(
            lambda value: isinstance(value, str) and not value.strip()
        )
        if invalid.any():
            raise ValueError(f"{column} must contain non-null, nonempty values")


def _parse_aware_utc_series(series, *, name):
    """Parse a timestamp series while rejecting null, malformed, and naive values."""
    if not isinstance(series, pd.Series):
        series = pd.Series(series)

    malformed = []
    naive = []
    for index, value in series.items():
        if pd.isna(value):
            malformed.append(index)
            continue
        try:
            timestamp = pd.Timestamp(value)
        except (TypeError, ValueError, OverflowError):
            malformed.append(index)
            continue
        if pd.isna(timestamp):
            malformed.append(index)
        elif timestamp.tzinfo is None:
            naive.append(index)

    if malformed:
        raise ValueError(f"{name} contains invalid timestamp values at {malformed}")
    if naive:
        raise ValueError(f"{name} values must be timezone-aware at {naive}")

    try:
        parsed = pd.to_datetime(series, utc=True, errors="raise", format="mixed")
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} contains invalid timestamp values") from error
    return pd.Series(parsed, index=series.index, name=series.name)


def load_observable_pool(corpus_dir):
    """Load the model-visible event pool without reading synthetic oracle truth."""
    event_columns = [
        "event_id",
        "event_timestamp_utc",
        "observed_person_record_id",
        "primary_person_id",
        "region",
        "seizure_flag",
        "label_available_time_utc",
    ]
    split_columns = ["entity_id", "split"]
    try:
        events = pd.read_csv(
            corpus_dir / "crossing_events.csv", usecols=event_columns
        )
        splits = pd.read_csv(
            corpus_dir / "train_valid_test_splits.csv", usecols=split_columns
        )
    except (FileNotFoundError, ValueError) as error:
        raise ValueError(
            "observable corpus files are missing or lack required columns"
        ) from error

    _require_nonempty_identifiers(
        events,
        [
            "event_id",
            "observed_person_record_id",
            "primary_person_id",
            "region",
        ],
    )
    _require_nonempty_identifiers(splits, ["entity_id", "split"])
    if events["event_id"].duplicated().any():
        raise ValueError("crossing_events.csv requires unique event_id values")
    if splits["entity_id"].duplicated().any():
        raise ValueError(
            "train_valid_test_splits.csv requires unique event_id values"
        )
    unknown_splits = set(splits["split"]) - {"train", "validation", "test"}
    if unknown_splits:
        raise ValueError(f"split contains unsupported values: {sorted(unknown_splits)}")

    events = events.copy()
    events["t"] = _parse_aware_utc_series(
        events["event_timestamp_utc"], name="event_timestamp_utc"
    )
    events["label_available_time_utc"] = _parse_aware_utc_series(
        events["label_available_time_utc"], name="label_available_time_utc"
    )
    before_event = events["label_available_time_utc"] < events["t"]
    if before_event.any():
        bad_ids = events.loc[before_event, "event_id"].tolist()
        raise ValueError(
            "label_available_time_utc cannot be before event time for event IDs: "
            f"{bad_ids[:3]}"
        )
    events["seizure_flag"] = parse_bool_series(events["seizure_flag"])
    events = events.rename(
        columns={"observed_person_record_id": "primary_obs_id"}
    ).drop(columns=["event_timestamp_utc"])
    splits = splits.rename(columns={"entity_id": "event_id"})

    merged = events.merge(
        splits,
        on="event_id",
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    if not merged["_merge"].eq("both").all():
        missing = merged.loc[merged["_merge"] == "left_only", "event_id"].tolist()
        extra = merged.loc[merged["_merge"] == "right_only", "event_id"].tolist()
        raise ValueError(
            "observable event/split merge must be one-to-one with no missing "
            f"or extra IDs; missing split={missing[:3]}, extra split={extra[:3]}"
        )
    return merged[_OBSERVABLE_COLUMNS].copy()


def load_oracle_evaluation(corpus_dir):
    """Load synthetic carrier targets for retrospective evaluation only."""
    try:
        oracle = pd.read_csv(
            corpus_dir / "event_ground_truth.csv", usecols=_ORACLE_COLUMNS
        )
    except (FileNotFoundError, ValueError) as error:
        raise ValueError(
            "event_ground_truth.csv is missing or lacks required oracle columns"
        ) from error

    _require_nonempty_identifiers(oracle, ["event_id", "primary_person_id"])
    if oracle["event_id"].duplicated().any():
        raise ValueError("event_ground_truth.csv requires unique event_id values")
    for column in ("true_contraband_present", "false_negative_flag"):
        oracle[column] = parse_bool_series(oracle[column])
    return oracle[_ORACLE_COLUMNS].copy()


_OFFICIAL_HISTORY_TOKEN = object()


@dataclass(frozen=True, init=False)
class OfficialCatchHistory:
    """Immutable provenance for official catches from one complete event pool."""

    caught_times: tuple
    source_event_ids: tuple
    source_event_count: int
    source_event_fingerprint: str
    split_counts: tuple
    source_scope: str

    def __new__(cls, token=None):
        if token is not _OFFICIAL_HISTORY_TOKEN:
            raise TypeError(
                "OfficialCatchHistory must be created by "
                "build_official_catch_history"
            )
        return super().__new__(cls)

    def __init__(self, token=None):
        # Fields are populated exactly once by build_official_catch_history.
        del token


def _event_id_fingerprint(event_ids):
    digest = hashlib.sha256()
    for event_id in sorted(event_ids, key=str):
        encoded = str(event_id).encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def build_official_catch_history(observable_all, expected_event_ids):
    """Map each officially caught person to the earliest observable catch time."""
    if not isinstance(observable_all, pd.DataFrame):
        raise TypeError("observable_all must be a pandas DataFrame")
    required = {
        "event_id",
        "split",
        "t",
        "primary_person_id",
        "seizure_flag",
        "label_available_time_utc",
    }
    missing = required - set(observable_all.columns)
    if missing:
        raise ValueError(f"observable_all is missing required columns: {sorted(missing)}")
    rows = observable_all.reset_index(drop=True).copy()
    _require_nonempty_identifiers(
        rows, ["event_id", "split", "primary_person_id"]
    )
    if rows["event_id"].duplicated().any():
        raise ValueError("observable_all requires unique event_id values")
    if not isinstance(expected_event_ids, (set, frozenset)):
        raise TypeError("expected_event_ids must be an independent set of event IDs")
    if any(
        pd.isna(event_id)
        or (isinstance(event_id, str) and not event_id.strip())
        for event_id in expected_event_ids
    ):
        raise ValueError("expected_event_ids contains an invalid event ID")
    actual_event_ids = set(rows["event_id"])
    if actual_event_ids != expected_event_ids:
        missing_expected = expected_event_ids - actual_event_ids
        unexpected = actual_event_ids - expected_event_ids
        raise ValueError(
            "observable_all must exactly match expected_event_ids; "
            f"missing={sorted(missing_expected)[:3]}, "
            f"unexpected={sorted(unexpected)[:3]}"
        )
    required_splits = {"train", "validation", "test"}
    actual_splits = set(rows["split"])
    if actual_splits != required_splits:
        raise ValueError(
            "observable_all must contain all train/validation/test splits and "
            f"no others; found {sorted(actual_splits)}"
        )
    event_times = _parse_aware_utc_series(rows["t"], name="t")
    caught = parse_bool_series(rows["seizure_flag"])
    availability = _parse_aware_utc_series(
        rows["label_available_time_utc"],
        name="label_available_time_utc",
    )
    before_event = availability < event_times
    if before_event.any():
        bad_ids = rows.loc[before_event, "event_id"].tolist()
        raise ValueError(
            "label_available_time_utc cannot be before event time for event IDs: "
            f"{bad_ids[:3]}"
        )
    caught_rows = pd.DataFrame({
        "primary_person_id": rows["primary_person_id"].to_numpy(),
        "caught_time": availability.to_numpy(),
        "caught": caught.to_numpy(),
    })
    earliest = (
        caught_rows.loc[caught_rows["caught"]]
        .groupby("primary_person_id", sort=False)["caught_time"]
        .min()
    )
    history = OfficialCatchHistory(_OFFICIAL_HISTORY_TOKEN)
    object.__setattr__(
        history,
        "caught_times",
        tuple(
            (person_id, pd.Timestamp(caught_time))
            for person_id, caught_time in earliest.items()
        ),
    )
    object.__setattr__(history, "source_event_ids", tuple(rows["event_id"]))
    object.__setattr__(history, "source_event_count", int(len(rows)))
    object.__setattr__(
        history,
        "source_event_fingerprint",
        _event_id_fingerprint(expected_event_ids),
    )
    object.__setattr__(
        history,
        "split_counts",
        tuple(
            (split, int(rows["split"].eq(split).sum()))
            for split in ("train", "validation", "test")
        ),
    )
    object.__setattr__(history, "source_scope", "complete_observable_pool")
    return history


def _immutable_score_array(scores):
    try:
        copied = np.array(scores, dtype=float, copy=True, order="C")
    except (TypeError, ValueError) as error:
        raise ValueError("scores must be numeric") from error
    if copied.ndim != 1 or copied.size == 0:
        raise ValueError("scores must be a nonempty 1D sequence")
    if not np.isfinite(copied).all():
        raise ValueError("scores must contain only finite values")
    return np.frombuffer(copied.tobytes(order="C"), dtype=copied.dtype)


@dataclass(frozen=True)
class FrozenScoredEvents:
    """Oracle-free, immutable event scores and their observable identities."""

    event_ids: tuple
    scores: np.ndarray
    primary_person_ids: tuple
    event_times: tuple
    observed_caught: tuple
    threshold: float
    comparator: str = "greater_equal"

    def __post_init__(self):
        event_ids = tuple(self.event_ids)
        person_ids = tuple(self.primary_person_ids)
        event_times = tuple(
            _parse_aware_utc_series(
                pd.Series(self.event_times), name="event_times"
            ).tolist()
        )
        caught = tuple(
            parse_bool_series(pd.Series(self.observed_caught, dtype=object)).tolist()
        )
        scores = _immutable_score_array(self.scores)
        lengths = {
            len(event_ids), len(person_ids), len(event_times), len(caught), len(scores)
        }
        if len(lengths) != 1:
            raise ValueError("frozen event fields and scores must have the same length")
        if not event_ids:
            raise ValueError("frozen scored events must not be empty")
        identifiers = pd.DataFrame({
            "event_id": event_ids,
            "primary_person_id": person_ids,
        })
        _require_nonempty_identifiers(
            identifiers, ["event_id", "primary_person_id"]
        )
        if len(set(event_ids)) != len(event_ids):
            raise ValueError("FrozenScoredEvents requires unique event_id values")
        try:
            threshold = float(self.threshold)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("threshold must be finite") from error
        if not np.isfinite(threshold):
            raise ValueError("threshold must be finite")
        if self.comparator != "greater_equal":
            raise ValueError("comparator must be 'greater_equal'")

        object.__setattr__(self, "event_ids", event_ids)
        object.__setattr__(self, "scores", scores)
        object.__setattr__(self, "primary_person_ids", person_ids)
        object.__setattr__(self, "event_times", event_times)
        object.__setattr__(self, "observed_caught", caught)
        object.__setattr__(self, "threshold", threshold)

    @property
    def selected_mask(self):
        """Return the selections implied by the frozen comparator and threshold."""
        return apply_score_threshold(
            self.scores, self.threshold, comparator=self.comparator
        )


def freeze_scored_events(
    observable_test_rows, scores, threshold, comparator="greater_equal"
):
    """Detach scored test events before any oracle data is loaded or joined."""
    if not isinstance(observable_test_rows, pd.DataFrame):
        raise TypeError("observable_test_rows must be a pandas DataFrame")
    forbidden = _ORACLE_TARGET_COLUMNS.intersection(observable_test_rows.columns)
    if forbidden:
        raise ValueError(
            "observable_test_rows contains oracle columns: "
            f"{sorted(forbidden)}"
        )
    required = {"event_id", "primary_person_id", "t", "seizure_flag"}
    missing = required - set(observable_test_rows.columns)
    if missing:
        raise ValueError(
            "observable_test_rows is missing required columns: "
            f"{sorted(missing)}"
        )
    return FrozenScoredEvents(
        event_ids=tuple(observable_test_rows["event_id"]),
        scores=scores,
        primary_person_ids=tuple(observable_test_rows["primary_person_id"]),
        event_times=tuple(observable_test_rows["t"]),
        observed_caught=tuple(observable_test_rows["seizure_flag"]),
        threshold=threshold,
        comparator=comparator,
    )


def _validated_caught_times(official_caught_times):
    if not isinstance(official_caught_times, OfficialCatchHistory):
        raise TypeError(
            "official_caught_times must be an OfficialCatchHistory built from "
            "the complete observable pool"
        )
    normalized = {}
    for person_id, value in official_caught_times.caught_times:
        if pd.isna(person_id) or (isinstance(person_id, str) and not person_id.strip()):
            raise ValueError("official_caught_times contains an invalid person ID")
        try:
            timestamp = pd.Timestamp(value)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(
                "official_caught_times must contain valid timestamps"
            ) from error
        if pd.isna(timestamp) or timestamp.tzinfo is None:
            raise ValueError(
                "official_caught_times must contain timezone-aware timestamps"
            )
        normalized[person_id] = timestamp.tz_convert("UTC")
    return normalized


def _binary_event_metrics(y_true, selected):
    target = np.asarray(y_true, dtype=bool)
    predicted = np.asarray(selected, dtype=bool)
    positive_count = int(target.sum())
    predicted_count = int(predicted.sum())
    true_positive_count = int((target & predicted).sum())
    precision = true_positive_count / predicted_count if predicted_count else 0.0
    recall = true_positive_count / positive_count if positive_count else 0.0
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "positive_count": positive_count,
        "predicted_positive_count": predicted_count,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _person_recovery_metrics(person_ids, missed, selected, eligible_people=None):
    missed_people = {
        person_id
        for person_id, is_missed in zip(person_ids, missed, strict=True)
        if is_missed
    }
    if eligible_people is not None:
        missed_people &= set(eligible_people)
    found_people = {
        person_id
        for person_id, is_missed, is_selected in zip(
            person_ids, missed, selected, strict=True
        )
        if is_missed and is_selected and person_id in missed_people
    }
    positive_count = len(missed_people)
    found = len(found_people)
    return {
        "positive_count": positive_count,
        "found": found,
        "recall": found / positive_count if positive_count else 0.0,
    }


def _unique_person_first_hits(
    event_ids, person_ids, event_times, missed, selected
):
    metrics = _person_recovery_metrics(person_ids, missed, selected)
    selected_missed = [
        (event_time, str(event_id), index, person_id, event_id)
        for index, (event_id, person_id, event_time, is_missed, is_selected)
        in enumerate(
            zip(
                event_ids,
                person_ids,
                event_times,
                missed,
                selected,
                strict=True,
            )
        )
        if is_missed and is_selected
    ]
    first_hit_event_ids = {}
    for _, _, _, person_id, event_id in sorted(selected_missed):
        first_hit_event_ids.setdefault(person_id, event_id)
    return {
        "definition": (
            "Among people with at least one missed-at-event row, count a person "
            "recovered at their chronologically earliest selected missed event; "
            "official catch history does not restrict this stratum."
        ),
        **metrics,
        "first_hit_event_ids": first_hit_event_ids,
    }


def evaluate_frozen_scores(frozen, oracle_rows, official_caught_times):
    """Join oracle truth after scoring and calculate retrospective target strata."""
    if not isinstance(frozen, FrozenScoredEvents):
        raise TypeError("frozen must be a FrozenScoredEvents instance")
    if not isinstance(oracle_rows, pd.DataFrame):
        raise TypeError("oracle_rows must be a pandas DataFrame")
    if set(oracle_rows.columns) != set(_ORACLE_COLUMNS):
        raise ValueError(
            "oracle_rows must contain exactly the retrospective oracle columns"
        )
    _require_nonempty_identifiers(oracle_rows, ["event_id", "primary_person_id"])
    if oracle_rows["event_id"].duplicated().any():
        raise ValueError("oracle_rows contains duplicate event_id values")

    frozen_ids = set(frozen.event_ids)
    oracle_ids = set(oracle_rows["event_id"])
    missing = frozen_ids - oracle_ids
    extra = oracle_ids - frozen_ids
    if missing:
        raise ValueError(f"oracle_rows is missing event IDs: {sorted(missing)[:3]}")
    if extra:
        raise ValueError(f"oracle_rows contains extra event IDs: {sorted(extra)[:3]}")

    oracle = oracle_rows.copy()
    for column in ("true_contraband_present", "false_negative_flag"):
        oracle[column] = parse_bool_series(oracle[column])
    frozen_rows = pd.DataFrame({
        "event_id": frozen.event_ids,
        "frozen_person_id": frozen.primary_person_ids,
        "event_time": frozen.event_times,
        "observed_caught": frozen.observed_caught,
        "selected": frozen.selected_mask,
        "_order": np.arange(len(frozen.event_ids)),
    })
    joined = frozen_rows.merge(
        oracle,
        on="event_id",
        how="left",
        validate="one_to_one",
        sort=False,
    ).sort_values("_order")
    person_mismatch = joined["frozen_person_id"] != joined["primary_person_id"]
    if person_mismatch.any():
        bad_ids = joined.loc[person_mismatch, "event_id"].tolist()
        raise ValueError(
            "oracle primary_person_id does not match frozen person IDs for "
            f"events: {bad_ids[:3]}"
        )

    caught_times = _validated_caught_times(official_caught_times)
    uncovered_ids = set(frozen.event_ids) - set(
        official_caught_times.source_event_ids
    )
    if uncovered_ids:
        raise ValueError(
            "OfficialCatchHistory does not cover frozen event IDs: "
            f"{sorted(uncovered_ids)[:3]}"
        )
    observed_caught_people = {
        person_id
        for person_id, is_caught in zip(
            frozen.primary_person_ids, frozen.observed_caught, strict=True
        )
        if is_caught
    }
    missing_caught_people = observed_caught_people - set(caught_times)
    if missing_caught_people:
        raise ValueError(
            "frozen observed-caught person is absent from OfficialCatchHistory: "
            f"{sorted(missing_caught_people)[:3]}"
        )
    selected = joined["selected"].to_numpy(dtype=bool)
    carriers = joined["true_contraband_present"].to_numpy(dtype=bool)
    missed = joined["false_negative_flag"].to_numpy(dtype=bool)
    person_ids = tuple(joined["primary_person_id"])
    event_times = tuple(joined["event_time"])
    no_prior_catch = np.array([
        person_id not in caught_times
        or not caught_times[person_id] < event_time
        for person_id, event_time in zip(person_ids, event_times, strict=True)
    ])
    no_prior_missed = missed & no_prior_catch
    observed_caught = joined["observed_caught"].to_numpy(dtype=bool)

    observed_metrics = _binary_event_metrics(observed_caught, selected)
    prevalence = float(observed_caught.mean()) if len(observed_caught) else None
    if (
        prevalence in (None, 0.0)
        or observed_metrics["predicted_positive_count"] == 0
    ):
        lift = None
    else:
        lift = observed_metrics["precision"] / prevalence
    observed_metrics.update({
        "prevalence": prevalence,
        "lift_over_prevalence": lift,
    })

    never_caught_people = set(person_ids) - set(caught_times)
    return {
        "all_carrier_events": _binary_event_metrics(carriers, selected),
        "missed_at_event": _binary_event_metrics(missed, selected),
        "no_prior_catch_missed_events": _binary_event_metrics(
            no_prior_missed, selected
        ),
        "observed_catch_enrichment": observed_metrics,
        "unique_person_first_hits": _unique_person_first_hits(
            frozen.event_ids,
            person_ids,
            event_times,
            missed,
            selected,
        ),
        "lifetime_never_caught_people": _person_recovery_metrics(
            person_ids,
            missed,
            selected,
            eligible_people=never_caught_people,
        ),
    }


def prepare_training_rows(train_df, mode="strict"):
    """Select the rows used to fit an anomaly detector for *mode*.

    Strict mode is label-free and therefore keeps every training row.  Assisted
    mode is an explicitly label-assisted benchmark that removes known positive
    rows before fitting.
    """
    if mode == "strict":
        return train_df.copy(), {
            "labels_used_for_fit": False,
            "train_positive_excluded": 0,
        }

    if mode == "assisted":
        if "true_contraband_present" not in train_df.columns:
            raise ValueError(
                "assisted mode requires true_contraband_present training labels"
            )
        positives = train_df["true_contraband_present"].astype(bool)
        selected = train_df.loc[~positives].copy()
        return selected, {
            "labels_used_for_fit": True,
            "train_positive_excluded": int(positives.sum()),
        }

    raise ValueError(f"unknown anomaly mode: {mode!r}")


def choose_threshold(train_scores, mode, y_valid, contamination=0.1):
    """Choose an anomaly-score threshold and describe its label provenance."""
    if mode not in {"strict", "assisted"}:
        raise ValueError(f"unknown anomaly mode: {mode!r}")

    scores = np.asarray(train_scores, dtype=float)
    if scores.size == 0:
        raise ValueError("train_scores must not be empty")
    if not 0 < contamination <= 1:
        raise ValueError("contamination must be in the interval (0, 1]")

    if mode == "strict":
        anomaly_scores = -scores
        threshold = np.quantile(
            anomaly_scores,
            1.0 - contamination,
            method="higher",
        )
        return float(threshold), {
            "threshold_source": "train_score_quantile",
            "validation_labels_used_for_threshold": False,
        }

    if y_valid is None:
        raise ValueError("assisted mode requires validation labels")

    labels = np.asarray(y_valid)
    if labels.size != scores.size or pd.isna(labels).any():
        raise ValueError("assisted mode requires validation labels")

    result = find_best_threshold_f1(labels.astype(bool), scores)
    if result is None:
        raise ValueError("validation labels must include at least one positive")
    return float(result[0]), {
        "threshold_source": "validation_f1",
        "validation_labels_used_for_threshold": True,
    }


def load_pool_with_region(corpus_dir):
    """Loads the test set and training set with region and ground truth labels."""
    # 1. Ground Truth
    egt = pd.read_csv(
        corpus_dir / "event_ground_truth.csv",
        usecols=["event_id", "primary_person_id", "true_contraband_present"]
    )
    # Convert string boolean if necessary
    if egt["true_contraband_present"].dtype == object:
        egt["true_contraband_present"] = egt["true_contraband_present"].astype(str).str.lower().eq("true")
    else:
        egt["true_contraband_present"] = egt["true_contraband_present"].fillna(False).astype(bool)

    # 2. Splits
    splits = pd.read_csv(
        corpus_dir / "train_valid_test_splits.csv",
        usecols=["entity_id", "split"]
    )

    # 3. Events (to get time, obs_id, and region)
    ev = pd.read_csv(
        corpus_dir / "crossing_events.csv",
        usecols=["event_id", "event_timestamp_utc", "observed_person_record_id", "region"]
    )

    # Merge
    df = egt.merge(splits, left_on="event_id", right_on="entity_id", how="inner")
    df = df.merge(ev, on="event_id", how="inner")

    df["t"] = pd.to_datetime(df.event_timestamp_utc, utc=True, errors="coerce")
    df = df.rename(columns={"observed_person_record_id": "primary_obs_id"})

    return df

def find_best_threshold_f1(y_true, scores, num_thresholds=100):
    """Finds the threshold that maximizes F1 score.

    Returns (best_threshold, precision, recall, f1).  If there are no
    positive labels the function returns None to signal that threshold
    tuning is impossible rather than silently returning zeros.
    """
    # Lower scores in Isolation Forest mean more anomalous.
    # We will negate scores so that higher = more anomalous.
    anom_scores = -scores

    # If all labels are false, we can't calculate a meaningful best threshold
    if y_true.sum() == 0:
        return None

    min_score = anom_scores.min()
    max_score = anom_scores.max()

    best_f1 = -1
    best_p = 0
    best_r = 0
    best_t = min_score

    thresholds = np.linspace(min_score, max_score, num_thresholds)

    for t in thresholds:
        y_pred = (anom_scores >= t)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_p = precision_score(y_true, y_pred, zero_division=0)
            best_r = recall_score(y_true, y_pred, zero_division=0)
            best_t = t

    return best_t, best_p, best_r, best_f1

def _extract_features(df, corpus_dir, obs2id):
    """Build feature matrix for *df* and assert row alignment."""
    X, names = build_baseline_features(
        df[["event_id", "primary_obs_id", "t"]], corpus_dir, obs2id
    )
    assert X.shape[0] == len(df), (
        f"Feature matrix rows ({X.shape[0]}) != DataFrame rows ({len(df)})"
    )
    return X, names


def cached_feature_rows(rows, feature_cache):
    """Return cached feature rows in the exact order of *rows* event IDs."""
    event_ids = rows["event_id"].tolist()
    missing = [event_id for event_id in event_ids if event_id not in feature_cache]
    if missing:
        raise KeyError(f"feature cache missing event IDs: {missing[:3]}")
    return np.vstack([feature_cache[event_id] for event_id in event_ids])


def _evaluate_threshold(y_true, scores, threshold):
    """Return auditable metrics for a frozen anomaly-score threshold."""
    y_true = np.asarray(y_true, dtype=bool)
    scores = np.asarray(scores, dtype=float)
    preds = -scores >= float(threshold)
    positive_count = int(y_true.sum())
    predicted_count = int(preds.sum())
    prevalence = float(y_true.mean()) if len(y_true) else 0.0
    predicted_rate = float(preds.mean()) if len(preds) else 0.0
    return {
        "precision": round(float(precision_score(y_true, preds, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, preds, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, preds, zero_division=0)), 4),
        "positive_count": positive_count,
        "predicted_positive_count": predicted_count,
        "positive_prevalence": round(prevalence, 4),
        "predicted_positive_rate": round(predicted_rate, 4),
    }


def _run_region(region_df, corpus_dir, obs2id, mode, contamination=0.1,
                feature_cache=None, feature_names=None, n_estimators=100):
    """Fit and evaluate one regional Isolation Forest for one leakage mode."""
    train_df = region_df[region_df["split"] == "train"].copy()
    valid_df = region_df[region_df["split"] == "validation"].copy()
    test_df = region_df[region_df["split"] == "test"].copy()

    fit_df, fit_meta = prepare_training_rows(train_df, mode=mode)
    if feature_cache is None:
        X_train, feature_names = _extract_features(fit_df, corpus_dir, obs2id)
        X_valid, _ = _extract_features(valid_df, corpus_dir, obs2id)
        X_test, _ = _extract_features(test_df, corpus_dir, obs2id)
    else:
        X_train = cached_feature_rows(fit_df, feature_cache)
        X_valid = cached_feature_rows(valid_df, feature_cache)
        X_test = cached_feature_rows(test_df, feature_cache)

    clf = IsolationForest(
        n_estimators=n_estimators, random_state=42, n_jobs=-1
    )
    clf.fit(X_train)
    train_scores = clf.decision_function(X_train)
    valid_scores = clf.decision_function(X_valid)
    test_scores = clf.decision_function(X_test)

    y_valid = valid_df["true_contraband_present"].to_numpy(dtype=bool)
    y_test = test_df["true_contraband_present"].to_numpy(dtype=bool)
    threshold_scores = train_scores if mode == "strict" else valid_scores
    threshold_labels = None if mode == "strict" else y_valid
    threshold, threshold_meta = choose_threshold(
        threshold_scores,
        mode=mode,
        y_valid=threshold_labels,
        contamination=contamination,
    )
    valid_metrics = _evaluate_threshold(y_valid, valid_scores, threshold)
    test_metrics = _evaluate_threshold(y_test, test_scores, threshold)

    result = {
        "mode": mode,
        "feature_names": feature_names,
        "labels_used_for_fit": fit_meta["labels_used_for_fit"],
        "validation_labels_used_for_threshold": threshold_meta[
            "validation_labels_used_for_threshold"
        ],
        "train_fit_samples": int(len(fit_df)),
        "train_normal_samples": int(len(fit_df)),
        "train_positive_excluded": fit_meta["train_positive_excluded"],
        "valid_samples": int(len(valid_df)),
        "test_samples": int(len(test_df)),
        "valid_anomalies": valid_metrics["positive_count"],
        "test_anomalies": test_metrics["positive_count"],
        "threshold": float(threshold),
        "threshold_source": threshold_meta["threshold_source"],
        "validation": valid_metrics,
        "test": test_metrics,
    }
    for prefix, metrics in (("val", valid_metrics), ("test", test_metrics)):
        result[f"{prefix}_precision"] = metrics["precision"]
        result[f"{prefix}_recall"] = metrics["recall"]
        result[f"{prefix}_f1"] = metrics["f1"]
    result["positive_prevalence"] = test_metrics["positive_prevalence"]
    result["predicted_positive_count"] = test_metrics["predicted_positive_count"]
    result["predicted_positive_rate"] = test_metrics["predicted_positive_rate"]
    return result


def _declared_validation_boundary(observable_rows):
    validation_times = observable_rows.loc[
        observable_rows["split"].eq("validation"), "t"
    ]
    if validation_times.empty:
        raise ValueError("observable pool requires a validation split")
    boundary = validation_times.min().normalize()
    train_times = observable_rows.loc[observable_rows["split"].eq("train"), "t"]
    if train_times.empty or not train_times.max() < boundary:
        raise ValueError(
            "the validation UTC calendar boundary must be strictly after all "
            "training events"
        )
    return boundary


def _split_contract(observable_rows, fit_as_of=None):
    ranges = {}
    for split in ("train", "validation", "test"):
        group = observable_rows.loc[observable_rows["split"].eq(split)]
        ranges[split] = {
            "samples": int(len(group)),
            "start_utc": group["t"].min().isoformat() if len(group) else None,
            "end_utc": group["t"].max().isoformat() if len(group) else None,
        }
    return {
        "strategy": "corpus-provided temporal train/validation/test split",
        "fit_labels_as_of": "strictly before declared validation boundary",
        "declared_fit_as_of_utc": fit_as_of,
        "ranges": ranges,
    }


def _official_catch_history_provenance(catch_history):
    if catch_history is None:
        return None
    if not isinstance(catch_history, OfficialCatchHistory):
        raise TypeError("catch_history must be an OfficialCatchHistory")
    return {
        "source_scope": catch_history.source_scope,
        "source_event_count": catch_history.source_event_count,
        "source_event_fingerprint": catch_history.source_event_fingerprint,
        "split_counts": dict(catch_history.split_counts),
    }


def _logical_corpus_name(corpus_dir):
    """Return the generated corpus identity, falling back to its basename."""
    corpus_dir = Path(corpus_dir)
    fallback = corpus_dir.name
    try:
        config = json.loads((corpus_dir / "GENERATION_CONFIG.json").read_text())
    except (OSError, UnicodeError, json.JSONDecodeError):
        return fallback

    scale_key = config.get("scale_key") if isinstance(config, dict) else None
    prefix = "synthetic_cbp_graph_corpus_"
    if not isinstance(scale_key, str):
        return fallback

    suffix = (
        scale_key[len(prefix):]
        if scale_key.startswith(prefix)
        else scale_key
    )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", suffix):
        return fallback
    return prefix + suffix


def corpus_output_path(results_dir, corpus_dir):
    """Return a corpus-qualified diagnostics path for anomaly results.

    ``results_dir`` is the output directory and ``corpus_dir`` supplies the
    corpus basename used to form the qualified filename.  The return value is a
    ``Path`` ending in ``unsupervised_ad_results_<corpus>.json``; it does not
    create directories or write content.  The naming rule avoids collisions
    between synthetic corpus scales while preserving the caller's requested
    output root, and invalid path-like values fail through ``Path`` conversion.
    """
    corpus_name = Path(corpus_dir).name
    prefix = "synthetic_cbp_graph_corpus_"
    suffix = corpus_name[len(prefix):] if corpus_name.startswith(prefix) else corpus_name
    return Path(results_dir) / f"unsupervised_ad_results_{suffix}.json"


def _write_schema_v3_results(output, results_dir, corpus_dir):
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    generic = results_dir / "unsupervised_ad_results.json"
    qualified = corpus_output_path(results_dir, corpus_dir)
    serialized = json.dumps(output, indent=2, ensure_ascii=False) + "\n"
    for destination in (generic, qualified):
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(serialized)
        temporary.replace(destination)
    return {"generic": generic, "qualified": qualified}


def main(
    mode=None,
    contamination=0.1,
    *,
    corpus_dir=None,
    results_dir=None,
    include_deployable_arms=True,
    seed=FC.SEED,
    n_estimators=100,
):
    """Run deployable anomaly arms, freeze scores, then attach oracle-only evaluation.

    ``mode`` selects strict/assisted legacy modes, ``contamination`` controls
    the alert-rate operating point, and the keyword arguments select corpus and
    results paths, whether the four deployable arms run, the random ``seed``,
    and Isolation Forest ``n_estimators``.  The return value is the schema-v3
    results mapping and the function writes generic and corpus-qualified JSON
    diagnostics under ``results_dir``.  Model-visible rows, features, scores,
    and thresholds are frozen from observable inputs before oracle targets are
    admitted; hidden outcomes and official catch history are used only for
    retrospective evaluation, and ``unsupervised_ad`` preserves its explicit
    caught-state as-of boundary.  Invalid modes, corpus contracts, or feature
    alignment raise without silently producing a partial result.
    """
    corpus_dir = Path(corpus_dir) if corpus_dir is not None else FC.CORPUS_DIR
    results_dir = Path(results_dir) if results_dir is not None else FC.RESULTS
    print(f"Loading data from {corpus_dir}...")

    modes = [mode] if mode else ["strict", "assisted"]
    unknown = set(modes) - set(MODE_METADATA)
    if unknown:
        raise ValueError(f"unknown anomaly mode(s): {sorted(unknown)}")

    # Freeze every deployable score before synthetic carrier truth is loaded.
    observable = load_observable_pool(corpus_dir)
    obs2id = _build_oracle(corpus_dir)
    frozen_arms = None
    catch_history = None
    evaluated_arms = {
        arm_id: {} for arm_id in (*PRIMARY_ARM_ORDER, *ABLATION_ARM_ORDER)
    }
    fit_as_of = None
    if include_deployable_arms:
        feature_bundle = build_relational_feature_bundle(
            observable[["event_id", "primary_obs_id", "t"]],
            corpus_dir,
            obs2id,
        )
        fit_as_of = _declared_validation_boundary(observable).isoformat()
        frozen_arms = run_deployable_arms(
            observable,
            feature_bundle,
            fit_as_of=fit_as_of,
            alert_rate=contamination,
            seed=seed,
            n_estimators=n_estimators,
        )
        catch_history = build_official_catch_history(
            observable, set(observable["event_id"])
        )
        # Observable features, deployable scores, and thresholds are frozen
        # above; oracle targets enter only for retrospective evaluation below.
        oracle = load_oracle_evaluation(corpus_dir)
        evaluated_arms = evaluate_frozen_arms(
            frozen_arms, oracle, catch_history
        )

    # Run the schema-v2 legacy modes afterward, retaining their historical API.
    df = load_pool_with_region(corpus_dir)

    results_by_mode = {}

    # Process each region separately for each explicitly described mode.
    regions = df["region"].dropna().unique()
    print(f"Found {len(regions)} regions: {regions}")
    all_features, feature_names = _extract_features(
        df[["event_id", "primary_obs_id", "t"]], corpus_dir, obs2id
    )
    feature_cache = {
        event_id: all_features[i]
        for i, event_id in enumerate(df["event_id"])
    }
    for run_mode in modes:
        print(f"\n=== {MODE_METADATA[run_mode]['label']} ===")
        mode_results = {}
        for region in regions:
            print(f"\n--- Processing Region: {region} ---")
            region_df = df[df["region"] == region].copy()
            if any(
                len(region_df[region_df["split"] == split]) < 50
                for split in ("train", "validation", "test")
            ):
                print(f"Skipping {region} due to insufficient data.")
                continue
            metrics = _run_region(
                region_df, corpus_dir, obs2id, run_mode,
                contamination=contamination,
                feature_cache=feature_cache,
                feature_names=feature_names,
                n_estimators=n_estimators,
            )
            mode_results[region] = metrics
            print(
                f"  Test — P: {metrics['test_precision']:.4f} | "
                f"R: {metrics['test_recall']:.4f} | "
                f"F1: {metrics['test_f1']:.4f}"
            )
        results_by_mode[run_mode] = mode_results

    first_mode = modes[0]
    assisted_results = results_by_mode.get("assisted")
    output = {
        "schema_version": 3,
        "provenance": {
            "corpus_name": _logical_corpus_name(corpus_dir),
            "corpus_path": str(corpus_dir),
            "artifact": "unsupervised_ad_schema_v3",
        },
        "default_mode": first_mode,
        "identity_substrate": (
            "oracle canonical_person_id in this synthetic study; deployable label "
            "and threshold semantics are conditional on a production identity-"
            "resolution system"
        ),
        "feature_names": feature_names,
        "contamination": float(contamination),
        "mode_metadata": {name: MODE_METADATA[name] for name in modes},
        "modes": results_by_mode,
        "primary_arm_order": list(PRIMARY_ARM_ORDER),
        "ablation_arm_order": list(ABLATION_ARM_ORDER),
        "arm_metadata": ARM_METADATA,
        "arms": evaluated_arms,
        "target_contract": {
            "all_carrier_events": "true_contraband_present",
            "missed_at_event": "false_negative_flag",
            "oracle_available_in_production": False,
            "oracle_use": "retrospective evaluation only after scores freeze",
            "observed_operational_target": "seizure_flag",
        },
        "split_contract": _split_contract(observable, fit_as_of),
        "evaluation_provenance": {
            "official_catch_history": _official_catch_history_provenance(
                catch_history
            ),
        },
        "label_provenance": {
            "fit_label": "observable seizure_flag known strictly before fit_as_of",
            "fit_as_of": fit_as_of,
            "immature_outcome_policy": "unlabeled",
            "threshold_policy": "label-free validation score quantile",
            "threshold_labels_used": False,
            "pu_interpretation": (
                "caught-supervised naive PU; no SCAR ranking guarantee"
            ),
        },
        "legacy_oracle_benchmarks": {
            "assisted": {
                "nondeployable": True,
                "is_ceiling": False,
                "description": (
                    "Legacy oracle-label-assisted benchmark retained for context; "
                    "it changes the fit population and oracle-tunes its threshold, "
                    "so it is not a performance ceiling."
                ),
                "results": assisted_results,
            }
        },
    }
    paths = _write_schema_v3_results(output, results_dir, corpus_dir)
    print(f"\nSaved detailed results to {paths['generic']}")
    print(f"Saved corpus-qualified results to {paths['qualified']}")
    return output

if __name__ == "__main__":
    main()
