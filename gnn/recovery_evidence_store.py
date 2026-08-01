"""Normalization helpers for immutable recovery evidence and as-of day state."""

from __future__ import annotations

import json
import hashlib
import sqlite3
from collections.abc import Mapping
from pathlib import Path


class RecoveryEvidenceStore:
    """Split canonical evidence from fields that can change between scoring days."""

    _DAY_NODE_FIELDS = frozenset(
        {
            "caught_before_snapshot",
            "caught_label_available_time",
            "message_distance",
            "pooled_member",
            "target",
            "x",
            "y",
            "layout_x",
            "layout_y",
            "cluster",
        }
    )
    _DAY_EDGE_FIELDS = frozenset(
        {"message_hop", "source_row_ids", "source_row_count"}
    )

    @staticmethod
    def _detached(value):
        return json.loads(
            json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        )

    @classmethod
    def split_node(cls, node):
        if not isinstance(node, Mapping) or not isinstance(node.get("node_id"), str):
            raise ValueError("community node requires node_id")
        detached = cls._detached(node)
        canonical = {
            key: value
            for key, value in detached.items()
            if key not in cls._DAY_NODE_FIELDS
        }
        status = {
            "node_id": detached["node_id"],
            **{
                key: detached[key]
                for key in sorted(cls._DAY_NODE_FIELDS)
                if key in detached
            },
        }
        return canonical, status

    @classmethod
    def split_edge(cls, edge):
        if not isinstance(edge, Mapping) or not isinstance(edge.get("edge_id"), str):
            raise ValueError("community edge requires edge_id")
        detached = cls._detached(edge)
        canonical = {
            key: value
            for key, value in detached.items()
            if key not in cls._DAY_EDGE_FIELDS
        }
        membership = {
            "edge_id": detached["edge_id"],
            **{
                key: detached[key]
                for key in sorted(cls._DAY_EDGE_FIELDS)
                if key in detached
            },
        }
        return canonical, membership


class RecoveryCatalogStore:
    """Disk-backed canonical catalog with transactional community membership."""

    _KINDS = frozenset({"nodes", "edges", "provenance"})

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, isolation_level=None)
        self._connection.execute("PRAGMA journal_mode=DELETE")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS records (
                record_type TEXT NOT NULL,
                canonical_id TEXT NOT NULL,
                canonical_json TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                PRIMARY KEY (record_type, canonical_id)
            );
            CREATE TABLE IF NOT EXISTS community_records (
                community_key TEXT NOT NULL,
                record_type TEXT NOT NULL,
                canonical_id TEXT NOT NULL,
                PRIMARY KEY (community_key, record_type, canonical_id),
                FOREIGN KEY (record_type, canonical_id)
                    REFERENCES records (record_type, canonical_id)
            );
            CREATE INDEX IF NOT EXISTS community_records_lookup
                ON community_records (record_type, canonical_id, community_key);
            """
        )
        self._connection.commit()
        self._active_community = None
        self.closed = False

    @property
    def in_memory_record_count(self):
        return 0

    @staticmethod
    def _canonical_json(record):
        return json.dumps(
            record,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def _validate_kind(cls, kind):
        if kind not in cls._KINDS:
            raise ValueError(f"invalid recovery catalog kind {kind!r}")

    def begin_community(self, community_key):
        self.rollback_pending()
        self._connection.execute("BEGIN IMMEDIATE")
        self._connection.execute(
            "DELETE FROM community_records WHERE community_key = ?",
            (community_key,),
        )
        self._active_community = community_key

    def register(self, kind, canonical_id, record):
        self._validate_kind(kind)
        if self._active_community is None:
            raise ValueError("recovery catalog has no active community transaction")
        canonical_json = self._canonical_json(record)
        digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
        existing = self._connection.execute(
            """
            SELECT canonical_json, sha256
            FROM records
            WHERE record_type = ? AND canonical_id = ?
            """,
            (kind, canonical_id),
        ).fetchone()
        if existing is None:
            self._connection.execute(
                """
                INSERT INTO records
                    (record_type, canonical_id, canonical_json, sha256)
                VALUES (?, ?, ?, ?)
                """,
                (kind, canonical_id, canonical_json, digest),
            )
        elif existing != (canonical_json, digest):
            raise ValueError(
                f"conflicting run-global {kind} record {canonical_id!r}"
            )
        cursor = self._connection.execute(
            """
            INSERT OR IGNORE INTO community_records
                (community_key, record_type, canonical_id)
            VALUES (?, ?, ?)
            """,
            (self._active_community, kind, canonical_id),
        )
        return cursor.rowcount == 1

    def community_counts(self, community_key):
        counts = {kind: 0 for kind in self._KINDS}
        for kind, count in self._connection.execute(
            """
            SELECT record_type, COUNT(*)
            FROM community_records
            WHERE community_key = ?
            GROUP BY record_type
            """,
            (community_key,),
        ):
            counts[kind] = count
        return counts

    def has_community_record(self, community_key, kind, canonical_id):
        self._validate_kind(kind)
        return self._connection.execute(
            """
            SELECT 1
            FROM community_records
            WHERE community_key = ? AND record_type = ? AND canonical_id = ?
            """,
            (community_key, kind, canonical_id),
        ).fetchone() is not None

    def commit_community(self):
        if self._active_community is None:
            raise ValueError("recovery catalog has no active community transaction")
        self._connection.commit()
        self._active_community = None

    def rollback_pending(self):
        if self.closed:
            return
        if self._active_community is not None:
            self._connection.rollback()
            self._active_community = None

    def _select_active_communities(self, community_keys):
        self._connection.execute(
            "CREATE TEMP TABLE IF NOT EXISTS active_communities "
            "(community_key TEXT PRIMARY KEY)"
        )
        self._connection.execute("DELETE FROM active_communities")
        self._connection.executemany(
            "INSERT INTO active_communities (community_key) VALUES (?)",
            ((key,) for key in community_keys),
        )

    def iter_active_records(self, kind, community_keys, *, fetch_size=1000):
        self._validate_kind(kind)
        self._select_active_communities(community_keys)
        cursor = self._connection.execute(
            """
            SELECT DISTINCT records.canonical_id, records.canonical_json
            FROM records
            JOIN community_records USING (record_type, canonical_id)
            JOIN active_communities USING (community_key)
            WHERE records.record_type = ?
            ORDER BY records.canonical_id
            """,
            (kind,),
        )
        while True:
            rows = cursor.fetchmany(fetch_size)
            if not rows:
                break
            for canonical_id, canonical_json in rows:
                yield canonical_id, json.loads(canonical_json)

    def close(self):
        if self.closed:
            return
        self.rollback_pending()
        self._connection.close()
        self.closed = True

    def remove_files(self):
        self.close()
        for suffix in ("", "-journal", "-wal", "-shm"):
            Path(f"{self.path}{suffix}").unlink(missing_ok=True)
