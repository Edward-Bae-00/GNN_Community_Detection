# Repository Reorganization Design

**Date:** 2026-08-06  
**Branch:** `feature/repository-reorganization`  
**Worktree:** `/Users/edward/.config/superpowers/worktrees/GNN_Community_Detection/reorganize-repo`

## Goal

Reorganize the repository around the active GNN research stack, make the README
and supporting documentation match the resulting filesystem, preserve every
current feature, remove only proven noise or dead material, remove V8 data from
the organized branch, preserve all research papers, and upload all canonical V9
data and schema-3 explanation evidence through Git LFS.

## Safety Baseline

- The original `main` worktree remains untouched as the fallback.
- The isolated worktree was created from commit `b16034e`.
- Sixteen tracked files from the user's uncommitted working state were seeded
  into the isolated worktree through a temporary Git object. Every transferred
  file matched the source by SHA-256.
- Nineteen untracked source, design, and plan documents were copied explicitly.
- The main worktree's Git status was identical before and after seeding.
- The seeded suite currently reports 1,219 passed, 2 skipped, and 20 failed.
  Every failure is caused by an ignored V9/V9dev corpus file or generated V9
  dashboard file that is absent from a clean worktree. There is no seeded code
  regression in that result.

The current user-owned source and documentation changes are part of the
baseline. They will be committed separately from the structural reorganization
so their provenance remains visible.

## Chosen Approach

Use a conservative, path-aware reorganization:

- Keep `gnn/` flat so existing `from gnn...` imports and module entry points
  remain stable.
- Keep `tests/` at the repository root.
- Move peripheral dashboard/data utilities as coherent units and update every
  path reference in code, tests, and documentation.
- Preserve the schema-3 Colab handoff as an atomic, intentionally divergent
  source snapshot. Its internal layout will not be flattened or deduplicated.
- Add conventional dependency metadata and reproducible commands without
  changing model behavior.
- Use Git LFS for canonical corpora, binary evidence, and papers.

A full `src/gnn` conversion was rejected because it would create broad import
churn without improving the active model boundary. A documentation-only cleanup
was rejected because it would leave code mixed into `Documents/Data/` and would
not make clean clones runnable.

## Target Structure

```text
.
├── gnn/                              # active, flat Python package
│   └── diagnostics/                  # generated and ignored; path stays stable
├── tests/
│   └── fixtures/v9dev/               # LFS-backed small reproducible corpus
├── scripts/
│   ├── dashboard/                    # builders, UI modules, and font assets
│   └── data/                         # corpus validation utilities
├── docs/
│   ├── data/                         # current data guide
│   └── research/                     # V9 findings and research history
├── reproducibility/
│   └── v9_observability_colab_schema3/
│       ├── checkpoint/
│       ├── corpus/synthetic_cbp_graph_corpus_v9/
│       ├── gnn/                      # preserved schema-3 source snapshot
│       ├── tests/
│       ├── README.md
│       ├── requirements.txt
│       ├── run_schema3_observability.py
│       └── v9_schema3_observability.ipynb
├── artifacts/
│   └── v9/explanations/
│       ├── v9_schema3_results.zip    # complete sidecar tree, tracked by LFS
│       └── MANIFEST.sha256
├── references/
│   └── papers/                       # all seven PDFs, byte-preserved
├── tasks/                            # active and historical task records
├── pyproject.toml
├── .gitattributes                    # Git LFS rules
└── README.md
```

## Code Boundaries

### Active GNN package

`gnn/` remains the authoritative active implementation. The baseline, graph
construction, as-of caught propagation, checkpoint, observability, recovery,
explanation, unsupervised, and architecture-bakeoff modules stay import
compatible. `gnn/diagnostics/` remains the generated result location because
checkpoint and dashboard consumers rely on it.

The tightly coupled observability stack remains together:

```text
run_demo
├── observability_artifact
├── sage_explainer
├── explanation_narrative
├── recovery_observability
├── recovery_bundle
└── recovery_evidence_store
```

No module is split or removed merely because it appears unused. Removal requires
an import/reference scan, a clear replacement or obsolete status, and passing
tests after deletion.

### Schema-3 reproducibility package

The bundled `gnn/` snapshot differs intentionally from the active root package.
It will remain self-contained and will continue to be imported by the bundled
runner. Parent-directory moves are allowed only after notebook, runner, and test
paths are updated and verified. Internal checkpoint and corpus paths remain
relative to the package root.

