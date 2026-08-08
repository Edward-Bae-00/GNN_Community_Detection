"""Leak-safe feature bundles for deployability comparisons."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.preprocessing import OrdinalEncoder

from gnn.demo_baseline import FEATURE_NAMES, build_baseline_features


RELATIONAL_PROXY_FEATURES = [
    "party_size",
    "repeat_crossing_count_prior_365d",
    "same_vehicle_crossing_count_prior_365d",
    "same_document_crossing_count_prior_365d",
]

_EVENT_CATEGORICAL_FEATURES = [
    "citizenship_country",
    "residence_country",
    "region",
    "mode_of_transportation",
    "travel_category",
    "declared_trip_purpose",
    "day_of_week",
]

CATEGORICAL_FEATURES = frozenset(["sex", *_EVENT_CATEGORICAL_FEATURES])


@dataclass(frozen=True)
class FeatureBundle:
    """Leak-safe tabular and relational feature frames plus provenance.

    ``event_ids`` preserves requested row order; ``matrix`` is the numeric
    baseline-plus-relational-proxy array; ``names`` gives its column order;
    ``categorical_names`` identifies raw categorical columns; and ``display``
    retains aligned human-readable categorical values for train-only encoding.
    The dataclass is frozen, but its arrays, lists, and DataFrame are caller
    owned, so producers must treat them as immutable after construction.
    Builders validate event/observed IDs, source columns, uniqueness, and row
    alignment, and relational proxies remain comparison features rather than
    hidden outcomes or future labels.
    """

    event_ids: list[str]
    matrix: np.ndarray
    names: list[str]
    categorical_names: frozenset[str]
    display: pd.DataFrame


@dataclass(frozen=True)
class EncodedSplits:
    """Encoded train, validation, and test matrices with frozen schemas.

    ``train``, ``validation``, and ``test`` are numeric matrices with identical
    feature-column order; ``encoder`` is the training-fitted
    ``OrdinalEncoder`` or ``None`` when no categorical columns exist.  The
    frozen dataclass protects attribute reassignment but does not deep-freeze
    NumPy arrays or the encoder, so callers must not mutate them after score
    generation.  ``encode_feature_splits`` validates required columns and
    nonempty training data, learns categories from training only, and maps
    unseen validation/test categories to ``-1`` without admitting future labels.
    """

    train: np.ndarray
    validation: np.ndarray
    test: np.ndarray
    encoder: OrdinalEncoder | None


def _duplicate_values(values: pd.Series) -> list:
    return values.loc[values.duplicated(keep=False)].drop_duplicates().tolist()


def build_relational_feature_bundle(
    rows: pd.DataFrame, corpus_dir, obs_to_identity
) -> FeatureBundle:
    """Return aligned baseline and relational-proxy features for ``rows``.

    ``matrix`` retains the numeric values produced by the existing 14-feature
    baseline. ``display`` has the same feature columns and row order, but keeps
    observable categorical values in their raw form for train-only encoding.
    """
    missing_row_columns = [
        name for name in ("event_id", "primary_obs_id") if name not in rows.columns
    ]
    if missing_row_columns:
        raise ValueError(
            f"requested rows are missing required columns: {missing_row_columns}"
        )
    if rows["primary_obs_id"].isna().any():
        raise ValueError("requested rows contain null primary_obs_id values")

    event_ids = rows["event_id"].tolist()
    duplicate_requested = _duplicate_values(rows["event_id"])
    if duplicate_requested:
        raise ValueError(
            f"requested rows contain duplicate event_id values: {duplicate_requested[:3]}"
        )

    required_event_columns = [
        "event_id",
        *RELATIONAL_PROXY_FEATURES,
        *_EVENT_CATEGORICAL_FEATURES,
    ]
    crossings = pd.read_csv(
        corpus_dir / "crossing_events.csv",
        usecols=lambda name: name in required_event_columns,
    )
    if "event_id" not in crossings.columns:
        raise ValueError(
            "crossing_events.csv is missing required event ID column: event_id"
        )
    missing_proxy_columns = [
        name for name in RELATIONAL_PROXY_FEATURES if name not in crossings.columns
    ]
    if missing_proxy_columns:
        raise ValueError(
            f"missing required proxy columns: {missing_proxy_columns}"
        )
    missing_event_categorical = [
        name for name in _EVENT_CATEGORICAL_FEATURES if name not in crossings.columns
    ]
    if missing_event_categorical:
        raise ValueError(
            "missing required raw event categorical columns: "
            f"{missing_event_categorical}"
        )

    duplicate_source = _duplicate_values(crossings["event_id"])
    if duplicate_source:
        raise ValueError(
            f"crossing_events contains duplicate event_id values: {duplicate_source[:3]}"
        )

    crossing_ids = set(crossings["event_id"])
    missing_event_ids = [
        event_id for event_id in event_ids if event_id not in crossing_ids
    ]
    if missing_event_ids:
        raise KeyError(f"missing requested event IDs: {missing_event_ids[:3]}")

    observed_path = corpus_dir / "observed_person_records.csv"
    if not observed_path.exists():
        raise ValueError("observed_person_records.csv is required for raw sex values")
    required_observed_columns = [
        "observed_person_record_id",
        "observed_sex_marker",
    ]
    try:
        observed = pd.read_csv(
            observed_path,
            usecols=lambda name: name in required_observed_columns,
        )
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise ValueError("observed_person_records.csv is malformed") from exc
    missing_observed_columns = [
        name for name in required_observed_columns if name not in observed.columns
    ]
    if missing_observed_columns:
        raise ValueError(
            "missing required observed-person columns: "
            f"{missing_observed_columns}"
        )
    duplicate_observed_ids = _duplicate_values(
        observed["observed_person_record_id"]
    )
    if duplicate_observed_ids:
        raise ValueError(
            "observed_person_records contains duplicate observed_person_record_id "
            f"values: {duplicate_observed_ids[:3]}"
        )

    sex_by_observed_id = observed.set_index("observed_person_record_id")[
        "observed_sex_marker"
    ]
    requested_observed_ids = rows["primary_obs_id"].drop_duplicates().tolist()
    missing_observed_ids = [
        observed_id
        for observed_id in requested_observed_ids
        if observed_id not in sex_by_observed_id.index
    ]
    if missing_observed_ids:
        raise ValueError(
            "missing observed sex for requested primary_obs_id values: "
            f"{missing_observed_ids[:3]}"
        )
    null_sex_ids = [
        observed_id
        for observed_id in requested_observed_ids
        if pd.isna(sex_by_observed_id.at[observed_id])
    ]
    if null_sex_ids:
        raise ValueError(
            "null observed sex for requested primary_obs_id values: "
            f"{null_sex_ids[:3]}"
        )

    base_matrix, base_names = build_baseline_features(
        rows, corpus_dir, obs_to_identity
    )
    if base_names != list(FEATURE_NAMES):
        raise ValueError(
            "baseline feature names do not match the required 14-feature contract"
        )
    base_matrix = np.asarray(base_matrix, dtype=float)
    if base_matrix.shape != (len(rows), len(FEATURE_NAMES)):
        raise ValueError(
            "baseline feature matrix shape does not match requested rows and columns"
        )

    aligned = crossings.set_index("event_id").loc[event_ids]
    proxies = aligned[RELATIONAL_PROXY_FEATURES].apply(
        pd.to_numeric, errors="raise"
    )
    names = list(FEATURE_NAMES) + list(RELATIONAL_PROXY_FEATURES)
    matrix = np.column_stack([base_matrix, proxies.to_numpy(dtype=float)])

    display = pd.DataFrame(matrix, columns=names)
    for name in _EVENT_CATEGORICAL_FEATURES:
        display[name] = aligned[name].to_numpy()
    display["sex"] = rows["primary_obs_id"].map(sex_by_observed_id).to_numpy()

    return FeatureBundle(
        event_ids=event_ids,
        matrix=matrix,
        names=names,
        categorical_names=CATEGORICAL_FEATURES,
        display=display,
    )


def encode_feature_splits(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    names,
    categorical_names,
) -> EncodedSplits:
    """Encode categorical columns using only training-split categories.

    Each input is a DataFrame containing the columns in ``names``. Numeric
    columns are copied without transformation; unseen validation or test
    categories receive the code ``-1``.
    """
    names = list(names)
    if len(names) != len(set(names)):
        raise ValueError("feature names must be unique")
    categorical_names = frozenset(categorical_names)
    unknown_categorical = categorical_names - set(names)
    if unknown_categorical:
        raise ValueError(
            f"categorical names are not present in feature names: {sorted(unknown_categorical)}"
        )

    frames = {"train": train, "validation": validation, "test": test}
    for split_name, frame in frames.items():
        missing = [name for name in names if name not in frame.columns]
        if missing:
            raise ValueError(f"{split_name} is missing feature columns: {missing}")
    if train.empty:
        raise ValueError("training data must not be empty")

    categorical_columns = [
        name for name in names if name in categorical_names
    ]
    numeric_columns = [name for name in names if name not in categorical_names]
    categorical_indices = [names.index(name) for name in categorical_columns]
    numeric_indices = [names.index(name) for name in numeric_columns]

    for split_name, frame in frames.items():
        missing_categorical_values = [
            name for name in categorical_columns if frame[name].isna().any()
        ]
        if missing_categorical_values:
            raise ValueError(
                f"{split_name} contains missing categorical values: "
                f"{missing_categorical_values}"
            )

    output = {
        split_name: np.empty((len(frame), len(names)), dtype=float)
        for split_name, frame in frames.items()
    }
    for split_name, frame in frames.items():
        if numeric_columns:
            output[split_name][:, numeric_indices] = frame[numeric_columns].to_numpy(
                dtype=float
            )

    encoder = None
    if categorical_columns:
        encoder = OrdinalEncoder(
            handle_unknown="use_encoded_value",
            unknown_value=-1,
        )
        encoder.fit(train[categorical_columns])
        for split_name, frame in frames.items():
            output[split_name][:, categorical_indices] = encoder.transform(
                frame[categorical_columns]
            )

    return EncodedSplits(
        train=output["train"],
        validation=output["validation"],
        test=output["test"],
        encoder=encoder,
    )
