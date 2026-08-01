"""As-of caught labels and label-free operating-point selection."""

from dataclasses import FrozenInstanceError
import inspect
import json

import numpy as np
import pandas as pd
import pytest
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest

import gnn.pu_learning as pu_learning
from gnn.pu_learning import (
    CaughtSnapshot,
    build_caught_snapshot,
    choose_score_quantile,
    parse_bool_series,
)


FIT_AS_OF = "2024-01-01T00:00:00Z"


def test_parse_bool_series_accepts_bool_and_case_insensitive_strings():
    values = pd.Series([True, False, "true", "FALSE", " True "])

    parsed = parse_bool_series(values)

    assert parsed.dtype == bool
    assert parsed.tolist() == [True, False, True, False, True]


@pytest.mark.parametrize("bad_value", [None, pd.NA, np.nan, "", "unknown", 1])
def test_parse_bool_series_rejects_null_and_unknown_tokens(bad_value):
    with pytest.raises(ValueError, match="boolean"):
        parse_bool_series(pd.Series([True, bad_value], dtype=object))


def test_caught_snapshot_uses_strict_as_of_maturity():
    rows = pd.DataFrame({
        "seizure_flag": [True, True, True, True, False],
        "label_available_time_utc": [
            "2023-12-31T23:59:59Z",
            FIT_AS_OF,
            "2024-01-01T00:00:01Z",
            pd.NaT,
            "2023-12-31T00:00:00Z",
        ],
    })

    snapshot = build_caught_snapshot(rows, FIT_AS_OF)

    assert isinstance(snapshot, CaughtSnapshot)
    assert snapshot.labels.dtype == np.uint8
    assert snapshot.labels.tolist() == [1, 0, 0, 0, 0]
    assert snapshot.fit_as_of == "2024-01-01T00:00:00+00:00"
    assert snapshot.positive_rows == 1
    assert snapshot.immature_rows == 3


def test_caught_snapshot_counts_all_immature_rows_not_only_catches():
    rows = pd.DataFrame({
        "seizure_flag": [False, False, True],
        "label_available_time_utc": [
            FIT_AS_OF,
            "2024-01-02T00:00:00Z",
            None,
        ],
    })

    snapshot = build_caught_snapshot(rows, FIT_AS_OF)

    assert snapshot.labels.tolist() == [0, 0, 0]
    assert snapshot.positive_rows == 0
    assert snapshot.immature_rows == 3


def test_caught_snapshot_is_frozen_and_independent_of_input_mutation():
    rows = pd.DataFrame({
        "seizure_flag": [True],
        "label_available_time_utc": ["2023-12-31T00:00:00Z"],
    })
    original = rows.copy(deep=True)
    snapshot = build_caught_snapshot(rows, FIT_AS_OF)

    pd.testing.assert_frame_equal(rows, original)
    rows.loc[0, "seizure_flag"] = False

    assert snapshot.labels.tolist() == [1]
    with pytest.raises(FrozenInstanceError):
        snapshot.positive_rows = 0


def test_caught_snapshot_labels_are_read_only_so_counts_cannot_diverge():
    rows = pd.DataFrame({
        "seizure_flag": [True],
        "label_available_time_utc": ["2023-12-31T00:00:00Z"],
    })
    snapshot = build_caught_snapshot(rows, FIT_AS_OF)

    with pytest.raises(ValueError, match="read-only"):
        snapshot.labels[0] = 0

    assert snapshot.positive_rows == int(snapshot.labels.sum()) == 1


def test_caught_snapshot_labels_cannot_be_made_writeable():
    rows = pd.DataFrame({
        "seizure_flag": [True],
        "label_available_time_utc": ["2023-12-31T00:00:00Z"],
    })
    snapshot = build_caught_snapshot(rows, FIT_AS_OF)

    with pytest.raises(ValueError):
        snapshot.labels.setflags(write=True)


@pytest.mark.parametrize(
    "columns",
    [
        {"seizure_flag": [True]},
        {"label_available_time_utc": [FIT_AS_OF]},
        {
            "seizure_flag": [True],
            "label_available_time_utc": [FIT_AS_OF],
            "true_contraband_present": [True],
        },
    ],
)
def test_caught_snapshot_requires_exact_observable_columns(columns):
    with pytest.raises(ValueError, match="exactly"):
        build_caught_snapshot(pd.DataFrame(columns), FIT_AS_OF)


