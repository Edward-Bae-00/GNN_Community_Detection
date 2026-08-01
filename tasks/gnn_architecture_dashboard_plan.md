# Standalone GNN Architecture Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a strictly additive dashboard section backed by one standalone run of all five registered GNN architectures, with three seeds per architecture and no Baseline or Hybrid execution.

**Architecture:** Create a dedicated `gnn.gnn_architecture_bakeoff` module that prepares the V9 corpus and graph once, loops over `GNN_ARMS`, and atomically emits an architecture-only JSON artifact. Load that artifact independently in the V9 builder and mount an isolated UI component inside the existing V9 Results tab without removing, renaming, reordering, or changing any existing dashboard behavior.

**Tech Stack:** Python 3.14, PyTorch/PyTorch Geometric, pandas/numpy, pytest, static HTML/CSS/JavaScript, Node-based JavaScript tests, Merget history.

---

## File Map

- Create `gnn/gnn_architecture_bakeoff.py`: GNN-only preparation, training,
  aggregation, validation, atomic artifact publication, and CLI.
- Create `tests/test_gnn_architecture_bakeoff.py`: runner, schema, CLI, failure,
  and no-Baseline/no-Hybrid contracts.
- Create `Documents/Data/scripts/v9_gnn_architecture_ui.py`: isolated CSS,
  view-model helper, accessible renderer, and unavailable state.
- Modify `Documents/Data/scripts/build_v9_dashboard.py`: optional artifact
  validation/loading and additive CSS/JavaScript injection.
- Modify `Documents/Data/scripts/v9_dashboard_ui.py`: add one mount element and
  one renderer invocation while preserving all existing source in order.
- Modify `tests/test_v9_dashboard_builder.py`: builder/UI contracts and
  preservation tests.
- Modify `Documents/Data/changes_3.md`: record the command and measured results
  only after the full V9 artifact exists.
- Generate `gnn/diagnostics/gnn_architecture_comparison_v9.json`: full V9
  comparison artifact.

### Task 1: Define the architecture-only artifact and aggregation

**Files:**

- Create: `tests/test_gnn_architecture_bakeoff.py`
- Create: `gnn/gnn_architecture_bakeoff.py`

- [ ] **Step 1: Write failing aggregation and schema tests**

Add fixtures with five small score bundles and tests that require:

```python
EXPECTED_ARCHITECTURES = ("sage", "rgcn", "gat", "gin", "kpiaa")


def test_build_artifact_contains_only_registered_gnn_architectures():
    payload = bakeoff.build_artifact(
        corpus_name="synthetic_cbp_graph_corpus_v9dev",
        corpus_identity="/tmp/v9dev",
        seeds=(0, 1, 2),
        epochs=1,
        train_bucket="M",
        ks=(2,),
        daily_ks=(1,),
        pool=pool_fixture(),
        strata=strata_fixture(),
        architecture_scores=score_fixture(),
        architecture_specs=spec_fixture(),
        feature_schema=("caught_count",),
        relation_schema={"COTRAVEL": 0},
    )

    assert payload["schema_version"] == 1
    assert payload["artifact_kind"] == "gnn_architecture_comparison"
    assert tuple(payload["architecture_order"]) == EXPECTED_ARCHITECTURES
    assert tuple(payload["architectures"]) == EXPECTED_ARCHITECTURES
    forbidden = {"baseline", "hybrid", "hybrid_oracle", "fusion_weights"}
    assert forbidden.isdisjoint(payload)
    assert all(forbidden.isdisjoint(row) for row in payload["architectures"].values())


def test_build_artifact_reports_ensemble_and_per_seed_depth_metrics():
    payload = build_fixture_artifact()
    sage = payload["architectures"]["sage"]

    assert sage["ensemble"]["overall"]["found@2"] == 2
    assert sage["ensemble"]["overall"]["recall@2"] == 1.0
    assert set(sage["per_seed"]) == {"0", "1", "2"}
    assert sage["per_seed"]["0"]["overall"]["found@2"] == 1
    assert sage["ensemble"]["daily"]["daily_budget@1"] > 0
    assert sage["ensemble"]["stratified"]["observable"]["hidden"] >= 0
```

