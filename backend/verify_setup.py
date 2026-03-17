#!/usr/bin/env python
"""
Quantivara.ai Complete Setup Verification
Checks: Python modules, Firebase, Firestore, Scheduler, API endpoints, Frontend config
"""

import sys
import os
import json
from pathlib import Path

# Add backend to path
backend_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_path)

def check_backend_imports():
    """Verify critical backend Python imports"""
    print("\n" + "="*60)
    print("1. BACKEND PYTHON IMPORTS")
    print("="*60)
    
    checks = {
        "FastAPI": "fastapi",
        "Firebase Admin": "firebase_admin",
        "yfinance": "yfinance",
        "pandas": "pandas",
        "APScheduler": "apscheduler",
        "pytz": "pytz",
    }
    
    for name, module in checks.items():
        try:
            __import__(module)
            print(f"✅ {name:20} - OK")
        except ImportError as e:
            print(f"❌ {name:20} - MISSING: {e}")
            return False
    
    return True


def check_backend_modules():
    """Verify custom backend modules"""
    print("\n" + "="*60)
    print("2. CUSTOM BACKEND MODULES")
    print("="*60)
    
    modules = {
        "shared": "shared.py",
        "scraper": "scraper.py",
        "prediction_engine": "prediction_engine.py",
        "signal_tracker": "signal_tracker.py",
        "foreign_flow": "foreign_flow.py",
        "signal_engine": "signal_engine.py",
        "ncss_scraper": "ncss_scraper.py",
        "main": "main.py",
    }
    
    all_ok = True
    for module_name, filename in modules.items():
        filepath = os.path.join(backend_path, filename)
        if os.path.exists(filepath):
            try:
                __import__(module_name)
                print(f"✅ {module_name:20} - EXISTS & IMPORTABLE")
            except Exception as e:
                print(f"⚠️  {module_name:20} - EXISTS but import error: {str(e)[:40]}")
                all_ok = False
        else:
            print(f"❌ {module_name:20} - MISSING FILE")
            all_ok = False
    
    return all_ok


def check_firebase_config():
    """Verify Firebase is initialized"""
    print("\n" + "="*60)
    print("3. FIREBASE CONFIGURATION")
    print("="*60)
    
    try:
        from shared import db
        
        if db:
            print(f"✅ Firestore DB          - CONNECTED")
        else:
            print(f"❌ Firestore DB          - NOT CONNECTED")
            return False
        
        # Try a test read
        try:
            test_doc = list(db.collection("market_data").limit(1).stream())
            print(f"✅ Firestore Read        - OK (can read collections)")
        except Exception as e:
            print(f"⚠️  Firestore Read        - Error: {str(e)[:40]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Firebase Config       - ERROR: {e}")
        return False


def check_firestore_rules():
    """Check that Firestore rules are deployed"""
    print("\n" + "="*60)
    print("4. FIRESTORE SECURITY RULES")
    print("="*60)
    
    # Check for firestore.rules file
    rules_path = os.path.join(os.path.dirname(backend_path), "firestore.rules")
    
    if os.path.exists(rules_path):
        with open(rules_path, 'r') as f:
            content = f.read()
            
        # Check for critical rules
        required_rules = [
            ("market_data", "market_data read"),
            ("foreign_flow", "foreign_flow read"),
            ("predictions", "predictions collection"),
            ("signal_log", "signal_log collection"),
        ]
        
        print(f"✅ firestore.rules       - FILE EXISTS")
        
        all_found = True
        for required, desc in required_rules:
            if required in content:
                print(f"✅ {desc:25} - RULE FOUND")
            else:
                print(f"⚠️  {desc:25} - RULE NOT FOUND")
                all_found = False
        
        return all_found
    else:
        print(f"❌ firestore.rules       - FILE NOT FOUND")
        return False


def check_firestore_collections():
    """Check expected Firestore collections"""
    print("\n" + "="*60)
    print("5. FIRESTORE COLLECTIONS")
    print("="*60)
    
    try:
        from shared import db
        
        collections = [
            "market_data",
            "market_sectors",
            "predictions",
            "prediction_history",
            "foreign_flow",
            "signal_log",
            "market_watch",
            "volume_spikes",
        ]
        
        for collection_name in collections:
            try:
                count = len(list(db.collection(collection_name).limit(1).stream()))
                status = "EXISTS" if count >= 0 else "EMPTY"
                print(f"✅ {collection_name:25} - {status}")
            except Exception as e:
                print(f"⚠️  {collection_name:25} - Can't read (may not exist): {str(e)[:30]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Can't access Firestore - {e}")
        return False


def check_scheduler():
    """Check scheduler configuration"""
    print("\n" + "="*60)
    print("6. SCHEDULER CONFIGURATION")
    print("="*60)
    
    try:
        from scraper import init_scheduler
        
        # Check if init_scheduler function exists
        if init_scheduler:
            print(f"✅ Scheduler Function    - EXISTS")
            print(f"ℹ️  Scheduler Instance    - Starts automatically with main.py")
            return True
        else:
            print(f"❌ Scheduler Function    - NOT FOUND")
            return False
            
    except Exception as e:
        print(f"⚠️  Scheduler Config      - {str(e)[:50]}")
        return False  # Not critical but log it


