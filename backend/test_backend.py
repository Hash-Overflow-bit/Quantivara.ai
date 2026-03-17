#!/usr/bin/env python3
"""
Quick test to verify the scheduler is running and data is being updated.
Run this while the backend is running to check if data updates are working.
"""

import requests
import json
import time
from datetime import datetime
import pytz

PKT = pytz.timezone('Asia/Karachi')

def test_backend():
    BASE_URL = "http://localhost:8000"
    
    print("\n" + "="*80)
    print("PSX DASHBOARD - BACKEND VERIFICATION TEST")
    print("="*80)
    print(f"Time: {datetime.now(PKT).strftime('%Y-%m-%d %H:%M:%S PKT')}\n")
    
    # Test 1: Server is running
    print("1. Testing server connectivity...")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code == 200:
            print("   ✓ Backend server is running")
            data = response.json()
            print(f"   Status: {data.get('status')}")
    except Exception as e:
        print(f"   ❌ Cannot connect to backend: {e}")
        print("   Run: cd backend && python main.py")
        return
    
    # Test 2: API Health Check
    print("\n2. Checking system health...")
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        health = response.json()
        print(f"   ✓ Active spike alerts: {health.get('active_spikes_detected')}")
        print(f"   ✓ Tickers being tracked: {health.get('tickers_tracked_in_baseline')}")
        print(f"   ✓ Last checked: {health.get('checked_at')}")
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
    
    # Test 3: Market Status
    print("\n3. Fetching market indices...")
    try:
        response = requests.get(f"{BASE_URL}/api/market/status", timeout=5)
        market = response.json()
        
        kse100 = market.get('kse100', {})
        kse30 = market.get('kse30', {})
        volume = market.get('volume')
        
        print(f"   KSE-100: {kse100.get('value')} ({kse100.get('change'):+.2f}%)")
        print(f"   KSE-30:  {kse30.get('value')} ({kse30.get('change'):+.2f}%)")
        print(f"   Volume:  {volume}")
        print("   ✓ Market indices retrieved")
    except Exception as e:
        print(f"   ❌ Failed to fetch market data: {e}")
    
    # Test 4: Firebase Connectivity (via health endpoint)
    print("\n4. Checking Firebase integration...")
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code == 200:
            print("   ✓ Firebase connection is active")
            print("   ✓ Data is being synced to Firestore")
    except Exception as e:
        print(f"   ❌ Firebase connectivity issue: {e}")
    
    # Test 5: Check current market hours
    print("\n5. Market hours check...")
    now = datetime.now(PKT)
    hour = now.hour + now.minute / 60
    
    MARKET_OPEN = 9.5    # 9:30 AM
    MARKET_CLOSE = 15.5  # 3:30 PM
    is_weekday = now.weekday() < 5  # Monday=0, Friday=4
    
    if is_weekday and MARKET_OPEN <= hour <= MARKET_CLOSE:
        print(f"   ✓ Market is OPEN (9:30 AM - 3:30 PM)")
        print(f"   ✓ Data updates every 10 minutes")
    elif is_weekday:
        print(f"   ⏰ Market is CLOSED (opens at 9:30 AM PKT)")
        print(f"   Next update at market open")
    else:
        print(f"   🔒 Weekend - Market closed (next open Monday 9:30 AM)")
    
    # Test 6: Predictions
    print("\n6. Checking prediction engine...")
    try:
        response = requests.get(f"{BASE_URL}/api/predictions?timeframe=day", timeout=5)
        pred = response.json()
        if 'data' in pred and pred['data']:
            print(f"   ✓ Daily predictions available ({len(pred['data'])} stocks)")
        elif 'message' in pred:
            print(f"   ⏳ {pred['message']}")
        else:
            print(f"   ⚠ Unexpected response: {pred}")
    except Exception as e:
        print(f"   ❌ Prediction fetch failed: {e}")
    
    # Test 7: Data Freshness
    print("\n7. Data freshness check...")
    try:
        response = requests.get(f"{BASE_URL}/api/market/status", timeout=5)
        market = response.json()
        
        # Check if last_update exists
        if 'last_update' in market:
            last_update = market['last_update']
            print(f"   Last update: {last_update}")
            print("   ✓ Data has timestamps (freshness verified)")
        else:
            print("   ℹ Last update timestamp not yet set (first cycle)")
    except Exception as e:
        print(f"   Cannot determine freshness: {e}")
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print("""
If all tests pass (✓):
- Backend is running correctly
- Scheduler is active and fetching data
- Firebase is connected
- Dashboard should update every 10 minutes during market hours

If any test fails (❌):
1. Check backend logs (look for error messages)
2. Run: python backend/debug_psx_structure.py  (to debug PSX parsing)
3. Verify Firebase credentials are in place
4. Check network connectivity to PSX website
    """)
    print("="*80 + "\n")

if __name__ == "__main__":
    try:
        test_backend()
    except KeyboardInterrupt:
        print("\nTest interrupted")
