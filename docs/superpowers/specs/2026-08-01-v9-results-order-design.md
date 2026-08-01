# V9 Results live-demo order

## Design read

This is a redesign of a research dashboard for analysts and live-demo viewers. The surface should feel calm, evidence-first, and concise. Use the existing vanilla CSS token system. Set `DESIGN_VARIANCE` to 4, `MOTION_INTENSITY` to 2, and `VISUAL_DENSITY` to 6.

## Problem

The current V9 Results tab places model mechanics and the architecture comparison before the reader sees the operational result. The page also mixes event-level rankings, unique-person recovery, confidence checks, and method detail without clear narrative boundaries.

## Approved structure

Keep the existing headline, metrics, charts, recovery explorer, bootstrap tables, model notes, architecture comparison, IDs, interactions, and data contracts. Change only their rendered order and add minimal grouping labels where they improve scanability.

1. Positive-control headline and compact summary stats.
2. Three-lens orientation, kept brief and immediately visible.
3. Operational results: population toggle, depth event recall, daily capacity, simulated first-time recoveries, and daily crossing context.
4. Unique-person recovery evidence.
5. Bootstrap confidence checks.
6. Model lineup and GNN architecture comparison as supporting method detail.
7. Run context metrics.

The primary model order is Baseline, Deployable Hybrid, then GNN wherever the UI renders the lineup. Existing event-versus-person wording remains explicit. The cumulative simulated-catch view remains the default.

## Live-demo copy rules

- Keep section headings to short noun phrases.
- Keep explanatory copy to one sentence per panel where possible.
- Do not add a new explanatory paragraph when an existing label or chart subtitle already carries the meaning.
- Do not change published metric values, evaluation semantics, or leak-safety behavior.

## Verification

- Add a source-order regression test for the approved section sequence and model lineup.
- Run the focused V9 dashboard builder tests and related recovery/UI tests.
- Rebuild the static dashboard, parse the generated JavaScript, and inspect the V9 Results tab at desktop and mobile widths.
- Confirm every preserved mount remains present exactly once.
