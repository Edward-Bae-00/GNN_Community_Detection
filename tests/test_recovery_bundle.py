import json
import os
from pathlib import Path

import pytest

from gnn.recovery_bundle import RecoveryBundleError, RecoveryBundleWriter


def _community(key="community:a"):
    return {
        "community_key": key,
        "complete": True,
        "scoring_day": "2025-01-02T00:00:00+00:00",
        "component_id": "component-7",
        "nodes": [
            {"node_id": "person:p1", "kind": "person"},
            {"node_id": "plate:x", "kind": "plate"},
        ],
        "edges": [
            {
                "edge_id": "edge:1",
                "u": "person:p1",
                "v": "plate:x",
                "edge_type": "used_plate",
                "source_row_ids": ["row:1", "row:2"],
                "source_row_count": 2,
                "observations": [
                    {"source_row_id": "row:1", "available_time": "2025-01-01"},
                    {"source_row_id": "row:2", "available_time": "2025-01-01"},
                ],
            }
        ],
        "provenance_expansions": [
            {
                "expansion_id": "expansion:1",
                "label": "shared plate history",
                "nodes": [{"node_id": "person:p2", "kind": "person"}],
                "edges": [
                    {
                        "edge_id": "edge:2",
                        "u": "person:p2",
                        "v": "plate:x",
                        "edge_type": "used_plate",
                        "source_row_ids": ["row:3"],
                        "source_row_count": 1,
                        "observations": [
                            {
                                "source_row_id": "row:3",
                                "available_time": "2024-12-31",
                            }
                        ],
                    }
                ],
            }
        ],
    }


def _read_ref(root: Path, ref):
    path = root / ref["path"]
    content = path.read_bytes()
    assert len(content) == ref["bytes"]
    return json.loads(content)


def _case(case_id, community_key="community:a"):
    return {
        "case_id": case_id,
        "person_id": case_id.split(":", 1)[-1],
        "event_id": f"event:{case_id.split(':', 1)[-1]}",
        "community_key": community_key,
        "scoring_day": "2025-01-02T00:00:00+00:00",
    }


def _explanation(case_id):
    return {
        "case_id": case_id,
        "person_id": case_id.split(":", 1)[-1],
        "event_id": f"event:{case_id.split(':', 1)[-1]}",
        "scoring_day": "2025-01-02T00:00:00+00:00",
        "community_key": "community:a",
        "attributions": {"top_edges": []},
        "llm_narrative": {
            "source": "llm",
            "model": "gemma4:12b",
            "validated": True,
            "prompt_version": "recovery-grounded-v2",
            "summary": "Grounded summary.",
            "summary_source_refs": ["ranks.seed0_hybrid"],
            "claims": [
                {
                    "text": "The recorded Hybrid rank was source-grounded.",
                    "source_refs": ["ranks.seed0_hybrid"],
                }
            ],
        },
    }


def test_community_objects_are_content_deduplicated_and_provenance_is_separate(tmp_path):
    writer = RecoveryBundleWriter(
        tmp_path / "stage",
        tmp_path / "published",
        run_fingerprint={"seed": 0, "k": 5},
        chunk_size=1,
    )

    first = writer.write_community(_community("community:a"))
    second = writer.write_community(_community("community:a"))

    assert first == second
    manifest = _read_ref(tmp_path / "stage", first)
    assert manifest["complete"] is True
    assert manifest["node_count"] == 3
    assert manifest["edge_count"] == 2
    assert manifest["provenance_observation_count"] == 3
    edges = [
        edge
        for ref in manifest["edge_chunks"]
        for edge in _read_ref(tmp_path / "stage", ref)["edges"]
    ]
    assert all("observations" not in edge for edge in edges)
    observations = [
        row
        for ref in manifest["provenance_chunks"]
        for row in _read_ref(tmp_path / "stage", ref)["observations"]
    ]
    assert {row["source_row_id"] for row in observations} == {
        "row:1",
        "row:2",
        "row:3",
    }
    memberships = [
        row
        for ref in manifest["provenance_expansion_membership_chunks"]
        for row in _read_ref(tmp_path / "stage", ref)["memberships"]
    ]
    assert {
        (row["kind"], row["record_id"], row["expansion_id"])
        for row in memberships
    } == {
        ("node", "person:p2", "expansion:1"),
        ("edge", "edge:2", "expansion:1"),
    }
    object_files = list((tmp_path / "stage" / "objects").rglob("*.json"))
    assert len(object_files) == 11  # records + expansion memberships + manifest


