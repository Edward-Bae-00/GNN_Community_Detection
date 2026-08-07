import ast
import types
import unittest
from pathlib import Path

import numpy as np


def _load_formatter():
    source_path = Path(__file__).parents[1] / "gnn" / "sage_explainer.py"
    tree = ast.parse(source_path.read_text())
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_counterfactual_probability_mismatch_diagnostic"
    )
    namespace = {"np": np}
    exec(compile(ast.Module([function], type_ignores=[]), str(source_path), "exec"), namespace)
    return namespace[function.name]


def _load_probability_parity_policy():
    source_path = Path(__file__).parents[1] / "gnn" / "sage_explainer.py"
    tree = ast.parse(source_path.read_text())
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_probability_parity_matches"
    )
    namespace = {"np": np}
    exec(compile(ast.Module([function], type_ignores=[]), str(source_path), "exec"), namespace)
    return namespace[function.name]


def _load_sage_source_tree():
    source_path = Path(__file__).parents[1] / "gnn" / "sage_explainer.py"
    return source_path, ast.parse(source_path.read_text())


class CounterfactualDiagnosticTests(unittest.TestCase):
    def test_probability_parity_policy_uses_shared_tolerance(self):
        policy = _load_probability_parity_policy()

        self.assertTrue(policy(0.844204009, 0.844204128))
        self.assertFalse(policy(0.844, 0.845))
        self.assertFalse(policy(0.844204009, 0.844304009))

    def test_probability_parity_policy_and_sites_are_shared(self):
        _, tree = _load_sage_source_tree()
        policy = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_probability_parity_matches"
        )
        allclose_calls = [
            node for node in ast.walk(policy)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "np"
            and node.func.attr == "allclose"
        ]
        self.assertEqual(len(allclose_calls), 1)
        tolerances = {
            keyword.arg: keyword.value.value
            for keyword in allclose_calls[0].keywords
            if keyword.arg in {"rtol", "atol"}
        }
        self.assertEqual(tolerances, {"rtol": 1e-6, "atol": 1e-7})

        for function_name in (
            "__score_grouped_counterfactual",
            "compose_case_explanation",
        ):
            function = next(
                node for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)
                and node.name == function_name
            )
            helper_calls = [
                node for node in ast.walk(function)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_probability_parity_matches"
            ]
            self.assertEqual(len(helper_calls), 1)

    def test_probability_mismatch_has_bounded_context(self):
        formatter = _load_formatter()
        context = types.SimpleNamespace(
            person_id="P-1",
            row_index=1,
            scoring_day=types.SimpleNamespace(
                isoformat=lambda: "2025-01-02T00:00:00+00:00"
            ),
            same_day_person_row_indices=tuple(range(30)),
        )
        reference = types.SimpleNamespace(
            event_ids=tuple(f"event-{i}" for i in range(30))
        )
        message = formatter(
            context,
            reference,
            "sha256:" + "f" * 64,
            0.987654321,
            np.array([0.1 + i / 100 for i in range(30)]),
        )
        self.assertTrue(message.startswith(
            "affected frozen seed0 probabilities do not match the strict "
            "as-of snapshot probability"
        ))
        for field in (
            "original_recomputed_probability=",
            "frozen_probability_range=",
            "frozen_probability_values=",
            "max_abs_delta=",
            "person_id=P-1",
            "scoring_day=2025-01-02T00:00:00+00:00",
            "anchor_row=1",
            "anchor_event=event-1",
            "same_day_rows(count=30, indices=",
            "rank_reference_fingerprint=sha256:",
        ):
            self.assertIn(field, message)
        self.assertLessEqual(len(message), 1200)
        self.assertIn("...", message)
