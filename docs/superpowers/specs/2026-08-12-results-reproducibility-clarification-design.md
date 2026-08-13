# Current RGCN results publication and historical preservation design

## Goal

Publish the newer 40,578-row RGCN architecture results as the repository's
current RGCN measurements, backed by their exact JSON artifact. Preserve the
older 38,948-row RGCN-era numbers verbatim in a clearly historical appendix.
GraphSAGE remains the active runtime default; this change updates result
provenance and publication surfaces, not model behavior.

## Evidence boundary

The current RGCN source is the existing
`gnn/diagnostics/gnn_architecture_comparison_v9.json` from the user-owned main
worktree. It is 549,896 bytes with SHA-256
`d4b5d349532ca949f11a3c1df59f27b4323189e06ae6099d7310dac3fc7ad35a`.
The artifact records schema 1, the logical V9 corpus, a 40,578-event test pool,
2,691 hidden events, seeds 0/1/2, 18 epochs, quarterly training buckets, oracle
identity, and all five GNN architecture arms. Implementation will copy those
exact bytes into the feature worktree and explicitly unignore that one file.

The RGCN artifact contains evaluated metrics but no RGCN checkpoint, score
arrays, corpus content fingerprint, bootstrap comparison, or complete
environment lock. Its current numbers are therefore **frozen-artifact
verifiable**, not exactly retrainable. The producer can run a new RGCN fit, but
that would be a new experiment rather than a byte-for-byte replay guarantee.
The artifact's old absolute `corpus_identity` path is retained as provenance;
documentation uses its logical corpus name and measured denominators rather
than presenting that machine-specific path as portable.

The current graph-free baseline lives in the separate frozen
`demo_comparison_v9.json`. The baseline and architecture artifacts agree on the
logical V9 corpus, pool size, hidden count, seeds, epochs, and quarterly bucket,
but they were serialized by separate commands. Any Baseline-to-RGCN table must
identify both sources and describe the comparison as cross-artifact; it must
not imply that the architecture bakeoff executed or serialized a Baseline arm.

## Published current RGCN measurements

The current whole-pool RGCN ensemble values are:

| K | Found | Recall | Baseline reference recall |
| ---: | ---: | ---: | ---: |
| 500 | 144 | 0.0535 | 0.0149 |
| 2,000 | 538 | 0.1999 | 0.0710 |
| 5,000 | 1,030 | 0.3828 | 0.1557 |

The baseline reference column comes from `demo_comparison_v9.json`, not the
architecture artifact. No historical `p=0` or paired-bootstrap claim transfers
to this newer comparison.

On the artifact's 708-person observable slice, RGCN found 111, 407, and 700 at
K=500, 2,000, and 5,000, with recall 0.1568, 0.5749, and 0.9887. At 25
inspections per day, it records 1,129 found, precision 0.1654, recall 0.4195,
and F1 0.2373.

## Documentation and dashboard changes

- Restructure `docs/research/changes_3.md` so the newer RGCN table is the
  current RGCN result and the old 38,948-row table is retained verbatim under a
  conspicuous historical/unrecoverable heading. Remove current-tense headline
  or significance language that depends only on the old table.
- Update the existing architecture-bakeoff section: the artifact is now
  committed rather than ignored, its current RGCN values are authoritative for
  RGCN claims, and its exact-retraining limitation is explicit.
- Update `README.md` and `docs/data/DATA_GUIDE.md` to distinguish the active
  GraphSAGE default, current artifact-backed RGCN measurements, and preserved
  historical RGCN-era observations. The old table remains available but is not
  described as current or reproducible.
- Because the dashboard builder already validates and conditionally embeds
  this diagnostics path, rebuild the committed dashboard snapshot after
  versioning the artifact. The organized builder currently rejects the exact
  file's legacy absolute `corpus_identity`; retain the artifact bytes and add a
  narrow compatibility path that accepts that legacy identity only when the
  complete file matches the pinned release SHA-256. Canonical-path artifacts
  continue through the normal validator, while modified or unrelated legacy-
  path artifacts fail closed. The resulting V9 Results architecture section
  must contain the same RGCN metrics. Generated sidecars remain ignored.
- Preserve the existing schema-3 limitation: the explanation ZIP is a degraded
  19-of-20 archive, not a fully passing coverage run.

## Machine-checkable contracts

- Add a release-provenance test for the architecture artifact's exact SHA-256,
  byte size, schema/configuration, architecture ordering, whole-pool RGCN
  metrics, observable-slice metrics, and daily-25 metrics.
- Assert cross-artifact compatibility only on the fields both releases can
  substantiate: logical corpus name, pool size, hidden count, seeds, epochs,
  and training bucket. Assert independently that the baseline reference values
  come from `demo_comparison_v9.json`.
- Add documentation assertions that the current and historical labels exist,
  the old numbers remain present, and old bootstrap significance is not
  assigned to the current RGCN artifact.
- Strengthen the baseline contract with a test-owned exact 14-feature
  allowlist. The expectation must not be derived from implementation
  `FEATURE_NAMES`, so graph or neighbor labels, party size, shared
  vehicle/document co-use, future or lifetime outcomes, hidden organization
  fields, and outcome aggregates cannot enter silently.
- Add an active-versus-bundled executable-AST parity contract. Core
  scoring/as-of modules must remain equivalent, while the already audited
  schema-3 explanation and path/provenance differences are explicitly
  allowlisted. Any new divergence fails closed until reviewed.
- Exercise the dashboard builder against the real committed architecture
  artifact and assert the generated embedded payload equals it exactly.
- Test the legacy-identity exception in both directions: the exact pinned file
  is accepted, while any content mutation invalidates the hash exception and
  restores the canonical corpus-identity requirement.

## Non-goals

- Do not delete or alter any number in the old historical table.
- Do not claim the newer RGCN artifact is exactly retrainable or checkpoint
  replayable.
- Do not transfer the old run's paired-bootstrap p-values to the newer run.
- Do not change the active GraphSAGE default, model/evaluation logic, corpora,
  checkpoints, the frozen GraphSAGE diagnostic, explanation ZIP, or strict
  as-of semantics.
- Do not normalize the frozen archive's known `pair:pair:` evidence IDs.
- Do not commit, merge, push, or modify the user's dirty main worktree.

## Verification

Use test-first changes for the new contracts: add focused tests and confirm the
expected failures while the RGCN artifact is absent from the feature worktree;
then copy the exact artifact, update ignore rules, documentation, and the
generated dashboard snapshot, and rerun the tests to green. Run the affected
baseline, architecture-bakeoff, dashboard, checkpoint, archive, documentation,
layout, and cross-tree parity tests. Revalidate both V9 corpora, run Git LFS and
artifact hash checks, compare a temporary dashboard rebuild byte-for-byte with
the updated committed snapshot, and finally run the complete root test suite
after removing the temporary audit plan from the active layout.

Success means a clean-clone reviewer can verify the newer RGCN measurements
from the committed JSON, see them in synchronized documentation and dashboard
output, understand that exact RGCN retraining remains unavailable, and still
access every older number as explicitly historical evidence.
