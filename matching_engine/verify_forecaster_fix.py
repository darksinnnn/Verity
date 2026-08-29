import sqlite3, json
conn = sqlite3.connect('finance.db')

cur = conn.execute("""
    SELECT p.id, p.order_id, p.amount, p.captured_at, p.method
    FROM payments p
    LEFT JOIN settlement_items si ON si.payment_id = p.id
    WHERE si.id IS NULL
    ORDER BY p.captured_at ASC
""")
rows = cur.fetchall()
print(f"Payments with no settlement_items row (now selected by forecaster): {len(rows)}")

with open('ground_truth.json') as f:
    gt = json.load(f)

for r in rows:
    pid = r[0]
    gt_match = next((g for g in gt if pid in g.get('expected_payment_ids', [])), None)
    gt_type = gt_match['type'] if gt_match else 'NORMAL (no GT entry)'
    print(f"  {pid}: gross={r[2]} paise, method={r[4]}, type=\"{gt_type}\"")

print()
print("Pending refunds (status=pending or initiated):")
refunds = conn.execute("SELECT * FROM refunds WHERE status='pending' OR status='initiated'").fetchall()
for r in refunds:
    print(f"  {r}")

conn.close()
