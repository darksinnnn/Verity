import argparse
from preprocessing.parser import process_batch_narrations

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', type=str, default='finance.db', help='Path to SQLite database')
    args = parser.parse_args()

    updated = process_batch_narrations(args.db)
    print(f"Pre-processing complete. Updated {updated} bank_credit records with parsed UTRs.")

if __name__ == '__main__':
    main()