def test_checkpoint_resumes_and_reuses_matching_fingerprint_objects(tmp_path):
    stage = tmp_path / "stage"
    published = tmp_path / "published"
    first = RecoveryBundleWriter(
        stage, published, run_fingerprint={"seed": 0, "k": 5}, chunk_size=2
    )
    community_ref = first.write_community(_community())
    checkpoint = first.checkpoint()
    object_mtimes = {
        path: path.stat().st_mtime_ns for path in (stage / "objects").rglob("*.json")
    }

    resumed = RecoveryBundleWriter(
        stage, published, run_fingerprint={"k": 5, "seed": 0}, chunk_size=2
    )

    assert resumed.community_index == {"community:a": community_ref}
    assert checkpoint == stage / "checkpoint.json"
    assert resumed.write_community(_community()) == community_ref
    assert {
        path: path.stat().st_mtime_ns for path in (stage / "objects").rglob("*.json")
    } == object_mtimes


def test_resume_rejects_a_different_run_fingerprint(tmp_path):
    stage = tmp_path / "stage"
    first = RecoveryBundleWriter(
        stage, tmp_path / "published", run_fingerprint={"seed": 0}
    )
    first.write_community(_community())
    first.checkpoint()

    with pytest.raises(RecoveryBundleError, match="fingerprint mismatch"):
        RecoveryBundleWriter(
            stage, tmp_path / "published", run_fingerprint={"seed": 1}
        )


def test_resume_rejects_a_corrupt_referenced_cache_object(tmp_path):
    stage = tmp_path / "stage"
    first = RecoveryBundleWriter(
        stage, tmp_path / "published", run_fingerprint={"seed": 0}
    )
    ref = first.write_community(_community())
    first.checkpoint()
    (stage / ref["path"]).write_text("{}", encoding="utf-8")

    with pytest.raises(RecoveryBundleError, match="corrupt cached object"):
        RecoveryBundleWriter(
            stage, tmp_path / "published", run_fingerprint={"seed": 0}
        )


def test_finalize_publishes_complete_cases_and_pointer_last(tmp_path):
    writer = RecoveryBundleWriter(
        tmp_path / "stage",
        tmp_path / "published",
        run_fingerprint={"seed": 0, "k": 5},
    )
    writer.write_community(_community())
    writer.write_case(
        "hybrid_only",
        _case("case:h"),
        explanation=_explanation("case:h"),
        overlay_evidence=_streaming_overlay(),
    )
    writer.write_case("baseline_only", _case("case:b"))

    manifest = writer.finalize(
        expected_hybrid_case_ids={"case:h"},
        expected_baseline_case_ids={"case:b"},
        policy={"observability_seed": 0, "inspections_per_day": 5},
        summary={"hybrid_only_recovered": 1, "baseline_only_recovered": 1},
    )

    assert manifest["coverage"] == {
        "hybrid_only_count": 1,
        "baseline_only_count": 1,
        "explained_count": 1,
        "llm_validated_count": 1,
        "failed_count": 0,
        "complete": True,
    }
    assert [item["case_id"] for item in manifest["cohorts"]["hybrid_only"]] == [
        "case:h"
    ]
    pointer = json.loads((tmp_path / "published" / "current.json").read_text())
    assert pointer["bundle_id"] == manifest["bundle_id"]
    bundle = tmp_path / "published" / pointer["bundle_path"]
    assert json.loads((bundle / "manifest.json").read_text()) == manifest
    assert all((bundle / ref["path"]).is_file() for ref in manifest["case_index"].values())
    community_manifest = _read_ref(
        bundle, manifest["community_index"]["community:a"]
    )
    assert all(
        (bundle / ref["path"]).is_file()
        for ref in community_manifest["provenance_expansion_membership_chunks"]
    )


