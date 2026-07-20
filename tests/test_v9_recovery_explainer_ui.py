import copy
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


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
            "observability_seed": 0,
            "gnn_arm": "sage",
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
            "hybrid_only_count": hybrid_only,
            "explanation_limit": 40,
            "attempted_count": 2,
            "explained_count": 2,
            "failed_count": 0,
        },
        "hybrid_only_cases": [
            {
                "case_id": "case:p1",
                "person_id": "p1",
                "event_id": "e1",
                "scoring_day": "2025-01-02T00:00:00Z",
                "baseline_rank": 40,
                "seed0_gnn_rank": 3,
                "seed0_hybrid_rank": 8,
                "hybrid_rank_uplift": 32,
                "gnn_percentile_uplift": 0.5,
                "relationship_categories": ["COTRAVEL"],
                "stable_factor_status": "stable",
            },
            {
                "case_id": "case:p2",
                "person_id": "p2",
                "event_id": "e2",
                "scoring_day": "2025-01-03T00:00:00Z",
                "baseline_rank": 30,
                "seed0_gnn_rank": 5,
                "seed0_hybrid_rank": 10,
                "hybrid_rank_uplift": 20,
                "gnn_percentile_uplift": 0.7,
                "relationship_categories": ["RESIDENCE"],
                "stable_factor_status": "unstable",
            },
        ],
        "explanations": [
            {
                "case_id": "case:p1",
                "person_id": "p1",
                "decision_trace": {
                    "baseline_rank": 40,
                    "seed0_gnn_rank": 3,
                    "seed0_hybrid_rank": 8,
                },
                "factors": [
                    {
                        "factor_id": "factor:rel:1",
                        "label": "COTRAVEL factor",
                        "kind": "edge_source_set",
                        "counterfactual": {
                            "original_hybrid_rank": 8,
                            "ablated_hybrid_rank": 14,
                        },
                        "restart": {
                            "selection_frequency": 1.0,
                            "iqr": 0.1,
                            "source": "edge_mask",
                        },
                        "stability": "stable",
                        "provenance_expansion_ids": [
                            "provenance:factor:rel:1"
                        ],
                    }
                ],
                "community": {
                    "complete": True,
                    "nodes": [
                        {
                            "node_id": "p2",
                            "x": 0.8,
                            "y": 0.5,
                            "target": False,
                            "pooled_member": True,
                        },
                        {
                            "node_id": "p1",
                            "x": 0.5,
                            "y": 0.5,
                            "target": True,
                            "pooled_member": True,
                        },
                    ],
                    "edges": [
                        {
                            "edge_id": "edge-1",
                            "u": "p1",
                            "v": "p2",
                            "edge_type": "COTRAVEL",
                            "explainer_median": 0.8,
                        },
                    ],
                    "provenance_expansions": [
                        {
                            "expansion_id": "provenance:factor:rel:1",
                            "label": "outside message community",
                            "nodes": [
                                {
                                    "node_id": "p2",
                                    "x": 0.8,
                                    "y": 0.5,
                                },
                                {
                                    "node_id": "p3",
                                    "x": 0.95,
                                    "y": 0.2,
                                },
                            ],
                            "edges": [
                                {
                                    "edge_id": "provenance-edge-1",
                                    "u": "p2",
                                    "v": "p3",
                                    "edge_type": "SHARED_PLATE",
                                }
                            ],
                        }
                    ],
                },
                "flow_stages": [
                    {
                        "stage_id": "first_hop",
                        "node_ids": ["p1", "p2"],
                        "edge_ids": ["edge-1"],
                        "emphasized_edge_ids": ["edge-1"],
                    },
                    {
                        "stage_id": "second_hop",
                        "node_ids": ["p1", "p2"],
                        "edge_ids": ["edge-1"],
                        "emphasized_edge_ids": [],
                    },
                    {
                        "stage_id": "component_pool",
                        "node_ids": ["p1", "p2"],
                        "edge_ids": ["edge-1"],
                        "emphasized_edge_ids": ["edge-1"],
                    },
                    {
                        "stage_id": "rank_fusion",
                        "node_ids": ["p1", "p2"],
                        "edge_ids": ["edge-1"],
                        "emphasized_edge_ids": [],
                    },
                ],
                "evidence_boundary": {
                    "snapshot": "2025-01-02T00:00:00Z",
                    "edge_rule": "available_time < snapshot",
                    "caught_rule": "label_available_time_utc < snapshot",
                },
                "llm_narrative": {
                    "source": "deterministic_template",
                    "model": None,
                    "prompt_version": "v1",
                    "summary": "Seed 0 evidence summary.",
                    "summary_source_refs": ["scope.observability_seed"],
                    "claims": [],
                    "validated": True,
                },
            },
            {
                "case_id": "case:p2",
                "person_id": "p2",
                "factors": [],
                "community": {
                    "complete": True,
                    "nodes": [{"node_id": "p2", "x": 0.5, "y": 0.5}],
                    "edges": [],
                    "provenance_expansions": [],
                },
                "flow_stages": [
                    {
                        "stage_id": stage_id,
                        "node_ids": ["p2"],
                        "edge_ids": [],
                        "emphasized_edge_ids": [],
                    }
                    for stage_id in (
                        "first_hop",
                        "second_hop",
                        "component_pool",
                        "rank_fusion",
                    )
                ],
                "llm_narrative": {
                    "source": "deterministic_template",
                    "model": None,
                    "prompt_version": "v1",
                    "summary": "Another seed 0 summary.",
                    "summary_source_refs": ["scope.observability_seed"],
                    "claims": [],
                    "validated": True,
                },
            },
        ],
        "generation_diagnostics": {"failed_attempts": []},
    }


