# V9 schema-3 observability Colab handoff

This is the clean schema-3 handoff for the V9 observability run. It is
separate from the legacy `v9_observability_colab` package, which generates the
older schema-2 artifact for all 268 Hybrid-only cases.

The production policy is:

- schema `3.0`;
- 20 selected Hybrid detail cases;
- 10 Baseline structural controls;
- full lightweight score/rank cohort summaries;
- strict local `gemma4:12b` narrative validation for selected Hybrid details.

## Colab setup

1. Upload this whole folder to Google Drive (~1.4 GB, almost all corpus).
2. Open a **high-RAM** runtime. A GPU is *not* required and only costs compute
   units: there is no CUDA path in this package (the sole device reference is
   `device="cpu"` in `gnn/graphmodel_rgcn.py`) and this path scores from a
   verified checkpoint rather than training. RAM is the real constraint.
3. Open `v9_schema3_observability.ipynb` and run all cells.

The notebook copies the package from Drive to local `/content` storage, installs
the Ollama installer’s `zstd` prerequisite when needed, starts Ollama, obtains
and hard-verifies `gemma4:12b`, and only then runs the producer. Keep the
corpus, checkpoint, SQLite/catalog scratch, and generated output on local
storage during the run; Drive FUSE is too slow for hot writes.
The notebook runs a bounded Ollama CLI smoke probe (180 seconds) while the
12B model cold-loads on CPU; it limits visible stdout/stderr and does not claim
full selector-contract validation.

To run it by hand instead:

```bash
cd /content/v9_observability_colab_schema3
python -m pip install -r requirements.txt
python run_schema3_observability.py \
  --work-root /content/v9_schema3_run \
  --export-dir /content/drive/MyDrive/v9_schema3_results
```

The runner recreates the checkpoint's recorded absolute corpus path inside
the Colab VM, validates the checkpoint/corpus identity through the normal
producer, and writes atomic stage progress to `progress.json`.

## The exported artifact is a pointer manifest, not the evidence

`hybrid_recovery_explanations_v9.json` is a **compact pointer manifest**. Its
`detail_index`, `community_index`, `catalog_index`, and `community_sidecar_index`
hold only `{path, sha256, bytes}` references — the producer explicitly rejects a
manifest that inlines communities or explanations. The real evidence lives in a
sibling `recovery/` tree, and the dashboard builder resolves sidecars relative to
the JSON's own directory.

So the export is a **pair**, and both halves must travel together:

```
<export-dir>/
  hybrid_recovery_explanations_v9.json
  recovery/
    current.json
    bundles/<bundle_id>/...
```

`--export-dir` publishes both. It stages the `recovery/` tree inside the export
directory, verifies every staged file against its source (and every
manifest-recorded `sha256`/`bytes`), swaps it into place, and copies the JSON
**last** — so a partial export can never leave a JSON pointing at missing or
corrupt sidecars. Copy the whole export directory back to the repository; the
JSON on its own cannot build the dashboard.

## The run is gated on real coverage

A missing or broken Ollama does **not** make the producer fail. The narrative
preflight failure is recorded, selected Hybrid cases use deterministic narrative
fallbacks, and the run keeps a structurally valid local artifact with a failed
coverage gate (it is not necessarily empty).

The runner therefore gates on the artifact's own `coverage` block before
exporting, requiring: no narrative preflight failure, no failed cases, no
deterministic-template fallbacks, at least one explained Hybrid case, and — when
the candidate pool is large enough — the full Hybrid and Baseline budgets.

**The Hybrid budget must be filled by `hybrid_explained` alone.** Any
`hybrid_structural_fallback` fails the gate: a candidate too large for
GNNExplainer is downgraded to community-only evidence, which is different
evidence rather than a substitute for an explanation. When the budget is short,
the failure names `hybrid_eligible` if the explainer ceiling — not case failures
— is what kept it from being filled, since only that is fixed by raising the
ceiling.

A candidate pool smaller than the requested limit is still treated as a
legitimate shortfall, not a failure.

On a gate failure the runner prints which conditions failed, exits non-zero, and
skips the export. The local artifact is kept for debugging and `result.json`
records the reason. `--allow-shortfall` downgrades the gate to a warning and
exports anyway; use it only when you have decided a partial artifact is
acceptable.

