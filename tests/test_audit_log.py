"""
tests/test_audit_log.py

Unit and integration tests for Phase 8 Cryptographic Audit Trail.
Implements the required test from implementation_plan.md Phase 8:
A test that edits a past entry directly in SQLite causes a hash-chain
verification failure that is clearly detectable by the verification engine.
"""

import json
import sqlite3
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from audit_trail.audit_log import AuditTrail, compute_entry_hash, canonical_json


@pytest.fixture
def test_db():
    """Provides an isolated in-memory SQLite database with schema initialized."""
    conn = sqlite3.connect(":memory:")
    with open("schema.sql") as f:
        conn.executescript(f.read())
    yield conn
    conn.close()


def test_genesis_and_sequential_hash_chaining(test_db):
    """Verify that entries chain cleanly from GENESIS with unbroken SHA-256 hashes."""
    e1 = AuditTrail.append_entry(test_db, "TEST_EVENT_1", {"amount": 100, "status": "PROVEN"})
    assert e1["previous_hash"] == "GENESIS"
    assert len(e1["entry_hash"]) == 64

    e2 = AuditTrail.append_entry(test_db, "TEST_EVENT_2", {"amount": 200, "status": "PROBABLE"})
    assert e2["previous_hash"] == e1["entry_hash"]

    e3 = AuditTrail.append_entry(test_db, "TEST_EVENT_3", {"amount": 300, "status": "UNRESOLVED"})
    assert e3["previous_hash"] == e2["entry_hash"]

    res = AuditTrail.verify_chain(test_db)
    assert res["is_valid"] is True
    assert res["total_entries"] == 3
    assert res["genesis_hash"] == e1["entry_hash"]
    assert res["latest_hash"] == e3["entry_hash"]
    assert res["tampered_entry_id"] is None


def test_tamper_detection_modified_payload(test_db):
    """
    Phase 8 Done-When Requirement:
    Direct modification of a past entry payload causes a clear hash-chain verification failure.
    """
    e1 = AuditTrail.append_entry(test_db, "EVENT_1", {"metric": 10})
    e2 = AuditTrail.append_entry(test_db, "EVENT_2", {"status": "UNRESOLVED", "risk": 50000})
    e3 = AuditTrail.append_entry(test_db, "EVENT_3", {"metric": 30})

    # Direct malicious tampering: change UNRESOLVED to PROVEN in SQLite without updating hash
    tampered_payload = canonical_json({"event_type": "EVENT_2", "data": {"status": "PROVEN", "risk": 50000}})
    test_db.execute("UPDATE audit_log SET payload_json = ? WHERE id = ?", (tampered_payload, e2["id"]))
    test_db.commit()

    res = AuditTrail.verify_chain(test_db)
    assert res["is_valid"] is False
    assert res["tampered_entry_id"] == e2["id"]
    assert res["tampered_index"] == 1
    assert "Content tampering detected" in res["error_message"]


def test_tamper_detection_deleted_intermediate_entry(test_db):
    """Verify that deleting an intermediate entry breaks previous_hash linkage."""
    e1 = AuditTrail.append_entry(test_db, "EVENT_1", {"v": 1})
    e2 = AuditTrail.append_entry(test_db, "EVENT_2", {"v": 2})
    e3 = AuditTrail.append_entry(test_db, "EVENT_3", {"v": 3})

    # Delete e2 directly
    test_db.execute("DELETE FROM audit_log WHERE id = ?", (e2["id"],))
    test_db.commit()

    res = AuditTrail.verify_chain(test_db)
    assert res["is_valid"] is False
    assert res["tampered_entry_id"] == e3["id"]
    assert res["tampered_index"] == 1
    assert "Linkage broken" in res["error_message"]


