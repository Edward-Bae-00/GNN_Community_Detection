"""Would a run actually yield 20 exact Hybrid explanations?

Everything downstream of eligibility is decided by pure selection logic, so it
can be simulated here: given N candidates passing explainer preflight, this
exercises the real frozen selection, the real structural-fallback rule, and the
real coverage gate, and asserts what the run would report.

What it cannot answer is the value of N. That is an empirical property of the
corpus at a given ceiling, measurable only by running explainer preflight with
Torch and PyG (``--preflight-only``). At the ceiling currently committed
(128/256) the observed N was 10.
"""
import sys
import types
import unittest

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

import pandas as pd

from gnn.recovery_observability import (
    RecoveryAnchor,
    RecoveryCase,
    _round_robin_balanced_cases,
    select_balanced_detail_cases,
)
import run_schema3_observability as runner


HYBRID_LIMIT = 20
BASELINE_LIMIT = 10
HYBRID_CANDIDATES = 268
BASELINE_CANDIDATES = 113
CATEGORIES = ("cotravel", "residence", "shared_plate")
PERIODS = ("2019-Q1", "2019-Q2", "2019-Q3", "2019-Q4")


def _case(index, cohort):
    prefix = "H" if cohort == "hybrid_only" else "B"
    person_id = f"P{prefix}{index:05d}"
    day = pd.Timestamp("2019-01-01", tz="UTC") + pd.Timedelta(days=index % 60)
    return RecoveryCase(
        case_id=f"case:{person_id}",
        recovery_cohort=cohort,
        anchor_event=RecoveryAnchor(
            person_id=person_id,
            event_id=f"event:{person_id}",
            row_index=index,
            scoring_day=day,
            inspected_rank=1 + (index % 5),
        ),
        subject_id=person_id,
        subject_display={},
        baseline_raw=float(index) / 1000.0,
        baseline_percentile=float(index % 100) / 100.0,
        baseline_rank=1 + index,
        seed0_gnn_probability=float(index % 100) / 100.0,
        seed0_gnn_percentile=float(index % 100) / 100.0,
        seed0_gnn_rank=1 + index,
        seed0_hybrid_score=float(index % 100) / 100.0,
        seed0_hybrid_rank=1 + index,
        hybrid_blend_weight=0.75,
        relationship_categories=(CATEGORIES[index % len(CATEGORIES)],),
        scoring_period=PERIODS[index % len(PERIODS)],
    )


def _simulate(eligible_count, *, hybrid_limit=HYBRID_LIMIT):
    """Run the real selection path and report what the run would publish."""
    hybrid = [_case(index, "hybrid_only") for index in range(HYBRID_CANDIDATES)]
    baseline = [
        _case(index, "baseline_only") for index in range(BASELINE_CANDIDATES)
    ]
    # Eligibility is a property of graph size, which is uncorrelated with
    # selection order, so take an arbitrary subset rather than a prefix.
    eligible_ids = [case.case_id for case in hybrid[::3]][:eligible_count]

    selection = select_balanced_detail_cases(
        hybrid,
        baseline,
        hybrid_limit=hybrid_limit,
        baseline_limit=BASELINE_LIMIT,
        eligible_hybrid_ids=eligible_ids,
    )
    selected_hybrid = selection.selected_ids["hybrid_only"]
    selected_baseline = selection.selected_ids["baseline_only"]

    # Mirrors gnn/observability_artifact.py's structural-fallback rule.
    fallback_slots = max(0, hybrid_limit - len(selected_hybrid))
    eligible_id_set = set(eligible_ids)
    ineligible = [
        case
        for case in sorted(hybrid, key=lambda value: value.case_id)
        if case.case_id not in eligible_id_set
    ]
    fallbacks = tuple(
        case.case_id
        for case in _round_robin_balanced_cases(ineligible, hybrid=True)[
            :fallback_slots
        ]
    )
    return {
        "hybrid_selected": len(selected_hybrid),
        "hybrid_structural_fallback": len(fallbacks),
        "baseline_selected": len(selected_baseline),
    }


def _coverage_if_every_case_succeeds(outcome, *, eligible_count):
    """Coverage for the best case: nothing failed, attribution all complete."""
    return {
        "narrative_preflight_failed": 0,
        "failed_count": 0,
        "narrative_fallback": 0,
        "hybrid_explained": outcome["hybrid_selected"],
        "hybrid_attribution_complete": outcome["hybrid_selected"],
        "hybrid_structural_fallback": outcome["hybrid_structural_fallback"],
        "hybrid_available": HYBRID_CANDIDATES,
        "hybrid_eligible": eligible_count,
        "baseline_available": BASELINE_CANDIDATES,
        "baseline_community": outcome["baseline_selected"],
    }


def _gate(coverage):
    return runner._evaluate_coverage_gate(
        coverage,
        hybrid_detail_limit=HYBRID_LIMIT,
        baseline_control_limit=BASELINE_LIMIT,
    )


class TwentyExactOutcomeTests(unittest.TestCase):
    def test_twenty_eligible_yields_twenty_exact_and_no_fallbacks(self):
        outcome = _simulate(20)
        self.assertEqual(outcome["hybrid_selected"], 20)
        self.assertEqual(outcome["hybrid_structural_fallback"], 0)
        self.assertEqual(outcome["baseline_selected"], 10)

    def test_twenty_eligible_passes_the_gate(self):
        outcome = _simulate(20)
        self.assertEqual(
            _gate(_coverage_if_every_case_succeeds(outcome, eligible_count=20)), []
        )

    def test_surplus_eligibility_still_selects_exactly_twenty(self):
        for eligible_count in (24, 40, 100, HYBRID_CANDIDATES):
            with self.subTest(eligible=eligible_count):
                outcome = _simulate(eligible_count)
                self.assertEqual(outcome["hybrid_selected"], 20)
                self.assertEqual(outcome["hybrid_structural_fallback"], 0)
                self.assertEqual(
                    _gate(
                        _coverage_if_every_case_succeeds(
                            outcome, eligible_count=eligible_count
                        )
                    ),
                    [],
                )

    def test_todays_ceiling_yields_ten_plus_ten_and_fails_the_gate(self):
        # The observed state at 128/256: ten eligible candidates.
        outcome = _simulate(10)
        self.assertEqual(outcome["hybrid_selected"], 10)
        self.assertEqual(outcome["hybrid_structural_fallback"], 10)
        reasons = _gate(_coverage_if_every_case_succeeds(outcome, eligible_count=10))
        joined = " ".join(reasons)
        self.assertIn("hybrid_structural_fallback=10", joined)
        self.assertIn("MAX_EXPLAINER_INPUT", joined)

    def test_nineteen_eligible_backfills_one_and_fails(self):
        outcome = _simulate(19)
        self.assertEqual(outcome["hybrid_selected"], 19)
        self.assertEqual(outcome["hybrid_structural_fallback"], 1)
        self.assertTrue(
            _gate(_coverage_if_every_case_succeeds(outcome, eligible_count=19))
        )

    def test_surplus_eligibility_is_not_failure_tolerance(self):
        # Selection freezes 20 even when 24 are eligible, and there is no
        # post-failure replacement, so spare eligible candidates go unused: one
        # failed case still leaves 19 and fails the gate.
        outcome = _simulate(24)
        coverage = _coverage_if_every_case_succeeds(outcome, eligible_count=24)
        coverage.update(
            hybrid_explained=19, hybrid_attribution_complete=19, failed_count=1
        )
        self.assertTrue(_gate(coverage))


if __name__ == "__main__":
    unittest.main()
