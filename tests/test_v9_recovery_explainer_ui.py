import copy
import hashlib
import importlib.util
import json
import re
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












def test_schema_v3_ui_contract_preserves_full_cohorts_and_evidence_boundary():
    js = UI.V9_RECOVERY_EXPLAINER_JS

    for token in (
        "schema_version!=='3.0'",
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


def _run_display_formatter(expression):
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


def test_recovery_display_formatter_caps_precision_and_handles_signs():
    result = _run_display_formatter(
        "[recoveryFormatNumber(0.8427),recoveryFormatNumber(0.5),"
        "recoveryFormatNumber(1),recoveryFormatSigned(-4),"
        "recoveryFormatSigned(32),recoveryFormatNumber(NaN)]"
    )
    assert result == ["0.843", "0.5", "1", "-4", "+32", "not available"]


def test_factor_view_model_resolves_pair_factor_to_readable_edge_and_keeps_id_technical():
    view = _run_ui(
        "buildRecoveryFactorViewModel",
        {
            "factors": [
                {
                    "factor_id": "pair:pair:abc123:rel:7",
                    "label": "pair:pair:abc123:rel:7",
                    "kind": "pair_relation",
                    "stability": "unstable",
                    "counterfactual": {
                        "original_hybrid_rank": 8,
                        "ablated_hybrid_rank": 14,
                    },
                }
            ],
            "community": {
                "edges": [
                    {
                    "edge_id": "pair:abc123:rel:7",
                    "u": "person:1",
                    "v": "person:2",
                    "edge_type": "COTRAVEL",
                    "rel": 7,
                    }
                ]
            },
        },
    )

    assert view == [
        {
            "factorId": "pair:pair:abc123:rel:7",
            "technicalId": "pair:pair:abc123:rel:7",
            "label": "COTRAVEL · person:1 ↔ person:2",
            "stability": "unstable",
            "stabilityLabel": "varied across restarts",
            "effect": 6,
            "effectLabel": "measured rank effect",
            "relation": "COTRAVEL",
            "u": "person:1",
            "v": "person:2",
            "edgeId": "pair:abc123:rel:7",
        }
    ]


def test_factors_and_attribution_copy_explains_restart_consistency_and_top5_weights():
    js = UI.V9_RECOVERY_EXPLAINER_JS

    assert "Measured effect is the rank change when a factor is removed" in js
    assert "Restart support reports whether the explainer selected that factor consistently" in js
    assert "No factor was consistently selected across restarts" in js
    assert "varied across restarts" in js
    assert "'Effect: '+recoveryFormatSigned(readable.effect)" in js
    assert "'Restart support: '+readable.stabilityLabel" in js
    assert "top 5 nodes and top 5 connections" in js
    assert "normalized unsigned median salience weights" in js


def test_factor_effect_labels_keep_effect_and_restart_support_independent():
    result = _run_display_formatter(
        "[recoveryFactorEffectLabel(5),recoveryFactorEffectLabel(-2),"
        "recoveryFactorEffectLabel(0)]"
    )
    assert result == [
        "measured rank effect",
        "countervailing effect",
        "no measured rank effect",
    ]


def test_factor_restart_support_labels_selection_consistency():
    result = _run_display_formatter(
        "[recoveryFactorStabilityLabel('stable'),"
        "recoveryFactorStabilityLabel('unstable'),"
        "recoveryFactorStabilityLabel('countervailing')]"
    )
    assert result == [
        "consistently selected by explainer",
        "varied across restarts",
        "mixed signed effects across restarts",
    ]


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


def test_highest_attribution_view_model_ranks_top5_without_mutating_input():
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
            {"rank": 4, "nodeId": "n4", "weight": 0.99},
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


def test_highest_attribution_view_model_limits_each_category_to_top5():
    explanation = {
        "attributions": {
            "top_local_nodes": [
                {"rank": index, "node_id": f"n{index}", "explainer_median": 1 / index}
                for index in range(1, 7)
            ],
            "top_edges": [
                {
                    "rank": index,
                    "edge_id": f"e{index}",
                    "u": f"n{index}",
                    "v": f"n{index + 1}",
                    "edge_type": "COTRAVEL",
                    "explainer_median": 1 / index,
                }
                for index in range(1, 7)
            ],
        }
    }

    view = _run_ui("buildHighestAttributionViewModel", explanation)

    assert [row["nodeId"] for row in view["nodes"]] == [
        "n1", "n2", "n3", "n4", "n5"
    ]
    assert [row["edgeId"] for row in view["connections"]] == [
        "e1", "e2", "e3", "e4", "e5"
    ]


def test_highest_attribution_view_model_preserves_fewer_than_five_valid_entries():
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

    assert [row["nodeId"] for row in view["nodes"]] == ["z", "a", "b", "c"]
    assert [row["rank"] for row in view["nodes"]] == [1, 2, 3, 4]


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
    connection_text = result["text"]
    assert connection_text.index("COTRAVEL") < connection_text.index("n1 ↔ n2")
    assert connection_text.index("SHARED_PLATE") < connection_text.index("n2 ↔ n3")
    assert connection_text.index("RESIDENCE") < connection_text.index("n1 ↔ n3")


def test_recovery_date_only_formatter_keeps_plain_dates_and_strips_iso_time():
    result = _run_display_formatter(
        "[recoveryFormatDateOnly('2025-01-31T23:59:59Z'),"
        "recoveryFormatDateOnly('2025-01-31'),"
        "recoveryFormatDateOnly('not-a-date')]"
    )
    assert result == ["2025-01-31", "2025-01-31", "not available"]


def test_highest_attribution_connections_compact_visible_ids_but_retain_full_accessibility_ids():
    explanation = {
        "attributions": {
            "top_local_nodes": [],
            "top_edges": [{
                "rank": 1,
                "edge_id": "edge:full-identifier-123456789",
                "u": "person:source-123456789",
                "v": "person:target-987654321",
                "edge_type": "COTRAVEL",
                "explainer_median": 0.9,
            }],
        }
    }
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nconst explanation="
        + json.dumps(explanation)
        + r""";
function fakeElement(tag){
  return {tag,children:[],textContent:'',className:'',attrs:{},style:{},id:'',
    appendChild(child){this.children.push(child);return child;},
    setAttribute(name,value){this.attrs[name]=String(value);}};
}
const doc={createElement:fakeElement};
const root=renderHighestAttributionPanel(doc,explanation);
function all(node){return [node,...node.children.flatMap(all)];}
const nodes=all(root);
process.stdout.write(JSON.stringify({
  text:nodes.map(node=>node.textContent).filter(Boolean),
  titles:nodes.map(node=>node.attrs.title).filter(Boolean),
  labels:nodes.map(node=>node.attrs['aria-label']).filter(Boolean)
}));"""
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    result = json.loads(completed.stdout)
    assert any(text.startswith("COTRAVEL") for text in result["text"])
    assert not any("person:source-123456789" in text for text in result["text"])
    assert any("person:source-123456789" in value
               and "person:target-987654321" in value
               and "edge:full-identifier-123456789" in value
               for value in result["labels"])
    assert any("person:source-123456789" in value
               and "person:target-987654321" in value
               and "edge:full-identifier-123456789" in value
               for value in result["titles"])


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
        "outside message community",
        "Inner color and pattern show the observable relationship type",
        "scoring day",
        "recoveryEdgeStyle",
    ):
        assert token in js

    assert js.count("root.addEventListener('click'") == 1
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


def test_recovery_mobile_toolbar_wraps_with_full_width_touch_controls():
    css = UI.V9_RECOVERY_EXPLAINER_CSS

    assert "#tab-v9Results .v9-recovery-toolbar { display:grid; grid-template-columns:repeat(auto-fit,minmax(178px,1fr));" in css
    assert "#tab-v9Results .v9-recovery-toolbar { flex-wrap: nowrap;" not in css
    assert "#tab-v9Results .v9-recovery-toolbar { overflow-x: auto;" not in css
    assert "#tab-v9Results .v9-recovery-control-group" in css
    assert "#tab-v9Results .v9-recovery-control-items" in css
    assert "#tab-v9Results .v9-recovery-control-items > * { width:100%; min-width:0; }" in css
    assert "#tab-v9Results .v9-recovery-toolbar > .v9-recovery-search, #tab-v9Results .v9-recovery-toolbar .v9-recovery-select { width:100%; min-width:0; }" in css
    assert (
        "#tab-v9Results .v9-recovery-button, #tab-v9Results .v9-recovery-toolbar .v9-recovery-select, #tab-v9Results .v9-recovery-search { min-height: 44px; }"
        in css
    )
    assert (
        "#tab-v9Results .v9-recovery-control-items .v9-recovery-button { min-height:44px; }"
        in css
    )


def test_schema3_graph_workspace_css_uses_bounded_rail_and_graph_first_tracks():
    css = UI.V9_RECOVERY_EXPLAINER_CSS

    for token in (
        "grid-template-columns: 214px minmax(0, 1fr)",
        "max-height: min(70vh, 720px)",
        "position: sticky",
        "top: 16px",
        "overflow-y: auto",
        "height: clamp(460px, 58vh, 640px)",
        ".v9-recovery-explanation-row",
        "grid-template-columns: minmax(0, 1fr)",
    ):
        assert token in css
    assert "radial-gradient" not in css


def test_schema3_graph_workspace_css_switches_to_picker_and_touch_grid():
    css = UI.V9_RECOVERY_EXPLAINER_CSS

    for token in (
        "@media(max-width:900px)",
        ".v9-recovery-v3-list { display: none; }",
        ".v9-recovery-v3-picker { display: block;",
        "height: clamp(360px, 48vh, 470px)",
        "@media(max-width:700px)",
        "height: 340px; min-height: 300px",
        "grid-template-columns: repeat(2, minmax(0, 1fr))",
        "min-height: 44px",
        "@media(max-width:359px)",
    ):
        assert token in css
    assert "@media(max-width:360px)" not in css


