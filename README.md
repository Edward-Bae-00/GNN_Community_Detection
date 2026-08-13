# GNN Community Detection

Research project for graph-based anomaly detection on fully synthetic CBP-style
border-crossing data. The active runtime is the V9 baseline-vs-GNN positive
control in `gnn/`.

## Safety and synthetic-data scope

Every modeled record is synthetic. No row represents a real person, vehicle,
document, officer, case, event, seizure, arrest, address, phone number, email,
license plate, or name. Optional/local aggregate real-world CSVs under
`Documents/Data/RealWorld_Data/` are calibration/context inputs only; that
directory is absent from a fresh clone unless supplied. They are not
operational records or model targets.

V8 is historical honest-track context only. Its corpus is intentionally absent
from this checkout and is not the default or active data path.

## What the V9 positive control demonstrates

V9 is an active, deliberately designed positive control: hidden-carrier risk is
propagable through observable co-travel, shared-plate, residence, and prior
caught-cell-mate structure. The evaluation is strict and leak-free: graph edges
and caught labels used for a row are available before that row's time `T`, and
future outcomes, lifetime catches, hidden organization labels, and outcome
aggregates are excluded from features.

The graph-free baseline remains strong and fair. It uses own history, observed
demographics, and current event context, but no graph or neighbor-label
features, party size, shared vehicle/document co-use, or other relational graph
shadows. The experiment asks whether the as-of caught-propagation GNN can
recover more hidden carriers at operational depth when relational signal is
actually present; it does not claim that V9 supersedes the historical V8
honest-track caveat.

## Current V9 evidence

GraphSAGE remains the active runtime default; the committed 40,578-row RGCN architecture artifact is frozen-artifact verifiable, not exactly retrainable.
The current demo diagnostic is the committed `gnn/diagnostics/demo_comparison_v9.json`; the committed
`gnn/diagnostics/gnn_architecture_comparison_v9.json` is the current
architecture comparison artifact; no RGCN checkpoint or score arrays survive.
The 38,948-row RGCN-era table in `docs/research/changes_3.md` is
clearly labeled historical evidence with its artifact unavailable; its old
significance claims do not transfer to the current release.

## Repository layout

```text
gnn/                                  Active flat implementation and diagnostics
scripts/data/                         Corpus and explanation utilities
scripts/data/validate_corpus.py      Corpus validator
scripts/dashboard/                   Dashboard readers/builders
scripts/dashboard/build_v9_dashboard.py
reproducibility/v9_observability_colab_schema3/
                                      Full V9 corpus, checkpoint, notebook, runner
tests/fixtures/v9dev/                 Tracked small V9 development/test corpus
artifacts/v9/explanations/            Committed schema-3 evidence ZIP and manifest
artifacts/v9/dashboard/index.html     Committed Git LFS V9 dashboard snapshot
docs/data/                            Active data guide
docs/research/                        V9 research log and historical ideas page
docs/superpowers/                     Immutable historical plans/specifications
references/papers/                    Seven tracked research papers
```

The canonical full V9 corpus is
`reproducibility/v9_observability_colab_schema3/corpus/synthetic_cbp_graph_corpus_v9/`.
`gnn/config.py` uses it by default. Set `CBP_CORPUS_DIR` to evaluate another
compatible corpus intentionally; the override does not change the repository's
canonical V9 path.

## Clone and hydrate Git LFS assets

Git LFS is required for the full V9 corpus, the V9dev fixture, the explanation
ZIP and checkpoints, and all seven papers. After cloning, hydrate the tracked
large files:

```bash
git lfs install
git lfs pull
```

## Environment setup

Check that Python 3 is installed, then create the virtual environment with
Python 3:

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

`pyproject.toml` is the authoritative install metadata and requires Python
`>=3.11`. This project is currently verified with Python 3.14; other supported
Python versions must satisfy the metadata requirement. The project installs
PyTorch, PyTorch Geometric, scikit-learn, networkx, pandas, numpy, and pytest.

## Run the V9 demo

```bash
python -m gnn.run_demo
```

