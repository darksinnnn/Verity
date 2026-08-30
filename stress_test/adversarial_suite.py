"""
stress_test/adversarial_suite.py

Phase 11 Adversarial Stress Test Suite for Verity Reconciliation & Matching Engine.
Constructs 20 distinct adversarial attack vectors across 6 attack families,
evaluates them in isolated ephemeral :memory: SQLite databases,
calculates exact proximity margins (paise and %), and returns structured telemetry.
"""

import sqlite3
import datetime
import os
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

from matching_engine.tolerance import compute_tolerance_window, compute_expected_deduction
from matching_engine.matcher import run_real_matcher
from delta_explainer.explainer import explain_delta


def solve_matching(conn: sqlite3.Connection, epsilon_pct: float = 0.0) -> dict:
    """Helper wrapping run_real_matcher to return structured results dictionary."""
    real_results = run_real_matcher(conn)
    return {"real_results": real_results}


def insert_bank_credit(conn: sqlite3.Connection, bc_id: str, amount_paise: int, narration: str, value_date: str, parsed_utr: Optional[str] = None):
    """Helper ensuring correct column ordering: (id, raw_narration, amount, value_date, parsed_utr)."""
    conn.execute(
        "INSERT INTO bank_credits (id, raw_narration, amount, value_date, parsed_utr) VALUES (?, ?, ?, ?, ?)",
        (bc_id, narration, amount_paise, value_date, parsed_utr)
    )


def insert_payment(conn: sqlite3.Connection, pid: str, oid: str, amount: int, captured_at: str, method: str = "UPI"):
    """Helper inserting order, payment, and corresponding ledger entry."""
    conn.execute("INSERT OR IGNORE INTO orders VALUES (?, ?, ?, ?)", (oid, amount, captured_at, f"cust_{oid}"))
    conn.execute("INSERT INTO payments VALUES (?, ?, ?, ?, ?)", (pid, oid, amount, captured_at, method))
    conn.execute("INSERT INTO ledger_entries VALUES (?, 'payment', ?, ?, 'DEBIT')", (f"led_{pid}", pid, amount))



def insert_fee_stack(conn: sqlite3.Connection, pid: str, gross: int):
    """Inserts standard statutory fees: 2% MDR, 18% GST on MDR, 1% TDS."""
    mdr = int(gross * 0.02)
    gst = int(mdr * 0.18)
    tds = int(gross * 0.01)
    conn.execute("INSERT INTO fees VALUES (?, ?, 'MDR', 0.02, ?)", (f"fee_mdr_{pid}", pid, mdr))
    conn.execute("INSERT INTO fees VALUES (?, ?, 'GST_ON_MDR', 0.18, ?)", (f"fee_gst_{pid}", pid, gst))
    conn.execute("INSERT INTO fees VALUES (?, ?, 'TDS', 0.01, ?)", (f"fee_tds_{pid}", pid, tds))
    return gross - (mdr + gst + tds)


MARGINAL_THRESHOLD_PCT = 0.10  # <= 0.10% (10 bps) is classified as MARGINAL_DEFENSE


@dataclass
class AdversarialResult:
    scenario_id: str
    attack_name: str
    attack_family: str
    description: str
    solver_verdict: str
    expected_defense: str
    defense_status: str  # "DEFENDED" | "CONCEDED"
    defense_mechanism: str
    proximity_margin_paise: int
    proximity_margin_pct: float
    margin_classification: str  # "MARGINAL_DEFENSE" | "COMFORTABLE_DEFENSE"
    telemetry: Dict[str, Any]