def test_schema3_factor_identifiers_wrap_without_clipping():
    css = UI.V9_RECOVERY_EXPLAINER_CSS
    assert ".v9-recovery-factor {" in css
    assert "min-width: 0" in css
    assert ".v9-recovery-factor strong {" in css
    assert "overflow-wrap: anywhere" in css
    assert "word-break: break-word" in css


def test_recovery_summary_and_metadata_keep_readable_columns_and_type():
    css = UI.V9_RECOVERY_EXPLAINER_CSS

    assert "#tab-v9Results .v9-recovery-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));" in css
    assert "#tab-v9Results .v9-recovery-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }" in css
    assert "#tab-v9Results .v9-recovery-summary { grid-template-columns: 1fr; }" in css
    assert "#tab-v9Results .v9-recovery-stat span {" in css
    assert "#tab-v9Results .v9-recovery-stat span { display: block; margin-top: 4px; color: var(--text2); font-size: 10px;" in css
    assert "#tab-v9Results .v9-recovery-table-wrap { margin-top: 12px; overflow-x: auto; }" in css
    assert "white-space: nowrap" in css
    assert not re.search(
        r"#tab-v9Results \.(?:v9-recovery|v9-attribution)[^{}]*font-size: [89]px",
        css,
    )


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
        "recoveryEdgeStyle",
        {"importance": 0.0, "emphasized": True, "attributed": True},
    )
    high = _run_ui(
        "recoveryEdgeStyle",
        {"importance": 1.0, "emphasized": True, "attributed": True},
    )
    background = _run_ui(
        "recoveryEdgeStyle", {"importance": 0.0, "emphasized": False}
    )

    assert low == {
        "alpha": 0.9,
        "lineWidth": 1.6,
        "evidenceAlpha": 0.16,
        "evidenceLineWidth": 2.5,
    }
    assert high == {
        "alpha": 0.95,
        "lineWidth": 3,
        "evidenceAlpha": 0.48,
        "evidenceLineWidth": 8,
    }
    assert background == {
        "alpha": 0.14,
        "lineWidth": 0.75,
        "evidenceAlpha": 0,
        "evidenceLineWidth": 0,
    }


def test_edge_style_scales_evidence_against_the_strongest_visible_edge():
    """A case that attributes every edge at high absolute weight must still
    show a readable spread instead of saturating the whole canvas in gold."""
    scale = _run_ui(
        "recoveryEvidenceScale",
        [
            {"attributed": True, "importance": 0.62},
            {"attributed": True, "importance": 0.31},
            {"attributed": False, "importance": 0.99},
        ],
    )
    assert scale == 0.62

    strongest = _run_ui(
        "recoveryEdgeStyle", {"importance": 0.62, "attributed": True}, 0.62
    )
    weaker = _run_ui(
        "recoveryEdgeStyle", {"importance": 0.31, "attributed": True}, 0.62
    )

    assert strongest["evidenceLineWidth"] == 8
    assert weaker["evidenceLineWidth"] == 5.25
    assert strongest["evidenceAlpha"] > weaker["evidenceAlpha"]


def test_node_label_priority_keeps_identity_labels_above_bulk_context():
    """Sampled communities put hundreds of markers in a narrow band. Labels the
    reader explicitly asked for must outrank attributed and emphasized bulk."""

    def priority(node, hover=None, emphasized=(), density="key"):
        script = (
            UI.V9_RECOVERY_EXPLAINER_JS
            + "\nconst result=recoveryNodeLabelPriority("
            + json.dumps(node)
            + ","
            + json.dumps(hover)
            + ",new Set("
            + json.dumps(list(emphasized))
            + "),"
            + json.dumps(density)
            + ");process.stdout.write(JSON.stringify(result));"
        )
        completed = subprocess.run(
            ["node", "-e", script], check=True, capture_output=True, text=True
        )
        return json.loads(completed.stdout)

    target = priority({"id": "a", "target": True})
    matched = priority({"id": "b", "matched": True})
    hovered = priority({"id": "c"}, hover="c")
    ranked = priority({"id": "d", "attributed": True, "rank": 2})
    ranked_later = priority({"id": "e", "attributed": True, "rank": 40})
    unranked = priority({"id": "f", "attributed": True})
    emphasized = priority({"id": "g"}, emphasized=["g"])
    plain = priority({"id": "h"})

    assert target < matched < hovered < ranked < ranked_later < unranked
    assert unranked < emphasized
    assert plain is None
    assert priority({"id": "i", "target": True}, density="none") == 0
    assert priority({"id": "j"}, density="none") is None
    assert priority({"id": "k"}, density="all") == 300


def test_node_label_box_never_collides_with_its_own_marker():
    """Collision-checked labels are tested against every marker box including
    their own, so an overlapping label box silently suppresses every label."""
    for radius in (4.5, 6, 8):
        for text_width in (1, 40, 120):
            script = (
                UI.V9_RECOVERY_EXPLAINER_JS
                + "\nconst point={x:120,y:80};const radius="
                + json.dumps(radius)
                + ";process.stdout.write(JSON.stringify({"
                + "overlaps:recoveryRectOverlaps("
                + "recoveryNodeLabelBox(point,radius," + json.dumps(text_width) + "),"
                + "recoveryNodeMarkerBox(point,radius))}));"
            )
            completed = subprocess.run(
                ["node", "-e", script], check=True, capture_output=True, text=True
            )
            assert json.loads(completed.stdout)["overlaps"] is False, (
                f"label box overlaps its marker at radius={radius}"
            )


def test_edge_style_falls_back_to_absolute_weight_without_a_scale():
    assert _run_ui(
        "recoveryEdgeStyle", {"importance": 0.5, "attributed": True}, 0
    ) == _run_ui("recoveryEdgeStyle", {"importance": 0.5, "attributed": True})


def test_recovery_relation_presentation_normalizes_known_and_unknown_relations():
    assert _run_ui("recoveryRelationPresentation", "   ") == {
        "key": "RELATION",
        "label": "Relation",
        "color": "#8b8b96",
        "dash": [12, 6],
    }
    assert _run_ui("recoveryRelationPresentation", None) == {
        "key": "RELATION",
        "label": "Relation",
        "color": "#8b8b96",
        "dash": [12, 6],
    }
    assert _run_ui("recoveryRelationPresentation", " cotravel ") == {
        "key": "COTRAVEL",
        "label": "Co-travel",
        "color": "#34d399",
        "dash": [],
    }
    assert _run_ui("recoveryRelationPresentation", "RESIDENCE") == {
        "key": "RESIDENCE",
        "label": "Residence",
        "color": "#60a5fa",
        "dash": [9, 5],
    }
    assert _run_ui("recoveryRelationPresentation", "SHARED_PLATE") == {
        "key": "SHARED_PLATE",
        "label": "Shared plate",
        "color": "#a78bfa",
        "dash": [2, 5],
    }
    assert _run_ui("recoveryRelationPresentation", "OTHER_LINK") == {
        "key": "OTHER_LINK",
        "label": "Other link",
        "color": "#8b8b96",
        "dash": [12, 6],
    }
    assert _run_ui("recoveryRelationPresentation", "  foo_BAR_baz  ") == {
        "key": "FOO_BAR_BAZ",
        "label": "Foo bar baz",
        "color": "#8b8b96",
        "dash": [12, 6],
    }


def test_non_attributed_emphasized_edge_uses_dual_channel_without_evidence():
    assert _run_ui(
        "recoveryEdgeStyle", {"importance": 0.0, "emphasized": True}
    ) == {
        "alpha": 0.5,
        "lineWidth": 1.35,
        "evidenceAlpha": 0,
        "evidenceLineWidth": 0,
    }


def test_non_attributed_edge_style_does_not_scale_with_importance():
    assert _run_ui(
        "recoveryEdgeStyle", {"importance": 1.0, "emphasized": True}
    ) == {
        "alpha": 0.5,
        "lineWidth": 1.35,
        "evidenceAlpha": 0,
        "evidenceLineWidth": 0,
    }
    assert _run_ui(
        "recoveryEdgeStyle", {"importance": 1.0, "emphasized": False}
    ) == {
        "alpha": 0.14,
        "lineWidth": 0.75,
        "evidenceAlpha": 0,
        "evidenceLineWidth": 0,
    }


def test_filter_recovery_graph_commands_by_relationship_is_non_mutating():
    commands = {
        "nodes": [
            {"id": "target", "target": True},
            {"id": "n2"},
            {"id": "n3"},
        ],
        "edges": [
            {"id": "e1", "relation": "COTRAVEL", "u": "target", "v": "n2"},
            {"id": "e2", "relation": "RESIDENCE", "u": "target", "v": "n3"},
        ],
        "tableNodes": [{"id": "target"}, {"id": "n2"}, {"id": "n3"}],
        "tableEdges": [
            {"id": "e1", "relation": "COTRAVEL"},
            {"id": "e2", "relation": "RESIDENCE"},
        ],
        "provenanceNodes": [{"id": "p"}],
        "provenanceEdges": [{"id": "pe"}],
    }
    before = copy.deepcopy(commands)
    result = _run_ui("filterRecoveryGraphCommands", commands, "RESIDENCE")
    assert [edge["id"] for edge in result["edges"]] == ["e2"]
    assert [node["id"] for node in result["nodes"]] == ["target", "n3"]
    assert result["tableEdges"] == commands["tableEdges"]
    assert result["tableNodes"] == commands["tableNodes"]
    assert result["provenanceNodes"] == []
    assert result["provenanceEdges"] == []
    assert result["relationship"] == "RESIDENCE"
    assert result["relationshipOptions"] == [
        {"key": "all", "label": "All types"},
        {"key": "COTRAVEL", "label": "Co-travel"},
        {"key": "RESIDENCE", "label": "Residence"},
    ]
    assert commands == before


