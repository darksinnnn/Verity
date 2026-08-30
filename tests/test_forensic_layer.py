"""
tests/test_forensic_layer.py

Pytest suite for Phase 12 Statistical Forensic Layer.
Verifies Benford's Law calculations, tolerance boundary clustering detection,
dual caveat assertions, and read-only database isolation.
"""

import pytest
import sqlite3
import math
import os
import json

from forensic_layer.benford import (
    extract_first_digits,
    analyze_benford_distribution,
    BENFORD_EXPECTED_PROBABILITIES,
    CHI_SQUARE_CRITICAL_05,
)
from forensic_layer.clustering import (
    analyze_tolerance_clustering,
    CLIFF_EDGE_HEURISTIC_THRESHOLD_PCT,
)
from forensic_layer.analyzer import compute_statistical_forensics
from forensic_layer.run_forensics import run_forensics


def test_benford_digit_extraction():
    amounts = [100000, 25050, 399999, 41234, 500000, 999999, 0, -100]
    digits = extract_first_digits(amounts)
    assert digits == [1, 2, 3, 4, 5, 9]



def test_benford_synthetic_logarithmic_conformance():
    """Generates an ideal logarithmic sample to verify chi-square acceptance."""
    sample = []
    # Create 1000 numbers weighted precisely by Benford probabilities
    for d, prob in BENFORD_EXPECTED_PROBABILITIES.items():
        count = int(prob * 1000)
        sample.extend([d * 10000 + i for i in range(count)])

    analysis = analyze_benford_distribution(sample, "Ideal Logarithmic Dataset")
    assert analysis.is_statistically_conforming is True
    assert analysis.chi_square_statistic < CHI_SQUARE_CRITICAL_05
    assert analysis.conformity_classification in ["CLOSE_CONFORMITY", "ACCEPTABLE_CONFORMITY"]


def test_benford_uniform_synthetic_non_conformance():
    """Generates a flat uniform distribution (100k-500k) to verify non-conformance detection."""
    # Bounded uniform data has excess 1, 2, 3, 4
    sample = []
    for d in range(1, 5):
        sample.extend([d * 10000 + i for i in range(250)])

    analysis = analyze_benford_distribution(sample, "Bounded Uniform Sample")
    assert analysis.is_statistically_conforming is False
    assert analysis.chi_square_statistic > CHI_SQUARE_CRITICAL_05


def test_tolerance_clustering_normal_distribution():
    """All matches sitting at 0% epsilon (exact matches) must flag no cliff-edge anomaly."""
    epsilon_values = [0.0] * 49
    analysis = analyze_tolerance_clustering(epsilon_values)

    assert analysis.total_matched_records == 49
    assert analysis.cliff_edge_count == 0
    assert analysis.cliff_edge_ratio_pct == 0.0
    assert analysis.is_boundary_engineered_anomaly is False
    assert analysis.bins[0].count == 49
    assert analysis.bins[4].count == 0


def test_tolerance_clustering_engineered_cliff_edge_anomaly():
    """Injected anomalous cluster (>25% at 95% boundary) must trigger anomaly flag."""
    # 20 matches at 95% (cliff edge) and 30 matches at 10%
    epsilon_values = ([95.0] * 20) + ([10.0] * 30)
    analysis = analyze_tolerance_clustering(epsilon_values)

    assert analysis.total_matched_records == 50
    assert analysis.cliff_edge_count == 20
    assert analysis.cliff_edge_ratio_pct == 40.0  # 40% > 25% threshold
    assert analysis.is_boundary_engineered_anomaly is True


def test_forensics_analyzer_integration_and_caveats():
    """Tests the full read-only analyzer over an isolated in-memory database."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root_dir, "schema.sql"), "r") as f:
        conn.executescript(f.read())

    # Seed sample payments and bank credits
    conn.execute("INSERT INTO orders VALUES ('o1', 100000, '2026-08-01', 'c1')")
    conn.execute("INSERT INTO payments VALUES ('p1', 'o1', 100000, '2026-08-01', 'UPI')")
    conn.execute("INSERT INTO bank_credits VALUES ('b1', 'NEFT-1', 96640, '2026-08-02', 'UTR1')")
    conn.commit()

    report = compute_statistical_forensics(conn)
    conn.close()

    assert "benford_analysis" in report
    assert "payments_pool" in report["benford_analysis"]
    assert "credits_pool" in report["benford_analysis"]
    assert "combined_pool" in report["benford_analysis"]
    assert "tolerance_clustering" in report

    # Verify both caveats are present
    assert "caveats" in report
    assert "synthetic_sample_size_caveat" in report["caveats"]
    assert "adversarial_gaming_caveat" in report["caveats"]


def test_forensics_cli_runner_and_json_export(tmp_path):
    output_file = tmp_path / "test_forensics_report.json"
    report = run_forensics(db_path="finance.db", output_json_path=str(output_file))

    assert os.path.exists(output_file)
    with open(output_file, "r") as f:
        data = json.load(f)

    assert "benford_analysis" in data
    assert data["benford_analysis"]["payments_pool"]["sample_size_n"] == 58
    assert data["benford_analysis"]["credits_pool"]["sample_size_n"] == 54
    assert data["tolerance_clustering"]["total_matched_records"] == 49
