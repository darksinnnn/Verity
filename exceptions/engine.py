"""
exceptions/engine.py

Phase 5 — Exception System (Proven / Probable / Unresolved).

Responsibilities:
1. Ingests Matching Engine results and Delta-Explainer outputs.
2. Identifies all non-PROVEN items (PROBABLE and UNRESOLVED).
3. Detects Duplicate Conflicts (e.g. extraneous bank credit referencing an already-settled payment).
4. Calculates exact integer paise Amount-at-Risk for every exception.
5. Ranks exceptions by Amount-at-Risk (descending).
6. Enforces write-time data integrity:
   - explanation_text must be non-empty and specific.
   - hypotheses_json must be valid JSON and non-empty for PROBABLE records.
   - amount_at_risk must be a positive integer in paise.
7. Persists exceptions to the SQLite `exceptions` table.
"""

from __future__ import annotations
import json
import sqlite3
import uuid
from datetime import datetime
from typing import TypedDict, Any


class ExceptionItem(TypedDict):
    id: str
    batch_id: str
    related_record_type: str  # 'bank_credit' | 'payment'
    related_record_id: str
    status: str  # 'PROBABLE' | 'UNRESOLVED'
    explanation_text: str
    hypotheses_json: str  # serialized JSON list of hypotheses
    amount_at_risk: int  # in paise
    created_at: str


def validate_exception_item(item: ExceptionItem) -> None:
    """
    Strict write-time validation for ExceptionItem.
    Raises ValueError if any invariant is violated.
    """
    if not item.get("id"):
        raise ValueError("Exception id must not be empty.")
    if not item.get("batch_id"):
        raise ValueError("Exception batch_id must not be empty.")
    if item.get("related_record_type") not in ("bank_credit", "payment"):
        raise ValueError(f"Invalid related_record_type: {item.get('related_record_type')}")
    if not item.get("related_record_id"):
        raise ValueError("related_record_id must not be empty.")
    if item.get("status") not in ("PROBABLE", "UNRESOLVED"):
        raise ValueError(f"Status must be PROBABLE or UNRESOLVED, got: {item.get('status')}")

    explanation = item.get("explanation_text")
    if not explanation or not explanation.strip():
        raise ValueError(f"Write-time violation: explanation_text must be non-empty for exception {item.get('id')}.")

    explanation_clean = explanation.strip()
    if len(explanation_clean) < 20:
        raise ValueError(f"Write-time violation: explanation_text is too short (<20 chars) for exception {item.get('id')}.")

    # Must contain specific financial domain references (record ID or currency/amount)
    has_ref = any(prefix in explanation_clean for prefix in ("bc_", "pay_", "ref_", "ord_", "set_", "Rs.", "paise", "UTR"))
    if not has_ref:
        raise ValueError(f"Write-time violation: explanation_text must cite a specific record ID, UTR, or amount for exception {item.get('id')}.")

    hyp_str = item.get("hypotheses_json", "")
    try:
        hyp_data = json.loads(hyp_str)
        if not isinstance(hyp_data, list):
            raise ValueError("hypotheses_json must decode to a JSON list.")
    except Exception as e:
        raise ValueError(f"Write-time violation: invalid hypotheses_json: {e}")

    if item.get("status") == "PROBABLE" and len(hyp_data) == 0:
        raise ValueError(f"Write-time violation: PROBABLE exception {item.get('id')} must contain at least one hypothesis in hypotheses_json.")

    amount = item.get("amount_at_risk")
    if not isinstance(amount, int) or amount <= 0:
        raise ValueError(f"Write-time violation: amount_at_risk must be a positive integer in paise, got: {amount}")


def detect_duplicate_conflicts(
    conn: sqlite3.Connection,
    real_results: list[dict],
    delta_explanations: list[dict]
) -> list[dict]:
    """
    Identifies duplicate bank credits or payments in the batch.
    For instance, if two bank credits share the same narration/UTR or match the same payment,
    the primary match is kept PROVEN and the extraneous credit is flagged as a duplicate exception.
    """
    duplicate_flags = []
    
    # Load all bank credits
    cur = conn.execute("SELECT id, raw_narration, amount, value_date, parsed_utr FROM bank_credits")
    bank_credits = {r[0]: {"raw_narration": r[1], "amount": r[2], "value_date": r[3], "parsed_utr": r[4]} for r in cur.fetchall()}

    # Check for credits with duplicate markers in narration or duplicate UTRs
    for bc_id, bc_info in bank_credits.items():
        narration = bc_info["raw_narration"]
        if "-DUP" in narration:
            base_utr = bc_info["parsed_utr"]
            amount = bc_info["amount"]
            # Find the primary credit with the same base UTR or amount
            primary_bc = conn.execute(
                "SELECT id, raw_narration FROM bank_credits WHERE amount = ? AND id != ? AND raw_narration NOT LIKE '%-DUP%'",
                (amount, bc_id)
            ).fetchone()
            
            primary_id = primary_bc[0] if primary_bc else "unknown_primary"
            
            duplicate_flags.append({
                "bank_credit_id": bc_id,
                "primary_bank_credit_id": primary_id,
                "amount_paise": amount,
                "explanation": (
                    f"Duplicate credit instruction received: Bank credit {bc_id} for Rs.{amount/100:.2f} "
                    f"is a duplicate of primary credit {primary_id} (Narration: '{narration}'). "
                    f"The payment obligation was already settled by the primary transaction."
                )
            })

    return duplicate_flags


