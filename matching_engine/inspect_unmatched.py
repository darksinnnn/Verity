import json
import sqlite3

conn = sqlite3.connect('finance.db')
with open('ground_truth.json') as f:
    gt = json.load(f)

gt_by_bc = {g['bank_credit_id']: g for g in gt if g.get('bank_credit_id')}

with open('matching_results.json') as f:
    mr = json.load(f)

unmatched_ids = mr['unmatched_bank_credit_ids']
print(f"Unmatched bank credit count: {len(unmatched_ids)}")
for uid in unmatched_ids:
    bc = conn.execute("SELECT id, raw_narration, amount, value_date, parsed_utr FROM bank_credits WHERE id=?", (uid,)).fetchone()
    gt_row = gt_by_bc.get(uid, {})
    gtype = gt_row.get("type", "Unknown")
    gstatus = gt_row.get("expected_status", "Unknown")
    gpids = gt_row.get("expected_payment_ids", [])
    print(f"BC ID: {uid}")
    print(f"  Narration : {bc[1]}")
    print(f"  Amount    : {bc[2]} paise")
    print(f"  Date      : {bc[3]}")
    print(f"  ParsedUTR : {bc[4]}")
    print(f"  GT Type   : {gtype}")
    print(f"  GT Status : {gstatus}")
    print(f"  GT PayIDs : {gpids}")
    
    # Check candidate payments
    for pid in gpids:
        p = conn.execute("SELECT p.id, p.amount, p.captured_at, p.method, COALESCE(SUM(f.amount),0) FROM payments p LEFT JOIN fees f ON f.payment_id=p.id WHERE p.id=? GROUP BY p.id", (pid,)).fetchone()
        if p:
            print(f"    Expected payment {p[0]}: gross={p[1]}, net={p[1]-p[4]}, delta={p[1]-p[4]-bc[2]} paise")
    print()

conn.close()