def test_relationship_filter_options_come_from_canvas_edges_and_validate_selection():
    commands = {
        "nodes": [
            {"id": "target", "target": True},
            {"id": "n2"},
            {"id": "n3"},
        ],
        "edges": [
            {"id": "e1", "relation": "COTRAVEL", "u": "target", "v": "n2"},
            {"id": "e2", "relation": "RESIDENCE", "u": "target", "v": "n3"},
            {"id": "e3", "relation": "Z_LINK", "u": "n2", "v": "n3"},
            {"id": "e4", "relation": "A_LINK", "u": "n2", "v": "n3"},
        ],
        "tableNodes": [{"id": "target"}],
        "tableEdges": [{"id": "e1"}, {"id": "e2"}],
    }
    result = _run_ui("filterRecoveryGraphCommands", commands, "RESIDENCE")
    assert result["relationship"] == "RESIDENCE"
    assert result["relationshipOptions"] == [
        {"key": "all", "label": "All types"},
        {"key": "COTRAVEL", "label": "Co-travel"},
        {"key": "RESIDENCE", "label": "Residence"},
        {"key": "A_LINK", "label": "A link"},
        {"key": "Z_LINK", "label": "Z link"},
    ]


def test_relationship_filter_invalid_selection_falls_back_to_all_and_clones_arrays():
    commands = {
        "nodes": [{"id": "target", "target": True}],
        "edges": [{"id": "e1", "relation": "COTRAVEL", "u": "target", "v": "target"}],
        "tableNodes": [{"id": "target"}],
        "tableEdges": [{"id": "e1"}],
        "provenanceNodes": [{"id": "p"}],
        "provenanceEdges": [{"id": "pe"}],
    }
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nconst input=" + json.dumps(commands) + ";"
        + "const result=filterRecoveryGraphCommands(input,'MISSING');"
        + "process.stdout.write(JSON.stringify({result,inputSame:JSON.stringify(input)==="
        + "JSON.stringify(" + json.dumps(commands) + "),"
        + "arrays:[result.nodes!==input.nodes,result.edges!==input.edges,"
        + "result.tableNodes!==input.tableNodes,result.tableEdges!==input.tableEdges,"
        + "result.provenanceNodes!==input.provenanceNodes,result.provenanceEdges!==input.provenanceEdges]}));"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    payload = json.loads(completed.stdout)
    assert payload["inputSame"] is True
    assert all(payload["arrays"])
    assert payload["result"]["relationship"] == "all"
    assert payload["result"]["provenanceNodes"] == commands["provenanceNodes"]


def test_uppercase_all_relation_is_distinct_from_lowercase_all_control():
    edges = [
        {"id": "e1", "relation": "ALL", "u": "target", "v": "n1"},
        {"id": "e2", "relation": "COTRAVEL", "u": "target", "v": "n2"},
    ]
    options = _run_ui("recoveryGraphRelationshipOptions", edges)
    assert options == [
        {"key": "all", "label": "All types"},
        {"key": "COTRAVEL", "label": "Co-travel"},
        {"key": "ALL", "label": "All"},
    ]


def test_all_control_and_actual_all_relation_filter_separately():
    commands = {
        "nodes": [
            {"id": "target", "target": True},
            {"id": "n1"},
            {"id": "n2"},
        ],
        "edges": [
            {"id": "e1", "relation": "ALL", "u": "target", "v": "n1"},
            {"id": "e2", "relation": "COTRAVEL", "u": "target", "v": "n2"},
        ],
    }
    all_result = _run_ui("filterRecoveryGraphCommands", commands, "all")
    actual_all_result = _run_ui("filterRecoveryGraphCommands", commands, "ALL")
    assert [edge["id"] for edge in all_result["edges"]] == ["e1", "e2"]
    assert all_result["relationship"] == "all"
    assert [edge["id"] for edge in actual_all_result["edges"]] == ["e1"]
    assert actual_all_result["relationship"] == "ALL"



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



def test_essential_explorer_labels_use_the_contrast_safe_text_token():
    assert "var(--text3)" not in UI.V9_RECOVERY_EXPLAINER_CSS
    assert UI.V9_RECOVERY_EXPLAINER_CSS.count("var(--text2)") >= 12























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


def test_valid_llm_v4_narrative_is_restored_with_published_provenance():
    narrative = _valid_recovery_artifact()["explanations"][0]["llm_narrative"]
    narrative.update(
        source="llm",
        model="gemma4:12b",
        prompt_version="v4",
        validated=True,
    )

    view = _run_ui("validateRecoveryNarrative", narrative)

    assert view == {
        "visible": True,
        "summary": "Seed 0 evidence summary.",
        "summarySourceRefs": ["scope.observability_seed"],
        "claims": [],
        "source": "llm",
        "model": "gemma4:12b",
    }


def test_v4_narrative_accepts_producer_generated_evidence_source_refs():
    narrative = _valid_recovery_artifact()["explanations"][0]["llm_narrative"]
    narrative["summary_source_refs"] = ["rank_fusion.hybrid_score"]
    narrative["claims"] = [
        {
            "text": "Attribution evidence.",
            "source_refs": ["attributions.top_local_nodes.0.node_id"],
        },
        {
            "text": "Component evidence.",
            "source_refs": [
                "component_pooling.top_members_by_absolute_contribution.0.person_id"
            ],
        },
        {"text": "Fusion evidence.", "source_refs": ["rank_fusion.hybrid_score"]},
    ]
    narrative.update(source="llm", model="gemma4:12b", prompt_version="v4")

    view = _run_ui("validateRecoveryNarrative", narrative)

    assert view["visible"] is True
    assert view["summarySourceRefs"] == ["rank_fusion.hybrid_score"]


def test_v4_narrative_remains_hidden_for_unknown_source_refs():
    narrative = _valid_recovery_artifact()["explanations"][0]["llm_narrative"]
    narrative["summary_source_refs"] = ["rank_fusion.unknown_field"]
    narrative.update(source="llm", model="gemma4:12b", prompt_version="v4")

    assert _run_ui("validateRecoveryNarrative", narrative)["visible"] is False


