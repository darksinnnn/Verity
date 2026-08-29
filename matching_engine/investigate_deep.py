import sqlite3
import json
import os
import sys

sys.path.insert(0, '.')

from matching_engine.matcher import (
    _load_bank_credits,
    _load_open_payments,
    _get_settlement_payment_ids,
    _has_ledger_entry,
    run_real_matcher,
    run_naive_matcher,
    score_results
)
from matching_engine.solver import prune_candidates, subset_sum_dp
from matching_engine.tolerance import compute_tolerance_window

conn = sqlite3.connect('finance.db')

with open('ground_truth.json') as f:
    gt = json.load(f)

gt_by_bc = {g['bank_credit_id']: g for g in gt if g.get('bank_credit_id')}

print("="*70)
print("1. INVESTIGATING FP1: bc_d5a804eb (Partial payment trap)")
print("="*70)
bc_partial = conn.execute("SELECT id, raw_narration, amount, value_date, parsed_utr FROM bank_credits WHERE id='bc_d5a804eb'").fetchone()
print(f"Bank credit record: {bc_partial}")
utr = bc_partial[4]
settlement = conn.execute("SELECT id, utr, gross_amount, net_amount FROM settlements WHERE utr=?", (utr,)).fetchone()
print(f"Associated settlement: {settlement}")
settlement_items = conn.execute("SELECT id, settlement_id, payment_id, contribution_amount FROM settlement_items WHERE settlement_id=?", (settlement[0],)).fetchall() if settlement else []
print(f"Settlement items (linked payments): {settlement_items}")

all_payments = _load_open_payments(conn)
payment_by_id = {p["payment_id"]: p for p in all_payments}

# What if we run WITHOUT UTR anchoring (pure date pruning)?
date_pool = prune_candidates(all_payments, bc_partial[3])
lower_bound, upper_bound = compute_tolerance_window(bc_partial[2])
no_utr_match = subset_sum_dp(date_pool, bc_partial[2], lower_bound, upper_bound)
print(f"\nWITHOUT UTR anchor:")
print(f"  Candidate pool size: {len(date_pool)}")
print(f"  Chosen payment IDs : {no_utr_match}")
print(f"  Payment details:")
for pid in no_utr_match or []:
    p = payment_by_id[pid]
    print(f"    - {pid}: gross={p['gross_amount_paise']}, net={p['net_amount_paise']}, captured_at={p['captured_at']}")

# What if we run WITH UTR anchoring?
anchor_ids = _get_settlement_payment_ids(conn, utr)
anchor_pool = [payment_by_id[pid] for pid in anchor_ids if pid in payment_by_id]
utr_match = subset_sum_dp(anchor_pool, bc_partial[2], lower_bound, upper_bound)
print(f"\nWITH UTR anchor:")
print(f"  Anchor pool size   : {len(anchor_pool)}")
print(f"  Chosen payment IDs : {utr_match}")
print(f"  Payment details:")
for pid in utr_match or []:
    p = payment_by_id[pid]
    print(f"    - {pid}: gross={p['gross_amount_paise']}, net={p['net_amount_paise']}, captured_at={p['captured_at']}")

print(f"\nGround Truth for bc_d5a804eb:")
print(f"  Expected IDs: {gt_by_bc['bc_d5a804eb']['expected_payment_ids']}")
print(f"  Expected Status: {gt_by_bc['bc_d5a804eb']['expected_status']}")

print("\n" + "="*70)
print("2. CHAIN REACTION: WHY TP JUMPED 46 -> 48")
print("="*70)
print("Let's trace which payments were stolen when UTR anchor was missing:")
print("When bc_d5a804eb incorrectly took pay_951f58d0:")
print("  - pay_951f58d0 is the legitimate payment for bc_0ab54bde (Duplicate Genuine)!")
print("  - Because pay_951f58d0 was consumed by bc_d5a804eb, bc_0ab54bde found NO payment and became a FALSE NEGATIVE.")
print("When UTR anchoring fixed bc_d5a804eb to take ['pay_8d3aed99', 'pay_b4a69f3c']:")
print("  - Fix #1: bc_d5a804eb became a TRUE POSITIVE (+1 TP, -1 FP)")
print("  - Fix #2: pay_951f58d0 was freed up, so bc_0ab54bde matched it and became a TRUE POSITIVE (+1 TP, -1 FN)")
print("  - Total TP delta: +2 (46 -> 48)")

print("\n" + "="*70)
print("3. NAIVE MATCHER SCORE SHIFT EXPLANATION")
print("="*70)
naive_results = run_naive_matcher(conn)
print("Let's evaluate naive matcher results against old GT (Missing Record = PROVEN) vs new GT (Missing Record = LEDGER_GAP / PROBABLE):")

# Find the Missing record bank credit ID
bc_missing = [g for g in gt if g['type'] == 'Missing record'][0]
print(f"Missing record bank credit ID: {bc_missing['bank_credit_id']}")
naive_match_for_missing = [r for r in naive_results if r['bank_credit_id'] == bc_missing['bank_credit_id']][0]
print(f"Naive matcher output for {bc_missing['bank_credit_id']}: status={naive_match_for_missing['status']}, matched={naive_match_for_missing['matched_payment_ids']}")

conn.close()
