"""Contract tests for the active and reproducibility GNN package documentation."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOTS = (
    pytest.param(REPOSITORY_ROOT / "gnn", id="active"),
    pytest.param(
        REPOSITORY_ROOT / "reproducibility" / "v9_observability_colab_schema3" / "gnn",
        id="schema3",
    ),
)
REQUIRED_ACTIVE_MODULE_SENTENCES = {
    "__init__.py": "Active leak-safe GNN anomaly-detection research package.",
    "config.py": "Runtime configuration for corpus selection and generated diagnostics.",
    "detector.py": "Scikit-learn fitting helpers shared by tabular detector experiments.",
    "graphmodel_alt.py": "Alternative GraphSAGE, GAT, GIN, and KPI-AA encoder definitions.",
    "graphmodel_rgcn.py": "Typed as-of person-graph construction and relational GNN scoring.",
    "unsupervised_ad.py": "Leak-safe unsupervised and caught-supervised anomaly evaluation.",
}

REQUIRED_ACTIVE_API_SENTENCES = {
    "demo_baseline.build_baseline_features": (
        "Build leak-safe as-of tabular features for requested crossing events."
    ),
    "demo_checkpoint.WrittenDemoCheckpoint": (
        "Paths and identity metadata for a newly written checkpoint."
    ),
    "demo_checkpoint.LoadedDemoCheckpoint": (
        "Validated models, scores, and metadata loaded from a checkpoint."
    ),
    "demo_checkpoint.read_demo_checkpoint_metadata": (
        "Read checkpoint metadata without loading model tensors or score arrays."
    ),
    "detector.fit_predict": (
        "Fit the tabular detector and return positive-class scores for the supplied rows."
    ),
    "explanation_narrative.build_prompt": (
        "Build the bounded evidence prompt used for one recovery narrative."
    ),
    "explanation_narrative.validate_candidate": (
        "Validate a generated narrative against its structured evidence contract."
    ),
    "explanation_narrative.render_template": (
        "Render the deterministic narrative fallback from validated evidence."
    ),
    "explanation_narrative.generate_narrative": (
        "Generate and validate one narrative, failing closed outside explicit template mode."
    ),
    "giant_observability_benchmark.run_benchmark": (
        "Measure schema-3 observability memory and publication behavior on the full graph."
    ),
    "giant_observability_benchmark.main": (
        "Parse CLI arguments and run the giant observability benchmark."
    ),
    "gnn_architecture_bakeoff.build_parser": (
        "Build the architecture-bakeoff command-line parser."
    ),
    "gnn_architecture_bakeoff.main": (
        "Train and compare configured GNN encoders on one corpus snapshot."
    ),
    "graphmodel_alt.SAGEEncoder": (
        "Encode person nodes with two GraphSAGE message-passing layers."
    ),
    "graphmodel_alt.GATEncoder": (
        "Encode person nodes with relation-collapsed graph attention layers."
    ),
    "graphmodel_alt.GINEncoder": (
        "Encode person nodes with graph isomorphism network layers."
    ),
    "graphmodel_alt.KPIAAEncoder": (
        "Approximate the KPI-AA comparison arm with two homogeneous graph-convolution layers."
    ),
    "graphmodel_rgcn.RelationSAGEEncoder": (
        "Encode typed person relations with two relational graph-convolution layers."
    ),
    "graphmodel_rgcn.build_anchor_graph": (
        "Build the legacy anchor graph retained for compatibility experiments."
    ),
    "graphmodel_rgcn.build_person_graph_typed": (
        "Build the timestamped lifetime person graph on canonical oracle identities."
    ),
    "graphmodel_rgcn.train_rgcn": (
        "Fit the relational encoder on the caller-supplied training mask and labels."
    ),
    "graphmodel_rgcn.asof_risk_rgcn": (
        "Score rows from graph edges available strictly before each row time."
    ),
    "learned_cell.UF": (
        "Maintain disjoint co-travel components while replaying events in time order."
    ),
    "learned_cell.DaySnapshotInputs": (
        "Frozen daily graph inputs used by relational training and scoring."
    ),
    "observability_artifact.validate_schema3_artifact": (
        "Validate in-memory schema-3 coverage, index, and fingerprint invariants."
    ),
    "observability_artifact.serialize_artifact": (
        "Serialize the legacy schema-2 artifact with inline explanation and community payloads."
    ),
    "observability_artifact.validate_artifact_invariants": (
        "Reject observability artifacts that violate leakage or schema contracts."
    ),
    "recovery_observability.RecoveryAnchor": (
        "Identify one person's first recovery event for an evaluation arm."
    ),
    "recovery_observability.DailyPoolTrace": (
        "Frozen daily candidate-pool and ranking provenance."
    ),
    "recovery_observability.RecoveryRun": (
        "Record one evaluation arm's complete daily recovery run."
    ),
    "recovery_observability.RecoveryOverlap": (
        "Overlap counts between baseline and hybrid recovery sets."
    ),
    "recovery_observability.FrozenRankReference": (
        "Freeze pool-wide rank and score arrays for deterministic reference."
    ),
    "recovery_observability.HybridOnlyCase": (
        "A hidden carrier recovered by Hybrid but missed by the baseline."
    ),
    "run_demo.evaluate": "Evaluate ranked scores at configured operational depths.",
    "run_demo.add_tiebreak": (
        "Add deterministic row-order jitter without changing rank meaningfully."
    ),
    "run_demo.load_pool": (
        "Load a split-aligned event pool with oracle fields reserved for retrospective evaluation."
    ),
    "run_demo.stratum_for_pool": (
        "Assign retrospective graph-observability strata from synthetic ground truth."
    ),
    "run_demo.paired_event_bootstrap": (
        "Bootstrap paired baseline and hybrid metrics over shared sampled events."
    ),
    "run_demo.stratum_metrics": (
        "Compute per-stratum ranking metrics for one score vector."
    ),
    "run_demo.main": "Run the leak-safe baseline-versus-GNN V9 comparison.",
    "sage_explainer.AblationSpec": (
        "Describe one evidence factor removed for a counterfactual score."
    ),
    "sage_explainer.CounterfactualContext": (
        "Freeze candidate and same-day row references for grouped counterfactual scoring."
    ),
    "sage_explainer.DaySnapshot": (
        "As-of graph, features, and scores frozen for one evaluation day."
    ),
    "sage_explainer.Seed0ExplanationEngine": (
        "Generate deterministic seed-0 GNNExplainer evidence for selected cases."
    ),
    "sage_explainer.score_grouped_counterfactual": (
        "Score grouped evidence ablations without rebuilding unchanged graph state."
    ),
    "sage_explainer.member_subgraph": (
        "Materialize the exact member-induced subgraph used by one explanation."
    ),
    "sage_explainer.make_gnn_explainer": (
        "Construct the configured PyG GNNExplainer wrapper."
    ),
    "sage_explainer.build_flow_stages": (
        "Describe how observable evidence flows through the two-hop scoring pipeline."
    ),
    "sage_explainer.aggregate_restart_masks": (
        "Aggregate restart attribution masks with completeness diagnostics."
    ),
    "sage_explainer.matched_random_controls": (
        "Select deterministic matched controls for faithfulness comparisons."
    ),
    "sage_explainer.edge_removal_faithfulness": (
        "Measure score change after removing attributed versus control edges."
    ),
    "sage_explainer.classify_factor_stability": (
        "Classify whether an evidence factor is stable across explanation restarts."
    ),
    "sage_explainer.build_ablation_specs": (
        "Build deterministic node, edge, and relation ablation specifications."
    ),
    "sage_explainer.build_complete_community": (
        "Stream the complete community while bounding the display projection."
    ),
    "unsupervised_ad.corpus_output_path": (
        "Return a corpus-qualified diagnostics path for anomaly results."
    ),
    "unsupervised_ad.main": (
        "Run deployable anomaly arms, freeze scores, then attach oracle-only evaluation."
    ),
    "unsupervised_features.FeatureBundle": (
        "Leak-safe tabular and relational feature frames plus provenance."
    ),
    "unsupervised_features.EncodedSplits": (
        "Encoded train, validation, and test matrices with frozen schemas."
    ),
}


def _python_files(package_root: Path) -> list[Path]:
    return sorted(path for path in package_root.rglob("*.py") if path.is_file())


def _public_definitions(tree: ast.Module):
    return (
        node
        for node in tree.body
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef))
        and not node.name.startswith("_")
    )


@pytest.mark.parametrize("package_root", PACKAGE_ROOTS)
def test_gnn_modules_and_public_top_level_apis_are_documented(package_root: Path):
    missing = []
    if not package_root.is_dir():
        missing.append(f"{package_root}: package root does not exist")
    paths = _python_files(package_root) if package_root.is_dir() else []
    if not paths:
        missing.append(f"{package_root}: recursive .py inventory is empty")
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if not ast.get_docstring(tree):
            missing.append(f"{path}: missing module docstring")
        for node in _public_definitions(tree):
            if not ast.get_docstring(node):
                missing.append(
                    f"{path}:{node.lineno}: missing docstring for public {node.name}"
                )
    assert not missing, "missing GNN documentation contracts:\n" + "\n".join(missing)


def test_active_required_module_docstring_first_sentences_are_stable():
    for filename, sentence in REQUIRED_ACTIVE_MODULE_SENTENCES.items():
        path = REPOSITORY_ROOT / "gnn" / filename
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        docstring = ast.get_docstring(tree, clean=False)
        assert docstring is not None
        assert docstring.strip().splitlines()[0] == sentence, path


def test_active_required_api_docstring_first_sentences_are_stable():
    missing = []
    for qualified_name, sentence in REQUIRED_ACTIVE_API_SENTENCES.items():
        module_name, symbol_name = qualified_name.split(".", 1)
        path = REPOSITORY_ROOT / "gnn" / f"{module_name}.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        node = next(
            (
                candidate
                for candidate in tree.body
                if isinstance(
                    candidate, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef)
                )
                and candidate.name == symbol_name
            ),
            None,
        )
        if node is None:
            missing.append(f"{qualified_name}: definition not found")
            continue
        docstring = ast.get_docstring(node, clean=False)
        first_sentence = (docstring or "").strip().splitlines()
        if not first_sentence or first_sentence[0] != sentence:
            actual = first_sentence[0] if first_sentence else "<missing>"
            missing.append(
                f"{qualified_name}: expected first sentence {sentence!r}; got {actual!r}"
            )
    assert len(REQUIRED_ACTIVE_API_SENTENCES) == 58
    assert not missing, "incorrect active API documentation:\n" + "\n".join(missing)
