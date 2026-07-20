import json
import os
from pathlib import Path

import pytest

from gnn.recovery_bundle import RecoveryBundleError, RecoveryBundleWriter
from Documents.Data.scripts import v9_recovery_sidecars


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
    assert manifest["chunk_size"] == 1
    assert manifest["chunking_policy"] == "bounded-page-records"
    assert all(
        reference["count"] <= manifest["chunk_size"]
        for field in (
            "node_chunks",
            "edge_chunks",
            "provenance_chunks",
            "provenance_expansion_membership_chunks",
        )
        for reference in manifest[field]
    )
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
    assert len(object_files) <= 18  # bounded catalog/day chunks, never one file per record


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
        policy={
            "observability_seed": 0,
            "gnn_arm": "sage",
            "surrounding_results_seeds": [0, 1, 2],
            "inspections_per_day": 5,
        },
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
        policy={"observability_seed": 0, "inspections_per_day": 5},
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


def test_finalize_atomically_consumes_successful_staging_tree(tmp_path):
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

    target = published / manifest["bundle_path"] / community_ref["path"]
    assert target.is_file()
    assert not stage.exists()


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

    target = published / manifest["bundle_path"] / community_ref["path"]
    assert target.is_file()
    assert not stage.exists()


def test_two_day_views_share_immutable_catalogs_but_not_caught_status(tmp_path):
    writer = RecoveryBundleWriter(
        tmp_path / "stage", tmp_path / "published", run_fingerprint="two-day"
    )
    first = _community("community:day-1")
    first["scoring_day"] = "2025-01-01T00:00:00+00:00"
    first["nodes"][0].update(
        {
            "caught_before_snapshot": False,
            "caught_label_available_time": None,
        }
    )
    second = _community("community:day-2")
    second["scoring_day"] = "2025-01-02T00:00:00+00:00"
    second["nodes"][0].update(
        {
            "caught_before_snapshot": True,
            "caught_label_available_time": "2025-01-01T12:00:00+00:00",
        }
    )

    first_manifest = _read_ref(tmp_path / "stage", writer.write_community(first))
    second_manifest = _read_ref(tmp_path / "stage", writer.write_community(second))

    assert first_manifest["catalogs"] == second_manifest["catalogs"]
    assert first_manifest["day_view"]["node_status_chunks"] != (
        second_manifest["day_view"]["node_status_chunks"]
    )


def test_resume_hash_verifies_normalized_day_status_chunks(tmp_path):
    stage = tmp_path / "stage"
    published = tmp_path / "published"
    writer = RecoveryBundleWriter(stage, published, run_fingerprint="day-status")
    community_ref = writer.write_community(_community())
    manifest = _read_ref(stage, community_ref)
    status_ref = manifest["day_view"]["node_status_chunks"][0]
    (stage / status_ref["path"]).write_text("{}", encoding="utf-8")

    with pytest.raises(RecoveryBundleError, match="corrupt cached object"):
        RecoveryBundleWriter(stage, published, run_fingerprint="day-status")


