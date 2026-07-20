import csv
import copy
import errno
import importlib.util
import json
import re
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
    assert "hidden-positive event hits / day" in ui
    assert 'data-layer="hidden-carriers"' in ui
    assert 'data-layer="crossings"' in ui
    assert "v9-hidden-carriers-layer" in ui


def test_v9_ui_keeps_three_metric_lenses_without_redundant_global_table():
    ui_path = Path(__file__).resolve().parents[1] / "Documents/Data/scripts/v9_dashboard_ui.py"
    ui = ui_path.read_text()

    assert "Read the V9 result through three lenses" in ui
    assert "1. Global event ranking" in ui
    assert "2. Findable event depth" in ui
    assert "3. Daily event operations" in ui
    assert 'id="v9-pop"' in ui
    assert "Observable slice" in ui
    assert "Whole pool" in ui
    assert "Depth event recall" in ui
    assert 'id="v9-bars"' in ui
    assert (
        "Leak-safe baselines use row-level history and context. GNN arms add as-of "
        "relational signals."
    ) in ui
    assert (
        "Baselines use the target row; GNN arms add graph evidence available before scoring."
    ) in ui
    assert "The main rankings count event hits; the recovery explorer separately counts unique people." in ui
    assert "The graph advantage appears at operational depth." in ui
    assert (
        "One whole-pool top-K list, with all hidden-positive events in the recall denominator."
    ) in ui
    assert (
        "Defaults to the '+fmt(demo.stratum_hidden.observable)+'-event observable "
        "slice. Toggle for the whole pool."
    ) in ui
    assert (
        "Each of '+fmt(dailyDays)+' test days gets its own quota; 25/day equals "
        "'+fmt(dailyBudget25)+' inspections."
    ) in ui
    assert "Share of hidden-positive events hit in the selected population." in ui
    assert (
        "Found, precision, recall, and F1 under fixed per-day inspection budgets."
    ) in ui
    assert (
        "Daily test-window crossing volume and hidden-positive event hits by each model."
    ) in ui
    assert "Daily top-k event hits only. Toggle a model to show or hide its line." in ui
    assert (
        "Paired event-bootstrap results for Hybrid minus baseline, using global and daily "
        "budgets."
    ) in ui
    assert "wholeHybridAt2000" in ui
    assert "wholeBaselineAt2000" in ui
    assert "Global Found@K by selected population" not in ui
    assert 'id="v9-table"' not in ui
    assert "function drawTable()" not in ui


def test_v9_ui_labels_overall_found_counts_as_event_hits_not_people():
    ui = UI_MODULE_PATH.read_text()

    for label in (
        "Hybrid event hits",
        "Baseline event hits",
        "GNN event-hit ceiling",
        "Depth event recall",
        "hidden-positive event hits / day",
    ):
        assert label in ui
    assert "Whole-pool hidden carriers found" not in ui
    assert "observable hidden-positive events" in ui
    assert "Hidden-positive event hits" in ui
    assert "observable carriers" not in ui
    assert ">Hidden carriers<" not in ui


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

    assert "Simulated catches - first-time unique-person recoveries" in ui
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


def test_v9_ui_simulated_mode_toggle_defaults_to_cumulative():
    ui = UI_MODULE_PATH.read_text()

    assert 'id="v9-simulated-mode"' in ui
    assert 'data-v="cumulative" class="on" aria-pressed="true"' in ui
    assert 'data-v="daily" aria-pressed="false"' in ui
    assert "const accessibleName=" in ui
    assert "simMode" in ui.split("const accessibleName=", 1)[1].split(";", 1)[0]


def test_v9_ui_accessibility_table_does_not_expand_results_tab():
    assert re.search(
        r"#tab-v9Results\s+table\.v9-sr-only\s*\{[^}]*\bdisplay:\s*block\s*;",
        V9_UI.V9_RESULTS_CSS,
    )


def test_v9_ui_model_list_uses_a_shrinkable_mobile_column():
    _, separator, mobile_css = V9_UI.V9_RESULTS_CSS.partition("@media(max-width:700px){")

    assert separator
    assert re.search(
        r"#tab-v9Results\s+\.v9-model-list\s*\{[^}]*"
        r"grid-template-columns:\s*minmax\(0,\s*1fr\)\s*;",
        mobile_css,
    )


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


def test_simulated_view_model_reports_cumulative_series():
    baseline = _simulated_arm({5: [
        {"date": "2025-01-01", "found": 1},
        {"date": "2025-01-02", "found": 0},
        {"date": "2025-01-03", "found": 2},
    ]})
    hybrid = _simulated_arm({5: [
        {"date": "2025-01-01", "found": 2},
        {"date": "2025-01-02", "found": 3},
        {"date": "2025-01-03", "found": 1},
    ]})
    view = _run_simulated_view_model(
        {"arms": {"baseline": baseline, "hybrid": hybrid}}, 5
    )
    assert view["cumulativeByArm"] == {
        "baseline": [1, 1, 3],
        "hybrid": [2, 5, 6],
    }
    assert view["cumulativeMaxY"] == 6
    assert view["cumulativeTicks"] == [0, 2, 4, 6]


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


def test_v9_results_mounts_recovery_explorer_in_the_approved_story_position():
    js = V9_UI.V9_RESULTS_JS

    assert 'href="#v9-case-evidence"' in js
    assert 'id="v9-case-evidence"' in js
    assert js.count('id="v9-case-evidence"') == 1
    assert js.index('class="v9-story"') < js.index('id="v9-case-evidence"')
    assert js.index('id="v9-case-evidence"') < js.index(
        "Baseline vs Hybrid vs GNN"
    )
    assert "mountV9RecoveryExplainer(" in js
    assert "DATA.v9RecoveryExplainer" in js
    assert "DATA.explorer" not in js
    assert "ground_truth_community" not in js
    assert "community_propensity" not in js
    assert "data-navigate-tab=\"explorer\"" not in js


