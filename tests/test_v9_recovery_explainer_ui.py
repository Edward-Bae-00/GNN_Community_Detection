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


def _case(
    case_id,
    person_id,
    *,
    event_id=None,
    scoring_day="2025-01-02T00:00:00Z",
    baseline_rank=40,
    seed0_gnn_rank=3,
    seed0_hybrid_rank=8,
    hybrid_rank_uplift=32,
    gnn_percentile_uplift=0.5,
    relationship_categories=None,
    stable_factor_status="stable",
):
    return {
        "case_id": case_id,
        "person_id": person_id,
        "event_id": event_id or "event:" + person_id,
        "scoring_day": scoring_day,
        "baseline_rank": baseline_rank,
        "seed0_gnn_rank": seed0_gnn_rank,
        "seed0_hybrid_rank": seed0_hybrid_rank,
        "hybrid_rank_uplift": hybrid_rank_uplift,
        "gnn_percentile_uplift": gnn_percentile_uplift,
        "relationship_categories": relationship_categories or ["COTRAVEL"],
        "stable_factor_status": stable_factor_status,
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


def test_schema_v3_ui_contract_preserves_full_cohorts_and_evidence_boundary():
    js = UI.V9_RECOVERY_EXPLAINER_JS

    for token in (
        "schema_version==='3.0'",
        "buildRecoverySchema3ViewModel",
        "mountRecoveryExplorerV3",
        "hybrid_only",
        "baseline_only",
        "recovered_by_both",
        "Hybrid technical detail",
        "Community context only",
        "No GNN explanation, mask, or attribution",
        "Hybrid score is percentile fusion, not probability",
        "recoverySchema3Community",
        "communitySidecarIndex",
    ):
        assert token in js


def _schema3_ui_artifact():
    ref = {"path": "cases/case.json", "sha256": "a" * 64}
    community_ref = {"path": "communities/community.json", "sha256": "b" * 64}

    def record(case_id, cohort, status, kind):
        return {
            "case_id": case_id,
            "person_id": "person:" + case_id,
            "event_id": "event:" + case_id,
            "scoring_day": "2025-01-02T00:00:00+00:00",
            "cohort": cohort,
            "baseline_raw": 0.2,
            "baseline_percentile": 0.2,
            "baseline_rank": 20,
            "seed0_gnn_probability": 0.8,
            "seed0_gnn_percentile": 0.8,
            "seed0_gnn_rank": 4,
            "seed0_hybrid_score": 0.56,
            "seed0_hybrid_rank": 8,
            "hybrid_score_semantics": "percentile_fusion_not_probability",
            "detail_status": status,
            "detail_kind": kind,
        }

    hybrid = record("h1", "hybrid_only", "available", "gnn_explanation")
    baseline = record(
        "b1", "baseline_only", "community_only", "community_control"
    )
    return {
        "schema_version": "3.0",
        "bundle_id": "0123456789abcdef01234567",
        "sidecar_base": "recovery/bundles/0123456789abcdef01234567/",
        "policy": {
            "observability_seed": 0,
            "gnn_arm": "sage",
            "inspections_per_day": 5,
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
            "hybrid_requested": 1,
            "baseline_requested": 1,
            "hybrid_selected": 1,
            "baseline_selected": 1,
            "hybrid_explained": 1,
            "baseline_community": 1,
            "hybrid_shortfall": 0,
            "baseline_shortfall": 0,
            "shortfall": 0,
            "shortfall_reasons": [],
        },
        "cohorts": {
            "hybrid_only": [hybrid],
            "baseline_only": [baseline],
            "recovered_by_both": [],
        },
        "selection": {
            "selected_ids": {
                "hybrid_only": ["h1"],
                "baseline_only": ["b1"],
                "recovered_by_both": [],
            }
        },
        "detail_index": {"h1": ref},
        "community_index": {"b1": {**community_ref, "cohort": "baseline_only"}},
        "community_sidecar_index": {"community:a": community_ref},
    }


def test_schema_v3_view_model_validates_partial_indexes_and_semantics():
    artifact = _schema3_ui_artifact()
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nprocess.stdout.write(JSON.stringify(buildRecoverySchema3ViewModel("
        + json.dumps(artifact)
        + ")));"
    )

    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    view = json.loads(completed.stdout)

    assert view["available"] is True
    assert view["schemaVersion"] == "3.0"
    assert set(view["cohorts"]) == {
        "hybrid_only", "baseline_only", "recovered_by_both"
    }
    assert view["coverage"]["hybrid_explained"] == 1
    assert view["detailIndex"]["h1"]["sha256"] == "a" * 64

    artifact["community_index"]["b1"]["sha256"] = "not-a-hash"
    invalid_script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nprocess.stdout.write(JSON.stringify(buildRecoverySchema3ViewModel("
        + json.dumps(artifact)
        + ")));"
    )
    invalid = subprocess.run(
        ["node", "-e", invalid_script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(invalid.stdout)["available"] is False


def test_schema_v3_selection_ids_must_match_declared_cohort():
    artifact = _schema3_ui_artifact()
    artifact["selection"]["selected_ids"] = {
        "hybrid_only": ["b1"],
        "baseline_only": ["h1"],
        "recovered_by_both": [],
    }

    result = _node_json(
        "buildRecoverySchema3ViewModel(" + json.dumps(artifact) + ")"
    )

    assert result == {
        "available": False,
        "reason": "invalid-schema3-selection",
    }


@pytest.mark.parametrize(
    "field",
    [
        "baseline_raw",
        "baseline_percentile",
        "seed0_gnn_probability",
        "seed0_gnn_percentile",
        "seed0_hybrid_score",
    ],
)
def test_schema_v3_view_model_requires_all_published_score_fields(field):
    artifact = _schema3_ui_artifact()
    del artifact["cohorts"]["hybrid_only"][0][field]

    result = _node_json(
        "buildRecoverySchema3ViewModel(" + json.dumps(artifact) + ")"
    )

    assert result == {
        "available": False,
        "reason": "invalid-schema3-case-records",
    }


def test_schema_v3_view_model_accepts_hybrid_structural_fallback_coverage():
    artifact = _schema3_ui_artifact()
    fallback = dict(artifact["cohorts"]["hybrid_only"][0])
    fallback.update(
        case_id="hf",
        person_id="person:hf",
        event_id="event:hf",
        detail_status="community_only",
        detail_kind="community_control",
    )
    artifact["cohorts"]["hybrid_only"].append(fallback)
    artifact["summary"].update(hybrid_only_recovered=2, hybrid_total=2, net_gain=1)
    artifact["coverage"].update(
        hybrid_requested=2,
        hybrid_shortfall=1,
        shortfall=1,
        shortfall_reasons=["node_limit_exceeded"],
        hybrid_structural_fallback=1,
    )
    artifact["selection"]["hybrid_structural_fallback_ids"] = ["hf"]
    artifact["community_index"]["hf"] = {
        "path": "cases/fallback.json",
        "sha256": "c" * 64,
        "cohort": "hybrid_only",
    }
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nprocess.stdout.write(JSON.stringify(buildRecoverySchema3ViewModel("
        + json.dumps(artifact)
        + ")));"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    view = json.loads(completed.stdout)
    assert view["available"] is True
    assert view["coverage"]["baseline_community"] == 1


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


def test_recovery_sidecar_paths_reject_traversal_and_absolute_segments():
    script = UI.V9_RECOVERY_EXPLAINER_JS + r"""
const view={sidecarBase:'recovery/bundles/0123456789abcdef01234567/'};
const paths=['../escape.json','communities/../escape.json','/absolute.json',
  './cases/case.json','communities\\escape.json'];
const errors=paths.map(path=>{
  try{return recoverySidecarUrl(view,path);}
  catch(error){return error.message;}
});
const owner={complete:true,node_count:1,edge_count:0,
  provenance_observation_count:0,
  node_chunks:[{path:'../nodes.json',sha256:'a'.repeat(64),offset:0,count:1}],
  edge_chunks:[],provenance_chunks:[],provenance_expansion_membership_chunks:[]};
process.stdout.write(JSON.stringify({
  safe:recoverySidecarUrl(view,'cases/case.json'),
  reference:recoverySchema3Reference({path:'../escape.json',sha256:'a'.repeat(64)}),
  owner:recoveryValidateChunkOwner(owner),errors
}));
"""
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    result = json.loads(completed.stdout)

    assert result["safe"] == (
        "recovery/bundles/0123456789abcdef01234567/cases/case.json"
    )
    assert result["reference"] is False
    assert result["owner"] is False
    assert result["errors"] == ["Unsafe sidecar path"] * 5


def test_schema3_community_rejects_inline_rows_for_chunk_only_loading():
    inline = {
        "schema_version": "1.0",
        "complete": True,
        "community_key": "community:a",
        "node_count": 1,
        "edge_count": 0,
        "provenance_observation_count": 0,
        "nodes": [{"node_id": "p1"}],
        "edge_chunks": [],
        "provenance_chunks": [],
    }
    result = _node_json(
        "(()=>{const value=%s;return {community:"
        "recoverySchema3Community(value,'community:a'),"
        "owner:recoveryValidateChunkOwner(value)};})()" % json.dumps(inline)
    )

    assert result == {"community": False, "owner": False}


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


def _run_ui_with_input_snapshot(function_name, value):
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nconst input="
        + json.dumps(value)
        + ";const before=JSON.stringify(input);"
        + "const result="
        + function_name
        + "(input);process.stdout.write(JSON.stringify({result,input,before}));"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def test_highest_attribution_view_model_ranks_top3_without_mutating_input():
    explanation = {
        "attributions": {
            "top_local_nodes": [
                {"rank": 3, "node_id": "n3", "explainer_median": 0.4},
                {"rank": 1, "node_id": "n1", "explainer_median": 0.8},
                {"rank": 2, "node_id": "n2", "explainer_median": 0.6},
                {"rank": 4, "node_id": "n4", "explainer_median": 0.99},
            ],
            "top_edges": [
                {
                    "rank": 2,
                    "edge_id": "e2",
                    "u": "n2",
                    "v": "n3",
                    "edge_type": "SHARED_PLATE",
                    "explainer_median": 0.7,
                },
                {
                    "rank": 1,
                    "edge_id": "e1",
                    "u": "n1",
                    "v": "n2",
                    "edge_type": "COTRAVEL",
                    "explainer_median": 0.9,
                },
                {
                    "rank": 3,
                    "edge_id": "e3",
                    "u": "n1",
                    "v": "n3",
                    "edge_type": "RESIDENCE",
                    "explainer_median": 0.5,
                },
            ],
        }
    }
    snapshot = _run_ui_with_input_snapshot(
        "buildHighestAttributionViewModel", explanation
    )
    view = snapshot["result"]

    assert view == {
        "available": True,
        "nodes": [
            {"rank": 1, "nodeId": "n1", "weight": 0.8},
            {"rank": 2, "nodeId": "n2", "weight": 0.6},
            {"rank": 3, "nodeId": "n3", "weight": 0.4},
        ],
        "connections": [
            {
                "rank": 1,
                "edgeId": "e1",
                "u": "n1",
                "v": "n2",
                "relation": "COTRAVEL",
                "weight": 0.9,
            },
            {
                "rank": 2,
                "edgeId": "e2",
                "u": "n2",
                "v": "n3",
                "relation": "SHARED_PLATE",
                "weight": 0.7,
            },
            {
                "rank": 3,
                "edgeId": "e3",
                "u": "n1",
                "v": "n3",
                "relation": "RESIDENCE",
                "weight": 0.5,
            },
        ],
    }
    assert snapshot["input"] == explanation
    assert snapshot["before"] == json.dumps(explanation, separators=(",", ":"))


def test_highest_attribution_view_model_preserves_fewer_than_three_valid_entries():
    view = _run_ui(
        "buildHighestAttributionViewModel",
        {
            "attributions": {
                "top_local_nodes": [
                    {"rank": 1, "node_id": "n1", "explainer_median": 0.8}
                ],
                "top_edges": [
                    {
                        "rank": 2,
                        "edge_id": "e2",
                        "u": "n2",
                        "v": "n3",
                        "edge_type": "SHARED_PLATE",
                        "explainer_median": 0.4,
                    },
                    {
                        "rank": 1,
                        "edge_id": "e1",
                        "u": "n1",
                        "v": "n2",
                        "edge_type": "COTRAVEL",
                        "explainer_median": 0.7,
                    },
                ],
            }
        },
    )

    assert view == {
        "available": True,
        "nodes": [{"rank": 1, "nodeId": "n1", "weight": 0.8}],
        "connections": [
            {
                "rank": 1,
                "edgeId": "e1",
                "u": "n1",
                "v": "n2",
                "relation": "COTRAVEL",
                "weight": 0.7,
            },
            {
                "rank": 2,
                "edgeId": "e2",
                "u": "n2",
                "v": "n3",
                "relation": "SHARED_PLATE",
                "weight": 0.4,
            },
        ],
    }


def test_highest_attribution_falls_back_to_median_and_id_tie_break():
    view = _run_ui(
        "buildHighestAttributionViewModel",
        {
            "attributions": {
                "top_local_nodes": [
                    {"node_id": "b", "explainer_median": 0.8},
                    {"node_id": "a", "explainer_median": 0.8},
                    {"node_id": "c", "explainer_median": 0.2},
                    {"node_id": "z", "rank": 0, "explainer_median": 0.99},
                ],
                "top_edges": [],
            }
        },
    )

    assert [row["nodeId"] for row in view["nodes"]] == ["z", "a", "b"]
    assert [row["rank"] for row in view["nodes"]] == [1, 2, 3]


def test_highest_attribution_mixed_ranks_fall_back_for_entire_collection():
    view = _run_ui(
        "buildHighestAttributionViewModel",
        {
            "attributions": {
                "top_local_nodes": [
                    {"rank": 2, "node_id": "n2", "explainer_median": 0.6},
                    {"node_id": "n1", "explainer_median": 0.9},
                    {"rank": 1, "node_id": "n3", "explainer_median": 0.8},
                ],
                "top_edges": [],
            }
        },
    )

    assert [row["nodeId"] for row in view["nodes"]] == ["n1", "n3", "n2"]
    assert [row["rank"] for row in view["nodes"]] == [1, 2, 3]


def test_highest_attribution_duplicate_ranks_fall_back_to_unique_display_ranks():
    view = _run_ui(
        "buildHighestAttributionViewModel",
        {
            "attributions": {
                "top_local_nodes": [
                    {"rank": 1, "node_id": "n2", "explainer_median": 0.9},
                    {"rank": 1, "node_id": "n1", "explainer_median": 0.8},
                    {"rank": 2, "node_id": "n3", "explainer_median": 0.7},
                ],
                "top_edges": [],
            }
        },
    )

    assert [row["nodeId"] for row in view["nodes"]] == ["n2", "n1", "n3"]
    assert [row["rank"] for row in view["nodes"]] == [1, 2, 3]
    assert len({row["rank"] for row in view["nodes"]}) == len(view["nodes"])


@pytest.mark.parametrize(
    "attributions",
    [
        None,
        {},
        {"top_local_nodes": "bad", "top_edges": []},
        {
            "top_local_nodes": [{"node_id": "", "explainer_median": 0.5}],
            "top_edges": [],
        },
        {
            "top_local_nodes": [],
            "top_edges": [
                {
                    "edge_id": "e1",
                    "u": "n1",
                    "v": "n2",
                    "edge_type": "COTRAVEL",
                    "explainer_median": float("nan"),
                }
            ],
        },
    ],
)
def test_highest_attribution_returns_unavailable_for_empty_or_malformed_data(attributions):
    view = _run_ui("buildHighestAttributionViewModel", {"attributions": attributions})

    assert view["available"] is False
    assert view["reason"] == "no-valid-attribution-ranking"


def test_highest_attribution_renderer_contract_is_shared_by_schema_paths():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    css = UI.V9_RECOVERY_EXPLAINER_CSS

    assert "function buildHighestAttributionViewModel" in js
    assert "function renderHighestAttributionPanel" in js
    v2_detail = js.split("function renderV2Detail", 1)[1].split(
        "function renderV2()", 1
    )[0]
    hybrid_branch = v2_detail.split("if(state.cohort==='hybrid_only')", 1)[1].split(
        "}else{", 1
    )[0]
    assert "renderHighestAttributionPanel(doc" not in v2_detail.split(
        "if(state.cohort==='hybrid_only')", 1
    )[0]
    assert hybrid_branch.index("renderHighestAttributionPanel(doc") < hybrid_branch.index(
        "panels.appendChild(recoveryV2Panel(doc,'Validated local Gemma narrative'"
    )
    legacy_detail = js.split("function renderDetail", 1)[1].split(
        "function render(){", 1
    )[0]
    assert legacy_detail.index("renderNarrative(left,explanation)") < legacy_detail.index(
        "renderHighestAttributionPanel(doc"
    ) < legacy_detail.index("renderGraph(right,explanation)")
    assert "Highest-attribution evidence" in js
    assert "Unsigned median attribution weights show salience across deterministic explainer restarts, not causal direction." in js
    assert "Attribution ranking unavailable in this artifact." in js
    assert "Nodes" in js and "Connections" in js
    assert ".v9-attribution-grid" in css
    assert "grid-template-columns: repeat(2" in css
    assert ".v9-attribution-bar-fill { display: block;" in css
    assert "@media(max-width:700px)" in css
    assert "grid-template-columns: 1fr" in css


def test_highest_attribution_renderer_dom_contract_and_accessible_connection_labels():
    explanation = {
        "attributions": {
            "top_local_nodes": [
                {"rank": 1, "node_id": "n1", "explainer_median": 0.8},
                {"rank": 2, "node_id": "n2", "explainer_median": 0.6},
                {"rank": 3, "node_id": "n3", "explainer_median": 0.4},
            ],
            "top_edges": [
                {
                    "rank": 1,
                    "edge_id": "e1",
                    "u": "n1",
                    "v": "n2",
                    "edge_type": "COTRAVEL",
                    "explainer_median": 0.9,
                },
                {
                    "rank": 2,
                    "edge_id": "e2",
                    "u": "n2",
                    "v": "n3",
                    "edge_type": "SHARED_PLATE",
                    "explainer_median": 0.7,
                },
                {
                    "rank": 3,
                    "edge_id": "e3",
                    "u": "n1",
                    "v": "n3",
                    "edge_type": "RESIDENCE",
                    "explainer_median": 0.5,
                },
            ],
        }
    }
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nconst explanation="
        + json.dumps(explanation)
        + r""";
function fakeElement(tag){
  return {
    tag,children:[],textContent:'',className:'',attrs:{},style:{},id:'',
    appendChild(child){this.children.push(child);return child;},
    setAttribute(name,value){this.attrs[name]=String(value);}
  };
}
const doc={createElement:fakeElement};
const root=renderHighestAttributionPanel(doc,explanation);
function all(node){return [node,...node.children.flatMap(all)];}
const nodes=all(root);
const bars=nodes.filter(node=>node.attrs.role==='progressbar');
process.stdout.write(JSON.stringify({
  rootAttrs:root.attrs,
  ids:nodes.filter(node=>node.id).map(node=>node.id),
  text:nodes.map(node=>node.textContent).filter(Boolean),
  bars:bars.map(node=>node.attrs),
  widths:bars.map(node=>node.children[0].style.width)
}));"""
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    result = json.loads(completed.stdout)

    assert result["rootAttrs"]["aria-label"] == "Highest-attribution evidence"
    assert result["ids"] == []
    assert "Highest-attribution evidence" in result["text"]
    assert "Nodes" in result["text"]
    assert "Connections" in result["text"]
    assert len(result["bars"]) == 6
    labels = [bar["aria-label"] for bar in result["bars"]]
    assert len(set(labels)) == 6
    assert all(bar["aria-valuemin"] == "0" for bar in result["bars"])
    assert all(bar["aria-valuemax"] == "1" for bar in result["bars"])
    assert result["widths"] == ["80%", "60%", "40%", "90%", "70%", "50%"]
    for endpoint, relation, edge_id in (
        ("n1 ↔ n2", "COTRAVEL", "e1"),
        ("n2 ↔ n3", "SHARED_PLATE", "e2"),
        ("n1 ↔ n3", "RESIDENCE", "e3"),
    ):
        connection_labels = [
            label for label in labels if label.startswith("Connections")
        ]
        assert any(
            endpoint in label and relation in label and edge_id in label
            for label in connection_labels
        )


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

    assert js.count("root.addEventListener('click'") == 3
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


def test_draw_commands_map_schema3_overlay_and_keep_complete_tables():
    explanation = _valid_recovery_artifact()["explanations"][0]
    explanation["overlayNodes"] = [
        {
            "node_id": "p2",
            "importance": 0.9,
            "attributed": True,
            "rank": 1,
        }
    ]
    explanation["overlayEdges"] = [
        {
            "edge_id": "edge-1",
            "u": "p1",
            "v": "p2",
            "edge_type": "COTRAVEL",
            "relation": "COTRAVEL",
            "importance": 0.8,
            "attributed": True,
            "rank": 1,
        }
    ]

    result = _run_ui(
        "buildCommunityDrawCommands",
        explanation,
        {"mode": "flow", "stageId": "rank_fusion", "query": ""},
    )

    assert result["available"] is True
    assert result["sampled"] is False
    assert result["fullNodeCount"] == len(explanation["community"]["nodes"])
    assert result["fullEdgeCount"] == len(explanation["community"]["edges"])
    assert [node["id"] for node in result["tableNodes"]] == [
        node["node_id"] for node in explanation["community"]["nodes"]
    ]
    assert [edge["id"] for edge in result["tableEdges"]] == [
        edge["edge_id"] for edge in explanation["community"]["edges"]
    ]
    assert next(node for node in result["nodes"] if node["id"] == "p1")["target"] is True
    attributed_node = next(node for node in result["nodes"] if node["id"] == "p2")
    assert attributed_node["importance"] == 0.9
    assert attributed_node["attributed"] is True
    assert attributed_node["rank"] == 1
    attributed_edge = result["edges"][0]
    assert attributed_edge["importance"] == 0.8
    assert attributed_edge["attributed"] is True
    assert attributed_edge["rank"] == 1
    assert attributed_edge["emphasized"] is True


def test_evidence_edge_style_uses_single_accent_and_weight_scaling():
    low = _run_ui(
        "recoveryEdgeStyle",
        {"importance": 0.0, "attributed": True, "emphasized": False},
    )
    high = _run_ui(
        "recoveryEdgeStyle",
        {"importance": 1.0, "attributed": True, "emphasized": False},
    )

    assert low["color"] == high["color"]
    assert low["alpha"] < high["alpha"]
    assert low["lineWidth"] < high["lineWidth"]


def test_canvas_draw_loop_skips_missing_edge_endpoints():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    draw = js.split("function draw(){", 1)[1].split(
        "function pointerDistance(){", 1
    )[0]
    assert "if(!from||!to)continue;" in draw


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


def test_filter_sorts_explained_cases_first_when_ids_supplied():
    low_uplift_explained = _case("case:p1", "p1", hybrid_rank_uplift=10)
    high_uplift_unexplained = _case("case:p2", "p2", hybrid_rank_uplift=90)
    result = _run_ui(
        "filterAndSortRecoveryCases",
        [high_uplift_unexplained, low_uplift_explained],
        {"explainedIds": ["case:p1"]},
    )
    assert [item["case_id"] for item in result] == ["case:p1", "case:p2"]


def test_filter_evidence_only_drops_unexplained_cases():
    result = _run_ui(
        "filterAndSortRecoveryCases",
        [_case("case:p1", "p1"), _case("case:p2", "p2")],
        {"explainedIds": ["case:p1"], "evidence": "explained"},
    )
    assert [item["case_id"] for item in result] == ["case:p1"]


def test_filter_without_new_options_keeps_legacy_order():
    low = _case("case:p1", "p1", hybrid_rank_uplift=10)
    high = _case("case:p2", "p2", hybrid_rank_uplift=90)
    result = _run_ui("filterAndSortRecoveryCases", [high, low], {})
    assert [item["case_id"] for item in result] == ["case:p2", "case:p1"]


def _node_json(expression):
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nprocess.stdout.write(JSON.stringify("
        + expression
        + "));"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def _schema3_structural_control(person_id="p1"):
    return {
        "person_id": person_id,
        "community": {
            "complete": True,
            "nodes": [
                {
                    "node_id": person_id,
                    "x": 0.5,
                    "y": 0.5,
                    "pooled_member": True,
                    "caught_before_snapshot": False,
                },
                {
                    "node_id": "p2",
                    "x": 0.8,
                    "y": 0.4,
                    "pooled_member": True,
                    "caught_before_snapshot": True,
                },
                {
                    "node_id": "p3",
                    "x": 0.2,
                    "y": 0.7,
                    "pooled_member": False,
                    "caught_before_snapshot": False,
                },
            ],
            "edges": [
                {
                    "edge_id": "e1",
                    "u": person_id,
                    "v": "p2",
                    "edge_type": "COTRAVEL",
                    "message_hop": 1,
                },
                {
                    "edge_id": "e2",
                    "u": "p2",
                    "v": "p3",
                    "edge_type": "RESIDENCE",
                    "message_hop": 2,
                },
            ],
            "provenance_expansions": [],
        },
        "structural_stages": [
            {"stage_id": "first_hop", "edge_rule": {"max_message_hop": 1}},
            {"stage_id": "second_hop", "edge_rule": {"max_message_hop": 2}},
            {
                "stage_id": "component_pool",
                "edge_rule": {
                    "edge_type": "COTRAVEL",
                    "both_pooled_members": True,
                },
            },
        ],
    }


def test_schema3_filters_cover_every_cohort_and_detail_kind():
    artifact = _schema3_ui_artifact()
    both = dict(artifact["cohorts"]["hybrid_only"][0])
    both.update(
        case_id="x1",
        person_id="person:x1",
        event_id="event:x1",
        cohort="recovered_by_both",
        detail_status="not_selected",
        detail_kind=None,
    )
    artifact["cohorts"]["recovered_by_both"].append(both)
    artifact["summary"].update(
        recovered_by_both=1, baseline_recovered=2, hybrid_total=2, net_gain=0
    )

    view_expr = "buildRecoverySchema3ViewModel(" + json.dumps(artifact) + ")"
    result = _node_json(
        "["
        + ",".join(
            "filterRecoverySchema3Cases(%s,%s).map(r=>r.caseId)"
            % (view_expr, json.dumps(name))
            for name in (
                "all",
                "hybrid_only",
                "baseline_only",
                "recovered_by_both",
                "gnn_explanation",
                "community_control",
                "all_detail",
            )
        )
        + "]"
    )

    assert result[0] == ["h1", "b1", "x1"]
    assert result[1] == ["h1"]
    assert result[2] == ["b1"]
    assert result[3] == ["x1"]
    assert result[4] == ["h1"]
    assert result[5] == ["b1"]
    assert result[6] == ["h1", "b1"]


def test_schema3_view_model_exposes_normalized_detail_state():
    artifact = _schema3_ui_artifact()
    artifact["cohorts"]["hybrid_only"][0].update(
        selection_reason="balanced_frozen_prefix",
        failure_reason=None,
    )
    artifact["cohorts"]["baseline_only"][0].update(
        selection_reason="ineligible_preflight_structural_fallback",
        explanation_unavailable_reason="node_limit_exceeded",
    )

    view = _node_json(
        "buildRecoverySchema3ViewModel(" + json.dumps(artifact) + ")"
    )

    hybrid = view["caseIndex"]["h1"]
    baseline = view["caseIndex"]["b1"]
    assert hybrid["detailStatus"] == "available"
    assert hybrid["detailKind"] == "gnn_explanation"
    assert hybrid["selectionReason"] == "balanced_frozen_prefix"
    assert hybrid["failureReason"] is None
    assert baseline["detailKind"] == "community_control"
    assert baseline["explanationUnavailableReason"] == "node_limit_exceeded"
    assert view["catalogIndex"] == {}


def test_schema3_overlay_rejects_baseline_explanation_kind():
    artifact = _schema3_ui_artifact()
    artifact["cohorts"]["baseline_only"][0]["detail_kind"] = "gnn_explanation"

    result = _node_json(
        "buildRecoverySchema3ViewModel(" + json.dumps(artifact) + ")"
    )

    assert result == {
        "available": False,
        "reason": "invalid-schema3-case-records",
    }


def test_schema3_explorer_uses_explainer_only_filter_for_published_explanations():
    mount = UI.V9_RECOVERY_EXPLAINER_JS.split(
        "function mountRecoveryExplorerV3", 1
    )[1].split("const recoveryMounts", 1)[0]
    assert "const state={filter:" in mount
    assert "filter:'gnn_explanation'" in mount
    filters = mount.split("function renderFilters", 1)[1].split(
        "function renderRecordStatus", 1
    )[0]
    assert "Showing GNN explanations only" in filters
    assert "All cases" not in filters
    assert "Baseline-only" not in filters
    assert "Community control" not in filters

    artifact = _schema3_ui_artifact()
    extra = dict(artifact["cohorts"]["hybrid_only"][0])
    extra.update(
        case_id="h2",
        person_id="person:h2",
        detail_status="not_selected",
        detail_kind=None,
    )
    artifact["cohorts"]["hybrid_only"].append(extra)
    artifact["summary"].update(hybrid_only_recovered=2, hybrid_total=2, net_gain=1)
    artifact["coverage"].update(
        hybrid_requested=2,
        hybrid_shortfall=1,
        shortfall=1,
        shortfall_reasons=["not_selected"],
    )

    result = _node_json(
        "(()=>{const view=buildRecoverySchema3ViewModel("
        + json.dumps(artifact)
        + ");return filterRecoverySchema3Cases(view,'gnn_explanation');})()"
    )

    assert [row["caseId"] for row in result] == ["h1"]
    assert all(row["detailKind"] == "gnn_explanation" for row in result)

    # The first cohort row is not necessarily the first published explanation.
    artifact["cohorts"]["hybrid_only"].insert(0, extra)
    artifact["cohorts"]["hybrid_only"].pop()
    view = _node_json(
        "buildRecoverySchema3ViewModel(" + json.dumps(artifact) + ")"
    )
    assert view["defaultCaseId"] == "h1"


def test_structural_draw_commands_keep_neutral_emphasis_and_local_target():
    control = _schema3_structural_control()

    neutral = _node_json(
        "buildStructuralDrawCommands(%s,{mode:'all',stageId:'first_hop',query:''})"
        % json.dumps(control)
    )
    staged = _node_json(
        "buildStructuralDrawCommands(%s,{mode:'flow',stageId:'first_hop',query:''})"
        % json.dumps(control)
    )

    assert neutral["available"] is True
    # Every edge keeps zero importance: a control carries no explainer mask.
    assert [edge["importance"] for edge in neutral["edges"]] == [0, 0]
    assert all(edge["emphasized"] for edge in neutral["edges"])
    assert [node["id"] for node in neutral["nodes"]] == ["p1", "p2", "p3"]
    assert [node["target"] for node in neutral["nodes"]] == [True, False, False]
    # Flow mode still resolves the stage rule against each edge's own hop.
    assert [edge["emphasized"] for edge in staged["edges"]] == [True, False]
    assert staged["provenanceEdges"] == []


def test_structural_draw_commands_reject_the_hybrid_rank_fusion_stage():
    control = _schema3_structural_control()

    rejected = _node_json(
        "buildStructuralDrawCommands(%s,{mode:'all',stageId:'rank_fusion',query:''})"
        % json.dumps(control)
    )

    assert rejected["available"] is False
    assert rejected["reason"] == "invalid-view-options"


@pytest.mark.parametrize(
    "mutate,reason",
    [
        (lambda c: c["community"].__setitem__("nodes", []),
         "invalid-community-membership"),
        (lambda c: c["community"]["nodes"][0].__setitem__("x", 4.5),
         "invalid-community-coordinates"),
        (lambda c: c["community"]["edges"][0].__setitem__("u", "ghost"),
         "invalid-community-membership"),
        (lambda c: c.__setitem__("structural_stages", []),
         "invalid-structural-stages"),
        (lambda c: c.__setitem__("person_id", "absent"),
         "invalid-community-membership"),
    ],
)
def test_structural_draw_commands_fail_closed(mutate, reason):
    control = _schema3_structural_control()
    mutate(control)

    result = _node_json(
        "buildStructuralDrawCommands(%s,{mode:'all',stageId:'first_hop',query:''})"
        % json.dumps(control)
    )

    assert result["available"] is False
    assert result["reason"] == reason


def test_schema3_community_assembly_requires_every_chunk():
    manifest = {"community_key": "community:a", "node_count": 2, "edge_count": 1}
    nodes = [{"node_id": "p1"}, {"node_id": "p2"}]
    edges = [{"edge_id": "e1", "u": "p1", "v": "p2"}]

    complete = _node_json(
        "assembleRecoverySchema3Community(%s,%s,%s)"
        % (json.dumps(manifest), json.dumps(nodes), json.dumps(edges))
    )
    partial = _node_json(
        "assembleRecoverySchema3Community(%s,%s,%s)"
        % (json.dumps(manifest), json.dumps(nodes[:1]), json.dumps(edges))
    )
    unloaded = _node_json(
        "assembleRecoverySchema3Community(%s,null,null)" % json.dumps(manifest)
    )

    assert complete["available"] is True
    assert complete["community"]["complete"] is True
    assert complete["community"]["node_count"] == 2
    assert complete["community"]["edge_count"] == 1
    assert complete["community"]["provenance_expansions"] == []
    assert partial == {"available": False, "reason": "community-partially-loaded"}
    assert unloaded == {"available": False, "reason": "community-not-loaded"}


def test_schema3_detail_branches_by_kind_and_bounds_the_canvas():
    community = _schema3_structural_control()["community"]
    community_view = {"available": True, "community": community}
    hybrid_record = {
        "personId": "p1",
        "detailKind": "gnn_explanation",
        "scoring_day": "2025-01-02T00:00:00+00:00",
    }
    control_record = {
        "personId": "p1",
        "detailKind": "community_control",
        "scoring_day": "2025-01-02T00:00:00+00:00",
    }
    boundary = {
        "snapshot": "2025-01-02T00:00:00+00:00",
        "edge_rule": "available_time < snapshot",
        "caught_rule": "label_available_time_utc < snapshot",
    }

    hybrid = _node_json(
        "buildRecoverySchema3Detail(%s,%s,%s)"
        % (
            json.dumps(hybrid_record),
            json.dumps({"explanation": {"evidence_boundary": boundary}}),
            json.dumps(community_view),
        )
    )
    control = _node_json(
        "buildRecoverySchema3Detail(%s,%s,%s)"
        % (
            json.dumps(control_record),
            json.dumps(
                {
                    "detail": {
                        "evidence_boundary": boundary,
                        "structural_stages": [],
                    }
                }
            ),
            json.dumps(community_view),
        )
    )
    missing = _node_json(
        "buildRecoverySchema3Detail(%s,%s,%s)"
        % (
            json.dumps(control_record),
            json.dumps({"case": {}}),
            json.dumps(community_view),
        )
    )

    assert hybrid["available"] is True
    assert hybrid["kind"] == "gnn_explanation"
    assert hybrid["explanation"]["person_id"] == "p1"
    assert hybrid["control"] is None
    assert hybrid["canvasAvailable"] is True
    assert hybrid["evidenceBoundary"] == boundary
    assert control["available"] is True
    assert control["explanation"] is None
    assert control["control"]["structural_stages"] == []
    assert missing == {
        "available": False,
        "kind": "community_control",
        "reason": "structural-detail-unavailable",
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("snapshot", "2025-01-03T00:00:00+00:00"),
        ("edge_rule", "available_time <= snapshot"),
        ("caught_rule", "label_available_time_utc <= snapshot"),
    ],
)
def test_schema3_detail_rejects_invalid_as_of_evidence_boundary(field, value):
    community = _schema3_structural_control()["community"]
    boundary = {
        "snapshot": "2025-01-02T00:00:00+00:00",
        "edge_rule": "available_time < snapshot",
        "caught_rule": "label_available_time_utc < snapshot",
    }
    boundary[field] = value

    detail = _node_json(
        "buildRecoverySchema3Detail(%s,%s,%s)"
        % (
            json.dumps({
                "personId": "p1",
                "detailKind": "gnn_explanation",
                "scoring_day": "2025-01-02T00:00:00+00:00",
            }),
            json.dumps({"explanation": {"evidence_boundary": boundary}}),
            json.dumps({"available": True, "community": community}),
        )
    )

    assert detail == {
        "available": False,
        "kind": "gnn_explanation",
        "reason": "invalid-evidence-boundary",
    }


def test_schema3_detail_falls_back_to_the_table_above_the_render_bound():
    nodes = [
        {"node_id": "p%d" % index, "x": 0.5, "y": 0.5}
        for index in range(1, 1602)
    ]
    community_view = {
        "available": True,
        "community": {"complete": True, "nodes": nodes, "edges": []},
    }

    detail = _node_json(
        "buildRecoverySchema3Detail(%s,%s,%s)"
        % (
            json.dumps({
                "personId": "p1",
                "detailKind": "community_control",
                "scoring_day": "2025-01-02T00:00:00+00:00",
            }),
            json.dumps({
                "detail": {
                    "structural_stages": [],
                    "evidence_boundary": {
                        "snapshot": "2025-01-02T00:00:00+00:00",
                        "edge_rule": "available_time < snapshot",
                        "caught_rule": "label_available_time_utc < snapshot",
                    },
                }
            }),
            json.dumps(community_view),
        )
    )

    assert detail["available"] is True
    assert detail["nodeCount"] == 1601
    assert detail["canvasAvailable"] is False


def test_schema3_detail_renderer_reuses_the_technical_evidence_panels():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    mount = js.split("function mountRecoveryExplorerV3", 1)[1].split(
        "const recoveryMounts", 1
    )[0]

    hybrid_branch = mount.split(
        "if(detailView.kind==='gnn_explanation'){", 1
    )[1].split("}else{", 1)[0]
    assert "renderFactors(left,detailView.explanation)" in hybrid_branch
    assert "renderNarrative(left,detailView.explanation)" in hybrid_branch
    assert "renderHighestAttributionPanel(doc,detailView.explanation)" in hybrid_branch
    assert "renderGraph(right,detailView,record)" in mount
    assert "buildCommunityDrawCommands(detailView.explanation,options)" in mount
    assert "buildStructuralDrawCommands(detailView.control,options)" in mount
    # The boundary gate must run before any evidence renderer.
    assert mount.index("renderEvidenceBoundary(detail,detailView.evidenceBoundary)") < (
        mount.index("renderFactors(left,detailView.explanation)")
    )


def test_schema3_control_suppresses_attribution_and_states_its_scope():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    mount = js.split("function mountRecoveryExplorerV3", 1)[1].split(
        "const recoveryMounts", 1
    )[0]
    control_branch = mount.split(
        "if(detailView.kind==='community_control'){", 1
    )[1].split("}else{", 1)[0]

    assert (
        "Community context only: GNNExplainer was not run for this baseline control."
        in control_branch
    )
    assert (
        "Attribution, counterfactual factor, stability, and faithfulness panels are suppressed for a control."
        in mount
    )
    assert "renderFactors" not in control_branch
    assert "renderHighestAttributionPanel" not in control_branch
    # Mask semantics stay visible wherever a Hybrid mask is drawn.
    assert (
        "Mask values are unsigned evidence weights, not causal claims." in mount
    )


def test_schema3_graph_exposes_accessible_names_and_a_table_fallback():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    mount = js.split("function mountRecoveryExplorerV3", 1)[1].split(
        "const recoveryMounts", 1
    )[0]

    for token in (
        "renderGraphTable(panel,commands,record)",
        "Non-canvas equivalent of the graph above.",
        "As-of community context + explanation evidence",
        "Muted context remains visible",
        "unsigned explainer median",
        "This is not a causal claim",
        "Context relations",
        "Explanation evidence",
        "Caught before snapshot",
        "Weight range",
        "Sampled context:",
        "Strict-bound unavailable:",
        "commands.sampled",
        "v9-recovery-legend",
        "Graph legend",
        "canvas.setAttribute('aria-label'",
        "record.cohort==='baseline_only'",
        "Hybrid structural fallback ",
        "exceed the interactive rendering bound",
        "restoreV3Focus('data-v3-stage','v3Stage',data.v3Stage)",
        "restoreV3Focus('data-v3-zoom','v3Zoom',data.v3Zoom)",
        "bindRecoveryCanvas(",
    ):
        assert token in mount
    assert "v9-recovery-table" in UI.V9_RECOVERY_EXPLAINER_CSS
    assert "overflow-x: auto" in UI.V9_RECOVERY_EXPLAINER_CSS


def test_schema3_graph_copy_renders_explanation_legend_keys():
    rendered = _mount_schema3("h1")
    text = " | ".join(rendered["text"])

    assert "As-of community context + explanation evidence" in text
    assert "Muted context remains visible" in text
    assert "Explanation evidence" in text
    assert "Target" in text
    assert "Caught before snapshot" in text
    assert "Weight range" in text


def test_schema3_css_polish_is_scoped_and_reduced_motion_safe():
    css = UI.V9_RECOVERY_EXPLAINER_CSS

    for token in (
        ".v9-recovery-v3",
        "radial-gradient",
        ".v9-recovery-legend-swatch",
        ".v9-recovery-sampled",
        "height: 470px",
        "overflow-x: auto",
        ":focus:not(:focus-visible)",
        "prefers-reduced-motion: reduce",
    ):
        assert token in css


def test_schema3_mount_discards_stale_responses_and_reports_failures():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    mount = js.split("function mountRecoveryExplorerV3", 1)[1].split(
        "const recoveryMounts", 1
    )[0]

    assert "const token=++requestToken" in mount
    assert mount.count("token!==requestToken") >= 4
    assert "state.caseData=await recoveryFetchJson" not in mount
    assert "Published sidecar reference is missing for this case" in mount
    assert "Schema-3 case sidecar identity is invalid" in mount
    assert "Schema-3 community sidecar identity is invalid" in mount
    assert "recoveryServerHelp(state.error)" in mount
    assert "Partial coverage: " in mount
    assert "GNNExplainer was not run for this case: " in mount
    assert "".join(mount.split()).count(
        "record.cohort==='hybrid_only'&&record.detailKind==='gnn_explanation'"
    ) >= 2


def _schema3_overlay_fixture():
    community = {
        "complete": True,
        "node_count": 4,
        "edge_count": 3,
        "nodes": [
            {"node_id": "p1", "x": 0.1, "y": 0.2},
            {"node_id": "p2", "x": 0.3, "y": 0.4},
            {"node_id": "p3", "x": 0.5, "y": 0.6},
            {"node_id": "p4", "x": 0.7, "y": 0.8},
        ],
        "edges": [
            {"edge_id": "e1", "u": "p1", "v": "p2", "edge_type": "COTRAVEL"},
            {"edge_id": "e2", "u": "p2", "v": "p3", "edge_type": "RESIDENCE"},
            {"edge_id": "e3", "u": "p3", "v": "p4", "edge_type": "SHARED_PLATE"},
        ],
    }
    overlay_nodes = [
        {"node_id": "p1", "explainer_median": 0.9, "rank": 1},
        {"node_id": "p4", "explainer_median": 0.7, "rank": 2},
    ]
    overlay_edges = [
        {
            "edge_id": "e1",
            "u": "p1",
            "v": "p2",
            "edge_type": "COTRAVEL",
            "relation": "COTRAVEL",
            "explainer_median": 0.8,
            "rank": 1,
        },
        {
            "edge_id": "e3",
            "u": "p3",
            "v": "p4",
            "edge_type": "SHARED_PLATE",
            "relation": "SHARED_PLATE",
            "explainer_median": 0.6,
            "rank": 2,
        },
    ]
    return community, overlay_nodes, overlay_edges


def test_schema3_overlay_merges_attribution_onto_community_rows():
    community, overlay_nodes, overlay_edges = _schema3_overlay_fixture()

    result = _node_json(
        "(()=>{const community=%s;const overlayNodes=%s;const overlayEdges=%s;"
        "const communitySnapshot=JSON.stringify(community);"
        "const nodeSnapshot=JSON.stringify(overlayNodes);"
        "const edgeSnapshot=JSON.stringify(overlayEdges);"
        "const first=mergeRecoverySchema3Overlay(community,overlayNodes,overlayEdges);"
        "const second=mergeRecoverySchema3Overlay(community,overlayNodes,overlayEdges);"
        "const reversed=mergeRecoverySchema3Overlay(community,"
        "overlayNodes.slice().reverse(),overlayEdges.slice().reverse());"
        "return {deterministic:JSON.stringify(first)===JSON.stringify(second),"
        "orderInvariant:JSON.stringify(first)===JSON.stringify(reversed),"
        "inputsUnchanged:JSON.stringify(community)===communitySnapshot"
        "&&JSON.stringify(overlayNodes)===nodeSnapshot"
        "&&JSON.stringify(overlayEdges)===edgeSnapshot,result:first};})()"
        % (
            json.dumps(community),
            json.dumps(overlay_nodes),
            json.dumps(overlay_edges),
        )
    )
    merged = result["result"]

    assert result["deterministic"] is True
    assert result["orderInvariant"] is True
    assert result["inputsUnchanged"] is True
    assert merged["available"] is True
    nodes_by_id = {node["node_id"]: node for node in merged["nodes"]}
    edges_by_id = {edge["edge_id"]: edge for edge in merged["edges"]}
    assert set(nodes_by_id) == {"p1", "p2", "p3", "p4"}
    assert set(edges_by_id) == {"e1", "e2", "e3"}
    assert nodes_by_id["p1"]["importance"] == 0.9
    assert nodes_by_id["p1"]["attributed"] is True
    assert nodes_by_id["p1"]["rank"] == 1
    assert nodes_by_id["p4"]["importance"] == 0.7
    assert nodes_by_id["p4"]["attributed"] is True
    assert nodes_by_id["p4"]["rank"] == 2
    assert edges_by_id["e1"]["importance"] == 0.8
    assert edges_by_id["e1"]["attributed"] is True
    assert edges_by_id["e1"]["rank"] == 1
    assert edges_by_id["e1"]["relation"] == "COTRAVEL"
    assert edges_by_id["e1"]["edge_type"] == "COTRAVEL"
    assert edges_by_id["e3"]["importance"] == 0.6
    assert edges_by_id["e3"]["attributed"] is True
    assert edges_by_id["e3"]["rank"] == 2
    assert edges_by_id["e3"]["relation"] == "SHARED_PLATE"
    assert nodes_by_id["p2"]["x"] == 0.3
    assert nodes_by_id["p2"]["y"] == 0.4
    assert nodes_by_id["p2"]["importance"] == 0
    assert nodes_by_id["p2"]["attributed"] is False
    assert nodes_by_id["p3"]["importance"] == 0
    assert nodes_by_id["p3"]["attributed"] is False
    assert edges_by_id["e2"]["u"] == "p2"
    assert edges_by_id["e2"]["v"] == "p3"
    assert edges_by_id["e2"]["relation"] == "RESIDENCE"
    assert edges_by_id["e2"]["edge_type"] == "RESIDENCE"
    assert edges_by_id["e2"]["importance"] == 0
    assert edges_by_id["e2"]["attributed"] is False
    assert edges_by_id["e2"]["rank"] is None


def test_schema3_overlay_canonicalizes_attributed_edge_relation_fallback():
    community, overlay_nodes, overlay_edges = _schema3_overlay_fixture()
    overlay_edges[0].pop("relation")

    result = _node_json(
        "mergeRecoverySchema3Overlay(%s,%s,%s)"
        % (json.dumps(community), json.dumps(overlay_nodes), json.dumps(overlay_edges))
    )

    edge = next(row for row in result["edges"] if row["edge_id"] == "e1")
    assert edge["relation"] == "COTRAVEL"
    assert edge["edge_type"] == "COTRAVEL"
    assert edge["rank"] == 1


def test_schema3_overlay_detail_presentation_keeps_complete_community_rows():
    community, overlay_nodes, overlay_edges = _schema3_overlay_fixture()
    overlay = _node_json(
        "mergeRecoverySchema3Overlay(%s,%s,%s)"
        % (json.dumps(community), json.dumps(overlay_nodes), json.dumps(overlay_edges))
    )
    boundary = {
        "snapshot": "2025-01-02T00:00:00+00:00",
        "edge_rule": "available_time < snapshot",
        "caught_rule": "label_available_time_utc < snapshot",
    }
    record = {
        "personId": "p1",
        "detailKind": "gnn_explanation",
        "scoring_day": "2025-01-02T00:00:00+00:00",
    }
    payload = {"explanation": {"evidence_boundary": boundary}}
    community_view = {"available": True, "community": community}
    result = _node_json(
        "(()=>{const community=%s;const overlay=%s;"
        "const snapshot=JSON.stringify(community);"
        "const detail=buildRecoverySchema3Detail(%s,%s,{available:true,community},overlay);"
        "return {detail,unchanged:JSON.stringify(community)===snapshot};})()"
        % (
            json.dumps(community),
            json.dumps(overlay),
            json.dumps(record),
            json.dumps(payload),
        )
    )

    detail = result["detail"]
    assert detail["available"] is True
    assert result["unchanged"] is True
    assert detail["explanation"]["overlayNodes"][0]["importance"] == 0.9
    assert detail["explanation"]["overlayNodes"][0]["attributed"] is True
    assert detail["explanation"]["overlayEdges"][0]["importance"] == 0.8
    assert detail["explanation"]["overlayEdges"][0]["attributed"] is True
    assert detail["explanation"]["community"] == community


def test_schema3_overlay_normalizes_trimmed_graph_identity_fields():
    community, overlay_nodes, overlay_edges = _schema3_overlay_fixture()
    overlay_nodes[0]["node_id"] = " p1 "
    overlay_edges[0].update(
        edge_id=" e1 ",
        u=" p1 ",
        v=" p2 ",
        edge_type=" COTRAVEL ",
        relation=" COTRAVEL ",
    )

    result = _node_json(
        "mergeRecoverySchema3Overlay(%s,%s,%s)"
        % (json.dumps(community), json.dumps(overlay_nodes), json.dumps(overlay_edges))
    )

    node = next(row for row in result["nodes"] if row["node_id"] == "p1")
    edge = next(row for row in result["edges"] if row["edge_id"] == "e1")
    assert node["node_id"] == "p1"
    assert edge["edge_id"] == "e1"
    assert edge["u"] == "p1"
    assert edge["v"] == "p2"
    assert edge["edge_type"] == "COTRAVEL"
    assert edge["relation"] == "COTRAVEL"


def test_schema3_overlay_does_not_overwrite_base_structural_fields():
    community, overlay_nodes, overlay_edges = _schema3_overlay_fixture()
    community["nodes"][0].update(
        pooled_member=True,
        caught_before_snapshot=False,
        day_state="as_of",
    )
    community["edges"][0]["message_hop"] = 1
    overlay_nodes[0].update(
        x=99,
        y=98,
        pooled_member=False,
        caught_before_snapshot=True,
        day_state="malicious",
        arbitrary_overlay_key="must-not-leak",
    )
    overlay_edges[0].update(
        message_hop=99,
        arbitrary_overlay_key="must-not-leak",
    )

    result = _node_json(
        "mergeRecoverySchema3Overlay(%s,%s,%s)"
        % (json.dumps(community), json.dumps(overlay_nodes), json.dumps(overlay_edges))
    )

    node = next(row for row in result["nodes"] if row["node_id"] == "p1")
    edge = next(row for row in result["edges"] if row["edge_id"] == "e1")
    assert node["x"] == 0.1
    assert node["y"] == 0.2
    assert node["pooled_member"] is True
    assert node["caught_before_snapshot"] is False
    assert node["day_state"] == "as_of"
    assert "arbitrary_overlay_key" not in node
    assert edge["message_hop"] == 1
    assert "arbitrary_overlay_key" not in edge


@pytest.mark.parametrize(
    "field,value",
    [
        ("complete", False),
        ("complete", None),
        ("node_count", 3),
        ("node_count", -1),
        ("edge_count", 2),
        ("edge_count", -1),
    ],
)
def test_schema3_overlay_requires_complete_community_counts(field, value):
    community, overlay_nodes, overlay_edges = _schema3_overlay_fixture()
    community[field] = value

    result = _node_json(
        "mergeRecoverySchema3Overlay(%s,%s,%s)"
        % (json.dumps(community), json.dumps(overlay_nodes), json.dumps(overlay_edges))
    )

    assert result == {"available": False, "reason": "invalid-overlay-identity"}


def test_schema3_overlay_loader_contract_is_verified_and_stale_safe():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    mount = js.split("function mountRecoveryExplorerV3", 1)[1].split(
        "const recoveryMounts", 1
    )[0]
    loader = mount.split("async function loadRecoverySchema3OverlayRows", 1)[1].split(
        "function onV3Click", 1
    )[0]

    assert "recoveryValidateChunkOwner(owner)" in loader
    assert "owner[normalized==='node'?'node_chunks':'edge_chunks']" in loader
    assert "recoveryFetchJson(" in loader
    assert "recoverySidecarUrl(view,ref.path)" in loader
    assert "ref.sha256" in loader
    assert "recoveryValidatedChunkRows(" in loader
    assert "normalized==='node'?'nodes':'edges'" in loader
    assert "Chunk offset or count contract is invalid" in loader
    assert "if(disposed||token!==requestToken)return collected;" in loader
    assert "recoveryResolveCatalogRows" not in loader
    assert "recoveryApplyDayView" not in loader


@pytest.mark.parametrize(
    "mutate,reason",
    [
        (lambda nodes, edges: nodes.append({
            "node_id": "ghost", "explainer_median": 0.4, "rank": 2,
        }),
         "invalid-overlay-membership"),
        (lambda nodes, edges: edges.append({
            "edge_id": "ghost", "u": "p1", "v": "p2",
            "edge_type": "COTRAVEL", "relation": "COTRAVEL",
            "explainer_median": 0.4, "rank": 2,
        }), "invalid-overlay-membership"),
        (lambda nodes, edges: nodes.append({
            "node_id": "p1", "explainer_median": 0.4, "rank": 2,
        }),
         "invalid-overlay-identity"),
        (lambda nodes, edges: edges.append({
            "edge_id": "e1", "u": "p1", "v": "p2",
            "edge_type": "COTRAVEL", "relation": "COTRAVEL",
            "explainer_median": 0.4, "rank": 2,
        }), "invalid-overlay-identity"),
        (lambda nodes, edges: edges[0].update(u="p3"),
         "invalid-overlay-membership"),
        (lambda nodes, edges: nodes[0].update(explainer_median=float("nan")),
         "invalid-overlay-identity"),
        (lambda nodes, edges: nodes[0].update(explainer_median="not-a-number"),
         "invalid-overlay-identity"),
        (lambda nodes, edges: edges[0].update(edge_type="RESIDENCE"),
         "invalid-overlay-identity"),
        (lambda nodes, edges: edges[0].pop("u"),
         "invalid-overlay-identity"),
        (lambda nodes, edges: edges[0].pop("v"),
         "invalid-overlay-identity"),
        (lambda nodes, edges: edges[0].pop("edge_type"),
         "invalid-overlay-identity"),
        (lambda nodes, edges: edges[0].update(edge_type=""),
         "invalid-overlay-identity"),
        (lambda nodes, edges: edges[0].update(relation=""),
         "invalid-overlay-identity"),
        (lambda nodes, edges: edges[0].update(relation="RESIDENCE"),
         "invalid-overlay-identity"),
        (lambda nodes, edges: edges[0].pop("rank"),
         "invalid-overlay-identity"),
        (lambda nodes, edges: edges[0].update(rank=0),
         "invalid-overlay-identity"),
    ],
)
def test_schema3_overlay_validation_fails_closed(mutate, reason):
    community, overlay_nodes, overlay_edges = _schema3_overlay_fixture()
    mutate(overlay_nodes, overlay_edges)

    result = _node_json(
        "mergeRecoverySchema3Overlay(%s,%s,%s)"
        % (json.dumps(community), json.dumps(overlay_nodes), json.dumps(overlay_edges))
    )

    assert result == {"available": False, "reason": reason}


def test_schema3_graph_slice_bounded_context_preserves_attribution_and_tables():
    node_limit = _node_json("RECOVERY_GRAPH_NODE_LIMIT")
    edge_limit = _node_json("RECOVERY_GRAPH_EDGE_LIMIT")
    full_nodes = [
        {"node_id": "p0", "x": 0.0, "y": 0.0, "target": True},
        {"node_id": "p1", "x": 0.1, "y": 0.1, "attributed": True, "importance": 0.9},
        {"node_id": "p2", "x": 0.2, "y": 0.2, "attributed": True, "importance": 0.7},
    ]
    full_nodes.extend(
        {"node_id": "p%04d" % index, "x": 0.5, "y": 0.5}
        for index in range(3, node_limit + 5)
    )
    full_edges = [{
        "edge_id": "ea",
        "u": "p1",
        "v": "p2",
        "importance": 0.8,
        "attributed": True,
    }]
    full_edges.extend(
        {
            "edge_id": "e%04d" % index,
            "u": "p0",
            "v": "p%04d" % (3 + ((index - 3) % (node_limit + 2))),
            "importance": 0,
        }
        for index in range(3, edge_limit + 5)
    )

    result = _node_json(
        "(()=>{const fullNodes=%s;const fullEdges=%s;"
        "const nodeSnapshot=JSON.stringify(fullNodes);"
        "const edgeSnapshot=JSON.stringify(fullEdges);"
        "const first=buildRecoveryGraphSlice(fullNodes,fullEdges,'p0');"
        "const second=buildRecoveryGraphSlice(fullNodes,fullEdges,'p0');"
        "const reordered=buildRecoveryGraphSlice(fullNodes.slice().reverse(),"
        "fullEdges.slice().reverse(),'p0');"
        "return {deterministic:JSON.stringify(first)===JSON.stringify(second),"
        "inputsUnchanged:JSON.stringify(fullNodes)===nodeSnapshot"
        "&&JSON.stringify(fullEdges)===edgeSnapshot,slice:first,"
        "reorderedSlice:{sampled:reordered.sampled,nodes:reordered.nodes,"
        "edges:reordered.edges},reorderedTableNodes:reordered.tableNodes,"
        "reorderedTableEdges:reordered.tableEdges};})()"
        % (json.dumps(full_nodes), json.dumps(full_edges))
    )
    sliced = result["slice"]

    assert result["deterministic"] is True
    assert result["inputsUnchanged"] is True
    assert result["reorderedSlice"] == {
        "sampled": sliced["sampled"],
        "nodes": sliced["nodes"],
        "edges": sliced["edges"],
    }
    assert result["reorderedTableNodes"] == list(reversed(full_nodes))
    assert result["reorderedTableEdges"] == list(reversed(full_edges))
    assert sliced["sampled"] is True
    assert len(sliced["nodes"]) <= node_limit
    assert len(sliced["edges"]) <= edge_limit
    returned_node_ids = {node["node_id"] for node in sliced["nodes"]}
    assert {"p0", "p1", "p2"} <= returned_node_ids
    assert next(node for node in sliced["nodes"] if node["node_id"] == "p0")["target"] is True
    attributed_nodes = {
        node["node_id"]: node
        for node in sliced["nodes"]
        if node["node_id"] in {"p1", "p2"}
    }
    assert attributed_nodes["p1"]["importance"] == 0.9
    assert attributed_nodes["p1"]["attributed"] is True
    assert attributed_nodes["p2"]["importance"] == 0.7
    assert attributed_nodes["p2"]["attributed"] is True
    returned_edges = {edge["edge_id"]: edge for edge in sliced["edges"]}
    assert returned_edges["ea"]["importance"] == 0.8
    assert returned_edges["ea"]["attributed"] is True
    assert {"p1", "p2"} <= {
        returned_edges["ea"]["u"], returned_edges["ea"]["v"]
    }
    assert all(
        edge["u"] in returned_node_ids and edge["v"] in returned_node_ids
        for edge in sliced["edges"]
    )
    assert sliced["tableNodes"] == full_nodes
    assert sliced["tableEdges"] == full_edges


def test_schema3_graph_slice_fails_closed_when_mandatory_nodes_exceed_bound():
    node_limit = _node_json("RECOVERY_GRAPH_NODE_LIMIT")
    full_nodes = [
        {"node_id": "p0", "x": 0.0, "y": 0.0, "target": True},
        *(
            {"node_id": "e%04d" % index, "x": 0.5, "y": 0.5,
             "attributed": True, "importance": 0.9}
            for index in range(node_limit)
        ),
    ]

    result = _node_json(
        "buildRecoveryGraphSlice(%s,[], 'p0')" % json.dumps(full_nodes)
    )

    assert result == {
        "available": False,
        "reason": "mandatory-evidence-node-limit-exceeded",
        "sampled": True,
        "fullNodeCount": node_limit + 1,
        "fullEdgeCount": 0,
        "nodes": [],
        "edges": [],
        "tableNodes": full_nodes,
        "tableEdges": [],
    }


def test_draw_commands_propagate_mandatory_node_bound_without_truncating_tables():
    node_limit = _node_json("RECOVERY_GRAPH_NODE_LIMIT")
    explanation = _valid_recovery_artifact()["explanations"][0]
    full_nodes = [
        {"node_id": "p1", "x": 0.0, "y": 0.0, "target": True},
        *(
            {"node_id": "e%04d" % index, "x": 0.5, "y": 0.5,
             "attributed": True, "importance": 0.9}
            for index in range(node_limit)
        ),
    ]
    explanation["community"]["nodes"] = full_nodes
    explanation["community"]["edges"] = []
    for stage in explanation["flow_stages"]:
        stage["node_ids"] = [node["node_id"] for node in full_nodes]
        stage["edge_ids"] = []
        stage["emphasized_edge_ids"] = []

    result = _run_ui(
        "buildCommunityDrawCommands",
        explanation,
        {"mode": "flow", "stageId": "rank_fusion", "query": ""},
    )

    assert result["available"] is False
    assert result["reason"] == "mandatory-evidence-node-limit-exceeded"
    assert result["nodes"] == []
    assert result["edges"] == []
    assert len(result["tableNodes"]) == node_limit + 1
    assert result["tableEdges"] == []


def _sidecar(payload):
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    import hashlib

    return body, hashlib.sha256(body.encode()).hexdigest()


def _schema3_served_bundle():
    """Build a manifest plus every sidecar the schema-3 mount actually fetches."""
    base = "recovery/bundles/0123456789abcdef01234567/"
    files = {}

    def publish(path, payload, **extra):
        body, digest = _sidecar(payload)
        files[base + path] = body
        return {"path": path, "sha256": digest, **extra}

    node_records = [
        {"record_id": "p1", "record": {"node_id": "p1"}},
        {"record_id": "p2", "record": {"node_id": "p2"}},
    ]
    edge_records = [
        {
            "record_id": "e1",
            "record": {
                "edge_id": "e1",
                "u": "p1",
                "v": "p2",
                "edge_type": "COTRAVEL",
            },
        }
    ]
    node_catalog = publish(
        "catalog/nodes-0.json",
        {"offset": 0, "count": 2, "records": node_records},
        offset=0,
        count=2,
        first_id="p1",
        last_id="p2",
    )
    edge_catalog = publish(
        "catalog/edges-0.json",
        {"offset": 0, "count": 1, "records": edge_records},
        offset=0,
        count=1,
        first_id="e1",
        last_id="e1",
    )
    node_chunk = publish(
        "communities/nodes-0.json",
        {
            "offset": 0,
            "count": 2,
            "nodes": [
                {"node_id": "p1", "catalog_id": "p1"},
                {"node_id": "p2", "catalog_id": "p2"},
            ],
        },
        offset=0,
        count=2,
    )
    edge_chunk = publish(
        "communities/edges-0.json",
        {
            "offset": 0,
            "count": 1,
            "edges": [{"edge_id": "e1", "catalog_id": "e1"}],
        },
        offset=0,
        count=1,
    )
    overlay_node_chunk = publish(
        "overlays/h1-nodes-0.json",
        {
            "offset": 0,
            "count": 1,
            "nodes": [
                {
                    "node_id": "p2",
                    "explainer_median": 0.9,
                    "rank": 1,
                }
            ],
        },
        offset=0,
        count=1,
    )
    overlay_edge_chunk = publish(
        "overlays/h1-edges-0.json",
        {
            "offset": 0,
            "count": 1,
            "edges": [
                {
                    "edge_id": "e1",
                    "u": "p1",
                    "v": "p2",
                    "edge_type": "COTRAVEL",
                    "explainer_median": 0.8,
                    "rank": 1,
                }
            ],
        },
        offset=0,
        count=1,
    )
    node_status = publish(
        "communities/node-status-0.json",
        {
            "offset": 0,
            "count": 2,
            "node_statuses": [
                {
                    "node_id": "p1",
                    "x": 0.5,
                    "y": 0.5,
                    "pooled_member": True,
                    "caught_before_snapshot": False,
                },
                {
                    "node_id": "p2",
                    "x": 0.8,
                    "y": 0.3,
                    "pooled_member": True,
                    "caught_before_snapshot": True,
                },
            ],
        },
        offset=0,
        count=2,
    )
    edge_membership = publish(
        "communities/edge-membership-0.json",
        {
            "offset": 0,
            "count": 1,
            "edge_memberships": [
                {"edge_id": "e1", "message_hop": 1, "source_row_ids": ["row:1"]}
            ],
        },
        offset=0,
        count=1,
    )
    community = {
        "schema_version": "1.0",
        "complete": True,
        "community_key": "community:a",
        "node_count": 2,
        "edge_count": 1,
        "provenance_observation_count": 0,
        "node_chunks": [node_chunk],
        "edge_chunks": [edge_chunk],
        "provenance_chunks": [],
        "provenance_expansion_membership_chunks": [],
        "day_view": {
            "node_status_chunks": [node_status],
            "edge_membership_chunks": [edge_membership],
        },
    }
    community_ref = publish("communities/community-a.json", community)
    boundary = {
        "snapshot": "2025-01-02T00:00:00+00:00",
        "edge_rule": "available_time < snapshot",
        "caught_rule": "label_available_time_utc < snapshot",
    }
    hybrid_ref = publish(
        "cases/h1.json",
        {
            "schema_version": "3.0",
            "cohort": "hybrid_only",
            "community_key": "community:a",
            "case": {"case_id": "h1", "community_key": "community:a"},
            "explanation": {
                "evidence_boundary": boundary,
                "flow_stages": [
                    {"stage_id": "first_hop", "edge_rule": {"max_message_hop": 1}},
                    {"stage_id": "second_hop", "edge_rule": {"max_message_hop": 2}},
                    {
                        "stage_id": "component_pool",
                        "edge_rule": {
                            "edge_type": "COTRAVEL",
                            "both_pooled_members": True,
                        },
                    },
                    {"stage_id": "rank_fusion", "edge_rule": {"match_none": True}},
                ],
                "factors": [],
                "attributions": {"top_local_nodes": [], "top_edges": []},
                "llm_narrative": {},
                "stability": {
                    "stable_factor_count": 2,
                    "signed_effect_source": "counterfactual_only",
                },
                "faithfulness": {
                    "original_probability": 0.82,
                    "points": [
                        {
                            "fraction": 0.1,
                            "top_edge_probability_drop": 0.31,
                            "matched_random_probability_drop": 0.04,
                            "unmatched_control_count": 0,
                        },
                        {
                            "fraction": 0.25,
                            "top_edge_probability_drop": 0.48,
                            "matched_random_probability_drop": None,
                            "unmatched_control_count": 2,
                        },
                    ],
                },
            },
            "overlay_evidence": {
                "complete": True,
                "node_count": 1,
                "edge_count": 1,
                "provenance_observation_count": 0,
                "node_chunks": [overlay_node_chunk],
                "edge_chunks": [overlay_edge_chunk],
                "provenance_chunks": [],
                "provenance_expansion_membership_chunks": [],
            },
        },
    )
    baseline_ref = publish(
        "cases/b1.json",
        {
            "schema_version": "3.0",
            "cohort": "baseline_only",
            "community_key": "community:a",
            "case": {"case_id": "b1", "community_key": "community:a"},
            "detail": {
                "evidence_boundary": boundary,
                "structural_stages": [
                    {"stage_id": "first_hop", "edge_rule": {"max_message_hop": 1}},
                    {"stage_id": "second_hop", "edge_rule": {"max_message_hop": 2}},
                    {
                        "stage_id": "component_pool",
                        "edge_rule": {
                            "edge_type": "COTRAVEL",
                            "both_pooled_members": True,
                        },
                    },
                ],
            },
        },
    )
    artifact = _schema3_ui_artifact()
    for record in artifact["cohorts"]["hybrid_only"]:
        record["person_id"] = "p1"
        record["community_key"] = "community:a"
    for record in artifact["cohorts"]["baseline_only"]:
        record["person_id"] = "p1"
        record["community_key"] = "community:a"
    artifact["detail_index"] = {"h1": hybrid_ref}
    artifact["community_index"] = {"b1": baseline_ref}
    artifact["community_sidecar_index"] = {"community:a": community_ref}
    artifact["catalog_index"] = {
        "nodes": {"record_count": 2, "chunk_size": 250, "chunks": [node_catalog]},
        "edges": {"record_count": 1, "chunk_size": 250, "chunks": [edge_catalog]},
        "provenance": {"record_count": 0, "chunk_size": 250, "chunks": []},
    }
    return artifact, files


_FAKE_DOM = r"""
function fakeElement(tag){
  const element={
    tag,children:[],textContent:'',className:'',attrs:{},style:{},id:'',
    dataset:{},type:'',value:'',tabIndex:0,
    appendChild(child){this.children.push(child);return child;},
    setAttribute(name,value){this.attrs[name]=String(value);},
    getContext(){return null;},
    focus(){},
    replaceChildren(...nodes){this.children=nodes.slice();},
    querySelectorAll(){return [];},
    querySelector(){return null;},
    addEventListener(){},removeEventListener(){},
    classList:{add(){}},
    contains(){return true;}
  };
  return element;
}
const doc={
  createElement:fakeElement,
  createDocumentFragment(){return fakeElement('fragment');}
};
function makeRoot(){const root=fakeElement('div');root.ownerDocument=doc;return root;}
function allNodes(node){
  return [node,...node.children.flatMap(allNodes)];
}
function visibleText(root){
  return allNodes(root).map(node=>node.textContent).filter(Boolean);
}
function ariaLabels(root){
  return allNodes(root).map(node=>node.attrs['aria-label']).filter(Boolean);
}
"""


def _mount_schema3(case_id, bundle=None):
    artifact, files = bundle or _schema3_served_bundle()
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nconst FILES="
        + json.dumps(files)
        + ";\nglobalThis.fetch=async function(url){\n"
        "  globalThis.FETCHED.push(url);\n"
        "  const body=FILES[url];\n"
        "  if(body===undefined)return {ok:false,status:404};\n"
        "  return {ok:true,status:200,\n"
        "    arrayBuffer:async()=>new TextEncoder().encode(body).buffer};\n"
        "};\n"
        + _FAKE_DOM
        + "\nconst FETCHED=[];globalThis.FETCHED=FETCHED;"
        + "\nconst DETAILS=[];"
        + "const ORIGINAL_DETAIL=buildRecoverySchema3Detail;"
        + "buildRecoverySchema3Detail=function(...args){"
        + "  const result=ORIGINAL_DETAIL(...args);"
        + "  if(result.available)DETAILS.push(result);"
        + "  return result;"
        + "};"
        + "\nconst root=makeRoot();"
        + "\nconst cleanup=mountRecoveryExplorerV3(root,"
        + json.dumps(artifact)
        + ",{});"
        + "\nsetTimeout(()=>{"
        + "process.stdout.write(JSON.stringify({"
        + "text:visibleText(root),labels:ariaLabels(root),"
        + "fetches:FETCHED,details:DETAILS,"
        + "tables:allNodes(root).filter(n=>n.tag==='table').length,"
        + "rows:allNodes(root).filter(n=>n.tag==='tr').length"
        + "}));cleanup();},250);"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def test_schema3_mount_renders_hybrid_technical_evidence_end_to_end():
    rendered = _mount_schema3("h1")
    text = " | ".join(rendered["text"])

    assert "Hybrid technical detail" in text
    assert "Strict as-of evidence boundary" in text
    assert "Baseline score: 0.2" in text
    assert "Baseline percentile: 0.2" in text
    assert "Seed-0 GNN probability: 0.8" in text
    assert "Hybrid percentile-fusion score: 0.56" in text
    assert "Salient counterfactual factors" in text
    assert "Grounded narrative" in text
    assert "Highest-attribution evidence" in " | ".join(rendered["labels"] + rendered["text"])
    assert "As-of community context + explanation evidence" in text
    assert "Community data table" in text
    # Faithfulness, community members, and community relationships tables.
    assert rendered["tables"] == 3
    assert rendered["rows"] >= 5
    assert any("Community graph for Hybrid case p1" in label
               for label in rendered["labels"])
    assert any("overlays/h1-nodes-0.json" in url for url in rendered["fetches"])
    assert any("overlays/h1-edges-0.json" in url for url in rendered["fetches"])
    detail = rendered["details"][-1]
    overlay_nodes = {
        row["node_id"]: row for row in detail["explanation"]["overlayNodes"]
    }
    overlay_edges = {
        row["edge_id"]: row for row in detail["explanation"]["overlayEdges"]
    }
    assert overlay_nodes["p2"]["importance"] == 0.9
    assert overlay_nodes["p2"]["attributed"] is True
    assert overlay_edges["e1"]["importance"] == 0.8
    assert overlay_edges["e1"]["attributed"] is True


def test_schema3_lazy_joins_fail_closed_on_missing_catalog_or_day_identity():
    artifact, files = _schema3_served_bundle()
    base = artifact["sidecar_base"]
    bad_catalog = {
        "offset": 0,
        "count": 1,
        "records": [{"record_id": "p1", "record": {"node_id": "p1"}}],
    }
    body, digest = _sidecar(bad_catalog)
    files[base + "catalog/nodes-bad.json"] = body
    artifact["catalog_index"]["nodes"]["chunks"] = [{
        "path": "catalog/nodes-bad.json",
        "sha256": digest,
        "offset": 0,
        "count": 1,
        "first_id": "p1",
        "last_id": "p2",
    }]

    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nconst FILES="
        + json.dumps(files)
        + ";\nglobalThis.fetch=async function(url){\n"
        "  const body=FILES[url];\n"
        "  if(body===undefined)return {ok:false,status:404};\n"
        "  return {ok:true,status:200,\n"
        "    arrayBuffer:async()=>new TextEncoder().encode(body).buffer};\n"
        "};\n"
        + "(async()=>{const view=buildRecoverySchema3ViewModel("
        + json.dumps(artifact)
        + ");const owner=JSON.parse(FILES["
        + json.dumps(base + "communities/community-a.json")
        + "]);const result=[];"
        + "try{await recoveryResolveCatalogRows(view,[{catalog_id:'p2'}],'nodes');result.push('catalog-ok');}"
        + "catch(error){result.push(error.message);}"
        + "try{await recoveryApplyDayView(view,owner,'node',0,[{node_id:'ghost'}]);result.push('day-ok');}"
        + "catch(error){result.push(error.message);}"
        + "process.stdout.write(JSON.stringify(result));})();"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    result = json.loads(completed.stdout)

    assert result == [
        "Normalized catalog record is missing",
        "Normalized day-view identity contract is invalid",
    ]


def test_schema3_lazy_catalog_join_rejects_mismatched_record_identity():
    artifact, files = _schema3_served_bundle()
    base = artifact["sidecar_base"]
    bad_catalog = {
        "offset": 0,
        "count": 1,
        "records": [{"record_id": "p1", "record": {"node_id": "ghost"}}],
    }
    body, digest = _sidecar(bad_catalog)
    files[base + "catalog/nodes-bad.json"] = body
    artifact["catalog_index"]["nodes"]["chunks"] = [{
        "path": "catalog/nodes-bad.json",
        "sha256": digest,
        "offset": 0,
        "count": 1,
        "first_id": "p1",
        "last_id": "p1",
    }]

    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nconst FILES="
        + json.dumps(files)
        + ";\nglobalThis.fetch=async function(url){\n"
        "  const body=FILES[url];\n"
        "  if(body===undefined)return {ok:false,status:404};\n"
        "  return {ok:true,status:200,\n"
        "    arrayBuffer:async()=>new TextEncoder().encode(body).buffer};\n"
        "};\n"
        + "(async()=>{const view=buildRecoverySchema3ViewModel("
        + json.dumps(artifact)
        + ");const result=[];"
        + "try{await recoveryResolveCatalogRows(view,[{node_id:'p1',catalog_id:'p1'}],'nodes');result.push('join-ok');}"
        + "catch(error){result.push(error.message);}"
        + "process.stdout.write(JSON.stringify(result));})();"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )

    assert json.loads(completed.stdout) == [
        "Normalized catalog identity contract is invalid"
    ]


def test_schema3_mount_hides_baseline_control_from_explainer_only_case_list():
    artifact, files = _schema3_served_bundle()
    # Drop the Hybrid case so the control is the default selection.
    artifact["cohorts"]["hybrid_only"] = []
    artifact["summary"].update(hybrid_only_recovered=0, hybrid_total=0, net_gain=-1)
    artifact["coverage"].update(
        hybrid_requested=0, hybrid_selected=0, hybrid_explained=0
    )
    artifact["selection"]["selected_ids"]["hybrid_only"] = []
    artifact["detail_index"] = {}

    rendered = _mount_schema3("b1", (artifact, files))
    text = " | ".join(rendered["text"])

    assert "Showing GNN explanations only" in text
    assert "No cases match the current filter." in text
    assert "Community context only: GNNExplainer was not run for this baseline control." not in text
    assert "Structural evidence only" not in text
    assert "Salient counterfactual factors" not in text
    assert "Highest-attribution evidence" not in text
    assert "Grounded narrative" not in text
    assert "Community data table" not in text
    assert not any("baseline control p1" in label for label in rendered["labels"])
    assert not any("overlays/" in url for url in rendered["fetches"])
    assert rendered["details"] == []


def test_schema3_mount_hides_hybrid_structural_fallback_from_explainer_only_case_list():
    artifact, files = _schema3_served_bundle()
    base = artifact["sidecar_base"]
    fallback = json.loads(files[base + "cases/b1.json"])
    fallback["cohort"] = "hybrid_only"
    fallback["case"]["case_id"] = "h1"
    body, digest = _sidecar(fallback)
    files[base + "cases/h1-fallback.json"] = body

    artifact["cohorts"]["hybrid_only"][0].update(
        detail_status="community_only", detail_kind="community_control"
    )
    artifact["selection"]["selected_ids"]["hybrid_only"] = []
    artifact["selection"]["hybrid_structural_fallback_ids"] = ["h1"]
    artifact["detail_index"] = {}
    artifact["community_index"]["h1"] = {
        "path": "cases/h1-fallback.json",
        "sha256": digest,
        "cohort": "hybrid_only",
    }
    artifact["coverage"].update(
        hybrid_selected=0,
        hybrid_explained=0,
        hybrid_shortfall=1,
        shortfall=1,
        shortfall_reasons=["node_limit_exceeded"],
        hybrid_structural_fallback=1,
    )

    rendered = _mount_schema3("h1", (artifact, files))
    text = " | ".join(rendered["text"])

    assert "Showing GNN explanations only" in text
    assert "No cases match the current filter." in text
    assert "Community context only: GNNExplainer was not run for this Hybrid structural fallback." not in text
    assert "Community context only: GNNExplainer was not run for this baseline control." not in text
    assert all("Hybrid structural fallback p1" not in label for label in rendered["labels"])
    assert all("baseline control p1" not in label for label in rendered["labels"])
    assert rendered["details"] == []


def test_schema3_mount_surfaces_a_sidecar_hash_failure_instead_of_evidence():
    artifact, files = _schema3_served_bundle()
    key = next(
        name for name in files if "nodes-0" in name and "catalog" not in name
    )
    files[key] = files[key].replace('"p2"', '"pX"')

    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nconst FILES="
        + json.dumps(files)
        + ";\nglobalThis.fetch=async function(url){\n"
        "  const body=FILES[url];\n"
        "  if(body===undefined)return {ok:false,status:404};\n"
        "  return {ok:true,status:200,\n"
        "    arrayBuffer:async()=>new TextEncoder().encode(body).buffer};\n"
        "};\n"
        + _FAKE_DOM
        + "\nconst root=makeRoot();"
        + "\nconst cleanup=mountRecoveryExplorerV3(root,"
        + json.dumps(artifact)
        + ",{});"
        + "\nsetTimeout(()=>{"
        + "process.stdout.write(JSON.stringify({text:visibleText(root)}));"
        + "cleanup();},250);"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    text = " | ".join(json.loads(completed.stdout)["text"])

    # A tampered chunk must fail closed: no graph, no table, explicit reason.
    assert "Community data table" not in text
    assert "Complete as-of message community" not in text
    assert "SHA-256 mismatch" in text
    assert "python -m http.server 8000" in text


def test_schema3_mount_renders_restart_stability_and_removal_faithfulness():
    rendered = _mount_schema3("h1")
    text = " | ".join(rendered["text"])

    assert "Restart stability and removal faithfulness" in text
    assert "Stable factors across deterministic restarts: 2" in text
    assert "Signed effect source: counterfactual_only" in text
    assert "Seed-0 probability before removal: 0.82" in text
    # The matched random control is what makes a top-edge drop meaningful.
    assert "matched random control" in text
    assert "0.31" in text and "0.04" in text
    # A control that could not be matched is reported, never imputed.
    assert "not measured" in text
    assert any(
        "Edge removal faithfulness by removed fraction" in label
        for label in rendered["labels"]
    )


def test_schema3_stability_and_faithfulness_fail_closed_without_measurements():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    mount = js.split("function mountRecoveryExplorerV3", 1)[1].split(
        "const recoveryMounts", 1
    )[0]
    panel = mount.split("function renderStabilityAndFaithfulness", 1)[1].split(
        "function graphButton", 1
    )[0]

    assert "Restart stability is unavailable in this artifact." in panel
    assert "Edge-removal faithfulness is unavailable in this artifact." in panel
    assert "renderStabilityAndFaithfulness(left,detailView.explanation)" in mount
