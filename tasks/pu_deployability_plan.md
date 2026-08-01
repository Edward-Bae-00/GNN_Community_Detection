# Caught-Supervised Deployability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a leak-free A/B/C deployability comparison plus a 14-feature caught-supervised ablation, using only as-of observable catches for learning and reserving synthetic carrier truth for frozen retrospective evaluation.

**Architecture:** Keep the existing schema-v2 `strict` and `assisted` computations reproducible, but move the new comparison into explicitly named schema-v3 `arms`. Feature construction and caught-supervised learning live in focused modules; fitting and label-free operating-point selection run on oracle-free frames, and a separate evaluation stage joins synthetic truth only after scores and thresholds are frozen. All model claims are conditional on the existing oracle identity-resolution substrate.

**Tech Stack:** Python 3.14, pandas, NumPy, scikit-learn Isolation Forest, HistGradientBoostingClassifier, pytest, JSON, generated dashboard HTML/JavaScript.

---

## Research And Naming Contract

Primary arms:

| ID | Display label | Fit signal | Features | Threshold |
|---|---|---|---|---|
| `tabular_unlabeled` | Tabular unlabeled | Unlabeled feature distribution | 14 | Validation-score quantile |
| `relational_unlabeled` | Relational-proxy unlabeled | Unlabeled feature distribution | 14 + 4 | Validation-score quantile |
| `relational_caught_supervised` | Relational caught-supervised | As-of observed catches vs unlabeled | 14 + 4 | Validation-score quantile |

Appendix ablation:

| ID | Display label | Fit signal | Features | Threshold |
|---|---|---|---|---|
| `tabular_caught_supervised` | Tabular caught-supervised | As-of observed catches vs unlabeled | 14 | Validation-score quantile |

The caught-supervised arms are naive-PU/historical-enforcement rankers. Scores are not carrier probabilities, the Elkan-Noto/SCAR ranking guarantee is not claimed, and the validation quantile is an operating-point policy rather than probability calibration.

`assisted` remains reproducible only under `legacy_oracle_benchmarks`; it is not a ceiling and is not shown in the primary lineup. Existing consumers may continue reading the legacy `modes` tree during the schema transition.

## Fixed As-Of And Evaluation Contract

- Training fit-as-of time is the start of the validation split: `2024-01-01T00:00:00Z` for V9.
- The operational caught source is the observed seizure/catch outcome plus `label_available_time_utc`; no target is derived from `true_contraband_present`.
- A training event is positive only when the observed caught outcome is true and its label availability is strictly before fit-as-of.
- An eventual catch whose label is immature at fit-as-of remains in the unlabeled pool. Metadata records the immature-row count without using future carrier truth for fitting.
- Validation thresholds use scores only. Hyperparameters and contamination are frozen before oracle evaluation.
- Oracle evaluation happens in a separate function after model scores and thresholds have been produced.
- Evaluation strata are: all carrier events, missed-at-this-event, no-prior-catch missed events, lifetime-never-caught people, unique-person first hits, and observed-catch enrichment.
- The identity claim is `deployable label/threshold semantics conditional on resolved identity`; artifacts must continue declaring `oracle canonical_person_id`.

## File Map

- Create `gnn/unsupervised_features.py`: aligned 14/18-feature bundles, raw categorical display values, train-only categorical encoding.
- Create `gnn/pu_learning.py`: as-of caught-label snapshots, deterministic HGB fitting/scoring, quantile operating point, oracle-free arm execution.
- Modify `gnn/unsupervised_ad.py`: orchestrate four new arms, frozen oracle evaluation, schema-v3 output, legacy benchmark quarantine.
- Create `tests/test_unsupervised_features.py`: feature alignment, proxy contract, categorical encoding.
- Create `tests/test_pu_learning.py`: label maturity, deterministic model, threshold, oracle firewall.
- Modify `tests/test_unsupervised_ad.py`: arm/schema integration and evaluation-target arithmetic.
- Modify `Documents/Data/scripts/build_v9_dashboard.py`: expose schema-v3 arms without making legacy assisted primary.
- Modify `Documents/Data/scripts/v9_dashboard_ui.py`: render A/B/C plus ablation and disclosures.
- Modify `tests/test_v9_dashboard_builder.py`: dashboard schema/copy contracts.
- Modify `Documents/Data/changes_3.md`: document SCAR violation, maturity rule, arm definitions, and conditional deployability.
- Regenerate `gnn/diagnostics/unsupervised_ad_results_v9.json`, compatibility diagnostics, and V9 dashboard artifacts only after source tests pass.

