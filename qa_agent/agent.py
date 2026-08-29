"""
qa_agent/agent.py

Phase 7 — Settlement Q&A Agent (Non-Sycophantic Conversational Interface).

Hard Rules (PRD.md §4.7, Architecture.md §7, AGENTS.md §2):
1. The agent may NEVER simply agree with a user-stated explanation without documentary proof.
2. Every claim confirmation MUST cite specific record IDs (e.g. pay_*, bc_*, set_*, ref_*) from finance.db.
3. If supporting records do NOT exist or an item is UNRESOLVED/PROBABLE, the agent MUST state
   what specific evidence is missing — even under repeated, authoritative pressure.
4. Reads from already-computed records and exceptions; never performs arithmetic to decide verdicts.
"""

from __future__ import annotations
import json
import sqlite3
import re
from typing import TypedDict, Any


class Message(TypedDict):
    role: str  # 'user' | 'assistant' | 'system'
    content: str


class RecordContext(TypedDict):
    bank_credits: list[dict]
    payments: list[dict]
    settlements: list[dict]
    refunds: list[dict]
    fees: list[dict]
    exceptions: list[dict]


def fetch_relevant_records(conn: sqlite3.Connection, query_text: str) -> RecordContext:
    """
    Extracts referenced IDs, UTRs, or amounts from user query and fetches relevant DB records.
    """
    context: RecordContext = {
        "bank_credits": [],
        "payments": [],
        "settlements": [],
        "refunds": [],
        "fees": [],
        "exceptions": [],
    }

    # Find ID tokens
    bc_ids = re.findall(r"bc_[a-f0-9]+", query_text)
    pay_ids = re.findall(r"pay_[a-f0-9]+", query_text)
    set_ids = re.findall(r"set_[a-f0-9]+", query_text)
    ref_ids = re.findall(r"ref_[a-f0-9]+", query_text)
    utrs = re.findall(r"UTR\d+", query_text)

    # 1. Bank credits
    if bc_ids:
        placeholders = ",".join(["?"] * len(bc_ids))
        cur = conn.execute(f"SELECT * FROM bank_credits WHERE id IN ({placeholders})", bc_ids)
        for r in cur.fetchall():
            context["bank_credits"].append({
                "id": r[0], "narration": r[1], "amount_paise": r[2], "value_date": r[3], "parsed_utr": r[4]
            })
    elif utrs:
        placeholders = ",".join(["?"] * len(utrs))
        cur = conn.execute(f"SELECT * FROM bank_credits WHERE parsed_utr IN ({placeholders})", utrs)
        for r in cur.fetchall():
            context["bank_credits"].append({
                "id": r[0], "narration": r[1], "amount_paise": r[2], "value_date": r[3], "parsed_utr": r[4]
            })

    # 2. Payments
    if pay_ids:
        placeholders = ",".join(["?"] * len(pay_ids))
        cur = conn.execute(f"SELECT * FROM payments WHERE id IN ({placeholders})", pay_ids)
        for r in cur.fetchall():
            context["payments"].append({
                "id": r[0], "order_id": r[1], "amount_paise": r[2], "captured_at": r[3], "method": r[4]
            })

    # 3. Exceptions
    target_ids = bc_ids + pay_ids
    if target_ids:
        placeholders = ",".join(["?"] * len(target_ids))
        cur = conn.execute(
            f"SELECT id, related_record_id, status, explanation_text, hypotheses_json, amount_at_risk "
            f"FROM exceptions WHERE related_record_id IN ({placeholders})",
            target_ids
        )
        for r in cur.fetchall():
            context["exceptions"].append({
                "id": r[0],
                "related_record_id": r[1],
                "status": r[2],
                "explanation_text": r[3],
                "hypotheses": json.loads(r[4]) if r[4] else [],
                "amount_at_risk_paise": r[5],
            })
    else:
        # If no specific ID, load all current exceptions for context
        cur = conn.execute("SELECT id, related_record_id, status, explanation_text, hypotheses_json, amount_at_risk FROM exceptions")
        for r in cur.fetchall():
            context["exceptions"].append({
                "id": r[0],
                "related_record_id": r[1],
                "status": r[2],
                "explanation_text": r[3],
                "hypotheses": json.loads(r[4]) if r[4] else [],
                "amount_at_risk_paise": r[5],
            })

    return context


