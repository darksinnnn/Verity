"""
tests/test_forecaster.py

Unit and integration tests for Phase 6 Forward Cash Forecaster.
Covers:
  - test_hand_calculated_pending_inflow_totals: Hand-verifiable arithmetic on exact integer paise
  - test_pending_refund_deduction: Verifies open refund deduction from projected position
  - test_method_breakdown: Verifies aggregation by payment method (UPI, CARD, NACH)
  - test_settled_payments_excluded: Proves already-settled payments are excluded
  - test_integer_paise_no_float_drift: Asserts zero floating-point drift on all values
  - test_daily_schedule_t_plus_offset: Asserts correct T+1 and T+3 scheduling
"""

import sqlite3
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from forecaster.forecaster import compute_pending_exposure


def test_hand_calculated_pending_inflow_totals():
    """
    Hand-calculated verification:
    Payment 1: UPI gross 100,000 paise (MDR 2000, GST 360, TDS 1000 -> net 96,640)
    Payment 2: NACH gross 50,000 paise (0 MDR/GST/TDS -> net 50,000)
    Total Gross = 150,000 paise
    Total Fees  = 3,360 paise
    Expected Net Inflow = 146,640 paise
    """
    conn = sqlite3.connect(':memory:')
    conn.executescript("""
        CREATE TABLE orders (id TEXT PRIMARY KEY, amount INTEGER, created_at TEXT, customer_ref TEXT);
        CREATE TABLE payments (id TEXT PRIMARY KEY, order_id TEXT, amount INTEGER, captured_at TEXT, method TEXT);
        CREATE TABLE refunds (id TEXT PRIMARY KEY, payment_id TEXT, amount INTEGER, created_at TEXT, status TEXT);
        CREATE TABLE settlement_items (id TEXT PRIMARY KEY, settlement_id TEXT, payment_id TEXT, contribution_amount INTEGER);

        INSERT INTO orders VALUES ('ord_1', 100000, '2026-09-01T10:00:00', 'cust_1'), ('ord_2', 50000, '2026-09-01T10:00:00', 'cust_2');
        INSERT INTO payments VALUES ('pay_1', 'ord_1', 100000, '2026-09-01T10:00:00', 'UPI'), ('pay_2', 'ord_2', 50000, '2026-09-01T10:00:00', 'NACH');
    """)

    report = compute_pending_exposure(conn, settled_payment_ids=set())
    conn.close()

    assert report["total_pending_inflows_gross_paise"] == 150000
    assert report["total_estimated_deductions_paise"] == 3360
    assert report["total_expected_inflows_net_paise"] == 146640
    assert report["total_pending_outflows_paise"] == 0
    assert report["net_projected_cash_position_paise"] == 146640


def test_pending_refund_deduction():
    """
    Verify that an open/pending refund of 20,000 paise is deducted from net cash position.
    Expected Net Position = 146,640 - 20,000 = 126,640 paise.
    """
    conn = sqlite3.connect(':memory:')
    conn.executescript("""
        CREATE TABLE orders (id TEXT PRIMARY KEY, amount INTEGER, created_at TEXT, customer_ref TEXT);
        CREATE TABLE payments (id TEXT PRIMARY KEY, order_id TEXT, amount INTEGER, captured_at TEXT, method TEXT);
        CREATE TABLE refunds (id TEXT PRIMARY KEY, payment_id TEXT, amount INTEGER, created_at TEXT, status TEXT);
        CREATE TABLE settlement_items (id TEXT PRIMARY KEY, settlement_id TEXT, payment_id TEXT, contribution_amount INTEGER);

        INSERT INTO orders VALUES ('ord_1', 100000, '2026-09-01T10:00:00', 'cust_1'), ('ord_2', 50000, '2026-09-01T10:00:00', 'cust_2');
        INSERT INTO payments VALUES ('pay_1', 'ord_1', 100000, '2026-09-01T10:00:00', 'UPI'), ('pay_2', 'ord_2', 50000, '2026-09-01T10:00:00', 'NACH');
        INSERT INTO refunds VALUES ('ref_1', 'pay_1', 20000, '2026-09-02T10:00:00', 'pending');
    """)

    report = compute_pending_exposure(conn, settled_payment_ids=set())
    conn.close()

    assert report["total_pending_outflows_paise"] == 20000
    assert report["net_projected_cash_position_paise"] == 126640


