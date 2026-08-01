import numpy as np
import pandas as pd
import pytest
from sklearn.preprocessing import OrdinalEncoder

from gnn.demo_baseline import FEATURE_NAMES
from gnn.unsupervised_features import (
    RELATIONAL_PROXY_FEATURES,
    build_relational_feature_bundle,
    encode_feature_splits,
)


CATEGORICAL_NAMES = frozenset(
    {
        "sex",
        "citizenship_country",
        "residence_country",
        "region",
        "mode_of_transportation",
        "travel_category",
        "declared_trip_purpose",
        "day_of_week",
    }
)


def _write_crossings(corpus, rows):
    pd.DataFrame(rows).to_csv(corpus / "crossing_events.csv", index=False)


def _crossing(event_id, obs_id, *, offset):
    return {
        "event_id": event_id,
        "observed_person_record_id": obs_id,
        "party_size": 2 + offset,
        "repeat_crossing_count_prior_365d": 10 + offset,
        "same_vehicle_crossing_count_prior_365d": 20 + offset,
        "same_document_crossing_count_prior_365d": 30 + offset,
        "sex": f"unused-{offset}",
        "citizenship_country": f"citizenship-{offset}",
        "residence_country": f"residence-{offset}",
        "region": f"region-{offset}",
        "mode_of_transportation": f"mode-{offset}",
        "travel_category": f"category-{offset}",
        "declared_trip_purpose": f"purpose-{offset}",
        "day_of_week": f"day-{offset}",
    }


def _stub_baseline(rows, corpus_dir, obs_to_identity):
    del corpus_dir, obs_to_identity
    values = np.arange(len(rows) * len(FEATURE_NAMES), dtype=float)
    return values.reshape(len(rows), len(FEATURE_NAMES)), list(FEATURE_NAMES)


def test_relational_bundle_preserves_requested_order_names_and_values(
    tmp_path, monkeypatch
):
    _write_crossings(
        tmp_path,
        [
            _crossing("E1", "O1", offset=1),
            _crossing("E2", "O2", offset=2),
        ],
    )
    pd.DataFrame(
        {
            "observed_person_record_id": ["O1", "O2"],
            "observed_sex_marker": ["F", "M"],
        }
    ).to_csv(tmp_path / "observed_person_records.csv", index=False)
    monkeypatch.setattr(
        "gnn.unsupervised_features.build_baseline_features", _stub_baseline
    )
    rows = pd.DataFrame(
        {
            "event_id": ["E2", "E1"],
            "primary_obs_id": ["O2", "O1"],
            "t": pd.to_datetime(
                ["2023-01-02T00:00:00Z", "2023-01-01T00:00:00Z"]
            ),
        }
    )

    bundle = build_relational_feature_bundle(rows, tmp_path, {})

    assert RELATIONAL_PROXY_FEATURES == [
        "party_size",
        "repeat_crossing_count_prior_365d",
        "same_vehicle_crossing_count_prior_365d",
        "same_document_crossing_count_prior_365d",
    ]
    assert bundle.event_ids == ["E2", "E1"]
    assert bundle.names == FEATURE_NAMES + RELATIONAL_PROXY_FEATURES
    assert bundle.matrix.shape == (2, 18)
    np.testing.assert_array_equal(
        bundle.matrix[:, : len(FEATURE_NAMES)],
        np.arange(2 * len(FEATURE_NAMES), dtype=float).reshape(
            2, len(FEATURE_NAMES)
        ),
    )
    np.testing.assert_array_equal(
        bundle.matrix[:, -4:],
        np.array([[4.0, 12.0, 22.0, 32.0], [3.0, 11.0, 21.0, 31.0]]),
    )
    assert bundle.categorical_names == CATEGORICAL_NAMES
    assert bundle.display.columns.tolist() == bundle.names
    assert bundle.display["region"].tolist() == ["region-2", "region-1"]
    assert bundle.display["sex"].tolist() == ["M", "F"]
    assert bundle.display["age_bucket"].tolist() == [
        bundle.matrix[0, FEATURE_NAMES.index("age_bucket")],
        bundle.matrix[1, FEATURE_NAMES.index("age_bucket")],
    ]
    assert bundle.display[RELATIONAL_PROXY_FEATURES].to_numpy().tolist() == [
        [4, 12, 22, 32],
        [3, 11, 21, 31],
    ]