### Task 1: Relational Feature Bundle And Train-Only Encoding

**Files:**
- Create: `gnn/unsupervised_features.py`
- Create: `tests/test_unsupervised_features.py`

- [x] **Step 1: Write failing alignment and encoding tests**

```python
def test_relational_bundle_preserves_requested_event_order(tmp_path, monkeypatch):
    rows = pd.DataFrame({"event_id": ["E2", "E1"], "primary_obs_id": ["O2", "O1"],
                         "t": pd.to_datetime(["2023-01-02Z", "2023-01-01Z"])})
    bundle = build_relational_feature_bundle(rows, tmp_path, {})
    assert bundle.event_ids == ["E2", "E1"]
    assert bundle.names[-4:] == RELATIONAL_PROXY_FEATURES


def test_encoder_learns_categories_from_training_rows_only():
    encoded = encode_feature_splits(train, validation, test, names, categorical_names)
    assert encoded.validation[0, names.index("region")] == -1
    assert encoded.test[0, names.index("region")] == -1
```

- [x] **Step 2: Run RED**

Run: `rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_features.py`

Expected: collection fails because `gnn.unsupervised_features` does not exist.

- [x] **Step 3: Implement the minimal feature API**

```python
RELATIONAL_PROXY_FEATURES = [
    "party_size",
    "repeat_crossing_count_prior_365d",
    "same_vehicle_crossing_count_prior_365d",
    "same_document_crossing_count_prior_365d",
]

@dataclass(frozen=True)
class FeatureBundle:
    event_ids: list[str]
    matrix: np.ndarray
    names: list[str]
    categorical_names: frozenset[str]
    display: pd.DataFrame

def build_relational_feature_bundle(rows, corpus_dir, obs_to_identity) -> FeatureBundle:
    """Return aligned 14+4 values and raw display categories; fail on missing IDs."""

def encode_feature_splits(train, validation, test, names, categorical_names):
    """Fit OrdinalEncoder on train only; encode unknown validation/test values as -1."""
```

- [x] **Step 4: Run GREEN and regression tests**

Run: `rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_features.py tests/test_demo_baseline.py`

Expected: all selected tests pass.

### Task 2: As-Of Caught Labels And Label-Free Operating Point

**Files:**
- Create: `gnn/pu_learning.py`
- Create: `tests/test_pu_learning.py`

- [x] **Step 1: Write failing maturity and threshold tests**

```python
def test_caught_snapshot_keeps_immature_catches_unlabeled():
    rows = pd.DataFrame({
        "seizure_flag": [True, True, False],
        "label_available_time_utc": [
            "2023-12-31T00:00:00Z", "2024-01-02T00:00:00Z", "2023-12-30T00:00:00Z"
        ],
    })
    snapshot = build_caught_snapshot(rows, "2024-01-01T00:00:00Z")
    assert snapshot.labels.tolist() == [1, 0, 0]
    assert snapshot.immature_rows == 1


def test_operating_threshold_uses_validation_scores_without_labels():
    threshold, meta = choose_score_quantile([0.1, 0.2, 0.8, 0.9], alert_rate=0.25)
    assert threshold == pytest.approx(0.9)
    assert meta["threshold_source"] == "validation_score_quantile"
    assert meta["labels_used_for_threshold"] is False
    assert meta["score_direction"] == "higher_is_more_alert_worthy"
```

