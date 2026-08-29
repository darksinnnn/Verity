"""
nudges/run_nudges.py

CLI runner for Phase 9 Actionable Exceptions (Mocked Nudge Engine).
Displays drafted nudge messages for all exceptions in finance.db and demonstrates the mocked dispatch.
"""

import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from nudges.nudge_engine import generate_all_nudges, dispatch_nudge_mock


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', type=str, default='finance.db', help='SQLite database path')
    parser.add_argument('--dispatch-demo', action='store_true', help='Demonstrate mocked dispatch execution')
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    cur = conn.execute("SELECT id, related_record_id, status, explanation_text, hypotheses_json, amount_at_risk FROM exceptions ORDER BY amount_at_risk DESC")
    exceptions = []
    for r in cur.fetchall():
        exceptions.append({
            "id": r[0],
            "related_record_id": r[1],
            "status": r[2],
            "explanation_text": r[3],
            "hypotheses_json": r[4],
            "amount_at_risk": r[5],
        })
    conn.close()

    nudges = generate_all_nudges(exceptions)

    print("\n" + "="*85)
    print(f"ACTIONABLE EXCEPTIONS — AUTO-DRAFTED NUDGE QUEUE ({len(nudges)} Items)")
    print("Strictly Mocked UI Proof-of-Concept (No External Network Requests)")
    print("="*85)

    for i, nudge in enumerate(nudges, 1):
        print(f"\n[NUDGE {i}/{len(nudges)}] — Exception: {nudge['exception_id']} ({nudge['status']})")
        print(f"  Target Recipient : {nudge['recipient_team']}")
        print(f"  Proposed Channel : {nudge['channel']}")
        print(f"  Subject Line     : {nudge['subject']}")
        print(f"  Suggested Action : {nudge['suggested_action']}")
        print(f"  --- Draft Message Body ---")
        for line in nudge['message_body'].split("\n"):
            print(f"  | {line}")
        print("  " + "-"*80)

        if args.dispatch_demo and i == 1:
            receipt = dispatch_nudge_mock(nudge)
            print(f"  [MOCKED DISPATCH TEST RESULT]:")
            print(f"    Status       : {receipt['status']}")
            print(f"    Logged Only  : {receipt['logged_only']}")
            print(f"    Confirmation : {receipt['mocked_confirmation']}")
            print("  " + "-"*80)

    print(f"\nAll {len(nudges)} exception nudges drafted and ready for Phase 10 Dashboard integration.")


if __name__ == '__main__':
    main()