### Dashboard and data utilities

Dashboard builders, UI helpers, sidecar readers, design-system code, and font
assets move together to `scripts/dashboard/`. Bare sibling imports and asset
lookups will be updated as a unit. The corpus validator moves to
`scripts/data/`. Legacy V8-capable utility behavior is retained when it remains
a valid externally supplied corpus path; the V8 dataset and V8 default are not.

## GNN Documentation Standard

The documentation pass focuses on `gnn/` and the schema-3 package's bundled
`gnn/` snapshot.

- Every GNN module receives an accurate module docstring where one is absent.
- Public classes, functions, CLI entry points, and complex internal helpers
  receive docstrings covering purpose, inputs, outputs, and important failure
  conditions.
- Inline comments document strict as-of semantics, leakage boundaries, graph
  relation construction, checkpoint identity, schema invariants, attribution
  completeness, atomic publication, and non-obvious performance constraints.
- Existing comments are corrected when they no longer describe current code.
- Tests receive comments only where they explain a research invariant, fixture
  contract, or regression that is not evident from the assertion.
- Non-GNN code is left stylistically unchanged except where moved paths or new
  interfaces require documentation.

Comment-only changes will be isolated where practical and checked by comparing
Python ASTs with docstrings removed. Functional behavior is proved by tests,
not inferred from the presence of comments.

## V9 Data and Explanation Evidence

### Canonical full V9 corpus

The full corpus inside
`reproducibility/v9_observability_colab_schema3/corpus/` is the canonical
uploaded V9 snapshot because the verified checkpoint fingerprints those exact
files and the Colab runner consumes them directly.

Before removing the duplicate root V9 corpus from the organized layout, every
same-name file will be compared by SHA-256. Identical files are stored once. If
any file differs, work stops for classification; the differing file is
preserved under a documented V9 variant path and is not silently discarded.

### V9dev fixture

The 28 MB V9dev corpus moves to `tests/fixtures/v9dev/` and is tracked through
Git LFS. Tests and smoke runners use that location explicitly, making a clean
clone testable after `git lfs pull`.

`Documents/Data/RealWorld_Data/` and `Documents/Data/CAVIAR/` are aggregate
calibration/reference inputs rather than V9 synthetic corpus outputs. They
remain local and ignored and are not part of the requested V9 upload. The full
generated V9 corpus already contains the calibrated synthetic result needed to
run the model and reproduce the schema-3 checkpoint workflow.

### Explanation evidence

`v9_schema3_results.zip` is the canonical transport for the explanation
evidence tree. It contains 64,964 archive entries and approximately 4.82 GB of
uncompressed pointer-manifest and recovery-sidecar evidence. The ZIP is tracked
through Git LFS, accompanied by its SHA-256
`54064788c0cd92893296d1db926aaa902604e30db16fdc3151545413a30008fd`.

The artifact is preserved honestly: its coverage gate is false, it contains 19
exact Hybrid explanations rather than 20, and one case failed. Documentation
will not describe it as a fully passing run. It remains valuable reproducible
evidence and can be regenerated by the schema-3 runner.

A checked command will verify the ZIP hash before extraction and restore every
sidecar. The dashboard builder will consume the extracted artifact or an
explicit artifact path. The generated dashboard is rebuilt from canonical
inputs rather than committing a second 4.7 GB extracted copy.

### LFS rules and upload verification

`.gitattributes` will track the following through Git LFS:

- corpus tables and large generated corpus payloads under the schema-3 package;
- V9dev fixture payloads;
- `artifacts/v9/explanations/v9_schema3_results.zip`;
- checkpoint tensors and score archives;
- research PDFs.

Small source, Markdown, schema metadata, and checksum manifests remain normal
Git files. Verification will reject regular Git blobs larger than GitHub's
ordinary limit and confirm every intended file appears in `git lfs ls-files`.

The feature branch, including LFS objects, will be pushed to `origin`. `main`
will not be pushed, merged, reset, or cleaned as part of this task.

## V8 Policy

- No V8 corpus is copied into or uploaded from the organized branch.
- The default corpus changes from V8 to the canonical full V9 snapshot.
- `CBP_CORPUS_DIR` remains supported for explicit compatible corpora.
- Historical V8 findings remain in research documentation so V9 claims are not
  misrepresented, but documentation no longer presents V8 data as required or
  present.
- The ignored 1.4 GB V8 directory in the original main worktree remains there
  while that worktree serves as the fallback. It can be removed separately only
  after the user accepts the branch.

