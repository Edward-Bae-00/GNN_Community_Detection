# Overview Dataset and Model Snapshot Design

## Goal

Make the V9 Overview useful as a first-stop orientation page by exposing the
synthetic corpus shape and the two deployable comparison arms alongside the
existing research evidence.

## Design

The Overview renderer will consume the existing embedded `D.meta`,
`D.overview`, and `D.v9Demo` payloads through a small validated JavaScript view
model. It will render a new Dataset and models block after the introductory
brief and before operational evidence.

The block will show four headline totals: nodes, edges, events, and
communities. It will also show compact node-type and edge-type breakdowns,
using the existing typed counts and stable descending count order. Model cards
will describe the leak-safe HGB tabular baseline and the deployable Baseline +
GraphSAGE rank-fusion Hybrid. The card metadata will include the baseline
feature count, GNN seed count, training bucket, epochs, and deployable fusion
weight when those values validate. The synthetic-only oracle Hybrid will be
mentioned only as a clearly labeled non-deployable ceiling if the payload
contains it.

All numeric values will be accepted only when they are safe non-negative
integers; text will use safe fallbacks; malformed optional sections will render
an explicit unavailable state rather than throwing or inventing values. The
existing evidence sections, result semantics, and as-of caveats remain
unchanged.

## Testing

Add Node-backed runtime tests for a complete snapshot and for malformed/missing
metadata. Add renderer assertions that the generated Overview contains the
dataset snapshot heading, totals, and model labels. Retain the existing syntax
and dashboard-builder regression tests.

## Out of scope

- Changing model training, scores, or evaluation artifacts.
- Recomputing counts from CSVs in the browser.
- Moving detailed graph exploration out of the existing Explorer tab.
- Treating total heterogeneous corpus edges as person-graph edges.