def test_edge_and_provenance_transitions_reuse_run_global_immutable_records(tmp_path):
    writer = RecoveryBundleWriter(
        tmp_path / "stage", tmp_path / "published", run_fingerprint="transition"
    )
    first = _community("community:day-1")
    first["edges"][0]["message_hop"] = 1
    second = _community("community:day-2")
    second["scoring_day"] = "2025-01-03T00:00:00+00:00"
    second["edges"][0]["message_hop"] = 2
    second["edges"][0]["source_row_ids"].append("row:later")
    second["edges"][0]["source_row_count"] = 3
    second["edges"][0]["observations"].append(
        {"source_row_id": "row:later", "available_time": "2025-01-02"}
    )

    first_manifest = _read_ref(tmp_path / "stage", writer.write_community(first))
    second_manifest = _read_ref(tmp_path / "stage", writer.write_community(second))

    assert first_manifest["catalogs"]["edge_count"] == 2
    assert second_manifest["catalogs"]["edge_count"] == 2
    assert first_manifest["catalogs"]["provenance_count"] == 3
    assert second_manifest["catalogs"]["provenance_count"] == 4
    assert first_manifest["day_view"] != second_manifest["day_view"]

    first_case = _case("case:first", "community:day-1")
    first_case["scoring_day"] = first["scoring_day"]
    second_case = _case("case:second", "community:day-2")
    second_case["scoring_day"] = second["scoring_day"]
    writer.write_case("baseline_only", first_case)
    writer.write_case("baseline_only", second_case)
    bundle = writer.finalize(
        expected_hybrid_case_ids=set(),
        expected_baseline_case_ids={"case:first", "case:second"},
        policy={},
        summary={},
    )
    final_root = tmp_path / "published" / bundle["bundle_path"]
    edge_index = bundle["catalog_index"]["edges"]
    provenance_index = bundle["catalog_index"]["provenance"]
    assert edge_index["record_count"] == 2
    assert provenance_index["record_count"] == 4
    assert len(edge_index["chunks"]) <= 2
    assert len(provenance_index["chunks"]) <= 2
    provenance_ids = [
        record["record_id"]
        for reference in provenance_index["chunks"]
        for record in _read_ref(final_root, reference)["records"]
    ]
    assert provenance_ids.count("row:1") == 1


def test_finalize_compacts_staging_in_place_without_producer_copy(tmp_path, monkeypatch):
    writer = RecoveryBundleWriter(
        tmp_path / "stage", tmp_path / "published", run_fingerprint="no-copy"
    )
    writer.write_community(_community())
    writer.write_case("baseline_only", _case("case:b"))
    monkeypatch.setattr(
        writer,
        "_copy_bundle_objects",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("producer publication must not copy its bundle")
        ),
        raising=False,
    )

    manifest = writer.finalize(
        expected_hybrid_case_ids=set(),
        expected_baseline_case_ids={"case:b"},
        policy={},
        summary={},
    )

    assert (tmp_path / "published" / manifest["bundle_path"] / "manifest.json").is_file()


def test_chunked_catalog_file_and_page_fetch_bounds(tmp_path):
    chunk_size = 2_000
    record_count = 10_001
    writer = RecoveryBundleWriter(
        tmp_path / "stage",
        tmp_path / "published",
        run_fingerprint="catalog-bounds",
        chunk_size=chunk_size,
    )
    community = {
        "community_key": "community:bounded",
        "complete": True,
        "scoring_day": "2025-01-02T00:00:00+00:00",
        "component_id": "component:bounded",
        "nodes": (
            {"node_id": f"node:{index:06d}", "kind": "person"}
            for index in range(record_count)
        ),
        "edges": iter(()),
        "provenance_expansions": iter(()),
    }
    writer.write_community(community)
    writer.write_case(
        "baseline_only", _case("case:bounded", "community:bounded")
    )
    manifest = writer.finalize(
        expected_hybrid_case_ids=set(),
        expected_baseline_case_ids={"case:bounded"},
        policy={},
        summary={},
    )
    expected_chunks = (record_count + chunk_size - 1) // chunk_size
    node_catalog = manifest["catalog_index"]["nodes"]
    assert node_catalog["record_count"] == record_count
    assert len(node_catalog["chunks"]) == expected_chunks
    assert all(chunk["count"] <= chunk_size for chunk in node_catalog["chunks"])

    bundle = tmp_path / "published" / manifest["bundle_path"]
    community_manifest = _read_ref(
        bundle, manifest["community_index"]["community:bounded"]
    )
    for membership_ref in community_manifest["node_chunks"]:
        ids = [
            row["catalog_id"]
            for row in _read_ref(bundle, membership_ref)["nodes"]
        ]
        matching_catalog_chunks = {
            chunk["path"]
            for catalog_id in ids
            for chunk in node_catalog["chunks"]
            if chunk["first_id"] <= catalog_id <= chunk["last_id"]
        }
        assert len(matching_catalog_chunks) == 1
    assert len(list(bundle.rglob("*.json"))) <= expected_chunks * 3 + 4


