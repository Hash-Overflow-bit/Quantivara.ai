import os
import sys
import re

# Add current directory to path
sys.path.append(os.getcwd())

from scraper import get_all_stocks, get_announcements, analyze_announcement_sentiment

def debug():
    print("--- DEBUG: SYMBOLS AND ANNOUNCEMENTS ---")
    stocks = get_all_stocks()
    symbols = {s['symbol']: s['price'] for s in stocks}
    print(f"Total symbols fetched: {len(symbols)}")
    print(f"Sample symbols: {list(symbols.keys())[:20]}")

    anncs = get_announcements()
    print(f"Total announcements: {len(anncs)}")

    matches = 0
    for a in anncs[:50]:
        headline = a['headline']
        ann_symbol = a['symbol'].upper()
        sentiment = analyze_announcement_sentiment(headline)
        
        print(f"Ann: [{ann_symbol}] | Sent: {sentiment} | Headline: {headline[:60]}...")
        
        found_match = None
        if ann_symbol in symbols:
            found_match = ann_symbol
        else:
            # Check for partial matches like in the main scraper
            for s in symbols.keys():
                if s == ann_symbol or s.startswith(ann_symbol) or ann_symbol.startswith(s):
                    found_match = s
                    break
        
        if found_match:
            print(f"  >>> MATCHED WITH: {found_match} (Price: {symbols[found_match]})")
            if sentiment != 'neutral':
                matches += 1
                print(f"  *** ACTIONABLE SIGNAL FOUND ***")
        else:
            print(f"  (no price match found in market watch)")

    print(f"\nTotal actionable signals: {matches}")

if __name__ == "__main__":
    debug()
