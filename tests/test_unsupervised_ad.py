import json
from pathlib import Path
import shutil

import pandas as pd
import pytest
import numpy as np

import gnn.unsupervised_ad as unsupervised_ad
from gnn.demo_baseline import FEATURE_NAMES
from gnn.unsupervised_ad import (
    ABLATION_ARM_ORDER,
    FrozenScoredEvents,
    FrozenDeployableArms,
    OfficialCatchHistory,
    PRIMARY_ARM_ORDER,
    build_official_catch_history,
    cached_feature_rows,
    choose_threshold,
    evaluate_frozen_scores,
    evaluate_frozen_arms,
    freeze_scored_events,
    load_observable_pool,
    load_oracle_evaluation,
    main,
    prepare_training_rows,
    run_deployable_arms,
)
from gnn.unsupervised_features import FeatureBundle, RELATIONAL_PROXY_FEATURES


def test_cached_features_follow_event_row_order():
    rows = pd.DataFrame({"event_id": ["E2", "E1"]})
    cache = {
        "E1": np.array([1.0, 2.0]),
        "E2": np.array([3.0, 4.0]),
    }

    X = cached_feature_rows(rows, cache)

    np.testing.assert_array_equal(X, np.array([[3.0, 4.0], [1.0, 2.0]]))


def test_strict_mode_does_not_require_target_labels_or_exclude_rows():
    train = pd.DataFrame({"event_id": ["E1", "E2", "E3"]})

    selected, meta = prepare_training_rows(train, mode="strict")

    assert selected["event_id"].tolist() == ["E1", "E2", "E3"]
    assert meta["labels_used_for_fit"] is False
    assert meta["train_positive_excluded"] == 0


def test_assisted_mode_records_label_based_clean_training():
    train = pd.DataFrame({
        "event_id": ["E1", "E2", "E3"],
        "true_contraband_present": [False, True, False],
    })

    selected, meta = prepare_training_rows(train, mode="assisted")

    assert selected["event_id"].tolist() == ["E1", "E3"]
    assert meta["labels_used_for_fit"] is True
    assert meta["train_positive_excluded"] == 1


def test_strict_threshold_comes_from_training_scores_only():
    threshold, meta = choose_threshold(
        train_scores=[-0.9, -0.5, -0.1, 0.2],
        mode="strict",
        y_valid=None,
        contamination=0.25,
    )

    assert threshold == pytest.approx(0.9)
    assert meta == {
        "threshold_source": "train_score_quantile",
        "validation_labels_used_for_threshold": False,
    }


def test_assisted_threshold_requires_and_uses_validation_labels():
    threshold, meta = choose_threshold(
        train_scores=[-0.9, -0.5, -0.1, 0.2],
        mode="assisted",
        y_valid=[True, False, False, False],
    )

    assert isinstance(threshold, float)
    assert meta == {
        "threshold_source": "validation_f1",
        "validation_labels_used_for_threshold": True,
    }


def test_assisted_threshold_rejects_missing_validation_labels():
    with pytest.raises(ValueError, match="validation labels"):
        choose_threshold(
            train_scores=[-0.9, -0.5],
            mode="assisted",
            y_valid=None,
        )


def _write_observable_files(corpus_dir, *, events=None, splits=None):
    if events is None:
        events = pd.DataFrame({
            "event_id": ["E1", "E2"],
            "event_timestamp_utc": [
                "2025-01-01T12:00:00Z",
                "2025-01-02T12:00:00-05:00",
            ],
            "observed_person_record_id": ["OBS1", "OBS2"],
            "primary_person_id": ["P1", "P2"],
            "region": ["North", "South"],
            "seizure_flag": ["false", "TRUE"],
            "label_available_time_utc": [
                "2025-01-01T13:00:00Z",
                "2025-01-03T12:00:00-05:00",
            ],
        })
    if splits is None:
        splits = pd.DataFrame({
            "entity_id": ["E1", "E2"],
            "split": ["train", "test"],
        })
    events.to_csv(corpus_dir / "crossing_events.csv", index=False)
    splits.to_csv(corpus_dir / "train_valid_test_splits.csv", index=False)


def _observable_rows():
    return pd.DataFrame({
        "event_id": ["E1", "E2", "E3", "E4"],
        "split": ["test"] * 4,
        "t": pd.to_datetime([
            "2025-01-10T00:00:00Z",
            "2025-01-15T00:00:00Z",
            "2025-01-18T00:00:00Z",
            "2025-01-20T00:00:00Z",
        ], utc=True),
        "primary_obs_id": ["OBS1", "OBS1B", "OBS2", "OBS3"],
        "primary_person_id": ["P1", "P1", "P2", "P3"],
        "region": ["North"] * 4,
        "seizure_flag": [False, True, False, False],
        "label_available_time_utc": pd.to_datetime([
            "2025-01-10T01:00:00Z",
            "2025-01-25T00:00:00Z",
            "2025-01-18T01:00:00Z",
            "2025-01-20T01:00:00Z",
        ], utc=True),
    })


