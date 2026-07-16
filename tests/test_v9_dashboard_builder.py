import csv
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


MODULE_PATH = (
    __import__("pathlib").Path(__file__).resolve().parents[1]
    / "Documents/Data/scripts/build_v9_dashboard.py"
)
SPEC = importlib.util.spec_from_file_location("build_v9_dashboard", MODULE_PATH)
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)

UI_MODULE_PATH = (
    __import__("pathlib").Path(__file__).resolve().parents[1]
    / "Documents/Data/scripts/v9_dashboard_ui.py"
)
UI_SPEC = importlib.util.spec_from_file_location("v9_dashboard_ui", UI_MODULE_PATH)
V9_UI = importlib.util.module_from_spec(UI_SPEC)
UI_SPEC.loader.exec_module(V9_UI)


def _write_csv(path, rows):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def _simulated_arm(budgets):
    arm = {}
    for budget, rows in budgets.items():
        found = sum(row["found"] for row in rows)
        inspections = budget * len(rows)
        arm.update({
            f"daily_people_found@{budget}": found,
            f"daily_found_by_day@{budget}": rows,
            f"daily_budget@{budget}": inspections,
            f"daily_precision@{budget}": found / inspections if inspections else 0.0,
            f"daily_recall@{budget}": found / 10,
            f"daily_f1@{budget}": found / 20,
            f"later_candidate_events_removed@{budget}": found + 2,
            f"later_hidden_events_removed@{budget}": found + 1,
        })
    return arm


def _run_simulated_view_model(simulated, requested_budget=None):
    assert hasattr(V9_UI, "SIMULATED_CATCH_VIEW_MODEL_JS")
    script = (
        V9_UI.SIMULATED_CATCH_VIEW_MODEL_JS
        + "\nprocess.stdout.write(JSON.stringify(buildSimulatedCatchViewModel("
        + json.dumps(simulated)
        + ","
        + json.dumps(requested_budget)
        + ")));"
    )
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_daily_crossing_series_uses_test_split(tmp_path):
    _write_csv(tmp_path / "train_valid_test_splits.csv", [
        {"entity_id": "E1", "split": "test"},
        {"entity_id": "E2", "split": "test"},
        {"entity_id": "E3", "split": "train"},
    ])
    _write_csv(tmp_path / "crossing_events.csv", [
        {"event_id": "E1", "event_timestamp_utc": "2025-01-02T03:00:00Z"},
        {"event_id": "E2", "event_timestamp_utc": "2025-01-02T04:00:00Z"},
        {"event_id": "E3", "event_timestamp_utc": "2025-01-02T05:00:00Z"},
    ])

    assert BUILDER._daily_crossing_series(tmp_path) == [
        {"date": "2025-01-02", "crossings": 2},
    ]


def test_direct_file_data_discards_stale_demo_without_current_diagnostic(
    tmp_path, monkeypatch
):
    stale_demo = {
        "overall": {
            "baseline": {"found@50": 1},
            "gnn": {"found@50": 2},
        },
    }
    (tmp_path / "dashboard_data.json").write_text(
        json.dumps({"v9Demo": stale_demo})
    )
    _write_csv(tmp_path / "train_valid_test_splits.csv", [
        {"entity_id": "E1", "split": "test"},
    ])
    _write_csv(tmp_path / "crossing_events.csv", [
        {"event_id": "E1", "event_timestamp_utc": "2025-01-02T03:00:00Z"},
    ])
    monkeypatch.setattr(BUILDER, "V9_DATA", str(tmp_path / "dashboard_data.json"))
    monkeypatch.setattr(BUILDER, "V9_DEMO", str(tmp_path / "missing_demo.json"))
    monkeypatch.setattr(BUILDER, "V9_CORPUS", str(tmp_path))

    data = BUILDER._load_v9_data()
    embedded = BUILDER._embed_dashboard_data(
        "const DATA = OLD;\n(async function(){\n  if(!D) return;\n",
        data,
    )

    assert "v9Demo" not in data
    assert '"v9Demo"' not in embedded


