
import sys
import os
import json
from datetime import datetime

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

import scraper

def test_scrapers():
    print(f"Testing scrapers at {datetime.now()}")
    
    print("\n1. Testing get_psx_page...")
    soup = scraper.get_psx_page()
    if soup:
        print("[OK] Successfully fetched PSX page")
    else:
        print("[FAILED] Failed to fetch PSX page")
        return

    print("\n2. Testing get_market_indices...")
    indices = scraper.get_market_indices()
    if indices:
        print("[OK] Successfully fetched indices:")
        print(json.dumps(indices, indent=2))
    else:
        print("[FAILED] Failed to fetch indices")

    print("\n3. Testing get_market_movers...")
    movers = scraper.get_market_movers()
    if movers:
        print("[OK] Successfully fetched movers:")
        print(json.dumps(movers, indent=2))
    else:
        print("[FAILED] Failed to fetch movers")

    print("\n4. Testing get_all_stocks (first 5)...")
    stocks = scraper.get_all_stocks()
    if stocks:
        print(f"[OK] Successfully fetched {len(stocks)} stocks. First 5:")
        print(json.dumps(stocks[:5], indent=2))
    else:
        print("[FAILED] Failed to fetch stocks")

    print("\n5. Testing get_macro_data...")
    macro = scraper.get_macro_data()
    if macro:
        print("[OK] Successfully fetched macro data:")
        print(json.dumps(macro, indent=2))
    else:
        print("[FAILED] Failed to fetch macro data")

if __name__ == "__main__":
    test_scrapers()