Results are written to the generated `gnn/diagnostics/` tree. The published
5/10/25 dashboard rebuild uses the committed frozen diagnostic
`gnn/diagnostics/demo_comparison_v9.json`; the committed architecture
comparison is a separate current RGCN evidence input, while other diagnostics
remain generated and ignored. To use an intentional compatible override:

```bash
CBP_CORPUS_DIR=/path/to/compatible/corpus python -m gnn.run_demo
```

### Reproduce the published release

The bare command above runs the current experimental defaults (30 epochs,
monthly training buckets), which are deliberately *not* the settings behind the
committed artifacts. To replay exactly what produced them — seeds `0/1/2`,
18 epochs, quarterly buckets, GraphSAGE — use:

```bash
python -m gnn.run_demo release
```

Those settings are pinned as `gnn.run_demo.PUBLISHED_RELEASE` and are asserted
against the frozen diagnostic, the architecture comparison, and the published
checkpoint metadata by `tests/test_v9_release_provenance.py`. Changing the
experimental defaults does not change what `release` replays.

## Run tests

```bash
pytest -q
```

The test suite includes path contracts, leak-safe baseline/GNN behavior, and
the tracked V9dev fixture.

## Validate corpora

```bash
python -m scripts.data.validate_corpus tests/fixtures/v9dev
```

The same validator can inspect the canonical full V9 directory when its Git
LFS payloads are hydrated.

## Run schema-3 observability in Colab

> **Hardware disclaimer — RAM is the binding constraint.**
>
> Regenerating the explanation evidence is the only part of this repository
> with a real hardware floor. Everything else — the test suite, the dashboard
> rebuild, verifying the committed archive — runs comfortably on an ordinary
> laptop.
>
> Measured figures from the giant-benchmark run behind the committed artifact
> (checkpoint `17d5ee9f`, 120,000 nodes / 2,639,472 typed edges, largest
> Hybrid-only community 6,952 nodes):
>
> - **Peak resident memory ~5.2 GiB** for the producer, and only because
>   per-scoring-day snapshots are released as it goes. Without that release the
>   run OOMs (exit 137).
> - A **16 GiB machine is not enough**: a 16 GiB Mac reached roughly 7 GiB
>   resident plus 2.8 GiB of swap before publication and had to be abandoned.
>   Treat **32 GiB as the practical minimum**, which is why the instructions
>   below specify a high-RAM Colab runtime.
> - The narrative stage additionally loads `gemma4:12b` through Ollama, about
>   **8.1 GiB on top** of the producer's own footprint.
> - Disk: the handoff package is ~1.4 GB (almost all corpus), and the run needs
>   local scratch for the recovery bundle on top of that.
>
> **On GPUs.** The scoring path genuinely does not need one — there is no CUDA
> path in the package and it scores from a verified checkpoint rather than
> training. The *narrative* stage is a different story: `gemma4:12b` on CPU was
> measured at 4.8 tokens/s, taking 179.6s on a real fact packet against a
> hardcoded 180s timeout (`explanation_narrative.py`). That is a 0.4s margin,
> and a single timeout degrades the case to a narrative fallback, which the
> post-run coverage gate then rejects for the whole export. Use a GPU runtime
> for the narrative stage unless you intend to pass `--allow-shortfall`.

The handoff package is
`reproducibility/v9_observability_colab_schema3/`. Upload that whole directory
to `MyDrive/v9_observability_colab_schema3`, open a high-RAM Colab runtime, and
open `v9_schema3_observability.ipynb`. The notebook's Run all path performs the
same mount/copy sequence below. Start from a fresh runtime; if the local
destination already exists, Run all automatically replaces only that VM-local
`/content/v9_observability_colab_schema3` copy before copying. The Drive source
is not deleted, but unsaved edits in the local copy are discarded; a fresh
runtime is simplest.

Colab Python cell:

```python
from google.colab import drive
from pathlib import Path
import shutil

drive.mount("/content/drive")
source = Path("/content/drive/MyDrive/v9_observability_colab_schema3")
destination = Path("/content/v9_observability_colab_schema3")
if destination.is_symlink() or destination.is_file():
    destination.unlink()
elif destination.exists():
    shutil.rmtree(destination)
shutil.copytree(source, destination)
```