def _complete_observable_pool(*, p3_catch_time="2025-01-20T00:00:00Z"):
    scored = _observable_rows()
    history_rows = pd.DataFrame({
        "event_id": ["T1", "V1"],
        "split": ["train", "validation"],
        "t": pd.to_datetime([
            "2024-01-01T00:00:00Z", "2025-01-19T00:00:00Z"
        ], utc=True),
        "primary_obs_id": ["OBS_T", "OBS_P3_CATCH"],
        "primary_person_id": ["PT", "P3"],
        "region": ["North", "North"],
        "seizure_flag": [False, True],
        "label_available_time_utc": pd.to_datetime([
            "2024-01-01T00:00:00Z", p3_catch_time
        ], utc=True),
    })
    return pd.concat([history_rows, scored], ignore_index=True)


def _official_history(*, p3_catch_time="2025-01-20T00:00:00Z"):
    rows = _complete_observable_pool(p3_catch_time=p3_catch_time)
    return build_official_catch_history(rows, set(rows["event_id"]))


def _oracle_rows():
    return pd.DataFrame({
        "event_id": ["E1", "E2", "E3", "E4"],
        "primary_person_id": ["P1", "P1", "P2", "P3"],
        "true_contraband_present": [True, True, True, True],
        "false_negative_flag": [True, False, True, True],
    })


def test_observable_loader_never_requires_or_exposes_oracle_file(tmp_path):
    _write_observable_files(tmp_path)
    assert not (tmp_path / "event_ground_truth.csv").exists()

    rows = load_observable_pool(tmp_path)

    assert rows.columns.tolist() == [
        "event_id",
        "split",
        "t",
        "primary_obs_id",
        "primary_person_id",
        "region",
        "seizure_flag",
        "label_available_time_utc",
    ]
    assert rows["event_id"].tolist() == ["E1", "E2"]
    assert rows["seizure_flag"].tolist() == [False, True]
    assert str(rows["t"].dtype) == "datetime64[us, UTC]"
    assert str(rows["label_available_time_utc"].dtype) == "datetime64[us, UTC]"
    assert not {
        "true_contraband_present", "false_negative_flag", "detected_flag"
    }.intersection(rows.columns)


@pytest.mark.parametrize(
    "mutation, message",
    [
        ("duplicate_event", "unique event_id"),
        ("missing_split", "one-to-one"),
        ("bad_bool", "boolean"),
        ("naive_event_time", "timezone-aware"),
        ("bad_label_time", "label_available_time_utc"),
        ("label_before_event", "before event"),
    ],
)
def test_observable_loader_fails_closed_on_invalid_inputs(
    tmp_path, mutation, message
):
    events = pd.DataFrame({
        "event_id": ["E1", "E2"],
        "event_timestamp_utc": [
            "2025-01-01T12:00:00Z", "2025-01-02T12:00:00Z"
        ],
        "observed_person_record_id": ["OBS1", "OBS2"],
        "primary_person_id": ["P1", "P2"],
        "region": ["North", "South"],
        "seizure_flag": ["false", "true"],
        "label_available_time_utc": [
            "2025-01-01T13:00:00Z", "2025-01-02T13:00:00Z"
        ],
    })
    splits = pd.DataFrame({
        "entity_id": ["E1", "E2"],
        "split": ["train", "test"],
    })
    if mutation == "duplicate_event":
        events.loc[1, "event_id"] = "E1"
    elif mutation == "missing_split":
        splits = splits.iloc[:1]
    elif mutation == "bad_bool":
        events.loc[1, "seizure_flag"] = "not-known"
    elif mutation == "naive_event_time":
        events.loc[1, "event_timestamp_utc"] = "2025-01-02T12:00:00"
    elif mutation == "bad_label_time":
        events.loc[1, "label_available_time_utc"] = "not-a-time"
    elif mutation == "label_before_event":
        events.loc[1, "label_available_time_utc"] = "2025-01-01T12:00:00Z"
    _write_observable_files(tmp_path, events=events, splits=splits)

    with pytest.raises(ValueError, match=message):
        load_observable_pool(tmp_path)


def test_oracle_loader_is_separate_and_parses_bools_fail_closed(tmp_path):
    pd.DataFrame({
        "event_id": ["E1", "E2"],
        "primary_person_id": ["P1", "P2"],
        "true_contraband_present": ["TRUE", "false"],
        "false_negative_flag": ["true", "FALSE"],
    }).to_csv(tmp_path / "event_ground_truth.csv", index=False)

    rows = load_oracle_evaluation(tmp_path)

    assert rows.columns.tolist() == [
        "event_id",
        "primary_person_id",
        "true_contraband_present",
        "false_negative_flag",
    ]
    assert rows["true_contraband_present"].tolist() == [True, False]
    assert rows["false_negative_flag"].tolist() == [True, False]


