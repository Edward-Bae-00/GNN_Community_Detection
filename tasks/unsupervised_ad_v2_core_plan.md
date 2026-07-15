# Unsupervised AD V2 Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a backward-compatible `relational_strict` Isolation Forest arm with recent unlabeled calibration, richer leak-safe relational proxy features, chart-ready evaluation diagnostics, provenance, and bounded non-causal explainability.

**Architecture:** Keep `modes.strict` and `modes.assisted` unchanged in `gnn/unsupervised_ad.py`. Build the additive feature bundle in `gnn/unsupervised_features.py`, compute rarity and replacement-sensitivity explanations in `gnn/unsupervised_explain.py`, and assemble schema-v3 diagnostics through pure helpers before writing both corpus-qualified and compatibility artifacts.

**Tech Stack:** Python 3.14, pandas, NumPy, scikit-learn Isolation Forest and metrics, pytest, JSON.

---

## File Map

- Create `gnn/unsupervised_features.py`: relational proxy feature construction, row alignment, display values, and feature kinds.
- Create `gnn/unsupervised_explain.py`: regional references, rarity, replacement sensitivity, local alerts, and global influence.
- Modify `gnn/unsupervised_ad.py`: recent calibration, diagnostics, relational arm orchestration, provenance, and artifact writing.
- Modify `tests/test_unsupervised_ad.py`: threshold, diagnostics, arm compatibility, and orchestration tests.
- Create `tests/test_unsupervised_features.py`: feature contract and validation tests.
- Create `tests/test_unsupervised_explain.py`: deterministic explainability tests.
- Modify `Documents/Data/changes_3.md`: record the new arm, evaluation contract, and limitations.
- Regenerate `gnn/diagnostics/unsupervised_ad_results_v9.json` and the compatibility artifact only after all source tests pass.

### Task 1: Relational Proxy Feature Bundle

**Files:**
- Create: `gnn/unsupervised_features.py`
- Create: `tests/test_unsupervised_features.py`

- [ ] **Step 1: Write failing feature-order and value tests**

Create a tiny crossing-event CSV and monkeypatch the existing baseline builder so the test isolates augmentation and alignment:

```python
import numpy as np
import pandas as pd
import pytest

from gnn.unsupervised_features import (
    RELATIONAL_PROXY_FEATURES,
    build_relational_feature_bundle,
)


def test_relational_features_follow_requested_event_order(tmp_path, monkeypatch):
    pd.DataFrame([
        {"event_id": "E1", "party_size": 2,
         "repeat_crossing_count_prior_365d": 3,
         "same_vehicle_crossing_count_prior_365d": 4,
         "same_document_crossing_count_prior_365d": 5},
        {"event_id": "E2", "party_size": 6,
         "repeat_crossing_count_prior_365d": 7,
         "same_vehicle_crossing_count_prior_365d": 8,
         "same_document_crossing_count_prior_365d": 9},
    ]).to_csv(tmp_path / "crossing_events.csv", index=False)
    monkeypatch.setattr(
        "gnn.unsupervised_features.build_baseline_features",
        lambda rows, corpus_dir, obs_to_identity:
            (np.array([[10.0], [20.0]]), ["baseline"]),
    )
    rows = pd.DataFrame({
        "event_id": ["E2", "E1"],
        "primary_obs_id": ["O2", "O1"],
        "t": pd.to_datetime(["2025-01-02Z", "2025-01-01Z"]),
    })

    bundle = build_relational_feature_bundle(rows, tmp_path, {})

    assert bundle.names == ["baseline", *RELATIONAL_PROXY_FEATURES]
    np.testing.assert_array_equal(
        bundle.matrix[:, -4:],
        np.array([[6, 7, 8, 9], [2, 3, 4, 5]], dtype=float),
    )
    assert bundle.display.loc[0, "event_id"] == "E2"
    assert set(bundle.kinds.values()) <= {"numeric", "categorical"}


def test_relational_features_reject_missing_event(tmp_path, monkeypatch):
    pd.DataFrame([{
        "event_id": "E1", "party_size": 1,
        "repeat_crossing_count_prior_365d": 0,
        "same_vehicle_crossing_count_prior_365d": 0,
        "same_document_crossing_count_prior_365d": 0,
    }]).to_csv(tmp_path / "crossing_events.csv", index=False)
    monkeypatch.setattr(
        "gnn.unsupervised_features.build_baseline_features",
        lambda rows, corpus_dir, obs_to_identity:
            (np.zeros((len(rows), 1)), ["baseline"]),
    )
    rows = pd.DataFrame({
        "event_id": ["E2"], "primary_obs_id": ["O2"],
        "t": pd.to_datetime(["2025-01-02Z"]),
    })

    with pytest.raises(KeyError, match="missing event IDs"):
        build_relational_feature_bundle(rows, tmp_path, {})
```

- [ ] **Step 2: Run the feature tests and verify RED**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_features.py
```

Expected: collection fails because `gnn.unsupervised_features` does not exist.

- [ ] **Step 3: Implement the feature bundle**

Create the module with a frozen bundle contract and strict one-to-one merge:

```python
from dataclasses import dataclass

import numpy as np
import pandas as pd

from gnn.demo_baseline import build_baseline_features


RELATIONAL_PROXY_FEATURES = [
    "party_size",
    "repeat_crossing_count_prior_365d",
    "same_vehicle_crossing_count_prior_365d",
    "same_document_crossing_count_prior_365d",
]
CATEGORICAL_BASELINE_FEATURES = {
    "sex", "citizenship_country", "residence_country", "region",
    "mode_of_transportation", "travel_category",
    "declared_trip_purpose", "day_of_week",
}
DISPLAY_EVENT_FEATURES = [
    "citizenship_country", "residence_country", "region",
    "mode_of_transportation", "travel_category",
    "declared_trip_purpose", "day_of_week",
]


