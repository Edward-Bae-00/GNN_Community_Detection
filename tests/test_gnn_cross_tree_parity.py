"""Explicit active-versus-schema3 GNN executable parity boundary."""

import ast
from hashlib import sha256
from pathlib import Path

from scripts.data.compare_comment_only import _DocstringStripper


ROOT = Path(__file__).resolve().parents[1]
ACTIVE = ROOT / "gnn"
BUNDLED = ROOT / "reproducibility/v9_observability_colab_schema3/gnn"
COMMON = {
    "__init__.py", "config.py", "demo_baseline.py", "demo_checkpoint.py",
    "detector.py", "explanation_narrative.py", "giant_observability_benchmark.py",
    "gnn_architecture_bakeoff.py", "graphmodel_alt.py", "graphmodel_rgcn.py",
    "learned_cell.py", "observability_artifact.py", "pu_learning.py",
    "recovery_bundle.py", "recovery_evidence_store.py",
    "recovery_observability.py", "run_demo.py", "sage_explainer.py",
    "unsupervised_ad.py", "unsupervised_features.py",
}
ACTIVE_ONLY = {"paths.py"}
BUNDLED_ONLY = set()
INTENTIONAL_DIVERGENCES = {
    "config.py", "explanation_narrative.py", "giant_observability_benchmark.py",
    "gnn_architecture_bakeoff.py", "observability_artifact.py",
    "recovery_bundle.py", "recovery_evidence_store.py", "sage_explainer.py",
    "unsupervised_ad.py",
}
ACTIVE_INTENTIONAL_FINGERPRINTS = {
    "config.py": "848ae33cd9d8d14298fa5e59cb75811b8da4b5e551077b32989c7c628c844bc6",
    "explanation_narrative.py": "a7113f2fc8c735738b52aed76a4ddfe0ca925b450915291f840e9a0f95e4d172",
    "giant_observability_benchmark.py": "cba247c797f61af4d34c5d9d70e9c2cdfe5195de97ee9e451a19487b6667aea1",
    "gnn_architecture_bakeoff.py": "0960eb30da422cddcf8e34b1022f930f1b522e4ba6596796368af51147f85c8f",
    "observability_artifact.py": "8fe1d716e0c6133f3d7cec84e27e97011f83099c72c2723924366eb4af461a8d",
    "recovery_bundle.py": "b061444e719a0f355ae8bfc68c026394bce77d8fa37e437fa0593108af45dabb",
    "recovery_evidence_store.py": "7134b2993b127ef9e18fd5153b555bccec721166546551365180d11c580f5812",
    "sage_explainer.py": "4c00348a0a77046f3c808af38f4d5bd39d5801ae5ae5946e8cd8b55346e9a7ea",
    "unsupervised_ad.py": "8caee5205d354f5299499ed3c9940e132c247b007d9eeebec8d76118e4904bfc",
}
BUNDLED_INTENTIONAL_FINGERPRINTS = {
    "config.py": "c3c9819d1c457a68c99f615389bf9a5d19e46874bdba9ac434d24c159bd017d8",
    "explanation_narrative.py": "0192c9f0f110a1b8b04bae75dace9500de9bf8756c7f8665a91632daac8e14b3",
    "giant_observability_benchmark.py": "e74e7806b51e216edd157f647c6cebced8f0e804d29bf38850094e211d74ee0e",
    "gnn_architecture_bakeoff.py": "8567a1f15952c3a87254d3f537d9ca1c05b1d690b98bf523e0ae1e689d5ed999",
    "observability_artifact.py": "e5eed8835838e3e89e50567167ce3549ab6c34fae8d51b20dc928cdc6b174204",
    "recovery_bundle.py": "3d2848e87f08a45f4dd291d651bfe666e2bb1a3de2003e9dc9cf089eba011d50",
    "recovery_evidence_store.py": "356842cc6396d24ef712ca4905c7a2ca365ffa247db6cc73f9c00b321ec2998c",
    "sage_explainer.py": "d4b85d6b1f87cb99067a724eb530634967b2e3b7dc4eebe0fb25a774de7673ab",
    "unsupervised_ad.py": "5934385d319d836547aafc71a68745ea21f2b6d14650962ea3146d909ea56228",
}
IDENTICAL_CORE = {
    "__init__.py", "demo_baseline.py", "demo_checkpoint.py", "detector.py",
    "graphmodel_alt.py", "graphmodel_rgcn.py", "learned_cell.py", "pu_learning.py",
    "recovery_observability.py", "run_demo.py", "unsupervised_features.py",
}


def _paths(package: Path) -> set[str]:
    return {path.relative_to(package).as_posix() for path in package.rglob("*.py")}


def _stable_ast_value(value):
    """Return a Python-version-stable representation of an executable AST value."""
    if isinstance(value, ast.AST):
        fields = tuple(
            (name, _stable_ast_value(field_value))
            for name, field_value in ast.iter_fields(value)
            if field_value is not None
            and not (isinstance(field_value, list) and not field_value)
        )
        return (type(value).__name__, fields)
    if isinstance(value, list):
        return tuple(_stable_ast_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_stable_ast_value(item) for item in value)
    return value


def _stable_executable_ast(source: str, filename: str):
    tree = ast.parse(source, filename=filename)
    stripped = _DocstringStripper().visit(tree)
    return _stable_ast_value(stripped)


def _syntax_fingerprint(source: str, filename: str) -> str:
    serialized = repr(_stable_executable_ast(source, filename))
    return sha256(serialized.encode("utf-8"), usedforsecurity=True).hexdigest()


def test_active_and_bundled_gnn_module_inventory_is_explicit():
    active = _paths(ACTIVE)
    bundled = _paths(BUNDLED)
    assert COMMON == IDENTICAL_CORE | INTENTIONAL_DIVERGENCES
    assert IDENTICAL_CORE.isdisjoint(INTENTIONAL_DIVERGENCES)
    assert active == COMMON | ACTIVE_ONLY
    assert bundled == COMMON | BUNDLED_ONLY
    assert active - bundled == ACTIVE_ONLY
    assert bundled - active == BUNDLED_ONLY


def test_identical_core_modules_have_equal_executable_syntax():
    for relative in sorted(IDENTICAL_CORE):
        active_dump = _stable_executable_ast(
            (ACTIVE / relative).read_text(encoding="utf-8"), f"active/{relative}"
        )
        bundled_dump = _stable_executable_ast(
            (BUNDLED / relative).read_text(encoding="utf-8"), f"bundled/{relative}"
        )
        assert active_dump == bundled_dump, relative


def test_executable_mutation_changes_stable_fingerprint():
    source = (ACTIVE / "run_demo.py").read_text(encoding="utf-8")
    mutated = source + "\nparity_mutation_probe = 1\n"
    assert _syntax_fingerprint(source, "active/run_demo.py") != _syntax_fingerprint(
        mutated, "active/run_demo.py"
    )


def test_intentional_divergence_modules_match_pinned_executable_fingerprints():
    for relative in sorted(INTENTIONAL_DIVERGENCES):
        active_fingerprint = _syntax_fingerprint(
            (ACTIVE / relative).read_text(encoding="utf-8"), f"active/{relative}"
        )
        bundled_fingerprint = _syntax_fingerprint(
            (BUNDLED / relative).read_text(encoding="utf-8"), f"bundled/{relative}"
        )
        assert active_fingerprint == ACTIVE_INTENTIONAL_FINGERPRINTS[relative], relative
        assert bundled_fingerprint == BUNDLED_INTENTIONAL_FINGERPRINTS[relative], relative
        assert active_fingerprint != bundled_fingerprint, relative
