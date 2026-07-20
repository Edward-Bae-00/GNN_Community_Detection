#!/usr/bin/env python3
"""Publish schema-2 recovery evidence as deterministic lazy-load sidecars."""
from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path


def _canonical_bytes(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _safe_slug(value: str) -> str:
    slug = "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in value
    ).strip("-")
    return slug[:80] or "item"


def _write_content_addressed(root: Path, folder: str, stem: str, payload: dict):
    content = _canonical_bytes(payload)
    digest = hashlib.sha256(content).hexdigest()
    relative = Path(folder) / f"{_safe_slug(stem)}-{digest[:16]}.json"
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_bytes() != content:
            raise ValueError(f"content-address collision at {destination}")
    else:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, destination)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
    return {
        "path": relative.as_posix(),
        "sha256": digest,
        "bytes": len(content),
    }


def _write_atomic_file(destination: Path, content: bytes):
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _chunks(values, size):
    for offset in range(0, len(values), size):
        yield offset, values[offset:offset + size]


def _community_key(value: dict) -> str:
    explicit = value.get("community_key")
    if isinstance(explicit, str) and explicit:
        return explicit
    scoring_day = value.get("scoring_day")
    component_id = value.get("component_id")
    if isinstance(scoring_day, str) and isinstance(component_id, str):
        return f"{scoring_day}:{component_id}"
    raise ValueError("community requires community_key or scoring_day/component_id")


def _sorted_records(records, keys):
    if not isinstance(records, list):
        raise ValueError("community record collection must be a list")
    return sorted(
        records,
        key=lambda item: tuple(str(item.get(key, "")) for key in keys),
    )


def _validate_artifact(artifact):
    if not isinstance(artifact, dict) or artifact.get("schema_version") != "2.0":
        raise ValueError("recovery artifact must use schema_version 2.0")
    policy = artifact.get("policy")
    if not isinstance(policy, dict) or policy.get("observability_seed") != 0:
        raise ValueError("recovery policy must use observability seed 0")
    if policy.get("inspections_per_day") != 5:
        raise ValueError("recovery policy must use K=5 inspections per day")
    if policy.get("gnn_arm") != "sage":
        raise ValueError("recovery policy must use the SAGE arm")
    if policy.get("surrounding_results_seeds") != [0, 1, 2]:
        raise ValueError("recovery policy must use surrounding seeds [0, 1, 2]")

    cohorts = artifact.get("cohorts")
    if not isinstance(cohorts, dict):
        raise ValueError("recovery cohorts are missing")
    hybrid = cohorts.get("hybrid_only")
    baseline = cohorts.get("baseline_only")
    if not isinstance(hybrid, list) or not isinstance(baseline, list):
        raise ValueError("recovery cohorts must contain both named lists")
    cohort_ids = {}
    for cohort_name, cases in (("hybrid_only", hybrid), ("baseline_only", baseline)):
        for case in cases:
            if not isinstance(case, dict):
                raise ValueError("recovery cohort cases must be objects")
            case_id = case.get("case_id")
            community_key = case.get("community_key")
            if (
                not isinstance(case_id, str)
                or not case_id
                or not isinstance(community_key, str)
                or not community_key
                or case_id in cohort_ids
            ):
                raise ValueError("recovery cohort case identities are invalid")
            cohort_ids[case_id] = (cohort_name, community_key)

    summary = artifact.get("summary")
    overlap_fields = (
        "baseline_recovered",
        "recovered_by_both",
        "hybrid_only_recovered",
        "baseline_only_recovered",
        "hybrid_total",
        "net_gain",
    )
    if not isinstance(summary, dict) or any(
        type(summary.get(field)) is not int for field in overlap_fields
    ):
        raise ValueError("recovery overlap summary is invalid")
    if (
        min(summary[field] for field in overlap_fields[:-1]) < 0
        or summary["hybrid_only_recovered"] != len(hybrid)
        or summary["baseline_only_recovered"] != len(baseline)
        or summary["baseline_recovered"]
        != summary["recovered_by_both"] + summary["baseline_only_recovered"]
        or summary["hybrid_total"]
        != summary["recovered_by_both"] + summary["hybrid_only_recovered"]
        or summary["net_gain"]
        != summary["hybrid_total"] - summary["baseline_recovered"]
    ):
        raise ValueError("recovery overlap algebra is inconsistent")

    coverage = artifact.get("coverage")
    if not isinstance(coverage, dict):
        raise ValueError("recovery coverage is missing")
    required = (
        "hybrid_only_count",
        "baseline_only_count",
        "explained_count",
        "llm_validated_count",
        "failed_count",
    )
    if any(type(coverage.get(key)) is not int or coverage[key] < 0 for key in required):
        raise ValueError("recovery coverage counts are invalid")
    if (
        coverage.get("complete") is not True
        or coverage["hybrid_only_count"] != len(hybrid)
        or coverage["baseline_only_count"] != len(baseline)
        or coverage["explained_count"] != coverage["hybrid_only_count"]
        or coverage["llm_validated_count"] != coverage["hybrid_only_count"]
        or coverage["failed_count"] != 0
    ):
        raise ValueError("recovery coverage is incomplete")

    case_index = artifact.get("case_index")
    community_index = artifact.get("community_index")
    if case_index is not None or community_index is not None or artifact.get("bundle_id"):
        if not isinstance(case_index, dict) or set(case_index) != set(cohort_ids):
            raise ValueError("recovery case index coverage is invalid")
        if not isinstance(community_index, dict):
            raise ValueError("recovery community index is invalid")
        for case_id, (cohort_name, community_key) in cohort_ids.items():
            record = case_index[case_id]
            if (
                not isinstance(record, dict)
                or record.get("cohort") != cohort_name
                or record.get("community_key") != community_key
                or community_key not in community_index
            ):
                raise ValueError("recovery case index identity is inconsistent")


