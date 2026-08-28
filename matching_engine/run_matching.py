"""
matching_engine/run_matching.py

CLI entry point. Runs the real matcher and the naive baseline matcher against
the database, scores both against ground_truth.json, and prints the comparison
table — the exact contrast that goes into the demo (PRD.md §6).

Results are saved to matching_results.json for downstream use by
Delta-Explainer (Phase 4) and Exception System (Phase 5).
"""

import argparse
import json
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from matching_engine.matcher import run_real_matcher, run_naive_matcher, score_results
from preprocessing.parser import process_batch_narrations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db',           type=str, default='finance.db',     help='SQLite DB path')
    parser.add_argument('--ground-truth', type=str, default='ground_truth.json', help='Ground truth JSON')
    parser.add_argument('--output',       type=str, default='matching_results.json', help='Output results JSON')
    args = parser.parse_args()

    # Run pre-processing first (idempotent — already-parsed rows are skipped)
    process_batch_narrations(args.db)

    conn = sqlite3.connect(args.db)

    print("Running real matcher (DP subset-sum, 1:1 + N:1 + 1:N, dynamic tolerance)...")
    real_results = run_real_matcher(conn)

    print("Running naive matcher (exact 1:1 only, no tolerance)...")
    naive_results = run_naive_matcher(conn)

    conn.close()

    with open(args.ground_truth) as f:
        ground_truth = json.load(f)

    real_score  = score_results(real_results,  ground_truth)
    naive_score = score_results(naive_results, ground_truth)

    print("\n" + "="*60)
    print("MATCHING RESULTS — REAL SOLVER vs. NAIVE BASELINE")
    print("="*60)
    print(f"{'Metric':<25} {'Real Solver':>15} {'Naive Baseline':>15}")
    print("-"*60)
    for key in ["true_positives", "false_positives", "false_negatives", "precision", "recall", "f1"]:
        print(f"  {key:<23} {real_score[key]:>15} {naive_score[key]:>15}")
    print("="*60)
    print()

    unmatched_ids = [r["bank_credit_id"] for r in real_results if r["status"] == "UNMATCHED"]
    print(f"Unmatched bank credits (passed to Delta-Explainer): {len(unmatched_ids)}")
    for uid in unmatched_ids:
        print(f"  - {uid}")

    # Save full results for downstream phases
    output = {
        "real_results":   real_results,
        "naive_results":  naive_results,
        "real_score":     real_score,
        "naive_score":    naive_score,
        "unmatched_bank_credit_ids": unmatched_ids,
    }
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nFull results saved to {args.output}")


if __name__ == '__main__':
    main()