def test_tamper_detection_modified_timestamp(test_db):
    """Verify that backdating or altering an entry's timestamp breaks its hash."""
    e1 = AuditTrail.append_entry(test_db, "EVENT_1", {"v": 1}, created_at="2026-08-01T10:00:00")
    e2 = AuditTrail.append_entry(test_db, "EVENT_2", {"v": 2}, created_at="2026-08-01T11:00:00")

    # Alter timestamp on e1
    test_db.execute("UPDATE audit_log SET created_at = '2026-08-01T09:00:00' WHERE id = ?", (e1["id"],))
    test_db.commit()

    res = AuditTrail.verify_chain(test_db)
    assert res["is_valid"] is False
    assert res["tampered_entry_id"] == e1["id"]
    assert "Content tampering detected" in res["error_message"]


def test_canonical_json_key_order_invariance():
    """
    Verify that JSON serialization and SHA-256 entry hash are strictly invariant
    to dictionary key insertion order (preventing nondeterministic hash drift).
    """
    # Two dictionaries with identical logical data constructed in reversed/scrambled key orders
    payload_a = {
        "status": "PROVEN",
        "amount_paise": 45000,
        "bank_credit_id": "bc_test_123",
        "metadata": {"utr": "UTR12345", "method": "UPI", "tolerance_bps": 50},
        "matched_payment_ids": ["pay_01", "pay_02"],
    }
    payload_b = {
        "matched_payment_ids": ["pay_01", "pay_02"],
        "metadata": {"tolerance_bps": 50, "method": "UPI", "utr": "UTR12345"},
        "bank_credit_id": "bc_test_123",
        "amount_paise": 45000,
        "status": "PROVEN",
    }

    str_a = canonical_json(payload_a)
    str_b = canonical_json(payload_b)
    assert str_a == str_b

    prev_hash = "GENESIS"
    ts = "2026-08-29T20:00:00"
    hash_a = compute_entry_hash(prev_hash, str_a, ts)
    hash_b = compute_entry_hash(prev_hash, str_b, ts)
    assert hash_a == hash_b


def test_batch_verdicts_logging_and_verification(test_db):
    """Test full pipeline verdict logging across individual matches, delta-explainer, exceptions, and forecast."""
    matching_results = {
        "real_results": [
            {"bank_credit_id": "bc_1", "status": "MATCHED", "matched_payment_ids": ["pay_1"]},
            {"bank_credit_id": "bc_2", "status": "PROBABLE", "matched_payment_ids": ["pay_2"], "missing_ledger_payment_ids": ["pay_2"]},
            {"bank_credit_id": "bc_3", "status": "UNMATCHED"},
        ]
    }
    delta_explanations = [
        {"bank_credit_id": "bc_3", "status": "PROBABLE", "delta_paise": 900, "hypotheses": [{"category": "TAX_RATE_VARIANCE"}]}
    ]
    exceptions = [
        {"id": "exc_1", "related_record_id": "bc_3", "status": "PROBABLE", "amount_at_risk": 900, "explanation_text": "TDS rate variance"}
    ]
    forecast_report = {
        "total_expected_inflows_net_paise": 62816,
        "total_pending_outflows_paise": 12000,
        "net_projected_cash_position_paise": 50816,
    }

    entries = AuditTrail.record_batch_verdicts(
        conn=test_db,
        batch_id="test_batch_01",
        matching_results=matching_results,
        delta_explanations=delta_explanations,
        exceptions=exceptions,
        forecast_report=forecast_report
    )

    # 3 matching verdicts (bc_1, bc_2, bc_3) + 1 delta explainer + 1 exception + 1 forecast snapshot = 6 entries
    assert len(entries) == 6
    assert entries[0]["payload_json"].find("MATCH_VERDICT_PROVEN") != -1
    assert entries[1]["payload_json"].find("MATCH_VERDICT_PROBABLE_LEDGER_GAP") != -1
    assert entries[2]["payload_json"].find("MATCH_VERDICT_UNMATCHED") != -1

    res = AuditTrail.verify_chain(test_db)
    assert res["is_valid"] is True
    assert res["total_entries"] == 6