Also test `validate_artifact()` rejects missing/extra architectures, duplicate
seeds, non-finite metrics, inconsistent hidden denominators, and any forbidden
Baseline/Hybrid field.

- [ ] **Step 2: Run the focused tests and confirm the missing-module failure**

Run:

```bash
rtk .venv/bin/python -m pytest -q tests/test_gnn_architecture_bakeoff.py
```

Expected: collection fails because `gnn.gnn_architecture_bakeoff` does not
exist.

- [ ] **Step 3: Implement deterministic artifact construction**

In `gnn/gnn_architecture_bakeoff.py`, define:

```python
SCHEMA_VERSION = 1
ARTIFACT_KIND = "gnn_architecture_comparison"
DEFAULT_OUTPUT = FC.RESULTS / "gnn_architecture_comparison_v9.json"
DEFAULT_SEEDS = (0, 1, 2)
DEFAULT_EPOCHS = 18
DEFAULT_TRAIN_BUCKET = "Q"


def _score_metrics(pool, scores, strata, ks, daily_ks):
    hidden = pool["hidden"].to_numpy(dtype=bool)
    ranked = add_tiebreak(scores, pool)
    return {
        "overall": _add_f1_at_k(
            evaluate(pool.assign(_score=ranked), "_score", ks), ks
        ),
        "stratified": stratum_metrics(ranked, pool, hidden, strata, ks),
        "daily": evaluate_daily(pool, ranked, daily_ks),
    }


def build_artifact(
    *,
    corpus_name,
    corpus_identity,
    seeds,
    epochs,
    train_bucket,
    ks,
    daily_ks,
    pool,
    strata,
    architecture_scores,
    architecture_specs,
    feature_schema,
    relation_schema,
):
    architecture_order = tuple(architecture_specs)
    if architecture_order != tuple(GNN_ARMS):
        raise ValueError("architecture registry must match GNN_ARMS order")
    rows = {}
    for arm_id in architecture_order:
        by_seed = architecture_scores[arm_id]
        ensemble = np.mean(
            np.column_stack([by_seed[seed] for seed in seeds]), axis=1
        )
        rows[arm_id] = {
            "label": architecture_specs[arm_id]["label"],
            "looks_for": architecture_specs[arm_id]["looks_for"],
            "num_relations": int(architecture_specs[arm_id]["num_rel"]),
            "ensemble": _score_metrics(pool, ensemble, strata, ks, daily_ks),
            "per_seed": {
                str(seed): _score_metrics(
                    pool, by_seed[seed], strata, ks, ()
                )
                for seed in seeds
            },
        }
        for seed_payload in rows[arm_id]["per_seed"].values():
            seed_payload.pop("daily")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "corpus": corpus_name,
        "corpus_identity": corpus_identity,
        "substrate": SUBSTRATE,
        "seeds": list(seeds),
        "epochs": int(epochs),
        "train_bucket": train_bucket,
        "ks": list(ks),
        "daily_ks": list(daily_ks),
        "pool_size": int(len(pool)),
        "hidden_total": int(pool["hidden"].sum()),
        "stratum_hidden": {
            name: int(
                ((strata == name).to_numpy() & pool["hidden"].to_numpy(dtype=bool)).sum()
            )
            for name in STRATA
        },
        "feature_schema": list(feature_schema),
        "relation_schema": {
            key: int(value) for key, value in sorted(relation_schema.items())
        },
        "architecture_order": list(architecture_order),
        "architectures": rows,
    }
    validate_artifact(payload)
    return payload
```

Keep validation pure and recursive. Reject booleans as numeric metrics, and use
`math.isfinite()` for every metric leaf.