def test_settled_payments_excluded():
    """
    Verify that already-settled payments (e.g. pay_1 in settled_payment_ids)
    are strictly excluded from the forward pending exposure view.
    """
    conn = sqlite3.connect(':memory:')
    conn.executescript("""
        CREATE TABLE orders (id TEXT PRIMARY KEY, amount INTEGER, created_at TEXT, customer_ref TEXT);
        CREATE TABLE payments (id TEXT PRIMARY KEY, order_id TEXT, amount INTEGER, captured_at TEXT, method TEXT);
        CREATE TABLE refunds (id TEXT PRIMARY KEY, payment_id TEXT, amount INTEGER, created_at TEXT, status TEXT);
        CREATE TABLE settlement_items (id TEXT PRIMARY KEY, settlement_id TEXT, payment_id TEXT, contribution_amount INTEGER);

        INSERT INTO orders VALUES ('ord_1', 100000, '2026-09-01T10:00:00', 'cust_1'), ('ord_2', 50000, '2026-09-01T10:00:00', 'cust_2');
        INSERT INTO payments VALUES ('pay_1', 'ord_1', 100000, '2026-09-01T10:00:00', 'UPI'), ('pay_2', 'ord_2', 50000, '2026-09-01T10:00:00', 'NACH');
    """)

    report = compute_pending_exposure(conn, settled_payment_ids={'pay_1'})
    conn.close()

    assert len(report["pending_inflow_items"]) == 1
    assert report["pending_inflow_items"][0]["payment_id"] == "pay_2"
    assert report["total_pending_inflows_gross_paise"] == 50000
    assert report["total_expected_inflows_net_paise"] == 50000


def test_method_breakdown():
    """Verify that expected net inflows are accurately broken down by method."""
    conn = sqlite3.connect(':memory:')
    conn.executescript("""
        CREATE TABLE orders (id TEXT PRIMARY KEY, amount INTEGER, created_at TEXT, customer_ref TEXT);
        CREATE TABLE payments (id TEXT PRIMARY KEY, order_id TEXT, amount INTEGER, captured_at TEXT, method TEXT);
        CREATE TABLE refunds (id TEXT PRIMARY KEY, payment_id TEXT, amount INTEGER, created_at TEXT, status TEXT);
        CREATE TABLE settlement_items (id TEXT PRIMARY KEY, settlement_id TEXT, payment_id TEXT, contribution_amount INTEGER);

        INSERT INTO orders VALUES ('ord_1', 100000, '2026-09-01T10:00:00', 'cust_1'), ('ord_2', 50000, '2026-09-01T10:00:00', 'cust_2');
        INSERT INTO payments VALUES ('pay_1', 'ord_1', 100000, '2026-09-01T10:00:00', 'UPI'), ('pay_2', 'ord_2', 50000, '2026-09-01T10:00:00', 'NACH');
    """)

    report = compute_pending_exposure(conn, settled_payment_ids=set())
    conn.close()

    assert report["inflows_by_method"]["UPI"] == 96640
    assert report["inflows_by_method"]["NACH"] == 50000


def test_integer_paise_no_float_drift():
    """Verify that all monetary values in the forecast report are pure integers with no float drift."""
    conn = sqlite3.connect('finance.db')
    report = compute_pending_exposure(conn)
    conn.close()

    assert isinstance(report["total_pending_inflows_gross_paise"], int)
    assert isinstance(report["total_estimated_deductions_paise"], int)
    assert isinstance(report["total_expected_inflows_net_paise"], int)
    assert isinstance(report["total_pending_outflows_paise"], int)
    assert isinstance(report["net_projected_cash_position_paise"], int)

    for item in report["pending_inflow_items"]:
        assert isinstance(item["gross_amount_paise"], int)
        assert isinstance(item["estimated_net_inflow_paise"], int)
        assert isinstance(item["estimated_mdr_paise"], int)
        assert isinstance(item["estimated_gst_paise"], int)
        assert isinstance(item["estimated_tds_paise"], int)


def test_daily_schedule_t_plus_offset():
    """Verify that UPI settles at T+1 and NACH settles at T+3."""
    conn = sqlite3.connect(':memory:')
    conn.executescript("""
        CREATE TABLE orders (id TEXT PRIMARY KEY, amount INTEGER, created_at TEXT, customer_ref TEXT);
        CREATE TABLE payments (id TEXT PRIMARY KEY, order_id TEXT, amount INTEGER, captured_at TEXT, method TEXT);
        CREATE TABLE refunds (id TEXT PRIMARY KEY, payment_id TEXT, amount INTEGER, created_at TEXT, status TEXT);
        CREATE TABLE settlement_items (id TEXT PRIMARY KEY, settlement_id TEXT, payment_id TEXT, contribution_amount INTEGER);

        INSERT INTO orders VALUES ('ord_1', 100000, '2026-09-01T10:00:00', 'cust_1'), ('ord_2', 50000, '2026-09-01T10:00:00', 'cust_2');
        INSERT INTO payments VALUES ('pay_1', 'ord_1', 100000, '2026-09-01T10:00:00', 'UPI'), ('pay_2', 'ord_2', 50000, '2026-09-01T10:00:00', 'NACH');
    """)

    report = compute_pending_exposure(conn, settled_payment_ids=set())
    conn.close()

    items = {item["payment_id"]: item for item in report["pending_inflow_items"]}
    assert items["pay_1"]["expected_settlement_date"] == "2026-09-02"  # T+1
    assert items["pay_2"]["expected_settlement_date"] == "2026-09-04"  # T+3
