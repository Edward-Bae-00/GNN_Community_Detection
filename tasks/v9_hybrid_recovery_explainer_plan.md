# V9 Hybrid Recovery Explainer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct HOT-plate as-of timing, preserve the three-seed V9 headline evaluation, and add a seed-0 Hybrid-only recovery explorer with complete message communities, measured attribution, and grounded local Gemma narratives.

**Architecture:** Keep the existing three-seed comparison JSON authoritative for headline V9 results. Add a separate seed-0 observability pipeline: pure recovery/ranking logic in `gnn/recovery_observability.py`, Torch/PyG attribution in `gnn/sage_explainer.py`, and local Ollama narration in `gnn/explanation_narrative.py`. Emit a versioned `hybrid_recovery_explanations_v9.json` artifact and render it through a focused dashboard UI module without reusing the generic lifetime Explorer heuristics.

**Tech Stack:** Python 3.14, pandas, NumPy, SciPy, PyTorch, PyTorch Geometric 2.8, pytest, standard-library `subprocess`/JSON, Ollama `gemma4:12b`, vanilla JavaScript, HTML canvas, and CSS.

---

## File map

**Create:**

- `gnn/recovery_observability.py` — pure same-budget recovery sets, frozen rank references, case traces, and representative ordering.
- `gnn/sage_explainer.py` — seed-0 day snapshots, exact explanation communities, GNNExplainer restart aggregation, grouped counterfactuals, and serialization guards.
- `gnn/explanation_narrative.py` — local `gemma4:12b` command adapter, fact packets, claim validation, and deterministic fallback.
- `gnn/observability_artifact.py` — versioned artifact composition, representative-attempt loop, atomic serialization, and generation diagnostics.
- `Documents/Data/scripts/v9_recovery_explainer_ui.py` — scoped Results-section CSS/JS, view-model validation, split explorer, and complete-community canvas.
- `tests/test_recovery_observability.py`
- `tests/test_sage_explainer.py`
- `tests/test_explanation_narrative.py`
- `tests/test_v9_recovery_explainer_ui.py`

**Modify:**

- `gnn/graphmodel_rgcn.py` — label-available HOT timing, edge provenance, and feature names.
- `gnn/learned_cell.py` — shared day-snapshot input construction used by production scoring and explanations.
- `gnn/run_demo.py` — per-seed score bundle, seed-0 observability orchestration, and separate artifact output.
- `tests/test_df_graphmodel_rgcn.py`
- `tests/test_run_demo_smoke.py`
- `Documents/Data/scripts/build_v9_dashboard.py`
- `Documents/Data/scripts/v9_dashboard_ui.py`
- `tests/test_v9_dashboard_builder.py`
- `Documents/Data/changes_3.md`

**Regenerate after tests pass:**

- `gnn/diagnostics/demo_comparison_v9.json`
- `gnn/diagnostics/hybrid_recovery_explanations_v9.json`
- `Documents/Data/v9_dashboard/data_v9.json`
- `Documents/Data/v9_dashboard/index.html`

---

### Task 1: Correct `SHARED_PLATE_HOT` availability

**Files:**

- Modify: `gnn/graphmodel_rgcn.py:28-71`
- Modify: `tests/test_df_graphmodel_rgcn.py:81-129`

- [ ] **Step 1: Replace the current event-time fixture with explicit delayed availability cases**

Replace the old event-time plate test with this self-contained fixture and three focused tests:

```python
def _write_plate_rows(tmp_path, events):
    records = []
    crossings = []
    for event_id, observed_id, person_id, vehicle_id, event_time, seizure, label_time in events:
        records.append({
            "observed_person_record_id": observed_id,
            "event_id": event_id,
            "event_timestamp_utc": event_time,
            "observed_residence_location_id": pd.NA,
        })
        crossings.append({
            "event_id": event_id,
            "observed_person_record_id": observed_id,
            "vehicle_id": vehicle_id,
            "event_timestamp_utc": event_time,
            "seizure_flag": seizure,
            "label_available_time_utc": label_time,
        })
    pd.DataFrame(records).to_csv(tmp_path / "observed_person_records.csv", index=False)
    pd.DataFrame(crossings).to_csv(tmp_path / "crossing_events.csv", index=False)
    return {observed_id: person_id for _, observed_id, person_id, *_ in events}


def test_build_anchor_graph_hot_plate_waits_for_label_availability(tmp_path):
    mapping = _write_plate_rows(tmp_path, [
        ("e1", "r1", "p1", "veh-1", "2024-01-01T00:00:00Z", False, None),
        ("e2", "r2", "p2", "veh-1", "2024-01-03T00:00:00Z", True,
         "2024-01-10T00:00:00Z"),
        ("e3", "r3", "p3", "veh-1", "2024-01-08T00:00:00Z", False, None),
        ("e4", "r4", "p4", "veh-1", "2024-01-11T00:00:00Z", False, None),
    ])
    edges = gm.build_anchor_graph(mapping, tmp_path, include_plate=True)

    before = edges[(edges.u == "p2") & (edges.v == "p3")].iloc[0]
    after = edges[(edges.u == "p2") & (edges.v == "p4")].iloc[0]
    assert before.edge_type == "SHARED_PLATE"
    assert after.edge_type == "SHARED_PLATE_HOT"


def test_hot_plate_at_label_time_is_not_active_at_same_snapshot(tmp_path):
    mapping = _write_plate_rows(tmp_path, [
        ("e1", "r1", "p1", "veh-1", "2024-01-01T00:00:00Z", True,
         "2024-01-10T00:00:00Z"),
        ("e2", "r2", "p2", "veh-1", "2024-01-10T00:00:00Z", False, None),
    ])
    edges = gm.build_anchor_graph(mapping, tmp_path, include_plate=True)
    snapshot = pd.Timestamp("2024-01-10T00:00:00Z")
    edge = edges[(edges.u == "p1") & (edges.v == "p2")].iloc[0]
    assert edge.edge_type == "SHARED_PLATE_HOT"
    assert edge.avail_time == snapshot
    assert not (edge.avail_time < snapshot)


@pytest.mark.parametrize("label_time", [None, "not-a-time"])
def test_missing_or_malformed_label_time_never_creates_hot_plate(tmp_path, label_time):
    mapping = _write_plate_rows(tmp_path, [
        ("e1", "r1", "p1", "veh-1", "2024-01-01T00:00:00Z", True, label_time),
        ("e2", "r2", "p2", "veh-1", "2024-01-20T00:00:00Z", False, None),
    ])
    edges = gm.build_anchor_graph(mapping, tmp_path, include_plate=True)
    assert "SHARED_PLATE_HOT" not in set(edges.edge_type)
```

- [ ] **Step 2: Run the tests and verify the current implementation fails**

Run:

```bash
rtk .venv/bin/python -m pytest -q tests/test_df_graphmodel_rgcn.py -k 'hot_plate or shares_plate'
```

Expected: the delayed-availability test fails because current code uses `event_timestamp_utc` as the first seizure time.

- [ ] **Step 3: Derive HOT state from official label availability**

Update the `include_plate` block in `build_anchor_graph()`:

```python
ce = pd.read_csv(
    corpus_dir / "crossing_events.csv",
    usecols=[
        "observed_person_record_id",
        "vehicle_id",
        "event_timestamp_utc",
        "seizure_flag",
        "label_available_time_utc",
    ],
)
ce["identity"] = ce["observed_person_record_id"].map(obs_to_person)
ce = ce.dropna(subset=["identity", "vehicle_id"])
ce["avail_time"] = pd.to_datetime(
    ce["event_timestamp_utc"], utc=True, errors="coerce"
)
ce["label_available_time"] = pd.to_datetime(
    ce["label_available_time_utc"], utc=True, errors="coerce"
)
ce["seizure_flag"] = ce["seizure_flag"].astype(str).str.lower().eq("true")
first_observable_seizure_time = (
    ce.loc[ce["seizure_flag"] & ce["label_available_time"].notna()]
    .groupby("vehicle_id")["label_available_time"]
    .min()
)

merged_ce = ce.merge(ce, on="vehicle_id")
merged_ce = merged_ce[merged_ce["identity_x"] != merged_ce["identity_y"]]
merged_ce["avail_time"] = merged_ce[["avail_time_x", "avail_time_y"]].max(axis=1)
merged_ce["edge_type"] = "SHARED_PLATE"
merged_ce["first_observable_seizure_time"] = merged_ce["vehicle_id"].map(
    first_observable_seizure_time
)
hot_mask = (
    merged_ce["first_observable_seizure_time"].notna()
    & (merged_ce["avail_time"] >= merged_ce["first_observable_seizure_time"])
)
merged_ce.loc[hot_mask, "edge_type"] = "SHARED_PLATE_HOT"
```

- [ ] **Step 4: Run the focused graph/model tests**

Run:

```bash
rtk .venv/bin/python -m pytest -q tests/test_df_graphmodel_rgcn.py tests/test_demo_baseline.py
```

Expected: all tests pass; the baseline remains strict on `label_available_time_utc` and the graph now matches it.

- [ ] **Step 5: Commit the leak fix**

```bash
rtk git add gnn/graphmodel_rgcn.py tests/test_df_graphmodel_rgcn.py
rtk git commit -m "fix: delay hot-plate signal until label availability"
```

---

### Task 2: Add pure recovery-set accounting

**Files:**

- Create: `gnn/recovery_observability.py`
- Create: `tests/test_recovery_observability.py`
- Reference: `gnn/run_demo.py:69-195`

- [ ] **Step 1: Write failing tests for unique-person recovery and overlap**

```python
def test_recovery_overlap_uses_exact_person_sets():
    pool = pd.DataFrame({
        "event_id": ["e1", "e2", "e3", "e4"],
        "primary_person_id": ["p1", "p1", "p2", "p3"],
        "t": pd.to_datetime([
            "2025-01-01T01:00:00Z", "2025-01-01T02:00:00Z",
            "2025-01-01T03:00:00Z", "2025-01-02T01:00:00Z",
        ]),
        "hidden": [True, True, True, True],
    })
    baseline = simulate_recovery_run(
        pool, np.array([0.9, 0.8, 0.7, 0.6]), arm="baseline",
        daily_budget=1, official_caught_times={},
    )
    hybrid = simulate_recovery_run(
        pool, np.array([0.8, 0.7, 0.9, 0.95]), arm="hybrid_seed0",
        daily_budget=1, official_caught_times={},
    )
    overlap = recovery_overlap(baseline, hybrid)

    assert overlap.baseline_ids == frozenset({"p1", "p3"})
    assert overlap.hybrid_ids == frozenset({"p2", "p3"})
    assert overlap.both_ids == frozenset({"p3"})
    assert overlap.hybrid_only_ids == frozenset({"p2"})
    assert overlap.baseline_only_ids == frozenset({"p1"})
    assert overlap.summary == {
        "overlap_ids_available": True,
        "baseline_recovered": 2,
        "recovered_by_both": 1,
        "hybrid_only_recovered": 1,
        "baseline_only_recovered": 1,
        "hybrid_total": 2,
        "net_gain": 0,
    }


def test_recovery_run_anchors_first_hidden_inspection_and_defers_removal():
    pool = pd.DataFrame({
        "event_id": ["e-highest", "e-repeat", "e-other"],
        "primary_person_id": ["p1", "p1", "p2"],
        "t": pd.to_datetime([
            "2025-01-01T01:00:00Z", "2025-01-01T02:00:00Z",
            "2025-01-01T03:00:00Z",
        ]),
        "hidden": [True, True, True],
    })
    run = simulate_recovery_run(
        pool, np.array([0.9, 0.8, 0.7]), arm="hybrid_seed0",
        daily_budget=2, official_caught_times={},
    )
    anchor = run.first_recovery["p1"]
    assert anchor.event_id == "e-highest"
    assert anchor.inspected_rank == 1
    assert run.days[anchor.scoring_day].inspected_row_indices == (0, 1)
```

- [ ] **Step 2: Run the new test file and verify import failure**

```bash
rtk .venv/bin/python -m pytest -q tests/test_recovery_observability.py
```

Expected: collection fails because `gnn.recovery_observability` does not exist.

- [ ] **Step 3: Implement immutable recovery records and the simulator**

Create `gnn/recovery_observability.py` with these public records and functions:

```python
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RecoveryAnchor:
    person_id: str
    event_id: str
    row_index: int
    scoring_day: pd.Timestamp
    inspected_rank: int


@dataclass(frozen=True)
class DailyPoolTrace:
    scoring_day: pd.Timestamp
    candidate_row_indices: tuple[int, ...]
    inspected_row_indices: tuple[int, ...]


@dataclass(frozen=True)
class RecoveryRun:
    arm: str
    daily_budget: int
    recovered_ids: frozenset[str]
    first_recovery: Mapping[str, RecoveryAnchor]
    days: Mapping[pd.Timestamp, DailyPoolTrace]


@dataclass(frozen=True)
class RecoveryOverlap:
    baseline_ids: frozenset[str]
    hybrid_ids: frozenset[str]
    both_ids: frozenset[str]
    hybrid_only_ids: frozenset[str]
    baseline_only_ids: frozenset[str]

    @property
    def summary(self) -> dict[str, int | bool]:
        return {
            "overlap_ids_available": True,
            "baseline_recovered": len(self.baseline_ids),
            "recovered_by_both": len(self.both_ids),
            "hybrid_only_recovered": len(self.hybrid_only_ids),
            "baseline_only_recovered": len(self.baseline_only_ids),
            "hybrid_total": len(self.hybrid_ids),
            "net_gain": len(self.hybrid_ids) - len(self.baseline_ids),
        }


def simulate_recovery_run(
    pool: pd.DataFrame,
    scores: np.ndarray,
    *,
    arm: str,
    daily_budget: int,
    official_caught_times: Mapping[str, pd.Timestamp],
) -> RecoveryRun:
    required = {"event_id", "primary_person_id", "t", "hidden"}
    missing = required.difference(pool.columns)
    if missing:
        raise ValueError(f"pool is missing required columns: {sorted(missing)}")
    if int(daily_budget) <= 0:
        raise ValueError("daily_budget must be positive")
    work = pool.reset_index(drop=True).copy()
    work["_row_index"] = np.arange(len(work), dtype=int)
    work["_day"] = pd.to_datetime(work["t"], utc=True).dt.floor("D")
    values = np.asarray(scores, dtype=float)
    if len(values) != len(work) or not np.isfinite(values).all():
        raise ValueError("scores must be finite and aligned to pool rows")

    caught = {
        str(person_id): pd.to_datetime(value, utc=True, errors="coerce")
        for person_id, value in official_caught_times.items()
    }
    recovered: set[str] = set()
    anchors: dict[str, RecoveryAnchor] = {}
    traces: dict[pd.Timestamp, DailyPoolTrace] = {}
    for day, frame in work.groupby("_day", sort=True):
        candidate_rows = []
        for row_index in frame["_row_index"].astype(int):
            person_id = str(work.at[row_index, "primary_person_id"])
            caught_time = caught.get(person_id)
            officially_caught = caught_time is not None and not pd.isna(caught_time) and caught_time < day
            if person_id not in recovered and not officially_caught:
                candidate_rows.append(row_index)
        ordered = sorted(candidate_rows, key=lambda i: (-values[i], i))
        inspected = ordered[:daily_budget]
        today: set[str] = set()
        for rank, row_index in enumerate(inspected, start=1):
            row = work.iloc[row_index]
            person_id = str(row.primary_person_id)
            if bool(row.hidden) and person_id not in recovered and person_id not in today:
                today.add(person_id)
                anchors[person_id] = RecoveryAnchor(
                    person_id=person_id,
                    event_id=str(row.event_id),
                    row_index=row_index,
                    scoring_day=day,
                    inspected_rank=rank,
                )
        traces[day] = DailyPoolTrace(day, tuple(ordered), tuple(inspected))
        recovered.update(today)
    return RecoveryRun(
        arm=arm,
        daily_budget=daily_budget,
        recovered_ids=frozenset(recovered),
        first_recovery=MappingProxyType(anchors),
        days=MappingProxyType(traces),
    )


def recovery_overlap(baseline: RecoveryRun, hybrid: RecoveryRun) -> RecoveryOverlap:
    if baseline.daily_budget != hybrid.daily_budget:
        raise ValueError("recovery runs must use the same daily budget")
    baseline_ids = baseline.recovered_ids
    hybrid_ids = hybrid.recovered_ids
    return RecoveryOverlap(
        baseline_ids=baseline_ids,
        hybrid_ids=hybrid_ids,
        both_ids=baseline_ids & hybrid_ids,
        hybrid_only_ids=hybrid_ids - baseline_ids,
        baseline_only_ids=baseline_ids - hybrid_ids,
    )
```

- [ ] **Step 4: Run recovery tests**

```bash
rtk .venv/bin/python -m pytest -q tests/test_recovery_observability.py
```

Expected: all recovery-set, strict-day-start, deduplication, and arm-isolation tests pass.

- [ ] **Step 5: Commit the pure recovery layer**

```bash
rtk git add gnn/recovery_observability.py tests/test_recovery_observability.py
rtk git commit -m "feat: add seed observability recovery accounting"
```

---

### Task 3: Add frozen rank references and representative ordering

**Files:**

- Modify: `gnn/recovery_observability.py`
- Modify: `tests/test_recovery_observability.py`
- Reference: `gnn/run_demo.py:390-397`

- [ ] **Step 1: Write failing rank and selection tests**

```python
def test_rank_reference_matches_existing_rank_fuse():
    pool = pd.DataFrame({"event_id": ["e1", "e2", "e3"]})
    baseline = np.array([0.1, 0.8, 0.4])
    gnn = np.array([0.9, 0.2, 0.5])
    reference = build_rank_reference(pool, baseline, gnn, blend_weight=0.75)
    np.testing.assert_allclose(
        reference.seed0_hybrid_score,
        run_demo._rank_fuse(baseline, gnn, 0.75),
    )
    assert reference.percentile_reference_id.startswith("sha256:")


def test_representative_attempt_order_is_deterministic_and_round_robin():
    day = pd.Timestamp("2025-01-02T00:00:00Z")
    cases = [
        HybridOnlyCase("p1", RecoveryAnchor("p1", "e1", 0, day, 1), 21, 2, 1,
                       0.40, 0.90, ("COTRAVEL",), "2025-01"),
        HybridOnlyCase("p2", RecoveryAnchor("p2", "e2", 1, day, 1), 20, 3, 1,
                       0.41, 0.88, ("RESIDENCE",), "2025-01"),
        HybridOnlyCase("p3", RecoveryAnchor("p3", "e3", 2, day, 1), 19, 4, 1,
                       0.42, 0.87, ("SHARED_PLATE",), "2025-02"),
        HybridOnlyCase("p4", RecoveryAnchor("p4", "e4", 3, day, 1), 18, 5, 1,
                       0.43, 0.86, ("COTRAVEL",), "2025-01"),
    ]
    first = representative_attempt_order(cases)
    second = representative_attempt_order(list(reversed(cases)))
    assert [case.person_id for case in first] == [case.person_id for case in second]
    assert {case.relationship_categories[0] for case in first[:3]} == {
        "COTRAVEL", "RESIDENCE", "SHARED_PLATE"
    }
```

