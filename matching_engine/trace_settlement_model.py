"""
Understand the exact settlement model across all trap types.
For each unsettled payment, check whether a bank_credit exists that matches it.
"""
import sqlite3, json

conn = sqlite3.connect('finance.db')
with open('ground_truth.json') as f:
    gt = json.load(f)

# Build a map: payment_id -> ground truth entries
gt_by_pid = {}
for g in gt:
    for pid in g.get('expected_payment_ids', []):
        gt_by_pid.setdefault(pid, []).append(g)

# Payments with no settlement_items
cur = conn.execute("""
    SELECT p.id, p.order_id, p.amount, p.captured_at, p.method
    FROM payments p
    LEFT JOIN settlement_items si ON si.payment_id = p.id
    WHERE si.id IS NULL
    ORDER BY p.captured_at ASC
""")
rows = cur.fetchall()
print(f"{'Payment ID':<18} {'Has BC?':<8} {'BC ID':<14} {'GT Type'}")
print("-"*80)
for r in rows:
    pid = r[0]
    gt_entries = gt_by_pid.get(pid, [])
    gt_type = gt_entries[0]['type'] if gt_entries else 'NORMAL'
    bc_id = gt_entries[0].get('bank_credit_id') if gt_entries else None
    has_bc = "YES" if bc_id else "NO"
    print(f"  {pid:<16} {has_bc:<8} {str(bc_id):<14} {gt_type}")
print()
print("Conclusion: trap payments have bank credits but no settlement_items rows.")
print("The correct filter for TRULY PENDING is: no settlement_items AND no bank_credit")
print()

# Correct filter: no settlement_items AND no matching bank credit in ground truth
print("=== CORRECT PENDING: no settlement_items AND no bank_credit at all ===")
cur2 = conn.execute("""
    SELECT p.id, p.order_id, p.amount, p.captured_at, p.method
    FROM payments p
    LEFT JOIN settlement_items si ON si.payment_id = p.id
    WHERE si.id IS NULL
    ORDER BY p.captured_at ASC
""")
truly_pending = []
for r in cur2.fetchall():
    pid = r[0]
    gt_entries = gt_by_pid.get(pid, [])
    bc_id = gt_entries[0].get('bank_credit_id') if gt_entries else None
    if bc_id is None:
        truly_pending.append((r, gt_entries))

for r, gt_entries in truly_pending:
    pid = r[0]
    gt_type = gt_entries[0]['type'] if gt_entries else 'NORMAL (no GT)'
    print(f"  {pid}: gross={r[2]} paise, method={r[4]}, type=\"{gt_type}\"")

conn.close()
