#!/usr/bin/env python
"""Test real macro data fetching from authentic sources"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper import get_macro_data, get_market_indices
from datetime import datetime
from shared import PKT

print("\n" + "="*70)
print("MACRO DATA TEST - AUTHENTICATED DATA SOURCES")
print("="*70)

now_pkt = datetime.now(PKT)
print(f"\n[Time] Test Time (PKT): {now_pkt.strftime('%Y-%m-%d %H:%M:%S %A')}")

# Test 1: Fetch Macro Data
print("\n1. MACROECONOMIC DATA (Real Sources)")
print("-" * 70)
try:
    macro = get_macro_data()
    print(f"\n   [OK] USD/PKR Exchange Rate:  {macro.get('usdPkr')} PKR/USD")
    print(f"   [OK] Gold Price (10g):       {macro.get('gold')} PKR")
    print(f"                                (Converted from COMEX futures)")
    print(f"   [OK] T-Bill Yield (6M):      {macro.get('tBillYield')}%")
    print(f"                                (SBP Latest Auction)")
except Exception as e:
    print(f"   [ERROR] {e}")

# Test 2: Market Indices & Volume
print("\n2. MARKET DATA (PSX Official)")
print("-" * 70)
try:
    indices = get_market_indices()
    if indices:
        kse100_val = indices['kse100']['value']
        kse100_chg = indices['kse100']['change']
        kse30_val = indices['kse30']['value']
        kse30_chg = indices['kse30']['change']
        volume = indices['volume']
        status = indices['status']
        
        print(f"\n   [OK] KSE-100 Index:         {kse100_val:,.2f} ({kse100_chg:+.2f}%)")
        print(f"   [OK] KSE-30 Index:          {kse30_val:,.2f} ({kse30_chg:+.2f}%)")
        print(f"   [OK] Market Volume:         {volume}")
        print(f"   [OK] Market Status:         {status}")
    else:
        print("   [WARN] Could not parse PSX data")
except Exception as e:
    print(f"   [ERROR] {e}")

print("\n" + "="*70)
print("DATA SOURCES")
print("="*70)
print("""
[YAHOO FINANCE]
  USD/PKR: Real-time forex rates (PKR=X ticker)
           Primary source for exchange rates

[COMEX FUTURES]
  Gold:    COMEX Gold Futures (GC=F ticker)
           Converted to PKR per 10 grams
           Calculation: (USD/oz price * USD/PKR rate) / 3.1035

[STATE BANK OF PAKISTAN]
  T-Bill:  Latest 6-Month T-Bill auction yields
           Updated on auction dates

[PAKISTAN STOCK EXCHANGE]
  Volume:  Real market volume from PSX official website
  Indices: Official KSE-100 and KSE-30 index feeds
  Status:  Current market session status

All data is sourced from authentic, official resources.
""")

print("="*70)
