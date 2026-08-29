"""
matching_engine/matcher.py

Main orchestrator for matching bank credits against open payments.

For each unmatched bank credit:
  1. UTR-priority pass: if the bank credit has a parsed_utr, find any
     settlement with the same UTR and restrict the candidate pool to
     payments listed in that settlement's settlement_items. This is the
     strongest anchor and prevents coincidental amount matches.
  2. Prune the remaining candidate pool by date window.
  3. Run the DP subset-sum solver within the dynamic tolerance window.
  4. After a match is found, verify that every matched payment has a
     corresponding ledger_entries row. If not, downgrade to LEDGER_GAP.

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
            p.method,
            COALESCE(SUM(f.amount), 0) AS total_fees
        FROM payments p
        LEFT JOIN fees f ON f.payment_id = p.id
        GROUP BY p.id
    """)
    rows = cur.fetchall()
    result = []
    for r in rows:
        gross      = r[2]
        total_fees = r[5]
        net        = gross - total_fees
        result.append({
            "payment_id":         r[0],
            "order_id":           r[1],
            "gross_amount_paise": gross,
            "net_amount_paise":   net,
            "captured_at":        r[3],
            "method":             r[4],
        })
    return result


def _get_settlement_payment_ids(conn: sqlite3.Connection, utr: str) -> list[str]:
    """
    Given a UTR string, find the settlement with that UTR and return the
    payment_ids of all its settlement_items. Returns empty list if no match.
    This is the UTR-priority anchor: bank credit -> settlement -> payments.
    """
    row = conn.execute(
        "SELECT id FROM settlements WHERE utr = ?", (utr,)
    ).fetchone()
    if not row:
        return []
    settlement_id = row[0]
    cur = conn.execute(
        "SELECT payment_id FROM settlement_items WHERE settlement_id = ? AND payment_id IS NOT NULL",
        (settlement_id,)
    )
    return [r[0] for r in cur.fetchall()]


