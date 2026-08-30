"""
forensic_layer/benford.py

Benford's Law (First-Digit Phenomenon) Statistical Forensic Analyzer.
Evaluates transaction amount distributions against theoretical logarithmic frequencies,
calculating Pearson Chi-Square (chi^2) and per-digit Z-scores.
"""

import math
from dataclasses import dataclass, asdict
from typing import List, Dict, Any


BENFORD_EXPECTED_PROBABILITIES = {
    1: math.log10(1 + 1 / 1),  # 0.3010 (30.1%)
    2: math.log10(1 + 1 / 2),  # 0.1761 (17.6%)
    3: math.log10(1 + 1 / 3),  # 0.1249 (12.5%)
    4: math.log10(1 + 1 / 4),  # 0.0969 (9.7%)
    5: math.log10(1 + 1 / 5),  # 0.0792 (7.9%)
    6: math.log10(1 + 1 / 6),  # 0.0669 (6.7%)
    7: math.log10(1 + 1 / 7),  # 0.0580 (5.8%)
    8: math.log10(1 + 1 / 8),  # 0.0512 (5.1%)
    9: math.log10(1 + 1 / 9),  # 0.0458 (4.6%)
}

# Chi-Square critical value for df = 8 at alpha = 0.05
CHI_SQUARE_CRITICAL_05 = 15.51
CHI_SQUARE_CRITICAL_01 = 20.09


@dataclass
class DigitStat:
    digit: int
    observed_count: int
    observed_pct: float
    expected_pct: float
    expected_count: float
    chi_square_contribution: float
    z_score: float


@dataclass
class BenfordPoolAnalysis:
    pool_name: str
    sample_size_n: int
    chi_square_statistic: float
    critical_value_05: float
    is_statistically_conforming: bool
    conformity_classification: str
    digit_statistics: List[DigitStat]
    methodological_note: str


def extract_first_digits(amounts_paise: List[int]) -> List[int]:
    """Extracts leading significant digit (1-9) from integer paise amounts, ignoring non-positive values."""
    digits = []
    for a in amounts_paise:
        if a is not None and a > 0:
            s = str(abs(a)).lstrip("0")
            if s and s[0].isdigit() and s[0] != "0":
                digits.append(int(s[0]))
    return digits


def analyze_benford_distribution(amounts_paise: List[int], pool_name: str) -> BenfordPoolAnalysis:
    """
    Computes Pearson Chi-Square and per-digit Z-scores for first-digit frequency.
    """
    digits = extract_first_digits(amounts_paise)
    n = len(digits)

    if n == 0:
        return BenfordPoolAnalysis(
            pool_name=pool_name,
            sample_size_n=0,
            chi_square_statistic=0.0,
            critical_value_05=CHI_SQUARE_CRITICAL_05,
            is_statistically_conforming=True,
            conformity_classification="INSUFFICIENT_DATA",
            digit_statistics=[],
            methodological_note="Empty dataset."
        )

    freqs = {d: digits.count(d) for d in range(1, 10)}
    total_chi_square = 0.0
    stats = []

    for d in range(1, 10):
        obs_count = freqs[d]
        obs_pct = (obs_count / n) * 100.0
        exp_prob = BENFORD_EXPECTED_PROBABILITIES[d]
        exp_pct = exp_prob * 100.0
        exp_count = exp_prob * n

        chi_contrib = ((obs_count - exp_count) ** 2) / exp_count if exp_count > 0 else 0.0
        total_chi_square += chi_contrib

        # Nigrini Z-statistic with continuity correction: (|p - P| - 1/(2N)) / sqrt(P(1-P)/N)
        obs_prob = obs_count / n
        denom = math.sqrt((exp_prob * (1 - exp_prob)) / n)
        z = (abs(obs_prob - exp_prob) - (1 / (2 * n))) / denom if denom > 0 else 0.0
        z = max(0.0, z)

        stats.append(DigitStat(
            digit=d,
            observed_count=obs_count,
            observed_pct=round(obs_pct, 2),
            expected_pct=round(exp_pct, 2),
            expected_count=round(exp_count, 2),
            chi_square_contribution=round(chi_contrib, 2),
            z_score=round(z, 2)
        ))

    total_chi_square = round(total_chi_square, 2)
    is_conforming = total_chi_square <= CHI_SQUARE_CRITICAL_05

    if total_chi_square <= 10.0:
        classification = "CLOSE_CONFORMITY"
    elif total_chi_square <= CHI_SQUARE_CRITICAL_05:
        classification = "ACCEPTABLE_CONFORMITY"
    elif total_chi_square <= CHI_SQUARE_CRITICAL_01:
        classification = "MARGINAL_NON_CONFORMITY"
    else:
        classification = "SIGNIFICANT_NON_CONFORMITY"

    if n < 300:
        note = (
            f"Sample size (N={n}) is below empirical surveillance threshold (N >= 1,000). "
            f"Non-conformity is expected for bounded uniform synthetic test data (Rs.100 - Rs.5,000)."
        )
    else:

        note = "Sample size sufficient for population distribution analysis."

    return BenfordPoolAnalysis(
        pool_name=pool_name,
        sample_size_n=n,
        chi_square_statistic=total_chi_square,
        critical_value_05=CHI_SQUARE_CRITICAL_05,
        is_statistically_conforming=is_conforming,
        conformity_classification=classification,
        digit_statistics=stats,
        methodological_note=note
    )