def _verify_reference(bundle_root: Path, reference: dict):
    if not isinstance(reference, dict):
        raise ValueError("sidecar reference must be an object")
    relative = reference.get("path")
    expected = reference.get("sha256")
    if not isinstance(relative, str) or not isinstance(expected, str):
        raise ValueError("sidecar reference requires path and sha256")
    path = bundle_root / relative
    try:
        path.resolve().relative_to(bundle_root.resolve())
    except ValueError as error:
        raise ValueError(f"sidecar reference escapes bundle: {relative}") from error
    if not path.is_file():
        raise ValueError(f"missing sidecar {relative}")
    content = path.read_bytes()
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected:
        raise ValueError(f"sidecar hash mismatch for {relative}")
    expected_bytes = reference.get("bytes")
    if expected_bytes is not None and expected_bytes != len(content):
        raise ValueError(f"sidecar byte count mismatch for {relative}")
    try:
        return json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"sidecar is not valid JSON: {relative}") from error


_COMPACT_CHUNK_SPECS = (
    ("node_chunks", "nodes", "node_count"),
    ("edge_chunks", "edges", "edge_count"),
    ("provenance_chunks", "observations", "provenance_observation_count"),
    ("provenance_expansion_membership_chunks", "memberships", None),
)


def _verify_compact_chunks(bundle_root, owner, label, catalog_ids=None):
    if not isinstance(owner, dict) or owner.get("complete") is not True:
        raise ValueError(f"{label} is incomplete")
    verified = set()
    for field, row_field, count_field in _COMPACT_CHUNK_SPECS:
        references = owner.get(field)
        if not isinstance(references, list):
            raise ValueError(f"{label} lacks {field}")
        expected_offset = 0
        for reference in references:
            payload = _verify_reference(bundle_root, reference)
            rows = payload.get(row_field) if isinstance(payload, dict) else None
            if (
                not isinstance(rows, list)
                or payload.get("offset") != expected_offset
                or payload.get("count") != len(rows)
                or reference.get("offset") != expected_offset
                or reference.get("count") != len(rows)
            ):
                raise ValueError(f"{label} {field} metadata is invalid")
            expected_offset += len(rows)
            verified.add(reference["path"])
            if catalog_ids is not None and field != "provenance_expansion_membership_chunks":
                kind = {
                    "node_chunks": "nodes",
                    "edge_chunks": "edges",
                    "provenance_chunks": "provenance",
                }[field]
                referenced_ids = {
                    row.get("catalog_id") if isinstance(row, dict) else None
                    for row in rows
                }
                if None in referenced_ids or not referenced_ids.issubset(
                    catalog_ids[kind]
                ):
                    raise ValueError(f"{label} {field} catalog reference is invalid")
        if count_field is not None and owner.get(count_field) != expected_offset:
            raise ValueError(f"{label} {count_field} is invalid")
    return verified