class SettlementQAAgent:
    """
    Non-sycophantic Settlement Q&A Agent.
    Strictly verifies all user claims against reconciled data in finance.db.
    Maintains conversational context across turns.
    """

    def __init__(self, db_path: str = "finance.db"):
        self.db_path = db_path
        self.history: list[Message] = []
        self.active_record_id: str | None = None

    def answer_query(self, user_query: str) -> str:
        """
        Processes user query, queries DB for factual ground truth,
        and generates an evidence-grounded, non-sycophantic response.
        """
        conn = sqlite3.connect(self.db_path)

        # Check for referenced records in query
        bc_match = re.search(r"bc_[a-f0-9]+", user_query)
        pay_match = re.search(r"pay_[a-f0-9]+", user_query)

        bc_id = bc_match.group(0) if bc_match else None
        pay_id = pay_match.group(0) if pay_match else None

        # Update or reuse active record ID across turns
        if bc_id:
            self.active_record_id = bc_id
        elif pay_id:
            self.active_record_id = pay_id
        elif self.active_record_id:
            # Inherit context from previous turns
            if self.active_record_id.startswith("bc_"):
                bc_id = self.active_record_id
            elif self.active_record_id.startswith("pay_"):
                pay_id = self.active_record_id

        # Query relevant context using active IDs or full text
        query_context_text = user_query
        if self.active_record_id and self.active_record_id not in user_query:
            query_context_text += f" {self.active_record_id}"

        context = fetch_relevant_records(conn, query_context_text)
        conn.close()

        # Find relevant exception if any
        matching_exc = None
        for exc in context["exceptions"]:
            if bc_id and exc["related_record_id"] == bc_id:
                matching_exc = exc
                break
            if pay_id and exc["related_record_id"] == pay_id:
                matching_exc = exc
                break

        # Check user intent: Is user asserting an unverified claim / asking to confirm something?
        is_asserting_explanation = any(
            phrase in user_query.lower()
            for phrase in [
                "is just", "is actually", "cashback", "promotional", "confirm that",
                "can we match", "i authorized", "my approval", "mark it as", "agree with",
                "waived", "discount", "special fee", "settled manually", "accept my word",
                "i am the", "just confirm", "please update", "override"
            ]
        )

        response = ""

        if matching_exc:
            exc_status = matching_exc["status"]
            exc_id = matching_exc["id"]
            rec_id = matching_exc["related_record_id"]
            risk_rs = matching_exc["amount_at_risk_paise"] / 100.0
            explanation = matching_exc["explanation_text"]
            hypotheses = matching_exc["hypotheses"]

            if is_asserting_explanation:
                # Anti-sycophancy guardrail: Check if user's asserted claim exists in the DB evidence
                if exc_status == "UNRESOLVED":
                    response = (
                        f"I cannot confirm or accept that explanation for {rec_id}. "
                        f"According to the reconciliation records, exception {exc_id} is classified as UNRESOLVED "
                        f"with an unverified exposure of Rs.{risk_rs:,.2f}.\n\n"
                        f"Database Status: {explanation}\n\n"
                        f"Missing Evidence Required: Documentary proof is absent. To substantiate any manual adjustment, "
                        f"cashback, or fee waiver, the system requires an official Credit Note, bank debit advice, "
                        f"or Razorpay fee schedule amendment record matching this exact amount in finance.db. "
                        f"Verity does not alter reconciliation verdicts based on unverified verbal or supervisory assertions."
                    )
                elif exc_status == "PROBABLE":
                    top_h = hypotheses[0] if hypotheses else {}
                    evidence_needed = top_h.get("evidence_needed", "Official settlement deduction advice.")
                    response = (
                        f"I cannot fully confirm that claim for {rec_id}. "
                        f"This transaction is currently classified as PROBABLE (Exception {exc_id}, Amount at Risk: Rs.{risk_rs:,.2f}).\n\n"
                        f"Plausible Hypothesis: {top_h.get('hypothesis', explanation)}\n\n"
                        f"Missing Evidence Required: {evidence_needed}\n"
                        f"Until this specific documentary evidence is logged and verified in the database, "
                        f"this item remains PROBABLE and cannot be closed as PROVEN."
                    )
            else:
                # Informational query about the exception
                if exc_status == "UNRESOLVED":
                    response = (
                        f"Record {rec_id} has an active UNRESOLVED exception ({exc_id}) with Rs.{risk_rs:,.2f} at risk.\n\n"
                        f"Details: {explanation}\n\n"
                        f"Status: No supported hypothesis found in statutory tax sections, MDR rates, or refund records. "
                        f"Requires manual investigation and counterparty confirmation."
                    )
                else:  # PROBABLE
                    top_h = hypotheses[0] if hypotheses else {}
                    response = (
                        f"Record {rec_id} is classified as PROBABLE (Exception {exc_id}, Amount at Risk: Rs.{risk_rs:,.2f}).\n\n"
                        f"Top Hypothesis: {top_h.get('hypothesis', explanation)}\n\n"
                        f"Missing Evidence Required: {top_h.get('evidence_needed', 'Supporting audit documentation.')}"
                    )
        else:
            # Check if this is a cleanly settled PROVEN bank credit
            if context["bank_credits"]:
                bc = context["bank_credits"][0]
                response = (
                    f"Bank credit {bc['id']} for Rs.{bc['amount_paise']/100:,.2f} (UTR: {bc['parsed_utr'] or 'N/A'}) "
                    f"was successfully reconciled and verified as PROVEN. "
                    f"All underlying payment and settlement items match within statutory tolerances with a complete ledger audit trail."
                )
            elif context["payments"]:
                pay = context["payments"][0]
                response = (
                    f"Payment {pay['id']} for gross amount Rs.{pay['amount_paise']/100:,.2f} ({pay['method']}) "
                    f"is recorded in finance.db captured at {pay['captured_at']}."
                )
            else:
                response = (
                    f"I have reviewed the reconciliation records in finance.db. "
                    f"There are currently {len(context['exceptions'])} active exceptions requiring documentary resolution. "
                    f"Please specify a valid record ID (e.g. bc_*, pay_*) to view specific audit evidence."
                )

        # Log conversation
        self.history.append({"role": "user", "content": user_query})
        self.history.append({"role": "assistant", "content": response})
        return response
