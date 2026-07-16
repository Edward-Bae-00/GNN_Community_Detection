import json
import os
import subprocess

import pytest

from gnn.explanation_narrative import (
    MODEL_TAG,
    PROMPT_VERSION,
    build_fact_packet,
    build_prompt,
    generate_narrative,
    render_template,
    validate_candidate,
)


class FakeCompleted:
    def __init__(self, stdout, returncode=0, stderr=""):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class FakeRunner:
    def __init__(self, *, list_stdout, run_stdout, list_returncode=0, run_returncode=0):
        self.list_stdout = list_stdout
        self.run_stdout = run_stdout
        self.list_returncode = list_returncode
        self.run_returncode = run_returncode
        self.calls = []

    @property
    def commands(self):
        return [command for command, _kwargs in self.calls]

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if command[1] == "list":
            return FakeCompleted(self.list_stdout, self.list_returncode)
        return FakeCompleted(self.run_stdout, self.run_returncode)


class FailingRunner:
    def __call__(self, command, **kwargs):
        raise FileNotFoundError("ollama unavailable")


class TimeoutRunner(FakeRunner):
    def __call__(self, command, **kwargs):
        if command[1] == "run":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return super().__call__(command, **kwargs)


def _fact_packet(*, factors=None):
    if factors is None:
        factors = {
            "factor-1": {
                "label": "COTRAVEL with P-100",
                "kind": "pair_relation",
                "counterfactual": {
                    "original_hybrid_rank": 7,
                    "ablated_hybrid_rank": 43,
                    "hybrid_rank_delta": 36,
                },
                "restart": {"selection_frequency": 1.0, "iqr": 0.1},
                "stability": "stable",
            }
        }
    return {
        "scope": {"observability_seed": 0, "gnn_arm": "sage"},
        "snapshot": "2025-01-02T00:00:00Z",
        "ranks": {"baseline": 18, "seed0_gnn": 4, "seed0_hybrid": 7},
        "factors_by_id": factors,
        "visible_paths": [
            {
                "edge_id": "edge-1",
                "relation": "COTRAVEL",
                "u": "P-100",
                "v": "P-200",
                "explainer_median": 0.8,
            }
        ],
        "caveats": [
            "This is seed-0 observability, not the three-seed headline result.",
            "GNNExplainer masks are unsigned; direction comes from counterfactual rank effects.",
            "The evidence is associative and does not establish causation.",
        ],
    }


def _valid_candidate():
    return {
        "summary": {
            "text": "In seed 0, the recorded Hybrid rank was 7.",
            "source_refs": ["scope.observability_seed", "ranks.seed0_hybrid"],
        },
        "claims": [
            {
                "text": "Removing COTRAVEL with P-100 moved Hybrid rank from 7 to 43.",
                "source_refs": [
                    "factors_by_id.factor-1.label",
                    "factors_by_id.factor-1.counterfactual.original_hybrid_rank",
                    "factors_by_id.factor-1.counterfactual.ablated_hybrid_rank",
                ],
            }
        ],
    }


def _explanation():
    return {
        "scoring_day": "2025-01-02T00:00:00Z",
        "decision_trace": {
            "baseline_rank": 18,
            "seed0_gnn_rank": 4,
            "seed0_hybrid_rank": 7,
        },
        "factors": [
            {
                "factor_id": "factor-1",
                "label": "COTRAVEL with P-100",
                "kind": "pair_relation",
                "counterfactual": {
                    "original_hybrid_rank": 7,
                    "ablated_hybrid_rank": 43,
                    "hybrid_rank_delta": 36,
                },
                "restart": {"selection_frequency": 1.0, "iqr": 0.1},
                "stability": "stable",
                "ignored_extra": "not approved",
            }
        ],
        "community": {
            "edges": [
                {
                    "edge_id": "edge-1",
                    "edge_type": "COTRAVEL",
                    "u": "P-100",
                    "v": "P-200",
                    "explainer_median": 0.8,
                    "availability_time": "2024-12-01T00:00:00Z",
                }
            ]
        },
        "hidden": True,
    }