@pytest.mark.parametrize("fit_as_of", ["not-a-time", "2024-01-01T00:00:00", None, pd.NaT])
def test_caught_snapshot_rejects_invalid_or_naive_fit_as_of(fit_as_of):
    rows = pd.DataFrame({
        "seizure_flag": [True],
        "label_available_time_utc": ["2023-12-31T00:00:00Z"],
    })

    with pytest.raises(ValueError, match="fit_as_of"):
        build_caught_snapshot(rows, fit_as_of)


def test_caught_snapshot_rejects_malformed_availability_timestamp():
    rows = pd.DataFrame({
        "seizure_flag": [True],
        "label_available_time_utc": ["not-a-time"],
    })

    with pytest.raises(ValueError, match="label_available_time_utc"):
        build_caught_snapshot(rows, FIT_AS_OF)


def test_caught_snapshot_rejects_naive_non_null_availability_timestamp():
    rows = pd.DataFrame({
        "seizure_flag": [True, False],
        "label_available_time_utc": ["2023-12-31T00:00:00", None],
    })

    with pytest.raises(ValueError, match="timezone-aware"):
        build_caught_snapshot(rows, FIT_AS_OF)


def test_caught_snapshot_canonicalizes_offset_timestamps_to_utc():
    rows = pd.DataFrame({
        "seizure_flag": [True],
        "label_available_time_utc": ["2023-12-31T18:59:59-05:00"],
    })

    snapshot = build_caught_snapshot(rows, "2023-12-31T19:00:00-05:00")

    assert snapshot.labels.tolist() == [1]
    assert snapshot.fit_as_of == "2024-01-01T00:00:00+00:00"


def test_operating_threshold_uses_validation_scores_without_labels():
    threshold, metadata = choose_score_quantile(
        [0.1, 0.2, 0.8, 0.9], alert_rate=0.25
    )

    assert threshold == pytest.approx(0.9)
    assert metadata == {
        "threshold_source": "validation_score_quantile",
        "threshold_quantile": 0.75,
        "threshold_source_samples": 4,
        "validation_labels_used_for_threshold": False,
        "labels_used_for_threshold": False,
        "score_direction": "higher_is_more_alert_worthy",
        "threshold_comparator": "greater_equal",
        "realized_validation_alert_rate": 0.25,
    }


def test_operating_threshold_uses_higher_method_for_ties():
    threshold, metadata = choose_score_quantile(
        np.array([0.1, 0.2, 0.2, 0.9]), alert_rate=0.5
    )

    assert threshold == pytest.approx(0.2)
    assert metadata["threshold_quantile"] == pytest.approx(0.5)


def test_tied_score_threshold_reports_greater_equal_oversubscription():
    scores = np.array([0.1, 0.2, 0.2, 0.9])

    threshold, metadata = choose_score_quantile(scores, alert_rate=0.5)
    selected = pu_learning.apply_score_threshold(scores, threshold)

    assert selected.tolist() == [False, True, True, True]
    assert metadata["threshold_comparator"] == "greater_equal"
    assert metadata["realized_validation_alert_rate"] == pytest.approx(0.75)


@pytest.mark.parametrize("scores", [[], [[0.1]], [0.1, np.nan], [np.inf]])
def test_apply_score_threshold_requires_finite_nonempty_1d_scores(scores):
    with pytest.raises(ValueError):
        pu_learning.apply_score_threshold(scores, 0.1)


def test_apply_score_threshold_rejects_unsupported_comparator():
    with pytest.raises(ValueError, match="comparator"):
        pu_learning.apply_score_threshold([0.1, 0.2], 0.1, comparator="greater")


@pytest.mark.parametrize(
    "scores, alert_rate",
    [
        ([], 0.1),
        ([[0.1, 0.2]], 0.1),
        ([0.1, np.nan], 0.1),
        ([0.1, np.inf], 0.1),
        ([0.1], 0.0),
        ([0.1], -0.1),
        ([0.1], 1.1),
        ([0.1], np.nan),
    ],
)
def test_operating_threshold_rejects_invalid_inputs(scores, alert_rate):
    with pytest.raises(ValueError):
        choose_score_quantile(scores, alert_rate=alert_rate)