def _case_reference(record):
    if isinstance(record, dict) and isinstance(record.get("ref"), dict):
        return record["ref"]
    return record


def _verify_catalog_index(bundle_root, manifest):
    index = manifest.get("catalog_index")
    if not isinstance(index, dict):
        raise ValueError("recovery manifest catalog_index is invalid")
    verified = set()
    record_ids = {}
    for kind in ("nodes", "edges", "provenance"):
        catalog = index.get(kind)
        if not isinstance(catalog, dict) or not isinstance(catalog.get("chunks"), list):
            raise ValueError(f"recovery catalog {kind!r} is invalid")
        expected_offset = 0
        ids = []
        for reference in catalog["chunks"]:
            payload = _verify_reference(bundle_root, reference)
            records = payload.get("records") if isinstance(payload, dict) else None
            chunk_ids = [
                record.get("record_id") if isinstance(record, dict) else None
                for record in records or ()
            ]
            if (
                payload.get("catalog_kind") != kind
                or not isinstance(records, list)
                or any(not isinstance(record, dict) for record in records)
                or chunk_ids != sorted(set(chunk_ids))
                or payload.get("offset") != expected_offset
                or payload.get("count") != len(records)
                or reference.get("offset") != expected_offset
                or reference.get("count") != len(records)
                or len(records) > catalog.get("chunk_size", 0)
                or (records and reference.get("first_id") != chunk_ids[0])
                or (records and reference.get("last_id") != chunk_ids[-1])
            ):
                raise ValueError(f"recovery catalog {kind!r} chunk is invalid")
            expected_offset += len(records)
            ids.extend(chunk_ids)
            verified.add(reference["path"])
        if expected_offset != catalog.get("record_count") or ids != sorted(set(ids)):
            raise ValueError(f"recovery catalog {kind!r} count is invalid")
        record_ids[kind] = frozenset(ids)
    return verified, record_ids


def _verify_prepackaged_references(bundle_root, manifest):
    verified, catalog_ids = _verify_catalog_index(bundle_root, manifest)
    for case_id, record in manifest["case_index"].items():
        reference = _case_reference(record)
        payload = _verify_reference(bundle_root, reference)
        verified.add(reference["path"])
        if not isinstance(payload, dict):
            raise ValueError(f"case {case_id!r} payload is invalid")
        case = payload.get("case")
        if (
            not isinstance(case, dict)
            or case.get("case_id") != case_id
            or payload.get("cohort") != record.get("cohort")
            or payload.get("community_key") != record.get("community_key")
            or case.get("community_key") != record.get("community_key")
        ):
            raise ValueError(f"case {case_id!r} identity is invalid")
        overlay = payload.get("overlay_evidence")
        if overlay is not None:
            verified.update(
                _verify_compact_chunks(
                    bundle_root, overlay, f"case {case_id!r} overlay"
                )
            )
    for community_key, reference in manifest["community_index"].items():
        community = _verify_reference(bundle_root, reference)
        if not isinstance(community, dict) or community.get("community_key") != community_key:
            raise ValueError(f"community {community_key!r} identity is invalid")
        verified.add(reference["path"])
        verified.update(
            _verify_compact_chunks(
                bundle_root,
                community,
                f"community {community_key!r}",
                catalog_ids,
            )
        )
        day_view = community.get("day_view", {})
        if not isinstance(day_view, dict):
            raise ValueError(f"community {community_key!r} day_view is invalid")
        for field in ("node_status_chunks", "edge_membership_chunks"):
            references = day_view.get(field, [])
            if not isinstance(references, list):
                raise ValueError(
                    f"community {community_key!r} {field} is invalid"
                )
            for chunk_reference in references:
                _verify_reference(bundle_root, chunk_reference)
                verified.add(chunk_reference["path"])
        catalogs = community.get("catalogs")
        if not isinstance(catalogs, dict):
            raise ValueError(f"community {community_key!r} catalogs are invalid")
        if catalogs.get("scope") != "run_global" or any(
            type(catalogs.get(field)) is not int or catalogs[field] < 0
            for field in ("node_count", "edge_count", "provenance_count")
        ):
            raise ValueError(f"community {community_key!r} catalogs are invalid")
    return verified