- [x] **Step 2: Run RED**

Run: `rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_pu_learning.py -k 'snapshot or operating'`

Expected: collection fails because `gnn.pu_learning` does not exist.

- [x] **Step 3: Implement pure snapshot and threshold helpers**

```python
@dataclass(frozen=True)
class CaughtSnapshot:
    labels: np.ndarray
    fit_as_of: str
    positive_rows: int
    immature_rows: int

def build_caught_snapshot(rows, fit_as_of) -> CaughtSnapshot:
    available = pd.to_datetime(rows["label_available_time_utc"], utc=True) < pd.Timestamp(fit_as_of)
    caught = parse_bool(rows["seizure_flag"])
    labels = (caught & available).astype(np.uint8).to_numpy()
    return CaughtSnapshot(labels, pd.Timestamp(fit_as_of).isoformat(),
                          int(labels.sum()), int((~available).sum()))

def choose_score_quantile(validation_scores, alert_rate=0.1):
    """Return a higher-score threshold plus explicit >= tie behavior and realized rate."""
```

- [x] **Step 4: Run GREEN**

Run: `rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_pu_learning.py -k 'snapshot or operating'`

Expected: all selected tests pass.

### Task 3: Deterministic Caught-Supervised And Unlabeled Arm Runner

**Files:**
- Modify: `gnn/pu_learning.py`
- Modify: `tests/test_pu_learning.py`

- [x] **Step 1: Write failing deterministic and failure-behavior tests**

```python
def test_caught_supervised_scores_are_deterministic():
    first = fit_caught_supervised(X_train, y_caught, X_validation, X_test, seed=42)
    second = fit_caught_supervised(X_train, y_caught, X_validation, X_test, seed=42)
    np.testing.assert_array_equal(first.validation_scores, second.validation_scores)
    np.testing.assert_array_equal(first.test_scores, second.test_scores)


def test_caught_supervised_rejects_training_without_both_label_classes():
    with pytest.raises(ValueError, match="both caught and unlabeled"):
        fit_caught_supervised(X_train, np.zeros(len(X_train)), X_validation, X_test)
```

- [x] **Step 2: Run RED**

Run: `rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_pu_learning.py -k 'deterministic or both_label'`

Expected: tests fail because the runner is absent.

- [x] **Step 3: Fit once and score every split with one frozen model**

```python
def fit_caught_supervised(X_train, y_caught, X_validation, X_test, seed=42):
    model = HistGradientBoostingClassifier(
        class_weight="balanced", random_state=seed,
        early_stopping=False, validation_fraction=None,
    )
    model.fit(X_train, y_caught)
    return FrozenScores(
        validation_scores=model.predict_proba(X_validation)[:, 1],
        test_scores=model.predict_proba(X_test)[:, 1],
        model_metadata={"class": type(model).__name__, "parameters": model.get_params()},
    )
```

Add the parallel Isolation Forest runner with normalized `higher_is_more_anomalous` scores. Both runners must accept feature arrays and observable caught labels only; oracle columns are not accepted by their APIs.

- [x] **Step 4: Run GREEN**

Run: `rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_pu_learning.py`

Expected: all PU unit tests pass.

### Task 4: Frozen Oracle Evaluation And Metamorphic Firewall

**Files:**
- Modify: `gnn/unsupervised_ad.py`
- Modify: `tests/test_unsupervised_ad.py`

- [x] **Step 1: Write failing evaluation-strata arithmetic tests**

```python
def test_evaluation_distinguishes_missed_event_from_lifetime_never_caught():
    metrics = evaluate_frozen_scores(scored_events, oracle_events, threshold=0.5)
    assert metrics["all_carrier_events"]["positive_count"] == 3
    assert metrics["missed_at_event"]["positive_count"] == 2
    assert metrics["lifetime_never_caught_people"]["positive_count"] == 1
    assert metrics["unique_person_first_hits"]["found"] == 1
```

