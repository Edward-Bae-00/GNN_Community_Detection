"""Resumable, fail-closed publication of recovery explanation sidecars."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path


class RecoveryBundleError(ValueError):
    """Raised when a recovery bundle cannot be safely reused or published."""


def _canonical_bytes(value) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RecoveryBundleError("recovery bundle data must be JSON-safe") from exc


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _source_row_accumulate(state, source_row_id):
    value = int.from_bytes(
        hashlib.sha256(source_row_id.encode("utf-8")).digest(), "big"
    )
    count, total, xor = state
    return count + 1, (total + value) % (1 << 256), xor ^ value


def _source_row_fingerprint(source_row_ids):
    state = (0, 0, 0)
    for source_row_id in source_row_ids:
        state = _source_row_accumulate(state, source_row_id)
    return state


def _chunks(values, size):
    for offset in range(0, len(values), size):
        yield offset, values[offset : offset + size]


def _records(value, field_name):
    if isinstance(value, (str, bytes, Mapping)):
        raise RecoveryBundleError(f"{field_name} must be an iterable of objects")
    try:
        return iter(value)
    except TypeError as exc:
        raise RecoveryBundleError(
            f"{field_name} must be an iterable of objects"
        ) from exc


def _atomic_write(destination: Path, content: bytes):
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


class RecoveryBundleWriter:
    """Incrementally stage immutable recovery evidence for atomic publication."""

    _STATE_FILE = "checkpoint.json"
    _CASE_IDENTITY_FIELDS = (
        "case_id",
        "person_id",
        "event_id",
        "scoring_day",
        "community_key",
    )

    def __init__(
        self,
        staging_root,
        final_root,
        *,
        run_fingerprint,
        chunk_size=250,
        sidecar_prefix="",
    ):
        if type(chunk_size) is not int or chunk_size < 1:
            raise RecoveryBundleError("chunk_size must be a positive integer")
        self.staging_root = Path(staging_root)
        self.final_root = Path(final_root)
        self.chunk_size = chunk_size
        if not isinstance(sidecar_prefix, str):
            raise RecoveryBundleError("sidecar_prefix must be a relative path string")
        normalized_prefix = sidecar_prefix.strip("/")
        prefix_path = Path(normalized_prefix)
        if prefix_path.is_absolute() or ".." in prefix_path.parts:
            raise RecoveryBundleError("sidecar_prefix must be a safe relative path")
        self.sidecar_prefix = (
            "" if normalized_prefix in {"", "."} else prefix_path.as_posix()
        )
        raw_fingerprint_bytes = _canonical_bytes(run_fingerprint)
        self.run_fingerprint = json.loads(raw_fingerprint_bytes)
        fingerprint_bytes = _canonical_bytes(
            {
                "run_fingerprint": self.run_fingerprint,
                "sidecar_prefix": self.sidecar_prefix,
            }
        )
        self.run_fingerprint_sha256 = _sha256(fingerprint_bytes)
        self.staging_root.mkdir(parents=True, exist_ok=True)
        self._state = {
            "schema_version": "1.0",
            "run_fingerprint": self.run_fingerprint,
            "run_fingerprint_sha256": self.run_fingerprint_sha256,
            "chunk_size": self.chunk_size,
            "sidecar_prefix": self.sidecar_prefix,
            "communities": {},
            "cases": {},
            "failures": [],
        }
        checkpoint_path = self.staging_root / self._STATE_FILE
        if checkpoint_path.exists():
            self._load_checkpoint(checkpoint_path)

    @property
    def community_index(self):
        return json.loads(_canonical_bytes(self._state["communities"]))

    @property
    def case_index(self):
        return json.loads(_canonical_bytes(self._state["cases"]))

    def _object_path(self, ref):
        if not isinstance(ref, Mapping):
            raise RecoveryBundleError("sidecar reference must be an object")
        relative_text = ref.get("path")
        if not isinstance(relative_text, str):
            raise RecoveryBundleError("sidecar reference requires path")
        relative = Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise RecoveryBundleError("sidecar reference path is unsafe")
        destination = self.staging_root / relative
        try:
            destination.resolve().relative_to(self.staging_root.resolve())
        except ValueError as exc:
            raise RecoveryBundleError("sidecar reference escapes staging root") from exc
        return destination

    def _read_verified_ref(self, ref):
        destination = self._object_path(ref)
        if not destination.is_file():
            raise RecoveryBundleError(f"missing cached object {ref.get('path')!r}")
        content = destination.read_bytes()
        digest = _sha256(content)
        if (
            ref.get("sha256") != digest
            or ref.get("bytes") != len(content)
            or destination.name != f"{digest}.json"
        ):
            raise RecoveryBundleError(f"corrupt cached object {ref.get('path')!r}")
        try:
            return json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RecoveryBundleError(f"invalid cached JSON {ref.get('path')!r}") from exc

    def _verify_community_ref(self, ref):
        manifest = self._read_verified_ref(ref)
        if not isinstance(manifest, Mapping) or manifest.get("complete") is not True:
            raise RecoveryBundleError("cached community manifest is incomplete")
        for field in (
            "node_chunks",
            "edge_chunks",
            "provenance_chunks",
            "provenance_expansion_membership_chunks",
        ):
            refs = manifest.get(field)
            if not isinstance(refs, list):
                raise RecoveryBundleError(f"cached community lacks {field}")
            for chunk_ref in refs:
                self._read_verified_ref(chunk_ref)
        return manifest

    def _verify_overlay_evidence(self, overlay):
        if not isinstance(overlay, Mapping) or overlay.get("complete") is not True:
            raise RecoveryBundleError("cached case overlay is incomplete")
        fields = (
            ("node_chunks", "nodes", "node_count"),
            ("edge_chunks", "edges", "edge_count"),
            ("provenance_chunks", "observations", "provenance_observation_count"),
            (
                "provenance_expansion_membership_chunks",
                "memberships",
                None,
            ),
        )
        for ref_field, payload_field, count_field in fields:
            refs = overlay.get(ref_field)
            if not isinstance(refs, list):
                raise RecoveryBundleError(f"cached case overlay lacks {ref_field}")
            total = 0
            expected_offset = 0
            for ref in refs:
                payload = self._read_verified_ref(ref)
                rows = payload.get(payload_field) if isinstance(payload, Mapping) else None
                if (
                    not isinstance(rows, list)
                    or payload.get("offset") != expected_offset
                    or payload.get("count") != len(rows)
                    or ref.get("offset") != expected_offset
                    or ref.get("count") != len(rows)
                ):
                    raise RecoveryBundleError("cached case overlay chunk metadata is invalid")
                total += len(rows)
                expected_offset = total
            if count_field is not None and overlay.get(count_field) != total:
                raise RecoveryBundleError("cached case overlay count is invalid")
        expansions = overlay.get("provenance_expansions")
        if not isinstance(expansions, list):
            raise RecoveryBundleError("cached case overlay expansions are invalid")
        return overlay

    def _verify_case_record(self, case_id, record):
        if not isinstance(record, Mapping) or not isinstance(record.get("ref"), Mapping):
            raise RecoveryBundleError("cached case index is invalid")
        payload = self._read_verified_ref(record["ref"])
        if not isinstance(payload, Mapping):
            raise RecoveryBundleError("cached case payload is invalid")
        case = payload.get("case")
        if (
            not isinstance(case, Mapping)
            or case.get("case_id") != case_id
            or payload.get("cohort") != record.get("cohort")
            or payload.get("community_key") != record.get("community_key")
            or case.get("community_key") != record.get("community_key")
        ):
            raise RecoveryBundleError("cached case metadata mismatch")
        self._validate_case_identity(case)
        overlay = payload.get("overlay_evidence")
        if record.get("cohort") == "baseline_only":
            if overlay is not None or payload.get("explanation") is not None:
                raise RecoveryBundleError("Baseline-only cache contains explanation evidence")
        elif record.get("cohort") == "hybrid_only":
            explanation = payload.get("explanation")
            if not isinstance(explanation, Mapping):
                raise RecoveryBundleError("cached Hybrid-only explanation is missing")
            if (
                explanation.get("case_id") != case_id
                or explanation.get("community_key") != record.get("community_key")
            ):
                raise RecoveryBundleError("cached explanation identity mismatch")
            self._validate_case_explanation_identity(case, explanation)
            self._validated_llm_metadata(
                explanation, payload.get("validation_metadata")
            )
            if overlay is None:
                raise RecoveryBundleError("cached Hybrid-only overlay is missing")
            self._verify_overlay_evidence(overlay)
            edge_count = overlay.get("edge_count", 0)
            provenance_count = overlay.get("provenance_observation_count", 0)
            if (
                overlay.get("node_count", 0) < 1
                or (edge_count == 0) != (provenance_count == 0)
            ):
                raise RecoveryBundleError("cached Hybrid-only overlay is empty")
        else:
            raise RecoveryBundleError("cached case cohort is invalid")
        return payload

    def _load_checkpoint(self, checkpoint_path):
        try:
            state = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RecoveryBundleError("recovery checkpoint is corrupt") from exc
        if not isinstance(state, Mapping) or state.get("schema_version") != "1.0":
            raise RecoveryBundleError("unsupported recovery checkpoint")
        if (
            state.get("run_fingerprint_sha256") != self.run_fingerprint_sha256
            or _canonical_bytes(state.get("run_fingerprint"))
            != _canonical_bytes(self.run_fingerprint)
        ):
            raise RecoveryBundleError("recovery checkpoint fingerprint mismatch")
        if state.get("chunk_size") != self.chunk_size:
            raise RecoveryBundleError("recovery checkpoint chunk_size mismatch")
        if state.get("sidecar_prefix", "") != self.sidecar_prefix:
            raise RecoveryBundleError("recovery checkpoint sidecar_prefix mismatch")
        communities = state.get("communities")
        cases = state.get("cases")
        failures = state.get("failures")
        if (
            not isinstance(communities, Mapping)
            or not isinstance(cases, Mapping)
            or not isinstance(failures, list)
        ):
            raise RecoveryBundleError("recovery checkpoint indexes are invalid")
        for key, ref in communities.items():
            manifest = self._verify_community_ref(ref)
            if manifest.get("community_key") != key:
                raise RecoveryBundleError("cached community key mismatch")
        for case_id, record in cases.items():
            self._verify_case_record(case_id, record)
        self._state = json.loads(_canonical_bytes(state))

    def checkpoint(self):
        destination = self.staging_root / self._STATE_FILE
        _atomic_write(destination, _canonical_bytes(self._state))
        return destination

    def has_completed_case(self, case_id, cohort=None):
        if not isinstance(case_id, str) or not case_id:
            raise RecoveryBundleError("case_id must be a non-blank string")
        if cohort is not None and cohort not in {"hybrid_only", "baseline_only"}:
            raise RecoveryBundleError("cohort must be hybrid_only or baseline_only")
        record = self._state["cases"].get(case_id)
        if record is None or (cohort is not None and record.get("cohort") != cohort):
            return False
        if any(
            failure.get("case_id") == case_id
            for failure in self._state["failures"]
        ):
            return False
        self._verify_case_record(case_id, record)
        return True

    def _put_object(self, payload):
        content = _canonical_bytes(payload)
        digest = _sha256(content)
        relative = Path("objects") / digest[:2] / f"{digest}.json"
        destination = self.staging_root / relative
        if destination.exists():
            if destination.read_bytes() != content:
                raise RecoveryBundleError(
                    f"corrupt content-addressed object {relative.as_posix()}"
                )
        else:
            _atomic_write(destination, content)
        return {
            "path": relative.as_posix(),
            "sha256": digest,
            "bytes": len(content),
        }

    def _write_chunks(self, kind, records):
        refs = []
        for offset, rows in _chunks(records, self.chunk_size):
            ref = self._put_object(
                {"offset": offset, "count": len(rows), kind: rows}
            )
            refs.append({**ref, "offset": offset, "count": len(rows)})
        return refs

    class _ChunkSink:
        def __init__(self, owner, kind):
            self.owner = owner
            self.kind = kind
            self.buffer = []
            self.refs = []
            self.count = 0

        def add(self, record):
            detached = json.loads(_canonical_bytes(record))
            if not isinstance(detached, dict):
                raise RecoveryBundleError(f"{self.kind} record must be an object")
            self.buffer.append(detached)
            self.count += 1
            if len(self.buffer) == self.owner.chunk_size:
                self.flush()

        def flush(self):
            if not self.buffer:
                return
            offset = self.count - len(self.buffer)
            payload = {
                "offset": offset,
                "count": len(self.buffer),
                self.kind: self.buffer,
            }
            ref = self.owner._put_object(payload)
            self.refs.append({**ref, "offset": offset, "count": len(self.buffer)})
            self.buffer = []

        def finish(self):
            self.flush()
            return self.refs

    def write_community(self, community):
        if not isinstance(community, Mapping) or community.get("complete") is not True:
            raise RecoveryBundleError("community must be a complete object")
        key = community.get("community_key")
        if not isinstance(key, str) or not key.strip():
            raise RecoveryBundleError("community requires a non-blank community_key")
        base_nodes = _records(community.get("nodes", ()), "community nodes")
        base_edges = _records(community.get("edges", ()), "community edges")
        expansions = _records(
            community.get("provenance_expansions", ()),
            "community provenance_expansions",
        )
        external_provenance_value = community.get("provenance_observations")
        external_provenance = (
            None
            if external_provenance_value is None
            else _records(external_provenance_value, "community provenance_observations")
        )

        node_sink = self._ChunkSink(self, "nodes")
        edge_sink = self._ChunkSink(self, "edges")
        provenance_sink = self._ChunkSink(self, "observations")
        membership_sink = self._ChunkSink(self, "memberships")
        node_hashes = {}
        edge_hashes = {}
        expected_provenance_counts = {}
        observed_provenance_counts = {}
        expected_source_rows = {}
        observed_source_rows = {}
        expansion_index = []

        def add_node(node):
            if not isinstance(node, Mapping) or not isinstance(node.get("node_id"), str):
                raise RecoveryBundleError("community node requires node_id")
            detached = json.loads(_canonical_bytes(node))
            node_id = detached["node_id"]
            digest = _sha256(_canonical_bytes(detached))
            prior_digest = node_hashes.get(node_id)
            if prior_digest is not None:
                if prior_digest != digest:
                    raise RecoveryBundleError(f"conflicting node {node_id!r}")
                return
            node_hashes[node_id] = digest
            node_sink.add(detached)

        def add_provenance(observation, edge_id):
            if not isinstance(observation, Mapping):
                raise RecoveryBundleError("edge observation must be an object")
            row = json.loads(_canonical_bytes(observation))
            explicit_edge_id = row.get("edge_id")
            if explicit_edge_id is not None and explicit_edge_id != edge_id:
                raise RecoveryBundleError("edge observation has conflicting edge_id")
            source_row_id = row.get("source_row_id")
            if not isinstance(source_row_id, str) or not source_row_id:
                raise RecoveryBundleError("edge observation requires source_row_id")
            row["edge_id"] = edge_id
            provenance_sink.add(row)
            observed_provenance_counts[edge_id] = (
                observed_provenance_counts.get(edge_id, 0) + 1
            )
            observed_source_rows[edge_id] = _source_row_accumulate(
                observed_source_rows.get(edge_id, (0, 0, 0)), source_row_id
            )
            return source_row_id

        def add_edge(edge):
            if not isinstance(edge, Mapping) or not isinstance(edge.get("edge_id"), str):
                raise RecoveryBundleError("community edge requires edge_id")
            edge_without_observations = dict(edge)
            inline_observations = edge_without_observations.pop("observations", None)
            detached = json.loads(_canonical_bytes(edge_without_observations))
            if external_provenance is not None and inline_observations is not None:
                raise RecoveryBundleError(
                    "streamed provenance cannot be combined with inline observations"
                )
            source_row_ids = detached.get("source_row_ids")
            if not isinstance(source_row_ids, list) or not source_row_ids:
                raise RecoveryBundleError("community edge requires source_row_ids")
            if (
                any(not isinstance(value, str) or not value for value in source_row_ids)
                or len(set(source_row_ids)) != len(source_row_ids)
            ):
                raise RecoveryBundleError("edge source_row_ids must be unique strings")
            source_row_count = detached.get("source_row_count", len(source_row_ids))
            if source_row_count != len(source_row_ids):
                raise RecoveryBundleError("edge source_row_count is inconsistent")
            detached["source_row_count"] = source_row_count
            edge_id = detached["edge_id"]
            digest = _sha256(_canonical_bytes(detached))
            prior_digest = edge_hashes.get(edge_id)
            if prior_digest is not None:
                if prior_digest != digest:
                    raise RecoveryBundleError(f"conflicting edge {edge_id!r}")
                return edge_id
            edge_hashes[edge_id] = digest
            expected_provenance_counts[edge_id] = source_row_count
            observed_provenance_counts[edge_id] = 0
            expected_source_rows[edge_id] = _source_row_fingerprint(source_row_ids)
            observed_source_rows[edge_id] = (0, 0, 0)
            edge_sink.add(detached)
            if external_provenance is None:
                if inline_observations is None:
                    raise RecoveryBundleError(
                        "community edge requires provenance observations"
                    )
                observed_ids = [
                    add_provenance(observation, edge_id)
                    for observation in _records(
                        inline_observations, "edge observations"
                    )
                ]
                if sorted(observed_ids) != sorted(source_row_ids):
                    raise RecoveryBundleError(
                        "edge observations disagree with source_row_ids"
                    )
            return edge_id

        for node in base_nodes:
            add_node(node)
        for edge in base_edges:
            add_edge(edge)
        seen_expansion_ids = set()
        for expansion in expansions:
            if not isinstance(expansion, Mapping):
                raise RecoveryBundleError("provenance expansion must be an object")
            expansion_id = expansion.get("expansion_id")
            if (
                not isinstance(expansion_id, str)
                or not expansion_id
                or expansion_id in seen_expansion_ids
            ):
                raise RecoveryBundleError("invalid provenance expansion_id")
            seen_expansion_ids.add(expansion_id)
            node_count = 0
            edge_count = 0
            for node in _records(
                expansion.get("nodes", ()), "provenance expansion nodes"
            ):
                if not isinstance(node, Mapping) or not isinstance(node.get("node_id"), str):
                    raise RecoveryBundleError("community node requires node_id")
                add_node(node)
                membership_sink.add(
                    {
                        "expansion_id": expansion_id,
                        "kind": "node",
                        "record_id": node["node_id"],
                    }
                )
                node_count += 1
            for edge in _records(
                expansion.get("edges", ()), "provenance expansion edges"
            ):
                edge_id = add_edge(edge)
                membership_sink.add(
                    {
                        "expansion_id": expansion_id,
                        "kind": "edge",
                        "record_id": edge_id,
                    }
                )
                edge_count += 1
            expansion_index.append(
                {
                    "expansion_id": expansion_id,
                    "label": expansion.get("label"),
                    "node_count": node_count,
                    "edge_count": edge_count,
                }
            )

        if external_provenance is not None:
            for observation in external_provenance:
                if not isinstance(observation, Mapping):
                    raise RecoveryBundleError("edge observation must be an object")
                edge_id = observation.get("edge_id")
                if not isinstance(edge_id, str) or edge_id not in edge_hashes:
                    raise RecoveryBundleError(
                        "streamed provenance references an unknown edge"
                    )
                add_provenance(observation, edge_id)
        if (
            observed_provenance_counts != expected_provenance_counts
            or observed_source_rows != expected_source_rows
        ):
            raise RecoveryBundleError(
                "provenance observations disagree with canonical edge source_row_ids"
            )

        manifest = {
            "schema_version": "1.0",
            "community_key": key,
            "complete": True,
            "scoring_day": community.get("scoring_day"),
            "component_id": community.get("component_id"),
            "node_count": node_sink.count,
            "edge_count": edge_sink.count,
            "provenance_observation_count": provenance_sink.count,
            "node_chunks": node_sink.finish(),
            "edge_chunks": edge_sink.finish(),
            "provenance_chunks": provenance_sink.finish(),
            "provenance_expansion_membership_chunks": membership_sink.finish(),
            "provenance_expansions": sorted(
                expansion_index, key=lambda item: item["expansion_id"]
            ),
        }
        ref = self._put_object(manifest)
        prior = self._state["communities"].get(key)
        if prior is not None and prior != ref:
            raise RecoveryBundleError(f"community key {key!r} has conflicting content")
        self._state["communities"][key] = ref
        self.checkpoint()
        return ref

    def _stream_overlay_evidence(self, overlay):
        if not isinstance(overlay, Mapping):
            raise RecoveryBundleError("overlay_evidence must be an object")
        nodes = _records(overlay.get("nodes", ()), "overlay nodes")
        edges = _records(overlay.get("edges", ()), "overlay edges")
        expansions = _records(
            overlay.get("provenance_expansions", ()),
            "overlay provenance_expansions",
        )
        external_value = overlay.get("provenance_observations")
        external = (
            None
            if external_value is None
            else _records(external_value, "overlay provenance_observations")
        )
        node_sink = self._ChunkSink(self, "nodes")
        edge_sink = self._ChunkSink(self, "edges")
        provenance_sink = self._ChunkSink(self, "observations")
        membership_sink = self._ChunkSink(self, "memberships")
        node_hashes = {}
        edge_hashes = {}
        expected_counts = {}
        observed_counts = {}
        expected_source_rows = {}
        observed_source_rows = {}
        expansion_index = []

        def add_node(node):
            if not isinstance(node, Mapping) or not isinstance(node.get("node_id"), str):
                raise RecoveryBundleError("overlay node requires node_id")
            detached = json.loads(_canonical_bytes(node))
            node_id = detached["node_id"]
            digest = _sha256(_canonical_bytes(detached))
            prior = node_hashes.get(node_id)
            if prior is not None:
                if prior != digest:
                    raise RecoveryBundleError(f"conflicting overlay node {node_id!r}")
                return
            node_hashes[node_id] = digest
            node_sink.add(detached)

        def add_observation(observation, edge_id):
            if not isinstance(observation, Mapping):
                raise RecoveryBundleError("overlay observation must be an object")
            row = json.loads(_canonical_bytes(observation))
            explicit_edge_id = row.get("edge_id")
            if explicit_edge_id is not None and explicit_edge_id != edge_id:
                raise RecoveryBundleError("overlay observation has conflicting edge_id")
            source_row_id = row.get("source_row_id")
            if not isinstance(source_row_id, str) or not source_row_id:
                raise RecoveryBundleError("overlay observation requires source_row_id")
            row["edge_id"] = edge_id
            provenance_sink.add(row)
            observed_counts[edge_id] = observed_counts.get(edge_id, 0) + 1
            observed_source_rows[edge_id] = _source_row_accumulate(
                observed_source_rows.get(edge_id, (0, 0, 0)), source_row_id
            )
            return source_row_id

        def add_edge(edge):
            if not isinstance(edge, Mapping) or not isinstance(edge.get("edge_id"), str):
                raise RecoveryBundleError("overlay edge requires edge_id")
            without_observations = dict(edge)
            inline = without_observations.pop("observations", None)
            detached = json.loads(_canonical_bytes(without_observations))
            if external is not None and inline is not None:
                raise RecoveryBundleError(
                    "streamed overlay provenance cannot be combined with inline observations"
                )
            source_row_ids = detached.get("source_row_ids")
            if (
                not isinstance(source_row_ids, list)
                or not source_row_ids
                or any(not isinstance(value, str) or not value for value in source_row_ids)
                or len(set(source_row_ids)) != len(source_row_ids)
            ):
                raise RecoveryBundleError(
                    "overlay edge source_row_ids must be unique strings"
                )
            count = detached.get("source_row_count", len(source_row_ids))
            if count != len(source_row_ids):
                raise RecoveryBundleError("overlay edge source_row_count is inconsistent")
            detached["source_row_count"] = count
            edge_id = detached["edge_id"]
            digest = _sha256(_canonical_bytes(detached))
            prior = edge_hashes.get(edge_id)
            if prior is not None:
                if prior != digest:
                    raise RecoveryBundleError(f"conflicting overlay edge {edge_id!r}")
                return edge_id
            edge_hashes[edge_id] = digest
            expected_counts[edge_id] = count
            observed_counts[edge_id] = 0
            expected_source_rows[edge_id] = _source_row_fingerprint(source_row_ids)
            observed_source_rows[edge_id] = (0, 0, 0)
            edge_sink.add(detached)
            if external is None:
                if inline is None:
                    raise RecoveryBundleError(
                        "overlay edge requires provenance observations"
                    )
                observed_ids = [
                    add_observation(observation, edge_id)
                    for observation in _records(inline, "overlay edge observations")
                ]
                if sorted(observed_ids) != sorted(source_row_ids):
                    raise RecoveryBundleError(
                        "overlay observations disagree with source_row_ids"
                    )
            return edge_id

        for node in nodes:
            add_node(node)
        for edge in edges:
            add_edge(edge)
        seen_expansions = set()
        for expansion in expansions:
            if not isinstance(expansion, Mapping):
                raise RecoveryBundleError("overlay provenance expansion must be an object")
            expansion_id = expansion.get("expansion_id")
            if (
                not isinstance(expansion_id, str)
                or not expansion_id
                or expansion_id in seen_expansions
            ):
                raise RecoveryBundleError("invalid overlay provenance expansion_id")
            seen_expansions.add(expansion_id)
            node_count = 0
            edge_count = 0
            for node in _records(
                expansion.get("nodes", ()), "overlay expansion nodes"
            ):
                add_node(node)
                membership_sink.add(
                    {
                        "expansion_id": expansion_id,
                        "kind": "node",
                        "record_id": node["node_id"],
                    }
                )
                node_count += 1
            for edge in _records(
                expansion.get("edges", ()), "overlay expansion edges"
            ):
                edge_id = add_edge(edge)
                membership_sink.add(
                    {
                        "expansion_id": expansion_id,
                        "kind": "edge",
                        "record_id": edge_id,
                    }
                )
                edge_count += 1
            expansion_index.append(
                {
                    "expansion_id": expansion_id,
                    "label": expansion.get("label"),
                    "node_count": node_count,
                    "edge_count": edge_count,
                }
            )
        if external is not None:
            for observation in external:
                if not isinstance(observation, Mapping):
                    raise RecoveryBundleError("overlay observation must be an object")
                edge_id = observation.get("edge_id")
                if not isinstance(edge_id, str) or edge_id not in edge_hashes:
                    raise RecoveryBundleError(
                        "overlay provenance references an unknown edge"
                    )
                add_observation(observation, edge_id)
        if observed_counts != expected_counts or observed_source_rows != expected_source_rows:
            raise RecoveryBundleError(
                "overlay provenance disagrees with canonical edge source_row_ids"
            )
        return {
            "schema_version": "1.0",
            "complete": True,
            "node_count": node_sink.count,
            "edge_count": edge_sink.count,
            "provenance_observation_count": provenance_sink.count,
            "node_chunks": node_sink.finish(),
            "edge_chunks": edge_sink.finish(),
            "provenance_chunks": provenance_sink.finish(),
            "provenance_expansion_membership_chunks": membership_sink.finish(),
            "provenance_expansions": sorted(
                expansion_index, key=lambda item: item["expansion_id"]
            ),
        }

    @staticmethod
    def _validated_llm_metadata(explanation, validation_metadata):
        narrative = explanation.get("llm_narrative")
        metadata = validation_metadata if validation_metadata is not None else narrative
        if not isinstance(metadata, Mapping):
            raise RecoveryBundleError("Hybrid-only case lacks LLM validation metadata")
        source = metadata.get("source")
        model = metadata.get("model")
        prompt_version = metadata.get("prompt_version")
        summary = narrative.get("summary") if isinstance(narrative, Mapping) else None
        summary_refs = (
            narrative.get("summary_source_refs")
            if isinstance(narrative, Mapping)
            else None
        )
        claims = narrative.get("claims") if isinstance(narrative, Mapping) else None
        grounded_claims = (
            isinstance(claims, list)
            and bool(claims)
            and all(
                isinstance(claim, Mapping)
                and isinstance(claim.get("text"), str)
                and bool(claim["text"].strip())
                and isinstance(claim.get("source_refs"), list)
                and bool(claim["source_refs"])
                and all(
                    isinstance(source_ref, str) and bool(source_ref.strip())
                    for source_ref in claim["source_refs"]
                )
                for claim in claims
            )
        )
        if (
            metadata.get("validated") is not True
            or source != "llm"
            or model != "gemma4:12b"
            or not isinstance(prompt_version, str)
            or not prompt_version.strip()
            or not isinstance(summary, str)
            or not summary.strip()
            or not isinstance(summary_refs, list)
            or not summary_refs
            or any(
                not isinstance(source_ref, str) or not source_ref.strip()
                for source_ref in summary_refs
            )
            or not grounded_claims
        ):
            raise RecoveryBundleError(
                "Hybrid-only case requires complete grounded Gemma metadata"
            )
        if not isinstance(narrative, Mapping) or narrative.get("validated") is not True:
            raise RecoveryBundleError("Hybrid-only explanation lacks validated narrative")
        if narrative.get("source") != source or narrative.get("model") != model:
            raise RecoveryBundleError("LLM validation metadata disagrees with narrative")
        return {
            "source": source,
            "model": model,
            "validated": True,
            "prompt_version": prompt_version,
        }

    @classmethod
    def _validate_case_identity(cls, case):
        for field in cls._CASE_IDENTITY_FIELDS:
            value = case.get(field)
            if not isinstance(value, str) or not value.strip():
                raise RecoveryBundleError(
                    "case identity fields must be present and non-blank"
                )

    @classmethod
    def _validate_case_explanation_identity(cls, case, explanation):
        cls._validate_case_identity(case)
        for field in cls._CASE_IDENTITY_FIELDS:
            case_value = case.get(field)
            explanation_value = explanation.get(field)
            if (
                not isinstance(case_value, str)
                or not case_value.strip()
                or not isinstance(explanation_value, str)
                or not explanation_value.strip()
                or case_value != explanation_value
            ):
                raise RecoveryBundleError(
                    "explanation identity does not match its case"
                )

    def write_case(
        self,
        cohort,
        case,
        *,
        explanation=None,
        validation_metadata=None,
        overlay_evidence=None,
    ):
        if cohort not in {"hybrid_only", "baseline_only"}:
            raise RecoveryBundleError("case cohort must be hybrid_only or baseline_only")
        if not isinstance(case, Mapping):
            raise RecoveryBundleError("case must be an object")
        detached_case = json.loads(_canonical_bytes(case))
        self._validate_case_identity(detached_case)
        case_id = detached_case.get("case_id")
        community_key = detached_case.get("community_key")
        if not isinstance(case_id, str) or not case_id:
            raise RecoveryBundleError("case requires case_id")
        if not isinstance(community_key, str) or community_key not in self._state["communities"]:
            raise RecoveryBundleError("case requires a staged complete community")
        community_manifest = self._verify_community_ref(
            self._state["communities"][community_key]
        )
        if community_manifest.get("complete") is not True:
            raise RecoveryBundleError("case community is incomplete")
        if (
            detached_case.get("scoring_day") is not None
            and community_manifest.get("scoring_day") is not None
            and detached_case["scoring_day"] != community_manifest["scoring_day"]
        ):
            raise RecoveryBundleError("case identity disagrees with its community")

        detached_explanation = None
        validated_metadata = None
        detached_overlay = None
        if cohort == "hybrid_only":
            if not isinstance(explanation, Mapping):
                raise RecoveryBundleError("Hybrid-only case requires an explanation")
            detached_explanation = json.loads(_canonical_bytes(explanation))
            if "community" in detached_explanation:
                raise RecoveryBundleError(
                    "case explanation must reference, not embed, its community"
                )
            if (
                detached_explanation.get("case_id") != case_id
                or detached_explanation.get("community_key") != community_key
            ):
                raise RecoveryBundleError("explanation does not match its case")
            self._validate_case_explanation_identity(
                detached_case, detached_explanation
            )
            validated_metadata = self._validated_llm_metadata(
                detached_explanation, validation_metadata
            )
            if overlay_evidence is None:
                raise RecoveryBundleError(
                    "Hybrid-only case requires complete nonempty overlay evidence"
                )
            detached_overlay = self._stream_overlay_evidence(overlay_evidence)
            edge_count = detached_overlay.get("edge_count", 0)
            provenance_count = detached_overlay.get(
                "provenance_observation_count", 0
            )
            if (
                detached_overlay.get("complete") is not True
                or detached_overlay.get("node_count", 0) < 1
                or (edge_count == 0) != (provenance_count == 0)
            ):
                raise RecoveryBundleError(
                    "Hybrid-only case requires complete nonempty overlay evidence"
                )
        elif (
            explanation is not None
            or validation_metadata is not None
            or overlay_evidence is not None
        ):
            raise RecoveryBundleError(
                "Baseline-only cases do not have explanations or overlay evidence"
            )

        payload = {
            "schema_version": "1.0",
            "cohort": cohort,
            "case": detached_case,
            "community_key": community_key,
            "explanation": detached_explanation,
            "validation_metadata": validated_metadata,
            "overlay_evidence": detached_overlay,
        }
        ref = self._put_object(payload)
        record = {
            "ref": ref,
            "cohort": cohort,
            "community_key": community_key,
            "case": detached_case,
            "llm_validated": cohort == "hybrid_only",
        }
        prior = self._state["cases"].get(case_id)
        if prior is not None and prior != record:
            raise RecoveryBundleError(f"case ID {case_id!r} has conflicting content")
        self._state["cases"][case_id] = record
        self._state["failures"] = [
            failure
            for failure in self._state["failures"]
            if failure.get("case_id") != case_id
        ]
        self.checkpoint()
        return ref

    def record_failure(self, failure):
        detached = json.loads(_canonical_bytes(failure))
        if not isinstance(detached, dict):
            raise RecoveryBundleError("failure must be an object")
        if detached not in self._state["failures"]:
            self._state["failures"].append(detached)
            self._state["failures"].sort(key=lambda value: _canonical_bytes(value))
        self.checkpoint()

    @staticmethod
    def _expected_ids(values, field_name):
        try:
            items = list(values)
        except TypeError as exc:
            raise RecoveryBundleError(f"{field_name} must be an iterable") from exc
        if any(not isinstance(item, str) or not item for item in items):
            raise RecoveryBundleError(f"{field_name} must contain non-blank strings")
        if len(items) != len(set(items)):
            raise RecoveryBundleError(f"{field_name} contains duplicates")
        return set(items)

    def _all_referenced_objects(self):
        refs = {}

        def add(ref):
            payload = self._read_verified_ref(ref)
            prior = refs.get(ref["path"])
            if prior is not None and prior != ref:
                raise RecoveryBundleError("conflicting sidecar reference metadata")
            refs[ref["path"]] = dict(ref)
            return payload

        for ref in self._state["communities"].values():
            manifest = add(ref)
            for field in (
                "node_chunks",
                "edge_chunks",
                "provenance_chunks",
                "provenance_expansion_membership_chunks",
            ):
                for chunk_ref in manifest[field]:
                    add(chunk_ref)
        for case_id, record in self._state["cases"].items():
            payload = self._verify_case_record(case_id, record)
            add(record["ref"])
            overlay = payload.get("overlay_evidence")
            if isinstance(overlay, Mapping):
                for field in (
                    "node_chunks",
                    "edge_chunks",
                    "provenance_chunks",
                    "provenance_expansion_membership_chunks",
                ):
                    for ref in overlay[field]:
                        add(ref)
        return [refs[path] for path in sorted(refs)]

    def _copy_bundle_objects(self, destination, refs):
        for ref in refs:
            source = self._object_path(ref)
            target = destination / ref["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            content = target.read_bytes()
            if len(content) != ref["bytes"] or _sha256(content) != ref["sha256"]:
                raise RecoveryBundleError("published sidecar verification failed")

    def finalize(
        self,
        *,
        expected_hybrid_case_ids,
        expected_baseline_case_ids,
        policy,
        summary,
    ):
        hybrid_expected = self._expected_ids(
            expected_hybrid_case_ids, "expected_hybrid_case_ids"
        )
        baseline_expected = self._expected_ids(
            expected_baseline_case_ids, "expected_baseline_case_ids"
        )
        if hybrid_expected.intersection(baseline_expected):
            raise RecoveryBundleError("expected recovery cohorts must be disjoint")
        if self._state["failures"]:
            raise RecoveryBundleError("recovery failures prevent publication")

        actual_hybrid = {
            case_id
            for case_id, record in self._state["cases"].items()
            if record["cohort"] == "hybrid_only"
        }
        actual_baseline = {
            case_id
            for case_id, record in self._state["cases"].items()
            if record["cohort"] == "baseline_only"
        }
        if actual_hybrid != hybrid_expected or actual_baseline != baseline_expected:
            raise RecoveryBundleError("staged case sets do not exactly match expectations")
        referenced_communities = {
            record["community_key"] for record in self._state["cases"].values()
        }
        if set(self._state["communities"]) != referenced_communities:
            raise RecoveryBundleError(
                "unreferenced staged communities prevent publication"
            )
        for case_id in sorted(actual_hybrid):
            if self._state["cases"][case_id].get("llm_validated") is not True:
                raise RecoveryBundleError(
                    f"Hybrid-only case {case_id!r} lacks validated local Gemma metadata"
                )
        for case_id, record in self._state["cases"].items():
            community_key = record["community_key"]
            if community_key not in self._state["communities"]:
                raise RecoveryBundleError(f"case {case_id!r} has no complete community")
            self._verify_community_ref(self._state["communities"][community_key])

        detached_policy = json.loads(_canonical_bytes(policy))
        detached_summary = json.loads(_canonical_bytes(summary))
        if not isinstance(detached_policy, dict) or not isinstance(detached_summary, dict):
            raise RecoveryBundleError("policy and summary must be objects")
        cohorts = {"hybrid_only": [], "baseline_only": []}
        case_index = {}
        for case_id in sorted(self._state["cases"]):
            record = self._state["cases"][case_id]
            cohorts[record["cohort"]].append(record["case"])
            case_index[case_id] = {
                **record["ref"],
                "cohort": record["cohort"],
                "community_key": record["community_key"],
            }
        community_index = {
            key: self._state["communities"][key]
            for key in sorted(self._state["communities"])
        }
        coverage = {
            "hybrid_only_count": len(hybrid_expected),
            "baseline_only_count": len(baseline_expected),
            "explained_count": len(hybrid_expected),
            "llm_validated_count": len(hybrid_expected),
            "failed_count": 0,
            "complete": True,
        }
        core = {
            "schema_version": "2.0",
            "run_fingerprint_sha256": self.run_fingerprint_sha256,
            "sidecar_prefix": self.sidecar_prefix,
            "policy": detached_policy,
            "summary": detached_summary,
            "coverage": coverage,
            "cohorts": cohorts,
            "case_index": case_index,
            "community_index": community_index,
        }
        bundle_id = _sha256(_canonical_bytes(core))[:24]
        bundle_path = Path("bundles") / bundle_id
        manifest = {
            **core,
            "bundle_id": bundle_id,
            "bundle_path": bundle_path.as_posix(),
            "sidecar_base": (
                f"{self.sidecar_prefix}/{bundle_path.as_posix()}/"
                if self.sidecar_prefix
                else f"{bundle_path.as_posix()}/"
            ),
        }
        manifest_content = _canonical_bytes(manifest)
        refs = self._all_referenced_objects()

        bundles_root = self.final_root / "bundles"
        bundles_root.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".publish-", dir=bundles_root))
        final_bundle = self.final_root / bundle_path
        try:
            self._copy_bundle_objects(stage, refs)
            _atomic_write(stage / "manifest.json", manifest_content)
            for ref in refs:
                content = (stage / ref["path"]).read_bytes()
                if _sha256(content) != ref["sha256"] or len(content) != ref["bytes"]:
                    raise RecoveryBundleError("staged publication verification failed")
            if final_bundle.exists():
                existing_manifest = final_bundle / "manifest.json"
                if (
                    not existing_manifest.is_file()
                    or existing_manifest.read_bytes() != manifest_content
                ):
                    raise RecoveryBundleError("existing versioned recovery bundle conflicts")
                for ref in refs:
                    published_object = final_bundle / ref["path"]
                    if not published_object.is_file():
                        raise RecoveryBundleError(
                            "published recovery bundle is missing a referenced object"
                        )
                    content = published_object.read_bytes()
                    if (
                        len(content) != ref["bytes"]
                        or _sha256(content) != ref["sha256"]
                    ):
                        raise RecoveryBundleError(
                            "published recovery bundle contains a corrupt object"
                        )
                shutil.rmtree(stage)
            else:
                os.replace(stage, final_bundle)
            pointer = {
                "bundle_id": bundle_id,
                "bundle_path": bundle_path.as_posix(),
                "manifest_sha256": _sha256(manifest_content),
            }
            _atomic_write(self.final_root / "current.json", _canonical_bytes(pointer))
            return manifest
        except Exception:
            if stage.exists():
                shutil.rmtree(stage)
            raise