def test_finalize_fails_closed_when_an_expected_case_is_missing(tmp_path):
    writer = RecoveryBundleWriter(
        tmp_path / "stage", tmp_path / "published", run_fingerprint="run-a"
    )
    writer.write_community(_community())

    with pytest.raises(RecoveryBundleError, match="exactly match expectations"):
        writer.finalize(
            expected_hybrid_case_ids={"case:missing"},
            expected_baseline_case_ids=set(),
            policy={},
            summary={},
        )

    assert not (tmp_path / "published" / "current.json").exists()


def test_invalid_hybrid_llm_metadata_is_rejected_before_publication(tmp_path):
    writer = RecoveryBundleWriter(
        tmp_path / "stage", tmp_path / "published", run_fingerprint="run-a"
    )
    writer.write_community(_community())
    explanation = _explanation("case:h")
    explanation["llm_narrative"]["model"] = "deterministic-template"

    with pytest.raises(RecoveryBundleError, match="grounded Gemma metadata"):
        writer.write_case(
            "hybrid_only",
            _case("case:h"),
            explanation=explanation,
            overlay_evidence=_streaming_overlay(),
        )

    assert writer.case_index == {}
    assert not (tmp_path / "published" / "current.json").exists()


def test_prior_publication_survives_a_failed_replacement(tmp_path):
    writer = RecoveryBundleWriter(
        tmp_path / "stage", tmp_path / "published", run_fingerprint="run-a"
    )
    writer.write_community(_community())
    writer.write_case(
        "hybrid_only",
        _case("case:h"),
        explanation=_explanation("case:h"),
        overlay_evidence=_streaming_overlay(),
    )
    first_manifest = writer.finalize(
        expected_hybrid_case_ids={"case:h"},
        expected_baseline_case_ids=set(),
        policy={"inspections_per_day": 5},
        summary={},
    )
    pointer_path = tmp_path / "published" / "current.json"
    prior_pointer = pointer_path.read_bytes()
    prior_bundle = tmp_path / "published" / first_manifest["bundle_path"]
    prior_manifest = (prior_bundle / "manifest.json").read_bytes()

    writer.record_failure({"case_id": "case:x", "reason": "ollama timeout"})
    with pytest.raises(RecoveryBundleError, match="failures prevent publication"):
        writer.finalize(
            expected_hybrid_case_ids={"case:h"},
            expected_baseline_case_ids=set(),
            policy={"inspections_per_day": 5},
            summary={},
        )

    assert pointer_path.read_bytes() == prior_pointer
    assert (prior_bundle / "manifest.json").read_bytes() == prior_manifest


def test_manifest_is_deterministic_across_write_order(tmp_path):
    def publish(root, reverse):
        writer = RecoveryBundleWriter(
            root / "stage",
            root / "published",
            run_fingerprint={"seed": 0, "corpus": "v9"},
            chunk_size=2,
        )
        communities = [_community("community:a"), _community("community:b")]
        if reverse:
            communities.reverse()
        for community in communities:
            writer.write_community(community)
        writes = [
            (
                "hybrid_only",
                _case("case:h", "community:a"),
                {**_explanation("case:h"), "community_key": "community:a"},
            ),
            ("baseline_only", _case("case:b", "community:b"), None),
        ]
        if reverse:
            writes.reverse()
        for cohort, case, explanation in writes:
            writer.write_case(
                cohort,
                case,
                explanation=explanation,
                overlay_evidence=(
                    _streaming_overlay() if cohort == "hybrid_only" else None
                ),
            )
        return writer.finalize(
            expected_hybrid_case_ids={"case:h"},
            expected_baseline_case_ids={"case:b"},
            policy={"observability_seed": 0, "inspections_per_day": 5},
            summary={"net_gain": 0},
        )

    assert publish(tmp_path / "first", False) == publish(tmp_path / "second", True)