@dataclass(frozen=True)
class FeatureBundle:
    matrix: np.ndarray
    names: list[str]
    kinds: dict[str, str]
    display: pd.DataFrame


def build_relational_feature_bundle(rows, corpus_dir, obs_to_identity):
    ordered = rows.reset_index(drop=True)
    base, base_names = build_baseline_features(
        ordered[["event_id", "primary_obs_id", "t"]],
        corpus_dir,
        obs_to_identity,
    )
    if base.shape != (len(ordered), len(base_names)):
        raise ValueError("baseline feature matrix is not aligned with requested rows")
    event_display = [name for name in DISPLAY_EVENT_FEATURES if name in base_names]
    events = pd.read_csv(
        corpus_dir / "crossing_events.csv",
        usecols=["event_id", *RELATIONAL_PROXY_FEATURES, *event_display],
    )
    if events["event_id"].duplicated().any():
        raise ValueError("crossing_events contains duplicate event IDs")
    aligned = ordered[["event_id"]].merge(
        events, on="event_id", how="left", validate="one_to_one", sort=False,
    )
    missing = aligned.loc[
        aligned[RELATIONAL_PROXY_FEATURES].isna().all(axis=1), "event_id"
    ].tolist()
    if missing:
        raise KeyError(f"relational features missing event IDs: {missing[:3]}")
    proxies = aligned[RELATIONAL_PROXY_FEATURES].fillna(0).to_numpy(dtype=float)
    names = [*base_names, *RELATIONAL_PROXY_FEATURES]
    kinds = {
        name: ("categorical" if name in CATEGORICAL_BASELINE_FEATURES else "numeric")
        for name in names
    }
    display = pd.concat(
        [ordered[["event_id"]], pd.DataFrame(base, columns=base_names),
         aligned[RELATIONAL_PROXY_FEATURES]], axis=1,
    )
    for name in event_display:
        display[name] = aligned[name]
    observed_display = {
        "age_bucket": "observed_dob_year_bucket",
        "sex": "observed_sex_marker",
    }
    requested_observed = {
        name: source for name, source in observed_display.items()
        if name in base_names
    }
    if requested_observed:
        observed = pd.read_csv(
            corpus_dir / "observed_person_records.csv",
            usecols=["observed_person_record_id", *requested_observed.values()],
        ).set_index("observed_person_record_id")
        for name, source in requested_observed.items():
            display[name] = ordered["primary_obs_id"].map(observed[source])
    return FeatureBundle(np.column_stack([base, proxies]), names, kinds, display)
```

- [ ] **Step 4: Run tests and verify GREEN**

Run the feature tests and the existing baseline tests:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_features.py tests/test_demo_baseline.py
```

Expected: all selected tests pass.

- [ ] **Step 5: Checkpoint the new isolated files**

If the current dirty-worktree baseline has been checkpointed by the user, run:

```bash
rtk git add gnn/unsupervised_features.py tests/test_unsupervised_features.py
rtk git commit -m "feat: add relational anomaly features"
```

Otherwise leave the files unstaged and record the completed task in the active task tracker; do not absorb pre-existing user changes into a commit.

### Task 2: Recent Unlabeled Calibration

**Files:**
- Modify: `gnn/unsupervised_ad.py:61-98`
- Modify: `tests/test_unsupervised_ad.py`

- [ ] **Step 1: Write failing calibration tests**

Append tests proving that labels are neither accepted nor needed:

```python
from gnn.unsupervised_ad import choose_recent_unlabeled_threshold


def test_recent_threshold_uses_validation_score_quantile_without_labels():
    threshold, meta = choose_recent_unlabeled_threshold(
        validation_scores=[-0.9, -0.5, -0.1, 0.2],
        contamination=0.25,
    )
    assert threshold == pytest.approx(0.9)
    assert meta == {
        "threshold_source": "validation_score_quantile",
        "threshold_quantile": 0.75,
        "threshold_source_samples": 4,
        "validation_labels_used_for_threshold": False,
        "score_direction": "higher_is_more_anomalous",
    }


@pytest.mark.parametrize("contamination", [0, -0.1, 1.1])
def test_recent_threshold_rejects_invalid_contamination(contamination):
    with pytest.raises(ValueError, match="interval"):
        choose_recent_unlabeled_threshold([-0.2, 0.1], contamination)
```

- [ ] **Step 2: Run the new test and verify RED**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_ad.py -k recent_threshold
```

Expected: import fails because the helper is missing.

- [ ] **Step 3: Implement the pure calibration helper**

Add without changing `choose_threshold`, preserving legacy behavior:

```python
def choose_recent_unlabeled_threshold(validation_scores, contamination=0.1):
    scores = np.asarray(validation_scores, dtype=float)
    if scores.size == 0 or not np.isfinite(scores).all():
        raise ValueError("validation_scores must contain finite values")
    if not 0 < contamination <= 1:
        raise ValueError("contamination must be in the interval (0, 1]")
    quantile = 1.0 - contamination
    threshold = np.quantile(-scores, quantile, method="higher")
    return float(threshold), {
        "threshold_source": "validation_score_quantile",
        "threshold_quantile": float(quantile),
        "threshold_source_samples": int(scores.size),
        "validation_labels_used_for_threshold": False,
        "score_direction": "higher_is_more_anomalous",
    }
```

- [ ] **Step 4: Run all anomaly threshold tests**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_ad.py
```

Expected: all tests pass and legacy strict/assisted assertions remain unchanged.

### Task 3: Ranked, Capacity, Hidden-Target, And Temporal Diagnostics