@pytest.mark.parametrize("mutation", ["duplicate", "bad_bool"])
def test_oracle_loader_rejects_duplicate_ids_and_unknown_bools(tmp_path, mutation):
    rows = pd.DataFrame({
        "event_id": ["E1", "E2"],
        "primary_person_id": ["P1", "P2"],
        "true_contraband_present": ["true", "false"],
        "false_negative_flag": ["true", "false"],
    })
    if mutation == "duplicate":
        rows.loc[1, "event_id"] = "E1"
    else:
        rows.loc[1, "false_negative_flag"] = "unknown"
    rows.to_csv(tmp_path / "event_ground_truth.csv", index=False)

    with pytest.raises(ValueError, match="unique event_id|boolean"):
        load_oracle_evaluation(tmp_path)


def test_official_catch_history_uses_earliest_label_availability():
    rows = _complete_observable_pool()
    later_catch = rows.iloc[[0]].copy()
    later_catch["event_id"] = "E5"
    later_catch["primary_person_id"] = "P1"
    later_catch["seizure_flag"] = True
    later_catch["label_available_time_utc"] = pd.to_datetime(
        ["2025-02-01T00:00:00Z"], utc=True
    )

    complete = pd.concat([rows, later_catch])
    history = build_official_catch_history(complete, set(complete["event_id"]))

    assert isinstance(history, OfficialCatchHistory)
    assert dict(history.caught_times) == {
        "P3": pd.Timestamp("2025-01-20T00:00:00Z"),
        "P1": pd.Timestamp("2025-01-25T00:00:00Z"),
    }
    assert history.source_event_count == len(rows) + 1
    assert history.source_event_ids == tuple(
        pd.concat([rows, later_catch])["event_id"]
    )
    assert dict(history.split_counts) == {"test": 4, "train": 2, "validation": 1}
    assert history.source_scope == "complete_observable_pool"
    assert len(history.source_event_fingerprint) == 64
    with pytest.raises((TypeError, AttributeError)):
        history.caught_times += (("PX", pd.Timestamp("2025-01-01T00:00:00Z")),)


@pytest.mark.parametrize("mutation", ["duplicate", "missing_split"])
def test_official_catch_history_requires_complete_unique_observable_pool(mutation):
    rows = _complete_observable_pool()
    if mutation == "duplicate":
        rows.loc[1, "event_id"] = rows.loc[0, "event_id"]
    else:
        rows = rows.loc[rows["split"] != "validation"]

    with pytest.raises(ValueError, match="unique event_id|all train/validation/test"):
        build_official_catch_history(rows, set(rows["event_id"]))


def test_official_catch_history_cannot_be_constructed_without_builder():
    with pytest.raises(TypeError, match="build_official_catch_history"):
        OfficialCatchHistory()


def test_frozen_scored_events_detaches_and_immutably_stores_observables():
    rows = _observable_rows()
    scores = np.array([0.9, 0.8, 0.7, 0.1])

    frozen = freeze_scored_events(rows, scores, threshold=0.65)
    rows.loc[0, "event_id"] = "MUTATED"
    scores[0] = -100

    assert isinstance(frozen, FrozenScoredEvents)
    assert frozen.event_ids == ("E1", "E2", "E3", "E4")
    assert frozen.primary_person_ids == ("P1", "P1", "P2", "P3")
    assert frozen.observed_caught == (False, True, False, False)
    assert frozen.scores.tolist() == [0.9, 0.8, 0.7, 0.1]
    assert frozen.selected_mask.tolist() == [True, True, True, False]
    assert not frozen.scores.flags.writeable
    with pytest.raises(ValueError):
        frozen.scores.setflags(write=True)


@pytest.mark.parametrize(
    "frame_mutation, scores, message",
    [
        ("none", [0.1], "same length"),
        ("duplicate", [0.1, 0.2, 0.3, 0.4], "unique event_id"),
        ("oracle", [0.1, 0.2, 0.3, 0.4], "oracle"),
        ("naive_time", [0.1, 0.2, 0.3, 0.4], "timezone-aware"),
    ],
)
def test_freeze_scored_events_rejects_misalignment_and_oracle_data(
    frame_mutation, scores, message
):
    rows = _observable_rows()
    if frame_mutation == "duplicate":
        rows.loc[1, "event_id"] = "E1"
    elif frame_mutation == "oracle":
        rows["true_contraband_present"] = False
    elif frame_mutation == "naive_time":
        rows["t"] = rows["t"].dt.tz_localize(None)

    with pytest.raises(ValueError, match=message):
        freeze_scored_events(rows, scores, threshold=0.5)