def test_recovery_assets_precede_renderer_that_mounts_them():
    template = (
        "<style>base</style><script>const Tabs={\n"
        "explorer:{rendered:false,render(){}}\n};</script>"
    )
    recovery_js = "function mountV9RecoveryExplainer(){}"
    recovery_css = ".v9-recovery{}"
    renderer = (
        "v9Results:{rendered:false,render(){"
        "mountV9RecoveryExplainer();}},\n"
    )

    injected = BUILDER._inject_recovery_assets(
        template, recovery_css, recovery_js
    )
    injected = BUILDER._inject_dashboard_tab_scripts(
        injected, "", renderer
    )

    assert injected.index(recovery_js) < injected.index(renderer)
    subprocess.run(
        ["node", "--check", "-"],
        input=injected.split("<script>", 1)[1].split("</script>", 1)[0],
        text=True,
        check=True,
        capture_output=True,
    )


def test_recovery_mount_validation_requires_one_local_artifact_mount():
    valid = (
        '<a href="#v9-case-evidence">Evidence</a>'
        '<section id="v9-case-evidence"></section>'
        '<script>mountV9RecoveryExplainer(node,'
        'DATA.v9RecoveryExplainer,helpers);</script>'
    )

    assert BUILDER._validate_recovery_explorer_mount(valid) == valid

    for invalid in (
        valid.replace('<section id="v9-case-evidence"></section>', ''),
        valid.replace(
            '<section id="v9-case-evidence"></section>',
            '<section id="v9-case-evidence"></section>' * 2,
        ),
        valid.replace('DATA.v9RecoveryExplainer', 'DATA.explorer'),
    ):
        with pytest.raises(ValueError, match="recovery explorer mount"):
            BUILDER._validate_recovery_explorer_mount(invalid)


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
    ],
)
def test_load_recovery_artifact_warns_and_returns_none_when_invalid(
    tmp_path, capsys, contents, warning
):
    path = tmp_path / "hybrid_recovery_explanations_v9.json"
    path.write_text(contents)

    assert BUILDER._load_recovery_artifact(path) is None
    assert warning in capsys.readouterr().out


def test_load_recovery_artifact_fails_closed_for_present_invalid_schema_v2(tmp_path):
    path = tmp_path / "hybrid_recovery_explanations_v9.json"
    path.write_text(json.dumps({"schema_version": "2.0"}))

    with pytest.raises(ValueError, match="schema-2 recovery artifact"):
        BUILDER._load_recovery_artifact(path)


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


def _schema_v2_recovery_artifact():
    shared_community = {
        "community_key": "2025-01-02:component-7",
        "scoring_day": "2025-01-02T00:00:00Z",
        "component_id": "component-7",
        "complete": True,
        "nodes": [
            {"node_id": "p1", "target": True, "pooled_member": True},
            {"node_id": "p2", "target": False, "pooled_member": True},
        ],
        "edges": [
            {
                "edge_id": "e2",
                "u": "p2",
                "v": "p1",
                "edge_type": "RESIDENCE",
                "source_row_ids": ["row-2"],
                "source_row_count": 1,
                "observations": [{"source_row_id": "row-2", "available_time": "2025-01-01T11:00:00Z"}],
            },
            {
                "edge_id": "e1",
                "u": "p1",
                "v": "p2",
                "edge_type": "COTRAVEL",
                "source_row_ids": ["row-1a", "row-1b"],
                "source_row_count": 2,
                "observations": [
                    {"source_row_id": "row-1a", "available_time": "2025-01-01T09:00:00Z"},
                    {"source_row_id": "row-1b", "available_time": "2025-01-01T10:00:00Z"},
                ],
            },
        ],
        "provenance_expansions": [
            {
                "expansion_id": "expansion-1",
                "label": "outside message community",
                "nodes": [{"node_id": "p3"}],
                "edges": [{
                    "edge_id": "e3", "u": "p2", "v": "p3",
                    "edge_type": "SHARED_PLATE",
                    "source_row_ids": ["row-3"], "source_row_count": 1,
                    "observations": [{"source_row_id": "row-3", "available_time": "2025-01-01T12:00:00Z"}],
                }],
            }
        ],
    }
    return {
        "schema_version": "2.0",
        "policy": {
            "observability_seed": 0,
            "inspections_per_day": 5,
            "gnn_arm": "sage",
            "surrounding_results_seeds": [0, 1, 2],
        },
        "summary": {
            "baseline_recovered": 1,
            "recovered_by_both": 0,
            "hybrid_only_recovered": 1,
            "baseline_only_recovered": 1,
            "hybrid_total": 1,
            "net_gain": 0,
        },
        "coverage": {
            "hybrid_only_count": 1,
            "baseline_only_count": 1,
            "explained_count": 1,
            "llm_validated_count": 1,
            "failed_count": 0,
            "complete": True,
        },
        "cohorts": {
            "hybrid_only": [
                {
                    "case_id": "hybrid:p1",
                    "person_id": "p1",
                    "event_id": "crossing-1",
                    "scoring_day": "2025-01-02T00:00:00Z",
                    "community_key": "2025-01-02:component-7",
                    "baseline_rank": 20,
                    "seed0_gnn_rank": 2,
                    "seed0_hybrid_rank": 4,
                }
            ],
            "baseline_only": [
                {
                    "case_id": "baseline:p2",
                    "person_id": "p2",
                    "event_id": "crossing-2",
                    "scoring_day": "2025-01-02T00:00:00Z",
                    "community_key": "2025-01-02:component-7",
                    "baseline_rank": 3,
                    "seed0_gnn_rank": 30,
                    "seed0_hybrid_rank": 18,
                }
            ],
        },
        "explanations": [
            {
                "case_id": "hybrid:p1",
                "community_key": "2025-01-02:component-7",
                "llm_narrative": {
                    "source": "llm",
                    "model": "gemma4:12b",
                    "validated": True,
                    "summary": "Local narrative.",
                },
                "attributions": {
                    "top_edges": [{"edge_id": "e1", "explainer_median": 0.8}],
                    "top_local_nodes": [{"node_id": "p2", "explainer_median": 0.7}],
                    "top_features": [{"feature_name": "caught_before_snapshot", "node_id": "p2", "explainer_median": 0.6}],
                },
                "decision_ledger": {
                    "component_pooling": {"top_members_by_absolute_contribution": [{"person_id": "p2", "pooled_logit_contribution": 0.4}]},
                    "rank_fusion": {"daily_budget": 5, "baseline_weighted_term": 0.2, "seed0_gnn_weighted_term": 0.5, "hybrid_score": 0.7},
                },
            }
        ],
        "communities": [shared_community],
    }


