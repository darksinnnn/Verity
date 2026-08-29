"""
Audit exactly which payment IDs the forecaster selected as 'pending',
trace their actual settlement and bank credit status in the DB,
and show the current query's WHERE logic vs what it should be.
"""
import json
import sqlite3

conn = sqlite3.connect('finance.db')

print("=== CURRENT FORECASTER INPUT: settled_pids from matching_results.json ===")
with open('matching_results.json') as f:
    mr = json.load(f)
settled_pids = set()
for r in mr.get("real_results", []):
    if r.get("status") == "MATCHED":
        settled_pids.update(r.get("matched_payment_ids", []))
print(f"Payment IDs marked as settled (MATCHED) by real solver: {len(settled_pids)}")
print()

print("=== ALL PAYMENTS IN DB ===")
cur = conn.execute("SELECT p.id, p.order_id, p.amount, p.captured_at, p.method FROM payments p ORDER BY p.captured_at")
all_payments = cur.fetchall()
print(f"Total payments in DB: {len(all_payments)}")
print()

print("=== FORECASTER's CANDIDATE POOL (not in settled_pids) ===")
pending_candidates = [p for p in all_payments if p[0] not in settled_pids]
print(f"Count: {len(pending_candidates)}")
for p in pending_candidates:
    pid = p[0]
    # Check settlement_items
    si = conn.execute("SELECT si.id, si.settlement_id FROM settlement_items si WHERE si.payment_id=?", (pid,)).fetchall()
    # Check bank credits matched to this via ground truth
    with open('ground_truth.json') as f:
        gt = json.load(f)
    gt_matches = [g for g in gt if pid in g.get('expected_payment_ids', [])]
    # Check matching_results
    mr_match = next((r for r in mr.get("real_results", []) if pid in r.get("matched_payment_ids", [])), None)
    print(f"\n  {pid}:")
    print(f"    gross={p[2]}, captured_at={p[3]}, method={p[4]}")
    print(f"    settlement_items rows: {si}")
    print(f"    ground_truth matches: {[(g['type'], g['bank_credit_id'], g['expected_status']) for g in gt_matches]}")
    print(f"    matching_result: status={mr_match['status'] if mr_match else 'NOT IN REAL RESULTS'}")

print()
print("=== CURRENT QUERY LOGIC IN forecaster.py ===")
print("SELECT p.id FROM payments p WHERE p.id NOT IN settled_pids (passed as Python set)")
print()
print("THE BUG:")
print("settled_pids only contains payment_ids from MATCHED results in matching_results.json.")
print("But settlement_items table already has the settlement linkage for ALL payments,")
print("including those matched PROVEN, PROBABLE, and even trap-matched payments.")
print()
print("=== SETTLEMENT_ITEMS LINKAGE ===")
for p in pending_candidates:
    pid = p[0]
    si = conn.execute("SELECT si.settlement_id FROM settlement_items si WHERE si.payment_id=?", (pid,)).fetchall()
    print(f"  {pid}: settlement_items={[r[0] for r in si]}")

print()
print("=== CORRECT QUERY: join settlement_items to exclude settled payments ===")
cur = conn.execute("""
    SELECT p.id, p.order_id, p.amount, p.captured_at, p.method
    FROM payments p
    LEFT JOIN settlement_items si ON si.payment_id = p.id
    WHERE si.id IS NULL
    ORDER BY p.captured_at ASC
""")
truly_pending = cur.fetchall()
print(f"Payments with NO settlement_items row (truly unsettled): {len(truly_pending)}")
for p in truly_pending:
    pid = p[0]
    with open('ground_truth.json') as f:
        gt = json.load(f)
    gt_match = next((g for g in gt if pid in g.get('expected_payment_ids', [])), None)
    print(f"  {pid}: gross={p[2]} paise, method={p[4]}, type={gt_match['type'] if gt_match else 'NORMAL?'}")

conn.close()
