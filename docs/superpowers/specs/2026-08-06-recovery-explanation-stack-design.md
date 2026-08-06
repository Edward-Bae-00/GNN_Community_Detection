# Recovery explanation stack design

## Goal

Make the schema-3 GNN explanation area easier to scan by giving each explanation block the full width of the explanation container. The blocks will appear in this order:

1. Highest-attribution evidence
2. Key counterfactual factors
3. LLM explanation

## Design

Keep the existing panel components and content unchanged. Change the shared explanation-row container from a two-column grid to a single-column grid with the existing gap, margins, and child `min-width` rule intact. Reorder the existing render calls so the DOM order matches the requested visual and keyboard-reading order. The structural-only fallback remains a single panel in the same container.

## Constraints and states

- No data, ranking, factor filtering, attribution, or narrative logic changes.
- Existing responsive CSS remains compatible; the one-column desktop rule also satisfies the mobile layout.
- Each panel must occupy the full available explanation width without constraining or sharing a horizontal column with another panel.

## Verification

- Add static UI tests that assert the one-column explanation grid and the attribution → factors → narrative render order.
- Run the focused recovery-explainer and dashboard-builder test files.
- Rebuild the generated V9 dashboard and verify the generated bundle contains the updated CSS and render order.
- Run `git diff --check`.