def test_v9_ui_includes_model_daily_catch_chart():
    ui_path = Path(__file__).resolve().parents[1] / "Documents/Data/scripts/v9_dashboard_ui.py"
    ui = ui_path.read_text()

    assert "daily_found_by_day@" in ui
    assert "Baseline" in ui
    assert "Deployable Hybrid" in ui
    assert "GNN" in ui
    assert ".v9-chart-key.baseline" in ui
    assert ".v9-chart-key.hybrid" in ui
    assert ".v9-chart-key.gnn" in ui
    assert "pointermove" in ui
    assert "v9-hover-guide" in ui
    assert "v9-chart-stack" in ui
    assert "v9-chart-toggle" in ui
    assert "modelVisibility" in ui
    assert "Number(point.dataset.index)===i" in ui
    assert "v9-combined-chart" in ui
    assert "crossing events / day" in ui
    assert "hidden carriers found / day" in ui
    assert 'data-layer="hidden-carriers"' in ui
    assert 'data-layer="crossings"' in ui
    assert "v9-hidden-carriers-layer" in ui


def test_v9_ui_keeps_three_metric_lenses_without_redundant_global_table():
    ui_path = Path(__file__).resolve().parents[1] / "Documents/Data/scripts/v9_dashboard_ui.py"
    ui = ui_path.read_text()

    assert "Read the V9 result through three lenses" in ui
    assert "1. Global ranking" in ui
    assert "2. Findable depth" in ui
    assert "3. Daily operations" in ui
    assert 'id="v9-pop"' in ui
    assert "Observable slice" in ui
    assert "Whole pool" in ui
    assert "Depth Recall" in ui
    assert 'id="v9-bars"' in ui
    assert (
        "Leak-safe baselines use row-level history and context. GNN arms add as-of "
        "relational signals."
    ) in ui
    assert (
        "Baselines use the target row; GNN arms add graph evidence available before scoring."
    ) in ui
    assert "Each panel uses a different population or inspection budget." in ui
    assert "The graph advantage appears at operational depth." in ui
    assert (
        "One whole-pool top-K list, with all hidden carriers in the recall denominator."
    ) in ui
    assert (
        "Defaults to the '+fmt(demo.stratum_hidden.observable)+'-carrier observable "
        "slice. Toggle for the whole pool."
    ) in ui
    assert (
        "Each of '+fmt(dailyDays)+' test days gets its own quota; 25/day equals "
        "'+fmt(dailyBudget25)+' inspections."
    ) in ui
    assert "Share of hidden carriers found in the selected population." in ui
    assert (
        "Found, precision, recall, and F1 under fixed per-day inspection budgets."
    ) in ui
    assert (
        "Daily test-window crossing volume and hidden carriers found by each model."
    ) in ui
    assert "Daily top-k finds only. Toggle a model to show or hide its line." in ui
    assert (
        "Paired event-bootstrap results for Hybrid minus baseline, using global and daily "
        "budgets."
    ) in ui
    assert "wholeHybridAt2000" in ui
    assert "wholeBaselineAt2000" in ui
    assert "Global Found@K by selected population" not in ui
    assert 'id="v9-table"' not in ui
    assert "function drawTable()" not in ui


def test_v9_ui_removes_whole_pool_model_comparison_and_dead_helpers():
    ui_path = Path(__file__).resolve().parents[1] / "Documents/Data/scripts/v9_dashboard_ui.py"
    ui = ui_path.read_text()

    assert "Whole-pool model comparison" not in ui
    assert 'id="v9-model-table"' not in ui
    assert "drawModelTable" not in ui
    assert "compareKs" not in ui
    assert "const recall=" not in ui
    assert "const precision=" not in ui
    assert "const f1=" not in ui
    assert ".group-header" not in ui
    assert ".v9-table-wrap" in ui


def test_v9_ui_adds_independent_simulated_catch_contract():
    ui_path = Path(__file__).resolve().parents[1] / "Documents/Data/scripts/v9_dashboard_ui.py"
    ui = ui_path.read_text()

    assert "Simulated catches — first-time recoveries" in ui
    assert 'id="v9-simulated-catches"' in ui
    assert 'id="v9-simulated-k"' in ui
    assert 'id="v9-simulated-summary"' in ui
    assert 'id="v9-simulated-volume"' in ui
    assert "function drawSimulatedCatches()" in ui
    assert "demo.simulated_catch_daily" in ui
    assert "daily_people_found@" in ui
    assert "daily_found_by_day@" in ui
    assert "daily_budget@" in ui
    assert "daily_precision@" in ui
    assert "daily_recall@" in ui
    assert "daily_f1@" in ui
    assert "later_hidden_events_removed@" in ui
    assert "Unique people found" in ui
    assert "Inspections" in ui
    assert "Precision" in ui
    assert "Recall" in ui
    assert "F1" in ui
    assert "Later hidden-positive events removed" in ui
    assert "Simulated first-time recoveries at '+fmt(selected)+' inspections per day" in ui
    assert "aria-describedby=\"v9-simulated-data-'+selected+'\"" in ui
    assert "<table id=\"v9-simulated-data-'+selected+'\" class=\"v9-sr-only\">" in ui
    assert "<th>Date</th><th>Baseline</th><th>Deployable Hybrid</th>" in ui
    assert 'class="v9-simulated-chart-scroll"' in ui
    assert "No simulated-catch series is embedded in this dashboard." in ui

    simulated_renderer = ui.split("function drawSimulatedCatches()", 1)[1].split(
        "function drawSig()", 1
    )[0]
    assert "['baseline','hybrid']" in simulated_renderer
    assert "view.valuesByArm" in simulated_renderer
    assert "showTip" in simulated_renderer
    assert "hideTip" in simulated_renderer
    assert "gnn" not in simulated_renderer.lower()
    assert "v9DailyCrossings" not in simulated_renderer