def test_resume_after_case_checkpoint_can_finish_publication(tmp_path):
    stage = tmp_path / "stage"
    published = tmp_path / "published"
    interrupted = RecoveryBundleWriter(
        stage, published, run_fingerprint={"seed": 0, "k": 5}
    )
    interrupted.write_community(_community())
    interrupted.write_case(
        "hybrid_only",
        _case("case:h"),
        explanation=_explanation("case:h"),
        overlay_evidence=_streaming_overlay(),
    )

    resumed = RecoveryBundleWriter(
        stage, published, run_fingerprint={"k": 5, "seed": 0}
    )
    manifest = resumed.finalize(
        expected_hybrid_case_ids={"case:h"},
        expected_baseline_case_ids=set(),
        policy={"inspections_per_day": 5},
        summary={},
    )

    assert set(resumed.case_index) == {"case:h"}
    assert manifest["coverage"]["complete"] is True


def test_community_accepts_one_shot_node_edge_and_provenance_streams(tmp_path):
    consumed = {"nodes": 0, "edges": 0, "provenance": 0}

    def nodes():
        for node_id in ("person:p1", "plate:x"):
            consumed["nodes"] += 1
            yield {"node_id": node_id, "kind": node_id.split(":", 1)[0]}

    def edges():
        consumed["edges"] += 1
        yield {
            "edge_id": "edge:streamed",
            "u": "person:p1",
            "v": "plate:x",
            "edge_type": "used_plate",
            "source_row_ids": ["row:streamed"],
            "source_row_count": 1,
        }

    def provenance():
        consumed["provenance"] += 1
        yield {
            "edge_id": "edge:streamed",
            "source_row_id": "row:streamed",
            "available_time": "2025-01-01",
        }

    writer = RecoveryBundleWriter(
        tmp_path / "stage",
        tmp_path / "published",
        run_fingerprint="streaming-run",
        chunk_size=1,
    )
    ref = writer.write_community(
        {
            "community_key": "community:streamed",
            "complete": True,
            "scoring_day": "2025-01-02T00:00:00+00:00",
            "component_id": "component-streamed",
            "nodes": nodes(),
            "edges": edges(),
            "provenance_observations": provenance(),
            "provenance_expansions": iter(()),
        }
    )

    assert consumed == {"nodes": 2, "edges": 1, "provenance": 1}
    manifest = _read_ref(tmp_path / "stage", ref)
    assert manifest["node_count"] == 2
    assert manifest["edge_count"] == 1
    assert manifest["provenance_observation_count"] == 1


def test_case_attribution_overlays_do_not_change_shared_base_community(tmp_path):
    stage = tmp_path / "stage"
    writer = RecoveryBundleWriter(
        stage, tmp_path / "published", run_fingerprint="overlay-run"
    )
    community_ref = writer.write_community(_community())
    community_bytes = (stage / community_ref["path"]).read_bytes()
    first = _explanation("case:h1")
    first["attributions"] = {"top_edges": [{"edge_id": "edge:1", "weight": 0.8}]}
    second = _explanation("case:h2")
    second["attributions"] = {"top_edges": [{"edge_id": "edge:2", "weight": 0.3}]}

    writer.write_case(
        "hybrid_only",
        _case("case:h1"),
        explanation=first,
        overlay_evidence=_streaming_overlay(),
    )
    writer.write_case(
        "hybrid_only",
        _case("case:h2"),
        explanation=second,
        overlay_evidence=_streaming_overlay(),
    )

    assert writer.community_index == {"community:a": community_ref}
    assert (stage / community_ref["path"]).read_bytes() == community_bytes
    assert writer.case_index["case:h1"]["ref"] != writer.case_index["case:h2"]["ref"]


