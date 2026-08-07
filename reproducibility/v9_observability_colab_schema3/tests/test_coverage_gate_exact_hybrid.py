import unittest

import run_schema3_observability as runner


def _coverage(**overrides):
    """A coverage block that passes the gate, before overrides are applied."""
    base = {
        "narrative_preflight_failed": 0,
        "failed_count": 0,
        "narrative_fallback": 0,
        "hybrid_explained": 20,
        "hybrid_attribution_complete": 20,
        "hybrid_structural_fallback": 0,
        "hybrid_available": 268,
        "hybrid_eligible": 24,
        "baseline_available": 113,
        "baseline_community": 10,
    }
    base.update(overrides)
    return base


def _gate(coverage, *, hybrid_detail_limit=20, baseline_control_limit=10):
    return runner._evaluate_coverage_gate(
        coverage,
        hybrid_detail_limit=hybrid_detail_limit,
        baseline_control_limit=baseline_control_limit,
    )


class ExactHybridBudgetTests(unittest.TestCase):
    """The gate must certify the goal: every Hybrid case actually explained.

    Structural fallbacks are community-only evidence, not GNNExplainer
    explanations. Counting them as interchangeable with explanations is what let
    a 10-explained run exit successfully against a 20-case budget.
    """

    def test_twenty_exact_passes(self):
        self.assertEqual(_gate(_coverage()), [])

    def test_ten_plus_ten_fails(self):
        reasons = _gate(
            _coverage(hybrid_explained=10, hybrid_structural_fallback=10)
        )
        self.assertTrue(reasons)
        joined = " ".join(reasons)
        self.assertIn("hybrid_structural_fallback=10", joined)
        self.assertIn("hybrid_explained=10", joined)

    def test_nineteen_plus_one_fails(self):
        reasons = _gate(
            _coverage(hybrid_explained=19, hybrid_structural_fallback=1)
        )
        self.assertTrue(reasons)
        self.assertIn("hybrid_structural_fallback=1", " ".join(reasons))

    def test_nineteen_exact_and_no_fallback_still_fails(self):
        # A short budget is a failure even with nothing downgraded: 19 exact
        # explanations is not the 20 the run was asked for.
        reasons = _gate(
            _coverage(hybrid_explained=19, hybrid_structural_fallback=0)
        )
        self.assertTrue(reasons)
        self.assertIn("hybrid_explained=19", " ".join(reasons))

    def test_failure_names_the_ceiling_when_eligibility_is_binding(self):
        # The actionable diagnostic is "the ceiling admitted too few", not
        # "the budget is short".
        reasons = _gate(
            _coverage(
                hybrid_explained=10, hybrid_structural_fallback=10,
                hybrid_eligible=10,
            )
        )
        joined = " ".join(reasons)
        self.assertIn("hybrid_eligible=10", joined)
        self.assertIn("MAX_EXPLAINER_INPUT", joined)

    def test_eligible_pool_is_not_blamed_when_it_was_sufficient(self):
        # 24 eligible but only 19 explained means cases failed, not that the
        # ceiling was too low, so the ceiling must not be blamed.
        reasons = _gate(_coverage(hybrid_explained=19))
        self.assertNotIn("MAX_EXPLAINER_INPUT", " ".join(reasons))


class AttributionCompletenessTests(unittest.TestCase):
    """Partial attribution must not be certified as an exact explanation.

    A payload whose ranked attribution omitted mask records still publishes
    ``top_local_nodes``/``top_edges``, and the narrative quotes them as the top
    attribution outright. Counting such a case as exact is what would let 20
    incomplete payloads satisfy an "exact 20" gate.
    """

    def test_all_complete_passes(self):
        self.assertEqual(_gate(_coverage()), [])

    def test_one_incomplete_case_fails(self):
        reasons = _gate(_coverage(hybrid_attribution_complete=19))
        self.assertTrue(reasons)
        joined = " ".join(reasons)
        self.assertIn("hybrid_attribution_complete=19", joined)
        self.assertIn("hybrid_explained=20", joined)

    def test_all_incomplete_fails_even_with_a_full_budget(self):
        reasons = _gate(_coverage(hybrid_attribution_complete=0))
        self.assertTrue(reasons)
        self.assertIn("hybrid_attribution_complete=0", " ".join(reasons))

    def test_small_pool_also_requires_complete_attribution(self):
        reasons = _gate(
            _coverage(
                hybrid_available=5, hybrid_eligible=5, hybrid_explained=5,
                hybrid_attribution_complete=4,
            )
        )
        self.assertTrue(reasons)

    def test_completeness_is_not_double_reported_when_budget_is_short(self):
        # A short budget with matching completeness is one problem, not two.
        reasons = _gate(
            _coverage(hybrid_explained=19, hybrid_attribution_complete=19)
        )
        self.assertNotIn("hybrid_attribution_complete", " ".join(reasons))


class ZeroExplainedDiagnosticTests(unittest.TestCase):
    def test_zero_explained_still_names_the_ceiling(self):
        # Zero eligible candidates is exactly when the ceiling hint matters, so
        # it must not be suppressed by the "nothing was explained" branch.
        reasons = _gate(
            _coverage(
                hybrid_explained=0, hybrid_attribution_complete=0,
                hybrid_eligible=0, hybrid_structural_fallback=0,
            )
        )
        joined = " ".join(reasons)
        self.assertIn("hybrid_eligible=0", joined)
        self.assertIn("MAX_EXPLAINER_INPUT", joined)


class SmallCandidatePoolTests(unittest.TestCase):
    """A candidate pool smaller than the budget stays a legitimate shortfall."""

    def test_small_pool_does_not_fail_the_budget_rule(self):
        reasons = _gate(
            _coverage(
                hybrid_available=5, hybrid_eligible=5, hybrid_explained=5,
                hybrid_attribution_complete=5, hybrid_structural_fallback=0,
            )
        )
        self.assertEqual(reasons, [])

    def test_small_pool_still_rejects_structural_fallbacks(self):
        reasons = _gate(
            _coverage(
                hybrid_available=5, hybrid_eligible=3, hybrid_explained=3,
                hybrid_structural_fallback=2,
            )
        )
        self.assertTrue(reasons)
        self.assertIn("hybrid_structural_fallback=2", " ".join(reasons))

    def test_no_explanations_at_all_still_fails(self):
        reasons = _gate(
            _coverage(
                hybrid_available=5, hybrid_eligible=0, hybrid_explained=0,
                hybrid_structural_fallback=0,
            )
        )
        self.assertTrue(reasons)


class GateFieldTests(unittest.TestCase):
    def test_missing_field_is_reported_once(self):
        coverage = _coverage()
        del coverage["hybrid_eligible"]
        reasons = _gate(coverage)
        self.assertEqual(len(reasons), 1)
        self.assertIn("hybrid_eligible", reasons[0])

    def test_unrelated_failures_are_still_reported(self):
        reasons = _gate(_coverage(narrative_fallback=3, failed_count=1))
        joined = " ".join(reasons)
        self.assertIn("narrative_fallback=3", joined)
        self.assertIn("failed_count=1", joined)


if __name__ == "__main__":
    unittest.main()
