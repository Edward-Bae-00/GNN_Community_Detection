import tempfile
import unittest
from pathlib import Path

from gnn.recovery_evidence_store import RecoveryCatalogStore


class CatalogCountEquivalenceTests(unittest.TestCase):
    """``count_active_records`` must match what ``iter_active_records`` yields.

    The bundle writer recomputes catalog sizes after every community write, and
    it used to do that by paging every row into Python. The counting query
    replaced it, so the two have to agree exactly -- including for records
    shared by several communities and for communities excluded from the active
    set.
    """

    def _store(self, tmp):
        return RecoveryCatalogStore(Path(tmp) / "catalog.sqlite3")

    def _register(self, store, community_key, kind, records):
        store.begin_community(community_key)
        for canonical_id, record in records:
            store.register(kind, canonical_id, record)
        store.commit_community()

    def _assert_agrees(self, store, kind, community_keys):
        expected = sum(
            1 for _ in store.iter_active_records(kind, community_keys, fetch_size=2)
        )
        self.assertEqual(store.count_active_records(kind, community_keys), expected)
        return expected

    def test_counts_match_across_shared_and_excluded_communities(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            try:
                self._register(
                    store,
                    "community-a",
                    "nodes",
                    [(f"node-{index}", {"node_id": f"node-{index}"}) for index in range(5)],
                )
                # "node-4" is deliberately shared, so a naive per-community sum
                # would double count it.
                self._register(
                    store,
                    "community-b",
                    "nodes",
                    [
                        ("node-4", {"node_id": "node-4"}),
                        ("node-5", {"node_id": "node-5"}),
                    ],
                )
                self._register(
                    store,
                    "community-c",
                    "edges",
                    [(f"edge-{index}", {"edge_id": f"edge-{index}"}) for index in range(3)],
                )

                self.assertEqual(
                    self._assert_agrees(store, "nodes", ["community-a", "community-b"]),
                    6,
                )
                self.assertEqual(
                    self._assert_agrees(store, "nodes", ["community-a"]), 5
                )
                self.assertEqual(self._assert_agrees(store, "edges", ["community-c"]), 3)
                # A kind with no active rows, and an active set that excludes
                # every community holding the records.
                self.assertEqual(self._assert_agrees(store, "provenance", ["community-a"]), 0)
                self.assertEqual(self._assert_agrees(store, "nodes", ["community-c"]), 0)
                self.assertEqual(self._assert_agrees(store, "nodes", []), 0)
            finally:
                store.close()

    def test_invalid_kind_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(tmp)
            try:
                with self.assertRaises(ValueError):
                    store.count_active_records("bogus", [])
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