def test_evaluation_distinguishes_missed_here_and_strict_prior_catch_timing():
    frozen = freeze_scored_events(
        _observable_rows(), [0.9, 0.8, 0.7, 0.1], threshold=0.65
    )
    caught_times = _official_history()

    metrics = evaluate_frozen_scores(frozen, _oracle_rows(), caught_times)

    assert metrics["all_carrier_events"] == {
        "positive_count": 4,
        "predicted_positive_count": 3,
        "precision": 1.0,
        "recall": 0.75,
        "f1": pytest.approx(6 / 7),
    }
    assert metrics["missed_at_event"] == {
        "positive_count": 3,
        "predicted_positive_count": 3,
        "precision": pytest.approx(2 / 3),
        "recall": pytest.approx(2 / 3),
        "f1": pytest.approx(2 / 3),
    }
    assert metrics["no_prior_catch_missed_events"]["positive_count"] == 3
    assert metrics["unique_person_first_hits"]["definition"] == (
        "Among people with at least one missed-at-event row, count a person "
        "recovered at their chronologically earliest selected missed event; "
        "official catch history does not restrict this stratum."
    )
    assert metrics["unique_person_first_hits"]["positive_count"] == 3
    assert metrics["unique_person_first_hits"]["found"] == 2
    assert metrics["unique_person_first_hits"]["recall"] == pytest.approx(2 / 3)
    assert metrics["unique_person_first_hits"]["first_hit_event_ids"] == {
        "P1": "E1", "P2": "E3"
    }
    assert metrics["lifetime_never_caught_people"] == {
        "positive_count": 1,
        "found": 1,
        "recall": 1.0,
    }
    assert metrics["observed_catch_enrichment"] == {
        "positive_count": 1,
        "predicted_positive_count": 3,
        "precision": pytest.approx(1 / 3),
        "recall": 1.0,
        "f1": 0.5,
        "prevalence": 0.25,
        "lift_over_prevalence": pytest.approx(4 / 3),
    }

    prior_metrics = evaluate_frozen_scores(
        frozen,
        _oracle_rows(),
        _official_history(p3_catch_time="2025-01-19T23:59:59Z"),
    )
    assert prior_metrics["no_prior_catch_missed_events"]["positive_count"] == 2


def test_unique_person_first_hit_is_earliest_selected_missed_event():
    rows = _complete_observable_pool()
    repeated = rows.loc[rows["event_id"].eq("E1")].copy()
    repeated["event_id"] = "E0_LATER"
    repeated["t"] = pd.to_datetime(["2025-01-11T00:00:00Z"], utc=True)
    repeated["label_available_time_utc"] = pd.to_datetime(
        ["2025-01-11T01:00:00Z"], utc=True
    )
    rows = pd.concat([rows, repeated], ignore_index=True)
    test_rows = rows.loc[rows["split"].eq("test")]
    frozen = freeze_scored_events(
        test_rows,
        [0.9, 0.8, 0.7, 0.1, 0.95],
        threshold=0.65,
    )
    oracle = pd.concat([
        _oracle_rows(),
        pd.DataFrame({
            "event_id": ["E0_LATER"],
            "primary_person_id": ["P1"],
            "true_contraband_present": [True],
            "false_negative_flag": [True],
        }),
    ], ignore_index=True)

    metrics = evaluate_frozen_scores(
        frozen, oracle, build_official_catch_history(rows, set(rows["event_id"]))
    )

    assert metrics["unique_person_first_hits"]["first_hit_event_ids"]["P1"] == "E1"


def test_empty_positive_strata_return_zeros_and_null_lift():
    frozen = freeze_scored_events(
        _observable_rows().iloc[:2], [0.9, 0.8], threshold=1.0
    )
    oracle = _oracle_rows().iloc[:2].assign(
        true_contraband_present=False,
        false_negative_flag=False,
    )

    metrics = evaluate_frozen_scores(
        frozen, oracle, _official_history()
    )

    assert metrics["all_carrier_events"] == {
        "positive_count": 0,
        "predicted_positive_count": 0,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
    }
    assert metrics["unique_person_first_hits"]["positive_count"] == 0
    assert metrics["unique_person_first_hits"]["found"] == 0
    assert metrics["unique_person_first_hits"]["recall"] == 0.0
    assert metrics["unique_person_first_hits"]["first_hit_event_ids"] == {}
    assert metrics["observed_catch_enrichment"]["lift_over_prevalence"] is None


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "person"])
def test_evaluation_requires_exact_one_to_one_person_aligned_oracle(mutation):
    frozen = freeze_scored_events(
        _observable_rows(), [0.9, 0.8, 0.7, 0.1], threshold=0.65
    )
    oracle = _oracle_rows()
    if mutation == "missing":
        oracle = oracle.iloc[:-1]
    elif mutation == "extra":
        oracle = pd.concat([
            oracle,
            pd.DataFrame({
                "event_id": ["EXTRA"],
                "primary_person_id": ["PX"],
                "true_contraband_present": [False],
                "false_negative_flag": [False],
            }),
        ], ignore_index=True)
    elif mutation == "duplicate":
        oracle.loc[1, "event_id"] = "E1"
    else:
        oracle.loc[0, "primary_person_id"] = "WRONG"

    with pytest.raises(ValueError, match="missing|extra|duplicate|person"):
        evaluate_frozen_scores(frozen, oracle, _official_history())


