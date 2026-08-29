import json
import sqlite3

with open('matching_results.json') as f:
    mr = json.load(f)

for r in mr['real_results']:
    if 'pay_aabc25fa' in r['matched_payment_ids']:
        print(f"Payment pay_aabc25fa was matched by: {r['bank_credit_id']}, status={r['status']}")

# What is bc_4eea04e7?
conn = sqlite3.connect('finance.db')
bc_dup = conn.execute("SELECT id, raw_narration, amount, value_date, parsed_utr FROM bank_credits WHERE id='bc_4eea04e7'").fetchone()
print(f"bc_4eea04e7 details: {bc_dup}")

# What is bc_f94d6204?
bc_ref = conn.execute("SELECT id, raw_narration, amount, value_date, parsed_utr FROM bank_credits WHERE id='bc_f94d6204'").fetchone()
print(f"bc_f94d6204 details: {bc_ref}")
conn.close()
