# Unsupervised AD V2 Design

**Date:** 2026-07-15

## Objective

Improve the V9 unsupervised anomaly-detection ranking and operational reporting
without changing or relabeling the existing `strict` and `assisted` results. Add
an explicitly separate, label-free-fit arm based on recent relational proxy
features, together with honest local and global explainability.

The implementation must preserve the V8 honest-track versus V9 positive-control
distinction and all strict as-of feature boundaries.

## Chosen Approach

Add a backward-compatible `relational_strict` arm. The existing `modes.strict`
and `modes.assisted` result trees remain present and retain their current
feature sets, fit behavior, and threshold policies. The new arm is additive and
is never presented as the fair non-graph tabular baseline.

This approach was selected over replacing strict mode in place, which would
erase historical comparability, and over building a general experiment-plugin
framework, which would add unnecessary architectural scope.

## Research Contract

`relational_strict` is an unsupervised estimator with label-free fitting and
label-free threshold selection. It may use observable features and historical
outcomes available strictly before the scored event. Ground-truth labels are
used only for retrospective evaluation.

The arm is called relational because party and shared-asset history are
relational proxies. It is not an unsupervised GNN and must not be described as
one. It also remains dependent on the synthetic oracle identity substrate;
that limitation must stay visible in the artifact and dashboard.

## Architecture

### Orchestration

`gnn/unsupervised_ad.py` remains the entry point. It will continue producing the
legacy strict and assisted modes, then evaluate the new arm through the same
regional train/validation/test contract.

The growing responsibilities will be separated into focused modules:

- `gnn/unsupervised_features.py` constructs the relational proxy feature matrix
  and retains display-ready values and feature metadata.
- `gnn/unsupervised_explain.py` computes regional reference values, feature
  rarity, local score sensitivity, and aggregate influence summaries.
- `gnn/unsupervised_ad.py` owns fitting, frozen-threshold evaluation, diagnostic
  assembly, provenance, and artifact writing.

### Backward-compatible result schema

The artifact schema advances to version 3. Existing consumers can continue to
read `modes.strict` and `modes.assisted`. A new top-level `arms` mapping contains
`relational_strict`, its metadata, regional results, and aggregate diagnostics.

The artifact will also record:

- corpus name and repository-relative corpus path;
- a SHA-256 snapshot fingerprint over the repository-relative names and bytes
  of the required corpus input files;
- target name and split date ranges;
- model class, full parameters, random seed, and package versions;
- generation timestamp and Git revision when available;
- identity substrate and label-provenance fields;
- feature names and feature-contract descriptions.

The canonical output will be corpus-qualified, for example
`unsupervised_ad_results_v9.json`. The existing
`unsupervised_ad_results.json` path remains a compatibility output containing
the same self-identifying payload. The V9 dashboard builder will prefer the
corpus-qualified artifact and fall back to the compatibility path.

## Feature Contract

The new arm starts with the current 14 leak-safe tabular features and adds only
fields already available at the event:

- `party_size`;
- `repeat_crossing_count_prior_365d`;
- `same_vehicle_crossing_count_prior_365d`;
- `same_document_crossing_count_prior_365d`.

The original lifetime history fields remain for comparability, while recent
counts provide a drift-resistant view. No current outcome, future outcome,
hidden community label, lifetime catch indicator, or target-derived aggregate
may enter the feature matrix.

Feature extraction must preserve event-row order and explicitly fail when a
required event or column is missing. Display values for categorical fields will
be retained so explanations never expose unexplained integer category codes.

## Threshold Policy

The new arm fits one regional Isolation Forest on all regional training rows.
It chooses the anomaly threshold from the 90th percentile of regional
validation anomaly scores without reading validation labels. The threshold is
then frozen before test evaluation.

This recent-unlabeled calibration policy is distinct from:

- legacy strict: training-score quantile;
- legacy assisted: validation-label F1 optimization.

The artifact must state the score direction as `higher_is_more_anomalous` and
record the source sample count, selected quantile, threshold, and realized alert
rate. Test labels must not be reachable by fitting or threshold-selection
helpers.