- [ ] **Step 4: Run aggregation tests**

Run:

```bash
rtk .venv/bin/python -m pytest -q tests/test_gnn_architecture_bakeoff.py
```

Expected: aggregation/schema tests pass; runner tests added in Task 2 still
fail if already collected.

### Task 2: Implement the one-pass GNN-only runner and CLI

**Files:**

- Modify: `tests/test_gnn_architecture_bakeoff.py`
- Modify: `gnn/gnn_architecture_bakeoff.py`

- [ ] **Step 1: Write failing runner-isolation tests**

Monkeypatch corpus/graph helpers and make forbidden calls fatal:

```python
def test_run_bakeoff_prepares_once_and_never_runs_baseline_or_hybrid(
    tmp_path, monkeypatch
):
    calls = {"graph": 0, "gnn": []}
    monkeypatch.setattr(
        run_demo,
        "build_baseline_features",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("baseline fitting is forbidden")
        ),
    )
    monkeypatch.setattr(
        run_demo,
        "_pick_fusion_weight",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("hybrid fusion is forbidden")
        ),
    )
    install_tiny_corpus_fakes(monkeypatch, calls)

    payload = bakeoff.run_bakeoff(
        corpus_dir=tmp_path,
        output_path=tmp_path / "bakeoff.json",
        seeds=(0, 1, 2),
        epochs=1,
        train_bucket="M",
        ks=(2,),
        daily_ks=(1,),
    )

    assert calls["graph"] == 1
    assert calls["gnn"] == list(bakeoff.GNN_ARMS)
    assert set(payload["architectures"]) == set(bakeoff.GNN_ARMS)
```

Add a failure test that creates a prior valid output, makes the third
architecture raise, and asserts the prior bytes remain unchanged and no
`.tmp` file remains.

- [ ] **Step 2: Run the focused runner test and confirm failure**

Run:

```bash
rtk .venv/bin/python -m pytest -q \
  tests/test_gnn_architecture_bakeoff.py::test_run_bakeoff_prepares_once_and_never_runs_baseline_or_hybrid
```

Expected: FAIL because `run_bakeoff()` is missing.

- [ ] **Step 3: Implement shared preparation and architecture loop**

Implement:

```python
def run_bakeoff(
    *,
    corpus_dir=None,
    output_path=DEFAULT_OUTPUT,
    seeds=DEFAULT_SEEDS,
    epochs=DEFAULT_EPOCHS,
    train_bucket=DEFAULT_TRAIN_BUCKET,
    ks=KS,
    daily_ks=DAILY_KS,
):
    cd = Path(corpus_dir or FC.CORPUS_DIR)
    train_cutoff, _ = _split_label_cutoffs(cd)
    obs2id = _build_oracle(cd)
    pool = load_pool(cd)
    strata = stratum_for_pool(pool, cd)
    train_pool, train_labels = _train_pool_and_labels(cd, train_cutoff)
    edges_typed, node_ids, node_feat = build_person_graph_typed(
        cd, substrate=SUBSTRATE, include_plate=True
    )
    caught_time = build_caught_times(cd, obs2id)
    node_index = {person_id: index for index, person_id in enumerate(node_ids)}
    validate_pool_identities(
        train_pool, obs2id, node_index, pool_name="training pool"
    )
    validate_pool_identities(
        pool, obs2id, node_index, pool_name="test pool"
    )

    architecture_scores = {}
    for arm_id, spec in GNN_ARMS.items():
        try:
            bundle = _gnn_scores(
                edges_typed,
                node_ids,
                node_feat,
                caught_time,
                train_pool,
                train_labels,
                [pool],
                obs2id,
                seeds=seeds,
                epochs=epochs,
                train_bucket=train_bucket,
                train_cutoff=train_cutoff,
                model_cls=spec["cls"],
                num_rel=spec["num_rel"],
            )
        except Exception as error:
            raise RuntimeError(
                f"GNN architecture {arm_id!r} failed"
            ) from error
        architecture_scores[arm_id] = {
            seed: np.array(bundle.scores_by_seed[seed][0], copy=True)
            for seed in bundle.seed_order
        }
        del bundle

    payload = build_artifact(
        corpus_name=cd.name,
        corpus_identity=str(cd.resolve()),
        seeds=tuple(seeds),
        epochs=epochs,
        train_bucket=train_bucket,
        ks=tuple(ks),
        daily_ks=tuple(daily_ks),
        pool=pool,
        strata=strata,
        architecture_scores=architecture_scores,
        architecture_specs=GNN_ARMS,
        feature_schema=caught_feature_names(NUM_REL_PLATE),
        relation_schema=REL_PLATE,
    )
    _atomic_json_write(Path(output_path), payload)
    return payload
```

