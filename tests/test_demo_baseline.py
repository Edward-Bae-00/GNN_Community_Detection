"""Realistic tabular baseline: shape, feature set, and as-of correctness.
See docs/research/changes_3.md."""
import numpy as np
import pandas as pd

from gnn.demo_baseline import build_baseline_features, FEATURE_NAMES
from gnn.paths import V9DEV_CORPUS_DIR

CD = V9DEV_CORPUS_DIR


def test_realistic_baseline_shape_and_asof_counts():
    from gnn.run_demo import _build_oracle, load_pool
    obs2id = _build_oracle(CD)
    pool = load_pool(CD).head(200)
    X, names = build_baseline_features(
        pool[["event_id", "primary_obs_id", "t"]], CD, obs2id)
    assert names == FEATURE_NAMES and len(names) >= 12
    assert X.shape == (len(pool), len(FEATURE_NAMES))
    for c in ("prior_crossings", "prior_seizure", "prior_arrests"):
        assert (X[:, names.index(c)] >= 0).all()                  # as-of counts
    assert not np.isnan(X).any()


def test_history_counts_outcomes_only_after_label_availability(tmp_path):
    """A prior event's outcome is unavailable until its label timestamp."""
    corpus = tmp_path
    pd.DataFrame([
        {
            "event_id": "E1",
            "event_timestamp_utc": "2025-01-01T00:00:00Z",
            "observed_person_record_id": "O1",
            "label_available_time_utc": "2025-01-02T00:00:00Z",
            "secondary_referral_flag": "false",
            "seizure_flag": "true",
            "arrest_flag": "false",
            "citizenship_country": "X",
            "residence_country": "X",
            "region": "R",
            "mode_of_transportation": "Air",
            "travel_category": "Air",
            "declared_trip_purpose": "business",
            "day_of_week": "Wednesday",
        },
        {
            "event_id": "E2",
            "event_timestamp_utc": "2025-01-01T12:00:00Z",
            "observed_person_record_id": "O1",
            "label_available_time_utc": "2025-01-02T12:00:00Z",
            "secondary_referral_flag": "false",
            "seizure_flag": "false",
            "arrest_flag": "false",
            "citizenship_country": "X",
            "residence_country": "X",
            "region": "R",
            "mode_of_transportation": "Air",
            "travel_category": "Air",
            "declared_trip_purpose": "business",
            "day_of_week": "Wednesday",
        },
        {
            "event_id": "E3",
            "event_timestamp_utc": "2025-01-03T00:00:00Z",
            "observed_person_record_id": "O1",
            "label_available_time_utc": "2025-01-04T00:00:00Z",
            "secondary_referral_flag": "false",
            "seizure_flag": "false",
            "arrest_flag": "false",
            "citizenship_country": "X",
            "residence_country": "X",
            "region": "R",
            "mode_of_transportation": "Air",
            "travel_category": "Air",
            "declared_trip_purpose": "business",
            "day_of_week": "Friday",
        },
    ]).to_csv(corpus / "crossing_events.csv", index=False)
    pd.DataFrame([
        {"event_id": "E1", "pre_event_features_json": '{"hour": 0}'},
        {"event_id": "E2", "pre_event_features_json": '{"hour": 12}'},
        {"event_id": "E3", "pre_event_features_json": '{"hour": 0}'},
    ]).to_csv(corpus / "event_features.csv", index=False)
    pd.DataFrame([
        {
            "observed_person_record_id": "O1",
            "observed_dob_year_bucket": "Y1990",
            "observed_sex_marker": "X",
        },
    ]).to_csv(corpus / "observed_person_records.csv", index=False)

    from gnn.demo_baseline import build_baseline_features

    rows = pd.DataFrame({
        "event_id": ["E2", "E3"],
        "primary_obs_id": ["O1", "O1"],
        "t": pd.to_datetime([
            "2025-01-01T12:00:00Z",
            "2025-01-03T00:00:00Z",
        ]),
    })
    X, names = build_baseline_features(rows, corpus, {"O1": "P1"})

    assert X[:, names.index("prior_seizure")].tolist() == [0.0, 1.0]