def _load_recovery_sidecars_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "Documents/Data/scripts/v9_recovery_sidecars.py"
    )
    assert module_path.exists(), "recovery sidecar packager is missing"
    spec = importlib.util.spec_from_file_location("v9_recovery_sidecars", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _writer_shaped_recovery_bundle(tmp_path):
    module_path = Path(__file__).resolve().parents[1] / "gnn/recovery_bundle.py"
    spec = importlib.util.spec_from_file_location("recovery_bundle", module_path)
    recovery_bundle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recovery_bundle)
    RecoveryBundleWriter = recovery_bundle.RecoveryBundleWriter

    source_root = tmp_path / "producer"
    writer = RecoveryBundleWriter(
        tmp_path / "producer-stage",
        source_root / "recovery",
        run_fingerprint={"seed": 0, "k": 5},
        chunk_size=1,
        sidecar_prefix="recovery",
    )
    community = {
        "community_key": "community:a",
        "complete": True,
        "scoring_day": "2025-01-02T00:00:00+00:00",
        "component_id": "component-7",
        "nodes": [
            {"node_id": "person:p1", "kind": "person"},
            {"node_id": "plate:x", "kind": "plate"},
        ],
        "edges": [{
            "edge_id": "edge:1",
            "u": "person:p1",
            "v": "plate:x",
            "edge_type": "used_plate",
            "source_row_ids": ["row:1"],
            "source_row_count": 1,
            "observations": [{
                "source_row_id": "row:1",
                "available_time": "2025-01-01",
            }],
        }],
        "provenance_expansions": [{
            "expansion_id": "expansion:1",
            "label": "shared plate history",
            "nodes": [{"node_id": "person:p2", "kind": "person"}],
            "edges": [{
                "edge_id": "edge:2",
                "u": "person:p2",
                "v": "plate:x",
                "edge_type": "used_plate",
                "source_row_ids": ["row:2"],
                "source_row_count": 1,
                "observations": [{
                    "source_row_id": "row:2",
                    "available_time": "2024-12-31",
                }],
            }],
        }],
    }
    writer.write_community(community)
    hybrid_case = {
        "case_id": "case:h1",
        "person_id": "p1",
        "event_id": "event:h1",
        "community_key": "community:a",
        "scoring_day": community["scoring_day"],
    }
    explanation = {
        **hybrid_case,
        "attributions": {"top_edges": []},
        "llm_narrative": {
            "source": "llm",
            "model": "gemma4:12b",
            "validated": True,
            "prompt_version": "v1",
            "summary": "Grounded summary.",
            "summary_source_refs": ["edge:1"],
            "claims": [{"text": "Grounded claim.", "source_refs": ["edge:1"]}],
        },
    }
    overlay = {
        "nodes": [{"node_id": "person:overlay", "kind": "person"}],
        "edges": [{
            "edge_id": "overlay-edge:1",
            "u": "person:overlay",
            "v": "plate:x",
            "edge_type": "attributed_used_plate",
            "source_row_ids": ["overlay-row:1"],
            "source_row_count": 1,
            "observations": [{
                "source_row_id": "overlay-row:1",
                "available_time": "2025-01-01",
            }],
        }],
        "provenance_expansions": [{
            "expansion_id": "overlay-expansion:1",
            "label": "overlay neighbor",
            "nodes": [{"node_id": "person:overlay-neighbor", "kind": "person"}],
            "edges": [{
                "edge_id": "overlay-edge:2",
                "u": "person:overlay-neighbor",
                "v": "plate:x",
                "edge_type": "attributed_used_plate",
                "source_row_ids": ["overlay-row:2"],
                "source_row_count": 1,
                "observations": [{
                    "source_row_id": "overlay-row:2",
                    "available_time": "2024-12-31",
                }],
            }],
        }],
    }
    writer.write_case(
        "hybrid_only",
        hybrid_case,
        explanation=explanation,
        overlay_evidence=overlay,
    )
    baseline_case = {
        "case_id": "case:b1",
        "person_id": "p3",
        "event_id": "event:b1",
        "community_key": "community:a",
        "scoring_day": community["scoring_day"],
    }
    writer.write_case("baseline_only", baseline_case)
    seed_summary = {
        "inspections_per_day": 5,
        "common_validation_tuned_fusion_weight": 0.75,
        "seeds": {
            "0": {"hybrid_unique_people_recovered": 1},
            "1": {"hybrid_unique_people_recovered": 1},
            "2": {"hybrid_unique_people_recovered": 1},
        },
        "mean": {"hybrid_unique_people_recovered": 1.0},
        "population_sd": {"hybrid_unique_people_recovered": 0.0},
        "score_averaged_ensemble": {"hybrid_unique_people_recovered": 1},
    }
    manifest = writer.finalize(
        expected_hybrid_case_ids=["case:h1"],
        expected_baseline_case_ids=["case:b1"],
        policy={
            "observability_seed": 0,
            "inspections_per_day": 5,
            "gnn_arm": "sage",
            "surrounding_results_seeds": [0, 1, 2],
        },
        summary={
            "baseline_recovered": 1,
            "recovered_by_both": 0,
            "hybrid_only_recovered": 1,
            "baseline_only_recovered": 1,
            "hybrid_total": 1,
            "net_gain": 0,
            "seed_level_unique_person_recovery": seed_summary,
        },
    )
    artifact_path = source_root / "manifest.json"
    artifact_path.write_text(json.dumps(manifest))
    return manifest, artifact_path