def _streaming_overlay():
    return {
        "nodes": (
            {"node_id": node_id, "kind": "person"}
            for node_id in ("person:overlay-target",)
        ),
        "edges": (
            {
                "edge_id": "overlay-edge:1",
                "u": "person:overlay-target",
                "v": "plate:x",
                "edge_type": "attributed_used_plate",
                "source_row_ids": ["overlay-row:1"],
                "source_row_count": 1,
            }
            for _ in range(1)
        ),
        "provenance_observations": (
            {
                "edge_id": edge_id,
                "source_row_id": row_id,
                "available_time": "2025-01-01",
            }
            for edge_id, row_id in (
                ("overlay-edge:1", "overlay-row:1"),
                ("overlay-edge:2", "overlay-row:2"),
            )
        ),
        "provenance_expansions": (
            {
                "expansion_id": "overlay-expansion:1",
                "label": "attributed shared plate",
                "nodes": (
                    {"node_id": "person:overlay-neighbor", "kind": "person"}
                    for _ in range(1)
                ),
                "edges": (
                    {
                        "edge_id": "overlay-edge:2",
                        "u": "person:overlay-neighbor",
                        "v": "plate:x",
                        "edge_type": "attributed_used_plate",
                        "source_row_ids": ["overlay-row:2"],
                        "source_row_count": 1,
                    }
                    for _ in range(1)
                ),
            }
            for _ in range(1)
        ),
    }


def test_hybrid_case_overlay_streams_are_chunked_separately_from_base(tmp_path):
    stage = tmp_path / "stage"
    published = tmp_path / "published"
    writer = RecoveryBundleWriter(
        stage, published, run_fingerprint="case-overlay", chunk_size=1
    )
    community_ref = writer.write_community(_community())
    community_bytes = (stage / community_ref["path"]).read_bytes()

    writer.write_case(
        "hybrid_only",
        _case("case:h"),
        explanation=_explanation("case:h"),
        overlay_evidence=_streaming_overlay(),
    )

    payload = _read_ref(stage, writer.case_index["case:h"]["ref"])
    overlay = payload["overlay_evidence"]
    assert overlay["complete"] is True
    assert overlay["node_count"] == 2
    assert overlay["edge_count"] == 2
    assert overlay["provenance_observation_count"] == 2
    assert len(overlay["provenance_expansion_membership_chunks"]) == 2
    assert (stage / community_ref["path"]).read_bytes() == community_bytes
    community_manifest = _read_ref(stage, community_ref)
    overlay_paths = {
        ref["path"]
        for field in (
            "node_chunks",
            "edge_chunks",
            "provenance_chunks",
            "provenance_expansion_membership_chunks",
        )
        for ref in overlay[field]
    }
    base_paths = {
        ref["path"]
        for field in (
            "node_chunks",
            "edge_chunks",
            "provenance_chunks",
            "provenance_expansion_membership_chunks",
        )
        for ref in community_manifest[field]
    }
    assert overlay_paths.isdisjoint(base_paths)
    manifest = writer.finalize(
        expected_hybrid_case_ids={"case:h"},
        expected_baseline_case_ids=set(),
        policy={},
        summary={},
    )
    bundle = published / manifest["bundle_path"]
    assert all((bundle / path).is_file() for path in overlay_paths)


def test_baseline_case_rejects_overlay_evidence(tmp_path):
    writer = RecoveryBundleWriter(
        tmp_path / "stage", tmp_path / "published", run_fingerprint="case-overlay"
    )
    writer.write_community(_community())

    with pytest.raises(RecoveryBundleError, match="Baseline-only"):
        writer.write_case(
            "baseline_only",
            _case("case:b"),
            overlay_evidence=_streaming_overlay(),
        )


def test_resume_hash_verifies_case_overlay_chunks(tmp_path):
    stage = tmp_path / "stage"
    published = tmp_path / "published"
    writer = RecoveryBundleWriter(
        stage, published, run_fingerprint="case-overlay", chunk_size=1
    )
    writer.write_community(_community())
    writer.write_case(
        "hybrid_only",
        _case("case:h"),
        explanation=_explanation("case:h"),
        overlay_evidence=_streaming_overlay(),
    )
    payload = _read_ref(stage, writer.case_index["case:h"]["ref"])
    corrupt_ref = payload["overlay_evidence"]["provenance_chunks"][0]
    (stage / corrupt_ref["path"]).write_text("{}", encoding="utf-8")

    with pytest.raises(RecoveryBundleError, match="corrupt cached object"):
        RecoveryBundleWriter(
            stage, published, run_fingerprint="case-overlay", chunk_size=1
        )


