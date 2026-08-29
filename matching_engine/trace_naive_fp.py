"""
Reconstruct exactly which bank_credit_id caused the naive FP=2 → FP=1 shift.

The batch was last scored with dup_amt=55000 but the DB hash changed on regeneration,
meaning the DB file that produced the FP=1 result may be different from the one now.
We need to identify:
1. Which BC was FP=2 under the prior scoring
2. Why the naive matcher changed count without its own code changing
"""
import json
import sqlite3
import sys, os
sys.path.insert(0, '.')

from matching_engine.matcher import run_naive_matcher, score_results

conn = sqlite3.connect('finance.db')
with open('ground_truth.json') as f:
    gt = json.load(f)

gt_by_bc = {g['bank_credit_id']: g for g in gt if g.get('bank_credit_id')}

naive_results = run_naive_matcher(conn)
print("=== NAIVE MATCHER FULL TRACE ===")
print(f"Total results: {len(naive_results)}")
print()
for r in naive_results:
    if r['status'] == 'MATCHED':
        bc_id = r['bank_credit_id']
        gt_row = gt_by_bc.get(bc_id, {})
        gt_status = gt_row.get('expected_status', 'NONE')
        gt_pay = set(gt_row.get('expected_payment_ids', []))
        actual_pay = set(r['matched_payment_ids'])
        is_tp = (gt_status == 'PROVEN') and (gt_pay == actual_pay)
        label = 'TP' if is_tp else 'FP'
        if label == 'FP':
            print(f"  [{label}] BC={bc_id:<14} Amount={r['bank_credit_amount_paise']}")
            print(f"         Matched: {r['matched_payment_ids']}")
            print(f"         GT IDs:  {list(gt_pay)}")
            print(f"         GT Type: {gt_row.get('type')}")
            print(f"         GT Status: {gt_status}")
            bc_narration = conn.execute("SELECT raw_narration FROM bank_credits WHERE id=?", (bc_id,)).fetchone()
            print(f"         Narration: {bc_narration[0]}")
            print()

# Show summary
score = score_results(naive_results, gt)
print(f"Naive Score: TP={score['true_positives']}, FP={score['false_positives']}, FN={score['false_negatives']}")

# Now also show what bc_4eea04e7's resolution looks like specifically
print()
bc_dup = 'bc_4eea04e7'
r_dup = next((r for r in naive_results if r['bank_credit_id'] == bc_dup), None)
gt_dup = gt_by_bc.get(bc_dup, {})
print(f"bc_4eea04e7 (Duplicate Extraneous trap):")
print(f"  Naive result:  status={r_dup['status'] if r_dup else 'NOT FOUND'}, matched={r_dup['matched_payment_ids'] if r_dup else '[]'}")
print(f"  GT expected_status: {gt_dup.get('expected_status')}")
print(f"  GT expected_payment_ids: {gt_dup.get('expected_payment_ids')}")

bc_dup_amount = conn.execute("SELECT amount FROM bank_credits WHERE id=?", (bc_dup,)).fetchone()
print(f"  Bank credit amount: {bc_dup_amount[0] if bc_dup_amount else 'NOT FOUND'}")

# How many payments have net == bc_4eea04e7 amount?
if bc_dup_amount:
    amt = bc_dup_amount[0]
    pays = conn.execute("""
        SELECT p.id, p.amount, COALESCE(SUM(f.amount),0) FROM payments p
        LEFT JOIN fees f ON f.payment_id=p.id
        GROUP BY p.id
        HAVING (p.amount - COALESCE(SUM(f.amount),0)) = ?
    """, (amt,)).fetchall()
    print(f"  Payments with net={amt}: {[(p[0], p[1]-p[2]) for p in pays]}")

conn.close()