def test_v9_ui_keeps_daily_volume_and_simulated_catches_independent():
    ui_path = Path(__file__).resolve().parents[1] / "Documents/Data/scripts/v9_dashboard_ui.py"
    ui = ui_path.read_text()

    for element_id in (
        "v9-daily-found-k",
        "v9-volume",
        "v9-simulated-catches",
        "v9-simulated-k",
        "v9-simulated-summary",
        "v9-simulated-volume",
    ):
        assert ui.count(f'id="{element_id}"') == 1

    assert ui.index('id="v9-volume"') < ui.index('id="v9-simulated-catches"')
    assert "select.onchange=()=>drawCombined()" in ui
    assert "simSelect.onchange=()=>drawSimulatedCatches()" in ui
    assert ".v9-daily-found-select:focus-visible" in ui
    assert ".v9-chart-toggle:focus-visible" in ui
    assert ".v9-simulated-chart-scroll" in ui
    assert "overflow-x: auto" in ui
    assert "min-width: 720px" in ui
    assert ".v9-simulated-chart text" in ui
    assert "fill: var(--text2)" in ui


def test_simulated_view_model_keeps_selector_state_and_series_independent():
    baseline = _simulated_arm({
        5: [
            {"date": "2025-01-01", "found": 1},
            {"date": "2025-01-02", "found": 0},
        ],
        25: [{"date": "2025-01-01", "found": 3}],
    })
    hybrid = _simulated_arm({
        5: [
            {"date": "2025-01-01", "found": 0},
            {"date": "2025-01-02", "found": 2},
        ],
        25: [{"date": "2025-01-01", "found": 4}],
    })
    simulated = {"arms": {"baseline": baseline, "hybrid": hybrid}}

    at_five = _run_simulated_view_model(simulated, 5)
    at_twenty_five = _run_simulated_view_model(simulated, 25)

    assert at_five["budgets"] == [5, 25]
    assert at_five["selected"] == 5
    assert at_five["valuesByArm"] == {
        "baseline": [1, 0],
        "hybrid": [0, 2],
    }
    assert at_twenty_five["selected"] == 25
    assert at_twenty_five["valuesByArm"] == {
        "baseline": [3],
        "hybrid": [4],
    }


def test_simulated_view_model_rejects_partial_arm_and_incomplete_budgets():
    baseline = _simulated_arm({
        5: [{"date": "2025-01-01", "found": 1}],
        25: [{"date": "2025-01-01", "found": 2}],
    })
    hybrid = _simulated_arm({25: [{"date": "2025-01-01", "found": 3}]})
    simulated = {"arms": {"baseline": baseline, "hybrid": hybrid}}

    shared = _run_simulated_view_model(simulated, 5)
    assert shared["available"] is True
    assert shared["budgets"] == [25]
    assert shared["selected"] == 25

    del hybrid["daily_f1@25"]
    unavailable = _run_simulated_view_model(simulated, 25)
    assert unavailable == {"available": False, "budgets": []}

    hybrid = _simulated_arm({25: [{"date": "2025-01-01", "found": 3}]})
    del hybrid["later_candidate_events_removed@25"]
    simulated["arms"]["hybrid"] = hybrid
    unavailable = _run_simulated_view_model(simulated, 25)
    assert unavailable == {"available": False, "budgets": []}