def test_public_apis_do_not_accept_oracle_or_validation_labels():
    assert list(inspect.signature(build_caught_snapshot).parameters) == [
        "rows",
        "fit_as_of",
    ]
    assert list(inspect.signature(choose_score_quantile).parameters) == [
        "validation_scores",
        "alert_rate",
    ]

    with pytest.raises(TypeError):
        choose_score_quantile([0.1], labels=[1])


def _caught_runner_inputs():
    rng = np.random.default_rng(7)
    negatives = rng.normal(-2.0, 0.25, size=(80, 2))
    positives = rng.normal(2.0, 0.25, size=(80, 2))
    X_train = np.vstack([negatives, positives])
    y_caught = np.array([0] * len(negatives) + [1] * len(positives))
    X_validation = np.array([[-2.0, -2.0], [2.0, 2.0]])
    X_test = np.array([[-1.8, -2.2], [1.8, 2.2]])
    return X_train, y_caught, X_validation, X_test


def _unlabeled_runner_inputs():
    rng = np.random.default_rng(11)
    X_train = rng.normal(0.0, 0.3, size=(200, 2))
    X_validation = np.array([[0.0, 0.0], [8.0, 8.0]])
    X_test = np.array([[0.1, -0.1], [-8.0, -8.0]])
    return X_train, X_validation, X_test


def test_caught_supervised_scores_trivial_signal_and_reports_provenance():
    X_train, y_caught, X_validation, X_test = _caught_runner_inputs()

    result = pu_learning.fit_caught_supervised(
        X_train, y_caught, X_validation, X_test, seed=17
    )

    assert isinstance(result, pu_learning.FrozenScores)
    assert result.validation_scores[1] > result.validation_scores[0]
    assert result.test_scores[1] > result.test_scores[0]
    assert result.model_metadata == {
        "class": "HistGradientBoostingClassifier",
        "parameters": {
            "categorical_features": "from_dtype",
            "class_weight": "balanced",
            "early_stopping": False,
            "interaction_cst": None,
            "l2_regularization": 0.0,
            "learning_rate": 0.1,
            "loss": "log_loss",
            "max_bins": 255,
            "max_depth": None,
            "max_features": 1.0,
            "max_iter": 100,
            "max_leaf_nodes": 31,
            "min_samples_leaf": 20,
            "monotonic_cst": None,
            "n_iter_no_change": 10,
            "random_state": 17,
            "scoring": "loss",
            "tol": 1e-7,
            "validation_fraction": None,
            "verbose": 0,
            "warm_start": False,
        },
        "seed": 17,
        "sklearn_version": sklearn.__version__,
        "fit_signal": "caught_vs_unlabeled",
        "labels_used_for_fit": True,
        "score_direction": "higher_is_more_alert_worthy",
    }
    json.dumps(result.model_metadata)


def test_caught_supervised_learns_a_strongly_imbalanced_caught_signal():
    rng = np.random.default_rng(23)
    unlabeled = rng.normal(-2.0, 0.2, size=(300, 2))
    caught = rng.normal(2.0, 0.2, size=(20, 2))
    X_train = np.vstack([unlabeled, caught])
    y_caught = np.array([0] * len(unlabeled) + [1] * len(caught))
    evaluation = np.array([[-2.0, -2.0], [2.0, 2.0]])

    result = pu_learning.fit_caught_supervised(
        X_train, y_caught, evaluation, evaluation, seed=29
    )

    assert result.validation_scores[1] > result.validation_scores[0]
    assert result.model_metadata["parameters"]["class_weight"] == "balanced"
    assert result.model_metadata["parameters"]["early_stopping"] is False
    assert result.model_metadata["parameters"]["validation_fraction"] is None


def test_caught_supervised_is_exactly_deterministic_and_freezes_scores():
    inputs = _caught_runner_inputs()

    first = pu_learning.fit_caught_supervised(*inputs, seed=3)
    second = pu_learning.fit_caught_supervised(*inputs, seed=3)

    assert np.array_equal(first.validation_scores, second.validation_scores)
    assert np.array_equal(first.test_scores, second.test_scores)
    assert not np.shares_memory(first.validation_scores, first.test_scores)
    assert not first.validation_scores.flags.writeable
    assert not first.test_scores.flags.writeable
    with pytest.raises(ValueError, match="read-only"):
        first.validation_scores[0] = 0.0