- [ ] **Step 2: Run the tests and verify missing symbols**

```bash
rtk .venv/bin/python -m pytest -q tests/test_recovery_observability.py -k 'rank_reference or representative'
```

Expected: failures name `build_rank_reference` and `representative_attempt_order`.

- [ ] **Step 3: Implement the frozen reference and deterministic queues**

Add the imports, records, and complete deterministic ranking helpers below. Percentiles use `scipy.stats.rankdata(..., method="average") / n`. The daily Baseline rank uses the Baseline arm's day-state candidate set; the GNN and Hybrid ranks use the seed-0 Hybrid arm's day-state candidate set. Each set is independently hashed and serialized in the decision trace.

```python
import hashlib
from collections import defaultdict, deque
from dataclasses import field

from scipy.stats import rankdata


@dataclass(frozen=True)
class FrozenRankReference:
    percentile_reference_id: str
    event_ids: tuple[str, ...]
    baseline_raw: np.ndarray
    seed0_gnn_raw: np.ndarray
    baseline_percentile: np.ndarray
    seed0_gnn_percentile: np.ndarray
    seed0_hybrid_score: np.ndarray
    baseline_selection_score: np.ndarray
    seed0_gnn_selection_score: np.ndarray
    seed0_hybrid_selection_score: np.ndarray
    blend_weight: float


@dataclass(frozen=True)
class HybridOnlyCase:
    person_id: str
    anchor: RecoveryAnchor
    baseline_rank: int
    gnn_rank: int
    hybrid_rank: int
    baseline_percentile: float
    gnn_percentile: float
    relationship_categories: tuple[str, ...]
    scoring_period: str
    same_day_person_row_indices: tuple[int, ...] = ()
    baseline_candidate_row_indices: tuple[int, ...] = ()
    hybrid_candidate_row_indices: tuple[int, ...] = ()
    decision_trace: Mapping[str, object] = field(default_factory=dict)

    @property
    def hybrid_rank_uplift(self) -> int:
        return self.baseline_rank - self.hybrid_rank

    @property
    def gnn_percentile_uplift(self) -> float:
        return self.gnn_percentile - self.baseline_percentile


def _ordered_id_hash(values) -> str:
    payload = "\n".join(str(value) for value in values).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _selection_tiebreak(scores) -> np.ndarray:
    values = np.asarray(scores, dtype=float)
    rng = np.random.default_rng(42)
    return values + rng.uniform(0.0, 1e-9, size=len(values))


def build_rank_reference(pool, baseline_raw, seed0_gnn_raw, blend_weight):
    baseline = np.asarray(baseline_raw, dtype=float)
    gnn = np.asarray(seed0_gnn_raw, dtype=float)
    n_rows = len(pool)
    if n_rows == 0 or len(baseline) != n_rows or len(gnn) != n_rows:
        raise ValueError("rank inputs must be non-empty and aligned to pool rows")
    if not np.isfinite(baseline).all() or not np.isfinite(gnn).all():
        raise ValueError("rank inputs must be finite")
    baseline_pct = rankdata(baseline, method="average") / n_rows
    gnn_pct = rankdata(gnn, method="average") / n_rows
    hybrid = blend_weight * gnn_pct + (1.0 - blend_weight) * baseline_pct
    event_ids = tuple(pool.event_id.astype(str))
    return FrozenRankReference(
        percentile_reference_id=_ordered_id_hash(event_ids),
        event_ids=event_ids,
        baseline_raw=baseline.copy(),
        seed0_gnn_raw=gnn.copy(),
        baseline_percentile=baseline_pct,
        seed0_gnn_percentile=gnn_pct,
        seed0_hybrid_score=hybrid,
        baseline_selection_score=_selection_tiebreak(baseline),
        seed0_gnn_selection_score=_selection_tiebreak(gnn),
        seed0_hybrid_selection_score=_selection_tiebreak(hybrid),
        blend_weight=float(blend_weight),
    )


def _rank_in_candidates(scores, row_index, candidate_row_indices) -> int:
    ordered = sorted(candidate_row_indices, key=lambda index: (-scores[index], index))
    if row_index not in ordered:
        raise ValueError("anchor row is absent from its daily candidate reference")
    return ordered.index(row_index) + 1


def build_decision_trace(
    reference: FrozenRankReference,
    *,
    row_index: int,
    baseline_candidate_row_indices: tuple[int, ...],
    hybrid_candidate_row_indices: tuple[int, ...],
    daily_budget: int,
) -> dict[str, object]:
    return {
        "percentile_reference_id": reference.percentile_reference_id,
        "baseline_daily_reference_id": _ordered_id_hash(
            reference.event_ids[index] for index in baseline_candidate_row_indices
        ),
        "hybrid_daily_reference_id": _ordered_id_hash(
            reference.event_ids[index] for index in hybrid_candidate_row_indices
        ),
        "daily_budget": int(daily_budget),
        "baseline_raw": float(reference.baseline_raw[row_index]),
        "baseline_percentile": float(reference.baseline_percentile[row_index]),
        "baseline_weighted_term": float(
            (1.0 - reference.blend_weight) * reference.baseline_percentile[row_index]
        ),
        "baseline_rank": _rank_in_candidates(
            reference.baseline_selection_score, row_index,
            baseline_candidate_row_indices,
        ),
        "seed0_gnn_probability": float(reference.seed0_gnn_raw[row_index]),
        "seed0_gnn_percentile": float(reference.seed0_gnn_percentile[row_index]),
        "seed0_gnn_weighted_term": float(
            reference.blend_weight * reference.seed0_gnn_percentile[row_index]
        ),
        "seed0_gnn_rank": _rank_in_candidates(
            reference.seed0_gnn_selection_score, row_index,
            hybrid_candidate_row_indices,
        ),
        "seed0_hybrid_score": float(reference.seed0_hybrid_score[row_index]),
        "seed0_hybrid_rank": _rank_in_candidates(
            reference.seed0_hybrid_selection_score, row_index,
            hybrid_candidate_row_indices,
        ),
    }


def representative_attempt_order(cases) -> list[HybridOnlyCase]:
    ranked = sorted(
        cases,
        key=lambda case: (
            -case.hybrid_rank_uplift,
            -case.gnn_percentile_uplift,
            case.person_id,
        ),
    )
    queues = defaultdict(deque)
    for case in ranked:
        for category in sorted(set(case.relationship_categories) or {"NONE"}):
            queues[(category, case.scoring_period)].append(case)
    selected = set()
    ordered = []
    while any(queues.values()):
        progressed = False
        for key in sorted(queues):
            queue = queues[key]
            while queue and queue[0].person_id in selected:
                queue.popleft()
            if queue:
                case = queue.popleft()
                selected.add(case.person_id)
                ordered.append(case)
                progressed = True
        if not progressed:
            break
    return ordered
```

- [ ] **Step 4: Run the complete pure-observability suite**

```bash
rtk .venv/bin/python -m pytest -q tests/test_recovery_observability.py
```

Expected: all tests pass, including deterministic ordering after input reversal.

- [ ] **Step 5: Commit the ranking layer**

```bash
rtk git add gnn/recovery_observability.py tests/test_recovery_observability.py
rtk git commit -m "feat: add frozen observability rank references"
```

---

### Task 4: Retain seed-0 models and scores without changing ensemble metrics

**Files:**

- Modify: `gnn/run_demo.py:420-443,473-580`
- Modify: `tests/test_run_demo_smoke.py`

- [ ] **Step 1: Write a failing bundle/compatibility test**

```python
def test_gnn_score_bundle_preserves_existing_ensemble(monkeypatch):
    def fake_train(*args, seed, **kwargs):
        return SimpleNamespace(seed=int(seed))

    def fake_score(model, candidate_pool, *args, **kwargs):
        return np.arange(len(candidate_pool), dtype=float) + model.seed

    monkeypatch.setattr(run_demo, "_train_caught_rgcn", fake_train)
    monkeypatch.setattr(run_demo, "_score_pool", fake_score)
    edges = pd.DataFrame(columns=["u", "v", "avail_time", "rel"])
    train_pool = pd.DataFrame({
        "primary_obs_id": ["obs-1"],
        "t": pd.to_datetime(["2023-01-01T00:00:00Z"]),
    })
    scored_pool = pd.DataFrame({
        "primary_obs_id": ["obs-1", "obs-1"],
        "t": pd.to_datetime([
            "2025-01-01T00:00:00Z", "2025-01-02T00:00:00Z",
        ]),
    })
    bundle = run_demo._gnn_scores(
        edges, ["p1"], {"p1": np.array([1.0])}, {}, train_pool,
        np.array([0]), [scored_pool], {"obs-1": "p1"}, seeds=(0, 1, 2),
        epochs=1, train_bucket="M", model_cls=object, num_rel=4,
    )
    assert set(bundle.models_by_seed) == {0, 1, 2}
    np.testing.assert_allclose(
        bundle.ensemble(0),
        np.array([1.0, 2.0]),
    )
```

Add `from types import SimpleNamespace` to the test imports. Extend `test_run_demo_smoke()` with `assert "observability" not in out` so the aggregate return contract remains focused.

- [ ] **Step 2: Run the focused smoke test and verify the old list return fails**

```bash
rtk .venv/bin/python -m pytest -q tests/test_run_demo_smoke.py -k 'score_bundle or ensemble_result_payload'
```

Expected: failures show `_gnn_scores()` returns a list and has no `models_by_seed`.

- [ ] **Step 3: Implement `GNNScoreBundle` and keep ensemble call sites unchanged in meaning**

```python
from dataclasses import dataclass

import torch


@dataclass(frozen=True)
class GNNScoreBundle:
    seed_order: tuple[int, ...]
    models_by_seed: dict[int, torch.nn.Module]
    scores_by_seed: dict[int, tuple[np.ndarray, ...]]

    def ensemble(self, pool_index: int) -> np.ndarray:
        ordered = [self.scores_by_seed[seed][pool_index] for seed in self.seed_order]
        return np.mean(np.column_stack(ordered), axis=1)


def _gnn_scores(
    edges_typed, node_ids, node_feat, caught_time, train_pool,
    train_labels, pools, obs2id, *, seeds, epochs, train_bucket,
    model_cls, num_rel,
):
    seed_order = tuple(int(seed) for seed in seeds)
    if not seed_order:
        raise ValueError("at least one GNN seed is required")
    index = {person_id: i for i, person_id in enumerate(node_ids)}
    models_by_seed = {}
    scores_by_seed = {}
    for seed in seed_order:
        model = _train_caught_rgcn(
            edges_typed, node_ids, node_feat, caught_time, train_pool, obs2id,
            train_labels, seed=seed, epochs=epochs, lr=1e-2,
            train_cutoff="2024-01-01", train_bucket=train_bucket,
            num_rel=num_rel, model_cls=model_cls,
        )
        models_by_seed[int(seed)] = model
        scores_by_seed[int(seed)] = tuple(
            _score_pool(
                model, candidate_pool, obs2id, edges_typed, node_ids, node_feat,
                caught_time, index, num_rel=num_rel,
            )
            for candidate_pool in pools
        )
    return GNNScoreBundle(seed_order, models_by_seed, scores_by_seed)
```

In `main()`, replace the old tuple unpack with:

```python
score_bundle = _gnn_scores(
    edges_typed, node_ids, node_feat, caught_time, train_pool, train_labels,
    [valid_pool, pool], obs2id, seeds=seeds, epochs=epochs,
    train_bucket=train_bucket, model_cls=spec["cls"], num_rel=spec["num_rel"],
)
gnn_valid_raw = score_bundle.ensemble(0)
gnn_test_raw = score_bundle.ensemble(1)
```

Continue building all existing arms, bootstraps, simulated catches, and JSON fields from those ensemble arrays.

- [ ] **Step 4: Run the run-demo and graph tests**

```bash
rtk .venv/bin/python -m pytest -q tests/test_run_demo_smoke.py tests/test_df_graphmodel_rgcn.py
```

Expected: all tests pass and the smoke output schema remains aggregate-only.

- [ ] **Step 5: Commit per-seed retention**

```bash
rtk git add gnn/run_demo.py tests/test_run_demo_smoke.py
rtk git commit -m "refactor: retain per-seed GNN scores for observability"
```

---

### Task 5: Share day snapshots and preserve tensor-edge provenance

**Files:**

- Modify: `gnn/graphmodel_rgcn.py:98-119`
- Modify: `gnn/learned_cell.py:43-77,126-138,186-202`
- Create: `gnn/sage_explainer.py`
- Create: `tests/test_sage_explainer.py`
- Modify: `tests/test_df_graphmodel_rgcn.py`

- [ ] **Step 1: Write failing strict-as-of, parity, provenance, and community tests**

```python
SCORING_DAY = pd.Timestamp("2025-01-02T00:00:00Z")


def _explanation_fixture():
    torch.manual_seed(0)
    node_ids = ["target", "poolmate", "hop1", "hop2", "future"]
    node_feat = {person_id: np.array([1.0]) for person_id in node_ids}
    edges = pd.DataFrame({
        "source_row_id": ["before", "cot", "res", "plate", "at-boundary"],
        "canonical_pair_group_id": ["g0", "g1", "g2", "g3", "g4"],
        "u": ["future", "target", "poolmate", "hop1", "target"],
        "v": ["hop1", "poolmate", "hop1", "hop2", "future"],
        "avail_time": pd.to_datetime([
            "2025-01-01T20:00:00Z", "2025-01-01T01:00:00Z",
            "2025-01-01T02:00:00Z", "2025-01-01T03:00:00Z",
            "2025-01-02T00:00:00Z",
        ]),
        "rel": [3, 0, 1, 2, 0],
        "edge_type": ["SHARED_PLATE_HOT", "COTRAVEL", "RESIDENCE",
                      "SHARED_PLATE", "COTRAVEL"],
    })
    caught_times = {
        "hop1": pd.Timestamp("2025-01-01T23:59:59Z"),
        "future": SCORING_DAY,
    }
    model = _SAGE(in_dim=8, hidden=4, out=4, num_relations=4)
    engine = Seed0ExplanationEngine(
        model=model, edges_typed=edges, node_ids=node_ids,
        node_feat=node_feat, caught_time=caught_times, num_rel=4,
    )
    pool = pd.DataFrame({
        "event_id": ["event-target"],
        "primary_obs_id": ["obs-target"],
        "t": [SCORING_DAY + pd.Timedelta(hours=6)],
    })
    production = _score_pool(
        model, pool, {"obs-target": "target"}, edges, node_ids,
        node_feat, caught_times, {person_id: i for i, person_id in enumerate(node_ids)},
        num_rel=4,
    )
    return engine, production


def test_snapshot_excludes_edges_and_catches_at_or_after_day_start():
    engine, _ = _explanation_fixture()
    snapshot = engine.snapshot(SCORING_DAY)
    assert "at-boundary" not in set(snapshot.active_edges.source_row_id)
    assert "before" in set(snapshot.active_edges.source_row_id)
    assert snapshot.caught_before_snapshot == frozenset({"hop1"})


def test_prepool_component_mean_matches_production_probability():
    engine, production = _explanation_fixture()
    snapshot = engine.snapshot(SCORING_DAY)
    target_index = engine.person_index["target"]
    np.testing.assert_allclose(snapshot.probabilities[target_index], production[0], rtol=1e-6)
    members = np.flatnonzero(
        snapshot.component_roots == snapshot.component_roots[target_index]
    )
    torch.testing.assert_close(
        snapshot.pooled_logits[target_index],
        snapshot.prepool_logits[members].mean(),
    )


def test_duplicate_tensor_edges_have_complete_provenance():
    edges = pd.DataFrame({
        "source_row_id": ["row-a", "row-b"],
        "u": ["p1", "p1"], "v": ["p2", "p2"], "rel": [0, 1],
    })
    edge_index, edge_type, source_rows = gm._edge_index_typed_with_provenance(
        edges, {"p1": 0, "p2": 1}
    )
    assert edge_index.shape[1] == edge_type.shape[0] == source_rows.shape[0]
    assert sorted(source_rows.tolist()) == ["row-a", "row-a", "row-b", "row-b"]


def test_community_contains_every_pooled_and_two_hop_node():
    engine, _ = _explanation_fixture()
    community = engine.community("target", SCORING_DAY)
    assert community["complete"] is True
    assert set(community["nodes_by_id"]) == {
        "target", "poolmate", "hop1", "hop2", "future"
    }
    assert set(community["base_source_row_ids"]) == {
        "before", "cot", "res", "plate"
    }
```

- [ ] **Step 2: Run focused tests and verify missing API failures**

```bash
rtk .venv/bin/python -m pytest -q tests/test_sage_explainer.py tests/test_df_graphmodel_rgcn.py -k 'snapshot or provenance or community or component_mean'
```

Expected: imports or attribute lookups fail for the new provenance/snapshot APIs.

- [ ] **Step 3: Add provenance and named feature helpers**

```python
def _stable_digest(*parts) -> str:
    value = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _add_edge_provenance(edges: pd.DataFrame) -> pd.DataFrame:
    work = edges.reset_index(drop=True).copy()
    keys = ["u", "v", "avail_time", "edge_type"]
    work["_occurrence"] = work.groupby(keys, dropna=False).cumcount()
    work["source_row_id"] = [
        "edge:" + _stable_digest(u, v, available_time.isoformat(), edge_type, occurrence)
        for u, v, available_time, edge_type, occurrence
        in work[[*keys, "_occurrence"]].itertuples(index=False, name=None)
    ]
    work["canonical_pair_group_id"] = [
        "pair:" + _stable_digest(*sorted((str(u), str(v))), edge_type)
        for u, v, edge_type
        in work[["u", "v", "edge_type"]].itertuples(index=False, name=None)
    ]
    return work.drop(columns="_occurrence")


def _edge_index_typed_with_provenance(edges, index):
    if len(edges) == 0:
        empty_index = torch.zeros((2, 0), dtype=torch.long)
        return (
            empty_index,
            torch.zeros((0,), dtype=torch.long),
            np.zeros(0, dtype=object),
        )
    if "source_row_id" not in edges:
        raise ValueError("typed edges require immutable source_row_id provenance")
    u = edges["u"].map(index).to_numpy(dtype=int)
    v = edges["v"].map(index).to_numpy(dtype=int)
    relation = edges["rel"].to_numpy(dtype=int)
    source_rows = edges["source_row_id"].astype(str).to_numpy(dtype=object)
    edge_index = np.stack([np.concatenate([u, v]), np.concatenate([v, u])])
    edge_type = np.concatenate([relation, relation])
    provenance = np.concatenate([source_rows, source_rows])
    return (
        torch.tensor(edge_index, dtype=torch.long),
        torch.tensor(edge_type, dtype=torch.long),
        provenance,
    )


def _edge_index_typed(edges, index):
    edge_index, edge_type, _ = _edge_index_typed_with_provenance(edges, index)
    return edge_index, edge_type


def caught_feature_names(num_rel):
    relation_names = [name for name, rel in sorted(REL_PLATE.items(), key=lambda item: item[1])]
    if len(relation_names) != num_rel:
        raise ValueError("relation feature names do not match num_rel")
    return ("bias", *[f"degree_{name.lower()}" for name in relation_names],
            "log1p_cotravel_component_size", "log1p_households_spanned",
            "caught_before_snapshot")
```

