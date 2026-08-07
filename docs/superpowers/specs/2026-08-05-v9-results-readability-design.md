# V9 Results readability pass

## Goal

Make the V9 Results surface easier to scan at desktop and narrow widths without
changing published metrics, view-model behavior, element IDs, evidence
semantics, or accessibility labels.

## Design direction

Treat the surface as a calm evidence-first research dashboard. Keep the current
Outfit and JetBrains Mono pairing, zinc/charcoal palette, green interaction
accent, and restrained motion. Use `DESIGN_VARIANCE=5`, `MOTION_INTENSITY=2`,
and `VISUAL_DENSITY=5`.

## Approved changes

- Add shrink boundaries to the V9 Results tree so narrow viewports do not inherit
  page-level overflow from wide charts or evidence panels.
- Keep wide charts and tables scrollable only inside their existing bounded
  wrappers.
- Increase explanatory copy and metric label sizes where they currently render
  at arm's-length-unreadable scales.
- Give the top summary, story block, capacity view, and chart sections clearer
  spacing and a stronger reading hierarchy.
- Make mobile controls and capacity metadata stack or wrap explicitly.
- Use a solid, muted crossing-volume context line so the chart is readable while
  preserving redundant dash/shape encodings for model series.
- Relax the recovery explorer summary and toolbar layout on mobile without
  changing case selection, evidence filtering, sidecar loading, or table
  semantics.

## Out of scope

- No changes to scoring, simulation, bootstrap calculations, artifacts, or JSON.
- No changes to V9 Results element IDs, accessibility names, or published values.
- No framework or component-library migration.

## Verification

- Focused source-contract tests for the new responsive rules.
- Existing V9 dashboard and design-system test suites.
- Python compilation and generated JavaScript syntax validation.
- Rebuilt dashboard inspected at desktop and 390px widths.
