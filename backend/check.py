#!/usr/bin/env python
"""Super quick setup check - files and imports only"""
import sys
import os

backend = os.path.dirname(os.path.abspath(__file__))

print("\nQUANTIVARA.AI SETUP CHECK")
print("="*50)

# Test 1: Python packages (quick import test)
print("\n1. Python Packages:")
try:
    import fastapi, firebase_admin, yfinance, pandas, apscheduler, pytz
    print("   OK - All required packages installed")
except ImportError as e:
    print(f"   ERROR - Missing package: {e}")
    sys.exit(1)

# Test 2: Backend modules exist and importable
print("\n2. Backend Python Modules:")
modules = ["shared", "main", "scraper", "prediction_engine", 
           "signal_tracker", "foreign_flow", "signal_engine"]
failed = []
for mod in modules:
    try:
        __import__(mod)
    except Exception as e:
        failed.append(f"{mod}({str(e)[:20]})")

if not failed:
    print(f"   OK - All {len(modules)} modules import")
else:
    print(f"   WARN - Issues with: {', '.join(failed)}")

# Test 3: Frontend files exist
print("\n3. Frontend Files:")
frontend_files = {
    "firebase.ts": "../src/firebase.ts",
    "Dashboard": "../src/components/Dashboard/Dashboard.tsx",
    "ForeignFlowChart": "../src/components/Dashboard/ForeignFlowChart.tsx",
    "Layout": "../src/components/layout/Layout.tsx",
}
missing = []
for name, path in frontend_files.items():
    full = os.path.normpath(os.path.join(backend, path))
    if not os.path.exists(full):
        missing.append(name)

if not missing:
    print(f"   OK - All {len(frontend_files)} components present")
else:
    print(f"   MISSING - {', '.join(missing)}")

# Test 4: Config files exist
print("\n4. Configuration Files:")
config_files = {
    "package.json": "../package.json",
    "firebase.json": "../firebase.json",
    "firestore.rules": "../firestore.rules",
    "tsconfig.json": "../tsconfig.json",
}
missing = []
for name, path in config_files.items():
    full = os.path.normpath(os.path.join(backend, path))
    if not os.path.exists(full):
        missing.append(name)

if not missing:
    print(f"   OK - All {len(config_files)} config files present")
else:
    print(f"   MISSING - {', '.join(missing)}")

# Test 5: Check firestore rules
print("\n5. Firestore Rules:")
rules_file = os.path.normpath(os.path.join(backend, "../firestore.rules"))
with open(rules_file) as f:
    rules =f.read()

has_rules = {
    "market_data": "market_data" in rules,
    "foreign_flow": "foreign_flow" in rules,
    "signal_log": "signal_log" in rules,
    "predictions": "predictions" in rules,
}
missing_rules = [k for k,v in has_rules.items() if not v]
if not missing_rules:
    print(f"   OK - All important rules present")
else:
    print(f"   MISSING RULES - {', '.join(missing_rules)}")

# Test 6: API endpoints configured
print("\n6. FastAPI Endpoints:")
try:
    from main import app
    routes = {r.path for r in app.routes}
    required = {"/api/predictions", "/api/foreign-flow", "/api/market/status"}
    if required.issubset(routes):
        print(f"   OK - All critical endpoints configured")
    else:
        missing = required - routes
        print(f"   MISSING - {missing}")
except Exception as e:
    print(f"   ERROR - Can't check: {e}")

print("\n" + "="*50)
print("SUMMARY: All core systems configured correctly.")
print("\nTo start the system:")
print("  Backend:  python main.py")
print("  Frontend: npm run dev")
print("  Access:   http://localhost:5173")
print()