Do not call `run_demo.main()`, `fit_predict()`, `build_baseline_features()`,
`_pick_fusion_weight()`, `_rank_fuse()`, checkpoint writing, bootstrap helpers,
or observability code.

- [ ] **Step 4: Add and test the CLI**

Use `argparse` with these exact arguments:

```python
def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run every registered GNN architecture without Baseline or Hybrid."
    )
    parser.add_argument("--corpus", type=Path, default=FC.CORPUS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--train-bucket", default=DEFAULT_TRAIN_BUCKET)
    parser.add_argument("--ks", type=int, nargs="+", default=list(KS))
    parser.add_argument("--daily-ks", type=int, nargs="+", default=list(DAILY_KS))
    return parser.parse_args(argv)
```

`main(argv=None)` passes parsed values to `run_bakeoff()` and prints the output
path plus architecture/seed configuration. Test `--help`, defaults, explicit
values, positive integer validation, and duplicate-seed rejection.

- [ ] **Step 5: Run all runner tests**

Run:

```bash
rtk .venv/bin/python -m pytest -q \
  tests/test_gnn_architecture_bakeoff.py \
  tests/test_run_demo_smoke.py
```

Expected: PASS, with the existing canonical demo tests unchanged.

### Task 3: Load the optional artifact without disturbing existing dashboard data

**Files:**

- Modify: `tests/test_v9_dashboard_builder.py`
- Modify: `Documents/Data/scripts/build_v9_dashboard.py`

- [ ] **Step 1: Write failing loader tests**

Add a minimal valid five-architecture fixture and assert:

```python
def test_load_v9_data_adds_valid_gnn_architecture_artifact(
    tmp_path, monkeypatch
):
    artifact = gnn_architecture_fixture()
    artifact_path = tmp_path / "gnn_architecture_comparison_v9.json"
    artifact_path.write_text(json.dumps(artifact))
    install_minimal_dashboard_data(tmp_path, monkeypatch)
    monkeypatch.setattr(
        BUILDER, "V9_GNN_ARCHITECTURE_COMPARISON", str(artifact_path)
    )

    data = BUILDER._load_v9_data()

    assert data["v9GNNArchitectureComparison"] == artifact


def test_load_v9_data_rejects_wrong_corpus_without_changing_existing_keys(
    tmp_path, monkeypatch
):
    artifact = gnn_architecture_fixture(corpus="wrong")
    artifact_path = tmp_path / "wrong.json"
    artifact_path.write_text(json.dumps(artifact))
    original = install_minimal_dashboard_data(tmp_path, monkeypatch)
    monkeypatch.setattr(
        BUILDER, "V9_GNN_ARCHITECTURE_COMPARISON", str(artifact_path)
    )

    data = BUILDER._load_v9_data()

    assert "v9GNNArchitectureComparison" not in data
    assert_existing_dashboard_payload_preserved(original, data)
```

Cover missing, malformed, incomplete, extra-architecture, non-finite, and
wrong-corpus artifacts.

- [ ] **Step 2: Run loader tests and confirm failure**