def test_render_factors_omits_zero_rank_movement_and_restart_warning_when_empty():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    render_factors = js.split("function renderFactors(", 1)[1].split(
        "function renderNarrative(", 1
    )[0]

    assert "Zero-rank-movement factors are omitted" in render_factors
    assert ".filter(factor=>recoveryValidFactor(factor)" in render_factors
    assert (
        "factor.counterfactual.ablated_hybrid_rank!=="
        "factor.counterfactual.original_hybrid_rank"
        in render_factors
    )
    assert "if(factors.length&&!factors.some(factor=>factor.stability==='stable'))" in render_factors
    assert "No measured factors are available for this explanation." in render_factors


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
    ("mode", "stage_id", "expected_emphasis", "expected_nodes"),
    [
        ("all", "first_hop", ["edge-1"], ["p1", "p2"]),
        ("flow", "first_hop", ["edge-1"], ["p1", "p2"]),
        ("flow", "second_hop", [], ["p1"]),
        ("flow", "component_pool", ["edge-1"], ["p1", "p2"]),
        ("flow", "rank_fusion", ["edge-1"], ["p1", "p2"]),
    ],
)
def test_draw_commands_filter_hop_canvas_membership_and_preserve_other_stages(
    mode, stage_id, expected_emphasis, expected_nodes
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
    assert [node["id"] for node in result["nodes"]] == expected_nodes
    assert [edge["id"] for edge in result["edges"]] == expected_emphasis
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

    assert low["alpha"] < high["alpha"]
    assert low["lineWidth"] < high["lineWidth"]
    assert low["evidenceAlpha"] < high["evidenceAlpha"]
    assert low["evidenceLineWidth"] < high["evidenceLineWidth"]


def test_evidence_edge_selection_is_rank_first_stable_and_bounded():
    edges = [
        {"id": "e3", "rank": 3, "importance": 0.95, "attributed": True},
        {"id": "e1", "rank": 1, "importance": 0.7, "attributed": True},
        {"id": "e2", "rank": 2, "importance": 0.8, "attributed": True},
        {"id": "e4", "rank": 4, "importance": 1.0, "attributed": True},
        {"id": "context", "rank": None, "importance": 1.0, "attributed": False},
    ]

    selected = _run_ui("selectRecoveryEvidenceEdges", edges, 3)

    assert [edge["id"] for edge in selected] == ["e1", "e2", "e3"]


def test_evidence_bounds_fit_target_and_attributed_endpoints_only():
    commands = {
        "nodes": [
            {"id": "target", "x": 0.4, "y": 0.4, "target": True},
            {"id": "evidence", "x": 0.6, "y": 0.7, "target": False},
            {"id": "context", "x": 0.99, "y": 0.01, "target": False},
        ],
        "edges": [
            {
                "id": "e1",
                "u": "target",
                "v": "evidence",
                "attributed": True,
            }
        ],
    }

    bounds = _run_ui("recoveryEvidenceBounds", commands)

    assert bounds == {"minX": 0.32, "minY": 0.32, "maxX": 0.68, "maxY": 0.78}


def test_evidence_labels_stay_inside_mobile_canvas_bounds():
    script = UI.V9_RECOVERY_EXPLAINER_JS + r'''
const calls=[];
const context={
  globalAlpha:1,
  measureText(text){return {width:text.length*8};},
  beginPath(){},moveTo(){},lineTo(){},stroke(){},fill(){},
  quadraticCurveTo(){},closePath(){},
  setLineDash(){},
  fillRect(){},strokeRect(){},fillText(){}
};
const originalRoundedRect=recoveryFillRoundedRect;
recoveryFillRoundedRect=function(target,x,y,width,height,radius){
  calls.push({op:'fillRect',x,y,width,height});
  return originalRoundedRect(target,x,y,width,height,radius);
};
recoveryDrawEvidenceLabels(
  context,
  [{id:'edge-right',u:'u',v:'v',relation:'COTRAVEL',importance:0.9,
    rank:1,attributed:true}],
  new Map([['u',{x:300,y:90}],['v',{x:320,y:90}]]),
  [],
  340,
  180
);
process.stdout.write(JSON.stringify(calls));'''
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    rects = json.loads(completed.stdout)

    assert rects
    assert all(6 <= rect["x"] for rect in rects)
    assert all(rect["x"] + rect["width"] <= 334 for rect in rects)
    assert all(6 <= rect["y"] for rect in rects)
    assert all(rect["y"] + rect["height"] <= 174 for rect in rects)


def test_graph_edge_strokes_encode_evidence_then_relationship_and_reset_state():
    script = UI.V9_RECOVERY_EXPLAINER_JS + r'''
function fakeContext(){
  const calls=[];
  const context={
    globalAlpha:1,strokeStyle:null,lineWidth:0,
    beginPath(){calls.push({op:'beginPath'});},
    setLineDash(value){this.dash=value.slice();calls.push({op:'dash',value:this.dash.slice()});},
    moveTo(){},lineTo(){},quadraticCurveTo(){},closePath(){},fill(){},
    stroke(){calls.push({op:'stroke',style:this.strokeStyle,alpha:this.globalAlpha,
      width:this.lineWidth,dash:(this.dash||[]).slice()});}
  };
  context.calls=calls;return context;
}
const attributed=fakeContext();
recoveryStrokeGraphEdge(attributed,{x:0,y:0},{x:1,y:1},
  {relation:'RESIDENCE',importance:1,attributed:true});
const context=fakeContext();
recoveryStrokeGraphEdge(context,{x:0,y:0},{x:1,y:1},
  {relation:'RESIDENCE',importance:1,attributed:false});
process.stdout.write(JSON.stringify({attributed:attributed.calls,context:context.calls,
  attributedReset:{alpha:attributed.globalAlpha,dash:attributed.dash||[]},
  contextReset:{alpha:context.globalAlpha,dash:context.dash||[]}}));'''
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    result = json.loads(completed.stdout)
    attributed_strokes = [
        call for call in result["attributed"] if call["op"] == "stroke"
    ]
    context_strokes = [
        call for call in result["context"] if call["op"] == "stroke"
    ]

    assert len(attributed_strokes) == 2
    assert attributed_strokes[0]["style"] == "#fbbf24"
    assert attributed_strokes[1]["style"] == "#60a5fa"
    assert attributed_strokes[1]["dash"] == [9, 5]
    assert len(context_strokes) == 1
    assert context_strokes[0]["style"] == "#60a5fa"
    assert result["attributedReset"] == {"alpha": 1, "dash": []}
    assert result["contextReset"] == {"alpha": 1, "dash": []}


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
    assert "function renderFilters" not in mount

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

    artifact["cohorts"]["hybrid_only"][1]["detail_status"] = "failed"
    no_eligible = _node_json(
        "(()=>{const view=buildRecoverySchema3ViewModel("
        + json.dumps(artifact)
        + ");return {defaultCaseId:view.defaultCaseId,rows:"
        "filterRecoverySchema3Cases(view,'gnn_explanation')};})()"
    )
    assert no_eligible == {"defaultCaseId": None, "rows": []}


def test_schema3_case_picker_uses_the_same_explained_case_state():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    mount = js[js.index("function mountRecoveryExplorerV3") :]
    assert "data.v3Change==='case'" in mount
    assert "state.caseId=control.value" in mount
    assert "loadSelected();return" in mount
    assert "Published GNN explanations" in mount


def test_schema3_manifest_rejects_noncanonical_case_ids():
    artifact = _schema3_ui_artifact()
    artifact["cohorts"]["hybrid_only"][0]["case_id"] = " h1 "
    artifact["selection"]["selected_ids"]["hybrid_only"] = [" h1 "]
    artifact["detail_index"] = {" h1 ": artifact["detail_index"]["h1"]}

    view = _node_json(
        "buildRecoverySchema3ViewModel(" + json.dumps(artifact) + ")"
    )

    assert view == {
        "available": False,
        "reason": "invalid-schema3-case-records",
    }


def test_schema3_explanation_filter_requires_a_published_index_entry():
    """Only available, indexed GNN rows become selectable explanations."""
    artifact = _schema3_ui_artifact()
    available = artifact["cohorts"]["hybrid_only"][0]
    failed_unindexed = dict(available)
    failed_unindexed.update(
        case_id="h-failed",
        person_id="person:h-failed",
        detail_status="failed",
        detail_kind="gnn_explanation",
        failure_reason="sidecar generation failed",
    )
    failed_indexed = dict(available)
    failed_indexed.update(
        case_id="h-failed-indexed",
        person_id="person:h-failed-indexed",
        detail_status="failed",
        detail_kind="gnn_explanation",
        failure_reason="sidecar generation failed after publication",
    )
    # Put the failed indexed row first so default selection cannot use raw order.
    artifact["cohorts"]["hybrid_only"] = [
        failed_indexed,
        available,
        failed_unindexed,
    ]
    artifact["selection"]["selected_ids"]["hybrid_only"] = [
        "h-failed-indexed",
        "h1",
        "h-failed",
    ]
    artifact["detail_index"] = {
        "h-failed-indexed": {"path": "cases/failed.json", "sha256": "c" * 64},
        "h1": artifact["detail_index"]["h1"],
    }
    artifact["summary"].update(hybrid_only_recovered=3, hybrid_total=3, net_gain=2)
    artifact["coverage"].update(
        hybrid_requested=3,
        hybrid_selected=3,
        hybrid_explained=2,
        hybrid_shortfall=1,
        shortfall=1,
        shortfall_reasons=["sidecar_generation_failed"],
    )

    result = _node_json(
        "(()=>{const view=buildRecoverySchema3ViewModel("
        + json.dumps(artifact)
        + ");return filterRecoverySchema3Cases(view,'gnn_explanation')"
        ".map(row=>row.caseId);})()"
    )

    assert result == ["h1"]
    view = _node_json(
        "buildRecoverySchema3ViewModel(" + json.dumps(artifact) + ")"
    )
    assert view["defaultCaseId"] == "h1"


def test_schema3_mount_has_no_legacy_schema_dispatch_or_helpers():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    css = UI.V9_RECOVERY_EXPLAINER_CSS
    mount = js.split("function mountV9RecoveryExplainer", 1)[1]
    assert "mountRecoveryExplorerV2" not in js
    assert "buildRecoveryManifestViewModel" not in js
    assert "recoveryV2Panel" not in js
    assert "data-v2-" not in js
    assert "schema_version==='2.0'" not in mount
    assert "schema_version==='1.0'" not in mount
    for dead_source in (
        "recoveryFormatJson",
        "recoveryPage",
        "recoveryClusterNodes",
        "v9-recovery-containment",
        "v9-recovery-workspace",
        "v9-recovery-rail",
        "v9-recovery-filter-grid",
        "v9-recovery-field",
        "v9-recovery-case-count",
        "v9-recovery-case-list",
        "v9-recovery-case-top",
        "v9-recovery-case-ranks",
        "v9-recovery-detail",
        "v9-recovery-progress",
    ):
        assert dead_source not in js + css


def test_schema3_mount_renders_explicit_unavailable_state_for_unsupported_artifact():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    assert "unsupported-or-missing-schema3-artifact" in js
    assert "Case evidence unavailable" in js


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
    assert [edge["importance"] for edge in neutral["edges"]] == [0]
    assert all(edge["emphasized"] for edge in neutral["edges"])
    assert [node["id"] for node in neutral["nodes"]] == ["p1", "p2"]
    assert [node["target"] for node in neutral["nodes"]] == [True, False]
    # Flow mode filters the canvas using each edge's own hop.
    assert [edge["emphasized"] for edge in staged["edges"]] == [True]
    assert staged["provenanceEdges"] == []


@pytest.mark.parametrize(
    ("stage_id", "expected_canvas_edges", "expected_canvas_nodes"),
    [
        ("first_hop", ["e1"], ["p1", "p2"]),
        ("second_hop", ["e1", "e2"], ["p1", "p2", "p3"]),
    ],
)
def test_structural_hop_stages_filter_canvas_but_keep_complete_tables(
    stage_id, expected_canvas_edges, expected_canvas_nodes
):
    control = _schema3_structural_control()

    result = _node_json(
        "buildStructuralDrawCommands(%s,{mode:'flow',stageId:%s,query:''})"
        % (json.dumps(control), json.dumps(stage_id))
    )

    assert [edge["id"] for edge in result["edges"]] == expected_canvas_edges
    assert [node["id"] for node in result["nodes"]] == expected_canvas_nodes
    assert [edge["id"] for edge in result["tableEdges"]] == ["e1", "e2"]
    assert [node["id"] for node in result["tableNodes"]] == [
        "p1",
        "p2",
        "p3",
    ]


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
    graph_index = mount.index("const graph=renderGraph(detail,detailView,record)")
    boundary_index = mount.index(
        "validateRecoveryEvidenceBoundary(\n      {evidence_boundary:detailView.evidenceBoundary}"
    )
    attribution_index = mount.index(
        "explanationRow.appendChild(renderHighestAttributionPanel(doc,detailView.explanation))"
    )
    narrative_index = mount.index(
        "renderNarrative(explanationRow,detailView.explanation)"
    )
    factors_index = mount.index("renderFactors(explanationRow,detailView.explanation)")
    assert boundary_index < graph_index < attribution_index < factors_index < narrative_index
    assert "renderHighestAttributionPanel(doc,detailView.explanation)" in hybrid_branch
    assert "renderNarrative(explanationRow,detailView.explanation)" in hybrid_branch
    assert "renderFactors(explanationRow,detailView.explanation)" in hybrid_branch
    assert "renderDisclosure(disclosures,'attribution'" not in mount
    assert "buildCommunityDrawCommands(detailView.explanation,options)" in mount
    assert "buildStructuralDrawCommands(detailView.control,options)" in mount


def test_schema3_gnn_explanation_shows_llm_narrative_and_attribution():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    mount = js.split("function mountRecoveryExplorerV3", 1)[1].split(
        "const recoveryMounts", 1
    )[0]

    assert "explanationRow.appendChild(renderHighestAttributionPanel(doc,detailView.explanation))" in mount
    assert "renderNarrative(explanationRow,detailView.explanation)" in mount
    assert "LLM explanation" in js
    assert "Validated local Gemma:" in js


def test_schema3_gnn_explanation_render_path_restores_llm_narrative_label():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    mount = js.split("function mountRecoveryExplorerV3", 1)[1].split(
        "const recoveryMounts", 1
    )[0]
    hybrid_branch = mount.split(
        "if(detailView.kind==='gnn_explanation'){", 1
    )[1].split("}else{", 1)[0]

    assert re.search(r"\brender[A-Za-z]*Narrative\(", hybrid_branch)
    assert "LLM explanation" in js


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
    fallback_branch = mount.split("const explanationRow=", 1)[1].split(
        "detail.appendChild(explanationRow)", 1
    )[0].split("}else{", 1)[1]
    assert (
        "Community membership is observable context, not an attribution claim."
        in fallback_branch
    )
    for renderer in (
        "renderNarrative",
        "renderFactors",
        "renderStabilityAndFaithfulness",
        "renderHighestAttributionPanel",
    ):
        assert renderer not in fallback_branch
    # The revised graph copy removes the stale duplicate mask sentence.
    assert "Mask values are unsigned evidence weights, not causal claims." not in mount


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
        "Caught before snapshot",
        "Model evidence weight",
        "Attributed node",
        "Sampled context:",
        "Strict-bound unavailable:",
        "commands.sampled",
        "v9-recovery-legend",
        "Graph legend",
        "canvas.setAttribute('aria-label'",
        "record.cohort==='baseline_only'",
        "Hybrid structural fallback ",
        "exceed the interactive rendering bound",
        "renderGraphOnly('data-v3-stage','v3Stage',data.v3Stage)",
        "renderGraphOnly('data-v3-zoom','v3Zoom',data.v3Zoom)",
        "bindRecoveryCanvas(",
    ):
        assert token in mount
    for token in (
        "Model evidence weight",
        "selectRecoveryEvidenceEdges",
        "recoveryEvidenceBounds",
        "recoveryDrawEvidenceLabels",
        "style.evidenceLineWidth",
        "relation.dash",
    ):
        assert token in js
    assert "v9-recovery-table" in UI.V9_RECOVERY_EXPLAINER_CSS
    assert "overflow-x: auto" in UI.V9_RECOVERY_EXPLAINER_CSS