def test_disk_catalog_keeps_writer_state_and_checkpoint_bounded(tmp_path):
    record_count = 10_001
    stage = tmp_path / "stage"
    writer = RecoveryBundleWriter(
        stage,
        tmp_path / "published",
        run_fingerprint="disk-catalog",
        chunk_size=2_000,
    )
    writer.write_community(
        {
            "community_key": "community:disk",
            "complete": True,
            "scoring_day": "2025-01-02T00:00:00+00:00",
            "component_id": "component:disk",
            "nodes": (
                {
                    "node_id": f"node:{index:06d}",
                    "kind": "person",
                    "payload": "x" * 128,
                }
                for index in range(record_count)
            ),
            "edges": iter(()),
            "provenance_expansions": iter(()),
        }
    )
    checkpoint = writer.checkpoint()

    assert "catalog_records" not in writer._state
    assert writer.catalog_store.in_memory_record_count == 0
    assert checkpoint.stat().st_size < 100_000
    assert writer.catalog_store.path.stat().st_size > checkpoint.stat().st_size


def test_run_global_catalog_conflicts_fail_closed(tmp_path):
    writer = RecoveryBundleWriter(
        tmp_path / "stage", tmp_path / "published", run_fingerprint="conflict"
    )
    first = _community("community:first")
    writer.write_community(first)
    second = _community("community:second")
    second["nodes"][0]["kind"] = "conflicting-kind"

    with pytest.raises(RecoveryBundleError, match="run-global nodes record"):
        writer.write_community(second)


def test_failed_streaming_objects_are_excluded_from_published_reference_closure(
    tmp_path,
):
    stage = tmp_path / "stage"
    writer = RecoveryBundleWriter(
        stage, tmp_path / "published", run_fingerprint="orphan", chunk_size=1
    )
    broken = _community("community:broken")
    broken["nodes"] = iter(
        [
            {"node_id": "orphan:node", "kind": "person"},
            {"kind": "missing-id"},
        ]
    )
    with pytest.raises(RecoveryBundleError, match="node_id"):
        writer.write_community(broken)
    failed_only = {
        path.relative_to(stage).as_posix()
        for path in (stage / "objects").rglob("*.json")
    }
    writer.write_community(_community())
    writer.write_case("baseline_only", _case("case:b"))
    manifest = writer.finalize(
        expected_hybrid_case_ids=set(),
        expected_baseline_case_ids={"case:b"},
        policy={},
        summary={},
    )
    published = tmp_path / "published" / manifest["bundle_path"]

    assert failed_only
    assert all(not (published / relative).exists() for relative in failed_only)


def test_case_attempt_phases_persist_and_are_capped_across_resume(tmp_path):
    stage = tmp_path / "stage"
    writer = RecoveryBundleWriter(
        stage, tmp_path / "published", run_fingerprint="attempts"
    )
    writer.begin_case_attempt("case:h", "first_pass")
    writer.record_failure({"case_id": "case:h", "message": "first"})
    resumed = RecoveryBundleWriter(
        stage, tmp_path / "published", run_fingerprint="attempts"
    )

    assert resumed.case_attempt_state("case:h") == {
        "first_pass": "started",
        "deferred_retry": "pending",
    }
    with pytest.raises(RecoveryBundleError, match="already started"):
        resumed.begin_case_attempt("case:h", "first_pass")
    resumed.begin_case_attempt("case:h", "deferred_retry")
    with pytest.raises(RecoveryBundleError, match="already started"):
        resumed.begin_case_attempt("case:h", "deferred_retry")


