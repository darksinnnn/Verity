"""
matching_engine/matcher.py

Main orchestrator for matching bank credits against open payments.

For each unmatched bank credit:
  1. Prune the candidate payment pool by date window.
  2. Run the DP subset-sum solver within the dynamic tolerance window.
  3. Record the match (PROVEN) or hand off to the Delta-Explainer (no match).

Also implements the naive 1:1-only baseline matcher for the contrast demo
required by PRD.md §6.

All amounts stored in the DB are in paise (INTEGER). We never convert to float.
"""

from __future__ import annotations

import sqlite3
from matching_engine.tolerance import compute_tolerance_window
from matching_engine.solver import prune_candidates, subset_sum_dp


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _load_bank_credits(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute(
        "SELECT id, raw_narration, amount, value_date, parsed_utr FROM bank_credits ORDER BY value_date"
    )
    return [
        {"id": r[0], "raw_narration": r[1], "amount": r[2], "value_date": r[3], "parsed_utr": r[4]}
        for r in cur.fetchall()
    ]


def _load_open_payments(conn: sqlite3.Connection) -> list[dict]:
    """
    Load all payments with their computed net amount (gross minus fees).
    Net amount is computed here from the fees table — not trusted from
    any other column — so that the matcher sees the same arithmetic
    the generator used, not a denormalized cache.
    """
    cur = conn.execute("""
        SELECT
            p.id,
            p.order_id,
            p.amount,
            p.captured_at,
            COALESCE(SUM(f.amount), 0) AS total_fees
        FROM payments p
        LEFT JOIN fees f ON f.payment_id = p.id
        GROUP BY p.id
    """)
    rows = cur.fetchall()
    result = []
    for r in rows:
        gross = r[2]
        total_fees = r[4]
        net = gross - total_fees
        result.append({
            "payment_id": r[0],
            "order_id": r[1],
            "gross_amount_paise": gross,
            "net_amount_paise": net,
            "captured_at": r[3],
        })
    return result


# ---------------------------------------------------------------------------
# Real solver (DP subset-sum, 1:1 + N:1 + 1:N)
# ---------------------------------------------------------------------------

def run_real_matcher(conn: sqlite3.Connection) -> list[dict]:
    """
    Matches bank credits to payments using the DP subset-sum solver.

    Returns a list of result dicts:
      {
        'bank_credit_id': str,
        'matched_payment_ids': list[str],   # empty if no match found
        'status': 'MATCHED' | 'UNMATCHED',
        'matched_sum_paise': int | None,
        'bank_credit_amount_paise': int,
        'epsilon_pct_used': float | None,   # for forensic layer / boundary analysis
      }
    """
    bank_credits = _load_bank_credits(conn)
    all_payments = _load_open_payments(conn)

    # Track which payment IDs are already consumed so we don't double-match.
    consumed_payment_ids: set[str] = set()

    results = []

    for bc in bank_credits:
        bc_amount = bc["amount"]  # already in paise
        bc_date   = bc["value_date"]

        # Step 1: Prune by date window
        available = [p for p in all_payments if p["payment_id"] not in consumed_payment_ids]
        pruned = prune_candidates(available, bc_date)

        if not pruned:
            results.append({
                "bank_credit_id": bc["id"],
                "matched_payment_ids": [],
                "status": "UNMATCHED",
                "matched_sum_paise": None,
                "bank_credit_amount_paise": bc_amount,
                "epsilon_pct_used": None,
            })
            continue

        # Step 2: Compute the gross amount for the candidate pool.
        # We match bc_amount against the *sum of net amounts* of some subset.
        # The tolerance window is computed from the total gross of the subset.
        # Since we don't know the subset in advance, we derive tolerance from bc_amount itself:
        # i.e., treat bc_amount as the expected net and allow for deductions on top.
        lower_bound, upper_bound = compute_tolerance_window(bc_amount)

        # Step 3: Run DP solver
        matched_ids = subset_sum_dp(pruned, bc_amount, lower_bound, upper_bound)

        if matched_ids:
            matched_sum = sum(
                p["net_amount_paise"] for p in pruned if p["payment_id"] in matched_ids
            )
            # Calculate how far through the tolerance band we used (for forensic clustering check)
            epsilon_low = bc_amount - lower_bound
            gap = abs(matched_sum - bc_amount)
            epsilon_pct = (gap / epsilon_low * 100) if epsilon_low > 0 else 0.0

            # Mark these payments as consumed
            consumed_payment_ids.update(matched_ids)

            results.append({
                "bank_credit_id": bc["id"],
                "matched_payment_ids": list(matched_ids),
                "status": "MATCHED",
                "matched_sum_paise": matched_sum,
                "bank_credit_amount_paise": bc_amount,
                "epsilon_pct_used": round(epsilon_pct, 2),
            })
        else:
            results.append({
                "bank_credit_id": bc["id"],
                "matched_payment_ids": [],
                "status": "UNMATCHED",
                "matched_sum_paise": None,
                "bank_credit_amount_paise": bc_amount,
                "epsilon_pct_used": None,
            })

    return results


# ---------------------------------------------------------------------------
# Naive 1:1-only baseline matcher (required for contrast demo, PRD.md §6)
# ---------------------------------------------------------------------------

def run_naive_matcher(conn: sqlite3.Connection) -> list[dict]:
    """
    Naive matcher: for each bank credit, find any single payment whose
    net amount == bank credit amount exactly. No tolerance. No multi-payment
    aggregation. This is the baseline we beat.
    """
    bank_credits = _load_bank_credits(conn)
    all_payments = _load_open_payments(conn)

    consumed_payment_ids: set[str] = set()
    results = []

    for bc in bank_credits:
        bc_amount = bc["amount"]

        available = [
            p for p in all_payments
            if p["payment_id"] not in consumed_payment_ids
            and p["net_amount_paise"] == bc_amount  # exact 1:1 only
        ]

        if available:
            match = available[0]
            consumed_payment_ids.add(match["payment_id"])
            results.append({
                "bank_credit_id": bc["id"],
                "matched_payment_ids": [match["payment_id"]],
                "status": "MATCHED",
                "matched_sum_paise": match["net_amount_paise"],
                "bank_credit_amount_paise": bc_amount,
            })
        else:
            results.append({
                "bank_credit_id": bc["id"],
                "matched_payment_ids": [],
                "status": "UNMATCHED",
                "matched_sum_paise": None,
                "bank_credit_amount_paise": bc_amount,
            })

    return results


# ---------------------------------------------------------------------------
# Scoring against ground truth (precision / recall — not just raw counts)
# ---------------------------------------------------------------------------

def score_results(results: list[dict], ground_truth: list[dict]) -> dict:
    """
    Scores matcher results against ground_truth.json.

    Precision = of the matches we claimed, how many were correct?
    Recall    = of the correct matchable cases, how many did we find?

    'Correct matchable cases' = ground truth entries whose expected_status is PROVEN.
    A result is correct if bank_credit_id matches AND matched_payment_ids matches
    expected_payment_ids (as sets, order-independent).
    """
    # Build lookup: bc_id -> ground truth row
    gt_by_bc = {
        g["bank_credit_id"]: g
        for g in ground_truth
        if g.get("bank_credit_id") is not None
    }

    # All cases we expect to be PROVEN (matchable by the engine)
    expected_proven = {
        bc_id: g
        for bc_id, g in gt_by_bc.items()
        if g["expected_status"] == "PROVEN"
    }

    true_positives  = 0
    false_positives = 0
    false_negatives = 0

    matched_bcs = {r["bank_credit_id"] for r in results if r["status"] == "MATCHED"}

    for r in results:
        bc_id = r["bank_credit_id"]
        if r["status"] == "MATCHED":
            gt_row = gt_by_bc.get(bc_id)
            if gt_row is None:
                # We matched something with no ground truth entry — count as FP
                false_positives += 1
                continue
            expected_ids = set(gt_row.get("expected_payment_ids", []))
            actual_ids   = set(r["matched_payment_ids"])
            if expected_ids == actual_ids and gt_row["expected_status"] == "PROVEN":
                true_positives += 1
            else:
                false_positives += 1

    # False negatives: cases we expected to match but didn't
    for bc_id, gt_row in expected_proven.items():
        if bc_id not in matched_bcs:
            false_negatives += 1

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall    = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1        = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "true_positives":  true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision":       round(precision, 4),
        "recall":          round(recall, 4),
        "f1":              round(f1, 4),
    }
