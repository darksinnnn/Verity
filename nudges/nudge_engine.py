"""
nudges/nudge_engine.py

Phase 9 — Actionable Exceptions (Mocked Nudge Engine).

Hard Rules (PRD.md §4.8, Architecture.md §7 item 4, AGENTS.md §2):
1. For resolvable-looking exceptions, auto-draft plain-English nudge messages
   citing specific record IDs, exact variances, and required counterparty evidence.
2. Absolutely NO live third-party integrations (Slack, email, SMS, etc.).
3. The dispatch action is a mocked UI no-op that logs the draft locally with `logged_only=True`.
"""

from __future__ import annotations
import json
import sqlite3
from datetime import datetime
from typing import TypedDict, Any


class NudgeDraft(TypedDict):
    exception_id: str
    related_record_id: str
    status: str
    amount_at_risk_paise: int
    recipient_team: str
    channel: str
    subject: str
    message_body: str
    suggested_action: str
    is_mocked: bool


class DispatchReceipt(TypedDict):
    status: str
    exception_id: str
    recipient: str
    channel: str
    subject: str
    dispatched_at: str
    logged_only: bool
    mocked_confirmation: str


def draft_nudge_for_exception(exception: dict) -> NudgeDraft:
    """
    Auto-drafts a targeted, plain-English action message for an exception.
    Cites specific transaction IDs, exact rupee amounts, and missing evidence required.
    """
    exc_id = exception["id"]
    rec_id = exception["related_record_id"]
    status = exception["status"]
    risk_paise = exception["amount_at_risk"]
    risk_rs = risk_paise / 100.0
    explanation = exception.get("explanation_text", "")
    
    hypotheses = []
    if exception.get("hypotheses_json"):
        try:
            hypotheses = json.loads(exception["hypotheses_json"]) if isinstance(exception["hypotheses_json"], str) else exception["hypotheses_json"]
        except Exception:
            hypotheses = []
    elif exception.get("hypotheses"):
        hypotheses = exception["hypotheses"]

    top_h = hypotheses[0] if hypotheses else {}
    top_hypothesis_text = top_h.get("hypothesis", "")
    evidence_needed = top_h.get("evidence_needed", "")

    # Target the nudge by exception type & hypothesis
    if "194C" in top_hypothesis_text or "194J" in top_hypothesis_text or "TDS" in explanation:
        recipient = "Vendor Tax Operations / Accounts Payable"
        channel = "Email (vendor-tax@counterparty.com)"
        subject = f"[Action Required] TDS Rate Variance on Settlement {rec_id} (Rs.{risk_rs:,.2f})"
        message_body = (
            f"Hi Tax Operations Team,\n\n"
            f"During automated settlement reconciliation for credit reference {rec_id}, "
            f"Verity detected an unexplained TDS deduction variance of Rs.{risk_rs:,.2f}.\n\n"
            f"• Primary Hypothesis: {top_hypothesis_text}\n"
            f"• Required Action: Please provide the vendor Form 16A TDS Certificate or settlement deduction breakdown "
            f"confirming the applicable section rate (Section 194C vs 194J(1)) to complete audit verification.\n\n"
            f"Reference Exception: {exc_id}"
        )
        suggested_action = "Request Form 16A TDS Certificate from Vendor Tax Ops"

    elif "refund" in top_hypothesis_text.lower() or "recovery of refund" in explanation.lower() or "refund on payment" in explanation.lower():
        recipient = "Merchant Operations / Settlement Desk"
        channel = "Slack (#finance-settlements)"
        subject = f"[Discrepancy Alert] Cross-Settlement Refund Recovery on {rec_id} (Rs.{risk_rs:,.2f})"
        message_body = (
            f"Hi Settlement Ops,\n\n"
            f"Bank credit {rec_id} was short-settled by Rs.{risk_rs:,.2f}.\n\n"
            f"• Finding: {top_hypothesis_text or explanation}\n"
            f"• Required Action: Please confirm if this deduction corresponds to the referenced refund adjustment "
            f"and attach the Razorpay settlement advice to resolve exception {exc_id}.\n\n"
            f"Reference Exception: {exc_id}"
        )
        suggested_action = "Confirm settlement deduction against refund ID in gateway portal"


    elif "ledger" in explanation.lower() or "missing" in explanation.lower():
        recipient = "Core Banking / ERP Engineering Team"
        channel = "Slack (#erp-data-sync)"
        subject = f"[Data Gap] Missing Double-Entry Ledger Record for Payment (Rs.{risk_rs:,.2f})"
        message_body = (
            f"Hi Engineering Team,\n\n"
            f"Bank credit {rec_id} (Rs.{risk_rs:,.2f}) has settled successfully, but the corresponding internal double-entry "
            f"ledger entry is absent in ledger_entries for the matched payment.\n\n"
            f"• Details: {explanation}\n"
            f"• Required Action: {evidence_needed or 'Inspect sync worker logs and backfill the missing ledger entry.'}\n\n"
            f"Reference Exception: {exc_id}"
        )
        suggested_action = "Trigger ERP integration resync for missing ledger_entries record"


    elif "duplicate" in explanation.lower():
        recipient = "Treasury Operations / Bank Relationship Manager"
        channel = "Email (treasury-ops@bank.com)"
        subject = f"[Duplicate Instruction Alert] Extraneous Bank Credit {rec_id} (Rs.{risk_rs:,.2f})"
        message_body = (
            f"Hi Treasury Team,\n\n"
            f"An unbacked duplicate credit instruction of Rs.{risk_rs:,.2f} was received under reference {rec_id}.\n\n"
            f"• Finding: {explanation}\n"
            f"• Required Action: Verify with remitting bank whether this represents a duplicate clearing attempt "
            f"or requires return credit reversal.\n\n"
            f"Reference Exception: {exc_id}"
        )
        suggested_action = "Initiate duplicate credit inquiry with remitting bank"

    else:
        recipient = "Finance Controller / Counterparty Support"
        channel = "Email (controller@company.com)"
        subject = f"[Unresolved Variance] Unexplained Gap on {rec_id} (Rs.{risk_rs:,.2f})"
        message_body = (
            f"Hi Finance Team,\n\n"
            f"Bank credit {rec_id} has an unexplained variance of Rs.{risk_rs:,.2f} with zero matching statutory or fee deductions.\n\n"
            f"• Status: {explanation}\n"
            f"• Required Action: Manual counterparty investigation required. Request revised settlement statement from Razorpay.\n\n"
            f"Reference Exception: {exc_id}"
        )
        suggested_action = "Request revised itemized settlement statement from gateway"


    return {
        "exception_id": exc_id,
        "related_record_id": rec_id,
        "status": status,
        "amount_at_risk_paise": risk_paise,
        "recipient_team": recipient,
        "channel": channel,
        "subject": subject,
        "message_body": message_body,
        "suggested_action": suggested_action,
        "is_mocked": True,
    }


def generate_all_nudges(exceptions: list[dict]) -> list[NudgeDraft]:
    """Generates auto-drafted actionable nudges for all provided exceptions."""
    return [draft_nudge_for_exception(exc) for exc in exceptions]


def dispatch_nudge_mock(nudge: NudgeDraft) -> DispatchReceipt:
    """
    Mocked 'would send' button handler (PRD.md §4.8).
    Strictly performs NO network requests or external side-effects.
    Returns a mocked dispatch receipt proving UI readiness.
    """
    now_iso = datetime.utcnow().isoformat()
    return {
        "status": "MOCKED_DISPATCHED",
        "exception_id": nudge["exception_id"],
        "recipient": nudge["recipient_team"],
        "channel": nudge["channel"],
        "subject": nudge["subject"],
        "dispatched_at": now_iso,
        "logged_only": True,
        "mocked_confirmation": f"[MOCKED NO-OP] Nudge for {nudge['exception_id']} successfully logged to dispatch queue (zero network side-effects).",
    }
