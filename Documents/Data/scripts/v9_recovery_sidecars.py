#!/usr/bin/env python3
"""Publish schema-2 recovery evidence as deterministic lazy-load sidecars."""
from __future__ import annotations

import errno
import hashlib
import json
import os
import posixpath
import re
import shutil
import tempfile
import zipfile
from pathlib import Path


def _canonical_bytes(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _safe_zip_member_name(name: str) -> str:
    """Return a canonical relative ZIP member name or reject it."""
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise ValueError("ZIP member path is unsafe")
    name = name.rstrip("/")
    if not name or name.startswith("/"):
        raise ValueError("ZIP member path is unsafe")
    parts = name.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("ZIP member path is unsafe")
    if posixpath.normpath(name) != name:
        raise ValueError("ZIP member path is unsafe")
    return name


class _ZipBundleRoot:
    """Read verified bundle members directly from a ZIP archive."""

    def __init__(self, archive, members, prefix):
        self.archive = archive
        self.members = members
        self.prefix = prefix.rstrip("/")

    def _member(self, relative):
        relative = _safe_zip_member_name(relative)
        name = f"{self.prefix}/{relative}" if self.prefix else relative
        info = self.members.get(name)
        if info is None or info.is_dir():
            raise ValueError(f"missing ZIP bundle member {relative}")
        if _zip_member_is_symlink(info):
            raise ValueError(f"ZIP bundle member is a symlink: {relative}")
        return info

    def read_member(self, relative):
        info = self._member(relative)
        with self.archive.open(info, "r") as source:
            return source.read()

    def open_member(self, relative):
        return self.archive.open(self._member(relative), "r")


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
    if isinstance(artifact, dict) and artifact.get("schema_version") == "3.0":
        return _validate_schema3_artifact(artifact)
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


def _validate_schema3_artifact(artifact):
    """Validate the partial-coverage producer artifact before sidecar staging."""
    if not isinstance(artifact, dict) or artifact.get("schema_version") != "3.0":
        raise ValueError("recovery artifact must use schema_version 3.0")
    policy = artifact.get("policy")
    if not isinstance(policy, dict) or policy.get("observability_seed") != 0:
        raise ValueError("schema-3 recovery policy is invalid")
    if policy.get("gnn_arm") != "sage" or policy.get("inspections_per_day") != 5:
        raise ValueError("schema-3 recovery policy is invalid")

    cohorts = artifact.get("cohorts")
    if not isinstance(cohorts, dict) or set(cohorts) != {
        "hybrid_only", "baseline_only", "recovered_by_both"
    }:
        raise ValueError("schema-3 cohorts are incomplete")
    records = {}
    for cohort, values in cohorts.items():
        if not isinstance(values, list):
            raise ValueError("schema-3 cohort must be a list")
        for record in values:
            if not isinstance(record, dict):
                raise ValueError("schema-3 cohort record must be an object")
            case_id = record.get("case_id")
            if not isinstance(case_id, str) or not case_id.strip():
                raise ValueError("schema-3 case_id is invalid")
            if case_id in records:
                raise ValueError("schema-3 case IDs must be globally unique")
            if record.get("cohort") != cohort:
                raise ValueError("schema-3 cohort identity is inconsistent")
            if not isinstance(record.get("person_id"), str) or not record["person_id"].strip():
                raise ValueError("schema-3 person identity is invalid")
            records[case_id] = record

    summary = artifact.get("summary")
    summary_fields = (
        "baseline_recovered", "recovered_by_both", "hybrid_only_recovered",
        "baseline_only_recovered", "hybrid_total", "net_gain",
    )
    if not isinstance(summary, dict) or any(type(summary.get(field)) is not int for field in summary_fields):
        raise ValueError("schema-3 overlap summary is invalid")
    if (
        min(summary[field] for field in summary_fields[:-1]) < 0
        or summary["hybrid_only_recovered"] != len(cohorts["hybrid_only"])
        or summary["baseline_only_recovered"] != len(cohorts["baseline_only"])
        or summary["baseline_recovered"] != summary["recovered_by_both"] + summary["baseline_only_recovered"]
        or summary["hybrid_total"] != summary["recovered_by_both"] + summary["hybrid_only_recovered"]
        or summary["net_gain"] != summary["hybrid_total"] - summary["baseline_recovered"]
    ):
        raise ValueError("schema-3 overlap algebra is inconsistent")

    selection = artifact.get("selection")
    selected = selection.get("selected_ids") if isinstance(selection, dict) else None
    if not isinstance(selection, dict) or not isinstance(selected, dict) or set(selected) != {
        "hybrid_only", "baseline_only", "recovered_by_both"
    }:
        raise ValueError("schema-3 selection is incomplete")
    selected_sets = {}
    for cohort, values in selected.items():
        if (
            not isinstance(values, list)
            or any(not isinstance(value, str) or not value.strip() for value in values)
            or len(values) != len(set(values))
            or any(value not in records for value in values)
        ):
            raise ValueError("schema-3 selected IDs are invalid")
        if cohort == "recovered_by_both" and values:
            raise ValueError("schema-3 recovered_by_both cannot be selected")
        selected_sets[cohort] = set(values)

    fallback_ids = selection.get("hybrid_structural_fallback_ids", [])
    if (
        not isinstance(fallback_ids, list)
        or any(not isinstance(value, str) or not value.strip() for value in fallback_ids)
        or len(fallback_ids) != len(set(fallback_ids))
    ):
        raise ValueError("schema-3 structural fallback IDs are invalid")
    fallback_set = set(fallback_ids)
    hybrid_ids = {record["case_id"] for record in cohorts["hybrid_only"]}
    if not fallback_set <= hybrid_ids or fallback_set & selected_sets["hybrid_only"]:
        raise ValueError("schema-3 structural fallback IDs are invalid")

    detail_index = artifact.get("detail_index", {})
    community_index = artifact.get("community_index", {})
    if not isinstance(detail_index, dict) or not isinstance(community_index, dict):
        raise ValueError("schema-3 detail indexes are invalid")
    if not set(detail_index) <= selected_sets["hybrid_only"]:
        raise ValueError("schema-3 detail index contains an unselected case")
    if not set(community_index) <= (selected_sets["baseline_only"] | fallback_set):
        raise ValueError("schema-3 community index contains an unselected case")

    communities = artifact.get("communities")
    if not isinstance(communities, dict):
        raise ValueError("schema-3 communities are missing")
    for key, community in communities.items():
        if not isinstance(community, dict) or community.get("complete") is not True:
            raise ValueError("schema-3 communities must be complete objects")
        if community.get("community_key", key) != key:
            raise ValueError("schema-3 community key is inconsistent")

    forbidden = {
        "explanation", "overlay", "overlay_evidence", "attributions", "factors",
        "stability", "faithfulness", "mask", "masks", "node_masks", "edge_masks",
    }

    def contains_forbidden(value):
        if isinstance(value, dict):
            return bool(forbidden.intersection(value)) or any(
                contains_forbidden(child) for child in value.values()
            )
        if isinstance(value, list):
            return any(contains_forbidden(child) for child in value)
        return False

    for case_id, detail in detail_index.items():
        if not isinstance(detail, dict) or detail.get("cohort") != "hybrid_only":
            raise ValueError("schema-3 Hybrid detail identity is invalid")
        if records[case_id].get("detail_kind") != "gnn_explanation":
            raise ValueError("schema-3 Hybrid detail kind is invalid")
        if detail.get("community_key") not in communities:
            raise ValueError("schema-3 Hybrid detail community is invalid")
    for case_id, detail in community_index.items():
        expected_cohort = "hybrid_only" if case_id in fallback_set else "baseline_only"
        if not isinstance(detail, dict) or detail.get("cohort", expected_cohort) != expected_cohort:
            raise ValueError("schema-3 community detail identity is invalid")
        if records[case_id].get("community_key") not in communities:
            raise ValueError("schema-3 community detail community is invalid")
        if contains_forbidden(detail):
            raise ValueError("Baseline structural detail contains attribution evidence")

    coverage = artifact.get("coverage")
    if not isinstance(coverage, dict):
        raise ValueError("schema-3 coverage is missing")
    requested = (coverage.get("hybrid_requested"), coverage.get("baseline_requested"))
    if any(type(value) is not int or value < 0 for value in requested):
        raise ValueError("schema-3 requested coverage is invalid")
    fallback_published = len(set(community_index) & fallback_set)
    hybrid_shortfall = max(0, requested[0] - len(detail_index))
    baseline_shortfall = max(0, requested[1] - (len(community_index) - fallback_published))
    shortfall = coverage.get("shortfall")
    if (
        type(shortfall) is not int
        or shortfall < 0
        or coverage.get("hybrid_shortfall") != hybrid_shortfall
        or coverage.get("baseline_shortfall") != baseline_shortfall
        or shortfall != hybrid_shortfall + baseline_shortfall
        or (shortfall and not coverage.get("shortfall_reasons"))
    ):
        raise ValueError("schema-3 shortfall coverage is invalid")


def _verify_reference(bundle_root: Path, reference: dict):
    if not isinstance(reference, dict):
        raise ValueError("sidecar reference must be an object")
    relative = reference.get("path")
    expected = reference.get("sha256")
    if not isinstance(relative, str) or not isinstance(expected, str):
        raise ValueError("sidecar reference requires path and sha256")
    if isinstance(bundle_root, _ZipBundleRoot):
        content = bundle_root.read_member(relative)
    else:
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
                identity_field = {
                    "nodes": "node_id",
                    "edges": "edge_id",
                    "provenance": "source_row_id",
                }[kind]
                referenced_ids = {
                    row.get("catalog_id") if isinstance(row, dict) else None
                    for row in rows
                }
                if None in referenced_ids or not referenced_ids.issubset(
                    catalog_ids[kind]
                ):
                    raise ValueError(f"{label} {field} catalog reference is invalid")
                if any(
                    not isinstance(row, dict)
                    or row.get(identity_field) != row.get("catalog_id")
                    for row in rows
                ):
                    raise ValueError(f"{label} {field} identity is invalid")
        if count_field is not None and owner.get(count_field) != expected_offset:
            raise ValueError(f"{label} {count_field} is invalid")
    return verified


def _verify_schema3_day_view_chunks(bundle_root, community, label):
    if not isinstance(community, dict):
        raise ValueError(f"{label} is invalid")
    day_view = community.get("day_view")
    if day_view is None:
        return set()
    if not isinstance(day_view, dict):
        raise ValueError(f"{label} day_view is invalid")

    expected_ids = {}
    verified = set()
    base_specs = (
        ("node_chunks", "nodes", "node_id", "nodes"),
        ("edge_chunks", "edges", "edge_id", "edges"),
    )
    for field, row_field, id_field, kind in base_specs:
        references = community.get(field)
        if isinstance(references, list):
            rows_by_id = []
            for reference in references:
                payload = _verify_reference(bundle_root, reference)
                rows = payload.get(row_field) if isinstance(payload, dict) else None
                if not isinstance(rows, list):
                    raise ValueError(f"{label} {field} payload is invalid")
                ids = [
                    row.get(id_field) if isinstance(row, dict) else None
                    for row in rows
                ]
                if any(not isinstance(value, str) or not value for value in ids):
                    raise ValueError(f"{label} {field} identity is invalid")
                rows_by_id.extend(ids)
                verified.add(reference["path"])
            if len(rows_by_id) != len(set(rows_by_id)):
                raise ValueError(f"{label} {field} identity is invalid")
            expected_ids[kind] = rows_by_id
        elif field == "node_chunks" and isinstance(community.get("nodes"), list):
            ids = [
                row.get(id_field) if isinstance(row, dict) else None
                for row in community["nodes"]
            ]
            if any(not isinstance(value, str) or not value for value in ids):
                raise ValueError(f"{label} nodes identity is invalid")
            if len(ids) != len(set(ids)):
                raise ValueError(f"{label} nodes identity is invalid")
            expected_ids[kind] = ids
        else:
            raise ValueError(f"{label} lacks {field}")

    day_specs = (
        ("node_status_chunks", "node_statuses", "node_id", "nodes"),
        ("edge_membership_chunks", "edge_memberships", "edge_id", "edges"),
    )
    for field, row_field, id_field, kind in day_specs:
        references = day_view.get(field)
        if not isinstance(references, list):
            raise ValueError(f"{label} day_view {field} is invalid")
        expected_offset = 0
        day_ids = []
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
                raise ValueError(f"{label} day_view {field} metadata is invalid")
            ids = [
                row.get(id_field) if isinstance(row, dict) else None
                for row in rows
            ]
            if any(not isinstance(value, str) or not value for value in ids):
                raise ValueError(f"{label} day_view {field} identity is invalid")
            day_ids.extend(ids)
            expected_offset += len(rows)
            verified.add(reference["path"])
        if day_ids != expected_ids[kind]:
            raise ValueError(f"{label} day_view {field} identity is invalid")
        count_field = "node_count" if kind == "nodes" else "edge_count"
        if community.get(count_field) != expected_offset:
            raise ValueError(f"{label} day_view {field} count is invalid")
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
        verified.update(
            _verify_schema3_day_view_chunks(
                bundle_root, community, f"community {community_key!r}"
            )
        )
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
        or sidecar_base not in {
            f"recovery/{bundle_path}/", f"{bundle_path}/"
        }
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


def _schema3_prepackaged_reference(value):
    reference = (
        value.get("ref")
        if isinstance(value, dict) and isinstance(value.get("ref"), dict)
        else value
    )
    if (
        not isinstance(reference, dict)
        or not isinstance(reference.get("path"), str)
        or not reference["path"]
        or not isinstance(reference.get("sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", reference["sha256"])
        or type(reference.get("bytes")) is not int
        or reference["bytes"] < 0
    ):
        raise ValueError("schema-3 prepackaged reference is invalid")
    return reference


def _validate_schema3_prepackaged_manifest(manifest):
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "3.0":
        raise ValueError("schema-3 prepackaged manifest has the wrong schema")
    bundle_id = manifest.get("bundle_id")
    bundle_path = manifest.get("bundle_path")
    sidecar_base = manifest.get("sidecar_base")
    if (
        not isinstance(bundle_id, str)
        or re.fullmatch(r"[0-9a-f]{24}", bundle_id) is None
        or bundle_path != f"bundles/{bundle_id}"
        or sidecar_base != f"recovery/{bundle_path}/"
    ):
        raise ValueError("schema-3 prepackaged bundle identity is invalid")
    selection = manifest.get("selection")
    selected = selection.get("selected_ids") if isinstance(selection, dict) else None
    if (
        not isinstance(selection, dict)
        or not isinstance(selected, dict)
        or set(selected) != {"hybrid_only", "baseline_only", "recovered_by_both"}
        or selected["recovered_by_both"]
    ):
        raise ValueError("schema-3 prepackaged selection is invalid")
    selected_hybrid = selected["hybrid_only"]
    selected_baseline = selected["baseline_only"]
    if any(
        not isinstance(values, list)
        or any(not isinstance(value, str) or not value.strip() for value in values)
        or len(values) != len(set(values))
        for values in selected.values()
    ):
        raise ValueError("schema-3 prepackaged selected IDs are invalid")
    fallback = selection.get("hybrid_structural_fallback_ids", [])
    if (
        not isinstance(fallback, list)
        or any(not isinstance(value, str) or not value.strip() for value in fallback)
        or len(fallback) != len(set(fallback))
        or set(fallback) & (set(selected_hybrid) | set(selected_baseline))
    ):
        raise ValueError("schema-3 prepackaged fallback IDs are invalid")
    detail_index = manifest.get("detail_index")
    community_index = manifest.get("community_index")
    community_sidecar_index = manifest.get("community_sidecar_index")
    if not all(
        isinstance(value, dict)
        for value in (detail_index, community_index, community_sidecar_index)
    ):
        raise ValueError("schema-3 prepackaged indexes are missing")
    if not set(detail_index) <= set(selected_hybrid):
        raise ValueError("schema-3 prepackaged detail index is invalid")
    if not set(community_index) <= (set(selected_baseline) | set(fallback)):
        raise ValueError("schema-3 prepackaged community index is invalid")
    for index in (detail_index, community_index):
        for reference in index.values():
            _schema3_prepackaged_reference(reference)
    for key, reference in community_sidecar_index.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("schema-3 prepackaged community key is invalid")
        _schema3_prepackaged_reference(reference)


def _verify_schema3_prepackaged_references(bundle_root, manifest):
    verified = set()
    catalog_ids = None
    catalog = manifest.get("catalog_index")
    if isinstance(catalog, dict) and catalog:
        catalog_verified, catalog_ids = _verify_catalog_index(bundle_root, manifest)
        verified.update(catalog_verified)

    for case_index_name in ("detail_index", "community_index"):
        for case_id, value in manifest[case_index_name].items():
            reference = _schema3_prepackaged_reference(value)
            payload = _verify_reference(bundle_root, reference)
            verified.add(reference["path"])
            if not isinstance(payload, dict):
                raise ValueError(f"schema-3 case {case_id!r} payload is invalid")
            case = payload.get("case")
            expected_cohort = value.get(
                "cohort",
                "hybrid_only" if case_index_name == "detail_index" else "baseline_only",
            )
            if (
                not isinstance(case, dict)
                or case.get("case_id") != case_id
                or payload.get("cohort") != expected_cohort
                or payload.get("community_key") != value.get("community_key")
                or case.get("community_key") != value.get("community_key")
            ):
                raise ValueError(f"schema-3 case {case_id!r} identity is invalid")
            overlay = payload.get("overlay_evidence")
            if overlay is not None:
                verified.update(
                    _verify_compact_chunks(
                        bundle_root, overlay, f"schema-3 case {case_id!r} overlay"
                    )
                )

    for community_key, value in manifest["community_sidecar_index"].items():
        reference = _schema3_prepackaged_reference(value)
        community = _verify_reference(bundle_root, reference)
        verified.add(reference["path"])
        if (
            not isinstance(community, dict)
            or community.get("community_key") != community_key
            or community.get("complete") is not True
        ):
            raise ValueError(f"schema-3 community {community_key!r} is invalid")
        if "node_chunks" in community:
            verified.update(
                _verify_compact_chunks(
                    bundle_root,
                    community,
                    f"schema-3 community {community_key!r}",
                    catalog_ids,
                )
            )
        else:
            nodes = community.get("nodes")
            if (
                not isinstance(nodes, list)
                or community.get("node_count") != len(nodes)
                or not isinstance(community.get("edge_chunks"), list)
                or not isinstance(community.get("provenance_chunks"), list)
            ):
                raise ValueError(f"schema-3 community {community_key!r} is incomplete")
            for field, row_field in (
                ("edge_chunks", "edges"), ("provenance_chunks", "observations")
            ):
                expected_offset = 0
                for chunk_ref in community[field]:
                    chunk_reference = _schema3_prepackaged_reference(chunk_ref)
                    payload = _verify_reference(bundle_root, chunk_reference)
                    rows = payload.get(row_field) if isinstance(payload, dict) else None
                    if (
                        not isinstance(rows, list)
                        or payload.get("offset") != expected_offset
                        or payload.get("count") != len(rows)
                        or chunk_reference.get("offset") != expected_offset
                        or chunk_reference.get("count") != len(rows)
                    ):
                        raise ValueError(
                            f"schema-3 community {community_key!r} chunks are invalid"
                        )
                    expected_offset += len(rows)
                    verified.add(chunk_reference["path"])
        verified.update(
            _verify_schema3_day_view_chunks(
                bundle_root, community, f"schema-3 community {community_key!r}"
            )
        )
    return verified


def _zip_members(archive):
    members = {}
    for info in archive.infolist():
        name = _safe_zip_member_name(info.filename)
        if _zip_member_is_symlink(info):
            raise ValueError(f"ZIP member is a symlink: {name}")
        if name in members:
            raise ValueError(f"ZIP contains duplicate member {name!r}")
        members[name] = info
    return members


def _zip_member_is_symlink(info):
    mode = (info.external_attr >> 16) & 0o170000
    return mode == 0o120000


def publish_prepackaged_schema3_zip(source_path, output_dir):
    """Validate and stream a prepackaged schema-3 bundle from a ZIP archive."""
    try:
        archive = zipfile.ZipFile(source_path)
    except (OSError, zipfile.BadZipFile) as error:
        raise ValueError(f"schema-3 recovery ZIP is invalid: {error}") from error

    with archive:
        members = _zip_members(archive)
        expected_manifest_name = (
            "v9_schema3_results/hybrid_recovery_explanations_v9.json"
        )
        manifest_names = [
            name
            for name in members
            if name.rsplit("/", 1)[-1] == "hybrid_recovery_explanations_v9.json"
        ]
        if manifest_names != [expected_manifest_name]:
            raise ValueError(
                "schema-3 recovery ZIP must contain exactly one "
                "v9_schema3_results/hybrid_recovery_explanations_v9.json"
            )
        manifest_name = expected_manifest_name
        manifest_prefix = "v9_schema3_results"
        manifest_info = members[manifest_name]
        if manifest_info.is_dir():
            raise ValueError("schema-3 recovery ZIP manifest is not a file")
        try:
            with archive.open(manifest_info, "r") as source:
                artifact_content = source.read()
            manifest = json.loads(artifact_content)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("schema-3 recovery ZIP manifest is not valid JSON") from error
        if not isinstance(manifest, dict):
            raise ValueError("schema-3 recovery ZIP manifest is not an object")
        _validate_schema3_prepackaged_manifest(manifest)
        manifest_content = _canonical_bytes(manifest)

        bundle_prefix = "/".join(
            value
            for value in (manifest_prefix, manifest["sidecar_base"].rstrip("/"))
            if value
        )
        bundle_root = _ZipBundleRoot(archive, members, bundle_prefix)
        if bundle_root.read_member("manifest.json") != manifest_content:
            raise ValueError("schema-3 ZIP source manifest bytes do not match")
        verified_paths = _verify_schema3_prepackaged_references(
            bundle_root, manifest
        )

        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        final_bundle = root / manifest["bundle_path"]
        try:
            final_bundle.resolve().relative_to(root.resolve())
        except ValueError as error:
            raise ValueError("schema-3 bundle_path escapes output directory") from error
        stage = Path(tempfile.mkdtemp(prefix=".bundle-stage-", dir=root))

        def copy_member(relative, destination):
            destination.parent.mkdir(parents=True, exist_ok=True)
            with bundle_root.open_member(relative) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)

        try:
            for relative in sorted(verified_paths):
                copy_member(relative, stage / relative)
            _write_atomic_file(stage / "manifest.json", manifest_content)
            pointer = {
                "bundle_id": manifest["bundle_id"],
                "bundle_path": manifest["bundle_path"],
                "manifest_sha256": hashlib.sha256(manifest_content).hexdigest(),
            }
            _write_atomic_file(stage / "current.json", _canonical_bytes(pointer))
            _verify_schema3_prepackaged_references(stage, manifest)
            final_bundle.parent.mkdir(parents=True, exist_ok=True)
            if final_bundle.exists():
                existing = final_bundle / "manifest.json"
                if not existing.is_file() or existing.read_bytes() != manifest_content:
                    raise ValueError("published schema-3 manifest does not match")
                _verify_schema3_prepackaged_references(final_bundle, manifest)
                shutil.rmtree(stage)
            else:
                os.replace(stage, final_bundle)
            _write_atomic_file(root / "current.json", _canonical_bytes(pointer))
            return manifest
        except Exception:
            if stage.exists():
                shutil.rmtree(stage)
            raise


def publish_prepackaged_schema3_manifest(manifest, source_path, output_dir):
    """Copy and verify a schema-3 bundle already finalized by the writer."""
    _validate_schema3_prepackaged_manifest(manifest)
    source_parent = Path(source_path).parent
    source_bundle = source_parent / manifest["sidecar_base"]
    try:
        source_bundle.resolve().relative_to(source_parent.resolve())
    except ValueError as error:
        raise ValueError("schema-3 sidecar_base escapes artifact directory") from error
    if not source_bundle.is_dir():
        raise ValueError(f"schema-3 source bundle is missing: {source_bundle}")
    source_manifest_content = _canonical_bytes(manifest)
    source_manifest = source_bundle / "manifest.json"
    if (
        not source_manifest.is_file()
        or source_manifest.read_bytes() != source_manifest_content
    ):
        raise ValueError("schema-3 source manifest bytes do not match")
    verified_paths = _verify_schema3_prepackaged_references(source_bundle, manifest)
    published_manifest = manifest
    if manifest["sidecar_base"] == f"{manifest['bundle_path']}/":
        published_manifest = {
            **manifest,
            "sidecar_base": f"recovery/{manifest['bundle_path']}/",
        }
    manifest_content = _canonical_bytes(published_manifest)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    final_bundle = root / manifest["bundle_path"]
    stage = Path(tempfile.mkdtemp(prefix=".bundle-stage-", dir=root))
    try:
        for relative in sorted(verified_paths):
            source = source_bundle / relative
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        _write_atomic_file(stage / "manifest.json", manifest_content)
        pointer = {
            "bundle_id": published_manifest["bundle_id"],
            "bundle_path": published_manifest["bundle_path"],
            "manifest_sha256": hashlib.sha256(manifest_content).hexdigest(),
        }
        _write_atomic_file(stage / "current.json", _canonical_bytes(pointer))
        _verify_schema3_prepackaged_references(stage, published_manifest)
        final_bundle.parent.mkdir(parents=True, exist_ok=True)
        if final_bundle.exists():
            existing = final_bundle / "manifest.json"
            if not existing.is_file() or existing.read_bytes() != manifest_content:
                raise ValueError("published schema-3 manifest does not match")
            _verify_schema3_prepackaged_references(final_bundle, published_manifest)
            shutil.rmtree(stage)
        else:
            os.replace(stage, final_bundle)
        _write_atomic_file(root / "current.json", _canonical_bytes(pointer))
        return published_manifest
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


def package_schema3_sidecars(artifact, output_dir, *, chunk_size=250):
    """Publish schema-3 selected evidence while retaining full lightweight cohorts."""
    _validate_schema3_artifact(artifact)
    if type(chunk_size) is not int or chunk_size < 1:
        raise ValueError("chunk_size must be a positive integer")
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    core = {
        "format": "recovery-sidecars-v3",
        "chunk_size": chunk_size,
        "artifact": artifact,
    }
    bundle_id = hashlib.sha256(_canonical_bytes(core)).hexdigest()[:24]
    bundle_path = Path("bundles") / bundle_id
    final_bundle = root / bundle_path
    stage = Path(tempfile.mkdtemp(prefix=".bundle-stage-", dir=root))
    try:
        raw_communities = artifact.get("communities", {})
        if not isinstance(raw_communities, dict):
            raise ValueError("schema-3 communities must be an object")
        community_sidecar_index = {
            key: _publish_community(stage, key, community, chunk_size)
            for key, community in sorted(raw_communities.items())
        }
        records = {
            record["case_id"]: record
            for values in artifact["cohorts"].values()
            for record in values
        }
        detail_index = {}
        for case_id, detail in sorted(artifact.get("detail_index", {}).items()):
            record = records[case_id]
            payload = {
                "schema_version": "3.0",
                "cohort": "hybrid_only",
                "case": record,
                "detail": detail,
                "community_key": record.get("community_key"),
            }
            ref = _write_content_addressed(stage, "cases", case_id, payload)
            detail_index[case_id] = {
                **ref,
                "cohort": "hybrid_only",
                "community_key": record.get("community_key"),
            }
        community_index = {}
        for case_id, detail in sorted(artifact.get("community_index", {}).items()):
            record = records[case_id]
            cohort = record["cohort"]
            payload = {
                "schema_version": "3.0",
                "cohort": cohort,
                "case": record,
                "detail": detail,
                "community_key": record.get("community_key"),
            }
            ref = _write_content_addressed(stage, "cases", case_id, payload)
            community_index[case_id] = {
                **ref,
                "cohort": cohort,
                "community_key": record.get("community_key"),
            }

        manifest = {
            "schema_version": "3.0",
            "policy": artifact["policy"],
            "summary": artifact["summary"],
            "coverage": artifact["coverage"],
            "cohorts": artifact["cohorts"],
            "selection": artifact["selection"],
            "detail_index": detail_index,
            "community_index": community_index,
            "community_sidecar_index": community_sidecar_index,
            "catalog_index": artifact.get("catalog_index", {}),
            "generation_diagnostics": artifact.get("generation_diagnostics", {}),
            "run_fingerprint": artifact.get("run_fingerprint", {}),
            "bundle_id": bundle_id,
            "bundle_path": bundle_path.as_posix(),
            "sidecar_base": f"recovery/{bundle_path.as_posix()}/",
        }
        manifest_content = _canonical_bytes(manifest)
        _validate_schema3_prepackaged_manifest(manifest)
        _write_atomic_file(stage / "manifest.json", manifest_content)
        _verify_schema3_prepackaged_references(stage, manifest)
        final_bundle.parent.mkdir(parents=True, exist_ok=True)
        if final_bundle.exists():
            existing = final_bundle / "manifest.json"
            if not existing.is_file() or existing.read_bytes() != manifest_content:
                raise ValueError("existing schema-3 bundle manifest disagrees")
            _verify_schema3_prepackaged_references(final_bundle, manifest)
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
