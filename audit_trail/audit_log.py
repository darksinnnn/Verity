"""
audit_trail/audit_log.py

Phase 8 — Audit Trail (Cryptographic Hash-Chained Append-Only Log).

Hard Rules (PRD.md §4.9, Architecture.md §2 & §7, implementation_plan.md Phase 8):
1. Every verdict (match, explanation, exception state, forecast snapshot) is written
   to an append-only, cryptographic hash-chained log in the `audit_log` table.
2. Each entry's hash is SHA-256(previous_hash + canonical_payload_json + created_at).
3. The genesis entry uses previous_hash = "GENESIS".
4. Any after-the-fact edit to past payloads, timestamps, or hash links instantly
   causes a hash-chain verification failure that pinpoints the exact tampered entry.
"""

from __future__ import annotations
import hashlib
import json
import sqlite3
import uuid
from datetime import datetime
from typing import TypedDict, Any


class AuditEntry(TypedDict):
    id: str
    entry_hash: str
    previous_hash: str | None
    payload_json: str
    created_at: str


class VerificationResult(TypedDict):
    is_valid: bool
    total_entries: int
    genesis_hash: str | None
    latest_hash: str | None
    tampered_entry_id: str | None
    tampered_index: int | None
    error_message: str | None


def canonical_json(data: Any) -> str:
    """Produces a deterministic, canonical JSON string with sorted keys."""
    return json.dumps(data, sort_keys=True, separators=(',', ':'))


def compute_entry_hash(previous_hash: str | None, payload_json: str, created_at: str) -> str:
    """Computes SHA-256 hash over previous_hash + payload_json + created_at."""
    prev_str = previous_hash if previous_hash is not None else "GENESIS"
    raw_bytes = f"{prev_str}|{payload_json}|{created_at}".encode('utf-8')
    return hashlib.sha256(raw_bytes).hexdigest()