def test_completed_case_probe_verifies_overlay_and_success_resolves_its_failure(tmp_path):
    writer = RecoveryBundleWriter(
        tmp_path / "stage",
        tmp_path / "published",
        run_fingerprint="case-overlay",
    )
    writer.write_community(_community())
    writer.record_failure({"case_id": "case:h", "reason": "interrupted"})
    writer.record_failure({"case_id": "case:other", "reason": "still failed"})
    assert writer.has_completed_case("case:h") is False
    writer.write_case(
        "hybrid_only",
        _case("case:h"),
        explanation=_explanation("case:h"),
        overlay_evidence=_streaming_overlay(),
    )

    assert writer.has_completed_case("case:h") is True
    assert writer.has_completed_case("case:h", cohort="hybrid_only") is True
    assert writer.has_completed_case("case:h", cohort="baseline_only") is False
    with pytest.raises(RecoveryBundleError, match="failures prevent publication"):
        writer.finalize(
            expected_hybrid_case_ids={"case:h"},
            expected_baseline_case_ids=set(),
            policy={},
            summary={},
        )


def test_recovery_sidecar_prefix_resolves_from_diagnostic_artifact_parent(tmp_path):
    diagnostics = tmp_path / "diagnostics"
    writer = RecoveryBundleWriter(
        tmp_path / "stage",
        diagnostics / "recovery",
        run_fingerprint={"seed": 0, "k": 5},
        sidecar_prefix="recovery",
    )
    writer.write_community(_community())
    writer.write_case("baseline_only", _case("case:b"))

    artifact = writer.finalize(
        expected_hybrid_case_ids=set(),
        expected_baseline_case_ids={"case:b"},
        policy={"inspections_per_day": 5},
        summary={},
    )

    assert artifact["sidecar_base"] == (
        f"recovery/bundles/{artifact['bundle_id']}/"
    )
    assert (diagnostics / artifact["sidecar_base"] / "manifest.json").is_file()


def test_streamed_provenance_must_match_declared_source_row_ids(tmp_path):
    writer = RecoveryBundleWriter(
        tmp_path / "stage", tmp_path / "published", run_fingerprint="rows"
    )
    community = _community()
    for edge in community["edges"]:
        edge.pop("observations")
    community["provenance_observations"] = iter(
        [
            {
                "edge_id": "edge:1",
                "source_row_id": "wrong-row:1",
                "available_time": "2025-01-01",
            },
            {
                "edge_id": "edge:1",
                "source_row_id": "wrong-row:2",
                "available_time": "2025-01-01",
            },
            {
                "edge_id": "edge:2",
                "source_row_id": "row:3",
                "available_time": "2024-12-31",
            },
        ]
    )
    community["provenance_expansions"][0]["edges"][0].pop("observations")

    with pytest.raises(RecoveryBundleError, match="source_row_ids"):
        writer.write_community(community)


def test_case_identity_must_match_explanation_and_community(tmp_path):
    writer = RecoveryBundleWriter(
        tmp_path / "stage", tmp_path / "published", run_fingerprint="identity"
    )
    writer.write_community(_community())
    explanation = _explanation("case:h")
    explanation["person_id"] = "different-person"

    with pytest.raises(RecoveryBundleError, match="identity"):
        writer.write_case(
            "hybrid_only", _case("case:h"), explanation=explanation
        )


def test_every_case_requires_complete_identity_fields(tmp_path):
    writer = RecoveryBundleWriter(
        tmp_path / "stage", tmp_path / "published", run_fingerprint="case-identity"
    )
    writer.write_community(_community())
    case = _case("case:b")
    case.pop("event_id")

    with pytest.raises(RecoveryBundleError, match="case identity"):
        writer.write_case("baseline_only", case)


