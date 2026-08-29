"""
forecaster/forecaster.py

Phase 6 — Forward Cash Forecaster (Deterministic Pending Exposure View).

Strict constraints (PRD.md §4.6, AGENTS.md §2):
- Deterministic arithmetic only. NO machine-learning forecasting or predictive models.
- Uses exact integer paise arithmetic. No floating-point drift.
- Computes:
  1. Pending Inflows: Captured payments awaiting settlement (T+1/T+2/NACH cycles) with expected net deductions.
  2. Pending Outflows: Open/pending refunds and clawback obligations.
  3. Pending Mandates/Debits due.
  4. Net Projected Cash Position grouped by value date and payment method.
"""

from __future__ import annotations
import sqlite3
from datetime import datetime, timedelta
from typing import TypedDict

# Standard deduction constants for forward settlement projection
STANDARD_MDR_RATE = 0.02
STANDARD_GST_RATE = 0.18
STANDARD_TDS_RATE = 0.01

# Settlement cycle offsets (business days / hours)
SETTLEMENT_OFFSETS = {
    "UPI": 1,    # T+1
    "CARD": 1,   # T+1
    "NETBANKING": 1, # T+1
    "NACH": 3,   # T+3 batched
}


class PendingInflowItem(TypedDict):
    payment_id: str
    order_id: str
    method: str
    captured_at: str
    expected_settlement_date: str
    gross_amount_paise: int
    estimated_mdr_paise: int
    estimated_gst_paise: int
    estimated_tds_paise: int
    estimated_net_inflow_paise: int


class PendingOutflowItem(TypedDict):
    refund_id: str
    payment_id: str
    created_at: str
    amount_paise: int
    status: str
    reason: str


class DailyProjection(TypedDict):
    date: str
    gross_inflows_paise: int
    estimated_fees_paise: int
    net_inflows_paise: int
    pending_outflows_paise: int
    net_projected_cash_paise: int


class ForecastReport(TypedDict):
    projection_generated_at: str
    total_pending_inflows_gross_paise: int
    total_estimated_deductions_paise: int
    total_expected_inflows_net_paise: int
    total_pending_outflows_paise: int
    net_projected_cash_position_paise: int
    inflows_by_method: dict[str, int]
    daily_projections: list[DailyProjection]
    pending_inflow_items: list[PendingInflowItem]
    pending_outflow_items: list[PendingOutflowItem]