_COW_CLONE_FALLBACK_ERRNOS = {
    errno.EXDEV,
    errno.EACCES,
    errno.EPERM,
    getattr(errno, "ENOSYS", -1),
    getattr(errno, "ENOTSUP", -1),
    getattr(errno, "EOPNOTSUPP", -1),
}
def publish_prepackaged_manifest(manifest, source_path, output_dir):
    """Atomically stage a validated producer bundle and publish its pointer last."""
    _validate_artifact(manifest)
    if not all(
        isinstance(manifest.get(key), dict)
        for key in ("case_index", "community_index")
    ):
        raise ValueError("prepackaged recovery manifest lacks indexes")
    bundle_id = manifest.get("bundle_id")
    bundle_path = manifest.get("bundle_path")
    sidecar_base = manifest.get("sidecar_base")
    if not all(isinstance(value, str) and value for value in (
        bundle_id, bundle_path, sidecar_base
    )):
        raise ValueError("prepackaged recovery manifest lacks bundle identity")
    if (
        re.fullmatch(r"[0-9a-f]{24}", bundle_id) is None
        or bundle_path != f"bundles/{bundle_id}"
        or sidecar_base != f"recovery/{bundle_path}/"
    ):
        raise ValueError("prepackaged recovery manifest lacks canonical bundle identity")
    source_parent = Path(source_path).parent
    source_bundle = source_parent / sidecar_base
    try:
        source_bundle.resolve().relative_to(source_parent.resolve())
    except ValueError as error:
        raise ValueError("prepackaged sidecar_base escapes artifact directory") from error
    if not source_bundle.is_dir():
        raise ValueError(f"prepackaged recovery bundle is missing: {source_bundle}")
    manifest_content = _canonical_bytes(manifest)
    source_manifest = source_bundle / "manifest.json"
    if not source_manifest.is_file() or source_manifest.read_bytes() != manifest_content:
        raise ValueError("source manifest bytes do not match the supplied manifest")
    verified_relative_paths = _verify_prepackaged_references(
        source_bundle, manifest
    )

    root = Path(output_dir)
    required_bytes = sum(
        (source_bundle / relative).stat().st_size
        for relative in verified_relative_paths
    ) + len(manifest_content)
    physical_preflight_complete = False

    def preflight_physical_copy():
        nonlocal physical_preflight_complete
        if physical_preflight_complete:
            return
        probe = root
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        available_bytes = shutil.disk_usage(probe).free
        if available_bytes < required_bytes:
            raise ValueError(
                "insufficient free space for physical recovery bundle copy: "
                f"required={required_bytes}, available={available_bytes}"
            )
        physical_preflight_complete = True

    clonefile = getattr(os, "clonefile", None)
    if not callable(clonefile):
        preflight_physical_copy()
    root.mkdir(parents=True, exist_ok=True)
    final_bundle = root / bundle_path
    try:
        final_bundle.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise ValueError("prepackaged bundle_path escapes output directory") from error
    stage = Path(tempfile.mkdtemp(prefix=".bundle-stage-", dir=root))
    try:
        for relative in sorted(verified_relative_paths):
            source = source_bundle / relative
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if callable(clonefile):
                try:
                    clonefile(source, destination)
                except OSError as error:
                    if error.errno not in _COW_CLONE_FALLBACK_ERRNOS:
                        raise
                    destination.unlink(missing_ok=True)
                    preflight_physical_copy()
                    shutil.copy2(source, destination)
                else:
                    if source.stat().st_ino == destination.stat().st_ino:
                        destination.unlink()
                        preflight_physical_copy()
                        shutil.copy2(source, destination)
                    else:
                        shutil.copystat(source, destination)
            else:
                shutil.copy2(source, destination)
        _write_atomic_file(stage / "manifest.json", manifest_content)
        bundle_pointer = {
            "bundle_id": bundle_id,
            "bundle_path": bundle_path,
            "manifest_sha256": hashlib.sha256(manifest_content).hexdigest(),
        }
        _write_atomic_file(
            stage / "current.json", _canonical_bytes(bundle_pointer)
        )
        _verify_prepackaged_references(stage, manifest)
        if (stage / "manifest.json").read_bytes() != manifest_content:
            raise ValueError("copied source manifest verification failed")
        final_bundle.parent.mkdir(parents=True, exist_ok=True)
        if final_bundle.exists():
            shutil.rmtree(stage)
            existing_manifest = final_bundle / "manifest.json"
            if (
                not existing_manifest.is_file()
                or existing_manifest.read_bytes() != manifest_content
            ):
                raise ValueError("published source manifest does not match")
            _verify_prepackaged_references(final_bundle, manifest)
        else:
            os.replace(stage, final_bundle)
        _write_atomic_file(
            root / "current.json", _canonical_bytes(bundle_pointer)
        )
        return manifest
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise


