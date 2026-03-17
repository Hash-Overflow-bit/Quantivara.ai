#!/usr/bin/env python
"""Debug script to check foreign_flow collection structure"""
import sys
sys.path.insert(0, '.')
from shared import db

if db:
    print("Checking foreign_flow collection...")
    docs = list(db.collection('foreign_flow').limit(5).stream())
    print(f"Total documents found: {len(docs)}")
    
    if len(docs) == 0:
        print("⚠️  No documents in foreign_flow collection!")
        print("Run: python backend/foreign_flow.py backfill")
    else:
        for i, doc in enumerate(docs, 1):
            data = doc.to_dict()
            print(f"\nDoc {i}:")
            print(f"  Keys: {list(data.keys())}")
            print(f"  date: {data.get('date')}")
            print(f"  net: {data.get('net')}")
            print(f"  net_foreign_flow: {data.get('net_foreign_flow')}")
            print(f"  rolling_5d: {data.get('rolling_5d')}")
            print(f"  signal_state: {data.get('signal_state')}")
else:
    print("✗ Database not initialized")
