"""
seed_sectors.py — "Honest" Sector Performance Calculator
Calculates sector averages by looking at the component changes of KSE-100 stocks.
Used to populate Firestore 'market_sectors' so the D6 signal in the prediction engine fires correctly.
"""
import os
import json
import time
import pandas as pd
import yfinance as yf
from datetime import datetime
from shared import db, PKT

def seed_sector_data():
    print("📊 Calculating 'Honest' Sector Performance from KSE-100 components...")
    
    kse100_path = os.path.join(os.path.dirname(__file__), "kse100.json")
    if not os.path.exists(kse100_path):
        print("❌ kse100.json not found.")
        return
        
    with open(kse100_path, 'r') as f:
        tickers = json.load(f)
    
    # Map to hold {sector_name: [list_of_percent_changes]}
    sector_map = {}
    processed = 0
    
    print(f"Processing {len(tickers)} stocks...")
    
    for symbol in tickers:
        try:
            ticker = yf.Ticker(f"{symbol}.KA")
            # Get 5 days of history to get a reliable daily change
            hist = ticker.history(period="5d", interval="1d", auto_adjust=False)
            if len(hist) < 2:
                continue
            
            info = ticker.info
            sector = info.get('sector', 'Unknown')
            
            # Calculate daily % change
            prev_close = hist['Close'].iloc[-2]
            last_close = hist['Close'].iloc[-1]
            if prev_close > 0:
                change = ((last_close - prev_close) / prev_close) * 100
                
                if sector not in sector_map:
                    sector_map[sector] = []
                sector_map[sector].append(change)
                
            processed += 1
            if processed % 10 == 0:
                print(f"  [{processed}/{len(tickers)}] stocks processed...")
                
        except Exception as e:
            # print(f"Error processing {symbol}: {e}")
            continue
            
    # Calculate averages
    final_sectors = []
    for name, changes in sector_map.items():
        if not changes: continue
        avg_change = sum(changes) / len(changes)
        final_sectors.append({
            "name": name,
            "change": round(avg_change, 2)
        })
        
    # Sort by performance
    final_sectors = sorted(final_sectors, key=lambda x: x['change'], reverse=True)
    
    print("\n✅ Sector Results:")
    for s in final_sectors:
        print(f"  {s['name']:<25}: {s['change']:>6}%")
        
    if db:
        db.collection("market_sectors").document("latest").set({
            "updated_at": datetime.now(PKT).isoformat(),
            "sectors": final_sectors
        })
        print("\n🚀 Pushed real sector data to Firestore 'market_sectors/latest'")
    else:
        print("\n❌ Firestore not initialized, skipping push.")

if __name__ == "__main__":
    seed_sector_data()
