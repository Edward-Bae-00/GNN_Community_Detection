import importlib.util
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER_SPEC = importlib.util.spec_from_file_location(
    "build_v9_dashboard", ROOT / "Documents/Data/scripts/build_v9_dashboard.py"
)
BUILDER = importlib.util.module_from_spec(BUILDER_SPEC)
BUILDER_SPEC.loader.exec_module(BUILDER)

SUMMARY_SPEC = importlib.util.spec_from_file_location(
    "v9_summary_page", ROOT / "Documents/Data/scripts/v9_summary_page.py"
)
SUMMARY = importlib.util.module_from_spec(SUMMARY_SPEC)
SUMMARY_SPEC.loader.exec_module(SUMMARY)


def test_summary_renderer_replaces_only_the_existing_overview_renderer():
    template = (
        "const Tabs={"
        "overview:{rendered:false,render(){const nested={value:'}'};}},"
        "explorer:{rendered:false,render(){}}};"
    )
    replacement = "overview:{rendered:false,render(){return 'summary';}},"

    rendered = BUILDER._replace_dashboard_renderer(template, "overview", replacement)

    assert rendered.count("overview:{rendered:false,render(){") == 1
    assert "const nested" not in rendered
    assert "explorer:{rendered:false,render(){}}" in rendered


def test_summary_runtime_validates_operational_and_as_of_evidence():
    script = SUMMARY.SUMMARY_PAGE_RUNTIME_JS + """
const result = DashboardRuntime.buildResearchSummary({
  operational_unique_person_recovery: {
    scope: 'three-seed', inspections_per_day: 2000,
    baseline_people: 10, hybrid_people: 14, net_people: 4
  },
  overall: {
    baseline: {'found@2000': 20},
    hybrid: {'found@2000': 25}
  }
}, {
  schema_version: '2.0',
  policy: {observability_seed: 0},
  summary: {baseline_recovered: 3, hybrid_total: 5, net_gain: 2}
});
process.stdout.write(JSON.stringify(result));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert result["canonicalOperational"]["netPeople"] == 4
    assert result["eventDepth"] == {
        "available": True,
        "k": 2000,
        "baselineEventHits": 20,
        "hybridEventHits": 25,
        "netEventHits": 5,
    }
    assert result["observability"]["netPeople"] == 2


def test_summary_renderer_and_runtime_are_node_syntax_valid():
    script = (
        SUMMARY.SUMMARY_PAGE_RUNTIME_JS
        + "\nconst Tabs={"
        + SUMMARY.SUMMARY_PAGE_RENDERER_JS
        + "explorer:{rendered:false,render(){}}};"
    )
    subprocess.run(
        ["node", "--check", "-"],
        input=script,
        check=True,
        capture_output=True,
        text=True,
    )
