import sqlite3
import json

conn = sqlite3.connect('finance.db')

# Bank credit bc_33173470
bc = conn.execute("SELECT id, raw_narration, amount, value_date, parsed_utr FROM bank_credits WHERE id='bc_33173470'").fetchone()
print(f"Bank credit bc_33173470: amount={bc[2]} paise (Rs. {bc[2]/100:.2f})")

# Look at ALL payments in the DB near that date
cur = conn.execute("""
    SELECT p.id, p.amount, p.captured_at, COALESCE(SUM(f.amount), 0) AS total_fees
    FROM payments p LEFT JOIN fees f ON f.payment_id = p.id
    GROUP BY p.id
""")
all_payments = cur.fetchall()

print("\nCandidate payments with their standard net amounts and deltas against bc_33173470 (100,968 paise):")
for p in all_payments:
    gross = p[1]
    fees = p[3]
    std_net = gross - fees
    delta = std_net - bc[2]
    if 0 < delta < 20000:
        print(f"  Payment {p[0]}: gross={gross}, fees={fees}, std_net={std_net}, delta={delta} paise (Rs. {delta/100:.2f})")

# Look at the ground truth expected payment for bc_33173470
with open('ground_truth.json') as f:
    gt = json.load(f)
gt_gap = [g for g in gt if g['bank_credit_id'] == 'bc_33173470'][0]
print(f"\nGround Truth for bc_33173470:")
print(f"  Expected payment ID: {gt_gap['expected_payment_ids']}")
gt_p = conn.execute("""
    SELECT p.id, p.amount, COALESCE(SUM(f.amount), 0) AS total_fees
    FROM payments p LEFT JOIN fees f ON f.payment_id = p.id
    WHERE p.id=? GROUP BY p.id
""", (gt_gap['expected_payment_ids'][0],)).fetchone()
print(f"  GT Payment {gt_p[0]}: gross={gt_p[1]}, fees={gt_p[2]}, std_net={gt_p[1]-gt_p[2]}, delta={gt_p[1]-gt_p[2]-bc[2]} paise (Rs. {(gt_p[1]-gt_p[2]-bc[2])/100:.2f})")

conn.close()
