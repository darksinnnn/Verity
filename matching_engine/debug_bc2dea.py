import sqlite3
from matching_engine.matcher import _load_bank_credits, _load_open_payments
from matching_engine.solver import prune_candidates, subset_sum_dp
from matching_engine.tolerance import compute_tolerance_window

conn = sqlite3.connect('finance.db')
bcs = _load_bank_credits(conn)
all_p = _load_open_payments(conn)

bc = next(b for b in bcs if b['id'] == 'bc_2dea9493')
pruned = prune_candidates(all_p, bc['value_date'])
lower, upper = compute_tolerance_window(bc['amount'])

matched = subset_sum_dp(pruned, bc['amount'], lower, upper)
print(f"bc_2dea9493 amount={bc['amount']}")
print(f"Matched by subset_sum_dp: {matched}")
for pid in matched or []:
    p = next(x for x in all_p if x['payment_id'] == pid)
    print(f"  - {pid}: gross={p['gross_amount_paise']}, net={p['net_amount_paise']}")

conn.close()