def test_build_fact_packet_is_allowlisted_and_json_safe():
    packet = build_fact_packet(_explanation())

    assert set(packet) == {
        "scope",
        "snapshot",
        "ranks",
        "factors_by_id",
        "visible_paths",
        "caveats",
    }
    assert packet["scope"] == {"observability_seed": 0, "gnn_arm": "sage"}
    assert packet["ranks"] == {"baseline": 18, "seed0_gnn": 4, "seed0_hybrid": 7}
    assert set(packet["factors_by_id"]["factor-1"]) == {
        "label",
        "kind",
        "counterfactual",
        "restart",
        "stability",
    }
    assert set(packet["visible_paths"][0]) == {
        "edge_id",
        "relation",
        "u",
        "v",
        "explainer_median",
    }
    assert "hidden" not in json.dumps(packet).casefold()


def test_build_fact_packet_rejects_forbidden_nested_evidence():
    explanation = _explanation()
    explanation["factors"][0]["counterfactual"]["future_edges"] = ["edge-9"]

    with pytest.raises(ValueError, match="forbidden explanation field"):
        build_fact_packet(explanation)


def test_build_fact_packet_nested_mappings_are_allowlisted():
    explanation = _explanation()
    explanation["factors"][0]["counterfactual"].update(
        {
            "original_seed0_probability": 0.7,
            "ablated_seed0_probability": 0.2,
            "seed0_probability_delta": -0.5,
            "future_outcomes": ["unsupported"],
        }
    )
    explanation["factors"][0]["restart"]["ground_truth_strength"] = 0.99

    packet = build_fact_packet(explanation)
    serialized = json.dumps(packet, sort_keys=True)

    assert "original_seed0_probability" in serialized
    assert "ablated_seed0_probability" in serialized
    assert "seed0_probability_delta" in serialized
    assert "future_outcomes" not in serialized
    assert "ground_truth_strength" not in serialized


def test_direct_fact_packet_rejects_fields_outside_the_allowlist():
    packet = _fact_packet()
    packet["ground_truth_strength"] = 0.99

    with pytest.raises(ValueError, match="fact packet fields"):
        build_prompt(packet)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda packet: packet["factors_by_id"]["factor-1"]["counterfactual"].__setitem__(
            "hybrid_rank_delta", {"unapproved_nested": "secret"}
        ),
        lambda packet: packet["factors_by_id"]["factor-1"]["counterfactual"].__setitem__(
            "hybrid_rank_delta", True
        ),
        lambda packet: packet["factors_by_id"]["factor-1"]["counterfactual"].__setitem__(
            "percentile_reference_id", {"secret": "reference"}
        ),
        lambda packet: packet["factors_by_id"]["factor-1"]["counterfactual"].__setitem__(
            "original_seed0_probability", False
        ),
        lambda packet: packet["factors_by_id"]["factor-1"]["counterfactual"].__setitem__(
            "original_component_size", 0
        ),
        lambda packet: packet["factors_by_id"]["factor-1"]["restart"].__setitem__(
            "selection_frequency", "always"
        ),
        lambda packet: packet["factors_by_id"]["factor-1"]["restart"].__setitem__(
            "iqr", float("inf")
        ),
        lambda packet: packet["factors_by_id"]["factor-1"].__setitem__(
            "kind", "hidden_relation"
        ),
        lambda packet: packet["factors_by_id"]["factor-1"].__setitem__(
            "kind", {"nested": "hidden_relation"}
        ),
        lambda packet: packet["factors_by_id"]["factor-1"].__setitem__(
            "stability", "ground_truth_confirmed"
        ),
        lambda packet: packet["visible_paths"][0].__setitem__(
            "relation", "SECRET_RELATION"
        ),
        lambda packet: packet["visible_paths"][0].__setitem__(
            "relation", {"nested": "SECRET_RELATION"}
        ),
        lambda packet: packet["visible_paths"][0].__setitem__("edge_id", ""),
        lambda packet: packet["visible_paths"][0].__setitem__(
            "explainer_median", {"secret": 0.9}
        ),
    ],
    ids=[
        "nested-counterfactual",
        "boolean-rank-delta",
        "nested-reference-id",
        "boolean-probability",
        "invalid-component-size",
        "nonnumeric-restart",
        "nonfinite-restart",
        "unknown-factor-kind",
        "nested-factor-kind",
        "unknown-stability",
        "unknown-relation",
        "nested-relation",
        "blank-edge-id",
        "nested-mask-value",
    ],
)
def test_direct_fact_packet_rejects_invalid_allowed_leaf_values(mutate):
    packet = _fact_packet()
    mutate(packet)

    with pytest.raises(ValueError, match="fact packet"):
        build_prompt(packet)


