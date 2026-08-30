"""
forensic_layer/run_forensics.py

CLI Runner for Phase 12 Statistical Forensic Layer.
Executes read-only Benford's Law and Tolerance Clustering checks over finance.db,
prints forensic distribution tables, and exports statistical_forensics_report.json.
"""

import sqlite3
import json
import os

from forensic_layer.analyzer import compute_statistical_forensics


def run_forensics(db_path: str = "finance.db", output_json_path: str = "statistical_forensics_report.json") -> dict:
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_db_path = os.path.join(root_dir, db_path) if not os.path.isabs(db_path) else db_path

    conn = sqlite3.connect(f"file:{full_db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    print("\n" + "=" * 80)
    print("VERITY // STATISTICAL FORENSIC SCREENING LAYER (PHASE 12)")
    print("Execution Mode: Strictly Read-Only Analytics over finance.db")
    print("Statistical Models: Pearson Chi-Square Goodness-of-Fit + Tolerance Epsilon Clustering")
    print("=" * 80 + "\n")

    report = compute_statistical_forensics(conn)
    conn.close()

    # 1. Print Caveats
    print("FORENSIC SCREENING CAVEATS & METHODOLOGICAL DISCLAIMERS:")
    print("-" * 80)
    print(f"[*] CAVEAT 1: {report['caveats']['synthetic_sample_size_caveat']}\n")
    print(f"[*] CAVEAT 2: {report['caveats']['adversarial_gaming_caveat']}\n")
    print("-" * 80 + "\n")

    # 2. Print Benford Tables for each pool
    for pool_key, pool_data in report["benford_analysis"].items():
        print(f"BENFORD 1ST-DIGIT DISTRIBUTION: {pool_data['pool_name'].upper()} (N = {pool_data['sample_size_n']})")
        print(f"Chi-Square Statistic: chi^2 = {pool_data['chi_square_statistic']} (Critical chi^2_0.05 = {pool_data['critical_value_05']})")
        print(f"Status: {pool_data['conformity_classification']}")
        print(f"{'Digit':<6} | {'Observed':<10} | {'Observed %':<12} | {'Benford %':<12} | {'chi^2 Contrib':<16} | {'Z-Score'}")
        print("-" * 75)
        for stat in pool_data["digit_statistics"]:
            print(f"{stat['digit']:<6} | {stat['observed_count']:<10} | {stat['observed_pct']:>9.1f}% | {stat['expected_pct']:>9.1f}% | {stat['chi_square_contribution']:>15.2f} | {stat['z_score']:>6.2f}")
        print("-" * 75)
        print(f"Note: {pool_data['methodological_note']}\n")


    # 3. Print Tolerance Boundary Clustering Histogram
    tc = report["tolerance_clustering"]
    print("TOLERANCE BOUNDARY CLUSTERING ANALYSIS (GAMING SURVEILLANCE):")
    print(f"Total Matched Records: {tc['total_matched_records']} | Mean Epsilon: {tc['mean_epsilon_pct']}% | Cliff-Edge Count: {tc['cliff_edge_count']} ({tc['cliff_edge_ratio_pct']}%)")
    print(f"{'Epsilon Range':<16} | {'Count':<8} | {'Percentage':<12} | {'Classification'}")
    print("-" * 75)
    for b in tc["bins"]:
        print(f"{b['bin_range']:<16} | {b['count']:<8} | {b['percentage']:>9.1f}% | {b['description']}")
    print("-" * 75)
    print(f"Forensic Verdict: {tc['forensic_interpretation']}\n" + "=" * 80 + "\n")

    full_output_path = os.path.join(root_dir, output_json_path) if not os.path.isabs(output_json_path) else output_json_path
    with open(full_output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Exported statistical forensics report to: {output_json_path}\n")
    return report


if __name__ == "__main__":
    run_forensics()
