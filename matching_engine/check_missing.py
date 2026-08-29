import sqlite3
from matching_engine.matcher import run_real_matcher

conn = sqlite3.connect('finance.db')
results = run_real_matcher(conn)
for r in results:
    if r['bank_credit_id'] == 'bc_c991603f':
        print("bc_c991603f result:", r)
    if 'pay_bc2cbb0d' in r['matched_payment_ids']:
        print(f"pay_bc2cbb0d was matched by {r['bank_credit_id']} with status={r['status']}")
conn.close()
