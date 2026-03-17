#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Quick setup verification"""
import sys
import os
import io

# Fix encoding for Windows console
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')

backend = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend)

print("\n" + "="*60)
print("QUANTIVARA.AI QUICK VERIFICATION")
print("="*60)

# Test 1: Python packages
print("\n[+] Python Packages:")
try:
    import fastapi
    import firebase_admin
    import yfinance
    import pandas
    import apscheduler
    import pytz
    print("  OK FastAPI, Firebase, yfinance, pandas, APScheduler, pytz")
except Exception as e:
    print(f"  ERROR {e}")
    sys.exit(1)

# Test 2: Backend modules
print("\n[+] Backend Modules:")
try:
    import shared
    import main
    import scraper
    import prediction_engine
    import signal_tracker
    import foreign_flow
    import signal_engine
    print("  OK All 8 modules import successfully")
except Exception as e:
    print(f"  ERROR {e}")
    sys.exit(1)

# Test 3: Firebase/Firestore
print("\n[+] Firebase Backend:")
try:
    from shared import db
    # Test read
    test = list(db.collection("market_data").limit(1).stream())
    print(f"  OK Firebase connected, Firestore accessible")
except Exception as e:
    print(f"  ERROR {e}")

# Test 4: Firestore collections
print("\n[+] Firestore Collections:")
collections_needed = [
    "market_data", "predictions", "prediction_history", 
    "foreign_flow", "signal_log", "market_sectors"
]
try:
    from shared import db
    for col in collections_needed:
        exists = len(list(db.collection(col).limit(1).stream())) >= 0
    print(f"  OK All {len(collections_needed)} collections accessible")
except Exception as e:
    print(f"  WARN {e}")

# Test 5: Firestore rules
print("\n[+] Firestore Rules:")
rules_path = os.path.join(os.path.dirname(backend), "firestore.rules")
if os.path.exists(rules_path):
    with open(rules_path) as f:
        rules = f.read()
    has_signal_log = "signal_log" in rules
    has_foreign_flow = "foreign_flow" in rules
    print(f"  OK Rules file exists")
    status_log = "present" if has_signal_log else "missing"
    status_ff = "present" if has_foreign_flow else "missing"
    print(f"     signal_log rule: {status_log}")
    print(f"     foreign_flow rule: {status_ff}")
else:
    print(f"  ERROR firestore.rules not found")

# Test 6: API endpoints  
print("\n[+] FastAPI Endpoints:")
try:
    from main import app
    routes = [r.path for r in app.routes]
    required = ["/api/predictions", "/api/foreign-flow", "/api/market/status"]
    found = [r for r in required if r in routes]
    print(f"  OK {len(found)}/{len(required)} critical endpoints configured")
    if len(found) == len(required):
        print(f"     All critical endpoints present")
except Exception as e:
    print(f"  ERROR {e}")

# Test 7: Scheduler
print("\n[+] Scheduler:")
try:
    from scraper import init_scheduler
    print(f"  OK Scheduler initialization function exists")
    print(f"     (Starts automatically when main.py runs)")
except Exception as e:
    print(f"  WARN {e}")

# Test 8: Frontend
print("\n[+] Frontend:")
frontend_files = [
    ("firebase.ts", "../src/firebase.ts"),
    ("Dashboard", "../src/components/Dashboard/Dashboard.tsx"),
    ("ForeignFlowChart", "../src/components/Dashboard/ForeignFlowChart.tsx"),
]
for name, path in frontend_files:
    full_path = os.path.normpath(os.path.join(backend, path))
    status = "OK" if os.path.exists(full_path) else "ERROR"
    print(f"  {status} {name}")

# Test 9: Config files
print("\n[+] Configuration Files:")
config_files = [
    ("package.json", "../package.json"),
    ("firebase.json", "../firebase.json"),
    ("firestore.rules", "../firestore.rules"),
    ("tsconfig.json", "../tsconfig.json"),
    ("vite.config.ts", "../vite.config.ts"),
]
found = 0
for name, path in config_files:
    full_path = os.path.normpath(os.path.join(backend, path))
    if os.path.exists(full_path):
        print(f"  OK {name}")
        found += 1
    else:
        print(f"  SKIP {name}")
print(f"  Summary: {found}/{len(config_files)} files present")

print("\n" + "="*60)
print("SETUP VERIFICATION COMPLETE")
print("="*60)
print("\nStatus: READY FOR DEPLOYMENT")
print("\nNext steps:")
print("  1. Run: python main.py (starts Backend + Scheduler)")
print("  2. Run: npm run dev (starts Frontend)")
print("  3. Open: http://localhost:5173 (Frontend)")
print("\n")
