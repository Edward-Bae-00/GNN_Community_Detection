# Guided Overview and Confidence-Interval Explanation

## Intent

Make the V9 dashboard easier to read on first visit without changing the
underlying artifacts, metrics, model behavior, or evaluation semantics.

The approved direction is a guided evidence brief for research and engineering
readers: lead with the result, explain why it occurs, then state the limits.

## Scope

### Overview

Update the Overview route in `Documents/Data/scripts/v9_summary_page.py` so its
reading order is explicit:

1. **Result:** state the operational conclusion in plain language and label the
   headline as unique-person recovery where applicable.
2. **Why:** describe the relational mechanism and the role of strict as-of
   evidence.
3. **Limits:** make the V9 positive-control status, connected-population
   dependence, V8 distinction, and oracle/synthetic boundaries easy to find.

Keep the dataset/model inventory as supporting evidence after the opening
brief. Preserve the existing unavailable/malformed-data states and responsive
layout. Keep metric definitions available through the existing semantics
disclosure.

### Confidence intervals

Rewrite the Daily bootstrap verdicts explanation in
`Documents/Data/scripts/v9_dashboard_ui.py` around four reader questions:

- **What is re-sampled?** Individual test event rows are re-drawn with
  replacement, then assigned and ranked within each day under the same daily
  inspection quota.
- **What is measured?** Each re-draw produces a Hybrid-minus-baseline gap in
  hidden-positive event hits.
- **What does 95% CI mean here?** It is the middle 95% of those re-drawn gaps,
  describing resampling variability. It is not a probability that the true gap
  lies inside the interval.
- **How should it be read?** An interval entirely above zero supports a Hybrid
  win at that depth; an interval crossing zero is inconclusive/wash; an interval
  entirely below zero supports a baseline win.

End with the operational caveat that these bootstrap rows count event hits,
not unique people; the separate recovery explorer answers the unique-person
question.

## Interaction and visual treatment

Use the selected guided-brief direction: a clear lead sentence, short
explanation blocks, and restrained accent treatment. Do not add a new chart,
new control, or new artifact field. Keep the current chart/table order and
accessibility labels. The new copy should remain readable when the layout
collapses to one column on mobile.

## Data and correctness constraints

- Do not introduce future outcomes, lifetime catches, hidden organization
  labels, or outcome aggregates as model or display inputs.
- Do not change the meaning of `mean diff`, `95% CI`, `p(Hybrid<=base)`, or the
  verdict logic.
- Preserve the distinction between V9 positive-control results and the V8
  honest track.
- Preserve the distinction between event hits and unique-person recovery.
- Preserve fail-closed behavior when summary metadata or evidence is missing.

## Verification

Update only source-contract tests needed to assert the improved copy and
ordering, then run:

- `tests/test_v9_dashboard_builder.py`
- `tests/test_v9_summary_page.py`

Also run the generated-dashboard smoke coverage if the focused tests identify a
builder integration regression. Record the user-facing copy change in
`Documents/Data/changes_3.md`.

## Non-goals

- No change to the V9 artifacts or statistical computation.
- No redesign of the Explorer, anomaly-detection, or recovery-explainer tabs.
- No replacement of the existing dashboard design system.