def test_relational_bundle_rejects_duplicate_requested_event_ids(
    tmp_path, monkeypatch
):
    _write_crossings(tmp_path, [_crossing("E1", "O1", offset=1)])
    monkeypatch.setattr(
        "gnn.unsupervised_features.build_baseline_features", _stub_baseline
    )
    rows = pd.DataFrame(
        {
            "event_id": ["E1", "E1"],
            "primary_obs_id": ["O1", "O1"],
            "t": pd.to_datetime(
                ["2023-01-01T00:00:00Z", "2023-01-02T00:00:00Z"]
            ),
        }
    )

    with pytest.raises(ValueError, match="duplicate.*event_id"):
        build_relational_feature_bundle(rows, tmp_path, {})


def test_relational_bundle_rejects_duplicate_source_event_ids(
    tmp_path, monkeypatch
):
    _write_crossings(
        tmp_path,
        [
            _crossing("E1", "O1", offset=1),
            _crossing("E1", "O1", offset=2),
        ],
    )

    def baseline_must_not_run(*args, **kwargs):
        raise AssertionError("baseline must not run")

    monkeypatch.setattr(
        "gnn.unsupervised_features.build_baseline_features", baseline_must_not_run
    )
    rows = pd.DataFrame(
        {
            "event_id": ["E1"],
            "primary_obs_id": ["O1"],
            "t": pd.to_datetime(["2023-01-01T00:00:00Z"]),
        }
    )

    with pytest.raises(ValueError, match="duplicate.*event_id"):
        build_relational_feature_bundle(rows, tmp_path, {})


def test_relational_bundle_rejects_missing_requested_event_ids(
    tmp_path, monkeypatch
):
    _write_crossings(tmp_path, [_crossing("E1", "O1", offset=1)])
    monkeypatch.setattr(
        "gnn.unsupervised_features.build_baseline_features", _stub_baseline
    )
    rows = pd.DataFrame(
        {
            "event_id": ["E2"],
            "primary_obs_id": ["O2"],
            "t": pd.to_datetime(["2023-01-02T00:00:00Z"]),
        }
    )

    with pytest.raises(KeyError, match="missing.*event IDs.*E2"):
        build_relational_feature_bundle(rows, tmp_path, {})


def test_relational_bundle_rejects_missing_proxy_columns(tmp_path, monkeypatch):
    crossing = _crossing("E1", "O1", offset=1)
    crossing.pop("same_document_crossing_count_prior_365d")
    _write_crossings(tmp_path, [crossing])
    monkeypatch.setattr(
        "gnn.unsupervised_features.build_baseline_features", _stub_baseline
    )
    rows = pd.DataFrame(
        {
            "event_id": ["E1"],
            "primary_obs_id": ["O1"],
            "t": pd.to_datetime(["2023-01-01T00:00:00Z"]),
        }
    )

    with pytest.raises(
        ValueError, match="missing required proxy columns.*same_document"
    ):
        build_relational_feature_bundle(rows, tmp_path, {})


def test_relational_bundle_rejects_missing_raw_event_categorical_column(
    tmp_path, monkeypatch
):
    crossing = _crossing("E1", "O1", offset=1)
    crossing.pop("region")
    _write_crossings(tmp_path, [crossing])

    def baseline_must_not_run(*args, **kwargs):
        raise AssertionError("baseline must not run")

    monkeypatch.setattr(
        "gnn.unsupervised_features.build_baseline_features", baseline_must_not_run
    )
    rows = pd.DataFrame(
        {
            "event_id": ["E1"],
            "primary_obs_id": ["O1"],
            "t": pd.to_datetime(["2023-01-01T00:00:00Z"]),
        }
    )

    with pytest.raises(
        ValueError, match="missing required raw event categorical columns.*region"
    ):
        build_relational_feature_bundle(rows, tmp_path, {})