class AuditTrail:
    """
    Manages the append-only cryptographic hash chain in SQLite.
    """

    def __init__(self, db_path: str = "finance.db"):
        self.db_path = db_path

    @staticmethod
    def append_entry(
        conn: sqlite3.Connection,
        event_type: str,
        payload_data: dict,
        created_at: str | None = None
    ) -> AuditEntry:
        """
        Appends a new event to the audit_log table, chaining to the previous entry's hash.
        """
        now_iso = created_at or datetime.utcnow().isoformat()

        # Fetch the latest entry hash
        cur = conn.execute("SELECT id, entry_hash FROM audit_log ORDER BY rowid DESC LIMIT 1")
        last_row = cur.fetchone()

        previous_hash = last_row[1] if last_row else "GENESIS"

        # Enrich payload with event metadata
        full_payload = {
            "event_type": event_type,
            "data": payload_data,
        }
        payload_str = canonical_json(full_payload)

        entry_id = f"aud_{uuid.uuid4().hex[:8]}"
        entry_hash = compute_entry_hash(previous_hash, payload_str, now_iso)

        conn.execute("""
            INSERT INTO audit_log (id, entry_hash, previous_hash, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (entry_id, entry_hash, previous_hash, payload_str, now_iso))
        conn.commit()

        return {
            "id": entry_id,
            "entry_hash": entry_hash,
            "previous_hash": previous_hash,
            "payload_json": payload_str,
            "created_at": now_iso,
        }

    @staticmethod
    def verify_chain(conn: sqlite3.Connection) -> VerificationResult:
        """
        Verifies the cryptographic integrity of the entire audit_log table.
        Recomputes SHA-256 hashes and verifies unbroken previous_hash linkage.
        """
        cur = conn.execute("SELECT id, entry_hash, previous_hash, payload_json, created_at FROM audit_log ORDER BY rowid ASC")
        rows = cur.fetchall()

        if not rows:
            return {
                "is_valid": True,
                "total_entries": 0,
                "genesis_hash": None,
                "latest_hash": None,
                "tampered_entry_id": None,
                "tampered_index": None,
                "error_message": None,
            }

        expected_prev_hash = "GENESIS"
        genesis_hash = rows[0][1]
        latest_hash = rows[-1][1]

        for idx, (entry_id, stored_hash, stored_prev, payload_json, created_at) in enumerate(rows):
            # 1. Check previous_hash link
            if stored_prev != expected_prev_hash:
                return {
                    "is_valid": False,
                    "total_entries": len(rows),
                    "genesis_hash": genesis_hash,
                    "latest_hash": latest_hash,
                    "tampered_entry_id": entry_id,
                    "tampered_index": idx,
                    "error_message": f"Linkage broken at index {idx} ({entry_id}): expected previous_hash '{expected_prev_hash}', got '{stored_prev}'",
                }

            # 2. Recompute and verify current entry hash
            recomputed_hash = compute_entry_hash(stored_prev, payload_json, created_at)
            if stored_hash != recomputed_hash:
                return {
                    "is_valid": False,
                    "total_entries": len(rows),
                    "genesis_hash": genesis_hash,
                    "latest_hash": latest_hash,
                    "tampered_entry_id": entry_id,
                    "tampered_index": idx,
                    "error_message": f"Content tampering detected at index {idx} ({entry_id}): stored hash '{stored_hash}' does not match recomputed hash '{recomputed_hash}'",
                }

            expected_prev_hash = stored_hash

        return {
            "is_valid": True,
            "total_entries": len(rows),
            "genesis_hash": genesis_hash,
            "latest_hash": latest_hash,
            "tampered_entry_id": None,
            "tampered_index": None,
            "error_message": None,
        }

    @classmethod
    def record_batch_verdicts(
        cls,
        conn: sqlite3.Connection,
        batch_id: str,
        matching_results: dict,
        delta_explanations: list[dict],
        exceptions: list[dict],
        forecast_report: dict | None = None
    ) -> list[AuditEntry]:
        """
        Records every individual pipeline verdict from Phases 3–7 into the cryptographic hash chain.
        Ensures all 49+ individual match decisions (PROVEN, PROBABLE, UNMATCHED) are immutably logged.
        """
        entries = []

        # 1. Record INDIVIDUAL Matching Engine verdicts for every single bank credit
        real_results = matching_results.get("real_results", [])
        for r in real_results:
            status = r.get("status")
            bc_id = r.get("bank_credit_id")
            if status == "MATCHED":
                event_type = "MATCH_VERDICT_PROVEN"
            elif status == "PROBABLE":
                event_type = "MATCH_VERDICT_PROBABLE_LEDGER_GAP"
            else:
                event_type = "MATCH_VERDICT_UNMATCHED"

            entries.append(cls.append_entry(conn, event_type, {
                "batch_id": batch_id,
                "bank_credit_id": bc_id,
                "status": status,
                "matched_payment_ids": r.get("matched_payment_ids", []),
                "bank_credit_amount_paise": r.get("bank_credit_amount_paise"),
                "matched_sum_paise": r.get("matched_sum_paise"),
                "epsilon_pct_used": r.get("epsilon_pct_used"),
                "utr_anchored": r.get("utr_anchored", False),
                "missing_ledger_payment_ids": r.get("missing_ledger_payment_ids", []),
            }))

        # 2. Record Delta Explainer verdicts
        for de in delta_explanations:
            entries.append(cls.append_entry(conn, "DELTA_EXPLANATION_VERDICT", {
                "batch_id": batch_id,
                "bank_credit_id": de["bank_credit_id"],
                "status": de["status"],
                "delta_paise": de.get("delta_paise", 0),
                "top_category": de["hypotheses"][0]["category"] if de.get("hypotheses") else "NO_EXPLANATION",
            }))

        # 3. Record Exceptions verdicts
        for exc in exceptions:
            entries.append(cls.append_entry(conn, "EXCEPTION_STATE_RECORDED", {
                "batch_id": batch_id,
                "exception_id": exc["id"],
                "related_record_id": exc["related_record_id"],
                "status": exc["status"],
                "amount_at_risk_paise": exc["amount_at_risk"],
                "explanation": exc["explanation_text"][:80],
            }))

        # 4. Record Cash Forecast snapshot
        if forecast_report:
            entries.append(cls.append_entry(conn, "CASH_FORECAST_SNAPSHOT", {
                "batch_id": batch_id,
                "expected_net_inflows_paise": forecast_report["total_expected_inflows_net_paise"],
                "pending_outflows_paise": forecast_report["total_pending_outflows_paise"],
                "net_projected_cash_paise": forecast_report["net_projected_cash_position_paise"],
            }))

        return entries