Call `_add_edge_provenance()` in `build_person_graph_typed()` after invalid times and relations are filtered but before returning. Return the extra `edge_type`, `source_row_id`, and `canonical_pair_group_id` columns; existing consumers continue selecting `u`, `v`, `avail_time`, and `rel` by name. Add `import hashlib` to `gnn/graphmodel_rgcn.py`.

- [ ] **Step 4: Extract one shared production snapshot-input helper**

Add `from dataclasses import dataclass` and import `_edge_index_typed_with_provenance` from `gnn.graphmodel_rgcn`. Add this immutable helper record and function to `gnn/learned_cell.py`, then make `_score_pool()` call it so scoring and explanation snapshots cannot drift:

```python
@dataclass(frozen=True)
class DaySnapshotInputs:
    scoring_day: pd.Timestamp
    active_edges: pd.DataFrame
    x: torch.Tensor
    edge_index: torch.Tensor
    edge_type: torch.Tensor
    tensor_edge_source_row_ids: np.ndarray
    component_roots: np.ndarray
    caught_before_snapshot: frozenset[str]


def build_day_snapshot_inputs(
    scoring_day, edges_typed, node_ids, node_feat, caught_time, index, *, num_rel
) -> DaySnapshotInputs:
    day = pd.to_datetime(scoring_day, utc=True, errors="raise").floor("D")
    active = edges_typed.loc[edges_typed["avail_time"] < day].copy()
    x = _asof_x_caught(
        node_ids, node_feat, active, caught_time, day, num_rel=num_rel
    )
    edge_index, edge_type, provenance = _edge_index_typed_with_provenance(
        active, index
    )
    roots = _component_roots(node_ids, active, day)
    caught = frozenset(
        person_id for person_id, available_time in caught_time.items()
        if pd.notna(available_time) and available_time < day
    )
    return DaySnapshotInputs(
        day, active, x, edge_index, edge_type, provenance, roots, caught
    )


@dataclass(frozen=True)
class DaySnapshot:
    scoring_day: pd.Timestamp
    active_edges: pd.DataFrame
    x: torch.Tensor
    edge_index: torch.Tensor
    edge_type: torch.Tensor
    tensor_edge_source_row_ids: np.ndarray
    component_roots: np.ndarray
    prepool_embeddings: torch.Tensor
    prepool_logits: torch.Tensor
    pooled_logits: torch.Tensor
    probabilities: np.ndarray
    caught_before_snapshot: frozenset[str]


class Seed0ExplanationEngine:
    def __init__(
        self, *, model, edges_typed, node_ids, node_feat, caught_time, num_rel,
        rank_reference=None,
    ):
        self.model = model.eval()
        self.edges_typed = edges_typed.copy()
        self.node_ids = tuple(node_ids)
        self.node_feat = node_feat
        self.caught_time = dict(caught_time)
        self.num_rel = int(num_rel)
        self.person_index = {person_id: i for i, person_id in enumerate(node_ids)}
        self.rank_reference = rank_reference
        self._snapshot_cache = {}
        self._counterfactual_cache = {}

    def relationship_categories(self, person_id, scoring_day):
        snapshot = self.snapshot(scoring_day)
        incident = snapshot.active_edges[
            (snapshot.active_edges.u == person_id)
            | (snapshot.active_edges.v == person_id)
        ]
        return tuple(sorted(set(incident.edge_type.astype(str))))

    def community(self, person_id, scoring_day):
        return build_complete_community(self, person_id, scoring_day)

    def explain_case(self, case):
        return compose_case_explanation(self, case)

    def score_counterfactual(self, context, factor):
        return score_grouped_counterfactual(self, context, factor)

    def snapshot(self, scoring_day) -> DaySnapshot:
        day = pd.to_datetime(scoring_day, utc=True, errors="raise").floor("D")
        if day in self._snapshot_cache:
            return self._snapshot_cache[day]
        inputs = build_day_snapshot_inputs(
            day, self.edges_typed, self.node_ids, self.node_feat,
            self.caught_time, self.person_index, num_rel=self.num_rel,
        )
        with torch.no_grad():
            embeddings = self.model.enc(
                inputs.x, inputs.edge_index, edge_type=inputs.edge_type
            )
            prepool_logits = self.model.head(embeddings).squeeze(-1)
            pooled_embeddings = _pool_by_roots_torch(
                embeddings, inputs.component_roots
            )
            pooled_logits = self.model.head(pooled_embeddings).squeeze(-1)
            probabilities = torch.sigmoid(pooled_logits).cpu().numpy()
        snapshot = DaySnapshot(
            scoring_day=day,
            active_edges=inputs.active_edges,
            x=inputs.x,
            edge_index=inputs.edge_index,
            edge_type=inputs.edge_type,
            tensor_edge_source_row_ids=inputs.tensor_edge_source_row_ids,
            component_roots=inputs.component_roots,
            prepool_embeddings=embeddings,
            prepool_logits=prepool_logits,
            pooled_logits=pooled_logits,
            probabilities=probabilities,
            caught_before_snapshot=inputs.caught_before_snapshot,
        )
        self._snapshot_cache[day] = snapshot
        return snapshot
```

In `_score_pool()`, replace its per-day body with:

```python
inputs = build_day_snapshot_inputs(
    t, edges_typed, node_ids, node_feat, caught_time, index, num_rel=num_rel
)
z = model.enc(inputs.x, inputs.edge_index, edge_type=inputs.edge_type)
zp = _pool_by_roots_torch(z, inputs.component_roots)
prob = torch.sigmoid(model.head(zp).squeeze(-1)).numpy()
```

Implement `Seed0ExplanationEngine.community()` with this exact membership rule: start with every node sharing the target's `component_root`; perform two breadth-first expansions over `snapshot.edge_index` from that entire set; include every active source row whose endpoints are both included; collapse display duplicates only by `(canonical_pair_group_id, rel)` while preserving every `source_row_id` and availability timestamp in an `observations` array. Generate deterministic normalized node coordinates with `networkx.spring_layout(graph, seed=0)` followed by min/max normalization to `[0, 1]`. Return:

```python
{
    "complete": True,
    "nodes": [{"node_id": person_id, "x": x, "y": y,
               "pooled_member": bool_value, "caught_before_snapshot": bool_value,
               "caught_label_available_time": timestamp_or_none}],
    "nodes_by_id": {person_id: node_record},
    "edges": [{"edge_id": group_id, "u": u, "v": v, "rel": rel,
               "edge_type": edge_type, "source_row_ids": source_ids,
               "message_hop": minimum_hop_from_any_pooled_member,
               "observations": [{"source_row_id": source_id,
                                  "available_time": timestamp}]}],
    "base_source_row_ids": sorted_source_ids,
    "provenance_expansions": [],
}
```

Implement the membership/collapse/layout function exactly as follows (add `import networkx as nx`):

```python
def build_complete_community(engine, target_person_id, scoring_day):
    snapshot = engine.snapshot(scoring_day)
    target_index = engine.person_index[target_person_id]
    target_root = snapshot.component_roots[target_index]
    pooled_indices = set(np.flatnonzero(snapshot.component_roots == target_root).tolist())
    adjacency = {index: set() for index in range(len(engine.node_ids))}
    for source, target in snapshot.edge_index.t().cpu().numpy():
        adjacency[int(source)].add(int(target))
        adjacency[int(target)].add(int(source))
    distances = {index: 0 for index in pooled_indices}
    frontier = set(pooled_indices)
    for hop in (1, 2):
        next_frontier = {
            neighbor for index in frontier for neighbor in adjacency[index]
            if neighbor not in distances
        }
        distances.update({index: hop for index in next_frontier})
        frontier = next_frontier
    included_people = {engine.node_ids[index] for index in distances}
    internal = snapshot.active_edges[
        snapshot.active_edges.u.isin(included_people)
        & snapshot.active_edges.v.isin(included_people)
    ]
    graph = nx.Graph()
    graph.add_nodes_from(sorted(included_people))
    graph.add_edges_from(internal[["u", "v"]].itertuples(index=False, name=None))
    raw_positions = nx.spring_layout(graph, seed=0) if len(graph) > 1 else {
        next(iter(graph.nodes)): np.array([0.5, 0.5])
    }
    values = np.array(list(raw_positions.values()), dtype=float)
    minimum, maximum = values.min(axis=0), values.max(axis=0)
    span = np.where(maximum > minimum, maximum - minimum, 1.0)
    positions = {
        person_id: (np.asarray(point) - minimum) / span
        for person_id, point in raw_positions.items()
    }
    nodes = []
    for person_id in sorted(included_people):
        index = engine.person_index[person_id]
        caught_available = engine.caught_time.get(person_id)
        nodes.append({
            "node_id": person_id,
            "x": float(positions[person_id][0]),
            "y": float(positions[person_id][1]),
            "target": person_id == target_person_id,
            "pooled_member": index in pooled_indices,
            "caught_before_snapshot": person_id in snapshot.caught_before_snapshot,
            "caught_label_available_time": (
                caught_available.isoformat()
                if person_id in snapshot.caught_before_snapshot else None
            ),
        })
    nodes_by_id = {node["node_id"]: node for node in nodes}
    edges = []
    for (group_id, relation), frame in internal.groupby(
        ["canonical_pair_group_id", "rel"], sort=True
    ):
        u, v = sorted((str(frame.iloc[0].u), str(frame.iloc[0].v)))
        source_ids = sorted(frame.source_row_id.astype(str))
        edges.append({
            "edge_id": f"{group_id}:rel:{int(relation)}",
            "u": u, "v": v, "rel": int(relation),
            "edge_type": str(frame.iloc[0].edge_type),
            "source_row_ids": source_ids,
            "message_hop": max(
                distances[engine.person_index[u]], distances[engine.person_index[v]]
            ),
            "observations": [{
                "source_row_id": str(row.source_row_id),
                "available_time": pd.Timestamp(row.avail_time).isoformat(),
            } for row in frame.itertuples()],
        })
    return {
        "complete": True, "nodes": nodes, "nodes_by_id": nodes_by_id,
        "edges": edges,
        "base_source_row_ids": sorted(internal.source_row_id.astype(str)),
        "provenance_expansions": [],
    }
```

Provenance expansions for aggregate features use the same node/edge records but live only in `provenance_expansions`; the UI labels them “outside message community” and never treats them as GraphSAGE message paths.

- [ ] **Step 5: Run parity and leakage tests**

```bash
rtk .venv/bin/python -m pytest -q tests/test_sage_explainer.py tests/test_df_graphmodel_rgcn.py tests/test_run_demo_smoke.py
```

Expected: all snapshot probabilities match production and exact-time/future evidence is excluded.

- [ ] **Step 6: Commit the shared snapshot seam**

```bash
rtk git add gnn/graphmodel_rgcn.py gnn/learned_cell.py gnn/sage_explainer.py tests/test_sage_explainer.py tests/test_df_graphmodel_rgcn.py
rtk git commit -m "feat: expose exact GraphSAGE explanation snapshots"
```

---

### Task 6: Add exact grouped counterfactual attribution

**Files:**

- Modify: `gnn/sage_explainer.py`
- Modify: `tests/test_sage_explainer.py`

- [ ] **Step 1: Write failing counterfactual and serialization tests**

```python
def test_cotravel_ablation_rebuilds_features_and_pooling():
    engine, _ = _explanation_fixture()
    reference = build_rank_reference(
        pd.DataFrame({"event_id": ["target-a", "target-b", "peer"]}),
        np.array([0.40, 0.40, 0.60]),
        np.array([0.80, 0.80, 0.30]),
        0.75,
    )
    engine.rank_reference = reference
    case = CounterfactualContext(
        person_id="target", row_index=0, scoring_day=SCORING_DAY,
        same_day_person_row_indices=(0, 1),
        candidate_row_indices=(0, 1, 2), original_hybrid_rank=1,
    )
    factor = AblationSpec(
        factor_id="cotravel:target:poolmate",
        kind="cotravel_pool",
        edge_source_row_ids=("cot",),
    )
    result = engine.score_counterfactual(case, factor)
    assert result["original_component_size"] == 2
    assert result["ablated_component_size"] == 1
    assert result["features_rebuilt"] is True
    assert result["pooling_rebuilt"] is True


def test_counterfactual_rank_updates_all_same_day_identity_rows_and_freezes_peers():
    reference = build_rank_reference(
        pd.DataFrame({"event_id": ["target-a", "target-b", "peer-a", "peer-b"]}),
        np.array([0.40, 0.40, 0.60, 0.20]),
        np.array([0.80, 0.80, 0.50, 0.10]),
        0.75,
    )
    result = frozen_peer_rank(
        reference,
        anchor_row_index=0,
        affected_row_indices=(0, 1),
        ablated_seed0_probability=0.20,
        candidate_row_indices=(0, 1, 2, 3),
        original_hybrid_rank=1,
    )
    assert result["updated_row_indices"] == [0, 1]
    assert result["unchanged_peer_row_indices"] == [2, 3]
    assert result["hybrid_rank_delta"] == (
        result["ablated_hybrid_rank"] - result["original_hybrid_rank"]
    )


@pytest.mark.parametrize(
    "forbidden",
    ["hidden", "organization_id", "community_propensity", "lifetime_seizures"],
)
def test_serialization_rejects_forbidden_hidden_and_lifetime_fields(forbidden):
    with pytest.raises(ValueError, match="forbidden explanation field"):
        validate_explanation_payload({forbidden: True})
```

- [ ] **Step 2: Run the tests and verify the new methods are missing**

```bash
rtk .venv/bin/python -m pytest -q tests/test_sage_explainer.py -k 'counterfactual or serialization or ablation'
```

Expected: failures name `AblationSpec`, `score_counterfactual`, and `validate_explanation_payload`.

- [ ] **Step 3: Implement factor groups, cache keys, and frozen-peer rank effects**

```python
@dataclass(frozen=True)
class AblationSpec:
    factor_id: str
    kind: str
    edge_source_row_ids: tuple[str, ...] = ()
    caught_person_ids: tuple[str, ...] = ()
    provenance_node_ids: tuple[str, ...] = ()

    def __post_init__(self):
        allowed = {
            "pair_relation", "caught_flag", "relation_star",
            "structural_provenance", "cotravel_pool",
        }
        if self.kind not in allowed:
            raise ValueError(f"unsupported ablation kind: {self.kind}")


@dataclass(frozen=True)
class CounterfactualContext:
    person_id: str
    row_index: int
    scoring_day: pd.Timestamp
    same_day_person_row_indices: tuple[int, ...]
    candidate_row_indices: tuple[int, ...]
    original_hybrid_rank: int


def frozen_peer_rank(
    reference: FrozenRankReference,
    *,
    anchor_row_index: int,
    affected_row_indices: tuple[int, ...],
    ablated_seed0_probability: float,
    candidate_row_indices: tuple[int, ...],
    original_hybrid_rank: int,
) -> dict[str, object]:
    gnn_raw = reference.seed0_gnn_raw.copy()
    gnn_raw[list(affected_row_indices)] = ablated_seed0_probability
    gnn_percentile = rankdata(gnn_raw, method="average") / len(gnn_raw)
    hybrid_raw = (
        reference.blend_weight * gnn_percentile
        + (1.0 - reference.blend_weight) * reference.baseline_percentile
    )
    hybrid_selection = _selection_tiebreak(hybrid_raw)
    ordered = sorted(
        candidate_row_indices,
        key=lambda index: (-hybrid_selection[index], index),
    )
    ablated_rank = ordered.index(anchor_row_index) + 1
    unchanged = sorted(set(candidate_row_indices) - set(affected_row_indices))
    return {
        "percentile_reference_id": reference.percentile_reference_id,
        "ablated_gnn_percentile": float(gnn_percentile[anchor_row_index]),
        "original_hybrid_rank": int(original_hybrid_rank),
        "ablated_hybrid_rank": ablated_rank,
        "hybrid_rank_delta": ablated_rank - int(original_hybrid_rank),
        "updated_row_indices": list(affected_row_indices),
        "unchanged_peer_row_indices": unchanged,
    }
```

Implement `build_ablation_specs(snapshot, person_id, community)` as follows:

```python
def build_ablation_specs(snapshot, person_id, community):
    internal = snapshot.active_edges[
        snapshot.active_edges["source_row_id"].isin(community["base_source_row_ids"])
    ]
    specs = []
    for group_id, frame in internal.groupby("canonical_pair_group_id", sort=True):
        specs.append(AblationSpec(
            factor_id=f"pair:{group_id}", kind="pair_relation",
            edge_source_row_ids=tuple(sorted(frame.source_row_id.astype(str))),
        ))
    for relation, frame in internal[
        (internal.u == person_id) | (internal.v == person_id)
    ].groupby("edge_type", sort=True):
        specs.append(AblationSpec(
            factor_id=f"relation-star:{person_id}:{relation}", kind="relation_star",
            edge_source_row_ids=tuple(sorted(frame.source_row_id.astype(str))),
        ))
    for caught_person_id in sorted(snapshot.caught_before_snapshot & set(community["nodes_by_id"])):
        specs.append(AblationSpec(
            factor_id=f"caught:{caught_person_id}", kind="caught_flag",
            caught_person_ids=(caught_person_id,),
        ))
    visible_people = set(community["nodes_by_id"])
    structural_rows = structural_provenance_rows(snapshot.active_edges, visible_people)
    if len(structural_rows):
        provenance_people = (
            set(structural_rows.u.astype(str)) | set(structural_rows.v.astype(str))
        ) - visible_people
        specs.append(AblationSpec(
            factor_id=f"structural:{person_id}", kind="structural_provenance",
            edge_source_row_ids=tuple(sorted(structural_rows.source_row_id.astype(str))),
            provenance_node_ids=tuple(sorted(provenance_people)),
        ))
    cotravel = internal[internal.edge_type == "COTRAVEL"]
    for group_id, frame in cotravel.groupby("canonical_pair_group_id", sort=True):
        specs.append(AblationSpec(
            factor_id=f"cotravel-pool:{group_id}", kind="cotravel_pool",
            edge_source_row_ids=tuple(sorted(frame.source_row_id.astype(str))),
        ))
    return specs


def structural_provenance_rows(active_edges, visible_people):
    cotravel = active_edges[active_edges.edge_type == "COTRAVEL"]
    residence = active_edges[active_edges.edge_type == "RESIDENCE"]
    cot_graph = nx.Graph()
    cot_graph.add_edges_from(cotravel[["u", "v"]].itertuples(index=False, name=None))
    cot_people = set(visible_people)
    for person_id in visible_people:
        if person_id in cot_graph:
            cot_people.update(nx.node_connected_component(cot_graph, person_id))
    residence_graph = nx.Graph()
    residence_graph.add_edges_from(
        residence[["u", "v"]].itertuples(index=False, name=None)
    )
    residence_people = set(cot_people)
    for person_id in cot_people:
        if person_id in residence_graph:
            residence_people.update(
                nx.node_connected_component(residence_graph, person_id)
            )
    cot_rows = cotravel[cotravel.u.isin(cot_people) & cotravel.v.isin(cot_people)]
    residence_rows = residence[
        residence.u.isin(residence_people) & residence.v.isin(residence_people)
    ]
    return pd.concat([cot_rows, residence_rows], ignore_index=False)


def score_grouped_counterfactual(engine, context, factor):
    if engine.rank_reference is None:
        raise ValueError("counterfactual scoring requires a frozen rank reference")
    fingerprint = hashlib.sha256(json.dumps(asdict(factor), sort_keys=True).encode()).hexdigest()
    cache_key = (context.scoring_day.isoformat(), context.person_id, fingerprint)
    if cache_key in engine._counterfactual_cache:
        return engine._counterfactual_cache[cache_key]
    original = engine.snapshot(context.scoring_day)
    modified_edges = engine.edges_typed[
        ~engine.edges_typed.source_row_id.isin(factor.edge_source_row_ids)
    ].copy()
    modified_caught = {
        person_id: available_time
        for person_id, available_time in engine.caught_time.items()
        if person_id not in factor.caught_person_ids
    }
    inputs = build_day_snapshot_inputs(
        context.scoring_day, modified_edges, engine.node_ids, engine.node_feat,
        modified_caught, engine.person_index, num_rel=engine.num_rel,
    )
    with torch.no_grad():
        embeddings = engine.model.enc(
            inputs.x, inputs.edge_index, edge_type=inputs.edge_type
        )
        pooled = _pool_by_roots_torch(embeddings, inputs.component_roots)
        probabilities = torch.sigmoid(engine.model.head(pooled).squeeze(-1)).cpu().numpy()
    target_index = engine.person_index[context.person_id]
    rank_effect = frozen_peer_rank(
        engine.rank_reference,
        anchor_row_index=context.row_index,
        affected_row_indices=context.same_day_person_row_indices,
        ablated_seed0_probability=float(probabilities[target_index]),
        candidate_row_indices=context.candidate_row_indices,
        original_hybrid_rank=context.original_hybrid_rank,
    )
    original_root = original.component_roots[target_index]
    ablated_root = inputs.component_roots[target_index]
    result = {
        **rank_effect,
        "factor_id": factor.factor_id,
        "original_seed0_probability": float(original.probabilities[target_index]),
        "ablated_seed0_probability": float(probabilities[target_index]),
        "original_component_size": int((original.component_roots == original_root).sum()),
        "ablated_component_size": int((inputs.component_roots == ablated_root).sum()),
        "features_rebuilt": True,
        "pooling_rebuilt": True,
    }
    validate_explanation_payload(result)
    engine._counterfactual_cache[cache_key] = result
    return result
```

Add `import hashlib`, `import json`, and `from dataclasses import asdict`. This path removes the complete immutable `source_row_id` group, optionally removes listed caught timestamps, rebuilds relation degrees, structural features, component roots, pooling, the target's seed-0 probability, and frozen-peer Hybrid rank. It updates every `same_day_person_row_indices` entry and caches only after forbidden-field validation succeeds.

Add the stability classifier. The UI reads this serialized field and never infers stability itself.

```python
def classify_factor_stability(
    counterfactual, restart_selection_frequency, restart_iqr
):
    effect = int(counterfactual["hybrid_rank_delta"])
    if effect < 0:
        return "countervailing"
    if effect > 0 and restart_selection_frequency >= (2 / 3) and restart_iqr <= 0.25:
        return "stable"
    return "unstable"
```

- [ ] **Step 4: Add recursive fail-closed field validation**

```python
FORBIDDEN_EXPLANATION_FIELDS = frozenset({
    "hidden", "false_negative_flag", "organization_id", "org_id",
    "ground_truth_community", "community_propensity", "lifetime_seizures",
    "lifetime_arrests", "future_caught", "future_edges",
})


def validate_explanation_payload(value, path="root"):
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).casefold() in FORBIDDEN_EXPLANATION_FIELDS:
                raise ValueError(f"forbidden explanation field at {path}.{key}")
            validate_explanation_payload(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            validate_explanation_payload(item, f"{path}[{index}]")
    return value
```

- [ ] **Step 5: Run attribution tests**

```bash
rtk .venv/bin/python -m pytest -q tests/test_sage_explainer.py -k 'counterfactual or serialization or ablation'
```

Expected: every grouped ablation rebuilds the full seed-0 path and reports signed rank effects against frozen peers.

- [ ] **Step 6: Commit counterfactual attribution**

```bash
rtk git add gnn/sage_explainer.py tests/test_sage_explainer.py
rtk git commit -m "feat: add exact seed-zero counterfactual attribution"
```

---

### Task 7: Add single-seed GNNExplainer message flow

**Files:**

- Modify: `gnn/sage_explainer.py`
- Modify: `tests/test_sage_explainer.py`

- [ ] **Step 1: Write failing wrapper and restart aggregation tests**

```python
def test_two_hop_wrapper_matches_full_graph_member_logit():
    engine, _ = _explanation_fixture()
    person_id = "target"
    snapshot = engine.snapshot(SCORING_DAY)
    local = member_subgraph(engine, person_id, SCORING_DAY)
    actual = PrePoolSAGELogitWrapper(engine.model)(
        local.x, local.edge_index
    )[local.target_index]
    expected = snapshot.prepool_logits[engine.person_index[person_id]]
    torch.testing.assert_close(actual, expected, rtol=1e-6, atol=1e-6)


def test_restart_aggregation_reports_median_iqr_and_top_frequency():
    masks = [
        np.array([0.9, 0.2, 0.1]),
        np.array([0.8, 0.3, 0.1]),
        np.array([0.7, 0.4, 0.1]),
    ]
    aggregate = aggregate_restart_masks(masks, top_fraction=1 / 3)
    np.testing.assert_allclose(aggregate["median"], [0.8, 0.3, 0.1])
    np.testing.assert_allclose(aggregate["selection_frequency"], [1.0, 0.0, 0.0])
    assert aggregate["restart_count"] == 3


def test_empty_edge_masks_are_explicit_not_errors():
    aggregate = aggregate_restart_masks([np.zeros(0), np.zeros(0), np.zeros(0)])
    assert aggregate["median"].size == 0
    assert aggregate["selection_frequency"].size == 0
    assert aggregate["status"] == "no-message-edges"


def test_faithfulness_controls_match_relation_and_degree_bins():
    edge_records = [
        {"edge_id": "e1", "relation": "COTRAVEL", "degree_bin": "2-4"},
        {"edge_id": "e2", "relation": "COTRAVEL", "degree_bin": "2-4"},
        {"edge_id": "e3", "relation": "RESIDENCE", "degree_bin": "5-8"},
        {"edge_id": "e4", "relation": "RESIDENCE", "degree_bin": "5-8"},
    ]
    controls = matched_random_controls(
        edge_records, selected_edge_ids=("e1", "e3"), seed=0
    )
    assert controls == ("e2", "e4")
```

- [ ] **Step 2: Run the focused tests and verify missing wrapper failures**

```bash
rtk .venv/bin/python -m pytest -q tests/test_sage_explainer.py -k 'wrapper or restart or message_flow'
```

Expected: failures name `PrePoolSAGELogitWrapper` or `aggregate_restart_masks`.

- [ ] **Step 3: Implement the exact pre-pool wrapper and PyG configuration**

```python
from torch_geometric.explain import Explainer, GNNExplainer, ModelConfig
from torch_geometric.utils import k_hop_subgraph


class PrePoolSAGELogitWrapper(torch.nn.Module):
    def __init__(self, model: torch.nn.Module):
        super().__init__()
        self.model = model

    def forward(self, x, edge_index):
        embeddings = self.model.enc(x, edge_index)
        return self.model.head(embeddings).squeeze(-1)


@dataclass(frozen=True)
class MemberSubgraph:
    x: torch.Tensor
    edge_index: torch.Tensor
    target_index: int
    original_node_indices: np.ndarray
    tensor_edge_source_row_ids: np.ndarray


def member_subgraph(engine, person_id, scoring_day):
    snapshot = engine.snapshot(scoring_day)
    target = engine.person_index[person_id]
    subset, edge_index, mapping, edge_mask = k_hop_subgraph(
        target, 2, snapshot.edge_index, relabel_nodes=True,
        num_nodes=len(engine.node_ids),
    )
    return MemberSubgraph(
        x=snapshot.x[subset],
        edge_index=edge_index,
        target_index=int(mapping.item()),
        original_node_indices=subset.cpu().numpy(),
        tensor_edge_source_row_ids=snapshot.tensor_edge_source_row_ids[
            edge_mask.cpu().numpy()
        ],
    )


def make_gnn_explainer(wrapper, epochs=150):
    return Explainer(
        model=wrapper,
        algorithm=GNNExplainer(epochs=epochs),
        explanation_type="model",
        node_mask_type="attributes",
        edge_mask_type="object",
        model_config=ModelConfig(
            mode="binary_classification",
            task_level="node",
            return_type="raw",
        ),
    )


def run_member_explanation(engine, person_id, scoring_day, *, restart_seeds=(0, 1, 2)):
    local = member_subgraph(engine, person_id, scoring_day)
    wrapper = PrePoolSAGELogitWrapper(engine.model)
    with torch.no_grad():
        local_logit = wrapper(local.x, local.edge_index)[local.target_index]
        full_logit = engine.snapshot(scoring_day).prepool_logits[
            engine.person_index[person_id]
        ]
    torch.testing.assert_close(local_logit, full_logit, rtol=1e-6, atol=1e-6)
    if local.edge_index.shape[1] == 0:
        return {"edge_masks": [np.zeros(0) for _ in restart_seeds],
                "feature_masks": [], "status": "no-message-edges"}
    edge_masks, feature_masks = [], []
    for restart_seed in restart_seeds:
        with torch.random.fork_rng():
            torch.manual_seed(restart_seed)
            explanation = make_gnn_explainer(wrapper)(
                x=local.x,
                edge_index=local.edge_index,
                index=local.target_index,
            )
        edge_masks.append(explanation.edge_mask.detach().cpu().numpy())
        feature_mask = explanation.node_mask.detach().cpu().numpy()
        feature_masks.append(
            feature_mask.mean(axis=0) if feature_mask.ndim == 2 else feature_mask
        )
    return {"edge_masks": edge_masks, "feature_masks": feature_masks, "status": "ok"}
```

For each pooled member, extract the exact two-hop subgraph, prove pre-pool logit parity, run `run_member_explanation()`, map local directed masks through immutable tensor-edge provenance, normalize each restart, weight member masks by `1 / component_size`, and only then collapse display duplicates. Separately assert `mean(member prepool_logits) == target pooled_logit`; this is the exact linear-head/component-mean decomposition. Aggregate edge and feature masks independently. GNNExplainer masks are unsigned: serialize `signed_effect_source: "counterfactual_only"` and never describe an explainer mask as positive or negative.

Serialize the four UI stages from the complete base graph; stages change emphasis only and never membership:

```python
def build_flow_stages(community):
    edges = community["edges"]
    first_hop = [edge["edge_id"] for edge in edges if edge["message_hop"] <= 1]
    second_hop = [edge["edge_id"] for edge in edges if edge["message_hop"] <= 2]
    pooling = [
        edge["edge_id"] for edge in edges
        if edge["edge_type"] == "COTRAVEL"
        and community["nodes_by_id"][edge["u"]]["pooled_member"]
        and community["nodes_by_id"][edge["v"]]["pooled_member"]
    ]
    return [
        {"stage_id": "first_hop", "emphasized_edge_ids": sorted(first_hop)},
        {"stage_id": "second_hop", "emphasized_edge_ids": sorted(second_hop)},
        {"stage_id": "component_pool", "emphasized_edge_ids": sorted(pooling)},
        {"stage_id": "rank_fusion", "emphasized_edge_ids": []},
    ]
```

- [ ] **Step 4: Implement deterministic restart aggregation**

```python
def aggregate_restart_masks(masks, top_fraction=0.1):
    matrix = np.vstack([np.asarray(mask, dtype=float) for mask in masks])
    if matrix.ndim != 2 or matrix.shape[0] == 0:
        raise ValueError("at least one aligned explainer mask is required")
    if matrix.shape[1] == 0:
        empty = np.zeros(0, dtype=float)
        return {
            "median": empty, "q1": empty, "q3": empty,
            "selection_frequency": empty,
            "restart_count": matrix.shape[0],
            "top_factor_agreement": 0.0,
            "status": "no-message-edges",
        }
    normalized = matrix / np.maximum(matrix.max(axis=1, keepdims=True), 1e-12)
    top_count = max(1, int(np.ceil(normalized.shape[1] * top_fraction)))
    selected = np.zeros_like(normalized, dtype=bool)
    for row_index, row in enumerate(normalized):
        top = np.argsort(-row, kind="mergesort")[:top_count]
        selected[row_index, top] = True
    return {
        "median": np.median(normalized, axis=0),
        "q1": np.quantile(normalized, 0.25, axis=0),
        "q3": np.quantile(normalized, 0.75, axis=0),
        "selection_frequency": selected.mean(axis=0),
        "restart_count": normalized.shape[0],
        "top_factor_agreement": float(selected.mean(axis=0).max()),
        "status": "ok",
    }
```

- [ ] **Step 5: Implement relation/degree-matched faithfulness curves**

Add deterministic controls and a scorer-driven curve. Degree bins are `1`, `2-4`, `5-8`, and `9+`; a control must match both the selected edge's displayed relation and degree bin. If no unused exact match exists, record the unmatched edge and do not substitute a looser control.

```python
def matched_random_controls(edge_records, *, selected_edge_ids, seed):
    by_id = {record["edge_id"]: record for record in edge_records}
    selected = set(selected_edge_ids)
    rng = np.random.default_rng(seed)
    controls = []
    for edge_id in selected_edge_ids:
        source = by_id[edge_id]
        candidates = sorted(
            record["edge_id"] for record in edge_records
            if record["edge_id"] not in selected
            and record["edge_id"] not in controls
            and record["relation"] == source["relation"]
            and record["degree_bin"] == source["degree_bin"]
        )
        if candidates:
            controls.append(candidates[int(rng.integers(0, len(candidates)))])
    return tuple(controls)


def edge_removal_faithfulness(edge_records, importance_by_id, *, rescore, seed=0):
    ordered = sorted(
        edge_records,
        key=lambda record: (-importance_by_id.get(record["edge_id"], 0.0),
                            record["edge_id"]),
    )
    original = float(rescore(()))
    points = []
    for fraction in (0.10, 0.25, 0.50):
        count = max(1, int(np.ceil(len(ordered) * fraction))) if ordered else 0
        selected = tuple(record["edge_id"] for record in ordered[:count])
        controls = matched_random_controls(
            edge_records, selected_edge_ids=selected, seed=seed + count
        )
        points.append({
            "fraction": fraction,
            "selected_edge_ids": list(selected),
            "matched_control_edge_ids": list(controls),
            "top_edge_probability_drop": original - float(rescore(selected)),
            "matched_random_probability_drop": (
                original - float(rescore(controls)) if len(controls) == len(selected) else None
            ),
            "unmatched_control_count": len(selected) - len(controls),
        })
    return {"original_probability": original, "points": points}
```

Compose a case only from the shared snapshot, measured counterfactuals, and restart aggregates. Add `from collections import defaultdict` and this function:

```python
def compose_case_explanation(engine, case):
    snapshot = engine.snapshot(case.anchor.scoring_day)
    target_index = engine.person_index[case.person_id]
    community = engine.community(case.person_id, case.anchor.scoring_day)
    component_root = snapshot.component_roots[target_index]
    member_ids = [
        engine.node_ids[index] for index in np.flatnonzero(
            snapshot.component_roots == component_root
        )
    ]
    edge_ids = [edge["edge_id"] for edge in community["edges"]]
    source_to_edge = {
        source_row_id: edge["edge_id"]
        for edge in community["edges"] for source_row_id in edge["source_row_ids"]
    }
    restart_edge_values = [defaultdict(float) for _ in (0, 1, 2)]
    restart_feature_values = [None, None, None]
    for member_id in member_ids:
        member = run_member_explanation(engine, member_id, case.anchor.scoring_day)
        local = member_subgraph(engine, member_id, case.anchor.scoring_day)
        for restart_index, mask in enumerate(member["edge_masks"]):
            for source_row_id, value in zip(local.tensor_edge_source_row_ids, mask):
                display_edge_id = source_to_edge.get(str(source_row_id))
                if display_edge_id is not None:
                    restart_edge_values[restart_index][display_edge_id] += (
                        float(value) / len(member_ids)
                    )
        for restart_index, feature_mask in enumerate(member["feature_masks"]):
            value = np.asarray(feature_mask, dtype=float) / len(member_ids)
            restart_feature_values[restart_index] = (
                value if restart_feature_values[restart_index] is None
                else restart_feature_values[restart_index] + value
            )
    aligned_edge_masks = [
        np.array([values[edge_id] for edge_id in edge_ids], dtype=float)
        for values in restart_edge_values
    ]
    edge_aggregate = aggregate_restart_masks(aligned_edge_masks)
    feature_aggregate = aggregate_restart_masks(
        [value for value in restart_feature_values if value is not None]
    ) if any(value is not None for value in restart_feature_values) else {
        "median": np.zeros(snapshot.x.shape[1]), "q1": np.zeros(snapshot.x.shape[1]),
        "q3": np.zeros(snapshot.x.shape[1]),
        "selection_frequency": np.zeros(snapshot.x.shape[1]),
        "restart_count": 0, "top_factor_agreement": 0.0, "status": "no-features",
    }
    for index, edge in enumerate(community["edges"]):
        edge["explainer_median"] = float(edge_aggregate["median"][index])
        edge["explainer_q1"] = float(edge_aggregate["q1"][index])
        edge["explainer_q3"] = float(edge_aggregate["q3"][index])
        edge["selection_frequency"] = float(
            edge_aggregate["selection_frequency"][index]
        )
    context = CounterfactualContext(
        person_id=case.person_id, row_index=case.anchor.row_index,
        scoring_day=case.anchor.scoring_day,
        same_day_person_row_indices=case.same_day_person_row_indices,
        candidate_row_indices=case.hybrid_candidate_row_indices,
        original_hybrid_rank=case.hybrid_rank,
    )
    factors = []
    for spec in build_ablation_specs(snapshot, case.person_id, community):
        counterfactual = engine.score_counterfactual(context, spec)
        matching = [
            edge for edge in community["edges"]
            if set(edge["source_row_ids"]) & set(spec.edge_source_row_ids)
        ]
        frequency = max(
            (edge["selection_frequency"] for edge in matching), default=0.0
        )
        iqr = max(
            (edge["explainer_q3"] - edge["explainer_q1"] for edge in matching),
            default=1.0,
        )
        stability = classify_factor_stability(counterfactual, frequency, iqr)
        expansion = build_provenance_expansion(engine, snapshot, spec, community)
        if expansion is not None:
            community["provenance_expansions"].append(expansion)
        factors.append({
            "factor_id": spec.factor_id,
            "label": spec.factor_id.replace(":", " · "),
            "kind": spec.kind,
            "counterfactual": counterfactual,
            "restart": {"selection_frequency": frequency, "iqr": iqr},
            "stability": stability,
            "provenance_expansion_ids": (
                [expansion["expansion_id"]] if expansion is not None else []
            ),
        })
    importance_by_id = {
        edge["edge_id"]: edge["explainer_median"] for edge in community["edges"]
    }
    degrees = defaultdict(int)
    for edge in community["edges"]:
        degrees[edge["u"]] += 1; degrees[edge["v"]] += 1
    def degree_bin(value):
        return "1" if value <= 1 else "2-4" if value <= 4 else "5-8" if value <= 8 else "9+"
    faithfulness_edges = [{
        "edge_id": edge["edge_id"], "relation": edge["edge_type"],
        "degree_bin": degree_bin(max(degrees[edge["u"]], degrees[edge["v"]])),
    } for edge in community["edges"]]
    edge_by_id = {edge["edge_id"]: edge for edge in community["edges"]}
    def rescore(removed_edge_ids):
        source_ids = tuple(sorted({
            source_row_id for edge_id in removed_edge_ids
            for source_row_id in edge_by_id[edge_id]["source_row_ids"]
        }))
        if not source_ids:
            return float(snapshot.probabilities[target_index])
        spec = AblationSpec(
            factor_id="faithfulness:" + hashlib.sha256(
                "\n".join(source_ids).encode()
            ).hexdigest(),
            kind="pair_relation", edge_source_row_ids=source_ids,
        )
        return float(engine.score_counterfactual(context, spec)["ablated_seed0_probability"])
    faithfulness = edge_removal_faithfulness(
        faithfulness_edges, importance_by_id, rescore=rescore, seed=0
    )
    member_indices = [engine.person_index[person_id] for person_id in member_ids]
    pooled_parity = torch.isclose(
        snapshot.pooled_logits[target_index],
        snapshot.prepool_logits[member_indices].mean(), rtol=1e-6, atol=1e-6,
    ).item()
    probability_parity = np.isclose(
        snapshot.probabilities[target_index],
        engine.rank_reference.seed0_gnn_raw[case.anchor.row_index],
        rtol=1e-6, atol=1e-6,
    )
    stable_count = sum(factor["stability"] == "stable" for factor in factors)
    return {
        "case_id": f"case:{case.person_id}", "person_id": case.person_id,
        "event_id": case.anchor.event_id,
        "scoring_day": case.anchor.scoring_day.isoformat(),
        "decision_trace": dict(case.decision_trace),
        "factors": factors, "community": community,
        "flow_stages": build_flow_stages(community),
        "stable_factor_status": "stable" if stable_count else "unstable",
        "stability": {
            "stable_factor_count": stable_count,
            "edge_restart_aggregate": json_safe(edge_aggregate),
            "feature_restart_aggregate": json_safe(feature_aggregate),
            "signed_effect_source": "counterfactual_only",
        },
        "faithfulness": faithfulness,
        "parity": {
            "production_seed0_probability": bool(probability_parity),
            "pooled_logit_decomposition": bool(pooled_parity),
            "frozen_percentile": case.decision_trace["percentile_reference_id"]
                == engine.rank_reference.percentile_reference_id,
            "frozen_daily_hybrid_rank": case.decision_trace["seed0_hybrid_rank"]
                == case.hybrid_rank,
        },
        "evidence_boundary": {
            "snapshot": case.anchor.scoring_day.isoformat(),
            "edge_rule": "available_time < snapshot",
            "caught_rule": "label_available_time_utc < snapshot",
        },
    }
```

Add the two serializers used above. Expansion coordinates place outside nodes on a deterministic ring; this expansion is contextual provenance only, not message flow.

```python
def json_safe(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def build_provenance_expansion(engine, snapshot, spec, community):
    base_ids = set(community["base_source_row_ids"])
    outside_ids = set(spec.edge_source_row_ids) - base_ids
    frame = snapshot.active_edges[
        snapshot.active_edges.source_row_id.isin(outside_ids)
    ]
    if frame.empty:
        return None
    base_nodes = community["nodes_by_id"]
    people = sorted(set(frame.u.astype(str)) | set(frame.v.astype(str)))
    outside_people = [person_id for person_id in people if person_id not in base_nodes]
    ring_position = {
        person_id: (
            0.5 + 0.46 * np.cos(2 * np.pi * index / max(1, len(outside_people))),
            0.5 + 0.46 * np.sin(2 * np.pi * index / max(1, len(outside_people))),
        )
        for index, person_id in enumerate(outside_people)
    }
    nodes = []
    for person_id in people:
        if person_id in base_nodes:
            nodes.append(dict(base_nodes[person_id]))
            continue
        caught_available = engine.caught_time.get(person_id)
        nodes.append({
            "node_id": person_id,
            "x": float(ring_position[person_id][0]),
            "y": float(ring_position[person_id][1]),
            "target": False, "pooled_member": False,
            "caught_before_snapshot": person_id in snapshot.caught_before_snapshot,
            "caught_label_available_time": (
                caught_available.isoformat()
                if person_id in snapshot.caught_before_snapshot else None
            ),
        })
    edges = []
    for (group_id, relation), group in frame.groupby(
        ["canonical_pair_group_id", "rel"], sort=True
    ):
        u, v = sorted((str(group.iloc[0].u), str(group.iloc[0].v)))
        edges.append({
            "edge_id": f"provenance:{group_id}:rel:{int(relation)}",
            "u": u, "v": v, "rel": int(relation),
            "edge_type": str(group.iloc[0].edge_type),
            "source_row_ids": sorted(group.source_row_id.astype(str)),
            "observations": [{
                "source_row_id": str(row.source_row_id),
                "available_time": pd.Timestamp(row.avail_time).isoformat(),
            } for row in group.itertuples()],
        })
    return {
        "expansion_id": f"provenance:{spec.factor_id}",
        "label": "outside message community",
        "nodes": nodes, "edges": edges,
    }
```

- [ ] **Step 6: Run all explainer tests**

```bash
rtk .venv/bin/python -m pytest -q tests/test_sage_explainer.py
```

Expected: parity, complete-community, provenance, counterfactual, mask aggregation, and forbidden-field tests all pass.

- [ ] **Step 7: Commit the message-flow explainer**

```bash
rtk git add gnn/sage_explainer.py tests/test_sage_explainer.py
rtk git commit -m "feat: add seed-zero GNNExplainer message flow"
```

---

### Task 8: Add grounded local Gemma narratives

**Files:**

- Create: `gnn/explanation_narrative.py`
- Create: `tests/test_explanation_narrative.py`

- [ ] **Step 1: Write failing Ollama, validation, and fallback tests**

```python
import json
import os

import pytest


class FakeCompleted:
    def __init__(self, stdout, returncode=0):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


class FakeRunner:
    def __init__(self, *, list_stdout, run_stdout):
        self.list_stdout = list_stdout
        self.run_stdout = run_stdout
        self.commands = []

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        stdout = self.list_stdout if command[1] == "list" else self.run_stdout
        return FakeCompleted(stdout)


class FailingRunner:
    def __call__(self, command, **kwargs):
        raise FileNotFoundError("ollama unavailable")


def _fact_packet():
    return {
        "scope": {"observability_seed": 0, "gnn_arm": "sage"},
        "snapshot": "2025-01-02T00:00:00Z",
        "ranks": {"baseline": 18, "seed0_gnn": 4, "seed0_hybrid": 7},
        "factors_by_id": {
            "factor-1": {
                "label": "COTRAVEL with P-100",
                "relation": "COTRAVEL",
                "counterfactual": {
                    "original_hybrid_rank": 7,
                    "ablated_hybrid_rank": 43,
                    "hybrid_rank_delta": 36,
                },
                "restart": {"selection_frequency": 1.0, "iqr": 0.1},
            }
        },
        "caveats": [
            "This is seed-0 observability, not the three-seed headline result.",
            "GNNExplainer masks are unsigned; direction comes from counterfactual rank effects.",
        ],
    }


def test_generate_narrative_uses_installed_gemma_without_pull():
    runner = FakeRunner(
        list_stdout="NAME ID SIZE MODIFIED\ngemma4:12b abc 7.4 GB now\n",
        run_stdout=json.dumps({
            "summary": {
                "text": "In seed 0, graph evidence raised this case's Hybrid rank.",
                "source_refs": ["scope.observability_seed", "ranks.seed0_hybrid"],
            },
            "claims": [{
                "text": "Removing the co-travel factor moved Hybrid rank from 7 to 43.",
                "source_refs": [
                    "factors_by_id.factor-1.counterfactual.original_hybrid_rank",
                    "factors_by_id.factor-1.counterfactual.ablated_hybrid_rank",
                ],
            }],
        }),
    )
    result = generate_narrative(_fact_packet(), runner=runner)
    assert result["source"] == "llm"
    assert result["model"] == "gemma4:12b"
    assert all("pull" not in command for command in runner.commands)


def test_unavailable_ollama_uses_deterministic_template():
    result = generate_narrative(_fact_packet(), runner=FailingRunner())
    assert result["source"] == "deterministic_template"
    assert result["validated"] is True


@pytest.mark.parametrize("invented", ["P-99999", "rank 777", "caused the seizure"])
def test_validator_rejects_unsupported_claims(invented):
    candidate = {
        "summary": {
            "text": "In seed 0, this is the selected observability case.",
            "source_refs": ["scope.observability_seed"],
        },
        "claims": [{
            "text": invented,
            "source_refs": ["factors_by_id.factor-1.counterfactual.hybrid_rank_delta"],
        }],
    }
    with pytest.raises(ValueError, match="unsupported narrative claim"):
        validate_candidate(_fact_packet(), candidate)


@pytest.mark.skipif(
    os.environ.get("RUN_OLLAMA_INTEGRATION") != "1",
    reason="set RUN_OLLAMA_INTEGRATION=1 for the local Gemma smoke test",
)
def test_live_gemma_returns_a_validated_narrative():
    result = generate_narrative(_fact_packet())
    assert result["source"] == "llm"
    assert result["model"] == "gemma4:12b"
    assert result["validated"] is True
```

- [ ] **Step 2: Run the tests and verify the module is absent**

```bash
rtk .venv/bin/python -m pytest -q tests/test_explanation_narrative.py
```

Expected: collection fails because `gnn.explanation_narrative` does not exist.

- [ ] **Step 3: Implement a no-shell, no-auto-pull Ollama adapter**

```python
import json
import os
import re
import subprocess


MODEL_TAG = "gemma4:12b"
PROMPT_VERSION = "v1"


def _installed_model_names(stdout):
    lines = [line.split() for line in stdout.splitlines() if line.split()]
    return {columns[0] for columns in lines[1:] if columns}


def _run_local_gemma(prompt, *, runner, timeout_seconds):
    listed = runner(
        ["ollama", "list"], capture_output=True, text=True,
        timeout=min(timeout_seconds, 10), check=False,
    )
    if listed.returncode != 0 or MODEL_TAG not in _installed_model_names(listed.stdout):
        raise RuntimeError("local gemma4:12b is unavailable")
    completed = runner(
        [
            "ollama", "run", MODEL_TAG, "--format", "json",
            "--think=false", "--keepalive", "10m",
        ],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("local Gemma generation failed")
    return json.loads(completed.stdout)
```

Use injected `subprocess.run`; never use `shell=True`, `ollama pull`, an HTTP browser call, or an external provider.

- [ ] **Step 4: Implement fact packets, source-ref validation, and fallback**

`build_fact_packet()` includes only scope, snapshot, three ranks, `factors_by_id`, visible paths, restart aggregates, and caveats. Use a dictionary keyed by factor ID so every dot-path is unambiguous. Require `{text, source_refs}` for both the summary and each claim. Add these exact validation primitives; every stored text passes them before serialization:

```python
def build_fact_packet(explanation):
    trace = explanation["decision_trace"]
    packet = {
        "scope": {"observability_seed": 0, "gnn_arm": "sage"},
        "snapshot": explanation["scoring_day"],
        "ranks": {
            "baseline": int(trace["baseline_rank"]),
            "seed0_gnn": int(trace["seed0_gnn_rank"]),
            "seed0_hybrid": int(trace["seed0_hybrid_rank"]),
        },
        "factors_by_id": {
            factor["factor_id"]: {
                "label": factor["label"],
                "kind": factor["kind"],
                "counterfactual": factor["counterfactual"],
                "restart": factor["restart"],
                "stability": factor["stability"],
            }
            for factor in explanation["factors"]
        },
        "visible_paths": [{
            "edge_id": edge["edge_id"], "relation": edge["edge_type"],
            "u": edge["u"], "v": edge["v"],
            "explainer_median": edge.get("explainer_median", 0.0),
        } for edge in explanation["community"]["edges"]],
        "caveats": [
            "This is seed-0 observability, not the three-seed headline result.",
            "GNNExplainer masks are unsigned; direction comes from counterfactual rank effects.",
            "The evidence is associative and does not establish causation.",
        ],
    }
    return validate_explanation_payload(packet)


def build_prompt(packet):
    schema = {
        "summary": {"text": "string", "source_refs": ["dot.path"]},
        "claims": [{"text": "string", "source_refs": ["dot.path"]}],
    }
    return (
        "Return JSON only. Explain this seed-0 observability result using only the "
        "fact packet. Every sentence needs source_refs. Do not claim causation or "
        "describe GNNExplainer masks as signed. Required schema: "
        + json.dumps(schema, sort_keys=True)
        + "\nFACT_PACKET\n"
        + json.dumps(packet, sort_keys=True, default=str)
    )


CAUSAL_PHRASES = re.compile(
    r"\b(caused|causes|proved|guaranteed|transferred weights|learned weight)\b",
    re.IGNORECASE,
)
ID_TOKEN = re.compile(r"\b(?:P|E|edge|pair)-[A-Za-z0-9_-]+\b")
NUMBER_TOKEN = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?")


def _resolve_source_ref(packet, source_ref):
    value = packet
    for part in source_ref.split("."):
        if not isinstance(value, dict) or part not in value:
            raise ValueError(f"unknown source_ref: {source_ref}")
        value = value[part]
    return value


def _validate_text(packet, record):
    text = str(record.get("text", "")).strip()
    refs = record.get("source_refs")
    if not text or not isinstance(refs, list) or not refs:
        raise ValueError("unsupported narrative claim: text and source_refs are required")
    values = [_resolve_source_ref(packet, str(source_ref)) for source_ref in refs]
    evidence_text = json.dumps(values, sort_keys=True, default=str)
    full_packet_text = json.dumps(packet, sort_keys=True, default=str)
    if CAUSAL_PHRASES.search(text):
        raise ValueError("unsupported narrative claim: causal language")
    if any(token not in full_packet_text for token in ID_TOKEN.findall(text)):
        raise ValueError("unsupported narrative claim: unknown identifier")
    referenced_numbers = set(NUMBER_TOKEN.findall(evidence_text))
    allowed_scope_numbers = {"0"} if packet["scope"]["observability_seed"] == 0 else set()
    if any(number not in referenced_numbers | allowed_scope_numbers
           for number in NUMBER_TOKEN.findall(text)):
        raise ValueError("unsupported narrative claim: unknown number")
    return {"text": text, "source_refs": [str(source_ref) for source_ref in refs]}


def validate_candidate(packet, candidate):
    summary = _validate_text(packet, candidate.get("summary", {}))
    if "seed 0" not in summary["text"].casefold():
        raise ValueError("unsupported narrative claim: missing single-seed scope")
    claims = [_validate_text(packet, item) for item in candidate.get("claims", [])]
    return {"summary": summary, "claims": claims}


def render_template(packet):
    factors = list(packet["factors_by_id"].items())
    factors.sort(
        key=lambda item: (
            -abs(item[1]["counterfactual"]["hybrid_rank_delta"]), item[0]
        )
    )
    candidate = {
        "summary": {
            "text": "In seed 0, graph evidence contributed to this Hybrid selection.",
            "source_refs": ["scope.observability_seed", "ranks.seed0_hybrid"],
        },
        "claims": [],
    }
    if factors:
        factor_id, factor = factors[0]
        candidate["claims"].append({
            "text": (
                f"Removing {factor['label']} moved Hybrid rank from "
                f"{factor['counterfactual']['original_hybrid_rank']} to "
                f"{factor['counterfactual']['ablated_hybrid_rank']}."
            ),
            "source_refs": [
                f"factors_by_id.{factor_id}.label",
                f"factors_by_id.{factor_id}.counterfactual.original_hybrid_rank",
                f"factors_by_id.{factor_id}.counterfactual.ablated_hybrid_rank",
            ],
        })
    validated = validate_candidate(packet, candidate)
    return {
        "source": "deterministic_template", "model": None,
        "prompt_version": PROMPT_VERSION,
        "summary": validated["summary"]["text"],
        "summary_source_refs": validated["summary"]["source_refs"],
        "claims": validated["claims"], "validated": True,
    }


def generate_narrative(packet, *, runner=subprocess.run, timeout_seconds=180):
    try:
        candidate = _run_local_gemma(
            build_prompt(packet), runner=runner, timeout_seconds=timeout_seconds
        )
        validated = validate_candidate(packet, candidate)
        return {
            "source": "llm",
            "model": MODEL_TAG,
            "prompt_version": PROMPT_VERSION,
            "summary": validated["summary"]["text"],
            "summary_source_refs": validated["summary"]["source_refs"],
            "claims": validated["claims"],
            "validated": True,
        }
    except (
        OSError, RuntimeError, TimeoutError, subprocess.TimeoutExpired,
        ValueError, json.JSONDecodeError,
    ):
        return render_template(packet)
```

`render_template()` uses the same `{text, source_refs}` validation path and returns the same serialized fields with `source: "deterministic_template"`, `model: None`, and `validated: True`; it may mention only the three stored ranks and the highest absolute validated counterfactual rank delta.

- [ ] **Step 5: Run narrative tests**

```bash
rtk .venv/bin/python -m pytest -q tests/test_explanation_narrative.py
```

Expected: all tests pass without a running Ollama daemon; command assertions prove no auto-pull path exists.

- [ ] **Step 6: Commit local narrative generation**

```bash
rtk git add gnn/explanation_narrative.py tests/test_explanation_narrative.py
rtk git commit -m "feat: add grounded local Gemma narratives"
```

---

### Task 9: Compose and write the observability artifact

**Files:**

- Create: `gnn/observability_artifact.py`
- Modify: `gnn/run_demo.py:473-608`
- Modify: `tests/test_run_demo_smoke.py`
- Create test coverage in: `tests/test_recovery_observability.py`

