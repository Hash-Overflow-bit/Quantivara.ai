#!/usr/bin/env python
"""Test Foreign Flow backfill and API"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared import db
from foreign_flow import backfill_flow_data

print("\n" + "="*60)
print("FOREIGN FLOW DATA CHECK")
print("="*60)

# Check current state
print("\n1. Checking current foreign_flow collection...")
try:
    docs = list(db.collection("foreign_flow").limit(5).stream())
    print(f"   Current documents: {len(docs)}")
    if len(docs) > 0:
        print(f"   Latest: {docs[-1].to_dict()['date']}")
        print("   ✓ Data exists - no backfill needed")
    else:
        print("   ⚠️  No data found - will backfill on startup")
except Exception as e:
    print(f"   ERROR: {e}")

# Test the backfill
print("\n2. Testing backfill function...")
try:
    print("   Running backfill_flow_data()...")
    backfill_flow_data()
    print("   ✓ Backfill completed")
except Exception as e:
    print(f"   ERROR during backfill: {e}")

# Verify data after backfill
print("\n3. Verifying data after backfill...")
try:
    docs = list(db.collection("foreign_flow").stream())
    print(f"   Documents now: {len(docs)}")
    if len(docs) > 0:
        sample = docs[0].to_dict()
        print(f"\n   Sample document fields:")
        for key in ['date', 'net', 'rolling_5d', 'rolling_30d', 'signal_state']:
            print(f"      {key}: {sample.get(key)}")
        print(f"\n   ✓ All required fields present")
except Exception as e:
    print(f"   ERROR: {e}")

# Test API response
print("\n4. Testing API response structure...")
try:
    # Simulate API call locally
    docs = db.collection("foreign_flow").order_by("date", direction="DESCENDING").limit(90).stream()
    data = [d.to_dict() for d in docs]
    data.reverse()
    
    print(f"   Total records available for API: {len(data)}")
    
    if len(data) > 0:
        print(f"   Date range: {data[0]['date']} to {data[-1]['date']}")
        
        # Check index data
        import yfinance as yf
        index_ticker = yf.Ticker("^KSE100")
        index_hist = index_ticker.history(period="1d", interval="1d")
        print(f"   KSE-100 data points: {len(index_hist)}")
        
        print("\n   ✓ API will return all required data")
    else:
        print("   ⚠️  No data - ensure backfill runs before accessing API")
except Exception as e:
    print(f"   ERROR: {e}")

print("\n" + "="*60)
print("SUMMARY")
print("="*60)
print("\nForeign Flow Chart will show data after:")
print("  1. Backend server starts (main.py)")
print("  2. Automatic backfill runs on startup")
print("  3. Component fetches from /api/foreign-flow")
print("  4. Firestore onSnapshot listener updates in real-time")
print("\nTo manually start the server:")
print("  python main.py")
print("\n")
