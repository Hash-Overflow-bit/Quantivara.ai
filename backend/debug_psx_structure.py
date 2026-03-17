#!/usr/bin/env python3
"""
Debug script to inspect PSX website HTML structure and verify data accuracy.
Run this to see what data is actually on PSX website vs what we're scraping.
"""

import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import pytz

PKT = pytz.timezone('Asia/Karachi')

def debug_market_watch():
    """Inspect table structure on Market Watch page"""
    print("\n" + "="*80)
    print("PSX MARKET WATCH PAGE DEBUG")
    print("="*80)
    
    url = "https://dps.psx.com.pk/market-watch"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find table
        table = soup.select_one("table.tbl")
        if not table:
            print("❌ Table with class 'tbl' not found!")
            return
        
        rows = table.select("tr")
        print(f"✓ Found table with {len(rows)} rows")
        
        # Examine first 3 rows (header + 2 data rows)
        for row_idx, row in enumerate(rows[:3]):
            cols = row.select("td, th")
            print(f"\nRow {row_idx}: {len(cols)} columns")
            for col_idx, col in enumerate(cols[:12]):  # First 12 columns
                text = col.text.strip()[:50]  # First 50 chars
                tag = col.name
                print(f"  Col {col_idx:2d} <{tag}>: {text}")
        
        # Parse actual stocks
        print("\n" + "-"*80)
        print("PARSED STOCKS (First 5):")
        print("-"*80)
        
        stocks = []
        for row_idx, row in enumerate(rows[1:6]):  # Skip header, take 5 stocks
            cols = row.select("td")
            if len(cols) < 11:
                continue
            
            try:
                symbol = cols[0].text.strip().split("\n")[0].strip()
                price = float(cols[7].text.strip().replace(",", ""))
                change = float(cols[9].text.strip().replace(",", "").replace("%", ""))
                volume = cols[10].text.strip()
                
                stock = {
                    "symbol": symbol,
                    "price": price,
                    "change": change,
                    "volume": volume
                }
                stocks.append(stock)
                
                print(f"{symbol:12} | Price: {price:10.2f} | Change: {change:7.2f}% | Vol: {volume}")
            except Exception as e:
                print(f"❌ Error parsing row {row_idx}: {e}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def debug_psx_index():
    """Debug index data extraction"""
    print("\n" + "="*80)
    print("PSX INDEX DATA DEBUG")
    print("="*80)
    
    url = "https://dps.psx.com.pk/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find index items
        items = soup.select(".topIndices__item")
        print(f"✓ Found {len(items)} index items")
        
        for idx, item in enumerate(items[:5]):  # First 5 indices
            name_el = item.select_one(".topIndices__item__name")
            val_el = item.select_one(".topIndices__item__val")
            change_el = item.select_one(".topIndices__item__changep")
            
            name = name_el.text.strip() if name_el else "?"
            val = val_el.text.strip() if val_el else "?"
            change = change_el.text.strip() if change_el else "?"
            
            print(f"{idx:2d}. {name:10} | Value: {val:15} | Change: {change}")
        
        # Check volume data
        print("\n" + "-"*80)
        print("MARKET STATS:")
        print("-"*80)
        
        reg_item = soup.select_one('.glide__slide[data-key="REG"]')
        if reg_item:
            stats = reg_item.select('.markets__item__stat')
            for stat in stats[:10]:  # First 10 stats
                label_el = stat.select_one('.markets__item__stat__label')
                val_divs = stat.select('div')
                
                label = label_el.text.strip() if label_el else "?"
                val = val_divs[-1].text.strip() if len(val_divs) > 1 else "?"
                
                print(f"{label:20} : {val}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def test_intraday_api():
    """Test intraday data API"""
    print("\n" + "="*80)
    print("PSX INTRADAY DATA API DEBUG")
    print("="*80)
    
    for symbol in ["KSE100", "KSE30"]:
        url = f"https://dps.psx.com.pk/timeseries/intraday/{symbol}"
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            
            if "data" in data:
                points = data["data"]
                print(f"\n{symbol}: {len(points)} data points")
                if points:
                    print(f"  Latest: {points[-1]}")
            else:
                print(f"\n{symbol}: Unexpected response format")
                print(f"  Keys: {list(data.keys())}")
        except Exception as e:
            print(f"\n❌ {symbol}: Error - {e}")

if __name__ == "__main__":
    print(f"\nDebug started at {datetime.now(PKT).strftime('%Y-%m-%d %H:%M:%S PKT')}")
    
    debug_psx_index()
    debug_market_watch()
    test_intraday_api()
    
    print(f"\nDebug completed at {datetime.now(PKT).strftime('%Y-%m-%d %H:%M:%S PKT')}")