@pytest.mark.parametrize(
    ("observed_variant", "expected_message"),
    [
        ("missing_file", "observed_person_records.csv is required"),
        (
            "missing_column",
            "missing required observed-person columns.*observed_sex_marker",
        ),
        ("duplicate_id", "duplicate observed_person_record_id"),
        ("missing_requested", "missing observed sex.*O2"),
        ("null_sex", "null observed sex.*O1"),
    ],
)
def test_relational_bundle_requires_complete_raw_observed_sex(
    tmp_path, monkeypatch, observed_variant, expected_message
):
    _write_crossings(tmp_path, [_crossing("E1", "O1", offset=1)])
    observed_rows = pd.DataFrame(
        {
            "observed_person_record_id": ["O1"],
            "observed_sex_marker": ["F"],
        }
    )
    requested_obs_id = "O1"
    if observed_variant == "missing_column":
        observed_rows = observed_rows.drop(columns="observed_sex_marker")
    elif observed_variant == "duplicate_id":
        observed_rows = pd.concat([observed_rows, observed_rows], ignore_index=True)
    elif observed_variant == "missing_requested":
        requested_obs_id = "O2"
    elif observed_variant == "null_sex":
        observed_rows.loc[0, "observed_sex_marker"] = None
    if observed_variant != "missing_file":
        observed_rows.to_csv(tmp_path / "observed_person_records.csv", index=False)

    monkeypatch.setattr(
        "gnn.unsupervised_features.build_baseline_features", _stub_baseline
    )
    rows = pd.DataFrame(
        {
            "event_id": ["E1"],
            "primary_obs_id": [requested_obs_id],
            "t": pd.to_datetime(["2023-01-01T00:00:00Z"]),
        }
    )

    with pytest.raises(ValueError, match=expected_message):
        build_relational_feature_bundle(rows, tmp_path, {})


def test_encoder_uses_training_categories_only_and_preserves_numeric_values():
    names = ["prior_crossings", "region", "age_bucket", "sex"]
    categorical_names = {"region", "sex"}
    train = pd.DataFrame(
        {
            "sex": ["F", "M"],
            "age_bucket": [7.0, 8.0],
            "region": ["North", "South"],
            "prior_crossings": [1.5, 2.5],
        }
    )
    validation = pd.DataFrame(
        {
            "sex": ["X", "F"],
            "age_bucket": [9.0, 10.0],
            "region": ["West", "North"],
            "prior_crossings": [3.5, 4.5],
        }
    )
    test = pd.DataFrame(
        {
            "sex": ["M"],
            "age_bucket": [11.0],
            "region": ["East"],
            "prior_crossings": [5.5],
        }
    )

    encoded = encode_feature_splits(
        train, validation, test, names, categorical_names
    )

    assert encoded.train.shape == (2, 4)
    assert encoded.validation.shape == (2, 4)
    assert encoded.test.shape == (1, 4)
    region = names.index("region")
    sex = names.index("sex")
    assert encoded.validation[0, region] == -1
    assert encoded.validation[0, sex] == -1
    assert encoded.test[0, region] == -1
    assert encoded.test[0, sex] != -1
    np.testing.assert_array_equal(encoded.train[:, 0], [1.5, 2.5])
    np.testing.assert_array_equal(encoded.validation[:, 2], [9.0, 10.0])
    np.testing.assert_array_equal(encoded.test[:, 0], [5.5])
    assert isinstance(encoded.encoder, OrdinalEncoder)
    np.testing.assert_array_equal(
        encoded.encoder.transform(test[["region", "sex"]]),
        encoded.test[:, [region, sex]],
    )


@pytest.mark.parametrize("split_name", ["train", "validation", "test"])
def test_encoder_rejects_missing_categorical_values(split_name):
    names = ["prior_crossings", "region"]
    frames = {
        "train": pd.DataFrame({"prior_crossings": [1.0], "region": ["North"]}),
        "validation": pd.DataFrame(
            {"prior_crossings": [2.0], "region": ["South"]}
        ),
        "test": pd.DataFrame({"prior_crossings": [3.0], "region": ["East"]}),
    }
    frames[split_name].loc[0, "region"] = None

    with pytest.raises(
        ValueError, match=f"{split_name}.*missing categorical values.*region"
    ):
        encode_feature_splits(
            frames["train"],
            frames["validation"],
            frames["test"],
            names,
            {"region"},
        )


def test_encoder_rejects_empty_training_data():
    names = ["prior_crossings", "region"]
    train = pd.DataFrame(columns=names)
    validation = pd.DataFrame({"prior_crossings": [2.0], "region": ["South"]})
    test = pd.DataFrame({"prior_crossings": [3.0], "region": ["East"]})

    with pytest.raises(ValueError, match="training data must not be empty"):
        encode_feature_splits(train, validation, test, names, {"region"})