def test_evaluator_oracle_mutation_cannot_modify_frozen_scores():
    observable = _observable_rows()
    frozen = freeze_scored_events(
        observable, [0.9, 0.8, 0.7, 0.1], threshold=0.65
    )
    score_bytes = frozen.scores.tobytes()
    identity_payload = (
        frozen.event_ids,
        frozen.primary_person_ids,
        frozen.event_times,
        frozen.observed_caught,
        frozen.threshold,
        frozen.comparator,
    )
    history = _official_history()
    original = evaluate_frozen_scores(frozen, _oracle_rows(), history)
    mutated_oracle = _oracle_rows().assign(
        true_contraband_present=False,
        false_negative_flag=False,
    )

    mutated = evaluate_frozen_scores(frozen, mutated_oracle, history)

    assert original != mutated
    assert frozen.scores.tobytes() == score_bytes
    assert (
        frozen.event_ids,
        frozen.primary_person_ids,
        frozen.event_times,
        frozen.observed_caught,
        frozen.threshold,
        frozen.comparator,
    ) == identity_payload


def test_evaluation_rejects_filtered_or_inconsistent_catch_history():
    frozen = freeze_scored_events(
        _observable_rows(), [0.9, 0.8, 0.7, 0.1], threshold=0.65
    )
    complete_pool = _complete_observable_pool()
    incomplete_pool = complete_pool.loc[
        lambda frame: frame["event_id"] != "E4"
    ]
    with pytest.raises(ValueError, match="expected_event_ids"):
        build_official_catch_history(
            incomplete_pool, set(complete_pool["event_id"])
        )

    unscored_catch_removed = complete_pool.loc[
        lambda frame: frame["event_id"] != "V1"
    ]
    with pytest.raises(ValueError, match="expected_event_ids"):
        build_official_catch_history(
            unscored_catch_removed, set(complete_pool["event_id"])
        )

    inconsistent_rows = _complete_observable_pool().assign(seizure_flag=False)
    inconsistent = build_official_catch_history(
        inconsistent_rows, set(inconsistent_rows["event_id"])
    )
    with pytest.raises(ValueError, match="observed-caught person"):
        evaluate_frozen_scores(frozen, _oracle_rows(), inconsistent)


def _runner_fixture(*, caught=True, rows_per_split=60):
    event_ids = []
    splits = []
    times = []
    for split, start in (
        ("train", "2023-01-01T00:00:00Z"),
        ("validation", "2024-01-01T00:00:00Z"),
        ("test", "2025-01-01T00:00:00Z"),
    ):
        for index, timestamp in enumerate(
            pd.date_range(start, periods=rows_per_split, freq="h")
        ):
            prefix = {"train": "TR", "validation": "VA", "test": "TE"}[split]
            event_ids.append(f"{prefix}{index:03d}")
            splits.append(split)
            times.append(timestamp)
    size = len(event_ids)
    seizure = np.zeros(size, dtype=bool)
    if caught:
        seizure[np.arange(0, rows_per_split, 10)] = True
    observable = pd.DataFrame({
        "event_id": event_ids,
        "split": splits,
        "t": pd.DatetimeIndex(times),
        "primary_obs_id": [f"OBS{i:03d}" for i in range(size)],
        "primary_person_id": [f"P{i:03d}" for i in range(size)],
        "region": ["Synthetic Region"] * size,
        "seizure_flag": seizure,
        "label_available_time_utc": pd.DatetimeIndex(times) + pd.Timedelta(hours=1),
    })
    names = list(FEATURE_NAMES) + list(RELATIONAL_PROXY_FEATURES)
    rng = np.random.default_rng(123)
    matrix = rng.normal(size=(size, len(names)))
    display = pd.DataFrame(matrix, columns=names)
    bundle = FeatureBundle(
        event_ids=list(event_ids),
        matrix=matrix,
        names=names,
        categorical_names=frozenset(),
        display=display,
    )
    oracle = pd.DataFrame({
        "event_id": event_ids,
        "primary_person_id": observable["primary_person_id"],
        "true_contraband_present": np.arange(size) % 7 == 0,
        "false_negative_flag": np.arange(size) % 11 == 0,
    })
    return observable, bundle, oracle