def test_simulated_view_model_handles_single_day_without_duplicate_ticks():
    simulated = {"arms": {
        "baseline": _simulated_arm({25: [{"date": "2025-01-01", "found": 0}]}),
        "hybrid": _simulated_arm({25: [{"date": "2025-01-01", "found": 1}]}),
    }}

    view = _run_simulated_view_model(simulated, 25)

    assert view["dates"] == ["2025-01-01"]
    assert view["dateTickIndexes"] == [0]
    assert view["yTicks"] == [0, 1]


def test_simulated_view_model_rejects_missing_or_malformed_series():
    missing = {"arms": {
        "baseline": _simulated_arm({25: [{"date": "2025-01-01", "found": 1}]}),
        "hybrid": _simulated_arm({25: [{"date": "2025-01-01", "found": 2}]}),
    }}
    del missing["arms"]["hybrid"]["daily_found_by_day@25"]
    malformed = {"arms": {
        "baseline": _simulated_arm({25: [{"date": "2025-01-01", "found": 1}]}),
        "hybrid": _simulated_arm({25: [{"date": "2025-01-01", "found": 2}]}),
    }}
    malformed["arms"]["hybrid"]["daily_found_by_day@25"] = "not-a-series"

    assert _run_simulated_view_model(None, 25) == {
        "available": False,
        "budgets": [],
    }
    assert _run_simulated_view_model(missing, 25) == {
        "available": False,
        "budgets": [],
    }
    assert _run_simulated_view_model(malformed, 25) == {
        "available": False,
        "budgets": [],
    }


def test_simulated_view_model_rejects_mismatched_daily_date_sets():
    simulated = {"arms": {
        "baseline": _simulated_arm({25: [
            {"date": "2025-01-01", "found": 1},
            {"date": "2025-01-02", "found": 0},
        ]}),
        "hybrid": _simulated_arm({25: [
            {"date": "2025-01-01", "found": 2},
        ]}),
    }}

    assert _run_simulated_view_model(simulated, 25) == {
        "available": False,
        "budgets": [],
    }


def test_simulated_view_model_rejects_duplicate_daily_dates():
    simulated = {"arms": {
        "baseline": _simulated_arm({25: [
            {"date": "2025-01-01", "found": 1},
            {"date": "2025-01-01", "found": 0},
        ]}),
        "hybrid": _simulated_arm({25: [
            {"date": "2025-01-01", "found": 2},
            {"date": "2025-01-02", "found": 0},
        ]}),
    }}

    assert _run_simulated_view_model(simulated, 25) == {
        "available": False,
        "budgets": [],
    }


def test_dashboard_script_injection_keeps_helpers_outside_tabs_registry():
    template = "const Tabs={\nexplorer:{rendered:false,render(){}}\n};"
    helper = "function buildViewModel(){}"
    renderer = "v9Results:{rendered:false,render(){}},\n"

    injected = BUILDER._inject_dashboard_tab_scripts(
        template, helper, renderer
    )

    assert injected.index(helper) < injected.index("const Tabs={")
    assert injected.index(renderer) > injected.index("const Tabs={")
    subprocess.run(
        ["node", "--check", "-"],
        input=injected,
        text=True,
        check=True,
        capture_output=True,
    )
def test_dashboard_html_embeds_data_for_direct_file_open():
    template = "const DATA = OLD;\n(async function(){\n  if(!D) return;\n"
    embedded = BUILDER._embed_dashboard_data(template, {"v9Demo": {"ready": True}})

    assert 'let DATA = {"v9Demo":{"ready":true}};' in embedded
    assert "fetch('data_v9.json')" not in embedded



def test_v9_results_injection_contains_simulated_helper_before_renderer_use():
    helper = "function buildSimulatedCatchViewModel"
    renderer_use = "function drawSimulatedCatches"

    assert helper in V9_UI.V9_RESULTS_JS
    assert V9_UI.V9_RESULTS_JS.index(helper) < V9_UI.V9_RESULTS_JS.index(
        renderer_use
    )

    template = "const Tabs={\nexplorer:{rendered:false,render(){}}\n};"
    injected = BUILDER._inject_dashboard_tab_scripts(
        template, "", V9_UI.V9_RESULTS_JS
    )
    assert injected.index(helper) < injected.index(renderer_use)


def _recovery_artifact():
    return {
        "schema_version": "1.0",
        "policy": {
            "observability_seed": 0,
            "gnn_arm": "sage",
            "surrounding_results_seeds": [0, 1, 2],
            "inspections_per_day": 25,
        },
    }


