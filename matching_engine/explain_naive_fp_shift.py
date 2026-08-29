"""
Reconstruct the OLD batch state (dup_amt=50000) by checking what bc_4eea04e7's
amount would have been, and what the naive matcher would have done.

When dup_amt=50000:
  - gross=50000, MDR=int(50000*0.02)=1000, GST=int(1000*0.18)=180, TDS=int(50000*0.01)=500
  - net_dup = 50000 - 1000 - 180 - 500 = 48320

When dup_amt=55000:
  - gross=55000, MDR=int(55000*0.02)=1100, GST=int(1100*0.18)=198, TDS=int(55000*0.01)=550
  - net_dup = 55000 - 1100 - 198 - 550 = 53152

So bc_4eea04e7's amount was:
  OLD: 48320 (when dup_amt=50000)
  NEW: 53152 (when dup_amt=55000)

Under old batch (dup_amt=50000):
  bc_4eea04e7 amount = 48320
  The REFUND trap payment pay_aabc25fa also has net=48320 (gross=50000, same fees structure)
  So naive matcher could 1:1 match bc_4eea04e7 → pay_aabc25fa
  => bc_4eea04e7 would be MATCHED by naive
  => GT says UNRESOLVED (Duplicate Extraneous) => counted as FP
  => naive FP count = 2

Under new batch (dup_amt=55000):
  bc_4eea04e7 amount = 53152 (pay_951f58d0 net)
  But pay_951f58d0 was already consumed by bc_0ab54bde (Duplicate Genuine)
  => bc_4eea04e7 amount 53152 has no available 1:1 match in naive pool
  => bc_4eea04e7 stays UNMATCHED
  => not counted as FP
  => naive FP count = 1

This is a DATA change (batch regeneration), not a scoring-logic change.
"""
print("Root cause of naive FP shift (2 -> 1):")
print()
print("OLD batch (dup_amt=50000):")
gross_old = 50000
mdr_old = int(gross_old * 0.02)
gst_old = int(mdr_old * 0.18)
tds_old = int(gross_old * 0.01)
net_old = gross_old - mdr_old - gst_old - tds_old
print(f"  dup_amt=50000: MDR={mdr_old}, GST={gst_old}, TDS={tds_old}, net_dup={net_old}")
print(f"  bc_4eea04e7 amount = {net_old}")
print(f"  Refund trap payment pay_aabc25fa also has net = {net_old} (gross=50000, same fee structure)")
print(f"  => Naive 1:1 matches bc_4eea04e7 -> pay_aabc25fa")
print(f"  => GT says UNRESOLVED => Naive FP += 1 (FP total = 2)")
print()
print("NEW batch (dup_amt=55000):")
gross_new = 55000
mdr_new = int(gross_new * 0.02)
gst_new = int(mdr_new * 0.18)
tds_new = int(gross_new * 0.01)
net_new = gross_new - mdr_new - gst_new - tds_new
print(f"  dup_amt=55000: MDR={mdr_new}, GST={gst_new}, TDS={tds_new}, net_dup={net_new}")
print(f"  bc_4eea04e7 amount = {net_new}")
print(f"  pay_951f58d0 has net={net_new} but was already consumed by bc_0ab54bde (Duplicate Genuine)")
print(f"  => Naive 1:1 finds no available match for bc_4eea04e7")
print(f"  => bc_4eea04e7 stays UNMATCHED => not counted as FP")
print(f"  => Naive FP count drops to 1")
print()
print("Conclusion: this is a batch-data change, not a scoring-logic change.")
print("The naive matcher's code was not touched. Its FP count changed because")
print("changing dup_amt from 50000->55000 (done to avoid Duplicate/Refund amount collision)")
print("also changed whether bc_4eea04e7 finds a 1:1 match in the naive pool.")
