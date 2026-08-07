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
    assert "eventDepth" not in result
    assert result["observability"]["netPeople"] == 2


def test_summary_runtime_builds_complete_dataset_snapshot():
    script = SUMMARY.SUMMARY_PAGE_RUNTIME_JS + """
const result = DashboardRuntime.buildDatasetSnapshot({
  corpus: 'synthetic_cbp_graph_corpus_v9',
  total_nodes: 636606, total_edges: 2090447,
  total_events: 200000, total_communities: 50052
}, {
  node_type_counts: {
    person: 120000, event: 200000, document: 144000,
    location: 77854, officer_team: 2000, vehicle: 72000,
    business: 8000, arrest: 4739, seizure: 8013
  },
  edge_type_counts: {
    PERSON_CROSSED_EVENT: 333640,
    DOCUMENT_PRESENTED_IN_EVENT: 333640,
    PERSON_USED_DOCUMENT: 200000
  }
}, {
  features: ['f01', 'f02', 'f03', 'f04', 'f05', 'f06', 'f07',
    'f08', 'f09', 'f10', 'f11', 'f12', 'f13', 'f14'],
  model_arms: {baseline: {label: 'HGB tabular baseline'}, hybrid: {
    label: 'Baseline + GraphSAGE rank-fusion Hybrid'
  }},
  gnn_arm: 'sage', gnn_seeds: [0, 1, 2], hybrid_fusion_w_gnn: 0.7
});
process.stdout.write(JSON.stringify(result));
"""
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    result = json.loads(completed.stdout)

    assert result["available"] is True
    assert result["totals"] == {
        "nodes": 636606,
        "edges": 2090447,
        "events": 200000,
        "communities": 50052,
    }
    assert result["nodeTypes"] == [
        {"label": "event", "count": 200000},
        {"label": "document", "count": 144000},
        {"label": "person", "count": 120000},
        {"label": "location", "count": 77854},
        {"label": "vehicle", "count": 72000},
        {"label": "seizure", "count": 8013},
        {"label": "business", "count": 8000},
        {"label": "arrest", "count": 4739},
        {"label": "officer_team", "count": 2000},
    ]
    assert result["edgeTypes"] == [
        {"label": "DOCUMENT_PRESENTED_IN_EVENT", "count": 333640},
        {"label": "PERSON_CROSSED_EVENT", "count": 333640},
        {"label": "PERSON_USED_DOCUMENT", "count": 200000},
    ]
    assert result["models"]["baseline"]["label"] == "HGB tabular baseline"
    assert result["models"]["baseline"]["featureCount"] == 14
    assert result["models"]["hybrid"]["label"] == (
        "Baseline + GraphSAGE rank-fusion Hybrid"
    )
    assert result["models"]["hybrid"]["gnnArm"] == "GraphSAGE"
    assert result["models"]["hybrid"]["seeds"] == 3
    assert result["models"]["hybrid"]["fusionWeight"] == 0.7


def test_summary_runtime_fails_closed_for_missing_or_malformed_snapshot_metadata():
    script = SUMMARY.SUMMARY_PAGE_RUNTIME_JS + """
const results = [
  DashboardRuntime.buildDatasetSnapshot({}, {}, {}),
  DashboardRuntime.buildDatasetSnapshot({
    total_nodes: -1, total_edges: 2.5, total_events: 3, total_communities: 4
  }, {node_type_counts: {person: -1}, edge_type_counts: {REL: 1}}, {})
];
process.stdout.write(JSON.stringify(results));
"""
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    results = json.loads(completed.stdout)

    assert results[0]["available"] is False
    assert results[1]["available"] is False
    assert results[1]["totals"]["nodes"] is None
    assert results[1]["nodeTypes"] == []
    assert results[1]["edgeTypes"] == [{"label": "REL", "count": 1}]


def test_summary_renderer_includes_dataset_snapshot_contract_markers():
    renderer = SUMMARY.SUMMARY_PAGE_RENDERER_JS

    for marker in (
        "Dataset and models",
        "Total nodes",
        "Total edges",
        "Total events",
        "Total communities",
        "node-type-breakdown",
        "edge-type-breakdown",
        "HGB tabular baseline",
        "Baseline + GraphSAGE rank-fusion Hybrid",
    ):
        assert marker in renderer
    assert "event-depth-evidence" not in renderer
    assert "event-depth artifact" not in renderer


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


def test_summary_renderer_uses_guided_evidence_order_and_plain_language_headings():
    renderer = SUMMARY.SUMMARY_PAGE_RENDERER_JS
    for marker in (
        "Why the graph can help",
        "Dataset and models",
        "V9 is a deliberately connected synthetic positive control",
    ):
        assert marker in renderer
    assert "What the result means" not in renderer
    assert "Limits and provenance" not in renderer
    assert "Canonical operational comparison unavailable." not in renderer
    assert renderer.index("Why the graph can help") < renderer.index("Dataset and models")
    assert renderer.index("Dataset and models") < renderer.index("Single-seed observability diagnostic")