- [x] **Step 2: Write the failing oracle-invariance test**

```python
def test_oracle_mutation_cannot_change_frozen_scores_or_threshold(monkeypatch):
    first = run_deployable_arms(observable_rows, feature_bundle, fit_as_of=FIT_AS_OF)
    mutated_oracle = oracle_rows.assign(
        true_contraband_present=~oracle_rows.true_contraband_present,
        false_negative_flag=~oracle_rows.false_negative_flag,
    )
    second = run_deployable_arms(observable_rows, feature_bundle, fit_as_of=FIT_AS_OF)
    assert frozen_payload(first) == frozen_payload(second)
    assert evaluate_frozen_arms(first, oracle_rows) != evaluate_frozen_arms(first, mutated_oracle)
```

- [x] **Step 3: Run RED**

Run: `rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_ad.py -k 'evaluation_distinguishes or oracle_mutation'`

Expected: tests fail because the frozen runner/evaluator boundary is absent.

- [x] **Step 4: Implement the physical data boundary**

```python
def load_observable_pool(corpus_dir) -> pd.DataFrame:
    """Load event IDs, split, time, region, observed IDs/outcomes, and availability only."""

def load_oracle_evaluation(corpus_dir) -> pd.DataFrame:
    """Load synthetic carrier targets; never called by fit or threshold helpers."""

def run_deployable_arms(observable_rows, feature_bundle, *, fit_as_of, alert_rate, seed):
    """Return frozen per-arm scores, thresholds, model/label provenance, and no oracle metrics."""

def evaluate_frozen_arms(frozen, oracle_rows):
    """Join oracle truth after freezing and compute event/person target strata."""
```

- [x] **Step 5: Run GREEN and current anomaly regressions**

Run: `rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_ad.py tests/test_pu_learning.py`

Expected: all selected tests pass.

### Task 5: Schema-V3 A/B/C Integration And Legacy Quarantine

**Files:**
- Modify: `gnn/unsupervised_ad.py`
- Modify: `tests/test_unsupervised_ad.py`

- [x] **Step 1: Write failing schema and arm tests**

```python
def test_schema_v3_has_three_primary_arms_and_one_ablation(tmp_path):
    output = main(corpus_dir=V9DEV, results_dir=tmp_path, n_estimators=10)
    assert output["schema_version"] == 3
    assert output["primary_arm_order"] == [
        "tabular_unlabeled", "relational_unlabeled", "relational_caught_supervised"
    ]
    assert "tabular_caught_supervised" in output["ablation_arm_order"]
    assert "assisted" not in output["primary_arm_order"]
    assert "assisted" in output["legacy_oracle_benchmarks"]
```

- [x] **Step 2: Run RED**

Run: `rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_ad.py -k schema_v3`

Expected: test fails against the current schema-v2 output.

- [x] **Step 3: Integrate the four arms without renaming legacy strict**

The output must include `arm_metadata`, `arms`, `primary_arm_order`, `ablation_arm_order`, `target_contract`, `split_contract`, `label_provenance`, `identity_substrate`, and `legacy_oracle_benchmarks`. Each regional result records threshold quantile/source/sample count, realized validation/test alert rates, score direction, feature names, caught-positive count, immature-label count, deterministic seed, and retrospective target metrics under a nested `evaluation_only` key.

- [x] **Step 4: Run GREEN and V9dev smoke**

Run: `rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_ad.py`

Expected: all anomaly tests pass, including bounded V9dev smoke.

### Task 6: Dashboard And Documentation

**Files:**
- Modify: `Documents/Data/scripts/build_v9_dashboard.py`
- Modify: `Documents/Data/scripts/v9_dashboard_ui.py`
- Modify: `tests/test_v9_dashboard_builder.py`
- Modify: `Documents/Data/changes_3.md`

- [x] **Step 1: Write failing dashboard disclosure tests**