def test_invalid_counterfactual_types_use_rank_only_template_without_ollama():
    packet = _fact_packet()
    packet["factors_by_id"]["factor-1"]["counterfactual"][
        "hybrid_rank_delta"
    ] = "not-numeric"

    class MustNotRun:
        def __call__(self, command, **kwargs):
            raise AssertionError("invalid evidence must fail before Ollama")

    result = generate_narrative(packet, runner=MustNotRun())

    assert result["source"] == "deterministic_template"
    assert result["validated"] is True
    assert result["claims"] == []
    assert result["summary"] == (
        "In seed 0, Baseline rank was 18, GNN rank was 4, and Hybrid rank was 7."
    )


def test_nested_enum_types_use_rank_only_template_without_ollama():
    packet = _fact_packet()
    packet["factors_by_id"]["factor-1"]["kind"] = {"nested": "bad"}

    class MustNotRun:
        def __call__(self, command, **kwargs):
            raise AssertionError("invalid evidence must fail before Ollama")

    result = generate_narrative(packet, runner=MustNotRun())

    assert result["source"] == "deterministic_template"
    assert result["claims"] == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda packet: packet["factors_by_id"]["factor-1"]["counterfactual"].update(
            {
                "original_seed0_probability": 0.7,
                "ablated_seed0_probability": 0.2,
                "seed0_probability_delta": 0.5,
            }
        ),
        lambda packet: packet["factors_by_id"]["factor-1"]["counterfactual"].__setitem__(
            "original_hybrid_rank", 8
        ),
    ],
    ids=["probability-delta", "factor-original-rank"],
)
def test_fact_packet_rejects_internally_inconsistent_counterfactuals(mutate):
    packet = _fact_packet()
    mutate(packet)

    with pytest.raises(ValueError, match="fact packet"):
        build_prompt(packet)


def test_prompt_requires_json_only_and_source_refs():
    prompt = build_prompt(_fact_packet())

    assert prompt.startswith("Return JSON only.")
    assert '"source_refs"' in prompt
    assert "Every sentence needs source_refs" in prompt
    assert "FACT_PACKET\n" in prompt


def test_generate_narrative_uses_installed_gemma_without_pull_or_shell():
    runner = FakeRunner(
        list_stdout="NAME ID SIZE MODIFIED\ngemma4:12b abc 7.4 GB now\n",
        run_stdout=json.dumps(_valid_candidate()),
    )

    result = generate_narrative(_fact_packet(), runner=runner)

    assert result == {
        "source": "llm",
        "model": "gemma4:12b",
        "prompt_version": PROMPT_VERSION,
        "summary": "In seed 0, the recorded Hybrid rank was 7.",
        "summary_source_refs": ["scope.observability_seed", "ranks.seed0_hybrid"],
        "claims": _valid_candidate()["claims"],
        "validated": True,
    }
    assert runner.commands[0] == ["ollama", "list"]
    assert runner.commands[1] == [
        "ollama",
        "run",
        MODEL_TAG,
        "--format",
        "json",
        "--think=false",
        "--keepalive",
        "10m",
    ]
    assert all("pull" not in command for command in runner.commands)
    assert all(kwargs.get("shell") is not True for _command, kwargs in runner.calls)
    assert runner.calls[0][1] == {
        "capture_output": True,
        "text": True,
        "timeout": 10,
        "check": False,
    }
    assert runner.calls[1][1]["input"].startswith("Return JSON only.")
    assert runner.calls[1][1]["check"] is False