Colab shell/magic cell:

```bash
%cd /content/v9_observability_colab_schema3
!python -m pip install -r requirements.txt
!python run_schema3_observability.py \
  --work-root /content/v9_schema3_run \
  --export-dir /content/drive/MyDrive/v9_schema3_results
```

The notebook installs the requirements, prepares local runtime storage, verifies
the checkpoint closure and the corpus content fingerprints, starts Ollama,
validates the exact `gemma4:12b` tag, and runs
`run_schema3_observability.py`. Keep the corpus, checkpoint, SQLite/catalog
scratch, and generated output on local storage during the run; Drive FUSE is
too slow for hot writes. The Colab-local `/content` sequence above is also the
manual runner path.

The runner replays the corpus packaged with the handoff in place, wherever that
handoff is unpacked — checkpoint compatibility is decided by the per-file
content fingerprints recorded in the checkpoint, not by the absolute path the
release was produced from. Pass `--corpus-dir` to point at a different copy;
any CSV mutation still fails closed.

The committed archive can be verified and used without rerunning Colab. A
Colab rerun is only needed to reproduce or replace the evidence artifact.

## Verify and extract explanation evidence

```bash
python -m scripts.data.v9_assets verify-explanations
python -m scripts.data.v9_assets extract-explanations \
  artifacts/v9/explanations/extracted
```

The extracted tree is generated and ignored; keep the committed ZIP and
`MANIFEST.sha256` as the reproducible evidence inputs.

## Build and serve the dashboard

```bash
python -m scripts.dashboard.build_v9_dashboard
python -m http.server 8000 --directory artifacts/v9/dashboard
```

The builder reads the canonical V9 contracts and refreshes the committed,
Git LFS-backed snapshot at `artifacts/v9/dashboard/index.html`. Other files
under `artifacts/v9/dashboard/`, including `data_v9.json` and recovery
sidecars, remain generated and ignored. Serve the directory over HTTP so
sidecar-backed pages can fetch their data.

On a fresh clone the builder reproduces the committed `index.html` byte for
byte from the committed frozen diagnostics alone. It warns that no
unsupervised AD artifact was found and that the anomaly-ranking tab will be
sparse — that is the expected state, because the unsupervised artifacts are
generated and ignored, and the committed snapshot was built without them.
Running `python -m gnn.unsupervised_ad` first populates that tab and therefore
produces a *different* `index.html`; rebuild from a clean diagnostics tree when
you intend to reproduce the committed bytes.

## Research papers

The seven Git LFS-backed papers are:

- `references/papers/ACGAN-GNNExplainer.pdf`
- `references/papers/GAT.pdf`
- `references/papers/GIN.pdf`
- `references/papers/GraphEXPLAINER.pdf`
- `references/papers/GraphSAGE.pdf`
- `references/papers/KPI-AA.pdf`
- `references/papers/RGCN.pdf`

## Generated and local-only files

Generated diagnostics under `gnn/diagnostics/`, except for the committed
frozen `demo_comparison_v9.json` and current
`gnn_architecture_comparison_v9.json`, extracted explanation trees under
`artifacts/v9/explanations/extracted/`, dashboard data and recovery sidecars
under `artifacts/v9/dashboard/`, Python caches, pytest caches, and local
scratch/log files are ignored or local-only. The generated dashboard HTML
snapshot at `artifacts/v9/dashboard/index.html` is also committed through Git
LFS and refreshed by the builder. The V9 explanation ZIP, its manifest, the
frozen demo diagnostic, schema-3 checkpoint, corpora, V9dev fixture, and papers
are the committed/LFS inputs; do not replace them with untracked generated
copies.

## Known schema-3 result limitation

The committed schema-3 ZIP failed its coverage gate. It contains 19 exact
Hybrid explanations out of 20 selected cases and records one failed case, so
it is a degraded 19-of-20 archive and is not fully passing or coverage-gated.
Treat it as committed evidence with an explicit limitation, never as a fully
passing run.