def test_dashboard_physical_copy_fails_free_space_preflight_before_staging(
    tmp_path, monkeypatch
):
    diagnostics = tmp_path / "diagnostics"
    writer = RecoveryBundleWriter(
        tmp_path / "stage",
        diagnostics / "recovery",
        run_fingerprint={"run_identity": {"checkpoint_id": "abc"}},
        sidecar_prefix="recovery",
    )
    writer.write_community(_community())
    writer.write_case("baseline_only", _case("case:b"))
    manifest = writer.finalize(
        expected_hybrid_case_ids=set(),
        expected_baseline_case_ids={"case:b"},
        policy={
            "observability_seed": 0,
            "gnn_arm": "sage",
            "surrounding_results_seeds": [0, 1, 2],
            "inspections_per_day": 5,
        },
        summary={
            "overlap_ids_available": True,
            "baseline_recovered": 1,
            "recovered_by_both": 0,
            "hybrid_only_recovered": 0,
            "baseline_only_recovered": 1,
            "hybrid_total": 0,
            "net_gain": -1,
        },
    )
    monkeypatch.delattr(v9_recovery_sidecars.os, "clonefile", raising=False)
    monkeypatch.setattr(
        v9_recovery_sidecars.shutil,
        "disk_usage",
        lambda path: v9_recovery_sidecars.shutil._ntuple_diskusage(1, 1, 0),
    )
    output = tmp_path / "dashboard" / "recovery"

    with pytest.raises(ValueError, match="insufficient free space"):
        v9_recovery_sidecars.publish_prepackaged_manifest(
            manifest, diagnostics / "demo.json", output
        )

    assert not output.exists()


def test_dashboard_publication_rejects_mismatched_source_manifest(tmp_path):
    diagnostics = tmp_path / "diagnostics"
    writer = RecoveryBundleWriter(
        tmp_path / "stage",
        diagnostics / "recovery",
        run_fingerprint={"run_identity": {"checkpoint_id": "abc"}},
        sidecar_prefix="recovery",
    )
    writer.write_community(_community())
    writer.write_case("baseline_only", _case("case:b"))
    manifest = writer.finalize(
        expected_hybrid_case_ids=set(),
        expected_baseline_case_ids={"case:b"},
        policy={
            "observability_seed": 0,
            "gnn_arm": "sage",
            "surrounding_results_seeds": [0, 1, 2],
            "inspections_per_day": 5,
        },
        summary={
            "overlap_ids_available": True,
            "baseline_recovered": 1,
            "recovered_by_both": 0,
            "hybrid_only_recovered": 0,
            "baseline_only_recovered": 1,
            "hybrid_total": 0,
            "net_gain": -1,
        },
    )
    source_manifest = (
        diagnostics / "recovery" / manifest["bundle_path"] / "manifest.json"
    )
    source_manifest.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="source manifest"):
        v9_recovery_sidecars.publish_prepackaged_manifest(
            manifest, diagnostics / "demo.json", tmp_path / "dashboard"
        )


def test_dashboard_publication_copies_only_verified_reference_closure(tmp_path):
    diagnostics = tmp_path / "diagnostics"
    writer = RecoveryBundleWriter(
        tmp_path / "stage",
        diagnostics / "recovery",
        run_fingerprint={"run_identity": {"checkpoint_id": "abc"}},
        sidecar_prefix="recovery",
    )
    writer.write_community(_community())
    writer.write_case("baseline_only", _case("case:b"))
    manifest = writer.finalize(
        expected_hybrid_case_ids=set(),
        expected_baseline_case_ids={"case:b"},
        policy={
            "observability_seed": 0,
            "gnn_arm": "sage",
            "surrounding_results_seeds": [0, 1, 2],
            "inspections_per_day": 5,
        },
        summary={
            "overlap_ids_available": True,
            "baseline_recovered": 1,
            "recovered_by_both": 0,
            "hybrid_only_recovered": 0,
            "baseline_only_recovered": 1,
            "hybrid_total": 0,
            "net_gain": -1,
        },
    )
    source_bundle = diagnostics / "recovery" / manifest["bundle_path"]
    (source_bundle / "orphan.json").write_text("{}", encoding="utf-8")

    v9_recovery_sidecars.publish_prepackaged_manifest(
        manifest, diagnostics / "demo.json", tmp_path / "dashboard"
    )

    target = tmp_path / "dashboard" / manifest["bundle_path"]
    assert not (target / "orphan.json").exists()