```python
def test_dashboard_presents_deployable_lineup_without_pu_theorem_or_oracle_ceiling():
    ui = UI_MODULE_PATH.read_text()
    for token in ("caught-supervised", "naive PU", "operating-point policy",
                  "conditional on resolved identity", "observed-catch enrichment"):
        assert token in ui
    assert "ranks in the same order as true carrier probability" not in ui
    assert "oracle ceiling" not in ui
```

- [x] **Step 2: Run RED**

Run: `rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_v9_dashboard_builder.py -k deployable_lineup`

Expected: missing schema-v3 copy/sections cause failure.

- [x] **Step 3: Render A/B/C and the appendix ablation**

The primary table shows the three deployable-semantics arms. A separate appendix shows the 14-feature caught-supervised ablation. The legacy assisted benchmark has its own section, labeled nondeployable and not a ceiling. Metrics distinguish overall carrier recovery, missed-event recovery, lifetime-never-caught person recovery, and observed-catch enrichment. Copy states V9 positive-control status and oracle-identity limitation.

- [x] **Step 4: Document empirical justifications**

Add the verified V9 SCAR check (50.9% org vs 27.4% non-org among carrier events), the fit-boundary maturity check (229 immature rows, 79 eventual catches), and the target distinction (2,691 test missed events, 213 tied to a person caught elsewhere). State that these are retrospective corpus diagnostics, not fit inputs.

- [x] **Step 5: Run dashboard/document regressions**

Run: `rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_v9_dashboard_builder.py`

Expected: all dashboard builder/source contracts pass.

### Task 7: Full Verification And Artifact Regeneration

**Files:**
- Regenerate: `gnn/diagnostics/unsupervised_ad_results_v9.json`
- Regenerate: `gnn/diagnostics/unsupervised_ad_results.json`
- Regenerate: `Documents/Data/v9_dashboard/data_v9.json`
- Regenerate: `Documents/Data/v9_dashboard/index.html`

- [x] **Step 1: Run targeted source suites**

Run: `rtk env PYTHONPATH=. .venv/bin/pytest -q tests/test_unsupervised_features.py tests/test_pu_learning.py tests/test_unsupervised_ad.py tests/test_demo_baseline.py tests/test_v9_dashboard_builder.py`

Expected: zero failures.

- [x] **Step 2: Run the full suite**

Run: `rtk env PYTHONPATH=. .venv/bin/pytest -q`

Expected: zero failures; report any unrelated pre-existing failure separately.

- [x] **Step 3: Generate V9 diagnostics with the corpus pinned explicitly**

Run: `rtk env PYTHONPATH=. CBP_CORPUS_DIR=Documents/Data/synthetic_cbp_graph_corpus_v9 .venv/bin/python -m gnn.unsupervised_ad`

Expected: schema-v3 payload with all four new arms and no oracle access before frozen scoring.

- [x] **Step 4: Rebuild and visually inspect the V9 dashboard**

Run: `rtk env PYTHONPATH=. .venv/bin/python Documents/Data/scripts/build_v9_dashboard.py`

Use the browser skill to verify the A/B/C table, ablation appendix, disclosures, responsive layout, and exact agreement between rendered metrics and embedded JSON.

- [x] **Step 5: Final integrity checks**

Run: `rtk git diff --check`

Run: `rtk git status --short`

Expected: no whitespace errors and only intended PU/anomaly/dashboard changes plus preserved pre-existing user changes.

Observed: all implementation files pass the whitespace scan. The repository-wide
check still reports five pre-existing whitespace findings in the unrelated,
user-edited `Documents/Data/DATA_GUIDE.md`; that file was deliberately left untouched.

Final evidence: targeted suites passed 167 tests; the full repository suite passed
185 tests. The regenerated V9 artifact records the declared midnight fit cutoff for
all 16 completed arm-region runs and full-pool evaluation provenance for 200,000
events. Rendered desktop/mobile dashboard QA matched embedded thresholds and showed
the primary, ablation, and legacy sections with no application runtime errors.
