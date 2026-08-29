import sqlite3
import json

conn = sqlite3.connect('finance.db')
with open('ground_truth.json') as f:
    gt = json.load(f)

gt_by_bc = {g['bank_credit_id']: g for g in gt if g.get('bank_credit_id')}

bc = conn.execute("SELECT id, raw_narration, amount, value_date, parsed_utr FROM bank_credits WHERE id='bc_2dea9493'").fetchone()
print(f"bc_2dea9493: {bc}")
print(f"Ground truth for bc_2dea9493: {gt_by_bc.get('bc_2dea9493')}")

# What settlement was generated for it?
s = conn.execute("SELECT s.id, s.utr, s.net_amount FROM settlements s WHERE s.utr=?", (bc[4],)).fetchone()
print(f"Settlement for bc_2dea9493: {s}")
si = conn.execute("SELECT si.payment_id FROM settlement_items si WHERE si.settlement_id=?", (s[0],)).fetchall() if s else []
print(f"Settlement items for bc_2dea9493: {si}")

conn.close()