**Files:**
- Modify: `gnn/unsupervised_ad.py:100-272`
- Modify: `tests/test_unsupervised_ad.py`

- [ ] **Step 1: Write failing pure-diagnostic tests**

Add tests for threshold counts, bounded curves, hidden labels, and unique people:

```python
from gnn.unsupervised_ad import build_score_diagnostics


def test_score_diagnostics_include_capacity_hidden_and_people_metrics():
    rows = pd.DataFrame({
        "event_id": ["E1", "E2", "E3", "E4"],
        "primary_person_id": ["P1", "P1", "P2", "P3"],
        "t": pd.to_datetime([
            "2025-01-01T01:00Z", "2025-01-01T02:00Z",
            "2025-02-01T01:00Z", "2025-02-01T02:00Z"
        ]),
        "true_contraband_present": [True, True, False, True],
        "false_negative_flag": [True, True, False, False],
    })
    result = build_score_diagnostics(
        rows,
        anomaly_scores=np.array([0.9, 0.8, 0.7, 0.1]),
        threshold=0.75,
        ks=(1, 2, 4),
        daily_ks=(1,),
        max_curve_points=20,
    )
    assert result["all_contraband"]["confusion"] == {
        "tp": 2, "fp": 0, "fn": 1, "tn": 1,
    }
    assert result["hidden_false_negative"]["found"] == 2
    assert result["unique_people"]["positive_people"] == 2
    assert result["unique_people"]["found_people"] == 1
    assert result["capacity"]["found@2"] == 2
    assert result["daily_capacity"]["daily_budget@1"] == 2
    assert result["daily_capacity"]["daily_found@1"] == 1
    assert len(result["threshold_curve"]) <= 20
    assert {row["month"] for row in result["monthly"]} == {
        "2025-01", "2025-02"
    }


def test_single_class_diagnostics_return_null_rank_metrics():
    rows = pd.DataFrame({
        "event_id": ["E1", "E2"],
        "primary_person_id": ["P1", "P2"],
        "t": pd.to_datetime(["2025-01-01Z", "2025-01-02Z"]),
        "true_contraband_present": [False, False],
        "false_negative_flag": [False, False],
    })
    result = build_score_diagnostics(rows, [0.2, 0.1], 0.15, ks=(1,))
    assert result["all_contraband"]["average_precision"] is None
    assert result["all_contraband"]["roc_auc"] is None
    assert result["warnings"] == [
        "all_contraband has one label class",
        "hidden_false_negative has one label class",
    ]
```

- [ ] **Step 2: Run the tests and verify RED**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_ad.py -k diagnostics
```

Expected: import fails because `build_score_diagnostics` is missing.

- [ ] **Step 3: Extend the pool contract and implement diagnostics**

Load `false_negative_flag` beside the current target and normalize both with a
shared truthy conversion. Implement helpers with anomaly scores already oriented
so higher means more anomalous:

```python
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score


def _safe_rank_metrics(labels, scores, warning_name, warnings):
    labels = np.asarray(labels, dtype=bool)
    if np.unique(labels).size < 2:
        warnings.append(f"{warning_name} has one label class")
        return {"average_precision": None, "roc_auc": None}
    return {
        "average_precision": round(float(average_precision_score(labels, scores)), 6),
        "roc_auc": round(float(roc_auc_score(labels, scores)), 6),
    }


def _bounded_threshold_curve(labels, scores, max_points=200):
    precision, recall, thresholds = precision_recall_curve(labels, scores)
    rows = []
    for i, threshold in enumerate(thresholds):
        p, r = float(precision[i]), float(recall[i])
        f1 = 0.0 if p + r == 0 else 2 * p * r / (p + r)
        rows.append({"threshold": float(threshold), "precision": p,
                     "recall": r, "f1": f1,
                     "alert_rate": float((scores >= threshold).mean())})
    if len(rows) > max_points:
        keep = np.linspace(0, len(rows) - 1, max_points, dtype=int)
        rows = [rows[i] for i in np.unique(keep)]
    return rows


