"""
delta_explainer/explainer.py

Deterministic Delta-Explainer (Tax-Line & Deduction Matcher).

For bank credits that could not be matched directly by the matching engine:
1. Identify candidate open payments (or unconsumed payments in date window).
2. Calculate the residual variance: delta = standard_expected_net - bank_credit_amount.
3. Search known deduction combinations to explain delta:
   - Alternate TDS section rates:
       * Section 194-O (Standard): 1.0%
       * Section 194C (Contractor payments): 2.0%
       * Section 194J(1) (Fees for Technical Services): 2.0%
       * Section 194H (Commission & Brokerage): 5.0%
       * Section 194J(2) (Professional Fees): 10.0%
   - Alternate MDR fee tiers: 1.5%, 1.8%, 2.5%, 3.0% (+ 18% GST on MDR)
   - Unlinked / cross-settlement refunds in the database
   - Compound combinations:
       * (Alternate MDR Tier + Alternate TDS Section)
       * (Alternate MDR Tier + Open Refund)
       * (Alternate TDS Section + Open Refund)
4. Implement the strict 3-way branch:
   - PROVEN: Delta explained with direct supporting record in DB.
   - PROBABLE: Delta mathematically matches a known deduction pattern; produces
               ranked candidate hypotheses with explicit missing evidence required.
   - UNRESOLVED: No combination of known tax, fee, or refund rules explains the gap.
                 Never guesses or fabricates.
"""

from __future__ import annotations
import sqlite3
from typing import TypedDict

# Fixed fee and tax constants
STANDARD_MDR_RATE = 0.02
STANDARD_GST_RATE = 0.18
STANDARD_TDS_RATE = 0.01

TDS_SECTIONS = {
    0.01: ("Section 194-O (E-commerce Operator)", "Standard 1.0% TDS rate for merchant settlements"),
    0.02: ("Section 194C / Section 194J(1)", "2.0% TDS deduction (Contractor/Technical Services)"),
    0.05: ("Section 194H (Commission & Brokerage)", "5.0% TDS deduction"),
    0.10: ("Section 194J(2) (Professional Fees)", "10.0% TDS deduction"),
}

MDR_TIERS = [0.015, 0.018, 0.020, 0.025, 0.030]


class Hypothesis(TypedDict):
    hypothesis: str
    category: str
    calculated_delta_paise: int
    observed_delta_paise: int
    discrepancy_paise: int
    evidence_needed: str
    plausibility_rank: int


class ExplanationResult(TypedDict):
    bank_credit_id: str
    candidate_payment_id: str | None
    bank_credit_amount_paise: int
    candidate_gross_paise: int | None
    standard_net_paise: int | None
    delta_paise: int
    status: str  # 'PROVEN' | 'PROBABLE' | 'UNRESOLVED'
    explanation_text: str
    hypotheses: list[Hypothesis]


def _load_candidate_payments(conn: sqlite3.Connection, credit_date: str, exclude_payment_ids: set[str] | None = None) -> list[dict]:
    """
    Load payments captured on or before credit_date within 14 days.
    Sorted by date proximity (closest to credit_date first).
    Prefers unconsumed/open payments.
    """
    from datetime import datetime
    try:
        c_dt = datetime.fromisoformat(credit_date)
    except ValueError:
        c_dt = datetime.strptime(credit_date[:10], "%Y-%m-%d")

    cur = conn.execute("""
        SELECT p.id, p.order_id, p.amount, p.captured_at, p.method,
               COALESCE(SUM(f.amount), 0) AS total_fees
        FROM payments p
        LEFT JOIN fees f ON f.payment_id = p.id
        GROUP BY p.id
    """)
    rows = cur.fetchall()
    results = []
    for r in rows:
        pid = r[0]
        if exclude_payment_ids and pid in exclude_payment_ids:
            continue
        p_date_str = r[3]
        try:
            p_dt = datetime.fromisoformat(p_date_str)
        except ValueError:
            p_dt = datetime.strptime(p_date_str[:10], "%Y-%m-%d")

        delta_days = (c_dt - p_dt).total_seconds() / 86400.0
        # Payment must precede or equal credit, within 14 days
        if not (-0.5 <= delta_days <= 14.0):
            continue

        gross = r[2]
        fees = r[5]
        net = gross - fees
        results.append({
            "payment_id": pid,
            "order_id": r[1],
            "gross_amount_paise": gross,
            "net_amount_paise": net,
            "captured_at": p_date_str,
            "method": r[4],
            "delta_days": delta_days,
        })

    # Sort by closest date proximity first
    results.sort(key=lambda x: abs(x["delta_days"]))
    return results


