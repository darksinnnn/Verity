import re

def extract_utr_from_narration(narration: str) -> str | None:
    """
    Extracts the UTR or reference code from a messy bank narration string.
    Returns the extracted UTR (string) or None if no identifier is found.
    """
    if not narration:
        return None
        
    # Look for "UTR" followed by one or more digits.
    # This handles standard cases (e.g., NEFT-UTR12345678-SETTLE) 
    # and truncated cases (e.g., NEFT-UTR123...)
    match = re.search(r'UTR(\d+)', narration)
    
    if match:
        return f"UTR{match.group(1)}"
        
    return None

def process_batch_narrations(db_path: str):
    """
    Reads all bank_credits with null parsed_utr, parses them, 
    and updates the parsed_utr column.
    """
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, raw_narration FROM bank_credits WHERE parsed_utr IS NULL")
    rows = cursor.fetchall()
    
    updates = []
    for row_id, raw_narration in rows:
        parsed = extract_utr_from_narration(raw_narration)
        updates.append((parsed, row_id))
        
    if updates:
        cursor.executemany("UPDATE bank_credits SET parsed_utr = ? WHERE id = ?", updates)
        conn.commit()
        
    conn.close()
    return len(updates)