def _frozen_arm_signature(frozen):
    payload = []
    for arm_id in (*PRIMARY_ARM_ORDER, *ABLATION_ARM_ORDER):
        for region, result in frozen.arms[arm_id].items():
            payload.append({
                "arm_id": arm_id,
                "region": region,
                "status": result.status,
                "feature_names": result.feature_names,
                "model_metadata": result.model_metadata,
                "threshold_metadata": result.threshold_metadata,
                "label_metadata": result.label_metadata,
                "sample_counts": result.sample_counts,
                "event_ids": (
                    result.scored_events.event_ids if result.scored_events else None
                ),
                "primary_person_ids": (
                    result.scored_events.primary_person_ids
                    if result.scored_events else None
                ),
                "event_times": (
                    tuple(time.isoformat() for time in result.scored_events.event_times)
                    if result.scored_events else None
                ),
                "observed_caught": (
                    result.scored_events.observed_caught
                    if result.scored_events else None
                ),
                "scores_hex": (
                    result.scored_events.scores.tobytes().hex()
                    if result.scored_events else None
                ),
                "threshold": (
                    result.scored_events.threshold if result.scored_events else None
                ),
                "comparator": (
                    result.scored_events.comparator if result.scored_events else None
                ),
                "realized_test_alert_rate": result.realized_test_alert_rate,
                "skip_reason": result.skip_reason,
            })
    return json.dumps(payload, sort_keys=True)


def test_deployable_runner_builds_four_frozen_oracle_free_arms():
    observable, bundle, _ = _runner_fixture()

    frozen = run_deployable_arms(
        observable,
        bundle,
        fit_as_of="2024-01-01T00:00:00Z",
        alert_rate=0.1,
        seed=17,
        n_estimators=5,
    )

    assert isinstance(frozen, FrozenDeployableArms)
    assert list(frozen.arms) == [*PRIMARY_ARM_ORDER, *ABLATION_ARM_ORDER]
    for arm_id in (*PRIMARY_ARM_ORDER, *ABLATION_ARM_ORDER):
        result = frozen.arms[arm_id]["Synthetic Region"]
        assert result.status == "completed"
        assert isinstance(result.scored_events, FrozenScoredEvents)
        assert result.threshold_metadata["threshold_source"] == (
            "validation_score_quantile"
        )
        assert result.threshold_metadata["labels_used_for_threshold"] is False
        assert result.sample_counts == {
            "train": 60, "validation": 60, "test": 60
        }
        expected_width = 14 if arm_id.startswith("tabular") else 18
        assert len(result.feature_names) == expected_width
        assert result.label_metadata["caught_positive_count"] == 6
        assert result.label_metadata["immature_label_count"] == 0
        assert 0.0 <= result.realized_test_alert_rate <= 1.0
    assert frozen.arms["tabular_unlabeled"]["Synthetic Region"].label_metadata[
        "labels_used_for_fit"
    ] is False
    assert frozen.arms["relational_caught_supervised"][
        "Synthetic Region"
    ].label_metadata["fit_signal"] == "caught_vs_unlabeled_naive_pu"
    with pytest.raises(TypeError):
        frozen.arms["new"] = {}


def test_deployable_runner_uses_declared_boundary_before_first_validation_event():
    observable, bundle, _ = _runner_fixture()
    validation = observable["split"].eq("validation")
    observable.loc[validation, "t"] += pd.Timedelta(minutes=30)
    observable.loc[validation, "label_available_time_utc"] += pd.Timedelta(
        minutes=30
    )
    delayed_catch = observable.index[
        observable["split"].eq("train") & observable["seizure_flag"]
    ][-1]
    observable.loc[delayed_catch, "label_available_time_utc"] = pd.Timestamp(
        "2024-01-01T00:15:00Z"
    )

    frozen = run_deployable_arms(
        observable,
        bundle,
        fit_as_of="2024-01-01T00:00:00Z",
        n_estimators=5,
    )

    assert frozen.fit_as_of == "2024-01-01T00:00:00+00:00"
    result = frozen.arms["relational_caught_supervised"]["Synthetic Region"]
    assert result.label_metadata["fit_as_of"] == "2024-01-01T00:00:00+00:00"
    assert result.label_metadata["caught_positive_count"] == 5
    assert result.label_metadata["immature_label_count"] == 1