def _community_sources(artifact):
    sources = artifact.get("communities", [])
    if isinstance(sources, dict):
        sources = [dict(value, community_key=key) for key, value in sources.items()]
    if not isinstance(sources, list):
        raise ValueError("communities must be a list or object")
    by_key = {}
    for source in sources:
        if not isinstance(source, dict) or source.get("complete") is not True:
            raise ValueError("every published community must be complete")
        key = _community_key(source)
        canonical = _canonical_bytes(source)
        if key in by_key and _canonical_bytes(by_key[key]) != canonical:
            raise ValueError(f"community key {key!r} maps to conflicting payloads")
        by_key[key] = source
    for explanation in artifact.get("explanations", []):
        community = explanation.get("community") if isinstance(explanation, dict) else None
        if isinstance(community, dict):
            merged = dict(community)
            for key in ("community_key", "scoring_day", "component_id"):
                if key not in merged and key in explanation:
                    merged[key] = explanation[key]
            community_key = _community_key(merged)
            if community_key not in by_key:
                by_key[community_key] = merged
    return by_key


def _publish_community(root, key, community, chunk_size):
    expansions = community.get("provenance_expansions", [])
    if not isinstance(expansions, list):
        raise ValueError("community provenance_expansions must be a list")
    node_records = list(community.get("nodes", []))
    edge_records = [(edge, None) for edge in community.get("edges", [])]
    expansion_index = []
    for expansion in expansions:
        if not isinstance(expansion, dict) or not isinstance(
            expansion.get("expansion_id"), str
        ):
            raise ValueError("provenance expansion requires expansion_id")
        expansion_id = expansion["expansion_id"]
        expansion_nodes = expansion.get("nodes", [])
        expansion_edges = expansion.get("edges", [])
        if not isinstance(expansion_nodes, list) or not isinstance(expansion_edges, list):
            raise ValueError("provenance expansion nodes and edges must be lists")
        node_records.extend(expansion_nodes)
        edge_records.extend((edge, expansion_id) for edge in expansion_edges)
        expansion_index.append({
            "expansion_id": expansion_id,
            "label": expansion.get("label"),
            "node_ids": sorted(str(node.get("node_id")) for node in expansion_nodes),
            "edge_ids": sorted(str(edge.get("edge_id")) for edge in expansion_edges),
        })
    nodes_by_id = {}
    for node in node_records:
        if not isinstance(node, dict) or not isinstance(node.get("node_id"), str):
            raise ValueError("community node requires node_id")
        existing = nodes_by_id.get(node["node_id"])
        if existing is not None and _canonical_bytes(existing) != _canonical_bytes(node):
            raise ValueError(f"conflicting community node {node['node_id']!r}")
        nodes_by_id[node["node_id"]] = node
    nodes = _sorted_records(list(nodes_by_id.values()), ("node_id",))
    edges = []
    provenance = []
    for edge, expansion_id in edge_records:
        if not isinstance(edge, dict) or not isinstance(edge.get("edge_id"), str):
            raise ValueError("community edge requires edge_id")
        observations = edge.get("observations")
        source_row_ids = edge.get("source_row_ids")
        if not isinstance(observations, list) or not observations:
            raise ValueError("community edge requires provenance observations")
        if not isinstance(source_row_ids, list) or not source_row_ids:
            raise ValueError("community edge requires source_row_ids")
        if edge.get("source_row_count", len(source_row_ids)) != len(source_row_ids):
            raise ValueError("community edge source_row_count disagrees with source_row_ids")
        cleaned = {key: value for key, value in edge.items() if key != "observations"}
        cleaned["source_row_count"] = len(source_row_ids)
        if expansion_id is not None:
            cleaned["provenance_expansion_id"] = expansion_id
        edges.append(cleaned)
        for observation in observations:
            if not isinstance(observation, dict):
                raise ValueError("edge provenance observation must be an object")
            row = dict(observation, edge_id=edge["edge_id"])
            if expansion_id is not None:
                row["provenance_expansion_id"] = expansion_id
            provenance.append(row)
    edges = _sorted_records(edges, ("edge_id", "u", "v", "edge_type"))
    provenance = _sorted_records(
        provenance,
        ("edge_id", "source_row_id", "available_time"),
    )
    edge_refs = []
    for offset, rows in _chunks(edges, chunk_size):
        ref = _write_content_addressed(
            root,
            "communities/edges",
            f"{key}-edges-{offset}",
            {"offset": offset, "count": len(rows), "edges": rows},
        )
        edge_refs.append({**ref, "offset": offset, "count": len(rows)})
    provenance_refs = []
    for offset, rows in _chunks(provenance, chunk_size):
        ref = _write_content_addressed(
            root,
            "communities/provenance",
            f"{key}-provenance-{offset}",
            {"offset": offset, "count": len(rows), "observations": rows},
        )
        provenance_refs.append({**ref, "offset": offset, "count": len(rows)})
    manifest = {
        "schema_version": "1.0",
        "community_key": key,
        "complete": True,
        "clustered": community.get("clustered", True),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "provenance_observation_count": len(provenance),
        "nodes": nodes,
        "provenance_expansions": sorted(
            expansion_index, key=lambda item: item["expansion_id"]
        ),
        "edge_chunks": edge_refs,
        "provenance_chunks": provenance_refs,
    }
    return _write_content_addressed(root, "communities", key, manifest)


