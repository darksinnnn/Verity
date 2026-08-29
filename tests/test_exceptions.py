"""
tests/test_exceptions.py

Unit and integration tests for Phase 5 Exception System.
Covers:
  - test_exception_amount_at_risk_ranking: Strictly ordered by amount_at_risk DESC
  - test_duplicate_conflict_detection: Specifically verifies duplicate conflict on bc_4eea04e7 vs bc_0ab54bde
  - test_write_time_validation_rejects_empty_explanation: Enforces non-empty explanation_text
  - test_write_time_validation_requires_hypotheses_for_probable: Enforces valid hypotheses_json for PROBABLE
  - test_exceptions_db_persistence_roundtrip: Validates SQLite write and integrity
  - test_no_numeric_confidence_scores: Validates strict 3-state system
"""

import json
import sqlite3
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from exceptions.engine import (
    build_exceptions,
    save_exceptions_to_db,
    validate_exception_item,
    detect_duplicate_conflicts,
    ExceptionItem
)


def test_exception_amount_at_risk_ranking():
    """Verify that exceptions are strictly ordered by amount_at_risk in descending order."""
    conn = sqlite3.connect('finance.db')
    with open('matching_results.json') as f:
        mr = json.load(f)
    with open('delta_explanations.json') as f:
        de = json.load(f)

    exceptions = build_exceptions(conn, mr, de, batch_id='test_batch')
    conn.close()

    assert len(exceptions) > 0, "No exceptions generated"
    amounts = [e["amount_at_risk"] for e in exceptions]
    assert amounts == sorted(amounts, reverse=True), f"Exceptions not sorted by amount_at_risk DESC: {amounts}"


def test_duplicate_conflict_detection_bc_4eea04e7():
    """
    Verify that duplicate conflict detection specifically catches bc_4eea04e7 vs bc_0ab54bde
    and marks bc_4eea04e7 as an UNRESOLVED duplicate exception with amount_at_risk == 53152.
    """
    conn = sqlite3.connect('finance.db')
    with open('matching_results.json') as f:
        mr = json.load(f)
    with open('delta_explanations.json') as f:
        de = json.load(f)

    exceptions = build_exceptions(conn, mr, de, batch_id='test_batch')
    conn.close()

    dup_exc = next((e for e in exceptions if e["related_record_id"] == "bc_4eea04e7"), None)
    assert dup_exc is not None, "Duplicate exception for bc_4eea04e7 not found"
    assert dup_exc["status"] == "UNRESOLVED"
    assert dup_exc["amount_at_risk"] == 53152  # Rs.531.52
    assert "Duplicate credit" in dup_exc["explanation_text"]
    assert "bc_0ab54bde" in dup_exc["explanation_text"] or "primary" in dup_exc["explanation_text"]


def test_write_time_validation_rejects_empty_explanation():
    """Verify that validate_exception_item raises ValueError on empty, too-short, or generic explanation_text."""
    invalid_exc: ExceptionItem = {
        "id": "exc_test1",
        "batch_id": "batch_1",
        "related_record_type": "bank_credit",
        "related_record_id": "bc_test",
        "status": "UNRESOLVED",
        "explanation_text": "",  # Empty explanation
        "hypotheses_json": "[]",
        "amount_at_risk": 5000,
        "created_at": "2026-08-29T10:00:00",
    }
    with pytest.raises(ValueError, match="explanation_text must be non-empty"):
        validate_exception_item(invalid_exc)

    invalid_exc["explanation_text"] = "Short explanation"  # < 20 chars
    with pytest.raises(ValueError, match="too short"):
        validate_exception_item(invalid_exc)

    invalid_exc["explanation_text"] = "This is a generic message without any financial reference."  # >=20 chars but no record/amount ref
    with pytest.raises(ValueError, match="must cite a specific record ID, UTR, or amount"):
        validate_exception_item(invalid_exc)


def test_write_time_validation_requires_hypotheses_for_probable():
    """Verify that validate_exception_item raises ValueError if a PROBABLE item has empty hypotheses."""
    invalid_probable: ExceptionItem = {
        "id": "exc_test2",
        "batch_id": "batch_1",
        "related_record_type": "bank_credit",
        "related_record_id": "bc_test",
        "status": "PROBABLE",
        "explanation_text": "Valid explanation citing bc_test and Rs.50.00 that is sufficiently long.",
        "hypotheses_json": "[]",  # Empty hypotheses for PROBABLE
        "amount_at_risk": 5000,
        "created_at": "2026-08-29T10:00:00",
    }
    with pytest.raises(ValueError, match="must contain at least one hypothesis in hypotheses_json"):
        validate_exception_item(invalid_probable)


def test_exceptions_db_persistence_roundtrip():
    """Verify that exceptions can be written to SQLite exceptions table and read back faithfully."""
    conn = sqlite3.connect(':memory:')
    with open('schema.sql') as f:
        conn.executescript(f.read())

    sample_exc: ExceptionItem = {
        "id": "exc_roundtrip",
        "batch_id": "batch_sample",
        "related_record_type": "bank_credit",
        "related_record_id": "bc_sample",
        "status": "PROBABLE",
        "explanation_text": "Sample valid exception on bc_sample with variance of Rs.125.00 for testing roundtrip persistence.",
        "hypotheses_json": json.dumps([{"hypothesis": "Test hypothesis", "evidence_needed": "Test evidence"}]),
        "amount_at_risk": 12500,
        "created_at": "2026-08-29T12:00:00",
    }

    save_exceptions_to_db(conn, [sample_exc])

    row = conn.execute("SELECT * FROM exceptions WHERE id = 'exc_roundtrip'").fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "exc_roundtrip"
    assert row[1] == "batch_sample"
    assert row[2] == "bank_credit"
    assert row[3] == "bc_sample"
    assert row[4] == "PROBABLE"
    assert row[5] == sample_exc["explanation_text"]
    assert json.loads(row[6]) == json.loads(sample_exc["hypotheses_json"])
    assert row[7] == 12500  # Exact integer paise
    assert row[8] == "2026-08-29T12:00:00"


def test_no_numeric_confidence_scores():
    """Verify that all exceptions use canonical 3-state verdicts and no numeric percentage scores exist."""
    conn = sqlite3.connect('finance.db')
    rows = conn.execute("SELECT status, explanation_text, hypotheses_json FROM exceptions").fetchall()
    conn.close()

    for status, explanation, hypotheses in rows:
        assert status in ("PROBABLE", "UNRESOLVED")
        # Ensure no percentage confidence statements like '87% confident' or '0.87 probability'
        assert "confident" not in explanation.lower()
        assert "% confident" not in explanation.lower()
        assert "% probability" not in explanation.lower()
