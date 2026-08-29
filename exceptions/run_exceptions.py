"""
exceptions/run_exceptions.py

CLI entry point for Phase 5 Exception System.
Loads matching_results.json and delta_explanations.json, builds ranked exceptions,
validates write-time invariants, persists to finance.db, and prints an executive summary.
"""

import argparse
import json
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from exceptions.engine import build_exceptions, save_exceptions_to_db


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', type=str, default='finance.db', help='SQLite DB path')
    parser.add_argument('--matching-results', type=str, default='matching_results.json', help='Matching results JSON')
    parser.add_argument('--delta-explanations', type=str, default='delta_explanations.json', help='Delta explanations JSON')
    parser.add_argument('--batch-id', type=str, default='batch_20260914', help='Batch identifier')
    parser.add_argument('--output', type=str, default='exceptions_report.json', help='Output JSON path')
    args = parser.parse_args()

    with open(args.matching_results) as f:
        mr = json.load(f)

    with open(args.delta_explanations) as f:
        de = json.load(f)

    conn = sqlite3.connect(args.db)
    exceptions = build_exceptions(conn, mr, de, batch_id=args.batch_id)
    save_exceptions_to_db(conn, exceptions)
    conn.close()

    total_risk_paise = sum(e["amount_at_risk"] for e in exceptions)
    total_risk_rupees = total_risk_paise / 100.0

    print("\n" + "="*85)
    print(f"EXCEPTIONS REPORT — RANKED BY AMOUNT-AT-RISK (Total At Risk: Rs.{total_risk_rupees:,.2f})")
    print("="*85)
    print(f"{'Rank':<5} {'Exception ID':<14} {'Record ID':<14} {'Status':<12} {'At Risk (Rs.)':<15} {'Summary'}")
    print("-"*85)

    for i, exc in enumerate(exceptions, 1):
        risk_str = f"Rs.{exc['amount_at_risk']/100:,.2f}"
        summary = exc['explanation_text'][:55] + "..." if len(exc['explanation_text']) > 55 else exc['explanation_text']
        print(f"{i:<5} {exc['id']:<14} {exc['related_record_id']:<14} {exc['status']:<12} {risk_str:<15} {summary}")
        
        hyp_list = json.loads(exc["hypotheses_json"])
        if hyp_list:
            top_h = hyp_list[0]
            print(f"      -> Hypothesis: {top_h.get('hypothesis')}")
            print(f"      -> Missing Evidence: {top_h.get('evidence_needed')}")
        print()

    print("="*85)
    print(f"Total exceptions created and saved to DB: {len(exceptions)}")
    print(f"Exceptions report saved to {args.output}")

    with open(args.output, "w") as f:
        json.dump(exceptions, f, indent=2)


if __name__ == '__main__':
    main()
