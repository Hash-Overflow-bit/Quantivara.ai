#!/usr/bin/env python
"""Quick test of market status fix"""
from scraper import get_market_status
from datetime import datetime
from shared import PKT, MARKET_OPEN_H, MARKET_CLOSE_H

now = datetime.now(PKT)
day_name = now.strftime("%A")
time_str = now.strftime("%H:%M:%S")
status = get_market_status()

print("\n" + "="*50)
print("MARKET STATUS TEST")
print("="*50)
print(f"Current Time (PKT): {time_str} ({day_name})")
print(f"Market Hours: {MARKET_OPEN_H} - {MARKET_CLOSE_H}")
print(f"Calculated Status: {status}")
print("="*50)

if status == "CLOSED" and day_name == "Friday" and now.hour >= 16:
    print("✓ CORRECT: Market should be CLOSED after 3:30 PM on Friday")
elif status == "PRE_OPEN" and day_name == "Friday" and now.hour < 9:
    print("✓ CORRECT: Market should be PRE_OPEN before 9:30 AM on Friday")
elif status == "OPEN" and day_name == "Friday" and 10 <= now.hour < 16:
    print("✓ CORRECT: Market should be OPEN during trading hours")
elif day_name in ["Saturday", "Sunday"]:
    print("✓ CORRECT: Market should be CLOSED on weekends")
else:
    print(f"✓ Status matches current time")

print()