Run:

```bash
rtk .venv/bin/python -m pytest -q tests/test_v9_dashboard_builder.py \
  -k "gnn_architecture_artifact"
```

Expected: FAIL because the builder constant and loader do not exist.

- [ ] **Step 3: Implement the optional loader**

Add `import math` with the standard-library imports, then add:

```python
V9_GNN_ARCHITECTURE_COMPARISON = os.path.join(
    DIAGNOSTICS_DIR, "gnn_architecture_comparison_v9.json"
)
GNN_ARCHITECTURE_IDS = ("sage", "rgcn", "gat", "gin", "kpiaa")


def _finite_metric_tree(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _finite_metric_tree(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return all(_finite_metric_tree(child) for child in value)
    return isinstance(value, str) or value is None


def _is_compatible_v9_gnn_architecture(payload):
    if not isinstance(payload, dict):
        return False
    if payload.get("schema_version") != 1:
        return False
    if payload.get("artifact_kind") != "gnn_architecture_comparison":
        return False
    if payload.get("corpus") != V9_CORPUS_NAME:
        return False
    if payload.get("architecture_order") != list(GNN_ARCHITECTURE_IDS):
        return False
    if set(payload.get("architectures", {})) != set(GNN_ARCHITECTURE_IDS):
        return False
    if payload.get("seeds") != [0, 1, 2]:
        return False
    if not isinstance(payload.get("ks"), list) or not payload["ks"]:
        return False
    if not isinstance(payload.get("daily_ks"), list) or not payload["daily_ks"]:
        return False
    for arm in GNN_ARCHITECTURE_IDS:
        row = payload["architectures"][arm]
        if not isinstance(row, dict):
            return False
        ensemble = row.get("ensemble")
        per_seed = row.get("per_seed")
        if not isinstance(ensemble, dict) or set(ensemble) != {
            "overall", "stratified", "daily"
        }:
            return False
        if not isinstance(per_seed, dict) or set(per_seed) != {"0", "1", "2"}:
            return False
        if not all(
            isinstance(ensemble.get(section), dict)
            for section in ("overall", "stratified", "daily")
        ):
            return False
        if not isinstance(ensemble["stratified"].get("observable"), dict):
            return False
        if not _finite_metric_tree(ensemble) or not _finite_metric_tree(per_seed):
            return False
    return True


def _load_v9_gnn_architecture_artifact(path):
    if not os.path.exists(path):
        p(f"[v9-dashboard] WARNING: {path} not found; GNN comparison unavailable.")
        return None
    try:
        with open(path) as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        p(f"[v9-dashboard] WARNING: invalid GNN comparison artifact: {error}")
        return None
    if not _is_compatible_v9_gnn_architecture(payload):
        p("[v9-dashboard] WARNING: discarded incompatible GNN comparison artifact.")
        return None
    return payload
```

At the end of `_load_v9_data()`, first remove any stale embedded
`v9GNNArchitectureComparison`, then set it only when this independent loader
returns a valid artifact. Do not change the existing `v9Demo`,
`v9RecoveryExplainer`, or `unsupervisedAD` paths.

- [ ] **Step 4: Run builder data tests**

Run:

```bash
rtk .venv/bin/python -m pytest -q tests/test_v9_dashboard_builder.py \
  -k "load_v9_data or gnn_architecture_artifact"
```

Expected: PASS.

### Task 4: Add the isolated accessible dashboard renderer

**Files:**

- Create: `Documents/Data/scripts/v9_gnn_architecture_ui.py`
- Modify: `tests/test_v9_dashboard_builder.py`

- [ ] **Step 1: Write failing view-model and renderer contract tests**

Load the new module with `importlib` and execute its pure JavaScript helper with
Node. Require:

