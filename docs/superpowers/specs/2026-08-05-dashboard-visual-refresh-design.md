# Dashboard visual refresh design

**Status:** Approved design direction; implementation pending.

## Goal

Improve the dashboard's overall visual hierarchy and readability for both laptop use and projected or screenshot-based presentation while preserving its current dark, technical identity and all existing data behavior.

## Design direction

The dashboard remains a dark research instrument rather than moving to a light theme. The palette will shift from near-black with low-contrast gray text toward a readable deep-slate system:

- blue-black slate canvas with visibly separated charcoal/slate surfaces;
- near-white primary text and lighter gray-blue secondary text;
- one teal accent for selected state and positive emphasis;
- pale slate, teal, and sky-blue series colors for Baseline, Hybrid, and GNN;
- amber for warnings and coral for negative states.

The change should feel like a refinement of the current dashboard, not a new product surface. Outfit and JetBrains Mono remain the type system. Existing navigation, chart interactions, tab routing, data semantics, accessibility labels, and generated-dashboard architecture remain intact.

## Visual hierarchy

The page will establish three reading levels:

1. **Primary finding:** headline result, key comparison, and selected operational depth receive the strongest type and surface contrast.
2. **Decision support:** metric groups, charts, legends, and comparison tables use clear grouping and consistent spacing.
3. **Method detail:** caveats, provenance, axis notes, and explanatory copy remain visible but use a quieter, still-readable treatment.

Cards will be used only where a surface communicates grouping or hierarchy. Repeated heavy borders will be reduced in favor of surface steps, quiet dividers, and restrained accent rails. The existing V9 story and summary blocks remain the narrative entry point, but their title, supporting copy, and metric relationships should scan more clearly.

## Typography and contrast

- Essential body and chart-supporting text must not depend on the current low-contrast tertiary gray.
- Essential labels, axis text, table headers, and control text should render at a readable 12px or larger equivalent; body copy should remain at 13–14px or larger.
- Primary findings use a larger, tabular-number treatment without oversized display typography.
- Uppercase micro-labels remain limited to metadata and compact category labels rather than entire sections.
- Focus-visible states remain explicit and consistent across tabs, controls, legends, and interactive chart regions.

## Charts and data encoding

The existing data series semantics remain unchanged. Baseline, Hybrid, and GNN will use a higher-contrast palette and retain redundant encoding through dash and marker differences so the comparison survives projection and color-vision differences. Grid lines and axes become visible enough to orient the reader without competing with the data. Legends and segmented controls receive larger hit areas and clearer selected states.

## Layout and responsive behavior

- Preserve the existing full-width dashboard shell and tab structure.
- Keep a comfortable reading measure for narrative copy and allow charts to use available width.
- Maintain two-column comparison layouts where they remain readable; collapse them cleanly at the existing responsive breakpoints.
- Prevent chart labels, tables, and metric values from becoming clipped or dependent on browser zoom.
- Keep screenshot-friendly spacing and print styling aligned with the on-screen hierarchy.

## Implementation seam

- `Documents/Data/scripts/v9_design_system.py` owns global palette, type, spacing, shape, contrast, interaction, and print overrides because it is appended after the generated template stylesheet.
- `Documents/Data/scripts/v9_dashboard_ui.py` owns V9 results-specific card, story, chart, table, segmented-control, and anomaly-ranking presentation rules.
- `Documents/Data/scripts/build_v9_dashboard.py` remains the composition path; no data or renderer contract changes are planned unless a visual fix requires a narrowly scoped markup class.
- Existing tests for the design system, dashboard builder, V9 dashboard behavior, and accessibility-sensitive UI remain the regression gate.

## Non-goals

- No change to model results, metric calculations, corpus content, or as-of semantics.
- No theme switch, framework migration, icon-library change, or data-model change.
- No removal of existing tabs, charts, tables, evidence panels, or explanatory content.
- No attempt to redesign unrelated research artifacts outside the generated dashboard surface.

## Acceptance criteria

1. The generated dashboard preserves the current dark technical character while using a deep-slate palette with visibly stronger text and surface contrast.
2. The V9 results page has an obvious scan order: headline finding, comparison evidence, supporting charts/tables, then methodology.
3. Essential labels, chart axes, legends, controls, and table headers remain readable at laptop width and in a normal-size screenshot without zooming.
4. Baseline, Hybrid, and GNN remain distinguishable by both color and non-color line/marker encoding.
5. Existing focused tests pass, including design-system and dashboard-builder tests.
6. Generated HTML is rebuilt and inspected at desktop and narrow widths, with no new console errors or horizontal overflow in the primary readout views.