@pytest.mark.parametrize(
    "runner",
    [
        FailingRunner(),
        FakeRunner(list_stdout="NAME ID SIZE MODIFIED\n", run_stdout="{}"),
        FakeRunner(list_stdout="", run_stdout="{}", list_returncode=1),
        FakeRunner(
            list_stdout="NAME ID SIZE MODIFIED\ngemma4:12b abc 7.4 GB now\n",
            run_stdout="{}",
            run_returncode=1,
        ),
        FakeRunner(
            list_stdout="NAME ID SIZE MODIFIED\ngemma4:12b abc 7.4 GB now\n",
            run_stdout="not-json",
        ),
        FakeRunner(
            list_stdout="NAME ID SIZE MODIFIED\ngemma4:12b abc 7.4 GB now\n",
            run_stdout=json.dumps({"summary": {}, "claims": []}),
        ),
        TimeoutRunner(
            list_stdout="NAME ID SIZE MODIFIED\ngemma4:12b abc 7.4 GB now\n",
            run_stdout="",
        ),
    ],
    ids=[
        "ollama-missing",
        "model-missing",
        "list-failed",
        "run-failed",
        "invalid-json",
        "unsupported-candidate",
        "timeout",
    ],
)
def test_expected_ollama_failures_use_validated_deterministic_template(runner):
    result = generate_narrative(_fact_packet(), runner=runner)

    assert result["source"] == "deterministic_template"
    assert result["model"] is None
    assert result["prompt_version"] == PROMPT_VERSION
    assert result["validated"] is True


@pytest.mark.parametrize(
    "invented",
    [
        "P-99999",
        "rank 777",
        "caused the seizure",
        "proved the outcome",
        "transferred weights across the edge",
        "a learned weight selected the case",
    ],
)
def test_validator_rejects_unsupported_claims(invented):
    candidate = {
        "summary": {
            "text": "In seed 0, this is the selected observability case.",
            "source_refs": ["scope.observability_seed"],
        },
        "claims": [
            {
                "text": invented,
                "source_refs": [
                    "factors_by_id.factor-1.counterfactual.hybrid_rank_delta"
                ],
            }
        ],
    }

    with pytest.raises(ValueError, match="unsupported narrative claim"):
        validate_candidate(_fact_packet(), candidate)


def test_validator_rejects_unknown_source_ref():
    candidate = _valid_candidate()
    candidate["claims"][0]["source_refs"] = ["factors_by_id.factor-404.label"]

    with pytest.raises(ValueError, match="unknown source_ref"):
        validate_candidate(_fact_packet(), candidate)


def test_validator_requires_identifier_to_be_supported_by_its_refs():
    candidate = _valid_candidate()
    candidate["claims"][0] = {
        "text": "P-100 had Hybrid rank 7.",
        "source_refs": ["ranks.seed0_hybrid"],
    }

    with pytest.raises(ValueError, match="unsupported narrative claim"):
        validate_candidate(_fact_packet(), candidate)


def test_validator_rejects_duplicate_source_refs():
    candidate = _valid_candidate()
    candidate["summary"]["source_refs"].append("ranks.seed0_hybrid")

    with pytest.raises(ValueError, match="unsupported narrative claim"):
        validate_candidate(_fact_packet(), candidate)


@pytest.mark.parametrize(
    "text,refs",
    [
        (
            "P-100 is married to P-200.",
            ["visible_paths.0.u", "visible_paths.0.v"],
        ),
        ("GraphSAGE used attention.", ["scope.gnn_arm"]),
        ("The three-seed headline Hybrid rank was 7.", ["ranks.seed0_hybrid"]),
    ],
)
def test_validator_rejects_unsupported_relationship_and_model_claims(text, refs):
    candidate = _valid_candidate()
    candidate["claims"][0] = {"text": text, "source_refs": refs}

    with pytest.raises(ValueError, match="unsupported narrative claim"):
        validate_candidate(_fact_packet(), candidate)


