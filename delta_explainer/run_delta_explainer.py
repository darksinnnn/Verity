"""
delta_explainer/run_delta_explainer.py

CLI entry point for Phase 4 Delta-Explainer.
Takes unmatched bank credit IDs from matching_results.json, runs delta explanation
search across tax rates, fee tiers, and refunds, and outputs delta_explanations.json.
"""

import argparse
import json
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from delta_explainer.explainer import explain_all_unmatched


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', type=str, default='finance.db', help='SQLite DB path')
    parser.add_argument('--matching-results', type=str, default='matching_results.json', help='Matching results JSON')
    parser.add_argument('--output', type=str, default='delta_explanations.json', help='Output JSON path')
    args = parser.parse_args()

    with open(args.matching_results) as f:
        mr = json.load(f)

    unmatched_ids = mr.get("unmatched_bank_credit_ids", [])
    consumed_pids = set()
    for r in mr.get("real_results", []):
        if r.get("status") == "MATCHED":
            consumed_pids.update(r.get("matched_payment_ids", []))

    print(f"Running Delta-Explainer on {len(unmatched_ids)} unmatched bank credits (excluding {len(consumed_pids)} already-settled payments)...")

    conn = sqlite3.connect(args.db)
    explanations = explain_all_unmatched(conn, unmatched_ids, exclude_consumed_pids=consumed_pids)
    conn.close()

    print("\n" + "="*75)
    print(f"{'Bank Credit ID':<16} {'Status':<12} {'Delta':<12} {'Top Hypothesis / Reason'}")
    print("-"*75)
    for exp in explanations:
        delta_str = f"Rs.{exp['delta_paise']/100:.2f}"
        top_h = exp['hypotheses'][0]['category'] if exp['hypotheses'] else "NO_EXPLANATION"
        print(f"{exp['bank_credit_id']:<16} {exp['status']:<12} {delta_str:<12} {top_h}")
        print(f"  Explanation: {exp['explanation_text'][:80]}...")
        if exp['hypotheses']:
            print(f"  Evidence needed: {exp['hypotheses'][0]['evidence_needed']}")
        print()
    print("="*75)

    with open(args.output, "w") as f:
        json.dump(explanations, f, indent=2)

    print(f"Delta explanations saved to {args.output}")


if __name__ == '__main__':
    main()