def test_deployable_runner_rejects_oracle_columns_and_feature_misalignment():
    observable, bundle, _ = _runner_fixture()
    with pytest.raises(ValueError, match="oracle"):
        run_deployable_arms(
            observable.assign(true_contraband_present=False),
            bundle,
            fit_as_of="2024-01-01T00:00:00Z",
            n_estimators=5,
        )

    misaligned = FeatureBundle(
        event_ids=bundle.event_ids[:-1],
        matrix=bundle.matrix[:-1],
        names=bundle.names,
        categorical_names=bundle.categorical_names,
        display=bundle.display.iloc[:-1],
    )
    with pytest.raises(ValueError, match="feature_bundle event IDs"):
        run_deployable_arms(
            observable,
            misaligned,
            fit_as_of="2024-01-01T00:00:00Z",
            n_estimators=5,
        )


@pytest.mark.parametrize(
    "mutation", ["late_cutoff", "early_cutoff", "overlapping_train"]
)
def test_deployable_runner_enforces_validation_cutoff_and_temporal_order(mutation):
    observable, bundle, _ = _runner_fixture()
    fit_as_of = "2024-01-01T00:00:00Z"
    if mutation == "late_cutoff":
        fit_as_of = "2024-01-02T00:00:00Z"
    elif mutation == "early_cutoff":
        fit_as_of = observable.loc[
            observable["split"].eq("train"), "t"
        ].max()
    else:
        last_train = observable.index[observable["split"].eq("train")][-1]
        observable.loc[last_train, "t"] = pd.Timestamp("2024-01-01T00:00:00Z")
        observable.loc[last_train, "label_available_time_utc"] = pd.Timestamp(
            "2024-01-01T01:00:00Z"
        )

    with pytest.raises(ValueError, match="validation start|temporal split order"):
        run_deployable_arms(
            observable,
            bundle,
            fit_as_of=fit_as_of,
            n_estimators=5,
        )

def test_one_class_caught_region_skips_only_supervised_arms():
    observable, bundle, _ = _runner_fixture(caught=False)

    frozen = run_deployable_arms(
        observable,
        bundle,
        fit_as_of="2024-01-01T00:00:00Z",
        n_estimators=5,
    )

    assert frozen.arms["tabular_unlabeled"]["Synthetic Region"].status == (
        "completed"
    )
    assert frozen.arms["relational_unlabeled"]["Synthetic Region"].status == (
        "completed"
    )
    for arm_id in ("tabular_caught_supervised", "relational_caught_supervised"):
        result = frozen.arms[arm_id]["Synthetic Region"]
        assert result.status == "skipped"
        assert "both caught and unlabeled classes" in result.skip_reason


