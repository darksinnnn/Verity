"""
tests/test_nudges.py

Unit and integration tests for Phase 9 Actionable Exceptions (Mocked Nudge Engine).
Validates PRD.md §4.8 & AGENTS.md §2 requirements:
- Actionable plain-English nudge messages for all exception categories.
- Strict mock isolation: zero external network / Slack / email side-effects.
- Exact transaction citation and integer paise integrity.
"""

import json
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from nudges.nudge_engine import draft_nudge_for_exception, generate_all_nudges, dispatch_nudge_mock


def test_nudge_drafting_tds_variance():
    """Verify targeted nudge drafting for TDS section rate variance."""
    exc = {
        "id": "exc_tds_01",
        "related_record_id": "bc_dd56cc94",
        "status": "PROBABLE",
        "amount_at_risk": 900,
        "explanation_text": "Plausible explanation found: TDS was deducted at 2.0% under Section 194C / Section 194J(1)",
        "hypotheses_json": json.dumps([{
            "category": "TAX_RATE_VARIANCE",
            "hypothesis": "TDS was deducted at 2.0% under Section 194C / Section 194J(1) rather than standard 1.0%",
            "evidence_needed": "Vendor TDS Certificate (Form 16A) confirming Section 194C / Section 194J(1)."
        }])
    }

    nudge = draft_nudge_for_exception(exc)
    assert nudge["exception_id"] == "exc_tds_01"
    assert nudge["related_record_id"] == "bc_dd56cc94"
    assert "Tax Operations" in nudge["recipient_team"]
    assert "194C" in nudge["message_body"] or "194J" in nudge["message_body"]
    assert "Form 16A" in nudge["message_body"]
    assert "Rs.9.00" in nudge["message_body"]
    assert nudge["is_mocked"] is True


def test_nudge_drafting_refund_recovery():
    """Verify targeted nudge drafting for cross-settlement refund recovery."""
    exc = {
        "id": "exc_ref_01",
        "related_record_id": "bc_f94d6204",
        "status": "PROBABLE",
        "amount_at_risk": 20000,
        "explanation_text": "Settlement was short by Rs.200.00 due to cross-settlement recovery of refund on payment pay_eededb07",
        "hypotheses_json": json.dumps([{
            "category": "REFUND_RECOVERY",
            "hypothesis": "Settlement was short by Rs.200.00 due to cross-settlement recovery of refund on payment pay_eededb07",
            "evidence_needed": "Settlement advice confirming refund deduction against refund ID ref_ae9bec36."
        }])
    }

    nudge = draft_nudge_for_exception(exc)
    assert nudge["exception_id"] == "exc_ref_01"
    assert "Settlement" in nudge["recipient_team"]
    assert "bc_f94d6204" in nudge["message_body"]
    assert "Rs.200.00" in nudge["message_body"]
    assert nudge["is_mocked"] is True


def test_nudge_drafting_missing_ledger():
    """Verify targeted nudge drafting for missing double-entry ERP record."""
    exc = {
        "id": "exc_leg_01",
        "related_record_id": "bc_c991603f",
        "status": "PROBABLE",
        "amount_at_risk": 24160,
        "explanation_text": "Audit trail incomplete: Bank credit bc_c991603f matches payment pay_bc2cbb0d, but missing ledger_entries row",
        "hypotheses_json": json.dumps([{
            "category": "MISSING_LEDGER",
            "hypothesis": "Payment pay_bc2cbb0d was received and settled, but corresponding ledger record is missing",
            "evidence_needed": "Verify ERP integration logs for payment pay_bc2cbb0d to post missing ledger_entries row."
        }])
    }

    nudge = draft_nudge_for_exception(exc)
    assert "Engineering" in nudge["recipient_team"] or "ERP" in nudge["recipient_team"]
    assert "pay_bc2cbb0d" in nudge["message_body"]
    assert "Rs.241.60" in nudge["message_body"]


def test_dispatch_nudge_mock_is_strictly_noop():
    """
    AGENTS.md §2 Hard Prohibition:
    Never wire up a real third-party integration (Slack, email, SMS).
    Verify that dispatch_nudge_mock strictly returns a local mocked receipt.
    """
    nudge = {
        "exception_id": "exc_test_01",
        "related_record_id": "bc_test_01",
        "status": "PROBABLE",
        "amount_at_risk_paise": 15000,
        "recipient_team": "Vendor Finance",
        "channel": "Slack (#finance-alerts)",
        "subject": "[Alert] Test",
        "message_body": "Test body",
        "suggested_action": "Review",
        "is_mocked": True,
    }

    receipt = dispatch_nudge_mock(nudge)
    assert receipt["status"] == "MOCKED_DISPATCHED"
    assert receipt["logged_only"] is True
    assert "MOCKED NO-OP" in receipt["mocked_confirmation"]
    assert receipt["exception_id"] == "exc_test_01"


def test_generate_all_nudges_batch_integrity():
    """Verify batch nudge generation across mixed exception states."""
    exceptions = [
        {"id": "exc_1", "related_record_id": "bc_1", "status": "PROBABLE", "amount_at_risk": 900, "explanation_text": "TDS 194C variance", "hypotheses_json": "[]"},
        {"id": "exc_2", "related_record_id": "bc_2", "status": "UNRESOLVED", "amount_at_risk": 50000, "explanation_text": "Duplicate extraneous bank credit", "hypotheses_json": "[]"},
        {"id": "exc_3", "related_record_id": "bc_3", "status": "UNRESOLVED", "amount_at_risk": 15000, "explanation_text": "Unexplained variance of Rs.150", "hypotheses_json": "[]"},
    ]

    nudges = generate_all_nudges(exceptions)
    assert len(nudges) == 3
    assert all(n["is_mocked"] is True for n in nudges)
    assert all(n["amount_at_risk_paise"] > 0 for n in nudges)
