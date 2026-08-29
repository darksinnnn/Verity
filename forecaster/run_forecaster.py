"""
forecaster/run_forecaster.py

CLI entry point for Phase 6 Forward Cash Forecaster.
Queries unsettled payments and pending refunds from finance.db,
computes deterministic pending exposure, and outputs forecast_report.json.
"""

import argparse
import json
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from forecaster.forecaster import compute_pending_exposure


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', type=str, default='finance.db', help='SQLite DB path')
    parser.add_argument('--matching-results', type=str, default='matching_results.json', help='Matching results JSON')
    parser.add_argument('--output', type=str, default='forecast_report.json', help='Output JSON path')
    args = parser.parse_args()

    settled_pids = set()
    if os.path.exists(args.matching_results):
        with open(args.matching_results) as f:
            mr = json.load(f)
        for r in mr.get("real_results", []):
            if r.get("status") == "MATCHED":
                settled_pids.update(r.get("matched_payment_ids", []))

    conn = sqlite3.connect(args.db)
    report = compute_pending_exposure(conn, settled_payment_ids=settled_pids)
    conn.close()

    total_gross = report["total_pending_inflows_gross_paise"] / 100.0
    total_deductions = report["total_estimated_deductions_paise"] / 100.0
    total_net_inflow = report["total_expected_inflows_net_paise"] / 100.0
    total_outflows = report["total_pending_outflows_paise"] / 100.0
    net_position = report["net_projected_cash_position_paise"] / 100.0

    print("\n" + "="*85)
    print("FORWARD CASH FORECASTER — DETERMINISTIC PENDING EXPOSURE VIEW")
    print("="*85)
    print(f"Total Pending Captured Inflows (Gross)  : Rs.{total_gross:>12,.2f}  ({report['total_pending_inflows_gross_paise']} paise)")
    print(f"Less: Estimated Deductions (MDR/GST/TDS): Rs.{total_deductions:>12,.2f}  ({report['total_estimated_deductions_paise']} paise)")
    print(f"Expected Net Settlements Inflow         : Rs.{total_net_inflow:>12,.2f}  ({report['total_expected_inflows_net_paise']} paise)")
    print(f"Less: Pending Refund Obligations        : Rs.{total_outflows:>12,.2f}  ({report['total_pending_outflows_paise']} paise)")
    print("-"*85)
    print(f"NET PROJECTED CASH POSITION             : Rs.{net_position:>12,.2f}  ({report['net_projected_cash_position_paise']} paise)")
    print("="*85)

    if report["daily_projections"]:
        print("\nDAILY SETTLEMENT SCHEDULE:")
        print(f"{'Date':<12} {'Gross Inflows':<16} {'Estimated Fees':<16} {'Net Inflows':<16} {'Outflows':<12} {'Net Position'}")
        print("-"*85)
        for dp in report["daily_projections"]:
            g_str = f"Rs.{dp['gross_inflows_paise']/100:,.2f}"
            f_str = f"Rs.{dp['estimated_fees_paise']/100:,.2f}"
            n_str = f"Rs.{dp['net_inflows_paise']/100:,.2f}"
            o_str = f"Rs.{dp['pending_outflows_paise']/100:,.2f}"
            np_str = f"Rs.{dp['net_projected_cash_paise']/100:,.2f}"
            print(f"{dp['date']:<12} {g_str:<16} {f_str:<16} {n_str:<16} {o_str:<12} {np_str}")
        print("="*85)

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Forecast report saved to {args.output}")


if __name__ == '__main__':
    main()