def test_schema_v2_ui_contract_lazy_loads_both_complete_cohorts():
    js = UI.V9_RECOVERY_EXPLAINER_JS

    for token in (
        "schema_version==='2.0'",
        "Hybrid-only",
        "Baseline-only",
        "recoveryFetchJson",
        "python -m http.server 8000 --directory Documents/Data/v9_dashboard",
        "http://localhost:8000/index.html",
        "Validated local Gemma narrative",
        "Selected anchor-event ranks",
        "B / G / H values are anchor-event ranks",
        "attributions.top_edges",
        "attributions.top_local_nodes",
        "attributions.top_features",
        "decision_ledger.component_pooling.top_members_by_absolute_contribution",
        "decision_ledger.rank_fusion",
        "Local GNNExplainer overlay",
        "No GNN explanation is generated for Baseline-only cases by policy.",
        "Complete community",
        "loaded /",
        "Node search",
        "current node page",
        "Relation filter",
        "Node page",
        "Edge page",
        "Provenance page",
        "Expansion membership page",
        "Case attribution overlay node page",
        "Case attribution overlay edge page",
        "Case attribution overlay provenance page",
        "Case attribution overlay expansion membership page",
    ):
        assert token in js

    assert "Explanation attempt failed or was not selected." not in js
    assert "Selected unique-person ranks" not in js


def test_schema_v2_ui_fetches_only_requested_sidecar_pages():
    js = UI.V9_RECOVERY_EXPLAINER_JS

    assert "loadRecoveryChunkPage" in js
    assert "for(const chunk of state.community.edge_chunks" not in js
    assert "for(const chunk of state.community.provenance_chunks" not in js
    assert "for(const chunk of state.community.node_chunks" not in js
    assert "state.community.nodes" not in js
    assert "loadRecoveryChunkPage('node',0" in js
    assert "state.loadedEdgeCount" in js
    assert "state.loadedProvenanceCount" in js
    assert "state.loadedNodeCount" in js
    assert "state.membershipPages" in js


def test_schema_v2_ui_lazily_merges_normalized_day_view_state():
    js = UI.V9_RECOVERY_EXPLAINER_JS

    for token in (
        "node_status_chunks",
        "edge_membership_chunks",
        "node_statuses",
        "edge_memberships",
        "resolvedRows",
        "catalogIndex",
        "recoveryCatalogChunkCache",
    ):
        assert token in js
    assert "Salient counterfactual factors" in js


def test_schema_v2_ui_lazily_pages_case_overlay_evidence_separately():
    js = UI.V9_RECOVERY_EXPLAINER_JS

    for token in (
        "state.overlayNodePages",
        "state.overlayEdgePages",
        "state.overlayProvenancePages",
        "state.overlayMembershipPages",
        "loadRecoveryChunkPage('overlay-node',0",
        "loadRecoveryChunkPage('overlay-edge',0",
        "loadRecoveryChunkPage('overlay-provenance',0",
        "loadRecoveryChunkPage('overlay-membership',0",
    ):
        assert token in js
    assert "for(const chunk of state.caseData.overlay_evidence" not in js


def test_schema_v2_ui_discards_stale_async_case_responses():
    js = UI.V9_RECOVERY_EXPLAINER_JS

    assert "let recoveryRequestToken=0" in js
    assert "const requestToken=++recoveryRequestToken" in js
    assert "requestToken!==recoveryRequestToken" in js
    assert "state.caseData=await recoveryFetchJson" not in js
    assert "state.community=await recoveryFetchJson" not in js


def _strict_manifest_artifact():
    summary = {
        "baseline_recovered": 1,
        "recovered_by_both": 0,
        "hybrid_only_recovered": 1,
        "baseline_only_recovered": 1,
        "hybrid_total": 1,
        "net_gain": 0,
    }
    cohorts = {
        "hybrid_only": [{
            "case_id": "h1", "person_id": "p1", "community_key": "c1"
        }],
        "baseline_only": [{
            "case_id": "b1", "person_id": "p2", "community_key": "c1"
        }],
    }
    return {
        "schema_version": "2.0",
        "bundle_id": "0123456789abcdef01234567",
        "sidecar_base": "recovery/bundles/0123456789abcdef01234567/",
        "policy": {
            "observability_seed": 0,
            "inspections_per_day": 5,
            "gnn_arm": "sage",
            "surrounding_results_seeds": [0, 1, 2],
        },
        "summary": summary,
        "coverage": {
            "hybrid_only_count": 1,
            "baseline_only_count": 1,
            "explained_count": 1,
            "llm_validated_count": 1,
            "failed_count": 0,
            "complete": True,
        },
        "cohorts": cohorts,
        "case_index": {
            "h1": {
                "path": "objects/h1.json", "sha256": "a",
                "cohort": "hybrid_only", "community_key": "c1",
            },
            "b1": {
                "path": "objects/b1.json", "sha256": "b",
                "cohort": "baseline_only", "community_key": "c1",
            },
        },
        "community_index": {"c1": {"path": "objects/c1.json", "sha256": "c"}},
    }


