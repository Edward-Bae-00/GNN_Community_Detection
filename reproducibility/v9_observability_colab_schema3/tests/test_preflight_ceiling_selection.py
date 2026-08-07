import ast
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

try:
    from gnn import sage_explainer  # noqa: F401
except ModuleNotFoundError as exc:
    # Mirrors tests/test_diagnostics_hardening.py: keep this runnable with only
    # stdlib plus the light data dependencies. Nothing here touches the
    # explainer internals -- the summary under test is pure arithmetic over
    # already-measured counts.
    if exc.name not in {"networkx", "torch", "torch_geometric"}:
        raise
    sage_stub = types.ModuleType("gnn.sage_explainer")
    sage_stub.validate_explanation_payload = lambda payload: None
    sage_stub.json_safe = lambda value: value
    for name in (
        "CommunityScope",
        "build_flow_stages", "build_structural_community_control", "compose_case_explanation",
        "explainability_eligibility",
    ):
        setattr(sage_stub, name, object())
    sage_stub.MAX_EXPLAINER_INPUT_NODES = 128
    sage_stub.MAX_EXPLAINER_INPUT_EDGES = 256
    # Display bounds mirror production by deriving from the explainer ceiling
    # rather than being set independently.
    sage_stub.MAX_LOCAL_EXPLANATION_NODES = sage_stub.MAX_EXPLAINER_INPUT_NODES
    sage_stub.MAX_LOCAL_EXPLANATION_EDGES = sage_stub.MAX_EXPLAINER_INPUT_EDGES
    # Attribution-shaping truncation caps, serialized into the fingerprint.
    sage_stub.MAX_LOCAL_SOURCE_ROWS_PER_EDGE = 16
    sage_stub.MAX_NODE_ATTRIBUTION_SOURCE_ROWS = 16
    sage_stub.MAX_NODE_FEATURE_MASK_STATS = 512
    sys.modules["gnn.sage_explainer"] = sage_stub

try:
    import scipy  # noqa: F401
except ModuleNotFoundError as exc:
    if exc.name != "scipy":
        raise
    scipy_stub = types.ModuleType("scipy")
    scipy_stats_stub = types.ModuleType("scipy.stats")
    scipy_stats_stub.rankdata = lambda values, *args, **kwargs: values
    scipy_stub.stats = scipy_stats_stub
    sys.modules["scipy"] = scipy_stub
    sys.modules["scipy.stats"] = scipy_stats_stub

from gnn import observability_artifact as artifact
import run_schema3_observability as runner


def _preflight(*sizes):
    return {
        f"case:P{index:05d}": {"node_count": nodes, "edge_count": edges}
        for index, (nodes, edges) in enumerate(sizes)
    }


class PreflightSizeSummaryTests(unittest.TestCase):
    def test_ceiling_grid_requires_both_limits(self):
        # The second candidate is small in nodes but far over in edges, so a
        # ceiling that admits it on nodes alone must still exclude it.
        summary = artifact._preflight_size_summary(
            _preflight((100, 200), (100, 9000), (5000, 9000))
        )
        by_ceiling = {
            (row["max_nodes"], row["max_edges"]): row["eligible"]
            for row in summary["ceiling_grid"]
        }
        self.assertEqual(by_ceiling[(128, 256)], 1)
        self.assertEqual(by_ceiling[(128, 512)], 1)
        self.assertEqual(by_ceiling[(8192, 16384)], 3)
        self.assertEqual(summary["candidates"], 3)

    def test_grid_is_monotonic_in_both_dimensions(self):
        summary = artifact._preflight_size_summary(
            _preflight(*[(nodes, nodes * 3) for nodes in range(50, 5050, 50)])
        )
        rows = summary["ceiling_grid"]
        for smaller, larger in zip(rows, rows[1:]):
            if (
                larger["max_nodes"] >= smaller["max_nodes"]
                and larger["max_edges"] >= smaller["max_edges"]
            ):
                self.assertGreaterEqual(larger["eligible"], smaller["eligible"])

    def test_percentiles_and_smallest_are_reported(self):
        summary = artifact._preflight_size_summary(
            _preflight(*[(nodes, nodes * 2) for nodes in (10, 20, 30, 40, 50)])
        )
        self.assertEqual(summary["percentiles"]["node_count"]["p0"], 10)
        self.assertEqual(summary["percentiles"]["node_count"]["p100"], 50)
        self.assertEqual(summary["percentiles"]["edge_count"]["p100"], 100)
        self.assertEqual(
            summary["smallest_by_nodes"][0],
            {"node_count": 10, "edge_count": 20},
        )

    def test_empty_preflight_is_not_an_error(self):
        summary = artifact._preflight_size_summary({})
        self.assertEqual(summary["candidates"], 0)
        self.assertEqual(summary["ceiling_grid"], [])


