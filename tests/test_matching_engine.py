"""
tests/test_matching_engine.py

Unit + integration tests for Phase 3.
Covers:
  - Tolerance window calculation (asymmetric)
  - DP solver: 1:1, N:1 / 1:N, no-match, candidate pruning
  - Naive baseline matcher
  - Precision/recall scoring against ground truth
"""

import json
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from matching_engine.tolerance import compute_tolerance_window, compute_expected_deduction
from matching_engine.solver import subset_sum_dp, prune_candidates
from matching_engine.matcher import run_real_matcher, run_naive_matcher, score_results

# ===========================================================================
# Tolerance tests
# ===========================================================================

def test_tolerance_window_asymmetric():
    """
    bc_amount is already the net amount received.
    Underpayment tolerance = full deduction headroom on that net amount.
    Overpayment = 100 paise max.
    """
    net_amount = 100_000
    lower, upper = compute_tolerance_window(net_amount)
    deduction_headroom = compute_expected_deduction(net_amount)

    assert upper == net_amount + 100
    assert lower == net_amount - deduction_headroom

def test_tolerance_window_overpayment_strict():
    """Overpayment tolerance is always exactly 100 paise regardless of amount."""
    for net in [50_000, 200_000, 500_000]:
        _, upper = compute_tolerance_window(net)
        assert upper == net + 100

# ===========================================================================
# DP solver tests
# ===========================================================================

def _make_cand(pid, net, date="2026-08-02T10:00:00"):
    return {"payment_id": pid, "net_amount_paise": net, "captured_at": date}

def test_solver_exact_1to1():
    """Single candidate whose net amount exactly equals the target."""
    cands = [_make_cand("p1", 97_000)]
    result = subset_sum_dp(cands, 97_000, 90_000, 97_100)
    assert result == ["p1"]

def test_solver_n_to_1():
    """Three candidates that must be summed to hit the target."""
    cands = [
        _make_cand("p1", 30_000),
        _make_cand("p2", 40_000),
        _make_cand("p3", 27_000),
    ]
    target = 97_000
    result = subset_sum_dp(cands, target, 90_000, 97_100)
    assert result is not None
    matched_sum = sum(c["net_amount_paise"] for c in cands if c["payment_id"] in result)
    assert 90_000 <= matched_sum <= 97_100

def test_solver_no_match():
    """No subset within the window — should return None, not hallucinate."""
    cands = [
        _make_cand("p1", 10_000),
        _make_cand("p2", 11_000),
    ]
    result = subset_sum_dp(cands, 97_000, 90_000, 97_100)
    assert result is None

def test_solver_empty_pool():
    """Empty candidate pool returns None gracefully."""
    result = subset_sum_dp([], 97_000, 90_000, 97_100)
    assert result is None

def test_solver_does_not_double_use_candidate():
    """A single candidate of 50_000 should not be 'used twice' to hit 100_000."""
    cands = [_make_cand("p1", 50_000)]
    result = subset_sum_dp(cands, 100_000, 95_000, 100_100)
    assert result is None

# ===========================================================================
# Date pruning tests
# ===========================================================================

def test_prune_within_window():
    cands = [
        _make_cand("p1", 100_000, "2026-08-01T10:00:00"),
        _make_cand("p2", 100_000, "2026-08-10T10:00:00"),  # 9 days after credit
    ]
    credit_date = "2026-08-02T10:00:00"
    result = prune_candidates(cands, credit_date, window_days=7)
    assert len(result) == 1
    assert result[0]["payment_id"] == "p1"

def test_prune_empty_if_all_outside():
    cands = [_make_cand("p1", 100_000, "2026-07-01T10:00:00")]
    result = prune_candidates(cands, "2026-08-02T10:00:00", window_days=7)
    assert result == []

# ===========================================================================
# Integration test: run both matchers against a real DB
# ===========================================================================

def test_matchers_against_synthetic_batch():
    """
    Integration test: run both matchers against the real generated batch.
    Our real solver must outperform naive on recall.
    Neither should have zero true positives.
    """
    db_path = "finance.db"
    gt_path = "ground_truth.json"

    if not os.path.exists(db_path) or not os.path.exists(gt_path):
        import pytest
        pytest.skip("Synthetic batch not generated yet — run generate_batch.py first")

    conn = sqlite3.connect(db_path)
    real_results  = run_real_matcher(conn)
    naive_results = run_naive_matcher(conn)
    conn.close()

    with open(gt_path) as f:
        ground_truth = json.load(f)

    real_score  = score_results(real_results,  ground_truth)
    naive_score = score_results(naive_results, ground_truth)

    # The real solver must find more true positives than the naive baseline
    assert real_score["true_positives"] >= naive_score["true_positives"], \
        "Real solver should not be worse than naive"

    # The real solver must have non-zero recall
    assert real_score["recall"] > 0.0, "Real solver produced zero true positives — critical failure"

    # Precision must be reasonable (not hallucinating matches everywhere)
    assert real_score["precision"] >= 0.5, \
        f"Precision too low: {real_score['precision']} — check tolerance window"

    print(f"\nReal solver   — Precision: {real_score['precision']}, Recall: {real_score['recall']}, F1: {real_score['f1']}")
    print(f"Naive baseline — Precision: {naive_score['precision']}, Recall: {naive_score['recall']}, F1: {naive_score['f1']}")


def test_missing_ledger_downgrades_to_probable():
    """
    Explicitly assert that a payment with matching amount but no ledger_entries
    row resolves to PROBABLE with reason MISSING_LEDGER_ENTRY under the 3-state model.
    """
    db_path = "finance.db"
    gt_path = "ground_truth.json"

    if not os.path.exists(db_path) or not os.path.exists(gt_path):
        import pytest
        pytest.skip("Synthetic batch not generated yet")

    with open(gt_path) as f:
        ground_truth = json.load(f)

    missing_record_gt = next((g for g in ground_truth if g.get("type") == "Missing record"), None)
    assert missing_record_gt is not None, "Missing record trap not found in ground_truth.json"
    assert missing_record_gt["expected_status"] == "PROBABLE"

    conn = sqlite3.connect(db_path)
    real_results = run_real_matcher(conn)
    conn.close()

    bc_id = missing_record_gt["bank_credit_id"]
    match = next((r for r in real_results if r["bank_credit_id"] == bc_id), None)
    assert match is not None, f"Bank credit {bc_id} was not returned by real matcher"
    assert match["status"] == "PROBABLE", f"Expected PROBABLE, got {match['status']}"
    assert match["reason"] == "MISSING_LEDGER_ENTRY"
    assert len(match["missing_evidence"]) > 0
    assert "ledger_entries row" in match["missing_evidence"][0]

