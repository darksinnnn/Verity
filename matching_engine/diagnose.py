"""Standalone diagnostic CLI tool to score and inspect solver matching results against ground truth (TP/FP/FN analysis)."""
import json, sqlite3, sys, os
sys.path.insert(0, '.')

from matching_engine.matcher import run_real_matcher, run_naive_matcher
from matching_engine.tolerance import compute_tolerance_window

with open('ground_truth.json') as f:
    gt = json.load(f)

gt_by_bc = {g['bank_credit_id']: g for g in gt if g.get('bank_credit_id')}

conn = sqlite3.connect('finance.db')
real_results  = run_real_matcher(conn)
naive_results = run_naive_matcher(conn)
conn.close()

# ── Score both ──────────────────────────────────────────────────────────────
def score(results):
    tp, fp, fn = 0, 0, 0
    fp_records, fn_records = [], []
    matched_bcs = {r['bank_credit_id'] for r in results if r['status'] == 'MATCHED'}
    
    for r in results:
        bc_id = r['bank_credit_id']
        if r['status'] == 'MATCHED':
            gt_row = gt_by_bc.get(bc_id)
            if gt_row is None:
                fp += 1
                fp_records.append({'reason': 'no_gt_entry', **r})
                continue
            expected_ids = set(gt_row.get('expected_payment_ids', []))
            actual_ids   = set(r['matched_payment_ids'])
            if expected_ids == actual_ids and gt_row['expected_status'] == 'PROVEN':
                tp += 1
            else:
                fp += 1
                fp_records.append({
                    'gt_expected_ids': list(expected_ids),
                    'gt_expected_status': gt_row['expected_status'],
                    'gt_type': gt_row['type'],
                    **r
                })
    
    for bc_id, gt_row in {k: v for k, v in gt_by_bc.items() if v['expected_status'] == 'PROVEN'}.items():
        if bc_id not in matched_bcs:
            fn += 1
            fn_records.append({'bank_credit_id': bc_id, 'gt': gt_row})
    
    return tp, fp, fn, fp_records, fn_records

real_tp,  real_fp,  real_fn,  real_fp_recs,  real_fn_recs  = score(real_results)
naive_tp, naive_fp, naive_fn, naive_fp_recs, naive_fn_recs = score(naive_results)

print("=== RAW COUNTS ===")
print(f"Real solver   — TP={real_tp}, FP={real_fp}, FN={real_fn}")
print(f"Naive solver  — TP={naive_tp}, FP={naive_fp}, FN={naive_fn}")

print("\n=== REAL SOLVER FALSE POSITIVES ===")
for fp in real_fp_recs:
    bc_id   = fp['bank_credit_id']
    bc_amt  = fp['bank_credit_amount_paise']
    matched = fp['matched_payment_ids']
    m_sum   = fp.get('matched_sum_paise')
    delta   = bc_amt - m_sum if m_sum is not None else 'N/A'
    eps     = fp.get('epsilon_pct_used')
    lower, upper = compute_tolerance_window(bc_amt)
    print(f"  bank_credit_id  : {bc_id}")
    print(f"  matched_to      : {matched}")
    print(f"  bc_amount       : {bc_amt}")
    print(f"  matched_sum     : {m_sum}")
    print(f"  delta (bc-sum)  : {delta}")
    print(f"  epsilon_pct_used: {eps}%")
    print(f"  tolerance window: [{lower}, {upper}]  (window width = {upper - lower})")
    print(f"  gt_expected_ids : {fp.get('gt_expected_ids')}")
    print(f"  gt_status       : {fp.get('gt_expected_status')}")
    print(f"  trap_type       : {fp.get('gt_type','no_gt')}")
    print()

print("=== REAL SOLVER FALSE NEGATIVES ===")
for fn in real_fn_recs:
    print(f"  bank_credit_id : {fn['bank_credit_id']}")
    print(f"  gt_type        : {fn['gt']['type']}")
    print(f"  gt_pay_ids     : {fn['gt']['expected_payment_ids']}")
    print()

print("=== NAIVE SOLVER FALSE POSITIVES ===")
for fp in naive_fp_recs:
    bc_id  = fp['bank_credit_id']
    bc_amt = fp['bank_credit_amount_paise']
    print(f"  bank_credit_id  : {bc_id}")
    print(f"  matched_to      : {fp['matched_payment_ids']}")
    print(f"  bc_amount       : {bc_amt}")
    print(f"  matched_sum     : {fp.get('matched_sum_paise')}")
    print(f"  gt_expected_ids : {fp.get('gt_expected_ids')}")
    print(f"  gt_status       : {fp.get('gt_expected_status')}")
    print(f"  trap_type       : {fp.get('gt_type','no_gt')}")
    print()
