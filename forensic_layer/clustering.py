"""
forensic_layer/clustering.py

Tolerance Boundary Clustering Forensic Detector.
Evaluates the distribution of epsilon usage (epsilon_pct_used) across matched transactions
to detect engineered deductions designed to crowd the boundary threshold.
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

CLIFF_EDGE_HEURISTIC_THRESHOLD_PCT = 25.0  # Heuristic threshold: >25% of matches in top bin is flagged


@dataclass
class EpsilonBin:
    bin_range: str
    min_pct: float
    max_pct: float
    count: int
    percentage: float
    description: str


@dataclass
class ToleranceClusteringAnalysis:
    total_matched_records: int
    mean_epsilon_pct: float
    max_epsilon_pct: float
    cliff_edge_count: int
    cliff_edge_ratio_pct: float
    heuristic_threshold_pct: float
    is_boundary_engineered_anomaly: bool
    bins: List[EpsilonBin]
    forensic_interpretation: str
    methodological_disclaimer: str


def analyze_tolerance_clustering(epsilon_values: List[float]) -> ToleranceClusteringAnalysis:
    """
    Analyzes epsilon_pct_used values from the matching solver.
    """
    clean_values = [v for v in epsilon_values if v is not None and v >= 0.0]
    total = len(clean_values)

    if total == 0:
        return ToleranceClusteringAnalysis(
            total_matched_records=0,
            mean_epsilon_pct=0.0,
            max_epsilon_pct=0.0,
            cliff_edge_count=0,
            cliff_edge_ratio_pct=0.0,
            heuristic_threshold_pct=CLIFF_EDGE_HEURISTIC_THRESHOLD_PCT,
            is_boundary_engineered_anomaly=False,
            bins=[],
            forensic_interpretation="No matched transactions available for clustering analysis.",
            methodological_disclaimer="Heuristic screening threshold (25% cliff-edge cutoff), not a parametric hypothesis test."
        )

    bin_defs = [
        ("[0% - 20%]", 0.0, 20.0, "Natural tight fit / exact matches"),
        ("[20% - 40%]", 20.0, 40.0, "Low variance within standard statutory deductions"),
        ("[40% - 60%]", 40.0, 60.0, "Moderate variance / typical compound fees"),
        ("[60% - 80%]", 60.0, 80.0, "High variance / elevated deduction headroom"),
        ("[80% - 100%]", 80.0, 100.0, "Boundary cliff-edge / near rejection threshold"),
    ]

    bin_counts = [0, 0, 0, 0, 0]

    for val in clean_values:
        if val <= 20.0:
            bin_counts[0] += 1
        elif val <= 40.0:
            bin_counts[1] += 1
        elif val <= 60.0:
            bin_counts[2] += 1
        elif val <= 80.0:
            bin_counts[3] += 1
        else:
            bin_counts[4] += 1

    bins = []
    for i, (label, min_p, max_p, desc) in enumerate(bin_defs):
        c = bin_counts[i]
        pct = (c / total) * 100.0
        bins.append(EpsilonBin(
            bin_range=label,
            min_pct=min_p,
            max_pct=max_p,
            count=c,
            percentage=round(pct, 2),
            description=desc
        ))

    cliff_count = bin_counts[4]
    cliff_ratio = (cliff_count / total) * 100.0
    mean_eps = sum(clean_values) / total
    max_eps = max(clean_values)

    is_anomaly = cliff_ratio >= CLIFF_EDGE_HEURISTIC_THRESHOLD_PCT

    if is_anomaly:
        interpretation = (
            f"SUSPICIOUS CLIFF-EDGE CLUSTERING FLAGGED: {cliff_ratio:.1f}% of matched transactions "
            f"fall in the 80%-100% tolerance boundary bin (exceeding heuristic threshold of {CLIFF_EDGE_HEURISTIC_THRESHOLD_PCT}%). "
            f"Indicates potential systematic fee sculpting to bypass clearance checks."
        )
    else:
        interpretation = (
            f"NORMAL TOLERANCE DISTRIBUTION: {bins[0].percentage:.1f}% of transactions reside in the 0%-20% tight-fit bin. "
            f"Zero suspicious crowding observed at the 80%-100% boundary cliff edge ({cliff_ratio:.1f}%)."
        )

    return ToleranceClusteringAnalysis(
        total_matched_records=total,
        mean_epsilon_pct=round(mean_eps, 2),
        max_epsilon_pct=round(max_eps, 2),
        cliff_edge_count=cliff_count,
        cliff_edge_ratio_pct=round(cliff_ratio, 2),
        heuristic_threshold_pct=CLIFF_EDGE_HEURISTIC_THRESHOLD_PCT,
        is_boundary_engineered_anomaly=is_anomaly,
        bins=bins,
        forensic_interpretation=interpretation,
        methodological_disclaimer="Heuristic screening threshold (25% cliff-edge cutoff), not a parametric hypothesis test."
    )