def test_schema_v2_sidecar_packager_is_deterministic_deduplicated_and_manifest_only(
    tmp_path,
):
    sidecars = _load_recovery_sidecars_module()
    artifact = _schema_v2_recovery_artifact()

    first = sidecars.package_recovery_sidecars(
        artifact, tmp_path / "recovery", chunk_size=1
    )
    second = sidecars.package_recovery_sidecars(
        artifact, tmp_path / "recovery", chunk_size=1
    )

    assert first == second
    assert first["schema_version"] == "2.0"
    assert first["policy"]["inspections_per_day"] == 5
    assert "explanations" not in first
    assert "communities" not in first
    assert set(first["case_index"]) == {"hybrid:p1", "baseline:p2"}
    assert len(first["community_index"]) == 1
    assert first["case_index"]["hybrid:p1"]["cohort"] == "hybrid_only"
    assert first["case_index"]["baseline:p2"]["cohort"] == "baseline_only"

    bundle_dir = tmp_path / "recovery" / first["bundle_path"]
    community_ref = next(iter(first["community_index"].values()))
    community = json.loads((bundle_dir / community_ref["path"]).read_text())
    assert community["complete"] is True
    assert community["node_count"] == 3
    assert community["edge_count"] == 3
    assert community["provenance_observation_count"] == 4
    assert len(community["edge_chunks"]) == 3
    assert len(community["provenance_chunks"]) == 4
    assert community["provenance_expansions"] == [{
        "expansion_id": "expansion-1",
        "label": "outside message community",
        "node_ids": ["p3"],
        "edge_ids": ["e3"],
    }]
    assert all("sha256" in chunk and "path" in chunk for chunk in community["edge_chunks"])
    edge_payload = json.loads((bundle_dir / community["edge_chunks"][0]["path"]).read_text())
    assert "observations" not in edge_payload["edges"][0]
    assert edge_payload["edges"][0]["source_row_count"] == len(
        edge_payload["edges"][0]["source_row_ids"]
    )
    provenance = []
    for chunk in community["provenance_chunks"]:
        provenance.extend(json.loads((bundle_dir / chunk["path"]).read_text())["observations"])
    assert {row["edge_id"] for row in provenance} == {"e1", "e2", "e3"}
    assert json.loads((tmp_path / "recovery/current.json").read_text())["bundle_id"] == first["bundle_id"]


def test_schema_v2_packaging_failure_keeps_prior_bundle_pointer(tmp_path):
    sidecars = _load_recovery_sidecars_module()
    output = tmp_path / "recovery"
    sidecars.package_recovery_sidecars(_schema_v2_recovery_artifact(), output)
    prior_pointer = (output / "current.json").read_bytes()
    invalid = _schema_v2_recovery_artifact()
    invalid["communities"][0]["complete"] = False

    with pytest.raises(ValueError):
        sidecars.package_recovery_sidecars(invalid, output)

    assert (output / "current.json").read_bytes() == prior_pointer


def test_schema_v2_sidecar_packager_rejects_incomplete_coverage(tmp_path):
    sidecars = _load_recovery_sidecars_module()
    artifact = _schema_v2_recovery_artifact()
    artifact["coverage"]["llm_validated_count"] = 0

    with pytest.raises(ValueError, match="coverage"):
        sidecars.package_recovery_sidecars(artifact, tmp_path / "recovery")


def test_schema_v2_sidecar_packager_rejects_unvalidated_hybrid_narrative(tmp_path):
    sidecars = _load_recovery_sidecars_module()
    artifact = _schema_v2_recovery_artifact()
    artifact["explanations"][0]["llm_narrative"]["validated"] = False

    with pytest.raises(ValueError, match="validated local Gemma"):
        sidecars.package_recovery_sidecars(artifact, tmp_path / "recovery")


def test_builder_rejects_raw_schema_v2_recovery_without_producer_bundle(
    tmp_path, monkeypatch
):
    artifact = _schema_v2_recovery_artifact()
    artifact_path = tmp_path / "recovery.json"
    artifact_path.write_text(json.dumps(artifact))
    monkeypatch.setattr(BUILDER, "OUT_DIR", str(tmp_path / "dashboard"))

    with pytest.raises(ValueError, match="prepackaged producer bundle"):
        BUILDER._load_recovery_artifact(artifact_path)