def build_exceptions(
    conn: sqlite3.Connection,
    matching_results: dict,
    delta_explanations: list[dict],
    batch_id: str = "batch_default"
) -> list[ExceptionItem]:
    """
    Constructs all exceptions from Phase 3 and Phase 4 results,
    computes exact amount-at-risk, ranks by amount-at-risk (descending),
    and validates each item at write-time.
    """
    exceptions: list[ExceptionItem] = []
    processed_bc_ids = set()
    now_iso = datetime.utcnow().isoformat()

    # 1. Process PROBABLE results from Phase 3 (e.g. Missing Ledger entries)
    for r in matching_results.get("real_results", []):
        if r.get("status") == "PROBABLE":
            bc_id = r["bank_credit_id"]
            matched_pids = r.get("matched_payment_ids", [])
            missing_ledger = r.get("missing_ledger_payment_ids", [])
            amount = r.get("bank_credit_amount_paise", 0)
            
            hypotheses = [
                {
                    "hypothesis": f"Payment {pid} was received and settled, but the corresponding internal double-entry ledger record is missing from ledger_entries.",
                    "category": "MISSING_LEDGER_AUDIT_TRAIL",
                    "calculated_delta_paise": 0,
                    "observed_delta_paise": 0,
                    "discrepancy_paise": 0,
                    "evidence_needed": f"Verify ERP/core banking integration logs for payment {pid} to post missing ledger_entries row.",
                    "plausibility_rank": 1,
                }
                for pid in missing_ledger
            ]
            
            explanation = (
                f"Audit trail incomplete: Bank credit {bc_id} (Rs.{amount/100:.2f}) matches payment(s) {', '.join(matched_pids)}, "
                f"but missing ledger_entries row(s) for: {', '.join(missing_ledger)}. Double-entry accounting trail cannot be fully proven."
            )
            
            exc: ExceptionItem = {
                "id": f"exc_{uuid.uuid4().hex[:8]}",
                "batch_id": batch_id,
                "related_record_type": "bank_credit",
                "related_record_id": bc_id,
                "status": "PROBABLE",
                "explanation_text": explanation,
                "hypotheses_json": json.dumps(hypotheses),
                "amount_at_risk": amount,
                "created_at": now_iso,
            }
            validate_exception_item(exc)
            exceptions.append(exc)
            processed_bc_ids.add(bc_id)

    # 2. Process Duplicate Conflicts
    duplicate_conflicts = detect_duplicate_conflicts(
        conn,
        matching_results.get("real_results", []),
        delta_explanations
    )
    dup_by_bc = {d["bank_credit_id"]: d for d in duplicate_conflicts}

    # 3. Process Delta-Explainer outputs (PROBABLE and UNRESOLVED)
    for exp in delta_explanations:
        bc_id = exp["bank_credit_id"]
        if bc_id in processed_bc_ids:
            continue

        status = exp["status"]
        if status not in ("PROBABLE", "UNRESOLVED"):
            continue

        # Check if this bank credit is a duplicate extraneous credit
        if bc_id in dup_by_bc:
            dup_info = dup_by_bc[bc_id]
            amount_risk = dup_info["amount_paise"]
            explanation = dup_info["explanation"]
            hyp_json = "[]"
            exc_status = "UNRESOLVED"
        else:
            hypotheses = exp.get("hypotheses", [])
            hyp_json = json.dumps(hypotheses)
            explanation = exp.get("explanation_text", "")
            
            # Amount at risk:
            # If there is an explained variance (delta_paise > 0), the amount at risk is the variance delta.
            # If it's a completely unexplained credit (NO_EXPLANATION), the full credit amount is at risk.
            delta = exp.get("delta_paise", 0)
            bc_amount = exp.get("bank_credit_amount_paise", 0)
            
            if delta > 0:
                amount_risk = delta
            else:
                amount_risk = bc_amount
                
            exc_status = status

        exc: ExceptionItem = {
            "id": f"exc_{uuid.uuid4().hex[:8]}",
            "batch_id": batch_id,
            "related_record_type": "bank_credit",
            "related_record_id": bc_id,
            "status": exc_status,
            "explanation_text": explanation,
            "hypotheses_json": hyp_json,
            "amount_at_risk": amount_risk,
            "created_at": now_iso,
        }
        validate_exception_item(exc)
        exceptions.append(exc)
        processed_bc_ids.add(bc_id)

    # 4. Rank exceptions by ₹-Amount-at-Risk (descending)
    exceptions.sort(key=lambda e: e["amount_at_risk"], reverse=True)
    return exceptions


def save_exceptions_to_db(conn: sqlite3.Connection, exceptions: list[ExceptionItem]) -> None:
    """
    Inserts validated exception items into the `exceptions` table in SQLite.
    """
    for exc in exceptions:
        validate_exception_item(exc)
        conn.execute("""
            INSERT OR REPLACE INTO exceptions (
                id, batch_id, related_record_type, related_record_id,
                status, explanation_text, hypotheses_json, amount_at_risk, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            exc["id"],
            exc["batch_id"],
            exc["related_record_type"],
            exc["related_record_id"],
            exc["status"],
            exc["explanation_text"],
            exc["hypotheses_json"],
            exc["amount_at_risk"],
            exc["created_at"],
        ))
    conn.commit()