```python
def test_gnn_architecture_view_model_keeps_registry_order_and_selected_depth():
    view = run_gnn_architecture_js(
        "buildGNNArchitectureViewModel(DATA, 'observable', 500)"
    )

    assert [row["id"] for row in view["rows"]] == [
        "sage", "rgcn", "gat", "gin", "kpiaa"
    ]
    assert view["population"] == "observable"
    assert view["selectedK"] == 500
    assert all("ensembleRecall" in row for row in view["rows"])
    assert all("seedRecallMin" in row and "seedRecallMax" in row for row in view["rows"])


def test_gnn_architecture_renderer_is_accessible_and_gnn_only():
    source = GNN_UI_MODULE_PATH.read_text()

    for label in ("GraphSAGE", "RGCN", "GAT", "GIN", "KPI-AA"):
        assert label in source
    assert "Baseline" not in source
    assert "Hybrid" not in source
    assert 'role="group"' in source
    assert "aria-pressed" in source
    assert "aria-describedby" in source
    assert "v9-gnn-architecture-data" in source
    assert "No GNN architecture comparison artifact is embedded." in source
    assert "python -m gnn.gnn_architecture_bakeoff" in source
```

- [ ] **Step 2: Run the focused UI tests and confirm failure**

Run:

```bash
rtk .venv/bin/python -m pytest -q tests/test_v9_dashboard_builder.py \
  -k "gnn_architecture_view_model or gnn_architecture_renderer"
```

Expected: FAIL because `v9_gnn_architecture_ui.py` does not exist.

- [ ] **Step 3: Implement the UI module**

Export exactly:

```python
GNN_ARCHITECTURE_VIEW_MODEL_JS = r"""
function buildGNNArchitectureViewModel(data,population,requestedK){
  const ids=['sage','rgcn','gat','gin','kpiaa'];
  const ks=(data&&data.ks||[]).map(Number).filter(Number.isFinite);
  const selectedK=ks.includes(Number(requestedK))
    ?Number(requestedK):(ks.includes(500)?500:(ks[0]||null));
  const selectedPopulation=population==='pool'?'pool':'observable';
  const rows=ids.map(id=>{
    const arm=data.architectures[id];
    const ensemble=selectedPopulation==='pool'
      ?arm.ensemble.overall:arm.ensemble.stratified.observable;
    const seedRows=Object.values(arm.per_seed).map(seed=>
      selectedPopulation==='pool'
        ?seed.overall:seed.stratified.observable
    );
    const found=Number(ensemble['found@'+selectedK]||0);
    const recall=Number(ensemble['recall@'+selectedK]||0);
    const seedFound=seedRows.map(row=>Number(row['found@'+selectedK]||0));
    const seedRecall=seedRows.map(row=>Number(row['recall@'+selectedK]||0));
    return {
      id,label:arm.label,looksFor:arm.looks_for,
      ensembleFound:found,ensembleRecall:recall,
      seedFoundMin:Math.min(...seedFound),seedFoundMax:Math.max(...seedFound),
      seedRecallMin:Math.min(...seedRecall),seedRecallMax:Math.max(...seedRecall)
    };
  });
  return {available:true,population:selectedPopulation,selectedK,ks,rows};
}
"""
```

`GNN_ARCHITECTURE_UI_JS` defines
`mountV9GNNArchitectureComparison(mount, artifact, helpers)`. It must:

- render an unavailable state plus the exact CLI command when no artifact is
  supplied;
- render only five fixed architecture IDs;
- expose whole-pool/observable buttons and a K selector;
- draw a native SVG recall bar chart without D3;
- attach an `aria-describedby` screen-reader table containing exact values;
- show ensemble found/recall and seed min-max values;
- include a collapsed native `<details>` daily-budget table;
- use delegated click/change handlers scoped to the mount;
- avoid global state and preserve reduced-motion behavior.

`GNN_ARCHITECTURE_CSS` scopes every selector beneath
`#v9-gnn-architecture-comparison`.

- [ ] **Step 4: Run UI module tests**

Run:

```bash
rtk .venv/bin/python -m pytest -q tests/test_v9_dashboard_builder.py \
  -k "gnn_architecture"
```

Expected: pure view-model and source-contract tests pass.

### Task 5: Mount the new section additively and prove preservation

**Files:**

- Modify: `Documents/Data/scripts/v9_dashboard_ui.py`
- Modify: `Documents/Data/scripts/build_v9_dashboard.py`
- Modify: `tests/test_v9_dashboard_builder.py`

- [ ] **Step 1: Write failing additive-preservation tests**

Capture the ordered list of existing V9 Results element IDs and renderer calls
before editing. Add assertions that, after integration:

```python
def test_gnn_architecture_section_is_strictly_additive():
    ui = UI_MODULE_PATH.read_text()

    assert ui.count('id="v9-gnn-architecture-comparison"') == 1
    assert ui.index('id="v9-model-notes"') < ui.index(
        'id="v9-gnn-architecture-comparison"'
    )
    assert ui.index('id="v9-gnn-architecture-comparison"') < ui.index(
        'id="v9-case-evidence"'
    )
    assert_existing_v9_ids_and_render_calls_keep_relative_order(ui)


def test_dashboard_builder_injects_gnn_assets_without_new_navigation_tab():
    html = build_minimal_dashboard_with_gnn_fixture()

    assert "mountV9GNNArchitectureComparison" in html
    assert "#v9-gnn-architecture-comparison" in html
    assert 'data-tab="v9GNNArchitecture"' not in html
    assert_existing_navigation_and_sections_keep_relative_order(html)
```

The preservation helper must list the pre-existing V9 IDs and calls explicitly,
not derive expectations from the modified source.

- [ ] **Step 2: Run integration tests and confirm failure**

Run:

```bash
rtk .venv/bin/python -m pytest -q tests/test_v9_dashboard_builder.py \
  -k "strictly_additive or injects_gnn_assets"
```

Expected: FAIL because the mount and assets are not integrated.

- [ ] **Step 3: Add only the mount and invocation to the existing V9 UI**

In the existing `sec.innerHTML` sequence, append:

```javascript
+'<section id="v9-gnn-architecture-comparison" '
+'aria-labelledby="v9-gnn-architecture-title"></section>'
```

after `v9-model-notes` and before the existing three-lens story. After the
existing render setup, add:

```javascript
mountV9GNNArchitectureComparison(
  document.getElementById('v9-gnn-architecture-comparison'),
  (typeof DATA!=='undefined'&&DATA)
    ?DATA.v9GNNArchitectureComparison:null,
  {fmt,pct,esc}
);
```

Do not alter or remove any existing string, ID, event listener, renderer call,
or relative ordering.

- [ ] **Step 4: Inject the isolated assets in the builder**

Import the three constants from `v9_gnn_architecture_ui.py`. Add the view-model
and renderer helpers before the `Tabs` registry via
`_inject_dashboard_tab_scripts()`, and append the scoped CSS beside existing V9
CSS:

```python
html = _inject_dashboard_tab_scripts(
    html,
    (
        GNN_ARCHITECTURE_VIEW_MODEL_JS
        + GNN_ARCHITECTURE_UI_JS
        + UNSUP_AD_VIEW_MODEL_JS
        + UNSUP_AD_CHART_JS
    ),
    V9_RESULTS_JS + UNSUP_AD_JS,
)
html = html.replace(
    "</style>",
    (
        V9_RESULTS_CSS
        + "\n"
        + GNN_ARCHITECTURE_CSS
        + "\n"
        + UNSUP_AD_CSS
        + "\n</style>"
    ),
    1,
)
```

- [ ] **Step 5: Run all dashboard tests**

Run:

```bash
rtk .venv/bin/python -m pytest -q tests/test_v9_dashboard_builder.py
```

Expected: PASS, including pre-existing source and generated-dashboard contracts.

