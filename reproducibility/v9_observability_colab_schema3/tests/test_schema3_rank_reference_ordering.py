"""Regression: the schema-3 bundle must bind its rank reference before it
fingerprints the engine.

``_build_schema3_bundle`` derives the resumable staging identity from
``observability_fingerprint_material()``, and that material includes the
engine's ``rank_reference_fingerprint``.  The engine therefore has to be bound
*before* the fingerprint is taken.  When the bind happened later (inside
``_build_schema3_artifact``) every schema-3 run died with
``ValueError: observability fingerprint requires a rank reference`` before any
GNNExplainer or narrative work started.
"""

import sys
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from gnn import explanation_narrative as _narrative  # noqa: F401
except ModuleNotFoundError as exc:
    # Mirrors tests/test_diagnostics_hardening.py: keep this runnable with only
    # stdlib plus the light data dependencies. Production imports the real
    # modules; nothing under test here touches the explainer internals.
    if exc.name not in {"networkx", "torch", "torch_geometric"}:
        raise
    sage_stub = types.ModuleType("gnn.sage_explainer")
    sage_stub.validate_explanation_payload = lambda payload: None
    # _detached_json_object round-trips the fingerprint material through
    # json_safe, so this one has to stay a real passthrough.
    sage_stub.json_safe = lambda value: value
    for name in (
        "CommunityScope",
        "build_flow_stages", "build_structural_community_control", "compose_case_explanation",
        "explainability_eligibility",
    ):
        setattr(sage_stub, name, object())
    # The explainer eligibility ceiling is part of the staging fingerprint, so
    # it gets serialized rather than merely passed around: it has to be a real
    # integer here, not an opaque sentinel.
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

    def _rankdata(values, method="average"):
        """Average-rank fallback so build_rank_reference stays truthful when
        SciPy is absent; the ordering assertion does not depend on it, but a
        silently wrong reference would make the test meaningless."""
        if method != "average":
            raise NotImplementedError(method)
        values = np.asarray(values, dtype=float)
        ranks = np.empty(values.shape, dtype=float)
        ranks[values.argsort(kind="mergesort")] = np.arange(
            1, values.size + 1, dtype=float
        )
        for value in np.unique(values):
            tied = values == value
            if tied.sum() > 1:
                ranks[tied] = ranks[tied].mean()
        return ranks

    scipy_stub = types.ModuleType("scipy")
    scipy_stats_stub = types.ModuleType("scipy.stats")
    scipy_stats_stub.rankdata = _rankdata
    scipy_stub.stats = scipy_stats_stub
    sys.modules["scipy"] = scipy_stub
    sys.modules["scipy.stats"] = scipy_stats_stub

from gnn import observability_artifact as artifact


class _StopAfterFingerprint(Exception):
    """Raised by the stub writer factory to end the run once the staging
    identity has been derived; everything past that point is out of scope."""


class _RecordingEngine:
    """Minimal stand-in for Seed0ExplanationEngine's fingerprint contract.

    ``observability_fingerprint_material`` raises exactly like the real engine
    (gnn/sage_explainer.py) when no rank reference is bound, so the ordering
    defect reproduces without torch/networkx.
    """

    def __init__(self):
        self.calls = []
        self._rank_state = None

    def bind_rank_reference(self, reference, row_bindings):
        self.calls.append("bind_rank_reference")
        self._rank_state = (reference, row_bindings)

    def observability_fingerprint_material(self):
        self.calls.append("observability_fingerprint_material")
        if self._rank_state is None:
            raise ValueError("observability fingerprint requires a rank reference")
        return {
            "graph_sha256": "0" * 64,
            "model_state_sha256": "1" * 64,
            "rank_reference_fingerprint": "2" * 64,
        }


def _pool(n_rows=4):
    return pd.DataFrame(
        {
            "event_id": [f"E-{index}" for index in range(n_rows)],
            "primary_person_id": [f"P-{index}" for index in range(n_rows)],
            "t": pd.to_datetime(
                [f"2025-01-0{index + 1}T00:00:00Z" for index in range(n_rows)],
                utc=True,
            ),
            "hidden": [False] * n_rows,
        }
    )


class Schema3RankReferenceOrderingTests(unittest.TestCase):
    def _run_bundle(self, engine, staging, final):
        def writer_factory(*args, **kwargs):
            raise _StopAfterFingerprint

        pool = _pool()
        n_rows = len(pool)
        return artifact._build_schema3_bundle(
            pool=pool,
            baseline_raw=np.linspace(0.1, 0.9, n_rows),
            seed0_gnn_raw=np.linspace(0.9, 0.1, n_rows),
            blend_weight=0.75,
            caught_times={},
            gnn_arm="sage",
            surrounding_seeds=(0, 1, 2),
            explanation_engine=engine,
            seed_level_unique_person_recovery={},
            staging_root=staging,
            final_root=final,
            explanation_limit=None,
            hybrid_detail_limit=20,
            baseline_control_limit=10,
            inspections_per_day=5,
            narrative_builder=lambda packet: {},
            corpus_identity="corpus-identity",
            recovery_run_identity={"checkpoint_id": "checkpoint"},
            instrumentation=None,
            narrative_preflight=None,
            writer_factory=writer_factory,
        )

    def test_rank_reference_is_bound_before_the_engine_is_fingerprinted(self):
        engine = _RecordingEngine()
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            final = Path(tmp) / "final"
            # Reaching the writer factory means the staging identity was
            # derived successfully; the rank-reference ValueError would have
            # been raised before this point.
            with self.assertRaises(_StopAfterFingerprint):
                self._run_bundle(engine, staging, final)

        self.assertIn("bind_rank_reference", engine.calls)
        self.assertIn("observability_fingerprint_material", engine.calls)
        self.assertLess(
            engine.calls.index("bind_rank_reference"),
            engine.calls.index("observability_fingerprint_material"),
            "the rank reference must be bound before the engine is fingerprinted",
        )


if __name__ == "__main__":
    unittest.main()
