import sqlite3
import os

db_path = 'finance.db'
schema_path = 'schema.sql'

if os.path.exists(db_path):
    os.remove(db_path)

with open(schema_path, 'r') as f:
    schema = f.read()

conn = sqlite3.connect(db_path)
conn.executescript(schema)
conn.commit()
conn.close()

print("Database initialized successfully.")