def test_schema3_graph_copy_renders_explanation_legend_keys():
    rendered = _mount_schema3("h1")
    text = " | ".join(rendered["text"])

    assert "As-of community context + explanation evidence" in text
    assert "Muted context remains visible" in text
    assert "Target" in text
    assert "Caught before snapshot" in text
    assert "Co-travel" in text
    assert "Model evidence weight" in text
    assert "Attributed node" in text
    for legacy in ("Context relations", "Explanation evidence", "Weight range"):
        assert legacy not in text


def test_schema3_relationship_legend_names_visual_cues_for_known_and_other_links():
    artifact, files = _schema3_served_bundle()
    relation_rows = [
        ("e2", "RESIDENCE"),
        ("e3", "SHARED_PLATE"),
        ("e4", "MYSTERY_LINK"),
    ]

    def rewrite(url, reference, mutate):
        payload = json.loads(files[url])
        mutate(payload)
        body, digest = _sidecar(payload)
        files[url] = body
        reference["sha256"] = digest

    edge_catalog_ref = artifact["catalog_index"]["edges"]["chunks"][0]
    edge_catalog_url = artifact["sidecar_base"] + edge_catalog_ref["path"]
    def extend_catalog(payload):
        payload["records"].extend(
            {"record_id": edge_id, "record": {
                "edge_id": edge_id, "u": "p1", "v": "p2", "edge_type": relation,
            }} for edge_id, relation in relation_rows
        )
        payload["count"] = 4

    rewrite(edge_catalog_url, edge_catalog_ref, extend_catalog)
    edge_catalog_ref.update(count=4, last_id="e4")
    artifact["catalog_index"]["edges"].update(record_count=4)

    community_ref = artifact["community_sidecar_index"]["community:a"]
    community_url = artifact["sidecar_base"] + community_ref["path"]
    community = json.loads(files[community_url])
    edge_chunk_ref = community["edge_chunks"][0]
    edge_chunk_url = artifact["sidecar_base"] + edge_chunk_ref["path"]
    def extend_edges(payload):
        payload["edges"].extend(
            {"edge_id": edge_id, "catalog_id": edge_id}
            for edge_id, _ in relation_rows
        )
        payload["count"] = 4

    rewrite(edge_chunk_url, edge_chunk_ref, extend_edges)
    edge_chunk_ref.update(count=4)
    day_ref = community["day_view"]["edge_membership_chunks"][0]
    day_url = artifact["sidecar_base"] + day_ref["path"]
    def extend_day_edges(payload):
        payload["edge_memberships"].extend(
            {"edge_id": edge_id, "message_hop": 1, "source_row_ids": []}
            for edge_id, _ in relation_rows
        )
        payload["count"] = 4

    rewrite(day_url, day_ref, extend_day_edges)
    day_ref.update(count=4)
    community["edge_count"] = 4
    community["day_view"]["edge_count"] = 4
    body, digest = _sidecar(community)
    files[community_url] = body
    community_ref["sha256"] = digest

    rendered = _mount_schema3("h1", (artifact, files))
    legend_labels = [
        node["attrs"]["aria-label"]
        for node in rendered["nodes"]
        if node["className"] == "v9-recovery-legend-item"
    ]

    assert any(label.startswith("Co-travel: green solid line") for label in legend_labels)
    assert any(label.startswith("Residence: blue dashed line") for label in legend_labels)
    assert any(label.startswith("Shared plate: violet dotted line") for label in legend_labels)
    assert any(label.startswith("Mystery link: gray long-dash line") for label in legend_labels)


def test_schema3_graph_groups_evidence_stage_relationship_and_navigation_controls():
    rendered = _mount_schema3("h1")
    text = " | ".join(rendered["text"])
    labels = rendered["labels"]

    for visible in (
        "Evidence first",
        "Full community",
        "First hop",
        "Second hop",
        "Component pool",
        "Rank fusion",
        "All types",
        "Co-travel",
        "Key labels",
        "Reset view",
        "Model evidence weight",
    ):
        assert visible in text
    for accessible in (
        "Graph view",
        "Explanation stage",
        "Relationship type",
        "Node labels",
        "Graph navigation",
    ):
        assert accessible in labels
    for stage in ("first hop", "second hop", "component pool", "rank fusion"):
        assert "Show "+stage+" explanation stage" in labels
    assert (
        "Gold underlay shows model evidence weight. Inner color and pattern show the observable relationship type."
        in text
    )
    assert "Mask values are unsigned evidence weights, not causal claims." not in text
    assert "Flow" not in text
    assert "Labels: auto" not in text
    assert "Fit" not in text


def test_v9_results_injection_contains_evidence_first_graph_language_once():
    from Documents.Data.scripts import v9_recovery_explainer_ui as recovery_ui

    recovery = recovery_ui.V9_RECOVERY_EXPLAINER_JS
    assert recovery.count("Evidence first") == 1
    assert recovery.count("Model evidence weight") >= 1
    assert "data-v3-relation" in recovery