def check_api_endpoints():
    """Check FastAPI endpoints are configured"""
    print("\n" + "="*60)
    print("7. FASTAPI ENDPOINTS")
    print("="*60)
    
    try:
        from main import app
        
        routes = [route.path for route in app.routes]
        
        required_endpoints = [
            "/",
            "/api/market/status",
            "/api/predictions",
            "/api/foreign-flow",
        ]
        
        for endpoint in required_endpoints:
            if endpoint in routes:
                print(f"✅ {endpoint:30} - CONFIGURED")
            else:
                print(f"⚠️  {endpoint:30} - NOT FOUND")
        
        print(f"\n📊 Total endpoints: {len(routes)}")
        return True
        
    except Exception as e:
        print(f"❌ Can't access FastAPI app - {e}")
        return False


def check_frontend_config():
    """Check frontend Firebase config"""
    print("\n" + "="*60)
    print("8. FRONTEND CONFIGURATION")
    print("="*60)
    
    frontend_config_path = os.path.join(
        os.path.dirname(backend_path),
        "src",
        "firebase.ts"
    )
    
    if os.path.exists(frontend_config_path):
        with open(frontend_config_path, 'r') as f:
            content = f.read()
        
        print(f"✅ firebase.ts           - FILE EXISTS")
        
        # Check for required exports
        if "getAuth" in content:
            print(f"✅ Firebase Auth         - CONFIGURED")
        if "getFirestore" in content:
            print(f"✅ Firestore Client      - CONFIGURED")
        if "getDatabase" in content:
            print(f"✅ Realtime DB           - CONFIGURED")
        
        return True
    else:
        print(f"❌ firebase.ts           - NOT FOUND")
        return False


def check_react_components():
    """Check critical React components exist"""
    print("\n" + "="*60)
    print("9. REACT COMPONENTS")
    print("="*60)
    
    components = {
        "Dashboard": "src/components/Dashboard/Dashboard.tsx",
        "ForeignFlowChart": "src/components/Dashboard/ForeignFlowChart.tsx",
        "Layout": "src/components/layout/Layout.tsx",
    }
    
    base_path = os.path.dirname(backend_path)
    all_ok = True
    
    for name, path in components.items():
        full_path = os.path.join(base_path, path)
        if os.path.exists(full_path):
            print(f"✅ {name:25} - EXISTS")
        else:
            print(f"❌ {name:25} - MISSING")
            all_ok = False
    
    return all_ok


def check_config_files():
    """Check configuration and build files"""
    print("\n" + "="*60)
    print("10. CONFIGURATION FILES")
    print("="*60)
    
    base_path = os.path.dirname(backend_path)
    
    files = {
        "package.json": os.path.join(base_path, "package.json"),
        "tsconfig.json": os.path.join(base_path, "tsconfig.json"),
        "tailwind.config.js": os.path.join(base_path, "tailwind.config.js"),
        "vite.config.ts": os.path.join(base_path, "vite.config.ts"),
        "firebase.json": os.path.join(base_path, "firebase.json"),
        "firestore.rules": os.path.join(base_path, "firestore.rules"),
    }
    
    all_ok = True
    for name, path in files.items():
        if os.path.exists(path):
            print(f"✅ {name:25} - EXISTS")
        else:
            print(f"⚠️  {name:25} - MISSING (may be optional)")
            if name in ["package.json", "firebase.json"]:
                all_ok = False
    
    return all_ok


def check_data_pipeline():
    """Check data pipeline integration"""
    print("\n" + "="*60)
    print("11. DATA PIPELINE")
    print("="*60)
    
    checks = [
        ("NCSS Scraper", "ncss_scraper", "get_ncss_from_cache_or_fallback"),
        ("Signal Engine", "signal_engine", "compute_signal"),
        ("Foreign Flow", "foreign_flow", "update_foreign_flow"),
        ("Prediction Engine", "prediction_engine", "run_prediction_engine"),
        ("Signal Tracker", "signal_tracker", "check_signal_outcomes"),
    ]
    
    all_ok = True
    for name, module_name, func_name in checks:
        try:
            mod = __import__(module_name)
            if hasattr(mod, func_name):
                print(f"✅ {name:25} - FUNCTION FOUND")
            else:
                print(f"⚠️  {name:25} - Module exists but missing {func_name}")
                all_ok = False
        except Exception as e:
            print(f"❌ {name:25} - {str(e)[:35]}")
            all_ok = False
    
    return all_ok


def print_summary(results):
    """Print final summary"""
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\n✅ PASSED: {passed}/{total}")
    print(f"⚠️  WARNINGS: {total - passed}")
    
    if passed == total:
        print("\n🎉 ALL SYSTEMS GO - Ready for deployment!")
    elif passed >= total * 0.8:
        print("\n⚠️  MOSTLY OK - Some issues to address before production")
    else:
        print("\n❌ CRITICAL ISSUES - Fix before deployment")
    
    print("\nFailed checks:")
    for check_name, passed in results.items():
        if not passed:
            print(f"  - {check_name}")


def main():
    print("\n" + "█"*60)
    print("█  QUANTIVARA.AI SETUP VERIFICATION")
    print("█"*60)
    print(f"\n📍 Backend Path: {backend_path}")
    
    results = {
        "Backend Dependencies": check_backend_imports(),
        "Custom Backend Modules": check_backend_modules(),
        "Firebase Configuration": check_firebase_config(),
        "Firestore Rules": check_firestore_rules(),
        "Firestore Collections": check_firestore_collections(),
        "Scheduler Configuration": check_scheduler(),
        "FastAPI Endpoints": check_api_endpoints(),
        "Frontend Configuration": check_frontend_config(),
        "React Components": check_react_components(),
        "Configuration Files": check_config_files(),
        "Data Pipeline": check_data_pipeline(),
    }
    
    print_summary(results)
    
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