- [ ] **Step 1: Write failing artifact-contract and ensemble-isolation tests**

```python
class FakeExplanationEngine:
    def relationship_categories(self, person_id, scoring_day):
        return ("COTRAVEL",)

    def explain_case(self, case):
        return {
            "case_id": f"case:{case.person_id}",
            "person_id": case.person_id,
            "event_id": case.anchor.event_id,
            "scoring_day": case.anchor.scoring_day.isoformat(),
            "decision_trace": dict(case.decision_trace),
            "factors": [],
            "community": {
                "complete": True, "nodes": [], "edges": [],
                "provenance_expansions": [],
            },
            "flow_stages": [
                {"stage_id": "first_hop", "emphasized_edge_ids": []},
                {"stage_id": "second_hop", "emphasized_edge_ids": []},
                {"stage_id": "component_pool", "emphasized_edge_ids": []},
                {"stage_id": "rank_fusion", "emphasized_edge_ids": []},
            ],
            "stability": {"stable_factor_count": 0},
            "faithfulness": {"points": []},
            "parity": {
                "production_seed0_probability": True,
                "pooled_logit_decomposition": True,
                "frozen_percentile": True,
                "frozen_daily_hybrid_rank": True,
            },
            "evidence_boundary": {
                "snapshot": case.anchor.scoring_day.isoformat(),
                "edge_rule": "available_time < snapshot",
                "caught_rule": "label_available_time_utc < snapshot",
            },
        }


def _artifact_fixture(**overrides):
    values = {
        "pool": pd.DataFrame({
            "event_id": ["e1", "e2", "e3", "e4"],
            "primary_person_id": ["p1", "p1", "p2", "p3"],
            "t": pd.to_datetime([
                "2025-01-01T01:00:00Z", "2025-01-01T02:00:00Z",
                "2025-01-01T03:00:00Z", "2025-01-02T01:00:00Z",
            ]),
            "hidden": [True, True, True, True],
        }),
        "baseline_raw": np.array([0.9, 0.8, 0.7, 0.6]),
        "seed0_gnn_raw": np.array([0.1, 0.2, 0.9, 0.95]),
        "blend_weight": 0.75,
        "caught_times": {},
        "gnn_arm": "sage",
        "surrounding_seeds": (0, 1, 2),
        "explanation_engine": FakeExplanationEngine(),
        "explanation_limit": 40,
        "inspections_per_day": 1,
        "narrative_builder": lambda packet: {
            "source": "deterministic_template", "model": None,
            "prompt_version": "v1", "summary": "Seed 0 evidence summary.",
            "summary_source_refs": ["scope.observability_seed"],
            "claims": [], "validated": True,
        },
    }
    values.update(overrides)
    return values


def test_observability_artifact_has_single_seed_scope_and_exact_summary():
    artifact = build_observability_artifact(**_artifact_fixture())
    assert artifact["schema_version"] == "1.0"
    assert artifact["policy"]["observability_seed"] == 0
    assert artifact["policy"]["surrounding_results_seeds"] == [0, 1, 2]
    assert artifact["summary"] == {
        "overlap_ids_available": True,
        "baseline_recovered": 2,
        "recovered_by_both": 1,
        "hybrid_only_recovered": 1,
        "baseline_only_recovered": 1,
        "hybrid_total": 2,
        "net_gain": 0,
    }
    assert artifact["coverage"]["explanation_limit"] == 40


def test_observability_generation_does_not_change_comparison_payload(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(run_demo.FC, "RESULTS", tmp_path)
    monkeypatch.setattr(
        run_demo, "build_observability_artifact",
        lambda **kwargs: build_observability_artifact(**_artifact_fixture()),
    )
    arguments = {
        "corpus_dir": CD, "seeds": (0, 1, 2), "n_boot": 10,
        "epochs": 1, "ks": (50,), "daily_ks": (25,), "valid_sample": 100,
    }
    without = run_demo.main(
        **arguments, out_name="without.json", observability=False
    )
    with_observability = run_demo.main(
        **arguments, out_name="with.json", observability=True,
        observability_out_name="observability.json", narrative=False,
    )
    assert without == with_observability
    assert json.loads((tmp_path / "without.json").read_text()) == json.loads(
        (tmp_path / "with.json").read_text()
    )


def test_observability_fails_closed_without_seed_zero_or_sage():
    with pytest.raises(ValueError, match="requires the surrounding three-seed GraphSAGE run"):
        build_observability_artifact(
            **_artifact_fixture(surrounding_seeds=(1, 2), gnn_arm="sage")
        )
    with pytest.raises(ValueError, match="requires the surrounding three-seed GraphSAGE run"):
        build_observability_artifact(
            **_artifact_fixture(surrounding_seeds=(0, 1, 2), gnn_arm="rgcn")
        )
```

- [ ] **Step 2: Run the focused tests and verify missing composer failures**

```bash
rtk .venv/bin/python -m pytest -q tests/test_recovery_observability.py tests/test_run_demo_smoke.py -k 'artifact or observability_generation'
```

Expected: failures name `gnn.observability_artifact` and the new `main()` arguments.

- [ ] **Step 3: Implement the artifact composer**

`build_observability_artifact()` must derive the seed-0 rank reference, Baseline and seed-0 Hybrid recovery runs, exact overlap, full lightweight cohort, deterministic attempt order, up to 40 validated explanations, failure counts, and narratives. It must call `validate_explanation_payload()` before returning.

```python
from types import MappingProxyType


def build_observability_artifact(
    *, pool, baseline_raw, seed0_gnn_raw, blend_weight,
    caught_times, gnn_arm, surrounding_seeds, explanation_engine,
    explanation_limit=40, inspections_per_day=25, narrative_builder=generate_narrative,
):
    if gnn_arm != "sage" or tuple(surrounding_seeds) != (0, 1, 2):
        raise ValueError(
            "observability requires the surrounding three-seed GraphSAGE run"
        )
    reference = build_rank_reference(pool, baseline_raw, seed0_gnn_raw, blend_weight)
    explanation_engine.rank_reference = reference
    baseline_run = simulate_recovery_run(
        pool, reference.baseline_selection_score, arm="baseline",
        daily_budget=inspections_per_day,
        official_caught_times=caught_times,
    )
    hybrid_run = simulate_recovery_run(
        pool, reference.seed0_hybrid_selection_score, arm="hybrid_seed0",
        daily_budget=inspections_per_day,
        official_caught_times=caught_times,
    )
    overlap = recovery_overlap(baseline_run, hybrid_run)
    cases = build_hybrid_only_cases(
        pool, overlap, baseline_run, hybrid_run, reference, explanation_engine
    )
    explanations, failures = explain_representatives(
        representative_attempt_order(cases), explanation_engine,
        narrative_builder=narrative_builder, limit=explanation_limit,
    )
    artifact = serialize_artifact(
        reference, overlap, cases, explanations, failures,
        seeds=surrounding_seeds, blend_weight=blend_weight,
        inspections_per_day=inspections_per_day,
        explanation_limit=explanation_limit,
    )
    return validate_explanation_payload(validate_artifact_invariants(artifact))
```

Implement the three composer helpers in the same module:

```python
def build_hybrid_only_cases(
    pool, overlap, baseline_run, hybrid_run, reference, explanation_engine
):
    cases = []
    day_values = pd.to_datetime(pool["t"], utc=True).dt.floor("D")
    for person_id in sorted(overlap.hybrid_only_ids):
        anchor = hybrid_run.first_recovery[person_id]
        same_day_rows = tuple(
            int(index) for index in pool.index[
                (pool.primary_person_id.astype(str) == person_id)
                & (day_values == anchor.scoring_day)
            ]
        )
        baseline_candidates = baseline_run.days[anchor.scoring_day].candidate_row_indices
        hybrid_candidates = hybrid_run.days[anchor.scoring_day].candidate_row_indices
        trace = build_decision_trace(
            reference, row_index=anchor.row_index,
            baseline_candidate_row_indices=baseline_candidates,
            hybrid_candidate_row_indices=hybrid_candidates,
            daily_budget=hybrid_run.daily_budget,
        )
        categories = tuple(sorted(explanation_engine.relationship_categories(
            person_id, anchor.scoring_day
        )))
        cases.append(HybridOnlyCase(
            person_id=person_id, anchor=anchor,
            baseline_rank=int(trace["baseline_rank"]),
            gnn_rank=int(trace["seed0_gnn_rank"]),
            hybrid_rank=int(trace["seed0_hybrid_rank"]),
            baseline_percentile=float(trace["baseline_percentile"]),
            gnn_percentile=float(trace["seed0_gnn_percentile"]),
            relationship_categories=categories,
            scoring_period=anchor.scoring_day.strftime("%Y-%m"),
            same_day_person_row_indices=same_day_rows,
            baseline_candidate_row_indices=baseline_candidates,
            hybrid_candidate_row_indices=hybrid_candidates,
            decision_trace=MappingProxyType(trace),
        ))
    return cases


def explain_representatives(
    cases, explanation_engine, *, narrative_builder, limit
):
    explanations, failures = [], []
    for case in cases:
        if len(explanations) >= int(limit):
            break
        try:
            explanation = explanation_engine.explain_case(case)
            required_parity = (
                "production_seed0_probability", "pooled_logit_decomposition",
                "frozen_percentile", "frozen_daily_hybrid_rank",
            )
            if any(explanation.get("parity", {}).get(key) is not True
                   for key in required_parity):
                raise ValueError("explanation parity validation failed")
            packet = build_fact_packet(explanation)
            explanation["llm_narrative"] = narrative_builder(packet)
            validate_explanation_payload(explanation)
            if explanation["community"]["complete"] is not True:
                raise ValueError("incomplete explanation community")
            explanations.append(explanation)
        except (KeyError, RuntimeError, ValueError) as error:
            failures.append({
                "person_id": case.person_id,
                "event_id": case.anchor.event_id,
                "reason_code": type(error).__name__,
                "message": str(error),
            })
    return explanations, failures


def serialize_artifact(
    reference, overlap, cases, explanations, failures, *, seeds,
    blend_weight, inspections_per_day, explanation_limit,
):
    lightweight = [{
        "case_id": f"case:{case.person_id}",
        "person_id": case.person_id,
        "event_id": case.anchor.event_id,
        "scoring_day": case.anchor.scoring_day.isoformat(),
        "baseline_rank": case.baseline_rank,
        "seed0_gnn_rank": case.gnn_rank,
        "seed0_hybrid_rank": case.hybrid_rank,
        "hybrid_rank_uplift": case.hybrid_rank_uplift,
        "gnn_percentile_uplift": case.gnn_percentile_uplift,
        "relationship_categories": list(case.relationship_categories),
        "stable_factor_status": next(
            (item.get("stable_factor_status", "unstable")
             for item in explanations if item["person_id"] == case.person_id),
            "not_explained",
        ),
    } for case in cases]
    return {
        "schema_version": "1.0",
        "policy": {
            "observability_seed": 0,
            "gnn_arm": "sage",
            "surrounding_results_seeds": list(seeds),
            "inspections_per_day": int(inspections_per_day),
            "hybrid_blend_weight": float(blend_weight),
            "percentile_reference_id": reference.percentile_reference_id,
        },
        "summary": overlap.summary,
        "coverage": {
            "hybrid_only_count": len(cases),
            "explanation_limit": int(explanation_limit),
            "attempted_count": len(explanations) + len(failures),
            "explained_count": len(explanations),
            "failed_count": len(failures),
        },
        "hybrid_only_cases": lightweight,
        "explanations": explanations,
        "generation_diagnostics": {"failed_attempts": failures},
    }


def validate_artifact_invariants(artifact):
    policy = artifact["policy"]
    if policy["observability_seed"] != 0 or policy["gnn_arm"] != "sage":
        raise ValueError("invalid observability scope")
    if policy["surrounding_results_seeds"] != [0, 1, 2]:
        raise ValueError("invalid surrounding ensemble provenance")
    summary = artifact["summary"]
    if summary["baseline_recovered"] != (
        summary["recovered_by_both"] + summary["baseline_only_recovered"]
    ):
        raise ValueError("invalid baseline overlap algebra")
    if summary["hybrid_total"] != (
        summary["recovered_by_both"] + summary["hybrid_only_recovered"]
    ) or summary["net_gain"] != (
        summary["hybrid_total"] - summary["baseline_recovered"]
    ):
        raise ValueError("invalid hybrid overlap algebra")
    required_parity = {
        "production_seed0_probability", "pooled_logit_decomposition",
        "frozen_percentile", "frozen_daily_hybrid_rank",
    }
    for explanation in artifact["explanations"]:
        snapshot = pd.Timestamp(explanation["scoring_day"])
        if explanation["community"]["complete"] is not True:
            raise ValueError("incomplete explanation community")
        if any(explanation["parity"].get(key) is not True for key in required_parity):
            raise ValueError("explanation parity failure")
        expansions = explanation["community"].get("provenance_expansions", [])
        edges = list(explanation["community"]["edges"])
        edges.extend(edge for expansion in expansions for edge in expansion.get("edges", []))
        for edge in edges:
            for observation in edge.get("observations", []):
                if not pd.Timestamp(observation["available_time"]) < snapshot:
                    raise ValueError("edge evidence is not strictly as-of")
        nodes = list(explanation["community"]["nodes"])
        nodes.extend(node for expansion in expansions for node in expansion.get("nodes", []))
        for node in nodes:
            if node.get("caught_before_snapshot") and not (
                pd.Timestamp(node["caught_label_available_time"]) < snapshot
            ):
                raise ValueError("caught evidence is not strictly as-of")
    return artifact
```

Before accepting an explanation, require parity flags for production seed-0 probability, pooled-logit decomposition, frozen percentile, and frozen daily Hybrid rank; a false or missing flag becomes a failed attempt.

- [ ] **Step 4: Add opt-in orchestration to `run_demo.main()`**

Add keyword arguments:

```python
def main(
    corpus_dir=None, seeds=(0, 1, 2), n_boot=2000,
    out_name="demo_comparison_v9.json", epochs=30, train_bucket="M",
    ks=KS, daily_ks=DAILY_KS, gnn_arm="sage", valid_sample=20000,
    observability=False,
    observability_out_name="hybrid_recovery_explanations_v9.json",
    explanation_limit=40,
    narrative=True,
):
```

Add `from pathlib import Path` and these exact output helpers:

```python
def _result_path(name_or_path):
    path = Path(name_or_path)
    return path if path.is_absolute() else FC.RESULTS / path


def _atomic_json_write(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2, default=str))
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
```

Write the existing comparison JSON first with `_atomic_json_write(_result_path(out_name), out)`. Only when `observability=True`, run this separate branch; it neither mutates nor nests data into `out`:

```python
if observability:
    engine = Seed0ExplanationEngine(
        model=score_bundle.models_by_seed[0],
        edges_typed=edges_typed,
        node_ids=node_ids,
        node_feat=node_feat,
        caught_time=caught_time,
        num_rel=spec["num_rel"],
    )
    artifact = build_observability_artifact(
        pool=pool,
        baseline_raw=base_raw,
        seed0_gnn_raw=score_bundle.scores_by_seed[0][1],
        blend_weight=w_gnn,
        caught_times=caught_time,
        gnn_arm=gnn_arm,
        surrounding_seeds=score_bundle.seed_order,
        explanation_engine=engine,
        explanation_limit=explanation_limit,
        inspections_per_day=25,
        narrative_builder=generate_narrative if narrative else render_template,
    )
    _atomic_json_write(_result_path(observability_out_name), artifact)
```

If artifact generation fails, the comparison file remains valid, no temporary artifact remains, and `main()` raises so a stale observability artifact cannot be mistaken for the current run.

- [ ] **Step 5: Run integration smoke tests**

```bash
rtk .venv/bin/python -m pytest -q tests/test_recovery_observability.py tests/test_sage_explainer.py tests/test_explanation_narrative.py tests/test_run_demo_smoke.py
```

Expected: all tests pass; observability is opt-in and ensemble output remains unchanged after the HOT correction.

- [ ] **Step 6: Commit artifact orchestration**

```bash
rtk git add gnn/observability_artifact.py gnn/run_demo.py tests/test_recovery_observability.py tests/test_run_demo_smoke.py
rtk git commit -m "feat: emit seed-zero recovery explanation artifact"
```

---

### Task 10: Embed the artifact and add pure dashboard view models

**Files:**

- Modify: `Documents/Data/scripts/build_v9_dashboard.py:21-24,84-122,158-235`
- Create: `Documents/Data/scripts/v9_recovery_explainer_ui.py`
- Modify: `tests/test_v9_dashboard_builder.py`
- Create: `tests/test_v9_recovery_explainer_ui.py`

- [ ] **Step 1: Write failing builder and view-model tests**

```python
import importlib.util
import json
import subprocess
from pathlib import Path


UI_PATH = (
    Path(__file__).resolve().parents[1]
    / "Documents/Data/scripts/v9_recovery_explainer_ui.py"
)
UI_SPEC = importlib.util.spec_from_file_location("v9_recovery_explainer_ui", UI_PATH)
UI = importlib.util.module_from_spec(UI_SPEC)
UI_SPEC.loader.exec_module(UI)


def _valid_recovery_artifact(*, baseline_only=0):
    baseline = 8
    both = baseline - baseline_only
    hybrid_only = 3
    return {
        "schema_version": "1.0",
        "policy": {
            "observability_seed": 0, "gnn_arm": "sage",
            "surrounding_results_seeds": [0, 1, 2],
            "inspections_per_day": 25,
            "percentile_reference_id": "sha256:test",
        },
        "summary": {
            "overlap_ids_available": True,
            "baseline_recovered": baseline,
            "recovered_by_both": both,
            "hybrid_only_recovered": hybrid_only,
            "baseline_only_recovered": baseline_only,
            "hybrid_total": both + hybrid_only,
            "net_gain": both + hybrid_only - baseline,
        },
        "coverage": {
            "hybrid_only_count": hybrid_only, "explanation_limit": 40,
            "attempted_count": 1, "explained_count": 1, "failed_count": 0,
        },
        "hybrid_only_cases": [{
            "case_id": "case:p1", "person_id": "p1", "event_id": "e1",
            "scoring_day": "2025-01-02T00:00:00Z",
            "baseline_rank": 40, "seed0_gnn_rank": 3,
            "seed0_hybrid_rank": 8, "hybrid_rank_uplift": 32,
            "gnn_percentile_uplift": 0.5,
            "relationship_categories": ["COTRAVEL"],
            "stable_factor_status": "stable",
        }],
        "explanations": [{
            "case_id": "case:p1", "person_id": "p1",
            "community": {
                "complete": True,
                "nodes": [{"node_id": "p1", "x": 0.5, "y": 0.5}],
                "edges": [{"edge_id": "edge-1", "u": "p1", "v": "p1"}],
                "provenance_expansions": [],
            },
            "llm_narrative": {
                "source": "deterministic_template", "model": None,
                "prompt_version": "v1", "summary": "Seed 0 evidence summary.",
                "summary_source_refs": ["scope.observability_seed"],
                "claims": [], "validated": True,
            },
        }],
        "generation_diagnostics": {"failed_attempts": []},
    }


def _run_ui(function_name, artifact, options=None):
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nconst result=" + function_name + "(" + json.dumps(artifact)
        + ("," + json.dumps(options) if options is not None else "")
        + ");process.stdout.write(JSON.stringify(result));"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def test_load_recovery_artifact_returns_valid_json(tmp_path):
    artifact = _valid_recovery_artifact()
    path = tmp_path / "hybrid_recovery_explanations_v9.json"
    path.write_text(json.dumps(artifact))
    assert builder._load_recovery_artifact(path) == artifact


def test_load_recovery_artifact_returns_none_when_missing(tmp_path):
    assert builder._load_recovery_artifact(tmp_path / "missing.json") is None


def test_nonzero_baseline_only_suppresses_containment():
    view = _run_ui(
        "buildRecoveryEvidenceViewModel",
        _valid_recovery_artifact(baseline_only=2),
    )
    assert view["summary"]["containment"] is False
    assert view["summary"]["tone"] == "warning"


def test_graph_stages_preserve_complete_base_membership():
    artifact = _valid_recovery_artifact()
    explanation = artifact["explanations"][0]
    all_view = _run_ui(
        "buildCommunityStageView", explanation,
        {"mode": "all", "stageId": "first_hop"},
    )
    flow_view = _run_ui(
        "buildCommunityStageView", explanation,
        {"mode": "flow", "stageId": "rank_fusion"},
    )
    assert all_view["nodeIds"] == flow_view["nodeIds"]
    assert all_view["edgeIds"] == flow_view["edgeIds"]
```

