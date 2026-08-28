CREATE TABLE orders (
  id TEXT PRIMARY KEY,
  amount INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  customer_ref TEXT
);

CREATE TABLE payments (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  amount INTEGER NOT NULL,
  captured_at TEXT NOT NULL,
  method TEXT,
  FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE refunds (
  id TEXT PRIMARY KEY,
  payment_id TEXT NOT NULL,
  amount INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL,
  FOREIGN KEY (payment_id) REFERENCES payments(id)
);

CREATE TABLE fees (
  id TEXT PRIMARY KEY,
  payment_id TEXT NOT NULL,
  fee_type TEXT NOT NULL,
  rate_applied REAL,
  amount INTEGER NOT NULL,
  FOREIGN KEY (payment_id) REFERENCES payments(id)
);

CREATE TABLE settlements (
  id TEXT PRIMARY KEY,
  utr TEXT NOT NULL,
  gross_amount INTEGER NOT NULL,
  net_amount INTEGER NOT NULL,
  settled_at TEXT NOT NULL
);

CREATE TABLE settlement_items (
  id TEXT PRIMARY KEY,
  settlement_id TEXT NOT NULL,
  payment_id TEXT,
  contribution_amount INTEGER NOT NULL,
  FOREIGN KEY (settlement_id) REFERENCES settlements(id),
  FOREIGN KEY (payment_id) REFERENCES payments(id)
);

CREATE TABLE bank_credits (
  id TEXT PRIMARY KEY,
  raw_narration TEXT NOT NULL,
  amount INTEGER NOT NULL,
  value_date TEXT NOT NULL,
  parsed_utr TEXT
);

CREATE TABLE ledger_entries (
  id TEXT PRIMARY KEY,
  reference_type TEXT NOT NULL,
  reference_id TEXT NOT NULL,
  amount INTEGER NOT NULL,
  entry_type TEXT NOT NULL
);

CREATE TABLE exceptions (
  id TEXT PRIMARY KEY,
  batch_id TEXT NOT NULL,
  related_record_type TEXT NOT NULL,
  related_record_id TEXT NOT NULL,
  status TEXT NOT NULL,
  explanation_text TEXT,
  hypotheses_json TEXT,
  amount_at_risk INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE audit_log (
  id TEXT PRIMARY KEY,
  entry_hash TEXT NOT NULL,
  previous_hash TEXT,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX idx_audit_log_entry_hash ON audit_log(entry_hash);
