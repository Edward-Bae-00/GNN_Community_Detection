"""Contract tests for the active and reproducibility GNN package documentation."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGES = (
    pytest.param("active", REPOSITORY_ROOT / "gnn", id="active"),
    pytest.param(
        "schema3",
        REPOSITORY_ROOT / "reproducibility" / "v9_observability_colab_schema3" / "gnn",
        id="schema3",
    ),
)
SHARED_REQUIRED_MODULE_SENTENCES = {
    "config.py": "Runtime configuration for corpus selection and generated diagnostics.",
    "detector.py": "Scikit-learn fitting helpers shared by tabular detector experiments.",
    "graphmodel_alt.py": "Alternative GraphSAGE, GAT, GIN, and KPI-AA encoder definitions.",
    "graphmodel_rgcn.py": "Typed as-of person-graph construction and relational GNN scoring.",
    "unsupervised_ad.py": "Leak-safe unsupervised and caught-supervised anomaly evaluation.",
}
REQUIRED_MODULE_SENTENCES_BY_PACKAGE = {
    "active": {
        "__init__.py": "Active leak-safe GNN anomaly-detection research package.",
        **SHARED_REQUIRED_MODULE_SENTENCES,
    },
    "schema3": {
        "__init__.py": "Bundled schema-3 GNN reproducibility snapshot.",
        **SHARED_REQUIRED_MODULE_SENTENCES,
    },
}

REQUIRED_API_SENTENCES = {
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

RUN_DEMO_PATHS = (
    REPOSITORY_ROOT / "gnn" / "run_demo.py",
    REPOSITORY_ROOT
    / "reproducibility"
    / "v9_observability_colab_schema3"
    / "gnn"
    / "run_demo.py",
)


def _top_level_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


@pytest.mark.parametrize("path", RUN_DEMO_PATHS, ids=lambda path: str(path.parent))
def test_run_demo_documents_default_graphsage_late_fusion_contract(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    main = _top_level_function(tree, "main")
    defaults = dict(
        zip(
            [argument.arg for argument in main.args.args[-len(main.args.defaults) :]],
            main.args.defaults,
        )
    )

    assert ast.literal_eval(defaults["seeds"]) == (0, 1, 2)
    assert ast.literal_eval(defaults["gnn_arm"]) == "sage"

    module_docstring = (ast.get_docstring(tree) or "").lower()
    for required_phrase in (
        "three-seed graphsage",
        "rank-normalized",
        "validation-tuned convex late rank fusion",
        "caught labels available to deployment",
    ):
        assert required_phrase in module_docstring


def test_data_guide_describes_active_graphsage_rank_fusion_arm():
    guide = (REPOSITORY_ROOT / "docs" / "data" / "DATA_GUIDE.md").read_text(
        encoding="utf-8"
    )
    guide_normalized = " ".join(guide.split())
    assert (
        "as-of caught-propagation RGCN, and a hybrid method that combines them"
        not in guide
    )
    assert "out-of-fold GNN scores" not in guide_normalized
    assert "GNN scores to train a gradient boosting model (HGB)" not in guide_normalized
    for required_phrase in (
        "three-seed GraphSAGE caught-propagation arm",
        "validation-tuned convex late rank fusion",
        "caught labels available to deployment",
        "graphmodel_alt.py",
        "default GraphSAGE arm",
        "graphmodel_rgcn.py",
        "optional RGCN model",
    ):
        assert required_phrase in guide


def _contains_artifact_contradiction(text: str) -> bool:
    normalized = " ".join(text.split())
    contradiction_context = (
        r"(?:architecture(?:\s+comparison)?|rgcn|dashboard\s+(?:payload|data)|"
        r"release\s+input|(?:comparison\s+)?artifact)"
    )
    contradiction = (
        r"(?:absent|ignored|generated(?:[-\s]+(?:only|and[-\s]+ignored))?|"
        r"(?:needs?|requires?|requiring)\s+regeneration|cannot\s+render)"
    )
    protected = re.sub(
        rf"(?i)\bnot\s+{contradiction}\b", "", normalized
    )
    return re.search(
        rf"(?i)(?:{contradiction_context})[^.!?]{{0,120}}{contradiction}"
        rf"|{contradiction}[^.!?]{{0,120}}(?:{contradiction_context})",
        protected,
    ) is not None


@pytest.mark.parametrize(
    ("text", "is_contradiction"),
    (
        ("The architecture artifact is not ignored.", False),
        ("The release input is not generated-only.", False),
        ("The artifact is not requiring regeneration.", False),
        ("The architecture artifact is absent.", True),
        ("The architecture artifact is ignored.", True),
        ("The release input is generated-only.", True),
        ("The release input is generated-and-ignored.", True),
        ("The release input is generated and ignored.", True),
        ("The release input is not generated-and-ignored.", False),
        ("The release input is not unrelated and ignored.", True),
        ("The dashboard payload requires regeneration.", True),
        ("The comparison artifact cannot render.", True),
        ("The architecture\nartifact is not ignored.", False),
    ),
)
def test_artifact_contradiction_probe_is_negation_aware(
    text: str, is_contradiction: bool
):
    assert _contains_artifact_contradiction(text) is is_contradiction


def test_results_docs_publish_current_rgcn_and_preserve_historical_table():
    changes = (REPOSITORY_ROOT / "docs/research/changes_3.md").read_text(
        encoding="utf-8"
    )
    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
    guide = (REPOSITORY_ROOT / "docs/data/DATA_GUIDE.md").read_text(
        encoding="utf-8"
    )
    current_marker = "### Current artifact-backed RGCN result (40,578-row release)"
    historical_marker = (
        "### Historical RGCN-era result (38,948-row run; artifact unavailable)"
    )
    assert current_marker in changes
    assert historical_marker in changes
    current_start = changes.index(current_marker)
    historical_start = changes.index(historical_marker)
    assert current_start < historical_start
    historical_tail = changes[historical_start + len(historical_marker) :]
    next_result_heading = re.search(r"^#{1,3}\s+", historical_tail, re.MULTILINE)
    assert next_result_heading is not None
    current = changes[current_start + len(current_marker) : historical_start]
    historical = historical_tail[: next_result_heading.start()]

    def table_rows(section: str, header: str) -> list[str]:
        lines = section.splitlines()
        header_index = lines.index(header)
        assert re.fullmatch(r"\|\s*:?-+:?\s*\|.*", lines[header_index + 1])
        rows = []
        for line in lines[header_index + 2 :]:
            if not line.startswith("|"):
                break
            rows.append(line)
        return rows

    assert table_rows(
        current, "| K | Baseline recall | RGCN found | RGCN recall |"
    ) == [
        "| 500 | 0.0149 | 144 | 0.0535 |",
        "| 2,000 | 0.0710 | 538 | 0.1999 |",
        "| 5,000 | 0.1557 | 1,030 | 0.3828 |",
    ]
    assert table_rows(
        historical, "| K | baseline R@K | GNN R@K | GNN found − base (p) |"
    ) == [
        "| 500  | 0.039 | 0.056 | +49  (p=0) |",
        "| 2000 | 0.091 | **0.261** | +455 (p=0) |",
        "| 5000 | 0.175 | **0.403** | +609 (p=0) |",
    ]

    current_normalized = " ".join(current.split())
    for required_phrase in (
        "gnn/diagnostics/demo_comparison_v9.json",
        "gnn/diagnostics/gnn_architecture_comparison_v9.json",
        "corpus logical name, oracle substrate, pool=40,578, hidden=2,691, strata 708/234/1749, seeds 0/1/2, epochs18, Q bucket",
        "d4b5d349532ca949f11a3c1df59f27b4323189e06ae6099d7310dac3fc7ad35a",
        "no checkpoint or score arrays",
        "cross-artifact comparison",
        "GraphSAGE remains the active runtime default",
        "frozen-artifact verifiable, not exactly retrainable",
    ):
        assert required_phrase in current_normalized
    assert "p=0" not in current_normalized
    assert (
        "No p-values or bootstrap significance transfer from the historical run."
        in current_normalized
    )

    required_sentence = (
        "GraphSAGE remains the active runtime default; the committed 40,578-row "
        "RGCN architecture artifact is frozen-artifact verifiable, not exactly retrainable."
    )
    diagnostic_paths = (
        "gnn/diagnostics/demo_comparison_v9.json",
        "gnn/diagnostics/gnn_architecture_comparison_v9.json",
    )
    readme_evidence = readme.split("## Current V9 evidence", 1)[1].split(
        "## Repository layout", 1
    )[0]
    guide_results = guide.split("## Current Results", 1)[1].split(
        "## Data Realism And Interdiction Rates", 1
    )[0]
    for document, evidence in ((readme, readme_evidence), (guide, guide_results)):
        normalized = " ".join(document.split())
        evidence_normalized = " ".join(evidence.split())
        assert required_sentence in normalized
        assert (
            "current demo diagnostic is the committed "
            "`gnn/diagnostics/demo_comparison_v9.json`"
        ) in evidence_normalized
        assert (
            "`gnn/diagnostics/gnn_architecture_comparison_v9.json` is the current "
            "architecture comparison artifact"
        ) in evidence_normalized
        assert "38,948-row" in document
        assert "historical" in normalized.lower()
        assert "artifact unavailable" in normalized.lower()

    assert table_rows(
        guide_results, "| K | Baseline recall | RGCN found | RGCN recall |"
    ) == [
        "| 500 | 0.0149 | 144 | 0.0535 |",
        "| 2,000 | 0.0710 | 538 | 0.1999 |",
        "| 5,000 | 0.1557 | 1,030 | 0.3828 |",
    ]
    dashboard_diagnostics = guide.split(
        "## Dashboard And Explorer Artifacts", 1
    )[1].split("## Current Regression Coverage", 1)[0]
    dashboard_normalized = " ".join(dashboard_diagnostics.split())
    assert (
        "After a fresh clone is hydrated with Git LFS, the dashboard can render "
        "canonical corpus content plus the committed schema-3 explanation evidence "
        "and the current architecture comparison release input."
    ) in dashboard_normalized
    assert not _contains_artifact_contradiction(dashboard_normalized)

    readme_normalized = " ".join(readme.split())
    guide_normalized = " ".join(guide.split())
    changes_normalized = " ".join(changes.split())
    assert "V8 is historical honest-track context only." in readme
    assert "V8 remains important because it is the honest, realistic track. V9 does not replace it." in guide_normalized
    assert "graph edges and caught labels used for a row are available before that row's time `T`" in readme_normalized
    assert "Edges and caught labels are only used when available strictly before the scoring time." in guide_normalized
    assert "V8 remains historical context; its corpus is absent from the organized checkout." in changes_normalized
    assert "strict as-of fail-closed behavior" in changes_normalized
    assert "degraded 19-of-20 archive and is not fully passing or coverage-gated." in readme_normalized


def test_current_results_guide_does_not_transfer_historical_top_k_inference():
    guide = (REPOSITORY_ROOT / "docs" / "data" / "DATA_GUIDE.md").read_text(
        encoding="utf-8"
    )
    current_results = guide.split("## Current Results", 1)[1].split(
        "## Data Realism And Interdiction Rates", 1
    )[0]
    normalized = " ".join(current_results.split())
    assert "Top-K is a wash at K <= 100;" not in normalized
    assert (
        "The current cross-artifact RGCN comparison has no paired-bootstrap inference; "
        "the historical K<=100 wash statement is not transferred to the current release."
        in normalized
    )


def _python_files(package_root: Path) -> list[Path]:
    return sorted(path for path in package_root.rglob("*.py") if path.is_file())


def _public_definitions(tree: ast.Module):
    return (
        node
        for node in tree.body
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef))
        and not node.name.startswith("_")
    )


@pytest.mark.parametrize(("package_name", "package_root"), PACKAGES)
def test_gnn_modules_and_public_top_level_apis_are_documented(
    package_name: str, package_root: Path
):
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


@pytest.mark.parametrize(("package_name", "package_root"), PACKAGES)
def test_required_gnn_docstring_first_sentences_are_stable(
    package_name: str, package_root: Path
):
    missing = []
    required_module_sentences = REQUIRED_MODULE_SENTENCES_BY_PACKAGE[package_name]
    for filename, sentence in required_module_sentences.items():
        path = package_root / filename
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        docstring = ast.get_docstring(tree, clean=False)
        first_sentence = (docstring or "").strip().splitlines()
        if not first_sentence or first_sentence[0] != sentence:
            actual = first_sentence[0] if first_sentence else "<missing>"
            missing.append(
                f"{filename}: expected first sentence {sentence!r}; got {actual!r}"
            )
    for qualified_name, sentence in REQUIRED_API_SENTENCES.items():
        module_name, symbol_name = qualified_name.split(".", 1)
        path = package_root / f"{module_name}.py"
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
    assert len(REQUIRED_API_SENTENCES) == 58
    assert not missing, "incorrect GNN documentation:\n" + "\n".join(missing)