def test_frozen_score_arrays_cannot_be_made_writeable():
    result = pu_learning.fit_caught_supervised(*_caught_runner_inputs())

    for scores in (result.validation_scores, result.test_scores):
        with pytest.raises(ValueError):
            scores.setflags(write=True)


def test_model_metadata_is_deeply_immutable_and_json_serializable():
    result = pu_learning.fit_caught_supervised(*_caught_runner_inputs())

    with pytest.raises(TypeError):
        result.model_metadata["parameters"]["max_iter"] = 1

    json.dumps(result.model_metadata)


def test_caught_supervised_one_class_error_names_both_required_groups():
    X_train, _, X_validation, X_test = _caught_runner_inputs()

    with pytest.raises(ValueError, match="both caught and unlabeled"):
        pu_learning.fit_caught_supervised(
            X_train, np.zeros(X_train.shape[0]), X_validation, X_test
        )


@pytest.mark.parametrize(
    "y_caught",
    [
        np.zeros(160),
        np.ones(160),
        np.array([0, 1] * 79 + [0, 2]),
        np.array([0, 1] * 79 + [0, np.nan]),
        np.array([[0, 1]] * 80),
        np.array([0, 1]),
    ],
)
def test_caught_supervised_rejects_one_class_or_invalid_labels(y_caught):
    X_train, _, X_validation, X_test = _caught_runner_inputs()

    with pytest.raises(ValueError, match="y_caught"):
        pu_learning.fit_caught_supervised(
            X_train, y_caught, X_validation, X_test
        )


@pytest.mark.parametrize(
    "matrix_name, replacement",
    [
        ("X_train", []),
        ("X_train", [1.0, 2.0]),
        ("X_train", [[1.0, np.nan]]),
        ("X_validation", np.empty((0, 2))),
        ("X_validation", [[1.0, np.inf]]),
        ("X_validation", [["a", "b"]]),
        ("X_test", [[[1.0, 2.0]]]),
        ("X_test", [[1.0, 2.0, 3.0]]),
    ],
)
def test_model_runners_reject_invalid_feature_matrices(matrix_name, replacement):
    X_train, y_caught, X_validation, X_test = _caught_runner_inputs()
    values = {
        "X_train": X_train,
        "X_validation": X_validation,
        "X_test": X_test,
    }
    values[matrix_name] = replacement

    with pytest.raises(ValueError, match=matrix_name):
        pu_learning.fit_caught_supervised(
            values["X_train"],
            y_caught,
            values["X_validation"],
            values["X_test"],
        )

    if matrix_name != "X_train":
        with pytest.raises(ValueError, match=matrix_name):
            pu_learning.fit_unlabeled_anomaly(
                values["X_train"],
                values["X_validation"],
                values["X_test"],
            )


def test_model_runners_reject_training_feature_width_mismatches():
    X_train, y_caught, X_validation, X_test = _caught_runner_inputs()
    narrower_train = X_train[:, :1]

    with pytest.raises(ValueError, match="feature width"):
        pu_learning.fit_caught_supervised(
            narrower_train, y_caught, X_validation, X_test
        )
    with pytest.raises(ValueError, match="feature width"):
        pu_learning.fit_unlabeled_anomaly(
            narrower_train, X_validation, X_test
        )


def test_unlabeled_anomaly_scores_outlier_higher_and_reports_provenance():
    X_train, X_validation, X_test = _unlabeled_runner_inputs()

    result = pu_learning.fit_unlabeled_anomaly(
        X_train, X_validation, X_test, seed=19, n_estimators=37
    )

    assert isinstance(result, pu_learning.FrozenScores)
    assert result.validation_scores[1] > result.validation_scores[0]
    assert result.test_scores[1] > result.test_scores[0]
    assert result.model_metadata == {
        "class": "IsolationForest",
        "parameters": {
            "bootstrap": False,
            "contamination": "auto",
            "max_features": 1.0,
            "max_samples": "auto",
            "n_estimators": 37,
            "n_jobs": -1,
            "random_state": 19,
            "verbose": 0,
            "warm_start": False,
        },
        "seed": 19,
        "sklearn_version": sklearn.__version__,
        "fit_signal": "unlabeled_feature_distribution",
        "labels_used_for_fit": False,
        "score_direction": "higher_is_more_alert_worthy",
    }
    json.dumps(result.model_metadata)