class CeilingEqualityTests(unittest.TestCase):
    """The display bound must stay tied to the explainer ceiling.

    ``materialize_local`` picks displayed nodes before attribution exists, and
    ``compose_case_explanation`` drops mask records for whatever it left out. A
    display bound below the explainer ceiling therefore silently turns
    ``top_local_nodes``/``top_edges`` into "top among displayed", which the
    narrative then states as the top attribution outright. Reading the source
    rather than the imported values is deliberate: under the stub both are
    integers, so only the source shows whether the link still exists.
    """

    def _module_assignments(self):
        source = Path(__file__).resolve().parent.parent / "gnn" / "sage_explainer.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        assignments = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assignments[target.id] = node.value
        return assignments

    def test_display_bounds_are_defined_from_the_explainer_ceiling(self):
        assignments = self._module_assignments()
        for display, explainer in (
            ("MAX_LOCAL_EXPLANATION_NODES", "MAX_EXPLAINER_INPUT_NODES"),
            ("MAX_LOCAL_EXPLANATION_EDGES", "MAX_EXPLAINER_INPUT_EDGES"),
        ):
            self.assertIn(display, assignments)
            value = assignments[display]
            self.assertIsInstance(
                value,
                ast.Name,
                f"{display} must be defined as {explainer}, not an independent "
                "literal, or published attribution silently becomes partial",
            )
            self.assertEqual(value.id, explainer)

    def test_explainer_ceilings_are_plain_integer_literals(self):
        assignments = self._module_assignments()
        for name in ("MAX_EXPLAINER_INPUT_NODES", "MAX_EXPLAINER_INPUT_EDGES"):
            value = assignments[name]
            self.assertIsInstance(value, ast.Constant)
            self.assertIsInstance(value.value, int)


class _FingerprintEngine:
    def observability_fingerprint_material(self):
        return {"engine": "fingerprint-material"}


class StagingFingerprintTests(unittest.TestCase):
    """The eligibility ceiling has to be part of the staging identity.

    The staging directory id is derived from this fingerprint. If the ceiling
    were left out, a run under a new ceiling would resume into a bundle staged
    under the old one and replay community-only payloads as explanations.
    """

    def _fingerprint(self):
        return artifact._recovery_run_fingerprint(
            _FingerprintEngine(),
            corpus_identity="corpus-identity",
            seeds=(0, 1, 2),
            recovery_run_identity={"checkpoint_id": "checkpoint"},
        )

    def test_policy_records_the_explainer_ceiling(self):
        policy = self._fingerprint()["policy"]
        self.assertEqual(
            policy["explainer_max_nodes"], artifact.MAX_EXPLAINER_INPUT_NODES
        )
        self.assertEqual(
            policy["explainer_max_edges"], artifact.MAX_EXPLAINER_INPUT_EDGES
        )

    def test_policy_records_the_display_bound(self):
        # The display bound decides what evidence is staged and how much
        # attribution survives into it, so it belongs in the staging identity
        # alongside the input ceiling.
        policy = self._fingerprint()["policy"]
        self.assertEqual(
            policy["display_max_nodes"], artifact.MAX_LOCAL_EXPLANATION_NODES
        )
        self.assertEqual(
            policy["display_max_edges"], artifact.MAX_LOCAL_EXPLANATION_EDGES
        )

    def test_changing_the_ceiling_changes_the_fingerprint(self):
        before = json.dumps(self._fingerprint(), sort_keys=True)
        original = artifact.MAX_EXPLAINER_INPUT_NODES
        artifact.MAX_EXPLAINER_INPUT_NODES = original * 4
        try:
            after = json.dumps(self._fingerprint(), sort_keys=True)
        finally:
            artifact.MAX_EXPLAINER_INPUT_NODES = original
        self.assertNotEqual(before, after)


class AttributionCapFingerprintTests(unittest.TestCase):
    """Truncation caps shape published attribution, so they bind staging too.

    Without them in the fingerprint, lowering a cap and re-running would resume
    into and reuse explanations staged under the previous truncation policy.
    """

    def _policy(self):
        return artifact._recovery_run_fingerprint(
            _FingerprintEngine(),
            corpus_identity="corpus-identity",
            seeds=(0, 1, 2),
            recovery_run_identity={"checkpoint_id": "checkpoint"},
        )["policy"]

    def test_every_attribution_shaping_cap_is_recorded(self):
        policy = self._policy()
        self.assertEqual(
            policy["max_source_rows_per_edge"],
            artifact.MAX_LOCAL_SOURCE_ROWS_PER_EDGE,
        )
        self.assertEqual(
            policy["max_node_attribution_source_rows"],
            artifact.MAX_NODE_ATTRIBUTION_SOURCE_ROWS,
        )
        self.assertEqual(
            policy["max_node_feature_mask_stats"],
            artifact.MAX_NODE_FEATURE_MASK_STATS,
        )

    def test_changing_a_cap_changes_the_fingerprint(self):
        before = json.dumps(self._policy(), sort_keys=True)
        original = artifact.MAX_LOCAL_SOURCE_ROWS_PER_EDGE
        artifact.MAX_LOCAL_SOURCE_ROWS_PER_EDGE = original * 2
        try:
            after = json.dumps(self._policy(), sort_keys=True)
        finally:
            artifact.MAX_LOCAL_SOURCE_ROWS_PER_EDGE = original
        self.assertNotEqual(before, after)