def test_builder_atomically_publishes_prepackaged_schema_v2_manifest(
    tmp_path, monkeypatch
):
    manifest, artifact_path = _writer_shaped_recovery_bundle(tmp_path)
    dashboard = tmp_path / "dashboard"
    monkeypatch.setattr(BUILDER, "OUT_DIR", str(dashboard))

    published = BUILDER._load_recovery_artifact(artifact_path)

    assert published == manifest
    copied_bundle = dashboard / "recovery" / published["bundle_path"]
    assert (copied_bundle / "manifest.json").exists()
    assert json.loads((dashboard / "recovery/current.json").read_text())[
        "bundle_id"
    ] == published["bundle_id"]
    source_bundle = artifact_path.parent / manifest["sidecar_base"]
    community_ref = next(iter(manifest["community_index"].values()))
    community = json.loads((source_bundle / community_ref["path"]).read_text())
    for field in (
        "node_chunks",
        "edge_chunks",
        "provenance_chunks",
        "provenance_expansion_membership_chunks",
    ):
        assert all((copied_bundle / ref["path"]).is_file() for ref in community[field])

    hybrid_ref = manifest["case_index"]["case:h1"]
    hybrid_payload = json.loads((source_bundle / hybrid_ref["path"]).read_text())
    overlay = hybrid_payload["overlay_evidence"]
    for field in (
        "node_chunks",
        "edge_chunks",
        "provenance_chunks",
        "provenance_expansion_membership_chunks",
    ):
        assert all((copied_bundle / ref["path"]).is_file() for ref in overlay[field])


def test_prepackaged_overlay_corruption_preserves_prior_pointer(tmp_path, monkeypatch):
    manifest, artifact_path = _writer_shaped_recovery_bundle(tmp_path)
    dashboard = tmp_path / "dashboard"
    monkeypatch.setattr(BUILDER, "OUT_DIR", str(dashboard))
    BUILDER._load_recovery_artifact(artifact_path)
    pointer_path = dashboard / "recovery/current.json"
    prior_pointer = pointer_path.read_bytes()

    source_bundle = artifact_path.parent / manifest["sidecar_base"]
    hybrid_ref = manifest["case_index"]["case:h1"]
    hybrid_payload = json.loads((source_bundle / hybrid_ref["path"]).read_text())
    corrupt_ref = hybrid_payload["overlay_evidence"]["node_chunks"][0]
    (source_bundle / corrupt_ref["path"]).write_text("{}")

    with pytest.raises(ValueError, match="hash mismatch"):
        BUILDER._load_recovery_artifact(artifact_path)

    assert pointer_path.read_bytes() == prior_pointer


@pytest.mark.parametrize(
    "mutate",
    [
        lambda manifest: manifest.update(bundle_id="not-a-producer-id"),
        lambda manifest: manifest.update(bundle_path="bundles/other"),
        lambda manifest: manifest.update(sidecar_base="recovery/bundles/../"),
        lambda manifest: manifest.update(
            sidecar_base="recovery/bundles/abcdefabcdefabcdefabcdef/"
        ),
    ],
    ids=["invalid-id", "path-mismatch", "dot-segment", "base-mismatch"],
)
def test_prepackaged_manifest_requires_canonical_bundle_identity(
    tmp_path, mutate
):
    sidecars = _load_recovery_sidecars_module()
    manifest, artifact_path = _writer_shaped_recovery_bundle(tmp_path)
    mutate(manifest)

    with pytest.raises(ValueError, match="canonical bundle identity"):
        sidecars.publish_prepackaged_manifest(
            manifest, artifact_path, tmp_path / "dashboard/recovery"
        )


def test_prepackaged_publication_isolates_verified_files_and_mutable_current(
    tmp_path, monkeypatch
):
    manifest, artifact_path = _writer_shaped_recovery_bundle(tmp_path)
    source_bundle = artifact_path.parent / manifest["sidecar_base"]
    mutable_source = source_bundle / "current.json"
    mutable_source.write_text('{"mutable":true}')
    dashboard = tmp_path / "dashboard"
    monkeypatch.setattr(BUILDER, "OUT_DIR", str(dashboard))

    published = BUILDER._load_recovery_artifact(artifact_path)

    copied_bundle = dashboard / "recovery" / published["bundle_path"]
    community_ref = next(iter(manifest["community_index"].values()))
    source_object = source_bundle / community_ref["path"]
    copied_object = copied_bundle / community_ref["path"]
    source_bytes = source_object.read_bytes()
    assert source_object.stat().st_ino != copied_object.stat().st_ino
    assert mutable_source.stat().st_ino != (copied_bundle / "current.json").stat().st_ino
    copied_object.write_text("{}")
    assert source_object.read_bytes() == source_bytes


