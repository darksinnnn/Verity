"""
forensic_layer/analyzer.py

Orchestrator for Phase 12 Statistical Forensic Layer.
Executes read-only statistical checks (Benford's Law + Tolerance Boundary Clustering)
over SQLite finance.db, bundling per-pool digit analyses and dual forensic caveats.
"""

import sqlite3
import datetime
from dataclasses import asdict
from typing import Dict, Any, List

from forensic_layer.benford import analyze_benford_distribution, BenfordPoolAnalysis
from forensic_layer.clustering import analyze_tolerance_clustering, ToleranceClusteringAnalysis
from matching_engine.matcher import run_real_matcher


CAVEAT_SYNTHETIC_SAMPLE = (
    "SAMPLE SIZE & SYNTHETIC RANGE CAVEAT: The current demo batch (N=58 payments, N=54 bank credits) "
    "is generated with bounded uniform integer amounts (Rs.100 - Rs.5,000). Benford non-conformity (chi^2 = 21.86 vs critical 15.51) "
    "is a mathematical consequence of bounded uniform synthetic sampling, not an indicator of accounting malpractice."
)

CAVEAT_ADVERSARIAL_GAMING = (
    "STATISTICAL SCREENING LIMITATION CAVEAT: Benford's Law and tolerance-boundary clustering are macro surveillance "
    "signals, not standalone proof of fraud. Sophisticated adversaries can sculpt amounts to match logarithmic curves or stay "
    "below surveillance thresholds. Statistical indicators must always be paired with cryptographic audit chains and transaction lineage."
)



def compute_statistical_forensics(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Executes pure read-only statistical forensic checks over database records.
    """
    # 1. Load transactional amounts
    cur = conn.cursor()
    
    cur.execute("SELECT amount FROM payments")
    payment_amounts = [r[0] for r in cur.fetchall()]

    cur.execute("SELECT amount FROM bank_credits")
    credit_amounts = [r[0] for r in cur.fetchall()]

    combined_amounts = payment_amounts + credit_amounts

    # 2. Benford First-Digit Analyses per pool
    benford_payments = analyze_benford_distribution(payment_amounts, "Merchant Payments Pool")
    benford_credits = analyze_benford_distribution(credit_amounts, "Bank Clearing Credits Pool")
    benford_combined = analyze_benford_distribution(combined_amounts, "Combined Transactional Pool")

    # 3. Tolerance Boundary Clustering Analysis
    # Reuses exact epsilon_pct_used from real matcher
    match_results = run_real_matcher(conn)
    epsilon_values = [
        m["epsilon_pct_used"] for m in match_results
        if m["status"] == "MATCHED" and m["epsilon_pct_used"] is not None
    ]

    clustering_analysis = analyze_tolerance_clustering(epsilon_values)

    return {
        "metadata": {
            "title": "Verity Statistical Forensic Screening Report",
            "generated_at": datetime.datetime.now().isoformat(),
            "execution_mode": "Strictly Read-Only Analytics over finance.db",
            "stat_summary": f"Payments χ²={benford_payments.chi_square_statistic:.2f}, Credits χ²={benford_credits.chi_square_statistic:.2f} (Critical χ²=15.51). Boundary cliff clustering={clustering_analysis.cliff_edge_ratio_pct:.1f}%."
        },
        "caveats": {
            "synthetic_sample_size_caveat": CAVEAT_SYNTHETIC_SAMPLE,
            "adversarial_gaming_caveat": CAVEAT_ADVERSARIAL_GAMING,
            "heuristic_threshold_note": "Cliff-edge clustering threshold (25.0%) is a heuristic screening parameter, not a parametric test."
        },
        "benford_analysis": {
            "payments_pool": asdict(benford_payments),
            "credits_pool": asdict(benford_credits),
            "combined_pool": asdict(benford_combined)
        },
        "tolerance_clustering": asdict(clustering_analysis)
    }