def test_load_recovery_artifact_returns_valid_json(tmp_path):
    artifact = _recovery_artifact()
    path = tmp_path / "hybrid_recovery_explanations_v9.json"
    path.write_text(json.dumps(artifact))

    assert BUILDER._load_recovery_artifact(path) == artifact


def test_load_recovery_artifact_warns_and_returns_none_when_missing(
    tmp_path, capsys
):
    path = tmp_path / "missing.json"

    assert BUILDER._load_recovery_artifact(path) is None
    assert "WARNING" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("contents", "warning"),
    [
        ("{not-json", "invalid recovery artifact"),
        (json.dumps([]), "unsupported recovery artifact schema"),
        (json.dumps({"schema_version": "2.0"}), "unsupported recovery artifact schema"),
    ],
)
def test_load_recovery_artifact_warns_and_returns_none_when_invalid(
    tmp_path, capsys, contents, warning
):
    path = tmp_path / "hybrid_recovery_explanations_v9.json"
    path.write_text(contents)

    assert BUILDER._load_recovery_artifact(path) is None
    assert warning in capsys.readouterr().out


def test_load_v9_data_uses_only_separate_recovery_artifact(
    tmp_path, monkeypatch
):
    (tmp_path / "dashboard_data.json").write_text(
        json.dumps({
            "v9RecoveryExplainer": {"stale": True},
            "v9Demo": {"recovery_overlap": {"baseline_recovered": 999}},
        })
    )
    _write_csv(tmp_path / "train_valid_test_splits.csv", [
        {"entity_id": "E1", "split": "test"},
    ])
    _write_csv(tmp_path / "crossing_events.csv", [
        {"event_id": "E1", "event_timestamp_utc": "2025-01-02T03:00:00Z"},
    ])
    artifact = _recovery_artifact()
    artifact_path = tmp_path / "hybrid_recovery_explanations_v9.json"
    artifact_path.write_text(json.dumps(artifact))
    monkeypatch.setattr(BUILDER, "V9_DATA", str(tmp_path / "dashboard_data.json"))
    monkeypatch.setattr(BUILDER, "V9_DEMO", str(tmp_path / "missing_demo.json"))
    monkeypatch.setattr(BUILDER, "V9_CORPUS", str(tmp_path))
    monkeypatch.setattr(
        BUILDER, "V9_RECOVERY_EXPLANATIONS", str(artifact_path)
    )

    assert BUILDER._load_v9_data()["v9RecoveryExplainer"] == artifact

    artifact_path.unlink()
    assert "v9RecoveryExplainer" not in BUILDER._load_v9_data()


def test_recovery_assets_are_injected_once_before_renderers_and_style_end():
    template = (
        "<style>base</style><script>const Tabs={\n"
        "explorer:{rendered:false,render(){}}\n};</script>"
    )
    recovery_js = "function buildRecoveryEvidenceViewModel(){}"
    recovery_css = ".v9-recovery{}"
    renderer = "v9Results:{rendered:false,render(){}},\n"

    injected = BUILDER._inject_recovery_assets(
        template, recovery_css, recovery_js
    )
    injected = BUILDER._inject_recovery_assets(
        injected, recovery_css, recovery_js
    )
    injected = BUILDER._inject_dashboard_tab_scripts(injected, "", renderer)

    assert injected.count(recovery_js) == 1
    assert injected.count(recovery_css) == 1
    assert injected.index(recovery_js) < injected.index(renderer)
    assert injected.index(recovery_css) < injected.index("</style>")
    subprocess.run(
        ["node", "--check", "-"],
        input=injected.split("<script>", 1)[1].split("</script>", 1)[0],
        text=True,
        check=True,
        capture_output=True,
    )


@pytest.mark.parametrize(
    "template",
    [
        (
            ".v9-recovery{}<style>base</style><script>const Tabs={\n"
            "explorer:{rendered:false,render(){}}\n};</script>"
        ),
        (
            "<style>base</style><script>const Tabs={\n"
            "explorer:{rendered:false,render(){}}\n};\n"
            "function buildRecoveryEvidenceViewModel(){}</script>"
        ),
    ],
    ids=["css-outside-style", "javascript-after-tabs"],
)
def test_recovery_assets_reject_existing_assets_in_wrong_boundaries(template):
    with pytest.raises(ValueError, match="recovery asset"):
        BUILDER._inject_recovery_assets(
            template,
            ".v9-recovery{}",
            "function buildRecoveryEvidenceViewModel(){}",
        )