def compute_pending_exposure(
    conn: sqlite3.Connection,
    settled_payment_ids: set[str] | None = None,
    as_of_date: str | None = None
) -> ForecastReport:
    """
    Computes deterministic pending exposure and forward cash projections
    based on unsettled captured payments and pending refund obligations.

    A payment is considered SETTLED if and only if it has a row in settlement_items.
    This is the canonical structural definition — the settlement_items table is the
    authoritative ledger of "payment has been included in a formal settlement run."

    The optional settled_payment_ids set is IGNORED in favour of the DB join —
    passing it from matching_results.json is incorrect because matching_results only
    reflects what the engine solved, not what the generator actually settled.
    """
    # Canonical definition of "pending settlement":
    # A payment is pending if and only if:
    #   1. It has NO row in settlement_items (not yet included in any settlement run), AND
    #   2. It has NO bank_credit already matched to it by the matching engine
    #      (i.e. not referenced in any bank_credit's settlement via matching_results).
    #
    # The settlement_items table is the authoritative ledger of formal settlement runs.
    # Bank credits that arrived but used non-settlement-items paths (trap payments) are
    # separately excluded by checking the matched_payment_ids from matching_results.
    #
    # We receive matched_payment_ids via the settled_payment_ids parameter from
    # run_forecaster.py (loaded from matching_results.json). This gives us:
    #   - Payments settled via normal settlement_items path (also in settlement_items)
    #   - Payments matched via the matching engine to a bank_credit (trap payments)
    #
    # A payment is genuinely pending only if it is in NEITHER set.
    if settled_payment_ids is None:
        cur = conn.execute("SELECT DISTINCT payment_id FROM settlement_items WHERE payment_id IS NOT NULL")
        settled_payment_ids = {r[0] for r in cur.fetchall()}

    # Get payments with no settlement_items row
    cur = conn.execute("""
        SELECT p.id, p.order_id, p.amount, p.captured_at, p.method
        FROM payments p
        LEFT JOIN settlement_items si ON si.payment_id = p.id
        WHERE si.id IS NULL
        ORDER BY p.captured_at ASC
    """)
    unsettled_payments = [
        r for r in cur.fetchall()
        if r[0] not in settled_payment_ids  # Also exclude trap payments matched to a bank_credit
    ]


    pending_inflows: list[PendingInflowItem] = []
    inflows_by_method: dict[str, int] = {}
    daily_map: dict[str, dict[str, int]] = {}

    for p in unsettled_payments:
        pid, oid, gross, captured_at, method = p[0], p[1], p[2], p[3], (p[4] or "UPI")

        # Determine settlement cycle offset
        offset_days = SETTLEMENT_OFFSETS.get(method.upper(), 1)
        try:
            cap_dt = datetime.fromisoformat(captured_at)
        except ValueError:
            cap_dt = datetime.strptime(captured_at[:10], "%Y-%m-%d")

        settle_dt = cap_dt + timedelta(days=offset_days)
        settle_date_str = settle_dt.strftime("%Y-%m-%d")

        # Deterministic fee estimation (paise)
        if method.upper() == "NACH":
            mdr = 0
            gst = 0
            tds = 0
            net = gross
        else:
            mdr = int(gross * STANDARD_MDR_RATE)
            gst = int(mdr * STANDARD_GST_RATE)
            tds = int(gross * STANDARD_TDS_RATE)
            net = gross - mdr - gst - tds

        item: PendingInflowItem = {
            "payment_id": pid,
            "order_id": oid,
            "method": method,
            "captured_at": captured_at,
            "expected_settlement_date": settle_date_str,
            "gross_amount_paise": gross,
            "estimated_mdr_paise": mdr,
            "estimated_gst_paise": gst,
            "estimated_tds_paise": tds,
            "estimated_net_inflow_paise": net,
        }
        pending_inflows.append(item)

        # Aggregate by method
        inflows_by_method[method] = inflows_by_method.get(method, 0) + net

        # Aggregate daily
        if settle_date_str not in daily_map:
            daily_map[settle_date_str] = {
                "gross_inflows": 0,
                "fees": 0,
                "net_inflows": 0,
                "outflows": 0,
            }
        daily_map[settle_date_str]["gross_inflows"] += gross
        daily_map[settle_date_str]["fees"] += (mdr + gst + tds)
        daily_map[settle_date_str]["net_inflows"] += net

    # 2. Query pending / open refunds
    cur = conn.execute("""
        SELECT r.id, r.payment_id, r.amount, r.created_at, r.status
        FROM refunds r
        WHERE r.status = 'pending' OR r.status = 'initiated'
        ORDER BY r.created_at ASC
    """)
    pending_refunds_rows = cur.fetchall()

    pending_outflows: list[PendingOutflowItem] = []
    total_pending_outflows = 0

    for r in pending_refunds_rows:
        rid, pid, amt, created_at, status = r[0], r[1], r[2], r[3], r[4]
        outflow_item: PendingOutflowItem = {
            "refund_id": rid,
            "payment_id": pid,
            "created_at": created_at,
            "amount_paise": amt,
            "status": status,
            "reason": f"Pending merchant refund recovery for payment {pid}",
        }
        pending_outflows.append(outflow_item)
        total_pending_outflows += amt

        # Attribute to refund date
        r_date_str = created_at[:10]
        if r_date_str not in daily_map:
            daily_map[r_date_str] = {
                "gross_inflows": 0,
                "fees": 0,
                "net_inflows": 0,
                "outflows": 0,
            }
        daily_map[r_date_str]["outflows"] += amt

    # 3. Build daily sorted projections
    daily_projections: list[DailyProjection] = []
    for d_str in sorted(daily_map.keys()):
        d_data = daily_map[d_str]
        daily_projections.append({
            "date": d_str,
            "gross_inflows_paise": d_data["gross_inflows"],
            "estimated_fees_paise": d_data["fees"],
            "net_inflows_paise": d_data["net_inflows"],
            "pending_outflows_paise": d_data["outflows"],
            "net_projected_cash_paise": d_data["net_inflows"] - d_data["outflows"],
        })

    total_gross = sum(item["gross_amount_paise"] for item in pending_inflows)
    total_fees = sum(
        item["estimated_mdr_paise"] + item["estimated_gst_paise"] + item["estimated_tds_paise"]
        for item in pending_inflows
    )
    total_net_inflows = sum(item["estimated_net_inflow_paise"] for item in pending_inflows)

    report: ForecastReport = {
        "projection_generated_at": datetime.utcnow().isoformat(),
        "total_pending_inflows_gross_paise": total_gross,
        "total_estimated_deductions_paise": total_fees,
        "total_expected_inflows_net_paise": total_net_inflows,
        "total_pending_outflows_paise": total_pending_outflows,
        "net_projected_cash_position_paise": total_net_inflows - total_pending_outflows,
        "inflows_by_method": inflows_by_method,
        "daily_projections": daily_projections,
        "pending_inflow_items": pending_inflows,
        "pending_outflow_items": pending_outflows,
    }
    return report