## Evaluation Outputs

Each arm and region will report the existing frozen-point metrics plus:

- average precision and ROC-AUC;
- exact confusion counts and lift over prevalence;
- chart-ready precision/recall/F1 versus threshold data;
- precision@k, recall@k, found@k, and cumulative lift at configured capacities;
- score histograms for train, validation, and test;
- monthly score quantiles, alert rate, and retrospective metrics;
- metrics for all contraband and hidden false-negative events separately;
- event-level and unique-person first-hit recovery.

Curves computed with test labels are retrospective evaluation only. They must
never influence the frozen operating point. Single-class slices will emit null
label-based metrics and a structured warning instead of failing or returning a
misleading zero.

Aggregate output will include both micro and macro regional summaries. Bootstrap
confidence intervals will resample by person or day rather than treating repeat
events as independent.

## Explainability

Isolation Forest does not provide calibrated probabilities or additive causal
feature attributions. The dashboard will therefore use two explicitly bounded
diagnostics.

### Feature rarity

For every explained alert, numeric rarity is derived from the feature's
empirical regional training distribution. Categorical rarity uses regional
training frequency. The output includes the decoded observed value, regional
reference value, percentile or frequency, and rarity score.

### Model sensitivity

For each feature, the scored row is copied and that feature alone is replaced
with its regional training reference: the median for numeric features and mode
for categorical features. The Isolation Forest rescoring delta is:

`original anomaly score - reference-replaced anomaly score`.

A positive delta means the observed value made the row more anomalous under
this fitted forest. Deltas are not additive, causal, or SHAP values, and the UI
must say so.

Local explanations are generated only for a bounded number of top alerts per
region. Global influence is the mean absolute sensitivity, plus mean positive
sensitivity, across those alerts. The artifact retains enough information to
audit explanation values without embedding the full event-level score table.

## Dashboard Design

The current strict and assisted cards remain. A distinct relational-strict
section adds:

1. an arm comparison summary with label and feature-contract disclosures;
2. train/validation/test score-distribution overlays with the frozen threshold;
3. precision-recall and F1/alert-volume operating curves;
4. top-k lift and daily-capacity views using regional percentile-normalized
   scores where cross-region ranking is shown;
5. monthly score and alert-rate drift charts;
6. hidden-event and unique-person recovery summaries;
7. a top-alert explanation table and detail panel showing decoded feature
   values, rarity, reference values, and sensitivity deltas.

The charts will reuse the existing V9 dashboard design tokens and lightweight
inline-SVG patterns. Raw Isolation Forest scores will never be labeled as
probabilities. The existing corpus generator's synthetic risk histogram and
lifetime-ground-truth Community Explorer will not be reused as anomaly-model
explanations.

## Error Handling And Limits

- Missing required proxy columns or row-alignment failures are fatal with a
  focused error message.
- Regions lacking sufficient train, validation, or test data are recorded with
  a structured skip reason.
- Missing Git metadata or optional package-version metadata is recorded as null
  and does not abort a run.
- Chart arrays and alert explanations are bounded to keep the standalone
  dashboard artifact manageable.
- V8 and V9 results remain separate and self-identifying.

## Testing And Verification

Implementation will be test-driven and include:

- feature-order and as-of availability tests for every added field;
- proof that relational-strict fit and calibration do not consume labels;
- recent-score quantile and frozen-test-threshold tests;
- metric, top-k, hidden-target, and unique-person arithmetic tests;
- rarity and sensitivity tests on deterministic toy data;
- single-class and insufficient-region behavior;
- schema-v3 backward-compatibility and provenance tests;
- dashboard contract tests for every new panel and disclosure;
- a V9dev end-to-end artifact/dashboard smoke test;
- targeted source tests, the full suite, artifact regeneration checks, and
  `git diff --check` before completion.

## Non-goals

This iteration will not replace the current strict or assisted modes, build a
graph autoencoder, claim causal explanations, solve production entity
resolution, or redesign unrelated dashboard tabs. A fully unsupervised graph
model can be evaluated later as a separate research arm.
