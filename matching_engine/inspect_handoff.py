import json
import sqlite3

with open('matching_results.json') as f:
    mr = json.load(f)

print("="*70)
print("PHASE 3 RESULTS INSPECTION")
print("="*70)
print(f"Total Bank Credits in batch: {len(mr['real_results'])}")
print(f"Matched count (status=MATCHED): {sum(1 for r in mr['real_results'] if r['status'] == 'MATCHED')}")
print(f"Probable count (status=PROBABLE): {sum(1 for r in mr['real_results'] if r['status'] == 'PROBABLE')}")
print(f"Unmatched count (status=UNMATCHED): {sum(1 for r in mr['real_results'] if r['status'] == 'UNMATCHED')}")
print()
print("Non-MATCHED bank credits in Phase 3:")
for r in mr['real_results']:
    if r['status'] != 'MATCHED':
        print(f"  ID: {r['bank_credit_id']:<14} Status: {r['status']:<10} Reason: {str(r.get('reason')):<24} Matched: {r['matched_payment_ids']}")

print("\n" + "="*70)
print("DELTA EXPLAINER HANDOFF & OUTPUT")
print("="*70)
with open('delta_explanations.json') as f:
    de = json.load(f)

print(f"Total records processed by Delta Explainer: {len(de)}")
for exp in de:
    cat = exp['hypotheses'][0]['category'] if exp['hypotheses'] else "NO_EXPLANATION"
    print(f"  ID: {exp['bank_credit_id']:<14} Status: {exp['status']:<10} Delta: Rs.{exp['delta_paise']/100:>6.2f}  Category: {cat:<22} Candidate: {exp['candidate_payment_id']}")

conn = sqlite3.connect('finance.db')
with open('ground_truth.json') as f:
    gt = json.load(f)
gt_by_bc = {g['bank_credit_id']: g for g in gt if g.get('bank_credit_id')}

print("\nGround Truth mapping for Delta Explainer records:")
for exp in de:
    bc_id = exp['bank_credit_id']
    g = gt_by_bc.get(bc_id, {})
    print(f"  ID: {bc_id:<14} GT Type: {g.get('type', 'None'):<32} GT Status: {g.get('expected_status')}")

conn.close()
