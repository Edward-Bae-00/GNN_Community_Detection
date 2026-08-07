# Design System: V9 Explanation Evidence Explorer

## 1. Visual Theme & Atmosphere

An evidence-reader interface for synthetic CBP-style graph research: calm,
precise, and editorially structured rather than a cockpit of competing metrics.
The selected case reads like a short investigation, then opens into measured
technical evidence. Density is 5/10, layout variance is 6/10, and motion is
2/10: deliberate spacing and hierarchy do the work, with only restrained state
transitions.

## 2. Color Palette & Roles

- **Charcoal Canvas** (`#0A0A0C`) — page background; never pure black.
- **Surface Zinc** (`#131316`) — primary panels and case surfaces.
- **Elevated Zinc** (`#1A1A1F`) — ranking cells, evidence panels, and controls.
- **Ink White** (`#E8E8EC`) — headings, primary values, and identifiers.
- **Muted Steel** (`#A1A1AB`) — explanatory copy and secondary metadata.
- **Quiet Label** (`#84848F`) — non-primary labels and captions; not for essential body copy.
- **Whisper Border** (`#2A2A31`) — structural dividers and panel edges.
- **Signal Green** (`#34D399`) — the single interaction accent for selected state, primary evidence emphasis, and focus.
- **Semantic Evidence Gold** (`#FBBF24`) — functional evidence/warning encoding only, never a decorative accent.
- **Semantic Context Blue** (`#60A5FA`) — functional caught-before-snapshot node
  fill and dashed Residence relationship stroke; shape/pattern plus labels
  disambiguate the uses.

Do not introduce a second decorative accent, neon gradient, purple glow, or
warm/cool neutral drift. Functional graph colors may remain where they carry a
specific evidence meaning and must be paired with labels or shape.

## 3. Typography Rules

- **Display and prose:** Outfit, weights 500-700; controlled scale, tight tracking, and relaxed line height.
- **Numbers and technical metadata:** JetBrains Mono, weights 400-600; use for ranks, scores, IDs, timestamps, tables, and graph labels.
- **Body measure:** keep explanatory copy near 65ch maximum and use at least 13px for readable narrative text.
- **Numeric presentation:** visible numbers use a shared formatter with `maximumFractionDigits: 3`; trailing zeroes are omitted. Artifact precision is never mutated.
- **Banned:** Inter and generic serif fonts. This is a dashboard, so serif typography is not used.

## 4. Component Stylings

- **Case header:** left-aligned copy block, compact scope badge, then a clear Baseline / Seed-0 GNN / Seed-0 Hybrid ranking strip.
- **Ranking cells:** shallow elevation, structural top borders, monospaced values, and a single green primary state for Hybrid. Explain rank movement in words, not abbreviations alone.
- **Narrative panel:** generous padding, readable 13px prose, source references kept adjacent to their claims.
- **Explanation graph:** default to Evidence first at First hop. Attributed
  relationships use a gold model-evidence-weight underlay beneath a narrower
  relationship stroke: solid green for co-travel, dashed blue for residence,
  and dotted violet for shared plate. The strongest three attributed edges may
  carry direct labels. Group View, Stage, Relationship, Labels, and Navigation
  controls explicitly; do not make one color carry both relationship and
  evidence semantics.
- **Cards and panels:** use borders and small elevation only where they separate evidence layers. High-density tables use dividers and whitespace rather than ornamental cards.
- **Buttons and controls:** minimum 44px touch target, clear focus ring, tactile pressed state, no outer glow or custom cursor.
- **Tables:** monospaced numeric columns, readable row padding, horizontal overflow only inside a bounded table wrapper.
- **Loading and empty states:** preserve the existing text/status states and use layout-matched skeletons if loading visuals are added later; no circular spinner.

## 5. Layout Principles

Use a grid-first hierarchy with clear spatial zones and no overlap.

The reading order is: selected case context, rank comparison, interactive
evidence graph, grounded narrative with measured factors, then the technical
disclosures and complete tables.

The wide layout uses a case rail beside the evidence detail. The evidence detail
uses a readable narrative/evidence column beside the graph. Below 900px, columns
collapse to one column. Below 700px, the ranking strip also becomes one column,
controls remain reachable, and no horizontal page scroll is allowed.

## 6. Motion & Interaction

Motion is restrained and functional. Use transform/opacity transitions only,
respect `prefers-reduced-motion`, and keep graph pan/zoom interactions direct.
No perpetual loops, bouncing chevrons, scroll prompts, or decorative animation.

## 7. Accessibility & Evidence Semantics

Keep explicit labels for Baseline, Seed-0 GNN, Seed-0 Hybrid, rank movement,
the strict as-of boundary, graph stages, evidence weights, and complete-table
fallback. Color never carries meaning alone. Do not relabel the Hybrid
percentile-fusion score as a probability, and do not imply that attribution is
causal.

## 8. Anti-Patterns (Banned)

- No emojis, Inter, generic serif fonts, pure black, neon/outer glow shadows, or oversaturated accents.
- No overlapping content, centered high-variance hero composition, equal three-card feature rows, or flexbox percentage hacks.
- No fake precision beyond three visible decimal places and no fake round numbers.
- No AI copywriting cliches such as “Elevate”, “Seamless”, “Unleash”, or “Next-Gen”.
- No filler UI text such as “Scroll to explore”, “Swipe down”, arrows, or bouncing chevrons.
- No placeholder identities such as “John Doe”, “Acme”, or “Nexus”.
- No broken remote image links, custom mouse cursors, or decorative gradients that compete with evidence.
