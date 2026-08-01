# Strict Unsupervised Anomaly Detection Implementation Plan

**Goal:** Remove outcome and label-availability leakage from the anomaly-detection features, expose strict and label-assisted modes separately, and present their limitations and operating metrics clearly.

**Architecture:** `demo_baseline.py` will construct historical outcome features using each outcome’s `label_available_time_utc`, not merely the prior event timestamp. `unsupervised_ad.py` will support a strict unsupervised mode (all training rows, training-score threshold only) and an explicitly labeled assisted benchmark (clean-normal training plus validation-label threshold tuning). Diagnostics and the V9 dashboard will report the mode, labels used, validation/test metrics, prevalence, lift, thresholds, and flagged volume.

**Tech Stack:** Python 3.14, pandas, NumPy, scikit-learn Isolation Forest, pytest, generated HTML dashboard.

## Task 1: Lock down strict as-of history behavior

**Files:**
- Modify: `gnn/demo_baseline.py`
- Test: `tests/test_demo_baseline.py`

- [x] Add a failing regression test using a tiny temporary corpus where a prior positive outcome has `label_available_time_utc` after the scored event. Assert that the prior outcome count is zero at the scored event and becomes visible only after availability.
- [x] Run the focused test and confirm it fails because the current history builder uses event time only.
- [x] Add `label_available_time_utc` to the history input and count each outcome only when its label availability is strictly before the current row time.
- [x] Run the focused test and confirm it passes; retain the existing feature-shape/as-of tests.

## Task 2: Separate strict and label-assisted anomaly modes

**Files:**
- Modify: `gnn/unsupervised_ad.py`
- Create: `tests/test_unsupervised_ad.py`

- [x] Add failing unit tests for strict mode: it fits on all training rows, does not require target labels, derives its threshold from training scores, and records `labels_used_for_fit` as false.
- [x] Add failing unit tests for assisted mode: it records that positives were excluded and validation labels tuned the threshold, while test labels are used only for final metrics.
- [x] Run the new tests and confirm they fail against the current single-mode implementation.
- [x] Implement small pure helpers for mode configuration, threshold selection, metric calculation, and result metadata; keep `main()` as the corpus runner.
- [x] Use strict mode as the default. Preserve the current assisted benchmark behind an explicit mode so existing research comparisons remain reproducible but are not described as unsupervised.
- [x] Include per-region event counts, positive prevalence, predicted-positive count/rate, validation metrics where applicable, test metrics, threshold source, feature names, and identity-substrate disclosure in JSON.
- [x] Run the new tests and the focused baseline tests.

## Task 3: Explain the methods and add presentation evidence

**Files:**
- Modify: `Documents/Data/scripts/v9_dashboard_ui.py`
- Modify: `Documents/Data/changes_3.md`
- Modify: `tests/test_v9_dashboard_builder.py`

- [x] Add failing dashboard-contract tests requiring strict/assisted labels, corrected validation wording, label-use disclosure, prevalence/lift, and threshold/flagged-count fields.
- [x] Update the dashboard copy to explain Isolation Forest scoring, regional fitting, strict mode, assisted benchmark mode, and what is or is not deployable.
- [x] Render validation and test metrics separately and add regional prevalence, lift over prevalence, flagged volume/rate, and training exclusion metadata.
- [x] Correct `changes_3.md` so the assisted run is not called a “purer baseline” without qualification and the strict track is documented as the primary result.
- [x] Run dashboard-contract tests.

## Task 4: Regenerate and verify artifacts

**Files:**
- Regenerate: `gnn/diagnostics/unsupervised_ad_results.json`
- Regenerate: `Documents/Data/v9_dashboard/data_v9.json`
- Regenerate: `Documents/Data/v9_dashboard/index.html`

- [x] Run the strict and assisted anomaly runs against the V9 corpus.
- [x] Rebuild the V9 dashboard from the canonical diagnostic artifact.
- [x] Run the affected tests, then the full test suite with `PYTHONPATH=.`.
- [x] Run `git diff --check`, inspect the diff, and report any pre-existing validator failure separately.