def build_score_diagnostics(rows, anomaly_scores, threshold, ks=(50, 100, 500),
                            daily_ks=(5, 10, 25), max_curve_points=200):
    frame = rows.reset_index(drop=True).copy()
    scores = np.asarray(anomaly_scores, dtype=float)
    if len(frame) != scores.size:
        raise ValueError("rows and anomaly_scores must have equal length")
    predicted = scores >= float(threshold)
    warnings = []

    def target_block(column, warning_name):
        labels = frame[column].to_numpy(dtype=bool)
        tp = int((predicted & labels).sum())
        fp = int((predicted & ~labels).sum())
        fn = int((~predicted & labels).sum())
        tn = int((~predicted & ~labels).sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) \
            if precision + recall else 0.0
        prevalence = float(labels.mean()) if labels.size else 0.0
        block = {
            "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
            "found": tp,
            "positive_count": int(labels.sum()),
            "precision": float(precision), "recall": float(recall),
            "f1": float(f1), "prevalence": prevalence,
            "alert_rate": float(predicted.mean()) if predicted.size else 0.0,
            "lift": float(precision / prevalence) if prevalence else None,
        }
        block.update(_safe_rank_metrics(labels, scores, warning_name, warnings))
        return block

    all_block = target_block("true_contraband_present", "all_contraband")
    hidden_block = target_block("false_negative_flag", "hidden_false_negative")
    all_labels = frame["true_contraband_present"].to_numpy(dtype=bool)
    hidden_labels = frame["false_negative_flag"].to_numpy(dtype=bool)

    capacity = {"ks": []}
    ranked = np.argsort(-scores, kind="stable")
    for requested in ks:
        k = min(int(requested), len(frame))
        if k <= 0:
            continue
        selected = ranked[:k]
        found = int(all_labels[selected].sum())
        precision = found / k
        recall = found / int(all_labels.sum()) if all_labels.sum() else 0.0
        prevalence = float(all_labels.mean()) if all_labels.size else 0.0
        capacity["ks"].append(k)
        capacity[f"found@{k}"] = found
        capacity[f"precision@{k}"] = float(precision)
        capacity[f"recall@{k}"] = float(recall)
        capacity[f"lift@{k}"] = float(precision / prevalence) if prevalence else None

    frame["day"] = frame["t"].dt.floor("D")
    daily_capacity = {"daily_ks": []}
    total_positives = int(all_labels.sum())
    for requested in daily_ks:
        k = int(requested)
        found = 0
        inspected = 0
        for _, day_rows in frame.groupby("day", sort=True):
            positions = day_rows.index.to_numpy()
            selected = positions[np.argsort(-scores[positions], kind="stable")[:k]]
            found += int(all_labels[selected].sum())
            inspected += len(selected)
        precision = found / inspected if inspected else 0.0
        recall = found / total_positives if total_positives else 0.0
        daily_capacity["daily_ks"].append(k)
        daily_capacity[f"daily_budget@{k}"] = inspected
        daily_capacity[f"daily_found@{k}"] = found
        daily_capacity[f"daily_precision@{k}"] = float(precision)
        daily_capacity[f"daily_recall@{k}"] = float(recall)

    positive_people = set(frame.loc[all_labels, "primary_person_id"].dropna())
    found_people = set(frame.loc[all_labels & predicted, "primary_person_id"].dropna())
    hidden_people = set(frame.loc[hidden_labels, "primary_person_id"].dropna())
    hidden_found_people = set(
        frame.loc[hidden_labels & predicted, "primary_person_id"].dropna()
    )
    people = {
        "positive_people": len(positive_people),
        "found_people": len(found_people),
        "hidden_positive_people": len(hidden_people),
        "hidden_found_people": len(hidden_found_people),
    }

    local_time = frame["t"].dt.tz_localize(None)
    frame["month"] = local_time.dt.to_period("M").astype(str)
    monthly = []
    for month, month_rows in frame.groupby("month", sort=True):
        positions = month_rows.index.to_numpy()
        labels = all_labels[positions]
        month_predicted = predicted[positions]
        tp = int((labels & month_predicted).sum())
        precision = tp / int(month_predicted.sum()) if month_predicted.sum() else 0.0
        recall = tp / int(labels.sum()) if labels.sum() else 0.0
        monthly.append({
            "month": month,
            "samples": int(len(positions)),
            "median_score": float(np.median(scores[positions])),
            "score_q10": float(np.quantile(scores[positions], 0.10)),
            "score_q90": float(np.quantile(scores[positions], 0.90)),
            "alert_rate": float(month_predicted.mean()),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(2 * precision * recall / (precision + recall))
                  if precision + recall else 0.0,
        })

    if np.unique(all_labels).size < 2:
        curve = []
    else:
        curve = _bounded_threshold_curve(all_labels, scores, max_curve_points)
    counts, edges = np.histogram(scores, bins=min(30, max(1, len(scores))))
    histogram = {
        "test": [{"low": float(edges[i]), "high": float(edges[i + 1]),
                  "count": int(counts[i])} for i in range(len(counts))]
    }
    return {
        "all_contraband": all_block,
        "hidden_false_negative": hidden_block,
        "unique_people": people,
        "capacity": capacity,
        "daily_capacity": daily_capacity,
        "threshold_curve": curve,
        "score_histogram": histogram,
        "monthly": monthly,
        "warnings": warnings,
    }
```

Add `_score_histograms({"train": train_scores, "validation": valid_scores,
"test": test_scores})` in Task 5 so the regional result replaces the test-only
histogram with common-bin train/validation/test distributions. The helper must
derive common finite edges from all three anomaly-score arrays and emit the
same `{low, high, count}` records used above.

```python
def _score_histograms(score_sets, bins=30):
    finite = np.concatenate([
        np.asarray(scores, dtype=float)[np.isfinite(scores)]
        for scores in score_sets.values()
    ])
    if finite.size == 0:
        return {name: [] for name in score_sets}
    low, high = float(finite.min()), float(finite.max())
    if low == high:
        high = low + 1e-12
    edges = np.linspace(low, high, bins + 1)
    output = {}
    for name, scores in score_sets.items():
        counts, _ = np.histogram(np.asarray(scores, dtype=float), bins=edges)
        output[name] = [
            {"low": float(edges[i]), "high": float(edges[i + 1]),
             "count": int(counts[i])}
            for i in range(len(counts))
        ]
    return output
```

- [ ] **Step 4: Add a deterministic person/day bootstrap helper**

Add a test using a fixed seed and then implement:

```python
def bootstrap_metric_ci(rows, anomaly_scores, threshold, group_col,
                        n_bootstrap=200, seed=42):
    rng = np.random.default_rng(seed)
    groups = rows[group_col].dropna().unique()
    if len(groups) < 2:
        return None
    estimates = []
    for _ in range(n_bootstrap):
        sampled = rng.choice(groups, size=len(groups), replace=True)
        indices = np.concatenate([
            rows.index[rows[group_col] == group].to_numpy() for group in sampled
        ])
        metrics = _evaluate_threshold(
            rows.loc[indices, "true_contraband_present"],
            -np.asarray(anomaly_scores)[indices], threshold,
        )
        estimates.append(metrics["f1"])
    low, high = np.quantile(estimates, [0.025, 0.975])
    return {"metric": "f1", "group": group_col,
            "low": float(low), "high": float(high),
            "samples": int(n_bootstrap), "seed": int(seed)}