def test_unlabeled_anomaly_is_exactly_deterministic_and_freezes_scores():
    inputs = _unlabeled_runner_inputs()

    first = pu_learning.fit_unlabeled_anomaly(*inputs, seed=5, n_estimators=23)
    second = pu_learning.fit_unlabeled_anomaly(*inputs, seed=5, n_estimators=23)

    assert np.array_equal(first.validation_scores, second.validation_scores)
    assert np.array_equal(first.test_scores, second.test_scores)
    assert not np.shares_memory(first.validation_scores, first.test_scores)
    assert not first.validation_scores.flags.writeable
    assert not first.test_scores.flags.writeable


@pytest.mark.parametrize("n_estimators", [True, False, 0, -1, 1.5, "10"])
def test_unlabeled_anomaly_rejects_non_positive_integer_estimator_counts(
    n_estimators,
):
    inputs = _unlabeled_runner_inputs()

    with pytest.raises(ValueError, match="n_estimators"):
        pu_learning.fit_unlabeled_anomaly(
            *inputs, n_estimators=n_estimators
        )


@pytest.mark.parametrize("seed", [-1, 2**32])
def test_model_runners_reject_seed_outside_uint32_range(seed):
    caught_inputs = _caught_runner_inputs()
    anomaly_inputs = _unlabeled_runner_inputs()

    with pytest.raises(ValueError, match="seed"):
        pu_learning.fit_caught_supervised(*caught_inputs, seed=seed)
    with pytest.raises(ValueError, match="seed"):
        pu_learning.fit_unlabeled_anomaly(*anomaly_inputs, seed=seed)


@pytest.mark.parametrize("seed", [0, 2**32 - 1])
def test_model_runners_accept_inclusive_uint32_seed_boundaries(seed):
    caught = pu_learning.fit_caught_supervised(
        *_caught_runner_inputs(), seed=seed
    )
    anomaly = pu_learning.fit_unlabeled_anomaly(
        *_unlabeled_runner_inputs(), seed=seed, n_estimators=3
    )

    assert caught.model_metadata["seed"] == seed
    assert anomaly.model_metadata["seed"] == seed


def test_caught_supervised_constructs_and_fits_one_real_estimator(monkeypatch):
    constructed = []
    fitted_ids = []
    predicted_ids = []

    class TrackingHGB(HistGradientBoostingClassifier):
        def __new__(cls, *args, **kwargs):
            instance = super().__new__(cls)
            constructed.append(instance)
            return instance

        def fit(self, X, y, **fit_params):
            fitted_ids.append(id(self))
            return super().fit(X, y, **fit_params)

        def predict_proba(self, X):
            predicted_ids.append(id(self))
            return super().predict_proba(X)

    monkeypatch.setattr(
        pu_learning, "HistGradientBoostingClassifier", TrackingHGB
    )
    inputs = _caught_runner_inputs()

    result = pu_learning.fit_caught_supervised(*inputs)

    assert result.validation_scores.shape == (2,)
    assert result.test_scores.shape == (2,)
    assert result.model_metadata["class"] == "TrackingHGB"
    assert len(constructed) == 1
    assert fitted_ids == [id(constructed[0])]
    assert predicted_ids == [id(constructed[0]), id(constructed[0])]


def test_unlabeled_anomaly_constructs_and_fits_one_real_estimator(monkeypatch):
    constructed = []
    fitted_ids = []
    scored_ids = []

    class TrackingIsolationForest(IsolationForest):
        def __new__(cls, *args, **kwargs):
            instance = super().__new__(cls)
            constructed.append(instance)
            return instance

        def fit(self, X, y=None, sample_weight=None):
            fitted_ids.append(id(self))
            return super().fit(X, y=y, sample_weight=sample_weight)

        def decision_function(self, X):
            scored_ids.append(id(self))
            return super().decision_function(X)

    monkeypatch.setattr(
        pu_learning, "IsolationForest", TrackingIsolationForest
    )
    inputs = _unlabeled_runner_inputs()

    result = pu_learning.fit_unlabeled_anomaly(*inputs, n_estimators=13)

    assert result.validation_scores.shape == (2,)
    assert result.test_scores.shape == (2,)
    assert result.model_metadata["class"] == "TrackingIsolationForest"
    assert len(constructed) == 1
    assert fitted_ids == [id(constructed[0])]
    assert scored_ids == [id(constructed[0]), id(constructed[0])]