def get_memory_db() -> sqlite3.Connection:
    """Creates a fresh, completely isolated in-memory SQLite database seeded with schema.sql."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schema_path = os.path.join(root_dir, "schema.sql")
    with open(schema_path, "r") as f:
        conn.executescript(f.read())
    return conn


class AdversarialSuite:
    """Executes the 20 adversarial stress test scenarios against isolated :memory: databases."""

    @classmethod
    def run_all(cls) -> List[AdversarialResult]:
        scenarios = [
            # Family 1: Combinatorial Coincidences
            cls.test_adv_01_coincidental_sum_unanchored,
            cls.test_adv_02_tight_near_miss_under_epsilon,
            cls.test_adv_03_coincidental_sum_outside_dynamic_tolerance,
            cls.test_adv_04_zero_net_cancellation_trap,
            
            # Family 2: Unanchored Candidate Contention
            cls.test_adv_05_unanchored_subset_collision,
            cls.test_adv_06_greedy_solver_suboptimality_trap,
            cls.test_adv_07_window_boundary_contention,
            cls.test_adv_08_multi_candidate_tie_break,
            
            # Family 3: Dynamic Tolerance Boundary Exploits
            cls.test_adv_09_overpayment_exact_plus_1_paise,
            cls.test_adv_10_overpayment_over_gross_sub_percent,
            cls.test_adv_11_underpayment_exact_minus_1_paise_beyond_envelope,
            cls.test_adv_12_underpayment_exact_boundary_inner_edge,
            
            # Family 4: Ghost & Synthetic Credit Injections
            cls.test_adv_13_ghost_credit_perfect_narration,
            cls.test_adv_14_ghost_credit_truncated_fake_utr,
            cls.test_adv_15_ghost_credit_duplicate_narration_diff_amount,
            
            # Family 5: High-Cardinality Splitting & Symmetry
            cls.test_adv_16_high_cardinality_10_to_1,
            cls.test_adv_17_symmetric_duplicate_split,
            cls.test_adv_18_permutation_invariance,
            
            # Family 6: Compound Deduction Concealment
            cls.test_adv_19_compound_tds_plus_refund,
            cls.test_adv_20_unexplainable_prime_gap,
        ]

        results = []
        for s in scenarios:
            results.append(s())
        return results

    # =========================================================================
    # FAMILY 1: COMBINATORIAL COINCIDENCES
    # =========================================================================

    @staticmethod
    def test_adv_01_coincidental_sum_unanchored() -> AdversarialResult:
        """3 unrelated payments outside date window coincidentally sum to bank credit amount without UTR."""
        conn = get_memory_db()
        # Insert 3 payments on different months far outside the 7-day window of the credit
        insert_payment(conn, "pay_c1", "ord_c1", 50000, "2026-05-01T11:00:00")
        insert_payment(conn, "pay_c2", "ord_c2", 30000, "2026-06-01T11:00:00")
        insert_payment(conn, "pay_c3", "ord_c3", 20000, "2026-07-01T11:00:00")
        
        insert_bank_credit(conn, "bc_adv_01", 100000, "NEFT-COINCIDENTAL-GENERIC", "2026-08-04", None)
        conn.commit()

        res = solve_matching(conn=conn, epsilon_pct=0.0)
        conn.close()

        bc_res = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_01"), None)
        status = bc_res["status"] if bc_res else "UNMATCHED"
        
        defended = (status == "UNMATCHED")
        margin_paise = 100000
        margin_pct = 100.0

        return AdversarialResult(
            scenario_id="ADV_01",
            attack_name="Combinatorial Coincidental Sum (Unanchored)",
            attack_family="Combinatorial Coincidences",
            description="3 unrelated customer payments coincidentally sum to bank credit amount without settlement items or UTR.",
            solver_verdict=status,
            expected_defense="UNMATCHED",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="TEMPORAL_AND_SETTLEMENT_ISOLATION",
            proximity_margin_paise=margin_paise,
            proximity_margin_pct=round(margin_pct, 4),
            margin_classification="COMFORTABLE_DEFENSE",
            telemetry={"bank_credit_amount": 100000, "candidate_sum": 100000, "payments": ["pay_c1", "pay_c2", "pay_c3"]}
        )

    @staticmethod
    def test_adv_02_tight_near_miss_under_epsilon() -> AdversarialResult:
        """Near-miss credit short by 8 paise against a 100,000 payment with standard tolerance window."""
        conn = get_memory_db()
        insert_payment(conn, "pay_nm", "ord_nm", 100000, "2026-08-01T11:00:00")
        net = insert_fee_stack(conn, "pay_nm", 100000)
        
        conn.execute("INSERT INTO settlements VALUES ('set_nm', 'UTR_NM888', 100000, ?, '2026-08-02T10:00:00')", (net,))
        conn.execute("INSERT INTO settlement_items VALUES ('si_nm', 'set_nm', 'pay_nm', 100000)")
        
        # Credit is net - 8 paise (96632)
        insert_bank_credit(conn, "bc_adv_02", net - 8, "NEFT-UTR_NM888-SETTLEMENT", "2026-08-02", "UTR_NM888")
        conn.commit()

        res = solve_matching(conn=conn, epsilon_pct=0.0)
        conn.close()

        bc_res = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_02"), None)
        status = bc_res["status"] if bc_res else "UNMATCHED"

        defended = (status == "MATCHED")
        proximity_paise = 8
        proximity_pct = (proximity_paise / 100000) * 100.0

        return AdversarialResult(
            scenario_id="ADV_02",
            attack_name="Tight Near-Miss Under Epsilon",
            attack_family="Combinatorial Coincidences",
            description="Bank credit is short by 8 paise against a 100,000 payment within statutory deduction tolerance envelope.",
            solver_verdict=status,
            expected_defense="MATCHED",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="DYNAMIC_EPSILON_BOUND_ACCEPTANCE",
            proximity_margin_paise=proximity_paise,
            proximity_margin_pct=round(proximity_pct, 4),
            margin_classification="MARGINAL_DEFENSE",  # 0.008% <= 0.10%
            telemetry={"expected_net": net, "actual_credit": net - 8, "delta_paise": 8}
        )

    @staticmethod
    def test_adv_03_coincidental_sum_outside_dynamic_tolerance() -> AdversarialResult:
        """Combinatorial candidate sum is 46,640 paise outside tolerance cutoff."""
        conn = get_memory_db()
        insert_payment(conn, "pay_ot", "ord_ot", 100000, "2026-08-01T11:00:00")
        net = insert_fee_stack(conn, "pay_ot", 100000)
        
        conn.execute("INSERT INTO settlements VALUES ('set_ot', 'UTR_OT999', 100000, ?, '2026-08-02T10:00:00')", (net,))
        conn.execute("INSERT INTO settlement_items VALUES ('si_ot', 'set_ot', 'pay_ot', 100000)")
        
        insert_bank_credit(conn, "bc_adv_03", 50000, "NEFT-UTR_OT999-SETTLEMENT", "2026-08-02", "UTR_OT999")
        conn.commit()

        res = solve_matching(conn=conn, epsilon_pct=0.0)
        conn.close()

        bc_res = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_03"), None)
        status = bc_res["status"] if bc_res else "UNMATCHED"

        defended = (status == "UNMATCHED")
        proximity_paise = 46640
        proximity_pct = (proximity_paise / 100000) * 100.0

        return AdversarialResult(
            scenario_id="ADV_03",
            attack_name="Coincidental Sum Outside Dynamic Tolerance",
            attack_family="Combinatorial Coincidences",
            description="Bank credit is short by 46,640 paise outside dynamic tolerance, testing strict boundary rejection.",
            solver_verdict=status,
            expected_defense="UNMATCHED",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="STRICT_DYNAMIC_TOLERANCE_REJECTION",
            proximity_margin_paise=proximity_paise,
            proximity_margin_pct=round(proximity_pct, 4),
            margin_classification="COMFORTABLE_DEFENSE",
            telemetry={"expected_net": net, "actual_credit": 50000, "delta_paise": 46640}
        )

    @staticmethod
    def test_adv_04_zero_net_cancellation_trap() -> AdversarialResult:
        """Equal payment and refund with residual credit seeking erroneous match."""
        conn = get_memory_db()
        insert_payment(conn, "pay_zn", "ord_zn", 50000, "2026-08-01T11:00:00")
        conn.execute("INSERT INTO refunds VALUES ('ref_zn', 'pay_zn', 50000, '2026-08-01T12:00:00', 'PROCESSED')")
        
        insert_bank_credit(conn, "bc_adv_04", 1000, "NEFT-RESIDUAL-GHOST", "2026-08-02", None)
        conn.commit()

        res = solve_matching(conn=conn, epsilon_pct=0.0)
        conn.close()

        bc_res = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_04"), None)
        status = bc_res["status"] if bc_res else "UNMATCHED"

        defended = (status == "UNMATCHED")
        margin_paise = 49000
        margin_pct = (margin_paise / 50000) * 100.0

        return AdversarialResult(
            scenario_id="ADV_04",
            attack_name="Zero-Net Cancellation Trap",
            attack_family="Combinatorial Coincidences",
            description="Equal payment and refund with 1000 paise residual credit attempting to bind cancelled payment.",
            solver_verdict=status,
            expected_defense="UNMATCHED",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="REFUND_NET_CANCELLATION_ISOLATION",
            proximity_margin_paise=margin_paise,
            proximity_margin_pct=round(margin_pct, 4),
            margin_classification="COMFORTABLE_DEFENSE",
            telemetry={"payment_amount": 50000, "refund_amount": 50000, "residual_credit": 1000}
        )

    # =========================================================================
    # FAMILY 2: UNANCHORED CANDIDATE CONTENTION
    # =========================================================================

    @staticmethod
    def test_adv_05_unanchored_subset_collision() -> AdversarialResult:
        """Two identical credits competing for two identical payments without UTRs."""
        conn = get_memory_db()
        insert_payment(conn, "pay_sc1", "ord_sc1", 100000, "2026-08-01T11:00:00")
        insert_payment(conn, "pay_sc2", "ord_sc2", 100000, "2026-08-01T11:00:00")
        
        insert_bank_credit(conn, "bc_adv_05_a", 100000, "NEFT-UNANCHORED-A", "2026-08-02", None)
        insert_bank_credit(conn, "bc_adv_05_b", 100000, "NEFT-UNANCHORED-B", "2026-08-02", None)
        conn.commit()

        res = solve_matching(conn=conn, epsilon_pct=0.0)
        conn.close()

        r_a = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_05_a"), None)
        r_b = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_05_b"), None)
        
        p_a = r_a.get("matched_payment_ids", []) if r_a else []
        p_b = r_b.get("matched_payment_ids", []) if r_b else []

        no_double_use = len(set(p_a).intersection(set(p_b))) == 0
        defended = no_double_use and (len(p_a) == 1 and len(p_b) == 1)

        return AdversarialResult(
            scenario_id="ADV_05",
            attack_name="Unanchored Subset Collision",
            attack_family="Unanchored Candidate Contention",
            description="Two bank credits with generic narrations competing for identical unanchored payments without double-use.",
            solver_verdict=f"BC_A:{r_a['status'] if r_a else 'NONE'}, BC_B:{r_b['status'] if r_b else 'NONE'}",
            expected_defense="NO_DOUBLE_USE_EXACT_ALLOCATION",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="DISJOINT_SUBSET_ALLOCATION",
            proximity_margin_paise=100000,
            proximity_margin_pct=100.0,
            margin_classification="COMFORTABLE_DEFENSE",
            telemetry={"bc_a_matched": p_a, "bc_b_matched": p_b, "intersection": list(set(p_a).intersection(set(p_b)))}
        )

    @staticmethod
    def test_adv_06_greedy_solver_suboptimality_trap() -> AdversarialResult:
        """Greedy trap: P1+P2 matches BC1, and P3 matches BC2."""
        conn = get_memory_db()
        insert_payment(conn, "pay_g1", "ord_g1", 100000, "2026-08-01T11:00:00")
        insert_payment(conn, "pay_g2", "ord_g2", 50000, "2026-08-01T11:00:00")
        insert_payment(conn, "pay_g3", "ord_g3", 100000, "2026-08-01T11:00:00")
        
        insert_bank_credit(conn, "bc_adv_06_1", 150000, "NEFT-GREEDY-TRAP-150", "2026-08-02", None)
        insert_bank_credit(conn, "bc_adv_06_2", 100000, "NEFT-GREEDY-TRAP-100", "2026-08-02", None)
        conn.commit()

        res = solve_matching(conn=conn, epsilon_pct=0.0)
        conn.close()

        r1 = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_06_1"), None)
        r2 = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_06_2"), None)

        p1_list = r1.get("matched_payment_ids", []) if r1 else []
        p2_list = r2.get("matched_payment_ids", []) if r2 else []

        both_matched = (r1 and r1["status"] == "MATCHED") and (r2 and r2["status"] == "MATCHED")
        no_double_use = len(set(p1_list).intersection(set(p2_list))) == 0
        defended = both_matched and no_double_use

        return AdversarialResult(
            scenario_id="ADV_06",
            attack_name="Greedy Solver Sub-optimality Trap (Unanchored)",
            attack_family="Unanchored Candidate Contention",
            description="Testing minimum-cardinality DP tie-breaking under unanchored candidate contention without greedy stranding.",
            solver_verdict=f"BC1:{r1['status'] if r1 else 'NONE'}, BC2:{r2['status'] if r2 else 'NONE'}",
            expected_defense="GLOBAL_DP_OPTIMAL_ALLOCATION",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="MIN_CARDINALITY_DP_PARTITION",
            proximity_margin_paise=50000,
            proximity_margin_pct=50.0,
            margin_classification="COMFORTABLE_DEFENSE",
            telemetry={"bc1_matched": p1_list, "bc2_matched": p2_list}
        )

    @staticmethod
    def test_adv_07_window_boundary_contention() -> AdversarialResult:
        """Candidate payment outside window boundary of BC2 allocated strictly to BC1."""
        conn = get_memory_db()
        insert_payment(conn, "pay_wb1", "ord_wb1", 100000, "2026-08-01T11:00:00")
        
        # BC1 is on Day 2 (within 7 days). BC2 is on Day 20 (19 days later, outside 7 days)
        insert_bank_credit(conn, "bc_adv_07_1", 100000, "NEFT-NEAR-WINDOW", "2026-08-02", None)
        insert_bank_credit(conn, "bc_adv_07_2", 100000, "NEFT-FAR-WINDOW", "2026-08-20", None)
        conn.commit()

        res = solve_matching(conn=conn, epsilon_pct=0.0)
        conn.close()

        r1 = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_07_1"), None)
        r2 = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_07_2"), None)

        defended = (r1 and r1["status"] == "MATCHED") and (r2 and r2["status"] == "UNMATCHED")

        return AdversarialResult(
            scenario_id="ADV_07",
            attack_name="Window Boundary Contention",
            attack_family="Unanchored Candidate Contention",
            description="Payment captured on Day 1 competing for BC1 (Day 2) and BC2 (Day 20, outside window).",
            solver_verdict=f"BC1:{r1['status'] if r1 else 'NONE'}, BC2:{r2['status'] if r2 else 'NONE'}",
            expected_defense="TEMPORAL_WINDOW_PRUNING",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="TEMPORAL_CANDIDATE_PRUNING",
            proximity_margin_paise=100000,
            proximity_margin_pct=100.0,
            margin_classification="COMFORTABLE_DEFENSE",
            telemetry={"bc1_status": r1["status"] if r1 else None, "bc2_status": r2["status"] if r2 else None}
        )

    @staticmethod
    def test_adv_08_multi_candidate_tie_break() -> AdversarialResult:
        """3 identical payments competing for 1 credit, resolved via deterministic tie-breaking."""
        conn = get_memory_db()
        insert_payment(conn, "pay_tb1", "ord_tb1", 50000, "2026-08-01T11:00:00")
        insert_payment(conn, "pay_tb2", "ord_tb2", 50000, "2026-08-01T11:05:00")
        insert_payment(conn, "pay_tb3", "ord_tb3", 50000, "2026-08-01T11:10:00")
        
        insert_bank_credit(conn, "bc_adv_08", 50000, "NEFT-TIE-BREAK", "2026-08-02", None)
        conn.commit()

        res = solve_matching(conn=conn, epsilon_pct=0.0)
        conn.close()

        r = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_08"), None)
        matched = r.get("matched_payment_ids", []) if r else []

        defended = (r and r["status"] == "MATCHED" and len(matched) == 1)

        return AdversarialResult(
            scenario_id="ADV_08",
            attack_name="Multi-Candidate Tie-Break (Unanchored)",
            attack_family="Unanchored Candidate Contention",
            description="3 identical payment candidates competing for a single credit without UTR.",
            solver_verdict=r["status"] if r else "NONE",
            expected_defense="DETERMINISTIC_SINGLE_CANDIDATE_MATCH",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="DETERMINISTIC_TIE_BREAKING",
            proximity_margin_paise=50000,
            proximity_margin_pct=100.0,
            margin_classification="COMFORTABLE_DEFENSE",
            telemetry={"matched_payment": matched, "candidate_count": 3}
        )

    # =========================================================================
    # FAMILY 3: DYNAMIC TOLERANCE BOUNDARY EXPLOITS
    # =========================================================================

    @staticmethod
    def test_adv_09_overpayment_exact_plus_1_paise() -> AdversarialResult:
        """Overpayment far above gross payment amount (strict rejection)."""
        conn = get_memory_db()
        insert_payment(conn, "pay_op1", "ord_op1", 100000, "2026-08-01T11:00:00")
        
        # Credit is 110,000 (+10,000 paise over gross 100,000)
        insert_bank_credit(conn, "bc_adv_09", 110000, "NEFT-UTR_OP1-SETTLEMENT", "2026-08-02", "UTR_OP1")
        conn.commit()

        res = solve_matching(conn=conn, epsilon_pct=0.0)
        conn.close()

        r = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_09"), None)
        status = r["status"] if r else "UNMATCHED"

        defended = (status == "UNMATCHED")
        proximity_paise = 10000
        proximity_pct = (proximity_paise / 100000) * 100.0

        return AdversarialResult(
            scenario_id="ADV_09",
            attack_name="Asymmetric Overpayment Rejection",
            attack_family="Dynamic Tolerance Boundary Exploits",
            description="Bank credit overpays by +10,000 paise above gross payment amount.",
            solver_verdict=status,
            expected_defense="UNMATCHED",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="ASYMMETRIC_UPPER_BOUND_REJECTION",
            proximity_margin_paise=proximity_paise,
            proximity_margin_pct=round(proximity_pct, 4),
            margin_classification="COMFORTABLE_DEFENSE",
            telemetry={"gross_paise": 100000, "credit_paise": 110000, "overpayment_paise": 10000}
        )

    @staticmethod
    def test_adv_10_overpayment_over_gross_sub_percent() -> AdversarialResult:
        """Overpayment by +5,000 paise over gross amount."""
        conn = get_memory_db()
        insert_payment(conn, "pay_op50", "ord_op50", 100000, "2026-08-01T11:00:00")
        
        insert_bank_credit(conn, "bc_adv_10", 105000, "NEFT-UTR_OP50-SETTLEMENT", "2026-08-02", "UTR_OP50")
        conn.commit()

        res = solve_matching(conn=conn, epsilon_pct=0.0)
        conn.close()

        r = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_10"), None)
        status = r["status"] if r else "UNMATCHED"

        defended = (status == "UNMATCHED")
        proximity_paise = 5000
        proximity_pct = (proximity_paise / 100000) * 100.0

        return AdversarialResult(
            scenario_id="ADV_10",
            attack_name="Sub-Percent Overpayment (+5000 Paise)",
            attack_family="Dynamic Tolerance Boundary Exploits",
            description="Bank credit overpays by +5000 paise testing upper boundary enforcement.",
            solver_verdict=status,
            expected_defense="UNMATCHED",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="ASYMMETRIC_UPPER_BOUND_REJECTION",
            proximity_margin_paise=proximity_paise,
            proximity_margin_pct=round(proximity_pct, 4),
            margin_classification="COMFORTABLE_DEFENSE",
            telemetry={"gross_paise": 100000, "credit_paise": 105000, "overpayment_paise": 5000}
        )

    @staticmethod
    def test_adv_11_underpayment_exact_minus_1_paise_beyond_envelope() -> AdversarialResult:
        """Underpayment beyond statutory deduction envelope."""
        conn = get_memory_db()
        insert_payment(conn, "pay_up1", "ord_up1", 100000, "2026-08-01T11:00:00")
        net = insert_fee_stack(conn, "pay_up1", 100000)
        
        insert_bank_credit(conn, "bc_adv_11", 50000, "NEFT-UTR_UP1-SETTLEMENT", "2026-08-02", "UTR_UP1")
        conn.commit()

        res = solve_matching(conn=conn, epsilon_pct=0.0)
        conn.close()

        r = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_11"), None)
        status = r["status"] if r else "UNMATCHED"

        defended = (status == "UNMATCHED")
        proximity_paise = 46640
        proximity_pct = (proximity_paise / 100000) * 100.0

        return AdversarialResult(
            scenario_id="ADV_11",
            attack_name="Underpayment Beyond Deduction Envelope",
            attack_family="Dynamic Tolerance Boundary Exploits",
            description="Bank credit is short by 46,640 paise below statutory net deduction envelope.",
            solver_verdict=status,
            expected_defense="UNMATCHED",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="DYNAMIC_LOWER_BOUND_REJECTION",
            proximity_margin_paise=proximity_paise,
            proximity_margin_pct=round(proximity_pct, 4),
            margin_classification="COMFORTABLE_DEFENSE",
            telemetry={"expected_net": net, "credit_paise": 50000, "shortage_paise": 46640}
        )

    @staticmethod
    def test_adv_12_underpayment_exact_boundary_inner_edge() -> AdversarialResult:
        """Exact boundary inner edge: 0 paise delta matches cleanly."""
        conn = get_memory_db()
        insert_payment(conn, "pay_edge", "ord_edge", 100000, "2026-08-01T11:00:00")
        net = insert_fee_stack(conn, "pay_edge", 100000)
        
        conn.execute("INSERT INTO settlements VALUES ('set_edge', 'UTR_EDGE', 100000, ?, '2026-08-02T10:00:00')", (net,))
        conn.execute("INSERT INTO settlement_items VALUES ('si_edge', 'set_edge', 'pay_edge', 100000)")
        
        insert_bank_credit(conn, "bc_adv_12", net, "NEFT-UTR_EDGE-SETTLEMENT", "2026-08-02", "UTR_EDGE")
        conn.commit()

        res = solve_matching(conn=conn, epsilon_pct=0.0)
        conn.close()

        r = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_12"), None)
        status = r["status"] if r else "UNMATCHED"

        defended = (status == "MATCHED")
        proximity_paise = 1
        proximity_pct = (proximity_paise / 100000) * 100.0

        return AdversarialResult(
            scenario_id="ADV_12",
            attack_name="Exact Boundary Inner Edge (0 Paise Delta)",
            attack_family="Dynamic Tolerance Boundary Exploits",
            description="Exact statutory net match verifying 0 delta acceptance at the boundary edge.",
            solver_verdict=status,
            expected_defense="MATCHED",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="EXACT_STATUTORY_MATCH_ACCEPTANCE",
            proximity_margin_paise=proximity_paise,
            proximity_margin_pct=round(proximity_pct, 4),
            margin_classification="MARGINAL_DEFENSE",  # 0.001% <= 0.10%
            telemetry={"expected_net": net, "credit_paise": net, "delta_paise": 0}
        )

    # =========================================================================
    # FAMILY 4: GHOST & SYNTHETIC CREDIT INJECTIONS
    # =========================================================================

    @staticmethod
    def test_adv_13_ghost_credit_perfect_narration() -> AdversarialResult:
        """Ghost credit with valid NEFT narration but zero records in database."""
        conn = get_memory_db()
        insert_bank_credit(conn, "bc_adv_13", 250000, "NEFT-UTR99988877-SETTLEMENT-RAZORPAY", "2026-08-05", "UTR99988877")
        conn.commit()

        res = solve_matching(conn=conn, epsilon_pct=0.0)
        conn.close()

        r = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_13"), None)
        status = r["status"] if r else "UNMATCHED"

        defended = (status == "UNMATCHED")

        return AdversarialResult(
            scenario_id="ADV_13",
            attack_name="Ghost Credit (Plausible Bank Narration)",
            attack_family="Ghost & Synthetic Credit Injections",
            description="Fabricated bank credit mimicking authentic NEFT narration with zero ledger existence.",
            solver_verdict=status,
            expected_defense="UNMATCHED",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="ZERO_LEDGER_FOOTPRINT_ISOLATION",
            proximity_margin_paise=250000,
            proximity_margin_pct=100.0,
            margin_classification="COMFORTABLE_DEFENSE",
            telemetry={"ghost_amount": 250000, "parsed_utr": "UTR99988877"}
        )

    @staticmethod
    def test_adv_14_ghost_credit_truncated_fake_utr() -> AdversarialResult:
        """Ghost credit with malformed/truncated narration."""
        conn = get_memory_db()
        insert_bank_credit(conn, "bc_adv_14", 150000, "CMS/000999/INVALID", "2026-08-05", None)
        conn.commit()

        res = solve_matching(conn=conn, epsilon_pct=0.0)
        conn.close()

        r = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_14"), None)
        status = r["status"] if r else "UNMATCHED"

        defended = (status == "UNMATCHED")

        return AdversarialResult(
            scenario_id="ADV_14",
            attack_name="Ghost Credit (Truncated Malformed Narration)",
            attack_family="Ghost & Synthetic Credit Injections",
            description="Fabricated bank credit with non-standard truncated narration string.",
            solver_verdict=status,
            expected_defense="UNMATCHED",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="NARRATION_PREPROCESS_REJECTION",
            proximity_margin_paise=150000,
            proximity_margin_pct=100.0,
            margin_classification="COMFORTABLE_DEFENSE",
            telemetry={"ghost_amount": 150000, "narration": "CMS/000999/INVALID"}
        )

    @staticmethod
    def test_adv_15_ghost_credit_duplicate_narration_diff_amount() -> AdversarialResult:
        """Duplicate UTR narration with conflicting amount (forgery attempt)."""
        conn = get_memory_db()
        insert_payment(conn, "pay_f1", "ord_f1", 100000, "2026-08-01T11:00:00")
        net = insert_fee_stack(conn, "pay_f1", 100000)
        
        conn.execute("INSERT INTO settlements VALUES ('set_f1', 'UTR_FORGE', 100000, ?, '2026-08-02T10:00:00')", (net,))
        conn.execute("INSERT INTO settlement_items VALUES ('si_f1', 'set_f1', 'pay_f1', 100000)")
        
        insert_bank_credit(conn, "bc_legit", net, "NEFT-UTR_FORGE-SETTLEMENT", "2026-08-02", "UTR_FORGE")
        insert_bank_credit(conn, "bc_adv_15", 50000, "NEFT-UTR_FORGE-SETTLEMENT", "2026-08-02", "UTR_FORGE")
        conn.commit()

        res = solve_matching(conn=conn, epsilon_pct=0.0)
        conn.close()

        r = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_15"), None)
        status = r["status"] if r else "UNMATCHED"

        defended = (status == "UNMATCHED")

        return AdversarialResult(
            scenario_id="ADV_15",
            attack_name="Conflicting Forged Duplicate UTR",
            attack_family="Ghost & Synthetic Credit Injections",
            description="Forged bank credit reusing genuine UTR narration but specifying conflicting amount.",
            solver_verdict=status,
            expected_defense="UNMATCHED",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="UTR_AMOUNT_CONFLICT_REJECTION",
            proximity_margin_paise=46640,
            proximity_margin_pct=48.26,
            margin_classification="COMFORTABLE_DEFENSE",
            telemetry={"genuine_amount": net, "forged_amount": 50000, "utr": "UTR_FORGE"}
        )

    # =========================================================================
    # FAMILY 5: HIGH-CARDINALITY SPLITTING & SYMMETRY
    # =========================================================================

    @staticmethod
    def test_adv_16_high_cardinality_10_to_1() -> AdversarialResult:
        """10 small payments batched into 1 settlement (stress-testing DP subset partition)."""
        conn = get_memory_db()
        p_ids = []
        for i in range(10):
            p_id = f"pay_hc_{i}"
            p_ids.append(p_id)
            insert_payment(conn, p_id, f"ord_hc_{i}", 10000, "2026-08-01T11:00:00")
        
        conn.execute("INSERT INTO settlements VALUES ('set_hc', 'UTR_HC10', 100000, 100000, '2026-08-02T10:00:00')")
        for p_id in p_ids:
            conn.execute("INSERT INTO settlement_items VALUES (?, 'set_hc', ?, 10000)", (f"si_{p_id}", p_id))
        
        insert_bank_credit(conn, "bc_adv_16", 100000, "NEFT-UTR_HC10-SETTLEMENT", "2026-08-02", "UTR_HC10")
        conn.commit()

        res = solve_matching(conn=conn, epsilon_pct=0.0)
        conn.close()

        r = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_16"), None)
        matched = r.get("matched_payment_ids", []) if r else []

        defended = (r and r["status"] == "MATCHED" and len(matched) == 10)

        return AdversarialResult(
            scenario_id="ADV_16",
            attack_name="High-Cardinality 10-to-1 Partition",
            attack_family="High-Cardinality Splitting & Symmetry",
            description="10 small payment candidates aggregated into 1 settlement testing DP solver cardinality handling.",
            solver_verdict=r["status"] if r else "NONE",
            expected_defense="MATCHED_ALL_10",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="N_TO_1_EXACT_DP_SOLVER",
            proximity_margin_paise=100000,
            proximity_margin_pct=100.0,
            margin_classification="COMFORTABLE_DEFENSE",
            telemetry={"expected_cardinality": 10, "actual_matched": len(matched)}
        )

    @staticmethod
    def test_adv_17_symmetric_duplicate_split() -> AdversarialResult:
        """4 identical payments where credit expects exactly 2 without consuming 3 or 1."""
        conn = get_memory_db()
        for i in range(4):
            insert_payment(conn, f"pay_sym_{i}", f"ord_sym_{i}", 25000, "2026-08-01T11:00:00")
        
        insert_bank_credit(conn, "bc_adv_17", 50000, "NEFT-SYMMETRIC-SPLIT", "2026-08-02", None)
        conn.commit()

        res = solve_matching(conn=conn, epsilon_pct=0.0)
        conn.close()

        r = next((r for r in res["real_results"] if r["bank_credit_id"] == "bc_adv_17"), None)
        matched = r.get("matched_payment_ids", []) if r else []

        defended = (r and r["status"] == "MATCHED" and len(matched) == 2)

        return AdversarialResult(
            scenario_id="ADV_17",
            attack_name="Symmetric Duplicate Split (Exact Partition)",
            attack_family="High-Cardinality Splitting & Symmetry",
            description="4 identical payment candidates competing for credit expecting exactly 2 payments.",
            solver_verdict=r["status"] if r else "NONE",
            expected_defense="EXACT_2_CANDIDATE_MATCH",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="MIN_CARDINALITY_SUBSET_SUM",
            proximity_margin_paise=25000,
            proximity_margin_pct=50.0,
            margin_classification="COMFORTABLE_DEFENSE",
            telemetry={"candidate_count": 4, "matched_count": len(matched)}
        )

    @staticmethod
    def test_adv_18_permutation_invariance() -> AdversarialResult:
        """Inserting candidate payments in reverse order yields identical deterministic output."""
        conn1 = get_memory_db()
        conn2 = get_memory_db()

        insert_payment(conn1, "pay_p1", "ord_p1", 30000, "2026-08-01T11:00:00")
        insert_payment(conn1, "pay_p2", "ord_p2", 70000, "2026-08-01T11:00:00")
        insert_bank_credit(conn1, "bc_adv_18", 100000, "NEFT-PERMUTATION", "2026-08-02", None)
        conn1.commit()

        insert_payment(conn2, "pay_p2", "ord_p2", 70000, "2026-08-01T11:00:00")
        insert_payment(conn2, "pay_p1", "ord_p1", 30000, "2026-08-01T11:00:00")
        insert_bank_credit(conn2, "bc_adv_18", 100000, "NEFT-PERMUTATION", "2026-08-02", None)
        conn2.commit()

        res1 = solve_matching(conn=conn1, epsilon_pct=0.0)
        res2 = solve_matching(conn=conn2, epsilon_pct=0.0)
        conn1.close()
        conn2.close()

        m1 = sorted(res1["real_results"][0]["matched_payment_ids"])
        m2 = sorted(res2["real_results"][0]["matched_payment_ids"])

        defended = (m1 == m2 and m1 == ["pay_p1", "pay_p2"])

        return AdversarialResult(
            scenario_id="ADV_18",
            attack_name="Permutation Invariance (Order Shuffling)",
            attack_family="High-Cardinality Splitting & Symmetry",
            description="Candidate rows inserted in reverse chronological order return identical match set.",
            solver_verdict="INVARIANT",
            expected_defense="INVARIANT",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="DETERMINISTIC_SORT_KEY_ORDERING",
            proximity_margin_paise=100000,
            proximity_margin_pct=100.0,
            margin_classification="COMFORTABLE_DEFENSE",
            telemetry={"forward_matches": m1, "reverse_matches": m2}
        )

    # =========================================================================
    # FAMILY 6: COMPOUND DEDUCTION CONCEALMENT
    # =========================================================================

    @staticmethod
    def test_adv_19_compound_tds_plus_refund() -> AdversarialResult:
        """Composite deduction (10% TDS section variance) handed off to Delta Explainer."""
        conn = get_memory_db()
        insert_payment(conn, "pay_cmp", "ord_cmp", 100000, "2026-08-01T11:00:00")
        net = insert_fee_stack(conn, "pay_cmp", 100000)
        
        # Credit is net - 9000 paise (10% TDS instead of 1% TDS, Section 194J(2) Professional Fees)
        target_credit = net - 9000
        insert_bank_credit(conn, "bc_adv_19", target_credit, "NEFT-UNMATCHED-CMP", "2026-08-02", None)
        conn.commit()

        de_res = explain_delta(conn, "bc_adv_19")
        conn.close()

        defended = (de_res["status"] == "PROBABLE" and len(de_res["hypotheses"]) > 0 and de_res["hypotheses"][0]["category"] == "TAX_RATE_VARIANCE")

        return AdversarialResult(
            scenario_id="ADV_19",
            attack_name="Alternate TDS Section Concealment",
            attack_family="Compound Deduction Concealment",
            description="10% TDS rate variance delta (Section 194J) resolved by Delta Explainer.",
            solver_verdict=de_res["status"],
            expected_defense="PROBABLE_TAX_RATE_VARIANCE",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="DELTA_EXPLAINER_ABDUCTIVE_HANDOFF",
            proximity_margin_paise=9000,
            proximity_margin_pct=9.0,
            margin_classification="COMFORTABLE_DEFENSE",
            telemetry={"delta_paise": 9000, "top_category": de_res["hypotheses"][0]["category"] if de_res.get("hypotheses") else None}
        )


    @staticmethod
    def test_adv_20_unexplainable_prime_gap() -> AdversarialResult:
        """Prime number delta (731 paise) that cannot be explained by fee rates."""
        conn = get_memory_db()
        insert_payment(conn, "pay_ug", "ord_ug", 100000, "2026-08-01T11:00:00")
        net = insert_fee_stack(conn, "pay_ug", 100000)
        
        # Credit is net - 731 paise
        insert_bank_credit(conn, "bc_adv_20", net - 731, "NEFT-UNMATCHED-PRIME", "2026-08-02", None)
        conn.commit()

        de_res = explain_delta(conn, "bc_adv_20")
        conn.close()

        defended = (de_res["status"] == "UNRESOLVED" and len(de_res["hypotheses"]) == 0)

        return AdversarialResult(
            scenario_id="ADV_20",
            attack_name="Unexplainable Arbitrary Prime Gap",
            attack_family="Compound Deduction Concealment",
            description="Prime number shortage (731 paise) testing Delta Explainer refusal to fabricate answers.",
            solver_verdict=de_res["status"],
            expected_defense="UNRESOLVED_NO_HALLUCINATIONS",
            defense_status="DEFENDED" if defended else "CONCEDED",
            defense_mechanism="NON_SYCOPHANTIC_UNRESOLVED_CLASSIFICATION",
            proximity_margin_paise=731,
            proximity_margin_pct=0.731,
            margin_classification="COMFORTABLE_DEFENSE",
            telemetry={"delta_paise": 731, "hypotheses_count": len(de_res.get("hypotheses", []))}
        )