@pytest.mark.parametrize(
    "causal_text",
    [
        "Graph evidence drove the selection.",
        "Graph evidence triggered the selection.",
        "The selection happened because of COTRAVEL.",
        "Graph evidence contributed to the selection.",
    ],
)
def test_validator_rejects_causal_language_beyond_the_minimum_blacklist(causal_text):
    candidate = _valid_candidate()
    candidate["claims"][0] = {
        "text": causal_text,
        "source_refs": ["factors_by_id.factor-1.label"],
    }

    with pytest.raises(ValueError, match="unsupported narrative claim"):
        validate_candidate(_fact_packet(), candidate)


def test_validator_resolves_list_indices_in_visible_path_refs():
    candidate = {
        "summary": _valid_candidate()["summary"],
        "claims": [
            {
                "text": "The visible relation is COTRAVEL.",
                "source_refs": ["visible_paths.0.relation"],
            }
        ],
    }

    validated = validate_candidate(_fact_packet(), candidate)

    assert validated["claims"] == candidate["claims"]


@pytest.mark.parametrize(
    "candidate",
    [
        [],
        {"summary": {"text": "In seed 0.", "source_refs": []}, "claims": []},
        {
            "summary": {
                "text": "The recorded Hybrid rank was 7.",
                "source_refs": ["ranks.seed0_hybrid"],
            },
            "claims": [],
        },
        {"summary": _valid_candidate()["summary"], "claims": {}},
    ],
    ids=["non-object", "missing-refs", "missing-seed-scope", "claims-not-list"],
)
def test_validator_fails_closed_on_invalid_candidate_shapes(candidate):
    with pytest.raises(ValueError, match="unsupported narrative claim"):
        validate_candidate(_fact_packet(), candidate)


def test_template_is_deterministic_and_uses_highest_absolute_counterfactual():
    packet = _fact_packet(
        factors={
            "factor-low": {
                "label": "RESIDENCE with P-300",
                "kind": "pair_relation",
                "counterfactual": {
                    "original_hybrid_rank": 7,
                    "ablated_hybrid_rank": 9,
                    "hybrid_rank_delta": 2,
                },
                "restart": {"selection_frequency": 1.0, "iqr": 0.1},
                "stability": "stable",
            },
            "factor-high": {
                "label": "COTRAVEL with P-100",
                "kind": "pair_relation",
                "counterfactual": {
                    "original_hybrid_rank": 7,
                    "ablated_hybrid_rank": 43,
                    "hybrid_rank_delta": 36,
                },
                "restart": {"selection_frequency": 1.0, "iqr": 0.1},
                "stability": "stable",
            },
        }
    )

    first = render_template(packet)
    second = render_template(packet)

    assert first == second
    assert first["source"] == "deterministic_template"
    assert first["model"] is None
    assert first["validated"] is True
    assert "COTRAVEL with P-100" in first["claims"][0]["text"]
    assert "RESIDENCE" not in first["claims"][0]["text"]
    json.dumps(first, sort_keys=True, allow_nan=False)


def test_template_with_no_factors_still_states_seed_zero_scope():
    result = render_template(_fact_packet(factors={}))

    assert "seed 0" in result["summary"].casefold()
    assert "Baseline rank was 18" in result["summary"]
    assert "GNN rank was 4" in result["summary"]
    assert "Hybrid rank was 7" in result["summary"]
    assert "contributed" not in result["summary"].casefold()
    assert result["claims"] == []


def test_unexpected_programmer_error_is_not_swallowed():
    class BuggyRunner:
        def __call__(self, command, **kwargs):
            raise TypeError("adapter programming bug")

    with pytest.raises(TypeError, match="programming bug"):
        generate_narrative(_fact_packet(), runner=BuggyRunner())


@pytest.mark.skipif(
    os.environ.get("RUN_OLLAMA_INTEGRATION") != "1",
    reason="set RUN_OLLAMA_INTEGRATION=1 for the local Gemma smoke test",
)
def test_live_gemma_returns_a_validated_narrative():
    result = generate_narrative(_fact_packet())

    assert result["source"] == "llm"
    assert result["model"] == MODEL_TAG
    assert result["validated"] is True
