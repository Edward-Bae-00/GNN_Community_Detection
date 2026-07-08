"""End-to-end smoke of the V9 baseline-vs-GNN demo on the tiny v9dev corpus.
See tasks/v9_demo_corpus_plan.md (Task 10)."""
import pathlib

import gnn.run_demo as rd

CD = pathlib.Path(__file__).resolve().parents[1] / \
    "Documents/Data/synthetic_cbp_graph_corpus_v9dev"


def test_run_demo_smoke():
    out = rd.main(
        corpus_dir=CD,
        seeds=(0,),
        n_boot=50,
        out_name="demo_smoke.json",
        epochs=1,
        ks=(50, 100),
    )
    assert {"baseline", "gnn"}.issubset(out["overall"])
    assert set(out["model_arms"]) == set(out["overall"])
    for arm in ("baseline", "gnn"):
        assert "precision@50" in out["overall"][arm]
        assert "recall@50" in out["overall"][arm]
        assert "f1@50" in out["overall"][arm]
        assert out["model_arms"][arm]["kind"] in {"baseline", "gnn"}
    assert out["hidden_total"] >= 0