### Task 6: Smoke-test, run full V9, rebuild, and verify

**Files:**

- Generate: `gnn/diagnostics/gnn_architecture_comparison_v9.json`
- Generate: `Documents/Data/v9_dashboard/data_v9.json`
- Generate: `Documents/Data/v9_dashboard/index.html`
- Modify: `Documents/Data/changes_3.md`
- Modify: `PROJECT_MEMORY.md`

- [ ] **Step 1: Run a cheap V9dev smoke comparison**

Run:

```bash
rtk .venv/bin/python -m gnn.gnn_architecture_bakeoff \
  --corpus Documents/Data/synthetic_cbp_graph_corpus_v9dev \
  --output /tmp/gnn_architecture_comparison_v9dev.json \
  --seeds 0 1 2 \
  --epochs 1 \
  --train-bucket M \
  --ks 5 10 \
  --daily-ks 1 2
```

Expected: exit 0; output reports all five architectures and three seeds; JSON
contains no Baseline/Hybrid fields.

- [ ] **Step 2: Run the full V9 comparison**

Run:

```bash
rtk .venv/bin/python -m gnn.gnn_architecture_bakeoff \
  --corpus Documents/Data/synthetic_cbp_graph_corpus_v9 \
  --output gnn/diagnostics/gnn_architecture_comparison_v9.json \
  --seeds 0 1 2 \
  --epochs 18 \
  --train-bucket Q \
  --ks 50 100 200 500 1000 2000 5000 \
  --daily-ks 5 10 25 50
```

Expected: exit 0; exactly five GNN architectures; no Baseline/Hybrid fitting or
output; atomic final artifact.

- [ ] **Step 3: Validate the measured artifact**

Run:

```bash
rtk .venv/bin/python -c \
  "import json; from pathlib import Path; from gnn.gnn_architecture_bakeoff import validate_artifact; p=Path('gnn/diagnostics/gnn_architecture_comparison_v9.json'); d=json.loads(p.read_text()); validate_artifact(d); print(d['architecture_order'], d['seeds'])"
```

Expected:

```text
['sage', 'rgcn', 'gat', 'gin', 'kpiaa'] [0, 1, 2]
```

- [ ] **Step 4: Rebuild the dashboard**

Run:

```bash
rtk .venv/bin/python Documents/Data/scripts/build_v9_dashboard.py
```

Expected: exit 0; `data_v9.json` embeds
`v9GNNArchitectureComparison`; all existing dashboard keys and tabs remain.

- [ ] **Step 5: Perform browser verification**

Serve:

```bash
rtk .venv/bin/python -m http.server 8000 --directory Documents/Data/v9_dashboard
```

Verify the V9 Results tab with the browser skill:

- every prior section is still present in the same relative order;
- the architecture block contains five GNNs and no Baseline/Hybrid row;
- population/depth controls update chart and table consistently;
- keyboard focus, accessible names, screen-reader table, and `<details>` work;
- mobile layout does not overflow;
- the console has no errors.

- [ ] **Step 6: Record only measured results**

Add the exact command, configuration, artifact path, and measured five-model
results to `Documents/Data/changes_3.md`. Update `PROJECT_MEMORY.md` with durable
schema/command decisions and any measured runtime or resource risk. Do not
change historical GraphSAGE/Hybrid result claims.

- [ ] **Step 7: Run the affected suite and inspect the final diff**

Run:

```bash
rtk .venv/bin/python -m pytest -q \
  tests/test_gnn_architecture_bakeoff.py \
  tests/test_run_demo_smoke.py \
  tests/test_df_graphmodel_rgcn.py \
  tests/test_v9_dashboard_builder.py
rtk git diff --check
rtk merget diff
```

Expected: all tests pass; no whitespace errors; diff contains only additive GNN
bake-off/dashboard work plus measured documentation. Let the Merget Historian
record the work; do not create a manual Git commit unless the user asks.