- [ ] **Step 2: Run the new UI tests and verify missing module/key failures**

```bash
rtk .venv/bin/python -m pytest -q tests/test_v9_dashboard_builder.py tests/test_v9_recovery_explainer_ui.py
```

Expected: failures show the artifact constant, UI module, and view-model functions are absent.

- [ ] **Step 3: Load and embed the separate artifact**

Add beside `V9_DEMO`:

```python
V9_RECOVERY_EXPLANATIONS = os.path.join(
    REPO_ROOT, "gnn", "diagnostics", "hybrid_recovery_explanations_v9.json"
)
```

Add and use this loader in `_load_v9_data()`; if it returns `None`, omit the key. Do not synthesize overlap values from `v9Demo`.

```python
def _load_recovery_artifact(path):
    if not os.path.exists(path):
        p(f"[v9-dashboard] WARNING: {path} not found; case evidence unavailable.")
        return None
    try:
        with open(path) as handle:
            artifact = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        p(f"[v9-dashboard] WARNING: invalid recovery artifact: {error}")
        return None
    if not isinstance(artifact, dict) or artifact.get("schema_version") != "1.0":
        p("[v9-dashboard] WARNING: unsupported recovery artifact schema.")
        return None
    return artifact
```

Import `V9_RECOVERY_EXPLAINER_CSS` and `V9_RECOVERY_EXPLAINER_JS` in `main()`, inject the JS exactly once before the tab renderer object, and inject the CSS exactly once before `</style>`.

- [ ] **Step 4: Implement pure JS validation and filtering in the focused UI module**

Create `v9_recovery_explainer_ui.py` exporting strings for CSS and JavaScript. The JavaScript must expose these functions for Node tests:

```javascript
function buildRecoveryEvidenceViewModel(artifact) {
  if (!artifact || artifact.schema_version !== '1.0') {
    return {available:false, reason:'unsupported-or-missing-artifact'};
  }
  const policy=artifact.policy||{};
  const summary=artifact.summary||{};
  const validScope=Number(policy.observability_seed)===0
    && policy.gnn_arm==='sage'
    && Number(policy.inspections_per_day)===25
    && Array.isArray(policy.surrounding_results_seeds)
    && policy.surrounding_results_seeds.join(',')==='0,1,2';
  if(!validScope){return {available:false,reason:'invalid-observability-scope'};}
  const required=['baseline_recovered','recovered_by_both','hybrid_only_recovered',
    'baseline_only_recovered','hybrid_total','net_gain'];
  const values=Object.fromEntries(required.map(key=>[key,Number(summary[key])]));
  const validSummary=summary.overlap_ids_available===true
    && required.every(key=>Number.isFinite(Number(summary[key])));
  const validAlgebra=validSummary
    && values.baseline_recovered===values.recovered_by_both+values.baseline_only_recovered
    && values.hybrid_total===values.recovered_by_both+values.hybrid_only_recovered
    && values.net_gain===values.hybrid_total-values.baseline_recovered;
  return {
    available:true,
    scope:{seed:Number(policy.observability_seed), arm:policy.gnn_arm,
      inspectionsPerDay:Number(policy.inspections_per_day)},
    summary: validAlgebra ? {
      values,
      containment:Number(summary.baseline_only_recovered)===0,
      tone:Number(summary.baseline_only_recovered)===0?'success':'warning'
    } : {unavailable:true,reason:'invalid-set-algebra'},
    coverage:artifact.coverage||{},
    cases:Array.isArray(artifact.hybrid_only_cases)?artifact.hybrid_only_cases:[],
    explanations:new Map((artifact.explanations||[]).map(item=>[item.case_id,item]))
  };
}

function validateRecoveryNarrative(narrative) {
  if(!narrative||narrative.validated!==true){
    return {visible:false,reason:'unvalidated'};
  }
  if(typeof narrative.summary!=='string'
      || !Array.isArray(narrative.summary_source_refs)
      || narrative.summary_source_refs.length===0){
    return {visible:false,reason:'missing-summary-sources'};
  }
  const claims=Array.isArray(narrative.claims)?narrative.claims:[];
  if(claims.some(claim=>typeof claim.text!=='string'
      || !Array.isArray(claim.source_refs)||claim.source_refs.length===0)){
    return {visible:false,reason:'missing-claim-sources'};
  }
  return {visible:true,summary:narrative.summary,claims,
    source:narrative.source,model:narrative.model||null};
}

function filterAndSortRecoveryCases(cases, options) {
  const stable=options.stableStatus||'all';
  const relation=options.relationshipCategory||'all';
  const sortBy=options.sortBy||'hybrid_rank_uplift';
  return cases.filter(item=>(stable==='all'||item.stable_factor_status===stable)
    && (relation==='all'||(item.relationship_categories||[]).includes(relation)))
    .slice().sort((left,right)=>
      Number(right[sortBy])-Number(left[sortBy])
      || Number(right.hybrid_rank_uplift)-Number(left.hybrid_rank_uplift)
      || String(left.person_id).localeCompare(String(right.person_id)));
}

function buildCommunityStageView(explanation, options) {
  const community=explanation.community;
  if (!community || community.complete!==true) {
    return {available:false, reason:'incomplete-community'};
  }
  return {
    available:true,
    nodeIds:community.nodes.map(node=>node.node_id).sort(),
    edgeIds:community.edges.map(edge=>edge.edge_id).sort(),
    mode:options.mode,
    stageId:options.stageId,
    selectedFactorId:options.selectedFactorId||null,
    query:String(options.query||'')
  };
}
```

- [ ] **Step 5: Run builder/view-model tests**

```bash
rtk .venv/bin/python -m pytest -q tests/test_v9_dashboard_builder.py tests/test_v9_recovery_explainer_ui.py
```

Expected: builder embedding, missing-artifact behavior, six-value validation, deterministic filters, containment suppression, and graph-membership invariance pass.

- [ ] **Step 6: Commit artifact embedding and pure UI state**

```bash
rtk git add Documents/Data/scripts/build_v9_dashboard.py Documents/Data/scripts/v9_recovery_explainer_ui.py tests/test_v9_dashboard_builder.py tests/test_v9_recovery_explainer_ui.py
rtk git commit -m "feat: embed V9 recovery explanation artifact"
```

---

### Task 11: Mount the split explorer and complete-community canvas

**Files:**

- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py`
- Modify: `Documents/Data/scripts/v9_dashboard_ui.py:190-265`
- Modify: `Documents/Data/scripts/build_v9_dashboard.py:197-225`
- Modify: `tests/test_v9_dashboard_builder.py`
- Modify: `tests/test_v9_recovery_explainer_ui.py`

- [ ] **Step 1: Write failing source-contract and narrative tests**

```python
def test_ui_exposes_scope_graph_controls_and_responsive_contract():
    source = ui.V9_RECOVERY_EXPLAINER_JS + ui.V9_RECOVERY_EXPLAINER_CSS
    for token in (
        "Single-seed observability", "GraphSAGE seed 0", "All connections",
        "Influence flow", "fit-to-community", "label-density", "ResizeObserver",
        "devicePixelRatio", "@media(max-width:900px)", "@media(max-width:700px)",
    ):
        assert token in source


def test_narrative_requires_validation_and_source_references():
    invalid = _valid_recovery_artifact()
    invalid["explanations"][0]["llm_narrative"]["validated"] = False
    view = _run_ui(
        "validateRecoveryNarrative",
        invalid["explanations"][0]["llm_narrative"],
    )
    assert view == {"visible": False, "reason": "unvalidated"}


def test_draw_commands_include_every_base_node_and_edge():
    explanation = _valid_recovery_artifact()["explanations"][0]
    commands = _run_ui(
        "buildCommunityDrawCommands", explanation,
        {"mode": "flow", "stageId": "rank_fusion", "selectedFactorId": None,
         "query": "", "labelDensity": "auto"},
    )
    assert [item["id"] for item in commands["nodes"]] == ["p1"]
    assert [item["id"] for item in commands["edges"]] == ["edge-1"]


def test_ui_never_uses_generic_explorer_heuristics():
    source = ui.V9_RECOVERY_EXPLAINER_JS
    for forbidden in ("DATA.explorer.gnn", "community_propensity", "true_smuggler"):
        assert forbidden not in source
```

- [ ] **Step 2: Run the UI tests and verify missing mount behavior**

```bash
rtk .venv/bin/python -m pytest -q tests/test_v9_recovery_explainer_ui.py tests/test_v9_dashboard_builder.py
```

Expected: failures show the mount, canvas controls, responsive CSS, and narrative validation are absent.

- [ ] **Step 3: Add the Results-section mount point**

In `V9_RESULTS_JS`, change the hero link to `href="#v9-case-evidence"`. Insert this section after the three-lens story and before “Baseline vs Hybrid vs GNN”:

```javascript
+'<section id="v9-case-evidence" aria-label="Single-seed Hybrid recovery evidence"></section>'
```

After `sec.innerHTML` is assigned, mount without reading the generic Explorer:

```javascript
mountV9RecoveryExplainer(
  document.getElementById('v9-case-evidence'),
  (typeof DATA!=='undefined'&&DATA)?DATA.v9RecoveryExplainer:null,
  {fmt,pct,esc}
);
```

- [ ] **Step 4: Implement the approved split explorer**

`mountV9RecoveryExplainer(root, artifact, helpers)` renders:

- the persistent “Single-seed observability · GraphSAGE seed 0” scope badge;
- six artifact-driven cards, with amber Baseline-only state and containment copy only at zero;
- coverage text such as “40 explained cases out of N Hybrid-only recoveries”;
- a left rail with deterministic sorting and stable/relation filters;
- right-side Baseline, seed-0 GNN, and seed-0 Hybrid ranks;
- measured factor cards with signed `ablated - original` rank effects;
- validated Gemma text via `textContent` and claim source chips;
- explicit missing, zero-case, failed-case, no-stable-factor, missing-graph, and template-fallback states.

Use event delegation on the section root and keep a single local state object. The narrative panel calls `validateRecoveryNarrative()` and writes summary/claim text with `textContent` only.

```javascript
const state={caseId:null,sortBy:'hybrid_rank_uplift',stableStatus:'all',
  relationshipCategory:'all',mode:'flow',stageId:'first_hop',
  selectedFactorId:null,query:'',scale:1,offsetX:0,offsetY:0,labelDensity:'auto'};
```

Use this mount skeleton; `renderCommunityCanvas()` is added in Step 5:

```javascript
function mountV9RecoveryExplainer(root,artifact,helpers){
  if(!root)return;
  const view=buildRecoveryEvidenceViewModel(artifact);
  if(!view.available){
    root.innerHTML='<div class="v9-recovery-empty">Case evidence unavailable · '
      +helpers.esc(view.reason)+'</div>';return;
  }
  const state={caseId:null,sortBy:'hybrid_rank_uplift',stableStatus:'all',
    relationshipCategory:'all',mode:'flow',stageId:'first_hop',
    selectedFactorId:null,query:'',scale:1,offsetX:0,offsetY:0,labelDensity:'auto'};
  const explanationById=new Map((artifact.explanations||[])
    .map(explanation=>[explanation.case_id,explanation]));

  function render(){
    const cases=filterAndSortRecoveryCases(view.cases,{
      stableStatus:state.stableStatus,
      relationshipCategory:state.relationshipCategory,
      sortBy:state.sortBy,
    });
    if(!state.caseId||!cases.some(item=>item.case_id===state.caseId)){
      state.caseId=cases[0]?.case_id||null;
    }
    const selected=view.cases.find(item=>item.case_id===state.caseId)||null;
    const explanation=selected?explanationById.get(selected.case_id):null;
    const summary=view.summary.unavailable
      ? '<div class="v9-recovery-warning">Overlap IDs unavailable; values are not inferred.</div>'
      : Object.entries(view.summary.values).map(([key,value])=>
          '<article class="v9-recovery-stat '+(key==='baseline_only_recovered'
            && value>0?'warning':'')+'"><span>'+helpers.esc(key.replaceAll('_',' '))
            +'</span><strong>'+helpers.fmt(value)+'</strong></article>').join('');
    const containment=!view.summary.unavailable&&view.summary.containment
      ? '<p class="v9-containment">The seed-0 Hybrid preserved every Baseline recovery.</p>'
      : '';
    const failureCopy=Number(view.coverage.failed_count||0)>0
      ? '<p class="v9-recovery-warning">'+helpers.fmt(view.coverage.failed_count)
        +' explanation attempts failed validation.</p>':'';
    const caseRows=cases.map(item=>'<button class="v9-case-row" data-case-id="'
      +helpers.esc(item.case_id)+'"><strong>'+helpers.esc(item.person_id)
      +'</strong><span>Hybrid uplift '+helpers.fmt(item.hybrid_rank_uplift)
      +'</span></button>').join('');
    const factors=explanation?(explanation.factors||[]).map(factor=>
      '<button class="v9-factor" data-factor-id="'+helpers.esc(factor.factor_id)
      +'"><span>'+helpers.esc(factor.label||factor.factor_id)+'</span><strong>'
      +helpers.fmt(factor.counterfactual?.hybrid_rank_delta||0)
      +' ranks</strong></button>').join(''):'';
    root.innerHTML='<div class="v9-recovery-head"><span class="v9-scope-badge">'
      +'Single-seed observability · GraphSAGE seed 0</span></div>'
      +'<div class="v9-recovery-summary">'+summary+'</div>'+containment
      +'<p class="v9-coverage">'+helpers.fmt(view.coverage.explained_count||0)
      +' explained cases out of '+helpers.fmt(view.coverage.hybrid_only_count||0)
      +' Hybrid-only recoveries</p>'+failureCopy
      +'<div class="v9-recovery-layout"><aside><div class="v9-case-filters">'
      +'<select data-filter="sort"><option value="hybrid_rank_uplift">Hybrid rank uplift</option>'
      +'<option value="gnn_percentile_uplift">GNN percentile uplift</option></select>'
      +'<select data-filter="stable"><option value="all">All stability</option>'
      +'<option value="stable">Stable factors</option><option value="unstable">Unstable</option>'
      +'<option value="not_explained">Not explained</option></select>'
      +'<select data-filter="relation"><option value="all">All connections</option>'
      +'<option>COTRAVEL</option><option>RESIDENCE</option><option>SHARED_PLATE</option>'
      +'<option>SHARED_PLATE_HOT</option></select></div>'
      +(caseRows||'<div class="v9-recovery-empty">No cases match these filters.</div>')
      +'</aside><div class="v9-case-detail">'
      +(selected?'<header><strong>'+helpers.esc(selected.person_id)+'</strong><span>Baseline rank '
        +helpers.fmt(selected.baseline_rank)+'</span><span>seed-0 GNN rank '
        +helpers.fmt(selected.seed0_gnn_rank)+'</span><span>seed-0 Hybrid rank '
        +helpers.fmt(selected.seed0_hybrid_rank)+'</span><span>Snapshot '
        +helpers.esc(selected.scoring_day)+'</span><span>25/day selected</span></header>':'' )
      +(explanation?'<div class="v9-factors">'+(factors
        ||'<div class="v9-recovery-empty">No stable factor met the display threshold.</div>')
        +'</div><div class="v9-graph-tools"><select data-graph-mode>'
        +'<option value="all">All connections</option><option value="flow">Influence flow</option>'
        +'</select><select data-flow-stage><option value="first_hop">First hop</option>'
        +'<option value="second_hop">Second hop</option><option value="component_pool">Component pool</option>'
        +'<option value="rank_fusion">Rank fusion</option></select>'
        +'<button data-graph-action="zoom-in">+</button>'
        +'<button data-graph-action="zoom-out">−</button><button data-graph-action="reset">Reset</button>'
        +'<button data-graph-action="fit-to-community">fit-to-community</button>'
        +'<input data-graph-query aria-label="Search community"><select data-label-density>'
        +'<option value="auto">label-density auto</option><option value="all">all labels</option>'
        +'<option value="none">minimal labels</option></select></div>'
        +'<canvas class="v9-community-canvas"></canvas><div class="v9-narrative"></div>'
        :selected?'<div class="v9-recovery-empty">Explanation attempt failed or was not selected.</div>'
        :'<div class="v9-recovery-empty">No Hybrid-only recoveries in this seed-0 run.</div>')
      +'</div></div>';
    root.querySelector('[data-filter="stable"]').value=state.stableStatus;
    root.querySelector('[data-filter="relation"]').value=state.relationshipCategory;
    root.querySelector('[data-filter="sort"]').value=state.sortBy;
    if(!explanation)return;
    const narrative=validateRecoveryNarrative(explanation.llm_narrative);
    const narrativeRoot=root.querySelector('.v9-narrative');
    if(narrative.visible){
      const label=document.createElement('strong');
      label.textContent=narrative.source==='llm'
        ?'AI-generated summary · Gemma 4 12B':'Deterministic evidence summary';
      const text=document.createElement('p');text.textContent=narrative.summary;
      narrativeRoot.replaceChildren(label,text);
      narrative.claims.forEach(claim=>{
        const row=document.createElement('p');row.textContent=claim.text;
        const sources=document.createElement('span');sources.className='v9-source-chips';
        claim.source_refs.forEach(sourceRef=>{
          const chip=document.createElement('code');chip.textContent=sourceRef;
          sources.appendChild(chip);
        });
        narrativeRoot.append(row,sources);
      });
    }
    const canvas=root.querySelector('.v9-community-canvas');
    root.querySelector('[data-graph-mode]').value=state.mode;
    root.querySelector('[data-flow-stage]').value=state.stageId;
    root.querySelector('[data-label-density]').value=state.labelDensity;
    if(explanation.community?.complete===true){
      renderCommunityCanvas(canvas,explanation,state);
      bindCommunityCanvas(canvas,explanation,state);
    }else{
      canvas.replaceWith(Object.assign(document.createElement('div'),
        {className:'v9-recovery-empty',textContent:'Complete community unavailable.'}));
    }
  }

  root.addEventListener('click',event=>{
    const caseButton=event.target.closest('[data-case-id]');
    const factorButton=event.target.closest('[data-factor-id]');
    if(caseButton){state.caseId=caseButton.dataset.caseId;state.selectedFactorId=null;render();}
    if(factorButton){state.selectedFactorId=factorButton.dataset.factorId;render();}
  });
  root.addEventListener('change',event=>{
    if(event.target.dataset.filter==='stable')state.stableStatus=event.target.value;
    if(event.target.dataset.filter==='relation')state.relationshipCategory=event.target.value;
    if(event.target.dataset.filter==='sort')state.sortBy=event.target.value;
    if(event.target.matches('[data-graph-mode]'))state.mode=event.target.value;
    if(event.target.matches('[data-flow-stage]'))state.stageId=event.target.value;
    if(event.target.matches('[data-label-density]'))state.labelDensity=event.target.value;
    render();
  });
  root.addEventListener('input',event=>{
    if(event.target.matches('[data-graph-query]')){
      state.query=event.target.value;render();
    }
  });
  render();
}
```

- [ ] **Step 5: Implement a complete native-canvas graph**

The canvas renderer must draw every base node and edge in every mode. Artifact-provided normalized coordinates determine layout. Stage and factor selection change style only; provenance expansion nodes/edges render as a dashed layer labelled “outside message community.” Build draw commands first so completeness is unit-testable:

```javascript
function buildCommunityDrawCommands(explanation,state){
  const community=explanation.community||{};
  const selected=(explanation.factors||[])
    .find(factor=>factor.factor_id===state.selectedFactorId);
  const expansionIds=new Set(selected&&selected.provenance_expansion_ids||[]);
  const expansions=(community.provenance_expansions||[])
    .filter(expansion=>expansionIds.has(expansion.expansion_id));
  return {
    edges:(community.edges||[]).map(edge=>({id:edge.edge_id,record:edge,layer:'base'})),
    nodes:(community.nodes||[]).map(node=>({id:node.node_id,record:node,layer:'base'})),
    provenanceEdges:expansions.flatMap(expansion=>(expansion.edges||[])
      .map(edge=>({id:edge.edge_id,record:edge,layer:'provenance'}))),
    provenanceNodes:expansions.flatMap(expansion=>(expansion.nodes||[])
      .map(node=>({id:node.node_id,record:node,layer:'provenance'})))
  };
}