```

Reset row indices before calling the helper so sampled positions align with
the score array. Use person bootstrap for aggregate test metrics and day
bootstrap for monthly/operational summaries.

- [ ] **Step 5: Run diagnostic tests and the legacy suite**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_ad.py tests/test_run_demo_smoke.py
```

Expected: all selected tests pass; legacy JSON keys asserted by smoke tests are unchanged.

### Task 4: Bounded Rarity And Sensitivity Explainability

**Files:**
- Create: `gnn/unsupervised_explain.py`
- Create: `tests/test_unsupervised_explain.py`

- [ ] **Step 1: Write failing deterministic explanation tests**

Use a fake model whose anomaly score equals the first feature:

```python
import numpy as np
import pandas as pd

from gnn.unsupervised_explain import explain_top_alerts


class FirstFeatureModel:
    def decision_function(self, X):
        return -np.asarray(X)[:, 0]


def test_explanation_reports_positive_replacement_sensitivity_and_rarity():
    train = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 1.0]])
    test = np.array([[10.0, 1.0], [3.0, 0.0]])
    rows = pd.DataFrame({"event_id": ["E1", "E2"]})
    result = explain_top_alerts(
        FirstFeatureModel(), train, test, rows,
        anomaly_scores=np.array([10.0, 3.0]),
        feature_names=["count", "category"],
        feature_kinds={"count": "numeric", "category": "categorical"},
        train_display_values=pd.DataFrame({
            "count": [0, 1, 2], "category": ["common", "common", "rare"],
        }),
        display_values=pd.DataFrame({
            "event_id": ["E1", "E2"], "count": [10, 3],
            "category": ["rare", "common"],
        }),
        threshold=5.0, limit=1,
    )
    alert = result["alerts"][0]
    count = next(item for item in alert["features"] if item["feature"] == "count")
    assert alert["event_id"] == "E1"
    assert count["reference_value"] == 1.0
    assert count["sensitivity_delta"] == 9.0
    assert count["rarity"] == 1.0
    assert alert["predicted"] is True
    assert result["global_influence"][0]["feature"] == "count"
```

- [ ] **Step 2: Run the test and verify RED**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_explain.py
```

Expected: collection fails because the module is missing.

- [ ] **Step 3: Implement regional references and rarity**

```python
def _reference(train_column, kind):
    values = np.asarray(train_column)
    if kind == "numeric":
        return float(np.median(values.astype(float)))
    unique, counts = np.unique(values, return_counts=True)
    return unique[int(np.argmax(counts))].item()


def _rarity(value, train_column, kind):
    values = np.asarray(train_column)
    if kind == "categorical":
        return float(1.0 - np.mean(values == value))
    numeric = values.astype(float)
    lower = np.mean(numeric <= float(value))
    upper = np.mean(numeric >= float(value))
    return float(np.clip(1.0 - 2.0 * min(lower, upper), 0.0, 1.0))
```

- [ ] **Step 4: Implement replacement sensitivity and aggregation**

`explain_top_alerts` must sort by descending anomaly score, limit before
rescoring, replace one feature at a time, and return JSON-native values:

```python
def explain_top_alerts(model, X_train, X_test, rows, anomaly_scores,
                       feature_names, feature_kinds, train_display_values,
                       display_values, threshold, limit=25):
    order = np.argsort(-np.asarray(anomaly_scores))[:limit]
    references = np.array([
        _reference(X_train[:, i], feature_kinds[name])
        for i, name in enumerate(feature_names)
    ], dtype=float)
    reference_display = {}
    for feature_index, name in enumerate(feature_names):
        if feature_kinds[name] == "categorical":
            matching = np.flatnonzero(
                np.asarray(X_train)[:, feature_index] == references[feature_index]
            )
            reference_display[name] = _json_value(
                train_display_values.iloc[int(matching[0])][name]
            )
        else:
            reference_display[name] = _json_value(references[feature_index])
    alerts = []
    influence = {name: [] for name in feature_names}
    for row_index in order:
        original = np.asarray(X_test[row_index], dtype=float)
        features = []
        for feature_index, name in enumerate(feature_names):
            replaced = original.copy()
            replaced[feature_index] = references[feature_index]
            replacement_score = -float(model.decision_function(replaced[None, :])[0])
            delta = float(anomaly_scores[row_index] - replacement_score)
            influence[name].append(delta)
            features.append({
                "feature": name,
                "observed_value": _json_value(display_values.iloc[row_index][name]),
                "reference_value": reference_display[name],
                "rarity": _rarity(original[feature_index],
                                  X_train[:, feature_index], feature_kinds[name]),
                "sensitivity_delta": delta,
            })
        alerts.append({"event_id": str(rows.iloc[row_index]["event_id"]),
                       "anomaly_score": float(anomaly_scores[row_index]),
                       "predicted": bool(anomaly_scores[row_index] >= threshold),
                       "features": sorted(features,
                                          key=lambda item: -abs(item["sensitivity_delta"]))})
    global_influence = sorted([
        {"feature": name,
         "mean_absolute_sensitivity": float(np.mean(np.abs(values))),
         "mean_positive_sensitivity": float(np.mean(np.maximum(values, 0.0)))}
        for name, values in influence.items()
    ], key=lambda item: -item["mean_absolute_sensitivity"])
    return {"method": "reference_replacement_sensitivity",
            "causal": False, "additive": False,
            "alerts": alerts, "global_influence": global_influence}