def test_reusing_versioned_bundle_revalidates_every_published_object(tmp_path):
    writer = RecoveryBundleWriter(
        tmp_path / "stage", tmp_path / "published", run_fingerprint="reuse"
    )
    writer.write_community(_community())
    writer.write_case("baseline_only", _case("case:b"))
    manifest = writer.finalize(
        expected_hybrid_case_ids=set(),
        expected_baseline_case_ids={"case:b"},
        policy={},
        summary={},
    )
    pointer_path = tmp_path / "published" / "current.json"
    prior_pointer = pointer_path.read_bytes()
    bundle = tmp_path / "published" / manifest["bundle_path"]
    corrupt_ref = next(iter(manifest["community_index"].values()))
    corrupt_path = bundle / corrupt_ref["path"]
    corrupt_path.unlink()
    corrupt_path.write_text("{}", encoding="utf-8")

    with pytest.raises(RecoveryBundleError, match="published recovery bundle"):
        writer.finalize(
            expected_hybrid_case_ids=set(),
            expected_baseline_case_ids={"case:b"},
            policy={},
            summary={},
        )

    assert pointer_path.read_bytes() == prior_pointer


def test_finalize_does_not_checkpoint_after_atomic_pointer_publication(
    tmp_path, monkeypatch
):
    writer = RecoveryBundleWriter(
        tmp_path / "stage", tmp_path / "published", run_fingerprint="pointer-last"
    )
    writer.write_community(_community())
    writer.write_case("baseline_only", _case("case:b"))

    def late_checkpoint_is_forbidden():
        raise AssertionError("checkpoint must not run after publication")

    monkeypatch.setattr(writer, "checkpoint", late_checkpoint_is_forbidden)
    manifest = writer.finalize(
        expected_hybrid_case_ids=set(),
        expected_baseline_case_ids={"case:b"},
        policy={},
        summary={},
    )

    assert json.loads((tmp_path / "published" / "current.json").read_text())[
        "bundle_id"
    ] == manifest["bundle_id"]


def test_hybrid_case_requires_nonempty_overlay_evidence(tmp_path):
    writer = RecoveryBundleWriter(
        tmp_path / "stage", tmp_path / "published", run_fingerprint="required-overlay"
    )
    writer.write_community(_community())

    with pytest.raises(RecoveryBundleError, match="nonempty overlay"):
        writer.write_case(
            "hybrid_only", _case("case:h"), explanation=_explanation("case:h")
        )


def test_hybrid_case_allows_target_only_overlay_when_there_are_no_message_edges(
    tmp_path,
):
    writer = RecoveryBundleWriter(
        tmp_path / "stage", tmp_path / "published", run_fingerprint="no-message-edges"
    )
    writer.write_community(_community())

    writer.write_case(
        "hybrid_only",
        _case("case:h"),
        explanation=_explanation("case:h"),
        overlay_evidence={
            "nodes": iter(
                [{"node_id": "person:h", "kind": "person", "target": True}]
            ),
            "edges": iter(()),
            "provenance_observations": iter(()),
            "provenance_expansions": iter(()),
        },
    )

    payload = _read_ref(
        tmp_path / "stage", writer.case_index["case:h"]["ref"]
    )
    assert payload["overlay_evidence"]["node_count"] == 1
    assert payload["overlay_evidence"]["edge_count"] == 0
    assert payload["overlay_evidence"]["provenance_observation_count"] == 0
    assert writer.has_completed_case("case:h") is True


def test_finalize_keeps_published_objects_independent_from_resumable_cache(tmp_path):
    stage = tmp_path / "stage"
    published = tmp_path / "published"
    writer = RecoveryBundleWriter(stage, published, run_fingerprint="hard-link")
    community_ref = writer.write_community(_community())
    writer.write_case("baseline_only", _case("case:b"))

    manifest = writer.finalize(
        expected_hybrid_case_ids=set(),
        expected_baseline_case_ids={"case:b"},
        policy={},
        summary={},
    )

    source = stage / community_ref["path"]
    target = published / manifest["bundle_path"] / community_ref["path"]
    assert source.stat().st_dev == target.stat().st_dev
    assert source.stat().st_ino != target.stat().st_ino
    source_content = source.read_bytes()
    target.write_text("{}", encoding="utf-8")
    assert source.read_bytes() == source_content
    assert (stage / "checkpoint.json").stat().st_ino != (
        published / manifest["bundle_path"] / "manifest.json"
    ).stat().st_ino


