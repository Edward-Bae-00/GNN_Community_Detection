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
                "community": {
                    "complete": True,
                    "nodes": [
                        {"node_id": "p2", "x": 0.8, "y": 0.5},
                        {"node_id": "p1", "x": 0.5, "y": 0.5},
                    ],
                    "edges": [
                        {"edge_id": "edge-1", "u": "p1", "v": "p2"},
                    ],
                    "provenance_expansions": [],
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
                "community": {
                    "complete": True,
                    "nodes": [{"node_id": "p2"}],
                    "edges": [],
                    "provenance_expansions": [],
                },
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