def test_schema3_css_polish_is_scoped_and_reduced_motion_safe():
    css = UI.V9_RECOVERY_EXPLAINER_CSS

    assert (
        ".v9-recovery-legend-swatch.is-evidence { height:9px; background:#fbbf24; box-shadow:none; opacity:.72; }"
        in css
    )
    assert ".v9-recovery-legend-swatch.is-weight" not in css
    assert ".v9-recovery-legend-swatch.is-context" not in css

    for token in (
        ".v9-recovery-v3",
        "linear-gradient",
        ".v9-recovery-legend-swatch",
        ".v9-recovery-sampled",
        "height: clamp(460px, 58vh, 640px)",
        "overflow-x: auto",
        ":focus:not(:focus-visible)",
        "prefers-reduced-motion: reduce",
        "#tab-v9Results .v9-recovery-skeleton { animation: none; }",
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
    assert "renderError(detail,state.error)" in mount
    assert "Partial coverage: " not in mount
    assert "v9-recovery-warning" not in UI.V9_RECOVERY_EXPLAINER_CSS
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


def test_schema3_overlay_ignores_neutral_structural_rows():
    community, overlay_nodes, overlay_edges = _schema3_overlay_fixture()
    overlay_nodes.append({"node_id": "p2", "source": "community"})
    overlay_edges.append({
        "edge_id": "e2",
        "u": "p2",
        "v": "p3",
        "edge_type": "RESIDENCE",
        "relation": "RESIDENCE",
        "source": "community",
    })
    overlay_nodes.append({"node_id": "outside-node", "source": "provenance"})
    overlay_edges.append({
        "edge_id": "outside-edge",
        "u": "outside-node",
        "v": "outside-peer",
        "edge_type": "COTRAVEL",
        "source": "provenance",
    })

    result = _node_json(
        "mergeRecoverySchema3Overlay(%s,%s,%s)"
        % (json.dumps(community), json.dumps(overlay_nodes), json.dumps(overlay_edges))
    )

    assert result["available"] is True
    node = next(row for row in result["nodes"] if row["node_id"] == "p2")
    edge = next(row for row in result["edges"] if row["edge_id"] == "e2")
    assert node["x"] == 0.3
    assert node["importance"] == 0
    assert node["attributed"] is False
    assert node["rank"] is None
    assert edge["u"] == "p2"
    assert edge["v"] == "p3"
    assert edge["relation"] == "RESIDENCE"
    assert edge["importance"] == 0
    assert edge["attributed"] is False
    assert edge["rank"] is None


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
        (lambda nodes, edges: nodes[0].pop("rank"),
         "invalid-overlay-identity"),
        (lambda nodes, edges: nodes[0].pop("explainer_median"),
         "invalid-overlay-identity"),
        (lambda nodes, edges: edges[0].pop("explainer_median"),
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
    return body, hashlib.sha256(body.encode()).hexdigest()


def _replace_served_detail(artifact, files, mutate):
    reference = artifact["detail_index"]["h1"]
    url = artifact["sidecar_base"] + reference["path"]
    payload = json.loads(files[url])
    mutate(payload)
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    files[url] = body
    reference["sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()


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
const FOCUS_CALLS=[];
const SCROLL_CALLS=[];
function datasetKeyFor(attribute){
  return String(attribute).replace(/^data-/,'')
    .replace(/-([a-z])/g,(whole,letter)=>letter.toUpperCase());
}
function parseAttributeSelector(selector){
  const match=/^\[([^\]=]+)(?:="([^"]*)")?\]$/.exec(String(selector).trim());
  if(!match)return null;
  return {key:datasetKeyFor(match[1]),value:match[2]};
}
function elementMatches(element,selector){
  return String(selector).split(',').some(part=>{
    const parsed=parseAttributeSelector(part);
    if(!parsed||!element.dataset)return false;
    const actual=element.dataset[parsed.key];
    if(actual===undefined)return false;
    return parsed.value===undefined||actual===parsed.value;
  });
}
function fakeElement(tag){
  const element={
    tag,children:[],textContent:'',className:'',attrs:{},style:{},id:'',
    dataset:{},type:'',value:'',tabIndex:0,listeners:{},rectTop:0,
    appendChild(child){child.parentNode=this;this.children.push(child);return child;},
    setAttribute(name,value){this.attrs[name]=String(value);},
    getContext(){return null;},
    focus(options){FOCUS_CALLS.push({tag:this.tag,dataset:{...this.dataset},
      options:options===undefined?null:options});},
    getBoundingClientRect(){return {top:this.rectTop,left:0,width:0,height:0};},
    replaceChildren(...nodes){
      for(const node of nodes)node.parentNode=this;
      this.children=nodes.slice();
    },
    querySelectorAll(selector){
      return allNodes(this).filter(node=>node!==this
        &&elementMatches(node,selector));
    },
    querySelector(selector){return this.querySelectorAll(selector)[0]||null;},
    closest(selector){
      let current=this;
      while(current){
        if(elementMatches(current,selector))return current;
        current=current.parentNode;
      }
      return null;
    },
    addEventListener(type,handler){
      (this.listeners[type]=this.listeners[type]||[]).push(handler);
    },
    removeEventListener(type,handler){
      const list=this.listeners[type]||[];
      const index=list.indexOf(handler);
      if(index>=0)list.splice(index,1);
    },
    classList:{add(){},remove(){}},
    contains(){return true;}
  };
  return element;
}
const doc={
  createElement:fakeElement,
  createDocumentFragment(){return fakeElement('fragment');},
  defaultView:{scrollBy(x,y){SCROLL_CALLS.push({x,y});}}
};
function makeRoot(){const root=fakeElement('div');root.ownerDocument=doc;return root;}
function findByDataset(root,key,value){
  return allNodes(root).find(node=>node.dataset&&node.dataset[key]===value)||null;
}
function fireEvent(root,type,target){
  for(const handler of (root.listeners[type]||[]).slice())handler({target});
}
function allNodes(node){
  return [node,...node.children.flatMap(allNodes)];
}
function visibleText(root){
  return allNodes(root).map(node=>node.textContent).filter(Boolean);
}
function ariaLabels(root){
  return allNodes(root).map(node=>node.attrs['aria-label']).filter(Boolean);
}
function snapshotRoot(root){
  function ancestorClasses(node){
    const classes=[];let parent=node.parentNode;
    while(parent){classes.push(parent.className);parent=parent.parentNode;}
    return classes;
  }
  const nodes=allNodes(root).map(node=>({
    tag:node.tag,
    className:node.className,
    id:node.id,
    parentClass:node.parentNode&&node.parentNode.className,
    ancestorClasses:ancestorClasses(node),
    attrs:node.attrs,
    dataset:node.dataset,
    open:node.open===true
  }));
  return {
    text:visibleText(root),
    labels:ariaLabels(root),
    nodes,
    tables:nodes.filter(node=>node.tag==='table').length,
    rows:nodes.filter(node=>node.tag==='tr').length
  };
}
"""


def _mount_schema3_interaction(interaction, bundle=None):
    """Mount the explorer, run `interaction` JS once the case is loaded, and
    return whatever that snippet assigns to the global RESULT object."""
    artifact, files = bundle or _schema3_served_bundle()
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
        + "\nconst RESULT={};"
        + "\nconst deadline=Date.now()+5000;"
        + "function pollReady(){"
        + "const loading=allNodes(root).some(node=>node.className==='v9-recovery-loading');"
        + "const panel=allNodes(root).find(node=>"
        + "node.className==='v9-recovery-graph-panel');"
        + "if(!loading&&panel){"
        + interaction
        + "process.stdout.write(JSON.stringify(RESULT));cleanup();return;}"
        + "if(Date.now()>=deadline)throw new Error('Timed out waiting for graph panel');"
        + "setTimeout(pollReady,10);}\npollReady();"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def test_stage_control_rebuilds_only_the_graph_panel():
    """A stage click must not tear down the header, case rail, attribution, and
    tables: that full rebuild is what made every control click cost a second
    and what threw the reader's scroll position back up the page."""
    result = _mount_schema3_interaction(
        "const before=allNodes(root);"
        "const beforePanel=before.find(n=>n.className==='v9-recovery-graph-panel');"
        "const beforeCase=before.find(n=>n.className==='v9-recovery-case');"
        "const beforeAttribution=before.find(n=>n.className==='v9-attribution-panel');"
        "const control=findByDataset(root,'v3Stage','second_hop');"
        "fireEvent(root,'click',control);"
        "const after=allNodes(root);"
        "const afterPanel=after.find(n=>n.className==='v9-recovery-graph-panel');"
        "const afterCase=after.find(n=>n.className==='v9-recovery-case');"
        "const afterAttribution=after.find(n=>n.className==='v9-attribution-panel');"
        "RESULT.panelReplaced=beforePanel!==afterPanel&&Boolean(afterPanel);"
        "RESULT.panelAttached=after.includes(afterPanel);"
        "RESULT.caseKept=Boolean(beforeCase)&&beforeCase===afterCase;"
        "RESULT.attributionKept=Boolean(beforeAttribution)"
        "&&beforeAttribution===afterAttribution;"
        "RESULT.stagePressed=(findByDataset(root,'v3Stage','second_hop')||{})"
        ".attrs['aria-pressed'];"
    )

    assert result["panelReplaced"] is True
    assert result["panelAttached"] is True
    assert result["caseKept"] is True
    assert result["attributionKept"] is True
    assert result["stagePressed"] == "true"


def test_control_focus_restore_never_scrolls_the_page():
    """focus() scrolls its target into view by default, which is what yanked
    the page back to the top of the explanation on every filter click."""
    result = _mount_schema3_interaction(
        "fireEvent(root,'click',findByDataset(root,'v3Stage','second_hop'));"
        "fireEvent(root,'click',findByDataset(root,'v3Relation','all'));"
        "RESULT.focusCalls=FOCUS_CALLS.map(call=>call.options);"
        "RESULT.scrollCalls=SCROLL_CALLS;"
    )

    assert result["focusCalls"], "expected the control to regain focus"
    assert all(call == {"preventScroll": True} for call in result["focusCalls"])
    assert result["scrollCalls"] == []


def test_zoom_control_repaints_the_canvas_without_touching_the_dom():
    result = _mount_schema3_interaction(
        "const beforePanel=allNodes(root).find(n=>"
        "n.className==='v9-recovery-graph-panel');"
        "fireEvent(root,'click',findByDataset(root,'v3Zoom','in'));"
        "const afterPanel=allNodes(root).find(n=>"
        "n.className==='v9-recovery-graph-panel');"
        "RESULT.panelKept=beforePanel===afterPanel;"
    )

    # No 2d context in the fake DOM, so the binding cannot expose a redraw and
    # the handler must fall back to rebuilding the panel rather than doing
    # nothing at all.
    assert result["panelKept"] is False


def _mount_schema3(case_id, bundle=None, fetch_latency_ms=0, expected_text=None):
    artifact, files = bundle or _schema3_served_bundle()
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nconst FILES="
        + json.dumps(files)
        + ";\nglobalThis.fetch=async function(url){\n"
        "  globalThis.FETCHED.push(url);\n"
        "  const body=FILES[url];\n"
        "  if(LATENCY_MS)await new Promise(resolve=>setTimeout(resolve,LATENCY_MS));\n"
        "  if(body===undefined)return {ok:false,status:404};\n"
        "  return {ok:true,status:200,\n"
        "    arrayBuffer:async()=>new TextEncoder().encode(body).buffer};\n"
        "};\n"
        + _FAKE_DOM
        + "\nconst LATENCY_MS="
        + str(fetch_latency_ms)
        + ";const EXPECTED_TEXT="
        + json.dumps(expected_text)
        + ";const FETCHED=[];globalThis.FETCHED=FETCHED;"
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
        + "\nconst initial=snapshotRoot(root);"
        + "\nconst deadline=Date.now()+5000;"
        + "function emitSnapshot(){return {...snapshotRoot(root),initial,fetches:FETCHED,details:DETAILS};}"
        + "function pollReady(){"
        + "const text=visibleText(root).join(' | ');"
        + "const loading=allNodes(root).some(node=>node.className==='v9-recovery-loading');"
        + "const ready=!loading"
        + "&&(!EXPECTED_TEXT||text.includes(EXPECTED_TEXT));"
        + "if(ready){process.stdout.write(JSON.stringify(emitSnapshot()));cleanup();return;}"
        + "if(Date.now()>=deadline)throw new Error('Timed out waiting for selected evidence: '+text);"
        + "setTimeout(pollReady,10);}\npollReady();"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def test_schema3_invalid_narrative_shows_highest_attribution_directly():
    artifact, files = _schema3_served_bundle()

    def mutate(payload):
        payload["explanation"]["llm_narrative"] = {}
        payload["explanation"]["attributions"] = {
            "top_local_nodes": [{"rank": 1, "node_id": "p2", "explainer_median": 0.9}],
            "top_edges": [{"rank": 1, "edge_id": "e1", "u": "p1", "v": "p2",
                            "edge_type": "COTRAVEL", "explainer_median": 0.8}],
        }

    _replace_served_detail(artifact, files, mutate)
    rendered = _mount_schema3("h1", (artifact, files))
    text = " | ".join(rendered["text"])
    disclosures = [node["dataset"].get("v3Disclosure") for node in rendered["nodes"]
                   if node["tag"] == "details"]
    assert "Grounded narrative" not in text
    assert "Validated narrative unavailable. Showing ranked model evidence" not in text
    assert text.count("Highest-attribution evidence") == 1
    assert "COTRAVEL" in text
    assert "attribution" not in disclosures


def test_schema3_unavailable_narrative_still_shows_attribution_panel():
    artifact, files = _schema3_served_bundle()

    def mutate(payload):
        payload["explanation"]["llm_narrative"] = {"summary": ""}
        payload["explanation"]["attributions"] = {
            "top_local_nodes": [],
            "top_edges": [],
        }

    _replace_served_detail(artifact, files, mutate)
    rendered = _mount_schema3("h1", (artifact, files))
    text = " | ".join(rendered["text"])
    disclosures = [node["dataset"].get("v3Disclosure") for node in rendered["nodes"]
                   if node["tag"] == "details"]

    assert "Grounded narrative" not in text
    assert "Validated narrative and ranked model evidence are unavailable." not in text
    assert "Showing ranked model evidence" not in text
    assert text.count("Highest-attribution evidence") == 1
    assert "Attribution ranking unavailable in this artifact." in text
    assert "attribution" not in disclosures


def test_schema3_valid_narrative_is_rendered_with_attribution():
    artifact, files = _schema3_served_bundle()

    def mutate(payload):
        payload["explanation"]["llm_narrative"] = {
            "validated": True, "prompt_version": "v1", "source": "deterministic_template",
            "model": None, "summary": "The published ranks identify this case.",
            "summary_source_refs": ["ranks.seed0_hybrid"], "claims": [],
        }

    _replace_served_detail(artifact, files, mutate)
    rendered = _mount_schema3("h1", (artifact, files))
    text = " | ".join(rendered["text"])
    disclosures = [node["dataset"].get("v3Disclosure") for node in rendered["nodes"]
                   if node["tag"] == "details"]
    assert "The published ranks identify this case." in text
    assert "Evidence explanation" in text
    assert text.count("Highest-attribution evidence") == 1
    assert "attribution" not in disclosures


def test_schema3_published_llm_v4_narrative_is_visible_in_selected_case():
    artifact, files = _schema3_served_bundle()

    def mutate(payload):
        payload["explanation"]["llm_narrative"] = {
            "validated": True,
            "prompt_version": "v4",
            "source": "llm",
            "model": "gemma4:12b",
            "summary": "The local model identified a high-ranked hybrid case.",
            "summary_source_refs": ["ranks.seed0_hybrid"],
            "claims": [
                {
                    "text": "The published Hybrid rank is supported by the recorded evidence.",
                    "source_refs": ["ranks.seed0_hybrid"],
                }
            ],
        }

    _replace_served_detail(artifact, files, mutate)
    rendered = _mount_schema3("h1", (artifact, files))
    text = " | ".join(rendered["text"])

    assert "LLM explanation" in text
    assert "Validated local Gemma: gemma4:12b" in text
    assert "The local model identified a high-ranked hybrid case." in text
    assert "The published Hybrid rank is supported by the recorded evidence." in text


def test_schema3_mount_renders_hybrid_technical_evidence_end_to_end():
    rendered = _mount_schema3("h1")
    text = " | ".join(rendered["text"])

    assert "Hybrid technical detail" in text
    assert "Strict as-of evidence boundary" not in text
    assert "Strict as-of status:" not in text
    assert "Event event:h1 / scoring day 2025-01-02." in text
    assert "Baseline score: 0.2" in text
    assert "Baseline percentile: 0.2" in text
    assert "Seed-0 GNN probability: 0.8" in text
    assert "Hybrid percentile-fusion score: 0.56" in text
    assert "Key counterfactual factors" in text
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


def test_schema3_mount_accepts_published_v1_case_sidecars():
    artifact, files = _schema3_served_bundle()
    reference = artifact["detail_index"]["h1"]
    url = artifact["sidecar_base"] + reference["path"]
    payload = json.loads(files[url])
    payload["schema_version"] = "1.0"
    body, digest = _sidecar(payload)
    files[url] = body
    reference["sha256"] = digest

    rendered = _mount_schema3(
        "h1", (artifact, files)
    )
    text = " | ".join(rendered["text"])

    assert "Hybrid technical detail" in text
    assert "Community data table" in text


def test_schema3_header_validates_nested_normalized_evidence_boundary():
    artifact, files = _schema3_served_bundle()
    reference = artifact["detail_index"]["h1"]
    url = artifact["sidecar_base"] + reference["path"]
    payload = json.loads(files[url])
    payload["detail"] = {
        "case_id": payload["case"]["case_id"],
        "explanation": payload.pop("explanation"),
    }
    body, digest = _sidecar(payload)
    files[url] = body
    reference["sha256"] = digest

    rendered = _mount_schema3("h1", (artifact, files))
    text = " | ".join(rendered["text"])

    assert "Strict as-of evidence boundary" not in text
    assert "Strict as-of status:" not in text


def test_schema3_header_rejects_semantically_wrong_nested_evidence_boundary():
    artifact, files = _schema3_served_bundle()
    reference = artifact["detail_index"]["h1"]
    url = artifact["sidecar_base"] + reference["path"]
    payload = json.loads(files[url])
    explanation = payload.pop("explanation")
    explanation["evidence_boundary"]["snapshot"] = "2025-01-03T00:00:00+00:00"
    payload["detail"] = {
        "case_id": payload["case"]["case_id"],
        "explanation": explanation,
    }
    body, digest = _sidecar(payload)
    files[url] = body
    reference["sha256"] = digest

    rendered = _mount_schema3("h1", (artifact, files))
    text = " | ".join(rendered["text"])

    assert "Strict as-of evidence boundary" not in text
    assert "Strict as-of status:" not in text


def test_schema3_mount_waits_for_slow_selected_evidence():
    rendered = _mount_schema3(
        "h1", fetch_latency_ms=300
    )
    text = " | ".join(rendered["text"])

    assert "Hybrid technical detail" in text
    assert "Strict as-of evidence boundary" not in text
    assert "Strict as-of status:" not in text


def test_schema3_mount_shows_loading_skeleton_snapshot_before_slow_evidence_resolves():
    rendered = _mount_schema3("h1", fetch_latency_ms=50)
    initial = rendered["initial"]
    classes = {node["className"] for node in initial["nodes"]}
    assert "v9-recovery-loading" in classes
    assert "v9-recovery-skeleton is-graph" in classes
    assert "v9-recovery-skeleton is-copy" in classes
    assert "v9-recovery-header" in classes
    assert "v9-recovery-ranks" in classes
    assert "v9-recovery-v3-list" in classes
    assert sum(node["attrs"].get("aria-busy") == "true" for node in initial["nodes"]) == 1
    assert sum(node["attrs"].get("role") == "status" for node in initial["nodes"]) == 1
    assert "Loading selected evidence" in initial["text"]
    assert "Loading selected evidence..." not in initial["text"]


def test_schema3_mount_composes_empty_published_explanation_state_with_cohort_context():
    artifact, files = _schema3_served_bundle()
    artifact["detail_index"] = {}
    artifact["cohorts"]["hybrid_only"][0]["detail_status"] = "failed"
    artifact["coverage"].update(
        hybrid_explained=0,
        hybrid_shortfall=1,
        shortfall=1,
        shortfall_reasons=["detail_failed"],
    )
    rendered = _mount_schema3("h1", (artifact, files))
    text = " | ".join(rendered["text"])
    classes = {node["className"] for node in rendered["nodes"]}
    titles = [node for node in rendered["nodes"] if node["id"] == "v9-recovery-title"]
    disclosures = [node for node in rendered["nodes"] if node["tag"] == "details"]
    summaries = [node for node in rendered["nodes"] if node["className"] == "v9-recovery-summary"]
    stats = [node for node in rendered["nodes"] if node["className"] == "v9-recovery-stat"]
    assert "v9-recovery-v3-list" not in classes
    assert "v9-recovery-v3-detail" not in classes
    assert "v9-recovery-empty-state" in classes
    assert len(titles) == 1 and titles[0]["tag"] == "h3"
    assert len(disclosures) == 1 and disclosures[0]["open"] is False
    assert disclosures[0]["dataset"].get("v3Disclosure") == "cohort"
    assert len(summaries) == 1
    assert len(stats) == 6
    assert "No published GNN explanations are available in this artifact." in text
    assert "Recovery cohort context" in text
    assert not any(label in text for label in (
        "Baseline score", "Baseline rank", "Seed-0 GNN rank", "Seed-0 Hybrid rank"
    ))


def test_schema3_mount_surfaces_retry_error_without_graph_heading_when_selected_sidecar_is_missing():
    artifact, files = _schema3_served_bundle()
    files.pop(artifact["sidecar_base"] + artifact["detail_index"]["h1"]["path"])
    rendered = _mount_schema3("h1", (artifact, files))
    text = " | ".join(rendered["text"])
    classes = {node["className"] for node in rendered["nodes"]}
    alerts = [node for node in rendered["nodes"] if node["attrs"].get("role") == "alert"]
    retries = [node for node in rendered["nodes"] if node["dataset"].get("v3Retry") == "true"]
    detail_nodes = [node for node in rendered["nodes"] if node["className"] == "v9-recovery-v3-detail"]
    assert "v9-recovery-v3-list" in classes
    assert "v9-recovery-error" in classes
    assert len(alerts) == 1
    assert len(retries) == 1 and retries[0]["attrs"].get("aria-label") == "Retry selected GNN evidence"
    assert len(detail_nodes) == 1 and detail_nodes[0]["attrs"].get("aria-busy") == "false"
    assert "Sidecars require local HTTP." in text
    assert text.count("Retry evidence") == 1
    assert "As-of community context + explanation evidence" not in text


def test_schema3_retry_is_handled_by_the_existing_delegated_click_listener():
    mount = UI.V9_RECOVERY_EXPLAINER_JS.split(
        "function mountRecoveryExplorerV3", 1
    )[1].split("const recoveryMounts", 1)[0]
    assert mount.count("root.addEventListener('click'") == 1
    assert "[data-v3-retry]" in mount
    assert "if(data.v3Retry){loadSelected();return;}" in mount


def test_schema3_mount_uses_graph_first_case_workspace_and_three_decimals():
    artifact, files = _schema3_served_bundle()
    record = artifact["cohorts"]["hybrid_only"][0]
    record["baseline_raw"] = 0.8427
    record["seed0_gnn_probability"] = 0.3184
    record["seed0_hybrid_score"] = 0.6719
    rendered = _mount_schema3("h1", (artifact, files))
    text = " | ".join(rendered["text"])

    assert "1 published GNN explanation" in text
    assert "Why case p1 surfaced" in text
    assert "Baseline rank" in text
    assert "Seed-0 GNN rank" not in text
    assert "Seed-0 Hybrid rank" in text
    assert "12 places higher than Baseline" in text
    assert text.index("Why case p1 surfaced") < text.index("Baseline rank")
    assert text.index("Baseline rank") < text.index(
        "As-of community context + explanation evidence"
    )
    assert text.index("As-of community context + explanation evidence") < text.index(
        "Highest-attribution evidence"
    )
    assert "0.843" in text
    assert "0.318" in text
    assert "0.672" in text
    assert "0.8427" not in text
    assert "0.3184" not in text
    assert "0.6719" not in text


def test_schema3_mount_puts_graph_before_open_prose_and_closed_technical_evidence():
    rendered = _mount_schema3("h1")
    text = " | ".join(rendered["text"])

    assert text.index("As-of community context + explanation evidence") < text.index(
        "Highest-attribution evidence"
    )
    assert text.index("Highest-attribution evidence") < text.index(
        "Restart stability and removal faithfulness"
    )
    disclosures = [
        node
        for node in rendered["nodes"]
        if node["tag"] == "details"
    ]
    assert [node["dataset"].get("v3Disclosure") for node in disclosures] == [
        "stability",
        "tables",
        "cohort",
    ]
    assert all(node["open"] is False for node in disclosures)


def test_schema3_disclosure_state_is_preserved_on_render_and_reset_on_case_load():
    js = UI.V9_RECOVERY_EXPLAINER_JS
    mount = js.split("function mountRecoveryExplorerV3", 1)[1].split(
        "const recoveryMounts", 1
    )[0]

    assert "openDisclosures:new Set()" in mount
    assert "state.openDisclosures.add" in mount
    assert "state.openDisclosures.delete" in mount
    assert "state.openDisclosures.clear()" in mount
    assert "root.addEventListener('toggle',onV3Toggle,true)" in mount
    assert "root.removeEventListener('toggle',onV3Toggle,true)" in mount


def test_schema3_graph_command_failure_preserves_record_status_reason():
    artifact, files = _schema3_served_bundle()
    artifact["cohorts"]["hybrid_only"][0]["failure_reason"] = (
        "forced graph command failure"
    )
    script = (
        UI.V9_RECOVERY_EXPLAINER_JS
        + "\nconst FILES="
        + json.dumps(files)
        + ";globalThis.fetch=async function(url){const body=FILES[url];"
        "if(body===undefined)return {ok:false,status:404};"
        "return {ok:true,status:200,arrayBuffer:async()=>"
        "new TextEncoder().encode(body).buffer};};"
        + _FAKE_DOM
        + "\nbuildCommunityDrawCommands=function(){"
        "return {available:false,reason:'forced-graph-failure'};};"
        + "\nconst root=makeRoot();"
        + "const cleanup=mountRecoveryExplorerV3(root,"
        + json.dumps(artifact)
        + ",{});"
        + "\nfunction all(node){return [node,...node.children.flatMap(all)];}"
        + "function poll(){const text=all(root).map(node=>node.textContent).filter(Boolean).join(' | ');"
        + "if(text.includes('Strict-bound unavailable: complete community unavailable')){"
        + "process.stdout.write(JSON.stringify(text));cleanup();return;}"
        + "setTimeout(poll,10);}poll();"
    )
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )
    text = json.loads(completed.stdout)

    assert "Recorded reason: forced graph command failure" in text


def test_schema3_cohort_context_is_rendered_once_inside_cohort_disclosure():
    rendered = _mount_schema3("h1")
    summaries = [
        node for node in rendered["nodes"] if node["className"] == "v9-recovery-summary"
    ]

    assert len(summaries) == 1
    assert "v9-recovery-disclosure-body" in summaries[0]["ancestorClasses"]
    assert any(
        node["tag"] == "details"
        and node["dataset"].get("v3Disclosure") == "cohort"
        for node in rendered["nodes"]
    )


def test_schema3_mount_supplies_the_v9_results_accessible_heading():
    rendered = _mount_schema3("h1")
    titles = [node for node in rendered["nodes"] if node["id"] == "v9-recovery-title"]
    assert len(titles) == 1
    assert titles[0]["tag"] == "h3"


def test_schema3_mount_renders_published_case_navigation_without_status_strip():
    rendered = _mount_schema3("h1")
    text = " | ".join(rendered["text"])
    classes = {node["className"] for node in rendered["nodes"]}
    assert "v9-recovery-v3-list" in classes
    assert "v9-recovery-v3-picker" in classes
    assert "Showing GNN explanations only" not in text
    assert "+12 places vs baseline" not in text
    assert "Hybrid rank 8" in text
    assert "12 places higher than Baseline" in text


def test_schema3_picker_is_direct_child_of_graph_workspace_grid():
    rendered = _mount_schema3("h1")
    picker = next(node for node in rendered["nodes"] if node["className"] == "v9-recovery-v3-picker")
    assert picker["parentClass"] == "v9-recovery-v3-grid"


def test_schema3_readability_system_uses_clear_zones_and_touch_targets():
    css = UI.V9_RECOVERY_EXPLAINER_CSS
    for token in (
        "font-family: Outfit",
        "font-family: 'JetBrains Mono'",
        ".v9-recovery-rank-delta",
        ".v9-recovery-rank.is-primary",
        "min-height: 44px",
        "grid-template-columns: 1fr",
    ):
        assert token in css




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

    assert "No published GNN explanations are available in this artifact." in text
    assert "Recovery cohort context" in text
    assert "v9-recovery-v3-list" not in {
        node["className"] for node in rendered["nodes"]
    }
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

    assert "No published GNN explanations are available in this artifact." in text
    assert "Recovery cohort context" in text
    assert "v9-recovery-v3-list" not in {
        node["className"] for node in rendered["nodes"]
    }
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
    assert "renderDisclosure(disclosures,'stability'" in mount
    assert "renderStabilityAndFaithfulness(body,detailView.explanation)" in mount
    assert "renderStabilityAndFaithfulness(left,detailView.explanation)" not in mount