def test_finalize_never_uses_mutation_aliasing_hard_links(
    tmp_path, monkeypatch
):
    stage = tmp_path / "stage"
    published = tmp_path / "published"
    writer = RecoveryBundleWriter(stage, published, run_fingerprint="copy-fallback")
    community_ref = writer.write_community(_community())
    writer.write_case("baseline_only", _case("case:b"))

    def unsafe_link(source, target):
        raise AssertionError("published evidence must not alias resumable cache")

    monkeypatch.setattr(os, "link", unsafe_link)
    manifest = writer.finalize(
        expected_hybrid_case_ids=set(),
        expected_baseline_case_ids={"case:b"},
        policy={},
        summary={},
    )

    source = stage / community_ref["path"]
    target = published / manifest["bundle_path"] / community_ref["path"]
    assert source.read_bytes() == target.read_bytes()
    assert source.stat().st_ino != target.stat().st_ino


@pytest.mark.parametrize(
    "mutate",
    [
        lambda narrative: narrative.__setitem__("model", "gemma2:12b"),
        lambda narrative: narrative.__setitem__("summary", " "),
        lambda narrative: narrative.__setitem__("claims", []),
        lambda narrative: narrative.__setitem__("summary_source_refs", []),
        lambda narrative: narrative.__setitem__("prompt_version", ""),
    ],
)
def test_hybrid_case_requires_complete_grounded_gemma_metadata(tmp_path, mutate):
    writer = RecoveryBundleWriter(
        tmp_path / "stage", tmp_path / "published", run_fingerprint="strict-llm"
    )
    writer.write_community(_community())
    explanation = _explanation("case:h")
    mutate(explanation["llm_narrative"])

    with pytest.raises(RecoveryBundleError, match="Gemma metadata"):
        writer.write_case(
            "hybrid_only",
            _case("case:h"),
            explanation=explanation,
            overlay_evidence=_streaming_overlay(),
        )


def test_completed_case_probe_is_false_while_same_case_failure_is_unresolved(tmp_path):
    writer = RecoveryBundleWriter(
        tmp_path / "stage", tmp_path / "published", run_fingerprint="failure-probe"
    )
    writer.write_community(_community())
    writer.write_case(
        "hybrid_only",
        _case("case:h"),
        explanation=_explanation("case:h"),
        overlay_evidence=_streaming_overlay(),
    )
    writer.record_failure({"case_id": "case:h", "reason": "later validation failed"})

    assert writer.has_completed_case("case:h") is False


def test_finalize_rejects_unreferenced_staged_community(tmp_path):
    writer = RecoveryBundleWriter(
        tmp_path / "stage", tmp_path / "published", run_fingerprint="stale-community"
    )
    writer.write_community(_community("community:a"))
    writer.write_community(_community("community:stale"))
    writer.write_case("baseline_only", _case("case:b", "community:a"))

    with pytest.raises(RecoveryBundleError, match="unreferenced staged communities"):
        writer.finalize(
            expected_hybrid_case_ids=set(),
            expected_baseline_case_ids={"case:b"},
            policy={},
            summary={},
        )


def test_public_indexes_are_deep_detached_copies(tmp_path):
    writer = RecoveryBundleWriter(
        tmp_path / "stage", tmp_path / "published", run_fingerprint="detached-index"
    )
    original_ref = writer.write_community(_community())
    writer.write_case("baseline_only", _case("case:b"))

    communities = writer.community_index
    cases = writer.case_index
    communities["community:a"]["path"] = "tampered"
    cases["case:b"]["case"]["person_id"] = "tampered"

    assert writer.community_index["community:a"] == original_ref
    assert writer.case_index["case:b"]["case"]["person_id"] == "b"
