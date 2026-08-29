import sqlite3
conn = sqlite3.connect('finance.db')
print("Checking gap bank credit amounts (expected: 120000 - fees - 15000 = ~100968):")
bcs = conn.execute('SELECT id, amount, raw_narration FROM bank_credits WHERE raw_narration LIKE "NEFT-UTR7178%"').fetchall()
for b in bcs:
    print(f'  id={b[0]}, amount={b[1]}, narration={b[2]}')
print("\nAll bank credits > 100000:")
bcs2 = conn.execute('SELECT id, amount, raw_narration FROM bank_credits WHERE amount > 100000').fetchall()
for b in bcs2:
    print(f'  id={b[0]}, amount={b[1]}')
conn.close()