```

Add `_json_value` to convert NumPy scalars and missing values to JSON-native
numbers, strings, booleans, or null:

```python
def _json_value(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
```

- [ ] **Step 5: Run explanation tests**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_explain.py
```

Expected: all explanation tests pass.

### Task 5: Integrate The Additive Relational Arm

**Files:**
- Modify: `gnn/unsupervised_ad.py:210-340`
- Modify: `tests/test_unsupervised_ad.py`

- [ ] **Step 1: Write a failing regional-arm integration test**

Monkeypatch the forest and feature cache so the test can assert provenance
without loading a corpus:

```python
from gnn.unsupervised_ad import _run_relational_region


def test_relational_region_is_label_free_and_uses_recent_calibration(monkeypatch):
    region = pd.DataFrame({
        "event_id": ["T1", "T2", "V1", "V2", "E1", "E2"],
        "split": ["train", "train", "validation", "validation", "test", "test"],
        "true_contraband_present": [True, False, True, False, True, False],
        "false_negative_flag": [True, False, True, False, True, False],
        "primary_person_id": ["P1", "P2", "P3", "P4", "P5", "P6"],
        "t": pd.to_datetime([
            "2023-01-01Z", "2023-01-02Z", "2024-01-01Z",
            "2024-01-02Z", "2025-01-01Z", "2025-01-02Z",
        ]),
    })
    cache = {event_id: np.array([i], dtype=float)
             for i, event_id in enumerate(region.event_id)}
    result = _run_relational_region(
        region, feature_cache=cache, feature_names=["x"],
        feature_kinds={"x": "numeric"},
        display_values=region[["event_id"]].assign(x=range(6)),
        contamination=0.5, n_estimators=10, explanation_limit=1,
        n_bootstrap=10,
    )
    assert result["labels_used_for_fit"] is False
    assert result["validation_labels_used_for_threshold"] is False
    assert result["threshold_source"] == "validation_score_quantile"
    assert result["score_direction"] == "higher_is_more_anomalous"
```

- [ ] **Step 2: Run the integration test and verify RED**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_ad.py -k relational_region
```

Expected: import fails because `_run_relational_region` is missing.

- [ ] **Step 3: Implement `_run_relational_region`**

Use all training rows, fit the existing fixed-seed forest, derive recent
threshold from validation scores, freeze it, then call the diagnostics and
explanation helpers:

```python
def _run_relational_region(region_df, feature_cache, feature_names,
                           feature_kinds, display_values, contamination=0.1,
                           n_estimators=100, explanation_limit=25,
                           n_bootstrap=200):
    train_df = region_df.loc[region_df["split"] == "train"].reset_index(drop=True)
    valid_df = region_df.loc[
        region_df["split"] == "validation"
    ].reset_index(drop=True)
    test_df = region_df.loc[region_df["split"] == "test"].reset_index(drop=True)
    X_train = cached_feature_rows(train_df, feature_cache)
    X_valid = cached_feature_rows(valid_df, feature_cache)
    X_test = cached_feature_rows(test_df, feature_cache)

    model = IsolationForest(
        n_estimators=n_estimators, random_state=42, n_jobs=-1
    ).fit(X_train)
    train_decision = model.decision_function(X_train)
    valid_decision = model.decision_function(X_valid)
    test_decision = model.decision_function(X_test)
    train_anomaly, valid_anomaly, test_anomaly = (
        -train_decision, -valid_decision, -test_decision
    )
    threshold, threshold_meta = choose_recent_unlabeled_threshold(
        valid_decision, contamination
    )
    validation_metrics = _evaluate_threshold(
        valid_df["true_contraband_present"], valid_decision, threshold
    )
    test_metrics = _evaluate_threshold(
        test_df["true_contraband_present"], test_decision, threshold
    )
    diagnostics = build_score_diagnostics(test_df, test_anomaly, threshold)
    diagnostics["score_histogram"] = _score_histograms({
        "train": train_anomaly,
        "validation": valid_anomaly,
        "test": test_anomaly,
    })
    bootstrap_rows = test_df.copy()
    bootstrap_rows["day"] = bootstrap_rows["t"].dt.floor("D")
    diagnostics["confidence_intervals"] = {
        "person_f1": bootstrap_metric_ci(
            bootstrap_rows, test_anomaly, threshold,
            "primary_person_id", n_bootstrap=n_bootstrap, seed=42,
        ),
        "day_f1": bootstrap_metric_ci(
            bootstrap_rows, test_anomaly, threshold,
            "day", n_bootstrap=n_bootstrap, seed=43,
        ),
    }

    display_index = display_values.set_index("event_id", drop=False)
    train_display = display_index.loc[train_df["event_id"]].reset_index(drop=True)
    test_display = display_index.loc[test_df["event_id"]].reset_index(drop=True)
    explanations = explain_top_alerts(
        model, X_train, X_test, test_df, test_anomaly,
        feature_names, feature_kinds, train_display, test_display,
        threshold, limit=explanation_limit,
    )
    return {
        "arm": "relational_strict",
        "labels_used_for_fit": False,
        "validation_labels_used_for_threshold": False,
        **threshold_meta,
        "feature_names": feature_names,
        "model": {"class": "IsolationForest", "parameters": model.get_params()},
        "train_fit_samples": int(len(train_df)),
        "valid_samples": int(len(valid_df)),
        "test_samples": int(len(test_df)),
        "validation": validation_metrics,
        "test": test_metrics,
        "test_precision": test_metrics["precision"],
        "test_recall": test_metrics["recall"],
        "test_f1": test_metrics["f1"],
        "diagnostics": diagnostics,
        "explainability": explanations,
    }
```

Do not route this arm through `prepare_training_rows`; that helper has legacy
mode semantics. Add `RELATIONAL_ARM_METADATA` with the relational-proxy and
oracle-identity limitations stated explicitly.

- [ ] **Step 4: Add the arm without changing legacy mode output**

In `main`, build the legacy cache exactly as today, build one relational bundle,
and add:

```python
arms = {"relational_strict": {}}
for region in regions:
    region_df = df[df["region"] == region].copy()
    if _insufficient_region(region_df):
        arms["relational_strict"][region] = {
            "status": "skipped", "reason": "fewer than 50 rows in a required split"
        }
        continue
    arms["relational_strict"][region] = _run_relational_region(
        region_df,
        feature_cache=relational_cache,
        feature_names=relational_bundle.names,
        feature_kinds=relational_bundle.kinds,
        display_values=relational_bundle.display,
        contamination=contamination,
        n_estimators=n_estimators,
        explanation_limit=explanation_limit,
        n_bootstrap=n_bootstrap,
    )
```

Keep `modes` byte-compatible in structure and key names. Fix the misleading
legacy `train_normal_samples` field only by adding the honest
`train_fit_samples`; do not reinterpret the historical field in this task.

- [ ] **Step 5: Add micro and macro arm aggregation**

Write a test with two synthetic regional results, then implement:

```python
def aggregate_arm_results(region_results):
    completed = [result for result in region_results.values()
                 if result.get("status") != "skipped"]
    metrics = [result["diagnostics"]["all_contraband"] for result in completed]
    if not metrics:
        return {"regions": 0, "micro": None, "macro": None}
    confusion = {
        key: sum(metric["confusion"][key] for metric in metrics)
        for key in ("tp", "fp", "fn", "tn")
    }
    tp, fp = confusion["tp"], confusion["fp"]
    fn = confusion["fn"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    micro_f1 = 2 * precision * recall / (precision + recall) \
        if precision + recall else 0.0
    macro_keys = ("precision", "recall", "f1", "average_precision", "roc_auc")
    macro = {}
    for key in macro_keys:
        values = [metric[key] for metric in metrics if metric[key] is not None]
        macro[key] = float(np.mean(values)) if values else None
    return {
        "regions": len(completed),
        "micro": {"confusion": confusion, "precision": precision,
                  "recall": recall, "f1": micro_f1},
        "macro": macro,
    }
```

Store this under `arm_aggregates.relational_strict`; do not synthesize legacy
aggregates from rounded fields in the compatibility tree.

- [ ] **Step 6: Run all source tests**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_ad.py tests/test_unsupervised_features.py tests/test_unsupervised_explain.py
```

Expected: all selected tests pass.

### Task 6: Schema V3 Provenance And Corpus-qualified Outputs

**Files:**
- Modify: `gnn/unsupervised_ad.py:275-340`
- Modify: `tests/test_unsupervised_ad.py`

- [ ] **Step 1: Write failing provenance and output-path tests**

```python
from pathlib import Path

from gnn.unsupervised_ad import build_run_provenance, corpus_output_path


def test_corpus_output_path_is_version_qualified(tmp_path):
    corpus = tmp_path / "synthetic_cbp_graph_corpus_v9"
    corpus.mkdir()
    assert corpus_output_path(tmp_path, corpus).name == "unsupervised_ad_results_v9.json"


def test_provenance_fingerprint_changes_when_required_input_changes(tmp_path):
    corpus = tmp_path / "synthetic_cbp_graph_corpus_v9dev"
    corpus.mkdir()
    for name in ("crossing_events.csv", "event_ground_truth.csv",
                 "train_valid_test_splits.csv", "observed_person_records.csv"):
        (corpus / name).write_text(name)
    first = build_run_provenance(corpus)
    (corpus / "event_ground_truth.csv").write_text("changed")
    second = build_run_provenance(corpus)
    assert first["corpus_name"] == "synthetic_cbp_graph_corpus_v9dev"
    assert first["snapshot_sha256"] != second["snapshot_sha256"]
```

- [ ] **Step 2: Run tests and verify RED**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_ad.py -k "provenance or corpus_output"
```

Expected: missing helper imports.

- [ ] **Step 3: Implement deterministic provenance**

```python
import hashlib
import importlib.metadata
import subprocess
from datetime import datetime, timezone


REQUIRED_PROVENANCE_FILES = (
    "crossing_events.csv", "event_ground_truth.csv",
    "train_valid_test_splits.csv", "observed_person_records.csv",
)


def _snapshot_sha256(corpus_dir):
    digest = hashlib.sha256()
    for name in REQUIRED_PROVENANCE_FILES:
        path = corpus_dir / name
        digest.update(name.encode())
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def build_run_provenance(corpus_dir):
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=FC.REPO_ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    try:
        corpus_path = str(corpus_dir.relative_to(FC.REPO_ROOT))
    except ValueError:
        corpus_path = str(corpus_dir)
    packages = {}
    for name in ("numpy", "pandas", "scikit-learn"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "corpus_name": corpus_dir.name,
        "corpus_path": corpus_path,
        "snapshot_sha256": _snapshot_sha256(corpus_dir),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_revision": revision,
        "packages": packages,
    }


def corpus_output_path(results_dir, corpus_dir):
    suffix = corpus_dir.name.rsplit("_", 1)[-1]
    return Path(results_dir) / f"unsupervised_ad_results_{suffix}.json"
```

- [ ] **Step 4: Write schema-v3 payload to both paths**

Build one payload with `schema_version: 3`, legacy `modes`, additive `arms`,
`provenance`, `target_contract`, and `split_contract`. Serialize it once, then
write identical bytes to the corpus-qualified path and compatibility path.
Return the payload plus output paths from a small `write_results` helper so the
test can use `tmp_path` without mutating checked-in diagnostics.

```python
def build_split_contract(rows):
    frame = rows.copy()
    frame["t"] = pd.to_datetime(frame["t"], utc=True, errors="coerce")
    ranges = {}
    for split, group in frame.groupby("split", sort=True):
        ranges[str(split)] = {
            "samples": int(len(group)),
            "start_utc": group["t"].min().isoformat(),
            "end_utc": group["t"].max().isoformat(),
        }
    return {
        "strategy": "temporal_returning_entity",
        "group_holdout_enforced": False,
        "ranges": ranges,
    }


def write_results(payload, results_dir, corpus_dir):
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    qualified = corpus_output_path(results_dir, corpus_dir)
    compatibility = results_dir / "unsupervised_ad_results.json"
    serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    qualified.write_text(serialized)
    compatibility.write_text(serialized)
    return {"qualified": qualified, "compatibility": compatibility}
```

Assemble the final payload in `main` with these stable top-level keys:

```python
output = {
    "schema_version": 3,
    "default_mode": first_mode,
    "identity_substrate": "oracle canonical_person_id",
    "feature_names": feature_names,
    "contamination": float(contamination),
    "mode_metadata": {name: MODE_METADATA[name] for name in modes},
    "modes": results_by_mode,
    "arm_metadata": {"relational_strict": RELATIONAL_ARM_METADATA},
    "arms": arms,
    "arm_aggregates": {
        "relational_strict": aggregate_arm_results(arms["relational_strict"])
    },
    "target_contract": {
        "primary": "true_contraband_present",
        "incremental": "false_negative_flag",
        "labels_used_for_evaluation_only": True,
    },
    "split_contract": build_split_contract(df),
    "provenance": build_run_provenance(corpus_dir),
}
write_results(output, results_dir, corpus_dir)
```

- [ ] **Step 5: Run provenance and full anomaly tests**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_ad.py tests/test_unsupervised_features.py tests/test_unsupervised_explain.py
```

Expected: all selected tests pass.

### Task 7: V9dev End-to-end Smoke And Documentation

**Files:**
- Modify: `tests/test_unsupervised_ad.py`
- Modify: `Documents/Data/changes_3.md`

- [ ] **Step 1: Add a V9dev smoke test with bounded runtime knobs**

Expose `main(corpus_dir=None, results_dir=None, modes=None,
include_relational=True, n_estimators=100, explanation_limit=25,
n_bootstrap=200)` while preserving no-argument CLI behavior. Test with V9dev,
10 trees, 2 explanations, and 10 bootstrap samples:

```python
def test_v9dev_relational_arm_smoke(tmp_path):
    corpus = Path(__file__).resolve().parents[1] / \
        "Documents/Data/synthetic_cbp_graph_corpus_v9dev"
    output = main(
        corpus_dir=corpus, results_dir=tmp_path,
        modes=["strict", "assisted"], include_relational=True,
        n_estimators=10, explanation_limit=2, n_bootstrap=10,
    )
    assert output["schema_version"] == 3
    assert set(output["modes"]) == {"strict", "assisted"}
    assert "relational_strict" in output["arms"]
    for result in output["arms"]["relational_strict"].values():
        if result.get("status") == "skipped":
            continue
        assert result["labels_used_for_fit"] is False
        assert len(result["explainability"]["alerts"]) <= 2
```

- [ ] **Step 2: Run the smoke test and fix only contract failures**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_ad.py::test_v9dev_relational_arm_smoke
```

Expected: pass within a few minutes on V9dev. Do not loosen as-of assertions or
skip regions merely to make the test green.

- [ ] **Step 3: Update the canonical V9 research log**

Add a dated section to `Documents/Data/changes_3.md` containing:

```markdown
## Relational Strict Unsupervised Arm (2026-07-15)

- Preserves the legacy strict and assisted arms unchanged.
- Fits Isolation Forest without target labels and calibrates the threshold from
  the recent unlabeled validation-score distribution.
- Adds party size and as-of 365-day person/vehicle/document history as explicit
  relational proxies; it is not the fair non-graph baseline or an unsupervised GNN.
- Reports all-contraband and hidden-false-negative evaluation separately.
- Explanation values are regional rarity and reference-replacement sensitivity,
  not probabilities, SHAP values, additive attributions, or causal effects.
- The benchmark still uses oracle synthetic identity resolution.
```

- [ ] **Step 4: Run the entire source suite**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q
```

Expected: zero failures. Record the total passed count and any pre-existing warnings.

### Task 8: Regenerate V9 Diagnostics And Verify The Core Deliverable

**Files:**
- Regenerate: `gnn/diagnostics/unsupervised_ad_results_v9.json`
- Regenerate: `gnn/diagnostics/unsupervised_ad_results.json`

- [ ] **Step 1: Run the full V9 artifact generation**

```bash
rtk env PYTHONPATH=. CBP_CORPUS_DIR=Documents/Data/synthetic_cbp_graph_corpus_v9 .venv/bin/python -m gnn.unsupervised_ad
```

Expected: four regional legacy strict results, four assisted results, four
relational-strict results, and two written schema-v3 artifact paths.

- [ ] **Step 2: Verify artifact identity and compatibility**

```bash
rtk .venv/bin/python -c "import json; p=json.load(open('gnn/diagnostics/unsupervised_ad_results_v9.json')); assert p['schema_version']==3; assert set(p['modes'])=={'strict','assisted'}; assert 'relational_strict' in p['arms']; assert p['provenance']['corpus_name'].endswith('v9'); print('schema-v3 artifact verified')"
```

Expected: `schema-v3 artifact verified`.

- [ ] **Step 3: Compare legacy mode values before accepting regeneration**

Use a short read-only comparison script against the pre-regeneration artifact
captured before Task 8. Assert equality for every legacy regional
`test_precision`, `test_recall`, `test_f1`, threshold, and sample count. Any
difference requires diagnosis before continuing.

- [ ] **Step 4: Run final core verification**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest -q
rtk git diff --check
rtk git status --short
```

Expected: tests pass, diff check exits zero, and status contains only intended
core, diagnostic, documentation, and pre-existing user changes.
