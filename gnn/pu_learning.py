"""Leak-free helpers for caught-supervised learning.

This module deliberately keeps observable caught-label construction separate
from any synthetic carrier truth used by retrospective evaluation.
"""

from dataclasses import dataclass
import json

import numpy as np
import pandas as pd
from sklearn import __version__ as sklearn_version
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest


_SNAPSHOT_COLUMNS = frozenset({"seizure_flag", "label_available_time_utc"})


def _immutable_array_copy(values, *, dtype=None) -> np.ndarray:
    copied = np.array(values, dtype=dtype, copy=True, order="C")
    immutable = np.frombuffer(copied.tobytes(order="C"), dtype=copied.dtype)
    return immutable.reshape(copied.shape)


class _FrozenJSONDict(dict):
    """A ``json.dumps`` compatible mapping that rejects mutation."""

    @staticmethod
    def _immutable(*args, **kwargs):
        raise TypeError("model metadata is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __ior__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable


def _deeply_freeze_json(value):
    if isinstance(value, dict):
        return _FrozenJSONDict({
            key: _deeply_freeze_json(item) for key, item in value.items()
        })
    if isinstance(value, list):
        return tuple(_deeply_freeze_json(item) for item in value)
    return value


def parse_bool_series(series: pd.Series) -> pd.Series:
    """Parse booleans and ``true``/``false`` strings without silent coercion."""
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series")

    parsed: list[bool] = []
    invalid: list[object] = []
    for index, value in series.items():
        if isinstance(value, (bool, np.bool_)):
            parsed.append(bool(value))
        elif isinstance(value, str) and value.strip().casefold() in {"true", "false"}:
            parsed.append(value.strip().casefold() == "true")
        else:
            invalid.append(index)

    if invalid:
        raise ValueError(
            "Invalid boolean value(s) at series indices "
            f"{invalid}; expected non-null true/false values"
        )
    return pd.Series(parsed, index=series.index.copy(), name=series.name, dtype=bool)


@dataclass(frozen=True)
class CaughtSnapshot:
    """Caught labels that were observable strictly before a fit cutoff."""

    labels: np.ndarray
    fit_as_of: str
    positive_rows: int
    immature_rows: int


def _canonical_utc_timestamp(value: object) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("fit_as_of must be a valid timezone-aware timestamp") from error
    if pd.isna(timestamp) or timestamp.tzinfo is None:
        raise ValueError("fit_as_of must be a valid timezone-aware timestamp")
    return timestamp.tz_convert("UTC")


def build_caught_snapshot(rows: pd.DataFrame, fit_as_of: object) -> CaughtSnapshot:
    """Build observable caught-vs-unlabeled labels at ``fit_as_of``.

    Only the caught outcome and its availability timestamp are accepted. A
    label that becomes available exactly at the cutoff remains unlabeled.
    Every non-null availability timestamp must carry timezone information.
    """
    if not isinstance(rows, pd.DataFrame):
        raise TypeError("rows must be a pandas DataFrame")
    if set(rows.columns) != _SNAPSHOT_COLUMNS:
        raise ValueError(
            "rows must contain exactly seizure_flag and label_available_time_utc"
        )

    cutoff = _canonical_utc_timestamp(fit_as_of)
    caught = parse_bool_series(rows["seizure_flag"])
    raw_availability = rows["label_available_time_utc"]

    malformed_indices: list[object] = []
    naive_indices: list[object] = []
    for index, value in raw_availability.items():
        if pd.isna(value):
            continue
        try:
            timestamp = pd.Timestamp(value)
        except (TypeError, ValueError, OverflowError):
            malformed_indices.append(index)
            continue
        if pd.isna(timestamp):
            malformed_indices.append(index)
        elif timestamp.tzinfo is None:
            naive_indices.append(index)

    if malformed_indices:
        raise ValueError(
            "label_available_time_utc contains an invalid timestamp at indices "
            f"{malformed_indices}"
        )
    if naive_indices:
        raise ValueError(
            "label_available_time_utc values must be timezone-aware at indices "
            f"{naive_indices}"
        )

    try:
        availability = pd.to_datetime(
            raw_availability,
            utc=True,
            errors="coerce",
            format="mixed",
        )
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(
            "label_available_time_utc contains an invalid timestamp"
        ) from error

    malformed = availability.isna() & raw_availability.notna()
    if malformed.any():
        bad_indices = raw_availability.index[malformed].tolist()
        raise ValueError(
            "label_available_time_utc contains an invalid timestamp at indices "
            f"{bad_indices}"
        )

    available = availability < cutoff
    labels = (
        caught.to_numpy(dtype=bool, copy=True)
        & available.to_numpy(dtype=bool, copy=True)
    ).astype(np.uint8, copy=True)
    labels = _immutable_array_copy(labels)
    return CaughtSnapshot(
        labels=labels,
        fit_as_of=cutoff.isoformat(),
        positive_rows=int(labels.sum()),
        immature_rows=int((~available).sum()),
    )


def _finite_1d_scores(scores, *, argument_name: str) -> np.ndarray:
    try:
        values = np.asarray(scores, dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{argument_name} must be numeric") from error
    if values.ndim != 1 or values.size == 0:
        raise ValueError(f"{argument_name} must be a nonempty 1D sequence")
    if not np.isfinite(values).all():
        raise ValueError(f"{argument_name} must contain only finite values")
    return values


def apply_score_threshold(
    scores,
    threshold: float,
    comparator: str = "greater_equal",
) -> np.ndarray:
    """Select finite 1D scores using the supported ``scores >= threshold`` rule."""
    if comparator != "greater_equal":
        raise ValueError("comparator must be 'greater_equal'")
    values = _finite_1d_scores(scores, argument_name="scores")
    try:
        cutoff = float(threshold)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("threshold must be finite") from error
    if not np.isfinite(cutoff):
        raise ValueError("threshold must be finite")
    return values >= cutoff


def choose_score_quantile(validation_scores, alert_rate: float = 0.1):
    """Choose a validation quantile and report ``>=`` tie oversubscription."""
    scores = _finite_1d_scores(
        validation_scores,
        argument_name="validation_scores",
    )

    if isinstance(alert_rate, (bool, np.bool_)):
        raise ValueError("alert_rate must satisfy 0 < alert_rate <= 1")
    try:
        rate = float(alert_rate)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("alert_rate must satisfy 0 < alert_rate <= 1") from error
    if not np.isfinite(rate) or not 0.0 < rate <= 1.0:
        raise ValueError("alert_rate must satisfy 0 < alert_rate <= 1")

    quantile = 1.0 - rate
    threshold = float(np.quantile(scores, quantile, method="higher"))
    selected = apply_score_threshold(scores, threshold)
    metadata = {
        "threshold_source": "validation_score_quantile",
        "threshold_quantile": quantile,
        "threshold_source_samples": int(scores.size),
        "validation_labels_used_for_threshold": False,
        "labels_used_for_threshold": False,
        "score_direction": "higher_is_more_alert_worthy",
        "threshold_comparator": "greater_equal",
        "realized_validation_alert_rate": float(selected.mean()),
    }
    return threshold, metadata


def _frozen_score_array(scores, *, name: str) -> np.ndarray:
    try:
        values = np.array(scores, dtype=float, copy=True)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be numeric") from error
    if values.ndim != 1 or values.size == 0:
        raise ValueError(f"{name} must be a nonempty 1D array")
    if not np.isfinite(values).all():
        raise ValueError(f"{name} must contain only finite values")
    return _immutable_array_copy(values)


@dataclass(frozen=True)
class FrozenScores:
    """Validation and test scores detached from a fitted estimator."""

    validation_scores: np.ndarray
    test_scores: np.ndarray
    model_metadata: dict

    def __post_init__(self):
        validation_scores = _frozen_score_array(
            self.validation_scores, name="validation_scores"
        )
        test_scores = _frozen_score_array(self.test_scores, name="test_scores")
        try:
            serialized_metadata = json.dumps(self.model_metadata)
        except (TypeError, ValueError) as error:
            raise ValueError("model_metadata must be JSON-serializable") from error

        object.__setattr__(self, "validation_scores", validation_scores)
        object.__setattr__(self, "test_scores", test_scores)
        object.__setattr__(
            self,
            "model_metadata",
            _deeply_freeze_json(json.loads(serialized_metadata)),
        )


def _feature_matrix(values, *, name: str) -> np.ndarray:
    try:
        array = np.asarray(values)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a numeric 2D matrix") from error
    if array.ndim != 2 or array.size == 0 or 0 in array.shape:
        raise ValueError(f"{name} must be a nonempty 2D matrix")
    if not np.issubdtype(array.dtype, np.number):
        raise ValueError(f"{name} must be a numeric 2D matrix")
    try:
        numeric = np.array(array, dtype=float, copy=True)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be a numeric 2D matrix") from error
    if not np.isfinite(numeric).all():
        raise ValueError(f"{name} must contain only finite values")
    return numeric


def _validated_feature_splits(X_train, X_validation, X_test):
    train = _feature_matrix(X_train, name="X_train")
    validation = _feature_matrix(X_validation, name="X_validation")
    test = _feature_matrix(X_test, name="X_test")
    if validation.shape[1] != train.shape[1]:
        raise ValueError(
            "X_validation feature width must match X_train feature width"
        )
    if test.shape[1] != train.shape[1]:
        raise ValueError("X_test feature width must match X_train feature width")
    return train, validation, test


def _caught_labels(y_caught, *, expected_rows: int) -> np.ndarray:
    try:
        labels = np.asarray(y_caught)
    except (TypeError, ValueError) as error:
        raise ValueError("y_caught must be a 1D binary array") from error
    if labels.ndim != 1 or labels.size != expected_rows:
        raise ValueError("y_caught must be 1D and aligned to X_train")
    if not (
        np.issubdtype(labels.dtype, np.number)
        or np.issubdtype(labels.dtype, np.bool_)
    ):
        raise ValueError("y_caught must contain only binary 0/1 labels")
    try:
        finite_labels = np.asarray(labels, dtype=float)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("y_caught must contain only binary 0/1 labels") from error
    if not np.isfinite(finite_labels).all() or not np.isin(
        finite_labels, [0.0, 1.0]
    ).all():
        raise ValueError("y_caught must contain only binary 0/1 labels")
    if np.unique(finite_labels).size != 2:
        raise ValueError(
            "y_caught must contain both caught and unlabeled classes"
        )
    return finite_labels.astype(np.uint8, copy=True)


def _integer_seed(seed) -> int:
    if isinstance(seed, (bool, np.bool_)) or not isinstance(
        seed, (int, np.integer)
    ):
        raise ValueError("seed must be an integer")
    seed = int(seed)
    if not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed must be in the inclusive range 0 to 2**32 - 1")
    return seed


def fit_caught_supervised(
    X_train,
    y_caught,
    X_validation,
    X_test,
    *,
    seed=42,
):
    """Fit one caught-vs-unlabeled HGB model and freeze both score splits."""
    train, validation, test = _validated_feature_splits(
        X_train, X_validation, X_test
    )
    labels = _caught_labels(y_caught, expected_rows=train.shape[0])
    seed = _integer_seed(seed)
    params = {
        "learning_rate": 0.1,
        "max_iter": 100,
        "max_leaf_nodes": 31,
        "min_samples_leaf": 20,
        "l2_regularization": 0.0,
        "class_weight": "balanced",
        "random_state": seed,
        "early_stopping": False,
        "validation_fraction": None,
    }
    model = HistGradientBoostingClassifier(**params)
    model.fit(train, labels)
    validation_scores = model.predict_proba(validation)[:, 1]
    test_scores = model.predict_proba(test)[:, 1]
    return FrozenScores(
        validation_scores=validation_scores,
        test_scores=test_scores,
        model_metadata={
            "class": type(model).__name__,
            "parameters": model.get_params(deep=False),
            "seed": seed,
            "sklearn_version": sklearn_version,
            "fit_signal": "caught_vs_unlabeled",
            "labels_used_for_fit": True,
            "score_direction": "higher_is_more_alert_worthy",
        },
    )


def fit_unlabeled_anomaly(
    X_train,
    X_validation,
    X_test,
    *,
    seed=42,
    n_estimators=100,
):
    """Fit one label-free Isolation Forest and freeze both score splits."""
    train, validation, test = _validated_feature_splits(
        X_train, X_validation, X_test
    )
    seed = _integer_seed(seed)
    if isinstance(n_estimators, (bool, np.bool_)) or not isinstance(
        n_estimators, (int, np.integer)
    ) or n_estimators <= 0:
        raise ValueError("n_estimators must be a positive integer")
    n_estimators = int(n_estimators)
    params = {
        "contamination": "auto",
        "n_estimators": n_estimators,
        "random_state": seed,
        "n_jobs": -1,
        "max_samples": "auto",
    }
    model = IsolationForest(**params)
    model.fit(train)
    validation_scores = -model.decision_function(validation)
    test_scores = -model.decision_function(test)
    return FrozenScores(
        validation_scores=validation_scores,
        test_scores=test_scores,
        model_metadata={
            "class": type(model).__name__,
            "parameters": model.get_params(deep=False),
            "seed": seed,
            "sklearn_version": sklearn_version,
            "fit_signal": "unlabeled_feature_distribution",
            "labels_used_for_fit": False,
            "score_direction": "higher_is_more_alert_worthy",
        },
    )