## How many Hybrid cases get a real explanation

GNNExplainer runs on the target's exact, unpruned two-hop pre-pool input, so a
candidate whose neighbourhood exceeds the eligibility ceiling is downgraded to
community-only evidence rather than explained over a truncated computation
graph. The ceiling is `MAX_EXPLAINER_INPUT_NODES` / `MAX_EXPLAINER_INPUT_EDGES`
in `gnn/sage_explainer.py`.

`MAX_LOCAL_EXPLANATION_NODES` / `MAX_LOCAL_EXPLANATION_EDGES` bound the display
projection, and they are **defined from** the ceiling rather than set
independently. That link is load-bearing, not stylistic. `materialize_local`
chooses the displayed nodes by target/pooled/caught/salience priority *before*
any attribution exists, and `compose_case_explanation` then drops mask records
for whatever the projection left out. If the display bound were lower than the
ceiling, `top_local_nodes` and `top_edges` — and the narrative sentences built
from them — would silently mean "top among displayed records" rather than top in
the explanation. Raise both together; a test parses this module and fails if the
two are ever unlinked.

Equal ceilings are necessary but not sufficient. Masks are keyed by source row,
and `MAX_LOCAL_SOURCE_ROWS_PER_EDGE` bounds how many source rows a displayed
edge publishes, so attribution is aggregated from **complete** per-edge
membership while only the published provenance stays bounded. This is a routine
corpus shape rather than a corner case: 5,878 co-travel pair groups and 24,466
shared-residence pair groups exceed 16 source rows, reaching 64 and 1,144.

Every explained case therefore publishes an `attribution_completeness` block —
omitted nodes, omitted mask records, omitted mask mass, and a separate
`node_feature_stats` count, since that dump is bounded by record count and does
not affect the ranked claims. Coverage publishes `hybrid_attribution_complete`,
and the gate requires it to equal `hybrid_explained`: a partial attribution is
still valid evidence, but it cannot be certified as an exact explanation.

Raising the ceiling is how you increase `hybrid_explained` at the expense of
`hybrid_structural_fallback`. Choose the value from measurements rather than
guesswork: `--preflight-only` runs the pipeline as far as explainer preflight,
writes `preflight_distribution.json` to the work root, and prints how many
candidates each candidate ceiling would admit. It does not depend on the current
ceiling, so one measurement run informs any choice.

Both the ceiling and the display bound are part of the run fingerprint, so
changing either mints a new staging directory instead of resuming into a bundle
staged under the old policy.

## `gemma4:12b` must be the exact tag

The producer's preflight matches the tag exactly against the first column of
`ollama list`, and every Hybrid case's evidence is rejected unless it carries a
validated narrative from that exact model. The notebook replicates that parsing
so it fails immediately rather than hours in.

If `gemma4:12b` is a private/local tag that is not on the public registry, the
pull step will fail with instructions to import it into the VM's Ollama store
first. Do not substitute another model — the artifact will not validate.

## Downstream dashboard

The schema-3 dashboard reader is under `scripts/dashboard/` in the organized
repository. Verify the committed explanation archive before building:

```bash
python -m scripts.data.v9_assets verify-explanations
python -m scripts.dashboard.build_v9_dashboard
```

The committed archive is degraded 19-of-20: it contains 19 exact Hybrid
explanations and one failed case. It failed the coverage gate and is not fully
passing or coverage-gated. The archive can still be used as committed evidence;
a new Colab run is only needed to produce a replacement artifact.

## Provenance and limitations

`gnn/` was synced from the
`feature/v9-balanced-explainability` worktree on 2026-08-02, including its
resume-path as-of re-validation and cached-community chunk identity checks.
The package source is self-contained. The current dashboard-side schema-3
reader is the organized repository implementation under `scripts/dashboard/`,
as documented in the downstream dashboard section above.

This is a clean schema-3 runner, not a four-worker schema-2 pack merger. The
producer builds one detached validated artifact and writes it at the end;
`progress.json` reports stages but does not resume individual cases. If the Colab
runtime expires before completion, rerun from the last successful full artifact
(there is no partial artifact to publish).

Keep the old Colab package unchanged until this run has passed the live
acceptance checks.
