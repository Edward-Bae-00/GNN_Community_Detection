# V9 Dashboard Capacity Metrics and Bootstrap Fix

## Goal

Repair the empty V9 Bootstrap Verdicts panel and extend Daily Capacity View with precision, recall, and F1 for every arm/budget, including daily-capacity hybrid-vs-baseline bootstrap verdicts.

## Approach

- Preserve the existing leak-free scoring and daily top-k semantics.
- Extend `evaluate_daily` with `daily_precision@k` and `daily_f1@k` derived from the actual daily inspection budget and daily found count.
- Add a paired daily bootstrap that resamples events and reapplies the per-day quota, then serialize results under explicit daily bootstrap keys.
- Fix the dashboard to read the existing whole-window hybrid bootstrap object and render a second daily bootstrap table.
- Rebuild the generated V9 dashboard data from the canonical diagnostic artifact.

## Files

- `gnn/run_demo.py`: daily metrics and daily bootstrap calculation.
- `tests/test_run_demo_smoke.py`: regression coverage for metric and bootstrap output contracts.
- `Documents/Data/scripts/v9_dashboard_ui.py`: source UI rendering for daily metrics and verdicts.
- `Documents/Data/v9_dashboard/index.html`: generated dashboard bundle.
- `Documents/Data/v9_dashboard/data_v9.json`: regenerated embedded result data.

## Verification

- Run the new targeted tests red before implementation and green after implementation.
- Run the affected V9 tests and the full test suite.
- Rebuild the dashboard and verify the embedded artifact contains hybrid and daily bootstrap fields.
- Review the final diff and leave changes uncommitted unless explicitly requested.

---

# Simulated Catch Candidate Removal and Separate Daily Chart

> **For agentic workers:** Use test-driven development and subagent-driven
> implementation. Preserve unrelated uncommitted work and do not commit.

## Goal

Report operational daily scores after successful model inspections remove that
person from the same arm/budget's future candidate pool, and show Baseline and
Deployable Hybrid results in a separate graph inside Daily Crossing Volume.

## Approved Decisions

- Keep the existing Daily Crossing Volume graph unchanged.
- Add a distinct simulated-catch subsection with its own budget selector, score
  cards, and Baseline/Hybrid graph. Do not overlay or combine it with the existing
  graph.
- Candidate-removal only: a selected hidden-positive person becomes simulated
  caught after that scoring day and is excluded from later days for the same
  arm/budget. Do not inject simulated catches into Hybrid/GNN graph features.
- Before simulation, exclude people only when an official catch label was
  available strictly before that UTC scoring-day start. Current-day and future
  catches remain eligible.
- Use a fixed initial denominator of 2,349 eligible hidden-positive people for
  person recall. Do not shrink the denominator as catches accumulate.
- Limit simulated results to Baseline and Deployable Hybrid.
- Remove the redundant Whole-pool model comparison card and its dead renderer.
- Correct the GNN's official caught timestamp to use
  `label_available_time_utc`, not the detected crossing timestamp, before the
  full V9 rerun.

## Output Contract

Add `simulated_catch_daily` to `demo_comparison_v9.json`:

```json
{
  "policy": {
    "official_catch_time_field": "label_available_time_utc",
    "official_boundary": "strictly_before_utc_day_start",
    "simulated_feedback": "candidate_removal_only"
  },
  "initial_pool": {
    "candidate_events": 38683,
    "hidden_events": 2499,
    "hidden_people": 2349,
    "excluded_events": 1895,
    "excluded_people": 1547,
    "excluded_hidden_events": 192,
    "excluded_hidden_people": 182
  },
  "arms": {
    "baseline": {
      "daily_people_found@25": 0,
      "daily_found_by_day@25": [],
      "daily_budget@25": 0,
      "daily_precision@25": 0.0,
      "daily_recall@25": 0.0,
      "daily_f1@25": 0.0,
      "later_candidate_events_removed@25": 0,
      "later_hidden_events_removed@25": 0
    },
    "hybrid": {
      "daily_people_found@25": 0,
      "daily_found_by_day@25": [],
      "daily_budget@25": 0,
      "daily_precision@25": 0.0,
      "daily_recall@25": 0.0,
      "daily_f1@25": 0.0,
      "later_candidate_events_removed@25": 0,
      "later_hidden_events_removed@25": 0
    }
  }
}
```

The zeros above define field types; the full V9 rerun supplies measured values.
Every `daily_found_by_day@K` series must include all test days and sum to
`daily_people_found@K`.

## Task 1: Correct official catch availability

**Files:**

- Modify `tests/test_df_graphmodel_rgcn.py`.
- Modify `gnn/learned_cell.py`.

- [x] Add a failing test whose detected crossing occurs before
  `label_available_time_utc` and assert `build_caught_times()` returns the label
  availability timestamp.
- [x] Run the targeted test and confirm it fails because the crossing timestamp
  is returned.
- [x] Change `build_caught_times()` to read and minimize
  `label_available_time_utc`, preserving strict `caught_time < T` behavior.
- [x] Run the targeted graph/learned-cell tests green.

## Task 2: Add deterministic simulated-catch daily evaluation

**Files:**

- Modify `tests/test_run_demo_smoke.py`.
- Modify `gnn/run_demo.py`.

- [x] Add failing unit tests for official-catch eligibility at UTC day start,
  high-scoring ineligible candidates not consuming quota, next-day-only
  simulated removal, arm/budget state isolation, fixed person recall denominator,
  all-day output series, and later hidden-event removal counts.