## Paper Preservation

All seven PDFs are preserved byte-for-byte under `references/papers/`:

- `ACGAN-GNNExplainer.pdf`
- `GAT.pdf`
- `GIN.pdf`
- `GraphEXPLAINER.pdf`
- `GraphSAGE.pdf`
- `KPI-AA.pdf`
- `RGCN.pdf`

Source and destination hashes will be compared before the old local path is
considered redundant. The original main-worktree copies remain untouched.

## Cleanup Rules

The organized branch excludes:

- the V8 corpus;
- `.pytest_cache/`, `__pycache__/`, `.pyc`, and `.DS_Store` files;
- `Documents/Data/.v9_dashboard.stage-*` temporary trees;
- duplicate extracted dashboard/recovery trees represented by the verified ZIP;
- local environments and agent/tool state;
- diagnostics and build products that can be regenerated from canonical inputs.

Active plans, specifications, source files, schema metadata, checkpoints,
papers, and canonical evidence are not cleanup candidates. Uncertain material is
preserved and documented rather than deleted.

## Documentation

The root README becomes the authoritative onboarding document and covers:

- project purpose and fully synthetic-data warning;
- V9-only active runtime and the historical V8 distinction;
- exact repository structure and module responsibilities;
- environment setup and dependency installation;
- Git LFS installation and `git lfs pull`;
- demo, test, observability, explanation extraction, validation, and dashboard
  commands;
- schema-3 limitations and degraded-result disclosure;
- paper locations;
- generated-versus-versioned artifact policy.

`AGENTS.md`, `CLAUDE.md`, data documentation, and path-bearing task/spec files
will be updated where their instructions would otherwise contradict the new
filesystem. Historical documents retain historical claims but receive a clear
archival label when their commands or paths are no longer current.

## Failure Handling

- Setup fails with a clear message when Git LFS pointers have not been hydrated.
- Corpus loading reports the missing path and the `git lfs pull` or
  `CBP_CORPUS_DIR` remedy.
- Explanation extraction verifies SHA-256 before writing output and refuses a
  mismatched archive.
- Dashboard builds use temporary staging and atomic publication; interrupted
  staging directories remain ignored and are never uploaded.
- Path migration keeps compatibility wrappers only where an external entry
  point would otherwise disappear. Wrappers emit a documented migration path.
- Any root-versus-bundle corpus hash mismatch pauses deduplication and preserves
  both files pending classification.

## Verification

The completed branch must pass all applicable gates:

1. Compare seeded source hashes and confirm the main worktree status remains
   unchanged.
2. Validate Git LFS attributes, pointer hydration, tracked-object inventory, and
   absence of oversized regular Git blobs.
3. Validate the full V9 and V9dev corpora with the corpus validator and snapshot
   tests.
4. Run the complete root pytest suite.
5. Run the schema-3 package's seven tests from its own package root.
6. Run import and CLI smoke checks for every moved entry point.
7. Validate the notebook as JSON and run the schema-3 runner's `--help` and
   preflight-safe checks that do not require a full Ollama execution.
8. Verify the explanation ZIP hash, listing, safe extraction behavior, and
   dashboard ingestion.
9. Build the V9 dashboard into a temporary directory and run its focused tests.
10. Scan source and documentation for stale `Documents/Data/scripts`, V8
    defaults, removed paths, and contradictory layout descriptions.
11. Compare GNN ASTs across comment-only edits and review functional diffs
    separately.
12. Obtain an independent code-review pass for correctness, leakage risk,
    security, path safety, and no-feature-loss coverage.
13. Push the feature branch and LFS objects, then verify the remote branch and
    LFS references are reachable.

Full live schema-3 generation with `gemma4:12b` is a high-RAM, long-running
Colab workflow and is not required for local completion. Its unit tests,
checkpoint/corpus identities, notebook wiring, and preflight contracts are
required.

## Completion Criteria

The task is complete only when:

- the organized filesystem matches the README;
- current GNN behavior and all entry points are preserved;
- GNN code has accurate, focused documentation;
- all seven papers are preserved;
- no V8 data exists in the organized branch;
- all canonical full V9, V9dev, checkpoint, and explanation evidence is tracked
  by Git/LFS and uploaded on the feature branch;
- generated noise and verified duplicates are absent;
- tests and verification gates pass or any unavoidable external limitation is
  reported with exact evidence;
- the original main worktree remains a usable fallback.