function graphPoint(node,width,height,state){
  const margin=34;
  return {
    x:margin+Number(node.x)*(width-2*margin)*state.scale+state.offsetX,
    y:margin+Number(node.y)*(height-2*margin)*state.scale+state.offsetY
  };
}

function drawBaseEdge(context,command,nodeById,state,width,height){
  const edge=command.record,u=nodeById.get(edge.u),v=nodeById.get(edge.v);
  if(!u||!v)return;
  const a=graphPoint(u,width,height,state),b=graphPoint(v,width,height,state);
  const influence=Number(edge.explainer_median||0);
  context.save();
  context.strokeStyle=edge.color||'#708090';
  context.globalAlpha=state.mode==='flow'?.18+.72*influence:.52;
  context.lineWidth=state.mode==='flow'?1+5*influence:1.4;
  context.beginPath();context.moveTo(a.x,a.y);context.lineTo(b.x,b.y);context.stroke();
  context.restore();
}

function drawBaseNode(context,command,state,width,height,nodeCount){
  const node=command.record,point=graphPoint(node,width,height,state);
  const match=state.query&&String(node.node_id).toLowerCase()
    .includes(String(state.query).toLowerCase());
  context.save();
  context.fillStyle=match?'#f4b942':(node.pooled_member?'#205b8f':'#d9e2ec');
  context.beginPath();context.arc(point.x,point.y,node.pooled_member?7:5,0,Math.PI*2);
  context.fill();
  const showLabel=state.labelDensity==='all'||match
    ||(state.labelDensity==='auto'&&nodeCount<=50)||node.target===true;
  if(showLabel){context.fillStyle='#17212b';context.fillText(node.node_id,point.x+8,point.y-7);}
  context.restore();
}

function drawSelectedFactorProvenance(context,commands,nodeById,state,width,height){
  context.save();context.setLineDash([5,4]);context.globalAlpha=.65;
  commands.provenanceEdges.forEach(command=>
    drawBaseEdge(context,command,nodeById,state,width,height));
  commands.provenanceNodes.forEach(command=>
    drawBaseNode(context,command,state,width,height,commands.provenanceNodes.length));
  context.restore();
}

function drawFlowStage(context,explanation,state,nodeById,width,height){
  if(state.mode!=='flow')return;
  const stage=(explanation.flow_stages||[]).find(item=>item.stage_id===state.stageId);
  if(!stage)return;
  context.save();context.strokeStyle='#d45b2c';context.globalAlpha=.85;
  (stage.emphasized_edge_ids||[]).forEach(edgeId=>{
    const edge=(explanation.community.edges||[]).find(item=>item.edge_id===edgeId);
    if(edge)drawBaseEdge(context,{record:{...edge,explainer_median:1}},nodeById,
      {...state,mode:'flow'},width,height);
  });
  context.restore();
}

function renderCommunityCanvas(canvas, explanation, state) {
  const context=canvas.getContext('2d');
  const ratio=window.devicePixelRatio||1;
  const bounds=canvas.getBoundingClientRect();
  canvas.width=Math.max(1,Math.round(bounds.width*ratio));
  canvas.height=Math.max(1,Math.round(bounds.height*ratio));
  context.setTransform(ratio,0,0,ratio,0,0);
  context.clearRect(0,0,bounds.width,bounds.height);
  const commands=buildCommunityDrawCommands(explanation,state);
  const nodeById=new Map([
    ...commands.nodes,...commands.provenanceNodes
  ].map(command=>[command.id,command.record]));
  commands.edges.forEach(command=>drawBaseEdge(
    context,command,nodeById,state,bounds.width,bounds.height));
  commands.nodes.forEach(command=>drawBaseNode(
    context,command,state,bounds.width,bounds.height,commands.nodes.length));
  drawSelectedFactorProvenance(
    context,commands,nodeById,state,bounds.width,bounds.height);
  drawFlowStage(
    context,explanation,state,nodeById,bounds.width,bounds.height);
}
```

Attach canvas-local wheel, pinch, pan, and resize controls with this function. The stable root click listener handles toolbar actions after it handles case/factor selection.

```javascript
function bindCommunityCanvas(canvas,explanation,state){
  let drag=null,pinchDistance=null;
  const pointers=new Map();
  const redraw=()=>renderCommunityCanvas(canvas,explanation,state);
  canvas.addEventListener('wheel',event=>{
    event.preventDefault();
    state.scale=Math.max(.25,Math.min(5,state.scale*(event.deltaY<0?1.12:.89)));
    redraw();
  },{passive:false});
  canvas.addEventListener('pointerdown',event=>{
    canvas.setPointerCapture(event.pointerId);
    pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});
    drag={x:event.clientX,y:event.clientY,offsetX:state.offsetX,offsetY:state.offsetY};
  });
  canvas.addEventListener('pointermove',event=>{
    if(pointers.has(event.pointerId)){
      pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});
    }
    if(pointers.size===2){
      const [a,b]=[...pointers.values()];
      const distance=Math.hypot(a.x-b.x,a.y-b.y);
      if(pinchDistance!==null){
        state.scale=Math.max(.25,Math.min(5,state.scale*distance/pinchDistance));
      }
      pinchDistance=distance;redraw();return;
    }
    if(!drag)return;
    state.offsetX=drag.offsetX+event.clientX-drag.x;
    state.offsetY=drag.offsetY+event.clientY-drag.y;
    redraw();
  });
  function releasePointer(event){
    pointers.delete(event.pointerId);pinchDistance=null;drag=null;
  }
  canvas.addEventListener('pointerup',releasePointer);
  canvas.addEventListener('pointercancel',releasePointer);
  new ResizeObserver(redraw).observe(canvas);
}
```

Add this branch to the stable `root.addEventListener('click', ...)` callback in `mountV9RecoveryExplainer()`:

```javascript
const action=event.target.closest('[data-graph-action]')?.dataset.graphAction;
if(action){
  if(action==='zoom-in')state.scale=Math.min(5,state.scale*1.2);
  if(action==='zoom-out')state.scale=Math.max(.25,state.scale/1.2);
  if(action==='reset'||action==='fit-to-community'){
    state.scale=1;state.offsetX=0;state.offsetY=0;
  }
  const explanation=explanationById.get(state.caseId);
  const canvas=root.querySelector('.v9-community-canvas');
  if(explanation&&canvas)renderCommunityCanvas(canvas,explanation,state);
}
```

- [ ] **Step 6: Add responsive CSS**

Desktop uses `grid-template-columns:minmax(260px,.34fr) minmax(0,1fr)`. At 900 px, stack the rail with bounded scrolling. At 700 px, use two summary/metric columns, horizontally scroll toolbars/stages, and reduce graph height without removing touch controls.

```css
#v9-case-evidence{margin:28px 0}.v9-scope-badge{display:inline-flex;padding:6px 10px;
  border:1px solid #9fb3c8;border-radius:999px;font-size:12px;letter-spacing:.03em}
.v9-recovery-summary{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;
  margin:14px 0}.v9-recovery-stat{padding:14px;border:1px solid #d8e1ea;border-radius:10px}
.v9-recovery-stat span{display:block;font-size:11px;text-transform:uppercase}
.v9-recovery-stat strong{display:block;font-size:24px}.v9-recovery-stat.warning,
.v9-recovery-warning{border-color:#d89b3c;color:#8a5413}.v9-recovery-layout{display:grid;
  grid-template-columns:minmax(260px,.34fr) minmax(0,1fr);gap:18px;align-items:start}
.v9-recovery-layout aside{max-height:720px;overflow:auto;border-right:1px solid #d8e1ea}
.v9-case-row,.v9-factor{display:flex;width:100%;justify-content:space-between;gap:12px;
  padding:10px;border:0;border-bottom:1px solid #e7edf3;background:transparent;text-align:left}
.v9-case-detail header,.v9-graph-tools{display:flex;gap:10px;align-items:center;overflow-x:auto}
.v9-community-canvas{display:block;width:100%;height:520px;touch-action:none;border:1px solid #d8e1ea}
.v9-recovery-empty{padding:18px;border:1px dashed #aebdca;border-radius:10px}
@media(max-width:900px){.v9-recovery-layout{grid-template-columns:1fr}.v9-recovery-layout aside{
  max-height:280px;border-right:0;border-bottom:1px solid #d8e1ea}}
@media(max-width:700px){.v9-recovery-summary{grid-template-columns:repeat(2,minmax(0,1fr))}
  .v9-case-detail header,.v9-graph-tools{white-space:nowrap}.v9-community-canvas{height:390px}
  .v9-graph-tools button,.v9-graph-tools input,.v9-graph-tools select{min-height:42px}}
```

- [ ] **Step 7: Run UI and builder tests**

```bash
rtk .venv/bin/python -m pytest -q tests/test_v9_recovery_explainer_ui.py tests/test_v9_dashboard_builder.py
```

Expected: all view, source-contract, graph-completeness, narrative, error-state, injection-count, and responsive tests pass.

- [ ] **Step 8: Commit the Results explorer**

```bash
rtk git add Documents/Data/scripts/v9_recovery_explainer_ui.py Documents/Data/scripts/v9_dashboard_ui.py Documents/Data/scripts/build_v9_dashboard.py tests/test_v9_recovery_explainer_ui.py tests/test_v9_dashboard_builder.py
rtk git commit -m "feat: add V9 Hybrid recovery case explorer"
```

---

### Task 12: Regenerate corrected V9 results and prove the complete feature

**Files:**

- Modify: `Documents/Data/changes_3.md`
- Regenerate: `gnn/diagnostics/demo_comparison_v9.json`
- Create/regenerate: `gnn/diagnostics/hybrid_recovery_explanations_v9.json`
- Regenerate: `Documents/Data/v9_dashboard/data_v9.json`
- Regenerate: `Documents/Data/v9_dashboard/index.html`

- [ ] **Step 1: Run every focused source test**

```bash
rtk .venv/bin/python -m pytest -q tests/test_df_graphmodel_rgcn.py tests/test_recovery_observability.py tests/test_sage_explainer.py tests/test_explanation_narrative.py tests/test_run_demo_smoke.py tests/test_v9_dashboard_builder.py tests/test_v9_recovery_explainer_ui.py
```

Expected: all focused tests pass with no Ollama daemon requirement.

- [ ] **Step 2: Run the V9dev observability smoke without Gemma**

```bash
rtk .venv/bin/python -c 'from pathlib import Path; from gnn.run_demo import main; main(corpus_dir=Path("Documents/Data/synthetic_cbp_graph_corpus_v9dev"), seeds=(0,1,2), n_boot=20, epochs=1, valid_sample=500, out_name="/private/tmp/demo_comparison_v9dev_observability.json", observability=True, observability_out_name="/private/tmp/hybrid_recovery_explanations_v9dev.json", explanation_limit=3, narrative=False)'
```

Expected: comparison and observability JSON files are created under `/private/tmp`; the comparison records seeds `[0,1,2]`, the observability policy records seed `0`, and every explanation passes parity/leakage validation without dirtying tracked diagnostics.

- [ ] **Step 3: Validate V9dev artifact invariants**

```bash
rtk .venv/bin/python -c 'import json; from pathlib import Path; from gnn.observability_artifact import validate_artifact_invariants; a=json.loads(Path("/private/tmp/hybrid_recovery_explanations_v9dev.json").read_text()); validate_artifact_invariants(a); assert a["coverage"]["explained_count"]<=3; print(json.dumps({"summary":a["summary"],"coverage":a["coverage"]},indent=2))'
```

Expected: assertions pass and the command prints the exact V9dev summary/coverage.

- [ ] **Step 4: Start local Ollama in a separate execution session and smoke-test Gemma**

Run the daemon in its own long-running session:

```bash
rtk ollama serve
```

Then verify the installed tag and one validated narrative:

```bash
rtk ollama list
rtk env RUN_OLLAMA_INTEGRATION=1 .venv/bin/python -m pytest -q tests/test_explanation_narrative.py -k live_gemma
```

Expected: `gemma4:12b` is listed and the opt-in integration test returns a validated `llm` narrative. Stop the daemon session after artifact generation.

- [ ] **Step 5: Regenerate the corrected full V9 comparison and observability artifact**

```bash
rtk .venv/bin/python -c 'from pathlib import Path; from gnn.run_demo import main; main(corpus_dir=Path("Documents/Data/synthetic_cbp_graph_corpus_v9"), seeds=(0,1,2), out_name="demo_comparison_v9.json", observability=True, observability_out_name="hybrid_recovery_explanations_v9.json", explanation_limit=40, narrative=True)'
```

Expected: the full three-seed comparison and seed-0 observability artifact complete successfully; accepted narratives record `gemma4:12b`, and any rejected generation uses the deterministic template.

- [ ] **Step 6: Inspect exact corrected metrics before editing documentation**

```bash
rtk .venv/bin/python -c 'import json; from pathlib import Path; c=json.loads(Path("gnn/diagnostics/demo_comparison_v9.json").read_text()); o=json.loads(Path("gnn/diagnostics/hybrid_recovery_explanations_v9.json").read_text()); print(json.dumps({"gnn_seeds":c["gnn_seeds"],"fusion_weight":c["hybrid_fusion_w_gnn"],"daily_25":{"baseline":c["overall_daily"]["baseline"]["daily_found@25"],"hybrid":c["overall_daily"]["hybrid"]["daily_found@25"]},"observability_summary":o["summary"],"coverage":o["coverage"],"narrative_sources":sorted({x["llm_narrative"]["source"] for x in o["explanations"]})},indent=2))'
```

Expected: output contains the exact post-fix values used in dashboard copy and `changes_3.md`; no pre-fix number is retained without being labelled historical.

- [ ] **Step 7: Update `changes_3.md` with the measured post-fix record**

Using `apply_patch`, add a dated subsection that states:

- HOT activation now uses earliest official `label_available_time_utc` per vehicle;
- V9dev boundary tests and full V9 regeneration passed;
- the exact three-seed daily-25 Baseline/Hybrid values printed in Step 6;
- the exact seed-0 overlap summary and explained coverage printed in Step 6; and
- the observability block is single-seed while every existing V9 headline remains ensemble-based.

Do not type values from memory; copy the Step 6 JSON exactly.

- [ ] **Step 8: Rebuild and test the static dashboard**

```bash
rtk .venv/bin/python Documents/Data/scripts/build_v9_dashboard.py
rtk .venv/bin/python -m pytest -q tests/test_v9_dashboard_builder.py tests/test_v9_recovery_explainer_ui.py tests/test_run_demo_smoke.py
rtk rg -n 'v9RecoveryExplainer|v9-case-evidence|Single-seed observability|AI-generated summary' Documents/Data/v9_dashboard/data_v9.json Documents/Data/v9_dashboard/index.html
```

Expected: generated data/HTML contain the new artifact, section, scope label, and narrative label exactly once; all tests pass.

- [ ] **Step 9: Perform browser visual QA**

Use the browser skill against the generated local dashboard. Verify desktop and narrow widths, six summary cards, containment suppression when appropriate, deterministic case filtering, complete graph counts, all four flow stages, factor provenance expansion, pan/zoom/search/fit controls, Gemma/template labels, and missing/failed-case states. Capture any issue as a failing source test before fixing it.

- [ ] **Step 10: Run final source verification**

```bash
rtk .venv/bin/python -m pytest -q tests/test_df_detector.py tests/test_df_graphmodel_rgcn.py tests/test_demo_baseline.py tests/test_run_demo_smoke.py tests/test_v9_corpus_snapshot.py tests/test_recovery_observability.py tests/test_sage_explainer.py tests/test_explanation_narrative.py tests/test_v9_dashboard_builder.py tests/test_v9_recovery_explainer_ui.py
rtk git diff --check
```

Expected: all listed tests pass and `git diff --check` prints nothing.

- [ ] **Step 11: Commit corrected artifacts, documentation, and dashboard output**

```bash
rtk git add Documents/Data/changes_3.md gnn/diagnostics/demo_comparison_v9.json gnn/diagnostics/hybrid_recovery_explanations_v9.json Documents/Data/v9_dashboard/data_v9.json Documents/Data/v9_dashboard/index.html
rtk git commit -m "docs: record corrected V9 observability results"
```