def _has_ledger_entry(conn: sqlite3.Connection, payment_id: str) -> bool:
    """Returns True if a ledger_entries row exists for this payment_id."""
    row = conn.execute(
        "SELECT 1 FROM ledger_entries WHERE reference_type = 'payment' AND reference_id = ? LIMIT 1",
        (payment_id,)
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Real solver (DP subset-sum, 1:1 + N:1 + 1:N)
# ---------------------------------------------------------------------------

def run_real_matcher(conn: sqlite3.Connection) -> list[dict]:
    """
    Matches bank credits to payments using the DP subset-sum solver.

    Pass 1 — UTR anchor: if the bank credit has a parsed_utr, look up the
    settlement and restrict candidates to that settlement's payment_ids.
    This eliminates coincidental amount-matches from unrelated payments.

    Pass 2 — Date-window DP: if no UTR anchor (or anchor yields no candidates),
    fall back to the full date-pruned pool.

    Post-match — Ledger integrity check: verify every matched payment has a
    ledger_entries row. If any are missing, flag status as LEDGER_GAP
    (downgraded from MATCHED) so Phase 5 Exception System sees it.

    Returns a list of result dicts:
      {
        'bank_credit_id': str,
        'matched_payment_ids': list[str],
        'status': 'MATCHED' | 'UNMATCHED' | 'LEDGER_GAP',
        'matched_sum_paise': int | None,
        'bank_credit_amount_paise': int,
        'epsilon_pct_used': float | None,
        'missing_ledger_payment_ids': list[str],  # populated for LEDGER_GAP
        'utr_anchored': bool,
      }
    """
    bank_credits = _load_bank_credits(conn)
    all_payments = _load_open_payments(conn)
    payment_by_id = {p["payment_id"]: p for p in all_payments}

    consumed_payment_ids: set[str] = set()
    results = []

    for bc in bank_credits:
        bc_amount  = bc["amount"]
        bc_date    = bc["value_date"]
        bc_utr     = bc["parsed_utr"]

        available = [p for p in all_payments if p["payment_id"] not in consumed_payment_ids]

        # ── Pass 1: UTR-anchor ──────────────────────────────────────────────
        utr_anchored    = False
        anchor_pool     = []
        if bc_utr:
            anchor_ids = _get_settlement_payment_ids(conn, bc_utr)
            anchor_pool = [
                payment_by_id[pid] for pid in anchor_ids
                if pid in payment_by_id and pid not in consumed_payment_ids
            ]
            if anchor_pool:
                utr_anchored = True

        # ── Pass 2: date-pruned fallback ────────────────────────────────────
        if utr_anchored:
            candidate_pool = anchor_pool
        else:
            candidate_pool = prune_candidates(available, bc_date)

        if not candidate_pool:
            results.append({
                "bank_credit_id":            bc["id"],
                "matched_payment_ids":        [],
                "status":                     "UNMATCHED",
                "matched_sum_paise":          None,
                "bank_credit_amount_paise":   bc_amount,
                "epsilon_pct_used":           None,
                "missing_ledger_payment_ids": [],
                "utr_anchored":               utr_anchored,
            })
            continue

        lower_bound, upper_bound = compute_tolerance_window(bc_amount)
        matched_ids = subset_sum_dp(candidate_pool, bc_amount, lower_bound, upper_bound)

        if matched_ids:
            matched_sum = sum(
                p["net_amount_paise"] for p in candidate_pool if p["payment_id"] in matched_ids
            )
            epsilon_low = bc_amount - lower_bound
            gap         = abs(matched_sum - bc_amount)
            epsilon_pct = (gap / epsilon_low * 100) if epsilon_low > 0 else 0.0

            # ── Ledger integrity check ──────────────────────────────────────
            missing_ledger = [
                pid for pid in matched_ids
                if not _has_ledger_entry(conn, pid)
            ]

            consumed_payment_ids.update(matched_ids)

            if missing_ledger:
                status = "PROBABLE"
                reason = "MISSING_LEDGER_ENTRY"
                missing_evidence = [f"ledger_entries row for {pid}" for pid in missing_ledger]
            else:
                status = "MATCHED"  # PROVEN match
                reason = None
                missing_evidence = []

            results.append({
                "bank_credit_id":            bc["id"],
                "matched_payment_ids":        list(matched_ids),
                "status":                     status,
                "reason":                     reason,
                "missing_evidence":           missing_evidence,
                "matched_sum_paise":          matched_sum,
                "bank_credit_amount_paise":   bc_amount,
                "epsilon_pct_used":           round(epsilon_pct, 2),
                "missing_ledger_payment_ids": missing_ledger,
                "utr_anchored":               utr_anchored,
            })
        else:
            results.append({
                "bank_credit_id":            bc["id"],
                "matched_payment_ids":        [],
                "status":                     "UNMATCHED",
                "reason":                     None,
                "missing_evidence":           [],
                "matched_sum_paise":          None,
                "bank_credit_amount_paise":   bc_amount,
                "epsilon_pct_used":           None,
                "missing_ledger_payment_ids": [],
                "utr_anchored":               utr_anchored,
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
    Scores matcher results against ground_truth.json using the 3-state system
    (PROVEN / PROBABLE / UNRESOLVED).

    - PROVEN matches: solver found payment(s) and full audit trail was verified.
      Scored for Precision, Recall, F1 against expected PROVEN cases.
    - PROBABLE matches: solver found payment(s) but flagged an audit gap
      (e.g., missing ledger_entries). Scored as probable_correct if ground truth
      agrees it is PROBABLE.
    """
    gt_by_bc = {
        g["bank_credit_id"]: g
        for g in ground_truth
        if g.get("bank_credit_id") is not None
    }

    expected_proven = {
        bc_id: g for bc_id, g in gt_by_bc.items()
        if g["expected_status"] == "PROVEN"
    }

    true_positives       = 0
    false_positives      = 0
    false_negatives      = 0
    probable_correct     = 0

    matched_bcs = {r["bank_credit_id"] for r in results if r["status"] == "MATCHED"}

    for r in results:
        bc_id = r["bank_credit_id"]
        gt_row = gt_by_bc.get(bc_id)

        if r["status"] == "MATCHED":
            if gt_row is None:
                false_positives += 1
                continue
            expected_ids = set(gt_row.get("expected_payment_ids", []))
            actual_ids   = set(r["matched_payment_ids"])
            if expected_ids == actual_ids and gt_row["expected_status"] == "PROVEN":
                true_positives += 1
            else:
                false_positives += 1
        elif r["status"] == "PROBABLE":
            if gt_row and gt_row["expected_status"] == "PROBABLE":
                expected_ids = set(gt_row.get("expected_payment_ids", []))
                actual_ids   = set(r["matched_payment_ids"])
                if expected_ids == actual_ids:
                    probable_correct += 1
                else:
                    false_positives += 1
            elif gt_row and gt_row["expected_status"] == "PROVEN":
                # Downgraded a genuine proven match — counts as FN
                false_negatives += 1
            else:
                false_positives += 1

    for bc_id in expected_proven:
        if bc_id not in matched_bcs:
            false_negatives += 1

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall    = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1        = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "true_positives":   true_positives,
        "false_positives":  false_positives,
        "false_negatives":  false_negatives,
        "probable_correct": probable_correct,
        "precision":        round(precision, 4),
        "recall":           round(recall, 4),
        "f1":               round(f1, 4),
    }