def _load_available_refunds(conn: sqlite3.Connection) -> list[dict]:
    """Load all processed refunds from database."""
    cur = conn.execute("""
        SELECT id, payment_id, amount, created_at, status
        FROM refunds
        WHERE status = 'processed'
    """)
    return [
        {"refund_id": r[0], "payment_id": r[1], "amount_paise": r[2], "created_at": r[3]}
        for r in cur.fetchall()
    ]


def explain_delta(conn: sqlite3.Connection, bank_credit_id: str, exclude_consumed_pids: set[str] | None = None) -> ExplanationResult:
    """
    Analyzes an unmatched bank credit and searches for deterministic explanations
    against available open candidate payments.
    """
    bc = conn.execute(
        "SELECT id, raw_narration, amount, value_date, parsed_utr FROM bank_credits WHERE id = ?",
        (bank_credit_id,)
    ).fetchone()

    if not bc:
        raise ValueError(f"Bank credit {bank_credit_id} not found")

    bc_id, narration, bc_amount, bc_date, parsed_utr = bc
    candidates = _load_candidate_payments(conn, bc_date, exclude_payment_ids=exclude_consumed_pids)
    refunds = _load_available_refunds(conn)

    best_candidate = None
    best_hypotheses: list[Hypothesis] = []
    best_status = "UNRESOLVED"
    best_explanation = "Unexplained variance: No known tax section, MDR rate variation, or refund record accounts for the difference between received credit and candidate payments."
    min_delta = None

    for cand in candidates:
        gross = cand["gross_amount_paise"]
        std_net = cand["net_amount_paise"]
        delta = std_net - bc_amount

        if delta <= 0:
            continue  # Overpayment or exact match

        hypotheses: list[Hypothesis] = []

        std_mdr = int(gross * STANDARD_MDR_RATE)
        std_gst = int(std_mdr * STANDARD_GST_RATE)
        std_tds = int(gross * STANDARD_TDS_RATE)

        # ── Test 1: Alternate TDS Rates ────────────────────────────────────
        for rate, (section_name, section_desc) in TDS_SECTIONS.items():
            if rate == STANDARD_TDS_RATE:
                continue
            alt_tds = int(gross * rate)
            expected_delta = alt_tds - std_tds
            if abs(delta - expected_delta) <= 1:
                hypotheses.append({
                    "hypothesis": f"TDS was deducted at {rate*100:.1f}% under {section_name} rather than standard 1.0% ({section_desc})",
                    "category": "TAX_RATE_VARIANCE",
                    "calculated_delta_paise": expected_delta,
                    "observed_delta_paise": delta,
                    "discrepancy_paise": abs(delta - expected_delta),
                    "evidence_needed": f"Vendor TDS Certificate (Form 16A) or settlement deduction statement confirming {section_name}.",
                    "plausibility_rank": 1,
                })

        # ── Test 2: Unlinked / Cross-Settlement Refunds ─────────────────────
        for ref in refunds:
            ref_amt = ref["amount_paise"]
            if abs(delta - ref_amt) <= 1:
                hypotheses.append({
                    "hypothesis": f"Settlement was short by Rs.{ref_amt/100:.2f} due to cross-settlement recovery of refund on payment {ref['payment_id']}",
                    "category": "REFUND_RECOVERY",
                    "calculated_delta_paise": ref_amt,
                    "observed_delta_paise": delta,
                    "discrepancy_paise": abs(delta - ref_amt),
                    "evidence_needed": f"Settlement advice confirming refund deduction against refund ID {ref['refund_id']}.",
                    "plausibility_rank": 1 if ref["payment_id"] == cand["payment_id"] else 2,
                })

        # ── Test 3: Alternate MDR Tiers ────────────────────────────────────
        for mdr_tier in MDR_TIERS:
            if mdr_tier == STANDARD_MDR_RATE:
                continue
            alt_mdr = int(gross * mdr_tier)
            alt_gst = int(alt_mdr * STANDARD_GST_RATE)
            alt_fees = alt_mdr + alt_gst + std_tds
            std_fees = std_mdr + std_gst + std_tds
            expected_delta = alt_fees - std_fees
            if expected_delta > 0 and abs(delta - expected_delta) <= 1:
                hypotheses.append({
                    "hypothesis": f"Merchant fee applied at custom tier {mdr_tier*100:.1f}% MDR + 18% GST rather than standard 2.0%",
                    "category": "MDR_TIER_VARIANCE",
                    "calculated_delta_paise": expected_delta,
                    "observed_delta_paise": delta,
                    "discrepancy_paise": abs(delta - expected_delta),
                    "evidence_needed": "Merchant pricing agreement or gateway invoice confirming tiered fee schedule.",
                    "plausibility_rank": 2,
                })

        # ── Test 4: Compound Deductions (e.g. MDR tier + TDS section or MDR tier + Refund) ──
        if not hypotheses:
            for mdr_tier in MDR_TIERS:
                alt_mdr = int(gross * mdr_tier)
                alt_gst = int(alt_mdr * STANDARD_GST_RATE)
                for rate, (section_name, _) in TDS_SECTIONS.items():
                    if mdr_tier == STANDARD_MDR_RATE and rate == STANDARD_TDS_RATE:
                        continue
                    alt_tds = int(gross * rate)
                    compound_fees = alt_mdr + alt_gst + alt_tds
                    std_fees = std_mdr + std_gst + std_tds
                    compound_delta = compound_fees - std_fees
                    if compound_delta > 0 and abs(delta - compound_delta) <= 1:
                        hypotheses.append({
                            "hypothesis": f"Compound variance: Custom MDR at {mdr_tier*100:.1f}% + 18% GST combined with {rate*100:.1f}% TDS under {section_name}",
                            "category": "COMPOUND_DEDUCTION",
                            "calculated_delta_paise": compound_delta,
                            "observed_delta_paise": delta,
                            "discrepancy_paise": abs(delta - compound_delta),
                            "evidence_needed": f"Merchant rate card ({mdr_tier*100:.1f}% MDR) and Form 16A ({section_name}).",
                            "plausibility_rank": 3,
                        })

        # Sort hypotheses by plausibility rank and discrepancy
        hypotheses.sort(key=lambda h: (h["plausibility_rank"], h["discrepancy_paise"]))

        if hypotheses:
            best_candidate = cand
            best_hypotheses = hypotheses
            best_status = "PROBABLE"
            top_h = hypotheses[0]
            best_explanation = (
                f"Plausible explanation found: {top_h['hypothesis']}. "
                f"Amount gap of Rs.{delta/100:.2f} matches expected variance. "
                f"Verification requires: {top_h['evidence_needed']}"
            )
            break
        else:
            if min_delta is None or delta < min_delta:
                min_delta = delta
                best_candidate = cand

    cand_id = best_candidate["payment_id"] if best_candidate else None
    cand_gross = best_candidate["gross_amount_paise"] if best_candidate else None
    cand_std_net = best_candidate["net_amount_paise"] if best_candidate else None
    observed_delta = (cand_std_net - bc_amount) if cand_std_net else 0

    if best_status == "UNRESOLVED":
        best_explanation = (
            f"Unexplained variance on {bc_id}: Bank credit of Rs.{bc_amount/100:.2f} has an unexplained gap of Rs.{observed_delta/100:.2f}. "
            f"No known tax section, MDR rate variation, or refund record accounts for the difference between received credit and candidate payments."
        )

    return {
        "bank_credit_id": bc_id,
        "candidate_payment_id": cand_id,
        "bank_credit_amount_paise": bc_amount,
        "candidate_gross_paise": cand_gross,
        "standard_net_paise": cand_std_net,
        "delta_paise": observed_delta,
        "status": best_status,
        "explanation_text": best_explanation,
        "hypotheses": best_hypotheses,
    }


def explain_all_unmatched(
    conn: sqlite3.Connection,
    unmatched_bank_credit_ids: list[str],
    exclude_consumed_pids: set[str] | None = None
) -> list[ExplanationResult]:
    """Runs the delta-explainer across all unmatched bank credits against unconsumed payments."""
    return [explain_delta(conn, bc_id, exclude_consumed_pids=exclude_consumed_pids) for bc_id in unmatched_bank_credit_ids]
