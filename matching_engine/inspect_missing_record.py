import sqlite3
from matching_engine.matcher import _load_bank_credits, _load_open_payments, _get_settlement_payment_ids
from matching_engine.solver import prune_candidates, subset_sum_dp
from matching_engine.tolerance import compute_tolerance_window

conn = sqlite3.connect('finance.db')
bcs = _load_bank_credits(conn)
all_p = _load_open_payments(conn)

bc = next(b for b in bcs if b['id'] == 'bc_c991603f')
print("Bank credit:", bc)

available = all_p
pruned = prune_candidates(available, bc['value_date'])
print(f"Pruned candidate count: {len(pruned)}")
for p in pruned:
    if p['payment_id'] == 'pay_bc2cbb0d':
        print("Target payment found in pruned:", p)

lower, upper = compute_tolerance_window(bc['amount'])
print(f"Tolerance window for amount {bc['amount']}: [{lower}, {upper}]")

matched = subset_sum_dp(pruned, bc['amount'], lower, upper)
print("Matched payment IDs:", matched)

conn.close()
