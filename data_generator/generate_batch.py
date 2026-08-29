import argparse
import random
import json
import sqlite3
import datetime

# Fixed fee and tax rates
MDR_RATE = 0.02
GST_ON_MDR_RATE = 0.18
TDS_RATE = 0.01

def generate_id(prefix):
    return f"{prefix}_{random.getrandbits(32):08x}"

def generate_date(base_date, offset_days=0, offset_hours=0):
    return (base_date + datetime.timedelta(days=offset_days, hours=offset_hours)).isoformat()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--size', type=int, default=60, help='Number of base orders to generate')
    parser.add_argument('--seed', type=int, default=42, help='Random seed for reproducibility')
    parser.add_argument('--db', type=str, default='finance.db', help='Path to SQLite database')
    args = parser.parse_args()

    random.seed(args.seed)
    base_date = datetime.datetime(2026, 8, 1, 10, 0, 0)
    
    records = {
        'orders': [], 'payments': [], 'refunds': [], 'fees': [],
        'settlements': [], 'settlement_items': [], 'bank_credits': [], 'ledger_entries': []
    }
    
    ground_truth = []

    def add_normal_transaction(amount, date, order_id=None, is_trap=False, trap_type="Exact 1:1 match"):
        o_id = order_id or generate_id("ord")
        if not order_id:
            records['orders'].append((o_id, amount, date.isoformat(), f"cust_{random.randint(1000,9999)}"))
        
        p_id = generate_id("pay")
        records['payments'].append((p_id, o_id, amount, generate_date(date, offset_hours=1), "UPI"))
        
        mdr = int(amount * MDR_RATE)
        gst = int(mdr * GST_ON_MDR_RATE)
        tds = int(amount * TDS_RATE)
        records['fees'].extend([
            (generate_id("fee"), p_id, 'MDR', MDR_RATE, mdr),
            (generate_id("fee"), p_id, 'GST_ON_MDR', GST_ON_MDR_RATE, gst),
            (generate_id("fee"), p_id, 'TDS', TDS_RATE, tds)
        ])
        
        s_id = generate_id("set")
        utr = f"UTR{random.randint(10000000, 99999999)}"
        net_amount = amount - mdr - gst - tds
        s_date = generate_date(date, offset_days=1)
        records['settlements'].append((s_id, utr, amount, net_amount, s_date))
        records['settlement_items'].append((generate_id("si"), s_id, p_id, amount))
        
        bc_id = generate_id("bc")
        narration = f"NEFT-{utr}-SETTLEMENT-RAZORPAY"
        records['bank_credits'].append((bc_id, narration, net_amount, s_date, None))
        
        records['ledger_entries'].append((generate_id("leg"), 'payment', p_id, amount, 'credit'))
        
        ground_truth.append({
            'type': trap_type,
            'is_trap': is_trap,
            'bank_credit_id': bc_id,
            'expected_payment_ids': [p_id],
            'expected_status': 'PROVEN'
        })

    num_normal = int(args.size * 0.7)
    for i in range(num_normal):
        add_normal_transaction(random.randint(10000, 500000), base_date + datetime.timedelta(days=i))

    trap_date = base_date + datetime.timedelta(days=num_normal+1)

    # 2. Aggregated settlement (N:1)
    p_ids = []
    total_gross = 0
    total_net = 0
    for _ in range(3):
        amt = random.randint(10000, 50000)
        o_id = generate_id("ord")
        records['orders'].append((o_id, amt, trap_date.isoformat(), f"cust_{random.randint(1000,9999)}"))
        p_id = generate_id("pay")
        records['payments'].append((p_id, o_id, amt, generate_date(trap_date, offset_hours=1), "CARD"))
        
        mdr = int(amt * MDR_RATE)
        gst = int(mdr * GST_ON_MDR_RATE)
        tds = int(amt * TDS_RATE)
        records['fees'].extend([
            (generate_id("fee"), p_id, 'MDR', MDR_RATE, mdr),
            (generate_id("fee"), p_id, 'GST_ON_MDR', GST_ON_MDR_RATE, gst),
            (generate_id("fee"), p_id, 'TDS', TDS_RATE, tds)
        ])
        
        records['ledger_entries'].append((generate_id("leg"), 'payment', p_id, amt, 'credit'))
        p_ids.append(p_id)
        total_gross += amt
        total_net += (amt - mdr - gst - tds)

    s_id = generate_id("set")
    utr = f"UTR{random.randint(10000000, 99999999)}"
    s_date = generate_date(trap_date, offset_days=1)
    records['settlements'].append((s_id, utr, total_gross, total_net, s_date))
    for pid in p_ids:
        p_row = next(p for p in records['payments'] if p[0] == pid)
        records['settlement_items'].append((generate_id("si"), s_id, pid, p_row[2]))
    bc_id = generate_id("bc")
    records['bank_credits'].append((bc_id, f"NEFT-{utr}-BULK", total_net, s_date, None))
    ground_truth.append({
        'type': 'Aggregated settlement (N:1)', 'is_trap': True, 'bank_credit_id': bc_id, 'expected_payment_ids': p_ids, 'expected_status': 'PROVEN'
    })

    # 3. Partial payment
    o_id = generate_id("ord")
    records['orders'].append((o_id, 100000, trap_date.isoformat(), f"cust_{random.randint(1000,9999)}"))
    p_id1 = generate_id("pay")
    p_id2 = generate_id("pay")
    records['payments'].append((p_id1, o_id, 40000, generate_date(trap_date, offset_hours=1), "UPI"))
    records['payments'].append((p_id2, o_id, 60000, generate_date(trap_date, offset_hours=2), "UPI"))
    
    mdr1 = int(40000 * MDR_RATE); gst1 = int(mdr1 * GST_ON_MDR_RATE); tds1 = int(40000 * TDS_RATE)
    mdr2 = int(60000 * MDR_RATE); gst2 = int(mdr2 * GST_ON_MDR_RATE); tds2 = int(60000 * TDS_RATE)
    records['fees'].extend([
        (generate_id("fee"), p_id1, 'MDR', MDR_RATE, mdr1), (generate_id("fee"), p_id1, 'GST_ON_MDR', GST_ON_MDR_RATE, gst1), (generate_id("fee"), p_id1, 'TDS', TDS_RATE, tds1),
        (generate_id("fee"), p_id2, 'MDR', MDR_RATE, mdr2), (generate_id("fee"), p_id2, 'GST_ON_MDR', GST_ON_MDR_RATE, gst2), (generate_id("fee"), p_id2, 'TDS', TDS_RATE, tds2)
    ])
    records['ledger_entries'].append((generate_id("leg"), 'payment', p_id1, 40000, 'credit'))
    records['ledger_entries'].append((generate_id("leg"), 'payment', p_id2, 60000, 'credit'))
    
    s_id = generate_id("set")
    utr = f"UTR{random.randint(10000000, 99999999)}"
    s_date = generate_date(trap_date, offset_days=1)
    total_gross = 100000
    total_net = (40000 - mdr1 - gst1 - tds1) + (60000 - mdr2 - gst2 - tds2)
    records['settlements'].append((s_id, utr, total_gross, total_net, s_date))
    records['settlement_items'].append((generate_id("si"), s_id, p_id1, 40000))
    records['settlement_items'].append((generate_id("si"), s_id, p_id2, 60000))
    bc_id = generate_id("bc")
    records['bank_credits'].append((bc_id, f"NEFT-{utr}-PARTIAL", total_net, s_date, None))
    ground_truth.append({
        'type': 'Partial payment', 'is_trap': True, 'bank_credit_id': bc_id, 'expected_payment_ids': [p_id1, p_id2], 'expected_status': 'PROVEN'
    })

    # 4. Duplicate (same payment recorded twice)
    dup_amt = 55000
    o_id = generate_id("ord")
    p_id = generate_id("pay")
    records['orders'].append((o_id, dup_amt, trap_date.isoformat(), "cust_dup"))
    records['payments'].append((p_id, o_id, dup_amt, generate_date(trap_date, offset_hours=1), "UPI"))
    mdr = int(dup_amt * MDR_RATE); gst = int(mdr * GST_ON_MDR_RATE); tds = int(dup_amt * TDS_RATE)
    records['fees'].extend([
        (generate_id("fee"), p_id, 'MDR', MDR_RATE, mdr), (generate_id("fee"), p_id, 'GST_ON_MDR', GST_ON_MDR_RATE, gst), (generate_id("fee"), p_id, 'TDS', TDS_RATE, tds)
    ])
    records['ledger_entries'].append((generate_id("leg"), 'payment', p_id, dup_amt, 'credit'))
    net_dup = dup_amt - mdr - gst - tds
    bc_id1 = generate_id("bc")
    bc_id2 = generate_id("bc")
    utr = f"UTR{random.randint(10000000, 99999999)}"
    records['bank_credits'].append((bc_id1, f"NEFT-{utr}", net_dup, generate_date(trap_date, offset_days=1), None))
    records['bank_credits'].append((bc_id2, f"NEFT-{utr}-DUP", net_dup, generate_date(trap_date, offset_days=1), None))
    ground_truth.append({
        'type': 'Duplicate Genuine', 'is_trap': True, 'bank_credit_id': bc_id1, 'expected_payment_ids': [p_id], 'expected_status': 'PROVEN'
    })
    ground_truth.append({
        'type': 'Duplicate Extraneous', 'is_trap': True, 'bank_credit_id': bc_id2, 'expected_payment_ids': [], 'expected_status': 'UNRESOLVED'
    })

    # 5. Refund after settlement
    amt = 80000
    o_id = generate_id("ord")
    p_id = generate_id("pay")
    records['orders'].append((o_id, amt, trap_date.isoformat(), "cust_ref"))
    records['payments'].append((p_id, o_id, amt, generate_date(trap_date, offset_hours=1), "UPI"))
    mdr = int(amt * MDR_RATE); gst = int(mdr * GST_ON_MDR_RATE); tds = int(amt * TDS_RATE)
    records['fees'].extend([
        (generate_id("fee"), p_id, 'MDR', MDR_RATE, mdr), (generate_id("fee"), p_id, 'GST_ON_MDR', GST_ON_MDR_RATE, gst), (generate_id("fee"), p_id, 'TDS', TDS_RATE, tds)
    ])
    records['ledger_entries'].append((generate_id("leg"), 'payment', p_id, amt, 'credit'))
    
    # Settlement happens FULL AMOUNT on day 1
    net_amt = amt - mdr - gst - tds
    utr = f"UTR{random.randint(10000000, 99999999)}"
    bc_id = generate_id("bc")
    records['bank_credits'].append((bc_id, f"NEFT-{utr}", net_amt, generate_date(trap_date, offset_days=1), None))
    
    # Refund happens on day 2
    r_id = generate_id("ref")
    records['refunds'].append((r_id, p_id, 20000, generate_date(trap_date, offset_days=2), "processed"))
    
    # Expected status is PROVEN for the initial bank credit, because at the time of matching the gap logic checks if there's any gap. 
    # Actually, the requirement says we check unresolved items. The refund creates a gap in a FUTURE settlement.
    # Wait, the feedback says: "settlement happens for the full amount on day 1 (refund doesn't exist yet), refund gets processed on day 2, and *now* there's a genuine discrepancy between what settled and what should have been recovered - which is a legitimately ambiguous case worth a PROBABLE verdict."
    # If the settlement happens for FULL amount, but the NEXT bank credit is short by the refund amount!
    # Ah! The *subsequent* bank credit is short. Let's model a second payment that is short by the refund amount.
    amt2 = 50000
    o_id2 = generate_id("ord")
    p_id2 = generate_id("pay")
    records['orders'].append((o_id2, amt2, trap_date.isoformat(), "cust_ref2"))
    records['payments'].append((p_id2, o_id2, amt2, generate_date(trap_date, offset_hours=2), "UPI"))
    mdr2 = int(amt2 * MDR_RATE); gst2 = int(mdr2 * GST_ON_MDR_RATE); tds2 = int(amt2 * TDS_RATE)
    records['fees'].extend([
        (generate_id("fee"), p_id2, 'MDR', MDR_RATE, mdr2), (generate_id("fee"), p_id2, 'GST_ON_MDR', GST_ON_MDR_RATE, gst2), (generate_id("fee"), p_id2, 'TDS', TDS_RATE, tds2)
    ])
    records['ledger_entries'].append((generate_id("leg"), 'payment', p_id2, amt2, 'credit'))
    
    # Second bank credit is short by the 20000 refund from p_id
    net_amt2 = amt2 - mdr2 - gst2 - tds2 - 20000
    utr2 = f"UTR{random.randint(10000000, 99999999)}"
    bc_id_short = generate_id("bc")
    records['bank_credits'].append((bc_id_short, f"NEFT-{utr2}-SHORT", net_amt2, generate_date(trap_date, offset_days=3), None))
    
    ground_truth.append({
        'type': 'Refund after settlement (Full)', 'is_trap': False, 'bank_credit_id': bc_id, 'expected_payment_ids': [p_id], 'expected_status': 'PROVEN'
    })
    ground_truth.append({
        'type': 'Refund after settlement (Short)', 'is_trap': True, 'bank_credit_id': bc_id_short, 'expected_payment_ids': [p_id2], 'expected_status': 'PROBABLE'
    })

    # 6. Wrong TDS section rate
    amt = 90000
    o_id = generate_id("ord")
    p_id = generate_id("pay")
    records['orders'].append((o_id, amt, trap_date.isoformat(), "cust_tds"))
    records['payments'].append((p_id, o_id, amt, generate_date(trap_date, offset_hours=1), "UPI"))
    mdr = int(amt * MDR_RATE); gst = int(mdr * GST_ON_MDR_RATE); tds = int(amt * TDS_RATE)
    records['fees'].extend([
        (generate_id("fee"), p_id, 'MDR', MDR_RATE, mdr), (generate_id("fee"), p_id, 'GST_ON_MDR', GST_ON_MDR_RATE, gst), (generate_id("fee"), p_id, 'TDS', TDS_RATE, tds)
    ])
    records['ledger_entries'].append((generate_id("leg"), 'payment', p_id, amt, 'credit'))
    
    wrong_tds_rate = 0.02
    wrong_tds = int(amt * wrong_tds_rate)
    net_amt = amt - mdr - gst - wrong_tds
    bc_id = generate_id("bc")
    utr = f"UTR{random.randint(10000000, 99999999)}"
    records['bank_credits'].append((bc_id, f"NEFT-{utr}", net_amt, generate_date(trap_date, offset_days=1), None))
    ground_truth.append({
        'type': 'Wrong TDS section rate', 'is_trap': True, 'bank_credit_id': bc_id, 'expected_payment_ids': [p_id], 'expected_status': 'PROBABLE'
    })

    # 7. Truncated narration
    amt = 75000
    o_id = generate_id("ord")
    p_id = generate_id("pay")
    records['orders'].append((o_id, amt, trap_date.isoformat(), "cust_trunc"))
    records['payments'].append((p_id, o_id, amt, generate_date(trap_date, offset_hours=1), "UPI"))
    mdr = int(amt * MDR_RATE); gst = int(mdr * GST_ON_MDR_RATE); tds = int(amt * TDS_RATE)
    records['fees'].extend([
        (generate_id("fee"), p_id, 'MDR', MDR_RATE, mdr), (generate_id("fee"), p_id, 'GST_ON_MDR', GST_ON_MDR_RATE, gst), (generate_id("fee"), p_id, 'TDS', TDS_RATE, tds)
    ])
    records['ledger_entries'].append((generate_id("leg"), 'payment', p_id, amt, 'credit'))
    net_amt = amt - mdr - gst - tds
    utr = f"UTR{random.randint(10000000, 99999999)}"
    bc_id = generate_id("bc")
    records['bank_credits'].append((bc_id, f"NEFT-{utr[:4]}...", net_amt, generate_date(trap_date, offset_days=1), None))
    ground_truth.append({
        'type': 'Truncated narration', 'is_trap': True, 'bank_credit_id': bc_id, 'expected_payment_ids': [p_id], 'expected_status': 'PROVEN'
    })

    # 8. Delayed / batched NACH credit
    amt1 = 15000
    amt2 = 18000
    p_id1 = generate_id("pay")
    p_id2 = generate_id("pay")
    records['orders'].append((generate_id("ord"), amt1, trap_date.isoformat(), "cust_nach1"))
    records['orders'].append((generate_id("ord"), amt2, trap_date.isoformat(), "cust_nach2"))
    records['payments'].append((p_id1, records['orders'][-2][0], amt1, generate_date(trap_date, offset_hours=1), "NACH"))
    records['payments'].append((p_id2, records['orders'][-1][0], amt2, generate_date(trap_date, offset_hours=1), "NACH"))
    records['ledger_entries'].append((generate_id("leg"), 'payment', p_id1, amt1, 'credit'))
    records['ledger_entries'].append((generate_id("leg"), 'payment', p_id2, amt2, 'credit'))
    # Assume no MDR on NACH for simplicity, full amount hits bank. But batched together and delayed by 3 days.
    utr = f"UTR{random.randint(10000000, 99999999)}"
    bc_id = generate_id("bc")
    records['bank_credits'].append((bc_id, f"NACH-SETTLE-{utr}", amt1+amt2, generate_date(trap_date, offset_days=3), None))
    ground_truth.append({
        'type': 'Delayed / batched NACH credit', 'is_trap': True, 'bank_credit_id': bc_id, 'expected_payment_ids': [p_id1, p_id2], 'expected_status': 'PROVEN'
    })

    # 9. Missing record
    amt = 25000
    p_id = generate_id("pay")
    o_id = generate_id("ord")
    records['orders'].append((o_id, amt, trap_date.isoformat(), "cust_miss"))
    records['payments'].append((p_id, o_id, amt, generate_date(trap_date, offset_hours=1), "UPI"))
    mdr = int(amt * MDR_RATE); gst = int(mdr * GST_ON_MDR_RATE); tds = int(amt * TDS_RATE)
    records['fees'].extend([
        (generate_id("fee"), p_id, 'MDR', MDR_RATE, mdr), (generate_id("fee"), p_id, 'GST_ON_MDR', GST_ON_MDR_RATE, gst), (generate_id("fee"), p_id, 'TDS', TDS_RATE, tds)
    ])
    # Trap: DO NOT insert into ledger_entries, as per spec.
    net_amt = amt - mdr - gst - tds
    bc_id = generate_id("bc")
    utr = f"UTR{random.randint(10000000, 99999999)}"
    records['bank_credits'].append((bc_id, f"NEFT-{utr}", net_amt, generate_date(trap_date, offset_days=1), None))
    ground_truth.append({
        'type': 'Missing record',
        'is_trap': True,
        'bank_credit_id': bc_id,
        'expected_payment_ids': [p_id],
        # Amount matches payment in DB, but ledger_entries row is absent.
        # Under the strict 3-state system, this is PROBABLE (strong arithmetic evidence, missing audit proof).
        'expected_status': 'PROBABLE'
    })

    # 10. Genuinely unexplainable gap
    amt = 120000
    o_id = generate_id("ord")
    p_id = generate_id("pay")
    records['orders'].append((o_id, amt, trap_date.isoformat(), "cust_gap"))
    records['payments'].append((p_id, o_id, amt, generate_date(trap_date, offset_hours=1), "UPI"))
    mdr = int(amt * MDR_RATE); gst = int(mdr * GST_ON_MDR_RATE); tds = int(amt * TDS_RATE)
    records['fees'].extend([
        (generate_id("fee"), p_id, 'MDR', MDR_RATE, mdr), (generate_id("fee"), p_id, 'GST_ON_MDR', GST_ON_MDR_RATE, gst), (generate_id("fee"), p_id, 'TDS', TDS_RATE, tds)
    ])
    records['ledger_entries'].append((generate_id("leg"), 'payment', p_id, amt, 'credit'))
    net_amt = amt - mdr - gst - tds - 15000  # gap must exceed tolerance window width to stay UNRESOLVED
    bc_id = generate_id("bc")
    utr = f"UTR{random.randint(10000000, 99999999)}"
    records['bank_credits'].append((bc_id, f"NEFT-{utr}", net_amt, generate_date(trap_date, offset_days=1), None))
    ground_truth.append({
        'type': 'Genuinely unexplainable gap', 'is_trap': True, 'bank_credit_id': bc_id, 'expected_payment_ids': [p_id], 'expected_status': 'UNRESOLVED'
    })

    # 11. Pending captured payment (T+1 settlement not yet arrived)
    # Captured on trap_date+3, no settlement_items row, no bank_credit.
    # This is the canonical Phase 6 case: money in, settlement pending.
    amt_pend = 65000
    o_id_pend = generate_id("ord")
    p_id_pend = generate_id("pay")
    records['orders'].append((o_id_pend, amt_pend, (trap_date + datetime.timedelta(days=3)).isoformat(), "cust_pending"))
    records['payments'].append((p_id_pend, o_id_pend, amt_pend, generate_date(trap_date, offset_days=3, offset_hours=1), "UPI"))
    mdr_pend = int(amt_pend * MDR_RATE); gst_pend = int(mdr_pend * GST_ON_MDR_RATE); tds_pend = int(amt_pend * TDS_RATE)
    records['fees'].extend([
        (generate_id("fee"), p_id_pend, 'MDR', MDR_RATE, mdr_pend),
        (generate_id("fee"), p_id_pend, 'GST_ON_MDR', GST_ON_MDR_RATE, gst_pend),
        (generate_id("fee"), p_id_pend, 'TDS', TDS_RATE, tds_pend),
    ])
    records['ledger_entries'].append((generate_id("leg"), 'payment', p_id_pend, amt_pend, 'credit'))
    # Deliberately: NO settlement, NO settlement_items, NO bank_credit.
    # This payment is awaiting T+1 settlement arrival.
    ground_truth.append({
        'type': 'Pending captured payment (awaiting T+1 settlement)',
        'is_trap': False,
        'bank_credit_id': None,  # No bank credit yet
        'expected_payment_ids': [p_id_pend],
        'expected_status': 'PENDING_SETTLEMENT'
    })

    # 12. Pending refund obligation (issued but not yet recovered from settlement)
    # Attached to a *previously-settled* base transaction. Status='pending'.
    # Phase 6 should count this as a future outflow obligation.
    #
    # We attach it to the very first normal payment (p_id from add_normal_transaction).
    # But we don't have that p_id here — instead we create a standalone base payment
    # that is fully settled, then issue a pending refund against it.
    amt_ref_base = 45000
    o_id_ref = generate_id("ord")
    p_id_ref_base = generate_id("pay")
    records['orders'].append((o_id_ref, amt_ref_base, (trap_date + datetime.timedelta(days=2)).isoformat(), "cust_refpend"))
    records['payments'].append((p_id_ref_base, o_id_ref, amt_ref_base, generate_date(trap_date, offset_days=2, offset_hours=1), "UPI"))
    mdr_rb = int(amt_ref_base * MDR_RATE); gst_rb = int(mdr_rb * GST_ON_MDR_RATE); tds_rb = int(amt_ref_base * TDS_RATE)
    records['fees'].extend([
        (generate_id("fee"), p_id_ref_base, 'MDR', MDR_RATE, mdr_rb),
        (generate_id("fee"), p_id_ref_base, 'GST_ON_MDR', GST_ON_MDR_RATE, gst_rb),
        (generate_id("fee"), p_id_ref_base, 'TDS', TDS_RATE, tds_rb),
    ])
    records['ledger_entries'].append((generate_id("leg"), 'payment', p_id_ref_base, amt_ref_base, 'credit'))
    net_rb = amt_ref_base - mdr_rb - gst_rb - tds_rb
    s_id_rb = generate_id("set")
    utr_rb = f"UTR{random.randint(10000000, 99999999)}"
    s_date_rb = generate_date(trap_date, offset_days=3)
    records['settlements'].append((s_id_rb, utr_rb, amt_ref_base, net_rb, s_date_rb))
    records['settlement_items'].append((generate_id("si"), s_id_rb, p_id_ref_base, amt_ref_base))
    bc_id_rb = generate_id("bc")
    records['bank_credits'].append((bc_id_rb, f"NEFT-{utr_rb}", net_rb, s_date_rb, None))
    # Now issue a pending refund against this settled payment — not yet recovered
    r_id_pend = generate_id("ref")
    refund_amt_pend = 12000  # Rs.120 pending refund
    records['refunds'].append((r_id_pend, p_id_ref_base, refund_amt_pend, generate_date(trap_date, offset_days=4), "pending"))
    ground_truth.append({
        'type': 'Pending refund obligation (not yet recovered)',
        'is_trap': False,
        'bank_credit_id': bc_id_rb,
        'expected_payment_ids': [p_id_ref_base],
        'expected_status': 'PROVEN'  # Base payment settled cleanly; refund is a future outflow
    })



    # Post-generation pass: create settlement + settlement_items rows for every
    # trap payment that has a bank_credit in ground_truth but lacks a settlement entry.
    # Real-world model: if a bank credit arrived, Razorpay's settlement engine ran,
    # producing both a settlements row and a settlement_items row.
    # Without this, the forecaster cannot distinguish "trap payment already settled
    # via bank credit" from "genuinely pending payment with no bank credit yet."
    gt_with_bc = [g for g in ground_truth if g.get('bank_credit_id') is not None]
    already_settled_pids = {si[2] for si in records['settlement_items'] if si[2]}
    for gt_entry in gt_with_bc:
        for pid in gt_entry.get('expected_payment_ids', []):
            if pid in already_settled_pids:
                continue  # Already has a settlement_items row
            # Find the payment amount
            p_row = next((p for p in records['payments'] if p[0] == pid), None)
            if p_row is None:
                continue
            p_gross = p_row[2]
            # Use this payment's ACTUAL recorded fees, not an assumed zero-deduction
            # net==gross — several trap payments (Wrong TDS, Unexplainable gap,
            # Truncated narration, Refund, Duplicate) already have real fee rows,
            # and net_amount must agree with them.
            total_fees_for_pid = sum(f[4] for f in records['fees'] if f[1] == pid)
            p_net = p_gross - total_fees_for_pid
            # Build a minimal settlement record
            s_id = generate_id("set")
            utr_si = f"UTR{random.randint(10000000, 99999999)}"
            s_date_si = generate_date(trap_date, offset_days=1)
            records['settlements'].append((s_id, utr_si, p_gross, p_net, s_date_si))
            records['settlement_items'].append((generate_id("si"), s_id, pid, p_gross))
            already_settled_pids.add(pid)

    # Clear DB tables first
    conn = sqlite3.connect(args.db)

    cursor = conn.cursor()
    for table in records.keys():
        cursor.execute(f"DELETE FROM {table}")
    cursor.execute("DELETE FROM exceptions")
    cursor.execute("DELETE FROM audit_log")

    
    # Insert records
    for table, rows in records.items():
        if not rows: continue
        cols = len(rows[0])
        placeholders = ",".join(["?"] * cols)
        cursor.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
    
    conn.commit()
    conn.close()

    with open('ground_truth.json', 'w') as f:
        json.dump(ground_truth, f, indent=2)
    
    print(f"Successfully generated {args.size} base records and traps with seed {args.seed}.")
    print(f"Data saved to {args.db} and ground truth to ground_truth.json.")

if __name__ == '__main__':
    main()
