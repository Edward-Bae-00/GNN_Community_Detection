# V9 Metric Story Design

## Goal

Make the V9 results tab explain why the Hybrid’s displayed values differ across
Found@K, Model comparison, and Daily Capacity View without changing model
calculations or result artifacts.

## Narrative

The tab will present the result through three lenses:

1. **Global ranking:** one top-K ranking over the entire test pool. Model
   comparison uses the whole pool of 40,578 events and 2,691 hidden carriers.
2. **Findable depth:** Found@K is a global ranking viewed against the selected
   population, defaulting to the 708-event observable slice where relational
   signal is available.
3. **Daily operations:** each test day receives its own inspection quota. With
   273 test days, 25 inspections/day represents 6,825 total inspections.

The explainer will state that the Hybrid’s graph advantage appears at
operational depth, while the baseline can remain competitive in the first few
global slots. It will also explain that whole-pool F1 is low because precision
and recall use different denominators and the pool includes dark and lone
carriers.

## UI changes

- Add a compact, always-visible three-lens explainer between the model notes and
  metric panels.
- Add concrete result examples to make the explanation auditable: whole-pool
  K=2,000 (Hybrid 310 vs Baseline 186) and daily 25/day (Hybrid 953 vs
  Baseline 536).
- Rename headings so scope is explicit: “Whole-pool model comparison,”
  “Global Found@K by selected population,” and “Daily capacity view.”
- Keep the existing population toggle and metric calculations unchanged.
- Preserve existing styles and responsive behavior; use the tab’s existing
  neutral palette with one restrained accent for each lens.

## Verification

- Add focused source assertions for the narrative text, concrete values, and
  explicit scope labels.
- Run the focused dashboard-builder tests and the relevant full test subset.
- Inspect the generated tab source for the new strings and confirm no metric
  fields or result JSON generation changed.
