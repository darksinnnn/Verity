"""
tests/test_stress_test.py

Pytest suite for Phase 11 Adversarial Stress Testing.
Verifies all 20 adversarial attack scenarios, asserting loud pytest failures
if the solver ever concedes a vulnerability.
"""

import pytest
import os
import json

from stress_test.adversarial_suite import AdversarialSuite, AdversarialResult
from stress_test.run_stress_test import run_stress_test


@pytest.fixture(scope="module")
def all_stress_results():
    return AdversarialSuite.run_all()


def test_adversarial_suite_generates_20_scenarios(all_stress_results):
    assert len(all_stress_results) == 20, f"Expected 20 scenarios, got {len(all_stress_results)}"


@pytest.mark.parametrize("scenario_func", [
    AdversarialSuite.test_adv_01_coincidental_sum_unanchored,
    AdversarialSuite.test_adv_02_tight_near_miss_under_epsilon,
    AdversarialSuite.test_adv_03_coincidental_sum_outside_dynamic_tolerance,
    AdversarialSuite.test_adv_04_zero_net_cancellation_trap,
    AdversarialSuite.test_adv_05_unanchored_subset_collision,
    AdversarialSuite.test_adv_06_greedy_solver_suboptimality_trap,
    AdversarialSuite.test_adv_07_window_boundary_contention,
    AdversarialSuite.test_adv_08_multi_candidate_tie_break,
    AdversarialSuite.test_adv_09_overpayment_exact_plus_1_paise,
    AdversarialSuite.test_adv_10_overpayment_over_gross_sub_percent,
    AdversarialSuite.test_adv_11_underpayment_exact_minus_1_paise_beyond_envelope,
    AdversarialSuite.test_adv_12_underpayment_exact_boundary_inner_edge,
    AdversarialSuite.test_adv_13_ghost_credit_perfect_narration,
    AdversarialSuite.test_adv_14_ghost_credit_truncated_fake_utr,
    AdversarialSuite.test_adv_15_ghost_credit_duplicate_narration_diff_amount,
    AdversarialSuite.test_adv_16_high_cardinality_10_to_1,
    AdversarialSuite.test_adv_17_symmetric_duplicate_split,
    AdversarialSuite.test_adv_18_permutation_invariance,
    AdversarialSuite.test_adv_19_compound_tds_plus_refund,
    AdversarialSuite.test_adv_20_unexplainable_prime_gap,
])
def test_individual_adversarial_scenario_defense(scenario_func):
    result: AdversarialResult = scenario_func()
    assert result.defense_status == "DEFENDED", (
        f"ADVERSARIAL VULNERABILITY CONCEDED in {result.scenario_id} ({result.attack_name})! "
        f"Solver Verdict: {result.solver_verdict}, Expected: {result.expected_defense}, "
        f"Proximity Margin: {result.proximity_margin_paise}p ({result.proximity_margin_pct}%)"
    )
    assert result.proximity_margin_paise >= 0, "Proximity margin must be non-negative"


def test_stress_test_report_generation(tmp_path):
    report_file = tmp_path / "test_report.json"
    report = run_stress_test(output_json_path=str(report_file))

    assert report["metadata"]["total_scenarios"] == 20
    assert report["metadata"]["conceded_count"] == 0
    assert report["metadata"]["defended_count"] == 20
    assert report["metadata"]["precision_rate_pct"] == 100.0
    assert os.path.exists(report_file)

    with open(report_file, "r") as f:
        data = json.load(f)
    assert len(data["results"]) == 20
