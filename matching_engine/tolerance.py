"""
matching_engine/tolerance.py

Computes the asymmetric, dynamic tolerance window for a bank credit.

The bank credit amount IS the net amount already received.
We allow it to be short by up to the full expected deduction stack
(MDR + GST-on-MDR + TDS computed on the bank credit amount as a proxy
for gross), and overpayment is near-zero (100 paise max).

All amounts are in paise (integer). Never floats.
"""

# These must stay consistent with generate_batch.py's values.
MDR_RATE        = 0.02
GST_ON_MDR_RATE = 0.18
TDS_RATE        = 0.01

# Maximum overpayment allowed (in paise). Near-zero as per spec.
MAX_OVERPAYMENT_PAISE = 100


def compute_expected_deduction(gross_amount_paise: int) -> int:
    """
    Returns the total expected deduction (MDR + GST-on-MDR + TDS) in paise,
    using the same cascading integer rounding as the generator.
    """
    mdr = int(gross_amount_paise * MDR_RATE)
    gst = int(mdr * GST_ON_MDR_RATE)
    tds = int(gross_amount_paise * TDS_RATE)
    return mdr + gst + tds


def compute_tolerance_window(net_amount_paise: int) -> tuple[int, int]:
    """
    Returns (lower_bound, upper_bound) in paise for matching against a
    bank credit of net_amount_paise.

    The bank credit amount is already net. We allow it to be short by
    up to the full expected deduction on the net amount (used as a proxy
    for the gross), and allow 100 paise overpayment.

    lower_bound = net_amount - full_deduction (underpayment tolerance)
    upper_bound = net_amount + 100 paise      (overpayment near-zero)
    """
    deduction_headroom = compute_expected_deduction(net_amount_paise)
    lower_bound = net_amount_paise - deduction_headroom
    upper_bound = net_amount_paise + MAX_OVERPAYMENT_PAISE
    return lower_bound, upper_bound

