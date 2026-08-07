import csv
from html.parser import HTMLParser
import importlib.util
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from test_recovery_bundle import _schema3_sidecar_artifact
from scripts.dashboard import v9_recovery_sidecars


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "dashboard" / "build_v9_dashboard.py"
SPEC = importlib.util.spec_from_file_location("build_v9_dashboard", MODULE_PATH)
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)

UI_MODULE_PATH = ROOT / "scripts" / "dashboard" / "v9_dashboard_ui.py"
UI_SPEC = importlib.util.spec_from_file_location("v9_dashboard_ui", UI_MODULE_PATH)
V9_UI = importlib.util.module_from_spec(UI_SPEC)
UI_SPEC.loader.exec_module(V9_UI)


@pytest.fixture(autouse=True)
def _clear_schema3_results_override(monkeypatch):
    """Keep host-level recovery overrides from affecting fixture-backed tests."""
    monkeypatch.delenv("V9_SCHEMA3_RESULTS_ZIP", raising=False)


# Frozen from the pre-architecture V9 Results renderer.  Keep these explicit
# (rather than deriving them from the implementation) so additive integration
# cannot silently reorder or drop an existing mount target.
FROZEN_V9_RESULT_IDS = (
    "v9-summary",
    "v9-story-title",
    "v9-daily-found-k",
    "v9-volume",
    "v9-daily",
    "v9-simulated-catches",
    "v9-simulated-title",
    "v9-simulated-mode",
    "v9-simulated-k",
    "v9-simulated-summary",
    "v9-simulated-volume",
    "v9-case-evidence",
    "v9-sig",
)
def _minimal_dashboard_template():
    return """<!doctype html>
<html><head><title>old</title><style>base
/* ---- Community Explorer ---- */
</style></head><body>
<nav class="tabs"><button data-tab="overview">Overview</button><button data-tab="explorer">Explorer</button></nav>
<main><h1>old</h1><section id="tab-overview" class="tab-content"></section><section id="tab-explorer" class="tab-content"></section></main>
<script>
const DATA = OLD;
(async function(){
  if(!D) return;
const tip=d3.select('body').append('div').attr('class','tooltip');
function showTip(e,html){
  tip.html(html).style('opacity',1);
  const b=tip.node().getBoundingClientRect();
  let x=e.clientX+14,y=e.clientY-12;
  if(x+b.width>window.innerWidth-10)x=e.clientX-b.width-14;
  if(y+b.height>window.innerHeight-10)y=e.clientY-b.height-10;
  if(y<6)y=6;
  tip.style('left',x+'px').style('top',y+'px');
}
function hideTip(){tip.style('opacity',0)}
const Tabs={
explorer:{rendered:false,render(){}}
};
document.querySelectorAll('nav.tabs button').forEach(b=>b.addEventListener('click',()=>switchTab(b.dataset.tab)));
})();
  </script></body></html>"""


