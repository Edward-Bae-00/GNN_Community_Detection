"""Realistic tabular baseline: shape, feature set, and as-of correctness.
See tasks/v9_demo_corpus_plan.md (Task 9)."""
import pathlib

import numpy as np

from gnn.demo_baseline import build_baseline_features, FEATURE_NAMES

CD = pathlib.Path(__file__).resolve().parents[1] / \
    "Documents/Data/synthetic_cbp_graph_corpus_v9dev"


def test_realistic_baseline_shape_and_asof_counts():
    from gnn.run_demo import _build_oracle, load_pool
    obs2id = _build_oracle(CD)
    pool = load_pool(CD).head(200)
    X, names = build_baseline_features(
        pool[["event_id", "primary_obs_id", "t"]], CD, obs2id)
    assert names == FEATURE_NAMES and len(names) >= 12
    assert X.shape == (len(pool), len(FEATURE_NAMES))
    for c in ("prior_crossings", "prior_seizure", "prior_arrests"):
        assert (X[:, names.index(c)] >= 0).all()                  # as-of counts
    assert not np.isnan(X).any()