def test_prepackaged_publication_copies_when_cow_clone_is_unsupported(
    tmp_path, monkeypatch
):
    sidecars = _load_recovery_sidecars_module()
    manifest, artifact_path = _writer_shaped_recovery_bundle(tmp_path)
    source_bundle = artifact_path.parent / manifest["sidecar_base"]
    calls = []

    def unsupported_clone(source, destination):
        calls.append((source, destination))
        raise OSError(errno.ENOTSUP, "clone unsupported")

    monkeypatch.setattr(sidecars.os, "clonefile", unsupported_clone, raising=False)
    monkeypatch.setattr(
        sidecars.os,
        "link",
        lambda *_: (_ for _ in ()).throw(AssertionError("hard links are unsafe")),
    )
    output = tmp_path / "dashboard/recovery"

    published = sidecars.publish_prepackaged_manifest(
        manifest, artifact_path, output
    )

    copied_bundle = output / published["bundle_path"]
    community_ref = next(iter(manifest["community_index"].values()))
    assert calls
    assert (source_bundle / community_ref["path"]).stat().st_ino != (
        copied_bundle / community_ref["path"]
    ).stat().st_ino
    assert json.loads((output / "current.json").read_text())["bundle_id"] == (
        manifest["bundle_id"]
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda artifact: artifact["policy"].update(gnn_arm="rgcn"),
        lambda artifact: artifact["policy"].update(surrounding_results_seeds=[0, 2]),
        lambda artifact: artifact["summary"].update(net_gain=99),
        lambda artifact: artifact["cohorts"]["baseline_only"].__setitem__(
            0, artifact["cohorts"]["hybrid_only"][0]
        ),
        lambda artifact: artifact["case_index"].pop("case:b1"),
        lambda artifact: artifact["case_index"]["case:h1"].update(
            cohort="baseline_only"
        ),
        lambda artifact: artifact["case_index"]["case:h1"].update(
            community_key="community:other"
        ),
    ],
    ids=[
        "wrong-gnn-arm",
        "wrong-surrounding-seeds",
        "broken-overlap-algebra",
        "overlapping-case-ids",
        "incomplete-case-index",
        "case-index-cohort-mismatch",
        "case-index-community-mismatch",
    ],
)
def test_compact_manifest_validation_fails_closed(tmp_path, mutate):
    sidecars = _load_recovery_sidecars_module()
    manifest, _ = _writer_shaped_recovery_bundle(tmp_path)
    invalid = copy.deepcopy(manifest)
    mutate(invalid)

    with pytest.raises(ValueError):
        sidecars._validate_artifact(invalid)


def test_dashboard_directory_swap_rolls_back_all_public_files_on_failure(
    tmp_path, monkeypatch
):
    destination = tmp_path / "dashboard"
    staged = tmp_path / "staged"
    for root, marker in ((destination, "old"), (staged, "new")):
        (root / "recovery").mkdir(parents=True)
        (root / "data_v9.json").write_text(marker + "-data")
        (root / "index.html").write_text(marker + "-html")
        (root / "recovery/current.json").write_text(marker + "-pointer")
    real_replace = BUILDER.os.replace

    def fail_staged_publish(source, target):
        if Path(source) == staged and Path(target) == destination:
            raise OSError("injected dashboard publish failure")
        return real_replace(source, target)

    monkeypatch.setattr(BUILDER.os, "replace", fail_staged_publish)

    with pytest.raises(OSError, match="injected dashboard publish failure"):
        BUILDER._publish_staged_dashboard(staged, destination)

    assert (destination / "data_v9.json").read_text() == "old-data"
    assert (destination / "index.html").read_text() == "old-html"
    assert (destination / "recovery/current.json").read_text() == "old-pointer"


def test_dashboard_generation_failure_removes_unpublished_staging_directory(
    tmp_path, monkeypatch
):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "dashboard_standalone.html").write_text("unused")
    output = tmp_path / "v9_dashboard"
    output.mkdir()
    (output / "index.html").write_text("old")
    monkeypatch.setattr(BUILDER, "V9_CORPUS", str(corpus))
    monkeypatch.setattr(BUILDER, "OUT_DIR", str(output))
    monkeypatch.setattr(
        BUILDER,
        "_load_v9_data",
        lambda **_: (_ for _ in ()).throw(ValueError("injected generation failure")),
    )

    with pytest.raises(ValueError, match="injected generation failure"):
        BUILDER.main()

    assert (output / "index.html").read_text() == "old"
    assert list(tmp_path.glob(".v9_dashboard.stage-*")) == []


def test_dashboard_final_log_requires_http_for_schema_v2():
    source = MODULE_PATH.read_text()

    assert "python -m http.server 8000 --directory Documents/Data/v9_dashboard" in source
    assert "open v9_dashboard/index.html directly" not in source
ROOT = Path(__file__).resolve().parents[1]
GENERATED_INDEX = ROOT / "Documents/Data/v9_dashboard/index.html"


def _run_unsupervised_view_model(payload):
    assert hasattr(V9_UI, "UNSUP_AD_VIEW_MODEL_JS")
    script = (
        V9_UI.UNSUP_AD_VIEW_MODEL_JS
        + "\nprocess.stdout.write(JSON.stringify(buildUnsupervisedADViewModel("
        + json.dumps(payload)
        + ")));"
    )
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _render_unsupervised_html(payload):
    script = (
        V9_UI.UNSUP_AD_VIEW_MODEL_JS
        + "\nconst DATA={unsupervisedAD:"
        + json.dumps(payload)
        + "};"
        + "\nconst section={innerHTML:''};"
        + "\nconst document={getElementById:()=>section};"
        + "\nconst esc=value=>String(value);"
        + "\nconst Tabs={"
        + V9_UI.UNSUP_AD_JS
        + "};"
        + "\nTabs.unsupervisedAD.render();"
        + "\nprocess.stdout.write(section.innerHTML);"
    )
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def _schema_v3_payload(corpus_name="synthetic_cbp_graph_corpus_v9", marker=None):
    return {
        "schema_version": 3,
        "provenance": {"corpus_name": corpus_name},
        "marker": marker,
        "primary_arm_order": [
            "tabular_unlabeled",
            "relational_unlabeled",
            "relational_caught_supervised",
        ],
        "ablation_arm_order": ["tabular_caught_supervised"],
        "arm_metadata": {},
        "arms": {},
        "legacy_oracle_benchmarks": {},
    }