def package_recovery_sidecars(artifact, output_dir, *, chunk_size=250):
    """Stage a versioned bundle, then atomically publish its pointer last."""
    raw_communities = artifact.get("communities") if isinstance(artifact, dict) else None
    if isinstance(raw_communities, (dict, list)):
        if len(raw_communities) > 100:
            raise ValueError(
                "legacy sidecar package limit exceeded; use the streaming bundle"
            )
        community_values = (
            raw_communities.values()
            if isinstance(raw_communities, dict)
            else raw_communities
        )
        for community in community_values:
            if not isinstance(community, dict):
                continue
            cost = sum(
                len(community.get(field, ())) for field in ("nodes", "edges")
            )
            edges = list(community.get("edges", ()))
            for edge in edges:
                if isinstance(edge, dict):
                    cost += sum(
                        len(edge.get(field, ()))
                        for field in ("observations", "source_row_ids")
                    )
            expansions = community.get("provenance_expansions", ())
            cost += len(expansions)
            for expansion in expansions:
                if not isinstance(expansion, dict):
                    continue
                expansion_nodes = expansion.get("nodes", ())
                expansion_edges = expansion.get("edges", ())
                cost += len(expansion_nodes) + len(expansion_edges)
                for edge in expansion_edges:
                    if isinstance(edge, dict):
                        cost += sum(
                            len(edge.get(field, ()))
                            for field in ("observations", "source_row_ids")
                        )
            if cost > 10_000:
                raise ValueError(
                    "legacy sidecar package limit exceeded; use the streaming bundle"
                )
    _validate_artifact(artifact)
    if type(chunk_size) is not int or chunk_size < 1:
        raise ValueError("chunk_size must be a positive integer")
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    bundle_id = hashlib.sha256(_canonical_bytes({
        "format": "recovery-sidecars-v2",
        "chunk_size": chunk_size,
        "artifact": artifact,
    })).hexdigest()[:24]
    bundle_path = Path("bundles") / bundle_id
    final_bundle = root / bundle_path
    stage = Path(tempfile.mkdtemp(prefix=".bundle-stage-", dir=root))
    try:
        communities = _community_sources(artifact)
        community_index = {
            key: _publish_community(stage, key, communities[key], chunk_size)
            for key in sorted(communities)
        }
        explanations = {
            item.get("case_id"): item
            for item in artifact.get("explanations", [])
            if isinstance(item, dict) and isinstance(item.get("case_id"), str)
        }
        case_index = {}
        lightweight_cohorts = {"hybrid_only": [], "baseline_only": []}
        seen_case_ids = set()
        for cohort in ("hybrid_only", "baseline_only"):
            for case in artifact["cohorts"][cohort]:
                if not isinstance(case, dict) or not isinstance(case.get("case_id"), str):
                    raise ValueError("each recovery case requires a case_id")
                case_id = case["case_id"]
                if case_id in seen_case_ids:
                    raise ValueError(f"duplicate recovery case_id {case_id!r}")
                seen_case_ids.add(case_id)
                community_key = _community_key(case)
                if community_key not in community_index:
                    raise ValueError(f"case {case_id!r} has no complete community")
                explanation = explanations.get(case_id)
                if cohort == "hybrid_only" and not isinstance(explanation, dict):
                    raise ValueError(f"Hybrid-only case {case_id!r} has no explanation")
                if cohort == "hybrid_only":
                    narrative = explanation.get("llm_narrative")
                    valid_narrative = (
                        isinstance(narrative, dict)
                        and narrative.get("validated") is True
                        and narrative.get("source") == "llm"
                        and isinstance(narrative.get("model"), str)
                        and "gemma" in narrative["model"].lower()
                        and isinstance(narrative.get("summary"), str)
                        and bool(narrative["summary"].strip())
                    )
                    if not valid_narrative:
                        raise ValueError(
                            f"Hybrid-only case {case_id!r} lacks a validated local Gemma narrative"
                        )
                payload = {
                    "schema_version": "1.0",
                    "cohort": cohort,
                    "case": case,
                    "community_key": community_key,
                    "explanation": explanation if cohort == "hybrid_only" else None,
                    "explanation_policy": (
                        "validated-local-gemma"
                        if cohort == "hybrid_only"
                        else "not-generated-for-baseline-only"
                    ),
                }
                ref = _write_content_addressed(stage, "cases", case_id, payload)
                case_index[case_id] = {
                    **ref,
                    "cohort": cohort,
                    "community_key": community_key,
                }
                lightweight_cohorts[cohort].append(case)

        manifest = {
            "schema_version": "2.0",
            "policy": artifact["policy"],
            "summary": artifact.get("summary", {}),
            "coverage": artifact["coverage"],
            "cohorts": lightweight_cohorts,
            "case_index": case_index,
            "community_index": community_index,
            "bundle_id": bundle_id,
            "bundle_path": bundle_path.as_posix(),
            "sidecar_base": f"recovery/{bundle_path.as_posix()}/",
        }
        manifest_content = _canonical_bytes(manifest)
        (stage / "manifest.json").write_bytes(manifest_content)
        for path in stage.rglob("*.json"):
            json.loads(path.read_text())
        final_bundle.parent.mkdir(parents=True, exist_ok=True)
        if final_bundle.exists():
            if (final_bundle / "manifest.json").read_bytes() != manifest_content:
                raise ValueError("existing recovery bundle manifest disagrees")
            shutil.rmtree(stage)
        else:
            os.replace(stage, final_bundle)
        pointer = {
            "bundle_id": bundle_id,
            "bundle_path": bundle_path.as_posix(),
            "manifest_sha256": hashlib.sha256(manifest_content).hexdigest(),
        }
        _write_atomic_file(root / "current.json", _canonical_bytes(pointer))
        return manifest
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
