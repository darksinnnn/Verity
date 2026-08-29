import json
import sqlite3

with open('ground_truth.json') as f:
    gt = json.load(f)

print("=== GROUND TRUTH REFUND TRAP ENTRIES ===")
for g in gt:
    if 'Refund' in g.get('type', ''):
        print(g)

conn = sqlite3.connect('finance.db')
print("\n=== REFUNDS TABLE ===")
for r in conn.execute('SELECT * FROM refunds').fetchall():
    print(r)

print("\n=== PAYMENTS IN DB ===")
for pid in ['pay_eededb07', 'pay_951f58d0', 'pay_aabc25fa']:
    p = conn.execute('SELECT * FROM payments WHERE id=?', (pid,)).fetchone()
    print(f"  {pid}: {p}")

print("\n=== BANK CREDIT bc_f94d6204 ===")
bc = conn.execute("SELECT * FROM bank_credits WHERE id='bc_f94d6204'").fetchone()
print(bc)

# Trace the refund trap generation logic in generate_batch.py:
# Trap 5: Refund after settlement
# Payment 1 (p_id): settled full on day 1 (bc_id, expected_status: PROVEN). Refund r_id created on day 2 on p_id!
# Payment 2 (p_id2): settled short on day 3 (bc_id2 = bc_f94d6204, expected_payment_ids = [p_id2], expected_status: PROBABLE).
# The refund being recovered on bc_f94d6204 is the refund on p_id!

print("\n=== TRACE OF REFUND ON P_ID VS P_ID2 ===")
refund_row = conn.execute("SELECT * FROM refunds").fetchall()
for ref in refund_row:
    ref_pid = ref[1]
    ref_amt = ref[2]
    p_info = conn.execute("SELECT * FROM payments WHERE id=?", (ref_pid,)).fetchone()
    print(f"Refund {ref[0]}: amount={ref_amt} paise, attached to payment {ref_pid} -> {p_info}")

conn.close()