def test_v9_unsupervised_loader_prefers_corpus_qualified_artifact(tmp_path):
    generic = _schema_v3_payload(marker="generic")
    qualified = _schema_v3_payload(marker="qualified")
    (tmp_path / "unsupervised_ad_results.json").write_text(json.dumps(generic))
    (tmp_path / "unsupervised_ad_results_v9.json").write_text(
        json.dumps(qualified)
    )

    loaded = BUILDER._load_v9_unsupervised_artifact(tmp_path)

    assert loaded["marker"] == "qualified"


def test_v9_unsupervised_loader_warns_on_legacy_generic_fallback(
    tmp_path, capsys
):
    legacy = {"schema_version": 2, "modes": {"strict": {}, "assisted": {}}}
    (tmp_path / "unsupervised_ad_results.json").write_text(json.dumps(legacy))

    loaded = BUILDER._load_v9_unsupervised_artifact(tmp_path)

    assert loaded == legacy
    assert "legacy schema-v2 generic fallback" in capsys.readouterr().out.lower()


def test_v9_unsupervised_loader_warns_on_legacy_qualified_artifact(
    tmp_path, capsys
):
    legacy = {"schema_version": 2, "modes": {"strict": {}, "assisted": {}}}
    (tmp_path / "unsupervised_ad_results_v9.json").write_text(
        json.dumps(legacy)
    )

    loaded = BUILDER._load_v9_unsupervised_artifact(tmp_path)

    assert loaded == legacy
    warning = capsys.readouterr().out.lower()
    assert "legacy schema-v2" in warning
    assert "provenance cannot verify the v9 corpus" in warning


@pytest.mark.parametrize(
    ("filename", "corpus_name"),
    [
        ("unsupervised_ad_results_v9.json", "synthetic_cbp_graph_corpus_v8"),
        ("unsupervised_ad_results_v9.json", "synthetic_cbp_graph_corpus_v9dev"),
        ("unsupervised_ad_results.json", "synthetic_cbp_graph_corpus_v8"),
        ("unsupervised_ad_results.json", "synthetic_cbp_graph_corpus_v9dev"),
    ],
)
def test_v9_unsupervised_loader_rejects_schema_v3_wrong_corpus(
    tmp_path, filename, corpus_name
):
    (tmp_path / filename).write_text(
        json.dumps(_schema_v3_payload(corpus_name=corpus_name))
    )

    with pytest.raises(ValueError, match="V9 dashboard.*wrong corpus"):
        BUILDER._load_v9_unsupervised_artifact(tmp_path)


def test_v9_unsupervised_loader_rejects_malformed_schema_v3_provenance(
    tmp_path,
):
    payload = _schema_v3_payload()
    payload["provenance"] = "not-an-object"
    (tmp_path / "unsupervised_ad_results_v9.json").write_text(
        json.dumps(payload)
    )

    with pytest.raises(ValueError, match="V9 dashboard.*wrong corpus"):
        BUILDER._load_v9_unsupervised_artifact(tmp_path)


def test_schema_v3_view_model_uses_artifact_order_and_quarantines_appendices():
    payload = _schema_v3_payload()
    payload["primary_arm_order"] = [
        "relational_unlabeled",
        "tabular_unlabeled",
        "relational_caught_supervised",
        "assisted",
    ]
    payload["arm_metadata"] = {
        arm_id: {"label": arm_id}
        for arm_id in (
            "tabular_unlabeled",
            "relational_unlabeled",
            "relational_caught_supervised",
            "tabular_caught_supervised",
        )
    }
    completed = {
        "status": "completed",
        "feature_count": 18,
        "scored_test": {"threshold": 0.42},
        "threshold_metadata": {
            "threshold_source": "validation_score_quantile",
            "quantile": 0.9,
            "threshold_comparator": ">=",
            "realized_test_alert_rate": 0.1,
        },
        "label_metadata": {
            "caught_positive_count": 17,
            "immature_label_count": 3,
        },
        "evaluation_only": {
            "all_carrier_events": {"recall": None, "precision": None},
            "missed_at_event": {"recall": None, "precision": None},
            "no_prior_catch_missed_events": {"recall": None},
            "lifetime_never_caught_people": {"recall": None, "found": None},
            "observed_catch_enrichment": {
                "precision": None,
                "lift_over_prevalence": None,
            },
        },
    }
    payload["arms"] = {
        "relational_unlabeled": {
            "Southwest": completed,
            "Skipped": {"status": "skipped", "skip_reason": "too few rows"},
        },
        "tabular_unlabeled": {},
        "relational_caught_supervised": {},
        "tabular_caught_supervised": {},
        "assisted": {"must_not_render": {}},
    }
    payload["legacy_oracle_benchmarks"] = {
        "assisted": {"nondeployable": True, "is_ceiling": False, "results": {}}
    }

    view = _run_unsupervised_view_model(payload)

    assert view["primaryArmIds"] == [
        "relational_unlabeled",
        "tabular_unlabeled",
        "relational_caught_supervised",
    ]
    assert view["ablationArmIds"] == ["tabular_caught_supervised"]
    assert "assisted" not in view["primaryArmIds"]
    assert view["primary"][0]["regions"][0]["metrics"][
        "allCarrierRecall"
    ] is None
    assert view["primary"][0]["regions"][0]["metrics"][
        "frozenThreshold"
    ] == pytest.approx(0.42)
    assert view["primary"][0]["regions"][1] == {
        "region": "Skipped",
        "status": "skipped",
        "skipReason": "too few rows",
    }
    assert view["legacyAssisted"]["nondeployable"] is True
    assert view["legacyAssisted"]["is_ceiling"] is False