class AttributionCompletenessFlagTests(unittest.TestCase):
    """A payload that cannot demonstrate coverage is not certified as exact."""

    def test_complete_true_is_recognised(self):
        self.assertTrue(
            artifact._schema3_attribution_complete(
                {"attribution_completeness": {"complete": True}}
            )
        )

    def test_complete_false_is_rejected(self):
        self.assertFalse(
            artifact._schema3_attribution_complete(
                {"attribution_completeness": {"complete": False}}
            )
        )

    def test_missing_block_is_rejected(self):
        self.assertFalse(artifact._schema3_attribution_complete({}))

    def test_malformed_block_is_rejected(self):
        for block in (None, "complete", [], {"complete": "yes"}, {"complete": 1}):
            with self.subTest(block=block):
                self.assertFalse(
                    artifact._schema3_attribution_complete(
                        {"attribution_completeness": block}
                    )
                )

    def test_non_mapping_payload_is_rejected(self):
        self.assertFalse(artifact._schema3_attribution_complete(None))


class MaskAggregationSourceTests(unittest.TestCase):
    """Masks must be aggregated from complete per-edge source-row membership.

    Mask records are keyed by source row. Aggregating them against the
    displayed list silently discards the weight of every row past
    MAX_LOCAL_SOURCE_ROWS_PER_EDGE, which this corpus produces routinely --
    co-travel pair groups reach 64 source rows and shared-residence groups
    reach 1144. The check is structural because exercising the real path needs
    Torch and PyG.
    """

    def _source(self):
        path = Path(__file__).resolve().parent.parent / "gnn" / "sage_explainer.py"
        return path.read_text(encoding="utf-8")

    def test_display_projection_records_complete_membership(self):
        tree = ast.parse(self._source())
        candidate_edges = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "candidate_edges"
        ]
        self.assertEqual(len(candidate_edges), 1)
        calls = [
            node
            for node in ast.walk(candidate_edges[0])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_edge_record"
        ]
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            [keyword.arg for keyword in calls[0].keywords],
            [],
            "candidate_edges must read complete source rows; passing "
            "source_limit here truncates the membership masks are keyed by",
        )

    def test_mask_aggregation_consumes_the_complete_index(self):
        source = self._source()
        self.assertIn("complete_source_rows = community.pop(", source)
        self.assertIn("COMPLETE_SOURCE_ROW_INDEX", source)

    def test_complete_index_never_reaches_a_published_payload(self):
        # It is popped before the community is embedded in the payload.
        source = self._source()
        self.assertLess(
            source.index("complete_source_rows = community.pop("),
            source.index('"community": community,'),
        )


class PreflightOnlyRunnerTests(unittest.TestCase):
    def test_preflight_only_stops_the_run_and_writes_the_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            progress = Path(tmp) / "progress.json"
            distribution = Path(tmp) / "preflight_distribution.json"
            on_stage = runner._progress_callback(
                progress, preflight_only_out=distribution
            )
            on_stage("preparation_start", {"stage": "preparation_start"})
            self.assertFalse(distribution.exists())

            payload = {"eligible_hybrid": 10, "size_summary": {"candidates": 268}}
            with self.assertRaises(runner._PreflightOnlyComplete) as raised:
                on_stage("preflight_complete", payload)
            self.assertEqual(raised.exception.summary_path, distribution)
            self.assertEqual(
                json.loads(distribution.read_text(encoding="utf-8")), payload
            )

    def test_normal_run_is_not_interrupted_at_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            progress = Path(tmp) / "progress.json"
            on_stage = runner._progress_callback(progress)
            on_stage("preflight_complete", {"eligible_hybrid": 10})
            self.assertEqual(
                json.loads(progress.read_text(encoding="utf-8"))["stage"],
                "preflight_complete",
            )

    def test_report_renders_a_written_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "preflight_distribution.json"
            summary_path.write_text(
                json.dumps(
                    {
                        "eligible_hybrid": 10,
                        "max_nodes": 128,
                        "max_edges": 256,
                        "size_summary": artifact._preflight_size_summary(
                            _preflight((100, 200), (1000, 4000))
                        ),
                    }
                ),
                encoding="utf-8",
            )
            # Rendering must not raise on a real summary shape; the report is
            # the only thing an operator sees before choosing a ceiling.
            runner._report_preflight_only(summary_path)


if __name__ == "__main__":
    unittest.main()
