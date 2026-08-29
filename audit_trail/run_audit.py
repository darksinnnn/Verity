"""
audit_trail/run_audit.py

CLI entrypoint and verification tool for Phase 8 Cryptographic Audit Trail.
Logs pipeline verdicts and runs SHA-256 hash-chain verification against tampering.
"""

import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from audit_trail.audit_log import AuditTrail


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', type=str, default='finance.db', help='SQLite database path')
    parser.add_argument('--log-batch', action='store_true', help='Record current pipeline verdicts to audit log')
    parser.add_argument('--verify', action='store_true', help='Verify cryptographic hash chain integrity')
    parser.add_argument('--demo-tamper', action='store_true', help='Simulate a database tampering attack and verify detection')
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)

    # 1. Log batch verdicts if requested or if audit_log is empty
    if args.log_batch:
        conn.execute("DELETE FROM audit_log")
        conn.commit()
        matching_results = {}

        if os.path.exists("matching_results.json"):
            with open("matching_results.json") as f:
                matching_results = json.load(f)

        delta_explanations = []
        if os.path.exists("delta_explanations.json"):
            with open("delta_explanations.json") as f:
                delta_explanations = json.load(f)

        exceptions = []
        cur = conn.execute("SELECT id, related_record_id, status, explanation_text, hypotheses_json, amount_at_risk FROM exceptions")
        for r in cur.fetchall():
            exceptions.append({
                "id": r[0], "related_record_id": r[1], "status": r[2],
                "explanation_text": r[3], "amount_at_risk": r[5]
            })

        forecast_report = None
        if os.path.exists("forecast_report.json"):
            with open("forecast_report.json") as f:
                forecast_report = json.load(f)

        entries = AuditTrail.record_batch_verdicts(
            conn=conn,
            batch_id="batch_2026_08",
            matching_results=matching_results,
            delta_explanations=delta_explanations,
            exceptions=exceptions,
            forecast_report=forecast_report
        )
        print(f"Logged {len(entries)} verdict entries into the cryptographic audit trail.")

    # 2. Simulate tamper attack demo
    if args.demo_tamper:
        print("\n" + "="*80)
        print("SIMULATING TAMPER ATTACK ON AUDIT TRAIL...")
        print("="*80)
        # Select an entry to tamper
        cur = conn.execute("SELECT id, payload_json, entry_hash FROM audit_log ORDER BY rowid ASC LIMIT 1 OFFSET 2")
        row = cur.fetchone()
        if not row:
            print("Audit log is empty. Please run with --log-batch first.")
            conn.close()
            return

        target_id, old_payload, old_hash = row[0], row[1], row[2]
        print(f"Target entry to tamper: {target_id}")
        print(f"Original payload: {old_payload[:80]}...")
        print(f"Original SHA-256 hash: {old_hash}")

        # Modify payload in SQLite directly without updating hash
        tampered_payload = old_payload.replace("PROBABLE", "PROVEN").replace("UNRESOLVED", "PROVEN")
        conn.execute("UPDATE audit_log SET payload_json = ? WHERE id = ?", (tampered_payload, target_id))
        conn.commit()
        print("\nTampering applied: Silently modified payload status in SQLite database.")

        # Run verification
        print("\nRunning cryptographic verification...")
        res = AuditTrail.verify_chain(conn)
        print(f"Verification result: valid={res['is_valid']}")
        print(f"Detection details: {res['error_message']}")

        # Restore original payload
        conn.execute("UPDATE audit_log SET payload_json = ? WHERE id = ?", (old_payload, target_id))
        conn.commit()
        print("\nRestored original database state.")
        conn.close()
        return

    # 3. Standard verification
    res = AuditTrail.verify_chain(conn)
    conn.close()

    print("\n" + "="*80)
    print("CRYPTOGRAPHIC AUDIT TRAIL VERIFICATION")
    print("="*80)
    print(f"Total Logged Entries : {res['total_entries']}")
    print(f"Genesis Hash         : {res['genesis_hash']}")
    print(f"Latest Hash (Tip)    : {res['latest_hash']}")
    print(f"Cryptographic Status : {'VALID (UNBROKEN HASH CHAIN)' if res['is_valid'] else 'TAMPERED / INVALID'}")
    if not res['is_valid']:
        print(f"Tamper Detected At   : Entry ID {res['tampered_entry_id']} (Index {res['tampered_index']})")
        print(f"Error Description    : {res['error_message']}")
    print("="*80)


if __name__ == '__main__':
    main()
