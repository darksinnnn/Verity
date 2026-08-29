"""Confirm the Missing Record trap's exact resolved status in the pipeline."""
import json, sqlite3, sys
sys.path.insert(0, '.')
from matching_engine.matcher import run_real_matcher

with open('ground_truth.json') as f:
    gt = json.load(f)

missing_record_gt = next(g for g in gt if g['type'] == 'Missing record')
print(f"Ground truth — bank_credit_id : {missing_record_gt['bank_credit_id']}")
print(f"Ground truth — expected_status: {missing_record_gt['expected_status']}")
print(f"Ground truth — expected_pay_id: {missing_record_gt['expected_payment_ids']}")
print()

conn = sqlite3.connect('finance.db')
real_results = run_real_matcher(conn)
conn.close()

bc_id = missing_record_gt['bank_credit_id']
result = next((r for r in real_results if r['bank_credit_id'] == bc_id), None)
if result:
    print(f"Actual result — status               : {result['status']}")
    print(f"Actual result — matched_payment_ids  : {result['matched_payment_ids']}")
    print(f"Actual result — missing_ledger_pids  : {result.get('missing_ledger_payment_ids', [])}")
    print()
    if result['status'] == missing_record_gt['expected_status']:
        print("PASS: Actual status matches expected ground truth status (PROBABLE).")
    else:
        print(f"FAIL: Expected {missing_record_gt['expected_status']}, got {result['status']}.")
else:
    print("ERROR: bank credit not found in results at all.")
