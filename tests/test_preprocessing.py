from preprocessing.parser import extract_utr_from_narration

def test_clean_narration():
    # Standard full format
    narration = "NEFT-UTR12345678-SETTLEMENT-RAZORPAY"
    assert extract_utr_from_narration(narration) == "UTR12345678"
    
    # NACH batched format
    narration2 = "NACH-SETTLE-UTR87654321"
    assert extract_utr_from_narration(narration2) == "UTR87654321"

def test_truncated_narration():
    # String abruptly cut off mid-identifier
    narration = "NEFT-UTR1234..."
    assert extract_utr_from_narration(narration) == "UTR1234"
    
    # Cut off with no trailing dots, just ends abruptly
    narration2 = "NEFT-UTR987"
    assert extract_utr_from_narration(narration2) == "UTR987"

def test_no_identifier_graceful_null():
    # Random text with no UTR marker
    narration = "INTERNAL-TRANSFER-SALARY"
    assert extract_utr_from_narration(narration) is None
    
    # Empty string
    assert extract_utr_from_narration("") is None
    
    # None input
    assert extract_utr_from_narration(None) is None