def test_schema_v3_ui_copy_and_metric_contracts_are_honest():
    ui = UI_MODULE_PATH.read_text()
    lowered = ui.lower()

    for token in (
        "caught-supervised",
        "naive PU",
        "operating-point policy",
        "conditional on resolved identity",
        "observed-catch enrichment",
        "no SCAR ranking guarantee",
        "oracle evaluation is unavailable in production",
        "V9 designed positive control",
    ):
        assert token.lower() in lowered

    for label in (
        "Fit signal",
        "Feature count",
        "Threshold source",
        "Frozen threshold",
        "Validation quantile",
        "Comparator",
        "Realized test alert rate",
        "Caught positives / immature",
        "All-carrier recall / precision",
        "Missed-at-event recall / precision",
        "No-prior-catch missed recall",
        "Lifetime-never-caught person recall / found",
        "Observed-catch enrichment precision / lift",
    ):
        assert label in ui

    assert "ad.primary_arm_order" in ui
    assert "ad.ablation_arm_order" in ui
    assert "ad.arms" in ui
    assert "Legacy oracle-assisted diagnostic" in ui
    assert "nondeployable" in lowered
    assert "not a ceiling" in lowered
    assert "status==='skipped'" in ui
    assert "metric===null" in ui

    for forbidden in (
        "scores are probabilities",
        "calibrated identically",
        "same true-carrier ranking",
        "oracle ceiling",
    ):
        assert forbidden not in lowered


def test_schema_v3_renderer_separates_ablation_and_legacy_sections():
    payload = _schema_v3_payload()
    payload["arm_metadata"] = {
        arm_id: {"label": arm_id, "feature_count": 14}
        for arm_id in (
            "tabular_unlabeled",
            "relational_unlabeled",
            "relational_caught_supervised",
            "tabular_caught_supervised",
        )
    }
    payload["arms"] = {
        arm_id: {}
        for arm_id in (
            "tabular_unlabeled",
            "relational_unlabeled",
            "relational_caught_supervised",
            "tabular_caught_supervised",
        )
    }
    payload["legacy_oracle_benchmarks"] = {
        "assisted": {
            "nondeployable": True,
            "is_ceiling": False,
            "description": "legacy fixture",
            "results": {},
        }
    }

    html = _render_unsupervised_html(payload)

    appendix_start = html.index('<div class="uad-appendix">')
    legacy_start = html.index('<div class="uad-legacy">')
    appendix = html[appendix_start:legacy_start]
    assert "tabular_caught_supervised" in appendix
    assert "Legacy oracle-assisted diagnostic" not in appendix
    assert html[legacy_start - len("</div>"):legacy_start] == "</div>"
    assert "Legacy oracle-assisted diagnostic" in html[legacy_start:]
    assert "nondeployable" in html[legacy_start:]
    assert "not a ceiling" in html[legacy_start:]


def test_schema_v2_ui_fallback_remains_explicitly_legacy():
    ui = UI_MODULE_PATH.read_text()

    assert "renderLegacySchemaV2" in ui
    assert "ad.modes||ad.results" in ui
    assert "Strict unsupervised" in ui
    assert "Legacy oracle-assisted diagnostic" in ui
    assert "nondeployable" in ui.lower()
    assert "not a ceiling" in ui.lower()
    assert "const modeHeading=mode==='assisted'?title:" in ui


def test_v9_research_log_records_caught_supervised_contract():
    log = (ROOT / "Documents/Data/changes_3.md").read_text()

    for token in (
        "tabular_unlabeled",
        "relational_unlabeled",
        "relational_caught_supervised",
        "tabular_caught_supervised",
        "50.9%",
        "27.4%",
        "229",
        "79",
        "8,013",
        "28 days",
        "2,691",
        "213",
        "immature -> unlabeled",
        "operating point",
        "conditional on resolved identity",
        "not a ceiling",
        "retrospective corpus diagnostics",
        "not fit inputs",
    ):
        assert token.lower() in log.lower()


def test_generated_dashboard_v9_bootstrap_does_not_require_d3():
    html = (
        Path(__file__).resolve().parents[1]
        / "Documents/Data/v9_dashboard/index.html"
    ).read_text()

    assert "const tip=document.createElement('div')" in html
    assert "const tip=d3.select('body')" not in html


def test_generated_dashboard_has_grouped_accessible_navigation_and_hash_state():
    html = GENERATED_INDEX.read_text()

    assert 'data-nav-group="readout"' in html
    assert 'data-nav-group="explore"' in html
    assert 'aria-controls="tab-v9Results"' in html
    assert 'aria-selected="true"' in html
    assert "location.hash" in html
    assert "hashchange" in html
    assert "closest('[data-navigate-tab]')" in html


def test_generated_dashboard_has_v9_headline_and_responsive_table_contract():
    html = GENERATED_INDEX.read_text()

    assert 'id="v9-summary"' in html
    assert "Deployable Hybrid" in html
    assert ".v9-table-wrap" in html
    assert "font-family: var(--font-body)" in html


def test_generated_dashboard_removes_legacy_duplicate_sections_and_styles():
    html = GENERATED_INDEX.read_text()

    assert html.count('data-tab="entityResolution"') == 0
    assert html.count("entityResolution:{rendered:false") == 0
    assert html.count("/* ---- Community Explorer ---- */") == 1


def test_unsupervised_dashboard_explains_modes_and_leakage_boundaries():
    ui_path = Path(__file__).resolve().parents[1] / "Documents/Data/scripts/v9_dashboard_ui.py"
    ui = ui_path.read_text()

    assert "Strict unsupervised" in ui
    assert "Label-assisted benchmark" in ui
    assert "validation set" in ui
    assert "test set" in ui
    assert "labels_used_for_fit" in ui
    assert "positive_prevalence" in ui
    assert "predicted_positive_rate" in ui