- [x] Run the new tests and confirm failure because the simulator/output contract
  does not exist.
- [x] Extend `load_pool()` to carry `label_available_time_utc` as needed and add a
  focused `evaluate_daily_simulated_catches(pool, scores_by_arm, daily_ks,
  official_caught_times)` helper.
- [x] For each Baseline/Hybrid arm and budget, iterate UTC days in order, rank
  only officially eligible and not-yet-simulated-caught rows, inspect up to K,
  count newly found unique hidden people, and add them to that state after the
  day.
- [x] Emit the approved `simulated_catch_daily` schema from `main()` without
  changing `overall_daily` or adding a bootstrap for the stateful simulation.
- [x] Run simulator unit tests and the V9dev smoke test green.

## Task 3: Remove the whole-pool table and add a separate dashboard graph

**Files:**

- Modify `tests/test_v9_dashboard_builder.py`.
- Modify `Documents/Data/scripts/v9_dashboard_ui.py`.

- [x] Add failing UI contract assertions for a separate
  `v9-simulated-catches` section, independent `v9-simulated-k` selector,
  `v9-simulated-volume` graph, Baseline/Hybrid score cards, and absence of
  `Whole-pool model comparison`, `v9-model-table`, and `drawModelTable()`.
- [x] Run the dashboard test and confirm the new contract fails.
- [x] Remove the whole-pool comparison markup, renderer, invocation,
  `compareKs`, exclusive precision/F1 helpers, and `.group-header` CSS while
  keeping responsive bootstrap table styles.
- [x] Add a visually separate chart block below the existing crossing-volume
  block. Its independent budget selector drives Baseline/Hybrid daily unique
  people lines and score cards for people found, inspections, precision, recall,
  F1, and later hidden events removed.
- [x] Reuse the existing palette and chart primitives, add visible keyboard focus,
  keep concise copy, and provide independent SVG/tooltip accessibility labels.
- [x] Run the dashboard source-contract tests green.

## Task 4: Produce and verify full V9 results

- [x] Run the affected source tests, then the full test suite.
- [x] Run the full V9 demo with
  `CBP_CORPUS_DIR=Documents/Data/synthetic_cbp_graph_corpus_v9`, seeds `(0, 1,
  2)`, 30 epochs, monthly training buckets, and 2,000 bootstrap resamples—the
  settings in the current diagnostic—writing
  `gnn/diagnostics/demo_comparison_v9.json`.
- [x] Verify full-corpus initial-pool counts equal 38,683 candidate events,
  2,499 hidden events, and 2,349 hidden people, and record measured simulated
  scores for every configured daily budget.
- [x] Rebuild `Documents/Data/v9_dashboard/data_v9.json` and `index.html` with
  `rtk .venv/bin/python Documents/Data/scripts/build_v9_dashboard.py`.
- [x] Render the generated dashboard and verify the original and simulated graphs
  are separate, both budget selectors work independently, and no removed table or
  empty layout gap remains.
- [x] Run fresh final tests, static stale-reference searches, JavaScript syntax
  checks, and diff checks before reporting completion.

Final evidence: the combined affected suite passed 29 tests and the full suite
passed 44 tests. The canonical full-corpus run completed with the approved three
seeds, 30 epochs, monthly training buckets, and 2,000 bootstrap resamples. All
eight Baseline/Hybrid budget series contain 273 unique dates and sum to their
reported people-found totals. Desktop and mobile-width generated-page renders
show separate original and simulated charts with independent selectors; stale
whole-pool references are absent and `git diff --check` is clean. Final
integrated review approved the work with no Critical, Important, or Minor
findings.

Measured simulated-catch results:

| Arm | K/day | People found | Inspections | Precision | Recall | F1 | Later hidden events removed |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 5 | 117 | 1,365 | 0.0857 | 0.0498 | 0.0630 | 9 |
| Hybrid | 5 | 350 | 1,365 | 0.2564 | 0.1490 | 0.1885 | 61 |
| Baseline | 10 | 219 | 2,730 | 0.0802 | 0.0932 | 0.0862 | 24 |
| Hybrid | 10 | 550 | 2,730 | 0.2015 | 0.2341 | 0.2166 | 82 |
| Baseline | 25 | 517 | 6,825 | 0.0758 | 0.2201 | 0.1127 | 39 |
| Hybrid | 25 | 917 | 6,825 | 0.1344 | 0.3904 | 0.1999 | 112 |
| Baseline | 50 | 945 | 13,650 | 0.0692 | 0.4023 | 0.1181 | 72 |
| Hybrid | 50 | 1,298 | 13,650 | 0.0951 | 0.5526 | 0.1623 | 128 |

## Errors Encountered

| Error | Attempt | Resolution |
|---|---:|---|
| Placeholder scan returned exit 1 because it found no forbidden placeholders, which stopped a chained read command. | 1 | Treated the no-match result as success and reran the plan read as a separate command. |
| Process-status probes (`pgrep`/`ps`) were denied by the workspace sandbox while the long V9 run was active. | 1 | Used the managed execution session's non-mutating output polling instead; the run remained live. |
| The first sandboxed headless-Chrome render terminated with signal 6. | 1 | Re-ran the same local-file render with approved GUI escalation; desktop and mobile screenshots were produced successfully. |