class _IdAriaParser(HTMLParser):
    """Collect actual rendered IDs and local ARIA references."""

    def __init__(self):
        super().__init__()
        self.ids = []
        self.aria_refs = []

    def handle_starttag(self, _tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.append(attributes["id"])
        for name in ("aria-labelledby", "aria-describedby"):
            value = attributes.get(name)
            if value:
                self.aria_refs.extend(value.split())


def _assert_rendered_ids_and_aria(fragment, *, expect_data_table):
    parser = _IdAriaParser()
    parser.feed(fragment)
    counts = {value: parser.ids.count(value) for value in set(parser.ids)}
    assert all(count == 1 for count in counts.values()), counts
    assert counts.get("v9-gnn-architecture-comparison") == 1
    assert counts.get("v9-gnn-architecture-title") == 1
    assert counts.get("v9-gnn-architecture-daily", 0) == (
        1 if expect_data_table else 0
    )
    for reference in parser.aria_refs:
        assert counts.get(reference) == 1, reference


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


def _run_crossing_budget_selection(daily_ks, current):
    assert hasattr(V9_UI, "DAILY_CROSSING_SELECTION_JS")
    script = (
        V9_UI.DAILY_CROSSING_SELECTION_JS
        + "\nprocess.stdout.write(JSON.stringify(selectDailyCrossingBudget("
        + json.dumps(daily_ks)
        + ","
        + json.dumps(current)
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
    monkeypatch.setattr(
        BUILDER,
        "V9_RECOVERY_EXPLANATIONS",
        str(tmp_path / "missing-recovery.json"),
    )
    monkeypatch.setattr(
        BUILDER, "V9_RECOVERY_ARCHIVE", str(tmp_path / "missing-results.zip")
    )

    data = BUILDER._load_v9_data()
    embedded = BUILDER._embed_dashboard_data(
        "const DATA = OLD;\n(async function(){\n  if(!D) return;\n",
        data,
    )

    assert "v9Demo" not in data
    assert '"v9Demo"' not in embedded


def test_v9_ui_includes_model_daily_catch_chart():
    ui_path = ROOT / "scripts" / "dashboard" / "v9_dashboard_ui.py"
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


def test_v9_ui_keeps_daily_metric_lens_without_global_controls():
    ui_path = ROOT / "scripts" / "dashboard" / "v9_dashboard_ui.py"
    ui = ui_path.read_text()

    assert "Read the V9 result as a daily operating view" in ui
    assert "Daily event operations" in ui
    assert 'id="v9-pop"' not in ui
    assert "Depth event recall" not in ui
    assert 'id="v9-bars"' not in ui
    assert (
        "Leak-safe baselines use row-level history and context. GNN arms add as-of "
        "relational signals."
    ) in ui
    assert (
        "Every result uses a fixed daily inspection budget. The recovery explorer separately counts unique people."
    ) in ui
    assert "The graph advantage appears at operational depth." in ui
    assert (
        "Each of '+fmt(dailyDays)+' test days gets its own quota; '+fmt(lensDailyK)+'/day "
        "equals '+fmt(dailyBudgetAtK)+' inspections."
    ) not in ui
    assert (
        "Found, precision, recall, and F1 under fixed per-day inspection budgets."
    ) in ui
    assert "Daily bootstrap verdicts" in ui
    assert (
        "Daily crossing volume and hidden-positive event hits by model. Toggle a model"
    ) in ui
    assert "Toggle a model to show or hide its line." in ui
    assert (
        "Does the Hybrid event-hit lead persist when we re-draw the test events many "
        "times and keep the same daily inspection quota?"
    ) in ui
    assert "wholeHybridAt2000" not in ui
    assert "wholeBaselineAt2000" not in ui
    assert "Global Found@K by selected population" not in ui
    assert 'id="v9-table"' not in ui
    assert "function drawTable()" not in ui


def test_v9_ui_labels_overall_found_counts_as_event_hits_not_people():
    ui = UI_MODULE_PATH.read_text()

    for label in (
        "Hybrid event hits",
        "Baseline event hits",
        "GNN event-hit ceiling",
        "Daily capacity view",
        "Daily bootstrap verdicts",
        "hidden-positive event hits / day",
    ):
        assert label in ui
    assert "Whole-pool hidden carriers found" not in ui
    assert "observable carriers" not in ui
    assert ">Hidden carriers<" not in ui


def test_v9_ui_removes_whole_pool_model_comparison_and_dead_helpers():
    ui_path = ROOT / "scripts" / "dashboard" / "v9_dashboard_ui.py"
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


def test_v9_results_exposes_daily_budgets_only():
    ui_path = ROOT / "scripts" / "dashboard" / "v9_dashboard_ui.py"
    ui = ui_path.read_text()

    assert "Depth event recall" not in ui
    assert 'id="v9-pop"' not in ui
    assert 'id="v9-bars"' not in ui
    assert "function drawBars()" not in ui
    assert "Global event ranking" not in ui
    assert "Findable event depth" not in ui
    assert "const supportedDailyKs=[5,10,25]" in ui
    combined = ui.split("function drawCombined()", 1)[1].split(
        "SIMULATED_CATCH_VIEW_MODEL", 1
    )[0]
    assert "supportedDailyKs.includes(k)" in combined
    assert "50" not in combined


def test_v9_results_crossing_selector_defaults_to_ten_when_published():
    combined = UI_MODULE_PATH.read_text().split("function drawCombined()", 1)[1].split(
        "SIMULATED_CATCH_VIEW_MODEL", 1
    )[0]

    assert "selectDailyCrossingBudget(dks,select.value)" in combined
    assert "budgets.includes(10)?10:budgets[0]" in V9_UI.DAILY_CROSSING_SELECTION_JS
    assert "budgets.includes(25)?25:budgets[0]" not in V9_UI.DAILY_CROSSING_SELECTION_JS


def test_v9_results_capacity_and_crossing_model_arms_are_scoped_independently():
    ui = UI_MODULE_PATH.read_text()
    daily = ui.split("function drawDaily()", 1)[1].split(
        "function drawCombined()", 1
    )[0]
    combined = ui.split("function drawCombined()", 1)[1].split(
        "SIMULATED_CATCH_VIEW_MODEL", 1
    )[0]

    assert "const arms=['baseline','hybrid'].filter(a=>od[a]);" in daily
    assert "gnn" not in daily
    assert "arms=['baseline','hybrid'].filter(a=>od[a])" in combined
    assert "arms=['baseline','hybrid','gnn'].filter(a=>od[a])" not in combined


def test_v9_crossing_budget_selection_keeps_valid_and_uses_safe_fallbacks():
    assert _run_crossing_budget_selection([5, 10, 25], 25) == 25
    assert _run_crossing_budget_selection([5, 10, 25], "") == 10
    assert _run_crossing_budget_selection([5, 25], "") == 5


def test_v9_capacity_grid_fits_two_arms_and_collapses_on_mobile():
    css = V9_UI.V9_RESULTS_CSS
    desktop = re.search(
        r"#tab-v9Results\s+\.v9-capacity-rows\s*\{[^}]*\}", css
    )
    _, separator, mobile_css = css.partition("@media(max-width:700px){")

    assert desktop and "grid-template-columns: repeat(2, minmax(0, 1fr));" in desktop.group(0)
    assert separator
    assert re.search(
        r"#tab-v9Results\s+\.v9-capacity-rows\s*\{[^}]*"
        r"grid-template-columns:\s*1fr\s*;",
        mobile_css,
    )


def test_v9_results_layout_can_shrink_without_page_level_overflow():
    css = V9_UI.V9_RESULTS_CSS

    root = re.search(r"#tab-v9Results\s*\{[^}]*\}", css)
    assert root and "min-width: 0;" in root.group(0)
    assert "overflow-x: clip;" in root.group(0)
    assert ".v9-summary {" in css and "min-width: 0;" in css.split(
        ".v9-summary {", 1
    )[1].split("}", 1)[0]
    assert ".v9-chart-block {" in css and "min-width: 0;" in css.split(
        ".v9-chart-block {", 1
    )[1].split("}", 1)[0]


def test_v9_results_mobile_controls_wrap_and_labels_stay_readable():
    css = V9_UI.V9_RESULTS_CSS
    _, separator, mobile_css = css.partition("@media(max-width:700px){")

    assert separator
    assert "overflow-wrap: anywhere;" in mobile_css
    assert re.search(
        r"#tab-v9Results\s+\.v9-daily-found-header\s*\{[^}]*"
        r"align-items:\s*stretch\s*;",
        mobile_css,
    )


def test_v9_results_removes_redundant_metrics_settings_block():
    ui = UI_MODULE_PATH.read_text()

    for token in (
        'id="v9-metrics"',
        "makeMetrics(document.getElementById('v9-metrics')",
        "{l:'test pool'",
        "{l:'fusion weight'",
        "{l:'GNN run'",
    ):
        assert token not in ui


def test_v9_results_removes_model_notes_section():
    ui = UI_MODULE_PATH.read_text()

    for token in (
        'id="v9-model-notes"',
        "drawModelNotes",
        "GNN Models",
        "What the models look for",
        "As-of caught-propagation over the person graph, ignoring edge types.",
    ):
        assert token not in ui


def test_gnn_architecture_renderer_exposes_daily_budgets_only():
    module = _load_gnn_architecture_ui_module()
    source = module.GNN_ARCHITECTURE_VIEW_MODEL_JS + module.GNN_ARCHITECTURE_UI_JS

    assert "Inspection depth" not in source
    assert "data-depth" not in source
    assert "data-population" not in source
    assert "v9-gnn-architecture-recall-chart" not in source
    assert "dailyKs" in source
    assert "DAILY_BUDGETS" in source
    assert "Daily budget K=" in source


def test_run_demo_daily_budget_contract_excludes_fifty_per_day():
    import gnn.run_demo as run_demo
    import gnn.gnn_architecture_bakeoff as bakeoff

    assert run_demo.DAILY_KS == (5, 10, 25)
    assert bakeoff.DAILY_KS == (5, 10, 25)


def test_v9_ui_adds_independent_simulated_catch_contract():
    ui_path = ROOT / "scripts" / "dashboard" / "v9_dashboard_ui.py"
    ui = ui_path.read_text()

    assert ">Simulated catches</h4>" in ui
    assert "Unique people caught for the first time. A caught person leaves the pool." in ui
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


def test_v9_ui_removes_dead_model_notes_and_bar_selectors():
    _, separator, mobile_css = V9_UI.V9_RESULTS_CSS.partition("@media(max-width:700px){")

    assert separator
    for selector in (
        ".v9-bars",
        ".v9-bar-row",
        ".v9-track",
        ".v9-fill",
        ".v9-model-list",
        ".v9-model-note",
    ):
        assert selector not in V9_UI.V9_RESULTS_CSS


def test_v9_ui_keeps_daily_volume_and_simulated_catches_independent():
    ui_path = ROOT / "scripts" / "dashboard" / "v9_dashboard_ui.py"
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

    assert ui.index('id="v9-volume"') < ui.index('id="v9-daily"')
    assert ui.index('id="v9-daily"') < ui.index('id="v9-simulated-catches"')
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


def test_v9_results_injection_with_selection_helper_is_valid_javascript():
    template = "const Tabs={\nexplorer:{rendered:false,render(){}}\n};"
    injected = BUILDER._inject_dashboard_tab_scripts(
        template, "", V9_UI.V9_RESULTS_JS
    )

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
    assert js.index("Daily capacity view") < js.index(
        'id="v9-case-evidence"'
    )
    assert "mountV9RecoveryExplainer(" in js
    assert "DATA.v9RecoveryExplainer" in js
    assert "DATA.explorer" not in js
    assert "ground_truth_community" not in js
    assert "community_propensity" not in js
    assert "data-navigate-tab=\"explorer\"" not in js


def test_v9_results_uses_live_demo_order():
    js = V9_UI.V9_RESULTS_JS
    architecture_mount = (
        '<section id="v9-gnn-architecture-comparison" '
        'aria-labelledby="v9-gnn-architecture-title"></section>'
    )

    assert js.count(architecture_mount) == 1
    assert js.count("mountV9GNNArchitectureComparison(") == 1
    assert js.index('class="v9-story"') < js.index('id="v9-volume"')
    assert js.index('id="v9-volume"') < js.index('id="v9-daily"')
    assert js.index('id="v9-daily"') < js.index('id="v9-simulated-catches"')
    assert js.index('id="v9-simulated-catches"') < js.index('id="v9-case-evidence"')
    assert js.index('id="v9-case-evidence"') < js.index("Daily bootstrap verdicts")
    assert js.index("Daily bootstrap verdicts") < js.index(architecture_mount)
    for result_id in FROZEN_V9_RESULT_IDS:
        assert js.count(f'id="{result_id}"') == 1, result_id
    for left, right in zip(FROZEN_V9_RESULT_IDS, FROZEN_V9_RESULT_IDS[1:]):
        assert js.index(f'id="{left}"') < js.index(f'id="{right}"')
    assert js.count('id="v9-case-evidence"') == 1
    assert js.count('id="v9-gnn-architecture-title"') == 0


@pytest.mark.parametrize("artifact_present", [False, True])
def test_injects_gnn_assets_in_generated_minimal_dashboard_without_new_tab(
    tmp_path, monkeypatch, artifact_present
):
    artifact = _architecture_artifact(tmp_path) if artifact_present else None
    data = {
        "v9Demo": _compatible_v9_demo(),
        "v9RecoveryExplainer": {"schema_version": "1.0", "fixture": True},
        "unsupervisedAD": {"fixture": "unsupervised"},
        "nav": {"keep": True},
        "unrelated": {"keep": "unchanged"},
    }
    if artifact is not None:
        data["v9GNNArchitectureComparison"] = artifact
    monkeypatch.setattr(BUILDER, "_load_v9_data", lambda **_: data)
    monkeypatch.setattr(BUILDER, "_publish_staged_dashboard", lambda *_: None)
    template_path = tmp_path / "template.html"
    template_path.write_text(_minimal_dashboard_template())
    staged = tmp_path / "staged"
    staged.mkdir()
    # Keep the generated files in the staged tree while the publish operation
    # is stubbed; this still exercises the complete composition pipeline.
    destination = staged

    BUILDER._build_staged_dashboard(staged, destination, template_path)
    html = (staged / "index.html").read_text()

    architecture_ui = _load_gnn_architecture_ui_module()
    GNN_ARCHITECTURE_CSS = architecture_ui.GNN_ARCHITECTURE_CSS
    GNN_ARCHITECTURE_UI_JS = architecture_ui.GNN_ARCHITECTURE_UI_JS
    GNN_ARCHITECTURE_VIEW_MODEL_JS = architecture_ui.GNN_ARCHITECTURE_VIEW_MODEL_JS

    assert html.count(GNN_ARCHITECTURE_VIEW_MODEL_JS) == 1
    assert html.count(GNN_ARCHITECTURE_UI_JS) == 1
    assert html.count(GNN_ARCHITECTURE_CSS) == 1
    assert html.count(
        "mountV9GNNArchitectureComparison(document.getElementById("
    ) == 1
    assert html.count('id="v9-gnn-architecture-comparison"') == 1
    assert 'data-tab="v9GNNArchitecture"' not in html
    assert html.index(GNN_ARCHITECTURE_VIEW_MODEL_JS) < html.index("const Tabs={")
    assert html.index(GNN_ARCHITECTURE_UI_JS) < html.index("const Tabs={")
    style_start = html.index("<style")
    style_end = html.index("</style>", style_start)
    assert style_start < html.index(GNN_ARCHITECTURE_CSS) < style_end
    script_start = html.index("<script")
    script_end = html.index("</script>", script_start)
    assert script_start < html.index(GNN_ARCHITECTURE_VIEW_MODEL_JS) < script_end
    assert script_start < html.index(GNN_ARCHITECTURE_UI_JS) < script_end
    assert html.count('id="v9-gnn-architecture-title"') == GNN_ARCHITECTURE_UI_JS.count(
        'id="v9-gnn-architecture-title"'
    )
    assert (
        '"v9GNNArchitectureComparison"' in html
        if artifact_present
        else '"v9GNNArchitectureComparison"' not in html
    )
    assert "No GNN architecture comparison artifact is embedded." in html
    for left, right in (
        ('data-tab="overview"', 'data-tab="explorer"'),
        ('id="tab-overview"', 'id="tab-explorer"'),
    ):
        assert html.index(left) < html.index(right)

    for token in (
        'data-tab="overview"',
        'data-tab="explorer"',
        'data-tab="v9Results"',
        'data-tab="unsupervisedAD"',
        'id="tab-overview"',
        'id="tab-explorer"',
        'id="tab-v9Results"',
        'id="tab-unsupervisedAD"',
    ):
        assert html.count(token) == 1, token
    assert html.index('data-tab="v9Results"') < html.index(
        'data-tab="unsupervisedAD"'
    )
    assert html.index('id="tab-v9Results"') < html.index(
        'id="tab-unsupervisedAD"'
    )

    published = json.loads((staged / "data_v9.json").read_text())
    assert published == data
    static_ids = _IdAriaParser()
    static_ids.feed(html)
    assert len(static_ids.ids) == len(set(static_ids.ids))


@pytest.mark.parametrize("artifact_present", [False, True])
def test_gnn_architecture_section_rendered_composition_has_unique_ids_and_resolved_aria(
    tmp_path, artifact_present
):
    if artifact_present:
        fragment = _render_gnn_architecture_html(_architecture_artifact(tmp_path))
    else:
        module = _load_gnn_architecture_ui_module()
        script = (
            module.GNN_ARCHITECTURE_VIEW_MODEL_JS
            + module.GNN_ARCHITECTURE_UI_JS
            + "\nconst mount={innerHTML:'',addEventListener(){},contains(){return true;}};"
            + "\nmountV9GNNArchitectureComparison(mount,null,{});"
            + "process.stdout.write(mount.innerHTML);"
        )
        fragment = subprocess.run(
            ["node", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    composed = (
        '<section id="v9-gnn-architecture-comparison" '
        'aria-labelledby="v9-gnn-architecture-title">'
        + fragment
        + "</section>"
    )
    _assert_rendered_ids_and_aria(composed, expect_data_table=artifact_present)


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


def test_recovery_artifact_path_prefers_existing_archive_over_legacy_json(
    tmp_path, monkeypatch
):
    archive_path = tmp_path / "v9_schema3_results.zip"
    archive_path.write_bytes(b"zip-placeholder")
    legacy_path = tmp_path / "hybrid_recovery_explanations_v9.json"
    legacy_path.write_text(json.dumps({"schema_version": "1.0"}))
    monkeypatch.delenv("V9_SCHEMA3_RESULTS_ZIP", raising=False)
    monkeypatch.setattr(BUILDER, "V9_RECOVERY_ARCHIVE", str(archive_path))
    monkeypatch.setattr(BUILDER, "V9_RECOVERY_EXPLANATIONS", str(legacy_path))

    assert BUILDER._recovery_artifact_path() == str(archive_path)


def test_recovery_artifact_path_prefers_explicit_schema3_override(
    tmp_path, monkeypatch
):
    override_path = tmp_path / "configured-results.zip"
    archive_path = tmp_path / "v9_schema3_results.zip"
    archive_path.write_bytes(b"zip-placeholder")
    schema3_path = tmp_path / "hybrid_recovery_explanations_v9.json"
    schema3_path.write_text(json.dumps({"schema_version": "3.0"}))
    monkeypatch.setenv("V9_SCHEMA3_RESULTS_ZIP", str(override_path))
    monkeypatch.setattr(BUILDER, "V9_RECOVERY_ARCHIVE", str(archive_path))
    monkeypatch.setattr(BUILDER, "V9_RECOVERY_EXPLANATIONS", str(schema3_path))

    assert BUILDER._recovery_artifact_path() == str(override_path)


def test_recovery_artifact_path_uses_schema3_json_when_archive_is_absent(
    tmp_path, monkeypatch
):
    archive_path = tmp_path / "missing-v9_schema3_results.zip"
    schema3_path = tmp_path / "hybrid_recovery_explanations_v9.json"
    schema3_path.write_text(json.dumps({"schema_version": "3.0"}))
    monkeypatch.delenv("V9_SCHEMA3_RESULTS_ZIP", raising=False)
    monkeypatch.setattr(BUILDER, "V9_RECOVERY_ARCHIVE", str(archive_path))
    monkeypatch.setattr(BUILDER, "V9_RECOVERY_EXPLANATIONS", str(schema3_path))

    assert BUILDER._recovery_artifact_path() == str(schema3_path)


def test_recovery_artifact_path_ignores_existing_legacy_json(
    tmp_path, monkeypatch
):
    archive_path = tmp_path / "missing-v9_schema3_results.zip"
    legacy_path = tmp_path / "hybrid_recovery_explanations_v9.json"
    legacy_path.write_text(json.dumps({"schema_version": "1.0"}))
    monkeypatch.delenv("V9_SCHEMA3_RESULTS_ZIP", raising=False)
    monkeypatch.setattr(BUILDER, "V9_RECOVERY_ARCHIVE", str(archive_path))
    monkeypatch.setattr(BUILDER, "V9_RECOVERY_EXPLANATIONS", str(legacy_path))

    assert BUILDER._recovery_artifact_path() == str(archive_path)


def test_load_recovery_artifact_rejects_schema1_json(tmp_path, capsys):
    artifact = _recovery_artifact()
    path = tmp_path / "hybrid_recovery_explanations_v9.json"
    path.write_text(json.dumps(artifact))

    assert BUILDER._load_recovery_artifact(path) is None
    assert "unsupported recovery artifact schema" in capsys.readouterr().out


def test_load_recovery_artifact_rejects_schema2_json_without_publishing(
    tmp_path, capsys
):
    path = tmp_path / "hybrid_recovery_explanations_v9.json"
    path.write_text(json.dumps({"schema_version": "2.0"}))

    assert BUILDER._load_recovery_artifact(path) is None
    assert "unsupported recovery artifact schema" in capsys.readouterr().out


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


def test_load_recovery_artifact_packages_schema3_sidecars(tmp_path, monkeypatch):
    artifact = {"schema_version": "3.0"}
    path = tmp_path / "hybrid_recovery_explanations_v9.json"
    path.write_text(json.dumps(artifact))
    packaged = {"schema_version": "3.0", "packaged": True}
    monkeypatch.setattr(
        v9_recovery_sidecars,
        "package_schema3_sidecars",
        lambda value, output_dir: packaged,
    )

    assert BUILDER._load_recovery_artifact(path, output_dir=tmp_path) == packaged


def test_load_recovery_artifact_publishes_prepackaged_schema3_manifest(
    tmp_path, monkeypatch
):
    artifact = {"schema_version": "3.0", "community_sidecar_index": {}}
    path = tmp_path / "hybrid_recovery_explanations_v9.json"
    path.write_text(json.dumps(artifact))
    packaged = {"schema_version": "3.0", "prepackaged": True}
    monkeypatch.setattr(
        v9_recovery_sidecars,
        "publish_prepackaged_schema3_manifest",
        lambda value, source_path, output_dir: packaged,
    )

    assert BUILDER._load_recovery_artifact(path, output_dir=tmp_path) == packaged


def test_load_recovery_artifact_publishes_schema3_zip_bundle(tmp_path):
    archive_path, manifest = _write_schema3_zip(tmp_path)

    published = BUILDER._load_recovery_artifact(
        archive_path, output_dir=tmp_path / "dashboard"
    )

    assert published["schema_version"] == "3.0"
    assert (
        tmp_path
        / "dashboard"
        / "recovery"
        / manifest["bundle_path"]
        / "manifest.json"
    ).is_file()


def _write_schema3_zip(tmp_path, prefix="v9_schema3_results", extra_members=()):
    source_root = tmp_path / "source-recovery"
    manifest = v9_recovery_sidecars.package_schema3_sidecars(
        _schema3_sidecar_artifact(), source_root
    )
    manifest_path = source_root / "hybrid_recovery_explanations_v9.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    archive_path = tmp_path / "v9_schema3_results.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(
            manifest_path,
            Path(prefix) / "hybrid_recovery_explanations_v9.json",
        )
        for source in (source_root / "bundles").rglob("*"):
            if source.is_file():
                archive.write(
                    source,
                    Path(prefix)
                    / "recovery"
                    / "bundles"
                    / source.relative_to(source_root / "bundles"),
                )
        for info, content in extra_members:
            archive.writestr(info, content)
    return archive_path, manifest


def test_load_recovery_artifact_rejects_schema3_zip_with_wrong_prefix(tmp_path):
    archive_path, _ = _write_schema3_zip(tmp_path, prefix="wrong-root")

    with pytest.raises(ValueError, match="v9_schema3_results"):
        BUILDER._load_recovery_artifact(
            archive_path, output_dir=tmp_path / "dashboard"
        )


def test_load_recovery_artifact_rejects_unreferenced_schema3_zip_symlink(tmp_path):
    symlink = zipfile.ZipInfo("v9_schema3_results/unreferenced-link")
    symlink.create_system = 3
    symlink.external_attr = (0o120777 << 16) | 0xA000
    archive_path, _ = _write_schema3_zip(
        tmp_path, extra_members=((symlink, "target"),)
    )

    with pytest.raises(ValueError, match="symlink"):
        BUILDER._load_recovery_artifact(
            archive_path, output_dir=tmp_path / "dashboard"
        )


def test_load_v9_data_discards_legacy_recovery_artifact(
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
    monkeypatch.setattr(
        BUILDER, "V9_RECOVERY_ARCHIVE", str(tmp_path / "missing-results.zip")
    )

    data = BUILDER._load_v9_data()
    assert "v9RecoveryExplainer" not in data

    artifact_path.unlink()
    assert "v9RecoveryExplainer" not in BUILDER._load_v9_data()


def test_load_v9_data_falls_back_to_repo_zip_when_json_is_absent(
    tmp_path, monkeypatch
):
    (tmp_path / "dashboard_data.json").write_text(json.dumps({}))
    _write_csv(tmp_path / "train_valid_test_splits.csv", [
        {"entity_id": "E1", "split": "test"},
    ])
    _write_csv(tmp_path / "crossing_events.csv", [
        {"event_id": "E1", "event_timestamp_utc": "2025-01-02T03:00:00Z"},
    ])
    missing_json = tmp_path / "missing-recovery.json"
    archive_path = tmp_path / "v9_schema3_results.zip"
    archive_path.write_bytes(b"zip-placeholder")
    monkeypatch.setattr(BUILDER, "V9_DATA", str(tmp_path / "dashboard_data.json"))
    monkeypatch.setattr(BUILDER, "V9_DEMO", str(tmp_path / "missing_demo.json"))
    monkeypatch.setattr(BUILDER, "V9_CORPUS", str(tmp_path))
    monkeypatch.setattr(BUILDER, "V9_RECOVERY_EXPLANATIONS", str(missing_json))
    monkeypatch.setattr(BUILDER, "V9_RECOVERY_ARCHIVE", str(archive_path))
    monkeypatch.setattr(
        BUILDER,
        "_load_recovery_artifact",
        lambda path, output_dir=None: {"source_path": str(path)},
    )

    assert BUILDER._load_v9_data()["v9RecoveryExplainer"] == {
        "source_path": str(archive_path)
    }


def _architecture_artifact(corpus_dir):
    ks = [1]
    daily_ks = [1]
    overall = {
        "found@1": 1,
        "precision@1": 1.0,
        "recall@1": 1.0,
        "f1@1": 1.0,
    }
    stratified = {
        "observable": {"hidden": 1, "found@1": 1, "recall@1": 1.0},
        "dark": {"hidden": 0, "found@1": 0, "recall@1": 0.0},
        "lone": {"hidden": 0, "found@1": 0, "recall@1": 0.0},
    }
    daily = {
        "n_days": 1,
        "daily_found@1": 1,
        "daily_found_by_day@1": [{"date": "2025-01-01", "found": 1}],
        "daily_recall@1": 1.0,
        "daily_precision@1": 1.0,
        "daily_f1@1": 1.0,
        "daily_budget@1": 1,
    }
    per_seed = {
        str(seed): {
            "overall": dict(overall),
            "stratified": {key: dict(value) for key, value in stratified.items()},
        }
        for seed in (0, 1, 2)
    }
    arm_metadata = {
        "sage": ("GraphSAGE", "As-of caught-propagation over the person graph, ignoring edge types. Best/representative GNN arm; the one the hybrid fuses."),
        "rgcn": ("RGCN full graph", "As-of caught-propagation over typed COTRAVEL, RESIDENCE, SHARED_PLATE, SHARED_PLATE_HOT relations."),
        "gat": ("GAT (attention)", "As-of caught-propagation with attention over neighbors."),
        "gin": ("GIN", "As-of caught-propagation with a high-expressivity GIN."),
        "kpiaa": ("KPI-AA (approx)", "As-of caught-propagation mimicking key-person ID."),
    }
    architectures = {
        architecture_id: {
            "label": arm_metadata[architecture_id][0],
            "looks_for": arm_metadata[architecture_id][1],
            "num_relations": 4,
            "ensemble": {
                "overall": dict(overall),
                "stratified": {key: dict(value) for key, value in stratified.items()},
                "daily": dict(daily),
            },
            "per_seed": per_seed,
        }
        for architecture_id in ("sage", "rgcn", "gat", "gin", "kpiaa")
    }
    return {
        "schema_version": 1,
        "artifact_kind": "gnn_architecture_comparison",
        "corpus": "synthetic_cbp_graph_corpus_v9",
        "corpus_identity": str(Path(corpus_dir).resolve()),
        "substrate": "oracle",
        "seeds": [0, 1, 2],
        "epochs": 18,
        "train_bucket": "Q",
        "ks": ks,
        "daily_ks": daily_ks,
        "pool_size": 1,
        "hidden_total": 1,
        "stratum_hidden": {"observable": 1, "dark": 0, "lone": 0},
        "feature_schema": [
            "bias", "degree_cotravel", "degree_residence",
            "degree_shared_plate", "degree_shared_plate_hot",
            "log1p_cotravel_component_size", "log1p_households_spanned",
            "caught_before_snapshot",
        ],
        "relation_schema": {
            "COTRAVEL": 0, "RESIDENCE": 1,
            "SHARED_PLATE": 2, "SHARED_PLATE_HOT": 3,
        },
        "architecture_order": ["sage", "rgcn", "gat", "gin", "kpiaa"],
        "architectures": architectures,
    }


def _compatible_v9_demo():
    return {
        "overall": {"baseline": {}, "hybrid": {}},
        "overall_daily": {"baseline": {}, "hybrid": {}},
        "stratified": {
            "baseline": {"observable": {}},
            "hybrid": {"observable": {}},
        },
        "stratum_hidden": {"hidden_total": 0},
        "hidden_total": 0,
    }


@pytest.fixture
def generated_dashboard_html(tmp_path, monkeypatch):
    data = {
        "v9Demo": _compatible_v9_demo(),
        "v9RecoveryExplainer": {"schema_version": "1.0", "fixture": True},
        "unsupervisedAD": {"schema_version": 3, "modes": {}},
        "nav": {"keep": True},
        "unrelated": {"keep": "unchanged"},
    }
    monkeypatch.setattr(BUILDER, "_load_v9_data", lambda **_: data)
    monkeypatch.setattr(BUILDER, "_publish_staged_dashboard", lambda *_: None)
    template_path = tmp_path / "template.html"
    template_path.write_text(_minimal_dashboard_template())
    staged = tmp_path / "staged"
    staged.mkdir()
    BUILDER._build_staged_dashboard(staged, staged, template_path)
    return (staged / "index.html").read_text()


def _configure_architecture_load(tmp_path, monkeypatch, artifact=None):
    preserved = {
        "v9Demo": _compatible_v9_demo(),
        "unsupervisedAD": {"fixture": "unsupervised"},
        "nav": {"keep": True},
        "unrelated": {"keep": "unchanged"},
        "v9GNNArchitectureComparison": {"stale": True},
    }
    data_path = tmp_path / "dashboard_data.json"
    data_path.write_text(json.dumps(preserved))
    _write_csv(tmp_path / "train_valid_test_splits.csv", [
        {"entity_id": "E1", "split": "test"},
    ])
    _write_csv(tmp_path / "crossing_events.csv", [
        {"event_id": "E1", "event_timestamp_utc": "2025-01-02T03:00:00Z"},
    ])
    artifact_path = tmp_path / "gnn_architecture_comparison_v9.json"
    if artifact is not None:
        artifact_path.write_text(json.dumps(artifact))
    demo_path = tmp_path / "demo.json"
    demo_path.write_text(json.dumps(preserved["v9Demo"]))
    monkeypatch.setattr(BUILDER, "V9_DATA", str(data_path))
    monkeypatch.setattr(BUILDER, "V9_CORPUS", str(tmp_path))
    monkeypatch.setattr(BUILDER, "V9_DEMO", str(demo_path))
    monkeypatch.setattr(
        BUILDER,
        "V9_RECOVERY_EXPLANATIONS",
        str(tmp_path / "missing-recovery.json"),
    )
    monkeypatch.setattr(
        BUILDER, "V9_RECOVERY_ARCHIVE", str(tmp_path / "missing-results.zip")
    )
    monkeypatch.setattr(BUILDER, "DIAGNOSTICS_DIR", str(tmp_path / "diagnostics"))
    monkeypatch.setattr(BUILDER, "V9_GNN_ARCHITECTURE_COMPARISON", str(artifact_path))
    monkeypatch.setattr(
        BUILDER,
        "_load_v9_unsupervised_artifact",
        lambda _diagnostics_dir: preserved["unsupervisedAD"],
    )
    return artifact_path, preserved


def test_load_v9_data_embeds_compatible_gnn_architecture_artifact(
    tmp_path, monkeypatch
):
    artifact = _architecture_artifact(tmp_path)
    _artifact_path, preserved = _configure_architecture_load(
        tmp_path, monkeypatch, artifact
    )

    data = BUILDER._load_v9_data()
    embedded = BUILDER._embed_dashboard_data(
        "const DATA = OLD;\n(async function(){\n  if(!D) return;\n", data
    )

    assert data["v9GNNArchitectureComparison"] == artifact
    for key, value in preserved.items():
        if key != "v9GNNArchitectureComparison":
            assert data[key] == value
    assert '"v9GNNArchitectureComparison"' in embedded


def test_load_v9_data_warns_and_omits_missing_gnn_architecture_artifact(
    tmp_path, monkeypatch, capsys
):
    _artifact_path, preserved = _configure_architecture_load(tmp_path, monkeypatch)

    data = BUILDER._load_v9_data()

    assert "v9GNNArchitectureComparison" not in data
    for key, value in preserved.items():
        if key != "v9GNNArchitectureComparison":
            assert data[key] == value
    assert "gnn architecture comparison" in capsys.readouterr().out.lower()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda artifact: artifact.update({"corpus": "synthetic_cbp_graph_corpus_v8"}),
        lambda artifact: artifact.update({"corpus_identity": "/wrong/corpus"}),
        lambda artifact: artifact.update({"schema_version": 2}),
        lambda artifact: artifact.update({"artifact_kind": "wrong_kind"}),
        lambda artifact: artifact.update({"architecture_order": ["rgcn", "sage", "gat", "gin", "kpiaa"]}),
        lambda artifact: artifact.update({"seeds": [0, 1]}),
        lambda artifact: artifact.update({"ks": []}),
        lambda artifact: artifact.update({"daily_ks": []}),
        lambda artifact: artifact["architectures"].pop("sage"),
        lambda artifact: artifact["architectures"].update({"extra": {}}),
        lambda artifact: artifact["architectures"]["sage"].pop("ensemble"),
        lambda artifact: artifact["architectures"]["sage"].pop("per_seed"),
        lambda artifact: artifact["architectures"]["sage"]["ensemble"]["stratified"].pop("observable"),
        lambda artifact: artifact["architectures"]["sage"]["ensemble"]["overall"].clear(),
        lambda artifact: artifact["architectures"]["sage"]["ensemble"]["overall"].update({"found@1": "1"}),
        lambda artifact: artifact.update({"hidden_total": 0}),
        lambda artifact: artifact.update({"stratum_hidden": {"observable": 0, "dark": 0, "lone": 0}}),
        lambda artifact: artifact.update({"feature_schema": ["wrong"]}),
        lambda artifact: artifact.update({"relation_schema": {"COTRAVEL": 9}}),
        lambda artifact: artifact.pop("substrate"),
        lambda artifact: artifact.pop("epochs"),
        lambda artifact: artifact.pop("train_bucket"),
        lambda artifact: artifact.pop("pool_size"),
        lambda artifact: artifact.pop("hidden_total"),
        lambda artifact: artifact.pop("stratum_hidden"),
        lambda artifact: artifact.pop("feature_schema"),
        lambda artifact: artifact.pop("relation_schema"),
        lambda artifact: artifact["architectures"]["sage"]["ensemble"]["overall"].update(
            {"precision@1": float("nan")}
        ),
        lambda artifact: artifact["architectures"]["sage"]["ensemble"]["overall"].update(
            {"precision@1": True}
        ),
    ],
    ids=[
        "wrong-corpus", "wrong-identity", "wrong-schema", "wrong-kind",
        "wrong-order", "wrong-seeds", "empty-ks", "empty-daily-ks",
        "incomplete-architecture", "extra-architecture", "missing-ensemble",
        "missing-per-seed", "missing-observable", "empty-metrics", "string-metric",
        "wrong-hidden-total", "wrong-strata", "wrong-feature-schema", "wrong-relation-schema",
        "missing-substrate", "missing-epochs", "missing-train-bucket", "missing-pool-size",
        "missing-hidden-total", "missing-stratum-hidden", "missing-feature-schema",
        "missing-relation-schema", "non-finite", "boolean-metric",
    ],
)
def test_load_v9_data_warns_and_omits_incompatible_gnn_architecture_artifact(
    tmp_path, monkeypatch, capsys, mutate
):
    artifact = _architecture_artifact(tmp_path)
    mutate(artifact)
    _artifact_path, preserved = _configure_architecture_load(
        tmp_path, monkeypatch, artifact
    )

    data = BUILDER._load_v9_data()

    assert "v9GNNArchitectureComparison" not in data
    for key, value in preserved.items():
        if key != "v9GNNArchitectureComparison":
            assert data[key] == value
    assert "gnn architecture comparison" in capsys.readouterr().out.lower()


def test_load_v9_data_warns_and_omits_malformed_gnn_architecture_artifact(
    tmp_path, monkeypatch, capsys
):
    artifact_path, preserved = _configure_architecture_load(tmp_path, monkeypatch)
    artifact_path.write_text("{not-json")

    data = BUILDER._load_v9_data()

    assert "v9GNNArchitectureComparison" not in data
    for key, value in preserved.items():
        if key != "v9GNNArchitectureComparison":
            assert data[key] == value
    assert "gnn architecture comparison" in capsys.readouterr().out.lower()


def test_load_v9_data_rejects_duplicate_architecture_identifier_json(
    tmp_path, monkeypatch, capsys
):
    artifact = _architecture_artifact(tmp_path)
    artifact_path, preserved = _configure_architecture_load(
        tmp_path, monkeypatch, artifact
    )
    raw = json.dumps(artifact, separators=(",", ":"))
    marker = '"architectures":{"sage":'
    assert marker in raw
    raw = raw.replace(marker, '"architectures":{"sage":{},"sage":', 1)
    artifact_path.write_text(raw)

    data = BUILDER._load_v9_data()

    assert "v9GNNArchitectureComparison" not in data
    assert data["unrelated"] == preserved["unrelated"]
    assert "duplicate" in capsys.readouterr().out.lower()


def test_load_v9_data_warns_and_continues_for_deeply_nested_invalid_json(
    tmp_path, monkeypatch, capsys
):
    artifact_path, preserved = _configure_architecture_load(tmp_path, monkeypatch)
    artifact_path.write_text("{" * 1200 + "0" + "}" * 1200)

    data = BUILDER._load_v9_data()

    assert "v9GNNArchitectureComparison" not in data
    assert data["unrelated"] == preserved["unrelated"]
    assert "invalid gnn architecture comparison" in capsys.readouterr().out.lower()


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


def test_recovery_assets_include_graph_first_explanation_contract():
    from scripts.dashboard import v9_recovery_explainer_ui as recovery_ui

    template = (
        "<style>base</style><script>const Tabs={\n"
        "explorer:{rendered:false,render(){}}\n};</script>"
    )
    injected = BUILDER._inject_recovery_assets(
        template,
        recovery_ui.V9_RECOVERY_EXPLAINER_CSS,
        recovery_ui.V9_RECOVERY_EXPLAINER_JS,
    )

    assert "recoveryFormatNumber" in injected
    assert "v9-recovery-title" in injected
    assert "v9-recovery-v3-picker" in injected
    assert "v9-recovery-graph-panel" in injected
    assert "Retry evidence" in injected
    assert "Why case " in injected


def test_v9_results_injection_contains_evidence_first_graph_language_once():
    from scripts.dashboard import v9_recovery_explainer_ui as recovery_ui

    recovery = recovery_ui.V9_RECOVERY_EXPLAINER_JS
    assert recovery.count("Evidence first") == 1
    assert recovery.count("Model evidence weight") >= 1
    assert "data-v3-relation" in recovery


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

    assert "python -m http.server 8000 --directory artifacts/v9/dashboard" in source
    assert "open v9_dashboard/index.html directly" not in source


def _load_gnn_architecture_ui_module():
    path = ROOT / "scripts" / "dashboard" / "v9_gnn_architecture_ui.py"
    spec = importlib.util.spec_from_file_location("v9_gnn_architecture_ui", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_gnn_architecture_view_model(artifact, population=None, requested_k=None):
    module = _load_gnn_architecture_ui_module()
    script = (
        module.GNN_ARCHITECTURE_VIEW_MODEL_JS
        + "\nprocess.stdout.write(JSON.stringify(buildGNNArchitectureViewModel("
        + json.dumps(artifact)
        + ","
        + json.dumps(population)
        + ","
        + json.dumps(requested_k)
        + ")));"
    )
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _richer_gnn_architecture_artifact(tmp_path, *, include_500=True):
    """Self-contained view-model fixture with distinct pool/observable/seed values."""
    ks = [50, 500, 1000] if include_500 else [50, 1000]
    daily_ks = [5, 25]
    labels = {
        "sage": ("GraphSAGE", "person-graph caught propagation"),
        "rgcn": ("RGCN full graph", "typed relation propagation"),
        "gat": ("GAT (attention)", "attention-weighted neighbors"),
        "gin": ("GIN", "high-expressivity neighborhood structure"),
        "kpiaa": ("KPI-AA (approx)", "key-person identity approximation"),
    }
    architecture_ids = ["sage", "rgcn", "gat", "gin", "kpiaa"]
    hidden_total = 20
    observable_hidden = 8
    n_days = 4

    def global_metrics(values):
        result = {}
        for k, found in values.items():
            precision = round(found / k, 4)
            recall = round(found / hidden_total, 4)
            f1 = round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0
            result.update({f"found@{k}": found, f"precision@{k}": precision,
                          f"recall@{k}": recall, f"f1@{k}": f1})
        return result

    def stratified_metrics(observable_values, overall_values):
        strata = {}
        for name, denominator in (("observable", observable_hidden), ("dark", 7), ("lone", 5)):
            strata[name] = {"hidden": denominator}
        for k in ks:
            observable_found = observable_values[k]
            remainder = overall_values[k] - observable_found
            dark_found = min(7, remainder)
            lone_found = remainder - dark_found
            for name, found, denominator in (
                ("observable", observable_found, observable_hidden),
                ("dark", dark_found, 7),
                ("lone", lone_found, 5),
            ):
                strata[name].update({f"found@{k}": found, f"recall@{k}": round(found / denominator, 4) if denominator else 0.0})
        return strata

    def daily_metrics(offset):
        result = {"n_days": n_days}
        for k in daily_ks:
            found = min(hidden_total, offset + (k // 10))
            budget = k * n_days
            precision = round(found / budget, 4)
            recall = round(found / hidden_total, 4)
            f1 = round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0
            result.update({
                f"daily_found@{k}": found,
                f"daily_found_by_day@{k}": [{"date": f"2025-01-0{day}", "found": found // n_days + (1 if day <= found % n_days else 0)} for day in range(1, n_days + 1)],
                f"daily_budget@{k}": budget,
                f"daily_precision@{k}": precision,
                f"daily_recall@{k}": recall,
                f"daily_f1@{k}": f1,
            })
        return result

    architectures = {}
    for index, architecture_id in enumerate(architecture_ids):
        overall_values = {k: min(hidden_total, 4 + index + (k // 250)) for k in ks}
        observable_values = {k: min(observable_hidden, 2 + index + (k // 500)) for k in ks}
        seed_rows = {}
        for seed in range(3):
            overall_seed_values = {k: min(hidden_total, 3 + index + seed + (k // 250)) for k in ks}
            observable_seed_values = {k: min(observable_hidden, 1 + index + seed + (k // 500)) for k in ks}
            seed_rows[str(seed)] = {
                "overall": global_metrics(overall_seed_values),
                "stratified": stratified_metrics(observable_seed_values, overall_seed_values),
            }
        architectures[architecture_id] = {
            "label": labels[architecture_id][0],
            "looks_for": labels[architecture_id][1],
            "num_relations": 4,
            "ensemble": {
                "overall": global_metrics(overall_values),
                "stratified": stratified_metrics(observable_values, overall_values),
                "daily": daily_metrics(index + 1),
            },
            "per_seed": seed_rows,
        }
    return {
        "schema_version": 1,
        "artifact_kind": "gnn_architecture_comparison",
        "corpus": "synthetic_cbp_graph_corpus_v9",
        "corpus_identity": str(Path(tmp_path).resolve()),
        "substrate": "oracle",
        "seeds": [0, 1, 2],
        "epochs": 24,
        "train_bucket": "2025-01",
        "ks": ks,
        "daily_ks": daily_ks,
        "pool_size": 100,
        "hidden_total": hidden_total,
        "stratum_hidden": {"observable": observable_hidden, "dark": 7, "lone": 5},
        "feature_schema": [],
        "relation_schema": {},
        "architecture_order": architecture_ids,
        "architectures": architectures,
    }


def test_gnn_architecture_view_model_is_fixed_order_and_observable_by_default(tmp_path):
    artifact = _richer_gnn_architecture_artifact(tmp_path)
    result = _run_gnn_architecture_view_model(artifact, None, 500)

    assert result["available"] is True
    assert "population" not in result
    assert "selectedK" not in result
    assert "ks" not in result
    assert result["dailyKs"] == [5, 25]
    assert [row["id"] for row in result["rows"]] == ["sage", "rgcn", "gat", "gin", "kpiaa"]
    assert set(result["rows"][0]["daily"]) == {"5", "25"}


def test_gnn_architecture_view_model_exposes_daily_metrics_and_provenance(tmp_path):
    artifact = _richer_gnn_architecture_artifact(tmp_path)
    result = _run_gnn_architecture_view_model(artifact, "pool", 1)

    assert result["dailyKs"] == [5, 25]
    assert result["provenance"] == {
        "corpus": "synthetic_cbp_graph_corpus_v9",
        "seeds": [0, 1, 2],
        "epochs": 24,
        "trainBucket": "2025-01",
    }
    assert result["rows"][0]["daily"]["5"] == {
        "found": 1, "budget": 20, "precision": 0.05, "recall": 0.05, "f1": 0.05,
    }


def test_gnn_architecture_view_model_ignores_global_depth_and_population_inputs(tmp_path):
    artifact = _richer_gnn_architecture_artifact(tmp_path)

    requested = _run_gnn_architecture_view_model(artifact, "observable", 1000)
    assert requested["dailyKs"] == [5, 25]
    assert "selectedK" not in requested
    assert "population" not in requested

    fallback = _run_gnn_architecture_view_model(artifact, "pool", 750)
    assert fallback["dailyKs"] == requested["dailyKs"]
    assert fallback["rows"][0]["daily"] == {
        "5": {"found": 1, "budget": 20, "precision": 0.05, "recall": 0.05, "f1": 0.05},
        "25": {"found": 3, "budget": 100, "precision": 0.03, "recall": 0.15, "f1": 0.05},
    }


def test_gnn_architecture_view_model_preserves_published_unsorted_k_order(tmp_path):
    artifact = _richer_gnn_architecture_artifact(tmp_path, include_500=False)
    artifact["ks"] = [1000, 50]
    result = _run_gnn_architecture_view_model(artifact, "observable", 750)

    assert result["dailyKs"] == [5, 25]
    assert "selectedK" not in result


def test_gnn_architecture_view_model_daily_metrics_cover_every_arm_and_depth(tmp_path):
    result = _run_gnn_architecture_view_model(_richer_gnn_architecture_artifact(tmp_path), "observable", 50)
    assert result["dailyKs"] == [5, 25]
    assert result["nDays"] == 4 and result["dailyDays"] == 4
    assert len(result["rows"]) == 5
    for row in result["rows"]:
        assert set(row["daily"]) == {"5", "25"}
        for values in row["daily"].values():
            assert set(values) == {"found", "budget", "precision", "recall", "f1"}


def test_gnn_architecture_renderer_is_isolated_accessible_and_gnn_only(tmp_path):
    module = _load_gnn_architecture_ui_module()
    source = module.GNN_ARCHITECTURE_UI_JS
    css = module.GNN_ARCHITECTURE_CSS

    assert "mountV9GNNArchitectureComparison" in source
    assert "v9-gnn-architecture-title" in source
    assert "role=\"group\"" not in source
    assert "aria-pressed" not in source
    assert "inspection depth" not in source.lower()
    assert "data-depth" not in source
    assert "data-population" not in source
    assert "<svg" not in source and "<table" in source
    assert "<details" not in source and "daily" in source.lower()
    assert "GraphSAGE" in source and "RGCN full graph" in source
    assert "GAT (attention)" in source and "GIN" in source and "KPI-AA (approx)" in source
    assert "Hybrid" not in source
    assert "#v9-gnn-architecture-comparison" in css
    assert "@media" in css


def test_gnn_architecture_renderer_adds_easy_to_read_daily_f1_charts(tmp_path):
    module = _load_gnn_architecture_ui_module()
    source = module.GNN_ARCHITECTURE_UI_JS

    assert "gnn-f1-chart" in source
    assert "F1 score" in source
    assert "gnn-chart-row" in source

    html = _render_gnn_architecture_html(_richer_gnn_architecture_artifact(tmp_path))
    assert html.count('class="gnn-f1-chart"') == 2
    assert html.count("gnn-chart-row") >= 10
    assert "F1 score; higher is better" in html
    assert "Precision" in html and "Recall" in html


def test_gnn_architecture_renderer_unavailable_state_is_explicit(tmp_path):
    module = _load_gnn_architecture_ui_module()
    source = module.GNN_ARCHITECTURE_UI_JS
    assert "No GNN architecture comparison artifact is embedded." in source
    assert ".venv/bin/python -m gnn.gnn_architecture_bakeoff" in source


def _render_gnn_architecture_html(artifact, *, helper_escape=True):
    module = _load_gnn_architecture_ui_module()
    helper = "{escape:s=>String(s).replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]))}" if helper_escape else "{}"
    script = (
        module.GNN_ARCHITECTURE_VIEW_MODEL_JS
        + module.GNN_ARCHITECTURE_UI_JS
        + "\nconst mount={innerHTML:'',listeners:{},addEventListener(type,fn){this.listeners[type]=fn;},contains(){return true;}};"
        + "\nmountV9GNNArchitectureComparison(mount,"
        + json.dumps(artifact)
        + ","
        + helper
        + ");process.stdout.write(mount.innerHTML);"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return completed.stdout


def test_gnn_architecture_renderer_handles_missing_and_invalid_artifacts(tmp_path):
    module = _load_gnn_architecture_ui_module()
    script = (
        module.GNN_ARCHITECTURE_VIEW_MODEL_JS
        + module.GNN_ARCHITECTURE_UI_JS
        + "\nconst mount={innerHTML:'',addEventListener(){},contains(){return true;}};"
        + "\nmountV9GNNArchitectureComparison(mount,null,{});process.stdout.write(mount.innerHTML+'\\n');"
        + "\nmountV9GNNArchitectureComparison(mount,{artifact_kind:'wrong'},{});process.stdout.write(mount.innerHTML);"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    output = completed.stdout
    assert output.count("No GNN architecture comparison artifact is embedded.") == 2
    assert output.count(".venv/bin/python -m gnn.gnn_architecture_bakeoff") == 2


def test_gnn_architecture_renderer_valid_markup_and_accessibility_contracts(tmp_path):
    artifact = _richer_gnn_architecture_artifact(tmp_path)
    artifact["corpus"] = "<unsafe corpus>"
    artifact["architectures"]["sage"]["looks_for"] = "<unsafe signal>. Hybrid contextual sentence."
    for architecture_id in ("rgcn", "gat", "gin", "kpiaa"):
        artifact["architectures"][architecture_id]["looks_for"] = (
            f"Architecture-only {architecture_id} description. Hybrid contextual sentence."
        )
    html = _render_gnn_architecture_html(artifact)

    assert "<unsafe corpus>" not in html and "&lt;unsafe corpus&gt;" in html
    assert "<unsafe signal>" not in html and "&lt;unsafe signal&gt;" in html
    assert "hybrid" not in html.lower()
    for architecture_id in ("rgcn", "gat", "gin", "kpiaa"):
        assert f"Architecture-only {architecture_id} description." in html
    assert html.count("GraphSAGE") >= 2
    for label in ("GraphSAGE", "RGCN full graph", "GAT (attention)", "GIN", "KPI-AA (approx)"):
        assert label in html
    assert "Hybrid" not in html
    assert "role=\"group\"" not in html and "aria-pressed=\"true\"" not in html
    assert "Inspection depth" not in html
    assert "data-depth" not in html
    assert "data-population" not in html
    assert "Found" in html and "Budget" in html
    assert "Recall" in html and "F1" in html
    for daily_k in (5, 25):
        assert f"Daily budget K={daily_k}" in html
    for metric in ("Found", "Precision", "Recall", "F1"):
        assert metric in html
    assert "Mechanism" in html
    assert "Aggregates across 4 test days" in html
    for provenance in ("Corpus:", "Seeds:", "Epochs:", "Train bucket:"):
        assert provenance in html


def test_gnn_architecture_renderer_fragment_composes_inside_planned_outer_mount(tmp_path):
    html = _render_gnn_architecture_html(_richer_gnn_architecture_artifact(tmp_path))
    assert 'id="v9-gnn-architecture-comparison"' not in html
    assert html.count('id="v9-gnn-architecture-title"') == 1
    assert "No GNN architecture comparison artifact is embedded." not in html

    unavailable = _render_gnn_architecture_html(None)
    assert 'id="v9-gnn-architecture-comparison"' not in unavailable
    assert unavailable.count('id="v9-gnn-architecture-title"') == 1
    assert "No GNN architecture comparison artifact is embedded." in unavailable


def _run_gnn_architecture_interaction(artifact):
    module = _load_gnn_architecture_ui_module()
    script = (
        module.GNN_ARCHITECTURE_VIEW_MODEL_JS
        + module.GNN_ARCHITECTURE_UI_JS
        + "\nfunction makeMount(){"
        + "const doc={activeElement:null};let html='';"
        + "const mount={ownerDocument:doc, listeners:{}, controls:{}, contains(node){return !!node&&node.mount===this;},"
        + "addEventListener(type,fn){this.listeners[type]=fn;},removeEventListener(type,fn){if(this.listeners[type]===fn)delete this.listeners[type];},"
        + "querySelector(selector){return this.controls[selector]||null;}};"
        + "Object.defineProperty(mount,'innerHTML',{get(){return html;},set(value){html=value;"
        + "const control=(attrs)=>({mount,focused:0,value:attrs.value||'',getAttribute(name){return Object.prototype.hasOwnProperty.call(attrs,name)?attrs[name]:null;},"
        + "closest(selector){return selector.startsWith('button')&&attrs['data-population']?this:(selector.startsWith('select')&&attrs['data-depth']!==undefined?this:null);},"
        + "focus(){this.focused+=1;doc.activeElement=this;}});"
        + "this.controls['button[data-population=\"observable\"]']=control({'data-population':'observable'});"
        + "this.controls['button[data-population=\"pool\"]']=control({'data-population':'pool'});"
        + "this.controls['select[data-depth]']=control({'data-depth':'',value:'500'});"
        + "this.controls['details']={mount,open:false};}});return mount;}"
        + "\nconst mount=makeMount();mountV9GNNArchitectureComparison(mount,"
        + json.dumps(artifact)
        + ",{escape:s=>String(s)});"
        + "\nconst pool=mount.controls['button[data-population=\"pool\"]'];mount.ownerDocument.activeElement=pool;mount.controls.details.open=true;mount.listeners.click({target:pool});"
        + "const poolFocus=mount.ownerDocument.activeElement===mount.controls['button[data-population=\"pool\"]'];const poolDetails=mount.controls.details.open;"
        + "\nconst select=mount.controls['select[data-depth]'];mount.ownerDocument.activeElement=select;mount.controls.details.open=true;mount.listeners.change({target:select});"
        + "const depthFocus=mount.ownerDocument.activeElement===mount.controls['select[data-depth]'];const depthDetails=mount.controls.details.open;"
        + "\nconst before=mount.innerHTML;const external={closest(){return this;},getAttribute(){return 'pool';}};mount.listeners.click({target:external});"
        + "process.stdout.write(JSON.stringify({poolFocus,poolDetails,depthFocus,depthDetails,rejected:mount.innerHTML===before}));"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def test_gnn_architecture_renderer_has_no_global_interaction_controls():
    module = _load_gnn_architecture_ui_module()
    source = module.GNN_ARCHITECTURE_UI_JS
    assert "mount.addEventListener('click'" not in source
    assert "mount.addEventListener('change'" not in source
    assert "requestedK" not in source
    assert "population" not in source


def test_gnn_architecture_renderer_source_and_exports_are_isolated_and_motion_safe():
    module = _load_gnn_architecture_ui_module()
    assert module.__all__ == [
        "GNN_ARCHITECTURE_VIEW_MODEL_JS",
        "GNN_ARCHITECTURE_UI_JS",
        "GNN_ARCHITECTURE_CSS",
    ]
    source = module.GNN_ARCHITECTURE_UI_JS
    assert "d3" not in source.lower()
    assert "mount.addEventListener('click'" not in source
    assert "mount.addEventListener('change'" not in source
    assert "mount.contains" not in source
    assert "window." not in source and "document." not in source
    assert "looksFor" in source and "escape" in source


def test_gnn_architecture_css_selectors_are_rooted_and_responsive():
    module = _load_gnn_architecture_ui_module()
    css = module.GNN_ARCHITECTURE_CSS
    root = "#v9-gnn-architecture-comparison"
    for line in css.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("@") or stripped == "}":
            continue
        if "{" in stripped:
            selector = stripped.split("{", 1)[0].strip()
            assert all(part.strip().startswith(root) for part in selector.split(",")), selector
        for variable in ("--surface", "--border", "--text1", "--text2", "--accent"):
            assert f"var({variable})" in css
        assert "@media" in css and "max-width" in css


def test_gnn_architecture_css_keeps_looks_for_column_readable_at_desktop():
    module = _load_gnn_architecture_ui_module()
    css = module.GNN_ARCHITECTURE_CSS
    assert "th:nth-child(2)" in css and "td:nth-child(2)" in css
    assert "text-align: left" in css
    assert "white-space: normal" in css
    assert "max-width" in css
ROOT = Path(__file__).resolve().parents[1]


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
        + V9_UI.UNSUP_AD_CHART_JS
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
    assert "legacyAssisted" not in view


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
    for dead_marker in (
        "renderLegacySchemaV2",
        "legacyAssisted",
        "Legacy oracle-assisted diagnostic",
        "nondeployable",
        "not a ceiling",
        "uad-legacy",
        "uad-badge",
    ):
        assert dead_marker not in ui
    assert "status==='skipped'" in ui
    assert "metric===null" in ui

    for forbidden in (
        "scores are probabilities",
        "calibrated identically",
        "same true-carrier ranking",
        "oracle ceiling",
    ):
        assert forbidden not in lowered


def test_schema_v3_renderer_ignores_legacy_oracle_appendix():
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
    appendix = html[appendix_start:]
    assert "tabular_caught_supervised" in appendix
    assert "Legacy oracle-assisted diagnostic" not in appendix
    assert "legacy fixture" not in html
    assert "nondeployable" not in html
    assert "not a ceiling" not in html


def test_schema_v2_renderer_is_explicitly_unsupported():
    payload = {"schema_version": 2, "modes": {"strict": {}, "assisted": {}}}

    html = _render_unsupervised_html(payload)

    assert "Unsupported anomaly artifact schema" in html
    assert "schema 3" in html
    assert "<h3>Anomaly ranking unavailable</h3>" in html
    assert "Legacy oracle-assisted diagnostic" not in html
    assert "Strict unsupervised" not in html


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


def test_generated_dashboard_v9_bootstrap_does_not_require_d3(generated_dashboard_html):
    html = generated_dashboard_html

    assert "const tip=document.createElement('div')" in html
    assert "const tip=d3.select('body')" not in html


def test_generated_dashboard_has_grouped_accessible_navigation_and_hash_state(
    generated_dashboard_html,
):
    html = generated_dashboard_html

    assert 'data-nav-group="readout"' in html
    assert 'data-nav-group="explore"' in html
    assert 'aria-controls="tab-v9Results"' in html
    assert 'aria-selected="true"' in html
    assert "location.hash" in html
    assert "hashchange" in html
    assert "closest('[data-navigate-tab]')" in html


def test_generated_dashboard_renders_the_overview_tab_exactly_once(
    generated_dashboard_html,
):
    """Only the hash-routed bootstrap may perform the initial render."""
    html = generated_dashboard_html

    assert "_navigateTo(n||'overview')" in html
    assert "Tabs.overview.render()" not in html


def test_generated_dashboard_has_v9_headline_and_responsive_table_contract(
    generated_dashboard_html,
):
    html = generated_dashboard_html

    assert 'id="v9-summary"' in html
    assert "Deployable Hybrid" in html
    assert "Event depth" not in html
    assert "Artifact-supported ranking depth" not in html
    assert ".v9-table-wrap" in html
    assert "font-family: var(--font-body)" in html


def test_generated_dashboard_omits_recovery_coverage_warning_banner(
    generated_dashboard_html,
):
    html = generated_dashboard_html

    assert "Partial coverage: " not in html
    assert "v9-recovery-warning" not in html


def test_generated_dashboard_removes_legacy_duplicate_sections_and_styles(
    generated_dashboard_html,
):
    html = generated_dashboard_html

    assert html.count('data-tab="entityResolution"') == 0
    assert html.count("entityResolution:{rendered:false") == 0
    assert html.count("/* ---- Community Explorer ---- */") == 1


def test_unsupervised_dashboard_explains_modes_and_leakage_boundaries():
    ui_path = ROOT / "scripts" / "dashboard" / "v9_dashboard_ui.py"
    ui = ui_path.read_text()

    assert "V9 designed positive control" in ui
    assert "validation quantile" in ui
    assert "Oracle evaluation is unavailable in production" in ui
    for dead_marker in (
        "Strict unsupervised",
        "Label-assisted benchmark",
        "labels_used_for_fit",
        "positive_prevalence",
        "predicted_positive_rate",
    ):
        assert dead_marker not in ui


def test_v9_ui_explains_what_the_bootstrap_verdict_table_shows():
    ui = UI_MODULE_PATH.read_text()

    assert "Daily bootstrap verdicts" in ui
    assert (
        "Each replicate samples test events with replacement. Both rankers score the "
        "same sample, rank within each day, and use the same quota. The table shows "
        "the Hybrid-minus-baseline gap in hidden-positive event hits across re-draws."
    ) in ui
    for term, gloss in (
        ("<dt>What is re-sampled?</dt>", "Test events are sampled with replacement, then ranked within each day under the same quota."),
        ("<dt>What is measured?</dt>", "The Hybrid-minus-baseline gap in hidden-positive event hits."),
        ("<dt>What does 95% CI mean here?</dt>", "The middle 95% of re-drawn gaps. This shows resampling variability"),
        ("<dt>How should it be read?</dt>", "if it crosses zero"),
    ):
        assert term in ui
        assert gloss in ui
    assert "not the probability that the true gap lies inside" in ui
    assert "event hits, not unique people" in ui
    # The verdict legend must use the same pills the table renders.
    verdict_row = ui.split("<dt>How should it be read?</dt>", 1)[1].split("</div>", 1)[0]
    for pill in ('v9-pill win">Hybrid win', 'v9-pill tie">wash', 'v9-pill loss">baseline win'):
        assert pill in verdict_row

    # Each table says what it is scored on; the daily table is never toggled.
    assert "Every one of the '+fmt(dailyDays)+' test days gets the same quota" in ui
    assert ".v9-sig-note" in V9_UI.V9_RESULTS_CSS


def test_v9_ui_daily_lens_quotes_a_budget_the_run_actually_published():
    ui = UI_MODULE_PATH.read_text()

    assert "const publishedDailyKs=(demo.daily_ks||[])" in ui
    assert "publishedDailyKs.includes(25)?25:" in ui
    for dead in ("daily_found@25'", "daily_budget@25'"):
        assert dead not in ui


def test_v9_ui_keeps_the_crossing_chart_on_the_runs_daily_budgets():
    ui = UI_MODULE_PATH.read_text()
    combined = ui.split("function drawCombined()", 1)[1].split("SIMULATED_CATCH_VIEW_MODEL", 1)[0]

    # The crossing chart reads daily_ks; only the simulated view sweeps its own budgets.
    assert "demo.daily_ks" in combined
    assert "simulated_catch_daily" not in combined
    simulated = ui.split("function drawSimulatedCatches()", 1)[1].split("function drawSig()", 1)[0]
    assert "demo.simulated_catch_daily" in simulated
    assert "daily_ks" not in simulated


def test_v9_results_and_anomaly_css_keep_readout_presentation_contract():
    results = V9_UI.V9_RESULTS_CSS
    anomaly = V9_UI.UNSUP_AD_CSS

    for hook in (
        ".v9-summary-lead",
        ".v9-summary-stat",
        ".v9-story",
        ".v9-chart-block",
        ".v9-seg button.on",
    ):
        assert hook in results

    for token in (
        "var(--sunk)",
        "var(--surface)",
        "var(--elevated)",
        "var(--border-strong)",
        "var(--text1)",
        "var(--text2)",
        "var(--text3)",
        "var(--data-gnn)",
        "var(--warning)",
        "var(--positive)",
    ):
        assert token in results

    assert "font-size: var(--fs-xs)" in results
    assert "font-size: var(--fs-lg)" in results
    assert "font-size: var(--fs-base)" in results
    assert ".v9-seg button.on { background: var(--accent-soft); color: var(--accent-hover);" in results
    assert "flex-wrap: wrap" in results
    assert "min-width: 0" in results
    assert "overflow-x: auto" in results

    for token in ("var(--surface)", "var(--elevated)", "var(--border-strong)", "var(--text1)", "var(--text2)", "var(--text3)"):
        assert token in anomaly
    assert "font-size: var(--fs-xs)" in anomaly
    assert "@media(max-width:700px)" in anomaly
    assert "grid-template-columns: minmax(0, 1fr)" in anomaly
    assert "min-width: 0" in anomaly


def test_v9_results_supporting_labels_use_readable_secondary_text():
    css = V9_UI.V9_RESULTS_CSS
    for selector in (
        "#tab-v9Results .v9-summary-stat span",
        "#tab-v9Results .v9-capacity-budget span",
        "#tab-v9Results .v9-volume-stat span",
    ):
        rule = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
        assert rule and "color: var(--text2)" in rule.group(1), selector


def test_v9_non_simulated_chart_mount_keeps_svg_labels_readable_on_narrow_views():
    css = V9_UI.V9_RESULTS_CSS
    mount = re.search(r"#tab-v9Results #v9-volume\s*\{([^}]*)\}", css)
    chart = re.search(
        r"#tab-v9Results #v9-volume \.v9-combined-chart\s*\{([^}]*)\}", css
    )

    assert mount and "overflow-x: auto" in mount.group(1)
    assert mount and "min-width: 0" in mount.group(1)
    assert chart and "min-width: 720px" in chart.group(1)


def test_anomaly_strata_labels_wrap_instead_of_ellipsizing():
    css = V9_UI.UNSUP_AD_CSS
    labels = re.search(r"\.uad-strata-row > span\s*\{([^}]*)\}", css)
    _, separator, mobile_css = css.partition("@media(max-width:700px){")

    assert labels
    assert "white-space: normal" in labels.group(1)
    assert "overflow-wrap: anywhere" in labels.group(1)
    assert "white-space: nowrap" not in labels.group(1)
    assert "text-overflow: ellipsis" not in labels.group(1)
    assert separator
    assert "grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr) 44px;" in mobile_css


def test_v9_mobile_best_capacity_row_keeps_semantic_accent():
    css = V9_UI.V9_RESULTS_CSS
    _, separator, mobile_css = css.partition("@media(max-width:700px){")
    best = re.search(
        r"#tab-v9Results \.v9-capacity-row\.is-best\s*\{([^}]*)\}",
        mobile_css,
    )

    assert separator and best
    assert "var(--positive)" in best.group(1) or "var(--accent)" in best.group(1)


def test_v9_capacity_metric_labels_use_readable_secondary_text():
    css = V9_UI.V9_RESULTS_CSS
    rule = re.search(
        r"#tab-v9Results \.v9-capacity-metric span\s*\{([^}]*)\}", css
    )

    assert rule and "color: var(--text2)" in rule.group(1)


def test_anomaly_charts_keep_svg_text_readable_with_narrow_view_scroll():
    css = V9_UI.UNSUP_AD_CSS
    chart = re.search(r"\.uad-chart\s*\{([^}]*)\}", css)
    figure = re.search(r"\.uad-figure\s*\{([^}]*)\}", css)

    assert chart and "min-width: 720px" in chart.group(1)
    assert figure and "overflow-x: auto" in figure.group(1)


def test_v9_lens_and_capacity_metadata_use_readable_secondary_text():
    css = V9_UI.V9_RESULTS_CSS
    for selector in (
        "#tab-v9Results .v9-lens-stat span",
        "#tab-v9Results .v9-capacity-found small",
    ):
        rule = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
        assert rule
        assert "color: var(--text2)" in rule.group(1), selector
        assert "font-size: var(--fs-xs)" in rule.group(1), selector


def test_simulated_view_model_defaults_to_the_five_per_day_budget():
    arms = {
        arm: _simulated_arm({
            budget: [{"date": "2025-01-01", "found": budget}]
            for budget in (5, 10, 25)
        })
        for arm in ("baseline", "hybrid")
    }

    view = _run_simulated_view_model({"arms": arms}, None)

    assert view["budgets"] == [5, 10, 25]
    assert view["selected"] == 5


def _run_unsupervised_chart_js(expression):
    script = (
        V9_UI.UNSUP_AD_VIEW_MODEL_JS
        + V9_UI.UNSUP_AD_CHART_JS
        + "\nfunction esc(v){return String(v ?? '');}"
        + "\nprocess.stdout.write(JSON.stringify(" + expression + "));"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def test_unsupervised_chart_axis_only_prints_round_ticks():
    recall = _run_unsupervised_chart_js("uadAxis([0.211, 0.302, 0.133], 0.05, 0.1, 5)")
    assert recall["max"] == 0.4
    assert recall["ticks"] == [0, 0.1, 0.2, 0.3, 0.4]

    lift = _run_unsupervised_chart_js("uadAxis([3.34, 5.8], 1, 2, 5)")
    assert lift["max"] == 6
    assert lift["ticks"] == [0, 2, 4, 6]


def test_unsupervised_chart_model_pins_each_arm_to_its_own_palette_slot():
    view = {
        "primary": [
            {"id": "tabular_unlabeled", "metadata": {"label": "Tabular unlabeled"},
             "regions": [{"region": "North", "status": "completed",
                          "metrics": {"missedRecall": 0.2}}]},
            {"id": "relational_caught_supervised", "metadata": {"label": "Relational PU"},
             "regions": [{"region": "North", "status": "completed",
                          "metrics": {"missedRecall": 0.3}},
                         {"region": "Skipped", "status": "skipped", "skipReason": "thin"}]},
        ],
        "ablation": [
            {"id": "tabular_caught_supervised", "metadata": {},
             "regions": [{"region": "South", "status": "completed",
                          "metrics": {"missedRecall": 0.1}}]},
        ],
    }

    model = _run_unsupervised_chart_js("buildUnsupervisedADChartModel(" + json.dumps(view) + ")")

    assert model["available"] is True
    assert model["regions"] == ["North", "South"]
    # Colour follows the arm identity, never its position in the lineup.
    assert [item["color"] for item in model["primary"]] == ["#3987e5", "#199e70"]
    assert [item["color"] for item in model["ablation"]] == ["#c98500"]
    # A skipped region never becomes a plotted point.
    assert list(model["primary"][1]["byRegion"]) == ["North"]


def _completed_region(region, recall, precision, lift):
    return {
        "status": "completed",
        "feature_count": 18,
        "threshold_metadata": {
            "threshold_source": "validation_score_quantile",
            "threshold_quantile": 0.9,
            "threshold_comparator": "greater_equal",
        },
        "label_metadata": {"caught_positive_count": 10, "immature_label_count": 1,
                           "fit_signal": "unlabeled_feature_distribution"},
        "realized_test_alert_rate": 0.1,
        "scored_test": {"threshold": 0.5},
        "evaluation_only": {
            "all_carrier_events": {"recall": recall + 0.1, "precision": precision + 0.1},
            "missed_at_event": {"recall": recall, "precision": precision},
            "no_prior_catch_missed_events": {"recall": recall - 0.05},
            "lifetime_never_caught_people": {"recall": recall - 0.06, "found": 40},
            "observed_catch_enrichment": {"precision": precision, "lift_over_prevalence": lift},
        },
    }


def _charted_payload():
    payload = _schema_v3_payload()
    payload["arm_metadata"] = {
        arm_id: {"label": arm_id, "feature_count": 18}
        for arm_id in ("tabular_unlabeled", "relational_unlabeled",
                       "relational_caught_supervised", "tabular_caught_supervised")
    }
    payload["arms"] = {
        "tabular_unlabeled": {"North": _completed_region("North", 0.21, 0.099, 3.3)},
        "relational_unlabeled": {"North": _completed_region("North", 0.30, 0.152, 3.8)},
        "relational_caught_supervised": {"North": _completed_region("North", 0.20, 0.137, 5.8)},
        "tabular_caught_supervised": {"North": _completed_region("North", 0.12, 0.081, 4.6)},
    }
    return payload


def test_schema_v3_renderer_charts_the_arms_before_the_metric_tables():
    html = _render_unsupervised_html(_charted_payload())

    figures_start = html.index('<div class="uad-figures">')
    tables_start = html.index('<h3 class="uad-mode-heading">Primary deployability progression</h3>')
    assert figures_start < tables_start

    figures = html[figures_start:tables_start]
    for title in ("Missed carrier events found, by region",
                  "Observed-catch enrichment lift",
                  "What each arm trades away"):
        assert title in figures
    # Each figure ships a legend, an SVG, and a screen-reader table view.
    assert figures.count('<svg class="uad-chart"') == 3
    assert figures.count('class="uad-legend"') >= 4
    for table_id in ("uad-missed-recall-data", "uad-lift-data", "uad-tradeoff-data"):
        assert 'id="' + table_id + '" class="uad-sr-only"' in figures
        assert 'aria-describedby="' + table_id + '"' in figures
    # The enrichment reference line is explained in the legend, not on top of a bar.
    assert "1× = no enrichment" in figures
    assert "uad-legend-rule" in figures


def test_schema_v3_region_cards_visualise_the_recall_strata():
    html = _render_unsupervised_html(_charted_payload())
    card = html.split('<h3 class="uad-mode-heading">Primary deployability progression</h3>', 1)[1]

    assert 'class="uad-strata"' in card
    for label in ("All carrier events", "Missed at event", "No prior catch", "Never-caught people"):
        assert label in card
    # The strata bars share one scale so cards stay comparable between arms.
    assert card.count("recall, shared 0 to 40.0% scale") == 4
    # The numeric table is kept alongside the bars, not replaced by them.
    assert "Missed-at-event recall / precision" in card


def test_unsupervised_renderer_stays_inert_without_a_live_dom():
    # The node harness has no querySelectorAll; tooltip wiring must not throw.
    html = _render_unsupervised_html(_charted_payload())

    assert "data-tip=" in html
    assert "wireUnsupervisedADTooltips" in V9_UI.UNSUP_AD_JS