@pytest.mark.parametrize(
    "mutation",
    [
        lambda artifact: artifact["policy"].update(gnn_arm="rgcn"),
        lambda artifact: artifact["policy"].update(surrounding_results_seeds=[0, 2]),
        lambda artifact: artifact["summary"].update(hybrid_total=2),
        lambda artifact: artifact["cohorts"]["baseline_only"].__setitem__(
            0, artifact["cohorts"]["hybrid_only"][0]
        ),
        lambda artifact: artifact["case_index"].pop("b1"),
        lambda artifact: artifact["case_index"]["h1"].update(
            cohort="baseline_only"
        ),
        lambda artifact: artifact["case_index"]["h1"].update(
            community_key="c2"
        ),
    ],
)
def test_schema_v2_manifest_helper_fails_closed_on_identity_contract(mutation):
    artifact = _strict_manifest_artifact()
    mutation(artifact)
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nprocess.stdout.write(JSON.stringify(buildRecoveryManifestViewModel("
        + json.dumps(artifact)
        + ")));"
    )

    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )

    assert json.loads(completed.stdout)["available"] is False


@pytest.mark.parametrize(
    ("bundle_id", "sidecar_base"),
    [
        ("0123456789abcdef01234567", None),
        ("0123456789abcdef01234567", ""),
        ("0123456789abcdef01234567", "recovery/bundles/../"),
        ("0123456789abcdef01234567", "recovery/bundles/./"),
        ("0123456789abcdef01234567", "recovery/bundles/abcdefabcdefabcdefabcdef/"),
        ("not-a-producer-id", "recovery/bundles/not-a-producer-id/"),
    ],
)
def test_schema_v2_manifest_helper_requires_safe_explicit_sidecar_base(
    bundle_id, sidecar_base
):
    artifact = _strict_manifest_artifact()
    artifact["bundle_id"] = bundle_id
    if sidecar_base is None:
        artifact.pop("sidecar_base")
    else:
        artifact["sidecar_base"] = sidecar_base
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nprocess.stdout.write(JSON.stringify(buildRecoveryManifestViewModel("
        + json.dumps(artifact)
        + ")));"
    )

    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )

    assert json.loads(completed.stdout)["available"] is False


def test_recovery_fetch_requires_canonical_hash_and_webcrypto():
    script = UI.V9_RECOVERY_EXPLAINER_JS + r"""
(async()=>{
  const errors=[];
  try{await recoveryFetchJson('unused','ABC');}catch(error){errors.push(error.message);}
  const descriptor=Object.getOwnPropertyDescriptor(globalThis,'crypto');
  Object.defineProperty(globalThis,'crypto',{value:undefined,configurable:true});
  try{await recoveryFetchJson('unused','a'.repeat(64));}catch(error){errors.push(error.message);}
  if(descriptor)Object.defineProperty(globalThis,'crypto',descriptor);
  process.stdout.write(JSON.stringify(errors));
})();
"""

    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )

    errors = json.loads(completed.stdout)
    assert len(errors) == 2
    assert "64-character lowercase SHA-256" in errors[0]
    assert "WebCrypto SHA-256 is required" in errors[1]


def test_schema_v2_chunk_validators_reject_identity_count_and_offset_mismatches():
    script = UI.V9_RECOVERY_EXPLAINER_JS + r"""
const owner={complete:true,node_count:1,edge_count:0,provenance_observation_count:0,
  node_chunks:[{path:'n',sha256:'x',offset:0,count:1}],edge_chunks:[],
  provenance_chunks:[],provenance_expansion_membership_chunks:[]};
const validRef=owner.node_chunks[0];
process.stdout.write(JSON.stringify({
  owner:recoveryValidateChunkOwner(owner),
  badOwner:recoveryValidateChunkOwner({...owner,node_count:2}),
  rows:recoveryValidatedChunkRows({offset:0,count:1,nodes:[{node_id:'p'}]},validRef,'nodes'),
  badOffset:recoveryValidatedChunkRows({offset:1,count:1,nodes:[{node_id:'p'}]},validRef,'nodes'),
  badCount:recoveryValidatedChunkRows({offset:0,count:2,nodes:[{node_id:'p'}]},validRef,'nodes')
}));
"""

    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    result = json.loads(completed.stdout)

    assert result == {
        "owner": True,
        "badOwner": False,
        "rows": [{"node_id": "p"}],
        "badOffset": None,
        "badCount": None,
    }


def test_schema_v2_manifest_helper_enforces_k5_complete_coverage_and_default_case():
    artifact = {
        "schema_version": "2.0",
        "bundle_id": "0123456789abcdef01234567",
        "sidecar_base": "recovery/bundles/0123456789abcdef01234567/",
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
            "seed_level_unique_person_recovery": {
                "inspections_per_day": 5,
                "common_validation_tuned_fusion_weight": 0.75,
                "seeds": {
                    "0": {"hybrid_unique_people_recovered": 8},
                    "1": {"hybrid_unique_people_recovered": 7},
                    "2": {"hybrid_unique_people_recovered": 9},
                },
                "mean": {"hybrid_unique_people_recovered": 8.0},
                "population_sd": {"hybrid_unique_people_recovered": 0.816},
                "score_averaged_ensemble": {"hybrid_unique_people_recovered": 9},
            }
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
            "hybrid_only": [{
                "case_id": "h1", "person_id": "p1", "community_key": "c1"
            }],
            "baseline_only": [{
                "case_id": "b1", "person_id": "p2", "community_key": "c1"
            }],
        },
        "case_index": {
            "h1": {
                "path": "cases/h1.json", "sha256": "abc",
                "cohort": "hybrid_only", "community_key": "c1"
            },
            "b1": {
                "path": "cases/b1.json", "sha256": "def",
                "cohort": "baseline_only", "community_key": "c1"
            },
        },
        "community_index": {"c1": {"path": "communities/c1.json", "sha256": "ghi"}},
    }
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nprocess.stdout.write(JSON.stringify(buildRecoveryManifestViewModel("
        + json.dumps(artifact)
        + ")));"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    view = json.loads(completed.stdout)

    assert view["available"] is True
    assert view["defaultCohort"] == "hybrid_only"
    assert view["defaultCaseId"] == "h1"
    assert view["coverageComplete"] is True
    assert view["seedLevelRecovery"]["seeds"]["0"][
        "hybrid_unique_people_recovered"
    ] == 8


def test_schema_v2_ui_separates_seed_population_ensemble_event_and_person_semantics():
    js = UI.V9_RECOVERY_EXPLAINER_JS

    for token in (
        "Per-seed mean",
        "Population SD",
        "Ensemble ranking / event-level metrics",
        "Individual unique-person overlap",
        "common_validation_tuned_fusion_weight",
        "score_averaged_ensemble",
        "seed_level_unique_person_recovery",
    ):
        assert token in js


def test_schema_v2_ui_has_real_edge_and_provenance_page_controls():
    js = UI.V9_RECOVERY_EXPLAINER_JS

    assert "data-v2-page" in js
    assert "edge-prev" in js
    assert "edge-next" in js
    assert "provenance-prev" in js
    assert "provenance-next" in js


def test_schema_v2_cluster_helper_groups_filtered_nodes_deterministically():
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nprocess.stdout.write(JSON.stringify(recoveryClusterNodes("
        + json.dumps([
            {"node_id": "p2", "cluster_id": "b"},
            {"node_id": "p1", "cluster_id": "a"},
            {"node_id": "x1", "cluster_id": "a"},
        ])
        + ", 'p')));"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )

    assert json.loads(completed.stdout) == [
        {"cluster": "a", "node_ids": ["p1"]},
        {"cluster": "b", "node_ids": ["p2"]},
    ]


def _run_ui(function_name, value, options=None):
    arguments = json.dumps(value)
    if options is not None:
        arguments += "," + json.dumps(options)
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nconst result="
        + function_name
        + "("
        + arguments
        + ");process.stdout.write(JSON.stringify(result));"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def _run_filter_with_input_snapshot(cases, options):
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nconst input="
        + json.dumps(cases)
        + ";const before=JSON.stringify(input);"
        + "const result=filterAndSortRecoveryCases(input,"
        + json.dumps(options)
        + ");process.stdout.write(JSON.stringify({result,input,before}));"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def _run_draw_with_input_snapshot(explanation, options):
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nconst input="
        + json.dumps(explanation)
        + ";const before=JSON.stringify(input);"
        + "const result=buildCommunityDrawCommands(input,"
        + json.dumps(options)
        + ");process.stdout.write(JSON.stringify({result,input,before}));"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def test_ui_javascript_is_valid_and_has_no_rendering_side_effects():
    subprocess.run(
        ["node", "--check", "-"],
        input=UI.V9_RECOVERY_EXPLAINER_JS,
        text=True,
        check=True,
        capture_output=True,
    )
    for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document."):
        assert forbidden not in UI.V9_RECOVERY_EXPLAINER_JS


def test_explorer_source_contract_covers_accessibility_lifecycle_and_states():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    css = UI.V9_RECOVERY_EXPLAINER_CSS

    for token in (
        "function mountV9RecoveryExplainer",
        "function buildCommunityDrawCommands",
        "function graphPoint",
        "textContent",
        "createElement",
        "ResizeObserver",
        "devicePixelRatio",
        "disconnect",
        "removeEventListener",
        "pointerdown",
        "pointermove",
        "pointerup",
        "wheel",
        "aria-label",
        "aria-describedby",
        "Single-seed observability",
        "GraphSAGE seed 0",
        "Main results remain three-seed",
        "No Hybrid-only recoveries in this seed-0 run.",
        "No validated explanation is available for this case.",
        "No stable factor found; inspect measured effects below.",
        "Complete community unavailable.",
        "Local Gemma output was unavailable or rejected.",
        "Overlap unavailable; no values are inferred.",
        "explanation attempts failed validation.",
        "outside message community",
        "Relation colors show observable context",
        "Selected at 25 inspections/day.",
        "Strict as-of evidence boundary",
        "scoring day",
        "recoveryEdgeStyle",
    ):
        assert token in js

    assert js.count("root.addEventListener('click'") == 2
    assert "new WeakMap" in js
    assert "innerHTML" not in js
    assert "window.addEventListener('scroll'" not in js
    assert "ground_truth_community" not in js
    assert "community_propensity" not in js
    assert "future_truth" not in js

    for token in (
        "touch-action: none",
        ":focus-visible",
        "@media(max-width:900px)",
        "@media(max-width:700px)",
        "var(--surface)",
        "var(--accent)",
        ".v9-recovery-stat.is-warning",
        "overflow-x: auto",
        "min-height: 44px",
    ):
        assert token in css

    visible_sources = js + css
    assert "—" not in visible_sources
    assert "–" not in visible_sources


def test_mount_without_a_root_is_a_safe_noop():
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nmountV9RecoveryExplainer(null,null,{});"
        + "process.stdout.write('ok');"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )

    assert completed.stdout == "ok"


def test_countervailing_factor_is_a_valid_signed_effect():
    factor = copy.deepcopy(
        _valid_recovery_artifact()["explanations"][0]["factors"][0]
    )
    factor["stability"] = "countervailing"
    factor["counterfactual"] = {
        "original_hybrid_rank": 8,
        "ablated_hybrid_rank": 5,
    }

    assert _run_ui("recoveryValidFactor", factor) is True


def test_edge_style_uses_restart_aggregated_influence_without_hiding_edges():
    low = _run_ui(
        "recoveryEdgeStyle", {"importance": 0.0, "emphasized": True}
    )
    high = _run_ui(
        "recoveryEdgeStyle", {"importance": 1.0, "emphasized": True}
    )
    background = _run_ui(
        "recoveryEdgeStyle", {"importance": 0.0, "emphasized": False}
    )

    assert low == {"alpha": 0.45, "lineWidth": 1.5}
    assert high == {"alpha": 0.95, "lineWidth": 4.5}
    assert background == {"alpha": 0.18, "lineWidth": 0.85}


def test_warning_card_and_reset_transform_contract_are_explicit():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    reset_branch = js.split("if(value==='reset')", 1)[1].split(
        "if(value==='fit')", 1
    )[0]

    assert "baseline_only_recovered" in js
    assert "is-warning" in js
    assert "state.scale=1" in reset_branch
    assert "state.offsetX=0" in reset_branch
    assert "state.offsetY=0" in reset_branch


@pytest.mark.parametrize(
    "mutate",
    [
        lambda explanation: explanation.pop("evidence_boundary"),
        lambda explanation: explanation["evidence_boundary"].update(
            {"snapshot": "2025-01-03T00:00:00Z"}
        ),
        lambda explanation: explanation["evidence_boundary"].update(
            {"edge_rule": "available_time <= snapshot"}
        ),
        lambda explanation: explanation["evidence_boundary"].update(
            {"caught_rule": "label_available_time_utc <= snapshot"}
        ),
    ],
    ids=["missing", "wrong-snapshot", "bad-edge-rule", "bad-caught-rule"],
)
def test_strict_as_of_boundary_validation_fails_closed(mutate):
    explanation = _valid_recovery_artifact()["explanations"][0]
    mutate(explanation)

    assert _run_ui(
        "validateRecoveryEvidenceBoundary",
        explanation,
        "2025-01-02T00:00:00Z",
    ) == {"available": False, "reason": "invalid-evidence-boundary"}


def test_valid_strict_as_of_boundary_preserves_only_display_fields():
    explanation = _valid_recovery_artifact()["explanations"][0]

    assert _run_ui(
        "validateRecoveryEvidenceBoundary",
        explanation,
        "2025-01-02T00:00:00Z",
    ) == {
        "available": True,
        "snapshot": "2025-01-02T00:00:00Z",
        "edgeRule": "available_time < snapshot",
        "caughtRule": "label_available_time_utc < snapshot",
    }


def test_detail_stops_before_evidence_renderers_when_boundary_is_invalid():
    detail_source = UI.V9_RECOVERY_EXPLAINER_JS.split(
        "function renderDetail", 1
    )[1].split("function render(){", 1)[0]

    validation_index = detail_source.index(
        "validateRecoveryEvidenceBoundary"
    )
    stop_index = detail_source.index("if(!boundaryView.available)")
    factors_index = detail_source.index("renderFactors")
    graph_index = detail_source.index("renderGraph")

    assert validation_index < stop_index < factors_index < graph_index
    invalid_branch = detail_source.split(
        "if(!boundaryView.available)", 1
    )[1].split("const evidence=", 1)[0]
    assert "return;" in invalid_branch


def test_focus_restoration_selects_the_exact_replacement_control():
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nconst focused=[];"
        + "const other={dataset:{recoveryAction:'zoom',recoveryValue:'out'},"
        + "focus(){focused.push('other');}};"
        + "const target={dataset:{recoveryAction:'zoom',recoveryValue:'in'},"
        + "focus(){focused.push('target');}};"
        + "const root={querySelectorAll(){return [other,target];}};"
        + "recoveryRestoreFocus(root,'recoveryAction','zoom','in');"
        + "process.stdout.write(JSON.stringify(focused));"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )

    assert json.loads(completed.stdout) == ["target"]


def test_delegated_click_and_change_restore_focus_after_render():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    click_source = js.split("function onClick", 1)[1].split(
        "function onChange", 1
    )[0]
    change_source = js.split("function onChange", 1)[1].split(
        "function onInput", 1
    )[0]

    assert click_source.index("render();") < click_source.index(
        "recoveryRestoreFocus(root,'recoveryAction',action,value)"
    )
    assert change_source.index("render();") < change_source.index(
        "recoveryRestoreFocus(root,'recoveryChange',action)"
    )


def test_essential_explorer_labels_use_the_contrast_safe_text_token():
    assert "var(--text3)" not in UI.V9_RECOVERY_EXPLAINER_CSS
    assert UI.V9_RECOVERY_EXPLAINER_CSS.count("var(--text2)") >= 12


def test_build_recovery_view_model_accepts_exact_policy_and_overlap_algebra():
    view = _run_ui("buildRecoveryEvidenceViewModel", _valid_recovery_artifact())

    assert view["available"] is True
    assert view["scope"] == {
        "seed": 0,
        "arm": "sage",
        "inspectionsPerDay": 25,
        "surroundingResultsSeeds": [0, 1, 2],
    }
    assert view["summary"]["values"] == {
        "baseline_recovered": 8,
        "recovered_by_both": 8,
        "hybrid_only_recovered": 3,
        "baseline_only_recovered": 0,
        "hybrid_total": 11,
        "net_gain": 3,
    }
    assert view["summary"]["containment"] is True
    assert view["summary"]["tone"] == "success"


@pytest.mark.parametrize(
    ("policy_key", "bad_value"),
    [
        ("observability_seed", "0"),
        ("observability_seed", 1),
        ("gnn_arm", "rgcn"),
        ("inspections_per_day", "25"),
        ("inspections_per_day", 50),
        ("surrounding_results_seeds", [0, 1]),
        ("surrounding_results_seeds", [0, 1, 2, 3]),
        ("surrounding_results_seeds", [0, 2, 1]),
        ("percentile_reference_id", ""),
    ],
)
def test_build_recovery_view_model_rejects_wrong_scope(policy_key, bad_value):
    artifact = _valid_recovery_artifact()
    artifact["policy"][policy_key] = bad_value

    assert _run_ui("buildRecoveryEvidenceViewModel", artifact) == {
        "available": False,
        "reason": "invalid-observability-scope",
    }


@pytest.mark.parametrize(
    ("summary_key", "bad_value"),
    [
        ("baseline_recovered", "8"),
        ("recovered_by_both", None),
        ("hybrid_only_recovered", -1),
        ("baseline_only_recovered", 0.5),
        ("hybrid_total", None),
        ("net_gain", "3"),
    ],
)
def test_all_six_overlap_values_require_exact_numeric_types(summary_key, bad_value):
    artifact = _valid_recovery_artifact()
    artifact["summary"][summary_key] = bad_value

    view = _run_ui("buildRecoveryEvidenceViewModel", artifact)

    assert view["available"] is True
    assert view["summary"] == {
        "unavailable": True,
        "reason": "invalid-set-algebra",
    }


@pytest.mark.parametrize(
    ("summary_key", "bad_value"),
    [
        ("baseline_recovered", 9),
        ("hybrid_total", 12),
        ("net_gain", 4),
    ],
)
def test_overlap_summary_rejects_inexact_set_algebra(summary_key, bad_value):
    artifact = _valid_recovery_artifact()
    artifact["summary"][summary_key] = bad_value

    view = _run_ui("buildRecoveryEvidenceViewModel", artifact)

    assert view["summary"] == {
        "unavailable": True,
        "reason": "invalid-set-algebra",
    }


def test_overlap_ids_unavailable_never_infers_numbers():
    artifact = _valid_recovery_artifact()
    artifact["summary"]["overlap_ids_available"] = False

    view = _run_ui("buildRecoveryEvidenceViewModel", artifact)

    assert view["summary"] == {
        "unavailable": True,
        "reason": "overlap-ids-unavailable",
    }
    assert "values" not in view["summary"]


def test_nonzero_baseline_only_suppresses_containment_and_warns():
    view = _run_ui(
        "buildRecoveryEvidenceViewModel",
        _valid_recovery_artifact(baseline_only=2),
    )

    assert view["summary"]["containment"] is False
    assert view["summary"]["tone"] == "warning"
    assert "Baseline-only" in view["summary"]["warning"]


@pytest.mark.parametrize(
    ("collection", "bad_value"),
    [
        ("hybrid_only_cases", {}),
        ("explanations", "not-an-array"),
    ],
)
def test_view_model_rejects_wrong_case_collection_types(collection, bad_value):
    artifact = _valid_recovery_artifact()
    artifact[collection] = bad_value

    assert _run_ui("buildRecoveryEvidenceViewModel", artifact) == {
        "available": False,
        "reason": "invalid-case-collections",
    }


@pytest.mark.parametrize("collection", ["hybrid_only_cases", "explanations"])
def test_view_model_rejects_duplicate_case_mappings(collection):
    artifact = _valid_recovery_artifact()
    artifact[collection].append(copy.deepcopy(artifact[collection][0]))

    assert _run_ui("buildRecoveryEvidenceViewModel", artifact) == {
        "available": False,
        "reason": "duplicate-case-id",
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda artifact: artifact["hybrid_only_cases"][0].update(
            {"case_id": ""}
        ),
        lambda artifact: artifact["hybrid_only_cases"][0].update(
            {"hybrid_rank_uplift": "32"}
        ),
        lambda artifact: artifact["hybrid_only_cases"][0].update(
            {"relationship_categories": "COTRAVEL"}
        ),
        lambda artifact: artifact["explanations"][0].update(
            {"case_id": "case:missing"}
        ),
    ],
    ids=[
        "blank-case-id",
        "numeric-string",
        "relations-not-array",
        "orphan-explanation",
    ],
)
def test_view_model_fails_closed_on_malformed_case_records(mutate):
    artifact = _valid_recovery_artifact()
    mutate(artifact)

    assert _run_ui("buildRecoveryEvidenceViewModel", artifact) == {
        "available": False,
        "reason": "invalid-case-records",
    }


def test_filter_and_sort_cases_is_deterministic_and_non_mutating():
    cases = _valid_recovery_artifact()["hybrid_only_cases"]
    original = copy.deepcopy(cases)
    options = {
        "stableStatus": "all",
        "relationshipCategory": "all",
        "sortBy": "gnn_percentile_uplift",
    }

    snapshot = _run_filter_with_input_snapshot(cases, options)
    first = snapshot["result"]
    second = _run_ui("filterAndSortRecoveryCases", cases, options)

    assert [item["case_id"] for item in first] == ["case:p2", "case:p1"]
    assert first == second
    assert snapshot["input"] == original
    assert snapshot["before"] == json.dumps(original, separators=(",", ":"))


def test_filter_full_ties_use_deterministic_code_unit_ids():
    cases = _valid_recovery_artifact()["hybrid_only_cases"]
    tied = copy.deepcopy(cases[0])
    tied.update({"case_id": "case:p10", "person_id": "p10"})
    cases[0].update({"case_id": "case:p2", "person_id": "p2"})
    cases.append(tied)

    result = _run_ui(
        "filterAndSortRecoveryCases",
        cases,
        {"sortBy": "hybrid_rank_uplift"},
    )

    tied_ids = [item["person_id"] for item in result if item["hybrid_rank_uplift"] == 32]
    assert tied_ids == ["p10", "p2"]
    assert "localeCompare" not in UI.V9_RECOVERY_EXPLAINER_JS


def test_filter_and_sort_cases_applies_stability_and_relation_filters():
    cases = _valid_recovery_artifact()["hybrid_only_cases"]

    result = _run_ui(
        "filterAndSortRecoveryCases",
        cases,
        {
            "stableStatus": "stable",
            "relationshipCategory": "COTRAVEL",
            "sortBy": "hybrid_rank_uplift",
        },
    )

    assert [item["case_id"] for item in result] == ["case:p1"]


@pytest.mark.parametrize(
    "narrative_update",
    [
        {"validated": False},
        {"summary": ""},
        {"summary_source_refs": []},
        {"summary_source_refs": [""]},
        {"claims": "not-an-array"},
        {"claims": [{"text": "Claim", "source_refs": []}]},
        {"claims": [{"text": "", "source_refs": ["factor.one"]}]},
    ],
)
def test_narrative_is_hidden_unless_validated_and_fully_sourced(narrative_update):
    narrative = _valid_recovery_artifact()["explanations"][0]["llm_narrative"]
    narrative.update(narrative_update)

    assert _run_ui("validateRecoveryNarrative", narrative)["visible"] is False


def test_valid_narrative_preserves_only_grounded_display_fields():
    narrative = _valid_recovery_artifact()["explanations"][0]["llm_narrative"]
    narrative["claims"] = [
        {
            "text": "Measured claim.",
            "source_refs": ["factors_by_id.factor-1.stability"],
        }
    ]

    view = _run_ui("validateRecoveryNarrative", narrative)

    assert view == {
        "visible": True,
        "summary": "Seed 0 evidence summary.",
        "summarySourceRefs": ["scope.observability_seed"],
        "claims": narrative["claims"],
        "source": "deterministic_template",
        "model": None,
    }


@pytest.mark.parametrize(
    "update",
    [
        {"summary_source_refs": ["made.up.path"]},
        {"source": "llm", "model": None},
        {"source": "llm", "model": "other-model"},
        {"source": "deterministic_template", "model": "gemma4:12b"},
        {"source": "untrusted", "model": None},
        {"prompt_version": "future"},
    ],
    ids=[
        "bogus-ref",
        "llm-missing-model",
        "llm-wrong-model",
        "template-with-model",
        "unknown-source",
        "wrong-prompt-version",
    ],
)
def test_narrative_rejects_invalid_references_and_provenance(update):
    narrative = _valid_recovery_artifact()["explanations"][0]["llm_narrative"]
    narrative.update(update)

    assert _run_ui("validateRecoveryNarrative", narrative)["visible"] is False


@pytest.mark.parametrize(
    ("mode", "stage_id"),
    [
        ("all", "first_hop"),
        ("flow", "second_hop"),
        ("flow", "component_pool"),
        ("flow", "rank_fusion"),
    ],
)
def test_graph_stages_preserve_complete_base_membership(mode, stage_id):
    explanation = _valid_recovery_artifact()["explanations"][0]

    view = _run_ui(
        "buildCommunityStageView",
        explanation,
        {"mode": mode, "stageId": stage_id},
    )

    assert view["available"] is True
    assert view["nodeIds"] == ["p1", "p2"]
    assert view["edgeIds"] == ["edge-1"]
    assert view["mode"] == mode
    assert view["stageId"] == stage_id


@pytest.mark.parametrize(
    "mutate",
    [
        lambda explanation: explanation["community"].update({"complete": False}),
        lambda explanation: explanation["community"].update({"nodes": {}}),
        lambda explanation: explanation["community"].update({"edges": None}),
        lambda explanation: explanation["community"]["nodes"].append(
            {"node_id": "p1"}
        ),
        lambda explanation: explanation["community"]["edges"].append(
            {"edge_id": "edge-2", "u": "p1", "v": "missing"}
        ),
    ],
    ids=[
        "incomplete",
        "nodes-not-array",
        "edges-not-array",
        "duplicate-node-id",
        "unknown-edge-endpoint",
    ],
)
def test_community_view_returns_unavailable_for_malformed_artifact(mutate):
    explanation = _valid_recovery_artifact()["explanations"][0]
    mutate(explanation)

    view = _run_ui(
        "buildCommunityStageView",
        explanation,
        {"mode": "flow", "stageId": "rank_fusion"},
    )

    assert view["available"] is False
    assert "reason" in view


@pytest.mark.parametrize(
    "nodes",
    [
        [],
        [{"node_id": "p2"}],
    ],
    ids=["empty", "focal-person-missing"],
)
def test_complete_community_requires_the_focal_person(nodes):
    explanation = _valid_recovery_artifact()["explanations"][0]
    explanation["community"]["nodes"] = nodes
    explanation["community"]["edges"] = []

    view = _run_ui(
        "buildCommunityStageView",
        explanation,
        {"mode": "flow", "stageId": "rank_fusion"},
    )

    assert view == {
        "available": False,
        "reason": "invalid-community-membership",
    }


def test_community_view_rejects_invalid_mode_or_stage_without_throwing():
    explanation = _valid_recovery_artifact()["explanations"][0]

    assert _run_ui(
        "buildCommunityStageView",
        explanation,
        {"mode": "sampled", "stageId": "rank_fusion"},
    ) == {"available": False, "reason": "invalid-view-options"}
    assert _run_ui(
        "buildCommunityStageView",
        explanation,
        {"mode": "flow", "stageId": "future_truth"},
    ) == {"available": False, "reason": "invalid-view-options"}


@pytest.mark.parametrize(
    ("mode", "stage_id", "expected_emphasis"),
    [
        ("all", "first_hop", ["edge-1"]),
        ("flow", "first_hop", ["edge-1"]),
        ("flow", "second_hop", []),
        ("flow", "component_pool", ["edge-1"]),
        ("flow", "rank_fusion", []),
    ],
)
def test_draw_commands_preserve_base_membership_and_only_change_emphasis(
    mode, stage_id, expected_emphasis
):
    explanation = _valid_recovery_artifact()["explanations"][0]
    snapshot = _run_draw_with_input_snapshot(
        explanation,
        {
            "mode": mode,
            "stageId": stage_id,
            "selectedFactorId": None,
            "query": "p1",
        },
    )
    result = snapshot["result"]

    assert result["available"] is True
    assert [node["id"] for node in result["nodes"]] == ["p1", "p2"]
    assert [edge["id"] for edge in result["edges"]] == ["edge-1"]
    assert [
        edge["id"] for edge in result["edges"] if edge["emphasized"]
    ] == expected_emphasis
    assert result["provenanceNodes"] == []
    assert result["provenanceEdges"] == []
    assert next(node for node in result["nodes"] if node["id"] == "p1")[
        "matched"
    ] is True
    assert snapshot["input"] == explanation
    assert json.loads(snapshot["before"]) == explanation


def test_selected_factor_adds_only_its_labeled_dashed_provenance():
    explanation = _valid_recovery_artifact()["explanations"][0]

    result = _run_ui(
        "buildCommunityDrawCommands",
        explanation,
        {
            "mode": "flow",
            "stageId": "first_hop",
            "selectedFactorId": "factor:rel:1",
            "query": "",
        },
    )

    assert result["available"] is True
    assert [node["id"] for node in result["nodes"]] == ["p1", "p2"]
    assert [node["id"] for node in result["provenanceNodes"]] == ["p3"]
    assert result["provenanceEdges"] == [
        {
            "id": "provenance-edge-1",
            "u": "p2",
            "v": "p3",
            "relation": "SHARED_PLATE",
            "label": "outside message community",
            "dashed": True,
        }
    ]


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda explanation: explanation["community"]["nodes"][0].update(
                {"x": None}
            ),
            "invalid-community-coordinates",
        ),
        (
            lambda explanation: explanation["community"]["nodes"][0].update(
                {"y": 1.1}
            ),
            "invalid-community-coordinates",
        ),
        (
            lambda explanation: explanation["flow_stages"][0].update(
                {"edge_ids": ["missing"]}
            ),
            "invalid-flow-stages",
        ),
        (
            lambda explanation: explanation["community"]
            ["provenance_expansions"][0]["edges"][0].update(
                {"v": "missing"}
            ),
            "invalid-provenance-expansion",
        ),
        (
            lambda explanation: explanation["community"]
            ["provenance_expansions"][0]["nodes"][1].update(
                {"x": float("nan")}
            ),
            "invalid-provenance-expansion",
        ),
    ],
    ids=[
        "missing-coordinate",
        "coordinate-out-of-range",
        "stage-membership-diverges",
        "provenance-endpoint-missing",
        "provenance-coordinate-nonfinite",
    ],
)
def test_draw_commands_fail_closed_on_invalid_graph_data(mutate, reason):
    explanation = _valid_recovery_artifact()["explanations"][0]
    mutate(explanation)

    result = _run_ui(
        "buildCommunityDrawCommands",
        explanation,
        {
            "mode": "flow",
            "stageId": "first_hop",
            "selectedFactorId": "factor:rel:1",
            "query": "",
        },
    )

    assert result == {"available": False, "reason": reason}


def test_graph_point_is_deterministic_and_does_not_mutate_inputs():
    point = {"x": 0.25, "y": 0.75}
    viewport = {
        "width": 100,
        "height": 50,
        "padding": 10,
        "scale": 2,
        "offsetX": 3,
        "offsetY": -2,
    }
    original = copy.deepcopy([point, viewport])

    first = _run_ui("graphPoint", point, viewport)
    second = _run_ui("graphPoint", point, viewport)

    assert first == second == {"x": 13, "y": 38}
    assert [point, viewport] == original