def test_actual_runner_is_invariant_to_oracle_file_mutation_until_evaluation(
    tmp_path, monkeypatch
):
    source = (
        Path(__file__).parents[1]
        / "Documents"
        / "Data"
        / "synthetic_cbp_graph_corpus_v9dev"
    )
    original_corpus = tmp_path / "original_corpus"
    mutated_corpus = tmp_path / "mutated_corpus"
    shutil.copytree(source, original_corpus)
    shutil.copytree(source, mutated_corpus)
    mutated_path = mutated_corpus / "event_ground_truth.csv"
    mutated_frame = pd.read_csv(mutated_path)
    for column in ("true_contraband_present", "false_negative_flag"):
        parsed = mutated_frame[column].astype(str).str.lower().eq("true")
        mutated_frame[column] = ~parsed
    mutated_frame.to_csv(mutated_path, index=False)
    assert (
        original_corpus / "event_ground_truth.csv"
    ).read_bytes() != mutated_path.read_bytes()

    actual_read_csv = pd.read_csv
    oracle_reads = []
    oracle_allowed = False

    def guarded_read_csv(path, *args, **kwargs):
        if Path(path).name == "event_ground_truth.csv":
            oracle_reads.append((str(path), oracle_allowed))
            if not oracle_allowed:
                raise AssertionError("oracle file read before all scores froze")
        return actual_read_csv(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", guarded_read_csv)

    def freeze_from(corpus):
        observable = load_observable_pool(corpus)
        identity = unsupervised_ad._build_oracle(corpus)
        bundle = unsupervised_ad.build_relational_feature_bundle(
            observable[["event_id", "primary_obs_id", "t"]], corpus, identity
        )
        validation_start = observable.loc[
            observable["split"].eq("validation"), "t"
        ].min()
        frozen = run_deployable_arms(
            observable,
            bundle,
            fit_as_of=validation_start,
            alert_rate=0.1,
            seed=19,
            n_estimators=5,
        )
        return observable, frozen

    original_observable, first = freeze_from(original_corpus)
    mutated_observable, second = freeze_from(mutated_corpus)
    assert oracle_reads == []
    assert _frozen_arm_signature(first) == _frozen_arm_signature(second)

    oracle_allowed = True
    original_oracle = load_oracle_evaluation(original_corpus)
    mutated_oracle = load_oracle_evaluation(mutated_corpus)
    original_history = build_official_catch_history(
        original_observable, set(original_observable["event_id"])
    )
    mutated_history = build_official_catch_history(
        mutated_observable, set(mutated_observable["event_id"])
    )
    original = evaluate_frozen_arms(first, original_oracle, original_history)
    mutated = evaluate_frozen_arms(second, mutated_oracle, mutated_history)
    assert original != mutated
    assert _frozen_arm_signature(first) == _frozen_arm_signature(second)
    assert len(oracle_reads) == 2
    assert all(allowed for _, allowed in oracle_reads)
    for arm_id in (*PRIMARY_ARM_ORDER, *ABLATION_ARM_ORDER):
        for region in original[arm_id].values():
            assert "evaluation_only" in region


def test_v9dev_main_schema_v3_freezes_before_oracle_and_quarantines_assisted(
    tmp_path, monkeypatch
):
    corpus = (
        Path(__file__).parents[1]
        / "Documents"
        / "Data"
        / "synthetic_cbp_graph_corpus_v9dev"
    )
    call_order = []
    actual_run = unsupervised_ad.run_deployable_arms
    actual_oracle_loader = unsupervised_ad.load_oracle_evaluation

    def tracked_run(*args, **kwargs):
        call_order.append("run_start")
        result = actual_run(*args, **kwargs)
        call_order.append("run_returned")
        return result

    def tracked_oracle_loader(*args, **kwargs):
        call_order.append("oracle_loaded")
        return actual_oracle_loader(*args, **kwargs)

    monkeypatch.setattr(unsupervised_ad, "run_deployable_arms", tracked_run)
    monkeypatch.setattr(
        unsupervised_ad, "load_oracle_evaluation", tracked_oracle_loader
    )

    output = main(
        corpus_dir=corpus,
        results_dir=tmp_path,
        include_deployable_arms=True,
        seed=23,
        n_estimators=10,
    )

    assert call_order.index("run_returned") < call_order.index("oracle_loaded")
    assert output["schema_version"] == 3
    assert output["provenance"] == {
        "corpus_name": "synthetic_cbp_graph_corpus_v9dev",
        "corpus_path": str(corpus),
        "artifact": "unsupervised_ad_schema_v3",
    }
    assert output["primary_arm_order"] == PRIMARY_ARM_ORDER
    assert output["ablation_arm_order"] == ABLATION_ARM_ORDER
    assert "assisted" not in output["primary_arm_order"]
    assert output["legacy_oracle_benchmarks"]["assisted"]["nondeployable"] is True
    assert output["legacy_oracle_benchmarks"]["assisted"]["is_ceiling"] is False
    assert "conditional" in output["identity_substrate"].lower()
    assert output["target_contract"]["oracle_available_in_production"] is False
    assert output["label_provenance"]["threshold_labels_used"] is False
    assert output["label_provenance"]["pu_interpretation"] == (
        "caught-supervised naive PU; no SCAR ranking guarantee"
    )
    assert output["label_provenance"]["fit_as_of"] == (
        "2024-01-01T00:00:00+00:00"
    )
    assert output["split_contract"]["declared_fit_as_of_utc"] == (
        "2024-01-01T00:00:00+00:00"
    )

    observable = load_observable_pool(corpus)
    catch_provenance = output["evaluation_provenance"][
        "official_catch_history"
    ]
    assert catch_provenance == {
        "source_scope": "complete_observable_pool",
        "source_event_count": len(observable),
        "source_event_fingerprint": unsupervised_ad._event_id_fingerprint(
            set(observable["event_id"])
        ),
        "split_counts": {
            split: int(observable["split"].eq(split).sum())
            for split in ("train", "validation", "test")
        },
    }
    json.dumps(output)

    immature_total = 0
    for arm_id in (*PRIMARY_ARM_ORDER, *ABLATION_ARM_ORDER):
        for result in output["arms"][arm_id].values():
            assert result["status"] == "completed"
            assert result["feature_count"] == (14 if arm_id.startswith("tabular") else 18)
            assert result["threshold_metadata"]["threshold_source"] == (
                "validation_score_quantile"
            )
            assert result["threshold_metadata"]["labels_used_for_threshold"] is False
            assert "evaluation_only" in result
            immature_total += result["label_metadata"]["immature_label_count"]
    assert immature_total > 0

    generic = tmp_path / "unsupervised_ad_results.json"
    qualified = tmp_path / "unsupervised_ad_results_v9dev.json"
    assert generic.read_bytes() == qualified.read_bytes()
    assert json.loads(generic.read_text())["schema_version"] == 3