def test_clone_runtime_fallback_preflights_before_physical_copy(
    tmp_path, monkeypatch
):
    diagnostics = tmp_path / "diagnostics"
    writer = RecoveryBundleWriter(
        tmp_path / "stage",
        diagnostics / "recovery",
        run_fingerprint={"run_identity": {"checkpoint_id": "abc"}},
        sidecar_prefix="recovery",
    )
    writer.write_community(_community())
    writer.write_case("baseline_only", _case("case:b"))
    manifest = writer.finalize(
        expected_hybrid_case_ids=set(),
        expected_baseline_case_ids={"case:b"},
        policy={
            "observability_seed": 0,
            "gnn_arm": "sage",
            "surrounding_results_seeds": [0, 1, 2],
            "inspections_per_day": 5,
        },
        summary={
            "overlap_ids_available": True,
            "baseline_recovered": 1,
            "recovered_by_both": 0,
            "hybrid_only_recovered": 0,
            "baseline_only_recovered": 1,
            "hybrid_total": 0,
            "net_gain": -1,
        },
    )
    physical_copies = []

    def unsupported_clone(source, destination):
        raise OSError(v9_recovery_sidecars.errno.ENOTSUP, "unsupported")

    monkeypatch.setattr(
        v9_recovery_sidecars.os, "clonefile", unsupported_clone, raising=False
    )
    monkeypatch.setattr(
        v9_recovery_sidecars.shutil,
        "disk_usage",
        lambda path: v9_recovery_sidecars.shutil._ntuple_diskusage(1, 1, 0),
    )
    monkeypatch.setattr(
        v9_recovery_sidecars.shutil,
        "copy2",
        lambda source, destination: physical_copies.append((source, destination)),
    )

    with pytest.raises(ValueError, match="insufficient free space"):
        v9_recovery_sidecars.publish_prepackaged_manifest(
            manifest, diagnostics / "demo.json", tmp_path / "dashboard"
        )

    assert physical_copies == []


def test_legacy_sidecar_packager_caps_input_before_community_materialization(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(v9_recovery_sidecars, "_validate_artifact", lambda value: None)
    artifact = {
        "communities": {
            f"community:{index}": {"community_key": f"community:{index}"}
            for index in range(101)
        }
    }

    with pytest.raises(ValueError, match="legacy sidecar package limit"):
        v9_recovery_sidecars.package_recovery_sidecars(
            artifact, tmp_path / "legacy"
        )


@pytest.mark.parametrize("nested_field", ["nodes", "edges"])
def test_legacy_packager_counts_nested_expansion_evidence_before_materializing(
    tmp_path, monkeypatch, nested_field
):
    monkeypatch.setattr(v9_recovery_sidecars, "_validate_artifact", lambda value: None)
    expansion = {"nodes": [], "edges": []}
    expansion[nested_field] = [{} for _ in range(10_001)]
    artifact = {
        "communities": [
            {
                "nodes": [],
                "edges": [],
                "provenance_expansions": [expansion],
            }
        ]
    }

    with pytest.raises(ValueError, match="legacy sidecar package limit"):
        v9_recovery_sidecars.package_recovery_sidecars(
            artifact, tmp_path / "legacy"
        )


@pytest.mark.parametrize("nested_field", ["observations", "source_row_ids"])
def test_legacy_packager_counts_nested_edge_rows_before_materializing(
    tmp_path, monkeypatch, nested_field
):
    monkeypatch.setattr(v9_recovery_sidecars, "_validate_artifact", lambda value: None)
    edge = {nested_field: [f"row:{index}" for index in range(10_001)]}
    artifact = {
        "communities": [
            {"nodes": [], "edges": [edge], "provenance_expansions": []}
        ]
    }

    with pytest.raises(ValueError, match="legacy sidecar package limit"):
        v9_recovery_sidecars.package_recovery_sidecars(
            artifact, tmp_path / "legacy"
        )


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
